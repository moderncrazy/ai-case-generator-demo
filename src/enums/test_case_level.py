from enum import Enum


class TestCaseLevel(str, Enum):
    """测试用例等级枚举，与数据库 test_cases.level 字段一致"""

    P0 = "P0"
    """核心功能"""

    P1 = "P1"
    """重要功能"""

    P2 = "P2"
    """一般功能"""

    P3 = "P3"
    """低优先级"""
