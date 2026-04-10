from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.enums.test_case_level import TestCaseLevel
from src.enums.test_case_type import TestCaseType


class TestCaseBase(BaseModel):
    """测试用例基础字段"""
    project_id: str = Field(..., description="所属项目ID")
    module_id: Optional[str] = Field(None, description="所属模块ID")
    title: str = Field(..., description="用例标题")
    precondition: Optional[str] = Field(None, description="前置条件")
    test_steps: Optional[str] = Field(None, description="测试步骤")
    expected_result: Optional[str] = Field(None, description="预期结果")
    test_data: Optional[str] = Field(None, description="测试数据")
    level: TestCaseLevel = Field(default=TestCaseLevel.P2, description="用例等级: P0/P1/P2/P3")
    type: TestCaseType = Field(default=TestCaseType.FUNCTIONAL, description="类型: functional/interface/performance")


class TestCaseCreate(TestCaseBase):
    """创建测试用例"""
    pass


class TestCaseUpdate(BaseModel):
    """更新测试用例"""
    module_id: Optional[str] = None
    title: Optional[str] = None
    precondition: Optional[str] = None
    test_steps: Optional[str] = None
    expected_result: Optional[str] = None
    test_data: Optional[str] = None
    level: Optional[TestCaseLevel] = None
    type: Optional[TestCaseType] = None


class TestCaseResponse(TestCaseBase):
    """测试用例响应"""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
