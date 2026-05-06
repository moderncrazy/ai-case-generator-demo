import uuid
import inspect
from functools import partial

from loguru import logger
from typing import TypeVar
from abc import ABC, abstractmethod
from collections.abc import Callable
from langchain.messages import AIMessage
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command, Overwrite
from langchain_core.tools import StructuredTool, ArgsSchema

from src.context import trans_id_ctx
from src.enums.filtrate_optimization_doc_review_issue_result import FiltrateOptimizationDocReviewIssueResult
from src.enums.reducer_action_type import ReducerActionType
from src.utils import utils as gutils
from src.enums.group_member_role import GroupMemberRole
from src.enums.pm_review_optimization_doc_result import PMReviewOptimizationDocResult
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.utils import (
    utils,
    format_utils,
    message_utils,
    validate_utils,
    structured_output_utils
)
from src.graphs.common.schemas.output_schemas import (
    Issue,
    OptimizeDocBaseOutput,
    ReviewOptimizationDocOutput,
    ReviewOptimizationPlanOutput,
    PMReviewOptimizationDocOutput,
    GenerateOptimizationPlanOutput,
    FiltrateOptimizationDocReviewIssueOutput, OptimizeDocBringRiskBaseOutput, PMReviewOptimizationDocBringRiskOutput,
    ReviewOptimizationDocBringRiskOutput, FiltrateOptimizationDocReviewIssueBringRiskOutput,
)

# 类型变量定义
AnyOptimizeDocOutput = TypeVar("AnyOptimizeDocOutput", bound=OptimizeDocBaseOutput)
AnyReviewOptimizationDocOutput = TypeVar("AnyReviewOptimizationDocOutput", bound=ReviewOptimizationDocOutput)
AnyPMReviewOptimizationDocOutput = TypeVar("AnyPMReviewOptimizationDocOutput", bound=PMReviewOptimizationDocOutput)
AnyFiltrateOptimizationDocReviewIssueOutput = TypeVar("AnyFiltrateOptimizationDocReviewIssueOutput",
                                                      bound=FiltrateOptimizationDocReviewIssueOutput)


