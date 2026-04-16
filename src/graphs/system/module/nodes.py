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
from src.graphs.system.module.state import State, GroupMemberState
from src.graphs.system.module.tools import (
    optimize_system_module_output,
    review_system_module_output,
)
from src.enums.system_prompt import SystemPrompt
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.repositories.module_repository import module_repository, ModuleUpdate


async def optimize_system_module_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化系统模块节点
    
    调用 LLM 根据上下文优化系统模块列表，
    支持通过工具查询项目历史文档等信息。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含优化后的模块列表）
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    # 发送自定义消息
    writer(CustomMessage(message=f"系统模块优化中..."))
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZE_SYSTEM_MODULE.template.format(
                       original_module=main_utils.format_state_modules_to_str(state.get("original_modules")),
                       system_module=main_utils.format_state_modules_to_str(
                           state.get("system_modules") or state.get("optimized_modules")),
                       system_module_issue=main_utils.format_issues_to_str(state.get("system_module_issues"))
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_system_module_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_system_module_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result


async def review_system_module_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审系统模块节点
    
    根据成员角色使用不同提示词评审系统模块，
    评审结果包含问题列表。
    
    Args:
        state: 成员评审状态（包含角色标识）
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含评审意见）
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    # 根据角色使用不同提示词
    system_prompt = None
    match state["role"]:
        case GroupMemberRole.PM:
            # 发送自定义消息
            writer(CustomMessage(message="PM评审系统模块中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_MODULE_PM.template
        case GroupMemberRole.ARCHITECT:
            # 发送自定义消息
            writer(CustomMessage(message="架构师评审系统模块中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_MODULE_ARCHITECT.template
        case GroupMemberRole.FRONTEND:
            # 发送自定义消息
            writer(CustomMessage(message="前端工程师评审系统模块中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_MODULE_FRONTEND.template
        case GroupMemberRole.BACKEND:
            # 发送自定义消息
            writer(CustomMessage(message="后端工程师评审系统模块中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_MODULE_BACKEND.template
        case GroupMemberRole.SRE:
            # 发送自定义消息
            writer(CustomMessage(message="运维工程师评审系统模块中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_MODULE_SRE.template
        case _:
            # 发送自定义消息
            writer(CustomMessage(message="内部评审系统模块中..."))
            system_prompt = SystemPrompt.REVIEW_SYSTEM_MODULE_PM.template
    messages = [
                   SystemMessage(content=system_prompt.format(
                       original_module=main_utils.format_state_modules_to_str(state.get("original_modules")),
                       system_module=main_utils.format_state_modules_to_str(state["system_modules"]),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    metadata = {"role": state["role"]}
    llm_with_tool = default_model.bind_tools([*common_tool_list, review_system_module_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         review_system_module_output,
                                                         messages_key="private_messages", metadata=metadata)
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 完成")
    return result


async def review_system_module_aggregator_node(state: State) -> State:
    """评审系统模块聚合节点
    
    汇总各角色评审意见，判断是否需要返工。
    若评审通过，使用架构师最后一次优化的消息返回客户。
    
    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    result = state
    project_id = state["project_id"]
    # 如果评审通过 则回复用户确认模块
    if not state["system_module_issues"]:
        # 如果原始模块内容为空 则保存当前版本为原始模块
        if not state.get("original_modules"):
            await module_repository.bulk_update(
                project_id,
                [ModuleUpdate(**item) for item in state["system_modules"]]
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 创建原始模块入库")
        # 使用架构最后一次优化的 message 返回客户
        message = [item.content for item in reversed(state["private_messages"]) if isinstance(item, HumanMessage)][0]
        # 回复客户确认模块 并赋值
        result = {
            "private_messages": ReducerActionType.RESET,
            "messages": [AIMessage(content=message, name="ARCHITECT")],
            "original_modules": state.get("original_modules") or state["system_modules"],
            "optimized_modules": state["system_modules"],
        }
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 输出:{gutils.to_json(result)}")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
