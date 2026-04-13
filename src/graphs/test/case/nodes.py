from loguru import logger
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langchain_core.runnables import RunnableConfig
from langchain.messages import SystemMessage, AIMessage, HumanMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.llms import default_model
from src.graphs import utils as main_utils
from src.graphs.schemas import CustomMessage
from src.graphs.tools import common_tool_list
from src.graphs.test.case.state import State, GroupMemberState
from src.graphs.test.case.tools import (
    optimize_test_case_output,
    review_test_case_output
)
from src.enums.system_prompt import SystemPrompt
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.repositories.test_case_repository import test_case_repository, TestCaseUpdate


async def optimize_test_case_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化测试用例节点
    
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
    writer(CustomMessage(message=f"测试用例优化中..."))
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZE_TEST_CASE.template.format(
                       original_test_case=main_utils.format_state_test_cases_to_str(state.get("original_test_cases")),
                       test_case=main_utils.format_state_test_cases_to_str(
                           state.get("test_cases") or state.get("optimized_test_cases")),
                       test_case_issue=main_utils.format_issues_to_str(state.get("test_case_issues"))
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_test_case_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_test_case_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result


async def review_test_case_node(state: GroupMemberState, runtime: Runtime, config: RunnableConfig) -> State:
    """评审测试用例节点

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
            writer(CustomMessage(message="PM评审测试用例中..."))
            system_prompt = SystemPrompt.REVIEW_TEST_CASE_PM.template
        case GroupMemberRole.ARCHITECT:
            # 发送自定义消息
            writer(CustomMessage(message="架构师评审测试用例中..."))
            system_prompt = SystemPrompt.REVIEW_TEST_CASE_ARCHITECT.template
        case GroupMemberRole.FRONTEND:
            # 发送自定义消息
            writer(CustomMessage(message="前端工程师评审测试用例中..."))
            system_prompt = SystemPrompt.REVIEW_TEST_CASE_FRONTEND.template
        case GroupMemberRole.BACKEND:
            # 发送自定义消息
            writer(CustomMessage(message="后端工程师评审测试用例中..."))
            system_prompt = SystemPrompt.REVIEW_TEST_CASE_BACKEND.template
        case GroupMemberRole.TEST:
            # 发送自定义消息
            writer(CustomMessage(message="测试工程师评审测试用例中..."))
            system_prompt = SystemPrompt.REVIEW_TEST_CASE_TEST.template
        case _:
            # 发送自定义消息
            writer(CustomMessage(message="内部评审测试用例中..."))
            system_prompt = SystemPrompt.REVIEW_TEST_CASE_PM.template
    messages = [
                   SystemMessage(content=system_prompt.format(
                       original_test_case=main_utils.format_state_test_cases_to_str(state.get("original_test_cases")),
                       test_case=main_utils.format_state_test_cases_to_str(state["test_cases"]),
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, review_test_case_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         review_test_case_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 角色:{state["role"]} 完成")
    return result


async def review_test_case_aggregator_node(state: State) -> State:
    """评审测试用例聚合节点

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    result = state
    project_id = state["project_id"]
    # 如果评审通过 则回复用户确认测试用例
    if not state["test_case_issues"]:
        # 如果原始测试用例内容为空 则保存当前版本为原始测试用例
        if not state.get("original_test_cases"):
            await test_case_repository.bulk_update(project_id, [TestCaseUpdate(**item) for item in state["test_cases"]])
            logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 创建原始测试用例入库")
        # 使用测试最后一次优化的 message 返回客户
        message = [item.content for item in reversed(state["private_messages"]) if isinstance(item, HumanMessage)][0]
        # 回复客户确认测试用例 并赋值
        result = {
            "private_messages": ReducerActionType.RESET,
            "messages": [AIMessage(content=message, name="TEST")],
            "original_cases": state.get("original_test_cases") or state["test_cases"],
            "optimized_modules": state["test_cases"],
        }
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 输出:{gutils.to_json(result)}")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
