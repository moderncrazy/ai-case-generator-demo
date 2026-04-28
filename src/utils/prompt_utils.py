import json
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from jinja2 import Environment, FileSystemLoader

from src import constant as const
from src.enums.project_progress import ProjectProgress
from src.enums.group_member_role import GroupMemberRole

PROMPT_DIR = Path(__file__).parent.parent.parent / "template/prompts/variable/"
env = Environment(loader=FileSystemLoader(PROMPT_DIR))

COMMON_TOOL_CALL_CONFIG = json.load((PROMPT_DIR / "0_common/common_tool_call.json").open())
STAGE_TOOL_CALL_CONFIG = json.load((PROMPT_DIR / "0_common/stage_tool_call.json").open())

PRODUCT_MANAGER_PROMPT_CONFIG = json.load((PROMPT_DIR / "1_product_manager/config.json").open())
PRODUCT_MANAGER_PROMPT_TEMPLATE = env.get_template("1_product_manager/template.md.j2")

GENERATE_OPTIMIZATION_PLAN_PROMPT_CONFIG = json.load((PROMPT_DIR / "2_generate_optimization_plan/config.json").open())
GENERATE_OPTIMIZATION_PLAN_PROMPT_TEMPLATE = env.get_template("2_generate_optimization_plan/template.md.j2")

REVIEW_OPTIMIZATION_PLAN_PROMPT_CONFIG = json.load((PROMPT_DIR / "3_review_optimization_plan/config.json").open())
REVIEW_OPTIMIZATION_PLAN_PROMPT_TEMPLATE = env.get_template("3_review_optimization_plan/template.md.j2")

OPTIMIZATION_DOC_PROMPT_CONFIG = json.load((PROMPT_DIR / "4_optimize_doc/config.json").open())
OPTIMIZATION_DOC_PROMPT_TEMPLATE = env.get_template("4_optimize_doc/template.md.j2")

REVIEW_OPTIMIZATION_DOC_PROMPT_CONFIG = json.load((PROMPT_DIR / "5_review_optimization_doc/config.json").open())
REVIEW_OPTIMIZATION_DOC_PROMPT_TEMPLATE = env.get_template("5_review_optimization_doc/template.md.j2")

SUMMARIZE_OPTIMIZATION_DOC_ISSUE_PROMPT_CONFIG = json.load(
    (PROMPT_DIR / "6_summarize_optimization_doc_issue/config.json").open())
SUMMARIZE_OPTIMIZATION_DOC_ISSUE_PROMPT_TEMPLATE = env.get_template("6_summarize_optimization_doc_issue/template.md.j2")


@lru_cache
def get_product_manager_prompt(progress: ProjectProgress, history_summary: str = const.EMPTY_ZH) -> str:
    result = PRODUCT_MANAGER_PROMPT_TEMPLATE.render(
        **PRODUCT_MANAGER_PROMPT_CONFIG["common"],
        **PRODUCT_MANAGER_PROMPT_CONFIG["stage"][progress.value],
        common_tool_calls=COMMON_TOOL_CALL_CONFIG[progress.value],
        history_summary=history_summary,
        datetime=str(datetime.now()),
    )
    return result


@lru_cache
def get_generate_optimization_plan_prompt(progress: ProjectProgress) -> str:
    result = GENERATE_OPTIMIZATION_PLAN_PROMPT_TEMPLATE.render(
        **GENERATE_OPTIMIZATION_PLAN_PROMPT_CONFIG["common"],
        **GENERATE_OPTIMIZATION_PLAN_PROMPT_CONFIG["stage"][progress.value],
        common_tool_calls=COMMON_TOOL_CALL_CONFIG[progress.value],
        stage_tool_calls=STAGE_TOOL_CALL_CONFIG[progress.value],
        datetime=str(datetime.now()),
    )
    return result


@lru_cache
def get_review_optimization_plan_prompt(progress: ProjectProgress) -> str:
    result = REVIEW_OPTIMIZATION_PLAN_PROMPT_TEMPLATE.render(
        **REVIEW_OPTIMIZATION_PLAN_PROMPT_CONFIG["common"],
        **REVIEW_OPTIMIZATION_PLAN_PROMPT_CONFIG["stage"][progress.value],
        common_tool_calls=COMMON_TOOL_CALL_CONFIG[progress.value],
        stage_tool_calls=STAGE_TOOL_CALL_CONFIG[progress.value],
        datetime=str(datetime.now()),
    )
    return result


@lru_cache
def get_optimization_doc_prompt(progress: ProjectProgress) -> str:
    result = OPTIMIZATION_DOC_PROMPT_TEMPLATE.render(
        **OPTIMIZATION_DOC_PROMPT_CONFIG["common"],
        **OPTIMIZATION_DOC_PROMPT_CONFIG["stage"][progress.value],
        common_tool_calls=COMMON_TOOL_CALL_CONFIG[progress.value],
        stage_tool_calls=STAGE_TOOL_CALL_CONFIG[progress.value],
        datetime=str(datetime.now()),
    )
    return result


@lru_cache
def get_review_optimization_doc_prompt(progress: ProjectProgress, role: GroupMemberRole) -> str:
    result = REVIEW_OPTIMIZATION_DOC_PROMPT_TEMPLATE.render(
        **REVIEW_OPTIMIZATION_DOC_PROMPT_CONFIG["common"],
        **REVIEW_OPTIMIZATION_DOC_PROMPT_CONFIG["stage"][progress.value],
        **REVIEW_OPTIMIZATION_DOC_PROMPT_CONFIG["stage"][progress.value]["role"][role.value],
        common_tool_calls=COMMON_TOOL_CALL_CONFIG[progress.value],
        stage_tool_calls=STAGE_TOOL_CALL_CONFIG[progress.value],
        datetime=str(datetime.now()),
    )
    return result


@lru_cache
def get_summarize_optimization_doc_issue_prompt(progress: ProjectProgress) -> str:
    result = SUMMARIZE_OPTIMIZATION_DOC_ISSUE_PROMPT_TEMPLATE.render(
        **SUMMARIZE_OPTIMIZATION_DOC_ISSUE_PROMPT_CONFIG["common"],
        **SUMMARIZE_OPTIMIZATION_DOC_ISSUE_PROMPT_CONFIG["stage"][progress.value],
        common_tool_calls=COMMON_TOOL_CALL_CONFIG[progress.value],
        stage_tool_calls=STAGE_TOOL_CALL_CONFIG[progress.value],
        datetime=str(datetime.now()),
    )
    return result