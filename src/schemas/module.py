from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ModuleBase(BaseModel):
    """模块基础字段"""
    project_id: str = Field(..., description="所属项目ID")
    name: str = Field(..., description="模块名称")
    description: Optional[str] = Field(None, description="模块描述")
    parent_id: Optional[str] = Field(None, description="父级模块ID")


class ModuleCreate(ModuleBase):
    """创建模块"""
    pass


class ModuleUpdate(BaseModel):
    """更新模块"""
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[str] = None


class ModuleResponse(ModuleBase):
    """模块响应"""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
