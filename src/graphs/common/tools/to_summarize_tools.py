from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.utils import utils as cutils


@tool
async def get_risks(runtime: ToolRuntime) -> str:
    """获取风险点列表

    AI大模型使用此工具可获取当前项目已识别的风险点列表。

    **功能说明：**
    从运行时状态中读取并返回已识别的风险点，用于了解项目潜在的风险。

    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 str 类型的字符串，格式为：
        问题：xxx
        建议方案：xxx

        如果无风险点，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = cutils.format_issues_to_str(runtime.state.get("private_risks"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_unclear_points(runtime: ToolRuntime) -> str:
    """获取不明确问题列表

    AI大模型使用此工具可获取当前项目待澄清的不明确问题列表。

    **功能说明：**
    从运行时状态中读取并返回待澄清的不明确问题，用于了解需要客户明确的事项。

    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 str 类型的字符串，格式为：
        问题：xxx
        建议方案：xxx

        如果无不明确问题，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = cutils.format_issues_to_str(runtime.state.get("private_unclear_points"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
