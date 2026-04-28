from langchain.messages import AIMessage, HumanMessage, ToolMessage, AnyMessage

from src.exceptions.exceptions import BusinessException
from src.utils import sensitive_word_utils, utils as gutils
from src.graphs.state import State
from src.graphs.common.schemas import StateRequirementModule
from src.enums.error_message import ErrorMessage
from src.enums.requirement_module_status import RequirementModuleStatus


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


def validate_requirement_module_completed(name: str, modules: list[StateRequirementModule] | None) -> bool:
    """验证指定需求模块是否已确认

    Args:
        name: 模块名称
        modules: 需求模块列表

    Returns:
        确认返回 True，未确认返回 False
    """
    for module in modules:
        if module["name"] == name and module["status"] == RequirementModuleStatus.COMPLETED:
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


def latest_human_message_append_system_hint(messages: list[AnyMessage]) -> list[AnyMessage]:
    """对最新一条 HumanMessage 增加系统提示"""
    if messages:
        temp_msgs = messages.copy()
        gen = (index for index, item in reversed(list(enumerate(messages))) if isinstance(item, HumanMessage))
        try:
            index = next(gen)
            content = f"{temp_msgs[index].content}\n\n（【系统提示】：\n**1. ⚠️【必须】使用 product_manager_output 方法输出**\n**2. ⚠️【禁止】自行设计任何项目文档，必须调用下游agent生成**\n**3. 若任务明确【直接执行流程】**）"
            temp_msgs[index] = HumanMessage(content=content)
            return temp_msgs
        except StopIteration:
            return messages
    return messages


def optimize_history_messages_to_subgraph(messages: list[AnyMessage]) -> list[AnyMessage]:
    """将历史消息中的 工具调用、工具输出、工具名称 都删掉，防止子图对pm方法的误用，并且将所有消息转为 AIMessage"""
    results = []
    for message in messages:
        if isinstance(message, HumanMessage) or (isinstance(message, AIMessage) and not message.tool_calls):
            # 过滤方法名
            content = sensitive_word_utils.filter_graph_tools(message.text)
            results.append(AIMessage(content))
    return results
