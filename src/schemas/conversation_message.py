from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.enums import ConversationRole


class ConversationMessageBase(BaseModel):
    """对话消息基础字段"""
    project_id: str = Field(..., description="所属项目ID")
    role: ConversationRole = Field(..., description="角色: user/assistant/system")
    content: Optional[str] = Field(None, description="消息内容")
    metadata: Optional[str] = Field(None, description="额外元数据")


class ConversationMessageCreate(ConversationMessageBase):
    """创建对话消息"""
    pass


class ConversationMessageResponse(ConversationMessageBase):
    """对话消息响应"""
    id: str
    created_at: Optional[datetime] = None
