import inspect
from langchain.tools import BaseTool
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from src.graphs.common.base.tools import with_common_tools
from src.graphs.common.base.nodes import OptimizationDocNodes
from src.graphs.common.base.state import OptimizationDocState
from src.graphs.requirement.outline.routes import Routes
from src.graphs.requirement.outline.output_tools import OutputTools


def create_agent() -> CompiledStateGraph:
    messages_key = "private_messages"
    routes = Routes(messages_key=messages_key)
    output_tools = OutputTools(messages_key=messages_key)
    nodes = OptimizationDocNodes(output_tools, with_common_tools, messages_key=messages_key)

    tools_list = with_common_tools + [v for _, v in inspect.getmembers(OutputTools) if isinstance(v, BaseTool)]

    agent_builder = StateGraph(OptimizationDocState)

    # 生成优化方案节点
    agent_builder.add_node("generate_optimization_plan_node", nodes.generate_optimization_plan_node)
    agent_builder.add_node("generate_optimization_plan_tool_node", ToolNode(tools_list, messages_key=messages_key))

    # 审核优化方案节点
    agent_builder.add_node("review_optimization_plan_node", nodes.review_optimization_plan_node)
    agent_builder.add_node("review_optimization_plan_tool_node", ToolNode(tools_list, messages_key=messages_key))

    # 优化文档节点
    agent_builder.add_node("optimize_doc_node", nodes.optimize_doc_node)
    agent_builder.add_node("optimize_doc_tool_node", ToolNode(tools_list, messages_key=messages_key))

    agent_builder.add_conditional_edges(
        START,
        routes.optimization_flow_router,
        ["generate_optimization_plan_node", "optimize_doc_node"]
    )

    # 生成优化方案
    agent_builder.add_conditional_edges(
        "generate_optimization_plan_node",
        routes.generate_optimization_plan_tool_router,
        ["generate_optimization_plan_tool_node", "review_optimization_plan_node"]
    )
    agent_builder.add_edge("generate_optimization_plan_tool_node", "generate_optimization_plan_node")

    # 审核优化方案
    agent_builder.add_conditional_edges(
        "review_optimization_plan_node",
        routes.review_optimization_plan_tool_router,
        [
            "review_optimization_plan_node",
            "review_optimization_plan_tool_node",
            "optimize_doc_node",
            "generate_optimization_plan_node",
            END
        ]
    )
    agent_builder.add_edge("review_optimization_plan_tool_node", "review_optimization_plan_node")

    # 优化文档
    agent_builder.add_conditional_edges(
        "optimize_doc_node",
        routes.optimize_doc_tool_router,
        [
            "optimize_doc_node",
            "optimize_doc_tool_node",
            END
        ]
    )
    agent_builder.add_edge("optimize_doc_tool_node", "optimize_doc_node")

    agent = agent_builder.compile()
    return agent
