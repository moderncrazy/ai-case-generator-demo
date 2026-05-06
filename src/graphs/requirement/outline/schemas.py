from pydantic import BaseModel, Field

from src.graphs.common.schemas.output_schemas import OptimizeDocBaseOutput


class RequirementModuleCreate(BaseModel):
    name: str = Field(description="模块名称", min_length=1)
    order: int = Field(description="序号")
    description: str = Field(description="模块描述（功能定位、核心能力等）", min_length=1)


class OptimizeDocOutput(OptimizeDocBaseOutput):
    """优化需求大纲输出"""
    requirement_outline: str = Field(description="输出优化后需求大纲", min_length=1)
    requirement_modules: list[RequirementModuleCreate] = Field(description="输出需求模块列表", min_length=1)
