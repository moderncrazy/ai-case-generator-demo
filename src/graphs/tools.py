from typing import Any
from loguru import logger
from langgraph.types import Command
from langchain.tools import tool, ToolRuntime, BaseTool
from langchain.messages import ToolMessage, AIMessage, HumanMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.models.project_file import ProjectFile
from src.enums.pm_next_step import PMNextStep
from src.enums.error_message import ErrorMessage
from src.enums.project_progress import ProjectProgress
from src.enums.requirement_module_status import RequirementModuleStatus
from src.graphs import utils
from src.graphs.state import State
from src.graphs.schemas import PMOutput, StateRequirementModule, StateModule, StateApi, StateTestCase, StateProjectFile
from src.repositories.project_file_repository import project_file_repository
from src.repositories.module_repository import module_repository, ModuleUpdate
from src.repositories.project_repository import project_repository, ProjectUpdate
from src.repositories.test_case_repository import test_case_repository, TestCaseBulkUpdate
from src.services.api_service import api_service
from src.services.project_file_service import project_file_service
from src.services.milvus_service import milvus_service, ProjectContextSearchResult, ProjectFileSearchResult
from src.exceptions.exceptions import BusinessException


@tool
async def get_project_file_by_id(id: str, runtime: ToolRuntime) -> ProjectFile:
    """根据文件ID查询项目文件信息

    Args:
        id: 项目文件的唯一标识符
        runtime: 包含项目状态的工具运行时对象

    Returns:
        包含文件详情的 ProjectFile 对象
    """
    project_id = runtime.state["project_id"]
    result = await project_file_repository.get_by_id(id)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


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
    result = await milvus_service.search_project_files(query, project_id)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 查询内容:{query} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_project_files_summary(runtime: ToolRuntime) -> str:
    """获取项目文件摘要

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        项目文件摘要
    """
    project_id = runtime.state["project_id"]
    result = await project_file_service.get_project_files_summary_to_str(project_id)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


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
    result = await milvus_service.search_project_context(project_id, query)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 查询内容:{query} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_requirement_outline(runtime: ToolRuntime[Any, State]) -> str:
    """获取需求大纲

    从运行时状态中获取当前项目的需求大纲

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        需求大纲文本
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("requirement_outline", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_requirement_modules(runtime: ToolRuntime[Any, State]) -> list[StateRequirementModule]:
    """获取需求模块列表

    从运行时状态中获取当前项目的需求模块列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        需求模块列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("requirement_modules", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_original_requirement(runtime: ToolRuntime[Any, State]) -> str:
    """获取原始需求文档

    从运行时状态中获取当前项目的原始需求文档

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        原始需求文档文本
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_requirement", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_requirement(runtime: ToolRuntime[Any, State]) -> str:
    """获取当前需求文档

    从运行时状态中获取当前项目的当前需求文档

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        当前需求文档文本
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_requirement", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_original_architecture(runtime: ToolRuntime[Any, State]) -> str:
    """获取原始架构设计

    从运行时状态中获取当前项目的原始架构设计

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        原始架构设计文本
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_architecture", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_architecture(runtime: ToolRuntime[Any, State]) -> str:
    """获取当前架构设计

    从运行时状态中获取当前项目的当前架构设计

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        当前架构设计文本
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_architecture", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_original_modules(runtime: ToolRuntime[Any, State]) -> list[StateModule]:
    """获取原始系统模块列表

    从运行时状态中获取当前项目的原始系统模块列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        原始系统模块列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_modules", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_current_modules(runtime: ToolRuntime[Any, State]) -> list[StateModule]:
    """获取当前系统模块列表

    从运行时状态中获取当前项目的当前系统模块列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        当前系统模块列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_modules", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_original_database(runtime: ToolRuntime[Any, State]) -> str:
    """获取原始数据库设计

    从运行时状态中获取当前项目的原始数据库设计

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        原始数据库设计文本
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_database", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_database(runtime: ToolRuntime[Any, State]) -> str:
    """获取当前数据库设计

    从运行时状态中获取当前项目的当前数据库设计

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        当前数据库设计文本
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_database", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_original_apis(runtime: ToolRuntime[Any, State]) -> list[StateApi]:
    """获取原始接口设计列表

    从运行时状态中获取当前项目的原始接口设计列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        原始接口设计列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_apis", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_current_apis(runtime: ToolRuntime[Any, State]) -> list[StateApi]:
    """获取当前接口设计列表

    从运行时状态中获取当前项目的当前接口设计列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        当前接口设计列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_apis", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_original_test_cases(runtime: ToolRuntime[Any, State]) -> list[StateTestCase]:
    """获取原始测试用例列表

    从运行时状态中获取当前项目的原始测试用例列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        原始测试用例列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_test_cases", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_current_test_cases(runtime: ToolRuntime[Any, State]) -> list[StateTestCase]:
    """获取当前测试用例列表

    从运行时状态中获取当前项目的当前测试用例列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        当前测试用例列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_test_cases", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_project_file_list(runtime: ToolRuntime[Any, State]) -> list[StateProjectFile]:
    """获取项目文件列表

    从运行时状态中获取当前项目的文件列表

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        项目文件列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("project_file_list", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_project_info(runtime: ToolRuntime) -> dict[str, Any]:
    """获取项目基本信息

    从运行时状态中获取当前项目的基本信息（ID、名称、进度、风险、不明确点）

    Args:
        runtime: 包含项目状态的工具运行时对象

    Returns:
        项目基本信息字典
    """
    project_id = runtime.state["project_id"]
    result = {
        "project_id": runtime.state["project_id"],
        "project_name": runtime.state["project_name"],
        "project_progress": runtime.state["project_progress"],
        "risks": runtime.state.get("risks", []),
        "unclear_points": runtime.state.get("unclear_points", []),
    }
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def confirm_requirement_module(name: str, runtime: ToolRuntime) -> str | Command:
    """确认模块完成

    征得用户确认确认模块设计完成，标记模块 status 为 COMPLETED
    **前提：** 模块 name 存在 且 content 不为空

    Args:
        name: 模块名称
        runtime: 包含项目状态的工具运行时对象

    Returns:
        返回更新 Command 或 error_message
    """
    error_message = ""
    project_id = runtime.state["project_id"]
    for module in runtime.state["requirement_modules"]:
        if module["name"] == name:
            if module["content"]:
                module["status"] = RequirementModuleStatus.COMPLETED
                logger.info(
                    f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 确认需求模块:{name} 成功")
                return Command(update={
                    "requirement_modules": runtime.state["requirement_modules"],
                    "messages": [ToolMessage(content=f"{name}模块确认成功", tool_call_id=runtime.tool_call_id)],
                })
            else:
                error_message = f"{name}模块内容为空，确认失败"

    error_message = error_message or f"{name}模块不存在，确认失败"
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 项目Id:{project_id} 确认需求模块:{name} 失败:{error_message}")
    return error_message


@tool(args_schema=PMOutput)
async def product_manager_output(next_step: PMNextStep, message: str, metadata: dict,
                                 runtime: ToolRuntime[Any, State]) -> Command:
    """输出产品经理决策结果

    用于在产品经理分析完成后，输出结构化的决策结果。

    Args:
        next_step: 下一步要做的事情，参考PMNextStep枚举类
        message: 给客户的回话，或者给下一步任务的指示
        metadata: 元数据
        runtime: 包含项目状态的工具运行时对象

    Returns:
        Command 更新项目状态
    """
    project_id = runtime.state["project_id"]
    tool_call_id = runtime.tool_call_id
    tool_name = gutils.get_func_name()
    tool_call_message = utils.mock_ai_message_in_structured_output(tool_call_id, tool_name, locals())
    output = PMOutput(next_step=next_step, message=message, metadata=metadata)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 下一步:{next_step.value} 输入:{output.model_dump_json()}")
    try:
        # 更新项目对象
        project_update: ProjectUpdate | None = None
        # 更新状态对象
        state_update: State = {
            "pm_next_step": next_step,
            "new_file_list": [],
            "messages": [
                tool_call_message,
                ToolMessage(content=output, tool_call_id=tool_call_id),
            ],
            "private_messages": [HumanMessage(content=message)]
        }
        # 关键节点处需要额外校验和更新
        match next_step:
            # 结束对话
            case PMNextStep.END:
                state_update["messages"].append(AIMessage(content=message, name="PRODUCT_MANAGER"))
            # 进入需求大纲设计阶段
            case PMNextStep.REQUIREMENT_OUTLINE_DESIGN:
                # 更新数据库状态
                project_update = ProjectUpdate(progress=ProjectProgress.REQUIREMENT_OUTLINE_DESIGN)
                # 更新 state
                state_update["project_progress"] = ProjectProgress.REQUIREMENT_OUTLINE_DESIGN
            # 进入需求模块设计阶段
            case PMNextStep.REQUIREMENT_MODULE_DESIGN:
                # 检查需求大纲和模块是否存在
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    fields=["requirement_outline", "requirement_modules"]
                )
                # 校验 module 存在
                if (not metadata.get("module") or not utils.validate_requirement_module_exist(
                        metadata["module"], runtime.state["requirement_modules"])):
                    raise BusinessException(ErrorMessage.FLOW_VALIDATE_FAILED.code, "metadata.module不存在")
                # 更新数据库状态
                project_update = ProjectUpdate(
                    progress=ProjectProgress.REQUIREMENT_MODULE_DESIGN,
                    requirement_outline_design=runtime.state["requirement_outline"]
                )
                # 更新 state
                state_update["metadata"] = metadata
                state_update["project_progress"] = ProjectProgress.REQUIREMENT_MODULE_DESIGN
            # 进入需求文档设计阶段
            case PMNextStep.REQUIREMENT_OVERALL_DESIGN:
                # 检查需求模块是否完整且是否存在风险和问题
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    none_fields=["risks", "unclear_points"]
                )
                if msg := utils.validate_requirement_modules_completed_to_str(
                        runtime.state.get("requirement_modules")):
                    raise BusinessException(ErrorMessage.FLOW_VALIDATE_FAILED.code, msg)
                # 更新数据库状态
                project_update = ProjectUpdate(
                    progress=ProjectProgress.REQUIREMENT_OVERALL_DESIGN,
                    requirement_module_design=gutils.to_json(runtime.state["requirement_modules"])
                )
                # 更新state
                state_update["project_progress"] = ProjectProgress.REQUIREMENT_OVERALL_DESIGN
            # 进入系统架构设计阶段
            case PMNextStep.SYSTEM_ARCHITECTURE_DESIGN:
                # 检查需求文档是否完整且是否存在风险和问题
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    fields=["optimized_requirement"],
                    none_fields=["risks", "unclear_points"]
                )
                # 更新数据库状态
                project_update = ProjectUpdate(
                    progress=ProjectProgress.SYSTEM_ARCHITECTURE_DESIGN,
                    requirement_overall_design=runtime.state["optimized_requirement"]
                )
                # 更新state
                state_update["project_progress"] = ProjectProgress.SYSTEM_ARCHITECTURE_DESIGN
            # 进入系统模块设计阶段
            case PMNextStep.SYSTEM_MODULES_DESIGN:
                # 检查系统架构是否完整且是否存在风险和问题
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    fields=["optimized_architecture"],
                    none_fields=["risks", "unclear_points"]
                )
                # 更新数据库状态
                project_update = ProjectUpdate(
                    progress=ProjectProgress.SYSTEM_MODULES_DESIGN,
                    architecture_design=runtime.state["optimized_architecture"]
                )
                # 更新state
                state_update["project_progress"] = ProjectProgress.SYSTEM_MODULES_DESIGN
            # 进入系统数据库设计阶段
            case PMNextStep.SYSTEM_DATABASE_DESIGN:
                # 检查系统模块是否完整
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    fields=["optimized_modules"],
                )
                # 更新系统模块
                await module_repository.bulk_update(
                    project_id,
                    [ModuleUpdate(**item) for item in runtime.state["optimized_modules"]]
                )
                # 更新数据库状态
                project_update = ProjectUpdate(progress=ProjectProgress.SYSTEM_DATABASE_DESIGN)
                # 更新state
                state_update["project_progress"] = ProjectProgress.SYSTEM_DATABASE_DESIGN
            # 进入系统接口设计阶段
            case PMNextStep.SYSTEM_API_DESIGN:
                # 检查系统数据库是否完整
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    fields=["optimized_database"],
                )
                # 更新项目状态和数据库文档
                project_update = ProjectUpdate(
                    progress=ProjectProgress.SYSTEM_API_DESIGN,
                    database_design=runtime.state["optimized_database"]
                )
                # 更新state
                state_update["project_progress"] = ProjectProgress.SYSTEM_API_DESIGN
            # 进入测试用例设计阶段
            case PMNextStep.TEST_CASE_DESIGN:
                # 检查API设计是否完整
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    fields=["optimized_apis"]
                )
                # 批量更新接口
                await api_service.bulk_update_by_state_apis(project_id, runtime.state["optimized_apis"])
                # 更新数据库状态
                project_update = ProjectUpdate(progress=ProjectProgress.TEST_CASE_DESIGN)
                # 更新state
                state_update["project_progress"] = ProjectProgress.TEST_CASE_DESIGN
            # 进入监控需求变更阶段
            case PMNextStep.MONITORING_CHANGE:
                # 检查测试用例设计是否完整
                utils.validate_state_fields_to_exception(
                    runtime.state,
                    fields=["optimized_test_cases"]
                )
                # 批量更新模块
                await test_case_repository.bulk_update(
                    project_id,
                    [TestCaseBulkUpdate(**item) for item in runtime.state["optimized_test_cases"]]
                )
                # 更新数据库状态
                project_update = ProjectUpdate(progress=ProjectProgress.COMPLETED)
                # 更新state
                state_update["project_progress"] = ProjectProgress.COMPLETED
        # 如果 project_update 存在则更新项目
        if project_update:
            await project_repository.update(project_id, project_update=project_update)
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 下一步:{next_step.value} project更新:{project_update.model_dump_json()}")
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 下一步:{next_step.value} 完成")
        return Command(update=state_update)
    except BusinessException as e:
        error_message = f"{e.message}，执行失败回到上一阶段修复"
        logger.warning(
            f"trans_id:{trans_id_ctx.get()} 工具:{gutils.get_func_name()} 下一步:{next_step.value}  打回:{error_message}")
        # 打回修复
        return Command(
            update={"messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
            goto="product_manager_node"
        )


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}

# 通用 tool 排除 pm 专用方法
common_tool_list = [t for t in tool_list if
                    t.name not in [confirm_requirement_module.name, product_manager_output.name]]
