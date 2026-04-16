from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from src.frontend.enums.creator_type import CreatorType


class Project(BaseModel):
    """项目表模型"""
    id: str = Field(description="项目Id")
    name: str = Field(description="项目名称")
    progress: str = Field(description="项目进度")
    description: Optional[str] = Field(default="", description="项目描述")
    requirement_outline_design: Optional[str] = Field(default="", description="需求大纲")
    requirement_module_design: Optional[str] = Field(default="", description="需求模块")
    requirement_overall_design: Optional[str] = Field(default="", description="需求文档")
    architecture_design: Optional[str] = Field(default="", description="架构设计内容")
    database_design: Optional[str] = Field(default="", description="数据库设计内容")
    creator_type: CreatorType = Field(description="创建者类型")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class ProjectCreate(BaseModel):
    """创建项目"""
    name: str = Field(description="项目名称")
    description: Optional[str] = Field(description="项目描述")


class ProjectStats(BaseModel):
    """项目统计信息"""
    modules_count: int = Field(default=0, description="模块数量")
    test_cases_count: int = Field(default=0, description="测试用例数量")
    apis_count: int = Field(default=0, description="接口数量")
    file_count: int = Field(default=0, description="文件数量")


class ProjectDetailResponse(BaseModel):
    """项目详情响应"""
    id: str = Field(description="项目ID")
    name: str = Field(description="项目名称")
    progress: str = Field(description="项目进度")
    description: Optional[str] = Field(default="", description="项目描述")
    requirement_outline_design: Optional[str] = Field(default="", description="需求大纲内容")
    requirement_module_design: Optional[str] = Field(default="", description="需求模块内容")
    requirement_overall_design: Optional[str] = Field(default="", description="需求文档内容")
    architecture_design: Optional[str] = Field(default="", description="架构设计内容")
    database_design: Optional[str] = Field(default="", description="数据库设计内容")
    creator_type: CreatorType = Field(description="创建者类型")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    stats: ProjectStats = Field(default=ProjectStats, description="统计信息")
