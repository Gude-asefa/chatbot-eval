"""Entry point.

Testers:  https://<your-app>.streamlit.app/
Admin:    https://<your-app>.streamlit.app/admin   (not linked anywhere; login required)
"""
import streamlit as st

st.set_page_config(
    page_title="Chatbot Evaluation · Bank of Abyssinia",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui import inject_css  # noqa: E402


def tester_page() -> None:
    import user_pages

    inject_css()
    user_pages.render()


def admin_page() -> None:
    import admin_page as admin

    inject_css(admin=True)
    admin.render()


pages = [
    st.Page(tester_page, title="Chatbot Evaluation · Bank of Abyssinia", icon="💬", default=True),
    st.Page(admin_page, title="Admin · Chatbot Evaluation", icon="🔒", url_path="admin"),
]
st.navigation(pages, position="hidden").run()
