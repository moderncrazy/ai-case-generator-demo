from piccolo.columns import Varchar, Timestamp

from src.models.base import BaseModel


class Api(BaseModel):
    """接口表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = Varchar(length=36)
    module_id = Varchar(length=36, null=True)
    name = Varchar(length=255)
    method = Varchar(length=10)
    path = Varchar(length=500)
    description = Varchar(null=True)
    request_params = Varchar(null=True)
    request_body = Varchar(null=True)
    response_schema = Varchar(null=True)
    test_script = Varchar(null=True)
    created_at = Timestamp(null=True)
    updated_at = Timestamp(null=True)

    class Meta:
        table_name = "api"
