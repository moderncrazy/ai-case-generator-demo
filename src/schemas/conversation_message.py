from datetime import datetime
from pydantic import BaseModel, Field

from src.enums.conversation_role import ConversationRole


class ConversationMessageResponse(BaseModel):
    """对话消息响应"""
    id: str = Field(description="对话ID")
    project_id: str = Field(description="项目ID")
    role: ConversationRole = Field(description="角色: user/assistant/system")
    content: str = Field(description="消息内容")
    metadata: str = Field(default=None, description="额外元数据")
    created_at: datetime = Field(default=datetime.now(), description="创建时间")
