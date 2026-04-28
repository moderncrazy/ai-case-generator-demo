from typing import Optional, List
from pydantic import BaseModel, Field

from src.frontend.enums.test_case_level import TestCaseLevel
from src.frontend.enums.test_case_type import TestCaseType


class TestCaseResponse(BaseModel):
    """测试用例响应"""
    id: str = Field(description="测试用例ID")
    module_id: str = Field(description="所属模块ID")
    title: str = Field(description="用例标题")
    precondition: Optional[str] = Field(default=None, description="前置条件")
    test_steps: str = Field(description="测试步骤")
    expected_result: str = Field(description="预期结果")
    test_data: str = Field(description="测试数据")
    level: TestCaseLevel = Field(description="用例等级")
    type: TestCaseType = Field(description="用例类型")


class TestCaseTreeNode(BaseModel):
    """测试用例树节点（按模块父子级组织）"""
    module_id: str = Field(description="模块ID")
    module_name: str = Field(description="模块名称")
    test_cases: list[TestCaseResponse] = Field(default_factory=list, description="测试用例列表")
    children: list["TestCaseTreeNode"] = Field(default_factory=list, description="子模块")


class TestCaseTreeDocumentResponse(BaseModel):
    """测试用例树文档响应（原始版和优化版）"""
    original: Optional[List[TestCaseTreeNode]] = Field(default=None, description="原始测试用例树")
    optimized: Optional[List[TestCaseTreeNode]] = Field(default=None, description="优化测试用例树")
