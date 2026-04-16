from typing import Optional, List, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field

from src.frontend.enums.creator_type import CreatorType
from src.frontend.enums.project_progress import ProjectProgress

T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    """分页数据"""
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20
