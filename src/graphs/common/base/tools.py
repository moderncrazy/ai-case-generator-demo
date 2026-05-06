from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.utils import format_utils
from src.graphs.common.tools import common_tools as ctools
from src.graphs.common.schemas.state_schemas import StateIssue


@tool
def get_optimization_plan_content(runtime: ToolRuntime) -> str:
    """获取优化方案内容

    从运行时状态中读取优化方案，供优化的agent根据此方案优化文档。
    方案包含方案逻辑链路、具体步骤

    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 str 类型的字符串，格式为：
        AI生成的具体优化方案如下：

        方案逻辑链路：xxx
        方案具体步骤：xxx

        如果无优化方案，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimization_plan_content")
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
def get_review_issues(runtime: ToolRuntime) -> str:
    """获取评审意见列表

    AI大模型使用此工具可获取各角色提出的评审意见。

    **功能说明：**
    从运行时状态中读取并返回评审意见，用于了解之前评审发现的问题。

    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 str 类型的字符串，格式为：
        问题Id：xxx
        问题：xxx
        建议方案：xxx

        如果无评审意见，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = format_utils.format_issues_to_str(runtime.state.get("review_issues"))
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
def remove_review_issues_by_ids(issue_ids: list[str], runtime: ToolRuntime) -> list[StateIssue]:
    """删除评审意见

    AI大模型使用此工具可将已根据评审意见优化完成的问题从意见列表中移除。

    **功能说明：**
    从运行时状态中删除指定ID的评审意见，用于记录哪些问题已经被解决。
    此工具通常在根据评审意见完成优化后调用。

    Args:
        issue_ids: list[str] - 需要删除的评审意见ID列表
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 list[StateIssue] 类型的列表，即删除后剩余的评审意见列表
    """
    project_id = runtime.state["project_id"]
    review_issues = runtime.state.get("review_issues", [])
    if review_issues:
        index_ids = {item["id"]: item for index, item in enumerate(review_issues)}
        for issue_id in issue_ids:
            if issue_id in index_ids:
                review_issues.remove(index_ids[issue_id])
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(review_issues)}")
    return review_issues


@tool
async def get_risks(runtime: ToolRuntime) -> str:
    """获取风险点列表

    AI大模型使用此工具可获取当前项目已识别的风险点列表。

    **功能说明：**
    从运行时状态中读取并返回已识别的风险点，用于了解项目潜在的风险。

    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 str 类型的字符串，格式为：
        问题Id：xxx
        问题：xxx
        建议方案：xxx

        如果无风险点，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = format_utils.format_issues_to_str(runtime.state.get("private_risks"))
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_unclear_points(runtime: ToolRuntime) -> str:
    """获取不明确问题列表

    AI大模型使用此工具可获取当前项目待澄清的不明确问题列表。

    **功能说明：**
    从运行时状态中读取并返回待澄清的不明确问题，用于了解需要客户明确的事项。

    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入

    Returns:
        返回 str 类型的字符串，格式为：
        问题Id：xxx
        问题：xxx
        建议方案：xxx

        如果无不明确问题，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = format_utils.format_issues_to_str(runtime.state.get("private_unclear_points"))
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

with_common_tools = tool_list + ctools.tool_list
