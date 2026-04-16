from enum import Enum
from pathlib import Path
from functools import cached_property
from langchain_core.prompts import PromptTemplate


class SystemPrompt(Enum):
    """系统提示词枚举 注意：使用 jinja2 格式"""

    DOCUMENT_CHECK = "document_check"
    DOCUMENT_EXTRACTOR = "document_extractor"
    FILE_SUMMARY = "file_summary"
    PROJECT_INIT_PM = "project_init_pm"
    OPTIMIZED_REQUIREMENT_OUTLINE = "optimized_requirement_outline"
    PROJECT_REQUIREMENT_OUTLINE_PM = "project_requirement_outline_pm"
    OPTIMIZED_REQUIREMENT_MODULE = "optimized_requirement_module"
    REVIEW_REQUIREMENT_MODULE_PM = "review_requirement_module_pm"
    REVIEW_REQUIREMENT_MODULE_ARCHITECT = "review_requirement_module_architect"
    REVIEW_REQUIREMENT_MODULE_FRONTEND = "review_requirement_module_frontend"
    REVIEW_REQUIREMENT_MODULE_BACKEND = "review_requirement_module_backend"
    REVIEW_REQUIREMENT_MODULE_TEST = "review_requirement_module_test"
    OPTIMIZED_REQUIREMENT_MODULE_ISSUE = "optimized_requirement_module_issue"
    PROJECT_REQUIREMENT_MODULE_PM = "project_requirement_module_pm"
    OPTIMIZED_REQUIREMENT_OVERALL = "optimized_requirement_overall"
    REVIEW_REQUIREMENT_OVERALL_PM = "review_requirement_overall_pm"
    REVIEW_REQUIREMENT_OVERALL_ARCHITECT = "review_requirement_overall_architect"
    REVIEW_REQUIREMENT_OVERALL_FRONTEND = "review_requirement_overall_frontend"
    REVIEW_REQUIREMENT_OVERALL_BACKEND = "review_requirement_overall_backend"
    REVIEW_REQUIREMENT_OVERALL_TEST = "review_requirement_overall_test"
    OPTIMIZED_REQUIREMENT_OVERALL_ISSUE = "optimized_requirement_overall_issue"
    PROJECT_REQUIREMENT_OVERALL_PM = "project_requirement_overall_pm"
    OPTIMIZE_SYSTEM_ARCHITECTURE = "optimize_system_architecture"
    REVIEW_SYSTEM_ARCHITECTURE_PM = "review_system_architecture_pm"
    REVIEW_SYSTEM_ARCHITECTURE_ARCHITECT = "review_system_architecture_architect"
    REVIEW_SYSTEM_ARCHITECTURE_FRONTEND = "review_system_architecture_frontend"
    REVIEW_SYSTEM_ARCHITECTURE_BACKEND = "review_system_architecture_backend"
    REVIEW_SYSTEM_ARCHITECTURE_SRE = "review_system_architecture_sre"
    OPTIMIZE_SYSTEM_ARCHITECTURE_ISSUE = "optimize_system_architecture_issue"
    PROJECT_SYSTEM_ARCHITECTURE_PM = "project_system_architecture_pm"
    OPTIMIZE_SYSTEM_MODULE = "optimize_system_module"
    REVIEW_SYSTEM_MODULE_PM = "review_system_module_pm"
    REVIEW_SYSTEM_MODULE_ARCHITECT = "review_system_module_architect"
    REVIEW_SYSTEM_MODULE_FRONTEND = "review_system_module_frontend"
    REVIEW_SYSTEM_MODULE_BACKEND = "review_system_module_backend"
    REVIEW_SYSTEM_MODULE_SRE = "review_system_module_sre"
    PROJECT_SYSTEM_MODULES_PM = "project_system_modules_pm"
    OPTIMIZE_SYSTEM_DATABASE = "optimize_system_database"
    REVIEW_SYSTEM_DATABASE_PM = "review_system_database_pm"
    REVIEW_SYSTEM_DATABASE_ARCHITECT = "review_system_database_architect"
    REVIEW_SYSTEM_DATABASE_DBA = "review_system_database_dba"
    REVIEW_SYSTEM_DATABASE_BACKEND = "review_system_database_backend"
    REVIEW_SYSTEM_DATABASE_SRE = "review_system_database_sre"
    PROJECT_SYSTEM_DATABASE_PM = "project_system_database_pm"
    OPTIMIZE_SYSTEM_API = "optimize_system_api"
    REVIEW_SYSTEM_API_PM = "review_system_api_pm"
    REVIEW_SYSTEM_API_ARCHITECT = "review_system_api_architect"
    REVIEW_SYSTEM_API_FRONTEND = "review_system_api_frontend"
    REVIEW_SYSTEM_API_BACKEND = "review_system_api_backend"
    REVIEW_SYSTEM_API_TEST = "review_system_api_test"
    REVIEW_SYSTEM_API_SRE = "review_system_api_sre"
    PROJECT_SYSTEM_API_PM = "project_system_api_pm"
    OPTIMIZE_TEST_CASE = "optimize_test_case"
    REVIEW_TEST_CASE_PM = "review_test_case_pm"
    REVIEW_TEST_CASE_ARCHITECT = "review_test_case_architect"
    REVIEW_TEST_CASE_FRONTEND = "review_test_case_frontend"
    REVIEW_TEST_CASE_BACKEND = "review_test_case_backend"
    REVIEW_TEST_CASE_TEST = "review_test_case_test"
    PROJECT_TEST_CASE_PM = "project_test_case_pm"
    PROJECT_COMPLETED_PM = "project_completed_pm"

    @cached_property
    def text(self) -> str:
        """从文件加载提示词内容（带缓存）"""
        prompt_dir = Path(__file__).parent.parent.parent / "prompts"
        file_path = prompt_dir / f"{self.value}.txt"
        return file_path.read_text(encoding="utf-8")

    @cached_property
    def template(self) -> PromptTemplate:
        return PromptTemplate.from_template(self.text, template_format="jinja2")
