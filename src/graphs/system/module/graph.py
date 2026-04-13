from loguru import logger
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src import constant as const
from src.graphs import tools as main_tools
from src.graphs.system.module.state import State
from src.graphs.system.module import routes, nodes, tools


def create_agent() -> CompiledStateGraph:
    agent_builder = StateGraph(State)

    agent_builder.add_node("optimize_system_module_node", nodes.optimize_system_module_node)
    agent_builder.add_node("optimize_system_module_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))
    agent_builder.add_node("review_system_module_node", nodes.review_system_module_node)
    agent_builder.add_node("review_system_module_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))
    agent_builder.add_node("review_system_module_aggregator_node", nodes.review_system_module_aggregator_node)

    agent_builder.add_edge(START, "optimize_system_module_node")
    agent_builder.add_conditional_edges(
        "optimize_system_module_node",
        routes.optimize_system_module_tool_router,
        ["optimize_system_module_tool_node", "review_system_module_node"]
    )
    agent_builder.add_edge("optimize_system_module_tool_node", "optimize_system_module_node")

    agent_builder.add_conditional_edges(
        "review_system_module_node",
        routes.review_system_module_tool_router,
        ["review_system_module_tool_node", "review_system_module_aggregator_node"]
    )
    agent_builder.add_edge("review_system_module_tool_node", "review_system_module_node")

    agent_builder.add_conditional_edges(
        "review_system_module_aggregator_node",
        routes.review_system_module_aggregator_router,
        ["optimize_system_module_node", END]
    )

    agent = agent_builder.compile()
    return agent
