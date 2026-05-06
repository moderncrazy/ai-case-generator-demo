from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils


@tool
async def get_system_database_content(runtime: ToolRuntime) -> str:
    """获取优化后数据库内容
    
    AI大模型使用此工具可获取经过AI优化后的数据库内容。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的数据库内容。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即数据库文档全文
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("system_database_content") \
             or runtime.state.get("optimized_database") \
             or const.EMPTY_ZH
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
