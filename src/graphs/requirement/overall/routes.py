from loguru import logger
from typing import Literal
from langgraph.types import Send
from langgraph.graph import END
from langchain.messages import AIMessage

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.requirement.overall.state import State
from src.enums.group_member_role import GroupMemberRole


def optimize_requirement_overall_tool_router(state: State) -> Literal[
                                                                  "optimize_requirement_overall_tool_node",
                                                                  "review_requirement_overall_node"] | list[Send]:
    """决定调用 tool 或 生成不同角色的项目成员评审需求文档"""
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:optimize_requirement_overall_tool_node")
        return "optimize_requirement_overall_tool_node"
    else:
        # 角色列表
        roles = [GroupMemberRole.PM,
                 GroupMemberRole.ARCHITECT,
                 GroupMemberRole.FRONTEND,
                 GroupMemberRole.BACKEND,
                 GroupMemberRole.TEST]
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:review_requirement_overall_node")
        return [Send("review_requirement_overall_node", {"role": role}) for role in roles]


def review_requirement_overall_tool_router(state: State) -> Literal[
    "review_requirement_overall_tool_node", "review_requirement_overall_aggregator_node"]:
    """决定是调用 tool 或 优化需求文档 或 总结需求文档问题"""
    destination_node = "review_requirement_overall_aggregator_node"
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        destination_node = "review_requirement_overall_tool_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node


def review_requirement_overall_aggregator_router(state: State) -> Literal[
    "optimize_requirement_module_node", "optimize_requirement_module_issue_node"]:
    destination_node = "optimize_requirement_overall_issue_node"
    if state["requirement_overall_issues"]:
        destination_node = "optimize_requirement_overall_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node


def optimize_requirement_overall_issue_tool_router(state: State) -> Literal[
    "optimize_requirement_overall_issue_tool_node", END]:
    """决定是调用 tool 或 返回主图"""
    destination_node = END
    if (isinstance(state["private_messages"], list)
            and isinstance(state["private_messages"][-1], AIMessage)
            and state["private_messages"][-1].tool_calls):
        destination_node = "optimize_requirement_overall_issue_tool_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node
