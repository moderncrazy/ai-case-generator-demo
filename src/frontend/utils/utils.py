import uuid
import httpx
import asyncio
import streamlit as st
from streamlit_local_storage import LocalStorage

from src.frontend import constant as const


def init_page():
    st.set_page_config(
        page_title="AI Case Generator Demo",
        page_icon=const.BASE_DIR / "static/favicon.png",
        layout="wide",
    )
    # 确保每个 Streamlit 页面运行都在独立的 Event Loop 中
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    get_user_id()


def get_user_id() -> str:
    """生成一个uuid作为user_id"""
    # 如果存在则使用 不存在则新建
    ls = get_local_storage()
    user_id = ls.getItem(const.USER_ID_KEY)
    if not user_id:
        user_id = str(uuid.uuid4())
        ls.setItem(const.USER_ID_KEY, user_id)
    return user_id


def get_local_storage() -> LocalStorage:
    return LocalStorage()


@st.cache_resource
def _get_async_http_client():
    return httpx.AsyncClient(timeout=st.secrets["server"]["http_timeout"])


def get_async_http_client():
    client = _get_async_http_client()
    if client.is_closed:
        st.cache_resource.clear()
        client = _get_async_http_client()
    return client


@st.cache_resource
def _get_http_client():
    return httpx.Client(timeout=st.secrets["server"]["http_timeout"])


def get_http_client():
    client = _get_http_client()
    if client.is_closed:
        st.cache_resource.clear()
        client = _get_http_client()
    return client
