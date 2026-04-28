from loguru import logger
from typing import Literal
from langgraph.types import Send
from langgraph.graph import END
from langchain.messages import AIMessage

from src.context import trans_id_ctx
from src.graphs.common.utils import workflow_router_utils
from src.graphs.requirement.module.state import State, GroupMemberState
from src.enums.group_member_role import GroupMemberRole


def generate_optimization_requirement_module_plan_tool_router(state: State) -> Literal[
    "generate_optimization_requirement_module_plan_tool_node",
    "review_optimization_requirement_module_plan_node"
]:
    project_id = state["project_id"]
    result = workflow_router_utils.tool_router(
        state,
        "generate_optimization_requirement_module_plan_tool_node",
        "review_optimization_requirement_module_plan_node"
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result


def review_optimization_requirement_module_plan_tool_router(state: State) -> Literal[
    "review_optimization_requirement_module_plan_node"
    "review_optimization_requirement_module_plan_tool_node",
    "optimize_requirement_module_node",
    "generate_optimization_requirement_module_plan_node",
    END
]:
    project_id = state["project_id"]
    result = workflow_router_utils.review_optimization_plan_tool_router(
        state,
        "review_optimization_requirement_module_plan_node",
        "review_optimization_requirement_module_plan_tool_node",
        "optimize_requirement_module_node",
        "generate_optimization_requirement_module_plan_node",
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result


def review_requirement_module_tool_router(state: GroupMemberState) -> Literal[
    "review_requirement_module_tool_node", END]:
    """评审工具调用路由"""
    project_id = state["project_id"]
    result = workflow_router_utils.tool_router(state, "review_requirement_module_tool_node", END)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{state["role"]} 路由至:{result}")
    return result


def optimize_requirement_module_tool_router(state: State) -> Literal[
                                                                 "optimize_requirement_module_node",
                                                                 "optimize_requirement_module_tool_node",
                                                                 "review_requirement_module_node"] | list[Send]:
    """优化工具调用路由（并发多角色评审）
    
    判断优化节点最后一条消息是否为工具调用：
    - 是：继续调用工具
    - 否：并发生成 多个角色进行评审
    """
    project_id = state["project_id"]
    result = workflow_router_utils.optimize_doc_tool_router(
        state,
        "optimize_requirement_module_node",
        "optimize_requirement_module_tool_node",
        "review_requirement_module_node",
        [
            GroupMemberRole.PM,
            GroupMemberRole.ARCHITECT,
            GroupMemberRole.FRONTEND,
            GroupMemberRole.BACKEND,
            GroupMemberRole.TEST
        ]
    )
    if isinstance(result, str):
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    else:
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:review_requirement_module_node")
    return result


def review_requirement_module_aggregator_router(state: State) -> Literal[
    "optimize_requirement_module_node", "optimize_requirement_module_issue_node"]:
    """评审聚合路由
    
    根据评审发现的问题数量决定后续流程：
    - 有问题：返回优化节点继续修改
    - 无问题：进入问题整理节点
    """
    project_id = state["project_id"]
    result = workflow_router_utils.review_optimize_doc_aggregator_router(
        state,
        "optimize_requirement_module_node",
        "optimize_requirement_module_issue_node"
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result


def optimize_requirement_module_issue_router(state: State) -> Literal[
    "optimize_requirement_module_issue_tool_node", END]:
    """问题整理工具调用路由"""
    project_id = state["project_id"]
    result = workflow_router_utils.tool_router(state, "optimize_requirement_module_issue_tool_node", END)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result
