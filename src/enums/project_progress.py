from enum import StrEnum


class ProjectProgress(StrEnum):
    """项目进度枚举，与数据库 projects.progress 字段一致"""

    INIT = "init"
    """初始化"""

    REQUIREMENT = "requirement"
    """需求设计"""

    SYSTEM_DESIGN = "system_design"
    """系统设计"""

    API = "api"
    """接口设计"""

    TEST_CASE = "test_case"
    """测试用例设计"""

    STRESS_TEST = "stress_test"
    """压测脚本设计"""

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
