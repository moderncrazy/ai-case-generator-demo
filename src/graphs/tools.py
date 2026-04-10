import inspect
from loguru import logger
from langgraph.types import Command
from langchain.tools import tool, ToolRuntime, BaseTool
from langchain.messages import ToolMessage, AIMessage, HumanMessage, ToolCall

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.pm_next_step import PMNextStep
from src.enums.project_progress import ProjectProgress
from src.graphs import utils
from src.graphs.schemas import PMOutput, PresentProjectInfo
from src.models.api import Api
from src.models.module import Module
from src.models.test_case import TestCase
from src.models.project_file import ProjectFile
from src.repositories.api_repository import api_repository, ApiCreate
from src.repositories.project_file_repository import project_file_repository
from src.repositories.module_repository import module_repository, ModuleCreate
from src.repositories.project_repository import project_repository, ProjectUpdate
from src.repositories.test_case_repository import test_case_repository, TestCaseCreate
from src.services.api_service import api_service
from src.services.module_service import module_service
from src.services.test_case_service import test_case_service
from src.services.milvus_service import milvus_service, ProjectContextSearchResult, ProjectFileSearchResult


@tool
async def get_project_file_by_id(id: str) -> ProjectFile:
    """根据文件ID查询项目文件信息

    Args:
        id: 项目文件的唯一标识符

    Returns:
        包含文件详情的 ProjectFile 对象
    """
    return await project_file_repository.get_by_id(id)


