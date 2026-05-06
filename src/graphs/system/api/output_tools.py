from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.services.business.api_service import api_service
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.system.api import utils
from src.graphs.system.api.schemas import OptimizeDocOutput, SystemApi
from src.graphs.common.utils import utils as cutils
from src.graphs.common.base.output_tools import tool, optimize_doc_output, OptimizationDocOutputTools


class OutputTools(OptimizationDocOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            system_apis: list[SystemApi],
            runtime: ToolRuntime,
    ) -> Command:
        """输出后端优化系统接口结果

        AI大模型使用此工具可完成系统接口的优化分析并输出结构化结果。

        **功能说明：**
        这是系统接口设计阶段的核心输出工具，用于：
        1. 对系统接口进行优化（补充参数说明、完善响应结构等）
        2. 验证接口列表合法性（检查 module_id 是否存在于系统模块中）
        3. 更新状态中的接口列表
        4. 清空之前的问题记录，为评审做准备

        Args:
            message: str - 针对系统接口优化的总结以及给团队成员接下来review的留言
            system_apis: list[SystemApi] - 输出优化后系统接口列表，包含以下字段：
                - id: str - 接口ID（默认自动生成）
                - module_id: str - 接口所属模块ID（必填）
                - name: str - 接口名称（必填）
                - method: HttpMethod - HTTP方法（get/post/put/delete/patch）
                - path: str - 接口URL路径（必填）
                - description: str - 接口描述
                - request_headers: list[SystemApiRequestParam] - 请求头参数
                - request_params: list[SystemApiRequestParam] - URL查询参数
                - request_body: list[SystemApiRequestParam] - 请求体参数
                - response_schema: str - 响应格式（必填）

                其中 SystemApiRequestParam 包含：
                - name: str - 参数名称
                - type: HttpParamType - 参数类型（string/number/object/array）
                - required: bool - 是否必填
                - description: str - 参数描述
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            message=message,
            system_apis=system_apis,
        )
        error_message = utils.validate_module_ids_str(system_apis, runtime.state["optimized_modules"])
        command = optimize_doc_output(
            output, runtime, ["system_apis"], error_message=error_message, messages_key=messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        project_id = runtime.state["project_id"]
        # 如果原始接口内容为空 则保存当前版本为原始接口
        if not runtime.state.get("original_apis"):
            await api_service.bulk_update_by_state_apis(project_id, runtime.state["system_apis"])
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始接口入库")
        cutils.send_custom_message(
            "接口文档已更新，快来看看吧！", GroupMemberRole.BACKEND, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.SYSTEM_API.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 更新 command
        command.update.update({
            "original_apis": runtime.state.get("original_apis") or runtime.state["system_apis"],
            "optimized_apis": runtime.state["system_apis"],
        })
