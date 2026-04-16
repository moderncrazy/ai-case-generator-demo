from enum import Enum
from functools import cached_property


class ProjectProgress(Enum):
    """项目进度枚举，与数据库 projects.progress 字段一致"""

    INIT = ("init", "初始化")
    """初始化"""

    REQUIREMENT_OUTLINE_DESIGN = ("requirement_outline_design", "需求大纲设计")
    """需求大纲设计"""

    REQUIREMENT_MODULE_DESIGN = ("requirement_module_design", "需求模块设计")
    """需求模块设计"""

    REQUIREMENT_OVERALL_DESIGN = ("requirement_overall_design", "需求文档设计")
    """需求总体（PRD）设计"""

    SYSTEM_ARCHITECTURE_DESIGN = ("system_architecture_design", "系统架构设计")
    """系统架构设计"""

    SYSTEM_MODULES_DESIGN = ("system_modules_design", "系统模块设计")
    """系统模块设计"""

    SYSTEM_DATABASE_DESIGN = ("system_database_design", "系统数据库设计")
    """系统数据库设计"""

    SYSTEM_API_DESIGN = ("system_api_design", "系统接口设计")
    """系统接口设计"""

    TEST_CASE_DESIGN = ("test_case_design", "测试用例设计")
    """测试用例设计"""

    COMPLETED = ("completed", "完成")
    """完成"""

    def __init__(self, code: str, label: str):
        self.code = code
        self.label = label

    def get_index(self) -> int:
        return list(ProjectProgress).index(self)

    def get_percent(self) -> float:
        return (self.get_index() + 1) / len(list(ProjectProgress))

    @classmethod
    def from_code(cls, code: str) -> "ProjectProgress | None":
        for item in list(cls):
            if item.code == code:
                return item
        return None

    @classmethod
    def labels(cls) -> list[str]:
        return [item.label for item in list(cls)]
