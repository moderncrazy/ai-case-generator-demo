from typing import Any, Optional
from pydantic import BaseModel, Field

from src.enums.pm_next_step import PMNextStep


class FileSummaryOutput(BaseModel):
    """文件摘要输出模型
    
    LLM 提取的文件摘要结果。
    """
    summary: str = Field(description="文件摘要内容", min_length=1)
    """摘要文本"""


class Metadata(BaseModel):
    """状态元数据结构

    状态元数据结构，常用于主图和子图间的传值
    """
    module: Optional[str] = Field(default=None, description="若需要修改需求模块时传递的需求模块名称")
    """模块名称（需求模块使用）"""
    generate_optimization_plan: bool = Field(description="调用子图优化文档时，是否需要先生成优化方案")
    """子图流程是否需要生成优化方案"""


class PMOutput(BaseModel):
    """产品经理输出模型
    
    PM 决策的结构化输出。
    """
    next_step: PMNextStep = Field(default=PMNextStep.END, description="下一步要做的事情，参考PMNextStep枚举类")
    """下一步操作决策"""
    message: str = Field(description="给客户的回话，或者给下一步任务的指示", min_length=1)
    """回复消息内容"""
    metadata: Metadata = Field(description="元数据信息")
    """额外元数据"""
