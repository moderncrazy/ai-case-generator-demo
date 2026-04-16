import uuid
from typing import List, Any
from datetime import datetime
from pydantic import BaseModel
from piccolo.query.functions.aggregate import Sum

from src.models.project_file import ProjectFile


class ProjectFileCreate(BaseModel):
    """创建项目文件参数"""
    project_id: str
    """所属项目 ID"""
    conversation_message_id: str
    """关联的对话消息 ID"""
    name: str
    """文件名"""
    path: str
    """文件路径"""
    type: str
    """文件类型（MIME type）"""
    size: int
    """文件大小（字节）"""
    content: str = None
    """文件内容"""
    summary: str = None
    """文件摘要"""
    metadata: str = None
    """元数据"""


class ProjectFileRepository:
    """项目文件 Repository
    
    提供项目文件（ProjectFile）的数据库操作，
    包括创建、查询、按对话关联、批量操作、统计等功能。
    """

    def __init__(self):
        self.model = ProjectFile

    async def create(self, project_file: ProjectFileCreate) -> str | None:
        """创建项目文件
        
        Args:
            project_file: 创建参数
            
        Returns:
            新建文件的 ID，失败返回 None
        """
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                project_id=project_file.project_id,
                conversation_message_id=project_file.conversation_message_id,
                name=project_file.name,
                path=project_file.path,
                type=project_file.type,
                size=project_file.size,
                content=project_file.content,
                summary=project_file.summary,
                metadata=project_file.metadata,
                created_at=datetime.now(),
            )
        )
        return results[0]["id"] if results else None

    async def bulk_create(self, project_files: List[ProjectFileCreate]) -> List[str]:
        """批量创建项目文件
        
        Args:
            project_files: 文件创建参数列表
            
        Returns:
            新建文件的 ID 列表
        """
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
                content=item.content,
                summary=item.summary,
                metadata=item.metadata,
                created_at=now,
            )
            for item in project_files
        ]
        results = await self.model.insert(*instances)
        return [item["id"] for item in results]

    async def get_by_id(self, id: str) -> ProjectFile | None:
        """根据 ID 获取文件
        
        Args:
            id: 文件 ID
            
        Returns:
            文件对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return ProjectFile(**result) if result else None

    async def get_by_project_and_name(self, project_id: str, name: str) -> ProjectFile | None:
        """根据项目和文件名获取文件
        
        Args:
            project_id: 项目 ID
            name: 文件名
            
        Returns:
            文件对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.name == name
        ).first()
        return ProjectFile(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[ProjectFile]:
        """获取项目的所有文件
        
        Args:
            project_id: 项目 ID
            
        Returns:
            文件列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [ProjectFile(**item) for item in results]

    async def list_by_conversation(self, conversation_message_id: str) -> List[ProjectFile]:
        """获取某个对话的所有文件
        
        Args:
            conversation_message_id: 对话消息 ID
            
        Returns:
            文件列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.conversation_message_id == conversation_message_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [ProjectFile(**item) for item in results]

    async def get_total_size(self, project_id: str) -> int:
        """获取项目文件的总大小
        
        Args:
            project_id: 项目 ID
            
        Returns:
            总大小（字节）
        """
        result = await (self.model.select(Sum(self.model.size))
                        .where(self.model.project_id == project_id)
                        .first())
        return result["sum"] or 0

    async def update_summary_by_project_and_name(self, project_id: str, name: str, summary: str) -> list[Any]:
        """更新文件摘要
        
        Args:
            project_id: 项目 ID
            name: 文件名
            summary: 新摘要
            
        Returns:
            更新结果
        """
        result = await self.model.update(
            self.model.summary == summary
        ).where(
            self.model.name == name,
            self.model.project_id == project_id
        )
        return result

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有文件记录
        
        Args:
            project_id: 项目 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def delete_by_conversation(self, conversation_message_id: str) -> int:
        """删除某个对话的所有文件记录
        
        Args:
            conversation_message_id: 对话消息 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.conversation_message_id == conversation_message_id
        )

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的文件数量
        
        Args:
            project_id: 项目 ID
            
        Returns:
            文件数量
        """
        return await self.model.count().where(
            self.model.project_id == project_id
        )


# 全局单例实例
project_file_repository = ProjectFileRepository()
