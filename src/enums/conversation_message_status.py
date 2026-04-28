from enum import StrEnum


class ConversationMessageStatus(StrEnum):
    """对话消息状态"""

    SUCCESS = "success"
    """处理成功"""

    FAILED = "failed"
    """处理失败"""
