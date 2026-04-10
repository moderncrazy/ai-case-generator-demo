from loguru import logger
from typing import Literal
from langgraph.types import Send
from langgraph.graph import END
from langchain.messages import AIMessage

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.requirement.state import State
from src.enums.group_member_role import GroupMemberRole


def optimize_prd_node_tool_router(state: State) -> Literal["optimize_prd_tool_node", "review_prd_node"] | list[Send]:
    """决定调用 tool 或 生成不同角色的项目成员评审prd"""
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:optimize_prd_tool_node")
        return "optimize_prd_tool_node"
    else:
        # 角色列表
        roles = [GroupMemberRole.PM,
                 GroupMemberRole.ARCHITECT,
                 GroupMemberRole.FRONTEND,
                 GroupMemberRole.BACKEND,
                 GroupMemberRole.TEST]
        logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:review_prd_node")
        return [Send("review_prd_node", {"role": role}) for role in roles]


def review_prd_tool_router(state: State) -> Literal[
    "review_prd_tool_node", "optimize_prd_node", "optimize_prd_issue_node"]:
    """决定是调用 tool 或 优化prd 或 总结prd问题"""
    destination_node = "optimize_prd_issue_node"
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        destination_node = "review_prd_tool_node"
    elif state["requirement_issues"]:
        destination_node = "optimize_prd_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node


def optimize_prd_issue_router(state: State) -> Literal["optimize_prd_issue_tool_node", END]:
    """决定是调用 tool 或 返回主图"""
    destination_node = END
    if (isinstance(state["private_messages"], list)
            and isinstance(state["private_messages"][-1], AIMessage)
            and state["private_messages"][-1].tool_calls):
        destination_node = "optimize_prd_issue_tool_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node
