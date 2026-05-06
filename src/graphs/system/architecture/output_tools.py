from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.services.business.project_service import project_service, ProjectUpdate
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.system.architecture.schemas import OptimizeDocOutput
from src.graphs.common.utils import utils as cutils
from src.graphs.common.schemas.output_schemas import Issue
from src.graphs.common.base.output_tools import tool, optimize_doc_output, OptimizationDocBringRiskOutputTools


class OutputTools(OptimizationDocBringRiskOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            system_architecture_content: str,
            risks: list[Issue] | None,
            unclear_points: list[Issue] | None,
            runtime: ToolRuntime,
    ) -> Command:
        """输出架构优化系统架构结果

        AI大模型使用此工具可完成系统架构的优化分析并输出结构化结果。

        **功能说明：**
        这是系统架构设计阶段的核心输出工具，用于：
        1. 对系统架构进行优化（补充设计细节、调整技术选型等）
        2. 汇总风险点和不明确点供后续团队评审
        3. 更新状态中的架构内容
        4. 清空之前的问题记录，为评审做准备

        Args:
            message: str - 针对系统架构优化的总结以及给团队成员接下来review的留言
            system_architecture_content: str - 输出优化后系统架构内容（Markdown格式）
            risks: list[Issue] - 给客户提出的风险和建议方案列表，包含以下字段：
                - content: str - 问题描述
                - propose: str - 建议方案
            unclear_points: list[Issue] - 需求中不明确的问题和建议方案列表，结构同上
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            message=message,
            system_architecture_content=system_architecture_content,
            risks=risks or [],
            unclear_points=unclear_points or [],
        )
        command = optimize_doc_output(output, runtime, ["system_architecture_content"], messages_key=messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        project_id = runtime.state["project_id"]
        # 如果原始架构内容为空 则保存当前版本为原始架构
        if not runtime.state.get("original_architecture"):
            await project_service.update_project_and_clear_cache(
                project_id,
                ProjectUpdate(architecture_design=runtime.state["system_architecture_content"])
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始架构入库")
        cutils.send_custom_message(
            "架构文档已更新，快来看看吧！", GroupMemberRole.ARCHITECT, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.SYSTEM_ARCHITECTURE.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 更新 command
        command.update.update({
            "original_architecture": runtime.state.get("original_architecture")
                                     or runtime.state["system_architecture_content"],
            "optimized_architecture": runtime.state["system_architecture_content"],
        })
