import inspect
from loguru import logger
from langgraph.types import Command
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
    StateModule,
    StateTestCase,
    StateNewProjectFile,
    StateApiRequestParam,
    StateRequirementModule,
)
from src.exceptions.exceptions import BusinessException


def format_state_new_project_files_to_str(files: list[StateNewProjectFile] | None) -> str:
    if files:
        content = ""
        for file in files:
            content += f"文件Id：{file["id"]}\n文件名：{file["name"]}\n上传时间：{file["created_at"]}\n文件内容：\n{file["content"]}----------{file["name"]} end----------\n\n"
        return content if content else "（空）"
    return "（空）"


def format_issues_to_str(issues: list[Issue] | None) -> str:
    if issues:
        content = ""
        for item in issues:
            content += f"问题：{item.content}\n建议方案：{item.propose}\n\n"
        return content if content else "（空）"
    return "（空）"


def format_state_requirement_modules_to_str(modules: list[StateRequirementModule] | None,
                                            status: RequirementModuleStatus | None = None) -> str:
    if modules:
        result = ""
        for module in modules:
            content = f"模块序号：{module["order"]}\n模块名称：{module["name"]}\n模块状态：{module["status"]}\n模块描述：\n{module["description"]}\n模块内容：\n{module["content"]}\n\n----------{module["name"]} end----------\n\n"
            if status:
                if module["status"] == status:
                    result += content
            else:
                result += content
        return result if result else "（空）"
    else:
        return "（空）"


def format_current_state_requirement_module_to_str(name, modules: list[StateRequirementModule] | None,
                                                   content: str | None = None) -> str:
    """根据模块名返回需求模块信息"""
    if modules:
        for module in modules:
            if module["name"] == name:
                return f"模块序号：{module["order"]}\n模块名称：{module["name"]}\n模块状态：{module["status"]}\n模块描述：\n{module["description"]}\n模块内容：\n{content if content else module.get("content", "（空）")}"
    return "（空）"


def format_state_modules_to_str(modules: list[StateModule] | None) -> str:
    if modules:
        result = ""
        for module in modules:
            result += f"模块Id：{module["id"]}\n模块名称：{module["name"]}\n父模块Id：{module.get("parent_id") or "（顶级模块）"}\n模块描述：\n{module["description"]}\n\n----------{module["name"]} end----------\n\n"
        return result if result else "（空）"
    else:
        return "（空）"


def format_state_api_request_param_to_str(params: list[StateApiRequestParam] | None):
    if params:
        result = ""
        for param in params:
            result += f"字段名称：{param["name"]}\n字段类型：{param["type"]}\n是否必传：{param["required"]}\n字段描述：{param["description"]}\n"
        return result if result else "（无）"
    return "（无）"


def format_state_apis_to_str(apis: list[StateApi] | None) -> str:
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
    """创建 ToolRuntime"""
    args = {"tool_call_id": tool_call_id, "state": state, "config": config}
    # 遍历 ToolRuntime 属性
    for key in [key for key in inspect.signature(ToolRuntime.__init__).parameters.keys() if
                # 排除以下属性
                key not in ["self", "tool_call_id", "state", "config"]]:
        args[key] = getattr(runtime, key)
    return ToolRuntime(**args)


def mock_ai_message_in_structured_output(tool_call_id: str, tool_name: str, tool_locals: dict) -> AIMessage:
    """在结构化输出 tool 中 mock tool call ai message """
    tool_args = {k: v for k, v in tool_locals.items() if not k.startswith(("__", "runtime"))}
    return AIMessage(content="", tool_calls=[ToolCall(id=tool_call_id, name=tool_name, args=tool_args)])


def validate_requirement_module_exist(name: str, modules: list[StateRequirementModule]) -> bool:
    """验证需求模块 name 是否存在"""
    for module in modules:
        if module["name"] == name:
            return True
    return False


def validate_requirement_modules_completed_to_str(modules: list[StateRequirementModule] | None) -> str:
    """验证需求模块是否完善"""
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


def validate_state_fields_to_exception(state: State, fields: list[str] = None, none_fields: list[str] = None):
    """验证 fields 字段在 state 中是否非空，验证 none_fields 字段在 state 中是否为空 若否则报错"""
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
                                     messages: list, structured_output_func: BaseTool,
                                     messages_key="messages"):
    """llm 调用 tool 进行结构化输出"""
    func_name = structured_output_func.name
    # 增加重试机制
    llm_with_retry = llm.with_retry(stop_after_attempt=settings.model_output_retry)
    for _ in range(settings.model_structured_output_retry):
        message_output = await llm_with_retry.ainvoke(messages)
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 重试:{_} llm输出: {message_output.model_dump_json()}")
        # 若响应非方法调用 则重试
        if not message_output.tool_calls:
            messages.extend([message_output, HumanMessage(content=f"调用 {func_name} 方法输出结果")])
        # 若响应为结构化输出方法则直接调用 通过路由跳转
        elif message_output.tool_calls[0]["name"] == func_name:
            tool_call_id = message_output.tool_calls[0]["id"]
            tool_call_args = message_output.tool_calls[0]["args"]
            tool_runtime = create_tool_runtime(tool_call_id, state, runtime, config)
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 结构化输出:{gutils.to_json(tool_call_args)}")
            try:
                return await structured_output_func.ainvoke({**tool_call_args, "runtime": tool_runtime})
            except Exception as e:
                logger.error(
                    f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 结构化输出异常:{str(e)}")
                messages.extend([
                    message_output,
                    ToolMessage(content=f"调用 {func_name} 方法异常，error：{str(e)}", tool_call_id=tool_call_id)
                ])
        # 若响应为查询方法则去查询
        else:
            logger.info(f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} "
                        f"调用tool:{",".join([item["name"] for item in message_output.tool_calls])}")
            return {messages_key: [message_output]}
    # 若重试后仍无法调用方法则报错
    logger.info(f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 重试超限")
    raise BusinessException.from_error_message(ErrorMessage.LLM_ERROR)
