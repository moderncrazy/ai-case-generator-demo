from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.project import Project
from src.models.base import BaseModel


class Module(BaseModel):
    """模块表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = ForeignKey(references=Project)
    parent_id = ForeignKey(null=True, key_column="parent_id", references="self")
    name = Varchar(length=255)
    description = Varchar(null=True)
    created_at = Timestamp()
    updated_at = Timestamp()

    class Meta:
        table_name = "module"
