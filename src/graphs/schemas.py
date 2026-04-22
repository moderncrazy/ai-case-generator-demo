from typing import Any
from pydantic import BaseModel, Field

from src.enums.pm_next_step import PMNextStep


class FileSummaryOutput(BaseModel):
    """文件摘要输出模型
    
    LLM 提取的文件摘要结果。
    """
    summary: str = Field(description="文件摘要内容", min_length=1)
    """摘要文本"""


class PMOutput(BaseModel):
    """产品经理输出模型
    
    PM 决策的结构化输出。
    """
    next_step: PMNextStep = Field(default=PMNextStep.END, description="下一步要做的事情，参考PMNextStep枚举类")
    """下一步操作决策"""
    message: str = Field(description="给客户的回话，或者给下一步任务的指示", min_length=1)
    """回复消息内容"""
    metadata: dict[str, Any] = Field(default={}, description="元数据，默认为空")
    """额外元数据"""
