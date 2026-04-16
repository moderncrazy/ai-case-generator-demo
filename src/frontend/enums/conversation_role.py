from enum import StrEnum


class ConversationRole(StrEnum):
    """对话角色枚举，与数据库 conversation_messages.role 字段一致"""

    USER = "user"
    """用户"""

    ASSISTANT = "assistant"
    """AI 助手"""

    SYSTEM = "system"
    """系统"""
