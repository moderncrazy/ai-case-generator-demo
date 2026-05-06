from typing import Annotated

from src.graphs.common.reduce import rewrite_reducer as wr
from src.graphs.common.base.state import OptimizationDocState, GroupMemberReviewOptimizationDocState


class State(OptimizationDocState):
    """系统数据库子图状态定义
    
    继承主图状态，添加系统数据库优化流程特有的字段。
    """

    system_database_content: Annotated[str, wr]
    """当前正在优化的系统数据库文档内容"""


class GroupMemberState(State, GroupMemberReviewOptimizationDocState):
    pass
