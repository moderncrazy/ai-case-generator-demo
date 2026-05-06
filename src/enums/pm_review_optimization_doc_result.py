from enum import StrEnum


class PMReviewOptimizationDocResult(StrEnum):
    """审核优化方案结果"""

    PASS = "pass"
    """审核通过（直接给用户）"""

    REVISE = "revise"
    """修正"""

    GROUP_MEMBER_REVIEW = "group_member_review"
    """团队成员审核"""
