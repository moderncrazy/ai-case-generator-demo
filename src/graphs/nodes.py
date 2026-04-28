import orjson
from loguru import logger
from langgraph.graph import END
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langchain_core.runnables import RunnableConfig
from langchain.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage

from src.config import settings
from src import constant as const
from src.context import trans_id_ctx
from src.utils import file_utils, mcp_utils, prompt_utils, utils as gutils
from src.graphs import utils
from src.graphs.state import State
from src.graphs.schemas import FileSummaryOutput
from src.graphs.tools import tool_list, product_manager_output
from src.graphs.common.llms import default_model
from src.graphs.common.schemas import StateProjectFile
from src.graphs.common.tools.tools import tool_list as ctool_list
from src.graphs.common.utils import structured_output_utils, repository_utils, utils as cutils
from src.services.milvus_service import milvus_service
from src.enums.project_progress import ProjectProgress
from src.enums.group_member_role import GroupMemberRole
from src.enums.const_system_prompt import ConstSystemPrompt
from src.enums.conversation_message_type import ConversationMessageType
from src.repositories.module_repository import module_repository
from src.repositories.project_repository import project_repository
from src.repositories.test_case_repository import test_case_repository
from src.repositories.conversation_summary_repository import conversation_summary_repository
from src.repositories.project_file_repository import project_file_repository, ProjectFileCreate


async def fix_state_messages_node(state: State) -> State:
    """修复状态消息节点

    若state的messages中出现AI tool call没有tool回应时删除tool call message

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    project_id = state["project_id"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    remove_messages = []
    for index, message in enumerate(state["messages"]):
        if isinstance(message, AIMessage) and message.tool_calls:
            if not isinstance(state["messages"][index + 1], ToolMessage):
                remove_messages.append(RemoveMessage(id=message.id))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 删除消息:{len(remove_messages)} 完成")
    return {"messages": remove_messages}


async def load_project_node(state: State) -> State:
    """加载项目节点

    若state中缺少项目信息则进行补全

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    project_id = state["project_id"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message("项目加载中...", GroupMemberRole.PM)
    project = await project_repository.get_by_id(project_id)
    requirement_module = orjson.loads(project.requirement_module_design or "[]")
    modules = await module_repository.list_by_project(project_id)
    modules = [item.to_dict() for item in modules]
    apis = await  repository_utils.list_by_project_to_state_api(project_id)
    test_cases = await test_case_repository.list_by_project(project_id)
    test_cases = [item.to_dict() for item in test_cases]
    project_files = await project_file_repository.list_by_project(project_id)
    project_files = gutils.copy_data_by_model(StateProjectFile, [item.to_dict() for item in project_files])
    history_summary = (await conversation_summary_repository.get_latest(project_id))
    history_summary = history_summary.summary if history_summary else const.EMPTY_ZH
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return {
        "history_summary": history_summary,
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
    project_id = state["project_id"]
    writer = get_stream_writer()
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    minimax_mcp_tools = await mcp_utils.get_minimax_mcp_tools_by_name()
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 新文件:{gutils.to_json(state["new_file_list"])}")
    for file in state["new_file_list"]:
        # 发送自定义消息
        cutils.send_custom_message(f"理解《{file["name"]}》中...", GroupMemberRole.PM)
        # 调用 MCP 方法理解文件
        content_output = await minimax_mcp_tools["understand_image"].ainvoke({
            "prompt": ConstSystemPrompt.DOCUMENT_EXTRACTOR.text,
            "image_source": file_utils.file_to_image_data_url(file["path"]),
        })
        file["content"] = content_output[0]["text"]
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 理解文件:{file["name"]}")
        # 生成文件摘要
        cutils.send_custom_message(f"整理《{file["name"]}》中...", GroupMemberRole.PM)
        structured_output_llm = default_model.with_structured_output(FileSummaryOutput)
        # 设置重试次数
        structured_output_llm.with_retry(stop_after_attempt=settings.model_output_retry)
        file_summary_output: FileSummaryOutput = await structured_output_llm.ainvoke([
            SystemMessage(content=ConstSystemPrompt.FILE_SUMMARY.text),
            HumanMessage(content=f"文件名称：{file["name"]}\n文件内容：\n{file["content"]}"),
        ])
        file["summary"] = file_summary_output.summary
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 总结文件:{file["name"]}")
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
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
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
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    cutils.send_custom_message("需求理解中...", GroupMemberRole.PM)
    # 根据项目阶段匹配 Prompt
    system_prompt = prompt_utils.get_product_manager_prompt(project_progress, state["history_summary"])
    # 对最新一条 HumanMessage 增加系统提示
    history_messages = utils.latest_human_message_append_system_hint(state["messages"])
    messages = [SystemMessage(content=system_prompt), *history_messages]
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 项目进度:{project_progress} 收到消息:{gutils.to_one_line(str(state["messages"][-1].content))}")
    # 绑定查询方法和结构化输出方法
    metadata = {"role": GroupMemberRole.PM}
    llm_with_tool = default_model.bind_tools([*tool_list, *ctool_list], tool_choice="any", strict=True)
    result = await structured_output_utils.llm_tool_structured_output(
        llm_with_tool, state, runtime, config, messages, product_manager_output, metadata=metadata)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def end_node(state: State) -> State:
    """结束节点

    进行善后工作，如：清理用户本次上传文件列表，发送结束标识

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    project_id = state["project_id"]
    # 发送结束消息
    cutils.send_custom_message(END, GroupMemberRole.PM, ConversationMessageType.END)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 流程结束")
    return {"new_file_list": [], "private_messages": []}
