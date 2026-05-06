from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.utils import format_utils


@tool
async def get_system_modules(runtime: ToolRuntime) -> str:
    """获取优化后系统模块列表
    
    AI大模型使用此工具可获取经过AI优化后的系统模块列表。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的系统模块列表。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即系统模块列表的格式化内容：
        模块Id：xxx
        模块名称：xxx
        父模块Id：xxx（顶级模块显示"（顶级模块）"）
        模块描述：xxx
        ----------xxx end----------
        
        如果无系统模块，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("system_modules") \
             or runtime.state.get("optimized_modules") \
             or []
    result_str = format_utils.format_state_modules_to_str(result)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result_str)}")
    return result_str


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
