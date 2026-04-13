from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.graphs import tools as main_tools
from src.graphs.requirement.module.state import State
from src.graphs.requirement.module import routes, nodes, tools


def create_agent() -> CompiledStateGraph:
    agent_builder = StateGraph(State)

    agent_builder.add_node("optimize_requirement_module_node", nodes.optimize_requirement_module_node)
    agent_builder.add_node("optimize_requirement_module_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))
    agent_builder.add_node("review_requirement_module_node", nodes.review_requirement_module_node)
    agent_builder.add_node("review_requirement_module_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))
    agent_builder.add_node("review_requirement_module_aggregator_node", lambda state: state)
    agent_builder.add_node("optimize_requirement_module_issue_node", nodes.optimize_requirement_module_issue_node)
    agent_builder.add_node("optimize_requirement_module_issue_tool_node",
                           ToolNode(main_tools.tool_list + tools.tool_list, messages_key="private_messages"))

    agent_builder.add_edge(START, "optimize_requirement_module_node")
    agent_builder.add_conditional_edges(
        "optimize_requirement_module_node",
        routes.optimize_requirement_module_tool_router,
        ["optimize_requirement_module_tool_node", "review_requirement_module_node"]
    )
    agent_builder.add_edge("optimize_requirement_module_tool_node", "optimize_requirement_module_node")

    agent_builder.add_conditional_edges(
        "review_requirement_module_node",
        routes.review_requirement_module_tool_router,
        ["review_requirement_module_tool_node", "review_requirement_module_aggregator_node"]
    )
    agent_builder.add_edge("review_requirement_module_tool_node", "review_requirement_module_node")

    agent_builder.add_conditional_edges(
        "review_requirement_module_aggregator_node",
        routes.review_requirement_module_aggregator_router,
        ["optimize_requirement_module_node", "optimize_requirement_module_issue_node"]
    )

    agent_builder.add_conditional_edges(
        "optimize_requirement_module_issue_node",
        routes.optimize_requirement_module_issue_router,
        ["optimize_requirement_module_issue_tool_node", END]
    )
    agent_builder.add_edge("optimize_requirement_module_issue_tool_node", "optimize_requirement_module_issue_node")

    agent = agent_builder.compile()
    return agent
