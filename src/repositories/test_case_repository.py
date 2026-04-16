import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from src.models.test_case import TestCase
from src.enums.test_case_level import TestCaseLevel
from src.enums.test_case_type import TestCaseType


class TestCaseCreate(BaseModel):
    """创建测试用例参数"""
    project_id: str
    """所属项目 ID"""
    title: str
    """用例标题"""
    module_id: str
    """所属模块 ID"""
    precondition: Optional[str]
    """前置条件"""
    test_steps: str
    """测试步骤"""
    expected_result: str
    """预期结果"""
    test_data: str
    """测试数据"""
    level: TestCaseLevel = TestCaseLevel.P2
    """用例等级"""
    type: TestCaseType = TestCaseType.FUNCTIONAL
    """用例类型"""


class TestCaseUpdate(BaseModel):
    """更新测试用例参数"""
    title: Optional[str] = None
    """用例标题"""
    module_id: Optional[str] = None
    """所属模块 ID"""
    precondition: Optional[str] = None
    """前置条件"""
    test_steps: Optional[str] = None
    """测试步骤"""
    expected_result: Optional[str] = None
    """预期结果"""
    test_data: Optional[str] = None
    """测试数据"""
    level: Optional[TestCaseLevel] = None
    """用例等级"""
    type: Optional[TestCaseType] = None
    """用例类型"""


class TestCaseBulkUpdate(BaseModel):
    """批量更新测试用例参数"""
    title: str
    """用例标题"""
    module_id: str
    """所属模块 ID"""
    precondition: Optional[str]
    """前置条件"""
    test_steps: str
    """测试步骤"""
    expected_result: str
    """预期结果"""
    test_data: str
    """测试数据"""
    level: TestCaseLevel = TestCaseLevel.P2
    """用例等级"""
    type: TestCaseType = TestCaseType.FUNCTIONAL
    """用例类型"""


class TestCaseRepository:
    """测试用例 Repository
    
    提供测试用例（TestCase）的数据库操作，
    包括创建、更新、查询、按模块/等级统计、批量操作等功能。
    """

    def __init__(self):
        self.model = TestCase

    async def create(self, test_case: TestCaseCreate) -> str | None:
        """创建测试用例
        
        Args:
            test_case: 创建参数
            
        Returns:
            新建测试用例的 ID，失败返回 None
        """
        now = datetime.now()
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                project_id=test_case.project_id,
                module_id=test_case.module_id,
                title=test_case.title,
                precondition=test_case.precondition,
                test_steps=test_case.test_steps,
                expected_result=test_case.expected_result,
                test_data=test_case.test_data,
                level=test_case.level.value,
                type=test_case.type.value,
                created_at=now,
                updated_at=now,
            )
        )
        return results[0]["id"] if results else None

    async def update(
            self,
            id: str,
            test_case: TestCaseUpdate
    ) -> None:
        """更新测试用例
        
        Args:
            id: 用例 ID
            test_case: TestCaseUpdate
        """
        update_data: dict = {self.model.updated_at: datetime.now()}
        if test_case.title is not None:
            update_data[self.model.title] = test_case.title
        if test_case.module_id is not None:
            update_data[self.model.module_id] = test_case.module_id
        if test_case.precondition is not None:
            update_data[self.model.precondition] = test_case.precondition
        if test_case.test_steps is not None:
            update_data[self.model.test_steps] = test_case.test_steps
        if test_case.expected_result is not None:
            update_data[self.model.expected_result] = test_case.expected_result
        if test_case.test_data is not None:
            update_data[self.model.test_data] = test_case.test_data
        if test_case.level is not None:
            update_data[self.model.level] = test_case.level.value
        if test_case.type is not None:
            update_data[self.model.type] = test_case.type.value

        await self.model.update(update_data).where(
            self.model.id == id
        )

    async def get_by_id(self, id: str) -> Optional[TestCase]:
        """根据 ID 获取测试用例
        
        Args:
            id: 用例 ID
            
        Returns:
            测试用例对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return TestCase(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[TestCase]:
        """获取项目的所有测试用例
        
        Args:
            project_id: 项目 ID
            
        Returns:
            测试用例列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [TestCase(**item) for item in results]

    async def list_by_module(self, module_id: str) -> List[TestCase]:
        """获取模块的所有测试用例
        
        Args:
            module_id: 模块 ID
            
        Returns:
            测试用例列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.module_id == module_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [TestCase(**item) for item in results]

    async def list_by_level(self, project_id: str, level: TestCaseLevel) -> List[TestCase]:
        """根据级别筛选测试用例
        
        Args:
            project_id: 项目 ID
            level: 用例等级
            
        Returns:
            符合条件测试用例列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.level == level.value
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [TestCase(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的测试用例数量
        
        Args:
            project_id: 项目 ID
            
        Returns:
            测试用例数量
        """
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有测试用例
        
        Args:
            project_id: 项目 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def bulk_update(self, project_id: str, test_cases: List[TestCaseBulkUpdate]) -> List[str]:
        """批量更新测试用例（先删除项目下所有测试用例再插入）

        Args:
            project_id: 项目ID
            test_cases: 测试用例更新参数列表

        Returns:
            插入的测试用例ID列表
        """
        # 先删除项目下所有测试用例
        await self.delete_by_project(project_id)

        now = datetime.now()
        instances = [
            self.model(
                id=str(uuid.uuid4()),
                project_id=project_id,
                module_id=item.module_id,
                title=item.title,
                precondition=item.precondition,
                test_steps=item.test_steps,
                expected_result=item.expected_result,
                test_data=item.test_data,
                level=item.level.value,
                type=item.type.value,
                created_at=now,
                updated_at=now,
            )
            for item in test_cases
        ]
        results = await self.model.insert(*instances)
        return [item["id"] for item in results]

    async def paginate(
            self,
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            module_id: str = None,
            level: TestCaseLevel = None,
            type: TestCaseType = None,
    ) -> tuple[List[TestCase], int]:
        """分页查询测试用例
        
        Args:
            project_id: 项目 ID
            page: 页码
            page_size: 每页数量
            module_id: 按模块筛选
            level: 按等级筛选
            type: 按类型筛选
            
        Returns:
            (测试用例列表, 总数) 元组
        """
        base_where = self.model.project_id == project_id
        if module_id:
            base_where = base_where & (self.model.module_id == module_id)
        if level:
            base_where = base_where & (self.model.level == level.value)
        if type:
            base_where = base_where & (self.model.type == type.value)
        total = await self.model.count().where(base_where)
        results = await (
            self.model.select()
            .where(base_where)
            .order_by(self.model.created_at, ascending=False)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        test_cases = [TestCase(**item) for item in results]
        return test_cases, total


# 全局单例实例
test_case_repository = TestCaseRepository()
