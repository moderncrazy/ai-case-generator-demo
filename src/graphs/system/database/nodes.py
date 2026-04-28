from loguru import logger
from langgraph.runtime import Runtime
from langchain.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.tools import optimization_plan_tools, review_issue_tools, tools as ctools
from src.graphs.common.utils import workflow_node_utils, utils as cutils
from src.graphs.system.database.state import State, GroupMemberState
from src.graphs.system.database.tools import (
    common_tool_list,
    optimize_system_database_output,
    review_system_database_output,
    review_optimization_system_database_plan_output,
    generate_optimization_system_database_plan_output,
)
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.conversation_message_type import ConversationMessageType
from src.repositories.project_repository import project_repository, ProjectUpdate

tool_list = optimization_plan_tools.tool_list + review_issue_tools.tool_list + ctools.tool_list + common_tool_list


async def generate_optimization_system_database_plan_node(state: State, runtime: Runtime,
                                                          config: RunnableConfig) -> State:
    """生成优化方案节点"""
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    result = await workflow_node_utils.generate_optimization_plan(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.DBA,
        generate_optimization_system_database_plan_output,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_optimization_system_database_plan_node(state: State, runtime: Runtime,
                                                        config: RunnableConfig) -> State:
    """审核优化方案节点"""
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    result = await workflow_node_utils.review_optimization_plan(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.PM,
        review_optimization_system_database_plan_output,
        GroupMemberRole.DBA,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def optimize_system_database_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化系统数据库文档节点
    
    调用 LLM 根据上下文优化系统数据库文档内容，
    支持通过工具查询项目历史文档等信息。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含优化后的数据库文档）
    """
    project_id = state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message("DBA优化数据库文档中...", GroupMemberRole.DBA)
    result = await workflow_node_utils.optimize_doc(
        state,
        runtime,
        config,
        tool_list,
        GroupMemberRole.DBA,
        optimize_system_database_output,
        GroupMemberRole.GROUP_MEMBER if state.get("review_issues") else GroupMemberRole.PM,
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_system_database_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审系统数据库文档节点
    
    根据成员角色使用不同提示词评审系统数据库文档，
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
    cutils.send_custom_message(f"{role.get_name_zh()}评审数据库文档中...", role)
    result = await workflow_node_utils.review_optimization_doc(
        state,
        runtime,
        config,
        tool_list,
        review_system_database_output,
        GroupMemberRole.DBA
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 完成")
    return result


async def review_system_database_aggregator_node(state: State) -> State:
    """评审系统数据库文档聚合节点
    
    汇总各角色评审意见，判断是否需要返工。
    若评审通过，使用 DBA 最后一次优化的消息返回客户。
    
    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    result = state
    project_id = state["project_id"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 如果评审通过 则回复用户确认数据库
    if not state["review_issues"]:
        # 如果原始数据库内容为空 则保存当前版本为原始数据库
        if not state.get("original_database"):
            await project_repository.update(
                project_id,
                ProjectUpdate(database_design=state["system_database_content"])
            )
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始数据库文档入库")
        cutils.send_custom_message(
            "数据库文档已更新，快来看看吧！", GroupMemberRole.DBA, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.SYSTEM_DATABASE.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 使用DBA最后一次优化的 message 返回客户
        message = workflow_node_utils.get_latest_role_message(GroupMemberRole.DBA, state["private_messages"])
        # 回复客户确认数据库 并赋值
        result = {
            "private_messages": ReducerActionType.RESET,
            "messages": [AIMessage(content=message.content, name=GroupMemberRole.DBA.value)],
            "original_database": state.get("original_database") or state["system_database_content"],
            "optimized_database": state["system_database_content"],
        }
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result
