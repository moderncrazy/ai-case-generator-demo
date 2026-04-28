from pydantic import Field

from src.graphs.common.schemas import OptimizeDocToSummarizeBaseOutput


class OptimizeRequirementModuleOutput(OptimizeDocToSummarizeBaseOutput):
    """产品优化需求模块输出"""
    requirement_module_content: str = Field(description="输出优化后需求模块内容", min_length=1)
