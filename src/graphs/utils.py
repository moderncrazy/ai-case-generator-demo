import time
import inspect
import traceback

from loguru import logger
from langgraph.runtime import Runtime
from langchain.chat_models import BaseChatModel
from langchain.tools import ToolRuntime, BaseTool
from langchain_core.runnables import RunnableConfig
from langchain.messages import HumanMessage, AIMessage, ToolMessage, ToolCall

from src.config import settings
from src.graphs.state import State
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.error_message import ErrorMessage
from src.enums.requirement_module_status import RequirementModuleStatus
from src.graphs.schemas import (
    Issue,
    StateApi,
    StateIssue,
    StateModule,
    StateTestCase,
    StateNewProjectFile,
    StateApiRequestParam,
    StateRequirementModule,
)
from src.exceptions.exceptions import BusinessException


def format_state_new_project_files_to_str(files: list[StateNewProjectFile] | None) -> str:
    """格式化新上传文件列表为可读文本
    
    将新上传的项目文件列表格式化为适合 LLM 理解的文本格式，
    包含文件ID、名称、上传时间和内容。
    
    Args:
        files: 新上传文件列表
        
    Returns:
        格式化后的文本，格式为：
        文件Id：xxx
        文件名：xxx
        上传时间：xxx
        文件内容：xxx
        ----------xxx end----------
    """
    if files:
        content = ""
        for file in files:
            content += f"文件Id：{file["id"]}\n文件名：{file["name"]}\n上传时间：{file["created_at"]}\n文件内容：\n{file["content"]}----------{file["name"]} end----------\n\n"
        return content if content else "（空）"
    return "（空）"


def format_issues_to_str(issues: list[StateIssue] | None) -> str:
    """格式化问题列表为可读文本
    
    将问题列表格式化为适合 LLM 理解的文本格式，
    每个问题包含内容和建议方案。
    
    Args:
        issues: 问题列表
        
    Returns:
        格式化后的文本，格式为：
        问题：xxx
        建议方案：xxx
    """
    if issues:
        content = ""
        for item in issues:
            content += f"问题：{item["content"]}\n建议方案：{item["propose"]}\n\n"
        return content if content else "（空）"
    return "（空）"


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
            content = f"模块序号：{module["order"]}\n模块名称：{module["name"]}\n模块状态：{module["status"]}\n模块描述：\n{module["description"]}\n模块内容：\n{module.get("content") or "（空）"}\n\n----------{module["name"]} end----------\n\n"
            if status:
                if module["status"] == status:
                    result += content
            else:
                result += content
        return result if result else "（空）"
    else:
        return "（空）"


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
                return f"模块序号：{module["order"]}\n模块名称：{module["name"]}\n模块状态：{module["status"]}\n模块描述：\n{module["description"]}\n模块内容：\n{content if content else module.get("content") or "（空）"}"
    return "（空）"


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
        return result if result else "（空）"
    else:
        return "（空）"


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
                f"接口描述：\n{api.get("description") or "（空）"}\nHeaders：\n{header}\nParams：\n{param}\nBody：\n{body}\n"
                f"响应结构：\n{api["response_schema"]}\n\n----------{api["name"]} end----------\n\n"
            )
        return result if result else "（空）"
    else:
        return "（空）"


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
        return result if result else "（空）"
    else:
        return "（空）"


def create_tool_runtime(tool_call_id: str, state: State, runtime: Runtime, config: RunnableConfig) -> ToolRuntime:
    """创建 ToolRuntime
    
    构建一个 ToolRuntime 实例，用于在 tool 调用时传递上下文信息。
    从原始 runtime 中复制除基础参数外的所有属性。
    
    Args:
        tool_call_id: 工具调用ID
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: 运行时配置
        
    Returns:
        创建的 ToolRuntime 实例
    """
    args = {"tool_call_id": tool_call_id, "state": state, "config": config}
    # 遍历 ToolRuntime 属性
    for key in [key for key in inspect.signature(ToolRuntime.__init__).parameters.keys() if
                # 排除以下属性
                key not in ["self", "tool_call_id", "state", "config"]]:
        args[key] = getattr(runtime, key)
    return ToolRuntime(**args)


def mock_ai_message_in_structured_output(tool_call_id: str, tool_name: str, tool_locals: dict) -> AIMessage:
    """在结构化输出 tool 中 mock tool call ai message
    
    在调用结构化输出方法时，需要先创建一个模拟的 AIMessage
    来表示 LLM 的 tool_call 意图。
    
    Args:
        tool_call_id: 工具调用ID
        tool_name: 工具名称
        tool_locals: 工具函数的局部变量字典
        
    Returns:
        模拟的 AIMessage，包含 tool_calls 信息
    """
    tool_args = {k: v for k, v in tool_locals.items() if not k.startswith(("__", "runtime"))}
    return AIMessage(content="", tool_calls=[ToolCall(id=tool_call_id, name=tool_name, args=tool_args)])


def validate_requirement_module_exist(name: str, modules: list[StateRequirementModule]) -> bool:
    """验证需求模块 name 是否存在
    
    检查给定名称的需求模块是否存在于模块列表中。
    
    Args:
        name: 模块名称
        modules: 需求模块列表
        
    Returns:
        存在返回 True，不存在返回 False
    """
    for module in modules:
        if module["name"] == name:
            return True
    return False


