from enum import StrEnum


class PMNextStep(StrEnum):
    """产品经理下一步执行的操作"""

    END = "end"
    """结束对话"""

    REQUIREMENT_DESIGN = "requirement_design"
    """需求设计"""

    SYSTEM_DESIGN = "system_design"
    """系统设计"""

    API_DESIGN = "api_design"
    """接口设计"""

    TEST_CASE_DESIGN = "test_case_design"
    """测试用例设计"""

    STRESS_TEST_DESIGN = "stress_test_design"
    """压测脚本设计"""
