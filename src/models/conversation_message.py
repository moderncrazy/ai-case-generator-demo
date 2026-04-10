from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.project import Project
from src.models.base import BaseModel


class ConversationMessage(BaseModel):
    """对话消息表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = ForeignKey(references=Project)
    role = Varchar(length=20)
    content = Varchar()
    metadata = Varchar(null=True)
    created_at = Timestamp()

    class Meta:
        table_name = "conversation_message"
