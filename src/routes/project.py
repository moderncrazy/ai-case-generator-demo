from typing import Annotated, Optional
from fastapi import APIRouter, Form, UploadFile, HTTPException, Query, Depends

from src.models.project import Project
from src.enums.project_progress import ProjectProgress
from src.exceptions.exceptions import BusinessException
from src.dependencies.dependencies import get_project_or_404
from src.schemas.response import ApiResponse, ApiListResponse, ListData
from src.schemas.project import ProjectCreate
from src.services.project_service import project_service
from src.services.milvus_service import milvus_service

router = APIRouter(prefix="/api/v1/project", tags=["项目"])


@router.post("", response_model=ApiResponse[dict])
async def create_project(data: ProjectCreate):
    """创建项目"""
    result = await project_service.create_project(data)
    return ApiResponse(data=result)


@router.get("", response_model=ApiListResponse[dict])
async def list_projects(
        page: int = 1,
        page_size: int = 20,
        progress: Annotated[Optional[ProjectProgress], Query] = None,
):
    """查询项目列表"""
    projects, total = await project_service.list_projects(page, page_size, progress)
    list_data = ListData(items=projects, total=total, page=page, page_size=page_size)
    return ApiListResponse(data=list_data)


@router.post("/{project_id}/query", response_model=ApiResponse[dict])
async def query_project(project: Annotated[Project, Depends(get_project_or_404)]):
    """复制项目"""
    await milvus_service.search_project_files("部署", project.id)
    return ApiResponse(data={})


@router.post("/{project_id}/discuss", response_model=ApiResponse[dict])
async def discuss_project(
        project: Annotated[Project, Depends(get_project_or_404)],
        message: Annotated[str, Form()],
        files: list[UploadFile] = None,
):
    """项目对话"""
    return await project_service.discuss_project(project, message, files)
