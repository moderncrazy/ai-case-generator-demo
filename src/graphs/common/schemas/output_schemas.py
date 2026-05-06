import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import TypedDict, Optional

from src.enums.filtrate_optimization_doc_review_issue_result import FiltrateOptimizationDocReviewIssueResult
from src.enums.http_method import HttpMethod
from src.enums.pm_review_optimization_doc_result import PMReviewOptimizationDocResult
from src.enums.test_case_type import TestCaseType
from src.enums.http_param_type import HttpParamType
from src.enums.test_case_level import TestCaseLevel
from src.enums.group_member_role import GroupMemberRole
from src.enums.requirement_module_status import RequirementModuleStatus
from src.enums.conversation_message_type import ConversationMessageType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult


class Issue(BaseModel):
    """问题模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="问题默认生成")
    """问题Id"""
    content: str = Field(description="问题描述", min_length=1)
    """问题描述内容"""
    propose: str = Field(description="针对该问题的建议方案", min_length=1)
    """建议方案内容"""


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


class OptimizeDocBaseOutput(BaseModel):
    """优化文档输出基类"""
    message: str = Field(description="针对优化内容的总结以及给团队成员接下来review的留言", min_length=1)


class OptimizeDocBringRiskBaseOutput(OptimizeDocBaseOutput):
    """优化文档输出基类"""
    risks: Optional[list[Issue]] = Field(default=[], description="给客户提出的风险和建议方案")
    unclear_points: Optional[list[Issue]] = Field(default=[], description="需求中不明确的问题和建议方案")


class ReviewOptimizationDocOutput(BaseModel):
    """项目成员审查优化内容输出"""
    review_issues: Optional[list[Issue]] = Field(default=[], description="针对优化内容提出的问题和建议方案")


class ReviewOptimizationDocBringRiskOutput(ReviewOptimizationDocOutput):
    """项目成员审查优化内容输出"""
    risks: Optional[list[Issue]] = Field(default=[], description="给客户提出的风险和建议方案")
    unclear_points: Optional[list[Issue]] = Field(default=[], description="需求中不明确的问题和建议方案")


class PMReviewOptimizationDocOutput(ReviewOptimizationDocOutput):
    """产品经理审查优化内容输出"""
    result: PMReviewOptimizationDocResult = Field(description="PM审核结果pass/revise/group_member_review")
    message: str = Field(description="给客户/设计人员/审核团队的话", min_length=1)
    review_roles: list[GroupMemberRole] = Field(default=[], description="审核角色列表")


class PMReviewOptimizationDocBringRiskOutput(PMReviewOptimizationDocOutput):
    """产品经理审查优化内容输出"""
    risks: Optional[list[Issue]] = Field(default=[], description="给客户提出的风险和建议方案")
    unclear_points: Optional[list[Issue]] = Field(default=[], description="需求中不明确的问题和建议方案")


class FiltrateOptimizationDocReviewIssueOutput(ReviewOptimizationDocOutput):
    """过滤筛选优化文档审核问题输出"""
    result: FiltrateOptimizationDocReviewIssueResult = Field(description="筛选文档优化审核问题结果pass/revise")
    message: str = Field(description="给客户的回话", min_length=1)


class FiltrateOptimizationDocReviewIssueBringRiskOutput(FiltrateOptimizationDocReviewIssueOutput):
    """总结优化风险和问题输出"""
    risks: Optional[list[Issue]] = Field(default=[], description="给客户提出的风险和建议方案")
    unclear_points: Optional[list[Issue]] = Field(default=[], description="需求中不明确的问题和建议方案")
