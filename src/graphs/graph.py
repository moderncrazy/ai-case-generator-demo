import aiosqlite
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.config import settings
from src.graphs import tools
from src.graphs import nodes
from src.graphs import routes
from src.graphs.state import State
from src.graphs.common import tools as ctools
from src.graphs.requirement.outline import graph as requirement_outline_graph
from src.graphs.requirement.module import graph as requirement_module_graph
from src.graphs.requirement.overall import graph as requirement_overall_graph
from src.graphs.system.architecture import graph as system_architecture_graph
from src.graphs.system.module import graph as system_module_graph
from src.graphs.system.database import graph as system_database_graph
from src.graphs.system.api import graph as system_api_graph
from src.graphs.test.case import graph as test_case_graph


async def create_agent() -> CompiledStateGraph:
    """创建主图 Agent
    
    构建完整的主图工作流，包含以下阶段：
    - 状态修复：处理消息状态异常
    - 项目加载：初始化项目数据
    - 图片理解：解析用户上传的文档文件
    - 产品经理：与用户沟通的核心节点
    - 子图调用：需求大纲/需求模块/整体设计/系统架构/系统模块/数据库/API设计/测试用例设计
    
    Returns:
        CompiledStateGraph: 编译后的完整 agent
    """
    agent_builder = StateGraph(State)

    agent_builder.add_node("fix_state_messages_node", nodes.fix_state_messages_node)
    agent_builder.add_node("load_project_node", nodes.load_project_node)
    agent_builder.add_node("understand_image_node", nodes.understand_image_node)
    agent_builder.add_node("product_manager_node", nodes.product_manager_node)
    agent_builder.add_node("end_node", nodes.end_node)
    agent_builder.add_node("product_manager_tool_node", ToolNode(tools.tool_list + ctools.tool_list))

    # 子图 节点
    subgraph_node = {
        # requirement 子图
        "requirement_outline_node": requirement_outline_graph.create_agent(),
        "requirement_module_node": requirement_module_graph.create_agent(),
        "requirement_overall_node": requirement_overall_graph.create_agent(),
        # system 子图
        "system_architecture_node": system_architecture_graph.create_agent(),
        "system_module_node": system_module_graph.create_agent(),
        "system_database_node": system_database_graph.create_agent(),
        "system_api_node": system_api_graph.create_agent(),
        # test 子图
        "test_case_node": test_case_graph.create_agent(),
    }
    # 添加子图
    for node, graph in subgraph_node.items():
        agent_builder.add_node(node, graph)

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
        ["end_node", "product_manager_tool_node", *[node for node in subgraph_node.keys()]]
    )
    agent_builder.add_edge("product_manager_tool_node", "product_manager_node")

    # 所有节点最终都走到 end_node
    for node in subgraph_node.keys():
        agent_builder.add_edge(node, "end_node")

    sqlite_conn = await aiosqlite.connect(settings.langgraph_sqlite_checkpoint_path)
    sqlite_saver = AsyncSqliteSaver(sqlite_conn)
    agent = agent_builder.compile(checkpointer=sqlite_saver)
    return agent
