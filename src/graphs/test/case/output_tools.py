from loguru import logger
from langgraph.types import Command
from langgraph.prebuilt import ToolRuntime

from src.context import trans_id_ctx
from src.services.business.test_case_service import test_case_service
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.test.case import utils
from src.graphs.test.case.schemas import OptimizeDocOutput, TestCase
from src.graphs.common.utils import utils as cutils
from src.graphs.common.base.output_tools import tool, optimize_doc_output, OptimizationDocOutputTools


class OutputTools(OptimizationDocOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            message: str,
            test_cases: list[TestCase],
            runtime: ToolRuntime,
    ) -> Command:
        """输出测试优化测试用例结果

        AI大模型使用此工具可完成测试用例的优化分析并输出结构化结果。

        **功能说明：**
        这是测试用例设计阶段的核心输出工具，用于：
        1. 对测试用例进行优化（完善步骤、调整分级、补充数据等）
        2. 验证测试用例合法性（检查 module_id 是否存在于系统模块中）
        3. 更新状态中的测试用例列表
        4. 清空之前的问题记录，为评审做准备

        Args:
            message: str - 针对测试用例优化的总结以及给团队成员接下来review的留言
            test_cases: list[TestCase] - 输出优化后测试用例列表，包含以下字段：
                - id: str - 测试用例ID（默认自动生成，UUID）
                - module_id: str - 测试用例所属模块ID（必填）
                - title: str - 测试用例标题（必填）
                - precondition: str - 前置条件
                - test_steps: str - 测试步骤（必填）
                - expected_result: str - 预期结果（必填）
                - test_data: str - 测试数据（必填）
                - level: TestCaseLevel - 测试用例等级（p0/p1/p2/p3）
                - type: TestCaseType - 测试用例类型（functional/interface/performance）
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            message=message,
            test_cases=test_cases,
        )
        error_message = utils.validate_module_ids_str(test_cases, runtime.state["optimized_modules"])
        command = optimize_doc_output(
            output, runtime, ["test_cases"], error_message=error_message, messages_key=messages_key)
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return command

    async def review_pass_callback(self, runtime: ToolRuntime, command: Command):
        project_id = runtime.state["project_id"]
        # 如果原始测试用例内容为空 则保存当前版本为原始测试用例
        if not runtime.state.get("original_test_cases"):
            await test_case_service.bulk_update_by_state_test_cases(project_id, runtime.state["test_cases"])
            logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 创建原始测试用例入库")
        cutils.send_custom_message(
            "测试用例已更新，快来看看吧！", GroupMemberRole.TEST, ConversationMessageType.NOTIFY)
        # 发送文档更新消息
        cutils.send_custom_message(
            ProjectDocType.TEST_CASE.value,
            GroupMemberRole.PRODUCT,
            ConversationMessageType.DOC_UPDATE
        )
        # 更新 command
        command.update.update({
            "original_test_cases": runtime.state.get("original_test_cases") or runtime.state["test_cases"],
            "optimized_test_cases": runtime.state["test_cases"],
        })
