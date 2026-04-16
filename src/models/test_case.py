from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.base import BaseModel
from src.models.project import Project
from src.models.module import Module
from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel


class TestCase(BaseModel):
    """测试用例表模型
    
    存储测试用例的定义信息。
    """
    id = Varchar(length=36, primary_key=True)
    """用例唯一标识（UUID）"""
    project_id = ForeignKey(references=Project)
    """所属项目ID"""
    module_id = ForeignKey(references=Module)
    """所属模块ID"""
    title = Varchar(length=255)
    """用例标题"""
    precondition = Varchar(null=True)
    """前置条件"""
    test_steps = Varchar()
    """测试步骤"""
    expected_result = Varchar()
    """预期结果"""
    test_data = Varchar()
    """测试数据"""
    level = Varchar(default=TestCaseLevel.P2.value)
    """用例等级（P0/P1/P2/P3）"""
    type = Varchar(default=TestCaseType.FUNCTIONAL.value)
    """用例类型（功能测试/接口测试/性能测试等）"""
    created_at = Timestamp()
    """创建时间"""
    updated_at = Timestamp()
    """更新时间"""

    class Meta:
        table_name = "test_case"
