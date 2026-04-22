import uuid
from typing import Any
from loguru import logger
from langchain.messages import AnyMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.reducer_action_type import ReducerActionType


def rewrite_reducer(current: Any, update: Any):
    """重写 reducer
    
    直接用新值覆盖旧值，用于需要完全替换的场景。
    
    Args:
        current: 当前值
        update: 更新值
        
    Returns:
        更新值
    """
    return update


def distinct_reducer(current: list, update: list | ReducerActionType):
    """支持清空和去重的 reducer
    
    新增项若不存在于列表中则追加，支持通过 RESET 清空列表。
    
    Args:
        current: 当前列表
        update: 更新列表或重置指令
        
    Returns:
        合并后的列表
    """
    item_type = type(current[0]).__name__ if current else (type(update[0]).__name__ if update else None)
    match update:
        case ReducerActionType.RESET:
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 元素类型:{item_type} 总记录:{len(current)} 清空记录")
            return []
        case _:
            for new_msg in update:
                if new_msg not in current:
                    current.append(new_msg)
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 元素类型:{item_type} 总记录:{len(current)} 新记录:{len(update)}")
            return current


def priority_message_reducer(current: list[AnyMessage], update: list[AnyMessage] | ReducerActionType):
    """带优先级的消息合并 reducer
    
    当消息ID相同时，比较优先级（additional_kwargs["priority"]），
    优先级高的覆盖低的；若优先级相同或更低则丢弃新消息。
    支持通过 RESET 清空消息列表。
    
    Args:
        current: 当前消息列表
        update: 新消息列表或重置指令
        
    Returns:
        合并后的消息列表
    """
    match update:
        case ReducerActionType.RESET:
            logger.info(f"trans_id:{trans_id_ctx.get()} 总消息:{len(current)} 清空消息")
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
                f"trans_id:{trans_id_ctx.get()} 总消息:{len(current)} 新消息:{len(update)}")
            return current
