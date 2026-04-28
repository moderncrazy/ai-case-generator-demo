from langgraph.config import get_stream_writer
from langchain.messages import AnyMessage, AIMessage, HumanMessage, ToolMessage

from src import constant as const
from src.utils import utils as gutils
from src.enums.group_member_role import GroupMemberRole
from src.enums.requirement_module_status import RequirementModuleStatus
from src.enums.conversation_message_type import ConversationMessageType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.graphs.common.schemas import (
    Issue,
    StateApi,
    StateIssue,
    StateModule,
    CustomMessage,
    StateTestCase,
    StateApiRequestParam,
    StateRequirementModule,
    ReviewOptimizationPlanOutput,
    GenerateOptimizationPlanOutput,
)


def format_issues_to_str(issues: list[StateIssue] | None) -> str:
    """格式化问题列表为可读文本
    
    将问题列表格式化为适合 LLM 理解的文本格式，
    每个问题包含内容和建议方案。
    
    Args:
        issues: 问题列表
        
    Returns:
        格式化后的文本，格式为：
        问题Id：xxx
        问题：xxx
        建议方案：xxx
    """
    if issues:
        content = ""
        for item in issues:
            content += f"问题Id：{item["id"]}\n问题：{item["content"]}\n建议方案：{item["propose"]}\n\n"
        return content if content else const.EMPTY_ZH
    return const.EMPTY_ZH


def format_state_requirement_modules_to_str(modules: list[StateRequirementModule] | None,
                                            status: RequirementModuleStatus | None = None) -> str:
    """格式化需求模块列表为可读文本
    
    将需求模块列表格式化为适合 LLM 理解的文本格式，
    可选择只返回特定状态的模块。
    
    Args:
        modules: 需求模块列表
        status: 可选参数，按状态过滤（如只返回已完成的模块）
        
    Returns:
        格式化后的文本，格式为：
        模块序号：xxx
        模块名称：xxx
        模块状态：xxx
        模块描述：xxx
        模块内容：xxx
        ----------xxx end----------
    """
    if modules:
        result = ""
        for module in modules:
            content = f"模块序号：{module["order"]}\n模块名称：{module["name"]}\n模块状态：{module["status"]}\n模块描述：\n{module["description"]}\n模块内容：\n{module.get("content") or const.EMPTY_ZH}\n\n----------{module["name"]} end----------\n\n"
            if status:
                if module["status"] == status:
                    result += content
            else:
                result += content
        return result if result else const.EMPTY_ZH
    else:
        return const.EMPTY_ZH


def format_current_state_requirement_module_to_str(name: str, modules: list[StateRequirementModule] | None,
                                                   content: str | None = None) -> str:
    """根据模块名返回需求模块信息
    
    在需求模块列表中查找指定名称的模块，返回其详细信息。
    
    Args:
        name: 模块名称
        modules: 需求模块列表
        content: 可选参数，指定模块内容（会覆盖模块中的内容）
        
    Returns:
        指定模块的格式化文本，若未找到则返回"（空）"
    """
    if modules:
        for module in modules:
            if module["name"] == name:
                return f"模块序号：{module["order"]}\n模块名称：{module["name"]}\n模块状态：{module["status"]}\n模块描述：\n{module["description"]}\n模块内容：\n{content if content else module.get("content") or const.EMPTY_ZH}"
    return const.EMPTY_ZH


def format_state_modules_to_str(modules: list[StateModule] | None) -> str:
    """格式化系统模块列表为可读文本
    
    将系统模块列表格式化为适合 LLM 理解的文本格式，
    包含模块ID、名称、父模块ID和描述。
    
    Args:
        modules: 系统模块列表
        
    Returns:
        格式化后的文本，格式为：
        模块Id：xxx
        模块名称：xxx
        父模块Id：xxx（顶级模块显示"（顶级模块）"）
        模块描述：xxx
        ----------xxx end----------
    """
    if modules:
        result = ""
        for module in modules:
            result += f"模块Id：{module["id"]}\n模块名称：{module["name"]}\n父模块Id：{module.get("parent_id") or "（顶级模块）"}\n模块描述：\n{module["description"]}\n\n----------{module["name"]} end----------\n\n"
        return result if result else const.EMPTY_ZH
    else:
        return const.EMPTY_ZH


def format_state_api_request_param_to_str(params: list[StateApiRequestParam] | None) -> str:
    """格式化API请求参数为可读文本
    
    将API请求参数列表格式化为适合 LLM 理解的文本格式。
    
    Args:
        params: API请求参数列表
        
    Returns:
        格式化后的文本，格式为：
        字段名称：xxx
        字段类型：xxx
        是否必传：xxx
        字段描述：xxx
    """
    if params:
        result = ""
        for param in params:
            result += f"字段名称：{param["name"]}\n字段类型：{param["type"]}\n是否必传：{param["required"]}\n字段描述：{param["description"]}\n"
        return result if result else "（无）"
    return "（无）"


