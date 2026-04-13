from pydantic import BaseModel, Field


class RequirementModuleCreate(BaseModel):
    name: str = Field(description="模块名称", min_length=1)
    order: int = Field(description="序号")
    description: str = Field(description="模块描述（功能定位、核心页面等）", min_length=1)


class OptimizeRequirementOutlineOutput(BaseModel):
    """优化需求大纲输出"""
    message: str = Field(description="针对需求大纲优化的总结以及给客户的回复", min_length=1)
    requirement_outline: str = Field(description="输出优化后需求大纲", min_length=1)
    requirement_modules: list[RequirementModuleCreate] = Field(description="输出需求模块列表", min_length=1)
