import uuid
from loguru import logger
from langgraph.types import Command
from langchain.messages import AIMessage
from langchain.tools import tool, BaseTool, ToolRuntime

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.utils import utils as cutils
from src.graphs.common.utils import workflow_tool_utils
from src.graphs.common.schemas import Issue, GenerateOptimizationPlanOutput, ReviewOptimizationPlanOutput
from src.graphs.requirement.overall.schemas import (
    OptimizeRequirementOverallOutput,
    ReviewRequirementOverallOutput,
    OptimizeRequirementOverallIssueOutput
)
from src.repositories.project_repository import project_repository, ProjectUpdate


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_requirement_overall_plan_output(
        logic: str,
        steps: list[str],
        questions: list[str] | None,
        risks: list[str] | None,
        runtime: ToolRuntime
) -> Command:
    """输出优化需求整体文档方案"""
    project_id = runtime.state["project_id"]
    output = GenerateOptimizationPlanOutput(logic=logic, steps=steps, questions=questions, risks=risks)
    message = cutils.format_generate_optimization_plan_output_to_str(output)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={"private_messages": [AIMessage(content=message, name=GroupMemberRole.PRODUCT.value)]})


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_requirement_overall_plan_output(
        result: ReviewOptimizationPlanResult,
        message: str,
        feedbacks: list[Issue] | None,
        questions: list[Issue] | None,
        runtime: ToolRuntime
) -> Command:
    """输出审核优化需求整体文档方案"""
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationPlanOutput(result=result, message=message, feedbacks=feedbacks, questions=questions)
    result = workflow_tool_utils.review_optimization_plan_output(
        output, "review_optimization_requirement_overall_plan_node", runtime)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return result


@tool(args_schema=OptimizeRequirementOverallOutput)
async def optimize_requirement_overall_output(
        message: str,
        requirement_overall_content: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出产品优化需求文档结果
    
    AI大模型使用此工具可完成整体需求文档的优化分析并输出结构化结果。
    
    **功能说明：**
    这是需求整体设计阶段的核心输出工具，用于：
    1. 对需求文档进行优化（补充细节、明确边界、修正逻辑）
    2. 汇总风险点和不明确点供后续团队评审
    3. 更新状态中的文档内容
    4. 清空之前的问题记录，为评审做准备
    
    Args:
        message: str - 针对需求文档优化的总结以及给团队成员接下来review的留言
        requirement_overall_content: str - 输出优化后需求文档内容（Markdown格式）
        risks: list[Issue] - 给客户提出的风险和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = OptimizeRequirementOverallOutput(
        message=message,
        requirement_overall_content=requirement_overall_content,
        risks=risks,
        unclear_points=unclear_points
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [AIMessage(content=output.message, name=GroupMemberRole.PRODUCT.value)],
        "review_reply_message_id": str(uuid.uuid4()),
        "requirement_overall_content": output.requirement_overall_content,
        "requirement_issues": ReducerActionType.RESET,
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool(args_schema=ReviewRequirementOverallOutput)
async def review_requirement_overall_output(
        requirement_overall_issues: list[Issue],
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出评审需求文档结果
    
    AI大模型使用此工具可输出各角色（架构/后端/前端/测试等）对需求文档的评审意见。
    
    **功能说明：**
    这是需求整体设计阶段的评审输出工具，用于：
    1. 汇总各角色提出的问题和建议方案
    2. 根据是否发现问题设置不同的回复优先级（发现问题的优先级更高）
    3. 更新状态中的问题、风险、不明确点列表
    
    Args:
        requirement_overall_issues: list[Issue] - 针对需求文档提出的问题和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        risks: list[Issue] - 给客户提出的风险和建议方案列表，结构同上
        unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    role = runtime.state["role"]
    project_id = runtime.state["project_id"]
    output = ReviewRequirementOverallOutput(
        requirement_overall_issues=requirement_overall_issues,
        risks=risks,
        unclear_points=unclear_points
    )
    # 构建回复 发现问题的优先级高于通过
    message_id = runtime.state["review_reply_message_id"]
    if requirement_overall_issues:
        message = AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="评审完成，发现问题，请产品根据评审意见修改需求文档。",
            additional_kwargs={"priority": 1}
        )
    else:
        message = AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="需求文档评审通过，请整理风险和不确定的问题点反馈给客户。",
            additional_kwargs={"priority": 0}
        )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [message],
        "requirement_overall_issues": [item.model_dump() for item in (output.requirement_overall_issues or [])],
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool(args_schema=OptimizeRequirementOverallIssueOutput)
async def optimize_requirement_overall_issue_output(
        message: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """整理输出需求文档问题结果
    
    AI大模型使用此工具可完成评审后的最终汇总，输出结构化的风险点和不明确点。
    
    **功能说明：**
    这是需求整体设计阶段的最终输出工具，用于：
    1. 汇总所有风险点和不明确点
    2. 如果原始需求为空，则将当前版本保存为原始需求
    3. 设置优化后的需求文档
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
    output = OptimizeRequirementOverallIssueOutput(
        message=message,
        risks=risks,
        unclear_points=unclear_points
    )
    # 如果原始需求内容为空 则保存当前版本为原始需求
    if not runtime.state.get("original_requirement"):
        await project_repository.update(
            project_id,
            ProjectUpdate(requirement_overall_design=runtime.state["requirement_overall_content"])
        )
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始需求入库")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": ReducerActionType.RESET,
        "messages": [
            AIMessage(content=output.message, name=GroupMemberRole.PRODUCT.value)
        ],
        "original_requirement": runtime.state.get("original_requirement")
                                or runtime.state["requirement_overall_content"],
        "optimized_requirement": runtime.state["requirement_overall_content"],
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool
async def get_requirement_overall_content(runtime: ToolRuntime) -> str:
    """获取优化后需求文档内容
    
    AI大模型使用此工具可获取经过AI优化后的需求文档内容。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的需求文档。
    优化内容包括：补全不明确点、修正逻辑、补充细节等。
    
    获取顺序：
    1. 优先取 `requirement_overall_content`（经过优化的内容）
    2. 其次取 `optimized_requirement`（优化后的需求）
    3. 如果都为空，返回"（空）"
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即优化后的需求文档全文
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("requirement_overall_content") \
             or runtime.state.get("optimized_requirement") \
             or const.EMPTY_ZH
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_requirement_overall_issues(runtime: ToolRuntime) -> str:
    """获取需求文档评审意见列表
    
    AI大模型使用此工具可获取各角色对需求文档提出的评审意见。
    
    **功能说明：**
    从运行时状态中读取并返回需求文档的评审意见，用于了解之前评审发现的问题。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        问题：xxx
        建议方案：xxx
        
        如果无评审意见，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = cutils.format_issues_to_str(runtime.state.get("requirement_overall_issues"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 专用方法
common_tool_list = [t for t in tool_list if
                    t.name not in [
                        optimize_requirement_overall_output.name,
                        review_requirement_overall_output.name,
                        optimize_requirement_overall_issue_output.name,
                        generate_optimization_requirement_overall_plan_output.name,
                        review_optimization_requirement_overall_plan_output.name,
                    ]]
