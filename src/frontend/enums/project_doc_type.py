from enum import StrEnum


class ProjectDocType(StrEnum):
    """项目文档类型"""

    REQUIREMENT_OUTLINE = "requirement_outline"
    """需求大纲"""

    REQUIREMENT_MODULE = "requirement_module"
    """需求模块"""

    REQUIREMENT_OVERALL = "requirement_overall"
    """需求文档"""

    SYSTEM_ARCHITECTURE = "system_architecture"
    """系统架构"""

    SYSTEM_MODULE = "system_module"
    """系统模块"""

    SYSTEM_DATABASE = "system_database"
    """数据库文档"""

    SYSTEM_API = "system_api"
    """系统接口"""

    TEST_CASE = "test_case"
    """测试用例"""

    ISSUES = "issues"
    """风险点和待明确问题"""
