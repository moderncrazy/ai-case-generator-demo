from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ModuleResponse(BaseModel):
    """模块响应"""
    id: str = Field(description="模块ID")
    project_id: str = Field(description="项目ID")
    parent_id: Optional[str] = Field(default=None, description="父模块ID")
    name: str = Field(description="模块名称")
    description: Optional[str] = Field(default=None, description="模块描述")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class ModuleTreeNode(BaseModel):
    """模块树节点"""
    id: str = Field(description="模块ID")
    parent_id: Optional[str] = Field(default=None, description="父模块ID")
    name: str = Field(description="模块名称")
    description: Optional[str] = Field(default=None, description="模块描述")
    children: list["ModuleTreeNode"] = Field(default_factory=list, description="子模块")


class ModuleTreeDocumentResponse(BaseModel):
    """模块树文档响应（原始版和优化版）"""
    original: Optional[List[ModuleTreeNode]] = Field(default=None, description="原始模块树")
    optimized: Optional[List[ModuleTreeNode]] = Field(default=None, description="优化模块树")
