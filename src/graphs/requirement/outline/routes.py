from loguru import logger
from typing import Literal
from langgraph.graph import END

from src.context import trans_id_ctx
from src.graphs.requirement.outline.state import State
from src.graphs.common.utils import workflow_router_utils


def generate_optimization_requirement_outline_plan_tool_router(state: State) -> Literal[
    "generate_optimization_requirement_outline_plan_tool_node",
    "review_optimization_requirement_outline_plan_node"
]:
    project_id = state["project_id"]
    result = workflow_router_utils.tool_router(
        state,
        "generate_optimization_requirement_outline_plan_tool_node",
        "review_optimization_requirement_outline_plan_node"
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result


def review_optimization_requirement_outline_plan_tool_router(state: State) -> Literal[
    "review_optimization_requirement_outline_plan_node",
    "review_optimization_requirement_outline_plan_tool_node",
    "optimize_requirement_outline_node",
    "generate_optimization_requirement_outline_plan_node",
    END
]:
    project_id = state["project_id"]
    result = workflow_router_utils.review_optimization_plan_tool_router(
        state,
        "review_optimization_requirement_outline_plan_node",
        "review_optimization_requirement_outline_plan_tool_node",
        "optimize_requirement_outline_node",
        "generate_optimization_requirement_outline_plan_node"
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result


def optimize_requirement_outline_tool_router(state: State) -> Literal["optimize_requirement_outline_tool_node", END]:
    """需求大纲优化工具调用路由"""
    project_id = state["project_id"]
    result = workflow_router_utils.rollback_tool_router(
        state,
        "optimize_requirement_outline_node",
        "optimize_requirement_outline_tool_node",
        END
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{result}")
    return result
