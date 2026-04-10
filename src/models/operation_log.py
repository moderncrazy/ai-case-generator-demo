from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.project import Project
from src.models.base import BaseModel


class OperationLog(BaseModel):
    """操作日志表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = ForeignKey(references=Project)
    entity_type = Varchar(length=50)
    entity_id = Varchar(length=36)
    action = Varchar(length=50)
    detail = Varchar(null=True)
    created_at = Timestamp()

    class Meta:
        table_name = "operation_log"
