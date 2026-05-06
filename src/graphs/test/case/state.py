from typing import Annotated

from src.graphs.common.reduce import rewrite_reducer as wr
from src.graphs.common.schemas.state_schemas import StateTestCase
from src.graphs.common.base.state import OptimizationDocState, GroupMemberReviewOptimizationDocState


class State(OptimizationDocState):
    """测试用例子图状态定义
    
    继承主图状态，添加测试用例优化流程特有的字段。
    """

    test_cases: Annotated[list[StateTestCase], wr]
    """当前正在优化的测试用例列表"""


class GroupMemberState(State, GroupMemberReviewOptimizationDocState):
    pass
