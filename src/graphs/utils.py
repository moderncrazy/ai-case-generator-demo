from src.utils import utils as gutils
from src.graphs.state import State
from src.graphs.common.schemas import StateRequirementModule
from src.exceptions.exceptions import BusinessException
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
