import json
import inspect
from loguru import logger
from langgraph.runtime import Runtime
from langchain.chat_models import BaseChatModel
from langchain.tools import ToolRuntime, BaseTool
from langchain_core.runnables import RunnableConfig
from langchain.messages import HumanMessage, AIMessage, ToolCall

from src.config import settings
from src.graphs.state import State
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.error_message import ErrorMessage
from src.graphs.schemas import StateNewProjectFile, Issue
from src.exceptions.exceptions import BusinessException


def format_state_new_project_files_to_str(files: list[StateNewProjectFile]) -> str:
    content = ""
    for file in files:
        content += f"文件Id：{file["id"]}\n文件名：{file["name"]}\n上传时间：{file["created_at"]}\n文件内容：\n{file["content"]}----------{file["name"]} end----------\n\n"
    return content


def format_issues_to_str(issues: list[Issue]) -> str:
    content = ""
    for item in issues:
        content += f"问题：{item.content}\n建议方案：{item.propose}\n"
    return content


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
            try:
                tool_call_id = message_output.tool_calls[0]["id"]
                tool_call_args = message_output.tool_calls[0]["args"]
                tool_runtime = create_tool_runtime(tool_call_id, state, runtime, config)
                logger.info(
                    f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 结构化输出:{gutils.to_json(tool_call_args)}")
                return await structured_output_func.ainvoke({**tool_call_args, "runtime": tool_runtime})
            except Exception as e:
                logger.info(
                    f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 结构化输出异常:{str(e)}")
                messages.extend([
                    message_output,
                    HumanMessage(content=f"调用 {func_name} 方法异常，error：{str(e)}")
                ])
        # 若响应为查询方法则去查询
        else:
            logger.info(f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} "
                        f"调用tool:{",".join([item["name"] for item in message_output.tool_calls])}")
            return {messages_key: [message_output]}
    # 若重试后仍无法调用方法则报错
    logger.info(f"trans_id:{trans_id_ctx.get()} 结构化输出方法:{func_name} 重试超限")
    raise BusinessException.from_error_message(ErrorMessage.LLM_ERROR)


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
