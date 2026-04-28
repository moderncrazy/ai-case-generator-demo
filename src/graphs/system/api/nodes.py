from loguru import logger
from langgraph.runtime import Runtime
from langchain.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.context import trans_id_ctx
from src.graphs.common.tools import optimization_plan_tools, review_issue_tools, tools as ctools
from src.graphs.common.utils import workflow_node_utils, repository_utils, utils as cutils
from src.graphs.system.api.state import State, GroupMemberState
from src.graphs.system.api.tools import (
    common_tool_list,
    review_system_api_output,
    optimize_system_api_output,
    review_optimization_system_api_plan_output,
    generate_optimization_system_api_plan_output,
)
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.conversation_message_type import ConversationMessageType

tool_list = optimization_plan_tools.tool_list + review_issue_tools.tool_list + ctools.tool_list + common_tool_list


async def generate_optimization_system_api_plan_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """生成优化方案节点

    调用 LLM 根据上下文生成优化系统接口的方案
    支持通过工具查询项目历史文档等信息

    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含生成的系统接口方案）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    result = await workflow_node_utils.generate_optimization_plan(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.BACKEND,
        generate_optimization_system_api_plan_output,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_optimization_system_api_plan_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """审核优化方案节点

    调用 LLM 根据上下文审核优化系统接口的方案
    支持通过工具查询项目历史文档等信息

    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含审核优化方案结果）
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
        review_optimization_system_api_plan_output,
        GroupMemberRole.BACKEND,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def optimize_system_api_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化系统接口节点
    
    调用 LLM 根据上下文优化系统接口列表，
    支持通过工具查询项目历史文档等信息。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含优化后的接口列表）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message("后端优化系统接口中...", GroupMemberRole.BACKEND)
    result = await workflow_node_utils.optimize_doc(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.BACKEND,
        optimize_system_api_output,
        GroupMemberRole.GROUP_MEMBER if state.get("review_issues") else GroupMemberRole.PM,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_system_api_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审系统接口节点
    
    根据成员角色使用不同提示词评审系统接口，
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
    cutils.send_custom_message(f"{role.get_name_zh()}评审系统接口中...", role)
    result = await workflow_node_utils.review_optimization_doc(
        state,
        runtime,
        config,
        tool_list,
        review_system_api_output,
        GroupMemberRole.BACKEND
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 完成")
    return result


async def review_system_api_aggregator_node(state: State) -> State:
    """评审系统接口聚合节点
    
    汇总各角色评审意见，判断是否需要返工。
    若评审通过，使用后端最后一次优化的消息返回客户。
    
    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    result = state
    project_id = state["project_id"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 如果评审通过 则回复用户确认接口
    if not state["review_issues"]:
        # 如果原始接口内容为空 则保存当前版本为原始接口
        if not state.get("original_apis"):
            await repository_utils.bulk_update_by_state_apis(project_id, state["system_apis"])
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始接口入库")
        cutils.send_custom_message(
            "接口文档已更新，快来看看吧！", GroupMemberRole.BACKEND, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.SYSTEM_API.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 使用后端最后一次优化的 message 返回客户
        message = workflow_node_utils.get_latest_role_message(GroupMemberRole.BACKEND, state["private_messages"])
        # 回复客户确认接口 并赋值
        result = {
            "private_messages": ReducerActionType.RESET,
            "messages": [AIMessage(content=message.content, name=GroupMemberRole.BACKEND.value)],
            "original_apis": state.get("original_apis") or state["system_apis"],
            "optimized_modules": state["system_apis"],
        }
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result
