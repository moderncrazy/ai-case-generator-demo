import uuid
from loguru import logger
from langgraph.types import Command
from langchain.messages import AIMessage
from langchain.tools import tool, BaseTool, ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.requirement_module_status import RequirementModuleStatus
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.utils import utils as cutils
from src.graphs.common.utils import workflow_tool_utils
from src.graphs.common.schemas import Issue, GenerateOptimizationPlanOutput, ReviewOptimizationPlanOutput
from src.graphs.requirement.module import utils
from src.graphs.requirement.module.schemas import (
    OptimizeRequirementModuleOutput,
    ReviewRequirementModuleOutput,
    OptimizeRequirementModuleIssueOutput
)
from src.repositories.project_repository import project_repository, ProjectUpdate


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_requirement_module_plan_output(
        logic: str,
        steps: list[str],
        questions: list[str] | None,
        risks: list[str] | None,
        runtime: ToolRuntime
) -> Command:
    """输出优化需求模块方案"""
    project_id = runtime.state["project_id"]
    output = GenerateOptimizationPlanOutput(logic=logic, steps=steps, questions=questions, risks=risks)
    message = cutils.format_generate_optimization_plan_output_to_str(output)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={"private_messages": [AIMessage(content=message, name=GroupMemberRole.PRODUCT.value)]})


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_requirement_module_plan_output(
        result: ReviewOptimizationPlanResult,
        message: str,
        feedbacks: list[Issue] | None,
        questions: list[Issue] | None,
        runtime: ToolRuntime
) -> Command:
    """输出审核优化需求模块方案"""
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationPlanOutput(result=result, message=message, feedbacks=feedbacks, questions=questions)
    result = workflow_tool_utils.review_optimization_plan_output(
        output, "review_optimization_requirement_module_plan_node", runtime)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return result


