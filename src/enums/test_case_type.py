from enum import Enum


class TestCaseType(str, Enum):
    """测试用例类型枚举，与数据库 test_cases.type 字段一致"""

    FUNCTIONAL = "functional"
    """功能测试"""

    INTERFACE = "interface"
    """接口测试"""

    PERFORMANCE = "performance"
    """性能测试"""
