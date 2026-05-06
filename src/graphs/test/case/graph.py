from langgraph.graph.state import CompiledStateGraph

from src.graphs.common.base.tools import with_common_tools
from src.graphs.common.base.nodes import OptimizationDocNodes
from src.graphs.common.base.routes import OptimizationDocRoutes
from src.graphs.common.base.graph import create_optimization_doc_agent
from src.graphs.test.case import tools
from src.graphs.test.case.output_tools import OutputTools
from src.graphs.test.case.state import State, GroupMemberState

common_tools = with_common_tools + tools.tool_list


def create_agent() -> CompiledStateGraph:
    messages_key = "private_messages"
    output_tools = OutputTools(messages_key=messages_key)
    nodes = OptimizationDocNodes(output_tools, common_tools, messages_key=messages_key)
    routes = OptimizationDocRoutes(messages_key=messages_key)
    agent = create_optimization_doc_agent(
        State, GroupMemberState, nodes, routes, output_tools, common_tools, messages_key)
    return agent