def optimize_doc_output(
        output: AnyOptimizeDocOutput,
        runtime: ToolRuntime,
        content_keys: list[str],
        error_message: str = None,
        messages_key: str = "private_messages"
) -> Command:
    """
    优化文档输出处理函数

    功能：
    1. 验证各角色提出的意见是否被清空
    2. 打包输出消息并更新状态

    Args:
        output: 优化文档输出对象（OptimizeDocBaseOutput 或其子类）
        runtime: 工具运行时对象
        content_keys: 需要从 output 中提取并更新到 state 的字段列表
        error_message: 自定义错误消息，如果有则打回
        messages_key: 消息存储的 state 键名

    Returns:
        Command: 状态更新命令

    State 更新：
        - node_rollback: 是否需要回滚
        - messages_key: 重写的消息列表
        - content_keys 中的字段: 从 output 中提取
        - review_issues: 重置为空列表
        - private_risks: 提取 output 中的 risks
        - private_unclear_points: 提取 output 中的 unclear_points
    """
    project_id = runtime.state["project_id"]
    project_progress = runtime.state["project_progress"]
    role = utils.get_role_optimization_by_project_progress(project_progress)
    # 外部传入自定义 error_message
    error_msg = error_message
    # 验证各角色提出的意见是否被清空
    if not error_msg and runtime.state.get("review_issues"):
        error_msg = f"检验失败：评审意见未全部解决，重新优化并解决全部评审意见"
    if error_msg:
        logger.warning(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 打回:{error_msg}")
        return structured_output_utils.rollback(
            runtime.tool_call_id, gutils.get_func_name(depth=2), output.model_dump(), error_message, messages_key)
    result_message = AIMessage(content=output.message, name=role.value)
    output_dict = output.model_dump()
    # 若是 BaseModel 则 转为 dict
    return Command(update={
        "node_rollback": False,
        # 重写消息列表 删除所有tool调用
        messages_key: Overwrite(
            value=message_utils.remove_tool_messages([*runtime.state[messages_key], result_message])),
        # 遍历 content_keys 将内容导入 state
        **{key: output_dict[key] for key in content_keys},
        "review_issues": ReducerActionType.RESET,
        # 若 output 存在 risks 和 unclear_points 则传
        "private_risks": [item.model_dump() for item in (getattr(output, "risks", None) or [])],
        "private_unclear_points": [item.model_dump() for item in (getattr(output, "unclear_points", None) or [])],
    })


async def pm_review_optimization_doc_output(
        output: AnyPMReviewOptimizationDocOutput,
        runtime: ToolRuntime,
        review_pass_callback: Callable[[ToolRuntime, Command], None],
        messages_key: str = "private_messages"
) -> Command:
    """
    PM 审核优化文档输出处理函数

    功能：
    1. 验证输出参数是否完整
    2. 根据 result 决定后续流程：
       - PASS: 发送消息给用户，重置审核状态
       - REVISE / GROUP_MEMBER_REVIEW: 打回给设计人员

    Args:
        output: PM 审核输出对象（PMReviewOptimizationDocOutput 或其子类）
        runtime: 工具运行时对象
        review_pass_callback: 审核成功回调函数
        messages_key: 消息存储的 state 键名

    Returns:
        Command: 状态更新命令

    State 更新（PASS）:
        - node_rollback: False
        - pm_review_optimization_doc_result: 审核结果
        - group_member_review_optimization_doc_roles: 需要审核的角色列表
        - messages: 发送给用户的消息
        - private_risks: 重置后设置为 output 中的 risks
        - private_unclear_points: 重置后设置为 output 中的 unclear_points
        - risks: 提取 output 中的 risks
        - unclear_points: 提取 output 中的 unclear_points

    State 更新（非 PASS）:
        - node_rollback: False
        - pm_review_optimization_doc_result: 审核结果
        - group_member_review_optimization_doc_roles: 需要审核的角色列表
        - messages_key: 重写的消息列表
        - review_reply_message_id: 新的消息 ID
        - review_issues: 从 output 提取
        - private_risks: 从 output 提取
        - private_unclear_points: 从 output 提取
    """
    project_id = runtime.state["project_id"]
    # 验证审核结果参数是否缺失
    error_message = validate_utils.validate_pm_review_optimization_doc_output_to_str(output)
    if error_message:
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 参数验证失败打回:{error_message}")
        return structured_output_utils.rollback(
            runtime.tool_call_id, gutils.get_func_name(depth=2), output.model_dump(), error_message, messages_key)
    result_message = AIMessage(content=output.message, name=GroupMemberRole.PM.value)
    command = Command(update={
        "node_rollback": False,
        "pm_review_optimization_doc_result": output.result,
        "group_member_review_optimization_doc_roles": output.review_roles,
    })
    if output.result == PMReviewOptimizationDocResult.PASS:
        command.update.update({
            "messages": [result_message],
            messages_key: ReducerActionType.RESET,
            "private_risks": ReducerActionType.RESET,
            "private_unclear_points": ReducerActionType.RESET,
            "risks": [item.model_dump() for item in (getattr(output, "risks", None) or [])],
            "unclear_points": [item.model_dump() for item in (getattr(output, "unclear_points", None) or [])],
        })
        # 审核成功执行回调函数
        await review_pass_callback(runtime, command)
    else:
        command.update.update({
            messages_key: Overwrite(
                value=message_utils.remove_tool_messages([*runtime.state[messages_key], result_message])),
            "review_reply_message_id": str(uuid.uuid4()),
            "review_issues": [item.model_dump() for item in (output.review_issues or [])],
            "private_risks": [item.model_dump() for item in (getattr(output, "risks", None) or [])],
            "private_unclear_points": [item.model_dump() for item in (getattr(output, "unclear_points", None) or [])],
        })
    return command


def group_member_review_optimization_doc_output(
        output: AnyReviewOptimizationDocOutput,
        runtime: ToolRuntime,
        messages_key: str = "private_messages"
) -> Command:
    """
    团队成员审核优化文档输出处理函数

    功能：
    1. 根据是否发现问题设置回复优先级
    2. 更新问题、风险、不明确点列表

    Args:
        output: 团队成员审核输出对象（ReviewOptimizationDocOutput 或其子类）
        runtime: 工具运行时对象
        messages_key: 消息存储的 state 键名

    Returns:
        Command: 状态更新命令

    State 更新：
        - messages_key: 重写的消息列表（消息带有 priority 标记）
        - review_issues: 从 output 提取
        - private_risks: 从 output 提取
        - private_unclear_points: 从 output 提取

    Priority 标记：
        - priority=1: 发现了问题，需要筛选
        - priority=0: 审核通过，无问题
    """
    # 构建回复 发现问题的优先级高于通过
    message_id = runtime.state["review_reply_message_id"]
    if output.review_issues:
        priority = 1
        content = "AI团队成员评审完成，发现问题，请筛选问题并判断是否需要优化设计。"
    else:
        priority = 0
        content = "AI团队成员评审通过，请整理风险和不确定的问题点反馈给客户。"
    message = AIMessage(
        id=message_id,
        name=GroupMemberRole.GROUP_MEMBER.value,
        content=content,
        additional_kwargs={"priority": priority}
    )
    return Command(update={
        # 重写消息列表 删除所有tool调用
        messages_key: Overwrite(value=message_utils.remove_tool_messages([*runtime.state[messages_key], message])),
        "review_issues": [item.model_dump() for item in (output.review_issues or [])],
        "private_risks": [item.model_dump() for item in (getattr(output, "risks", None) or [])],
        "private_unclear_points": [item.model_dump() for item in (getattr(output, "unclear_points", None) or [])],
    })


async def filtrate_optimization_doc_review_issue_output(
        output: AnyFiltrateOptimizationDocReviewIssueOutput,
        runtime: ToolRuntime,
        review_pass_callback: Callable[[ToolRuntime, Command], None],
        messages_key: str = "private_messages"
) -> Command:
    """
    筛选优化文档审核问题输出处理函数

    功能：
    1. 验证输出参数是否完整
    2. 根据 result 决定后续流程：
       - PASS: 发送消息给用户，清空临时数据
       - REVISE: 打回给设计人员重新优化

    Args:
        output: 筛选输出对象（FiltrateOptimizationDocReviewIssueOutput 或其子类）
        runtime: 工具运行时对象
        review_pass_callback: 审核成功回调函数
        messages_key: 消息存储的 state 键名

    Returns:
        Command: 状态更新命令

    State 更新（PASS）:
        - node_rollback: False
        - filtrate_optimization_doc_review_issue_result: 筛选结果
        - messages: 发送给用户的消息
        - private_risks: 重置
        - private_unclear_points: 重置
        - risks: 从 output 提取
        - unclear_points: 从 output 提取

    State 更新（REVISE）:
        - node_rollback: False
        - filtrate_optimization_doc_review_issue_result: 筛选结果
        - messages_key: 重写的消息列表
        - review_issues: 从 output 提取（需要设计人员重新处理）
        - private_risks: 从 output 提取
        - private_unclear_points: 从 output 提取
    """
    project_id = runtime.state["project_id"]
    # 验证审核结果参数是否缺失
    error_message = validate_utils.validate_filtrate_optimization_doc_review_issue_output_to_str(output)
    if error_message:
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 参数验证失败打回:{error_message}")
        return structured_output_utils.rollback(
            runtime.tool_call_id, gutils.get_func_name(depth=2), output.model_dump(), error_message, messages_key)
    result_message = AIMessage(content=output.message, name=GroupMemberRole.PM.value)
    command = Command(update={
        "node_rollback": False,
        "filtrate_optimization_doc_review_issue_result": output.result,
    })
    if output.result == FiltrateOptimizationDocReviewIssueResult.PASS:
        command.update.update({
            "messages": [result_message],
            messages_key: ReducerActionType.RESET,
            "private_risks": ReducerActionType.RESET,
            "private_unclear_points": ReducerActionType.RESET,
            "risks": [item.model_dump() for item in (getattr(output, "risks", None) or [])],
            "unclear_points": [item.model_dump() for item in (getattr(output, "unclear_points", None) or [])],
        })
        # 审核成功执行回调函数
        await review_pass_callback(runtime, command)
    else:
        command.update.update({
            messages_key: Overwrite(
                value=message_utils.remove_tool_messages([*runtime.state[messages_key], result_message])),
            "review_issues": [item.model_dump() for item in (output.review_issues or [])],
            "private_risks": [item.model_dump() for item in (getattr(output, "risks", None) or [])],
            "private_unclear_points": [item.model_dump() for item in (getattr(output, "unclear_points", None) or [])],
        })
    return command


class Tool:
    """将类内部方法转成 StructuredTool"""

    def __init__(self, func: Callable, args_schema: ArgsSchema):
        self.func = func
        self.args_schema = args_schema

    def __get__(self, instance, owner) -> StructuredTool | Callable:
        if instance is None:
            return self.func
        bound_func = partial(self.func, instance)
        bound_func.__doc__ = self.func.__doc__
        bound_func.__name__ = self.func.__name__
        is_async = inspect.iscoroutinefunction(self.func)
        return StructuredTool.from_function(
            None if is_async else bound_func,
            bound_func if is_async else None,
            args_schema=self.args_schema
        )


def tool(args_schema: ArgsSchema):
    """自定义注解 将类内部方法转成 StructuredTool"""

    def wrapper(func):
        return Tool(func, args_schema)

    return wrapper


class OptimizationDocOutputTools(ABC):

    def __init__(self, messages_key: str = "private_messages"):
        self.messages_key = messages_key

    @tool(args_schema=GenerateOptimizationPlanOutput)
    async def generate_optimization_plan_output(
            self,
            background: str,
            summary: str,
            logic: str,
            steps: list[str],
            questions: list[str] | None,
            risks: list[str] | None,
            runtime: ToolRuntime
    ) -> Command:
        """输出优化方案

        AI大模型使用此工具可完成优化方案的制定并输出结构化结果。

        **功能说明：**
        这是设计阶段的核心输出工具，用于：
        1. 分析、制定优化策略
        2. 明确优化步骤和执行顺序
        3. 识别潜在风险和待确认问题

        Args:
            background: str - 业务背景（项目名称、项目类型、业务描述、目标用户、使用场景、核心价值、约束条件、用户诉求）
            summary: str - 本次优化的整体说明
            logic: str - 需求模块优化的整体思路和策略说明
            steps: list[str] - 需求模块优化的具体步骤列表
            questions: list[str] | None - 在优化过程中发现的待确认问题列表
            risks: list[str] | None - 需求模块设计或实现中可能存在的风险列表
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        project_progress = runtime.state["project_progress"]
        role = utils.get_role_optimization_by_project_progress(project_progress)
        output = GenerateOptimizationPlanOutput(
            background=background,
            summary=summary,
            logic=logic,
            steps=steps,
            questions=questions or [],
            risks=risks or []
        )
        optimization_plan = format_utils.format_generate_optimization_plan_output_to_str(output)
        optimization_plan_and_question = format_utils.format_generate_optimization_plan_and_question_output_to_str(
            output)
        result_message = AIMessage(content=optimization_plan_and_question, name=role.value)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return Command(update={
            "optimization_plan_content": optimization_plan,
            # 重写消息列表 删除所有tool调用
            messages_key: Overwrite(
                value=message_utils.remove_tool_messages([*runtime.state[messages_key], result_message]))
        })

    @tool(args_schema=ReviewOptimizationPlanOutput)
    async def review_optimization_plan_output(
            self,
            result: ReviewOptimizationPlanResult,
            message: str,
            issues: list[Issue] | None,
            runtime: ToolRuntime
    ) -> Command:
        """输出审核优化方案工具

        AI大模型使用此工具可完成优化方案的审核并输出结构化结果。

        功能说明：
        这是设计阶段的方案审核输出工具，用于：
        1. 对优化方案进行评审
        2. 给出评审结论（通过/修正/向客户咨询）
        3. 提供反馈意见和改进建议
        4. 根据评审结果决定后续流程

        Args:
            result: ReviewOptimizationPlanResult - 评审结论
                - approve: 批准，继续执行优化
                - revise: 修正，需要重新设计
                - ask_question: 向人类咨询，需要用户确认后才能继续
            message: str - 针对方案的评审意见或向客户咨询时的方案背景
                - 审核通过时：简要说明通过原因
                - 审核修正时：说明需要修改的原因
                - 向用户咨询时：说明需要咨询的背景和问题
            issues: list[Issue] | None - 对方案的反馈意见列表
                - content: 问题描述
                - propose: 建议方案
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令
                - ask_question: 发送消息给用户，重置临时数据
                - approve: 重写消息，继续执行优化
                - revise: 重写消息，要求重新设计
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        role = GroupMemberRole.PM
        output = ReviewOptimizationPlanOutput(
            result=result,
            message=message,
            issues=issues or []
        )
        # 验证审核结果参数是否缺失
        error_message = validate_utils.validate_review_optimization_plan_output_to_str(output)
        if error_message:
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 参数验证失败打回:{error_message}")
            # 打回修复
            return structured_output_utils.rollback(
                runtime.tool_call_id,
                gutils.get_func_name(),
                output.model_dump(),
                error_message,
                messages_key=messages_key
            )
        update_state: dict = {
            "node_rollback": False,
            "review_optimization_plan_result": output.result
        }
        format_message = format_utils.format_review_optimization_plan_output_to_str(output)
        # 如果需要咨询客户则发消息给客户 否则继续
        if output.result == ReviewOptimizationPlanResult.ASK_QUESTION:
            update_state.update({
                "messages": [AIMessage(content=format_message, name=role.value)],
                messages_key: ReducerActionType.RESET,
                "private_risks": ReducerActionType.RESET,
                "private_unclear_points": ReducerActionType.RESET,
            })
        else:
            if output.result == ReviewOptimizationPlanResult.APPROVE:
                format_message = f"优化方案AI审核的结果如下：\n{format_message}\n**请根据AI生成的具体优化方案进行优化**"
            else:
                format_message = f"优化方案AI审核的结果如下：\n{format_message}\n**请根据上述意见重新设计方案**"
            result_message = AIMessage(content=format_message, name=role.value)
            update_state.update({
                messages_key: Overwrite(
                    value=message_utils.remove_tool_messages([*runtime.state[messages_key], result_message]))
            })
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return Command(update=update_state)

    # @tool(args_schema=OptimizeDocBaseOutput)
    @abstractmethod
    async def optimize_doc_output(
            self,
            message: str,
            runtime: ToolRuntime,
            **kwargs
    ) -> Command:
        """输出产品优化结果工具（抽象方法）

        AI大模型使用此工具可完成优化分析并输出结构化结果。

        功能说明：
        这是设计阶段的核心输出工具，用于：
        1. 对文档进行深度优化（补充细节、明确边界）
        2. 汇总风险点和不明确点供后续团队评审

        Args:
            message: str - 针对需求模块优化的总结以及给团队成员接下来review的留言
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
            **kwargs: 可传需要 args_schema 定义中的其它参数

        Returns:
            Command: 状态更新命令

        注意：此方法为抽象方法，子类必须实现
        """
        # messages_key = self.messages_key
        # project_id = runtime.state["project_id"]
        # output = OptimizeDocBaseOutput(message=message)
        # command = optimize_doc_output(output, runtime, ["xxx"], error_message, messages_key)
        # logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        # return command
        pass

    @tool(args_schema=PMReviewOptimizationDocOutput)
    async def pm_review_optimization_doc_output(
            self,
            result: PMReviewOptimizationDocResult,
            message: str,
            review_roles: list[GroupMemberRole] | None,
            review_issues: list[Issue] | None,
            runtime: ToolRuntime,
    ) -> Command:
        """PM 输出评审需求模块结果工具

        AI大模型使用此工具输出 PM 对设计文档的审核结果。

        功能说明：
        1. PM 审核设计文档
        2. 决定是否需要团队成员进一步审核
        3. 记录审核意见

        Args:
            result: PMReviewOptimizationDocResult - PM 审核结果
                - pass: 审核通过，直接给用户
                - revise: 需要修改，返回设计阶段
                - group_member_review: 需要团队成员进一步审核
            message: str - 给客户/设计人员/审核团队的话
                - pass: 简要说明通过原因
                - revise: 说明需要修改的原因
                - group_member_review: 说明为什么需要团队成员审核
            review_roles: list[GroupMemberRole] | None - 需要参与审核的角色列表
                - 当 result=group_member_review 时必须指定
                - 可选值：architect、backend、frontend、test、dba、sre
            review_issues: list[Issue] | None - 发现的问题和建议方案
                - content: 问题描述
                - propose: 建议方案
                - 当 result=revise 时必须包含
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = PMReviewOptimizationDocOutput(
            result=result,
            message=message,
            review_roles=review_roles or [],
            review_issues=review_issues or [],
        )
        command = await pm_review_optimization_doc_output(output, runtime, self.review_pass_callback, messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    @tool(args_schema=ReviewOptimizationDocOutput)
    async def group_member_review_optimization_doc_output(
            self,
            review_issues: list[Issue] | None,
            runtime: ToolRuntime
    ) -> Command:
        """输出团队成员评审结果工具

        AI大模型使用此工具输出各角色（架构/后端/前端/测试等）对设计文档的评审意见。

        功能说明：
        1. 汇总各角色提出的问题和建议方案
        2. 根据是否发现问题设置不同的回复优先级（发现问题的优先级更高）
        3. 更新状态中的问题、风险、不明确点列表

        Args:
            review_issues: list[Issue] - 针对设计文档提出的问题和建议方案列表
                - content: str - 问题描述
                - propose: str - 建议方案
                - 为空表示审核通过
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        role = runtime.state["role"]
        project_id = runtime.state["project_id"]
        output = ReviewOptimizationDocOutput(
            review_issues=review_issues or [],
        )
        command = group_member_review_optimization_doc_output(output, runtime, messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
        return command

    @tool(args_schema=FiltrateOptimizationDocReviewIssueOutput)
    async def filtrate_optimization_doc_review_issue_output(
            self,
            result: FiltrateOptimizationDocReviewIssueResult,
            message: str,
            review_issues: list[Issue] | None,
            runtime: ToolRuntime
    ) -> Command:
        """整理输出需求模块问题结果工具

        AI大模型使用此工具可完成评审后的最终汇总，输出结构化的风险点和不明确点。

        功能说明：
        这是需求模块设计阶段的最终输出工具，用于：
        1. 汇总所有风险点和不明确点
        2. 将优化后的模块内容更新到需求模块列表
        3. 将最终需求模块列表保存到数据库
        4. 生成给客户的会话消息

        Args:
            result: FiltrateOptimizationDocReviewIssueResult - 筛选结果
                - pass: 审核问题筛选完成，直接给用户
                - revise: 需要重新优化设计
            message: str - 给客户或设计人员的话
                - pass: 告知筛选结果，如有风险或待确认问题则一并反馈
                - revise: 说明需要修改的原因
            review_issues: list[Issue] - 针对设计文档提出的问题和建议方案列表
                - content: str - 问题描述
                - propose: str - 建议方案
                - 为空表示审核通过
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令

        注意：此方法为抽象方法，子类必须实现
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = FiltrateOptimizationDocReviewIssueOutput(
            result=result,
            message=message,
            review_issues=review_issues or [],
        )
        command = await filtrate_optimization_doc_review_issue_output(
            output, runtime, self.review_pass_callback, messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    @abstractmethod
    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        """审核通过持久化文档并回传数据至主图

        流程审核通过后会执行该方法
            1. 执行需要持久化的步骤
            2. 回传给主图的参数更新至command
        """
        pass


class OptimizationDocBringRiskOutputTools(OptimizationDocOutputTools):

    # @tool(args_schema=OptimizeDocBringRiskBaseOutput)
    @abstractmethod
    async def optimize_doc_output(
            self,
            message: str,
            risks: list[Issue] | None,
            unclear_points: list[Issue] | None,
            runtime: ToolRuntime,
            **kwargs
    ) -> Command:
        """输出产品优化结果工具（带风险版本）

        AI大模型使用此工具可完成优化分析并输出结构化结果。

        功能说明：
        这是设计阶段的核心输出工具，用于：
        1. 对文档进行深度优化（补充细节、明确边界）
        2. 汇总风险点和不明确点供后续团队评审

        Args:
            message: str - 针对需求模块优化的总结以及给团队成员接下来review的留言
            risks: list[Issue] - 给客户提出的风险和建议方案列表
                - content: str - 风险描述
                - propose: str - 建议方案
            unclear_points: list[Issue] | None - 需求中不明确的问题和建议方案列表
                - content: str - 问题描述
                - propose: str - 建议方案
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
            **kwargs: 可传需要 args_schema 定义中的其它参数

        Returns:
            Command: 状态更新命令

        注意：此方法为抽象方法，子类必须实现
        """
        # messages_key = self.messages_key
        # project_id = runtime.state["project_id"]
        # output = OptimizeDocBringRiskBaseOutput(
        #     message=message,
        #     risks=risks or [],
        #     unclear_points=unclear_points or [],
        # )
        # command = optimize_doc_output(output, runtime, ["xxx"], error_message, messages_key)
        # logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        # return command
        pass

    @tool(args_schema=PMReviewOptimizationDocBringRiskOutput)
    async def pm_review_optimization_doc_output(
            self,
            result: PMReviewOptimizationDocResult,
            message: str,
            review_roles: list[GroupMemberRole] | None,
            review_issues: list[Issue] | None,
            risks: list[Issue] | None,
            unclear_points: list[Issue] | None,
            runtime: ToolRuntime,
    ) -> Command:
        """PM 输出评审需求模块结果工具（带风险版本）

        AI大模型使用此工具输出 PM 对设计文档的审核结果。

        功能说明：
        1. PM 审核设计文档
        2. 决定是否需要团队成员进一步审核
        3. 记录审核意见
        4. 汇总风险点和待确认问题

        Args:
            result: PMReviewOptimizationDocResult - PM 审核结果
                - pass: 审核通过，直接给用户
                - revise: 需要修改，返回设计阶段
                - group_member_review: 需要团队成员进一步审核
            message: str - 给客户/设计人员/审核团队的话
                - pass: 简要说明通过原因
                - revise: 说明需要修改的原因
                - group_member_review: 说明为什么需要团队成员审核
            review_roles: list[GroupMemberRole] | None - 需要参与审核的角色列表
                - 当 result=group_member_review 时必须指定
            review_issues: list[Issue] | None - 发现的问题和建议方案
                - content: 问题描述
                - propose: 建议方案
                - 当 result=revise 时必须包含
            risks: list[Issue] | None - 给客户提出的风险和建议方案
            unclear_points: list[Issue] | None - 需求中不明确的问题和建议方案
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = PMReviewOptimizationDocBringRiskOutput(
            result=result,
            message=message,
            review_roles=review_roles or [],
            review_issues=review_issues or [],
            risks=risks or [],
            unclear_points=unclear_points or [],
        )
        command = await pm_review_optimization_doc_output(output, runtime, self.review_pass_callback, messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    @tool(args_schema=ReviewOptimizationDocBringRiskOutput)
    async def group_member_review_optimization_doc_output(
            self,
            review_issues: list[Issue] | None,
            risks: list[Issue] | None,
            unclear_points: list[Issue] | None,
            runtime: ToolRuntime
    ) -> Command:
        """输出团队成员评审结果工具（带风险版本）

        AI大模型使用此工具输出各角色对设计文档的评审意见。

        功能说明：
        1. 汇总各角色提出的问题和建议方案
        2. 根据是否发现问题设置不同的回复优先级
        3. 更新状态中的问题、风险、不明确点列表

        Args:
            review_issues: list[Issue] - 针对设计文档提出的问题和建议方案
                - content: str - 问题描述
                - propose: str - 建议方案
            risks: list[Issue] - 给客户提出的风险和建议方案
                - content: str - 问题描述
                - propose: str - 建议方案
            unclear_points: list[Issue] - 需求中不明确的问题和建议方案
                - content: str - 问题描述
                - propose: str - 建议方案
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令
        """
        messages_key = self.messages_key
        role = runtime.state["role"]
        project_id = runtime.state["project_id"]
        output = ReviewOptimizationDocBringRiskOutput(
            review_issues=review_issues or [],
            risks=risks or [],
            unclear_points=unclear_points or [],
        )
        command = group_member_review_optimization_doc_output(output, runtime, messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
        return command

    @tool(args_schema=FiltrateOptimizationDocReviewIssueBringRiskOutput)
    async def filtrate_optimization_doc_review_issue_output(
            self,
            result: FiltrateOptimizationDocReviewIssueResult,
            message: str,
            review_issues: list[Issue] | None,
            risks: list[Issue] | None,
            unclear_points: list[Issue] | None,
            runtime: ToolRuntime
    ) -> Command:
        """整理输出需求模块问题结果工具

        AI大模型使用此工具可完成评审后的最终汇总，输出结构化的风险点和不明确点。

        功能说明：
        1. 汇总所有风险点和不明确点
        2. 将优化后的模块内容更新到需求模块列表
        3. 将最终需求模块列表保存到数据库
        4. 生成给客户的会话消息

        Args:
            result: FiltrateOptimizationDocReviewIssueResult - 筛选结果
                - pass: 审核问题筛选完成，直接给用户
                - revise: 需要重新优化设计
            message: str - 给客户或设计人员的话
            review_issues: list[Issue] - 针对设计文档提出的问题和建议方案
                - content: str - 问题描述
                - propose: str - 建议方案
            risks: list[Issue] - 给客户提出的风险和建议方案
                - content: str - 问题描述
                - propose: str - 建议方案
            unclear_points: list[Issue] - 需求中不明确的问题和建议方案
                - content: str - 问题描述
                - propose: str - 建议方案
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = FiltrateOptimizationDocReviewIssueBringRiskOutput(
            result=result,
            message=message,
            review_issues=review_issues or [],
            risks=risks or [],
            unclear_points=unclear_points or [],
        )
        command = await filtrate_optimization_doc_review_issue_output(
            output, runtime, self.review_pass_callback, messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command


AnyOptimizationDocOutputTools = TypeVar("AnyOptimizationDocOutputTools", bound=OptimizationDocOutputTools)
