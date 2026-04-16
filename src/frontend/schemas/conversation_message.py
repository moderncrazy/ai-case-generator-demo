from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

from src.frontend.enums.conversation_role import ConversationRole
from src.frontend.enums.http_method import HttpMethod
from src.frontend.enums.http_param_type import HttpParamType
from src.frontend.enums.requirement_module_status import RequirementModuleStatus
from src.frontend.enums.test_case_level import TestCaseLevel
from src.frontend.enums.test_case_type import TestCaseType


class ConversationMessage(BaseModel):
    """对话消息响应"""
    id: str = Field(description="对话ID")
    role: ConversationRole = Field(description="角色: user/assistant/system")
    content: str = Field(description="消息内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class ContextRequirementModule(BaseModel):
    """需求模块"""
    name: str = Field(description="模块名称")
    order: int = Field(description="排序序号")
    status: RequirementModuleStatus = Field(description="模块状态")
    description: str = Field(description="模块描述")
    content: Optional[str] = Field(default=None, description="模块内容")


class ContextApiRequestParam(BaseModel):
    """API 请求参数字段"""
    name: str = Field(description="参数字段名")
    type: HttpParamType = Field(description="参数类型")
    required: bool = Field(description="是否必填")
    description: str = Field(description="参数描述")


class ContextApi(BaseModel):
    """API 接口定义"""
    id: str = Field(description="API ID")
    module_id: str = Field(description="所属模块ID")
    name: str = Field(description="API 名称")
    method: HttpMethod = Field(description="请求方法")
    path: str = Field(description="API 路径")
    description: Optional[str] = Field(default=None, description="API 描述")
    request_headers: Optional[list[ContextApiRequestParam]] = Field(default=None, description="请求头参数")
    request_params: Optional[list[ContextApiRequestParam]] = Field(default=None, description="URL 参数")
    request_body: Optional[list[ContextApiRequestParam]] = Field(default=None, description="请求体参数")
    response_schema: str = Field(description="响应格式")
    test_script: Optional[str] = Field(default=None, description="测试脚本")


class ContextTestCase(BaseModel):
    """测试用例定义"""
    id: Optional[str] = Field(default=None, description="测试用例ID")
    module_id: str = Field(description="所属模块ID")
    title: str = Field(description="用例标题")
    precondition: Optional[str] = Field(default=None, description="前置条件")
    test_steps: str = Field(description="测试步骤")
    expected_result: str = Field(description="预期结果")
    test_data: str = Field(description="测试数据")
    level: TestCaseLevel = Field(description="用例类型")
    type: TestCaseType = Field(description="用例等级")


class ContextIssue(BaseModel):
    """风险点或疑问"""
    content: str = Field(description="问题描述", min_length=1)
    propose: str = Field(description="建议方案", min_length=1)


class ModuleTreeNode(BaseModel):
    """模块树节点"""
    id: str = Field(description="模块ID")
    parent_id: Optional[str] = Field(default=None, description="父模块ID")
    name: str = Field(description="模块名称")
    description: Optional[str] = Field(default=None, description="模块描述")
    children: list["ModuleTreeNode"] = Field(default_factory=list, description="子模块")


class ApiModuleTree(BaseModel):
    """API 模块树"""
    module_id: str = Field(description="模块ID")
    module_name: str = Field(description="模块名称")
    apis: list[ContextApi] = Field(default_factory=list, description="API 列表")
    children: list["ApiModuleTree"] = Field(default_factory=list, description="子模块")


class TestCaseModuleTree(BaseModel):
    """测试用例模块树"""
    module_id: str = Field(description="模块ID")
    module_name: str = Field(description="模块名称")
    test_cases: list[ContextTestCase] = Field(default_factory=list, description="测试用例列表")
    children: list["TestCaseModuleTree"] = Field(default_factory=list, description="子模块")


class ConversationContext(BaseModel):
    """对话上下文响应"""
    project_progress: str = Field(description="项目进度状态")
    requirement_outline: Optional[str] = Field(default=None, description="需求大纲")
    requirement_modules: Optional[list[ContextRequirementModule]] = Field(default=None, description="需求模块")
    original_requirement: Optional[str] = Field(default=None, description="原始需求")
    optimized_requirement: Optional[str] = Field(default=None, description="优化后需求")
    original_architecture: Optional[str] = Field(default=None, description="原始架构")
    optimized_architecture: Optional[str] = Field(default=None, description="优化后架构")
    original_modules_tree: Optional[list[ModuleTreeNode]] = Field(default=None, description="原始模块树")
    optimized_modules_tree: Optional[list[ModuleTreeNode]] = Field(default=None, description="优化后模块树")
    original_database: Optional[str] = Field(default=None, description="原始数据库")
    optimized_database: Optional[str] = Field(default=None, description="优化后数据库")
    original_apis_tree: Optional[list[ApiModuleTree]] = Field(default=None, description="原始API树")
    optimized_apis_tree: Optional[list[ApiModuleTree]] = Field(default=None, description="优化后API树")
    original_test_cases_tree: Optional[list[TestCaseModuleTree]] = Field(default=None, description="原始测试用例树")
    optimized_test_cases_tree: Optional[list[TestCaseModuleTree]] = Field(default=None, description="优化后测试用例树")
    risks: Optional[list[ContextIssue]] = Field(default=None, description="风险点")
    unclear_points: Optional[list[ContextIssue]] = Field(default=None, description="不明确的问题")


class ConversationMessageResponse(BaseModel):
    """对话消息响应"""
    message: ConversationMessage = Field(description="对话消息")
    context: Optional[ConversationContext] = Field(default=None, description="对话上下文")
