from enum import Enum
from pathlib import Path
from functools import cached_property


class SystemPrompt(Enum):
    """系统提示词枚举"""

    PRD_CONTENT = "prd_content"
    ARCHITECTURE_CONTENT = "architecture_content"
    DATABASE_CONTENT = "database_content"
    DOCUMENT_EXTRACTOR = "document_extractor"
    DOCUMENT_CHECK = "document_check"
    PROJECT_INIT_PM = "project_init_pm"

    @cached_property
    def text(self) -> str:
        """从文件加载提示词内容（带缓存）"""
        prompt_dir = Path(__file__).parent.parent.parent / "prompts"
        file_path = prompt_dir / f"{self.value}.txt"
        return file_path.read_text(encoding="utf-8")
