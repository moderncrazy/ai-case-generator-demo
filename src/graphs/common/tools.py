import uuid
from typing import Any
from loguru import logger
from langchain.tools import tool, ToolRuntime, BaseTool

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.models.project_file import ProjectFile
from src.graphs import utils
from src.graphs.state import State
from src.graphs.common.schemas import StateRequirementModule, StateModule, StateApi, StateTestCase, StateProjectFile, \
    StateNewProjectFile
from src.repositories.project_file_repository import project_file_repository
from src.services.project_file_service import project_file_service
from src.services.milvus_service import milvus_service, ProjectContextSearchResult, ProjectFileSearchResult


@tool
async def get_project_file_by_id(id: str, runtime: ToolRuntime) -> ProjectFile:
    """根据文件ID查询项目文件
    
    AI大模型使用此工具可获取指定文件的完整信息。
    
    **功能说明：**
    通过文件ID从数据库中查询该文件的基本信息，包括文件名、路径、类型、大小、文件内容、内容摘要、创建时间等。
    
    Args:
        id: 文件的唯一标识符，即文件的UUID
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 ProjectFile 对象，包含以下字段：
        - id: str - 文件唯一标识
        - project_id: str - 所属项目ID
        - name: str - 文件名
        - path: str - 文件存储路径
        - type: str - 文件类型（如 pdf、docx）
        - size: int - 文件大小（字节）
        - summary: str - 文件内容摘要
        - content: str - 完整文件内容
        - created_at: datetime - 创建时间
        - updated_at: datetime - 更新时间
    
    Exception:
        文件ID不存在或已被删除 → 返回 None，AI应检查文件是否有效
        数据库连接异常 → 尝试重新调用该方法，若再次失败则可尝试调用 search_project_files 方法搜索文件
    """
    project_id = runtime.state["project_id"]
    result = await project_file_repository.get_by_id(id)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def search_project_files(query: str, runtime: ToolRuntime) -> list[ProjectFileSearchResult]:
    """搜索项目文件
    
    AI大模型使用此工具可在项目的历史文件库中进行语义搜索，找到与查询内容相关的文件。
    
    **功能说明：**
    利用向量数据库的混合检索能力（稠密向量+稀疏向量），在当前项目中搜索与查询语句语义相关的项目文件。
    返回的文件按相关性排序，便于AI快速定位所需参考文件。
    
    Args:
        query: 搜索查询文本，建议使用描述性的自然语言，如"用户登录相关的需求"或"数据库表结构设计"
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 ProjectFileSearchResult 对象列表，包含以下字段：
        - id: int - 搜索结果ID
        - distance: float - 与查询向量的距离/相似度
        - project_id: str - 所属项目ID
        - name: str - 文件名
        - path: str - 文件路径
        - type: str - 文件类型
        - content: str - 文件内容
        - summary: str - 文件摘要
        - create_time: str - 创建时间
        - metadata: dict - 额外元数据
    
    Exception:
        向量数据库Milvus服务不可用 → 尝试使用 get_project_file_list 获取文件列表，再根据 Id 调用 get_project_file_by_id 获取文件
        查询文本为空 → 可能返回全部文件或报错，需保证query非空
        项目无文件 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = await milvus_service.search_project_files(query, project_id)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 查询内容:{query} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_project_files_summary(runtime: ToolRuntime) -> str:
    """获取项目文件摘要汇总
    
    AI大模型使用此工具可快速了解当前项目已上传的所有文件概要。
    
    **功能说明：**
    获取当前项目中所有已入库文件的摘要信息，并按一定格式组织成字符串返回。
    便于AI在分析需求时快速浏览项目背景资料。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，每个文件的格式为：
        文件Id：{id}
        文件名：{name}
        上传时间：{created_at}
        文件摘要：
        {summary}
        
        ----------{name} end----------
        
        如果项目无文件，则返回"（空）"
    
    Exception:
        数据库查询异常 → 该方法暂不可用
    """
    project_id = runtime.state["project_id"]
    result = await project_file_service.get_project_files_summary_to_str(project_id)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def search_project_history_conversation(query: str, runtime: ToolRuntime) -> list[ProjectContextSearchResult]:
    """搜索项目历史对话摘要
    
    AI大模型使用此工具可在项目历史对话记录中进行语义检索，找到与当前分析相关的历史上下文摘要。
    
    **功能说明：**
    利用向量数据库检索项目中历史对话记录里与查询相关的片段。
    可帮助AI在继续分析时保持上下文连贯性，或参考之前的讨论结论。
    
    Args:
        query: 搜索查询文本，如"关于用户模块的风险点"或"之前的架构建议"
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 ProjectContextSearchResult 对象列表，包含以下字段：
        - id: int - 搜索结果ID
        - distance: float - 与查询向量的距离/相似度
        - project_id: str - 所属项目ID
        - content: str - 对话上下文内容
        - create_time: str - 创建时间
        - metadata: dict - 额外元数据
    
    Exception:
        项目无对话历史 → 返回空列表
        向量数据库服务异常 → 该方法暂不可用
        查询结果噪音过大 → 可尝试添加更多限定词缩小范围
    """
    project_id = runtime.state["project_id"]
    result = await milvus_service.search_project_context(project_id, query)
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 查询内容:{query} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_requirement_outline(runtime: ToolRuntime[Any, State]) -> str:
    """获取需求大纲
    
    AI大模型使用此工具可获取当前项目的需求大纲内容。
    
    **功能说明：**
    从运行时状态中读取并返回当前项目已完成的需求大纲。
    需求大纲是对用户需求上下文进行结构化总结分析后的产物，包含需求的整体框架和关键要点。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即需求大纲的完整内容（Markdown格式）
    
    Exception:
        需求大纲未生成 → 返回空字符串
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("requirement_outline", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_requirement_modules(runtime: ToolRuntime[Any, State]) -> list[StateRequirementModule]:
    """获取需求模块列表
    
    AI大模型使用此工具可获取当前项目的需求模块列表。
    
    **功能说明：**
    从运行时状态中读取并返回需求大纲下拆分的各功能模块列表。
    每个模块包含名称、序号、状态、描述和详细内容。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateRequirementModule 对象列表，包含以下字段：
        - name: str - 模块名称
        - order: int - 模块序号（用于排序）
        - status: RequirementModuleStatus - 模块状态（pending/draft/completed）
        - description: str - 模块简述
        - content: str | None - 模块详细内容（待填充）
    
    Exception:
        需求模块未创建 → 返回空列表
        模块内容为空 → 模块详细内容未生成
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("requirement_modules", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_original_requirement(runtime: ToolRuntime[Any, State]) -> str:
    """获取原始需求文档
    
    AI大模型使用此工具可获取在 requirement_overall_design 阶段生成的初版需求文档内容。
    
    **功能说明：**
    从运行时状态中读取并返回在 requirement_overall_design 阶段生成的初版的原始需求文档内容。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即原始需求文档全文
    
    Exception:
        原始需求文档不存在 → 返回空字符串
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_requirement", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_requirement(runtime: ToolRuntime[Any, State]) -> str:
    """获取当前需求文档
    
    AI大模型使用此工具可获取经过AI优化后的需求文档。
    
    **功能说明：**
    从运行时状态中读取并返回经过优化处理的需求文档。
    优化内容包括：补全不明确点、修正逻辑、补充细节等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即优化后的需求文档全文
    
    Exception:
        原始需求文档未优化 → 返回空字符串
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_requirement", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_original_architecture(runtime: ToolRuntime[Any, State]) -> str:
    """获取原始架构设计
    
    AI大模型使用此工具可获取最初生成的系统架构设计方案。
    
    **功能说明：**
    从运行时状态中读取并返回初始生成的架构设计内容。
    该设计可能存在一些问题，需要后续评审和优化。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即原始架构设计文档
    
    Exception:
        架构设计未生成 → 返回空字符串
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_architecture", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_architecture(runtime: ToolRuntime[Any, State]) -> str:
    """获取当前架构设计
    
    AI大模型使用此工具可获取经过优化和评审后的系统架构设计。
    
    **功能说明：**
    从运行时状态中读取并返回经过多视角评审优化后的架构设计。
    优化内容包括：解决架构问题、补充设计细节、调整技术选型等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即优化后的架构设计文档
    
    Exception:
        原始架构设计未优化 → 返回空字符串
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_architecture", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_original_modules(runtime: ToolRuntime[Any, State]) -> list[StateModule]:
    """获取原始系统模块列表
    
    AI大模型使用此工具可获取初步拆分的系统功能模块列表。
    
    **功能说明：**
    从运行时状态中读取并返回系统架构中包含的各功能模块定义。
    这些模块是按层级组织的（parent_id标识父子关系）。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateModule 对象列表，包含以下字段：
        - id: str - 模块唯一标识
        - parent_id: str | None - 父模块ID（顶级模块为空）
        - name: str - 模块名称
        - description: str | None - 模块描述
    
    Exception:
        系统模块未生成 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_modules", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_current_modules(runtime: ToolRuntime[Any, State]) -> list[StateModule]:
    """获取当前系统模块列表
    
    AI大模型使用此工具可获取经过优化调整后的系统功能模块列表。
    
    **功能说明：**
    从运行时状态中读取并返回优化后的系统模块定义。
    优化可能包括：调整模块层级、补充模块描述、合并或拆分模块等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateModule 对象列表，包含以下字段：
        - id: str - 模块唯一标识
        - parent_id: str | None - 父模块ID
        - name: str - 模块名称
        - description: str | None - 模块描述
    
    Exception:
        原始系统模块未优化 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_modules", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_original_database(runtime: ToolRuntime[Any, State]) -> str:
    """获取原始数据库设计
    
    AI大模型使用此工具可获取最初生成的数据库设计文档。
    
    **功能说明：**
    从运行时状态中读取并返回初始生成的数据库设计，包括表结构、字段定义、索引设计等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即原始数据库设计文档（通常是SQL或ER图描述）
    
    Exception:
        数据库设计未生成 → 返回空字符串
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_database", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_current_database(runtime: ToolRuntime[Any, State]) -> str:
    """获取当前数据库设计
    
    AI大模型使用此工具可获取经过优化评审后的数据库设计。
    
    **功能说明：**
    从运行时状态中读取并返回优化后的数据库设计。
    优化可能包括：补充字段注释、调整索引设计、优化表结构等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 str 类型的字符串，即优化后的数据库设计文档
    
    Exception:
        原始数据库设计未优化 → 返回空字符串
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_database", "")
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_original_apis(runtime: ToolRuntime[Any, State]) -> list[StateApi]:
    """获取原始接口设计列表
    
    AI大模型使用此工具可获取初步设计的API接口列表。
    
    **功能说明：**
    从运行时状态中读取并返回系统包含的所有接口定义。
    每个接口包含路径、方法、参数、响应等信息。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateApi 对象列表，包含以下字段：
        - id: str - 接口唯一标识
        - module_id: str - 所属模块ID
        - name: str - 接口名称
        - method: HttpMethod - HTTP方法（get/post/put/delete）
        - path: str - 接口路径
        - description: str | None - 接口描述
        - request_headers: list[StateApiRequestParam] | None - 请求头参数
        - request_params: list[StateApiRequestParam] | None - URL查询参数
        - request_body: list[StateApiRequestParam] | None - 请求体参数
        - response_schema: str - 响应结构定义
        - test_script: str | None - 测试脚本
        
        其中 StateApiRequestParam 包含以下字段：
        - name: str - 参数名称
        - type: HttpParamType - 参数类型（string/number/boolean/object/array）
        - required: bool - 是否必传
        - description: str - 参数描述
    
    Exception:
        接口未设计 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_apis", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_current_apis(runtime: ToolRuntime[Any, State]) -> list[StateApi]:
    """获取当前接口设计列表
    
    AI大模型使用此工具可获取经过优化评审后的API接口列表。
    
    **功能说明：**
    从运行时状态中读取并返回优化后的接口定义。
    优化可能包括：补充参数说明、调整响应结构、完善测试脚本等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateApi 对象列表，包含以下字段：
        - id: str - 接口唯一标识
        - module_id: str - 所属模块ID
        - name: str - 接口名称
        - method: HttpMethod - HTTP方法（get/post/put/delete）
        - path: str - 接口路径
        - description: str | None - 接口描述
        - request_headers: list[StateApiRequestParam] | None - 请求头参数
        - request_params: list[StateApiRequestParam] | None - URL查询参数
        - request_body: list[StateApiRequestParam] | None - 请求体参数
        - response_schema: str - 响应结构定义
        - test_script: str | None - 测试脚本
        
        其中 StateApiRequestParam 包含以下字段：
        - name: str - 参数名称
        - type: HttpParamType - 参数类型（string/number/boolean/object/array）
        - required: bool - 是否必传
        - description: str - 参数描述
    
    Exception:
        原始接口未优化 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_apis", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_original_test_cases(runtime: ToolRuntime[Any, State]) -> list[StateTestCase]:
    """获取原始测试用例列表
    
    AI大模型使用此工具可获取初步生成的测试用例列表。
    
    **功能说明：**
    从运行时状态中读取并返回为各功能模块生成的测试用例。
    用例包含标题、前置条件、测试步骤、预期结果、测试数据等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateTestCase 对象列表，包含以下字段：
        - id: str | None - 用例ID（入库后生成）
        - module_id: str - 所属模块ID
        - title: str - 用例标题
        - precondition: str | None - 前置条件
        - test_steps: str - 测试步骤
        - expected_result: str - 预期结果
        - test_data: str - 测试数据
        - level: TestCaseLevel - 用例等级（p0/p1/p2/p3）
        - type: TestCaseType - 用例类型（functional/interface/performance等）
    
    Exception:
        用例未生成 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("original_test_cases", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_current_test_cases(runtime: ToolRuntime[Any, State]) -> list[StateTestCase]:
    """获取当前测试用例列表
    
    AI大模型使用此工具可获取经过优化调整后的测试用例列表。
    
    **功能说明：**
    从运行时状态中读取并返回优化后的测试用例。
    优化可能包括：用例分级调整、步骤补充完善、优先级排序等。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateTestCase 对象列表，包含以下字段：
        - id: str | None - 用例ID（入库后生成）
        - module_id: str - 所属模块ID
        - title: str - 用例标题
        - precondition: str | None - 前置条件
        - test_steps: str - 测试步骤
        - expected_result: str - 预期结果
        - test_data: str - 测试数据
        - level: TestCaseLevel - 用例等级（p0/p1/p2/p3）
        - type: TestCaseType - 用例类型（functional/interface/performance等）
    
    Exception:
        原始用例未优化 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("optimized_test_cases", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_project_file_list(runtime: ToolRuntime[Any, State]) -> list[StateProjectFile]:
    """获取项目文件列表
    
    AI大模型使用此工具可获取当前项目已入库的所有文件清单。
    
    **功能说明：**
    从运行时状态中读取并返回当前项目上传的所有文件列表。
    注：
        1. 此列表包含本次对话新上传的文件。
        2. 此列表只包含文件内容摘要，不包含文件内容。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateProjectFile 对象列表，包含以下字段：
        - id: str - 文件唯一标识
        - conversation_message_id: str - 关联对话消息ID
        - name: str - 文件名
        - path: str - 文件路径
        - type: str - 文件类型
        - size: int - 文件大小（字节）
        - summary: str - 文件内容摘要
        - created_at: datetime - 创建时间
    
    Exception:
        项目无上传文件 → 返回空列表
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("project_file_list", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def get_new_project_file_list(runtime: ToolRuntime[Any, State]) -> list[StateNewProjectFile]:
    """获取本次对话用户上传的新项目文件
    
    AI大模型使用此工具可获取用户在本轮对话中新上传的文件。
    
    **功能说明：**
    从运行时状态中读取并返回本次会话中新上传的文件。
    这些文件可能包含用户新补充的需求参考资料。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 StateNewProjectFile 对象列表，包含以下字段：
        - id: str | None - 文件ID（入库后生成）
        - conversation_message_id: str - 关联对话消息ID
        - name: str - 文件名
        - path: str - 文件路径
        - type: str - 文件类型
        - size: int - 文件大小（字节）
        - content: str | None - 文件内容（OCR解析后）
        - summary: str | None - 文件摘要
        - created_at: datetime | None - 创建时间
    
    Exception:
        本次无新上传文件 → 返回空列表（这是正常的）
    """
    project_id = runtime.state["project_id"]
    result = runtime.state.get("new_file_list", [])
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


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
        问题：xxx
        建议方案：xxx

        如果无风险点，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = utils.format_issues_to_str(runtime.state.get("risks"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
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
        问题：xxx
        建议方案：xxx

        如果无不明确问题，则返回"（空）"
    """
    project_id = runtime.state["project_id"]
    result = utils.format_issues_to_str(runtime.state.get("unclear_points"))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_one_line(result)}")
    return result


@tool
async def get_project_info(runtime: ToolRuntime) -> dict[str, Any]:
    """获取项目基本信息
    
    AI大模型使用此工具可快速了解当前项目的整体状态概况。
    
    **功能说明：**
    从运行时状态中提取并返回项目的基本信息，包括项目ID、名称、当前进度、已识别风险和待澄清问题。
    便于AI在做决策时了解全局上下文。
    
    Args:
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 dict 对象，包含以下字段：
        - project_id: str - 项目唯一标识
        - project_name: str - 项目名称
        - project_progress: ProjectProgress - 当前进度状态（init/requirement_outline_design/requirement_module_design/requirement_overall_design/system_architecture_design/system_modules_design/system_database_design/system_api_design/test_case_design/completed）
        - risks: list[str] - 已识别风险点列表（可能为空）
        - unclear_points: list[str] - 待澄清问题列表（可能为空）
    
    Exception:
        项目信息不完整 → 返回的字典中某些字段可能缺失或为空
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
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(result)}")
    return result


@tool
async def batch_generator_uuid(size: int, runtime: ToolRuntime) -> list[str]:
    """批量生成唯一标识符
    
    AI大模型使用此工具可批量生成符合 UUID 标准的唯一标识符。
    
    **功能说明：**
    当需要为多个实体（如系统模块、测试用例、API接口等）生成唯一ID时，可调用此工具批量生成。
    返回的 UUID 符合 RFC 4122 标准，保证全局唯一性。
    
    Args:
        size: int - 需要生成的 UUID 数量
        runtime: 系统运行时对象，AI传参时不用传递，会自动注入
    
    Returns:
        返回 list[str] 对象，包含 size 个 UUID 字符串，如：
        ["550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440001", ...]
    
    Exception:
        size 为负数或零 → 返回空列表
        size 过大（如超过10000） → 可能造成性能问题，建议分批调用
    """
    results = []
    project_id = runtime.state["project_id"]
    for i in range(size):
        results.append(str(uuid.uuid4()))
    logger.info(
        f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{gutils.to_json(results)}")
    return results


# 自动加载本文件所有tool
tool_list = [obj for name, obj in globals().items() if isinstance(obj, BaseTool)]
tool_by_name = {tool.name: tool for tool in tool_list}
