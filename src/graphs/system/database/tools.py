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
from src.graphs.system.database.schemas import (
    OptimizeSystemDatabaseOutput,
    ReviewSystemDatabaseOutput,
)


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_system_database_plan_output(
        logic: str,
        steps: list[str],
        questions: list[str] | None,
        risks: list[str] | None,
        runtime: ToolRuntime
) -> Command:
    """输出优化系统接口方案"""
    project_id = runtime.state["project_id"]
    output = GenerateOptimizationPlanOutput(logic=logic, steps=steps, questions=questions, risks=risks)
    message = cutils.format_generate_optimization_plan_output_to_str(output)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={"private_messages": [AIMessage(content=message, name=GroupMemberRole.DBA.value)]})


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_system_database_plan_output(
        result: ReviewOptimizationPlanResult,
        message: str,
        feedbacks: list[Issue] | None,
        questions: list[Issue] | None,
        runtime: ToolRuntime
) -> Command:
    """输出审核优化系统接口方案"""
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationPlanOutput(result=result, message=message, feedbacks=feedbacks, questions=questions)
    result = workflow_tool_utils.review_optimization_plan_output(
        output, "review_optimization_system_database_plan_node", runtime)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return result


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
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [AIMessage(content=output.message, name=GroupMemberRole.DBA.value)],
        "review_reply_message_id": str(uuid.uuid4()),
        "system_database_content": system_database_content,
        "system_database_issues": ReducerActionType.RESET,
    })


@tool(args_schema=ReviewSystemDatabaseOutput)
async def review_system_database_output(
        system_database_issues: list[Issue],
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
        system_database_issues: list[Issue] - 针对系统数据库文档提出的问题和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    role = runtime.state["role"]
    project_id = runtime.state["project_id"]
    output = ReviewSystemDatabaseOutput(
        system_database_issues=system_database_issues,
    )
    # 发现问题构建回复
    messages = []
    message_id = runtime.state["review_reply_message_id"]
    if system_database_issues:
        messages.append(AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="评审完成，发现问题，请DBA根据评审意见修改系统数据库文档。",
            additional_kwargs={"priority": 1}
        ))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": messages,
        "system_database_issues": [item.model_dump() for item in (output.system_database_issues or [])],
    })


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


@tool
async def get_system_database_issues(runtime: ToolRuntime) -> str:
    """获取数据库评审意见列表
    
    AI大模型使用此工具可获取各角色对数据库文档提出的评审意见。
    
    **功能说明：**
    从运行时状态中读取并返回数据库的评审意见，用于了解之前评审发现的问题。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        问题：xxx
        建议方案：xxx
        
        如果无评审意见，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = cutils.format_issues_to_str(runtime.state.get("system_database_issues"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 专用方法
common_tool_list = [t for t in tool_list if
                    t.name not in [
                        optimize_system_database_output.name,
                        review_system_database_output.name,
                    ]]