@tool(args_schema=OptimizeRequirementModuleOutput)
async def optimize_requirement_module_output(
        message: str,
        requirement_module_content: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出产品优化需求模块结果
    
    AI大模型使用此工具可完成单个需求模块的优化分析并输出结构化结果。
    
    **功能说明：**
    这是需求模块设计阶段的核心输出工具，用于：
    1. 对单个需求模块进行深度优化（补充细节、明确边界）
    2. 汇总风险点和不明确点供后续团队评审
    3. 更新状态中的模块内容
    4. 清空之前的问题记录，为评审做准备
    
    Args:
        message: str - 针对需求模块优化的总结以及给团队成员接下来review的留言
        requirement_module_content: str - 输出优化后需求模块内容（Markdown格式）
        risks: list[Issue] - 给客户提出的风险和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = OptimizeRequirementModuleOutput(
        message=message,
        requirement_module_content=requirement_module_content,
        risks=risks,
        unclear_points=unclear_points
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [
            AIMessage(content=output.message, name=GroupMemberRole.PRODUCT.value)
        ],
        "review_reply_message_id": str(uuid.uuid4()),
        "requirement_module_content": requirement_module_content,
        "requirement_module_issues": ReducerActionType.RESET,
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool(args_schema=ReviewRequirementModuleOutput)
async def review_requirement_module_output(
        requirement_module_issues: list[Issue],
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出评审需求模块结果
    
    AI大模型使用此工具可输出各角色（架构/后端/前端/测试等）对需求模块的评审意见。
    
    **功能说明：**
    这是需求模块设计阶段的评审输出工具，用于：
    1. 汇总各角色提出的问题和建议方案
    2. 根据是否发现问题设置不同的回复优先级（发现问题的优先级更高）
    3. 更新状态中的问题、风险、不明确点列表
    
    Args:
        requirement_module_issues: list[Issue] - 针对需求模块提出的问题和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        risks: list[Issue] - 给客户提出的风险和建议方案列表，结构同上
        unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    role = runtime.state["role"]
    project_id = runtime.state["project_id"]
    output = ReviewRequirementModuleOutput(
        requirement_module_issues=requirement_module_issues,
        risks=risks,
        unclear_points=unclear_points
    )
    # 构建回复 发现问题的优先级高于通过
    message_id = runtime.state["review_reply_message_id"]
    if requirement_module_issues:
        message = AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="评审完成，发现问题，请产品根据评审意见修改需求模块。",
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
        "requirement_module_issues": [item.model_dump() for item in (output.requirement_module_issues or [])],
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool(args_schema=OptimizeRequirementModuleIssueOutput)
async def optimize_requirement_module_issue_output(
        message: str,
        risks: list[Issue],
        unclear_points: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """整理输出需求模块问题结果
    
    AI大模型使用此工具可完成评审后的最终汇总，输出结构化的风险点和不明确点。
    
    **功能说明：**
    这是需求模块设计阶段的最终输出工具，用于：
    1. 汇总所有风险点和不明确点
    2. 将优化后的模块内容更新到需求模块列表
    3. 将最终需求模块列表保存到数据库
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
    output = OptimizeRequirementModuleIssueOutput(
        message=message,
        risks=risks,
        unclear_points=unclear_points
    )
    # 更新需求模块内容
    module_name = runtime.state["metadata"]["module"]
    module_content = runtime.state["requirement_module_content"]
    utils.update_module_content_by_name(module_name, module_content, runtime.state["requirement_modules"])
    # 保存需求模块
    await project_repository.update(
        runtime.state["project_id"],
        ProjectUpdate(requirement_module_design=gutils.to_json(runtime.state["requirement_modules"]))
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 更新需求模块入库")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": ReducerActionType.RESET,
        "messages": [AIMessage(content=output.message, name=GroupMemberRole.PRODUCT.value)],
        "requirement_modules": runtime.state["requirement_modules"],
        "risks": [item.model_dump() for item in (output.risks or [])],
        "unclear_points": [item.model_dump() for item in (output.unclear_points or [])],
    })


@tool
async def get_completed_requirement_modules(runtime: ToolRuntime) -> str:
    """获取已完成的需求模块列表
    
    AI大模型使用此工具可获取当前项目中已完成的需求模块列表。
    
    **功能说明：**
    从运行时状态中读取并返回已完成的需求模块列表，用于确保新模块设计与已完成模块保持一致性。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        模块序号：xxx
        模块名称：xxx
        模块状态：xxx
        模块描述：xxx
        模块内容：xxx
        
        ----------xxx end----------
        
        如果无已完成模块，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = cutils.format_state_requirement_modules_to_str(
        runtime.state.get("requirement_modules"),
        RequirementModuleStatus.COMPLETED
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_requirement_module(runtime: ToolRuntime) -> str:
    """获取优化后需求模块内容
    
    AI大模型使用此工具可获取当前正在设计的需求模块的详细信息。
    
    **功能说明：**
    从运行时状态中读取并返回当前模块的内容，用于了解上一版优化后的模块状态。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        模块序号：xxx
        模块名称：xxx
        模块状态：xxx
        模块描述：xxx
        模块内容：xxx
        
        如果当前模块不存在，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    module_name = runtime.state.get("metadata", {}).get("module", "")
    result = cutils.format_current_state_requirement_module_to_str(
        module_name,
        runtime.state.get("requirement_modules"),
        runtime.state.get("requirement_module_content")
    )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_requirement_module_issues(runtime: ToolRuntime) -> str:
    """获取需求模块评审意见列表
    
    AI大模型使用此工具可获取各角色对需求模块提出的评审意见。
    
    **功能说明：**
    从运行时状态中读取并返回需求模块的评审意见，用于了解之前评审发现的问题。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        问题：xxx
        建议方案：xxx
        
        如果无评审意见，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = cutils.format_issues_to_str(runtime.state.get("requirement_module_issues"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 专用方法
common_tool_list = [t for t in tool_list if
                    t.name not in [
                        optimize_requirement_module_output.name,
                        review_requirement_module_output.name,
                        optimize_requirement_module_issue_output.name
                    ]]
