from piccolo.columns import ForeignKey, Varchar, Timestamp, Integer
from piccolo.table import Table

from src.models.base import BUSINESS_DB
from src.models.business.project import Project
from src.models.business.conversation_message import ConversationMessage


class ProjectFile(Table, db=BUSINESS_DB):
    """项目文件表模型
    
    存储项目相关文件的元信息和内容。
    """
    id = Varchar(length=36, primary_key=True)
    """文件唯一标识（UUID）"""
    project_id = ForeignKey(references=Project)
    """所属项目ID"""
    conversation_message_id = ForeignKey(references=ConversationMessage)
    """关联的对话消息ID"""
    name = Varchar(length=255)
    """文件名"""
    path = Varchar(length=500)
    """文件路径"""
    type = Varchar(length=50)
    """文件类型（MIME type）"""
    size = Integer()
    """文件大小（字节）"""
    content = Varchar(null=True)
    """文件内容（OCR 解析后的文本）"""
    summary = Varchar(null=True)
    """文件摘要（AI 提取的关键信息）"""
    metadata = Varchar(null=True)
    """元数据（JSON 格式）"""
    created_at = Timestamp()
    """创建时间"""

    class Meta:
        table_name = "project_file"
