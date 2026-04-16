import uuid
from typing import Optional
from pydantic import BaseModel, Field

from src.graphs.schemas import Issue
from src.enums.http_method import HttpMethod
from src.enums.http_param_type import HttpParamType


class SystemApiRequestParam(BaseModel):
    name: str = Field(description="请求参数名称", min_length=1)
    type: HttpParamType = Field(description="请求参数类型（STRING/NUMBER/OBJECT/ARRAY）")
    required: bool = Field(description="请求参数是否必填")
    description: str = Field(description="请求参数描述或样例", min_length=1)


class SystemApi(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="接口Id，默认自动生成",
                              min_length=1)
    module_id: str = Field(description="接口所属模块Id", min_length=1)
    name: str = Field(description="接口名称", min_length=1)
    method: HttpMethod = Field(description="接口调用方式（GET/POST/PUT/DELETE/PATCH）")
    path: str = Field(description="接口url路径", min_length=1)
    description: Optional[str] = Field(description="接口描述")
    request_headers: Optional[list[SystemApiRequestParam]] = Field(description="接口请求头，若不需要可为空")
    request_params: Optional[list[SystemApiRequestParam]] = Field(description="接口请求参数，若不需要可为空")
    request_body: Optional[list[SystemApiRequestParam]] = Field(description="接口请求体，若不需要可为空")
    response_schema: str = Field(description="接口请求响应格式", min_length=1)


class OptimizeSystemApiOutput(BaseModel):
    """后端优化系统接口输出"""
    message: str = Field(description="针对系统接口优化的总结以及给团队成员接下来review的留言", min_length=1)
    system_apis: list[SystemApi] = Field(description="输出优化后系统接口列表", min_length=1)


class ReviewSystemApiOutput(BaseModel):
    """项目成员审查系统接口输出"""
    system_api_issues: list[Issue] = Field(description="针对系统接口提出的问题和建议方案")
