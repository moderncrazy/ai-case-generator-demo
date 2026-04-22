from enum import StrEnum


class ConversationMessageType(StrEnum):
    """对话消息类型"""

    MESSAGE = "message"
    """消息（AI发送的实体消息）"""

    STAGE = "stage"
    """阶段消息（某个阶段中消息）"""

    STREAM = "stream"
    """消息流（前端拼接展示）"""

    NOTIFY = "notify"
    """通知消息"""

    END = "end"
    """结束消息"""
