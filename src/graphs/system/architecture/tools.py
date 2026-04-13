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
from src.graphs.system.architecture.schemas import (
    OptimizeSystemArchitectureOutput,
    ReviewSystemArchitectureOutput,
    OptimizeSystemArchitectureIssueOutput
)
from src.repositories.project_repository import project_repository, ProjectUpdate


@tool(args_schema=OptimizeSystemArchitectureOutput)
async def optimize_system_architecture_output(
        message: str,
        system_architecture_content: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出架构优化系统架构结果

    用于在架构优化系统架构完成后，输出结构化的结果

    Args:
        message: 针对系统架构优化的总结以及给团队成员接下来review的留言
        system_architecture_content: 输出优化后系统架构内容
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeSystemArchitectureOutput(
        message=message,
        system_architecture_content=system_architecture_content,
        risks=risks,
        unclear_points=unclear_points
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            tool_call_message,
            ToolMessage(content=output, tool_call_id=tool_call_id),
            HumanMessage(content=output.message, name="ARCHITECT")
        ],
        "review_reply_message_id": str(uuid.uuid4()),
        "system_architecture_content": system_architecture_content,
        "system_architecture_issues": ReducerActionType.RESET,
        "risks": output.risks,
        "unclear_points": output.unclear_points,
    })


@tool(args_schema=ReviewSystemArchitectureOutput)
async def review_system_architecture_output(
        system_architecture_issues: list[Issue],
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出审查系统架构结果

    用于在审查系统架构完成后，输出结构化的结果

    Args:
        system_architecture_issues: 针对系统架构提出的问题和建议方案
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = ReviewSystemArchitectureOutput(
        system_architecture_issues=system_architecture_issues,
        risks=risks,
        unclear_points=unclear_points
    )
    # 构建回复 发现问题的优先级高于通过
    human_message_id = runtime.state["review_reply_message_id"]
    if system_architecture_issues:
        human_message = HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="评审完成，发现问题，请架构根据评审意见修改系统架构。",
            additional_kwargs={"priority": 1}
        )
    else:
        human_message = HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="架构文档评审通过，请整理风险和不确定的问题点反馈给客户。",
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
        "system_architecture_issues": output.system_architecture_issues,
        "risks": output.risks,
        "unclear_points": output.unclear_points,
    })


@tool(args_schema=OptimizeSystemArchitectureIssueOutput)
async def optimize_system_architecture_issue_output(
        message: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出架构优化系统架构问题结果

    用于在架构优化系统架构问题后，输出结构化的结果

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
    output = OptimizeSystemArchitectureIssueOutput(
        message=message,
        risks=risks,
        unclear_points=unclear_points
    )
    # 如果原始架构内容为空 则保存当前版本为原始架构
    if not runtime.state.get("original_architecture"):
        await project_repository.update(
            runtime.state["project_id"],
            ProjectUpdate(architecture_design=runtime.state["system_architecture_content"])
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 创建原始架构入库")
    # 更新系统架构内容
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": ReducerActionType.RESET,
        "messages": [
            AIMessage(content=output.message, name="ARCHITECT")
        ],
        "original_architecture": runtime.state.get("original_architecture")
                                 or runtime.state["system_architecture_content"],
        "optimized_architecture": runtime.state["system_architecture_content"],
        "risks": output.risks,
        "unclear_points": output.unclear_points,
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
