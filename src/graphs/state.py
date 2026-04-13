from typing import Any, Annotated
from typing_extensions import Doc
from langchain.messages import AnyMessage
from langgraph.graph import MessagesState

from src.enums.pm_next_step import PMNextStep
from src.enums.project_progress import ProjectProgress
from src.graphs.schemas import (
    Issue,
    StateApi,
    StateModule,
    StateTestCase,
    StateProjectFile,
    StateNewProjectFile,
    StateRequirementModule
)


class State(MessagesState):
    """LangGraph 工作流状态定义"""

    project_id: Annotated[str, Doc("项目ID")]
    """项目ID"""

    project_name: Annotated[str, Doc("项目名称")]
    """项目名称"""

    project_progress: Annotated[ProjectProgress, Doc("项目进度状态")]
    """项目进度状态"""

    new_file_list: Annotated[list[StateNewProjectFile], Doc("用户新上传的文件信息列表")]
    """用户新上传的文件信息列表"""

    project_file_list: Annotated[list[StateProjectFile], Doc("项目文件列表")]
    """项目文件列表（不含内容）"""

    requirement_outline: Annotated[str, Doc("需求大纲")]
    """需求大纲"""

    requirement_modules: Annotated[list[StateRequirementModule], Doc("需求模块")]
    """需求模块"""

    original_requirement: Annotated[str, Doc("原始需求文档内容")]
    """原始PRD内容"""

    optimized_requirement: Annotated[str, Doc("优化后需求文档内容")]
    """优化后PRD内容"""

    original_architecture: Annotated[str, Doc("原始架构设计")]
    """原始架构设计"""

    optimized_architecture: Annotated[str, Doc("优化后架构设计")]
    """优化后架构设计"""

    original_modules: Annotated[list[StateModule], Doc("原始模块设计")]
    """原始模块设计"""

    optimized_modules: Annotated[list[StateModule], Doc("优化后模块设计")]
    """优化后模块设计"""

    original_database: Annotated[str, Doc("原始数据库设计")]
    """原始数据库设计"""

    optimized_database: Annotated[str, Doc("优化后数据库设计")]
    """优化后数据库设计"""

    original_apis: Annotated[list[StateApi], Doc("原始系统接口设计")]
    """原始API设计"""

    optimized_apis: Annotated[list[StateApi], Doc("优化后系统接口设计")]
    """优化后API设计"""

    original_test_cases: Annotated[list[StateTestCase], Doc("原始测试用例设计")]
    """原始测试用例设计"""

    optimized_test_cases: Annotated[list[StateTestCase], Doc("优化后测试用例设计")]
    """优化后测试用例设计"""

    risks: Annotated[list[Issue], Doc("风险点")]
    """需要提给客户的风险点和建议（不设置reducer等子图覆盖）"""

    unclear_points: Annotated[list[Issue], Doc("不明确点")]
    """需要让用户明确的问题和建议（不设置reducer等子图覆盖）"""

    pm_next_step: Annotated[PMNextStep, Doc("PM下一步操作")]
    """下一步执行"""

    metadata: Annotated[dict[str, Any], Doc("元数据")]
    """元数据（可用于子图传参）"""

    private_messages: Annotated[list[AnyMessage], Doc("私聊记录")]
    """用于子图私聊（不设置reducer等子图覆盖）"""
