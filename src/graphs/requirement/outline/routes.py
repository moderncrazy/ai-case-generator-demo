from loguru import logger
from typing import Literal
from langgraph.graph import END

from src.context import trans_id_ctx
from src.graphs.common.base.routes import OptimizationDocRoutes
from src.graphs.common.base.state import AnyOptimizationDocState


class Routes(OptimizationDocRoutes):

    def optimize_doc_tool_router(self, state: AnyOptimizationDocState) -> Literal[
        "optimize_doc_node",
        "optimize_doc_tool_node",
        END
    ]:
        project_id = state["project_id"]
        destination_node = END
        if self.is_to_tool_node(state):
            destination_node = "optimize_doc_tool_node"
        elif state.get("node_rollback"):
            destination_node = "optimize_doc_node"
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node
