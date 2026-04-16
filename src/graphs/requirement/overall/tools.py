import uuid
from loguru import logger
from langgraph.types import Command
from langchain.tools import tool, BaseTool, ToolRuntime
from langchain.messages import AIMessage, ToolMessage, HumanMessage, ToolCall

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.reducer_action_type import ReducerActionType
from src.graphs import utils as main_utils
from src.graphs.schemas import Issue
from src.graphs.requirement.overall.schemas import (
    OptimizeRequirementOverallOutput,
    ReviewRequirementOverallOutput,
    OptimizeRequirementOverallIssueOutput
)
from src.repositories.project_repository import project_repository, ProjectUpdate


@tool(args_schema=OptimizeRequirementOverallOutput)
async def optimize_requirement_overall_output(
        message: str,
        requirement_overall_content: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出产品优化需求文档结果
    
    在产品优化需求文档完成后调用，输出结构化的优化结果。
    更新状态中的文档内容，并清空之前的问题记录，为评审做准备。
    
    Args:
        message: 针对需求文档优化的总结以及给团队成员接下来review的留言
        requirement_overall_content: 输出优化后需求文档内容
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeRequirementOverallOutput(
        message=message,
        requirement_overall_content=requirement_overall_content,
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
        "requirement_overall_content": output.requirement_overall_content,
        "requirement_issues": ReducerActionType.RESET,
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool(args_schema=ReviewRequirementOverallOutput)
async def review_requirement_overall_output(
        requirement_overall_issues: list[Issue],
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出评审需求文档结果
    
    各角色评审完成后调用，输出结构化的评审意见。
    根据是否发现问题设置不同的回复优先级。
    
    Args:
        requirement_overall_issues: 针对需求文档提出的问题和建议方案
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = ReviewRequirementOverallOutput(
        requirement_overall_issues=requirement_overall_issues,
        risks=risks,
        unclear_points=unclear_points
    )
    # 构建回复 发现问题的优先级高于通过
    human_message_id = runtime.state["review_reply_message_id"]
    if requirement_overall_issues:
        human_message = HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="评审完成，发现问题，请产品根据评审意见修改需求文档。",
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
        "requirement_overall_issues": [item.model_dump() for item in (output.requirement_overall_issues or [])],
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool(args_schema=OptimizeRequirementOverallIssueOutput)
async def optimize_requirement_overall_issue_output(
        message: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """整理输出需求文档问题结果
    
    评审完成后汇总问题，输出结构化的风险点和不明确点，
    并将最终需求文档保存到数据库。
    
    Args:
        message: 给客户的会话
        risks: 给客户提出的风险和建议方案
        unclear_points: 需求中不明确的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态并保存到数据库
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeRequirementOverallIssueOutput(
        message=message,
        risks=risks,
        unclear_points=unclear_points
    )
    # 如果原始需求内容为空 则保存当前版本为原始需求
    if not runtime.state.get("original_requirement"):
        await project_repository.update(
            runtime.state["project_id"],
            ProjectUpdate(requirement_overall_design=runtime.state["requirement_overall_content"])
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 创建原始需求入库")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": ReducerActionType.RESET,
        "messages": [
            AIMessage(content=output.message, name="PRODUCT")
        ],
        "original_requirement": runtime.state.get("original_requirement")
                                or runtime.state["requirement_overall_content"],
        "optimized_requirement": runtime.state["requirement_overall_content"],
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
