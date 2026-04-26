import streamlit as st

from app_core import inject_css, set_page


def main() -> None:
    set_page("GateKeeper")
    inject_css()
    st.markdown('<div class="title-xl">Use Main App URL</div>', unsafe_allow_html=True)
    st.info(
        "This page is deprecated. The gate QR should point to the main app URL so the student's "
        "landing page shows their live pass after login."
    )


if __name__ == "__main__":
    main()
