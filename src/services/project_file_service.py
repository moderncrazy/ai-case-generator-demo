from src.repositories.project_file_repository import project_file_repository


class ProjectFileService:
    """项目文件服务"""

    @staticmethod
    async def get_project_files_summary_to_str(project_id: str) -> str:
        """提取项目文件摘要转为str"""
        content = ""
        project_files = await project_file_repository.list_by_project(project_id)
        for item in project_files:
            content += f"文件Id：{item.id}\n文件名：{item.name}\n上传时间：{item.created_at}\n文件摘要：\n{item.summary}\n\n----------{item.name} end----------\n\n"
        return content if content else "（空）"


# 导出单例
project_file_service = ProjectFileService()
