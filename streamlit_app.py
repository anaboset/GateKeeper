import csv
import io
from datetime import date, datetime, time, timezone
from typing import Any

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app_core import (
    authenticated_client,
    get_anon_client,
    get_device_record_by_user_id,
    get_public_photo_url,
    get_service_client,
    init_state,
    inject_css,
    is_admin,
    is_pass_valid,
    issue_pass,
    restore_auth_from_cookies,
    set_page,
    sign_in,
    sign_out,
    upsert_device_record,
    upload_photo,
)


def render_auth() -> None:
    st.markdown('<div class="title-xl">GateKeeper Login</div>', unsafe_allow_html=True)
    st.caption("No self-signup. Accounts are created by system admin.")
    with st.form("auth_form", clear_on_submit=False):
        email = st.text_input("Email", key="auth_email")
        password = st.text_input("Password", type="password", key="auth_password")
        submit = st.form_submit_button("Login", key="auth_login_button")
    if submit:
        client = get_anon_client()
        try:
            sign_in(client, email, password)
        except Exception as exc:
            st.error(f"Login error: {exc}")


def render_admin_registration() -> None:
    st.subheader("Admin: Register / Update Student Device")
    st.info("Create student login credentials in Supabase Auth first, then register their device here.")
    service_client = get_service_client()

    with st.form("admin_registration_form"):
        student_user_id = st.text_input("Student Auth User ID (UUID)", key="admin_student_user_id")
        full_name = st.text_input("Full Name", key="admin_full_name")
        department = st.text_input("Department", key="admin_department")
        student_id = st.text_input("Student ID", key="admin_student_id")
        laptop_brand = st.text_input("Laptop Brand", key="admin_laptop_brand")
        serial_number = st.text_input("Serial Number", key="admin_serial_number")
        profile_photo = st.file_uploader(
            "Profile Picture", type=["png", "jpg", "jpeg", "webp"], key="admin_profile_photo"
        )
        save = st.form_submit_button("Save Registration", key="admin_save_registration")

    if not save:
        return
    if not all([student_user_id, full_name, department, student_id, laptop_brand, serial_number]):
        st.error("All fields are required except the profile photo.")
        return
    try:
        existing = get_device_record_by_user_id(service_client, student_user_id)
        existing_path = existing.get("profile_image_path") if isinstance(existing, dict) else None
        photo_path = str(existing_path) if isinstance(existing_path, str) else None
        if profile_photo:
            photo_path = upload_photo(service_client, student_user_id, profile_photo)
        upsert_device_record(
            service_client,
            {
                "user_id": student_user_id,
                "full_name": full_name,
                "department": department,
                "student_id": student_id,
                "laptop_brand": laptop_brand,
                "serial_number": serial_number,
                "profile_image_path": photo_path,
            },
        )
        st.success("Student device registration saved.")
    except Exception as exc:
        st.error(f"Failed to save registration: {exc}")


def get_request_ip() -> str:
    headers = getattr(st.context, "headers", {}) or {}
    if not isinstance(headers, dict):
        return "unknown"
    forwarded_for = headers.get("x-forwarded-for")
    if isinstance(forwarded_for, str) and forwarded_for.strip():
        return forwarded_for.split(",")[0].strip()
    real_ip = headers.get("x-real-ip")
    if isinstance(real_ip, str) and real_ip.strip():
        return real_ip.strip()
    return "unknown"


def log_exit_once_per_session(device: dict) -> None:
    user_id = str(st.session_state.get("user_id") or "")
    pass_expires_at = str(device.get("pass_expires_at") or "")
    session_log_key = f"{user_id}:{pass_expires_at}"
    if st.session_state.get("last_logged_exit_key") == session_log_key:
        return

    service_client = get_service_client()
    payload = {
        "student_id": user_id,
        "student_name": str(device.get("full_name") or "Unknown Student"),
        "laptop_serial": str(device.get("serial_number") or "NO SERIAL"),
        "ip_address": get_request_ip(),
    }
    try:
        service_client.table("exit_logs").insert(payload).execute()
        st.session_state["last_logged_exit_key"] = session_log_key
    except Exception:
        # Silent failure by design; logging should not block gate flow.
        pass


def to_csv_bytes(rows: list[Any]) -> bytes:
    output = io.StringIO()
    fieldnames = ["student_name", "laptop_serial", "ip_address", "timestamp"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "student_name": row.get("student_name", ""),
                "laptop_serial": row.get("laptop_serial", ""),
                "ip_address": row.get("ip_address", ""),
                "timestamp": row.get("timestamp", ""),
            }
        )
    return output.getvalue().encode("utf-8")


