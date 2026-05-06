from loguru import logger
from langchain.messages import AnyMessage, AIMessage, HumanMessage, ToolMessage

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.group_member_role import GroupMemberRole


def get_latest_role_message(role: GroupMemberRole, messages: list[AnyMessage]) -> AIMessage | None:
    """获取最新一条 name 为指定 role 的 AIMessage"""
    if messages:
        gen = (index for index, item in reversed(list(enumerate(messages)))
               if isinstance(item, AIMessage) and item.name == role.value)
        try:
            return messages[next(gen)]
        except StopIteration:
            return None
    return None


def truncate_messages_by_latest_role_message_and_to_human_message(
        role: GroupMemberRole, messages: list[AnyMessage], sys_hint: str = None) -> list[AnyMessage]:
    """从最新的消息截取至最新一条 name 为指定 role 的 AIMessage 并转为 HumanMessage"""
    if messages:
        temp_msgs = messages.copy()
        gen = (index for index, item in reversed(list(enumerate(messages)))
               if isinstance(item, AIMessage) and item.name == role.value)
        try:
            index = next(gen)
            content = temp_msgs[index].content
            if sys_hint:
                content = f"{content}\n\n（【系统提示】：{sys_hint}）"
            temp_msgs[index] = HumanMessage(content=content)
            temp_msgs = temp_msgs[index:]
            logger.info(
                f"trans_id:{trans_id_ctx.get()} 角色:{role} 截取后消息量:{len(temp_msgs)} 截取后消息内容:{gutils.to_one_line(content)}")
            return temp_msgs
        except StopIteration:
            return messages
    return messages


def latest_role_message_to_human_message(
        role: GroupMemberRole, messages: list[AnyMessage], sys_hint: str = None) -> list[AnyMessage]:
    """将最新一条 name 为指定 role 的 AIMessage 转为 HumanMessage 并可增加系统提示"""
    if messages:
        temp_msgs = messages.copy()
        gen = (index for index, item in reversed(list(enumerate(messages)))
               if isinstance(item, AIMessage) and item.name == role.value)
        try:
            index = next(gen)
            content = temp_msgs[index].content
            if sys_hint:
                content = f"{content}\n\n（系统提示：{sys_hint}）"
            temp_msgs[index] = HumanMessage(content=content)
            logger.info(f"trans_id:{trans_id_ctx.get()} 角色:{role} 转换人类消息内容:{gutils.to_one_line(content)}")
            return temp_msgs
        except StopIteration:
            return messages
    return messages


def remove_tool_messages(messages: list[AnyMessage]) -> list[AnyMessage]:
    """将历史消息中的 工具调用、工具输出 都删掉，防止上下文超限"""
    results = messages.copy()
    for message in messages:
        if isinstance(message, ToolMessage) or (isinstance(message, AIMessage) and message.tool_calls):
            results.remove(message)
    return results
