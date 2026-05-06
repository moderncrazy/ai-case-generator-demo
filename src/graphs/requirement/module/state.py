from typing import Annotated

from src.graphs.common.reduce import rewrite_reducer as wr
from src.graphs.common.base.state import OptimizationDocBringRiskState, GroupMemberReviewOptimizationDocBringRiskState


class State(OptimizationDocBringRiskState):
    """需求模块子图状态定义
    
    扩展主图状态，添加需求模块优化流程特有的字段。
    """

    requirement_module_content: Annotated[str, wr]
    """当前正在优化的需求模块内容"""


class GroupMemberState(State, GroupMemberReviewOptimizationDocBringRiskState):
    pass
