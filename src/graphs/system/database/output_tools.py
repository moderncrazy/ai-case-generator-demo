from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.services.business.project_service import project_service, ProjectUpdate
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.system.database.schemas import OptimizeDocOutput
from src.graphs.common.utils import utils as cutils
from src.graphs.common.base.output_tools import tool, optimize_doc_output, OptimizationDocOutputTools


class OutputTools(OptimizationDocOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            system_database_content: str,
            runtime: ToolRuntime,
    ) -> Command:
        """输出 DBA 优化系统数据库文档结果

        AI大模型使用此工具可完成系统数据库文档的优化分析并输出结构化结果。

        **功能说明：**
        这是系统数据库设计阶段的核心输出工具，用于：
        1. 对系统数据库文档进行优化（补充字段注释、优化表结构等）
        2. 更新状态中的数据库文档内容
        3. 清空之前的问题记录，为评审做准备

        Args:
            message: str - 针对系统数据库文档优化的总结以及给团队成员接下来review的留言
            system_database_content: str - 输出优化后系统数据库文档内容（Markdown格式，通常包含SQL语句）
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            message=message,
            system_database_content=system_database_content,
        )
        command = optimize_doc_output(output, runtime, ["system_database_content"], messages_key=messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        project_id = runtime.state["project_id"]
        # 如果原始数据库内容为空 则保存当前版本为原始数据库
        if not runtime.state.get("original_database"):
            await project_service.update_project_and_clear_cache(
                project_id,
                ProjectUpdate(database_design=runtime.state["system_database_content"])
            )
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始数据库文档入库")
        cutils.send_custom_message(
            "数据库文档已更新，快来看看吧！", GroupMemberRole.DBA, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.SYSTEM_DATABASE.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 更新 command
        command.update.update({
            "original_database": runtime.state.get("original_database") or runtime.state["system_database_content"],
            "optimized_database": runtime.state["system_database_content"],
        })
