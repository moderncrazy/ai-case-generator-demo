from loguru import logger
from langchain.tools import tool, BaseTool, ToolRuntime

from src import constant as const
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.common.utils import format_utils


@tool
async def get_test_cases(runtime: ToolRuntime) -> str:
    """获取优化后测试用例列表
    
    AI大模型使用此工具可获取经过AI优化后的测试用例列表。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的测试用例列表。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即测试用例列表的格式化内容：
        测试用例Id：xxx
        模块名称：xxx
        所属模块Id：xxx
        前置条件：xxx
        测试步骤：xxx
        预期结果：xxx
        测试数据：xxx
        用例等级：xxx
        用例类型：xxx
        ----------xxx end----------
        
        如果无测试用例，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("test_cases") or runtime.state.get("optimized_test_cases")
    result_str = format_utils.format_state_test_cases_to_str(result)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result_str)}")
    return result_str


@tool
async def get_current_test_case_task(runtime: ToolRuntime) -> str:
    """获取当前测试用例任务
    
    AI大模型使用此工具可获取当前需要执行的测试用例任务信息。
    
    **功能说明：**
    返回当前需要执行的具体测试用例任务，
    包含任务所属模块、任务范围和测试用例标题列表。
    测试用例数量由 测试用例标题列表长度决定。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即任务信息的格式化内容：
        模块Id：xxx
        模块名称：xxx
        任务标题：xxx
        任务范围：xxx
        测试用例标题列表：
        - xxx
        - xxx
        用例数量：xxx 个
        
        如果无任务，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    task = runtime.state.get("task")
    if task:
        test_case_titles = "\n".join([f"- {title}" for title in task["test_case_titles"]])
        result_str = (
            f"模块Id：{task["module_id"]}\n"
            f"模块名称：{task["module_name"]}\n"
            f"任务标题：{task["title"]}\n"
            f"任务范围：{task["scope"]}\n"
            f"测试用例标题列表：\n{test_case_titles}\n"
            f"用例数量：{len(task["test_case_titles"])} 个"
        )
    else:
        result_str = const.EMPTY_ZH
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result_str)}")
    return result_str


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
