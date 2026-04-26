import os
import time
import uuid
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from supabase import Client, create_client

load_dotenv()

st.set_page_config(
    page_title="GateKeeper",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

PASS_DURATION_SECONDS = 5 * 60
PHOTO_BUCKET = "student-photos"


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .main {
                background-color: #0b1220;
                color: #f8fafc;
            }
            .stApp, [data-testid="stAppViewContainer"] {
                background: #0b1220;
                color: #f8fafc;
            }
            .title-xl {
                font-size: 2rem;
                font-weight: 800;
                margin-bottom: 0.5rem;
            }
            .serial-xl {
                font-size: 2.2rem;
                font-weight: 900;
                color: #facc15;
                letter-spacing: 0.02em;
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
            .secret-banner {
                font-size: 1.1rem;
                font-weight: 800;
                text-align: center;
                border-radius: 10px;
                padding: 0.7rem;
                margin: 0.8rem 0;
                color: #0f172a;
                background: #67e8f9;
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


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment.")
        st.stop()
    return create_client(url, key)


def init_state() -> None:
    defaults = {
        "access_token": None,
        "user_id": None,
        "email": None,
        "base_url": os.getenv("APP_BASE_URL", "http://localhost:8501"),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def sign_up(client: Client, email: str, password: str) -> None:
    response = client.auth.sign_up({"email": email, "password": password})
    user = getattr(response, "user", None)
    if user:
        st.success("Signup successful. Check your email if confirmation is enabled.")
    else:
        st.warning("Signup submitted. Please verify account settings in Supabase Auth.")


def sign_in(client: Client, email: str, password: str) -> None:
    response = client.auth.sign_in_with_password({"email": email, "password": password})
    session = response.session
    user = response.user
    if not session or not user:
        st.error("Login failed. Check email/password.")
        return
    st.session_state.access_token = session.access_token
    st.session_state.user_id = user.id
    st.session_state.email = user.email
    st.success("Logged in.")
    st.rerun()


def sign_out(client: Client) -> None:
    client.auth.sign_out()
    st.session_state.access_token = None
    st.session_state.user_id = None
    st.session_state.email = None
    st.rerun()


def authenticated_client(client: Client) -> Client:
    if st.session_state.access_token:
        client.auth.set_session(
            access_token=st.session_state.access_token,
            refresh_token="",
        )
    return client


def upload_photo(client: Client, user_id: str, file) -> str:
    ext = file.name.split(".")[-1].lower()
    path = f"{user_id}/{uuid.uuid4()}.{ext}"
    file_bytes = file.read()
    client.storage.from_(PHOTO_BUCKET).upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": file.type or "image/jpeg", "upsert": "false"},
    )
    return path


def get_public_photo_url(client: Client, path: str) -> str:
    if not path:
        return ""
    return client.storage.from_(PHOTO_BUCKET).get_public_url(path)


def get_device_record(client: Client, user_id: str):
    result = (
        client.table("student_devices")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def upsert_device_record(client: Client, payload: dict):
    client.table("student_devices").upsert(payload, on_conflict="user_id").execute()


def get_daily_secret_color(client: Client) -> str:
    result = (
        client.table("security_config")
        .select("value")
        .eq("key", "daily_secret_color")
        .limit(1)
        .execute()
    )
    if result.data and isinstance(result.data, list):
        first_row = result.data[0]
        if isinstance(first_row, dict):
            color = first_row.get("value")
            if isinstance(color, str) and color.strip():
                return color
    return "UNKNOWN"


def issue_pass(client: Client, user_id: str) -> None:
    now = datetime.now(timezone.utc)
    expires = now.timestamp() + PASS_DURATION_SECONDS
    expires_iso = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
    client.table("student_devices").update(
        {"pass_issued_at": now.isoformat(), "pass_expires_at": expires_iso}
    ).eq("user_id", user_id).execute()


def is_pass_valid(device: dict) -> bool:
    expires = device.get("pass_expires_at")
    if not expires:
        return False
    expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    return datetime.now(timezone.utc) <= expires_at


def render_auth(client: Client) -> None:
    st.markdown('<div class="title-xl">Campus Device Security System</div>', unsafe_allow_html=True)
    mode = st.radio("Authentication", ["Login", "Sign Up"], horizontal=True)
    with st.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Continue")
    if submit:
        try:
            if mode == "Sign Up":
                sign_up(client, email, password)
            else:
                sign_in(client, email, password)
        except Exception as exc:
            st.error(f"Auth error: {exc}")


def render_registration(client: Client, user_id: str):
    st.subheader("Student Registration")
    existing = get_device_record(client, user_id)
    existing_data = existing if isinstance(existing, dict) else {}
    with st.form("registration_form"):
        full_name = st.text_input("Full Name", value=existing_data.get("full_name", ""))
        department = st.text_input("Department", value=existing_data.get("department", ""))
        student_id = st.text_input("Student ID", value=existing_data.get("student_id", ""))
        laptop_brand = st.text_input("Laptop Brand", value=existing_data.get("laptop_brand", ""))
        serial_number = st.text_input(
            "Serial Number", value=existing_data.get("serial_number", "")
        )
        photo = st.file_uploader("Profile Picture", type=["png", "jpg", "jpeg", "webp"])
        save = st.form_submit_button("Save Registration")

    if save:
        if not all([full_name, department, student_id, laptop_brand, serial_number]):
            st.error("All fields except profile picture are required.")
            return
        try:
            photo_path = existing_data.get("profile_image_path")
            if photo:
                photo_path = upload_photo(client, user_id, photo)
            upsert_device_record(
                client,
                {
                    "user_id": user_id,
                    "full_name": full_name,
                    "department": department,
                    "student_id": student_id,
                    "laptop_brand": laptop_brand,
                    "serial_number": serial_number,
                    "profile_image_path": photo_path,
                },
            )
            st.success("Registration saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save registration: {exc}")


def render_pass(client: Client, user_id: str):
    st.subheader("Scan-to-Exit Pass")
    device = get_device_record(client, user_id)
    device_data = device if isinstance(device, dict) else {}
    if not device_data:
        st.warning("Please complete registration first.")
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Generate / Refresh 5-min Pass", use_container_width=True):
            try:
                issue_pass(client, user_id)
                st.success("New pass generated.")
                st.rerun()
            except Exception as exc:
                st.error(f"Pass generation failed: {exc}")
    with col2:
        currently_stolen = bool(device_data.get("is_stolen", False))
        label = "Mark Device Safe" if currently_stolen else "Flag As Stolen"
        if st.button(label, type="primary", use_container_width=True):
            try:
                client.table("student_devices").update(
                    {"is_stolen": not currently_stolen}
                ).eq("user_id", user_id).execute()
                st.rerun()
            except Exception as exc:
                st.error(f"Could not update stolen status: {exc}")

    qr_link = f"{st.session_state.base_url}/?route=verify"
    st.code(qr_link, language="text")
    st.caption("Use this URL in your QR generator. Route key is `route=verify`.")

    if not is_pass_valid(device_data):
        st.error("Pass expired or not generated yet. Generate a fresh 5-minute pass.")
        return

    render_verify_card(client, device_data)


def render_verify_card(client: Client, device: dict):
    st_autorefresh(interval=1000, key="clock_refresh")
    now_str = datetime.now().strftime("%H:%M:%S")
    secret_color = get_daily_secret_color(client)

    if device.get("is_stolen", False):
        st.markdown(
            """
            <div class="flash-red">
                <div class="flash-red-text">STOLEN DEVICE - ALERT SECURITY</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    photo_url = get_public_photo_url(client, device.get("profile_image_path") or "")
    st.markdown('<div class="pass-card">', unsafe_allow_html=True)
    if photo_url:
        st.image(photo_url, caption="Student Photo", use_container_width=True)
    st.markdown(
        f'<div class="name-xl">{device.get("full_name", "Unknown Student")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="serial-xl">{device.get("serial_number", "NO SERIAL")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="clock">LIVE TIME: {now_str}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="secret-banner">DAILY SECRET COLOR: {secret_color}</div>',
        unsafe_allow_html=True,
    )

    expires = device.get("pass_expires_at", "")
    st.markdown(f'<div class="expiry">Pass Expires: {expires}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def main():
    inject_css()
    init_state()
    client = get_supabase_client()
    client = authenticated_client(client)

    route = st.query_params.get("route", "")

    if not st.session_state.user_id:
        render_auth(client)
        return

    st.sidebar.write(f"Logged in as: {st.session_state.email}")
    if st.sidebar.button("Logout"):
        sign_out(client)

    if route == "verify":
        st.markdown('<div class="title-xl">Guard Verify View</div>', unsafe_allow_html=True)
        device = get_device_record(client, st.session_state.user_id)
        device_data = device if isinstance(device, dict) else {}
        if not device_data:
            st.warning("No registered device found for this account.")
            return
        if not is_pass_valid(device_data):
            st.error("Pass has expired. Student must generate a fresh pass.")
            return
        render_verify_card(client, device_data)
        return

    tab1, tab2 = st.tabs(["Registration", "Exit Pass"])
    with tab1:
        render_registration(client, st.session_state.user_id)
    with tab2:
        render_pass(client, st.session_state.user_id)


if __name__ == "__main__":
    main()
