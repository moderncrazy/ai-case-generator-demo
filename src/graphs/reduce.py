import uuid
from loguru import logger
from langchain.messages import AnyMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.reducer_action_type import ReducerActionType


def list_reducer(current: list, update: list | ReducerActionType):
    """支持清空的 reducer"""
    match update:
        case ReducerActionType.RESET:
            logger.info(f"trans_id:{trans_id_ctx.get()} 合并:{gutils.get_func_name()} 总记录:{len(current)} 清空记录")
            return []
        case _:
            current.extend(update)
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 合并:{gutils.get_func_name()} 总记录:{len(current)} 新记录:{len(update)}")
            return current


def priority_message_reducer(current: list[AnyMessage], update: list[AnyMessage] | ReducerActionType):
    """在 id 相同的情况下选择 additional_kwargs["priority"] 更高的覆盖原先的，小于等于则丢弃"""
    match update:
        case ReducerActionType.RESET:
            logger.info(f"trans_id:{trans_id_ctx.get()} 合并:{gutils.get_func_name()} 总消息:{len(current)} 清空消息")
            return []
        case _:
            # 将老消息转为 map
            current_index = {m.id: {
                "index": i,
                "priority": m.additional_kwargs.get("priority", float("-inf"))
            } for i, m in enumerate(current)}
            # 遍历新消息 对比优先级
            for new_msg in update:
                if not new_msg.id:
                    new_msg.id = str(uuid.uuid4())
                if new_msg.id in current_index:
                    new_msg_priority = new_msg.additional_kwargs.get("priority", float("-inf"))
                    if new_msg_priority > current_index[new_msg.id]["priority"]:
                        current[current_index[new_msg.id]["index"]] = new_msg
                else:
                    current.append(new_msg)
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 合并:{gutils.get_func_name()} 总消息:{len(current)} 新消息:{len(update)}")
            return current
