import orjson

from src.models.business.project import Project
from src.schemas.project_document import (
    ContextIssue,
    ContextRequirementModule,
    IssuesResponse,
    TextDocumentResponse,
    RequirementModulesResponse,
    CompareTextDocumentResponse,
)
from src.agents.main_agent import main_agent


class ProjectDocumentService:
    """项目文档服务
    
    提供项目各类文档的获取功能。
    """

    @staticmethod
    async def get_requirement_outline(project: Project) -> TextDocumentResponse:
        """获取需求大纲
        
        Args:
            project: 项目对象
            
        Returns:
            需求大纲响应
        """
        return TextDocumentResponse(content=project.requirement_outline_design)

    @staticmethod
    async def get_requirement_modules(project: Project) -> RequirementModulesResponse:
        """获取需求模块
        
        Args:
            project: 项目对象
            
        Returns:
            需求模块响应
        """
        if not project.requirement_module_design:
            return RequirementModulesResponse(modules=None)

        # 解析 JSON 格式的需求模块
        modules = [ContextRequirementModule.model_validate(m) for m in orjson.loads(project.requirement_module_design)]
        return RequirementModulesResponse(modules=modules)

    @staticmethod
    async def get_requirement_overall(project: Project) -> TextDocumentResponse:
        """获取需求整体文档

        Args:
            project: 项目对象

        Returns:
            需求整体文档响应
        """
        state = await main_agent.get_state(project.id)
        return TextDocumentResponse(
            content=project.requirement_overall_design
        )

    @staticmethod
    async def get_requirement_overall_compare(project: Project) -> CompareTextDocumentResponse:
        """对比需求整体文档
        
        Args:
            project: 项目对象
            
        Returns:
            需求整体文档响应
        """
        state = await main_agent.get_state(project.id)
        return CompareTextDocumentResponse(
            original=state.get("original_requirement") if state else None,
            optimized=state.get("optimized_requirement") if state else None
        )

    @staticmethod
    async def get_architecture(project: Project) -> TextDocumentResponse:
        """获取架构设计文档

        Args:
            project: 项目对象

        Returns:
            架构设计文档响应
        """
        state = await main_agent.get_state(project.id)
        return TextDocumentResponse(
            content=project.architecture_design
        )

    @staticmethod
    async def get_architecture_compare(project: Project) -> CompareTextDocumentResponse:
        """对比架构设计文档
        
        Args:
            project: 项目对象
            
        Returns:
            架构设计文档响应
        """
        state = await main_agent.get_state(project.id)
        return CompareTextDocumentResponse(
            original=state.get("original_architecture") if state else None,
            optimized=state.get("optimized_architecture") if state else None
        )

    @staticmethod
    async def get_database(project: Project) -> TextDocumentResponse:
        """获取数据库设计文档

        Args:
            project: 项目对象

        Returns:
            数据库设计文档响应
        """
        state = await main_agent.get_state(project.id)
        return TextDocumentResponse(
            content=project.database_design
        )

    @staticmethod
    async def get_database_compare(project: Project) -> CompareTextDocumentResponse:
        """获取数据库设计文档
        
        Args:
            project: 项目对象
            
        Returns:
            数据库设计文档响应
        """
        state = await main_agent.get_state(project.id)
        return CompareTextDocumentResponse(
            original=state.get("original_database") if state else None,
            optimized=state.get("optimized_database") if state else None
        )

    @staticmethod
    async def get_issues(project: Project) -> IssuesResponse:
        """获取风险点和疑问
        
        Args:
            project: 项目对象
            
        Returns:
            风险点和疑问响应
        """
        state = await main_agent.get_state(project.id)
        if not state:
            return IssuesResponse()

        # 解析 risks
        risks_data = state.get("risks") or []
        risks = [ContextIssue.model_validate(r) for r in risks_data] if isinstance(risks_data, list) else []

        # 解析 unclear_points
        unclear_data = state.get("unclear_points") or []
        unclear_points = [ContextIssue.model_validate(u) for u in unclear_data] if isinstance(unclear_data,
                                                                                              list) else []

        return IssuesResponse(risks=risks, unclear_points=unclear_points)


# 导出单例
project_document_service = ProjectDocumentService()
