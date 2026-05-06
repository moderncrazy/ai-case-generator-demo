from typing import Annotated

from src.graphs.test.case.schemas import StateTestCaseTask
from src.graphs.common.schemas.state_schemas import StateTestCase
from src.graphs.common.reduce import distinct_reducer, rewrite_reducer as wr
from src.graphs.common.base.state import OptimizationDocState, GroupMemberReviewOptimizationDocState


class State(OptimizationDocState):
    """测试用例子图状态定义
    
    继承主图状态，添加测试用例优化流程特有的字段。
    """

    test_cases: Annotated[list[StateTestCase], distinct_reducer]
    """当前正在优化的测试用例列表"""

    tasks: Annotated[list[StateTestCaseTask], wr]
    """输出需要优化的测试用例任务列表"""

    task_reply_message_id: Annotated[str, wr]
    """任务回复消息ID，用于统一任务结果的消息ID"""


class TaskState(State):
    """测试用例任务分配子图状态定义

    继承主图状态，添加测试用例任务特有的字段。
    """

    task: Annotated[StateTestCaseTask, wr]
    """当前具体要生成的测试用例任务"""


class GroupMemberState(State, GroupMemberReviewOptimizationDocState):
    pass
