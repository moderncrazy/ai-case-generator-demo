from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.enums import HttpMethod


class ApiBase(BaseModel):
    """接口基础字段"""
    project_id: str = Field(..., description="所属项目ID")
    module_id: Optional[str] = Field(None, description="所属模块ID")
    name: str = Field(..., description="接口名称")
    method: HttpMethod = Field(..., description="HTTP 方法: GET/POST/PUT/DELETE")
    path: str = Field(..., description="接口路径")
    description: Optional[str] = Field(None, description="接口描述")
    request_params: Optional[str] = Field(None, description="请求参数")
    request_body: Optional[str] = Field(None, description="请求体")
    response_schema: Optional[str] = Field(None, description="响应结构")
    test_script: Optional[str] = Field(None, description="压测脚本")


class ApiCreate(ApiBase):
    """创建接口"""
    pass


class ApiUpdate(BaseModel):
    """更新接口"""
    module_id: Optional[str] = None
    name: Optional[str] = None
    method: Optional[HttpMethod] = None
    path: Optional[str] = None
    description: Optional[str] = None
    request_params: Optional[str] = None
    request_body: Optional[str] = None
    response_schema: Optional[str] = None
    test_script: Optional[str] = None


class ApiResponse(ApiBase):
    """接口响应"""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
