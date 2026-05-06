import traceback

from loguru import logger
from typing import TypeVar
from langchain.tools import BaseTool
from langgraph.runtime import Runtime
from langgraph.config import RunnableConfig
from langchain_core.messages import SystemMessage

from src.utils import prompt_utils
from src.context import trans_id_ctx
from src.enums.project_progress import ProjectProgress
from src.enums.group_member_role import GroupMemberRole
from src.graphs.common.llms import default_model
from src.graphs.common.base.tools import with_common_tools
from src.graphs.common.base.output_tools import AnyOptimizationDocOutputTools
from src.graphs.common.base.state import AnyOptimizationDocState, AnyGroupMemberReviewOptimizationDocState
from src.graphs.common.utils import utils, structured_output_utils
from src.graphs.common.utils.message_utils import (
    latest_role_message_to_human_message,
    truncate_messages_by_latest_role_message_and_to_human_message
)


class OptimizationDocNodes:

    def __init__(
            self,
            output_tools: AnyOptimizationDocOutputTools,
            common_tools: list[BaseTool] = with_common_tools,
            messages_key: str = "private_messages",
    ):
        self.messages_key = messages_key
        self.output_tools = output_tools
        self.common_tools = common_tools

    # noinspection PyMethodMayBeStatic
    def get_stage_name(self, state: AnyOptimizationDocState) -> str:
        # 若当前是需求模块阶段 则返回具体模块名 否则返回阶段名
        if state["project_progress"] == ProjectProgress.REQUIREMENT_MODULE_DESIGN:
            return state["metadata"]["module"]
        return state["project_progress"].name_zh

    async def generate_optimization_plan_node(
            self,
            state: AnyOptimizationDocState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> AnyOptimizationDocState:
        """生成优化方案节点

        调用 LLM 根据上下文生成优化方案
        支持通过工具查询项目历史文档等信息

        Args:
            state: LangGraph 状态
            runtime: LangGraph 运行时
            config: LangGraph 运行时配置

        Returns:
            更新后的状态（包含生成的文档优化方案）
        """
        project_id = state["project_id"]
        project_progress = state["project_progress"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
        role = utils.get_role_optimization_by_project_progress(project_progress)
        last_node_role = GroupMemberRole.PM
        output_tool = self.output_tools.generate_optimization_plan_output
        stage_name = self.get_stage_name(state)
        # 发送自定义消息
        utils.send_custom_message(f"生成{stage_name}方案中...", role)
        messages = [
            SystemMessage(content=prompt_utils.get_generate_optimization_plan_prompt(project_progress)),
            # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
            *latest_role_message_to_human_message(
                last_node_role, state[self.messages_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
        ]
        # 添加角色
        metadata = {"role": role}
        # 绑定查询方法和结构化输出方法
        bind_tool_list = [*self.common_tools, output_tool]
        llm_with_tool = default_model.bind_tools(bind_tool_list, tool_choice="any", strict=True)
        result = await structured_output_utils.llm_tool_structured_output(
            llm_with_tool, state, runtime, config, messages, bind_tool_list, output_tool,
            messages_key=self.messages_key, metadata=metadata
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
        return result

    async def review_optimization_plan_node(
            self,
            state: AnyOptimizationDocState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> AnyOptimizationDocState:
        """审核优化方案节点

        调用 LLM 根据上下文审核优化方案
        支持通过工具查询项目历史文档等信息

        Args:
            state: LangGraph 状态
            runtime: LangGraph 运行时
            config: LangGraph 运行时配置

        Returns:
            更新后的状态（包含审核结果）
        """
        project_id = state["project_id"]
        project_progress = state["project_progress"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
        role = GroupMemberRole.PM
        last_node_role = utils.get_role_optimization_by_project_progress(project_progress)
        output_tool = self.output_tools.review_optimization_plan_output
        stage_name = self.get_stage_name(state)
        # 发送自定义消息
        utils.send_custom_message(f"审核{stage_name}方案中...", role)
        messages = [
            SystemMessage(content=prompt_utils.get_review_optimization_plan_prompt(project_progress)),
            # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
            *latest_role_message_to_human_message(
                last_node_role, state[self.messages_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
        ]
        # 添加角色
        metadata = {"role": role}
        # 绑定查询方法和结构化输出方法
        bind_tool_list = [*self.common_tools, output_tool]
        llm_with_tool = default_model.bind_tools(bind_tool_list, tool_choice="any", strict=True)
        result = await structured_output_utils.llm_tool_structured_output(
            llm_with_tool, state, runtime, config, messages, bind_tool_list, output_tool,
            messages_key=self.messages_key, metadata=metadata
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
        return result

    async def optimize_doc_node(
            self,
            state: AnyOptimizationDocState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> AnyOptimizationDocState:
        """优化文档节点

        调用 LLM 根据上下文优化当前文档内容，
        支持通过工具查询项目历史文档等信息。

        Args:
            state: LangGraph 状态
            runtime: LangGraph 运行时
            config: LangGraph 运行时配置

        Returns:
            更新后的状态（包含优化后的模块内容）
        """
        project_id = state["project_id"]
        project_progress = state["project_progress"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
        role = utils.get_role_optimization_by_project_progress(project_progress)
        last_node_role = GroupMemberRole.PM
        output_tool = self.output_tools.optimize_doc_output
        stage_name = self.get_stage_name(state)
        # 发送自定义消息
        utils.send_custom_message(f"优化{stage_name}中...", role)
        messages = [
            SystemMessage(content=prompt_utils.get_optimization_doc_prompt(project_progress)),
            # 截取至上一个节点角色的最后一条 AIMessage 并转为 HumanMessage 防止看到历史消息产生误解
            *truncate_messages_by_latest_role_message_and_to_human_message(
                last_node_role, state[self.messages_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
            # *latest_role_message_to_human_message(last_node_role, state[messages_key])
        ]
        # 添加角色
        metadata = {"role": role}
        # 绑定查询方法和结构化输出方法
        bind_tool_list = [*self.common_tools, output_tool]
        llm_with_tool = default_model.bind_tools(bind_tool_list, tool_choice="any", strict=True)
        result = await structured_output_utils.llm_tool_structured_output(
            llm_with_tool, state, runtime, config, messages, bind_tool_list, output_tool,
            messages_key=self.messages_key, metadata=metadata
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
        return result

    async def pm_review_optimization_doc_node(
            self,
            state: AnyOptimizationDocState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> AnyOptimizationDocState:
        """PM评审优化文档节点"""
        project_id = state["project_id"]
        project_progress = state["project_progress"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
        role = GroupMemberRole.PM
        last_node_role = utils.get_role_optimization_by_project_progress(project_progress)
        output_tool = self.output_tools.pm_review_optimization_doc_output
        stage_name = self.get_stage_name(state)
        # 发送自定义消息
        utils.send_custom_message(f"PM评审{stage_name}中...", role)
        messages = [
            SystemMessage(content=prompt_utils.get_pm_review_optimization_doc_prompt(project_progress)),
            # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
            *latest_role_message_to_human_message(
                last_node_role, state[self.messages_key],
                f"1. 必须使用 {output_tool.name} 方法输出，不要输出纯文本\n2. 若不进行 group_member_review 给出理由\n3. 根据【问题提出规则】禁止提出非本阶段的设计要求")
        ]
        # 添加角色
        metadata = {"role": role}
        # 绑定查询方法和结构化输出方法
        bind_tool_list = [*self.common_tools, output_tool]
        llm_with_tool = default_model.bind_tools(bind_tool_list, tool_choice="any", strict=True)
        result = await structured_output_utils.llm_tool_structured_output(
            llm_with_tool, state, runtime, config, messages, bind_tool_list, output_tool,
            messages_key=self.messages_key, metadata=metadata
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
        return result

    async def group_member_review_optimization_doc_node(
            self,
            state: AnyGroupMemberReviewOptimizationDocState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> AnyGroupMemberReviewOptimizationDocState:
        """组员评审优化文档节点"""
        role = state["role"]
        project_id = state["project_id"]
        project_progress = state["project_progress"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 进入")
        last_node_role = GroupMemberRole.PM
        output_tool = self.output_tools.group_member_review_optimization_doc_output
        stage_name = self.get_stage_name(state)
        # 发送自定义消息
        utils.send_custom_message(f"{role.name_zh}评审{stage_name}中...", role)
        messages = [
            SystemMessage(content=prompt_utils.get_group_member_review_optimization_doc_prompt(project_progress, role)),
            # 截取至上一个节点角色的最后一条 AIMessage 并转为 HumanMessage 防止看到历史消息产生误解
            *truncate_messages_by_latest_role_message_and_to_human_message(
                last_node_role, state[self.messages_key], f"1. 必须使用 {output_tool.name} 方法输出，不要输出纯文本\n2. 根据【问题提出规则】禁止提出非本阶段的设计要求")
            # *latest_role_message_to_human_message(last_node_role, state[messages_key])
        ]
        # 添加角色
        metadata = {"role": role}
        # 绑定查询方法和结构化输出方法
        bind_tool_list = [*self.common_tools, output_tool]
        llm_with_tool = default_model.bind_tools(bind_tool_list, tool_choice="any", strict=True)
        try:
            result = await structured_output_utils.llm_tool_structured_output(
                llm_with_tool, state, runtime, config, messages, bind_tool_list, output_tool,
                messages_key=self.messages_key, metadata=metadata
            )
        except Exception as e:
            # 如果异常则跳过这个review 避免影响整个流程
            result = state
            logger.error(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 角色:{role} 异常:{str(e)}\n异常栈:{traceback.format_exc()}")
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
        return result

    async def filtrate_optimization_doc_review_issue_node(
            self,
            state: AnyOptimizationDocState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> AnyOptimizationDocState:
        """整理文档问题节点

        收集汇总各角色评审意见，整理出风险点和不明确点，
        最终将优化后的文档内容保存到数据库。

        Args:
            state: LangGraph 状态
            runtime: LangGraph 运行时
            config: LangGraph 运行时配置

        Returns:
            更新后的状态（包含最终风险点和不明确点）
        """
        project_id = state["project_id"]
        project_progress = state["project_progress"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 进入")
        role = GroupMemberRole.PM
        last_node_role = GroupMemberRole.GROUP_MEMBER
        output_tool = self.output_tools.filtrate_optimization_doc_review_issue_output
        stage_name = self.get_stage_name(state)
        # 发送自定义消息
        utils.send_custom_message(f"PM整理{stage_name}评审意见中...", role)
        messages = [
            SystemMessage(content=prompt_utils.get_filtrate_optimization_doc_review_issue_prompt(project_progress)),
            # 将上一个节点角色的最后一条 AIMessage 转为 HumanMessage
            *latest_role_message_to_human_message(
                last_node_role, state[self.messages_key], f"必须使用 {output_tool.name} 方法输出，不要输出纯文本")
        ]
        # 添加角色
        metadata = {"role": role}
        # 绑定查询方法和结构化输出方法
        bind_tool_list = [*self.common_tools, output_tool]
        llm_with_tool = default_model.bind_tools(bind_tool_list, tool_choice="any", strict=True)
        result = await structured_output_utils.llm_tool_structured_output(
            llm_with_tool, state, runtime, config, messages, bind_tool_list, output_tool,
            messages_key=self.messages_key, metadata=metadata
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
        return result


AnyOptimizationDocNodes = TypeVar("AnyOptimizationDocNodes", bound=OptimizationDocNodes)
