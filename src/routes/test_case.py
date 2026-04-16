from typing import Annotated, Optional
from fastapi import APIRouter, Query, Depends

from src.models.project import Project
from src.dependencies.dependencies import get_project_or_404
from src.schemas.response import ApiResponse, ApiListResponse, ListData
from src.schemas.test_case import TestCaseResponse, TestCaseTreeNode
from src.services.test_case_service import test_case_service
from src.enums.test_case_level import TestCaseLevel
from src.enums.test_case_type import TestCaseType

# 测试用例路由
router = APIRouter(prefix="/api/v1/project", tags=["测试用例"])


@router.get("/{project_id}/test-cases", response_model=ApiListResponse[TestCaseResponse])
async def list_test_cases(
        project: Annotated[Project, Depends(get_project_or_404)],
        page: int = 1,
        page_size: int = 20,
        module_id: Annotated[Optional[str], Query] = None,
        level: Annotated[Optional[TestCaseLevel], Query] = None,
        type: Annotated[Optional[TestCaseType], Query] = None,
):
    """查询测试用例列表
    
    分页查询项目的测试用例列表，支持按模块、等级、类型筛选。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        page: 页码（从 1 开始）
        page_size: 每页数量
        module_id: 按模块筛选（可选）
        level: 按用例等级筛选（可选，如 P0/P1/P2）
        type: 按用例类型筛选（可选，如功能测试/接口测试）
        
    Returns:
        返回测试用例列表和总数
    """
    test_cases, total = await test_case_service.list_test_cases(
        project_id=project.id,
        page=page,
        page_size=page_size,
        module_id=module_id,
        level=level,
        type=type,
    )
    list_data = ListData(items=test_cases, total=total, page=page, page_size=page_size)
    return ApiListResponse(data=list_data)


@router.get("/{project_id}/test-cases/tree", response_model=ApiResponse[list[TestCaseTreeNode]])
async def get_test_cases_tree(project: Annotated[Project, Depends(get_project_or_404)]):
    """获取测试用例树形结构
    
    获取项目的测试用例树形结构，按模块父子级组织。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        
    Returns:
        返回测试用例树形结构列表
    """
    tree = await test_case_service.get_test_cases_tree(project.id)
    return ApiResponse(data=tree)