def render_admin_forensics() -> None:
    st.subheader("Admin Forensics Dashboard")
    service_client = get_service_client()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date.today())
        start_time = st.time_input("Start Time", value=time(hour=0, minute=0))
    with col2:
        end_date = st.date_input("End Date", value=date.today())
        end_time = st.time_input("End Time", value=time(hour=23, minute=59))

    serial_query = st.text_input("Search by Serial Number", placeholder="e.g. BCAJW2451V")

    start_dt = datetime.combine(start_date, start_time).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, end_time).replace(tzinfo=timezone.utc)
    if end_dt < start_dt:
        st.error("End time must be after start time.")
        return

    query = (
        service_client.table("exit_logs")
        .select("student_name,laptop_serial,ip_address,timestamp")
        .gte("timestamp", start_dt.isoformat())
        .lte("timestamp", end_dt.isoformat())
        .order("timestamp", desc=True)
        .limit(50)
    )

    serial_value = serial_query.strip()
    if serial_value:
        query = query.ilike("laptop_serial", f"%{serial_value}%")

    rows = query.execute().data or []
    rows_data = rows if isinstance(rows, list) else []

    st.markdown("**Live Feed (latest 50 exits)**")
    st.dataframe(rows_data, use_container_width=True)

    csv_bytes = to_csv_bytes(rows_data)
    now_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        "Export Filtered Logs (CSV)",
        data=csv_bytes,
        file_name=f"exit_logs_{now_label}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_student_pass() -> None:
    st.subheader("Active Exit Pass")
    st_autorefresh(interval=1000, key="student_live_clock")
    client = authenticated_client(get_anon_client())
    user_id = str(st.session_state.get("user_id") or "")

    # Live database read for stolen status at the very beginning
    try:
        status = (
            client.table("student_devices")
            .select("is_stolen")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        st.error(f"Failed to read device status: {exc}")
        return

    status_data = status.data if isinstance(status.data, dict) else {}
    is_stolen_live = bool(status_data.get("is_stolen", False))

    if is_stolen_live:
        st.markdown(
            """
            <style>
                .stApp, [data-testid="stAppViewContainer"] {
                    animation: stolenFlashBg 1s infinite !important;
                }
                @keyframes stolenFlashBg {
                    0% { background: #ff0000; }
                    50% { background: #5b0000; }
                    100% { background: #ff0000; }
                }
                .stolen-banner {
                    margin-top: 1rem;
                    padding: 1.2rem;
                    border: 4px solid #ffffff;
                    border-radius: 14px;
                    text-align: center;
                    background: rgba(0, 0, 0, 0.45);
                }
                .stolen-text {
                    color: #ffffff;
                    font-size: 2rem;
                    font-weight: 900;
                    line-height: 1.3;
                }
            </style>
            <div class="stolen-banner">
                <div class="stolen-text">🛑 STOLEN DEVICE DETECTED - ALERT SECURITY</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("I found my device", key="restore_device_button", use_container_width=True):
            try:
                client.table("student_devices").update({"is_stolen": False}).eq("user_id", user_id).execute()
                st.success("Device status restored to safe.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to restore device: {exc}")
        return

    # Not stolen, proceed with normal pass logic
    device = get_device_record_by_user_id(client, user_id)
    if not device:
        st.warning("Your device is not registered yet. Contact admin.")
        return

    if st.button("Flag As Stolen", key="flag_as_stolen_button", type="primary"):
        try:
            client.table("student_devices").update({"is_stolen": True}).eq("user_id", user_id).execute()
            st.success("Device flagged as stolen.")
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to flag stolen: {exc}")

    if not is_pass_valid(device):
        try:
            issue_pass(client, user_id)
            device = get_device_record_by_user_id(client, user_id)
        except Exception as exc:
            st.error(f"Failed to activate pass: {exc}")
            return

    if not device:
        st.error("Could not load your pass. Try refreshing.")
        return

    log_exit_once_per_session(device)

    photo_url = get_public_photo_url(client, str(device.get("profile_image_path") or ""))
    st.markdown('<div class="pass-card">', unsafe_allow_html=True)
    if photo_url:
        st.image(photo_url, caption="Student Photo", use_container_width=True)

    student_name = str(device.get("full_name") or "Unknown Student")
    department = str(device.get("department") or "Unknown Department")
    serial_number = str(device.get("serial_number") or "NO SERIAL")
    pass_expires_at = str(device.get("pass_expires_at") or "")

    st.markdown(f'<div class="name-xl">{student_name}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="name-xl">{department}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="serial-xl">{serial_number}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="clock">LIVE TIME: {datetime.now().strftime("%H:%M:%S")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="expiry">PASS EXPIRES: {pass_expires_at}</div>', unsafe_allow_html=True)
    st.caption("Security Notice: This exit is being digitally logged for campus safety.")
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    set_page("GateKeeper")
    inject_css()
    init_state()
    restore_auth_from_cookies()

    if not st.session_state.get("user_id"):
        render_auth()
        return

    client = authenticated_client(get_anon_client())
    st.sidebar.write(f"Logged in as: {st.session_state.get('email')}")
    if st.sidebar.button("Logout", key="sidebar_logout_button"):
        sign_out(client)

    if is_admin():
        st.markdown('<div class="title-xl">Admin Control Panel</div>', unsafe_allow_html=True)
        admin_tab1, admin_tab2 = st.tabs(["Student Registration", "Exit Forensics"])
        with admin_tab1:
            render_admin_registration()
        with admin_tab2:
            render_admin_forensics()
    else:
        st.markdown('<div class="title-xl">Gate Exit Verification</div>', unsafe_allow_html=True)
        st.caption("Gate QR should point to this app URL. Landing here shows your live pass.")
        render_student_pass()

    st.caption(f"Local Time: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
