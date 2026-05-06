from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.services.business.project_service import project_service, ProjectUpdate
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.requirement.module import utils
from src.graphs.requirement.module.schemas import OptimizeDocOutput
from src.graphs.common.utils import utils as cutils
from src.graphs.common.schemas.output_schemas import Issue
from src.graphs.common.base.output_tools import tool, optimize_doc_output, OptimizationDocBringRiskOutputTools


class OutputTools(OptimizationDocBringRiskOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            requirement_module_content: str,
            risks: list[Issue] | None,
            unclear_points: list[Issue] | None,
            runtime: ToolRuntime,
    ) -> Command:
        """输出需求模块优化结果工具

        AI大模型使用此工具可完成需求模块的优化并输出结构化结果。

        功能说明：
        1. 对需求模块进行深度优化（补充细节、明确边界）
        2. 汇总风险点和不明确点供后续团队评审
        3. 将优化后的内容更新到 state

        Args:
            message: str - 针对需求模块优化的总结以及给团队成员接下来review的留言
            requirement_module_content: str - 优化后的需求模块内容（Markdown格式）
            risks: list[Issue] - 给客户提出的风险和建议方案
                - content: str - 风险描述
                - propose: str - 建议方案
            unclear_points: list[Issue] - 需求中不明确的问题和建议方案
                - content: str - 问题描述
                - propose: str - 建议方案
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令，包含 requirement_module_content 更新
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            message=message,
            requirement_module_content=requirement_module_content,
            risks=risks or [],
            unclear_points=unclear_points or [],
        )
        command = optimize_doc_output(output, runtime, ["requirement_module_content"], messages_key=messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        project_id = runtime.state["project_id"]
        # 更新需求模块内容
        module_name = runtime.state["metadata"]["module"]
        module_content = runtime.state["requirement_module_content"]
        utils.update_module_content_by_name(module_name, module_content, runtime.state["requirement_modules"])
        # 保存需求模块
        await project_service.update_project_and_clear_cache(
            runtime.state["project_id"],
            ProjectUpdate(requirement_module_design=gutils.to_json(runtime.state["requirement_modules"]))
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 更新需求模块入库")
        # 发送通知消息
        cutils.send_custom_message(
            f"{module_name}已更新，快来看看吧！", GroupMemberRole.PM, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.REQUIREMENT_MODULE.value,
            GroupMemberRole.PM,
            ConversationMessageType.DOC_UPDATE
        )
        # 更新 command
        command.update.update({
            "requirement_modules": runtime.state["requirement_modules"],
        })