def validate_requirement_modules_completed_to_str(modules: list[StateRequirementModule] | None) -> str:
    """验证需求模块是否完善
    
    检查需求模块列表中的所有模块是否都已完成：
    1. 模块内容不能为空
    2. 模块状态必须为 COMPLETED
    
    Args:
        modules: 需求模块列表
        
    Returns:
        空字符串表示验证通过，否则返回错误信息
    """
    if modules:
        error_message = []
        for module in modules:
            if not module.get("content"):
                error_message.append(f"{module["name"]}模块内容为空")
            if module.get("status") != RequirementModuleStatus.COMPLETED:
                error_message.append(f"{module["name"]}模块状态未完成")
        return "，".join(error_message)
    else:
        return "需求模块为空"


def validate_state_fields_to_exception(state: State, fields: list[str] | None = None, 
                                       none_fields: list[str] | None = None) -> None:
    """验证状态字段是否符合要求
    
    - fields: 检查这些字段在 state 中是否存在且非空
    - none_fields: 检查这些字段在 state 中是否为空
    
    若验证失败则抛出 BusinessException。
    
    Args:
        state: LangGraph 状态
        fields: 必须存在的字段列表
        none_fields: 必须为空的字段列表
        
    Raises:
        BusinessException: 验证失败时抛出
    """
    if fields:
        for field in fields:
            if not state.get(field):
                error_message = f"{gutils.get_field_doc(State, field)}为空"
                raise BusinessException(ErrorMessage.FLOW_VALIDATE_FAILED.code, error_message)
    if none_fields:
        for field in none_fields:
            if state.get(field):
                error_message = f"{gutils.get_field_doc(State, field)}不为空"
                raise BusinessException(ErrorMessage.FLOW_VALIDATE_FAILED.code, error_message)


async def llm_tool_structured_output(llm: BaseChatModel, state: State, runtime: Runtime, config: RunnableConfig,
                                     messages: list, structured_output_func: BaseTool, messages_key: str = "messages",
                                     metadata: dict | None = None) -> dict | State:
    """LLM 调用 tool 进行结构化输出
    
    核心的结构化输出方法，实现以下逻辑：
    1. 调用 LLM 生成响应
    2. 若响应包含指定方法的 tool_call，则执行该方法
    3. 若响应包含其他 tool_call，则返回该消息继续
    4. 若响应不包含 tool_call，则提示 LLM 重试
    5. 内置重试机制，网络异常和方法调用失败都会重试
    
    Args:
        llm: LLM 实例
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: 运行时配置
        messages: 消息列表
        structured_output_func: 结构化输出方法
        messages_key: 消息存储的 state key，默认为 "messages"
        metadata: 额外元数据
        
    Returns:
        更新后的状态或消息列表
        
    Raises:
        BusinessException: LLM 输出重试超限时抛出
    """
    func_name = structured_output_func.name
    # 日志前缀
    log_prefix = f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 元数据:{gutils.to_json(metadata or {})}"
    # 增加重试机制
    for _ in range(settings.model_structured_output_retry):
        message_output = None
        for __ in range(settings.model_output_retry):
            try:
                message_output = await llm.ainvoke(messages)
                break
            except Exception as e:
                logger.warning(f"{log_prefix} 重试:{__} 网络异常:{str(e)}")
                time.sleep(1)

        if not message_output:
            logger.error(f"{log_prefix} llm输出重试超限")
            raise BusinessException.from_error_message(ErrorMessage.LLM_ERROR)

        logger.info(f"{log_prefix} 重试:{_} llm输出:{message_output.model_dump_json()}")
        # 若响应非方法调用 则重试
        if not message_output.tool_calls:
            messages.extend([message_output, HumanMessage(content=f"调用 {func_name} 方法输出结果")])
            logger.warning(f"{log_prefix} 重试:{_} llm未使用方法:{message_output.model_dump_json()}")
        # 若响应为结构化输出方法则直接调用 通过路由跳转
        elif message_output.tool_calls[0]["name"] == func_name:
            tool_call_id = message_output.tool_calls[0]["id"]
            tool_call_args = message_output.tool_calls[0]["args"]
            tool_runtime = create_tool_runtime(tool_call_id, state, runtime, config)
            logger.info(f"{log_prefix} 结构化输出:{gutils.to_json(tool_call_args)}")
            try:
                return await structured_output_func.ainvoke({**tool_call_args, "runtime": tool_runtime})
            except Exception as e:
                logger.error(f"{log_prefix} 结构化输出异常:{str(e)} 异常栈:{traceback.format_exc()}")
                messages.extend([
                    message_output,
                    ToolMessage(content=f"调用 {func_name} 方法异常，error：{str(e)}", tool_call_id=tool_call_id)
                ])
        # 若响应为查询方法则去查询
        else:
            logger.info(f"{log_prefix} 调用tool:{",".join([item["name"] for item in message_output.tool_calls])}")
            return {messages_key: [message_output]}
    # 若重试后仍无法调用方法则报错
    logger.info(f"{log_prefix} llm结构化输出重试超限")
    raise BusinessException.from_error_message(ErrorMessage.LLM_ERROR)
