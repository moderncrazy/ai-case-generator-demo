from enum import StrEnum


class CreatorType(StrEnum):
    """项目创建者类型枚举，与数据库 projects.creator_type 字段一致"""

    SYSTEM = "system"
    """系统创建"""

    USER = "user"
    """用户创建"""
