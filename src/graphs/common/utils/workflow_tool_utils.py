from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime
from langchain.messages import ToolMessage, AIMessage

from src.utils import utils as gutils
from src.context import trans_id_ctx
from src.graphs.common.utils import utils
from src.graphs.common.utils import structured_output_utils
from src.graphs.common.schemas import  ReviewOptimizationPlanOutput
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult


def validate_review_optimization_plan_output_to_str(output: ReviewOptimizationPlanOutput) -> str:
    error_message = ""
    match output.result:
        case ReviewOptimizationPlanResult.REVISE:
            if not output.feedbacks:
                error_message = "审核结果为：revise 时，feedbacks 不能为空"
        case ReviewOptimizationPlanResult.ASK_QUESTION:
            if not output.feedbacks:
                error_message = "审核结果为：ask_question 时，questions 不能为空"
    return error_message


def review_optimization_plan_output(output: ReviewOptimizationPlanOutput, rollback_node: str, runtime: ToolRuntime,
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
            goto=rollback_node,
            update={message_key: [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
        )
    message = utils.format_review_optimization_plan_output_to_str(output)
    # 如果需要咨询客户则发消息给客户 否则继续
    if output.result == ReviewOptimizationPlanResult.ASK_QUESTION:
        return Command(update={
            "messages": [AIMessage(content=message, name=role.value)],
            message_key: ReducerActionType.RESET,
            "review_optimization_plan_result": output.result
        })
    else:
        return Command(update={
            message_key: [AIMessage(content=message, name=role.value)],
            "review_optimization_plan_result": output.result
        })
