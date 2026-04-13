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
from src.graphs.requirement.module import utils
from src.graphs.requirement.module.schemas import (
    OptimizeRequirementModuleOutput,
    ReviewRequirementModuleOutput,
    OptimizeRequirementModuleIssueOutput
)


@tool(args_schema=OptimizeRequirementModuleOutput)
async def optimize_requirement_module_output(
        message: str,
        requirement_module_content: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出产品优化需求模块结果

    用于在产品优化需求模块完成后，输出结构化的结果

    Args:
        message: 针对需求模块优化的总结以及给团队成员接下来review的留言
        requirement_module_content: 输出优化后需求模块内容
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeRequirementModuleOutput(
        message=message,
        requirement_module_content=requirement_module_content,
        risks=risks,
        unclear_points=unclear_points
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            tool_call_message,
            ToolMessage(content=output, tool_call_id=tool_call_id),
            HumanMessage(content=output.message, name="PRODUCT")
        ],
        "review_reply_message_id": str(uuid.uuid4()),
        "requirement_module_content": requirement_module_content,
        "requirement_module_issues": ReducerActionType.RESET,
        "risks": output.risks,
        "unclear_points": output.unclear_points,
    })


@tool(args_schema=ReviewRequirementModuleOutput)
async def review_requirement_module_output(
        requirement_module_issues: list[Issue],
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出审查需求模块结果

    用于在审查需求模块完成后，输出结构化的结果

    Args:
        requirement_module_issues: 针对需求模块提出的问题和建议方案
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = ReviewRequirementModuleOutput(
        requirement_module_issues=requirement_module_issues,
        risks=risks,
        unclear_points=unclear_points
    )
    # 构建回复 发现问题的优先级高于通过
    human_message_id = runtime.state["review_reply_message_id"]
    if requirement_module_issues:
        human_message = HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="评审完成，发现问题，请产品根据评审意见修改需求模块。",
            additional_kwargs={"priority": 1}
        )
    else:
        human_message = HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="需求文档评审通过，请整理风险和不确定的问题点反馈给客户。",
            additional_kwargs={"priority": 0}
        )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 角色:{runtime.state["role"]} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            tool_call_message,
            ToolMessage(content=output, tool_call_id=tool_call_id),
            human_message
        ],
        "requirement_module_issues": output.requirement_module_issues,
        "risks": output.risks,
        "unclear_points": output.unclear_points,
    })


@tool(args_schema=OptimizeRequirementModuleIssueOutput)
async def optimize_requirement_module_issue_output(
        message: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出产品优化需求模块问题结果

    用于在产品优化需求模块问题后，输出结构化的结果

    Args:
        message: 给客户的会话
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeRequirementModuleIssueOutput(
        message=message,
        risks=risks,
        unclear_points=unclear_points
    )
    # 更新需求模块内容
    module_name = runtime.state["metadata"]["module"]
    module_content = runtime.state["requirement_module_content"]
    utils.update_module_content_by_name(module_name, module_content, runtime.state["requirement_modules"])
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": ReducerActionType.RESET,
        "messages": [
            AIMessage(content=output.message, name="PRODUCT")
        ],
        "requirement_modules": runtime.state["requirement_modules"],
        "risks": output.risks,
        "unclear_points": output.unclear_points,
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
