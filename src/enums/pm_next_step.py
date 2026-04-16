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

    MONITORING_CHANGE = "monitoring_change"
    """监控需求变更"""
