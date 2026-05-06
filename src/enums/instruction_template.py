from pathlib import Path
from enum import StrEnum
from functools import cached_property


class InstructionTemplate(StrEnum):
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

    @cached_property
    def name_zh(self) -> str:
        """获取中文名称"""
        match self:
            case InstructionTemplate.REQUIREMENT_OUTLINE_CREATE:
                return "创建需求大纲模板"
            case InstructionTemplate.REQUIREMENT_OUTLINE_UPDATE:
                return "更新需求大纲模板"
            case InstructionTemplate.REQUIREMENT_MODULE_CREATE:
                return "创建需求模块模板"
            case InstructionTemplate.REQUIREMENT_MODULE_UPDATE:
                return "更新需求模块模板"
            case InstructionTemplate.REQUIREMENT_OVERALL_CREATE:
                return "创建需求文档模板"
            case InstructionTemplate.REQUIREMENT_OVERALL_UPDATE:
                return "更新需求文档模板"
            case InstructionTemplate.SYSTEM_ARCHITECTURE_CREATE:
                return "创建系统架构模板"
            case InstructionTemplate.SYSTEM_ARCHITECTURE_UPDATE:
                return "更新系统架构模板"
            case InstructionTemplate.SYSTEM_MODULES_CREATE:
                return "创建系统模块模板"
            case InstructionTemplate.SYSTEM_MODULES_UPDATE:
                return "更新系统模块模板"
            case InstructionTemplate.SYSTEM_DATABASE_CREATE:
                return "创建系统数据库模板"
            case InstructionTemplate.SYSTEM_DATABASE_UPDATE:
                return "更新系统数据库模板"
            case InstructionTemplate.SYSTEM_API_CREATE:
                return "创建系统接口模板"
            case InstructionTemplate.SYSTEM_API_UPDATE:
                return "更新系统接口模板"
            case InstructionTemplate.TEST_CASE_CREATE:
                return "创建测试用例模板"
            case InstructionTemplate.TEST_CASE_UPDATE:
                return "更新测试用例模板"

