from enum import StrEnum


class PMNextStep(StrEnum):
    """产品经理下一步执行的操作"""

    END = "end"
    """结束对话"""

    REQUIREMENT_OUTLINE_DESIGN = "requirement_outline_design"
    """需求大纲设计"""

    REQUIREMENT_MODULE_DESIGN = "requirement_module_design"
    """需求模块设计"""

    REQUIREMENT_OVERALL_DESIGN = "requirement_overall_design"
    """需求总体（PRD）设计"""

    SYS_ARCHITECTURE_DESIGN = "sys_architecture_design"
    """系统架构设计设计"""

    SYS_MODULES_DESIGN = "sys_modules_design"
    """系统模块设计"""

    SYS_DATABASE_DESIGN = "sys_database_design"
    """系统数据库设计"""

    SYS_API_DESIGN = "sys_api_design"
    """系统接口设计"""

    TEST_CASE_DESIGN = "test_case_design"
    """测试用例设计"""

    MONITORING_CHANGE = "monitoring_change"
    """监控需求变更"""
