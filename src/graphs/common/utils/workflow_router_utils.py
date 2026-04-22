from langgraph.graph import END
from langchain.messages import AIMessage

from src.graphs.state import State
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult


def tool_router(state: State, tool_node: str, next_node: str, message_key="private_messages") -> str:
    destination_node = next_node
    if (isinstance(state[message_key], list)
            and state[message_key]
            and isinstance(state[message_key][-1], AIMessage)
            and state[message_key][-1].tool_calls):
        destination_node = tool_node
    return destination_node


def review_optimization_plan_tool_router(state: State, tool_node: str,
                                         approve_node: str,
                                         revise_node: str,
                                         message_key="private_messages") -> str:
    destination_node = END
    if (isinstance(state[message_key], list)
            and state[message_key]
            and isinstance(state[message_key][-1], AIMessage)
            and state[message_key][-1].tool_calls):
        destination_node = tool_node
    else:
        match state["review_optimization_plan_result"]:
            case ReviewOptimizationPlanResult.APPROVE:
                destination_node = approve_node
            case ReviewOptimizationPlanResult.REVISE:
                destination_node = revise_node
            case ReviewOptimizationPlanResult.ASK_QUESTION:
                destination_node = END
    return destination_node
