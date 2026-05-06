from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.services.business.module_service import module_service
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.system.module import utils
from src.graphs.system.module.schemas import OptimizeDocOutput, SystemModule
from src.graphs.common.utils import utils as cutils
from src.graphs.common.base.output_tools import tool, optimize_doc_output, OptimizationDocOutputTools


class OutputTools(OptimizationDocOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            system_modules: list[SystemModule],
            runtime: ToolRuntime,
    ) -> Command:
        """输出架构优化系统模块结果

        AI大模型使用此工具可完成系统模块的优化分析并输出结构化结果。

        **功能说明：**
        这是系统模块设计阶段的核心输出工具，用于：
        1. 对系统模块进行优化（调整层级、补充描述、合并拆分等）
        2. 验证模块列表合法性（检查模块名称重复、循环引用等）
        3. 更新状态中的模块列表
        4. 清空之前的问题记录，为评审做准备

        Args:
            message: str - 针对系统模块优化的总结以及给团队成员接下来review的留言
            system_modules: list[SystemModule] - 输出优化后系统模块列表，包含以下字段：
                - id: str - 模块ID（必填，UUID）
                - name: str - 模块名称（必填）
                - parent_id: str | None - 父模块ID（顶级模块为None）
                - description: str - 模块描述（必填）
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            message=message,
            system_modules=system_modules,
        )
        error_message = utils.validate_modules_to_str(system_modules)
        command = optimize_doc_output(
            output, runtime, ["system_modules"], error_message=error_message, messages_key=messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        project_id = runtime.state["project_id"]
        # 如果原始模块内容为空 则保存当前版本为原始模块
        if not runtime.state.get("original_modules"):
            await module_service.bulk_update_by_state_modules(project_id, runtime.state["system_modules"])
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始模块入库")
        cutils.send_custom_message(
            "系统模块已更新，快来看看吧！", GroupMemberRole.ARCHITECT, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.SYSTEM_MODULE.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 更新 command
        command.update.update({
            "original_modules": runtime.state.get("original_modules") or runtime.state["system_modules"],
            "optimized_modules": runtime.state["system_modules"],
        })
