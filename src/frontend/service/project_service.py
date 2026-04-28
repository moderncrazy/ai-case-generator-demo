import uuid
import traceback
import streamlit as st
from datetime import datetime
from streamlit.runtime.uploaded_file_manager import UploadedFile

from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.schemas.response import ListResponse, ErrorResponse
from src.frontend.schemas.project import ProjectListItem, ProjectBasicInfoResponse
from src.frontend.schemas.conversation_message import (
    ConversationMessage,
    HistoryConversationMessage,
    ConversationMessageResponse,
)

SERVER_HOST = st.secrets["server"]["host"]

logger = utils.get_logger()


class ProjectService:

    @staticmethod
    def create_project(name: str, description: str = "") -> str | None:
        """创建项目"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.post(
                f"{SERVER_HOST}/api/v1/project",
                headers={const.TRANSACTION_ID: trans_id},
                json={"name": name, "description": description}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return resp["data"]["id"]
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目名:{name} 描述:{description} 创建项目失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_projects(page: int = 1, page_size: int = 20) -> ListResponse[ProjectListItem] | None:
        """获取项目列表"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project",
                headers={const.TRANSACTION_ID: trans_id},
                params={"page": page, "page_size": page_size}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ListResponse[ProjectListItem].model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 页码:{page} 每页:{page_size} 获取项目列表失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_project_detail(project_id: str) -> ProjectBasicInfoResponse | None:
        """获取项目详情"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ProjectBasicInfoResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取项目详情失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_conversation_messages(project_id: str, page: int = 1, page_size: int = 200) -> (
            ListResponse[HistoryConversationMessage] | None):
        """获取对话历史"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/messages",
                headers={const.TRANSACTION_ID: trans_id},
                params={"page": page, "page_size": page_size}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ListResponse[HistoryConversationMessage].model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 页码:{page} 每页:{page_size} 获取对话历史失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def delete_project(project_id: str, user_id: str) -> bool:
        """删除项目"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.delete(
                f"{SERVER_HOST}/api/v1/project/{project_id}",
                headers={const.TRANSACTION_ID: trans_id},
                json={user_id: user_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return True
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return False
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 删除项目失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return False

    @staticmethod
    def project_discuss(project_id: str, user_id: str, message: str, files: list[UploadedFile]):
        """项目对话"""
        trans_id = str(uuid.uuid4())
        client = utils.get_http_client()
        with client.stream(
                "POST",
                f"{SERVER_HOST}/api/v1/project/{project_id}/discuss",
                data={"message": message, "user_id": user_id},
                files=[("files", (file.name, file.getvalue(), file.type)) for file in files],
                headers={const.TRANSACTION_ID: trans_id, "Accept": "text/event-stream"}
        ) as response:
            for line in response.iter_lines():
                print(f"{datetime.now()} {line}")
                if line and not line.startswith("heartbeat:"):
                    if line.startswith("error:"):
                        logger.error(
                            f"trans_id:{trans_id} 项目Id:{project_id} 用户Id:{user_id} 消息:{message} 项目对话失败:接收到[error:]")
                        raise Exception(f"网络异常")
                    elif line.startswith("data:"):
                        content = line[6:]
                        message_response = ConversationMessageResponse.model_validate_json(content)
                        yield message_response
                    else:
                        try:
                            # 尝试用 error response 解析
                            error_resp = ErrorResponse.model_validate_json(line)
                            st.toast(error_resp.message, icon="⚠️", duration="long")
                            raise Exception(error_resp.message)
                        except Exception as e:
                            logger.error(
                                f"trans_id:{trans_id} 项目Id:{project_id} 用户Id:{user_id} 消息:{message} 项目对话失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
                            raise e
