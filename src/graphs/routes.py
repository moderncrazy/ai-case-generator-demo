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
    destination_node = "product_manager_node"
    if not state.get("project_name"):
        destination_node = "load_project_node"
    if state.get("new_file_list"):
        destination_node = "understand_image_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node


def understand_image_router(state: State) -> Literal["understand_image_node", "product_manager_node"]:
    """决定是否走understand_image_node节点"""
    destination_node = "product_manager_node"
    if state.get("new_file_list"):
        destination_node = "understand_image_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node


def product_manager_tool_router(state: State) -> Literal[
    "product_manager_tool_node", "requirement_outline_node", "requirement_module_node", "requirement_overall_node",
    "system_architecture_node", "system_module_node", "system_database_node", "system_api_node",
    "test_case_node",
    END
]:
    # 如果不是最终决策则放行
    destination_node = END
    if isinstance(state["messages"][-1], AIMessage) and state["messages"][-1].tool_calls:
        destination_node = "product_manager_tool_node"
    else:
        match state["pm_next_step"]:
            case PMNextStep.REQUIREMENT_OUTLINE_DESIGN:
                destination_node = "requirement_outline_node"
            case PMNextStep.REQUIREMENT_MODULE_DESIGN:
                destination_node = "requirement_module_node"
            case PMNextStep.REQUIREMENT_OVERALL_DESIGN:
                destination_node = "requirement_overall_node"
            case PMNextStep.SYS_ARCHITECTURE_DESIGN:
                destination_node = "system_architecture_node"
            case PMNextStep.SYS_MODULES_DESIGN:
                destination_node = "system_module_node"
            case PMNextStep.SYS_DATABASE_DESIGN:
                destination_node = "system_database_node"
            case PMNextStep.SYS_API_DESIGN:
                destination_node = "system_api_node"
            case PMNextStep.TEST_CASE_DESIGN:
                destination_node = "test_case_node"
            case _:
                destination_node = END
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图路由:{gutils.get_func_name()} 路由至:{destination_node}")
    return destination_node
