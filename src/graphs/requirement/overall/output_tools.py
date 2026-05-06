from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.services.business.project_service import project_service, ProjectUpdate
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.requirement.overall.schemas import OptimizeDocOutput
from src.graphs.common.utils import utils as cutils
from src.graphs.common.schemas.output_schemas import Issue
from src.graphs.common.base.output_tools import tool, optimize_doc_output, OptimizationDocBringRiskOutputTools


class OutputTools(OptimizationDocBringRiskOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            requirement_overall_content: str,
            risks: list[Issue] | None,
            unclear_points: list[Issue] | None,
            runtime: ToolRuntime,
    ) -> Command:
        """输出产品优化需求文档结果

        AI大模型使用此工具可完成整体需求文档的优化分析并输出结构化结果。

        **功能说明：**
        这是需求整体设计阶段的核心输出工具，用于：
        1. 对需求文档进行优化（补充细节、明确边界、修正逻辑）
        2. 汇总风险点和不明确点供后续团队评审
        3. 更新状态中的文档内容
        4. 清空之前的问题记录，为评审做准备

        Args:
            message: str - 针对需求文档优化的总结以及给团队成员接下来review的留言
            requirement_overall_content: str - 输出优化后需求文档内容（Markdown格式）
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
            requirement_overall_content=requirement_overall_content,
            risks=risks or [],
            unclear_points=unclear_points or [],
        )
        command = optimize_doc_output(output, runtime, ["requirement_overall_content"], messages_key=messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        project_id = runtime.state["project_id"]
        if not runtime.state.get("original_requirement"):
            await project_service.update_project_and_clear_cache(
                project_id,
                ProjectUpdate(requirement_overall_design=runtime.state["requirement_overall_content"])
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始需求入库")
        cutils.send_custom_message(
            "需求文档已更新，快来看看吧！", GroupMemberRole.PRODUCT, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.REQUIREMENT_OVERALL.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 更新 command
        command.update.update({
            "original_requirement": runtime.state.get("original_requirement")
                                    or runtime.state["requirement_overall_content"],
            "optimized_requirement": runtime.state["requirement_overall_content"],
        })
