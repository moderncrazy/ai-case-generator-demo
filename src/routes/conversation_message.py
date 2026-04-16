from typing import Annotated
from fastapi import APIRouter, Form, UploadFile, Depends

from src.models.project import Project
from src.dependencies.dependencies import get_project_or_404
from src.schemas.response import ApiListResponse, ListData
from src.services.conversation_message_service import conversation_message_service

# 对话消息路由
router = APIRouter(prefix="/api/v1/project", tags=["对话消息"])


@router.get("/{project_id}/messages", response_model=ApiListResponse[dict])
async def list_messages(
        project: Annotated[Project, Depends(get_project_or_404)],
        page: int = 1,
        page_size: int = 20,
):
    """获取对话历史
    
    分页获取项目的对话历史消息列表。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        page: 页码（从 1 开始）
        page_size: 每页数量
        
    Returns:
        返回对话消息列表和总数
    """
    messages, total = await conversation_message_service.list_messages(
        project_id=project.id,
        page=page,
        page_size=page_size,
    )
    list_data = ListData(items=messages, total=total, page=page, page_size=page_size)
    return ApiListResponse(data=list_data)


@router.post("/{project_id}/discuss")
async def discuss_project(
        project: Annotated[Project, Depends(get_project_or_404)],
        message: Annotated[str, Form()],
        files: list[UploadFile] = None,
):
    """项目对话
    
    用户发送消息与 AI 进行项目相关的对话讨论。
    支持上传文件，AI 会解析文件内容并结合项目上下文进行回复。
    
    Args:
        project: 项目对象（通过依赖注入获取）
        message: 用户输入的消息内容
        files: 上传的文件列表（可选，支持多文件）
        
    Returns:
        返回对话响应结果
    """
    return await conversation_message_service.discuss_project(project=project, message=message, files=files)
