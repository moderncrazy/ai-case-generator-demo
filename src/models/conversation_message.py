from piccolo.columns import Varchar, Timestamp

from src.models.base import BaseModel


class ConversationMessage(BaseModel):
    """对话消息表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = Varchar(length=36)
    role = Varchar(length=20)
    content = Varchar(null=True)
    metadata = Varchar(null=True)
    created_at = Timestamp(null=True)

    class Meta:
        table_name = "conversation_message"
