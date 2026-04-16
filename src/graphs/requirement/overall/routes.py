from loguru import logger
from typing import Literal
from langgraph.types import Send
from langgraph.graph import END
from langchain.messages import AIMessage

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.requirement.overall.state import State, GroupMemberState
from src.enums.group_member_role import GroupMemberRole


def review_requirement_overall_tool_router(state: GroupMemberState) -> Literal[
    "review_requirement_overall_tool_node", END]:
    """评审工具调用路由
    
    判断评审节点最后一条消息是否为工具调用，决定继续调用工具或结束评审。
    
    Args:
        state: 组员状态
        
    Returns:
        目标节点名称或 END
    """
    destination_node = END
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        destination_node = "review_requirement_overall_tool_node"
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 角色:{state["role"]} 路由至:{destination_node}")
    return destination_node


def optimize_requirement_overall_tool_router(state: State) -> Literal[
                                                                  "optimize_requirement_overall_tool_node",
                                                                  "review_requirement_overall_node"] | list[Send]:
    """优化工具调用路由（并发多角色评审）
    
    判断优化节点最后一条消息是否为工具调用：
    - 是：继续调用工具
    - 否：并发生成多个角色进行评审
    
    Args:
        state: 状态
        
    Returns:
        工具节点名称或 Send 对象列表（并发评审）
    """
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
        return [Send("review_requirement_overall_node", {"role": role, **state}) for role in roles]


def review_requirement_overall_aggregator_router(state: State) -> Literal[
    "optimize_requirement_overall_node", "optimize_requirement_overall_issue_node"]:
    """评审聚合路由
    
    根据评审发现的问题数量决定后续流程：
    - 有问题：返回优化节点继续修改
    - 无问题：进入问题整理节点
    
    Args:
        state: 状态
        
    Returns:
        目标节点名称
    """
    destination_node = "optimize_requirement_overall_issue_node"
    if state["requirement_overall_issues"]:
        destination_node = "optimize_requirement_overall_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node


def optimize_requirement_overall_issue_tool_router(state: State) -> Literal[
    "optimize_requirement_overall_issue_tool_node", END]:
    """问题整理工具调用路由
    
    判断问题整理节点最后一条消息是否为工具调用，决定继续调用工具或结束子图。
    
    Args:
        state: 状态
        
    Returns:
        目标节点名称或 END
    """
    destination_node = END
    if (isinstance(state["private_messages"], list)
            and state["private_messages"]
            and isinstance(state["private_messages"][-1], AIMessage)
            and state["private_messages"][-1].tool_calls):
        destination_node = "optimize_requirement_overall_issue_tool_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node
