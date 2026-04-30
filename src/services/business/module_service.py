from src.graphs.common.schemas import StateModule
from src.services.business.redis_service import redis_service
from src.repositories.module_repository import module_repository, ModuleBulkUpdate


class ModuleService:
    """系统模块服务"""

    def __init__(self):
        self.repository = module_repository

    async def bulk_update_by_state_modules(self, project_id: str, modules: list[StateModule]):
        """批量更新模块

        根据状态数据批量更新项目的模块信息。

        Args:
            project_id: 项目 ID
            modules: 状态中的 module 列表
        """
        await self.repository.bulk_update(project_id, [ModuleBulkUpdate(**item) for item in modules])
        await redis_service.delete_project_basic_info_cache(project_id)


module_service = ModuleService()
