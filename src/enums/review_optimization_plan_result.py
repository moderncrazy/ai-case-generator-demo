from enum import StrEnum


class ReviewOptimizationPlanResult(StrEnum):
    """审核优化方案结果"""

    APPROVE = "approve"
    """批准"""

    REVISE = "revise"
    """修正"""

    ASK_QUESTION = "ask_question"
    """向人类咨询"""
