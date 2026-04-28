from typing import List, Tuple
from src.agents.main_agent import main_agent
from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel
from src.services.module_service import module_service
from src.schemas.test_case import TestCaseResponse, TestCaseTreeNode, TestCaseTreeDocumentResponse
from src.repositories.module_repository import module_repository
from src.repositories.test_case_repository import test_case_repository


class TestCaseService:
    """测试用例服务
    
    提供测试用例相关的业务逻辑处理，
    包括查询用例列表、获取用例树形结构等功能。
    """

    @staticmethod
    def _convert_tc_to_response(tc) -> TestCaseResponse:
        """将测试用例模型或字典转换为 TestCaseResponse

        Args:
            tc: 测试用例模型或字典

        Returns:
            TestCaseResponse 对象
        """
        if hasattr(tc, "to_dict"):
            return TestCaseResponse.model_validate(tc.to_dict())
        return TestCaseResponse.model_validate(tc)

    @staticmethod
    def _group_test_cases_by_module(test_cases: list) -> dict:
        """按 module_id 分组 TestCaseResponse

        Args:
            test_cases: TestCaseResponse 列表

        Returns:
            按 module_id 分组的字典
        """
        tcs_by_module = {}
        for tc in test_cases:
            module_id = tc.module_id
            if module_id:
                if module_id not in tcs_by_module:
                    tcs_by_module[module_id] = []
                tcs_by_module[module_id].append(tc)
        return tcs_by_module

    @staticmethod
    def _build_test_case_tree(module_nodes: list, tcs_by_module: dict) -> List[TestCaseTreeNode]:
        """构建测试用例树

        Args:
            module_nodes: 模块树节点列表
            tcs_by_module: 按 module_id 分组的字典

        Returns:
            测试用例树节点列表
        """
        result = []
        for node in module_nodes:
            children = TestCaseService._build_test_case_tree(node.children, tcs_by_module) if node.children else []
            result.append(TestCaseTreeNode(
                module_id=node.id,
                module_name=node.name,
                test_cases=tcs_by_module.get(node.id, []),
                children=children
            ))
        return result

    @staticmethod
    async def list_test_cases(
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            module_id: str = None,
            level: TestCaseLevel = None,
            type: TestCaseType = None,
    ) -> Tuple[List[TestCaseResponse], int]:
        """查询测试用例列表

        分页查询项目的测试用例列表。

        Args:
            project_id: 项目 ID
            page: 页码（从 1 开始）
            page_size: 每页数量
            module_id: 按模块筛选（可选）
            level: 按用例等级筛选（可选）
            type: 按用例类型筛选（可选）

        Returns:
            (测试用例响应列表, 总数) 元组
        """
        test_cases, total = await test_case_repository.paginate(
            project_id=project_id,
            page=page,
            page_size=page_size,
            module_id=module_id,
            level=level,
            type=type,
        )
        return [TestCaseResponse.model_validate(tc.to_dict()) for tc in test_cases], total

    @staticmethod
    async def get_test_cases_tree(project_id: str) -> List[TestCaseTreeNode]:
        """获取测试用例树形结构
        
        按模块父子级组织项目的测试用例。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            测试用例树形结构列表
        """
        # 获取项目下所有模块并转为字典格式
        all_modules = await module_repository.list_by_project(project_id)
        module_dicts = [m.to_dict() for m in all_modules]

        # 复用 module_service 的模块树构建方法
        module_tree = module_service.build_module_tree_from_dict(module_dicts)

        # 获取项目下所有测试用例并转换为 TestCaseResponse
        all_test_cases = await test_case_repository.list_by_project(project_id)
        tc_responses = [TestCaseService._convert_tc_to_response(tc) for tc in all_test_cases]

        # 复用公共方法构建测试用例树
        return TestCaseService._build_test_case_tree(
            module_tree, TestCaseService._group_test_cases_by_module(tc_responses))

    @staticmethod
    async def get_test_cases_compare(project_id: str) -> TestCaseTreeDocumentResponse:
        """获取测试用例对比文档
        
        从 graph state 获取原始版本和优化版本的测试用例树形结构。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            测试用例树文档响应（原始版和优化版）
        """
        state = await main_agent.get_state(project_id)
        modules = state.get("optimized_modules") or []

        # 复用 module_service 的模块树构建方法
        module_tree = module_service.build_module_tree_from_dict(modules)

        # 分别构建原始版和优化版的测试用例树
        original_tcs = state.get("original_test_cases") if state else []
        optimized_tcs = state.get("optimized_test_cases") if state else []

        original_test_cases = TestCaseService._build_test_case_tree(
            module_tree, TestCaseService._group_test_cases_by_module(
                [TestCaseService._convert_tc_to_response(tc) for tc in original_tcs]))
        optimized_test_cases = TestCaseService._build_test_case_tree(
            module_tree, TestCaseService._group_test_cases_by_module(
                [TestCaseService._convert_tc_to_response(tc) for tc in optimized_tcs]))

        return TestCaseTreeDocumentResponse(
            original=original_test_cases,
            optimized=optimized_test_cases
        )


# 导出单例
test_case_service = TestCaseService()
