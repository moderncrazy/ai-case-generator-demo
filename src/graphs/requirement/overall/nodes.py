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
from src.graphs.requirement.overall.state import State, GroupMemberState
from src.graphs.requirement.overall.tools import (
    optimize_requirement_overall_output,
    review_requirement_overall_output,
    optimize_requirement_overall_issue_output
)
from src.enums.system_prompt import SystemPrompt
from src.enums.group_member_role import GroupMemberRole


async def optimize_requirement_overall_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化需求文档节点
    
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
    writer(CustomMessage(message="产品优化需求文档中..."))
    project_id = state["project_id"]
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZED_REQUIREMENT_OVERALL.template.format(
                       original_requirement=state.get("original_requirement") or "（空）",
                       requirement_overall_content=state.get("requirement_overall_content")
                                                   or state.get("optimized_requirement") or "（空）",
                       requirement_overall_issues=main_utils.format_issues_to_str(
                           state.get("requirement_overall_issues")),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_requirement_overall_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_requirement_overall_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result


async def review_requirement_overall_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审需求文档节点

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
            writer(CustomMessage(message="PM评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_OVERALL_PM.template
        case GroupMemberRole.ARCHITECT:
            # 发送自定义消息
            writer(CustomMessage(message="架构师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_OVERALL_ARCHITECT.template
        case GroupMemberRole.FRONTEND:
            # 发送自定义消息
            writer(CustomMessage(message="前端工程师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_OVERALL_FRONTEND.template
        case GroupMemberRole.BACKEND:
            # 发送自定义消息
            writer(CustomMessage(message="后端工程师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_OVERALL_BACKEND.template
        case GroupMemberRole.TEST:
            # 发送自定义消息
            writer(CustomMessage(message="测试工程师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_OVERALL_TEST.template
        case _:
            # 发送自定义消息
            writer(CustomMessage(message="内部评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_OVERALL_PM.template
    messages = [
                   SystemMessage(content=system_prompt.format(
                       original_requirement=state.get("original_requirement") or "（空）",
                       requirement_overall_content=state["requirement_overall_content"],
                       risk=main_utils.format_issues_to_str(state.get("risks")),
                       unclear_point=main_utils.format_issues_to_str(state.get("unclear_points")),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, review_requirement_overall_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         review_requirement_overall_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 完成")
    return result


async def optimize_requirement_overall_issue_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化需求文档问题节点

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
    writer(CustomMessage(message="需求文档问题整理中..."))
    project_id = state["project_id"]
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZED_REQUIREMENT_OVERALL_ISSUE.template.format(
                       original_requirement=state.get("original_requirement") or "（空）",
                       requirement_overall_content=state["requirement_overall_content"],
                       risk=main_utils.format_issues_to_str(state.get("risks")),
                       unclear_point=main_utils.format_issues_to_str(state.get("unclear_points")),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_requirement_overall_issue_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_requirement_overall_issue_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
