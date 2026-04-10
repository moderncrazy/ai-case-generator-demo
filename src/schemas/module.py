from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Module(BaseModel):
    """模块基础字段"""
    project_id: str = Field(..., description="所属项目ID")
    name: str = Field(..., description="模块名称")
    description: Optional[str] = Field(None, description="模块描述")
    parent_id: Optional[str] = Field(None, description="父级模块ID")
