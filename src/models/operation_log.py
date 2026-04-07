from piccolo.columns import Varchar, Timestamp

from src.models.base import BaseModel


class OperationLog(BaseModel):
    """操作日志表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = Varchar(length=36)
    entity_type = Varchar(length=50)
    entity_id = Varchar(length=36)
    action = Varchar(length=50)
    detail = Varchar(null=True)
    created_at = Timestamp(null=True)

    class Meta:
        table_name = "operation_log"
