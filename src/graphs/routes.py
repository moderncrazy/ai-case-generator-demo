from loguru import logger
from typing import Literal
from langgraph.graph import END
from langchain_core.messages import AIMessage

from src.graphs.state import State
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.pm_next_step import PMNextStep


def load_project_router(state: State) -> Literal["load_project_node", "understand_image_node", "product_manager_node"]:
    """项目加载路由
    
    判断项目是否需要加载或用户是否有新上传文件：
    - 有新文件：进入文件理解节点
    - 无项目信息：进入项目加载节点
    - 其他情况：直接进入产品经理节点
    
    Args:
        state: LangGraph 状态
        
    Returns:
        目标节点名称
    """
    project_id = state["project_id"]
    destination_node = "product_manager_node"
    if not state.get("project_name"):
        destination_node = "load_project_node"
    if state.get("new_file_list"):
        destination_node = "understand_image_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
    return destination_node


def understand_image_router(state: State) -> Literal["understand_image_node", "product_manager_node"]:
    """图片理解路由
    
    判断是否还有未处理的新上传文件：
    - 有新文件：继续处理文件
    - 无新文件：进入产品经理节点
    
    Args:
        state: LangGraph 状态
        
    Returns:
        目标节点名称
    """
    project_id = state["project_id"]
    destination_node = "product_manager_node"
    if state.get("new_file_list"):
        destination_node = "understand_image_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
    return destination_node


def product_manager_tool_router(state: State) -> Literal[
    "product_manager_node", "product_manager_tool_node", "requirement_outline_node", "requirement_module_node",
    "requirement_overall_node", "system_architecture_node", "system_module_node", "system_database_node",
    "system_api_node", "test_case_node", "end_node"
]:
    """产品经理决策路由
    
    根据 PM 决策决定下一步操作：
    - 调用工具：继续查询/输出
    - 阶段决策：进入对应子图执行
    - 结束：返回用户
    
    Args:
        state: LangGraph 状态
        
    Returns:
        目标节点名称或 END
    """
    project_id = state["project_id"]
    # 如果不是最终决策则放行
    destination_node = "end_node"
    if isinstance(state["messages"][-1], AIMessage) and state["messages"][-1].tool_calls:
        destination_node = "product_manager_tool_node"
    elif state.get("node_rollback"):
        destination_node = "product_manager_node"
    else:
        match state["pm_next_step"]:
            case PMNextStep.REQUIREMENT_OUTLINE_DESIGN:
                destination_node = "requirement_outline_node"
            case PMNextStep.REQUIREMENT_MODULE_DESIGN:
                destination_node = "requirement_module_node"
            case PMNextStep.REQUIREMENT_OVERALL_DESIGN:
                destination_node = "requirement_overall_node"
            case PMNextStep.SYSTEM_ARCHITECTURE_DESIGN:
                destination_node = "system_architecture_node"
            case PMNextStep.SYSTEM_MODULES_DESIGN:
                destination_node = "system_module_node"
            case PMNextStep.SYSTEM_DATABASE_DESIGN:
                destination_node = "system_database_node"
            case PMNextStep.SYSTEM_API_DESIGN:
                destination_node = "system_api_node"
            case PMNextStep.TEST_CASE_DESIGN:
                destination_node = "test_case_node"
            case _:
                destination_node = "end_node"
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 路由至:{destination_node}")
    return destination_node
