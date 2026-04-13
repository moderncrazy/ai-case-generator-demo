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
from src.graphs.system.api import utils
from src.graphs.system.api.schemas import (
    SystemApi,
    OptimizeSystemApiOutput,
    ReviewSystemApiOutput
)


@tool(args_schema=OptimizeSystemApiOutput)
async def optimize_system_api_output(
        message: str,
        system_apis: list[SystemApi],
        runtime: ToolRuntime
) -> Command:
    """输出后端优化系统接口结果

    用于在后端优化系统接口完成后，输出结构化的结果

    Args:
        message: 针对系统接口优化的总结以及给团队成员接下来review的留言
        system_apis: 输出优化后系统接口列表
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeSystemApiOutput(
        message=message,
        system_apis=system_apis
    )
    # 验证 API 模块Id
    if msg := utils.validate_module_ids_str(system_apis, runtime.state["optimized_modules"]):
        error_message = f"接口校验失败：{msg}重新生成"
        logger.warning(
            f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()} 打回:{error_message}")
        return Command(
            update={"private_messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
            goto="optimize_system_api_node"
        )
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            tool_call_message,
            ToolMessage(content=output, tool_call_id=tool_call_id),
            HumanMessage(content=output.message, name="BACKEND")
        ],
        "review_reply_message_id": str(uuid.uuid4()),
        "system_apis": system_apis,
        "system_api_issues": ReducerActionType.RESET,
    })


@tool(args_schema=ReviewSystemApiOutput)
async def review_system_api_output(
        system_api_issues: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出审查系统接口结果

    用于在审查系统接口完成后，输出结构化的结果

    Args:
        system_api_issues: 针对系统接口提出的问题和建议方案
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = ReviewSystemApiOutput(
        system_api_issues=system_api_issues,
    )
    # 发现问题构建回复
    human_messages = []
    human_message_id = runtime.state["review_reply_message_id"]
    if system_api_issues:
        human_messages.append(HumanMessage(
            id=human_message_id,
            name="GROUP_MEMBER",
            content="评审完成，发现问题，请后端根据评审意见修改系统接口。",
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
        "system_api_issues": output.system_api_issues,
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
