import uuid
from typing import Optional
from pydantic import BaseModel, Field

from src.graphs.schemas import Issue


class SystemModule(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="模块Id，默认自动生成",
                              min_length=1)
    name: str = Field(description="模块名称", min_length=1)
    parent_id: Optional[str] = Field(default=None, description="当前模块若为顶级模块则为None，否则为直接父级模块Id")
    description: str = Field(description="模块描述", min_length=1)


class OptimizeSystemModuleOutput(BaseModel):
    """架构优化系统模块输出"""
    message: str = Field(description="针对系统模块优化的总结以及给团队成员接下来review的留言", min_length=1)
    system_modules: list[SystemModule] = Field(description="输出优化后系统模块列表", min_length=1)


class ReviewSystemModuleOutput(BaseModel):
    """项目成员审查系统模块输出"""
    system_module_issues: list[Issue] = Field(description="针对系统模块提出的问题和建议方案")
