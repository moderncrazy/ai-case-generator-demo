from loguru import logger
from typing import Literal
from langgraph.graph import END
from langchain_core.messages import AIMessage

from src.graphs.state import State
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.pm_next_step import PMNextStep


def load_project_router(state: State) -> Literal["load_project_node", "understand_image_node", "product_manager_node"]:
    """决定是否走load_project_node节点"""
    if not state.get("project_name"):
        logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:load_project_node")
        return "load_project_node"
    if state.get("new_file_list"):
        logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:understand_image_node")
        return "understand_image_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:product_manager_node")
    return "product_manager_node"


def understand_image_router(state: State) -> Literal["understand_image_node", "product_manager_node"]:
    """决定是否走understand_image_node节点"""
    if state.get("new_file_list"):
        logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:understand_image_node")
        return "understand_image_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:product_manager_node")
    return "product_manager_node"


def product_manager_tool_router(state: State) -> Literal["product_manager_tool_node", "requirement_node", END]:
    # 如果不是最终决策则放行
    if isinstance(state["messages"][-1], AIMessage) and state["messages"][-1].tool_calls:
        logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:product_manager_tool_node")
        return "product_manager_tool_node"
    else:
        match state["pm_next_step"]:
            case PMNextStep.REQUIREMENT_DESIGN:
                logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:requirement_node")
                return "requirement_node"
            case _:
                logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:{END}")
                return END
