from loguru import logger
from langgraph.runtime import Runtime
from langchain.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.tools import tool_list as ctool_list
from src.graphs.system.module.state import State, GroupMemberState
from src.graphs.common.utils import workflow_node_utils, utils as cutils
from src.graphs.system.module.tools import (
    common_tool_list,
    optimize_system_module_output,
    review_system_module_output,
    review_optimization_system_module_plan_output,
    generate_optimization_system_module_plan_output,
)
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.conversation_message_type import ConversationMessageType
from src.repositories.module_repository import module_repository, ModuleUpdate


async def generate_optimization_system_module_plan_node(state: State, runtime: Runtime,
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
        generate_optimization_system_module_plan_output,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_optimization_system_module_plan_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
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
        review_optimization_system_module_plan_output,
        GroupMemberRole.ARCHITECT,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


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
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message("架构优化系统模块中", GroupMemberRole.ARCHITECT)
    tool_list = [*ctool_list, *common_tool_list]
    result = await workflow_node_utils.optimize_doc(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.ARCHITECT,
        optimize_system_module_output,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
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
    role = state["role"]
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 进入")
    # 根据角色使用不同提示词
    cutils.send_custom_message(f"{role}评审系统模块中...", role)
    tool_list = [*ctool_list, *common_tool_list]
    result = await workflow_node_utils.review_optimization_doc(
        state,
        runtime,
        config,
        tool_list,
        review_system_module_output,
        GroupMemberRole.ARCHITECT
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 完成")
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
    result = state
    project_id = state["project_id"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 如果评审通过 则回复用户确认模块
    if not state["system_module_issues"]:
        # 如果原始模块内容为空 则保存当前版本为原始模块
        if not state.get("original_modules"):
            await module_repository.bulk_update(
                project_id,
                [ModuleUpdate(**item) for item in state["system_modules"]]
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始模块入库")
        cutils.send_custom_message(
            "系统模块已更新，快来看看吧！", GroupMemberRole.ARCHITECT, ConversationMessageType.NOTIFY)
        # 使用架构最后一次优化的 message 返回客户
        message = workflow_node_utils.get_latest_role_message(GroupMemberRole.ARCHITECT, state["private_messages"])
        # 回复客户确认模块 并赋值
        result = {
            "private_messages": ReducerActionType.RESET,
            "messages": [AIMessage(content=message.content, name=GroupMemberRole.ARCHITECT.value)],
            "original_modules": state.get("original_modules") or state["system_modules"],
            "optimized_modules": state["system_modules"],
        }
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result
