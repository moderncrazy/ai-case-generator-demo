import uuid
from typing import List, Any
from datetime import datetime

from src.enums import ConversationRole
from src.models import ConversationMessage


class ConversationMessageRepository:
    """对话消息 Repository"""

    def __init__(self):
        self.model = ConversationMessage

    async def create(
            self,
            project_id: str,
            role: ConversationRole,
            content: str = None,
            metadata: str = None,
    ) -> str | None:
        """创建对话消息"""
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                project_id=project_id,
                role=role.value,
                content=content,
                metadata=metadata,
                created_at=datetime.now(),
            )
        )
        return results[0]["id"] if results else None

    async def get_by_id(self, id: str) -> ConversationMessage | None:
        """根据 ID 获取记录"""
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return ConversationMessage(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[ConversationMessage]:
        """获取项目的所有对话消息"""
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [ConversationMessage(**item) for item in results]

    async def list_by_role(self, project_id: str, role: ConversationRole) -> List[ConversationMessage]:
        """根据角色筛选对话消息"""
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.role == role.value
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [ConversationMessage(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的对话消息数量"""
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有对话消息"""
        return await self.model.delete().where(
            self.model.project_id == project_id
        )


# 全局单例实例
conversation_message_repository = ConversationMessageRepository()
