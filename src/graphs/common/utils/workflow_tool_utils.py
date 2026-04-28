import uuid

from loguru import logger
from typing import TypeVar
from pydantic import BaseModel
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command, Overwrite
from langchain.messages import ToolMessage, AIMessage, AnyMessage

from src.utils import utils as gutils
from src.context import trans_id_ctx
from src.graphs.common.utils import utils
from src.graphs.common.utils import structured_output_utils
from src.graphs.common.schemas import (
    GenerateOptimizationPlanOutput,
    OptimizeDocBaseOutput,
    OptimizeDocToSummarizeBaseOutput,
    ReviewOptimizationDocOutput,
    ReviewOptimizationDocToSummarizeOutput,
    ReviewOptimizationPlanOutput,
    SummarizeOptimizationDocIssueOutput,
)
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult

AnyOptimizeDocOutput = TypeVar("AnyOptimizeDocOutput", bound=OptimizeDocBaseOutput)
AnyOptimizeDocToSummarizeOutput = TypeVar("AnyOptimizeDocToSummarizeOutput", bound=OptimizeDocToSummarizeBaseOutput)


def validate_review_optimization_plan_output_to_str(output: ReviewOptimizationPlanOutput) -> str:
    error_message = ""
    if not output.issues:
        match output.result:
            case ReviewOptimizationPlanResult.REVISE:
                error_message = "审核结果为：revise 时，issues 不能为空"
            case ReviewOptimizationPlanResult.ASK_QUESTION:
                error_message = "审核结果为：ask_question 时，issues 不能为空"
    return error_message


def remove_tool_messages(messages: list[AnyMessage]) -> list[AnyMessage]:
    """将历史消息中的 工具调用、工具输出 都删掉，防止上下文超限"""
    results = messages.copy()
    for message in messages:
        if isinstance(message, ToolMessage) or (isinstance(message, AIMessage) and message.tool_calls):
            results.remove(message)
    return results


def generate_optimization_plan_output(output: GenerateOptimizationPlanOutput, runtime: ToolRuntime,
                                      role: GroupMemberRole, message_key="private_messages") -> Command:
    optimization_plan = utils.format_generate_optimization_plan_output_to_str(output)
    optimization_plan_and_question = utils.format_generate_optimization_plan_and_question_output_to_str(output)
    result_message = AIMessage(content=optimization_plan_and_question, name=role.value)
    return Command(update={
        "optimization_plan_content": optimization_plan,
        # 重写消息列表 删除所有tool调用
        message_key: Overwrite(value=remove_tool_messages([*runtime.state[message_key], result_message]))
    })


def review_optimization_plan_output(output: ReviewOptimizationPlanOutput, runtime: ToolRuntime,
                                    role: GroupMemberRole = GroupMemberRole.PM,
                                    message_key="private_messages") -> Command:
    project_id = runtime.state["project_id"]
    # 验证审核结果参数是否缺失
    error_message = validate_review_optimization_plan_output_to_str(output)
    if error_message:
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 参数验证失败打回:{error_message}")
        tool_call_id = runtime.tool_call_id
        tool_name = gutils.get_func_name(depth=2)
        tool_call_message = structured_output_utils.mock_ai_message_in_structured_output(
            tool_call_id, tool_name, output.model_dump())
        # 打回修复
        return Command(
            update={
                "node_rollback": True,
                message_key: [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]
            },
        )
    message = utils.format_review_optimization_plan_output_to_str(output)
    # 如果需要咨询客户则发消息给客户 否则继续
    if output.result == ReviewOptimizationPlanResult.ASK_QUESTION:
        return Command(update={
            "node_rollback": False,
            "messages": [AIMessage(content=message, name=role.value)],
            message_key: ReducerActionType.RESET,
            "review_optimization_plan_result": output.result
        })
    else:
        if output.result == ReviewOptimizationPlanResult.APPROVE:
            message = f"优化方案AI审核的结果如下：\n{message}\n**请根据AI生成的具体优化方案进行优化**"
        else:
            message = f"优化方案AI审核的结果如下：\n{message}\n**请根据上述意见重新设计方案**"
        result_message = AIMessage(content=message, name=role.value)
        return Command(update={
            "node_rollback": False,
            # 重写消息列表 删除所有tool调用
            message_key: Overwrite(value=remove_tool_messages([*runtime.state[message_key], result_message])),
            "review_optimization_plan_result": output.result
        })


