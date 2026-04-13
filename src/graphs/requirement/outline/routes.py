from loguru import logger
from typing import Literal
from langgraph.graph import END
from langchain.messages import AIMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.requirement.outline.state import State


def optimize_requirement_outline_tool_router(state: State) -> Literal["optimize_requirement_outline_node", END]:
    """决定是调用 tool 或 返回主图"""
    destination_node = END
    if (isinstance(state["private_messages"], list)
            and isinstance(state["private_messages"][-1], AIMessage)
            and state["private_messages"][-1].tool_calls):
        destination_node = "optimize_requirement_outline_tool_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node
