from pydantic import Field

from src.graphs.common.schemas.output_schemas import OptimizeDocBaseOutput


class OptimizeDocOutput(OptimizeDocBaseOutput):
    """DBA优化系统数据库文档输出"""
    system_database_content: str = Field(description="输出优化后系统数据库文档内容", min_length=1)
