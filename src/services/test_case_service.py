from typing import List

from src.models.test_case import TestCase
from src.repositories.module_repository import module_repository


class TestCaseService:
    """Test Case 服务"""

    @staticmethod
    async def validate_module_ids(project_id: str, test_cases: List[TestCase]) -> dict:
        # 收集所有 module_id（排除 None 值）
        module_ids = set([item.module_id for item in test_cases if item.module_id is not None])
        existing_module_ids = []
        if module_ids:
            existing_modules = await module_repository.list_by_ids_and_project(project_id, [*module_ids])
            existing_module_ids = [module.id for module in existing_modules]
        # 找出无效的 TestCase
        module_id_none = []
        module_id_not_found = []
        for item in test_cases:
            if item.module_id is None:
                module_id_none.append(item.id)
            elif item.module_id not in existing_module_ids:
                module_id_not_found.append(item.id)
        return {"module_id_none": module_id_none, "module_id_not_found": module_id_not_found}

    @staticmethod
    async def validate_module_ids_to_str(project_id: str, test_cases: List[TestCase]) -> str:
        error_message = ""
        result = await test_case_service.validate_module_ids(project_id, test_cases)
        if result.get("module_id_none"):
            error_message += f"模块Id为空：{",".join(result["module_id_none"])}\n"
        if result.get("module_id_not_found"):
            error_message += f"模块Id不存在：{",".join(result["module_id_not_found"])}\n"
        return error_message


# 导出单例
test_case_service = TestCaseService()
