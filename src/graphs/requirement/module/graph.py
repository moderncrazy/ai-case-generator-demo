from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.graphs.requirement.module import routes, nodes, tools
from src.graphs.requirement.module.state import State, GroupMemberState
from src.graphs.common.tools import optimization_plan_tools, review_issue_tools, to_summarize_tools, tools as ctools

tool_node_tools = (optimization_plan_tools.tool_list + review_issue_tools.tool_list
                   + to_summarize_tools.tool_list + ctools.tool_list + tools.tool_list)


def create_group_member_review_agent() -> CompiledStateGraph:
    """创建评审子图（供多角色并发评审使用）
    
    该子图用于单角色评审需求模块，包含：
    - 评审节点：根据角色使用不同提示词评审模块
    - 工具节点：提供查询上下文等工具支持
    
    Returns:
        CompiledStateGraph: 编译后的评审子图
    """
    agent_builder = StateGraph(GroupMemberState)

    agent_builder.add_node("review_requirement_module_node", nodes.review_requirement_module_node)
    agent_builder.add_node("review_requirement_module_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    agent_builder.add_edge(START, "review_requirement_module_node")
    agent_builder.add_conditional_edges(
        "review_requirement_module_node",
        routes.review_requirement_module_tool_router,
        ["review_requirement_module_tool_node", END]
    )
    agent_builder.add_edge("review_requirement_module_tool_node", "review_requirement_module_node")

    agent = agent_builder.compile()
    return agent


def create_agent() -> CompiledStateGraph:
    """创建完整的优化 Agent
    
    工作流程：生成方案 → 审核方案 → 优化 → 评审（多角色并发）→ 聚合 → 问题整理
    - 生成方案节点：PM 生成优化方案
    - 审核方案节点：Product 审核优化方案
    - 优化节点：根据上下文优化当前模块内容
    - Review 子图：团队成员分别评审
    - 聚合节点：汇总评审结果，判断是否需要返工或进入下一阶段
    - 问题整理节点：整理风险点和待确认问题
    
    Returns:
        CompiledStateGraph: 编译后的完整 agent
    """
    agent_builder = StateGraph(State)

    # 生成方案节点
    agent_builder.add_node("generate_optimization_requirement_module_plan_node",
                           nodes.generate_optimization_requirement_module_plan_node)
    agent_builder.add_node("generate_optimization_requirement_module_plan_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    # 审核方案节点
    agent_builder.add_node("review_optimization_requirement_module_plan_node",
                           nodes.review_optimization_requirement_module_plan_node)
    agent_builder.add_node("review_optimization_requirement_module_plan_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    # 优化节点
    agent_builder.add_node("optimize_requirement_module_node", nodes.optimize_requirement_module_node)
    agent_builder.add_node("optimize_requirement_module_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    # review 子图
    agent_builder.add_node("review_requirement_module_node", create_group_member_review_agent())

    # 聚合节点
    agent_builder.add_node("review_requirement_module_aggregator_node", lambda state: state)

    agent_builder.add_node("optimize_requirement_module_issue_node", nodes.optimize_requirement_module_issue_node)
    agent_builder.add_node("optimize_requirement_module_issue_tool_node",
                           ToolNode(tool_node_tools, messages_key="private_messages"))

    agent_builder.add_edge(START, "generate_optimization_requirement_module_plan_node")

    agent_builder.add_conditional_edges(
        "generate_optimization_requirement_module_plan_node",
        routes.generate_optimization_requirement_module_plan_tool_router,
        ["generate_optimization_requirement_module_plan_tool_node",
         "review_optimization_requirement_module_plan_node"]
    )
    agent_builder.add_edge("generate_optimization_requirement_module_plan_tool_node",
                           "generate_optimization_requirement_module_plan_node")

    agent_builder.add_conditional_edges(
        "review_optimization_requirement_module_plan_node",
        routes.review_optimization_requirement_module_plan_tool_router,
        [
            "review_optimization_requirement_module_plan_node",
            "review_optimization_requirement_module_plan_tool_node",
            "optimize_requirement_module_node",
            "generate_optimization_requirement_module_plan_node",
            END
        ]
    )
    agent_builder.add_edge("review_optimization_requirement_module_plan_tool_node",
                           "review_optimization_requirement_module_plan_node")

    agent_builder.add_conditional_edges(
        "optimize_requirement_module_node",
        routes.optimize_requirement_module_tool_router,
        [
            "optimize_requirement_module_node",
            "optimize_requirement_module_tool_node",
            "review_requirement_module_node"
        ]
    )
    agent_builder.add_edge("optimize_requirement_module_tool_node", "optimize_requirement_module_node")

    agent_builder.add_edge("review_requirement_module_node", "review_requirement_module_aggregator_node")

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
