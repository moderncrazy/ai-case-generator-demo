from typing import Annotated
from langchain.messages import AnyMessage

from src.graphs.state import State as BaseState
from src.graphs.schemas import StateIssue, StateModule
from src.enums.group_member_role import GroupMemberRole
from src.graphs.reduce import priority_message_reducer, distinct_reducer, rewrite_reducer as wr


class State(BaseState):
    """系统模块子图状态定义
    
    继承主图状态，添加系统模块优化流程特有的字段。
    """

    review_reply_message_id: Annotated[str, wr]
    """评审回复消息ID，用于统一评审结果的消息ID"""

    system_modules: Annotated[list[StateModule], wr]
    """当前正在优化的系统模块列表"""

    system_module_issues: Annotated[list[StateIssue], distinct_reducer]
    """评审中针对系统模块提出的问题和建议（去重合并）"""

    private_messages: Annotated[list[AnyMessage], priority_message_reducer]
    """子图内部私聊消息（不暴露给主图）"""


class GroupMemberState(State):
    """项目成员评审状态
    
    继承系统模块状态，添加角色标识用于区分不同评审者。
    """
    role: GroupMemberRole
    """评审成员的角色"""
