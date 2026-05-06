from enum import StrEnum


class FiltrateOptimizationDocReviewIssueResult(StrEnum):
    """筛选文档优化审核问题结果"""

    PASS = "pass"
    """审核通过（直接给用户）"""

    REVISE = "revise"
    """修正（重新优化）"""
