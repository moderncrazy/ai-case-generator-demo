from enum import StrEnum


class RequirementModuleStatus(StrEnum):
    """需求模块状态"""

    PENDING = "pending"
    """待处理"""

    DRAFT = "draft"
    """草稿中"""

    COMPLETED = "completed"
    """已完成"""
