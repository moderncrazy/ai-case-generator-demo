import traceback

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
from src.graphs.requirement.module.state import State, GroupMemberState
from src.graphs.requirement.module.tools import (
    optimize_requirement_module_output,
    review_requirement_module_output,
    optimize_requirement_module_issue_output
)
from src.enums.system_prompt import SystemPrompt
from src.enums.group_member_role import GroupMemberRole
from src.enums.requirement_module_status import RequirementModuleStatus


async def optimize_requirement_module_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化需求模块节点
    
    调用 LLM 根据上下文优化当前需求模块内容，
    支持通过工具查询项目历史文档等信息。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含优化后的模块内容）
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    module_name = state["metadata"]["module"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 模块:{module_name}")
    # 发送自定义消息
    writer(CustomMessage(message=f"产品优化{module_name}中..."))
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZED_REQUIREMENT_MODULE.template.format(
                       requirement_outline=state.get("requirement_outline") or "（空）",
                       completed_module=main_utils.format_state_requirement_modules_to_str(
                           state.get("requirement_modules"), RequirementModuleStatus.COMPLETED),
                       current_module=main_utils.format_current_state_requirement_module_to_str(
                           module_name, state.get("requirement_modules"), state.get("requirement_module_content")),
                       requirement_module_issue=main_utils.format_issues_to_str(state.get("requirement_module_issues"))
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_requirement_module_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_requirement_module_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result


async def review_requirement_module_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审需求模块节点
    
    根据成员角色使用不同提示词评审需求模块，
    评审结果包含问题列表、风险点和不明确点。
    
    Args:
        state: 成员评审状态（包含角色标识）
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含评审意见）
    """
    try:
        logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 进入")
    except Exception as e:
        logger.error(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    module_name = state["metadata"]["module"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 模块:{module_name}")
    # 根据角色使用不同提示词
    system_prompt = None
    match state["role"]:
        case GroupMemberRole.PM:
            # 发送自定义消息
            writer(CustomMessage(message="PM评审需求模块中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_MODULE_PM.template
        case GroupMemberRole.ARCHITECT:
            # 发送自定义消息
            writer(CustomMessage(message="架构师评审需求模块中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_MODULE_ARCHITECT.template
        case GroupMemberRole.FRONTEND:
            # 发送自定义消息
            writer(CustomMessage(message="前端工程师评审需求模块中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_MODULE_FRONTEND.template
        case GroupMemberRole.BACKEND:
            # 发送自定义消息
            writer(CustomMessage(message="后端工程师评审需求模块中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_MODULE_BACKEND.template
        case GroupMemberRole.TEST:
            # 发送自定义消息
            writer(CustomMessage(message="测试工程师评审需求模块中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_MODULE_TEST.template
        case _:
            # 发送自定义消息
            writer(CustomMessage(message="内部评审需求模块中..."))
            system_prompt = SystemPrompt.REVIEW_REQUIREMENT_MODULE_PM.template
    messages = [
                   SystemMessage(content=system_prompt.format(
                       requirement_outline=state.get("requirement_outline") or "（空）",
                       completed_module=main_utils.format_state_requirement_modules_to_str(
                           state.get("requirement_modules"), RequirementModuleStatus.COMPLETED),
                       current_module=main_utils.format_current_state_requirement_module_to_str(
                           module_name, state.get("requirement_modules"), state.get("requirement_module_content")),
                       risk=main_utils.format_issues_to_str(state.get("risks")),
                       unclear_point=main_utils.format_issues_to_str(state.get("unclear_points")),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    metadata = {"role": state["role"]}
    llm_with_tool = default_model.bind_tools([*common_tool_list, review_requirement_module_output])
    try:
        result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                             review_requirement_module_output,
                                                             messages_key="private_messages", metadata=metadata)
    except Exception as e:
        # 如果异常则跳过这个review 避免影响整个流程
        result = state
        logger.error(
            f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 异常:{str(e)}\n异常栈:{traceback.format_exc()}")

    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 完成")
    return result


async def optimize_requirement_module_issue_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """整理需求模块问题节点
    
    收集汇总各角色评审意见，整理出风险点和不明确点，
    最终将优化后的需求模块内容保存到数据库。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含最终风险点和不明确点）
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    # 发送自定义消息
    writer(CustomMessage(message="需求模块问题整理中..."))
    project_id = state["project_id"]
    module_name = state["metadata"]["module"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 模块:{module_name}")
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZED_REQUIREMENT_MODULE_ISSUE.template.format(
                       requirement_outline=state.get("requirement_outline") or "（空）",
                       completed_module=main_utils.format_state_requirement_modules_to_str(
                           state.get("requirement_modules"), RequirementModuleStatus.COMPLETED),
                       current_module=main_utils.format_current_state_requirement_module_to_str(
                           module_name, state.get("requirement_modules"), state.get("requirement_module_content")),
                       risk=main_utils.format_issues_to_str(state.get("risks")),
                       unclear_point=main_utils.format_issues_to_str(state.get("unclear_points")),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_requirement_module_issue_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_requirement_module_issue_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
