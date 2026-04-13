from loguru import logger
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langchain_core.runnables import RunnableConfig
from langchain.messages import SystemMessage, HumanMessage, AIMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.llms import default_model
from src.graphs import utils as main_utils
from src.graphs.schemas import CustomMessage
from src.graphs.tools import common_tool_list
from src.graphs.system.database.state import State, GroupMemberState
from src.graphs.system.database.tools import (
    optimize_system_database_output,
    review_system_database_output,
)
from src.enums.system_prompt import SystemPrompt
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.repositories.project_repository import project_repository, ProjectUpdate


async def optimize_system_database_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化系统数据库文档节点
    
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
    writer(CustomMessage(message=f"系统数据库文档优化中..."))
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZE_SYSTEM_DATABASE.template.format(
                       original_database=state.get("original_database") or "（空）",
                       system_database_content=state.get("system_database_content")
                                               or state.get("optimized_database") or "（空）",
                       system_database_issue=main_utils.format_issues_to_str(
                           state.get("system_database_issues"))
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_system_database_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_system_database_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result


async def review_system_database_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审系统数据库文档节点

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
            writer(CustomMessage(message="PM评审系统数据库文档中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_DATABASE_PM.template
        case GroupMemberRole.ARCHITECT:
            # 发送自定义消息
            writer(CustomMessage(message="架构师评审系统数据库文档中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_DATABASE_ARCHITECT.template
        case GroupMemberRole.DBA:
            # 发送自定义消息
            writer(CustomMessage(message="数据库专家评审系统数据库文档中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_DATABASE_DBA.template
        case GroupMemberRole.BACKEND:
            # 发送自定义消息
            writer(CustomMessage(message="后端工程师评审系统数据库文档中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_DATABASE_BACKEND.template
        case GroupMemberRole.SRE:
            # 发送自定义消息
            writer(CustomMessage(message="运维工程师评审系统数据库文档中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_DATABASE_SRE.template
        case _:
            # 发送自定义消息
            writer(CustomMessage(message="内部评审系统数据库文档中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_DATABASE_PM.template
    messages = [
                   SystemMessage(content=system_prompt.format(
                       original_database=state.get("original_database") or "（空）",
                       system_database_content=state["system_database_content"],
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, review_system_database_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         review_system_database_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 完成")
    return result


async def review_system_database_aggregator_node(state: State) -> State:
    """评审系统数据库文档聚合节点

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    result = state
    project_id = state["project_id"]
    # 如果评审通过 则回复用户确认数据库
    if not state["system_database_issues"]:
        # 如果原始数据库内容为空 则保存当前版本为原始数据库
        if not state.get("original_database"):
            await project_repository.update(
                project_id,
                ProjectUpdate(database_design=state["system_database_content"])
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 创建原始数据库文档入库")
        # 使用DBA最后一次优化的 message 返回客户
        message = [item.content for item in reversed(state["private_messages"]) if isinstance(item, HumanMessage)][0]
        # 回复客户确认数据库 并赋值
        result = {
            "private_messages": ReducerActionType.RESET,
            "messages": [AIMessage(content=message, name="DBA")],
            "original_database": state.get("original_database") or state["system_database_content"],
            "optimized_database": state["system_database_content"],
        }
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 输出:{gutils.to_json(result)}")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
