from loguru import logger
from typing import Literal
from langgraph.types import Send
from langgraph.graph import END
from langchain.messages import AIMessage

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.test.case.state import State
from src.enums.group_member_role import GroupMemberRole


def optimize_test_case_tool_router(state: State) -> Literal[
                                                         "optimize_test_case_tool_node",
                                                         "review_test_case_node"] | list[Send]:
    """决定调用 tool 或 生成不同角色的项目成员评审测试用例"""
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:optimize_test_case_tool_node")
        return "optimize_test_case_tool_node"
    else:
        # 角色列表
        roles = [GroupMemberRole.PM,
                 GroupMemberRole.ARCHITECT,
                 GroupMemberRole.FRONTEND,
                 GroupMemberRole.BACKEND,
                 GroupMemberRole.TEST]
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:review_test_case_node")
        return [Send("review_test_case_node", {"role": role}) for role in roles]


def review_test_case_tool_router(state: State) -> Literal[
    "review_test_case_tool_node", "review_test_case_aggregator_node"]:
    """决定是调用 tool 或 优化测试用例 或 总结测试用例问题"""
    destination_node = "review_test_case_aggregator_node"
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        destination_node = "review_test_case_tool_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node


def review_test_case_aggregator_router(state: State) -> Literal["optimize_test_case_node", END]:
    destination_node = END
    if state["test_case_issues"]:
        destination_node = "optimize_test_case_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node
