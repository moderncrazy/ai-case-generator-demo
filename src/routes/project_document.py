from fastapi import APIRouter, Depends

from src.models.business.project import Project
from src.dependencies.dependencies import get_project_or_404
from src.schemas.response import ApiResponse
from src.schemas.project_document import IssuesResponse
from src.schemas.project import ProjectBasicInfoResponse
from src.services.project_service import project_service
from src.services.project_document_service import project_document_service

# 项目文档路由
router = APIRouter(prefix="/api/v1/project/{project_id}", tags=["项目文档"])


@router.get("/requirement-outline", response_model=ApiResponse)
async def get_requirement_outline(project: Project = Depends(get_project_or_404)):
    """获取需求大纲
    
    Args:
        project: 项目对象
        
    Returns:
        需求大纲内容
    """
    result = await project_document_service.get_requirement_outline(project)
    return ApiResponse(data=result)


@router.get("/requirement-modules", response_model=ApiResponse)
async def get_requirement_modules(project: Project = Depends(get_project_or_404)):
    """获取需求模块
    
    Args:
        project: 项目对象
        
    Returns:
        需求模块列表
    """
    result = await project_document_service.get_requirement_modules(project)
    return ApiResponse(data=result)


@router.get("/requirement-overall", response_model=ApiResponse)
async def get_requirement_overall(project: Project = Depends(get_project_or_404)):
    """获取需求整体文档

    Args:
        project: 项目对象

    Returns:
        需求整体文档（原始版和优化版）
    """
    result = await project_document_service.get_requirement_overall(project)
    return ApiResponse(data=result)


@router.get("/requirement-overall/compare", response_model=ApiResponse)
async def get_requirement_overall(project: Project = Depends(get_project_or_404)):
    """对比需求整体文档
    
    Args:
        project: 项目对象
        
    Returns:
        需求整体文档（原始版和优化版）
    """
    result = await project_document_service.get_requirement_overall_compare(project)
    return ApiResponse(data=result)


@router.get("/architecture", response_model=ApiResponse)
async def get_architecture(project: Project = Depends(get_project_or_404)):
    """获取架构设计文档

    Args:
        project: 项目对象

    Returns:
        架构设计文档（原始版和优化版）
    """
    result = await project_document_service.get_architecture(project)
    return ApiResponse(data=result)


@router.get("/architecture/compare", response_model=ApiResponse)
async def get_architecture(project: Project = Depends(get_project_or_404)):
    """对比架构设计文档
    
    Args:
        project: 项目对象
        
    Returns:
        架构设计文档（原始版和优化版）
    """
    result = await project_document_service.get_architecture_compare(project)
    return ApiResponse(data=result)


@router.get("/database", response_model=ApiResponse)
async def get_database(project: Project = Depends(get_project_or_404)):
    """获取数据库设计文档

    Args:
        project: 项目对象

    Returns:
        数据库设计文档（原始版和优化版）
    """
    result = await project_document_service.get_database(project)
    return ApiResponse(data=result)


@router.get("/database/compare", response_model=ApiResponse)
async def get_database(project: Project = Depends(get_project_or_404)):
    """对比数据库设计文档
    
    Args:
        project: 项目对象
        
    Returns:
        数据库设计文档（原始版和优化版）
    """
    result = await project_document_service.get_database_compare(project)
    return ApiResponse(data=result)


@router.get("/issues", response_model=ApiResponse)
async def get_issues(project: Project = Depends(get_project_or_404)):
    """获取风险点和疑问
    
    Args:
        project: 项目对象
        
    Returns:
        风险点和疑问列表
    """
    result = await project_document_service.get_issues(project)
    return ApiResponse(data=result)
