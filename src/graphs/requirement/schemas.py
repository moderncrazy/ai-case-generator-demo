from pydantic import BaseModel, Field

from src.graphs.schemas import Issue


class ProductOptimizePRDOutput(BaseModel):
    """产品优化PRD输出"""
    message: str = Field(description="针对PRD优化的总结以及给团队成员接下来review的留言")
    requirement_content: str = Field(description="输出优化后PRD内容")
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")


class ProductOptimizeIssueOutput(BaseModel):
    """产品优化风险和问题输出"""
    message: str = Field(description="给客户的会话")
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")


class ReviewPRDOutput(BaseModel):
    """项目成员审查PRD输出"""
    requirement_issue: list[Issue] = Field(description="针对PRD提出的问题和建议方案")
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")
