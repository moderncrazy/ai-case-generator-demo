from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ProjectFileBase(BaseModel):
    """项目文件基础字段"""
    project_id: str = Field(..., description="所属项目ID")
    conversation_message_id: str = Field(..., description="上传该文件的对话消息ID")
    name: str = Field(..., description="文件名")
    path: str = Field(..., description="文件路径")
    type: Optional[str] = Field(None, description="文件类型/扩展名")
    size: int = Field(..., description="文件大小(字节)")
    content: Optional[str] = Field(None, description="文件摘要")
    summary: Optional[str] = Field(None, description="文件摘要")
    metadata: Optional[str] = Field(None, description="额外元数据")


class ProjectFileCreate(ProjectFileBase):
    """创建项目文件"""
    pass


class ProjectFileUpdate(BaseModel):
    """更新项目文件"""
    name: Optional[str] = None
    path: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None
    summary: Optional[str] = None
    metadata: Optional[str] = None


class ProjectFileResponse(ProjectFileBase):
    """项目文件响应"""
    id: str
    created_at: Optional[datetime] = None
