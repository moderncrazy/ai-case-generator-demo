from typing import Annotated

from src.graphs.common.reduce import rewrite_reducer as wr
from src.graphs.common.base.state import OptimizationDocBringRiskState, GroupMemberReviewOptimizationDocBringRiskState


class State(OptimizationDocBringRiskState):
    """需求文档子图状态定义
    
    继承主图状态，添加需求文档优化流程特有的字段。
    """

    requirement_overall_content: Annotated[str, wr]
    """当前正在优化的需求文档内容"""


class GroupMemberState(State, GroupMemberReviewOptimizationDocBringRiskState):
    pass
