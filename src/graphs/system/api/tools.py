from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.utils import format_utils


@tool
async def get_system_apis(runtime: ToolRuntime) -> str:
    """获取优化后系统接口列表
    
    AI大模型使用此工具可获取经过AI优化后的系统接口列表。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的系统接口列表。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        接口序号：xxx
        模块ID：xxx
        接口名称：xxx
        请求方法：xxx
        请求路径：xxx
        接口描述：xxx
        请求头参数：xxx
        URL参数：xxx
        请求体参数：xxx
        响应格式：xxx
        
        ----------xxx end----------
        
        如果无接口，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    apis = runtime.state.get("system_apis") or runtime.state.get("optimized_apis")
    result = format_utils.format_state_apis_to_str(apis) if apis else const.EMPTY_ZH
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
