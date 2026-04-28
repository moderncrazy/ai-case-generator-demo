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
from src.graphs.system.api import utils
from src.graphs.system.api.schemas import SystemApi, OptimizeSystemApiOutput


@tool
async def get_system_apis(runtime: ToolRuntime) -> str:
    """获取优化后系统接口列表
    
    AI大模型使用此工具可获取经过AI优化后的系统接口列表。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的系统接口列表。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        接口序号：xxx
        模块ID：xxx
        接口名称：xxx
        请求方法：xxx
        请求路径：xxx
        接口描述：xxx
        请求头参数：xxx
        URL参数：xxx
        请求体参数：xxx
        响应格式：xxx
        
        ----------xxx end----------
        
        如果无接口，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    apis = runtime.state.get("system_apis") or runtime.state.get("optimized_apis")
    result = cutils.format_state_apis_to_str(apis) if apis else const.EMPTY_ZH
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_system_api_plan_output(
        background: str,
        summary: str,
        logic: str,
        steps: list[str],
        questions: list[str] | None,
        risks: list[str] | None,
        runtime: ToolRuntime
) -> Command:
    """输出优化系统接口方案

    AI大模型使用此工具可完成系统接口优化计划的制定并输出结构化结果。

    **功能说明：**
    这是系统接口设计阶段的核心输出工具，用于：
    1. 分析需求和系统模块，制定系统接口优化策略
    2. 明确优化步骤和执行顺序
    3. 识别潜在风险和待确认问题

    Args:
        background: str - 业务背景（项目名称、业务描述、用户诉求）
        summary: str - 本次优化的整体说明
        logic: str - 系统接口优化的整体思路和策略说明
        steps: list[str] - 系统接口优化的具体步骤列表
        questions: list[str] | None - 在优化过程中发现的待确认问题列表
        risks: list[str] | None - 系统接口设计或实现中可能存在的风险列表
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = GenerateOptimizationPlanOutput(
        background=background, summary=summary, logic=logic, steps=steps, questions=questions, risks=risks)
    command = workflow_tool_utils.generate_optimization_plan_output(output, runtime, GroupMemberRole.BACKEND)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_system_api_plan_output(
        result: ReviewOptimizationPlanResult,
        message: str,
        issues: list[Issue] | None,
        runtime: ToolRuntime
) -> Command:
    """输出审核优化系统接口方案

    AI大模型使用此工具可完成系统接口优化方案的审核并输出结构化结果。

    **功能说明：**
    这是系统接口设计阶段的方案审核输出工具，用于：
    1. 对系统接口优化方案进行评审
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


@tool(args_schema=OptimizeSystemApiOutput)
async def optimize_system_api_output(
        message: str,
        system_apis: list[SystemApi],
        runtime: ToolRuntime
) -> Command:
    """输出后端优化系统接口结果

    AI大模型使用此工具可完成系统接口的优化分析并输出结构化结果。

    **功能说明：**
    这是系统接口设计阶段的核心输出工具，用于：
    1. 对系统接口进行优化（补充参数说明、完善响应结构等）
    2. 验证接口列表合法性（检查 module_id 是否存在于系统模块中）
    3. 更新状态中的接口列表
    4. 清空之前的问题记录，为评审做准备

    Args:
        message: str - 针对系统接口优化的总结以及给团队成员接下来review的留言
        system_apis: list[SystemApi] - 输出优化后系统接口列表，包含以下字段：
            - id: str - 接口ID（默认自动生成）
            - module_id: str - 接口所属模块ID（必填）
            - name: str - 接口名称（必填）
            - method: HttpMethod - HTTP方法（get/post/put/delete/patch）
            - path: str - 接口URL路径（必填）
            - description: str - 接口描述
            - request_headers: list[SystemApiRequestParam] - 请求头参数
            - request_params: list[SystemApiRequestParam] - URL查询参数
            - request_body: list[SystemApiRequestParam] - 请求体参数
            - response_schema: str - 响应格式（必填）

            其中 SystemApiRequestParam 包含：
            - name: str - 参数名称
            - type: HttpParamType - 参数类型（string/number/object/array）
            - required: bool - 是否必填
            - description: str - 参数描述
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = OptimizeSystemApiOutput(
        message=message,
        system_apis=system_apis,
    )
    error_message = utils.validate_module_ids_str(system_apis, runtime.state["optimized_modules"])
    command = workflow_tool_utils.optimize_doc_output(
        output, runtime, GroupMemberRole.BACKEND, "system_apis", error_message)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return command


@tool(args_schema=ReviewOptimizationDocOutput)
async def review_system_api_output(
        review_issues: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出评审系统接口结果

    AI大模型使用此工具可输出各角色（架构/SRE/后端/前端/测试等）对系统接口的评审意见。

    **功能说明：**
    这是系统接口设计阶段的评审输出工具，用于：
    1. 汇总各角色提出的问题和建议方案
    2. 如果发现问题则添加高优先级回复
    3. 更新状态中的接口问题列表

    Args:
        review_issues: list[Issue] - 针对系统接口提出的问题和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    role = runtime.state["role"]
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationDocOutput(
        review_issues=review_issues,
    )
    command = workflow_tool_utils.review_optimization_doc_output(output, runtime)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
    return command


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 后缀为 output 的方法
common_tool_list = [t for t in tool_list if not t.name.endswith("output")]
