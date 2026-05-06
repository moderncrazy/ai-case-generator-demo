from typing import Annotated

from src.graphs.common.reduce import rewrite_reducer as wr
from src.graphs.common.schemas.state_schemas import StateModule
from src.graphs.common.base.state import OptimizationDocState, GroupMemberReviewOptimizationDocState


class State(OptimizationDocState):
    """系统模块子图状态定义
    
    继承主图状态，添加系统模块优化流程特有的字段。
    """

    system_modules: Annotated[list[StateModule], wr]
    """当前正在优化的系统模块列表"""


class GroupMemberState(State, GroupMemberReviewOptimizationDocState):
    pass
