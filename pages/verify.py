from datetime import datetime

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app_core import (
    get_device_record_for_verify,
    get_public_photo_url,
    get_service_client,
    inject_css,
    is_pass_valid,
    set_page,
    verify_token,
)


def render_stolen_alert() -> None:
    st.markdown(
        """
        <div class="flash-red">
            <div class="flash-red-text">STOLEN DEVICE - ALERT SECURITY</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_verify_card(device: dict) -> None:
    photo_url = get_public_photo_url(get_service_client(), str(device.get("profile_image_path") or ""))
    if photo_url:
        st.image(photo_url, caption="Student Photo", use_container_width=True)
    st.markdown(f'<div class="name-xl">{device.get("full_name", "Unknown Student")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="serial-xl">{device.get("serial_number", "NO SERIAL")}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="clock">LIVE TIME: {datetime.now().strftime("%H:%M:%S")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="expiry">Pass Expires: {device.get("pass_expires_at", "")}</div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    set_page("GateKeeper Verify")
    inject_css()
    st_autorefresh(interval=1000, key="verify_clock")
    st.markdown('<div class="title-xl">Guard Verify View</div>', unsafe_allow_html=True)

    token = str(st.query_params.get("token", "") or "")
    if not token:
        st.error("Missing verification token.")
        return

    payload = verify_token(token)
    if not payload:
        st.error("Invalid or expired verification token.")
        return

    user_id = payload["uid"]
    serial_number = payload["sn"]

    service_client = get_service_client()
    device = get_device_record_for_verify(service_client, user_id, serial_number)
    if not device:
        st.error("No matching registered device found.")
        return

    if bool(device.get("is_stolen", False)):
        render_stolen_alert()
        return

    if not is_pass_valid(device):
        st.error("Pass has expired. Student must generate a fresh pass.")
        return

    render_verify_card(device)


if __name__ == "__main__":
    main()
