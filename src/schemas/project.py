from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.enums.creator_type import CreatorType
from src.enums.project_progress import ProjectProgress


class ProjectCreate(BaseModel):
    """创建项目"""
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
