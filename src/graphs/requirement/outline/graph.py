from loguru import logger
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src import constant as const
from src.graphs import tools as main_tools
from src.graphs.requirement.outline.state import State
from src.graphs.requirement.outline import routes, nodes, tools


def create_agent() -> CompiledStateGraph:
    agent_builder = StateGraph(State)

    agent_builder.add_node("optimize_requirement_outline_node", nodes.optimize_requirement_outline_node)
    agent_builder.add_node("optimize_requirement_outline_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))

    agent_builder.add_edge(START, "optimize_requirement_outline_node")
    agent_builder.add_conditional_edges(
        "optimize_requirement_outline_node",
        routes.optimize_requirement_outline_tool_router,
        ["optimize_requirement_outline_tool_node", END]
    )
    agent_builder.add_edge("optimize_requirement_outline_tool_node", "optimize_requirement_outline_node")

    agent = agent_builder.compile()
    return agent
