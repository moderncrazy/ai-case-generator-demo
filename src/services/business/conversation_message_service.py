import traceback
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from langchain_core.messages.utils import trim_messages, count_tokens_approximately

from src.utils import utils
from src.config import settings
from src.context import trans_id_ctx
from src.agents.main_agent import main_agent
from src.graphs.common.llms import default_model
from src.graphs.common.utils import format_utils
from src.enums.const_system_prompt import ConstSystemPrompt
from src.services.business.redis_service import redis_service
from src.services.business.milvus_service import milvus_service
from src.services.business.conversation_summary_service import conversation_summary_service
from src.repositories.writes_repository import writes_repository
from src.repositories.checkpoints_repository import checkpoints_repository
from src.repositories.conversation_message_repository import conversation_message_repository
from src.repositories.conversation_summary_repository import conversation_summary_repository


class ConversationMessageService:
    """对话消息服务
    
    提供对话消息相关的业务逻辑处理，
    包括获取对话历史、构建对话上下文、项目对话流式响应等功能。
    """

    def __init__(self):
        self.repository = conversation_message_repository

    async def compress_context(self, project_id: str):
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
                    message_text = format_utils.format_context_messages_to_str(summary_messages)
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
                # 删除历史 checkpoint
                checkpoint_count = 0
                async for snapshot in agent.aget_state_history(config=config):
                    # 若 checkpoint_id 非当前 state checkpoint_id 则删除
                    checkpoint_id = snapshot.config["configurable"]["checkpoint_id"]
                    if checkpoint_id != state_snapshot.config["configurable"]["checkpoint_id"]:
                        checkpoint_count += 1
                        await writes_repository.delete_by_checkpoint_id(checkpoint_id)
                        await checkpoints_repository.delete_by_checkpoint_id(checkpoint_id)
                logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 删除:{checkpoint_count}条checkpoint")
                await redis_service.unlock_compress_context_lock(project_id)
                logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 上下文压缩解锁")
            else:
                logger.warning(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 上下文压缩取锁失败")
        except Exception as e:
            await redis_service.unlock_compress_context_lock(project_id)
            logger.error(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 异常:{str(e)}\n异常栈:\n{traceback.format_exc()}")


conversation_message_service = ConversationMessageService()
