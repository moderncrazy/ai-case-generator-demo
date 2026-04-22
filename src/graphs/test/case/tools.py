import uuid
import inspect
from loguru import logger
from langgraph.types import Command
from langchain.tools import tool, BaseTool, ToolRuntime
from langchain.messages import AIMessage, ToolMessage, HumanMessage, ToolCall

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.utils import utils as cutils
from src.graphs.common.utils import workflow_tool_utils
from src.graphs.common.utils import structured_output_utils
from src.graphs.common.schemas import Issue, GenerateOptimizationPlanOutput, ReviewOptimizationPlanOutput
from src.graphs.test.case import utils
from src.graphs.test.case.schemas import (
    TestCase,
    OptimizeTestCaseOutput,
    ReviewTestCaseOutput
)


@tool(args_schema=GenerateOptimizationPlanOutput)
async def generate_optimization_test_case_plan_output(
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
    return Command(update={"private_messages": [AIMessage(content=message, name=GroupMemberRole.TEST.value)]})


@tool(args_schema=ReviewOptimizationPlanOutput)
async def review_optimization_test_case_plan_output(
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
        output, "review_optimization_test_case_plan_node", runtime)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return result


@tool(args_schema=OptimizeTestCaseOutput)
async def optimize_test_case_output(
        message: str,
        test_cases: list[TestCase],
        runtime: ToolRuntime
) -> Command:
    """输出测试优化测试用例结果
    
    AI大模型使用此工具可完成测试用例的优化分析并输出结构化结果。
    
    **功能说明：**
    这是测试用例设计阶段的核心输出工具，用于：
    1. 对测试用例进行优化（完善步骤、调整分级、补充数据等）
    2. 验证测试用例合法性（检查 module_id 是否存在于系统模块中）
    3. 更新状态中的测试用例列表
    4. 清空之前的问题记录，为评审做准备
    
    Args:
        message: str - 针对测试用例优化的总结以及给团队成员接下来review的留言
        test_cases: list[TestCase] - 输出优化后测试用例列表，包含以下字段：
            - id: str - 测试用例ID（默认自动生成，UUID）
            - module_id: str - 测试用例所属模块ID（必填）
            - title: str - 测试用例标题（必填）
            - precondition: str - 前置条件
            - test_steps: str - 测试步骤（必填）
            - expected_result: str - 预期结果（必填）
            - test_data: str - 测试数据（必填）
            - level: TestCaseLevel - 测试用例等级（p0/p1/p2/p3）
            - type: TestCaseType - 测试用例类型（functional/interface/performance）
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    project_id = runtime.state["project_id"]
    output = OptimizeTestCaseOutput(
        message=message,
        test_cases=test_cases
    )
    # 验证 API 模块Id
    if msg := utils.validate_module_ids_str(test_cases, runtime.state["optimized_modules"]):
        error_message = f"测试用例校验失败：{msg}重新生成"
        logger.warning(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()} 打回:{error_message}")
        tool_call_id = runtime.tool_call_id
        tool_name = gutils.get_func_name()
        tool_call_message = structured_output_utils.mock_ai_message_in_structured_output(
            tool_call_id, tool_name, locals())
        return Command(
            goto="optimize_test_case_node",
            update={
                "private_messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
        )
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": [AIMessage(content=output.message, name=GroupMemberRole.TEST.value)],
        "review_reply_message_id": str(uuid.uuid4()),
        "test_cases": [item.model_dump() for item in output.test_cases],
        "test_case_issues": ReducerActionType.RESET,
    })


@tool(args_schema=ReviewTestCaseOutput)
async def review_test_case_output(
        test_case_issues: list[Issue],
        runtime: ToolRuntime
) -> Command:
    """输出评审测试用例结果
    
    AI大模型使用此工具可输出各角色（后端/前端等）对测试用例的评审意见。
    
    **功能说明：**
    这是测试用例设计阶段的评审输出工具，用于：
    1. 汇总各角色提出的问题和建议方案
    2. 如果发现问题则添加高优先级回复
    3. 更新状态中的用例问题列表
    
    Args:
        test_case_issues: list[Issue] - 针对测试用例提出的问题和建议方案列表，包含以下字段：
            - content: str - 问题描述
            - propose: str - 建议方案
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    """
    role = runtime.state["role"]
    project_id = runtime.state["project_id"]
    output = ReviewTestCaseOutput(
        test_case_issues=test_case_issues,
    )
    # 发现问题构建回复
    messages = []
    message_id = runtime.state["review_reply_message_id"]
    if test_case_issues:
        messages.append(AIMessage(
            id=message_id,
            name=GroupMemberRole.GROUP_MEMBER.value,
            content="评审完成，发现问题，请测试根据评审意见修改测试用例。",
            additional_kwargs={"priority": 1}
        ))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 输出:{output.model_dump_json()}")
    return Command(update={
        "private_messages": messages,
        "test_case_issues": [item.model_dump() for item in (output.test_case_issues or [])],
    })


@tool
async def get_test_cases(runtime: ToolRuntime) -> str:
    """获取优化后测试用例列表
    
    AI大模型使用此工具可获取经过AI优化后的测试用例列表。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的测试用例列表。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即测试用例列表的格式化内容：
        测试用例Id：xxx
        模块名称：xxx
        所属模块Id：xxx
        前置条件：xxx
        测试步骤：xxx
        预期结果：xxx
        测试数据：xxx
        用例等级：xxx
        用例类型：xxx
        ----------xxx end----------
        
        如果无测试用例，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("test_cases") or runtime.state.get("optimized_test_cases")
    result_str = cutils.format_state_test_cases_to_str(result)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result_str)}")
    return result_str


@tool
async def get_test_case_issues(runtime: ToolRuntime) -> str:
    """获取测试用例评审意见列表
    
    AI大模型使用此工具可获取各角色对测试用例提出的评审意见。
    
    **功能说明：**
    从运行时状态中读取并返回测试用例的评审意见，用于了解之前评审发现的问题。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，格式为：
        问题：xxx
        建议方案：xxx
        
        如果无评审意见，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = cutils.format_issues_to_str(runtime.state.get("test_case_issues"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 专用方法
common_tool_list = [t for t in tool_list if
                    t.name not in [
                        optimize_test_case_output.name,
                        review_test_case_output.name,
                    ]]
