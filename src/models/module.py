from piccolo.columns import Varchar, Timestamp

from src.models.base import BaseModel


class Module(BaseModel):
    """模块表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = Varchar(length=36)
    parent_id = Varchar(length=36, null=True)
    name = Varchar(length=255)
    description = Varchar(null=True)
    created_at = Timestamp(null=True)
    updated_at = Timestamp(null=True)

    class Meta:
        table_name = "module"
