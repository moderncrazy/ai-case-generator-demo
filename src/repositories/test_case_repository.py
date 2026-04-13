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
    title: str
    module_id: str
    precondition: Optional[str]
    test_steps: str
    expected_result: str
    test_data: str
    level: TestCaseLevel = TestCaseLevel.P2
    type: TestCaseType = TestCaseType.FUNCTIONAL


class TestCaseUpdate(BaseModel):
    """创建测试用例参数"""
    title: str
    module_id: str
    precondition: Optional[str]
    test_steps: str
    expected_result: str
    test_data: str
    level: TestCaseLevel = TestCaseLevel.P2
    type: TestCaseType = TestCaseType.FUNCTIONAL


class TestCaseRepository:
    """测试用例 Repository"""

    def __init__(self):
        self.model = TestCase

    async def create(self, test_case: TestCaseCreate) -> str | None:
        """创建测试用例"""
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
            title: Optional[str] = None,
            module_id: Optional[str] = None,
            precondition: Optional[str] = None,
            test_steps: Optional[str] = None,
            expected_result: Optional[str] = None,
            test_data: Optional[str] = None,
            level: Optional[TestCaseLevel] = None,
            type: Optional[TestCaseType] = None,
    ) -> None:
        """更新测试用例"""
        update_data = {self.model.updated_at: datetime.now()}
        if title is not None:
            update_data[self.model.title] = title
        if module_id is not None:
            update_data[self.model.module_id] = module_id
        if precondition is not None:
            update_data[self.model.precondition] = precondition
        if test_steps is not None:
            update_data[self.model.test_steps] = test_steps
        if expected_result is not None:
            update_data[self.model.expected_result] = expected_result
        if test_data is not None:
            update_data[self.model.test_data] = test_data
        if level is not None:
            update_data[self.model.level] = level.value
        if type is not None:
            update_data[self.model.type] = type.value

        await self.model.update(update_data).where(
            self.model.id == id
        )

    async def get_by_id(self, id: str) -> Optional[TestCase]:
        """根据 ID 获取记录"""
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return TestCase(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[TestCase]:
        """获取项目的所有测试用例"""
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [TestCase(**item) for item in results]

    async def list_by_module(self, module_id: str) -> List[TestCase]:
        """获取模块的所有测试用例"""
        results = await self.model.select().where(
            self.model.module_id == module_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [TestCase(**item) for item in results]

    async def list_by_level(self, project_id: str, level: TestCaseLevel) -> List[TestCase]:
        """根据级别筛选测试用例"""
        results = await self.model.select().where(
            self.model.project_id == project_id,
            self.model.level == level.value
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [TestCase(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的测试用例数量"""
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有测试用例"""
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def bulk_update(self, project_id: str, test_cases: List[TestCaseUpdate]) -> List[str]:
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


# 全局单例实例
test_case_repository = TestCaseRepository()
