from loguru import logger
from typing import Literal
from langgraph.types import Send
from langgraph.constants import END

from src.context import trans_id_ctx
from src.graphs.test.case.state import State
from src.graphs.common.base.routes import OptimizationDocRoutes


class Routes(OptimizationDocRoutes):

    def optimize_doc_tool_router(self, state: State) -> Literal[
        "optimize_doc_node",
        "optimize_doc_tool_node",
        "optimize_doc_by_task_node"
    ]:
        project_id = state["project_id"]
        if self.is_to_tool_node(state):
            destination_node = "optimize_doc_tool_node"
        elif state.get("node_rollback"):
            destination_node = "optimize_doc_node"
        else:
            tasks = state["tasks"]
            destination_node = [Send("optimize_doc_by_task_node", {"task": task, **state}) for task in tasks]
        if isinstance(destination_node, str):
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        else:
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:optimize_doc_by_task_node")
        return destination_node

    def optimize_doc_by_task_tool_router(self, state: State) -> Literal[
        "optimize_doc_by_task_node",
        "optimize_doc_by_task_tool_node",
        END
    ]:
        project_id = state["project_id"]
        destination_node = END
        if self.is_to_tool_node(state):
            destination_node = "optimize_doc_by_task_tool_node"
        elif state.get("node_rollback"):
            destination_node = "optimize_doc_by_task_node"
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node
