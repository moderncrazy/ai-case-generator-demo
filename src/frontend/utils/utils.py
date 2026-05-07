import sys
import uuid
import httpx
import streamlit as st
from pathlib import Path
from loguru import logger
from httpx import Response
from zoneinfo import ZoneInfo
from datetime import datetime
from loguru._logger import Logger
from streamlit_local_storage import LocalStorage

from src.frontend import constant as const


def init_page():
    st.set_page_config(
        page_title="AI Case Generator Demo",
        page_icon=const.BASE_DIR / "static/favicon.png",
        layout="wide",
    )
    # 根据配置隐藏 toolbar
    toolbar_mode = st.get_option("client.toolbarMode")
    if toolbar_mode == "minimal":
        st.html(f"""<style>header[data-testid="stHeader"] {{height: 2rem; width: 2rem;}}</style>""")
        st.html(f"""<style>div[data-testid="stMainBlockContainer"] {{padding-top: 1rem;}}</style>""")
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


def to_shanghai_dt(dt: datetime) -> datetime:
    return dt.astimezone(ZoneInfo("Asia/Shanghai"))


def _http_client_log(response: Response):
    logger = get_logger()
    url = response.url
    method = response.request.method
    req_data = response.request.content.decode("utf-8") or None
    trans_id = response.request.headers.get(const.TRANSACTION_ID)
    # 若是流式请求 则不打印响应
    if response.headers.get("Transfer-Encoding"):
        resp_data = "[stream]"
    else:
        resp_data = response.read().decode("utf-8") or None
    if response.status_code == 200:
        logger.info(f"{method} {url} trans_id:{trans_id} req_data:{req_data} resp_code:200 resp_data:{resp_data}")
    else:
        logger.error(
            f"{method} {url} trans_id:{trans_id} req_data:{req_data} resp_code:{response.status_code} resp_data:{resp_data}")


@st.cache_resource
def _get_http_client():
    return httpx.Client(
        timeout=st.secrets["server"]["http_timeout"],
        headers={const.REMOTE_ADDR: st.context.headers.get(const.REMOTE_ADDR, st.context.ip_address or "127.0.0.1")},
        event_hooks={"response": [_http_client_log]}
    )


def get_http_client():
    client = _get_http_client()
    if client.is_closed:
        st.cache_resource.clear()
        client = _get_http_client()
    return client


@st.cache_resource
def get_logger() -> Logger:
    """初始化日志配置"""
    logger.remove()
    log_path = Path(st.secrets["server"]["log_path"])
    log_path.mkdir(exist_ok=True)

    # 打印配置
    logger.add(sink=sys.stdout, level=st.secrets["server"]["log_level"])
    logger.add(
        sink=log_path / "web.log",
        level=st.secrets["server"]["log_level"],
        rotation=f"{st.secrets["server"]["log_rotation_size"]} MB",
        retention=f"{st.secrets["server"]["log_retention_days"]} days",
        compression="zip",
        enqueue=True,
        serialize=True
    )
    return logger
