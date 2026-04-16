from typing import Annotated, Optional
from fastapi import APIRouter, Query, Depends

from src.models.project import Project
from src.dependencies.dependencies import get_project_or_404
from src.schemas.response import ApiResponse, ApiListResponse, ListData
from src.schemas.module import ModuleResponse, ModuleTreeNode
from src.services.module_service import module_service

# 模块路由
router = APIRouter(prefix="/api/v1/project", tags=["模块"])


@router.get("/{project_id}/modules", response_model=ApiListResponse[ModuleResponse])
async def list_modules(
        project: Annotated[Project, Depends(get_project_or_404)],
        page: int = 1,
        page_size: int = 20,
        parent_id: Annotated[Optional[str], Query] = None,
):
    """查询模块列表
    
    分页查询项目的模块列表，支持按父模块筛选。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        page: 页码（从 1 开始）
        page_size: 每页数量
        parent_id: 按父模块筛选（可选，为空则查所有）
        
    Returns:
        返回模块列表和总数
    """
    modules, total = await module_service.list_modules(
        project_id=project.id,
        page=page,
        page_size=page_size,
        parent_id=parent_id,
    )
    list_data = ListData(items=modules, total=total, page=page, page_size=page_size)
    return ApiListResponse(data=list_data)


@router.get("/{project_id}/modules/tree", response_model=ApiResponse[list[ModuleTreeNode]])
async def get_modules_tree(project: Annotated[Project, Depends(get_project_or_404)]):
    """获取模块树形结构
    
    获取项目的完整模块树形结构，体现父子模块层级关系。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        
    Returns:
        返回模块树形结构列表
    """
    tree = await module_service.get_modules_tree(project.id)
    return ApiResponse(data=tree)
