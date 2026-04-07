from piccolo.columns import Varchar, Timestamp

from src.models.base import BaseModel


class TestCase(BaseModel):
    """测试用例表模型"""
    id = Varchar(length=36, primary_key=True)
    project_id = Varchar(length=36)
    module_id = Varchar(length=36, null=True)
    title = Varchar(length=255)
    precondition = Varchar(null=True)
    test_steps = Varchar(null=True)
    expected_result = Varchar(null=True)
    test_data = Varchar(null=True)
    level = Varchar(default="P2")
    type = Varchar(default="functional")
    created_at = Timestamp(null=True)
    updated_at = Timestamp(null=True)

    class Meta:
        table_name = "test_case"
