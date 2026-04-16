import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from src.models.project import Project
from src.enums.creator_type import CreatorType
from src.enums.project_progress import ProjectProgress


class ProjectUpdate(BaseModel):
    """更新项目参数"""
    name: Optional[str] = None
    """项目名称"""
    description: Optional[str] = None
    """项目描述"""
    requirement_outline_design: Optional[str] = None
    """需求大纲设计"""
    requirement_module_design: Optional[str] = None
    """需求模块设计"""
    requirement_overall_design: Optional[str] = None
    """整体需求文档设计"""
    architecture_design: Optional[str] = None
    """系统架构设计"""
    database_design: Optional[str] = None
    """数据库设计"""
    progress: Optional[ProjectProgress] = None
    """项目进度状态"""
    creator_type: Optional[CreatorType] = None
    """创建者类型"""


class ProjectRepository:
    """项目 Repository
    
    提供项目（Project）的数据库操作，
    包括创建、更新、查询、列表、分页等功能。
    """

    def __init__(self):
        self.model = Project

    async def create(
            self,
            name: str,
            description: Optional[str] = None,
            creator_type: CreatorType = CreatorType.USER,
    ) -> str | None:
        """创建项目
        
        Args:
            name: 项目名称
            description: 项目描述
            creator_type: 创建者类型（用户/AI）
            
        Returns:
            新建项目的 ID，失败返回 None
        """
        now = datetime.now()
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                progress=ProjectProgress.INIT.value,
                creator_type=creator_type.value,
                created_at=now,
                updated_at=now,
            )
        )
        return results[0]["id"] if results else None

    async def update(
            self,
            id: str,
            project_update: ProjectUpdate,
    ) -> None:
        """更新项目
        
        Args:
            id: 项目 ID
            project_update: 更新参数
        """
        update_data = {self.model.updated_at: datetime.now()}
        if project_update.name is not None:
            update_data[self.model.name] = project_update.name
        if project_update.description is not None:
            update_data[self.model.description] = project_update.description
        if project_update.requirement_outline_design is not None:
            update_data[self.model.requirement_outline_design] = project_update.requirement_outline_design
        if project_update.requirement_module_design is not None:
            update_data[self.model.requirement_module_design] = project_update.requirement_module_design
        if project_update.requirement_overall_design is not None:
            update_data[self.model.requirement_overall_design] = project_update.requirement_overall_design
        if project_update.architecture_design is not None:
            update_data[self.model.architecture_design] = project_update.architecture_design
        if project_update.database_design is not None:
            update_data[self.model.database_design] = project_update.database_design
        if project_update.progress is not None:
            update_data[self.model.progress] = project_update.progress.value
        if project_update.creator_type is not None:
            update_data[self.model.creator_type] = project_update.creator_type.value

        await self.model.update(update_data).where(
            self.model.id == id
        )

    async def get_by_id(self, id: str) -> Optional[Project]:
        """根据 ID 获取项目
        
        Args:
            id: 项目 ID
            
        Returns:
            项目对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return Project(**result) if result else None

    async def get_by_name(self, name: str) -> Optional[Project]:
        """根据名称获取项目
        
        Args:
            name: 项目名称
            
        Returns:
            项目对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.name == name
        ).first()
        return Project(**result) if result else None

    async def list_by_progress(
            self, progress: ProjectProgress, limit: int = 100, offset: int = 0
    ) -> List[Project]:
        """根据进度筛选项目列表
        
        Args:
            progress: 进度状态
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            符合条件项目列表
        """
        results = await self.model.select().where(
            self.model.progress == progress.value
        ).order_by(
            self.model.created_at, ascending=False
        ).limit(limit).offset(offset)
        return [Project(**item) for item in results]

    async def paginate(
            self, page: int = 1, page_size: int = 20, progress: Optional[ProjectProgress] = None
    ) -> tuple[List[Project], int]:
        """分页查询项目
        
        Args:
            page: 页码（从 1 开始）
            page_size: 每页数量
            progress: 按进度筛选（可选）
            
        Returns:
            (项目列表, 总数) 元组
        """
        # 数据查询
        if progress:
            total = await (self.model.count()
                           .where(self.model.progress == progress.value))
            results = await (self.model.select()
                             .where(self.model.progress == progress.value)
                             .order_by(self.model.created_at, ascending=False)
                             .offset((page - 1) * page_size)
                             .limit(page_size))
        else:
            total = await self.model.count()
            results = await (self.model.select()
                             .order_by(self.model.created_at, ascending=False)
                             .offset((page - 1) * page_size)
                             .limit(page_size))

        projects = [Project(**item) for item in results]
        return projects, total


# 全局单例实例
project_repository = ProjectRepository()
