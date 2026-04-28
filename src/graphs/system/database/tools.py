from loguru import logger
from langgraph.types import Command
from langchain.messages import AIMessage
from langchain.tools import tool, BaseTool, ToolRuntime

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.utils import utils as cutils
from src.graphs.common.utils import workflow_tool_utils
from src.graphs.common.schemas import (
    Issue,
    ReviewOptimizationDocOutput,
    ReviewOptimizationPlanOutput,
    GenerateOptimizationPlanOutput,
)
from src.graphs.system.database.schemas import OptimizeSystemDatabaseOutput


@tool
async def get_system_database_content(runtime: ToolRuntime) -> str:
    """获取优化后数据库内容
    
    AI大模型使用此工具可获取经过AI优化后的数据库内容。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的数据库内容。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即数据库文档全文
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("system_database_content") \
             or runtime.state.get("optimized_database") \
             or const.EMPTY_ZH
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_system_database_plan_output(
        background: str,
        summary: str,
        logic: str,
        steps: list[str],
        questions: list[str] | None,
        risks: list[str] | None,
        runtime: ToolRuntime
) -> Command:
    """输出优化系统数据库方案

    AI大模型使用此工具可完成系统数据库优化计划的制定并输出结构化结果。

    **功能说明：**
    这是系统数据库设计阶段的核心输出工具，用于：
    1. 分析需求，制定系统数据库优化策略
    2. 明确优化步骤和执行顺序
    3. 识别潜在风险和待确认问题

    Args:
        background: str - 业务背景（项目名称、业务描述、用户诉求）
        summary: str - 本次优化的整体说明
        logic: str - 系统数据库优化的整体思路和策略说明
        steps: list[str] - 系统数据库优化的具体步骤列表
        questions: list[str] | None - 在优化过程中发现的待确认问题列表
        risks: list[str] | None - 系统数据库设计或实现中可能存在的风险列表
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = GenerateOptimizationPlanOutput(
        background=background, summary=summary, logic=logic, steps=steps, questions=questions, risks=risks)
    command = workflow_tool_utils.generate_optimization_plan_output(output, runtime, GroupMemberRole.DBA)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_system_database_plan_output(
        result: ReviewOptimizationPlanResult,
        message: str,
        issues: list[Issue] | None,
        runtime: ToolRuntime
) -> Command:
    """输出审核优化系统数据库方案

    AI大模型使用此工具可完成系统数据库优化方案的审核并输出结构化结果。

    **功能说明：**
    这是系统数据库设计阶段的方案审核输出工具，用于：
    1. 对系统数据库优化方案进行评审
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


@tool(args_schema=OptimizeSystemDatabaseOutput)
async def optimize_system_database_output(
        message: str,
        system_database_content: str,
        runtime: ToolRuntime
) -> Command:
    """输出 DBA 优化系统数据库文档结果

    AI大模型使用此工具可完成系统数据库文档的优化分析并输出结构化结果。

    **功能说明：**
    这是系统数据库设计阶段的核心输出工具，用于：
    1. 对系统数据库文档进行优化（补充字段注释、优化表结构等）
    2. 更新状态中的数据库文档内容
    3. 清空之前的问题记录，为评审做准备

    Args:
        message: str - 针对系统数据库文档优化的总结以及给团队成员接下来review的留言
        system_database_content: str - 输出优化后系统数据库文档内容（Markdown格式，通常包含SQL语句）
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = OptimizeSystemDatabaseOutput(
        message=message,
        system_database_content=system_database_content,
    )
    command = workflow_tool_utils.optimize_doc_output(output, runtime, GroupMemberRole.DBA, "system_database_content")
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=ReviewOptimizationDocOutput)
async def review_system_database_output(
        review_issues: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出评审系统数据库文档结果

    AI大模型使用此工具可输出各角色（后端/SRE/DBA等）对系统数据库文档的评审意见。

    **功能说明：**
    这是系统数据库设计阶段的评审输出工具，用于：
    1. 汇总各角色提出的问题和建议方案
    2. 根据是否发现问题设置不同的回复优先级（发现问题的优先级更高）
    3. 更新状态中的数据库问题列表

    Args:
        review_issues: list[Issue] - 针对系统数据库文档提出的问题和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    role = runtime.state["role"]
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationDocOutput(
        review_issues=review_issues,
    )
    # 发现问题构建回复
    command = workflow_tool_utils.review_optimization_doc_output(output, runtime)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
    return command


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 后缀为 output 的方法
common_tool_list = [t for t in tool_list if not t.name.endswith("output")]
