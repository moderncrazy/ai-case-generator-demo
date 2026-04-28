from typing import Optional
from pydantic import BaseModel, Field

from src.graphs.common.schemas import OptimizeDocBaseOutput


class SystemModule(BaseModel):
    id: str = Field(description="模块Id，默认自动生成", min_length=1)
    name: str = Field(description="模块名称", min_length=1)
    parent_id: Optional[str] = Field(default=None, description="当前模块若为顶级模块则为None，否则为直接父级模块Id")
    description: str = Field(description="模块描述", min_length=1)


class OptimizeSystemModuleOutput(OptimizeDocBaseOutput):
    """架构优化系统模块输出"""
    system_modules: list[SystemModule] = Field(description="输出优化后系统模块列表", min_length=1)
