from loguru import logger
from langgraph.runtime import Runtime
from langchain.messages import SystemMessage
from langgraph.config import get_stream_writer
from langchain_core.runnables import RunnableConfig

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.llms import default_model
from src.graphs import utils as main_utils
from src.graphs.schemas import CustomMessage
from src.graphs.tools import common_tool_list
from src.graphs.requirement.outline.state import State
from src.graphs.requirement.outline.tools import optimize_requirement_outline_output
from src.enums.system_prompt import SystemPrompt
from src.services.project_file_service import project_file_service


async def optimize_requirement_outline_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """优化需求大纲节点
    
    调用 LLM 根据上下文生成需求大纲和模块划分，
    支持通过工具查询项目历史文档等信息。
    
    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态（包含生成的需求大纲和模块列表）
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    # 发送自定义消息
    writer(CustomMessage(message="产品优化需求大纲中..."))
    project_id = state["project_id"]
    messages = [
                   SystemMessage(content=SystemPrompt.OPTIMIZED_REQUIREMENT_OUTLINE.template.format(
                       requirement_outline=state.get("optimized_requirement") or "（空）",
                   ))
               ] + state["private_messages"]
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*common_tool_list, optimize_requirement_outline_output])
    result = await main_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                         optimize_requirement_outline_output,
                                                         messages_key="private_messages")
    logger.info(f"trans_id:{trans_id_ctx.get()} 子图节点:{gutils.get_func_name()} 完成")
    return result
