import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from src.models.business.operation_log import OperationLog
from src.enums.entity_type import EntityType
from src.enums.operation_action import OperationAction


class OperationLogCreate(BaseModel):
    """创建操作日志参数"""
    project_id: str
    """所属项目 ID"""
    entity_type: EntityType
    """实体类型"""
    entity_id: str
    """实体 ID"""
    action: OperationAction
    """操作类型"""
    detail: Optional[str] = None
    """操作详情"""


class OperationLogRepository:
    """操作日志 Repository
    
    提供操作日志（OperationLog）的数据库操作，
    用于记录和查询项目中的关键操作，支持审计和追踪。
    """

    def __init__(self):
        self.model = OperationLog

    async def create(self, log: OperationLogCreate) -> str | None:
        """创建操作日志
        
        Args:
            log: 创建参数
            
        Returns:
            新建日志的 ID，失败返回 None
        """
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
        """根据 ID 获取日志
        
        Args:
            id: 日志 ID
            
        Returns:
            日志对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return OperationLog(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[OperationLog]:
        """获取项目的所有操作日志
        
        Args:
            project_id: 项目 ID
            
        Returns:
            日志列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [OperationLog(**item) for item in results]

    async def list_by_entity(
            self, project_id: str, entity_type: EntityType, entity_id: str
    ) -> List[OperationLog]:
        """获取某个实体的操作日志
        
        Args:
            project_id: 项目 ID
            entity_type: 实体类型
            entity_id: 实体 ID
            
        Returns:
            日志列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.entity_type == entity_type.value,
            self.model.entity_id == entity_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [OperationLog(**item) for item in results]

    async def list_by_action(self, project_id: str, action: OperationAction) -> List[OperationLog]:
        """根据操作类型筛选
        
        Args:
            project_id: 项目 ID
            action: 操作类型
            
        Returns:
            符合条件日志列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.action == action.value
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [OperationLog(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的操作日志数量
        
        Args:
            project_id: 项目 ID
            
        Returns:
            日志数量
        """
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有操作日志
        
        Args:
            project_id: 项目 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.project_id == project_id
        )


# 全局单例实例
operation_log_repository = OperationLogRepository()
