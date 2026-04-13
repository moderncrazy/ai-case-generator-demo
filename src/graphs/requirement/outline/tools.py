import uuid
import inspect
from loguru import logger
from langgraph.types import Command
from langchain.tools import tool, BaseTool, ToolRuntime
from langchain.messages import AIMessage, ToolMessage, HumanMessage, ToolCall

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs import utils as main_utils
from src.graphs.requirement.outline import utils
from src.graphs.schemas import StateRequirementModule
from src.enums.reducer_action_type import ReducerActionType
from src.enums.requirement_module_status import RequirementModuleStatus
from src.graphs.requirement.outline.schemas import RequirementModuleCreate, OptimizeRequirementOutlineOutput


@tool(args_schema=OptimizeRequirementOutlineOutput)
async def optimize_requirement_outline_output(
        message: str,
        requirement_outline: str,
        requirement_modules: list[RequirementModuleCreate],
        runtime: ToolRuntime
) -> Command:
    """输出产品优化需求大纲结果

    用于在产品优化需求大纲完成后，输出结构化的结果

    Args:
        message: 针对需求大纲优化的总结以及给客户的回复
        requirement_outline: 输出优化后需求大纲
        requirement_modules: 输出需求模块列表
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = main_utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = OptimizeRequirementOutlineOutput(
        message=message,
        requirement_outline=requirement_outline,
        requirement_modules=requirement_modules
    )
    # 验证需求模块是否重复
    error_message = utils.validate_requirement_modules(requirement_modules)
    if error_message:
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 需求模块验证失败打回:{error_message}")
        # 打回修复
        return Command(
            update={
                "messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
            goto="optimize_requirement_outline_node"
        )
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图工具:{gutils.get_func_name()} 输出:{output.model_dump_json()}")
    return Command(update={
        "messages": [
            AIMessage(content=output.message, name="PRODUCT")
        ],
        "private_messages": ReducerActionType.RESET,
        "requirement_outline": output.requirement_outline,
        # 默认设置状态为 pending 并 排序
        "requirement_modules": sorted(
            [StateRequirementModule(status=RequirementModuleStatus.PENDING, **item.model_dump())
             for item in output.requirement_modules],
            key=lambda m: m.order
        ),
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
