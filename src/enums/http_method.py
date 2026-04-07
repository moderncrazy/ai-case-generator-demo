from enum import Enum


class HttpMethod(str, Enum):
    """HTTP 方法枚举，与数据库 apis.method 字段一致"""

    GET = "GET"
    """GET 请求"""

    POST = "POST"
    """POST 请求"""

    PUT = "PUT"
    """PUT 请求"""

    DELETE = "DELETE"
    """DELETE 请求"""

    PATCH = "PATCH"
    """PATCH 请求"""
