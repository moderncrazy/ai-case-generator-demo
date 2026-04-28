from fastapi import HTTPException

from src.models.business.project import Project
from src.enums.error_message import ErrorMessage
from src.exceptions.exceptions import BusinessException
from src.repositories.project_repository import project_repository


async def get_project_or_404(project_id: str) -> Project:
    """检查项目是否存在，不存在则抛出 404"""
    project = await project_repository.get_by_id(project_id)
    if not project:
        raise BusinessException.from_error_message(ErrorMessage.PROJECT_NOT_FOUND_ERROR)
    return project
