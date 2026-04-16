import uuid
from typing import List, Any
from datetime import datetime

from src.enums.conversation_role import ConversationRole
from src.models.conversation_message import ConversationMessage


class ConversationMessageRepository:
    """对话消息 Repository
    
    提供对话消息（ConversationMessage）的数据库操作，
    包括创建、查询、按角色筛选、分页等功能。
    """

    def __init__(self):
        self.model = ConversationMessage

    async def create(
            self,
            project_id: str,
            content: str,
            role: ConversationRole,
            id: str = None,
            metadata: str = None,
    ) -> str | None:
        """创建对话消息
        
        Args:
            project_id: 项目 ID
            content: 消息内容
            role: 消息角色（user/assistant/system）
            id: 消息 ID（可选，默认自动生成）
            metadata: 元数据
            
        Returns:
            新建消息的 ID，失败返回 None
        """
        results = await self.model.insert(
            self.model(
                id=id if id else str(uuid.uuid4()),
                project_id=project_id,
                role=role.value,
                content=content,
                metadata=metadata,
                created_at=datetime.now(),
            )
        )
        return results[0]["id"] if results else None

    async def get_by_id(self, id: str) -> ConversationMessage | None:
        """根据 ID 获取消息
        
        Args:
            id: 消息 ID
            
        Returns:
            消息对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return ConversationMessage(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[ConversationMessage]:
        """获取项目的所有对话消息
        
        Args:
            project_id: 项目 ID
            
        Returns:
            消息列表（按创建时间升序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [ConversationMessage(**item) for item in results]

    async def list_by_role(self, project_id: str, role: ConversationRole) -> List[ConversationMessage]:
        """根据角色筛选对话消息
        
        Args:
            project_id: 项目 ID
            role: 消息角色
            
        Returns:
            符合条件消息列表（按创建时间升序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.role == role.value
        ).order_by(
            self.model.created_at, ascending=True
        )
        return [ConversationMessage(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的对话消息数量
        
        Args:
            project_id: 项目 ID
            
        Returns:
            消息数量
        """
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有对话消息
        
        Args:
            project_id: 项目 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def paginate(
            self, project_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list, int]:
        """分页查询对话消息
        
        Args:
            project_id: 项目 ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            (消息列表, 总数) 元组
        """
        total = await self.model.count().where(
            self.model.project_id == project_id
        )
        # 先按时间递减查询最新的消息 再手工倒序
        results = await (
            self.model.select()
            .where(self.model.project_id == project_id)
            .order_by(self.model.created_at, ascending=False)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        messages = list(reversed([ConversationMessage(**item) for item in results]))
        return messages, total


# 全局单例实例
conversation_message_repository = ConversationMessageRepository()
