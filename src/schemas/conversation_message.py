from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

from src.enums.project_progress import ProjectProgress
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_role import ConversationRole
from src.enums.conversation_message_type import ConversationMessageType


class HistoryConversationMessage(BaseModel):
    """历史对话消息响应"""
    id: str = Field(description="对话ID")
    project_id: str = Field(description="项目Id")
    role: ConversationRole = Field(description="角色: user/assistant/system")
    content: str = Field(description="消息内容")
    metadata: dict = Field(default={}, description="元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class ConversationMessage(BaseModel):
    """对话消息响应"""
    id: str = Field(description="对话ID")
    role: ConversationRole = Field(description="角色: user/assistant/system")
    assistant_role: Optional[GroupMemberRole] = Field(default=None, description="assistant角色")
    type: ConversationMessageType = Field(description="消息类型: message/stream/notify/end")
    content: str = Field(description="消息内容")
    metadata: dict = Field(default={}, description="元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class ConversationContext(BaseModel):
    """对话上下文响应"""
    project_progress: ProjectProgress = Field(description="项目进度状态")


class ConversationMessageResponse(BaseModel):
    """对话消息响应"""
    message: ConversationMessage = Field(description="对话消息")
    context: Optional[ConversationContext] = Field(default=None, description="对话上下文")
