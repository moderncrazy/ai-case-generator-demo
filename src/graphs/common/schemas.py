import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import TypedDict, Optional

from src.enums.http_method import HttpMethod
from src.enums.test_case_type import TestCaseType
from src.enums.http_param_type import HttpParamType
from src.enums.test_case_level import TestCaseLevel
from src.enums.group_member_role import GroupMemberRole
from src.enums.requirement_module_status import RequirementModuleStatus
from src.enums.conversation_message_type import ConversationMessageType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult


class StateNewProjectFile(TypedDict):
    """新上传项目文件状态结构
    
    用户上传但尚未入库的文件信息。
    """
    id: Optional[str]
    """文件ID（入库后生成）"""
    conversation_message_id: str
    """关联的对话消息ID"""
    name: str
    """文件名"""
    path: str
    """文件路径"""
    type: str
    """文件类型"""
    size: int
    """文件大小（字节）"""
    content: Optional[str]
    """文件内容（OCR解析后）"""
    summary: Optional[str]
    """文件摘要"""
    created_at: Optional[datetime]
    """创建时间"""


class StateProjectFile(TypedDict):
    """项目文件状态结构
    
    已入库的项目文件信息（不含内容）。
    """
    id: str
    """文件唯一标识"""
    conversation_message_id: str
    """关联的对话消息ID"""
    name: str
    """文件名"""
    path: str
    """文件路径"""
    type: str
    """文件类型"""
    size: int
    """文件大小（字节）"""
    summary: str
    """文件摘要"""
    created_at: datetime
    """创建时间"""


class StateRequirementModule(TypedDict):
    """需求模块状态结构
    
    需求大纲下的功能模块定义。
    """
    name: str
    """模块名称"""
    order: int
    """模块序号"""
    status: RequirementModuleStatus
    """模块状态（待处理/进行中/已完成）"""
    description: str
    """模块描述"""
    content: Optional[str]
    """模块详细内容"""


class StateModule(TypedDict):
    """系统模块状态结构
    
    系统架构中的功能模块定义。
    """
    id: str
    """模块唯一标识"""
    parent_id: Optional[str]
    """父模块ID（顶级模块为空）"""
    name: str
    """模块名称"""
    description: Optional[str]
    """模块描述"""


class StateApiRequestParam(TypedDict):
    """API请求参数状态结构
    
    API接口的单个请求参数定义。
    """
    name: str
    """参数名称"""
    type: HttpParamType
    """参数类型（string/number/boolean/object/array）"""
    required: bool
    """是否必传"""
    description: str
    """参数描述"""


class StateApi(TypedDict):
    """API状态结构
    
    系统接口定义。
    """
    id: str
    """接口唯一标识"""
    module_id: str
    """所属模块ID"""
    name: str
    """接口名称"""
    method: HttpMethod
    """HTTP方法（GET/POST/PUT/DELETE等）"""
    path: str
    """接口路径"""
    description: Optional[str]
    """接口描述"""
    request_headers: Optional[list[StateApiRequestParam]]
    """请求头参数"""
    request_params: Optional[list[StateApiRequestParam]]
    """URL查询参数"""
    request_body: Optional[list[StateApiRequestParam]]
    """请求体参数"""
    response_schema: str
    """响应结构定义"""
    test_script: Optional[str]
    """测试脚本"""


class StateTestCase(TypedDict):
    """测试用例状态结构
    
    功能测试用例定义。
    """
    id: Optional[str]
    """用例ID（入库后生成）"""
    module_id: str
    """所属模块ID"""
    title: str
    """用例标题"""
    precondition: Optional[str]
    """前置条件"""
    test_steps: str
    """测试步骤"""
    expected_result: str
    """预期结果"""
    test_data: str
    """测试数据"""
    level: TestCaseLevel
    """用例等级（P0/P1/P2/P3）"""
    type: TestCaseType
    """用例类型（功能测试/接口测试/性能测试等）"""


class StateIssue(TypedDict):
    """问题状态结构
    
    评审中发现的问题或风险点。
    """
    id: str
    """问题Id"""
    content: str
    """问题描述"""
    propose: str
    """建议方案"""


class CustomMessage(BaseModel):
    """自定义消息结构（用于流式输出）
    
    前端展示用的进度提示消息。
    """
    type: ConversationMessageType = Field(description="消息类型")
    """消息类型"""

    role: GroupMemberRole = Field(description="发送消息的角色")
    """发送消息的角色"""

    message: str = Field(description="消息内容")
    """提示消息内容"""


class Issue(BaseModel):
    """问题模型
    
    结构化的问题描述和建议方案
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="问题默认生成")
    """问题Id"""
    content: str = Field(description="问题描述", min_length=1)
    """问题描述内容"""
    propose: str = Field(description="针对该问题的建议方案", min_length=1)
    """建议方案内容"""


class OptimizeDocBaseOutput(BaseModel):
    """优化文档输出基类"""
    message: str = Field(description="针对优化内容的总结以及给团队成员接下来review的留言", min_length=1)


class OptimizeDocToSummarizeBaseOutput(OptimizeDocBaseOutput):
    """优化文档输出基类"""
    risks: Optional[list[Issue]] = Field(default=[], description="给客户提出的风险和建议方案")
    unclear_points: Optional[list[Issue]] = Field(default=[], description="需求中不明确的问题和建议方案")


class ReviewOptimizationDocOutput(BaseModel):
    """项目成员审查优化内容输出"""
    review_issues: list[Issue] = Field(description="针对优化内容提出的问题和建议方案")


class ReviewOptimizationDocToSummarizeOutput(ReviewOptimizationDocOutput):
    """项目成员审查优化内容输出"""
    risks: Optional[list[Issue]] = Field(default=[], description="给客户提出的风险和建议方案")
    unclear_points: Optional[list[Issue]] = Field(default=[], description="需求中不明确的问题和建议方案")


class SummarizeOptimizationDocIssueOutput(BaseModel):
    """总结优化风险和问题输出"""
    message: str = Field(description="给客户的回话", min_length=1)
    risks: Optional[list[Issue]] = Field(default=[], description="给客户提出的风险和建议方案")
    unclear_points: Optional[list[Issue]] = Field(default=[], description="需求中不明确的问题和建议方案")


class GenerateOptimizationPlanOutput(BaseModel):
    """优化方案输出"""
    background: str = Field(description="业务背景（项目名称、业务描述、用户诉求）", min_length=1)
    summary: str = Field(description="本次优化的整体说明", min_length=1)
    logic: str = Field(description="方案的逻辑链路，解释为什么这么做", min_length=1)
    steps: list[str] = Field(description="具体的操作步骤，一个步骤一条", min_length=1)
    questions: Optional[list[str]] = Field(default=[], description="设计方案过程中对不明确的点提出的问题")
    risks: Optional[list[str]] = Field(default=[], description="方案中可能存在的潜在风险")


class ReviewOptimizationPlanOutput(BaseModel):
    """审核优化方案输出"""
    result: ReviewOptimizationPlanResult = Field(description="审核结果，approve/revise/ask_question")
    message: str = Field(description="针对方案审核的回复/背景补充/向人类发起提问的背景描述", min_length=1)
    issues: Optional[list[Issue]] = Field(default=[], description="针对优化方案提出的反馈/向人类发起的提问")
