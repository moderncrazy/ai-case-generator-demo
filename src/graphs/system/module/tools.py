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
from src.graphs.system.module import utils
from src.graphs.system.module.schemas import (
    SystemModule,
    OptimizeSystemModuleOutput,
    ReviewSystemModuleOutput,
)


@tool(args_schema=OptimizeSystemModuleOutput)
async def optimize_system_module_output(
        message: str,
        system_modules: list[SystemModule],
        runtime: ToolRuntime
) -> Command:
    """输出架构优化系统模块结果

    用于在架构优化系统模块完成后，输出结构化的结果

    Args:
        message: 针对系统模块优化的总结以及给团队成员接下来review的留言
        system_modules: 输出优化后系统模块列表
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeSystemModuleOutput(
        message=message,
        system_modules=system_modules,
    )
    # 验证模块
    if msg := utils.validate_modules_to_str(system_modules):
        error_message = f"模块校验失败：{msg}重新生成"
        logger.warning(
            f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()} 打回:{error_message}")
        return Command(
            update={
                "private_messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
            goto="optimize_system_module_node"
        )
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            tool_call_message,
            ToolMessage(content=output, tool_call_id=tool_call_id),
            HumanMessage(content=output.message, name="ARCHITECT")
        ],
        "review_reply_message_id": str(uuid.uuid4()),
        "system_modules": system_modules,
        "system_module_issues": ReducerActionType.RESET,
    })


@tool(args_schema=ReviewSystemModuleOutput)
async def review_system_module_output(
        system_module_issues: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出审查系统模块结果

    用于在审查系统模块完成后，输出结构化的结果

    Args:
        system_module_issues: 针对系统模块提出的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = ReviewSystemModuleOutput(
        system_module_issues=system_module_issues,
    )
    # 构建回复 发现问题的优先级高于通过
    human_message_id = runtime.state["review_reply_message_id"]
    if system_module_issues:
        human_message = HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="评审完成，发现问题，请架构根据评审意见修改系统模块。",
            additional_kwargs={"priority": 1}
        )
    else:
        human_message = HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="模块文档评审通过，请整理风险和不确定的问题点反馈给客户。",
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
        "system_module_issues": output.system_module_issues,
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
