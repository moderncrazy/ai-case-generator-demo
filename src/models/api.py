from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.base import BaseModel
from src.models.project import Project
from src.models.module import Module


class Api(BaseModel):
    """接口表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = ForeignKey(references=Project)
    module_id = ForeignKey(references=Module)
    name = Varchar(length=255)
    method = Varchar(length=10)
    path = Varchar(length=500)
    description = Varchar(null=True)
    request_params = Varchar()
    request_body = Varchar()
    response_schema = Varchar()
    test_script = Varchar(null=True)
    created_at = Timestamp()
    updated_at = Timestamp()

    class Meta:
        table_name = "api"
