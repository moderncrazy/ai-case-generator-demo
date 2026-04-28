from typing import Annotated
from langchain.messages import AnyMessage

from src.enums.group_member_role import GroupMemberRole
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.schemas import StateIssue
from src.graphs.state import State as BaseState
from src.graphs.common.reduce import priority_message_reducer, distinct_reducer, rewrite_reducer as wr


class State(BaseState):
    """系统数据库子图状态定义
    
    继承主图状态，添加系统数据库优化流程特有的字段。
    """

    review_reply_message_id: Annotated[str, wr]
    """评审回复消息ID，用于统一评审结果的消息ID"""

    system_database_content: Annotated[str, wr]
    """当前正在优化的系统数据库文档内容"""

    review_issues: Annotated[list[StateIssue], distinct_reducer]
    """评审中提出的问题和建议（去重合并）"""

    private_messages: Annotated[list[AnyMessage], priority_message_reducer]
    """子图内部私聊消息（不暴露给主图）"""

    optimization_plan_content: Annotated[str, wr]
    """优化方案内容"""

    review_optimization_plan_result: Annotated[ReviewOptimizationPlanResult, wr]
    """审核优化方案结果"""


class GroupMemberState(State):
    """项目成员评审状态
    
    继承系统数据库状态，添加角色标识用于区分不同评审者。
    """
    role: GroupMemberRole
    """评审成员的角色"""
