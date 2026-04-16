from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.project import Project
from src.models.base import BaseModel


class Module(BaseModel):
    """模块表模型
    
    存储系统模块的层级结构，支持父子模块关系。
    """
    id = Varchar(length=36, primary_key=True)
    """模块唯一标识（UUID）"""
    project_id = ForeignKey(references=Project)
    """所属项目ID"""
    parent_id = ForeignKey(null=True, key_column="parent_id", references="self")
    """父模块ID（顶级模块为空）"""
    name = Varchar(length=255)
    """模块名称"""
    description = Varchar(null=True)
    """模块描述"""
    created_at = Timestamp()
    """创建时间"""
    updated_at = Timestamp()
    """更新时间"""

    class Meta:
        table_name = "module"
