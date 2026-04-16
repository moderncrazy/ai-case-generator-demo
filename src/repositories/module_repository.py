import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from src.models.module import Module


class ModuleCreate(BaseModel):
    """创建模块参数"""
    project_id: str
    """所属项目 ID"""
    name: str
    """模块名称"""
    parent_id: Optional[str] = None
    """父模块 ID（顶级模块为空）"""
    description: Optional[str] = None
    """模块描述"""


class ModuleUpdate(BaseModel):
    """更新模块参数"""
    name: str
    """模块名称"""
    parent_id: Optional[str] = None
    """父模块 ID"""
    description: Optional[str] = None
    """模块描述"""


class ModuleRepository:
    """模块 Repository
    
    提供模块（Module）的数据库操作，
    包括创建、更新、查询、层级关系、批量操作等功能。
    """

    def __init__(self):
        self.model = Module

    async def create(self, module: ModuleCreate) -> str | None:
        """创建模块
        
        Args:
            module: 创建参数
            
        Returns:
            新建模块的 ID，失败返回 None
        """
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
        """更新模块
        
        Args:
            id: 模块 ID
            name: 模块名称
            parent_id: 父模块 ID
            description: 模块描述
        """
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
        """根据 ID 获取模块
        
        Args:
            id: 模块 ID
            
        Returns:
            模块对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return Module(**result) if result else None

    async def list_by_ids_and_project(self, project_id: str, module_ids: List[str]) -> List[Module]:
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
        """获取项目的所有模块
        
        Args:
            project_id: 项目 ID
            
        Returns:
            模块列表（按创建时间升序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [Module(**item) for item in results]

    async def get_root_modules(self, project_id: str) -> List[Module]:
        """获取项目的根模块（parent_id 为空）
        
        Args:
            project_id: 项目 ID
            
        Returns:
            根模块列表
        """
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.parent_id.is_null()
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [Module(**item) for item in results]

    async def get_children(self, parent_id: str) -> List[Module]:
        """获取子模块
        
        Args:
            parent_id: 父模块 ID
            
        Returns:
            子模块列表
        """
        results = await self.model.select().where(
            self.model.parent_id == parent_id
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [Module(**item) for item in results]

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有模块
        
        Args:
            project_id: 项目 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def bulk_update(self, project_id: str, modules: List[ModuleUpdate]) -> List[str]:
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

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的模块数量
        
        Args:
            project_id: 项目 ID
            
        Returns:
            模块数量
        """
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def paginate(
            self, project_id: str, page: int = 1, page_size: int = 20, parent_id: str = None,
    ) -> tuple[List[Module], int]:
        """分页查询项目模块
        
        Args:
            project_id: 项目 ID
            page: 页码
            page_size: 每页数量
            parent_id: 按父模块筛选
            
        Returns:
            (模块列表, 总数) 元组
        """
        # 数据查询
        if parent_id:
            total = await (self.model.count()
                           .where(self.model.parent_id == parent_id))
            results = await (self.model.select()
                             .where(self.model.parent_id == parent_id)
                             .order_by(self.model.created_at, ascending=False)
                             .offset((page - 1) * page_size)
                             .limit(page_size))
        else:
            total = await self.model.count()
            results = await (self.model.select()
                             .order_by(self.model.created_at, ascending=False)
                             .offset((page - 1) * page_size)
                             .limit(page_size))

        modules = [Module(**item) for item in results]
        return modules, total


# 全局单例实例
module_repository = ModuleRepository()
