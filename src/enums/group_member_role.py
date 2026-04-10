from enum import StrEnum


class GroupMemberRole(StrEnum):
    """项目成员角色"""

    PM = "pm"
    """产品经理"""

    PRODUCT = "product"
    """产品"""

    ARCHITECT = "architect"
    """架构师"""

    FRONTEND = "frontend"
    """前端"""

    BACKEND = "backend"
    """后端"""

    TEST = "test"
    """测试"""
