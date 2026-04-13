from loguru import logger
from langgraph.runtime import Runtime
from langchain.messages import SystemMessage
from langgraph.config import get_stream_writer
from langchain_core.runnables import RunnableConfig

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.llms import default_model
from src.graphs import utils as main_utils
from src.graphs.schemas import CustomMessage
from src.graphs.tools import common_tool_list
from src.graphs.system.architecture.state import State, GroupMemberState
from src.graphs.system.architecture.tools import (
    optimize_system_architecture_output,
    review_system_architecture_output,
    optimize_system_architecture_issue_output
)
from src.enums.system_prompt import SystemPrompt
from src.enums.group_member_role import GroupMemberRole


async def optimize_system_architecture_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化系统架构节点
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    # 发送自定义消息
    writer(CustomMessage(message=f"系统架构优化中..."))
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZE_SYSTEM_ARCHITECTURE.template.format(
                       original_architecture=state.get("original_architecture") or "（空）",
                       system_architecture_content=state.get("system_architecture_content")
                                                   or state.get("optimized_architecture") or "（空）",
                       system_architecture_issue=main_utils.format_issues_to_str(
                           state.get("system_architecture_issues"))
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_system_architecture_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_system_architecture_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result


async def review_system_architecture_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审系统架构节点

    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    # 根据角色使用不同提示词
    system_prompt = None
    match state["role"]:
        case GroupMemberRole.PM:
            # 发送自定义消息
            writer(CustomMessage(message="PM评审系统架构中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_ARCHITECTURE_PM.template
        case GroupMemberRole.ARCHITECT:
            # 发送自定义消息
            writer(CustomMessage(message="架构师评审系统架构中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_ARCHITECTURE_ARCHITECT.template
        case GroupMemberRole.FRONTEND:
            # 发送自定义消息
            writer(CustomMessage(message="前端工程师评审系统架构中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_ARCHITECTURE_FRONTEND.template
        case GroupMemberRole.BACKEND:
            # 发送自定义消息
            writer(CustomMessage(message="后端工程师评审系统架构中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_ARCHITECTURE_BACKEND.template
        case GroupMemberRole.SRE:
            # 发送自定义消息
            writer(CustomMessage(message="运维工程师评审系统架构中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_ARCHITECTURE_SRE.template
        case _:
            # 发送自定义消息
            writer(CustomMessage(message="内部评审系统架构中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_ARCHITECTURE_PM.template
    messages = [
                   SystemMessage(content=system_prompt.format(
                       original_architecture=state.get("original_architecture") or "（空）",
                       system_architecture_content=state["system_architecture_content"],
                       risk=main_utils.format_issues_to_str(state.get("risks")),
                       unclear_point=main_utils.format_issues_to_str(state.get("unclear_points")),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, review_system_architecture_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         review_system_architecture_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 完成")
    return result


async def optimize_system_architecture_issue_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化系统架构问题节点

    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    # 发送自定义消息
    writer(CustomMessage(message="系统架构问题整理中..."))
    project_id = state["project_id"]
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZE_SYSTEM_ARCHITECTURE_ISSUE.template.format(
                       original_architecture=state.get("original_architecture") or "（空）",
                       system_architecture_content=state["system_architecture_content"],
                       risk=main_utils.format_issues_to_str(state.get("risks")),
                       unclear_point=main_utils.format_issues_to_str(state.get("unclear_points")),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_system_architecture_issue_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_system_architecture_issue_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
