from typing import TypeVar, Annotated
from langchain.messages import AnyMessage

from src.enums.group_member_role import GroupMemberRole
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.enums.pm_review_optimization_doc_result import PMReviewOptimizationDocResult
from src.enums.filtrate_optimization_doc_review_issue_result import FiltrateOptimizationDocReviewIssueResult
from src.graphs.state import State
from src.graphs.common.schemas.state_schemas import StateIssue
from src.graphs.common.reduce import distinct_reducer, priority_message_reducer, rewrite_reducer as wr


class OptimizationDocState(State):
    """优化流程状态定义

    扩展主图状态，添加优化流程特有的字段。
    """
    optimization_plan_content: Annotated[str, wr]
    """优化方案内容"""

    review_optimization_plan_result: Annotated[ReviewOptimizationPlanResult, wr]
    """审核优化方案结果"""

    pm_review_optimization_doc_result: Annotated[PMReviewOptimizationDocResult, wr]
    """PM审核优化文档结果"""

    group_member_review_optimization_doc_roles: Annotated[PMReviewOptimizationDocResult, wr]
    """PM审核优化文档结果"""

    filtrate_optimization_doc_review_issue_result: Annotated[FiltrateOptimizationDocReviewIssueResult, wr]
    """筛选优化文档审核问题结果"""

    review_reply_message_id: Annotated[str, wr]
    """评审回复消息ID，用于统一评审结果的消息ID"""

    review_issues: Annotated[list[StateIssue], distinct_reducer]
    """评审中提出的问题和建议（去重合并）"""

    private_messages: Annotated[list[AnyMessage], priority_message_reducer]
    """子图内部私聊消息（不暴露给主图）"""


class GroupMemberReviewOptimizationDocState(OptimizationDocState):
    """项目成员评审状态

    继承需求模块状态，添加角色标识用于区分不同评审者。
    """
    role: GroupMemberRole
    """评审成员的角色"""


class OptimizationDocBringRiskState(OptimizationDocState):
    """优化流程状态定义"""

    private_risks: Annotated[list[StateIssue], distinct_reducer]
    """子图内部需要提给客户的风险点和建议（去重合并）"""

    private_unclear_points: Annotated[list[StateIssue], distinct_reducer]
    """子图内部需要让用户明确的问题和建议（去重合并）"""


class GroupMemberReviewOptimizationDocBringRiskState(
    OptimizationDocBringRiskState, GroupMemberReviewOptimizationDocState):
    pass


AnyOptimizationDocState = TypeVar("AnyOptimizationDocState", bound=OptimizationDocState)
AnyGroupMemberReviewOptimizationDocState = TypeVar("AnyGroupMemberReviewOptimizationDocState",
                                                   bound=GroupMemberReviewOptimizationDocState)
