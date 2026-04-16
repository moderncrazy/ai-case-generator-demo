import uuid
from typing import Optional
from pydantic import BaseModel, Field

from src.graphs.schemas import Issue
from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel


class TestCase(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="测试用例Id，默认自动生成",
                              min_length=1)
    module_id: str = Field(description="测试用例所属模块Id", min_length=1)
    title: str = Field(description="测试用例标题", min_length=1)
    precondition: Optional[str] = Field(description="前置条件")
    test_steps: str = Field(description="测试步骤", min_length=1)
    expected_result: str = Field(description="预期结果", min_length=1)
    test_data: str = Field(description="测试数据", min_length=1)
    level: TestCaseLevel = Field(description="测试用例等级（P0/P1/P2/P3）")
    type: TestCaseType = Field(description="测试用例类型（FUNCTIONAL/INTERFACE/PERFORMANCE）")


class OptimizeTestCaseOutput(BaseModel):
    """测试优化测试用例输出"""
    message: str = Field(description="针对测试用例优化的总结以及给团队成员接下来review的留言", min_length=1)
    test_cases: list[TestCase] = Field(description="输出优化后测试用例列表", min_length=1)


class ReviewTestCaseOutput(BaseModel):
    """项目成员审查测试用例输出"""
    test_case_issues: list[Issue] = Field(description="针对测试用例提出的问题和建议方案")
