from typing import List

from src.models.api import Api
from src.repositories.module_repository import module_repository


class ApiService:
    """API 服务"""

    @staticmethod
    async def validate_module_ids(project_id: str, apis: List[Api]) -> dict:
        # 收集所有 module_id（排除 None 值）
        module_ids = set([api.module_id for api in apis if api.module_id is not None])
        existing_module_ids = []
        if module_ids:
            existing_modules = await module_repository.list_by_ids_and_project(project_id, [*module_ids])
            existing_module_ids = [module.id for module in existing_modules]
        # 找出无效的 API
        module_id_none = []
        module_id_not_found = []
        for api in apis:
            if api.module_id is None:
                module_id_none.append(api.id)
            elif api.module_id not in existing_module_ids:
                module_id_not_found.append(api.id)
        return {"module_id_none": module_id_none, "module_id_not_found": module_id_not_found}

    @staticmethod
    async def validate_module_ids_to_str(project_id: str, apis: List[Api]) -> str:
        error_message = ""
        result = await api_service.validate_module_ids(project_id, apis)
        if result.get("module_id_none"):
            error_message += f"模块Id为空：{",".join(result["module_id_none"])}\n"
        if result.get("module_id_not_found"):
            error_message += f"模块Id不存在：{",".join(result["module_id_not_found"])}\n"
        return error_message


# 导出单例
api_service = ApiService()
