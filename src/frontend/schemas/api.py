from typing import Optional, List
from pydantic import BaseModel, Field

from src.frontend.enums.http_method import HttpMethod


class ApiRequestParam(BaseModel):
    """API 请求参数"""
    name: str = Field(description="字段名")
    type: str = Field(description="类型")
    required: bool = Field(description="是否必填")
    description: str = Field(description="描述")


class ApiResponse(BaseModel):
    """接口响应"""
    id: str = Field(description="接口ID")
    project_id: str = Field(description="项目ID")
    module_id: str = Field(description="所属模块ID")
    name: str = Field(description="接口名称")
    method: HttpMethod = Field(description="请求方法")
    path: str = Field(description="接口路径")
    description: Optional[str] = Field(default=None, description="接口描述")
    request_headers: Optional[List[ApiRequestParam]] = Field(default=None, description="请求头参数")
    request_params: Optional[List[ApiRequestParam]] = Field(default=None, description="查询参数")
    request_body: Optional[List[ApiRequestParam]] = Field(default=None, description="请求体参数")
    response_schema: str = Field(description="响应示例")
    test_script: Optional[str] = Field(default=None, description="测试脚本")


class ApiTreeNode(BaseModel):
    """接口树节点（按模块父子级组织）"""
    module_id: str = Field(description="模块ID")
    module_name: str = Field(description="模块名称")
    apis: list[ApiResponse] = Field(default_factory=list, description="接口列表")
    children: list["ApiTreeNode"] = Field(default_factory=list, description="子模块")


class ApiTreeDocumentResponse(BaseModel):
    """API 树文档响应（原始版和优化版）"""
    original: Optional[List[ApiTreeNode]] = Field(default=None, description="原始 API 树")
    optimized: Optional[List[ApiTreeNode]] = Field(default=None, description="优化 API 树")
