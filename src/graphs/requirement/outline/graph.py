from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.graphs.common.tools import optimization_plan_tools, tools as ctools
from src.graphs.requirement.outline.state import State
from src.graphs.requirement.outline import routes, nodes, tools

tool_node_tools = optimization_plan_tools.tool_list + ctools.tool_list + tools.tool_list


def create_agent() -> CompiledStateGraph:
    """创建需求大纲设计 Agent
    
    工作流程：优化需求大纲 → 调用工具 → 循环直到完成
    - 优化节点：根据上下文生成需求大纲和模块划分
    - 工具节点：提供查询历史文档等工具支持
    
    Returns:
        CompiledStateGraph: 编译后的 agent
    """
    agent_builder = StateGraph(State)

    agent_builder.add_node("generate_optimization_requirement_outline_plan_node",
                           nodes.generate_optimization_requirement_outline_plan_node)
    agent_builder.add_node("generate_optimization_requirement_outline_plan_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    agent_builder.add_node("review_optimization_requirement_outline_plan_node",
                           nodes.review_optimization_requirement_outline_plan_node)
    agent_builder.add_node("review_optimization_requirement_outline_plan_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    agent_builder.add_node("optimize_requirement_outline_node", nodes.optimize_requirement_outline_node)
    agent_builder.add_node("optimize_requirement_outline_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    agent_builder.add_edge(START, "generate_optimization_requirement_outline_plan_node")

    agent_builder.add_conditional_edges(
        "generate_optimization_requirement_outline_plan_node",
        routes.generate_optimization_requirement_outline_plan_tool_router,
        ["generate_optimization_requirement_outline_plan_tool_node",
         "review_optimization_requirement_outline_plan_node"]
    )
    agent_builder.add_edge("generate_optimization_requirement_outline_plan_tool_node",
                           "generate_optimization_requirement_outline_plan_node")

    agent_builder.add_conditional_edges(
        "review_optimization_requirement_outline_plan_node",
        routes.review_optimization_requirement_outline_plan_tool_router,
        [
            "review_optimization_requirement_outline_plan_node",
            "review_optimization_requirement_outline_plan_tool_node",
            "optimize_requirement_outline_node",
            "generate_optimization_requirement_outline_plan_node",
            END
        ]
    )
    agent_builder.add_edge("review_optimization_requirement_outline_plan_tool_node",
                           "review_optimization_requirement_outline_plan_node")

    agent_builder.add_conditional_edges(
        "optimize_requirement_outline_node",
        routes.optimize_requirement_outline_tool_router,
        ["optimize_requirement_outline_node", "optimize_requirement_outline_tool_node", END]
    )
    agent_builder.add_edge("optimize_requirement_outline_tool_node", "optimize_requirement_outline_node")

    agent = agent_builder.compile()
    return agent
