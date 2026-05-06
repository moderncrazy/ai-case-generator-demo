import os
import inspect
import pkgutil
import importlib

from pathlib import Path
from functools import lru_cache
from langchain.tools import BaseTool
from flashtext import KeywordProcessor

from src.enums.project_progress import ProjectProgress
from src.enums.instruction_template import InstructionTemplate
from src.graphs.common.base.output_tools import OptimizationDocOutputTools

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
                if name == "OptimizationDocOutputTools":
                    attr = getattr(module, name)
                    for output_name, _ in inspect.getmembers(attr):
                        if output_name.endswith("output"):
                            keyword_processor.add_keyword(output_name, EMPTY)
                elif not name.startswith("__"):
                    attr = getattr(module, name)
                    if isinstance(attr, BaseTool):
                        keyword_processor.add_keyword(attr.name, EMPTY)
        except Exception:
            continue
    return keyword_processor


@lru_cache()
def get_project_progress_keyword_processor():
    """将所有项目阶段替换成中文"""
    keyword_processor = KeywordProcessor()
    for progress in list(ProjectProgress):
        keyword_processor.add_keyword(progress.value, progress.name_zh)
    return keyword_processor


@lru_cache()
def get_instruction_template_keyword_processor():
    """将所有项目阶段替换成中文"""
    keyword_processor = KeywordProcessor()
    for item in list(InstructionTemplate):
        keyword_processor.add_keyword(item.value, item.name_zh)
    return keyword_processor


@lru_cache()
def get_workflow_keyword_processor():
    """将所有项目阶段替换成中文"""
    keyword_processor = KeywordProcessor()
    keyword_processor.add_keyword("next_step", "下一步骤")
    keyword_processor.add_keyword("metadata.module", "需求模块")
    keyword_processor.add_keyword("pass", "通过")
    keyword_processor.add_keyword("revise", "修正")
    keyword_processor.add_keyword("group_member_review", "团队审核")
    keyword_processor.add_keyword("review_issues", "审核意见")
    keyword_processor.add_keyword("risks", "风险项")
    keyword_processor.add_keyword("unclear_points", "待确认项")
    return keyword_processor


def filter_graph_tools(content: str) -> str:
    tools_keyword_processor = get_graph_tools_keyword_processor()
    return tools_keyword_processor.replace_keywords(content).replace(EMPTY, "").strip()


def filter_ai_output_content(content: str) -> str:
    workflow_keyword_processor = get_workflow_keyword_processor()
    tools_keyword_processor = get_graph_tools_keyword_processor()
    progress_keyword_processor = get_project_progress_keyword_processor()
    instruction_keyword_processor = get_instruction_template_keyword_processor()
    result = workflow_keyword_processor.replace_keywords(content)
    result = progress_keyword_processor.replace_keywords(result)
    result = instruction_keyword_processor.replace_keywords(result)
    return tools_keyword_processor.replace_keywords(result).replace(EMPTY, "").strip()