@tool
async def search_project_files(query: str, runtime: ToolRuntime) -> list[ProjectFileSearchResult]:
    """搜索项目文件

    使用混合搜索在当前项目中查找与查询相关的文件

    Args:
        query: 搜索查询文本
        runtime: 包含项目状态的工具运行时对象

    Returns:
        匹配查询的 ProjectFileSearchResult 对象列表
    """
    project_id = runtime.state["project_id"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目id:{project_id} 查询内容:{query}")
    return await milvus_service.search_project_files(query, project_id)


@tool
async def search_project_history_conversation(query: str, runtime: ToolRuntime) -> list[ProjectContextSearchResult]:
    """搜索项目历史对话上下文

    使用混合搜索在当前项目上下文中查找与查询相关对话历史

    Args:
        query: 搜索查询文本
        runtime: 包含项目状态的工具运行时对象

    Returns:
        匹配查询的 ProjectContextSearchResult 对象列表
    """
    project_id = runtime.state["project_id"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目id:{project_id} 查询内容:{query}")
    return await milvus_service.search_project_context(project_id, query)


@tool
async def get_project_info(runtime: ToolRuntime) -> PresentProjectInfo:
    """获取项目完整信息

    从运行时状态中获取当前项目的完整信息，返回包含所有项目数据的 PresentProjectInfo 对象

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        PresentProjectInfo 项目完整信息对象，包含需求、架构、模块、API、测试用例等所有数据
    """
    project_info = PresentProjectInfo(**runtime.state)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目信息:{project_info.model_dump_json()}")
    return project_info


@tool(args_schema=PMOutput)
async def product_manager_output(next_step: PMNextStep, message: str, runtime: ToolRuntime) -> Command:
    """输出产品经理决策结果

    用于在产品经理分析完成后，输出结构化的决策结果。

    Args:
        next_step: 下一步操作类型，参考 PMNextStep 枚举
        message: 给客户的回话，或给下一步任务的指示
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    project_id = runtime.state["project_id"]
    output = PMOutput(next_step=next_step, message=message)
    tool_call_id = runtime.tool_call_id
    tool_name = inspect.currentframe().f_code.co_name
    tool_call_message = utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 下一步:{next_step.value} 消息:{gutils.to_one_line(message)}")
    # 关键节点处需要额外校验和更新
    match next_step:
        # 结束对话
        case PMNextStep.END:
            logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 结束对话")
            return Command(update={
                "pm_next_step": next_step,
                "new_file_list": [],
                "messages": [
                    tool_call_message,
                    ToolMessage(content=output, tool_call_id=tool_call_id),
                    AIMessage(content=message, name="PRODUCT_MANAGER")
                ]
            })
        # 进入需求设计阶段
        case PMNextStep.REQUIREMENT_DESIGN:
            # 更新数据库状态
            await project_repository.update(
                project_id,
                project_update=ProjectUpdate(progress=ProjectProgress.REQUIREMENT)
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 进行需求设计")
            # 更新state
            return Command(update={
                "pm_next_step": next_step,
                "pm_next_step_instruction": message,
                "project_progress": ProjectProgress.REQUIREMENT,
                "new_file_list": [],
                "messages": [
                    tool_call_message,
                    ToolMessage(content=output, tool_call_id=tool_call_id),
                ],
                "private_messages": [HumanMessage(content=message)]
            })
        # 进入系统设计阶段
        case PMNextStep.SYSTEM_DESIGN:
            # 检查需求是否存在风险和问题
            error_message = None
            if runtime.state.get("risks"):
                error_message = "项目需求存在风险，回到需求阶段修复"
            elif runtime.state.get("unclear_points"):
                error_message = "项目需求存在不确定点，回到需求阶段修复"
            elif not runtime.state.get("optimized_requirement"):
                error_message = "PRD为空，回到需求阶段修复"
            if error_message:
                logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 系统设计打回:{error_message}")
                # 打回修复
                return Command(
                    update={
                        "messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
                    goto="product_manager_node"
                )
            # 更新数据库状态
            await project_repository.update(
                project_id,
                project_update=ProjectUpdate(
                    progress=ProjectProgress.SYSTEM_DESIGN,
                    requirement_design=runtime.state["optimized_requirement"]
                )
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 进行系统设计")
            # 更新state
            return Command(update={
                "pm_next_step": next_step,
                "pm_next_step_instruction": message,
                "project_progress": ProjectProgress.SYSTEM_DESIGN,
                "new_file_list": [],
                "messages": [
                    tool_call_message,
                    ToolMessage(content=output, tool_call_id=tool_call_id)
                ]
            })
        # 进入API设计阶段
        case PMNextStep.API_DESIGN:
            # 检查系统设计是否存在风险和问题
            error_message = None
            if runtime.state.get("risks"):
                error_message = "项目系统设计存在风险，回到系统设计阶段修复"
            elif runtime.state.get("unclear_points"):
                error_message = "项目系统设计存在不确定点，回到系统设计阶段修复"
            elif not runtime.state.get("optimized_architecture"):
                error_message = "架构设计为空，回到系统设计阶段修复"
            elif not runtime.state.get("optimized_database"):
                error_message = "数据库设计为空，回到系统设计阶段修复"
            elif not runtime.state.get("optimized_modules"):
                error_message = "系统模块设计为空，回到系统设计阶段修复"
            elif error := module_service.validate_modules_to_str(
                    [Module(**item) for item in runtime.state["optimized_modules"]]):
                error_message = f"{error}回到系统设计阶段修复"
            if error_message:
                logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} API设计打回:{error_message}")
                # 打回修复
                return Command(
                    update={
                        "messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
                    goto="product_manager_node"
                )
            # 更新数据库状态
            await project_repository.update(
                project_id,
                project_update=ProjectUpdate(
                    progress=ProjectProgress.API,
                    architecture_design=runtime.state["optimized_architecture"],
                    database_design=runtime.state["optimized_database"],
                )
            )
            # 批量更新模块
            await module_repository.bulk_update(
                project_id,
                [ModuleCreate(**item) for item in runtime.state["optimized_modules"]]
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 进行API设计")
            # 更新state
            return Command(update={
                "pm_next_step": next_step,
                "pm_next_step_instruction": message,
                "project_progress": ProjectProgress.API,
                "new_file_list": [],
                "messages": [
                    tool_call_message,
                    ToolMessage(content=output, tool_call_id=tool_call_id)
                ]
            })
        # 进入测试用例设计阶段
        case PMNextStep.TEST_CASE_DESIGN:
            # 检查API设计是否存在风险和问题
            error_message = None
            if runtime.state.get("risks"):
                error_message = "API设计存在风险，回到API设计阶段修复"
            elif runtime.state.get("unclear_points"):
                error_message = "API设计存在不确定点，回到API设计阶段修复"
            elif not runtime.state.get("optimized_apis"):
                error_message = "API设计为空，回到API设计阶段修复"
            elif errors := api_service.validate_module_ids_to_str(
                    [Api(**item) for item in runtime.state["optimized_apis"]]):
                error_message = f"{errors}回到API设计阶段修复"
            if error_message:
                logger.info(
                    f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 测试用例设计打回:{error_message}")
                # 打回修复
                return Command(
                    update={
                        "messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
                    goto="product_manager_node"
                )
            # 更新数据库状态
            await project_repository.update(
                project_id,
                project_update=ProjectUpdate(progress=ProjectProgress.TEST_CASE)
            )
            # 批量更新模块
            await api_repository.bulk_update(
                project_id,
                [ApiCreate(**item) for item in runtime.state["optimized_apis"]]
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 进行测试用例设计")
            # 更新state
            return Command(update={
                "pm_next_step": next_step,
                "pm_next_step_instruction": message,
                "project_progress": ProjectProgress.TEST_CASE,
                "new_file_list": [],
                "messages": [
                    tool_call_message,
                    ToolMessage(content=output, tool_call_id=tool_call_id)
                ]
            })
        # 进入压测设计阶段
        case PMNextStep.STRESS_TEST_DESIGN:
            # 检查测试用例设计是否存在风险和问题
            error_message = None
            if runtime.state.get("risks"):
                error_message = "测试用例设计存在风险，回到测试用例设计阶段修复"
            elif runtime.state.get("unclear_points"):
                error_message = "测试用例设计存在不确定点，回到测试用例设计阶段修复"
            elif not runtime.state.get("optimized_test_cases"):
                error_message = "测试用例设计为空，回到测试用例设计阶段修复"
            elif errors := test_case_service.validate_module_ids_to_str(
                    [TestCase(**item) for item in runtime.state["optimized_test_cases"]]):
                error_message = f"{errors}回到API设计阶段修复"
            if error_message:
                logger.info(
                    f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 压测设计打回:{error_message}")
                # 打回修复
                return Command(
                    update={
                        "messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
                    goto="product_manager_node"
                )
            # 更新数据库状态
            await project_repository.update(
                project_id,
                project_update=ProjectUpdate(progress=ProjectProgress.STRESS_TEST)
            )
            # 批量更新模块
            await test_case_repository.bulk_update(
                project_id,
                [TestCaseCreate(**item) for item in runtime.state["optimized_test_cases"]]
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 进行压测设计")
            # 更新state
            return Command(update={
                "pm_next_step": next_step,
                "pm_next_step_instruction": message,
                "project_progress": ProjectProgress.STRESS_TEST,
                "new_file_list": [],
                "messages": [
                    tool_call_message,
                    ToolMessage(content=output, tool_call_id=tool_call_id)
                ]
            })


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