def optimize_doc_output(
        output: AnyOptimizeDocOutput,
        runtime: ToolRuntime,
        role: GroupMemberRole,
        content_key: str,
        error_message: str = None,
        message_key="private_messages"
) -> Command:
    project_id = runtime.state["project_id"]
    # 外部传入自定义 error_message
    error_msg = error_message
    # 验证各角色提出的意见是否被清空
    if not error_msg and runtime.state.get("review_issues"):
        error_msg = f"检验失败：评审意见未全部解决，重新优化并解决全部评审意见"
    if error_msg:
        tool_call_id = runtime.tool_call_id
        tool_name = gutils.get_func_name(depth=2)
        tool_call_message = structured_output_utils.mock_ai_message_in_structured_output(
            tool_call_id, tool_name, output.model_dump())
        logger.warning(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 打回:{error_msg}")
        return Command(
            update={
                "node_rollback": True,
                message_key: [tool_call_message, ToolMessage(content=error_msg, tool_call_id=tool_call_id)]
            }
        )
    result_message = AIMessage(content=output.message, name=role.value)
    return Command(update={
        "node_rollback": False,
        # 重写消息列表 删除所有tool调用
        message_key: Overwrite(value=remove_tool_messages([*runtime.state[message_key], result_message])),
        "review_reply_message_id": str(uuid.uuid4()),
        content_key: output.model_dump()[content_key],
        "review_issues": ReducerActionType.RESET,
    })


def optimize_doc_to_summarize_output(
        output: AnyOptimizeDocToSummarizeOutput,
        runtime: ToolRuntime,
        role: GroupMemberRole,
        content_key: str,
        error_message: str = None,
        message_key="private_messages"
) -> Command:
    project_id = runtime.state["project_id"]
    # 外部传入自定义 error_message
    error_msg = error_message
    # 验证各角色提出的意见是否被清空
    if not error_msg and runtime.state.get("review_issues"):
        error_msg = f"检验失败：评审意见未全部解决，重新优化并解决全部评审意见"
    if error_msg:
        tool_call_id = runtime.tool_call_id
        tool_name = gutils.get_func_name(depth=2)
        tool_call_message = structured_output_utils.mock_ai_message_in_structured_output(
            tool_call_id, tool_name, output.model_dump())
        logger.warning(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 打回:{error_msg}")
        return Command(
            update={
                "node_rollback": True,
                message_key: [tool_call_message, ToolMessage(content=error_msg, tool_call_id=tool_call_id)]
            }
        )
    result_message = AIMessage(content=output.message, name=role.value)
    # 若是 BaseModel 则 转为 dict
    return Command(update={
        "node_rollback": False,
        # 重写消息列表 删除所有tool调用
        message_key: Overwrite(value=remove_tool_messages([*runtime.state[message_key], result_message])),
        "review_reply_message_id": str(uuid.uuid4()),
        content_key: output.model_dump()[content_key],
        "review_issues": ReducerActionType.RESET,
        "private_risks": [item.model_dump() for item in (output.risks or [])],
        "private_unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


def review_optimization_doc_output(
        output: ReviewOptimizationDocOutput,
        runtime: ToolRuntime,
        message_key="private_messages"
) -> Command:
    # 发现问题构建回复
    messages = []
    message_id = runtime.state["review_reply_message_id"]
    if output.review_issues:
        messages.append(AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="AI团队成员评审完成，发现问题，请根据评审意见修改设计",
            additional_kwargs={"priority": 1}
        ))
    return Command(update={
        # 重写消息列表 删除所有tool调用
        message_key: Overwrite(value=remove_tool_messages([*runtime.state[message_key], *messages])),
        "review_issues": [item.model_dump() for item in (output.review_issues or [])],
    })


def review_optimization_doc_to_summarize_output(output: ReviewOptimizationDocToSummarizeOutput,
                                                runtime: ToolRuntime, message_key="private_messages") -> Command:
    # 构建回复 发现问题的优先级高于通过
    message_id = runtime.state["review_reply_message_id"]
    if output.review_issues:
        message = AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="AI团队成员评审完成，发现问题，请根据评审意见修改设计",
            additional_kwargs={"priority": 1}
        )
    else:
        message = AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="AI团队成员评审通过，请整理风险和不确定的问题点反馈给客户。",
            additional_kwargs={"priority": 0}
        )
    return Command(update={
        # 重写消息列表 删除所有tool调用
        message_key: Overwrite(value=remove_tool_messages([*runtime.state[message_key], message])),
        "review_issues": [item.model_dump() for item in (output.review_issues or [])],
        "private_risks": [item.model_dump() for item in (output.risks or [])],
        "private_unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })
