import uuid
import traceback

import streamlit as st

from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.schemas.response import ListResponse
from src.frontend.enums.test_case_level import TestCaseLevel
from src.frontend.enums.test_case_type import TestCaseType
from src.frontend.schemas.test_case import TestCaseResponse, TestCaseTreeNode, TestCaseTreeDocumentResponse

SERVER_HOST = st.secrets["server"]["host"]

logger = utils.get_logger()


class TestCaseService:

    @staticmethod
    def list_test_cases(
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            module_id: str = None,
            level: TestCaseLevel = None,
            type: TestCaseType = None,
    ) -> ListResponse[TestCaseResponse] | None:
        """查询测试用例列表"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/test-cases",
                headers={const.TRANSACTION_ID: trans_id},
                params={
                    "page": page,
                    "page_size": page_size,
                    "module_id": module_id,
                    "level": level.value if level else None,
                    "type": type.value if type else None,
                }
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ListResponse[TestCaseResponse].model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 页码:{page} 每页:{page_size} 模块Id:{module_id} 用例等级:{level} 用例类型:{type} 查询测试用例列表失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_test_cases_tree(project_id: str) -> list[TestCaseTreeNode] | None:
        """获取测试用例树形结构"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/test-cases/tree",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return [TestCaseTreeNode.model_validate(item) for item in resp.get("data", [])]
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取测试用例树形结构失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_test_cases_compare(project_id: str) -> TestCaseTreeDocumentResponse | None:
        """获取测试用例对比文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/test-cases/compare",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return TestCaseTreeDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取测试用例对比文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_markdown_by_test_cases_tree(tree_nodes: list[TestCaseTreeNode], level: int = 1) -> str:
        """将测试用例树转换为 Markdown 格式文档"""
        content = ""
        if tree_nodes:
            for node in tree_nodes:
                # 模块标题
                content += f"{'#' * level} {node.module_name}\n\n"
                # 测试用例表格
                if node.test_cases:
                    content += "| 用例标题 | 用例等级 | 用例类型 | 前置条件 | 测试步骤 | 预期结果 | 测试数据 |\n"
                    content += "| -------- | -------- | -------- | -------- | -------- | -------- | -------- |\n"
                    for tc in node.test_cases:
                        # 处理单元格内容中的换行和特殊字符
                        precondition = tc.precondition.replace("\n", "<br>") if tc.precondition else ""
                        test_steps = tc.test_steps.replace("\n", "<br>")
                        expected_result = tc.expected_result.replace("\n", "<br>")
                        test_data = tc.test_data.replace("\n", "<br>")
                        level_value = tc.level.value
                        type_value = tc.type.value
                        content += f"| {tc.title} | {level_value} | {type_value} | {precondition} | {test_steps} | {expected_result} | {test_data} |\n"
                    content += "\n"

                # 递归处理子模块
                if node.children:
                    content += TestCaseService.get_markdown_by_test_cases_tree(node.children, level + 1)
        return content


# 导出单例
test_case_service = TestCaseService()
