from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.utils import format_utils
from src.enums.requirement_module_status import RequirementModuleStatus


@tool
async def get_completed_requirement_modules(runtime: ToolRuntime) -> str:
    """获取已完成的需求模块列表
    
    AI大模型使用此工具可获取当前项目中已完成的需求模块列表。
    
    **功能说明：**
    从运行时状态中读取并返回已完成的需求模块列表，用于确保新模块设计与已完成模块保持一致性。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        模块序号：xxx
        模块名称：xxx
        模块状态：xxx
        模块描述：xxx
        模块内容：xxx
        
        ----------xxx end----------
        
        如果无已完成模块，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = format_utils.format_state_requirement_modules_to_str(
        runtime.state.get("requirement_modules"),
        RequirementModuleStatus.COMPLETED
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_requirement_module(runtime: ToolRuntime) -> str:
    """获取优化后需求模块内容

    AI大模型使用此工具可获取当前正在设计的需求模块的详细信息。

    **功能说明：**
    从运行时状态中读取并返回当前模块的内容，用于了解上一版优化后的模块状态。

    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 str 类型的字符串，格式为：
        模块序号：xxx
        模块名称：xxx
        模块状态：xxx
        模块描述：xxx
        模块内容：xxx

        如果当前模块不存在，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    module_name = runtime.state.get("metadata", {}).get("module", "")
    result = format_utils.format_current_state_requirement_module_to_str(
        module_name,
        runtime.state.get("requirement_modules"),
        runtime.state.get("requirement_module_content")
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
