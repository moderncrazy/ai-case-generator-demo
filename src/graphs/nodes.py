import orjson
from loguru import logger
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langchain_core.runnables import RunnableConfig
from langchain.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage

from src.graphs import utils
from src.config import settings
from src.graphs.state import State
from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.graphs.llms import default_model
from src.graphs.tools import tool_list, product_manager_output
from src.graphs.schemas import CustomMessage, FileSummaryOutput, StateProjectFile
from src.utils import file_utils, mcp_utils
from src.services.api_service import api_service
from src.services.milvus_service import milvus_service
from src.enums.system_prompt import SystemPrompt
from src.enums.project_progress import ProjectProgress
from src.enums.requirement_module_status import RequirementModuleStatus
from src.repositories.module_repository import module_repository
from src.repositories.project_repository import project_repository
from src.repositories.test_case_repository import test_case_repository
from src.repositories.project_file_repository import project_file_repository, ProjectFileCreate


async def fix_state_messages_node(state: State) -> State:
    """修复状态消息节点

    若state的messages中出现AI tool call没有tool回应时删除tool call message

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 进入")
    remove_messages = []
    for index, message in enumerate(state["messages"]):
        if isinstance(message, AIMessage) and message.tool_calls:
            if not isinstance(state["messages"][index + 1], ToolMessage):
                remove_messages.append(RemoveMessage(id=message.id))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 删除消息:{len(remove_messages)} 完成")
    return {"messages": remove_messages}


async def load_project_node(state: State) -> State:
    """加载项目节点

    若state中缺少项目信息则进行补全

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    # 发送自定义消息
    writer(CustomMessage(message="项目加载中..."))
    project_id = state["project_id"]
    project = await project_repository.get_by_id(project_id)
    requirement_module = orjson.loads(project.requirement_module_design or "[]")
    modules = await module_repository.list_by_project(project_id)
    modules = [item.to_dict() for item in modules]
    apis = await api_service.list_by_project_to_state_api(project_id)
    test_cases = await test_case_repository.list_by_project(project_id)
    test_cases = [item.to_dict() for item in test_cases]
    project_files = await project_file_repository.list_by_project(project_id)
    project_files = gutils.copy_data_by_model(StateProjectFile, [item.to_dict() for item in project_files])
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 完成")
    return {
        "project_name": project.name,
        "project_progress": ProjectProgress(project.progress),
        "project_file_list": project_files,
        "requirement_outline": project.requirement_outline_design,
        "requirement_modules": requirement_module,
        "original_requirement": project.requirement_overall_design,
        "optimized_requirement": project.requirement_overall_design,
        "original_architecture": project.architecture_design,
        "optimized_architecture": project.architecture_design,
        "original_database": project.database_design,
        "optimized_database": project.database_design,
        "original_modules": modules,
        "optimized_modules": modules,
        "original_apis": apis,
        "optimized_apis": apis,
        "original_test_cases": test_cases,
        "optimized_test_cases": test_cases,
    }


