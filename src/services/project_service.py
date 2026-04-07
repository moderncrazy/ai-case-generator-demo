import json
from typing import Optional
from fastapi import UploadFile
from fastapi.responses import StreamingResponse

from src.models import Project
from src.config import settings
from src.utils import file_utils
from src.agents import main_agent
from src.schemas import ProjectCreate
from src.exceptions import BusinessException
from src.repositories import (
    ProjectFileCreate,
    project_repository,
    project_file_repository,
    conversation_message_repository,
)
from src.enums import CreatorType, ProjectProgress, ConversationRole, ErrorMessage


class ProjectService:
    """项目服务"""

    @staticmethod
    async def create_project(data: ProjectCreate) -> dict[str, str]:
        """创建项目"""
        project_id = await project_repository.create(
            name=data.name,
            description=data.description,
            creator_type=CreatorType.USER
        )
        return {"id": project_id}

    @staticmethod
    async def list_projects(
            page: int = 1,
            page_size: int = 20,
            progress: Optional[ProjectProgress] = None,
    ) -> tuple[list[Project], int]:
        """查询项目列表"""
        return await project_repository.paginate(
            page=page,
            page_size=page_size,
            progress=progress,
        )

    @staticmethod
    async def discuss_project(
            project: Project,
            message: str,
            files: list[UploadFile] = None,
    ) -> StreamingResponse:
        """项目对话"""
        # 上传文件检查
        file_name_list: list[str] = []
        project_file_create_list: list[ProjectFileCreate] = []
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
                # 记录文件
                file_name_list.append(file.filename)
                project_file_create_list.append(ProjectFileCreate(
                    project_id=project.id,
                    conversation_message_id="",
                    name=file.filename,
                    path=str(file_path),
                    type=file_type,
                    size=file.size
                ))

        # 创建对话
        conversation_message_id = await conversation_message_repository.create(project_id=project.id,
                                                                               role=ConversationRole.USER,
                                                                               content=message)
        # 创建项目文件
        if project_file_create_list:
            for item in project_file_create_list:
                item.conversation_message_id = conversation_message_id
            await project_file_repository.bulk_create(project_file_create_list)

        # 进行项目对话
        async def event_generator():
            async for chunk in await main_agent.astream(project.id, message, file_name_list):
                # 将 chunk 转为 SSE 格式
                print(chunk)
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")


# 导出单例
project_service = ProjectService()
