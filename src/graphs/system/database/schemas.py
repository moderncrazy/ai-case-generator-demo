from pydantic import BaseModel, Field

from src.graphs.common.schemas import Issue


class OptimizeSystemDatabaseOutput(BaseModel):
    """DBA优化系统数据库文档输出"""
    message: str = Field(description="针对系统数据库文档优化的总结以及给团队成员接下来review的留言", min_length=1)
    system_database_content: str = Field(description="输出优化后系统数据库文档内容", min_length=1)


class ReviewSystemDatabaseOutput(BaseModel):
    """项目成员审查系统数据库文档输出"""
    system_database_issues: list[Issue] = Field(description="针对系统数据库文档提出的问题和建议方案")

