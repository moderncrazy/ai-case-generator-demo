from src.services.business.redis_service import redis_service
from src.repositories.project_repository import project_repository, ProjectUpdate


class ProjectService:
    """项目服务
    
    提供项目相关的业务逻辑处理
    """

    def __init__(self):
        self.repository = project_repository

    async def update_project_and_clear_cache(self, project_id: str, project_update: ProjectUpdate):
        """更新项目并清除缓存"""
        await self.repository.update(project_id, project_update)
        await redis_service.delete_project_basic_info_cache(project_id)


project_service = ProjectService()
