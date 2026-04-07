import uuid
from typing import List
from datetime import datetime
from pydantic import BaseModel
from piccolo.query.functions.aggregate import Sum

from src.models import ProjectFile


class ProjectFileCreate(BaseModel):
    project_id: str
    conversation_message_id: str
    name: str
    path: str
    type: str
    size: int
    metadata: str = None


class ProjectFileRepository:
    """项目文件 Repository"""

    def __init__(self):
        self.model = ProjectFile

    async def create(self, project_file: ProjectFileCreate) -> str | None:
        """创建项目文件"""
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                project_id=project_file.project_id,
                conversation_message_id=project_file.conversation_message_id,
                name=project_file.name,
                path=project_file.path,
                type=project_file.type,
                size=project_file.size,
                metadata=project_file.metadata,
                created_at=datetime.now(),
            )
        )
        return results[0]["id"] if results else None

    async def bulk_create(self, project_files: List[ProjectFileCreate]) -> List[str]:
        """批量创建项目文件"""
        now = datetime.now()
        instances = [
            self.model(
                id=str(uuid.uuid4()),
                project_id=item.project_id,
                conversation_message_id=item.conversation_message_id,
                name=item.name,
                path=item.path,
                type=item.type,
                size=item.size,
                metadata=item.metadata,
                created_at=now,
            )
            for item in project_files
        ]
        results = await self.model.insert(*instances)
        return [item["id"] for item in results]

    async def get_by_id(self, id: str) -> ProjectFile | None:
        """根据 ID 获取记录"""
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return ProjectFile(**result) if result else None

    async def get_by_project_and_name(self, project_id: str, name: str) -> ProjectFile | None:
        """获取项目的所有文件"""
        result = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.name == name
        ).first()
        return ProjectFile(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[ProjectFile]:
        """获取项目的所有文件"""
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [ProjectFile(**item) for item in results]

    async def list_by_conversation(self, conversation_message_id: str) -> List[ProjectFile]:
        """获取某个对话的所有文件"""
        results = await self.model.select().where(
            self.model.conversation_message_id == conversation_message_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [ProjectFile(**item) for item in results]

    async def get_total_size(self, project_id: str) -> int:
        """获取项目文件的总大小"""
        result = await (self.model.select(Sum(self.model.size))
                        .where(self.model.project_id == project_id)
                        .first())
        return result["sum"] or 0

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有文件记录"""
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def delete_by_conversation(self, conversation_message_id: str) -> int:
        """删除某个对话的所有文件记录"""
        return await self.model.delete().where(
            self.model.conversation_message_id == conversation_message_id
        )


# 全局单例实例
project_file_repository = ProjectFileRepository()
