from enum import Enum


class EntityType(str, Enum):
    """实体类型枚举，与数据库 operation_logs.entity_type 字段一致"""

    PROJECT = "project"
    """项目"""

    MODULE = "module"
    """模块"""

    TEST_CASE = "test_case"
    """测试用例"""

    API = "api"
    """接口"""

    CONVERSATION_MESSAGE = "conversation_message"
    """对话消息"""

    PROJECT_FILE = "project_file"
    """项目文件"""
