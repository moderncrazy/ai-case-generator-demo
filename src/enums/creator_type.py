from enum import Enum


class CreatorType(str, Enum):
    """项目创建者类型枚举，与数据库 projects.creator_type 字段一致"""

    SYSTEM = "system"
    """系统创建"""

    USER = "user"
    """用户创建"""
