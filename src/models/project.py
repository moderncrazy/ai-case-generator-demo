from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.base import BaseModel
from src.enums.creator_type import CreatorType
from src.enums.project_progress import ProjectProgress


class Project(BaseModel):
    """项目表模型
    
    存储项目的基本信息和设计文档。
    """
    id = Varchar(length=36, primary_key=True)
    """项目唯一标识（UUID）"""
    name = Varchar(length=255, unique=True)
    """项目名称（唯一）"""
    description = Varchar(null=True)
    """项目描述"""
    requirement_outline_design = Varchar(null=True)
    """需求大纲设计"""
    requirement_module_design = Varchar(null=True)
    """需求模块设计（JSON 格式存储）"""
    requirement_overall_design = Varchar(null=True)
    """整体需求文档设计"""
    architecture_design = Varchar(null=True)
    """系统架构设计"""
    database_design = Varchar(null=True)
    """数据库设计"""
    progress = Varchar(default=ProjectProgress.INIT.value)
    """项目进度状态"""
    creator_type = Varchar(default=CreatorType.USER.value)
    """创建者类型"""
    created_at = Timestamp()
    """创建时间"""
    updated_at = Timestamp()
    """更新时间"""

    class Meta:
        table_name = "project"
