from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.enums import EntityType, OperationAction


class OperationLogBase(BaseModel):
    """操作日志基础字段"""
    project_id: str = Field(..., description="所属项目ID")
    entity_type: EntityType = Field(..., description="实体类型: project/module/test_case/api")
    entity_id: str = Field(..., description="实体ID")
    action: OperationAction = Field(..., description="操作类型: create/update/delete/export")
    detail: Optional[str] = Field(None, description="操作详情")


class OperationLogCreate(OperationLogBase):
    """创建操作日志"""
    pass


class OperationLogResponse(OperationLogBase):
    """操作日志响应"""
    id: str
    created_at: Optional[datetime] = None
