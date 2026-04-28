import uuid
from typing import Optional
from pydantic import BaseModel, Field

from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel
from src.graphs.common.schemas import OptimizeDocBaseOutput


class TestCase(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="测试用例Id，默认自动生成",
                              min_length=1)
    module_id: str = Field(description="测试用例所属模块Id", min_length=1)
    title: str = Field(description="测试用例标题", min_length=1)
    precondition: Optional[str] = Field(default="", description="前置条件")
    test_steps: str = Field(description="测试步骤", min_length=1)
    expected_result: str = Field(description="预期结果", min_length=1)
    test_data: str = Field(description="测试数据", min_length=1)
    level: TestCaseLevel = Field(description="测试用例等级（P0/P1/P2/P3）")
    type: TestCaseType = Field(description="测试用例类型（FUNCTIONAL/INTERFACE/PERFORMANCE）")


class OptimizeTestCaseOutput(OptimizeDocBaseOutput):
    """测试优化测试用例输出"""
    test_cases: list[TestCase] = Field(description="输出优化后测试用例列表", min_length=1)

