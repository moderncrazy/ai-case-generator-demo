from enum import StrEnum
from functools import cached_property


class RequirementModuleStatus(StrEnum):
    """需求模块状态"""

    PENDING = "pending"
    """待处理"""

    DRAFT = "draft"
    """草稿中"""

    COMPLETED = "completed"
    """已完成"""

    @cached_property
    def name_zh(self):
        match self:
            case RequirementModuleStatus.PENDING:
                return "待设计"
            case RequirementModuleStatus.DRAFT:
                return "草稿"
            case RequirementModuleStatus.COMPLETED:
                return "已确认"