def format_state_apis_to_str(apis: list[StateApi] | None) -> str:
    """格式化API列表为可读文本
    
    将API列表格式化为适合 LLM 理解的文本格式，
    包含接口ID、名称、方法、路径、描述和请求/响应参数。
    
    Args:
        apis: API列表
        
    Returns:
        格式化后的文本，格式为：
        接口Id：xxx
        所属模块Id：xxx
        接口名称：xxx
        调用方式：xxx
        接口路径：xxx
        接口描述：xxx
        Headers：xxx
        Params：xxx
        Body：xxx
        响应结构：xxx
        ----------xxx end----------
    """
    if apis:
        result = ""
        for api in apis:
            header = format_state_api_request_param_to_str(api.get("request_headers"))
            param = format_state_api_request_param_to_str(api.get("request_params"))
            body = format_state_api_request_param_to_str(api.get("request_body"))
            result += (
                f"接口Id：{api["id"]}\n所属模块Id：\n{api["module_id"]}\n"
                f"接口名称：{api["name"]}\n调用方式：{api["method"].value}\n接口路径：{api["path"]}\n"
                f"接口描述：\n{api.get("description") or const.EMPTY_ZH}\nHeaders：\n{header}\nParams：\n{param}\nBody：\n{body}\n"
                f"响应结构：\n{api["response_schema"]}\n\n----------{api["name"]} end----------\n\n"
            )
        return result if result else const.EMPTY_ZH
    else:
        return const.EMPTY_ZH


def format_state_test_cases_to_str(test_cases: list[StateTestCase] | None) -> str:
    """格式化测试用例列表为可读文本
    
    将测试用例列表格式化为适合 LLM 理解的文本格式，
    包含用例ID、标题、所属模块、前置条件、测试步骤等。
    
    Args:
        test_cases: 测试用例列表
        
    Returns:
        格式化后的文本，格式为：
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
    """
    if test_cases:
        result = ""
        for test_case in test_cases:
            result += (
                f"测试用例Id：{test_case["id"]}\n模块名称：{test_case["title"]}\n所属模块Id：{test_case["module_id"]}\n"
                f"前置条件：{test_case.get("precondition") or "（无）"}\n测试步骤：{test_case["test_steps"]}\n"
                f"预期结果：{test_case["expected_result"]}\n测试数据：{test_case["test_data"]}\n"
                f"用例等级：{test_case["level"].value}\n用例类型：{test_case["type"].value}\n\n----------{test_case["title"]} end----------\n\n"
            )
        return result if result else const.EMPTY_ZH
    else:
        return const.EMPTY_ZH


def format_generate_optimization_plan_output_to_str(output: GenerateOptimizationPlanOutput) -> str:
    """格式化优化方案输出为可读文本"""
    result = f"AI生成的具体优化方案如下：\n\n业务背景：\n{output.background}\n\n优化说明：\n{output.summary}\n\n方案逻辑链路：\n{output.logic}\n\n方案具体步骤：\n{"\n".join(output.steps)}"
    return result


def format_generate_optimization_plan_and_question_output_to_str(output: GenerateOptimizationPlanOutput) -> str:
    """格式化优化方案输出为可读文本"""
    result = f"{format_generate_optimization_plan_output_to_str(output)}\n\n"
    if output.questions:
        result += f"提出的问题：{"\n".join(output.questions)}\n\n"
    if output.risks:
        result += f"潜在的风险：{"\n".join(output.risks)}\n\n"
    return result


def format_review_optimization_plan_output_to_str(output: ReviewOptimizationPlanOutput) -> str:
    """格式化优化方案输出为可读文本"""
    result = ""
    match output.result:
        case ReviewOptimizationPlanResult.APPROVE:
            result = output.message
        case ReviewOptimizationPlanResult.REVISE:
            result = f"{"\n\n".join([f"待修改问题：{item.content}\n建议方案：{item.propose}" for item in output.issues])}\n\n{output.message}"
        case ReviewOptimizationPlanResult.ASK_QUESTION:
            result = f"{output.message}\n\n{"\n\n\n\n".join([f"**待确认问题：** {item.content}\n\n**建议方案：** {item.propose}" for item in output.issues])}"
    return result


def format_context_messages_to_str(message: list[AnyMessage]) -> str:
    """格式化上下文为可读文本"""
    result = ""
    if message:
        for message in message:
            content = gutils.to_one_line(str(message.content))
            if isinstance(message, HumanMessage):
                result += f"User: {content}\n\n"
            elif isinstance(message, ToolMessage):
                result += f"Tool: {content}\n\n"
            else:
                result += f"AI: {content}\n\n"
    return result


def send_custom_message(message: str, role: GroupMemberRole,
                        type: ConversationMessageType = ConversationMessageType.STAGE):
    """发送自定义消息"""
    writer = get_stream_writer()
    writer(CustomMessage(type=type, role=role, message=message))
