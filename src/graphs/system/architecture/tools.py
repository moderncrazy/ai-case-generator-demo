import uuid
from loguru import logger
from langgraph.types import Command
from langchain.messages import AIMessage
from langchain.tools import tool, BaseTool, ToolRuntime

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.conversation_message_type import ConversationMessageType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.utils import utils as cutils
from src.graphs.common.utils import workflow_tool_utils
from src.graphs.common.schemas import (
    Issue,
    ReviewOptimizationDocToSummarizeOutput,
    ReviewOptimizationPlanOutput,
    GenerateOptimizationPlanOutput,
    SummarizeOptimizationDocIssueOutput,
)
from src.graphs.system.architecture.schemas import OptimizeSystemArchitectureOutput
from src.repositories.project_repository import project_repository, ProjectUpdate


@tool
async def get_system_architecture_content(runtime: ToolRuntime) -> str:
    """获取优化后系统架构内容
    
    AI大模型使用此工具可获取经过AI优化后的系统架构内容。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的系统架构内容。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即系统架构文档全文
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("system_architecture_content") \
             or runtime.state.get("optimized_architecture") \
             or const.EMPTY_ZH
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_system_architecture_plan_output(
        background: str,
        summary: str,
        logic: str,
        steps: list[str],
        questions: list[str] | None,
        risks: list[str] | None,
        runtime: ToolRuntime
) -> Command:
    """输出优化系统架构方案

    AI大模型使用此工具可完成系统架构优化计划的制定并输出结构化结果。

    **功能说明：**
    这是系统架构设计阶段的核心输出工具，用于：
    1. 分析需求，制定系统架构优化策略
    2. 明确优化步骤和执行顺序
    3. 识别潜在风险和待确认问题

    Args:
        background: str - 业务背景（项目名称、业务描述、用户诉求）
        summary: str - 本次优化的整体说明
        logic: str - 系统架构优化的整体思路和策略说明
        steps: list[str] - 系统架构优化的具体步骤列表
        questions: list[str] | None - 在优化过程中发现的待确认问题列表
        risks: list[str] | None - 系统架构设计或实现中可能存在的风险列表
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = GenerateOptimizationPlanOutput(
        background=background, summary=summary, logic=logic, steps=steps, questions=questions, risks=risks)
    command = workflow_tool_utils.generate_optimization_plan_output(output, runtime, GroupMemberRole.ARCHITECT)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_system_architecture_plan_output(
        result: ReviewOptimizationPlanResult,
        message: str,
        issues: list[Issue] | None,
        runtime: ToolRuntime
) -> Command:
    """输出审核优化系统架构方案

    AI大模型使用此工具可完成系统架构优化方案的审核并输出结构化结果。

    **功能说明：**
    这是系统架构设计阶段的方案审核输出工具，用于：
    1. 对系统架构优化方案进行评审
    2. 给出评审结论（通过/修正/向客户咨询）
    3. 提供反馈意见和改进建议
    4. 根据评审结果决定后续流程

    Args:
        result: ReviewOptimizationPlanResult - 评审结论（approve/revise/ask_question）
        message: str - 针对方案的评审意见或向客户咨询时的方案背景
        issues: list[Issue] | None - 对方案的反馈意见列表 或 审核过程中发现的待确认问题列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationPlanOutput(result=result, message=message, issues=issues)
    command = workflow_tool_utils.review_optimization_plan_output(output, runtime)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=OptimizeSystemArchitectureOutput)
async def optimize_system_architecture_output(
        message: str,
        system_architecture_content: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出架构优化系统架构结果

    AI大模型使用此工具可完成系统架构的优化分析并输出结构化结果。

    **功能说明：**
    这是系统架构设计阶段的核心输出工具，用于：
    1. 对系统架构进行优化（补充设计细节、调整技术选型等）
    2. 汇总风险点和不明确点供后续团队评审
    3. 更新状态中的架构内容
    4. 清空之前的问题记录，为评审做准备

    Args:
        message: str - 针对系统架构优化的总结以及给团队成员接下来review的留言
        system_architecture_content: str - 输出优化后系统架构内容（Markdown格式）
        risks: list[Issue] - 给客户提出的风险和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = OptimizeSystemArchitectureOutput(
        message=message,
        system_architecture_content=system_architecture_content,
        risks=risks,
        unclear_points=unclear_points
    )
    command = workflow_tool_utils.optimize_doc_to_summarize_output(
        output, runtime, GroupMemberRole.ARCHITECT, "system_architecture_content")
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=ReviewOptimizationDocToSummarizeOutput)
async def review_system_architecture_output(
        review_issues: list[Issue],
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出评审系统架构结果

    AI大模型使用此工具可输出各角色（后端/前端/SRE等）对系统架构的评审意见。

    **功能说明：**
    这是系统架构设计阶段的评审输出工具，用于：
    1. 汇总各角色提出的问题和建议方案
    2. 根据是否发现问题设置不同的回复优先级（发现问题的优先级更高）
    3. 更新状态中的问题、风险、不明确点列表

    Args:
        review_issues: list[Issue] - 针对系统架构提出的问题和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        risks: list[Issue] - 给客户提出的风险和建议方案列表，结构同上
        unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    role = runtime.state["role"]
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationDocToSummarizeOutput(
        review_issues=review_issues,
        risks=risks,
        unclear_points=unclear_points
    )
    command = workflow_tool_utils.review_optimization_doc_to_summarize_output(output, runtime)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=SummarizeOptimizationDocIssueOutput)
async def optimize_system_architecture_issue_output(
        message: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """整理输出系统架构问题结果

    AI大模型使用此工具可完成评审后的最终汇总，输出结构化的风险点和不明确点。

    **功能说明：**
    这是系统架构设计阶段的最终输出工具，用于：
    1. 汇总所有风险点和不明确点
    2. 如果原始架构为空，则将当前版本保存为原始架构
    3. 设置优化后的架构文档
    4. 生成给客户的会话消息

    Args:
        message: str - 给客户的会话消息
        risks: list[Issue] - 给客户提出的风险和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = SummarizeOptimizationDocIssueOutput(
        message=message,
        risks=risks,
        unclear_points=unclear_points
    )
    # 如果原始架构内容为空 则保存当前版本为原始架构
    if not runtime.state.get("original_architecture"):
        await project_repository.update(
            project_id,
            ProjectUpdate(architecture_design=runtime.state["system_architecture_content"])
        )
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始架构入库")
    cutils.send_custom_message(
        "架构文档已更新，快来看看吧！", GroupMemberRole.ARCHITECT, ConversationMessageType.NOTIFY)
    # 发送文档更新消息
    cutils.send_custom_message(
        ProjectDocType.SYSTEM_ARCHITECTURE.value,
        GroupMemberRole.PRODUCT,
        ConversationMessageType.DOC_UPDATE
    )
    # 更新系统架构内容
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": ReducerActionType.RESET,
        "private_risks": ReducerActionType.RESET,
        "private_unclear_points": ReducerActionType.RESET,
        "messages": [
            AIMessage(content=output.message, name=GroupMemberRole.ARCHITECT.value)
        ],
        "original_architecture": runtime.state.get("original_architecture")
                                 or runtime.state["system_architecture_content"],
        "optimized_architecture": runtime.state["system_architecture_content"],
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 后缀为 output 的方法
common_tool_list = [t for t in tool_list if not t.name.endswith("output")]
