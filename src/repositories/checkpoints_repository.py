from src.models.checkpoint.checkpoints import Checkpoints


class CheckpointsRepository:
    """Checkpoint Repository
    
    提供 Checkpoint 表的数据库操作。
    """

    def __init__(self):
        self.model = Checkpoints

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
checkpoints_repository = CheckpointsRepository()
