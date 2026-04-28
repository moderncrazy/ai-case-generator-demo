from typing import Optional, List
from pydantic import BaseModel, Field

from src.frontend.enums.requirement_module_status import RequirementModuleStatus


class ContextIssue(BaseModel):
    """风险点或疑问"""
    content: str = Field(description="问题描述")
    propose: str = Field(description="建议方案")


class ContextRequirementModule(BaseModel):
    """需求模块"""
    name: str = Field(description="模块名称")
    order: int = Field(description="排序序号")
    status: RequirementModuleStatus = Field(description="模块状态")
    description: str = Field(description="模块描述")
    content: Optional[str] = Field(default=None, description="模块内容")


class RequirementModulesResponse(BaseModel):
    """需求模块响应"""
    modules: Optional[List[ContextRequirementModule]] = Field(default=None, description="需求模块列表")


class TextDocumentResponse(BaseModel):
    """文本文档响应"""
    content: Optional[str] = Field(None, description="文本文档")


class CompareTextDocumentResponse(BaseModel):
    """对比文本文档响应（原始版和优化版）"""
    original: Optional[str] = Field(None, description="原始版本")
    optimized: Optional[str] = Field(None, description="优化版本")


class IssuesResponse(BaseModel):
    """风险点和疑问响应"""
    risks: List[ContextIssue] = Field(default_factory=list, description="风险点列表")
    unclear_points: List[ContextIssue] = Field(default_factory=list, description="疑问列表")
