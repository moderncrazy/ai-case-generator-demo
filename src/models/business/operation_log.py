from piccolo.columns import Varchar, Timestamp, ForeignKey
from piccolo.table import Table

from src.models.base import BUSINESS_DB
from src.models.business.project import Project


class OperationLog(Table, db=BUSINESS_DB):
    """操作日志表模型
    
    记录项目中的关键操作，用于审计和追踪。
    """
    id = Varchar(length=36, primary_key=True)
    """日志唯一标识（UUID）"""
    project_id = ForeignKey(references=Project)
    """所属项目ID"""
    entity_type = Varchar(length=50)
    """实体类型（如：module/api/test_case）"""
    entity_id = Varchar(length=36)
    """实体ID"""
    action = Varchar(length=50)
    """操作类型（如：create/update/delete）"""
    detail = Varchar(null=True)
    """操作详情（JSON 格式）"""
    created_at = Timestamp()
    """创建时间"""

    class Meta:
        table_name = "operation_log"
