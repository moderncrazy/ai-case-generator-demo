from piccolo.columns import Varchar, Timestamp, ForeignKey

from src.models.base import BaseModel
from src.models.project import Project
from src.models.module import Module
from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel


class TestCase(BaseModel):
    """测试用例表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = ForeignKey(references=Project)
    module_id = ForeignKey(references=Module)
    title = Varchar(length=255)
    precondition = Varchar(null=True)
    test_steps = Varchar()
    expected_result = Varchar()
    test_data = Varchar()
    level = Varchar(default=TestCaseLevel.P2.value)
    type = Varchar(default=TestCaseType.FUNCTIONAL.value)
    created_at = Timestamp()
    updated_at = Timestamp()

    class Meta:
        table_name = "test_case"
