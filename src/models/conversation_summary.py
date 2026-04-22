from piccolo.columns import Varchar, Integer, Timestamp, ForeignKey

from src.models.project import Project
from src.models.base import BaseModel


class ConversationSummary(BaseModel):
    """会话摘要表模型
    
    存储项目对话的摘要信息，用于上下文压缩。
    """
    id = Varchar(length=36, primary_key=True)
    """摘要唯一标识（UUID）"""
    project_id = ForeignKey(references=Project)
    """所属项目ID"""
    summary = Varchar()
    """摘要内容"""
    token_count = Integer(null=True)
    """summary 的 token 数量"""
    created_at = Timestamp()
    """创建时间"""

    class Meta:
        table_name = "conversation_summary"