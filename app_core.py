import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import extra_streamlit_components as stx  # type: ignore[reportMissingImports]
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

PASS_DURATION_SECONDS = 5 * 60
PHOTO_BUCKET = "student-photos"


def inject_css() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stAppViewBlockContainer"] > div:first-child {
                opacity: 1 !important;
            }
            .stApp [data-testid="stVerticalBlock"] > div {
                opacity: 1 !important;
            }
            .main, .stApp, [data-testid="stAppViewContainer"] {
                background: #0b1220;
                color: #f8fafc;
            }
            .title-xl {
                font-size: 2rem;
                font-weight: 800;
                margin-bottom: 0.5rem;
            }
            .serial-xl {
                font-size: 3.4rem;
                font-weight: 900;
                color: #facc15;
                letter-spacing: 0.02em;
                line-height: 1.2;
            }
            .name-xl {
                font-size: 1.7rem;
                font-weight: 800;
            }
            .clock {
                font-size: 2rem;
                font-weight: 900;
                text-align: center;
                background: #111827;
                border: 2px solid #22c55e;
                border-radius: 12px;
                padding: 0.8rem;
                margin: 0.8rem 0;
            }
            .pass-card {
                border: 2px solid #38bdf8;
                border-radius: 14px;
                padding: 1rem;
                background: #111827;
            }
            .flash-red {
                animation: flash-bg 1s infinite;
                border-radius: 14px;
                padding: 1rem;
                border: 4px solid #ffffff;
                text-align: center;
            }
            .flash-red-text {
                color: #ffffff;
                font-size: 2rem;
                font-weight: 900;
                text-transform: uppercase;
            }
            @keyframes flash-bg {
                0% { background: #ff0000; }
                50% { background: #7f0000; }
                100% { background: #ff0000; }
            }
            .expiry {
                font-size: 1rem;
                font-weight: 700;
                color: #fca5a5;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def set_page(page_title: str) -> None:
    st.set_page_config(
        page_title=page_title,
        page_icon="🛡️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )


def init_state() -> None:
    defaults = {
        "access_token": None,
        "refresh_token": None,
        "user_id": None,
        "email": None,
        "base_url": os.getenv("APP_BASE_URL", "https://keepstudent.streamlit.app/"),
        "auth_restored_from_cookie": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_cookie_manager() -> stx.CookieManager:
    manager = st.session_state.get("cookie_manager")
    if manager is None:
        manager = stx.CookieManager()
        st.session_state["cookie_manager"] = manager
    return manager


def _cookie_expiry(days: int = 30) -> datetime:
    return datetime.utcnow() + timedelta(days=days)


def persist_auth_cookies() -> None:
    manager = get_cookie_manager()
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    user_id = st.session_state.get("user_id")
    email = st.session_state.get("email")
    expires_at = _cookie_expiry(30)

    if isinstance(access_token, str) and access_token:
        manager.set("gk_access_token", access_token, expires_at=expires_at)
    if isinstance(refresh_token, str) and refresh_token:
        manager.set("gk_refresh_token", refresh_token, expires_at=expires_at)
    if isinstance(user_id, str) and user_id:
        manager.set("gk_user_id", user_id, expires_at=expires_at)
    if isinstance(email, str) and email:
        manager.set("gk_email", email, expires_at=expires_at)


def clear_auth_cookies() -> None:
    manager = get_cookie_manager()
    manager.delete("gk_access_token")
    manager.delete("gk_refresh_token")
    manager.delete("gk_user_id")
    manager.delete("gk_email")


def restore_auth_from_cookies() -> None:
    if st.session_state.get("auth_restored_from_cookie"):
        return

    manager = get_cookie_manager()
    access_token = manager.get("gk_access_token")
    refresh_token = manager.get("gk_refresh_token")
    user_id = manager.get("gk_user_id")
    email = manager.get("gk_email")

    if (
        isinstance(access_token, str)
        and access_token
        and isinstance(refresh_token, str)
        and refresh_token
        and isinstance(user_id, str)
        and user_id
    ):
        st.session_state["access_token"] = access_token
        st.session_state["refresh_token"] = refresh_token
        st.session_state["user_id"] = user_id
        st.session_state["email"] = email if isinstance(email, str) else None

    st.session_state["auth_restored_from_cookie"] = True


def get_anon_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY.")
        st.stop()
    return create_client(url, key)


def get_service_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")
        st.stop()
    return create_client(url, key)


def authenticated_client(client: Client) -> Client:
    token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if isinstance(token, str) and token and isinstance(refresh_token, str) and refresh_token:
        client.auth.set_session(access_token=token, refresh_token=refresh_token)
    return client


def sign_in(client: Client, email: str, password: str) -> None:
    response = client.auth.sign_in_with_password({"email": email, "password": password})
    if not response.session or not response.user:
        st.error("Login failed.")
        return
    st.session_state.access_token = response.session.access_token
    st.session_state.refresh_token = response.session.refresh_token
    st.session_state.user_id = response.user.id
    st.session_state.email = response.user.email
    persist_auth_cookies()
    st.rerun()


def sign_out(client: Client) -> None:
    client.auth.sign_out()
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.user_id = None
    st.session_state.email = None
    clear_auth_cookies()
    st.rerun()


def is_admin() -> bool:
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    user_email = str(st.session_state.get("email") or "").strip().lower()
    return bool(admin_email and user_email and admin_email == user_email)


def get_device_record_by_user_id(client: Client, user_id: str) -> dict[str, Any]:
    result = (
        client.table("student_devices")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if result.data and isinstance(result.data, list) and isinstance(result.data[0], dict):
        return result.data[0]
    return {}


def get_device_record_for_verify(client: Client, user_id: str, serial_number: str) -> dict[str, Any]:
    result = (
        client.table("student_devices")
        .select("*")
        .eq("user_id", user_id)
        .eq("serial_number", serial_number)
        .limit(1)
        .execute()
    )
    if result.data and isinstance(result.data, list) and isinstance(result.data[0], dict):
        return result.data[0]
    return {}


def upsert_device_record(client: Client, payload: dict[str, Any]) -> None:
    client.table("student_devices").upsert(payload, on_conflict="user_id").execute()


def upload_photo(client: Client, user_id: str, file_obj: Any) -> str:
    ext = str(file_obj.name).split(".")[-1].lower()
    path = f"{user_id}/{uuid.uuid4()}.{ext}"
    data = file_obj.read()
    client.storage.from_(PHOTO_BUCKET).upload(
        path=path,
        file=data,
        file_options={"content-type": file_obj.type or "image/jpeg", "upsert": "false"},
    )
    return path


def get_public_photo_url(client: Client, path: str) -> str:
    if not path:
        return ""
    return client.storage.from_(PHOTO_BUCKET).get_public_url(path)


def issue_pass(client: Client, user_id: str) -> str:
    now = datetime.now(timezone.utc)
    expires_ts = int(now.timestamp()) + PASS_DURATION_SECONDS
    expires_at = datetime.fromtimestamp(expires_ts, tz=timezone.utc).isoformat()
    client.table("student_devices").update(
        {"pass_issued_at": now.isoformat(), "pass_expires_at": expires_at}
    ).eq("user_id", user_id).execute()
    return expires_at


def is_pass_valid(device: dict[str, Any]) -> bool:
    expires = device.get("pass_expires_at")
    if not isinstance(expires, str) or not expires:
        return False
    expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    return datetime.now(timezone.utc) <= expires_at


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def generate_verify_token(user_id: str, serial_number: str, expires_ts: int) -> str:
    secret = os.getenv("PASS_SIGNING_SECRET", "")
    if not secret:
        raise ValueError("PASS_SIGNING_SECRET is not configured.")
    payload = {"uid": user_id, "sn": serial_number, "exp": expires_ts}
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"


def verify_token(token: str) -> dict[str, Any]:
    secret = os.getenv("PASS_SIGNING_SECRET", "")
    if not secret:
        return {}
    if "." not in token:
        return {}
    payload_b64, sig_b64 = token.split(".", maxsplit=1)
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    try:
        provided = _b64url_decode(sig_b64)
    except Exception:
        return {}
    if not hmac.compare_digest(expected, provided):
        return {}
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    exp = payload.get("exp")
    uid = payload.get("uid")
    serial = payload.get("sn")
    if not isinstance(exp, int) or not isinstance(uid, str) or not isinstance(serial, str):
        return {}
    if int(time.time()) > exp:
        return {}
    return payload
