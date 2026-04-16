from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.base import BaseModel
from src.models.project import Project
from src.models.module import Module


class Api(BaseModel):
    """接口表模型
    
    存储系统 API 接口的定义信息。
    """
    id = Varchar(length=36, primary_key=True)
    """接口唯一标识（UUID）"""
    project_id = ForeignKey(references=Project)
    """所属项目ID"""
    module_id = ForeignKey(references=Module)
    """所属模块ID"""
    name = Varchar(length=255)
    """接口名称"""
    method = Varchar(length=10)
    """HTTP 方法（GET/POST/PUT/DELETE 等）"""
    path = Varchar(length=500)
    """接口路径"""
    description = Varchar(null=True)
    """接口描述"""
    request_headers = Varchar(null=True)
    """请求头参数（JSON 格式）"""
    request_params = Varchar(null=True)
    """URL 查询参数（JSON 格式）"""
    request_body = Varchar(null=True)
    """请求体参数（JSON 格式）"""
    response_schema = Varchar()
    """响应结构定义"""
    test_script = Varchar(null=True)
    """测试脚本"""
    created_at = Timestamp()
    """创建时间"""
    updated_at = Timestamp()
    """更新时间"""

    class Meta:
        table_name = "api"
