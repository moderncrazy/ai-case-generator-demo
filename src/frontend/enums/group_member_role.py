from enum import StrEnum


class GroupMemberRole(StrEnum):
    """项目成员角色"""

    PM = "product_manager"
    """产品经理"""

    PRODUCT = "product"
    """产品"""

    ARCHITECT = "architect"
    """架构师"""

    DBA = "dba"
    """数据库专家"""

    FRONTEND = "frontend"
    """前端"""

    BACKEND = "backend"
    """后端"""

    TEST = "test"
    """测试"""

    SRE = "sre"
    """运维"""

    GROUP_MEMBER = "group_member"
    """全体组员"""
