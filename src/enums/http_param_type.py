from enum import StrEnum


class HttpParamType(StrEnum):
    """HTTP 参数类型枚举"""

    STRING = "string"
    """字符串类型"""

    NUMBER = "number"
    """数值类型"""

    BOOLEAN = "boolean"
    """布尔类型"""

    OBJECT = "object"
    """对象类型"""

    ARRAY = "array"
    """数组类型"""
