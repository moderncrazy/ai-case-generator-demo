import traceback
from loguru import logger
from typing import TypeVar
from langchain.tools import BaseTool
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig
from langchain.messages import AnyMessage, SystemMessage, AIMessage, HumanMessage

from src.context import trans_id_ctx
from src.utils import prompt_utils, utils as gutils
from src.graphs.state import State
from src.graphs.common.llms import default_model
from src.graphs.common.utils import structured_output_utils, utils as cutils
from src.enums.group_member_role import GroupMemberRole

AnyState = TypeVar("AnyState", bound=State)


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
                content = f"{content}\n\n（系统提示：{sys_hint}）"
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


async def generate_optimization_plan(state: AnyState, runtime: Runtime, config: RunnableConfig,
                                     tool_list: list[BaseTool], role: GroupMemberRole, output_tool: BaseTool,
                                     last_node_role: GroupMemberRole = GroupMemberRole.PM,
                                     message_key="private_messages") -> AnyState:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message(f"生成{project_progress.get_name_zh()}方案中...", role)
    messages = [
        SystemMessage(content=prompt_utils.get_generate_optimization_plan_prompt(project_progress)),
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(
            last_node_role, state[message_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
    ]
    # 添加角色
    metadata = {"role": role}
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*tool_list, output_tool], tool_choice="any", strict=True)
    result = await structured_output_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                                      output_tool, messages_key=message_key,
                                                                      metadata=metadata)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_optimization_plan(state: AnyState, runtime: Runtime, config: RunnableConfig, tool_list,
                                   role: GroupMemberRole, output_tool, last_node_role: GroupMemberRole,
                                   message_key="private_messages") -> AnyState:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message(f"审核{project_progress.get_name_zh()}方案中...", role)
    messages = [
        SystemMessage(content=prompt_utils.get_review_optimization_plan_prompt(project_progress)),
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(
            last_node_role, state[message_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
    ]
    # 添加角色
    metadata = {"role": role}
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*tool_list, output_tool], tool_choice="any", strict=True)
    result = await structured_output_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                                      output_tool, messages_key=message_key,
                                                                      metadata=metadata)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def optimize_doc(state: AnyState, runtime: Runtime, config: RunnableConfig, tool_list, role: GroupMemberRole,
                       output_tool, last_node_role: GroupMemberRole, message_key="private_messages") -> AnyState:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    messages = [
        SystemMessage(content=prompt_utils.get_optimization_doc_prompt(project_progress)),
        # 截取至上一个节点角色的最后一条 AIMessage 并转为 HumanMessage 防止看到历史消息产生误解
        *truncate_messages_by_latest_role_message_and_to_human_message(
            last_node_role, state[message_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
        # *latest_role_message_to_human_message(last_node_role, state[message_key])
    ]
    # 添加角色
    metadata = {"role": role}
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*tool_list, output_tool], tool_choice="any", strict=True)
    result = await structured_output_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                                      output_tool, messages_key=message_key,
                                                                      metadata=metadata)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def review_optimization_doc(state: AnyState, runtime: Runtime, config: RunnableConfig, tool_list, output_tool,
                                  last_node_role: GroupMemberRole, message_key="private_messages") -> AnyState:
    role = state["role"]
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 进入")
    messages = [
        SystemMessage(content=prompt_utils.get_review_optimization_doc_prompt(project_progress, role)),
        # 截取至上一个节点角色的最后一条 AIMessage 并转为 HumanMessage 防止看到历史消息产生误解
        *truncate_messages_by_latest_role_message_and_to_human_message(
            last_node_role, state[message_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
        # *latest_role_message_to_human_message(last_node_role, state[message_key])
    ]
    # 添加角色
    metadata = {"role": role}
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*tool_list, output_tool], tool_choice="any", strict=True)
    try:
        result = await structured_output_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config,
                                                                          messages, output_tool,
                                                                          messages_key=message_key, metadata=metadata)
    except Exception as e:
        # 如果异常则跳过这个review 避免影响整个流程
        result = state
        logger.error(
            f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 异常:{str(e)}\n异常栈:{traceback.format_exc()}")
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result


async def summarize_optimization_doc_issue(state: AnyState, runtime: Runtime, config: RunnableConfig, tool_list,
                                           role: GroupMemberRole, output_tool,
                                           last_node_role: GroupMemberRole = GroupMemberRole.GROUP_MEMBER,
                                           message_key="private_messages") -> AnyState:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    messages = [
        SystemMessage(content=prompt_utils.get_summarize_optimization_doc_issue_prompt(project_progress)),
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(
            last_node_role, state[message_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
    ]
    # 添加角色
    metadata = {"role": role}
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([*tool_list, output_tool], tool_choice="any", strict=True)
    result = await structured_output_utils.llm_tool_structured_output(llm_with_tool, state, runtime, config, messages,
                                                                      output_tool, messages_key=message_key,
                                                                      metadata=metadata)
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
    return result
