import uuid
from typing import Any
from loguru import logger
from langgraph.types import Command
from langchain.tools import tool, ToolRuntime, BaseTool
from langchain.messages import ToolMessage, AIMessage, HumanMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.pm_next_step import PMNextStep
from src.enums.error_message import ErrorMessage
from src.enums.project_progress import ProjectProgress
from src.enums.group_member_role import GroupMemberRole
from src.enums.instruction_template import InstructionTemplate
from src.enums.requirement_module_status import RequirementModuleStatus
from src.graphs import utils
from src.graphs.schemas import PMOutput
from src.graphs.state import State
from src.graphs.common.utils import structured_output_utils
from src.services.api_service import api_service
from src.exceptions.exceptions import BusinessException
from src.repositories.module_repository import module_repository, ModuleUpdate
from src.repositories.project_repository import project_repository, ProjectUpdate
from src.repositories.test_case_repository import test_case_repository, TestCaseBulkUpdate


@tool
async def get_instruction_template(template: InstructionTemplate, runtime: ToolRuntime) -> str:
    """获取指令模板
    
    AI大模型使用此工具可获取指定类型的指令模板内容。
    
    **功能说明：**
    通过枚举加载对应的指令模板，返回模板内容供PM下发指令给团队成员
    
    Args:
        template: 模板枚举值，参考 InstructionTemplate
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的模板内容
    
    Exception:
        枚举值无效 → 返回错误提示信息
    """
    result = template.text
    project_id = runtime.state["project_id"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 模板:{template.name} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def confirm_requirement_module(name: str, runtime: ToolRuntime) -> str | Command:
    """确认需求模块完成
    
    AI大模型使用此工具可标记指定的需求模块为已完成状态。
    
    **功能说明：**
    当用户确认某个需求模块的内容已经完善后，调用此工具将模块状态更新为 COMPLETED。
    这将触发状态更新并通知用户确认成功。
    
    Args:
        name: 需要确认的模块名称
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        成功时：返回 Command 对象，包含更新后的 requirement_modules 和确认成功消息
        失败时：返回 str 类型的错误消息
    
    Exception:
        模块名称不存在 → 返回 "{name}模块不存在，确认失败"，核实模块名称后再调用
        模块内容为空 → 返回 "{name}模块内容为空，确认失败"，执行 requirement_module_design 完善需求模块
    """
    error_message = ""
    project_id = runtime.state["project_id"]
    for module in runtime.state["requirement_modules"]:
        if module["name"] == name:
            if module["content"]:
                module["status"] = RequirementModuleStatus.COMPLETED
                logger.info(
                    f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 确认需求模块:{name} 成功")
                return Command(update={
                    "requirement_modules": runtime.state["requirement_modules"],
                    "messages": [ToolMessage(content=f"{name}模块确认成功", tool_call_id=runtime.tool_call_id)],
                })
            else:
                error_message = f"{name}模块内容为空，确认失败"

    error_message = error_message or f"{name}模块不存在，确认失败"
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 确认需求模块:{name} 失败:{error_message}")
    return error_message


@tool(args_schema=PMOutput)
async def product_manager_output(next_step: PMNextStep, message: str, metadata: dict,
                                 runtime: ToolRuntime[Any, State]) -> Command:
    """输出产品经理决策结果
    
    AI大模型使用此工具可完成当前阶段分析并输出结构化的下一步决策。
    
    **功能说明：**
    这是产品经理Agent的核心输出工具，用于：
    1. 根据当前分析结果确定下一步操作（如继续设计、进入下一阶段、结束对话等）
    2. 生成给用户或后续Agent的提示消息
    3. 在关键节点更新数据库和运行时状态
    
    Args:
        next_step: PMNextStep - 下一步操作决策，包含以下枚举值：
            - end - 结束对话
            - requirement_outline_design - 进入需求大纲设计
            - requirement_module_design - 进入需求模块设计
            - requirement_overall_design - 进入整体需求设计
            - system_architecture_design - 进入架构设计
            - system_modules_design - 进入系统模块设计
            - system_database_design - 进入数据库设计
            - system_api_design - 进入API设计
            - test_case_design - 进入测试用例设计
            - monitoring_change - 监控变更
        message: str - 给用户的回话，或给下一步任务的指示
        metadata: dict - 额外元数据，如被选中进入下一步的模块名称等
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        成功时：返回 Command 对象，包含更新的状态（pm_next_step、messages、private_messages、project_progress等）
        失败时：返回 Command 对象，goto 回到 项目经理处 重新处理
    
    Exception:
        状态校验失败（如缺少必要字段） → 返回错误消息，打回修复
        流程校验失败（如模块不存在、风险未解决） → 返回具体错误原因，打回修复
    """
    project_id = runtime.state["project_id"]
    output = PMOutput(next_step=next_step, message=message, metadata=metadata)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 下一步:{next_step.value} 输入:{output.model_dump_json()}")
    try:
        # 更新项目对象
        project_update: ProjectUpdate | None = None
        # 更新状态对象
        state_update: State = {
            "pm_next_step": next_step,
            "messages": [],
            "private_messages": [AIMessage(content=message, name=GroupMemberRole.PM.value)],
        }
        # 关键节点处需要额外校验和更新
        match next_step:
            # 结束对话
            case PMNextStep.END:
                state_update["messages"].append(AIMessage(content=message, name=GroupMemberRole.PM.value))
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
                f"trans_id:{trans_id_ctx.get()} 下一步:{next_step.value} project更新:{project_update.model_dump_json()}")
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 下一步:{next_step.value} 完成")
        return Command(update=state_update)
    except BusinessException as e:
        error_message = f"{e.message}，执行失败回到上一阶段修复"
        logger.warning(
            f"trans_id:{trans_id_ctx.get()} 下一步:{next_step.value}  打回:{error_message}")
        # 打回修复
        tool_call_id = runtime.tool_call_id
        tool_name = gutils.get_func_name()
        tool_call_message = structured_output_utils.mock_ai_message_in_structured_output(
            tool_call_id, tool_name, locals())
        return Command(
            update={"messages": [tool_call_message, ToolMessage(content=error_message, tool_call_id=tool_call_id)]},
            goto="product_manager_node"
        )


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
