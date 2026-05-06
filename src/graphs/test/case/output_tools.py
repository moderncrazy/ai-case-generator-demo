import uuid
from loguru import logger
from langchain.messages import AIMessage
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command, Overwrite

from src.context import trans_id_ctx
from src.utils import utils as gutils
from src.enums.reducer_action_type import ReducerActionType
from src.services.business.test_case_service import test_case_service
from src.enums.project_doc_type import ProjectDocType
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.test.case import utils
from src.graphs.test.case.schemas import (
    TestCase,
    TestCaseTask,
    OptimizeDocOutput,
    OptimizeDocByTaskOutput,
)
from src.graphs.common.base.output_tools import tool, OptimizationDocOutputTools
from src.graphs.common.utils import utils as cutils, message_utils, structured_output_utils


class OutputTools(OptimizationDocOutputTools):

    @tool(args_schema=OptimizeDocOutput)
    async def optimize_doc_output(
            self,
            tasks: list[TestCaseTask],
            runtime: ToolRuntime,
    ) -> Command:
        """输出测试用例任务列表

        AI大模型使用此工具可完成测试用例任务的划分并输出结构化结果。

        **功能说明：**
        这是测试用例任务划分阶段的核心输出工具，用于：
        1. 将测试用例设计任务按模块/功能点细分为具体任务
        2. 每个任务预估生成 5-15 个测试用例，最多不超过 20 个
        3. 验证任务列表中的 module_id 是否存在于系统模块中
        4. 任务将由子agent并行执行生成具体测试用例
        5. 清空之前的问题记录

        Args:
            tasks: list[TestCaseTask] - 测试用例任务列表，包含以下字段：
                - module_id: str - 模块Id
                - module_name: str - 模块名称
                - title: str - 任务标题
                - scope: str - 任务范围描述
                - test_case_titles: list[str] - 测试用例标题列表
            runtime: 系统运行时对象，AI传参时不用传递，会自动注入
        """
        messages_key = self.messages_key
        project_id = runtime.state["project_id"]
        output = OptimizeDocOutput(
            tasks=tasks,
        )
        project_progress = runtime.state["project_progress"]
        role = cutils.get_role_optimization_by_project_progress(project_progress)
        # 验证各角色提出的意见是否被清空
        if runtime.state.get("review_issues"):
            error_message = f"检验失败：评审意见未全部解决，重新优化并解决全部评审意见"
        else:
            # 验证任务列表中的 module_id 是否存在于系统模块中
            error_message = utils.validate_task_module_ids(tasks, runtime.state["optimized_modules"])
        if error_message:
            logger.warning(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 打回:{error_message}")
            return structured_output_utils.rollback(
                runtime.tool_call_id, gutils.get_func_name(), output.model_dump(), error_message, messages_key)
        result_message = AIMessage(
            content="任务已下发，请严格按照 get_current_test_case_task 方法返回的【测试用例标题列表】生成/优化测试用例",
            name=role.value,
            id=runtime.state["task_reply_message_id"]
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        return Command(update={
            "node_rollback": False,
            "tasks": [item.model_dump() for item in tasks],
            "review_issues": ReducerActionType.RESET,
            "task_reply_message_id": str(uuid.uuid4()),
            # 重写消息列表 删除所有tool调用
            messages_key: Overwrite(
                value=message_utils.remove_tool_messages([*runtime.state[messages_key], result_message])),
        })

    @tool(args_schema=OptimizeDocByTaskOutput)
    async def optimize_doc_by_task_output(
            self,
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
        output = OptimizeDocByTaskOutput(
            test_cases=test_cases,
        )
        project_progress = runtime.state["project_progress"]
        role = cutils.get_role_optimization_by_project_progress(project_progress)
        # 验证测试用例模块划分
        error_message = utils.validate_module_ids_str(test_cases, runtime.state["optimized_modules"])
        if error_message:
            logger.warning(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 打回:{error_message}")
            return structured_output_utils.rollback(
                runtime.tool_call_id, gutils.get_func_name(), output.model_dump(), error_message, messages_key)
        result_message = AIMessage(
            content="测试用例优化完成，请审核",
            name=role.value,
            id=runtime.state["task_reply_message_id"]
        )
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 输出:{output.model_dump_json()}")
        # 若是 BaseModel 则 转为 dict
        return Command(update={
            "node_rollback": False,
            "test_cases": [item.model_dump() for item in test_cases],
            # 重写消息列表 删除所有tool调用
            messages_key: Overwrite(
                value=message_utils.remove_tool_messages([*runtime.state[messages_key], result_message])),
        })

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
