from enum import StrEnum


class ReducerActionType(StrEnum):
    """Reducer执行类型"""

    RESET = "reset"
    """清空列表"""
