from typing import Optional
from sqlite3 import IntegrityError

from src.models.project import Project
from src.exceptions.exceptions import BusinessException
from src.schemas.project import ProjectCreate, ProjectStats, ProjectDetailResponse
from src.repositories.api_repository import api_repository
from src.repositories.module_repository import module_repository
from src.repositories.project_repository import project_repository
from src.repositories.test_case_repository import test_case_repository
from src.repositories.project_file_repository import project_file_repository
from src.enums.creator_type import CreatorType
from src.enums.error_message import ErrorMessage
from src.enums.project_progress import ProjectProgress


class ProjectService:
    """项目服务
    
    提供项目相关的业务逻辑处理，
    包括创建项目、查询列表、获取详情、获取统计信息等功能。
    """

    @staticmethod
    async def create_project(data: ProjectCreate) -> dict[str, str]:
        """创建项目
        
        创建新项目，初始化基本信息。
        如果项目名称已存在，抛出业务异常。
        
        Args:
            data: 项目创建参数（名称、描述等）
            
        Returns:
            包含新建项目 ID 的字典
            
        Raises:
            BusinessException: 项目名称已存在
        """
        try:
            project_id = await project_repository.create(
                name=data.name,
                description=data.description,
                creator_type=CreatorType.USER
            )
            return {"id": project_id}
        except IntegrityError:
            raise BusinessException.from_error_message(ErrorMessage.PROJECT_NAME_EXIST_ERROR)

    @staticmethod
    async def list_projects(
            page: int = 1,
            page_size: int = 20,
            progress: Optional[ProjectProgress] = None,
    ) -> tuple[list[dict], int]:
        """查询项目列表
        
        分页查询项目列表，支持按进度状态筛选。
        
        Args:
            page: 页码（从 1 开始）
            page_size: 每页数量
            progress: 按进度状态筛选（可选）
            
        Returns:
            (项目字典列表, 总数) 元组
        """
        projects, total = await project_repository.paginate(
            page=page,
            page_size=page_size,
            progress=progress,
        )
        return [item.to_dict() for item in projects], total

    @staticmethod
    async def get_project_detail(project: Project) -> ProjectDetailResponse:
        """获取项目详情
        
        获取项目详细信息，包括各阶段设计内容和统计信息。
        
        Args:
            project: 项目对象
            
        Returns:
            项目详细信息响应
        """
        # 获取统计信息
        modules_count = await module_repository.count_by_project(project.id)
        test_cases_count = await test_case_repository.count_by_project(project.id)
        apis_count = await api_repository.count_by_project(project.id)
        file_count = await project_file_repository.count_by_project(project.id)

        stats = ProjectStats(
            modules_count=modules_count,
            test_cases_count=test_cases_count,
            apis_count=apis_count,
            file_count=file_count,
        )

        return ProjectDetailResponse(
            id=project.id,
            name=project.name,
            progress=ProjectProgress(project.progress),
            description=project.description,
            requirement_outline_design=project.requirement_outline_design,
            requirement_module_design=project.requirement_module_design,
            requirement_overall_design=project.requirement_overall_design,
            architecture_design=project.architecture_design,
            database_design=project.database_design,
            creator_type=CreatorType(project.creator_type),
            created_at=project.created_at,
            updated_at=project.updated_at,
            stats=stats,
        )


# 导出单例
project_service = ProjectService()
