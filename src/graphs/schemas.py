from datetime import datetime
from langchain.tools import InjectedToolArg
from pydantic import BaseModel, Field, SkipValidation
from typing import TypedDict, Optional, Any, Annotated

from src.enums.http_method import HttpMethod
from src.enums.pm_next_step import PMNextStep
from src.enums.test_case_type import TestCaseType
from src.enums.test_case_level import TestCaseLevel
from src.enums.project_progress import ProjectProgress


class StateNewProjectFile(TypedDict):
    id: Optional[str]
    conversation_message_id: str
    name: str
    path: str
    type: str
    size: int
    content: Optional[str]
    summary: Optional[str]
    created_at: Optional[datetime]


class StateProjectFile(TypedDict):
    id: str
    conversation_message_id: str
    name: str
    path: str
    type: str
    size: int
    summary: str
    created_at: datetime


class StateModule(TypedDict):
    id: Optional[str]
    project_id: str
    parent_id: Optional[str]
    name: str
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class StateApi(TypedDict):
    id: Optional[str]
    project_id: str
    module_id: Optional[str]
    name: str
    method: HttpMethod
    path: str
    description: Optional[str]
    request_params: str
    request_body: str
    response_schema: str
    test_script: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class StateTestCase(TypedDict):
    id: Optional[str]
    project_id: str
    module_id: Optional[str]
    title: str
    precondition: Optional[str]
    test_steps: str
    expected_result: str
    test_data: str
    level: TestCaseType
    type: TestCaseLevel
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class CustomMessage(TypedDict):
    message: str


class Issue(BaseModel):
    content: str = Field(description="问题描述")
    propose: str = Field(description="针对该问题的建议方案")


class FileSummaryOutput(BaseModel):
    summary: str = Field(description="文件摘要内容")


class PMOutput(BaseModel):
    next_step: PMNextStep = Field(default=PMNextStep.END, description="下一步要做的事情，参考PMNextStep枚举类")
    message: str = Field(description="给客户的回话，或者给下一步任务的指示")


class PresentProjectInfo(BaseModel):
    project_id: str = Field(description="项目ID")
    project_name: str = Field(description="项目名称")
    project_progress: ProjectProgress = Field(description="项目进度状态")
    project_file_list: list[StateProjectFile] = Field(default=[], description="项目文件列表")
    original_requirement: str = Field(default="", description="原始需求文档内容")
    optimized_requirement: str = Field(default="", description="优化后的需求文档内容")
    original_architecture: str = Field(default="", description="原始架构设计文档")
    optimized_architecture: str = Field(default="", description="优化后的架构设计文档")
    original_database: str = Field(default="", description="原始数据库设计文档")
    optimized_database: str = Field(default="", description="优化后的数据库设计文档")
    original_modules: list[StateModule] = Field(default=[], description="原始模块结构列表")
    optimized_modules: list[StateModule] = Field(default=[], description="优化后的模块结构列表")
    original_apis: list[StateApi] = Field(default=[], description="原始接口列表")
    optimized_apis: list[StateApi] = Field(default=[], description="优化后的接口列表")
    original_test_cases: list[StateTestCase] = Field(default=[], description="原始测试用例列表")
    optimized_test_cases: list[StateTestCase] = Field(default=[], description="优化后的测试用例列表")
    risks: list[Issue] = Field(default=[], description="识别的风险列表")
    unclear_points: list[Issue] = Field(default=[], description="不明确的问题点列表")
