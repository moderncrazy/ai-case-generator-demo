import uuid
from pydantic import BaseModel, Field
from typing import Optional, TypedDict

from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel


class StateTestCaseTask(TypedDict):
    """测试用例任务状态结构

    测试用例任务划分定义。
    """
    module_id: str
    """模块Id"""
    module_name: str
    """模块名称"""
    title: str
    """任务标题"""
    scope: str
    """任务范围描述"""
    test_case_titles: list[str]
    """测试用例标题列表"""


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


class TestCaseTask(BaseModel):
    """测试用例任务定义"""
    module_id: str = Field(description="模块Id", min_length=1)
    module_name: str = Field(description="模块名称", min_length=1)
    title: str = Field(description="任务标题（简洁明确）", min_length=1)
    scope: str = Field(description="任务范围描述", min_length=1)
    test_case_titles: list[str] = Field(description="测试用例标题列表", min_length=1)


class OptimizeDocOutput(BaseModel):
    """分配测试用例任务输出"""
    tasks: list[TestCaseTask] = Field(description="输出需要优化的具体任务列表", min_length=1)


class OptimizeDocByTaskOutput(BaseModel):
    """测试根据任务优化测试用例输出"""
    test_cases: list[TestCase] = Field(description="输出优化后测试用例列表", min_length=1)
