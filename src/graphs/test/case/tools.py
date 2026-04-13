import uuid
import inspect
from loguru import logger
from langgraph.types import Command
from langchain.tools import tool, BaseTool, ToolRuntime
from langchain.messages import AIMessage, ToolMessage, HumanMessage, ToolCall

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.reducer_action_type import ReducerActionType
from src.graphs.schemas import Issue
from src.graphs import utils as main_utils
from src.graphs.test.case import utils
from src.graphs.test.case.schemas import (
    TestCase,
    OptimizeTestCaseOutput,
    ReviewTestCaseOutput
)


@tool(args_schema=OptimizeTestCaseOutput)
async def optimize_test_case_output(
        message: str,
        test_cases: list[TestCase],
        runtime: ToolRuntime
) -> Command:
    """输出测试优化测试用例结果

    用于在测试优化测试用例完成后，输出结构化的结果

    Args:
        message: 针对测试用例优化的总结以及给团队成员接下来review的留言
        test_cases: 输出优化后测试用例列表
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeTestCaseOutput(
        message=message,
        test_cases=test_cases
    )
    # 验证 API 模块Id
    if msg := utils.validate_module_ids_str(test_cases, runtime.state["optimized_modules"]):
        error_message = f"测试用例校验失败：{msg}重新生成"
        logger.warning(
            f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()} 打回:{error_message}")
        return Command(
            update={
                "private_messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
            goto="optimize_test_case_node"
        )
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            tool_call_message,
            ToolMessage(content=output, tool_call_id=tool_call_id),
            HumanMessage(content=output.message, name="TEST")
        ],
        "review_reply_message_id": str(uuid.uuid4()),
        "test_cases": test_cases,
        "test_case_issues": ReducerActionType.RESET,
    })


@tool(args_schema=ReviewTestCaseOutput)
async def review_test_case_output(
        test_case_issues: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出审查测试用例结果

    用于在审查测试用例完成后，输出结构化的结果

    Args:
        test_case_issues: 针对测试用例提出的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = ReviewTestCaseOutput(
        test_case_issues=test_case_issues,
    )
    # 发现问题构建回复
    human_messages = []
    human_message_id = runtime.state["review_reply_message_id"]
    if test_case_issues:
        human_messages.append(HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="评审完成，发现问题，请测试根据评审意见修改测试用例。",
            additional_kwargs={"priority": 1}
        ))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 角色:{runtime.state["role"]} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            tool_call_message,
            ToolMessage(content=output, tool_call_id=tool_call_id),
            *human_messages
        ],
        "test_case_issues": output.test_case_issues,
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
