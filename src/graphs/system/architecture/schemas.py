from pydantic import Field

from src.graphs.common.schemas import OptimizeDocToSummarizeBaseOutput


class OptimizeSystemArchitectureOutput(OptimizeDocToSummarizeBaseOutput):
    """架构优化系统架构输出"""
    system_architecture_content: str = Field(description="输出优化后系统架构内容", min_length=1)
