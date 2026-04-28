from loguru import logger
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig

from src.context import trans_id_ctx
from src.enums.group_member_role import GroupMemberRole
from src.graphs.common.utils import workflow_node_utils, utils as cutils
from src.graphs.common.tools import optimization_plan_tools, tools as ctools
from src.graphs.requirement.outline.state import State
from src.graphs.requirement.outline.tools import (
    common_tool_list,
    optimize_requirement_outline_output,
    review_optimization_requirement_outline_plan_output,
    generate_optimization_requirement_outline_plan_output,
)

tool_list = optimization_plan_tools.tool_list + ctools.tool_list + common_tool_list


async def generate_optimization_requirement_outline_plan_node(state: State, runtime: Runtime,
                                                              config: RunnableConfig) -> State:
    """生成优化方案节点

    调用 LLM 根据上下文生成优化需求大纲和模块划分的方案
    支持通过工具查询项目历史文档等信息

    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含生成的需求大纲和模块的方案）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    result = await workflow_node_utils.generate_optimization_plan(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.PRODUCT,
        generate_optimization_requirement_outline_plan_output,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_optimization_requirement_outline_plan_node(state: State, runtime: Runtime,
                                                            config: RunnableConfig) -> State:
    """审核优化方案节点

    调用 LLM 根据上下文审核优化需求大纲和模块划分的方案
    支持通过工具查询项目历史文档等信息

    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含生成的需求大纲和模块的方案）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    result = await workflow_node_utils.review_optimization_plan(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.PM,
        review_optimization_requirement_outline_plan_output,
        GroupMemberRole.PRODUCT,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def optimize_requirement_outline_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化需求大纲节点
    
    调用 LLM 根据上下文生成需求大纲和模块划分，
    支持通过工具查询项目历史文档等信息。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含生成的需求大纲和模块列表）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message("产品优化需求大纲中...", GroupMemberRole.PRODUCT)
    result = await workflow_node_utils.optimize_doc(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.PRODUCT,
        optimize_requirement_outline_output,
        GroupMemberRole.PM,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result
