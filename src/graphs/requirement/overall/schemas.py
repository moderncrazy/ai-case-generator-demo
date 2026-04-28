from pydantic import Field

from src.graphs.common.schemas import OptimizeDocToSummarizeBaseOutput


class OptimizeRequirementOverallOutput(OptimizeDocToSummarizeBaseOutput):
    """产品优化需求文档输出"""
    requirement_overall_content: str = Field(description="输出优化后需求文档内容", min_length=1)
