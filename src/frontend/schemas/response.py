from pydantic import BaseModel
from typing import Optional, List, Generic, TypeVar


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
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
