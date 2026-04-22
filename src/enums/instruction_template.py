from enum import Enum
from pathlib import Path
from functools import cached_property


class InstructionTemplate(Enum):
    """指令模板枚举，PM用于给内部agent下指令"""

    REQUIREMENT_OUTLINE_CREATE = "requirement_outline_create"
    REQUIREMENT_OUTLINE_UPDATE = "requirement_outline_update"
    REQUIREMENT_MODULE_CREATE = "requirement_module_create"
    REQUIREMENT_MODULE_UPDATE = "requirement_module_update"
    REQUIREMENT_OVERALL_CREATE = "requirement_overall_create"
    REQUIREMENT_OVERALL_UPDATE = "requirement_overall_update"
    SYSTEM_ARCHITECTURE_CREATE = "system_architecture_create"
    SYSTEM_ARCHITECTURE_UPDATE = "system_architecture_update"
    SYSTEM_MODULES_CREATE = "system_modules_create"
    SYSTEM_MODULES_UPDATE = "system_modules_update"
    SYSTEM_DATABASE_CREATE = "system_database_create"
    SYSTEM_DATABASE_UPDATE = "system_database_update"
    SYSTEM_API_CREATE = "system_api_create"
    SYSTEM_API_UPDATE = "system_api_update"
    TEST_CASE_CREATE = "test_case_create"
    TEST_CASE_UPDATE = "test_case_update"

    @cached_property
    def text(self) -> str:
        """从文件加载模板内容（带缓存）"""
        template_dir = Path(__file__).parent.parent.parent / "template" / "instruction"
        file_path = template_dir / f"{self.value}.md"
        return file_path.read_text(encoding="utf-8")
