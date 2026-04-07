from piccolo.columns import Varchar, Timestamp, Integer

from src.models.base import BaseModel


class ProjectFile(BaseModel):
    """项目文件表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = Varchar(length=36)
    conversation_message_id = Varchar(length=36)
    name = Varchar(length=255)
    path = Varchar(length=500)
    type = Varchar(length=50, null=True)
    size = Integer(null=True)
    metadata = Varchar(null=True)
    created_at = Timestamp(null=True)

    class Meta:
        table_name = "project_file"
