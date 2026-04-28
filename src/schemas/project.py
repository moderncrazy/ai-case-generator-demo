from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.enums.creator_type import CreatorType
from src.enums.project_progress import ProjectProgress


class ProjectCreate(BaseModel):
    """创建项目"""
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")


class ProjectListItem(BaseModel):
    """项目列表项"""
    id: str = Field(description="项目ID")
    name: str = Field(description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    progress: ProjectProgress = Field(description="项目进度")
    created_at: datetime = Field(description="创建时间")
    

class ProjectBasicInfoResponse(BaseModel):
    """项目基本信息响应"""
    id: str = Field(description="项目ID")
    name: str = Field(description="项目名称")
    progress: ProjectProgress = Field(description="项目进度")
    description: Optional[str] = Field(None, description="项目描述")
    has_requirement_outline: bool = Field(default=False, description="是否有需求大纲")
    has_requirement_modules: bool = Field(default=False, description="是否有需求模块")
    has_requirement_overall: bool = Field(default=False, description="是否有需求整体设计")
    has_architecture: bool = Field(default=False, description="是否有架构设计")
    has_database: bool = Field(default=False, description="是否有数据库设计")
    has_modules: bool = Field(default=False, description="是否有系统模块")
    has_apis: bool = Field(default=False, description="是否有系统接口")
    has_test_cases: bool = Field(default=False, description="是否有测试用例")
    creator_type: CreatorType = Field(description="创建者类型")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
