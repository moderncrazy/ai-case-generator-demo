import inspect
from collections.abc import Callable
from langgraph.prebuilt import ToolNode
from langchain_core.tools import BaseTool
from langgraph.constants import START, END
from langgraph.graph.state import CompiledStateGraph, StateGraph

from src.graphs.common.base.tools import with_common_tools
from src.graphs.common.base.graph import create_group_member_review_optimization_doc_agent
from src.graphs.test.case import tools
from src.graphs.test.case.nodes import Nodes
from src.graphs.test.case.routes import Routes
from src.graphs.test.case.output_tools import OutputTools
from src.graphs.test.case.state import State, TaskState, GroupMemberState

common_tools = with_common_tools + tools.tool_list


def create_optimize_doc_by_task_agent(
        state_schema: type[TaskState],
        optimize_doc_by_task_node: Callable,
        optimize_doc_by_task_tool_router: Callable,
        tool_list: list[BaseTool] = common_tools,
        messages_key: str = "private_messages"
) -> CompiledStateGraph:
    """创建根据任务优化文档子图（供多任务并发优化使用）"""
    agent_builder = StateGraph(state_schema)

    agent_builder.add_node("optimize_doc_by_task_node", optimize_doc_by_task_node)
    agent_builder.add_node("optimize_doc_by_task_tool_node", ToolNode(tool_list, messages_key=messages_key))

    agent_builder.add_edge(START, "optimize_doc_by_task_node")
    agent_builder.add_conditional_edges(
        "optimize_doc_by_task_node",
        optimize_doc_by_task_tool_router,
        [
            "optimize_doc_by_task_node",
            "optimize_doc_by_task_tool_node",
            END
        ]
    )
    agent_builder.add_edge("optimize_doc_by_task_tool_node", "optimize_doc_by_task_node")

    agent = agent_builder.compile()
    return agent


def create_agent() -> CompiledStateGraph:
    """创建完整的优化 Agent"""

    messages_key = "private_messages"
    routes = Routes(messages_key=messages_key)
    output_tools = OutputTools(messages_key=messages_key)
    nodes = Nodes(output_tools, common_tools, messages_key=messages_key)

    tools_list = common_tools + [v for _, v in inspect.getmembers(OutputTools) if isinstance(v, BaseTool)]

    agent_builder = StateGraph(State)

    agent_builder.add_node("initialize_node", nodes.initialize_node)

    # 生成优化方案节点
    agent_builder.add_node("generate_optimization_plan_node", nodes.generate_optimization_plan_node)
    agent_builder.add_node("generate_optimization_plan_tool_node", ToolNode(tools_list, messages_key=messages_key))

    # 审核优化方案节点
    agent_builder.add_node("review_optimization_plan_node", nodes.review_optimization_plan_node)
    agent_builder.add_node("review_optimization_plan_tool_node", ToolNode(tools_list, messages_key=messages_key))

    # 优化文档节点
    agent_builder.add_node("optimize_doc_node", nodes.optimize_doc_node)
    agent_builder.add_node("optimize_doc_tool_node", ToolNode(tools_list, messages_key=messages_key))

    agent_builder.add_node("optimize_doc_by_task_node",
                           create_optimize_doc_by_task_agent(
                               TaskState,
                               nodes.optimize_doc_by_task_node,
                               routes.optimize_doc_by_task_tool_router,
                               tool_list=tools_list, messages_key=messages_key
                           ))

    # PM 审核优化文档节点
    agent_builder.add_node("pm_review_optimization_doc_node", nodes.pm_review_optimization_doc_node)
    agent_builder.add_node("pm_review_optimization_doc_tool_node", ToolNode(tools_list, messages_key=messages_key))

    # Group Member 审核优化文档节点
    agent_builder.add_node("group_member_review_optimization_doc_node",
                           create_group_member_review_optimization_doc_agent(
                               GroupMemberState,
                               nodes.group_member_review_optimization_doc_node,
                               routes.group_member_review_optimization_doc_tool_router,
                               tool_list=tools_list, messages_key=messages_key
                           ))

    # 总结优化文档问题节点
    agent_builder.add_node("filtrate_optimization_doc_review_issue_node",
                           nodes.filtrate_optimization_doc_review_issue_node)
    agent_builder.add_node("filtrate_optimization_doc_review_issue_tool_node",
                           ToolNode(tools_list, messages_key=messages_key))

    # 初始化节点
    agent_builder.add_edge(START, "initialize_node")

    # 优化流程路由，根据 metadata.generate_optimization_plan 判断是否生成优化方案
    agent_builder.add_conditional_edges(
        "initialize_node",
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
            "optimize_doc_by_task_node"
        ]
    )
    agent_builder.add_edge("optimize_doc_tool_node", "optimize_doc_node")

    # 并行优化文档
    agent_builder.add_edge("optimize_doc_by_task_node", "pm_review_optimization_doc_node")

    # PM 审核优化文档
    agent_builder.add_conditional_edges(
        "pm_review_optimization_doc_node",
        routes.pm_review_optimization_doc_tool_router,
        [
            "pm_review_optimization_doc_node",
            "pm_review_optimization_doc_tool_node",
            "group_member_review_optimization_doc_node",
            "optimize_doc_node",
            END
        ]
    )
    agent_builder.add_edge("pm_review_optimization_doc_tool_node", "pm_review_optimization_doc_node")

    # Group Member 审核优化文档
    agent_builder.add_edge("group_member_review_optimization_doc_node", "filtrate_optimization_doc_review_issue_node")

    # 总结优化文档问题
    agent_builder.add_conditional_edges(
        "filtrate_optimization_doc_review_issue_node",
        routes.filtrate_optimization_doc_review_issue_tool_router,
        [
            "filtrate_optimization_doc_review_issue_node",
            "filtrate_optimization_doc_review_issue_tool_node",
            "optimize_doc_node",
            END
        ]
    )
    agent_builder.add_edge("filtrate_optimization_doc_review_issue_tool_node",
                           "filtrate_optimization_doc_review_issue_node")

    agent = agent_builder.compile()
    return agent
