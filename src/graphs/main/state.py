from langgraph.graph import MessagesState

from src.enums.pm_next_step import PMNextStep
from src.enums.project_progress import ProjectProgress


class State(MessagesState):
    """LangGraph 工作流状态定义"""

    project_id: str
    """项目ID"""

    project_name: str
    """项目名称"""

    project_progress: ProjectProgress
    """项目进度状态"""

    new_file_list: list[str]
    """用户新上传的文件名列表"""

    new_files_content: dict[str, str]
    """新文件的解析内容，格式: {文件名: 解析后的文本内容}"""

    next_step: PMNextStep
    """下一步执行"""
