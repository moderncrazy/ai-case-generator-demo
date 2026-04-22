from src import constant as const
from src.repositories.project_file_repository import project_file_repository


class ProjectFileService:
    """项目文件服务
    
    提供项目文件相关的业务逻辑处理，
    包括提取文件摘要等功能。
    """

    @staticmethod
    async def get_project_files_summary_to_str(project_id: str) -> str:
        """提取项目文件摘要转为字符串
        
        将项目中所有文件的摘要信息整合为一个字符串，
        用于提供给 AI 作为上下文信息。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            包含所有文件摘要的字符串
        """
        content = ""
        project_files = await project_file_repository.list_by_project(project_id)
        for item in project_files:
            content += f"文件Id：{item.id}\n文件名：{item.name}\n上传时间：{item.created_at}\n文件摘要：\n{item.summary}\n\n----------{item.name} end----------\n\n"
        return content if content else const.EMPTY_ZH


# 导出单例
project_file_service = ProjectFileService()
