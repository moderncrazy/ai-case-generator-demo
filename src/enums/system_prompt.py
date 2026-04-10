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
    OPTIMIZED_REQUIREMENT = "optimized_requirement"
    REVIEW_REQUIREMENT_PM = "review_requirement_pm"
    REVIEW_REQUIREMENT_ARCHITECT = "review_requirement_architect"
    REVIEW_REQUIREMENT_FRONTEND = "review_requirement_frontend"
    REVIEW_REQUIREMENT_BACKEND = "review_requirement_backend"
    REVIEW_REQUIREMENT_TEST = "review_requirement_test"
    OPTIMIZED_REQUIREMENT_ISSUE = "optimized_requirement_issue"
    PROJECT_REQUIREMENT_PM = "project_requirement_pm"
    ARCHITECTURE_CONTENT = "architecture_content"
    DATABASE_CONTENT = "database_content"

    @cached_property
    def text(self) -> str:
        """从文件加载提示词内容（带缓存）"""
        prompt_dir = Path(__file__).parent.parent.parent / "prompts"
        file_path = prompt_dir / f"{self.value}.txt"
        return file_path.read_text(encoding="utf-8")

    @cached_property
    def template(self) -> PromptTemplate:
        return PromptTemplate.from_template(self.text, template_format="jinja2")
