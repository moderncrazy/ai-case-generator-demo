from src.models.checkpoint.writes import Writes


class WritesRepository:
    """Write Repository
    
    提供 Write 表的数据库操作。
    """

    def __init__(self):
        self.model = Writes

    async def delete_by_checkpoint_id(self, checkpoint_id: str) -> int:
        """根据 checkpoint_id 删除数据
        
        Args:
            checkpoint_id: 检查点 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.checkpoint_id == checkpoint_id
        )


# 全局单例实例
writes_repository = WritesRepository()
