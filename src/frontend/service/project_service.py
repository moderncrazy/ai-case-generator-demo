import uuid
from datetime import datetime

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from src.frontend.utils import utils
from src.frontend.constant import TRANSACTION_ID
from src.frontend.schemas.response import ListResponse
from src.frontend.schemas.project import Project, ProjectDetailResponse
from src.frontend.schemas.conversation_message import (
    ConversationMessage,
    HistoryConversationMessage,
    ConversationMessageResponse,
)

SERVER_HOST = st.secrets["server"]["host"]


class ProjectService:

    @staticmethod
    async def create_project(name: str, description: str = "") -> str | None:
        """创建项目"""
        try:
            async with utils.get_async_http_client() as client:
                response = await client.post(
                    f"{SERVER_HOST}/api/v1/project",
                    headers={TRANSACTION_ID: str(uuid.uuid4())},
                    json={"name": name, "description": description}
                )
                return response.json().get("data")["id"]
        except Exception as e:
            st.error(f"创建项目失败: {e}")
            return None

    @staticmethod
    async def get_projects(page: int = 1, page_size: int = 20) -> ListResponse[Project] | None:
        """获取项目列表"""
        try:
            async with utils.get_async_http_client() as client:
                response = await client.get(
                    f"{SERVER_HOST}/api/v1/project",
                    headers={TRANSACTION_ID: str(uuid.uuid4())},
                    params={"page": page, "page_size": page_size}
                )
                return ListResponse[Project].model_validate(response.json().get("data"))
        except Exception as e:
            st.error(f"获取项目列表失败: {e}")
            return None

    @staticmethod
    async def get_project_detail(project_id: str) -> ProjectDetailResponse | None:
        """获取项目详情"""
        try:
            async with utils.get_async_http_client() as client:
                response = await client.get(
                    f"{SERVER_HOST}/api/v1/project/{project_id}",
                    headers={TRANSACTION_ID: str(uuid.uuid4())}
                )
                return ProjectDetailResponse.model_validate(response.json().get("data"))
        except Exception as e:
            st.error(f"获取项目详情失败: {e}")
            return None

    @staticmethod
    async def get_conversation_messages(project_id: str, page: int = 1, page_size: int = 100) -> (
            ListResponse[HistoryConversationMessage] | None):
        """获取对话历史"""
        try:
            async with utils.get_async_http_client() as client:
                response = await client.get(
                    f"{SERVER_HOST}/api/v1/project/{project_id}/messages",
                    headers={TRANSACTION_ID: str(uuid.uuid4())},
                    params={"page": page, "page_size": page_size}
                )
                return ListResponse[HistoryConversationMessage].model_validate(response.json().get("data"))
        except Exception as e:
            st.error(f"获取对话历史失败: {e}")
            return None

    @staticmethod
    def project_discuss(project_id: str, user_id: str, message: str, files: list[UploadedFile]):
        """发送消息给项目"""
        with utils.get_http_client() as client:
            with client.stream(
                    "POST",
                    f"{SERVER_HOST}/api/v1/project/{project_id}/discuss",
                    data={"message": message, "user_id": user_id},
                    files=[("files", (file.name, file.getvalue(), file.type)) for file in files],
                    headers={TRANSACTION_ID: str(uuid.uuid4()), "Accept": "text/event-stream"}
            ) as response:
                for line in response.iter_lines():
                    print(f"{datetime.now()} {line}")
                    if line.startswith("error:"):
                        raise Exception(f"网络异常")
                    elif line.startswith("data:"):
                        content = line[6:]
                        message_response = ConversationMessageResponse.model_validate_json(content)
                        yield message_response
