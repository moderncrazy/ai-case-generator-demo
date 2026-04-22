import os
import pkgutil
import importlib

from pathlib import Path
from functools import lru_cache
from langchain.tools import BaseTool
from flashtext import KeywordProcessor

from src.enums.project_progress import ProjectProgress

EMPTY = "__EMPTY__"


@lru_cache()
def get_graph_tools_keyword_processor():
    """将所有工具方法加入敏感词，替换为空"""
    keyword_processor = KeywordProcessor()
    # 自动发现所有 BaseTool 子类
    graphs_pkg = Path(__file__).resolve().parent.parent / "graphs"
    for finder, module_name, is_pkg in pkgutil.walk_packages(path=[graphs_pkg], prefix="src.graphs."):
        try:
            module = importlib.import_module(module_name)
            for name in dir(module):
                if not name.startswith("__") and isinstance(getattr(module, name), BaseTool):
                    keyword_processor.add_keyword(name, EMPTY)
        except Exception:
            continue
    return keyword_processor


@lru_cache()
def get_project_progress_keyword_processor():
    """将所有项目阶段替换成中文"""
    keyword_processor = KeywordProcessor()
    for progress in list(ProjectProgress):
        keyword_processor.add_keyword(progress.value, progress.get_name_zh())
    return keyword_processor


def filter_ai_output_content(content: str) -> str:
    tools_keyword_processor = get_graph_tools_keyword_processor()
    progress_keyword_processor = get_project_progress_keyword_processor()
    result = progress_keyword_processor.replace_keywords(content)
    return tools_keyword_processor.replace_keywords(result).replace(EMPTY, "").strip()
