import time
import inspect
import traceback
import uuid

from loguru import logger
from langgraph.runtime import Runtime
from langchain.chat_models import BaseChatModel
from langchain.tools import ToolRuntime, BaseTool
from langchain_core.runnables import RunnableConfig
from langchain.messages import HumanMessage, AIMessage, ToolMessage, AnyMessage, ToolCall

from src.graphs.state import State
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.config import settings
from src.enums.error_message import ErrorMessage
from src.exceptions.exceptions import BusinessException


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
        metadata: 额外元数据，也会传递给 llm 在输出的 AIMessage 里可获取
        
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
                metadata_config = config.copy()
                metadata_config.update({"metadata": metadata})
                message_output = await llm.ainvoke(messages, config=metadata_config)
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
            mock_tool_call_id = str(uuid.uuid4())
            mock_msg = mock_ai_message_in_structured_output(mock_tool_call_id, func_name, {})
            mock_msg.content = message_output.content
            messages.extend([
                mock_msg,
                ToolMessage(
                    content=f"** ⚠️Warning 参数错误，无效输出，你已违反【核心规则】，使用当前回复内容重新调用该方法**",
                    tool_call_id=mock_tool_call_id
                )
            ])
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
