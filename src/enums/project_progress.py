from enum import StrEnum


class ProjectProgress(StrEnum):
    """项目进度枚举，与数据库 projects.progress 字段一致"""

    INIT = "init"
    """初始化"""

    REQUIREMENT_OUTLINE_DESIGN = "requirement_outline_design"
    """需求大纲设计"""

    REQUIREMENT_MODULE_DESIGN = "requirement_module_design"
    """需求模块设计"""

    REQUIREMENT_OVERALL_DESIGN = "requirement_overall_design"
    """需求总体（PRD）设计"""

    SYSTEM_ARCHITECTURE_DESIGN = "system_architecture_design"
    """系统架构设计"""

    SYSTEM_MODULES_DESIGN = "system_modules_design"
    """系统模块设计"""

    SYSTEM_DATABASE_DESIGN = "system_database_design"
    """系统数据库设计"""

    SYSTEM_API_DESIGN = "system_api_design"
    """系统接口设计"""

    TEST_CASE_DESIGN = "test_case_design"
    """测试用例设计"""

    COMPLETED = "completed"
    """完成"""

    @classmethod
    def get_next(cls, current: "ProjectProgress") -> "ProjectProgress | None":
        """获取下一个进度"""
        steps = list(cls)
        try:
            idx = steps.index(current)
            if idx + 1 < len(steps):
                return steps[idx + 1]
        except ValueError:
            pass
        return None

    @classmethod
    def is_completed(cls, current: "ProjectProgress") -> bool:
        """判断是否已完成"""
        return current == cls.COMPLETED
