from datetime import datetime
from langchain.tools import InjectedToolArg
from pydantic import BaseModel, Field, SkipValidation
from typing import TypedDict, Optional, Any, Annotated

from src.enums.http_method import HttpMethod
from src.enums.pm_next_step import PMNextStep
from src.enums.test_case_type import TestCaseType
from src.enums.http_param_type import HttpParamType
from src.enums.test_case_level import TestCaseLevel
from src.enums.project_progress import ProjectProgress
from src.enums.requirement_module_status import RequirementModuleStatus


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


class StateRequirementModule(TypedDict):
    name: str
    order: int
    status: RequirementModuleStatus
    description: str
    content: Optional[str]


class StateModule(TypedDict):
    id: str
    parent_id: Optional[str]
    name: str
    description: Optional[str]


class StateApiRequestParam(TypedDict):
    name: str
    type: HttpParamType
    required: bool
    description: str


class StateApi(TypedDict):
    id: str
    module_id: str
    name: str
    method: HttpMethod
    path: str
    description: Optional[str]
    request_headers: Optional[StateApiRequestParam]
    request_params: Optional[StateApiRequestParam]
    request_body: Optional[StateApiRequestParam]
    response_schema: str
    test_script: Optional[str]


class StateTestCase(TypedDict):
    id: Optional[str]
    module_id: str
    title: str
    precondition: Optional[str]
    test_steps: str
    expected_result: str
    test_data: str
    level: TestCaseType
    type: TestCaseLevel


class CustomMessage(TypedDict):
    message: str


class Issue(BaseModel):
    content: str = Field(description="问题描述", min_length=1)
    propose: str = Field(description="针对该问题的建议方案", min_length=1)


class FileSummaryOutput(BaseModel):
    summary: str = Field(description="文件摘要内容", min_length=1)


class PMOutput(BaseModel):
    next_step: PMNextStep = Field(default=PMNextStep.END, description="下一步要做的事情，参考PMNextStep枚举类")
    message: str = Field(description="给客户的回话，或者给下一步任务的指示", min_length=1)
    metadata: dict[str, Any] = Field(default={}, description="元数据，默认为空")
