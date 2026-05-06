from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils


@tool
async def get_requirement_overall_content(runtime: ToolRuntime) -> str:
    """获取优化后需求文档内容
    
    AI大模型使用此工具可获取经过AI优化后的需求文档内容。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的需求文档。
    优化内容包括：补全不明确点、修正逻辑、补充细节等。
    
    获取顺序：
    1. 优先取 `requirement_overall_content`（经过优化的内容）
    2. 其次取 `optimized_requirement`（优化后的需求）
    3. 如果都为空，返回"（空）"
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即优化后的需求文档全文
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("requirement_overall_content") \
             or runtime.state.get("optimized_requirement") \
             or const.EMPTY_ZH
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
