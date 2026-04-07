from pydantic import BaseModel
from typing import Any, Generic, TypeVar, Optional, List

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """通用响应"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class ApiListResponse(BaseModel, Generic[T]):
    """列表响应"""
    code: int = 200
    message: str = "success"
    data: "ListData[T]"


class ListData(BaseModel, Generic[T]):
    """分页数据"""
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    error: Optional[str] = None
