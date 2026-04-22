from typing import Annotated
from langchain.messages import AnyMessage

from src.graphs.state import State as BaseState
from src.graphs.common.reduce import priority_message_reducer, rewrite_reducer as wr
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult


class State(BaseState):
    """需求大纲子图状态定义
    
    继承主图状态，添加私聊消息字段用于子图内部通信。
    """

    private_messages: Annotated[list[AnyMessage], priority_message_reducer]
    """子图内部私聊消息（不暴露给主图）"""

    review_optimization_plan_result: Annotated[ReviewOptimizationPlanResult, wr]
    """审核优化方案结果"""
