import uuid
from datetime import datetime
from typing import Optional, List

from src.models import Project
from src.enums import CreatorType, ProjectProgress


class ProjectRepository:
    """项目 Repository"""

    def __init__(self):
        self.model = Project

    async def create(
            self,
            name: str,
            description: Optional[str] = None,
            creator_type: CreatorType = CreatorType.USER,
    ) -> str | None:
        """创建项目"""
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
            name: Optional[str] = None,
            description: Optional[str] = None,
            requirement_content: Optional[str] = None,
            requirement_optimized_content: Optional[str] = None,
            requirement_risks: Optional[str] = None,
            requirement_unclear_points: Optional[str] = None,
            architecture_design: Optional[str] = None,
            database_design: Optional[str] = None,
            progress: Optional[str] = None,
            creator_type: Optional[str] = None,
    ) -> None:
        """更新项目"""
        update_data = {self.model.updated_at: datetime.now()}
        if name is not None:
            update_data[self.model.name] = name
        if description is not None:
            update_data[self.model.description] = description
        if requirement_content is not None:
            update_data[self.model.requirement_content] = requirement_content
        if requirement_optimized_content is not None:
            update_data[self.model.requirement_optimized_content] = requirement_optimized_content
        if requirement_risks is not None:
            update_data[self.model.requirement_risks] = requirement_risks
        if requirement_unclear_points is not None:
            update_data[self.model.requirement_unclear_points] = requirement_unclear_points
        if architecture_design is not None:
            update_data[self.model.architecture_design] = architecture_design
        if database_design is not None:
            update_data[self.model.database_design] = database_design
        if progress is not None:
            update_data[self.model.progress] = progress
        if creator_type is not None:
            update_data[self.model.creator_type] = creator_type

        await self.model.update(update_data).where(
            self.model.id == id
        )

    async def get_by_id(self, id: str) -> Optional[Project]:
        """根据 ID 获取记录"""
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return Project(**result) if result else None

    async def get_by_name(self, name: str) -> Optional[Project]:
        """根据名称获取项目"""
        result = await self.model.select().where(
            self.model.name == name
        ).first()
        return Project(**result) if result else None

    async def list_by_progress(
            self, progress: ProjectProgress, limit: int = 100, offset: int = 0
    ) -> List[Project]:
        """根据进度筛选项目"""
        results = await self.model.select().where(
            self.model.progress == progress.value
        ).order_by(
            self.model.created_at, ascending=False
        ).limit(limit).offset(offset)
        return [Project(**item) for item in results]

    async def paginate(
            self, page: int = 1, page_size: int = 20, progress: Optional[ProjectProgress] = None
    ) -> tuple[List[Project], int]:
        """分页查询项目"""
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
