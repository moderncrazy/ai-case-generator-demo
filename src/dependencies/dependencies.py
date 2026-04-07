from fastapi import HTTPException

from src.models import Project
from src.repositories import project_repository


async def get_project_or_404(project_id: str) -> Project:
    """检查项目是否存在，不存在则抛出 404"""
    project = await project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project
