import aiosqlite
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.config import settings
from src.graphs.main.state import State
from src.graphs.main import routes, nodes


async def create_agent() -> CompiledStateGraph:
    agent_builder = StateGraph(State)

    agent_builder.add_node(nodes.load_project_node)
    agent_builder.add_node(nodes.understand_image_node)
    agent_builder.add_node(nodes.product_manager_node)

    agent_builder.add_conditional_edges(
        START,
        routes.load_project_router,
        ["understand_image_node", "load_project_node"]
    )
    agent_builder.add_conditional_edges(
        START,
        routes.understand_image_router,
        ["understand_image_node", "product_manager_node"]
    )
    agent_builder.add_edge("understand_image_node", "product_manager_node")

    sqlite_conn = await aiosqlite.connect(settings.langgraph_sqlite_checkpoint_path)
    sqlite_saver = AsyncSqliteSaver(sqlite_conn)
    agent = agent_builder.compile(checkpointer=sqlite_saver)
    return agent
