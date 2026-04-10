import json
import uuid
from typing import Optional
from datetime import datetime
from fastapi import UploadFile
from sqlite3 import IntegrityError
from langchain.messages import AIMessage
from fastapi.responses import StreamingResponse

from src.utils import file_utils
from src.config import settings
from src.models.project import Project
from src.agents.main_agent import main_agent
from src.graphs.schemas import StateNewProjectFile
from src.exceptions.exceptions import BusinessException
from src.schemas.project import ProjectCreate
from src.schemas.conversation_message import ConversationMessageResponse
from src.repositories.project_repository import project_repository
from src.repositories.project_file_repository import project_file_repository
from src.repositories.conversation_message_repository import conversation_message_repository
from src.enums.creator_type import CreatorType
from src.enums.error_message import ErrorMessage
from src.enums.project_progress import ProjectProgress
from src.enums.conversation_role import ConversationRole


class ProjectService:
    """项目服务"""

    @staticmethod
    async def create_project(data: ProjectCreate) -> dict[str, str]:
        """创建项目"""
        try:
            project_id = await project_repository.create(
                name=data.name,
                description=data.description,
                creator_type=CreatorType.USER
            )
            return {"id": project_id}
        except IntegrityError:
            raise BusinessException.from_error_message(ErrorMessage.PROJECT_NAME_EXIST_ERROR)

    @staticmethod
    async def list_projects(
            page: int = 1,
            page_size: int = 20,
            progress: Optional[ProjectProgress] = None,
    ) -> tuple[list[dict], int]:
        """查询项目列表"""
        projects, total = await project_repository.paginate(
            page=page,
            page_size=page_size,
            progress=progress,
        )
        return [item.to_dict() for item in projects], total

    @staticmethod
    async def discuss_project(
            project: Project,
            message: str,
            files: list[UploadFile] = None,
    ) -> StreamingResponse:
        """项目对话"""
        # 上传文件检查
        conversation_message_id = str(uuid.uuid4())
        graph_file_list: list[StateNewProjectFile] = []
        project_file_total_size = await project_file_repository.get_total_size(project.id)
        if files:
            for file in files:
                # 检查文件类型
                file_type = file_utils.get_file_type(file.filename)
                if file_type not in settings.project_file_types:
                    raise BusinessException.from_error_message(ErrorMessage.FILE_TYPE_ERROR)
                # 文件大小检查
                if file.size > settings.project_file_max_size:
                    raise BusinessException.from_error_message(ErrorMessage.FILE_SIZE_ERROR)
                # 检查项目文件总大小，未超过则累加
                if (file.size + project_file_total_size) > settings.project_file_total_max_size:
                    raise BusinessException.from_error_message(ErrorMessage.PROJECT_FILE_TOTAL_SIZE_ERROR)
                else:
                    project_file_total_size += file.size
                # 检查文件是否存在
                if await project_file_repository.get_by_project_and_name(project.id, file.filename):
                    raise BusinessException.from_error_message(ErrorMessage.PROJECT_FILE_EXIST_ERROR)
                # 存储文件
                file_path = file_utils.save_project_file(project.id, file.filename, await file.read())
                # 检查文件安全性
                scan_result = file_utils.scan_file_with_clamav(file_path)
                # 不安全则删除文件
                if not scan_result:
                    file_path.unlink(missing_ok=True)
                    raise BusinessException.from_error_message(ErrorMessage.FILE_EXCEPTION_ERROR)
                graph_file_list.append(StateNewProjectFile(
                    conversation_message_id=conversation_message_id,
                    name=file.filename,
                    path=str(file_path),
                    type=file_type,
                    size=file.size,
                    created_at=datetime.now()
                ))

        # 创建对话
        await conversation_message_repository.create(
            id=conversation_message_id,
            project_id=project.id,
            role=ConversationRole.USER,
            content=message)

        # 进行项目对话
        async def event_generator():
            async for chunk in await main_agent.astream(project.id, message, graph_file_list):
                # # 将 chunk 转为 SSE 格式
                match chunk["type"]:
                    case "custom":
                        msg = chunk["data"]["message"]
                        # 创建对话
                        msg_id = await conversation_message_repository.create(
                            project_id=project.id,
                            role=ConversationRole.SYSTEM,
                            content=msg)
                        response = ConversationMessageResponse(
                            id=msg_id,
                            project_id=project.id,
                            role=ConversationRole.SYSTEM,
                            content=msg)
                        # 响应用户
                        yield f"data: {response.model_dump_json()}\n\n"
                    case "updates":
                        # 检查节点返回是否包含对话
                        for node_name, state in chunk["data"].items():
                            # if state.get("messages") and isinstance(state["messages"][-1], AIMessage):
                            if state.get("messages"):
                                for msg in state["messages"]:
                                    if isinstance(msg, AIMessage):
                                        msg_content = msg.content
                                        # 返回思考内容 但不记录
                                        if isinstance(msg_content, list) and msg_content[0].get("thinking"):
                                            response = ConversationMessageResponse(
                                                id="",
                                                project_id=project.id,
                                                role=ConversationRole.SYSTEM,
                                                content=msg_content[0]["thinking"])
                                            # 响应用户
                                            yield f"data: {response.model_dump_json()}\n\n"
                                        # 如果是正式回话 则记录并返回
                                        if msg_content and not msg.tool_calls:
                                            # 创建对话
                                            msg_id = await conversation_message_repository.create(
                                                project_id=project.id,
                                                role=ConversationRole.ASSISTANT,
                                                content=msg_content)
                                            response = ConversationMessageResponse(
                                                id=msg_id,
                                                project_id=project.id,
                                                role=ConversationRole.ASSISTANT,
                                                content=msg_content)
                                            # 响应用户
                                            yield f"data: {response.model_dump_json()}\n\n"
                    case _:
                        print(chunk)
                        yield f"data: \n\n"
                pass

        return StreamingResponse(event_generator(), media_type="text/event-stream")


# 导出单例
project_service = ProjectService()
