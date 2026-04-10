from piccolo.columns import ForeignKey, Varchar, Timestamp, Integer

from src.models.base import BaseModel
from src.models.project import Project
from src.models.conversation_message import ConversationMessage


class ProjectFile(BaseModel):
    """项目文件表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = ForeignKey(references=Project)
    conversation_message_id = ForeignKey(references=ConversationMessage)
    name = Varchar(length=255)
    path = Varchar(length=500)
    type = Varchar(length=50)
    size = Integer()
    content = Varchar(null=True)
    summary = Varchar(null=True)
    metadata = Varchar(null=True)
    created_at = Timestamp()

    class Meta:
        table_name = "project_file"
