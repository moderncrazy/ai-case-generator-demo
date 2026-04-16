import httpx
import asyncio
import streamlit as st

from src.frontend.constant import BASE_DIR


def init_page():
    st.set_page_config(
        page_title="AI Case Generator Demo",
        page_icon=BASE_DIR / "static/favicon.png",
        layout="wide",
    )
    # 确保每个 Streamlit 页面运行都在独立的 Event Loop 中
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


@st.cache_resource
def _get_http_client():
    return httpx.AsyncClient(timeout=st.secrets["server"]["http_timeout"])


def get_http_client():
    client = _get_http_client()
    if client.is_closed:
        st.cache_resource.clear()
        client = _get_http_client()
    return client
