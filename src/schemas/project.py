from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.enums import CreatorType, ProjectProgress


class ProjectCreate(BaseModel):
    """创建项目"""
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
