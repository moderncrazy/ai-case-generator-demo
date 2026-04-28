from typing import TypeVar
from langgraph.graph import END
from langgraph.types import Send
from langchain.messages import AIMessage

from src.graphs.state import State
from src.enums.group_member_role import GroupMemberRole
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult

AnyState = TypeVar("AnyState", bound=State)


def tool_router(state: AnyState, tool_node: str, next_node: str, message_key="private_messages") -> str:
    destination_node = next_node
    if (isinstance(state[message_key], list)
            and state[message_key]
            and isinstance(state[message_key][-1], AIMessage)
            and state[message_key][-1].tool_calls):
        destination_node = tool_node
    return destination_node


def rollback_tool_router(state: AnyState, self_node: str, tool_node: str, next_node: str,
                         message_key="private_messages") -> str:
    destination_node = next_node
    if (isinstance(state[message_key], list)
            and state[message_key]
            and isinstance(state[message_key][-1], AIMessage)
            and state[message_key][-1].tool_calls):
        destination_node = tool_node
    elif state.get("node_rollback"):
        destination_node = self_node
    return destination_node


def review_optimization_plan_tool_router(state: AnyState,
                                         self_node: str,
                                         tool_node: str,
                                         approve_node: str,
                                         revise_node: str,
                                         message_key="private_messages") -> str:
    destination_node = END
    if (isinstance(state[message_key], list)
            and state[message_key]
            and isinstance(state[message_key][-1], AIMessage)
            and state[message_key][-1].tool_calls):
        destination_node = tool_node
    elif state.get("node_rollback"):
        destination_node = self_node
    else:
        match state["review_optimization_plan_result"]:
            case ReviewOptimizationPlanResult.APPROVE:
                destination_node = approve_node
            case ReviewOptimizationPlanResult.REVISE:
                destination_node = revise_node
            case ReviewOptimizationPlanResult.ASK_QUESTION:
                destination_node = END
    return destination_node


def optimize_doc_tool_router(state: AnyState,
                             self_node: str,
                             tool_node: str,
                             review_node: str,
                             roles: list[GroupMemberRole],
                             message_key="private_messages") -> str | list[Send]:
    if (isinstance(state[message_key], list)
            and state[message_key]
            and isinstance(state[message_key][-1], AIMessage)
            and state[message_key][-1].tool_calls):
        return tool_node
    elif state.get("node_rollback"):
        return self_node
    else:
        return [Send(review_node, {"role": role, **state}) for role in roles]


def review_optimize_doc_aggregator_router(state: AnyState, optimize_node: str, next_node: str) -> str:
    destination_node = next_node
    if state["review_issues"]:
        destination_node = optimize_node
    return destination_node
