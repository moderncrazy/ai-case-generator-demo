from piccolo.columns import Varchar, Timestamp

from src.models.base import BaseModel
from src.enums.creator_type import CreatorType
from src.enums.project_progress import ProjectProgress


class Project(BaseModel):
    """项目表模型"""
    id = Varchar(length=36, primary_key=True)
    name = Varchar(length=255, unique=True)
    description = Varchar(null=True)
    requirement_content = Varchar(null=True)
    requirement_optimized_content = Varchar(null=True)
    requirement_risks = Varchar(null=True)
    requirement_unclear_points = Varchar(null=True)
    architecture_design = Varchar(null=True)
    database_design = Varchar(null=True)
    progress = Varchar(default=ProjectProgress.INIT.value)
    creator_type = Varchar(default=CreatorType.USER.value)
    created_at = Timestamp(null=True)
    updated_at = Timestamp(null=True)

    class Meta:
        table_name = "project"
