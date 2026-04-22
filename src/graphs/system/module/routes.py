from loguru import logger
from typing import Literal
from langgraph.types import Send
from langgraph.graph import END
from langchain.messages import AIMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.group_member_role import GroupMemberRole
from src.graphs.common.utils import workflow_router_utils
from src.graphs.system.module.state import State, GroupMemberState


def generate_optimization_system_module_plan_tool_router(state: State) -> Literal[
    "generate_optimization_system_module_plan_tool_node",
    "review_optimization_system_module_plan_node"
]:
    """生成方案工具调用路由

    判断生成方案节点最后一条消息是否为工具调用：
    - 是：继续调用工具
    - 否：路由到审核方案节点
    """
    project_id = state["project_id"]
    result = workflow_router_utils.tool_router(
        state,
        "generate_optimization_system_module_plan_tool_node",
        "review_optimization_system_module_plan_node"
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result


def review_optimization_system_module_plan_tool_router(state: State) -> Literal[
    "review_optimization_system_module_plan_tool_node",
    "optimize_system_module_node",
    "generate_optimization_system_module_plan_node",
    END
]:
    """审核方案工具调用路由（合并工具调用和结果判断）

    判断审核方案节点最后一条消息是否为工具调用，以及根据审核方案结果决定后续流程：
    - 是工具调用：继续调用工具
    - APPROVED：路由到优化节点
    - REGENERATE：返回生成方案节点
    - ASK_QUESTION：结束子图返回主图
    """
    project_id = state["project_id"]
    result = workflow_router_utils.review_optimization_plan_tool_router(
        state,
        "review_optimization_system_module_plan_tool_node",
        "optimize_system_module_node",
        "generate_optimization_system_module_plan_node"
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result


def review_system_module_tool_router(state: GroupMemberState) -> Literal["review_system_module_tool_node", END]:
    """评审工具调用路由
    
    判断评审节点最后一条消息是否为工具调用，决定继续调用工具或结束评审。
    
    Args:
        state: 组员状态
        
    Returns:
        目标节点名称或 END
    """
    project_id = state["project_id"]
    result = workflow_router_utils.tool_router(state, "review_system_module_tool_node", END)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{state["role"]} 路由至:{result}")
    return result


def optimize_system_module_tool_router(state: State) -> Literal[
                                                            "optimize_system_module_tool_node",
                                                            "review_system_module_node"] | list[Send]:
    """优化工具调用路由（并发多角色评审）
    
    判断优化节点最后一条消息是否为工具调用：
    - 是：继续调用工具
    - 否：并发生成多个角色进行评审
    
    Args:
        state: 状态
        
    Returns:
        工具节点名称或 Send 对象列表（并发评审）
    """
    project_id = state["project_id"]
    if isinstance(state["private_messages"][-1], AIMessage) and state["private_messages"][-1].tool_calls:
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:optimize_system_module_tool_node")
        return "optimize_system_module_tool_node"
    else:
        # 角色列表
        roles = [GroupMemberRole.PM,
                 GroupMemberRole.ARCHITECT,
                 GroupMemberRole.FRONTEND,
                 GroupMemberRole.BACKEND,
                 GroupMemberRole.SRE]
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:review_system_module_node")
        return [Send("review_system_module_node", {"role": role, **state}) for role in roles]


def review_system_module_aggregator_router(state: State) -> Literal["optimize_system_module_node", END]:
    """评审聚合路由
    
    根据评审发现的问题数量决定后续流程：
    - 有问题：返回优化节点继续修改
    - 无问题：结束子图返回主图
    
    Args:
        state: 状态
        
    Returns:
        目标节点名称
    """
    project_id = state["project_id"]
    destination_node = END
    if state["system_module_issues"]:
        destination_node = "optimize_system_module_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
    return destination_node
