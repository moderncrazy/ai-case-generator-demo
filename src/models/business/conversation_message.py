from piccolo.columns import Varchar, Timestamp, ForeignKey
from piccolo.table import Table

from src.models.base import BUSINESS_DB
from src.models.business.project import Project


class ConversationMessage(Table, db=BUSINESS_DB):
    """对话消息表模型
    
    存储项目对话中的消息记录。
    """
    id = Varchar(length=36, primary_key=True)
    """消息唯一标识（UUID）"""
    project_id = ForeignKey(references=Project)
    """所属项目ID"""
    role = Varchar(length=20)
    """消息角色（user/assistant/system）"""
    content = Varchar()
    """消息内容"""
    metadata = Varchar(null=True)
    """元数据（JSON 格式，存储额外信息）"""
    created_at = Timestamp()
    """创建时间"""

    class Meta:
        table_name = "conversation_message"
