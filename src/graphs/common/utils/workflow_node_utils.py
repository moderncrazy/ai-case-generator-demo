import traceback
from loguru import logger
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig
from langchain.messages import AnyMessage, SystemMessage, AIMessage, HumanMessage

from src.utils import prompt_utils
from src.context import trans_id_ctx
from src.graphs.state import State
from src.graphs.common.llms import default_model
from src.graphs.common.utils import structured_output_utils, utils as cutils
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


def latest_role_message_to_human_message(role: GroupMemberRole, messages: list[AnyMessage]) -> list[AnyMessage]:
    """将最新一条 name 为指定 role 的 AIMessage 转为 HumanMessage"""
    if messages:
        temp_msgs = messages.copy()
        gen = (index for index, item in reversed(list(enumerate(messages)))
               if isinstance(item, AIMessage) and item.name == role.value)
        try:
            index = next(gen)
            temp_msgs[index] = HumanMessage(content=temp_msgs[index].content)
            return temp_msgs
        except StopIteration:
            return messages
    return messages


async def generate_optimization_plan(state: State, runtime: Runtime, config: RunnableConfig, tool_list,
                                     role: GroupMemberRole, output_tool,
                                     last_node_role: GroupMemberRole = GroupMemberRole.PM,
                                     message_key="private_messages") -> State:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message(f"生成{project_progress.get_name_zh()}方案中...", role)
    messages = [
        SystemMessage(content=prompt_utils.get_generate_optimization_plan_prompt(project_progress)),
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(last_node_role, state[message_key])
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


async def review_optimization_plan(state: State, runtime: Runtime, config: RunnableConfig, tool_list,
                                   role: GroupMemberRole, output_tool, last_node_role: GroupMemberRole,
                                   message_key="private_messages") -> State:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    # 发送自定义消息
    cutils.send_custom_message(f"审核{project_progress.get_name_zh()}方案中...", role)
    messages = [
        SystemMessage(content=prompt_utils.get_review_optimization_plan_prompt(project_progress)),
        *state["messages"],
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(last_node_role, state[message_key])
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


async def optimize_doc(state: State, runtime: Runtime, config: RunnableConfig, tool_list, role: GroupMemberRole,
                       output_tool, last_node_role: GroupMemberRole = GroupMemberRole.PM,
                       message_key="private_messages") -> State:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    messages = [
        SystemMessage(content=prompt_utils.get_optimization_doc_prompt(project_progress)),
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(last_node_role, state[message_key])
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


async def review_optimization_doc(state: State, runtime: Runtime, config: RunnableConfig, tool_list, output_tool,
                                  last_node_role: GroupMemberRole, message_key="private_messages") -> State:
    role = state["role"]
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    messages = [
        SystemMessage(content=prompt_utils.get_review_optimization_doc_prompt(project_progress, role)),
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(last_node_role, state[message_key])
    ]
    # 添加角色
    metadata = {"role": role}
    # 绑定查询方法和结构化输出方法
    llm_with_tool = default_model.bind_tools([tool_list, output_tool], tool_choice="any", strict=True)
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


async def summarize_optimization_doc_issue(state: State, runtime: Runtime, config: RunnableConfig, tool_list,
                                           role: GroupMemberRole, output_tool,
                                           last_node_role: GroupMemberRole = GroupMemberRole.GROUP_MEMBER,
                                           message_key="private_messages") -> State:
    project_id = state["project_id"]
    project_progress = state["project_progress"]
    logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
    messages = [
        SystemMessage(content=prompt_utils.get_summarize_optimization_doc_issue_prompt(project_progress)),
        # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
        *latest_role_message_to_human_message(last_node_role, state[message_key])
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
