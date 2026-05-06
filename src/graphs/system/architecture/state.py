from typing import Annotated

from src.graphs.common.reduce import rewrite_reducer as wr
from src.graphs.common.base.state import OptimizationDocBringRiskState, GroupMemberReviewOptimizationDocBringRiskState


class State(OptimizationDocBringRiskState):
    """系统架构子图状态定义
    
    继承主图状态，添加系统架构优化流程特有的字段。
    """

    system_architecture_content: Annotated[str, wr]
    """当前正在优化的系统架构内容"""


class GroupMemberState(State, GroupMemberReviewOptimizationDocBringRiskState):
    pass
