from langchain.messages import SystemMessage
from langgraph.config import get_stream_writer

from src.enums import SystemPrompt, ProjectProgress
from src.graphs.llms import minimax_llm
from src.graphs.main.state import State
from src.services import milvus_service
from src.graphs.main.schemas import CustomMessage, PMOutput
from src.utils import file_utils, mcp_utils
from src.repositories import project_repository, project_file_repository


async def load_project_node(state: State) -> State:
    """加载项目节点

    若state中缺少项目信息则进行不全

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态
    """
    writer = get_stream_writer()
    writer(CustomMessage(message="项目加载中..."))
    project_id = state["project_id"]
    project = await project_repository.get_by_id(project_id)
    return {
        "project_name": project.name,
        "project_progress": ProjectProgress(project.progress)
    }


async def understand_image_node(state: State) -> State:
    """理解图片文档节点
    
    使用 MiniMax MCP 的 understand_image 工具解析用户新上传的文件。
    支持 PDF、图片等格式，自动转为图片后调用 OCR/理解接口。
    
    Args:
        state: LangGraph 状态，包含 new_file_list (文件名列表)
        
    Returns:
        更新后的状态，包含 new_files_content (文件名到解析内容的映射)
    """
    files_content = {}
    minimax_mcp_tools = await mcp_utils.get_minimax_mcp_tools_by_name()
    for file in state["new_file_list"]:
        file_path = file_utils.get_project_file(state["project_id"], file)
        file_type = file_utils.get_file_type(file_path)
        # 调用 MCP 方法理解文件
        content = await minimax_mcp_tools["understand_image"].ainvoke({
            "prompt": SystemPrompt.DOCUMENT_EXTRACTOR.text,
            "image_source": file_utils.file_to_image_data_url(file_path),
        })
        content = content[0]["text"]
        files_content[file] = content
        # 写入向量数据库
        await milvus_service.add_project_file(state["project_id"], file, str(file_path), file_type, content)
    return {"new_files_content": files_content}


async def product_manager_node(state: State) -> State:
    """产品经理节点

    与客户沟通的主节点，接收客户的提问，收集需求分发任务等

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态，包含 new_files_content (文件名到解析内容的映射)
    """
    structured_output_llm = minimax_llm.with_structured_output(PMOutput)
    output = await structured_output_llm.ainvoke(
        [SystemMessage(content=SystemPrompt.PROJECT_INIT_PM.text)] + state["messages"])
    return {"messages": output.message, "next_step": output.next_step}
