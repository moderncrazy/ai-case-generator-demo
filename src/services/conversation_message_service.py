import uuid
import asyncio
import traceback
from loguru import logger
from typing import Optional
from datetime import datetime
from fastapi import UploadFile
from langchain.messages import AIMessage
from fastapi.responses import StreamingResponse

from src.config import settings
from src.context import trans_id_ctx
from src.utils import utils, file_utils
from src.models.project import Project
from src.agents.main_agent import main_agent
from src.graphs.state import State
from src.graphs.schemas import (
    StateApi,
    StateIssue,
    StateModule,
    StateTestCase,
    StateNewProjectFile,
    StateRequirementModule,
)
from src.exceptions.exceptions import BusinessException
from src.schemas.conversation_message import (
    ContextApi,
    ContextIssue,
    ApiModuleTree,
    ModuleTreeNode,
    ContextTestCase,
    TestCaseModuleTree,
    ConversationMessage,
    ConversationContext,
    ContextRequirementModule,
    ConversationMessageResponse,
)
from src.repositories.project_file_repository import project_file_repository
from src.repositories.conversation_message_repository import conversation_message_repository
from src.enums.http_method import HttpMethod
from src.enums.error_message import ErrorMessage
from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel
from src.enums.project_progress import ProjectProgress
from src.enums.conversation_role import ConversationRole
from src.enums.requirement_module_status import RequirementModuleStatus


