from loguru import logger
from langgraph.types import Command
from langchain.messages import AIMessage, ToolMessage
from langchain.tools import tool, BaseTool, ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.utils import utils as cutils
from src.graphs.common.utils import workflow_tool_utils
from src.graphs.common.utils import structured_output_utils
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.requirement_module_status import RequirementModuleStatus
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.repositories.project_repository import project_repository, ProjectUpdate
from src.graphs.requirement.outline import utils
from src.graphs.requirement.outline.schemas import RequirementModuleCreate, OptimizeRequirementOutlineOutput
from src.graphs.common.schemas import (
    Issue,
    StateRequirementModule,
    GenerateOptimizationPlanOutput,
    ReviewOptimizationPlanOutput
)


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_requirement_outline_plan_output(
        logic: str, steps: list[str],
        questions: list[str] | None,
        risks: list[str] | None,
        runtime: ToolRuntime
) -> Command:
    """输出优化需求大纲方案"""
    project_id = runtime.state["project_id"]
    output = GenerateOptimizationPlanOutput(logic=logic, steps=steps, questions=questions, risks=risks)
    message = cutils.format_generate_optimization_plan_output_to_str(output)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={"private_messages": [AIMessage(content=message, name=GroupMemberRole.PRODUCT.value)]})


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_requirement_outline_plan_output(
        result: ReviewOptimizationPlanResult,
        message: str,
        feedbacks: list[Issue] | None,
        questions: list[Issue] | None,
        runtime: ToolRuntime
) -> Command:
    """输出审核优化需求大纲方案"""
    project_id = runtime.state["project_id"]
    output = ReviewOptimizationPlanOutput(result=result, message=message, feedbacks=feedbacks, questions=questions)
    result = workflow_tool_utils.review_optimization_plan_output(
        output, "review_optimization_requirement_outline_plan_node", runtime)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return result


@tool(args_schema=OptimizeRequirementOutlineOutput)
async def optimize_requirement_outline_output(
        message: str,
        requirement_outline: str,
        requirement_modules: list[RequirementModuleCreate],
        runtime: ToolRuntime
) -> Command:
    """输出产品优化需求大纲结果
    
    AI大模型使用此工具可完成需求大纲的优化分析并输出结构化结果。
    
    **功能说明：**
    这是需求大纲设计阶段的核心输出工具，用于：
    1. 对需求大纲进行优化分析（补充缺失点、调整结构）
    2. 将需求拆解为多个功能模块
    3. 验证模块列表合法性（检查name重复、order重复、order不连续）
    4. 保存优化后的需求大纲到数据库
    5. 初始化模块列表（默认状态为 pending，按order排序）
    
    Args:
        message: str - 针对需求大纲优化的总结以及给客户的回复
        requirement_outline: str - 输出优化后需求大纲（Markdown格式）
        requirement_modules: list[RequirementModuleCreate] - 输出需求模块列表，包含以下字段：
            - name: str - 模块名称（必填）
            - order: int - 模块序号（用于排序）
            - description: str - 模块描述，包含功能定位、核心页面等（必填）
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = OptimizeRequirementOutlineOutput(
        message=message,
        requirement_outline=requirement_outline,
        requirement_modules=requirement_modules
    )
    # 验证需求模块是否重复
    error_message = utils.validate_requirement_modules(requirement_modules)
    if error_message:
        tool_call_id = runtime.tool_call_id
        tool_name = gutils.get_func_name()
        tool_call_message = structured_output_utils.mock_ai_message_in_structured_output(
            tool_call_id, tool_name, locals())
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 需求模块验证失败打回:{error_message}")
        # 打回修复
        return Command(
            update={
                "private_messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
            goto="optimize_requirement_outline_node"
        )
    # 保存需求大纲
    await project_repository.update(
        runtime.state["project_id"],
        ProjectUpdate(requirement_outline_design=requirement_outline)
    )
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 更新需求大纲入库")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "messages": [AIMessage(content=output.message, name=GroupMemberRole.PRODUCT.value)],
        "private_messages": ReducerActionType.RESET,
        "requirement_outline": output.requirement_outline,
        # 默认设置状态为 pending 并 排序
        "requirement_modules": sorted(
            [StateRequirementModule(status=RequirementModuleStatus.PENDING, **item.model_dump())
             for item in output.requirement_modules],
            key=lambda m: m["order"]
        ),
    })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
