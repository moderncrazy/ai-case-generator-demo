import uuid
import orjson
import asyncio
import traceback

from loguru import logger
from collections import deque
from datetime import datetime
from fastapi import UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langchain.messages import SystemMessage, AIMessage, AIMessageChunk, HumanMessage, RemoveMessage

from src.context import trans_id_ctx
from src.config import settings
from src.enums.conversation_message_status import ConversationMessageStatus
from src.utils import utils, file_utils, sensitive_word_utils
from src.models.business.project import Project
from src.agents.main_agent import main_agent
from src.graphs.common.utils import utils as cutils
from src.graphs.common.llms import default_model
from src.graphs.common.schemas import StateNewProjectFile
from src.exceptions.exceptions import BusinessException
from src.schemas.conversation_message import (
    ConversationMessage,
    ConversationContext,
    HistoryConversationMessage,
    ConversationMessageResponse,
)
from src.repositories.project_file_repository import project_file_repository
from src.repositories.conversation_message_repository import conversation_message_repository
from src.repositories.conversation_summary_repository import conversation_summary_repository
from src.services.redis_service import redis_service
from src.services.milvus_service import milvus_service
from src.services.conversation_summary_service import conversation_summary_service
from src.enums.error_message import ErrorMessage
from src.enums.project_progress import ProjectProgress
from src.enums.conversation_role import ConversationRole
from src.enums.const_system_prompt import ConstSystemPrompt
from src.enums.conversation_message_type import ConversationMessageType


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
    ) -> tuple[list[HistoryConversationMessage], int]:
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
        messages = [
            HistoryConversationMessage.model_validate({**msg.to_dict(), "metadata": orjson.loads(msg.metadata or "{}")})
            for msg in messages
        ]
        return messages, total

    @staticmethod
    async def _start_agent(project: Project, message: str, file_list: list[StateNewProjectFile] | None, queue):
        """启动 AI Agent 处理对话
        
        异步流式处理用户消息，返回 AI 响应。
        
        Args:
            project_id: 项目 ID
            message: 用户消息
            file_list: 上传的文件列表
            queue: 消息队列，用于异步通信
        """
        custom_messages = []
        try:
            # 最近3条消息内容 如果消息在该列表则不再发送
            latest_message_content_list = deque(maxlen=3)
            async for chunk in await main_agent.astream(project.id, message, file_list):
                # 将 chunk 转为 SSE 格式
                match chunk["type"]:
                    case "custom":
                        msg_type = chunk["data"].type
                        msg_content = chunk["data"].message
                        msg_assistant_role = chunk["data"].role
                        # 如果内容存在 且未发送过 则发送
                        if (msg_content
                                and msg_content != (custom_messages[-1] if custom_messages else None)
                                and msg_content not in latest_message_content_list):
                            if msg_type in [ConversationMessageType.STAGE, ConversationMessageType.MESSAGE]:
                                custom_messages.append(msg_content)
                            latest_message_content_list.append(msg_content)
                            msg_response = ConversationMessage(
                                id="",
                                role=ConversationRole.SYSTEM,
                                assistant_role=msg_assistant_role,
                                type=msg_type,
                                content=msg_content,
                                created_at=datetime.now()
                            )
                            response = ConversationMessageResponse(message=msg_response)
                            logger.info(
                                f"trans_id:{trans_id_ctx.get()} 项目Id:{project.id} 自定义消息发送:{response.model_dump_json()}")
                            # 响应用户
                            await queue.put(f"data: {response.model_dump_json()}\n\n")
                    case "values":
                        state = chunk["data"]
                        # 检查节点返回是否包含对话
                        if state.get("messages"):
                            msg = state["messages"][-1]
                            if isinstance(msg, AIMessage):
                                msg_content = msg.content
                                # 如果是正式回话 则记录并返回
                                if msg_content and not msg.tool_calls and msg_content not in latest_message_content_list:
                                    latest_message_content_list.append(msg_content)
                                    msg_metadata = {
                                        "custom_messages": custom_messages.copy(),
                                        "status": ConversationMessageStatus.SUCCESS.value
                                    }
                                    # 清空自定义消息
                                    custom_messages.clear()
                                    # 创建对话
                                    msg_id = await conversation_message_repository.create(
                                        project_id=project.id,
                                        role=ConversationRole.ASSISTANT,
                                        content=msg_content,
                                        metadata=utils.to_json(msg_metadata),
                                    )
                                    # 生成响应格式
                                    msg_response = ConversationMessage(
                                        id=msg_id,
                                        role=ConversationRole.ASSISTANT,
                                        type=ConversationMessageType.MESSAGE,
                                        content=msg_content,
                                        metadata=msg_metadata,
                                    )
                                    response = ConversationMessageResponse(
                                        message=msg_response,
                                        context=ConversationContext(project_progress=state["project_progress"])
                                    )
                                    logger.info(
                                        f"trans_id:{trans_id_ctx.get()} 项目Id:{project.id} AI消息发送:{response.model_dump_json()}")
                                    # 响应用户
                                    await queue.put(f"data: {response.model_dump_json()}\n\n")
                    case "messages":
                        token, metadata = chunk["data"]
                        if (isinstance(token, AIMessageChunk)
                                and token.content_blocks
                                and not token.tool_calls):
                            msg_content = "".join([block[block["type"]] for block in token.content_blocks
                                                   if block["type"] not in ["tool_call_chunk"]])
                            # 过滤系统工具
                            msg_content = sensitive_word_utils.filter_ai_output_content(msg_content)
                            if msg_content and msg_content not in latest_message_content_list:
                                latest_message_content_list.append(msg_content)
                                msg_response = ConversationMessage(
                                    id="",
                                    role=ConversationRole.SYSTEM,
                                    assistant_role=metadata.get("role"),
                                    type=ConversationMessageType.STREAM,
                                    content=msg_content,
                                    created_at=datetime.now()
                                )
                                response = ConversationMessageResponse(
                                    message=msg_response,
                                    context=ConversationContext(project_progress=ProjectProgress(project.progress))
                                )
                                # 响应用户
                                await queue.put(f"data: {response.model_dump_json()}\n\n")
                    case _:
                        print(chunk)
        except Exception as e:
            # 创建系统异常对话
            msg_content = "系统繁忙，请稍后再试！"
            msg_metadata = {
                "custom_messages": custom_messages,
                "status": ConversationMessageStatus.FAILED.value
            }
            msg_id = await conversation_message_repository.create(
                project_id=project.id,
                role=ConversationRole.SYSTEM,
                content=msg_content,
                metadata=utils.to_json(msg_metadata),
            )
            # 生成响应格式
            msg_response = ConversationMessage(
                id=msg_id,
                role=ConversationRole.SYSTEM,
                type=ConversationMessageType.MESSAGE,
                content=msg_content,
                metadata=msg_metadata,
            )
            response = ConversationMessageResponse(
                message=msg_response,
                context=ConversationContext(project_progress=ProjectProgress(project.progress))
            )
            await queue.put(f"data: {response.model_dump_json()}\n\n")
            await queue.put("error: \n\n")
            logger.error(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project.id} 异常:{str(e)}\n异常栈:{traceback.format_exc()}")
        finally:
            await queue.put(None)

    @staticmethod
    async def _send_heartbeat(queue):
        """发送心跳包"""
        while True:
            await asyncio.sleep(3)
            await queue.put("heartbeat: \n\n")

    @staticmethod
    async def _compress_context(project_id: str):
        """上下文压缩"""
        try:
            # 获取上下文压缩锁
            lock_result = await redis_service.get_compress_context_lock(project_id)
            if lock_result:
                logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 上下文压缩取锁成功")
                # 获取会话上下文
                config = {"configurable": {"thread_id": project_id}}
                agent = await main_agent.get_agent()
                state_snapshot = await agent.aget_state(config=config)
                total_messages = state_snapshot.values.get("messages", [])
                # 生成精简后的上下文
                compressed_messages = trim_messages(
                    total_messages,
                    strategy="last",
                    start_on="human",
                    token_counter=count_tokens_approximately,
                    max_tokens=settings.model_max_context_token
                )
                # 提取需要压缩的上下文
                compressed_message_ids = {item.id for item in compressed_messages}
                summary_messages = [item for item in total_messages if item.id not in compressed_message_ids]
                # 存在压缩的上下文则生成摘要
                if summary_messages:
                    # 获取历史摘要 默认最近20条
                    history_summary = await conversation_summary_service.get_conversation_summary_to_str(project_id)
                    message_text = cutils.format_context_messages_to_str(summary_messages)
                    # 生成摘要
                    messages = [
                        SystemMessage(content=ConstSystemPrompt.CONTEXT_SUMMARY.template.format(
                            existing_summary=history_summary, new_messages=message_text)),
                        HumanMessage(content="请生成摘要")
                    ]
                    result = await default_model.ainvoke(messages)
                    # 存储摘要
                    if result and result.text:
                        summary_token = count_tokens_approximately([result])
                        await milvus_service.add_project_context(project_id, result.text)
                        await conversation_summary_repository.create(project_id, result.text, token_count=summary_token)
                        # 更新至 state
                        remove_messages = [RemoveMessage(item.id) for item in summary_messages]
                        await agent.aupdate_state(
                            config=config,
                            values={"history_summary": result.text, "messages": remove_messages}
                        )
                        logger.info(
                            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 上下文压缩完成:{utils.to_one_line(result.text)}")
                    else:
                        logger.error(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 生成摘要响应异常:{result}")
                else:
                    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 上下文未达压缩上限")
                await redis_service.unlock_compress_context_lock(project_id)
                logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 上下文压缩解锁")
            else:
                logger.warning(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 上下文压缩取锁失败")
        except Exception as e:
            await redis_service.unlock_compress_context_lock(project_id)
            logger.error(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 异常:{str(e)}\n异常栈:\n{traceback.format_exc()}")

    @staticmethod
    async def discuss_project(
            project: Project,
            user_id: str,
            message: str,
            files: list[UploadFile] = None,
            background_tasks: BackgroundTasks = None,
    ) -> StreamingResponse:
        """项目对话"""
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

        lock_result = await redis_service.get_project_occupy_lock(project.id, user_id)
        if lock_result:
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project.id} 项目占用取锁成功")
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
                    ConversationMessageService._start_agent(project, message, graph_file_list, queue))
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
                        f"trans_id:{trans_id_ctx.get()} 项目Id:{project.id} 异常:{str(e)}\n异常栈:{traceback.format_exc()}")
                finally:
                    agent_task.cancel()
                    heart_task.cancel()
                    logger.info(f"trans_id:{trans_id_ctx.get(None)} 项目Id:{project.id} 对话结束")
                    # 执行上下文压缩
                    background_tasks.add_task(ConversationMessageService._compress_context, project.id)

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            # 删除已上传的文件
            for file in graph_file_list:
                file_utils.unlink_file(file["path"])
            raise BusinessException.from_error_message(ErrorMessage.PROJECT_OCCUPIED_ERROR)


# 导出单例
conversation_message_service = ConversationMessageService()
