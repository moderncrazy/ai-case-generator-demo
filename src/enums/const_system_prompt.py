from enum import Enum
from pathlib import Path
from functools import cached_property
from langchain_core.prompts import PromptTemplate


class ConstSystemPrompt(Enum):
    """固定系统提示词枚举 注意：使用 jinja2 格式"""

    DOCUMENT_CHECK = "document_check"
    DOCUMENT_EXTRACTOR = "document_extractor"
    FILE_SUMMARY = "file_summary"
    CONTEXT_SUMMARY = "context_summary"

    @cached_property
    def text(self) -> str:
        """从文件加载提示词内容（带缓存）"""
        prompt_dir = Path(__file__).parent.parent.parent / "template/prompts/constant"
        file_path = prompt_dir / f"{self.value}.md"
        return file_path.read_text(encoding="utf-8")

    @cached_property
    def template(self) -> PromptTemplate:
        return PromptTemplate.from_template(self.text, template_format="jinja2")
