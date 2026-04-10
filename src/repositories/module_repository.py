import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from src.models.module import Module


class ModuleCreate(BaseModel):
    """创建模块参数"""
    project_id: str
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = None


class ModuleRepository:
    """模块 Repository"""

    def __init__(self):
        self.model = Module

    async def create(self, module: ModuleCreate) -> str | None:
        """创建模块"""
        now = datetime.now()
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                project_id=module.project_id,
                parent_id=module.parent_id,
                name=module.name,
                description=module.description,
                created_at=now,
                updated_at=now,
            )
        )
        return results[0]["id"] if results else None

    async def update(
        self,
        id: str,
        name: Optional[str] = None,
        parent_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """更新模块"""
        update_data = {self.model.updated_at: datetime.now()}
        if name is not None:
            update_data[self.model.name] = name
        if parent_id is not None:
            update_data[self.model.parent_id] = parent_id
        if description is not None:
            update_data[self.model.description] = description

        await self.model.update(update_data).where(
            self.model.id == id
        )

    async def get_by_id(self, id: str) -> Optional[Module]:
        """根据 ID 获取记录"""
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return Module(**result) if result else None

    async def list_by_ids_and_project(self,project_id: str, module_ids: List[str]) -> List[Module]:
        """根据 module_id 列表和项目 ID 批量查询模块

        Args:
            project_id: 项目 ID
            module_ids: module_id 列表

        Returns:
            存在的模块列表
        """
        results = await self.model.select().where(
            self.model.id.in_(module_ids),
            self.model.project_id == project_id
        )
        return [Module(**item) for item in results]

    async def list_by_project(self, project_id: str) -> List[Module]:
        """获取项目的所有模块"""
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [Module(**item) for item in results]

    async def get_root_modules(self, project_id: str) -> List[Module]:
        """获取项目的根模块（parent_id 为空）"""
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.parent_id.is_null()
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [Module(**item) for item in results]

    async def get_children(self, parent_id: str) -> List[Module]:
        """获取子模块"""
        results = await self.model.select().where(
            self.model.parent_id == parent_id
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [Module(**item) for item in results]

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有模块"""
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def bulk_update(self, project_id: str, modules: List[ModuleCreate]) -> List[str]:
        """批量更新模块（先删除项目下所有模块再插入）

        Args:
            project_id: 项目ID
            modules: 模块更新参数列表

        Returns:
            插入的模块ID列表
        """
        # 先删除项目下所有模块
        await self.delete_by_project(project_id)

        now = datetime.now()
        instances = [
            self.model(
                id=str(uuid.uuid4()),
                project_id=project_id,
                parent_id=item.parent_id,
                name=item.name,
                description=item.description,
                created_at=now,
                updated_at=now,
            )
            for item in modules
        ]
        results = await self.model.insert(*instances)
        return [item["id"] for item in results]


# 全局单例实例
module_repository = ModuleRepository()
