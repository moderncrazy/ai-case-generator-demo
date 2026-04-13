from typing import Annotated
from langchain.messages import AnyMessage

from src.graphs.schemas import Issue
from src.graphs.state import State as BaseState
from src.enums.group_member_role import GroupMemberRole
from src.graphs.reduce import priority_message_reducer, list_reducer


class State(BaseState):
    """LangGraph 工作流状态定义"""

    review_reply_message_id: str
    """Review后统一用该Id回复消息"""

    requirement_module_content: str
    """优化后需求模块内容"""

    requirement_module_issues: Annotated[list[Issue], list_reducer]
    """针对需求模块提出的问题和建议"""

    private_messages: Annotated[list[AnyMessage], priority_message_reducer]
    """用于子图私聊"""


class GroupMemberState(State):
    """项目成员状态"""

    role: GroupMemberRole
    """成员角色"""