async def understand_image_node(state: State) -> State:
    """理解图片文档节点

    使用 MiniMax MCP 的 understand_image 工具解析用户新上传的文件。
    支持 PDF、图片等格式，自动转为图片后调用 OCR/理解接口。

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 进入")
    writer = get_stream_writer()
    project_id = state["project_id"]
    minimax_mcp_tools = await mcp_utils.get_minimax_mcp_tools_by_name()
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 新文件:{gutils.to_json(state["new_file_list"])}")
    for file in state["new_file_list"]:
        # 发送自定义消息
        writer(CustomMessage(message=f"理解《{file["name"]}》中..."))
        # 调用 MCP 方法理解文件
        content_output = await minimax_mcp_tools["understand_image"].ainvoke({
            "prompt": SystemPrompt.DOCUMENT_EXTRACTOR.text,
            "image_source": file_utils.file_to_image_data_url(file["path"]),
        })
        file["content"] = content_output[0]["text"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 理解文件:{file["name"]}")
        # 生成文件摘要
        writer(CustomMessage(message=f"整理《{file["name"]}》中..."))
        structured_output_llm = default_model.with_structured_output(FileSummaryOutput)
        # 设置重试次数
        structured_output_llm.with_retry(stop_after_attempt=settings.model_output_retry)
        file_summary_output: FileSummaryOutput = await structured_output_llm.ainvoke([
            SystemMessage(content=SystemPrompt.FILE_SUMMARY.text),
            HumanMessage(content=f"文件名称：{file["name"]}\n文件内容：\n{file["content"]}"),
        ])
        file["summary"] = file_summary_output.summary
        logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 总结文件:{file["name"]}")
        # 新建文件
        file["id"] = await project_file_repository.create(ProjectFileCreate(
            project_id=project_id,
            conversation_message_id=file["conversation_message_id"],
            name=file["name"],
            path=file["path"],
            type=file["type"],
            size=file["size"],
            content=file["content"],
            summary=file["summary"]
        ))
        # 写入向量数据库
        await milvus_service.add_project_file(
            project_id,
            file["name"],
            file["path"],
            file["type"],
            file["content"],
            file["summary"]
        )
        # 更新 state project_file_list
        state["project_file_list"].extend(gutils.copy_data_by_model(StateProjectFile, state["new_file_list"]))
        logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 完成")
    return {"new_file_list": state["new_file_list"], "project_file_list": state["project_file_list"]}


async def product_manager_node(state: State, runtime: Runtime, config: RunnableConfig) -> State:
    """产品经理节点

    与客户沟通的主节点，接收客户的提问，收集需求分发任务等

    Args:
        state: LangGraph 状态
        runtime: LangGraph 运行时
        config: LangGraph 运行时配置

    Returns:
        更新后的状态
    """
    logger.info(f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 进入")
    messages = []
    project_id = state["project_id"]
    writer = get_stream_writer()
    writer(CustomMessage(message=f"需求理解中..."))
    # 若用户上传文件则提取至提示词
    new_files_content = utils.format_state_new_project_files_to_str(state.get("new_file_list"))
    # 根据项目阶段匹配 Prompt
    match state["project_progress"]:
        case ProjectProgress.INIT:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_INIT_PM.template.format(
                new_files_content=new_files_content
            )))
        case ProjectProgress.REQUIREMENT_OUTLINE_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_REQUIREMENT_OUTLINE_PM.template.format(
                requirement_outline=state.get("requirement_outline") or "（空）",
                requirement_module=utils.format_state_requirement_modules_to_str(state.get("requirement_modules")),
                new_files_content=new_files_content
            )))
        case ProjectProgress.REQUIREMENT_MODULE_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_REQUIREMENT_MODULE_PM.template.format(
                requirement_outline=state.get("requirement_outline") or "（空）",
                completed_module=utils.format_state_requirement_modules_to_str(
                    state.get("requirement_modules"), RequirementModuleStatus.COMPLETED),
                pending_module=utils.format_state_requirement_modules_to_str(
                    state.get("requirement_modules"), RequirementModuleStatus.PENDING),
                current_module=utils.format_current_state_requirement_module_to_str(
                    state.get("metadata", {}).get("module"), state.get("requirement_modules")),
                risk=utils.format_issues_to_str(state.get("risks")),
                unclear_point=utils.format_issues_to_str(state.get("unclear_points")),
                new_files_content=new_files_content
            )))
        case ProjectProgress.REQUIREMENT_OVERALL_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_REQUIREMENT_OVERALL_PM.template.format(
                original_requirement=state.get("original_requirement") or "（空）",
                optimized_requirement=state.get("optimized_requirement") or "（空）",
                risk=utils.format_issues_to_str(state.get("risks")),
                unclear_point=utils.format_issues_to_str(state.get("unclear_points")),
                new_files_content=new_files_content
            )))
        case ProjectProgress.SYSTEM_ARCHITECTURE_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_SYSTEM_ARCHITECTURE_PM.template.format(
                original_architecture=state.get("original_architecture") or "（空）",
                optimized_architecture=state.get("optimized_architecture") or "（空）",
                risk=utils.format_issues_to_str(state.get("risks")),
                unclear_point=utils.format_issues_to_str(state.get("unclear_points")),
                new_files_content=new_files_content
            )))
        case ProjectProgress.SYSTEM_MODULES_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_SYSTEM_MODULES_PM.template.format(
                original_module=utils.format_state_modules_to_str(state.get("original_modules")),
                optimized_module=utils.format_state_modules_to_str(state.get("optimized_modules")),
                new_files_content=new_files_content
            )))
        case ProjectProgress.SYSTEM_DATABASE_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_SYSTEM_DATABASE_PM.template.format(
                original_database=state.get("original_database") or "（空）",
                optimized_database=state.get("optimized_database") or "（空）",
                new_files_content=new_files_content
            )))
        case ProjectProgress.SYSTEM_API_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_SYSTEM_API_PM.template.format(
                original_api=utils.format_state_apis_to_str(state.get("original_apis")),
                optimized_api=utils.format_state_apis_to_str(state.get("optimized_apis")),
                new_files_content=new_files_content
            )))
        case ProjectProgress.TEST_CASE_DESIGN:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_TEST_CASE_PM.template.format(
                original_test_case=utils.format_state_test_cases_to_str(state.get("original_test_cases")),
                optimized_test_case=utils.format_state_test_cases_to_str(state.get("optimized_test_cases")),
                new_files_content=new_files_content
            )))
        case ProjectProgress.COMPLETED:
            messages.append(SystemMessage(content=SystemPrompt.PROJECT_COMPLETED_PM.template.format(
                new_files_content=new_files_content
            )))
    messages += state["messages"]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 项目进度:{state["project_progress"]} 用户问题:{state["messages"][-1].content}")
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools(tool_list)
    result = await utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                    product_manager_output)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 主图节点:{gutils.get_func_name()} 完成")
    return result
