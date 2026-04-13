from pydantic import BaseModel, Field

from src.graphs.schemas import Issue


class OptimizeSystemArchitectureOutput(BaseModel):
    """架构优化系统架构输出"""
    message: str = Field(description="针对系统架构优化的总结以及给团队成员接下来review的留言", min_length=1)
    system_architecture_content: str = Field(description="输出优化后系统架构内容", min_length=1)
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")


class ReviewSystemArchitectureOutput(BaseModel):
    """项目成员审查系统架构输出"""
    system_architecture_issues: list[Issue] = Field(description="针对系统架构提出的问题和建议方案")
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")


class OptimizeSystemArchitectureIssueOutput(BaseModel):
    """架构优化风险和问题输出"""
    message: str = Field(description="给客户的会话", min_length=1)
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")
