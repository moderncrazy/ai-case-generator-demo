from typing import List, Tuple
from collections import defaultdict
from src.models.test_case import TestCase
from src.repositories.module_repository import module_repository
from src.repositories.test_case_repository import test_case_repository
from src.enums.test_case_level import TestCaseLevel
from src.enums.test_case_type import TestCaseType
from src.schemas.test_case import TestCaseResponse, TestCaseTreeNode


class TestCaseService:
    """测试用例服务
    
    提供测试用例相关的业务逻辑处理，
    包括查询用例列表、获取用例树形结构等功能。
    """

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
        # 获取项目下所有模块
        all_modules = await module_repository.list_by_project(project_id)
        module_dict = {m.id: m for m in all_modules}

        # 获取项目下所有测试用例
        all_test_cases = await test_case_repository.list_by_project(project_id)

        # 按 module_id 分组测试用例
        test_cases_by_module = defaultdict(list)
        for tc in all_test_cases:
            test_cases_by_module[tc.module_id].append(
                TestCaseResponse.model_validate(tc.to_dict())
            )

        # 构建树形结构
        def build_tree(parent_id: str = None) -> List[TestCaseTreeNode]:
            children = []
            for module in all_modules:
                if module.parent_id == parent_id:
                    node = TestCaseTreeNode(
                        module_id=module.id,
                        module_name=module.name,
                        test_cases=test_cases_by_module.get(module.id, []),
                        children=build_tree(module.id)
                    )
                    children.append(node)
            return children

        return build_tree()


# 导出单例
test_case_service = TestCaseService()
