from typing import Annotated
from langchain.messages import AnyMessage

from src.graphs.state import State as BaseState
from src.graphs.reduce import priority_message_reducer


class State(BaseState):
    """LangGraph 工作流状态定义"""

    private_messages: Annotated[list[AnyMessage], priority_message_reducer]
    """用于子图私聊"""
