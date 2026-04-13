from pydantic import BaseModel, Field

from src.graphs.schemas import Issue


class OptimizeRequirementModuleOutput(BaseModel):
    """产品优化需求模块输出"""
    message: str = Field(description="针对需求模块优化的总结以及给团队成员接下来review的留言", min_length=1)
    requirement_module_content: str = Field(description="输出优化后需求模块内容", min_length=1)
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")


class ReviewRequirementModuleOutput(BaseModel):
    """项目成员审查需求模块输出"""
    requirement_module_issues: list[Issue] = Field(description="针对需求模块提出的问题和建议方案")
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")


class OptimizeRequirementModuleIssueOutput(BaseModel):
    """产品优化风险和问题输出"""
    message: str = Field(description="给客户的会话", min_length=1)
    risks: list[Issue] = Field(description="给客户提出的风险和建议方案")
    unclear_points: list[Issue] = Field(description="需求中不明确的问题和建议方案")
