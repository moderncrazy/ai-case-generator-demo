from loguru import logger
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig

from src.context import trans_id_ctx
from src.graphs.common.tools import tool_list as ctool_list
from src.graphs.common.utils import workflow_node_utils, utils as cutils
from src.graphs.system.architecture.state import State, GroupMemberState
from src.graphs.system.architecture.tools import (
    common_tool_list,
    optimize_system_architecture_output,
    review_system_architecture_output,
    optimize_system_architecture_issue_output,
    review_optimization_system_architecture_plan_output,
    generate_optimization_system_architecture_plan_output,
)
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType


async def generate_optimization_system_architecture_plan_node(state: State, runtime: Runtime,
                                                              config: RunnableConfig) -> State:
    """生成优化方案节点"""
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    tool_list = [*ctool_list, *common_tool_list]
    result = await workflow_node_utils.generate_optimization_plan(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.ARCHITECT,
        generate_optimization_system_architecture_plan_output,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_optimization_system_architecture_plan_node(state: State, runtime: Runtime,
                                                            config: RunnableConfig) -> State:
    """审核优化方案节点"""
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    tool_list = [*ctool_list, *common_tool_list]
    result = await workflow_node_utils.review_optimization_plan(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.PM,
        review_optimization_system_architecture_plan_output,
        GroupMemberRole.ARCHITECT,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def optimize_system_architecture_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化系统架构节点
    
    调用 LLM 根据上下文优化系统架构内容，
    支持通过工具查询项目历史文档等信息。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含优化后的架构内容）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message("架构优化系统架构中...", GroupMemberRole.ARCHITECT)
    tool_list = [*ctool_list, *common_tool_list]
    result = await workflow_node_utils.optimize_doc(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.ARCHITECT,
        optimize_system_architecture_output,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_system_architecture_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审系统架构节点
    
    根据成员角色使用不同提示词评审系统架构，
    评审结果包含问题列表、风险点和不明确点。
    
    Args:
        state: 成员评审状态（包含角色标识）
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含评审意见）
    """
    role = state["role"]
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 进入")
    # 根据角色使用不同提示词
    cutils.send_custom_message(f"{role}评审系统架构中...", role)
    tool_list = [*ctool_list, *common_tool_list]
    result = await workflow_node_utils.review_optimization_doc(
        state,
        runtime,
        config,
        tool_list,
        review_system_architecture_output,
        GroupMemberRole.ARCHITECT
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 完成")
    return result


async def optimize_system_architecture_issue_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """整理系统架构问题节点
    
    收集汇总各角色评审意见，整理出风险点和不明确点。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含最终风险点和不明确点）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message("整理系统架构问题中...", GroupMemberRole.ARCHITECT)
    tool_list = [*ctool_list, *common_tool_list]
    result = await workflow_node_utils.summarize_optimization_doc_issue(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.ARCHITECT,
        optimize_system_architecture_issue_output,
    )
    cutils.send_custom_message(
        "架构文档已更新，快来看看吧！", GroupMemberRole.ARCHITECT, ConversationMessageType.NOTIFY)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result
