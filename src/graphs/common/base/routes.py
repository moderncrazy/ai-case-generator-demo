from loguru import logger
from langgraph.graph import END
from langgraph.types import Send
from typing import Literal, TypeVar
from langchain.messages import AIMessage

from src.context import trans_id_ctx
from src.graphs.common.base.state import AnyOptimizationDocState
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.enums.pm_review_optimization_doc_result import PMReviewOptimizationDocResult
from src.enums.filtrate_optimization_doc_review_issue_result import FiltrateOptimizationDocReviewIssueResult


class OptimizationDocRoutes:

    def __init__(self, messages_key: str = "private_messages"):
        self.messages_key = messages_key

    def is_to_tool_node(self, state: AnyOptimizationDocState) -> bool:
        if (isinstance(state[self.messages_key], list)
                and state[self.messages_key]
                and isinstance(state[self.messages_key][-1], AIMessage)
                and state[self.messages_key][-1].tool_calls):
            return True
        return False

    # noinspection PyMethodMayBeStatic
    def optimization_flow_router(self, state: AnyOptimizationDocState) -> Literal[
        "generate_optimization_plan_node",
        "optimize_doc_node"
    ]:
        project_id = state["project_id"]
        destination_node = "optimize_doc_node"
        if state.get("metadata") and state["metadata"].get("generate_optimization_plan"):
            destination_node = "generate_optimization_plan_node"
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node

    def generate_optimization_plan_tool_router(self, state: AnyOptimizationDocState) -> Literal[
        "generate_optimization_plan_tool_node",
        "review_optimization_plan_node"
    ]:
        project_id = state["project_id"]
        destination_node = "review_optimization_plan_node"
        if self.is_to_tool_node(state):
            destination_node = "generate_optimization_plan_tool_node"
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node

    def review_optimization_plan_tool_router(self, state: AnyOptimizationDocState) -> Literal[
        "review_optimization_plan_node"
        "review_optimization_plan_tool_node",
        "optimize_doc_node",
        "generate_optimization_plan_node",
        END
    ]:
        project_id = state["project_id"]
        destination_node = END
        if self.is_to_tool_node(state):
            destination_node = "review_optimization_plan_tool_node"
        elif state.get("node_rollback"):
            destination_node = "review_optimization_plan_node"
        else:
            match state["review_optimization_plan_result"]:
                case ReviewOptimizationPlanResult.APPROVE:
                    destination_node = "optimize_doc_node"
                case ReviewOptimizationPlanResult.REVISE:
                    destination_node = "generate_optimization_plan_node"
                case ReviewOptimizationPlanResult.ASK_QUESTION:
                    destination_node = END
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node

    def optimize_doc_tool_router(self, state: AnyOptimizationDocState) -> Literal[
        "optimize_doc_node",
        "optimize_doc_tool_node",
        "pm_review_optimization_doc_node"
    ]:
        """优化工具调用路由（并发多角色评审）

        判断优化节点最后一条消息是否为工具调用：
        - 是：继续调用工具
        - 否：并发生成 多个角色进行评审
        """
        project_id = state["project_id"]
        destination_node = "pm_review_optimization_doc_node"
        if self.is_to_tool_node(state):
            destination_node = "optimize_doc_tool_node"
        elif state.get("node_rollback"):
            destination_node = "optimize_doc_node"
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node

    def pm_review_optimization_doc_tool_router(self, state: AnyOptimizationDocState) -> Literal[
        "pm_review_optimization_doc_node",
        "pm_review_optimization_doc_tool_node",
        "group_member_review_optimization_doc_node",
        "optimize_doc_node",
        END
    ]:
        """优化工具调用路由（并发多角色评审）

        判断优化节点最后一条消息是否为工具调用：
        - 是：继续调用工具
        - 否：并发生成 多个角色进行评审
        """
        project_id = state["project_id"]
        destination_node = END
        if self.is_to_tool_node(state):
            destination_node = "pm_review_optimization_doc_tool_node"
        elif state.get("node_rollback"):
            destination_node = "pm_review_optimization_doc_node"
        else:
            match state["pm_review_optimization_doc_result"]:
                case PMReviewOptimizationDocResult.PASS:
                    destination_node = END
                case PMReviewOptimizationDocResult.REVISE:
                    destination_node = "optimize_doc_node"
                case PMReviewOptimizationDocResult.GROUP_MEMBER_REVIEW:
                    roles = state["group_member_review_optimization_doc_roles"]
                    destination_node = [Send("group_member_review_optimization_doc_node", {"role": role, **state})
                                        for role in roles]
        if isinstance(destination_node, str):
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        else:
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:group_member_review_optimization_doc_node")
        return destination_node

    def group_member_review_optimization_doc_tool_router(self, state: AnyOptimizationDocState) -> Literal[
        "review_optimization_doc_tool_node",
        END
    ]:
        """评审聚合路由

        根据评审发现的问题数量决定后续流程：
        - 有问题：返回优化节点继续修改
        - 无问题：进入问题整理节点
        """
        project_id = state["project_id"]
        destination_node = END
        if self.is_to_tool_node(state):
            destination_node = "review_optimization_doc_tool_node"
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node

    def filtrate_optimization_doc_review_issue_tool_router(self, state: AnyOptimizationDocState) -> Literal[
        "filtrate_optimization_doc_review_issue_node",
        "filtrate_optimization_doc_review_issue_tool_node",
        "optimize_doc_node",
        END
    ]:
        """问题整理工具调用路由"""
        project_id = state["project_id"]
        destination_node = END
        if self.is_to_tool_node(state):
            destination_node = "filtrate_optimization_doc_review_issue_tool_node"
        elif state.get("node_rollback"):
            destination_node = "filtrate_optimization_doc_review_issue_node"
        else:
            match state["filtrate_optimization_doc_review_issue_result"]:
                case FiltrateOptimizationDocReviewIssueResult.PASS:
                    destination_node = END
                case FiltrateOptimizationDocReviewIssueResult.REVISE:
                    destination_node = "optimize_doc_node"
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
        return destination_node


AnyOptimizationDocRoutes = TypeVar("AnyOptimizationDocRoutes", bound=OptimizationDocRoutes)
