from typing import Annotated, Optional
from fastapi import APIRouter, Query, Depends

from src.models.business.project import Project
from src.services.api_service import api_service
from src.dependencies.dependencies import get_project_or_404
from src.schemas.response import ApiResponse, ApiListResponse, ListData
from src.schemas.api import ApiResponse as ApiResponseSchema, ApiTreeNode, ApiTreeDocumentResponse

# 接口路由
router = APIRouter(prefix="/api/v1/project", tags=["接口"])


@router.get("/{project_id}/apis", response_model=ApiListResponse[ApiResponseSchema])
async def list_apis(
        project: Annotated[Project, Depends(get_project_or_404)],
        page: int = 1,
        page_size: int = 20,
        module_id: Annotated[Optional[str], Query] = None,
):
    """查询接口列表
    
    分页查询项目的接口列表，支持按模块筛选。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        page: 页码（从 1 开始）
        page_size: 每页数量
        module_id: 按模块筛选（可选）
        
    Returns:
        返回接口列表和总数
    """
    apis, total = await api_service.list_apis(
        project_id=project.id,
        page=page,
        page_size=page_size,
        module_id=module_id,
    )
    list_data = ListData(items=apis, total=total, page=page, page_size=page_size)
    return ApiListResponse(data=list_data)


@router.get("/{project_id}/apis/tree", response_model=ApiResponse[list[ApiTreeNode]])
async def get_apis_tree(project: Annotated[Project, Depends(get_project_or_404)]):
    """获取接口树形结构
    
    获取项目的接口树形结构，按模块父子级组织。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        
    Returns:
        返回接口树形结构列表
    """
    tree = await api_service.get_apis_tree(project.id)
    return ApiResponse(data=tree)


@router.get("/{project_id}/apis/compare", response_model=ApiResponse[ApiTreeDocumentResponse])
async def get_apis_compare(project: Annotated[Project, Depends(get_project_or_404)]):
    """获取 API 对比文档
    
    从 graph state 获取原始版本和优化版本的 API 树形结构。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        
    Returns:
        返回 API 对比文档（原始版和优化版）
    """
    result = await api_service.get_apis_compare(project.id)
    return ApiResponse(data=result)
