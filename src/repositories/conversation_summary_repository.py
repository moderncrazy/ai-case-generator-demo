import uuid
from typing import List, Optional
from datetime import datetime

from src.models.business.conversation_summary import ConversationSummary


class ConversationSummaryRepository:
    """会话摘要 Repository
    
    提供会话摘要（ConversationSummary）的数据库操作，
    包括创建、查询、统计等功能。
    """

    def __init__(self):
        self.model = ConversationSummary

    async def create(
            self,
            project_id: str,
            summary: str,
            id: str = None,
            token_count: int = None,
    ) -> str | None:
        """创建会话摘要
        
        Args:
            project_id: 项目 ID
            summary: 摘要内容
            id: 摘要 ID（可选，默认自动生成）
            token_count: token 数量（可选）
            
        Returns:
            新建摘要的 ID，失败返回 None
        """
        results = await self.model.insert(
            self.model(
                id=id if id else str(uuid.uuid4()),
                project_id=project_id,
                summary=summary,
                token_count=token_count,
                created_at=datetime.now(),
            )
        )
        return results[0]["id"] if results else None

    async def get_by_id(self, id: str) -> Optional[ConversationSummary]:
        """根据 ID 获取摘要
        
        Args:
            id: 摘要 ID
            
        Returns:
            摘要对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return ConversationSummary(**result) if result else None

    async def get_latest(self, project_id: str) -> Optional[ConversationSummary]:
        """获取项目最新的摘要
        
        Args:
            project_id: 项目 ID
            
        Returns:
            最新的摘要对象，不存在返回 None
        """
        result = await (
            self.model.select()
            .where(self.model.project_id == project_id)
            .order_by(self.model.created_at, ascending=False)
            .first()
        )
        return ConversationSummary(**result) if result else None

    async def list_by_project(
            self,
            project_id: str,
            limit: int = 20,
    ) -> List[ConversationSummary]:
        """获取项目的所有摘要
        
        Args:
            project_id: 项目 ID
            limit: 返回数量限制（默认 20）
            
        Returns:
            摘要列表（按创建时间降序）
        """
        results = await (
            self.model.select()
            .where(self.model.project_id == project_id)
            .order_by(self.model.created_at, ascending=False)
            .limit(limit)
        )
        return [ConversationSummary(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的摘要数量
        
        Args:
            project_id: 项目 ID
            
        Returns:
            摘要数量
        """
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有摘要
        
        Args:
            project_id: 项目 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.project_id == project_id
        )


# 全局单例实例
conversation_summary_repository = ConversationSummaryRepository()