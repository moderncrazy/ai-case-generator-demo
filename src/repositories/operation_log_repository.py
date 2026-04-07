import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from src.models import OperationLog
from src.enums import EntityType, OperationAction


class OperationLogCreate(BaseModel):
    """创建操作日志参数"""
    project_id: str
    entity_type: EntityType
    entity_id: str
    action: OperationAction
    detail: Optional[str] = None


class OperationLogRepository:
    """操作日志 Repository"""

    def __init__(self):
        self.model = OperationLog

    async def create(self, log: OperationLogCreate) -> str | None:
        """创建操作日志"""
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                project_id=log.project_id,
                entity_type=log.entity_type.value,
                entity_id=log.entity_id,
                action=log.action.value,
                detail=log.detail,
                created_at=datetime.now(),
            )
        )
        return results[0]["id"] if results else None

    async def get_by_id(self, id: str) -> OperationLog | None:
        """根据 ID 获取记录"""
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return OperationLog(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[OperationLog]:
        """获取项目的所有操作日志"""
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [OperationLog(**item) for item in results]

    async def list_by_entity(
            self, project_id: str, entity_type: EntityType, entity_id: str
    ) -> List[OperationLog]:
        """获取某个实体的操作日志"""
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.entity_type == entity_type.value,
            self.model.entity_id == entity_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [OperationLog(**item) for item in results]

    async def list_by_action(self, project_id: str, action: OperationAction) -> List[OperationLog]:
        """根据操作类型筛选"""
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.action == action.value
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [OperationLog(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的操作日志数量"""
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有操作日志"""
        return await self.model.delete().where(
            self.model.project_id == project_id
        )


# 全局单例实例
operation_log_repository = OperationLogRepository()
