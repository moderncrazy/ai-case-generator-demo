import aiosqlite
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.graphs import nodes
from src.graphs import routes
from src.config import settings
from src.graphs.state import State
from src.graphs.tools import tool_list
from src.graphs.requirement.outline import graph as requirement_outline_graph
from src.graphs.requirement.module import graph as requirement_module_graph
from src.graphs.requirement.overall import graph as requirement_overall_graph
from src.graphs.system.architecture import graph as system_architecture_graph
from src.graphs.system.module import graph as system_module_graph
from src.graphs.system.database import graph as system_database_graph
from src.graphs.system.api import graph as system_api_graph
from src.graphs.test.case import graph as test_case_graph


async def create_agent() -> CompiledStateGraph:
    agent_builder = StateGraph(State)

    agent_builder.add_node("fix_state_messages_node", nodes.fix_state_messages_node)
    agent_builder.add_node("load_project_node", nodes.load_project_node)
    agent_builder.add_node("understand_image_node", nodes.understand_image_node)
    agent_builder.add_node("product_manager_node", nodes.product_manager_node)
    agent_builder.add_node("product_manager_tool_node", ToolNode(tool_list))
    # requirement 子图
    agent_builder.add_node("requirement_outline_node", requirement_outline_graph.create_agent())
    agent_builder.add_node("requirement_module_node", requirement_module_graph.create_agent())
    agent_builder.add_node("requirement_overall_node", requirement_overall_graph.create_agent())
    # system 子图
    agent_builder.add_node("system_architecture_node", system_architecture_graph.create_agent())
    agent_builder.add_node("system_module_node", system_module_graph.create_agent())
    agent_builder.add_node("system_database_node", system_database_graph.create_agent())
    agent_builder.add_node("system_api_node", system_api_graph.create_agent())
    # test 子图
    agent_builder.add_node("test_case_node", test_case_graph.create_agent())

    agent_builder.add_edge(START, "fix_state_messages_node")
    agent_builder.add_conditional_edges(
        "fix_state_messages_node",
        routes.load_project_router,
        ["load_project_node", "understand_image_node", "product_manager_node"]
    )
    agent_builder.add_conditional_edges(
        "load_project_node",
        routes.understand_image_router,
        ["understand_image_node", "product_manager_node"]
    )
    agent_builder.add_edge("understand_image_node", "product_manager_node")

    agent_builder.add_conditional_edges(
        "product_manager_node",
        routes.product_manager_tool_router,
        [
            "product_manager_tool_node",
            "requirement_outline_node",
            "requirement_module_node",
            "requirement_overall_node",
            "system_architecture_node",
            "system_module_node",
            "system_database_node",
            "system_api_node",
            "test_case_node",
            END
        ]
    )
    agent_builder.add_edge("product_manager_tool_node", "product_manager_node")

    sqlite_conn = await aiosqlite.connect(settings.langgraph_sqlite_checkpoint_path)
    sqlite_saver = AsyncSqliteSaver(sqlite_conn)
    agent = agent_builder.compile(checkpointer=sqlite_saver)
    return agent
