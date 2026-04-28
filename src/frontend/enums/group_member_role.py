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

    def get_name_zh(self) -> str:
        match self:
            case GroupMemberRole.PM:
                return "产品经理"
            case GroupMemberRole.PRODUCT:
                return "产品"
            case GroupMemberRole.ARCHITECT:
                return "架构师"
            case GroupMemberRole.DBA:
                return "数据库专家"
            case GroupMemberRole.FRONTEND:
                return "前端工程师"
            case GroupMemberRole.BACKEND:
                return "后端工程师"
            case GroupMemberRole.TEST:
                return "测试工程师"
            case GroupMemberRole.SRE:
                return "运维工程师"
            case GroupMemberRole.GROUP_MEMBER:
                return "全体项目成员"
