from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils


@tool
def get_optimization_plan_content(runtime: ToolRuntime) -> str:
    """获取优化方案内容
    
    从运行时状态中读取优化方案，供优化的agent根据此方案优化文档。
    方案包含方案逻辑链路、具体步骤
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        AI生成的具体优化方案如下：
        
        方案逻辑链路：xxx
        方案具体步骤：xxx
        
        如果无优化方案，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimization_plan_content")
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