class ConversationMessageService:
    """对话消息服务
    
    提供对话消息相关的业务逻辑处理，
    包括获取对话历史、构建对话上下文、项目对话流式响应等功能。
    """

    @staticmethod
    async def list_messages(
            project_id: str,
            page: int = 1,
            page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """获取对话历史
        
        分页获取项目的对话历史消息。
        
        Args:
            project_id: 项目 ID
            page: 页码（从 1 开始）
            page_size: 每页数量
            
        Returns:
            (消息字典列表, 总数) 元组
        """
        messages, total = await conversation_message_repository.paginate(
            project_id=project_id,
            page=page,
            page_size=page_size,
        )
        return [msg.to_dict() for msg in messages], total

    @staticmethod
    def build_context_from_state(state: State) -> ConversationContext:
        """从 State 构建对话上下文
        
        根据项目当前进度，从状态中提取相应的上下文信息。
        
        Args:
            state: 项目状态
            
        Returns:
            对话上下文对象
        """
        progress = state.get("project_progress", ProjectProgress.INIT)
        progress = ProjectProgress(progress)
        context = ConversationContext(project_progress=progress)

        match progress:
            case ProjectProgress.INIT:
                pass
            case ProjectProgress.REQUIREMENT_OUTLINE_DESIGN:
                context.requirement_outline = state.get("requirement_outline")
                context.requirement_modules = ConversationMessageService._parse_state_requirement_modules(
                    state.get("requirement_modules"))
            case ProjectProgress.REQUIREMENT_MODULE_DESIGN:
                context.requirement_outline = state.get("requirement_outline")
                context.requirement_modules = ConversationMessageService._parse_state_requirement_modules(
                    state.get("requirement_modules"))
                context.risks = ConversationMessageService._parse_state_issues(state.get("risks"))
                context.unclear_points = ConversationMessageService._parse_state_issues(state.get("unclear_points"))
            case ProjectProgress.REQUIREMENT_OVERALL_DESIGN:
                context.original_requirement = state.get("original_requirement")
                context.optimized_requirement = state.get("optimized_requirement")
                context.risks = ConversationMessageService._parse_state_issues(state.get("risks"))
                context.unclear_points = ConversationMessageService._parse_state_issues(state.get("unclear_points"))
            case ProjectProgress.SYSTEM_ARCHITECTURE_DESIGN:
                context.original_architecture = state.get("original_architecture")
                context.optimized_architecture = state.get("optimized_architecture")
                context.risks = ConversationMessageService._parse_state_issues(state.get("risks"))
                context.unclear_points = ConversationMessageService._parse_state_issues(state.get("unclear_points"))
            case ProjectProgress.SYSTEM_MODULES_DESIGN:
                context.original_modules_tree = ConversationMessageService._build_module_tree_from_modules(
                    state.get("original_modules"))
                context.optimized_modules_tree = ConversationMessageService._build_module_tree_from_modules(
                    state.get("optimized_modules"))
            case ProjectProgress.SYSTEM_DATABASE_DESIGN:
                context.original_database = state.get("original_database")
                context.optimized_database = state.get("optimized_database")
            case ProjectProgress.SYSTEM_API_DESIGN:
                modules = state["optimized_modules"]
                context.original_apis_tree = ConversationMessageService._build_apis_tree_from_modules(
                    modules, state.get("original_apis"))
                context.optimized_apis_tree = ConversationMessageService._build_apis_tree_from_modules(
                    modules, state.get("optimized_apis"))
            case ProjectProgress.TEST_CASE_DESIGN:
                modules = state["optimized_modules"]
                context.original_test_cases_tree = ConversationMessageService._build_test_cases_tree_from_modules(
                    modules, state.get("original_test_cases"))
                context.optimized_test_cases_tree = ConversationMessageService._build_test_cases_tree_from_modules(
                    modules, state.get("optimized_test_cases"))
            case ProjectProgress.COMPLETED:
                context.requirement_outline = state.get("requirement_outline")
                context.requirement_modules = ConversationMessageService._parse_state_requirement_modules(
                    state.get("requirement_modules"))
                context.original_architecture = state.get("original_architecture")
                context.optimized_architecture = state.get("optimized_architecture")
                context.original_database = state.get("original_database")
                context.optimized_database = state.get("optimized_database")

        return context

    @staticmethod
    def _parse_state_requirement_modules(modules: list[StateRequirementModule]) -> Optional[
        list[ContextRequirementModule]]:
        """解析 State 中的需求模块
        
        将状态中的需求模块数据转换为对话上下文格式。
        
        Args:
            modules: 状态中的模块列表
            
        Returns:
            上下文模块列表
        """
        if not modules:
            return None
        return [ContextRequirementModule.model_validate(item) for item in modules]

    @staticmethod
    def _parse_state_issues(issues: list[StateIssue]) -> Optional[list[ContextIssue]]:
        """解析 State 中的风险点/疑问
        
        Args:
            issues: 状态中的问题列表
            
        Returns:
            上下文问题列表
        """
        if not issues:
            return None
        return [ContextIssue.model_validate(item) for item in issues]

    @staticmethod
    def _build_module_tree_from_modules(modules: list[StateModule]) -> Optional[list[ModuleTreeNode]]:
        """从模块数据构建模块树
        
        Args:
            modules: 状态中的模块列表
            
        Returns:
            模块树形结构
        """
        if not modules:
            return None
        # 转换为 dict，方便查找
        module_dict = {}
        for item in modules:
            module_dict[item["id"]] = item
        # 找到根节点（parent_id 为 None）
        tree = []
        for id, item in module_dict.items():
            if not item.get("parent_id"):
                tree.append(ConversationMessageService._build_module_node(id, module_dict))
        return tree if tree else None

    @staticmethod
    def _build_module_node(module_id: str, module_dict: dict[str, StateModule]) -> ModuleTreeNode:
        """递归构建模块节点
        
        Args:
            module_id: 模块 ID
            module_dict: 模块字典
            
        Returns:
            模块树节点
        """
        data = module_dict[module_id]
        children = []
        for mid, m in module_dict.items():
            if m.get("parent_id") == module_id:
                children.append(ConversationMessageService._build_module_node(mid, module_dict))
        return ModuleTreeNode(
            id=module_id,
            parent_id=data.get("parent_id"),
            name=data["name"],
            description=data.get("description"),
            children=children
        )

    @staticmethod
    def _build_apis_tree_from_modules(modules: list[StateModule], apis: list[StateApi]) -> Optional[
        list[ApiModuleTree]]:
        """从模块和 API 数据构建 API 树
        
        Args:
            modules: 状态中的模块列表
            apis: 状态中的 API 列表
            
        Returns:
            API 模块树形结构
        """
        # 构建模块字典
        module_dict = {}
        for m in modules:
            mid = m.get("id")
            if mid:
                module_dict[mid] = m
        # 按 module_id 分组 APIs
        apis_by_module = {}
        if isinstance(apis, list):
            for api in apis:
                module_id = api.get("module_id")
                if module_id:
                    if module_id not in apis_by_module:
                        apis_by_module[module_id] = []
                    apis_by_module[module_id].append(ContextApi.model_validate(api))
        # 构建树
        tree = []
        for mid, m in module_dict.items():
            if m.get("parent_id") is None:
                tree.append(ConversationMessageService._build_api_module_node(mid, module_dict, apis_by_module))
        return tree if tree else None

    @staticmethod
    def _build_api_module_node(module_id: str, module_dict: dict[str, StateModule],
                               apis_by_module: dict[str, list[ContextApi]]) -> ApiModuleTree:
        """递归构建 API 模块节点
        
        Args:
            module_id: 模块 ID
            module_dict: 模块字典
            apis_by_module: 按模块分组的 API 字典
            
        Returns:
            API 模块树节点
        """
        data = module_dict[module_id]
        children = []
        for mid, m in module_dict.items():
            if m.get("parent_id") == module_id:
                children.append(ConversationMessageService._build_api_module_node(mid, module_dict, apis_by_module))
        return ApiModuleTree(
            module_id=module_id,
            module_name=data.get("name", ""),
            apis=apis_by_module.get(module_id, []),
            children=children
        )

    @staticmethod
    def _build_test_cases_tree_from_modules(modules: list[StateModule], test_cases_data: list[StateTestCase]) -> \
            Optional[list[TestCaseModuleTree]]:
        """从模块和测试用例数据构建测试用例树
        
        Args:
            modules: 状态中的模块列表
            test_cases_data: 状态中的测试用例列表
            
        Returns:
            测试用例模块树形结构
        """
        # 构建模块字典
        module_dict = {}
        for item in modules:
            module_dict[item["id"]] = item
        # 按 module_id 分组测试用例
        tcs_by_module = {}
        if isinstance(test_cases_data, list):
            for tc in test_cases_data:
                module_id = tc.get("module_id")
                if module_id:
                    if module_id not in tcs_by_module:
                        tcs_by_module[module_id] = []
                    tcs_by_module[module_id].append(ContextTestCase.model_validate(tc))
        # 构建树
        tree = []
        for mid, m in module_dict.items():
            if m.get("parent_id") is None:
                tree.append(ConversationMessageService._build_test_case_module_node(mid, module_dict, tcs_by_module))
        return tree if tree else None

    @staticmethod
    def _build_test_case_module_node(module_id: str, module_dict: dict[str, StateModule],
                                     tcs_by_module: dict[str, list[ContextTestCase]]) -> TestCaseModuleTree:
        """递归构建测试用例模块节点
        
        Args:
            module_id: 模块 ID
            module_dict: 模块字典
            tcs_by_module: 按模块分组的测试用例字典
            
        Returns:
            测试用例模块树节点
        """
        data = module_dict[module_id]
        children = []
        for mid, m in module_dict.items():
            if m.get("parent_id") == module_id:
                children.append(
                    ConversationMessageService._build_test_case_module_node(mid, module_dict, tcs_by_module))
        return TestCaseModuleTree(
            module_id=module_id,
            module_name=data.get("name", ""),
            test_cases=tcs_by_module.get(module_id, []),
            children=children
        )

    @staticmethod
    async def _start_agent(project_id: str, message: str, file_list: list[StateNewProjectFile] | None, queue):
        """启动 AI Agent 处理对话
        
        异步流式处理用户消息，返回 AI 响应。
        
        Args:
            project_id: 项目 ID
            message: 用户消息
            file_list: 上传的文件列表
            queue: 消息队列，用于异步通信
        """
        try:
            async for chunk in await main_agent.astream(project_id, message, file_list):
                # 将 chunk 转为 SSE 格式
                match chunk["type"]:
                    case "custom":
                        msg = chunk["data"]["message"]
                        # 创建对话
                        msg_id = await conversation_message_repository.create(
                            project_id=project_id,
                            role=ConversationRole.SYSTEM,
                            content=msg)
                        msg_response = ConversationMessage(
                            id=msg_id,
                            role=ConversationRole.SYSTEM,
                            content=msg,
                            created_at=datetime.now()
                        )
                        response = ConversationMessageResponse(message=msg_response)
                        logger.info(
                            f"trans_id:{trans_id_ctx.get()} 方法:{utils.get_func_name()} 自定义消息发送:{response.model_dump_json()}")
                        # 响应用户
                        await queue.put(f"data: {response.model_dump_json()}\n\n")
                    case "values":
                        state = chunk["data"]
                        # 检查节点返回是否包含对话
                        if state.get("messages"):
                            msg = state["messages"][-1]
                            if isinstance(msg, AIMessage):
                                msg_content = msg.content
                                # 返回思考内容 但不记录
                                if isinstance(msg_content, list) and msg_content[0].get("thinking"):
                                    msg_response = ConversationMessage(
                                        id="",
                                        role=ConversationRole.SYSTEM,
                                        content=msg_content[0]["thinking"],
                                        created_at=datetime.now()
                                    )
                                    response = ConversationMessageResponse(message=msg_response)
                                    # 响应用户
                                    await queue.put(f"data: {response.model_dump_json()}\n\n")
                                # 如果是正式回话 则记录并返回
                                if msg_content and not msg.tool_calls:
                                    # 创建对话
                                    msg_id = await conversation_message_repository.create(
                                        project_id=project_id,
                                        role=ConversationRole.ASSISTANT,
                                        content=msg_content)
                                    msg_response = ConversationMessage(
                                        id=msg_id,
                                        role=ConversationRole.ASSISTANT,
                                        content=msg_content,
                                        created_at=datetime.now()
                                    )
                                    response = ConversationMessageResponse(
                                        message=msg_response,
                                        context=ConversationContext(
                                            project_progress=state["project_progress"])
                                    )
                                    logger.info(
                                        f"trans_id:{trans_id_ctx.get()} 方法:{utils.get_func_name()} AI消息发送:{response.model_dump_json()}")
                                    # 响应用户
                                    await queue.put(f"data: {response.model_dump_json()}\n\n")
                    case _:
                        print(chunk)
        except Exception as e:
            await queue.put("error: \n\n")
            logger.error(
                f"trans_id:{trans_id_ctx.get()} 方法:{utils.get_func_name()} 异常:{str(e)}\n异常栈:{traceback.format_exc()}")
        finally:
            await queue.put(None)

    @staticmethod
    async def _send_heartbeat(queue):
        """发送心跳包
        
        每3秒发送一次心跳包，保持连接活跃。
        
        Args:
            queue: 消息队列
        """
        while True:
            await asyncio.sleep(3)
            await queue.put("heartbeat: \n\n")

    @staticmethod
    async def discuss_project(
            project: Project,
            message: str,
            files: list[UploadFile] = None,
    ) -> StreamingResponse:
        """项目对话
        
        处理用户与 AI 的对话请求，支持上传文件。
        返回流式响应（SSE 格式）。
        
        Args:
            project: 项目对象
            message: 用户消息
            files: 上传的文件列表（可选）
            
        Returns:
            流式响应（Server-Sent Events）
            
        Raises:
            BusinessException: 文件类型错误、文件大小超限等
        """
        # 上传文件检查
        conversation_message_id = str(uuid.uuid4())
        graph_file_list: list[StateNewProjectFile] = []
        project_file_total_size = await project_file_repository.get_total_size(project.id)
        if files:
            for file in files:
                # 检查文件类型
                file_type = file_utils.get_file_type(file.filename)
                if file_type not in settings.project_file_types:
                    raise BusinessException.from_error_message(ErrorMessage.FILE_TYPE_ERROR)
                # 文件大小检查
                if file.size > settings.project_file_max_size:
                    raise BusinessException.from_error_message(ErrorMessage.FILE_SIZE_ERROR)
                # 检查项目文件总大小，未超过则累加
                if (file.size + project_file_total_size) > settings.project_file_total_max_size:
                    raise BusinessException.from_error_message(ErrorMessage.PROJECT_FILE_TOTAL_SIZE_ERROR)
                else:
                    project_file_total_size += file.size
                # 检查文件是否存在
                if await project_file_repository.get_by_project_and_name(project.id, file.filename):
                    raise BusinessException.from_error_message(ErrorMessage.PROJECT_FILE_EXIST_ERROR)
                # 存储文件
                file_path = file_utils.save_project_file(project.id, file.filename, await file.read())
                # 检查文件安全性
                scan_result = file_utils.scan_file_with_clamav(file_path)
                # 不安全则删除文件
                if not scan_result:
                    file_path.unlink(missing_ok=True)
                    raise BusinessException.from_error_message(ErrorMessage.FILE_EXCEPTION_ERROR)
                graph_file_list.append(StateNewProjectFile(
                    conversation_message_id=conversation_message_id,
                    name=file.filename,
                    path=str(file_path),
                    type=file_type,
                    size=file.size,
                    created_at=datetime.now()
                ))

        # 创建用户对话记录
        await conversation_message_repository.create(
            id=conversation_message_id,
            project_id=project.id,
            role=ConversationRole.USER,
            content=message)

        # 进行项目对话
        async def event_generator():
            # 创建异步任务发送心跳包 保持链接
            queue = asyncio.Queue()
            heart_task = asyncio.create_task(ConversationMessageService._send_heartbeat(queue))
            agent_task = asyncio.create_task(
                ConversationMessageService._start_agent(project.id, message, graph_file_list, queue))
            try:
                while True:
                    try:
                        # 每秒检查队列，有数据 不为 None 则发送给前端
                        data = await asyncio.wait_for(queue.get(), timeout=1)
                        if data is None:
                            break
                        yield data
                    except asyncio.TimeoutError:
                        continue
            except Exception as e:
                logger.error(
                    f"trans_id:{trans_id_ctx.get()} 方法:{utils.get_func_name()} 异常:{str(e)}\n异常栈:{traceback.format_exc()}")
            finally:
                agent_task.cancel()
                heart_task.cancel()
                logger.info(f"trans_id:{trans_id_ctx.get()} 方法:{utils.get_func_name()} 对话结束")

        return StreamingResponse(event_generator(), media_type="text/event-stream")


# 导出单例
conversation_message_service = ConversationMessageService()
