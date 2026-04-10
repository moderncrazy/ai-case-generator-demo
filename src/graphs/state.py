from langchain.messages import AnyMessage
from langgraph.graph import MessagesState

from src.enums.pm_next_step import PMNextStep
from src.enums.project_progress import ProjectProgress
from src.graphs.schemas import StateProjectFile, StateNewProjectFile, StateModule, StateTestCase, StateApi, Issue


class State(MessagesState):
    """LangGraph 工作流状态定义"""

    project_id: str
    """项目ID"""

    project_name: str
    """项目名称"""

    project_progress: ProjectProgress
    """项目进度状态"""

    new_file_list: list[StateNewProjectFile]
    """用户新上传的文件信息列表"""

    project_file_list: list[StateProjectFile]
    """项目文件列表（不含内容）"""

    original_requirement: str
    """原始PRD内容"""

    optimized_requirement: str
    """优化后PRD内容"""

    original_architecture: str
    """原始架构设计"""

    optimized_architecture: str
    """优化后架构设计"""

    original_database: str
    """原始数据库设计"""

    optimized_database: str
    """优化后数据库设计"""

    original_modules: list[StateModule]
    """原始模块设计"""

    optimized_modules: list[StateModule]
    """优化后模块设计"""

    original_apis: list[StateApi]
    """原始API设计"""

    optimized_apis: list[StateApi]
    """优化后API设计"""

    original_test_cases: list[StateTestCase]
    """原始测试用例设计"""

    optimized_test_cases: list[StateTestCase]
    """优化后测试用例设计"""

    risks: list[Issue]
    """需要提给客户的风险点和建议（不设置reducer等子图覆盖）"""

    unclear_points: list[Issue]
    """需要让用户明确的问题和建议（不设置reducer等子图覆盖）"""

    pm_next_step: PMNextStep
    """下一步执行"""

    pm_next_step_instruction: str
    """下一步执行的指示"""

    private_messages: list[AnyMessage]
    """用于子图私聊（不设置reducer等子图覆盖）"""
