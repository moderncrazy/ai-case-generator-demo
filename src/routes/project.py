from typing import Annotated, Optional
from fastapi import APIRouter, Query, Body, Depends

from src.models.business.project import Project
from src.enums.project_progress import ProjectProgress
from src.dependencies.dependencies import get_project_or_404
from src.schemas.response import ApiResponse, ApiListResponse, ListData
from src.schemas.project import ProjectCreate, ProjectListItem, ProjectBasicInfoResponse
from src.services.project_service import project_service

# 项目路由
router = APIRouter(prefix="/api/v1/project", tags=["项目"])


@router.post("", response_model=ApiResponse[dict])
async def create_project(data: ProjectCreate):
    """创建项目
    
    创建新项目，初始化项目的基本信息。
    
    Args:
        data: 项目创建参数（包含名称、描述等）
        
    Returns:
        返回新建项目的 ID
    """
    result = await project_service.create_project(data)
    return ApiResponse(data=result)


@router.get("", response_model=ApiListResponse[ProjectListItem])
async def list_projects(
        page: int = 1,
        page_size: int = 20,
        progress: Annotated[Optional[ProjectProgress], Query] = None,
):
    """查询项目列表
    
    分页查询项目列表，支持按进度状态筛选。
    
    Args:
        page: 页码（从 1 开始）
        page_size: 每页数量
        progress: 按进度状态筛选（可选）
        
    Returns:
        返回项目列表和总数
    """
    projects, total = await project_service.list_projects(page, page_size, progress)
    list_data = ListData(items=projects, total=total, page=page, page_size=page_size)
    return ApiListResponse(data=list_data)


@router.get("/{project_id}", response_model=ApiResponse[ProjectBasicInfoResponse])
async def get_project_basic_info(project: Annotated[Project, Depends(get_project_or_404)]):
    """获取项目基本信息
    
    根据项目 ID 获取项目的基本信息及各文档是否存在。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        
    Returns:
        返回项目基本信息
    """
    result = await project_service.get_project_basic_info(project)
    return ApiResponse(data=result)


@router.delete("/{project_id}", response_model=ApiResponse[None])
async def delete_project(user_id: Annotated[str, Body(embed=True)],
                         project: Annotated[Project, Depends(get_project_or_404)]):
    """删除项目
    
    删除项目及其所有关联数据
    
    Args:
        user_id: 用户UUID
        project: 项目对象（通过依赖注入获取）

    Raises:
        BusinessException: 系统创建的项目不允许删除或项目被占用
    """
    await project_service.delete_project(project, user_id)
    return ApiResponse(data=None)
