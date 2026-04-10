from loguru import logger
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src import constant as const
from src.graphs import tools as main_tools
from src.graphs.requirement.state import State
from src.graphs.requirement import routes, nodes, tools


def create_agent() -> CompiledStateGraph:
    agent_builder = StateGraph(State)

    agent_builder.add_node("optimize_prd_node", nodes.optimize_prd_node)
    agent_builder.add_node("optimize_prd_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))
    agent_builder.add_node("review_prd_node", nodes.review_prd_node)
    agent_builder.add_node("review_prd_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))
    agent_builder.add_node("optimize_prd_issue_node", nodes.optimize_prd_issue_node)
    agent_builder.add_node("optimize_prd_issue_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))

    agent_builder.add_edge(START, "optimize_prd_node")
    agent_builder.add_conditional_edges(
        "optimize_prd_node",
        routes.optimize_prd_node_tool_router,
        ["optimize_prd_tool_node", "review_prd_node"]
    )
    agent_builder.add_edge("optimize_prd_tool_node", "optimize_prd_node")

    agent_builder.add_conditional_edges(
        "review_prd_node",
        routes.review_prd_tool_router,
        ["review_prd_tool_node", "optimize_prd_node", "optimize_prd_issue_node"]
    )
    agent_builder.add_edge("review_prd_tool_node", "review_prd_node")

    agent_builder.add_conditional_edges(
        "optimize_prd_issue_node",
        routes.optimize_prd_issue_router,
        ["optimize_prd_issue_tool_node", END]
    )
    agent_builder.add_edge("optimize_prd_issue_tool_node", "optimize_prd_issue_node")

    agent = agent_builder.compile()
    return agent
