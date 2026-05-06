from loguru import logger
from langgraph.runtime import Runtime
from langchain.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from src.graphs.common.base.state import AnyOptimizationDocState
from src.utils import prompt_utils
from src.context import trans_id_ctx
from src.graphs.common.llms import default_model
from src.graphs.test.case.state import TaskState
from src.graphs.common.base.nodes import OptimizationDocNodes
from src.graphs.common.utils import message_utils, utils as cutils, structured_output_utils


class Nodes(OptimizationDocNodes):

    async def initialize_node(
            self,
            state: AnyOptimizationDocState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> AnyOptimizationDocState:
        project_id = state["project_id"]
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 完成")
        return {"test_cases": state.get("optimized_test_cases", [])}

    async def optimize_doc_by_task_node(
            self,
            state: TaskState,
            runtime: Runtime,
            config: RunnableConfig
    ) -> TaskState:
        """根据任务优化文档节点

        调用 LLM 根据任务优化当前文档内容，
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
        role = cutils.get_role_optimization_by_project_progress(project_progress)
        last_node_role = role
        output_tool = self.output_tools.optimize_doc_by_task_output
        task_name = state["task"]["title"]
        # 发送自定义消息
        cutils.send_custom_message(f"优化{task_name}中...", role)
        messages = [
            SystemMessage(content=prompt_utils.get_optimize_doc_by_task_prompt(project_progress)),
            # 截取至上一个节点角色的最后一条 AIMessage 并转为 HumanMessage 防止看到历史消息产生误解
            *message_utils.truncate_messages_by_latest_role_message_and_to_human_message(
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
