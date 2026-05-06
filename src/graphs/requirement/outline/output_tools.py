from loguru import logger
from langgraph.types import Command
from langchain.messages import AIMessage
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.services.business.project_service import project_service, ProjectUpdate
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.reducer_action_type import ReducerActionType
from src.enums.requirement_module_status import RequirementModuleStatus
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.common.schemas.state_schemas import StateRequirementModule
from src.graphs.common.base.output_tools import tool, OptimizationDocOutputTools
from src.graphs.common.utils import structured_output_utils, utils as cutils
from src.graphs.requirement.outline import utils
from src.graphs.requirement.outline.schemas import OptimizeDocOutput, RequirementModuleCreate


class OutputTools(OptimizationDocOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            requirement_outline: str,
            requirement_modules: list[RequirementModuleCreate],
            runtime: ToolRuntime,
    ) -> Command:
        """输出需求大纲优化结果工具

        AI大模型使用此工具可完成需求大纲的优化并输出结构化结果。

        功能说明：
        1. 验证需求模块是否重复
        2. 设置状态为 pending 并排序
        3. 保存到数据库
        4. 发送通知消息给客户

        Args:
            message: str - 针对需求大纲优化的总结以及给团队成员接下来review的留言
            requirement_outline: str - 优化后的需求大纲内容（Markdown格式）
            requirement_modules: list[RequirementModuleCreate] - 需求模块列表
                - name: str - 模块名称
                - description: str - 模块描述
                - order: int - 排序
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入

        Returns:
            Command: 状态更新命令，包含 requirement_outline 和 requirement_modules 更新
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            message=message,
            requirement_outline=requirement_outline,
            requirement_modules=requirement_modules
        )
        # 验证需求模块是否重复
        error_message = utils.validate_requirement_modules(requirement_modules)
        if error_message:
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 需求模块验证失败打回:{error_message}")
            structured_output_utils.rollback(
                runtime.tool_call_id,
                gutils.get_func_name(),
                output.model_dump(),
                error_message,
                messages_key=messages_key
            )
        # 默认设置状态为 pending 并 排序
        state_requirement_modules = sorted(
            [StateRequirementModule(status=RequirementModuleStatus.PENDING, **item.model_dump())
             for item in output.requirement_modules],
            key=lambda m: m["order"])
        # 保存需求大纲
        await project_service.update_project_and_clear_cache(
            project_id,
            ProjectUpdate(
                requirement_outline_design=requirement_outline,
                requirement_module_design=gutils.to_json(state_requirement_modules),
            )
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 更新需求大纲和模块入库")
        # 发送通知消息
        cutils.send_custom_message(
            "需求大纲已更新，快来看看吧！", GroupMemberRole.PRODUCT, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.REQUIREMENT_OUTLINE.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return Command(update={
            "node_rollback": False,
            "messages": [AIMessage(content=output.message, name=GroupMemberRole.PRODUCT.value)],
            messages_key: ReducerActionType.RESET,
            "requirement_outline": output.requirement_outline,
            "requirement_modules": state_requirement_modules,
        })

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        pass
