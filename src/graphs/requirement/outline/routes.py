from loguru import logger
from typing import Literal
from langgraph.graph import END
from langchain.messages import AIMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.requirement.outline.state import State


def optimize_requirement_outline_tool_router(state: State) -> Literal["optimize_requirement_outline_tool_node", END]:
    """需求大纲优化工具调用路由
    
    判断最后一条消息是否为工具调用，
    决定继续调用工具或结束子图返回主图。
    
    Args:
        state: 状态
        
    Returns:
        目标节点名称或 END
    """
    destination_node = END
    if (isinstance(state["private_messages"], list)
            and state["private_messages"]
            and isinstance(state["private_messages"][-1], AIMessage)
            and state["private_messages"][-1].tool_calls):
        destination_node = "optimize_requirement_outline_tool_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node
