from typing import Any, Annotated
from typing_extensions import Doc
from langchain.messages import AnyMessage
from langgraph.graph import MessagesState

from src.enums.pm_next_step import PMNextStep
from src.enums.project_progress import ProjectProgress
from src.graphs.common.schemas import (
    StateApi,
    StateIssue,
    StateModule,
    StateTestCase,
    StateProjectFile,
    StateNewProjectFile,
    StateRequirementModule
)
from src.graphs.common.reduce import rewrite_reducer as wr


class State(MessagesState):
    """LangGraph 工作流状态定义"""

    history_summary: Annotated[str, Doc("会话历史摘要"), wr]
    """会话历史摘要"""

    project_id: Annotated[str, Doc("项目ID"), wr]
    """项目ID"""

    project_name: Annotated[str, Doc("项目名称"), wr]
    """项目名称"""

    project_progress: Annotated[ProjectProgress, Doc("项目进度状态"), wr]
    """项目进度状态"""

    new_file_list: Annotated[list[StateNewProjectFile], Doc("用户新上传的文件信息列表"), wr]
    """用户新上传的文件信息列表"""

    project_file_list: Annotated[list[StateProjectFile], Doc("项目文件列表"), wr]
    """项目文件列表（不含内容）"""

    requirement_outline: Annotated[str, Doc("需求大纲"), wr]
    """需求大纲"""

    requirement_modules: Annotated[list[StateRequirementModule], Doc("需求模块"), wr]
    """需求模块"""

    original_requirement: Annotated[str, Doc("原始需求文档内容"), wr]
    """原始PRD内容"""

    optimized_requirement: Annotated[str, Doc("当前需求文档内容"), wr]
    """优化后PRD内容"""

    original_architecture: Annotated[str, Doc("原始架构设计"), wr]
    """原始架构设计"""

    optimized_architecture: Annotated[str, Doc("当前架构设计"), wr]
    """优化后架构设计"""

    original_modules: Annotated[list[StateModule], Doc("原始模块设计"), wr]
    """原始模块设计"""

    optimized_modules: Annotated[list[StateModule], Doc("当前模块设计"), wr]
    """优化后模块设计"""

    original_database: Annotated[str, Doc("原始数据库设计"), wr]
    """原始数据库设计"""

    optimized_database: Annotated[str, Doc("当前数据库设计"), wr]
    """优化后数据库设计"""

    original_apis: Annotated[list[StateApi], Doc("原始系统接口设计"), wr]
    """原始API设计"""

    optimized_apis: Annotated[list[StateApi], Doc("当前系统接口设计"), wr]
    """优化后API设计"""

    original_test_cases: Annotated[list[StateTestCase], Doc("原始测试用例设计"), wr]
    """原始测试用例设计"""

    optimized_test_cases: Annotated[list[StateTestCase], Doc("当前测试用例设计"), wr]
    """优化后测试用例设计"""

    risks: Annotated[list[StateIssue], Doc("风险点"), wr]
    """需要提给客户的风险点和建议（重写reducer等子图覆盖）"""

    unclear_points: Annotated[list[StateIssue], Doc("不明确点"), wr]
    """需要让用户明确的问题和建议（重写reducer等子图覆盖）"""

    metadata: Annotated[dict[str, Any], Doc("元数据"), wr]
    """元数据（可用于子图传参）"""

    private_risks: Annotated[list[StateIssue], wr]
    """子图内部需要提给客户的风险点和建议（不设置reducer等子图覆盖）"""

    private_unclear_points: Annotated[list[StateIssue], wr]
    """子图内部需要让用户明确的问题和建议（不设置reducer等子图覆盖）"""

    private_messages: Annotated[list[AnyMessage], Doc("私聊记录"), wr]
    """用于子图私聊（不设置reducer等子图覆盖）"""

    pm_next_step: Annotated[PMNextStep, Doc("PM下一步操作"), wr]
    """下一步执行"""

    node_rollback: Annotated[bool, Doc("节点回滚"), wr]
    """节点回滚重新执行某个操作"""
