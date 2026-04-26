from datetime import datetime

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
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
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
        student_user_id = st.text_input("Student Auth User ID (UUID)")
        full_name = st.text_input("Full Name")
        department = st.text_input("Department")
        student_id = st.text_input("Student ID")
        laptop_brand = st.text_input("Laptop Brand")
        serial_number = st.text_input("Serial Number")
        profile_photo = st.file_uploader("Profile Picture", type=["png", "jpg", "jpeg", "webp"])
        save = st.form_submit_button("Save Registration")

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


def render_student_pass() -> None:
    st.subheader("Active Exit Pass")
    st_autorefresh(interval=1000, key="student_live_clock")
    client = authenticated_client(get_anon_client())
    user_id = str(st.session_state.get("user_id") or "")
    device = get_device_record_by_user_id(client, user_id)
    if not device:
        st.warning("Your device is not registered yet. Contact admin.")
        return

    stolen_now = bool(device.get("is_stolen", False))
    if st.button("Mark Device Safe" if stolen_now else "Flag As Stolen", type="primary"):
        try:
            client.table("student_devices").update({"is_stolen": not stolen_now}).eq(
                "user_id", user_id
            ).execute()
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to toggle stolen status: {exc}")

    device = get_device_record_by_user_id(client, user_id)
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

    if bool(device.get("is_stolen", False)):
        st.markdown(
            """
            <div class="flash-red">
                <div class="flash-red-text">STOLEN DEVICE - ALERT SECURITY</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

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
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    set_page("GateKeeper")
    inject_css()
    init_state()

    if not st.session_state.get("user_id"):
        render_auth()
        return

    client = authenticated_client(get_anon_client())
    st.sidebar.write(f"Logged in as: {st.session_state.get('email')}")
    if st.sidebar.button("Logout"):
        sign_out(client)

    if is_admin():
        st.markdown('<div class="title-xl">Admin Control Panel</div>', unsafe_allow_html=True)
        render_admin_registration()
    else:
        st.markdown('<div class="title-xl">Gate Exit Verification</div>', unsafe_allow_html=True)
        st.caption("Gate QR should point to this app URL. Landing here shows your live pass.")
        render_student_pass()

    st.caption(f"Local Time: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
