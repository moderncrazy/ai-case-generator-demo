from src import constant as const
from src.repositories.conversation_summary_repository import conversation_summary_repository


class ConversationSummaryService:
    """会话摘要服务
    
    提供会话摘要相关的业务逻辑处理。
    """

    @staticmethod
    async def get_conversation_summary_to_str(project_id: str, limit: int = 20) -> str:
        """提取项目会话摘转为字符串"""
        summaries = await conversation_summary_repository.list_by_project(project_id, limit)
        content = "\n\n".join([f"摘要时间：{item.created_at}\n摘要内容：{item.summary}" for item in summaries])
        return content if content else const.EMPTY_ZH


# 导出单例
conversation_summary_service = ConversationSummaryService()
