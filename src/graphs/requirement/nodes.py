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
from src.graphs.tools import (
    get_project_info, get_project_file_by_id, search_project_files, search_project_history_conversation
)
from src.graphs.requirement.state import State, GroupMemberState
from src.graphs.requirement.tools import product_optimize_prd_output, product_optimize_issue_output, review_prd_output
from src.enums.system_prompt import SystemPrompt
from src.enums.group_member_role import GroupMemberRole
from src.services.project_file_service import project_file_service


async def optimize_prd_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化PRD节点
    
    Args:
        state: LangGraph 状态，包含 new_file_list (文件名列表)
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态，包含 new_files_content (文件名到解析内容的映射)
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    # 发送自定义消息
    writer(CustomMessage(message="产品优化需求文档中..."))
    project_id = state["project_id"]
    project_files_summary = await project_file_service.get_project_files_summary_to_str(project_id)
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZED_REQUIREMENT.template.format(
                       project_files_summary=project_files_summary,
                       original_requirement=state.get("original_requirement") or "（空）",
                       optimized_requirement=state.get("optimized_requirement") or "（空）",
                       requirement_issue=main_utils.format_issues_to_str(state["requirement_issues"]) if state.get(
                           "requirement_issues") else "（空）",
                       risk=main_utils.format_issues_to_str(state["risks"]) if state.get(
                           "risks") else "（空）",
                       unclear_point=main_utils.format_issues_to_str(state["unclear_points"]) if state.get(
                           "unclear_points") else "（空）",
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([
        get_project_info,
        get_project_file_by_id,
        search_project_files,
        search_project_history_conversation,
        product_optimize_prd_output
    ])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         product_optimize_prd_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result


async def review_prd_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审PRD节点

    Args:
        state: LangGraph 状态，包含 new_file_list (文件名列表)
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态，包含 new_files_content (文件名到解析内容的映射)
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    project_files_summary = await project_file_service.get_project_files_summary_to_str(project_id)
    # 根据角色使用不同提示词
    system_prompt = None
    match state["role"]:
        case GroupMemberRole.PM:
            # 发送自定义消息
            writer(CustomMessage(message="PM评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_PM.template
        case GroupMemberRole.ARCHITECT:
            # 发送自定义消息
            writer(CustomMessage(message="架构师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_ARCHITECT.template
        case GroupMemberRole.FRONTEND:
            # 发送自定义消息
            writer(CustomMessage(message="前端工程师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_FRONTEND.template
        case GroupMemberRole.BACKEND:
            # 发送自定义消息
            writer(CustomMessage(message="后端工程师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_BACKEND.template
        case GroupMemberRole.TEST:
            # 发送自定义消息
            writer(CustomMessage(message="测试工程师评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_TEST.template
        case _:
            # 发送自定义消息
            writer(CustomMessage(message="内部评审需求文档中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_PM.template
    messages = [
                   SystemMessage(content=system_prompt.format(
                       project_files_summary=project_files_summary,
                       original_requirement=state.get("original_requirement") or "（空）",
                       optimized_requirement=state.get("optimized_requirement") or "（空）",
                       risk=main_utils.format_issues_to_str(state["risks"]) if state.get(
                           "risks") else "（空）",
                       unclear_point=main_utils.format_issues_to_str(state["unclear_points"]) if state.get(
                           "unclear_points") else "（空）",
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([
        get_project_info,
        get_project_file_by_id,
        search_project_files,
        search_project_history_conversation,
        review_prd_output
    ])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         review_prd_output, messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 完成")
    return result


async def optimize_prd_issue_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化PRD问题节点

    Args:
        state: LangGraph 状态，包含 new_file_list (文件名列表)
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态，包含 new_files_content (文件名到解析内容的映射)
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    # 发送自定义消息
    writer(CustomMessage(message="需求文档问题整理中..."))
    project_id = state["project_id"]
    project_files_summary = await project_file_service.get_project_files_summary_to_str(project_id)
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZED_REQUIREMENT_ISSUE.template.format(
                       project_files_summary=project_files_summary,
                       original_requirement=state.get("original_requirement") or "（空）",
                       optimized_requirement=state.get("optimized_requirement") or "（空）",
                       risk=main_utils.format_issues_to_str(state["risks"]) if state.get(
                           "risks") else "（空）",
                       unclear_point=main_utils.format_issues_to_str(state["unclear_points"]) if state.get(
                           "unclear_points") else "（空）",
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([
        get_project_info,
        get_project_file_by_id,
        search_project_files,
        search_project_history_conversation,
        product_optimize_issue_output
    ])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         product_optimize_issue_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
