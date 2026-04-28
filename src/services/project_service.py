import traceback
from loguru import logger
from typing import Optional
from sqlite3 import IntegrityError
from piccolo.engine.sqlite import TransactionType

from src.context import trans_id_ctx
from src.models.business.project import Project
from src.exceptions.exceptions import BusinessException
from src.schemas.project import ProjectCreate, ProjectListItem, ProjectBasicInfoResponse
from src.repositories.api_repository import api_repository
from src.repositories.module_repository import module_repository
from src.repositories.project_repository import project_repository
from src.repositories.test_case_repository import test_case_repository
from src.repositories.project_file_repository import project_file_repository
from src.repositories.conversation_message_repository import conversation_message_repository
from src.repositories.conversation_summary_repository import conversation_summary_repository
from src.repositories.operation_log_repository import operation_log_repository
from src.services.redis_service import redis_service
from src.services.milvus_service import milvus_service
from src.utils.file_utils import delete_project_directory
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
    ) -> tuple[list[ProjectListItem], int]:
        """查询项目列表
        
        分页查询项目列表，支持按进度状态筛选。
        
        Args:
            page: 页码（从 1 开始）
            page_size: 每页数量
            progress: 按进度状态筛选（可选）
            
        Returns:
            (项目列表, 总数) 元组
        """
        projects, total = await project_repository.paginate(
            page=page,
            page_size=page_size,
            progress=progress,
        )
        return [
            ProjectListItem(
                id=item.id,
                name=item.name,
                description=item.description,
                progress=ProjectProgress(item.progress),
                created_at=item.created_at,
            )
            for item in projects
        ], total

    @staticmethod
    async def get_project_basic_info(project: Project) -> ProjectBasicInfoResponse:
        """获取项目基本信息
        
        获取项目基本信息及各文档是否存在。
        
        Args:
            project: 项目对象
            
        Returns:
            项目基本信息响应
        """
        # 获取统计信息
        modules_count = await module_repository.count_by_project(project.id)
        test_cases_count = await test_case_repository.count_by_project(project.id)
        apis_count = await api_repository.count_by_project(project.id)

        return ProjectBasicInfoResponse(
            id=project.id,
            name=project.name,
            progress=ProjectProgress(project.progress),
            description=project.description,
            has_requirement_outline=bool(project.requirement_outline_design),
            has_requirement_modules=bool(project.requirement_module_design),
            has_requirement_overall=bool(project.requirement_overall_design),
            has_architecture=bool(project.architecture_design),
            has_database=bool(project.database_design),
            has_modules=modules_count > 0,
            has_apis=apis_count > 0,
            has_test_cases=test_cases_count > 0,
            creator_type=CreatorType(project.creator_type),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    @staticmethod
    async def delete_project(project: Project, user_id: str) -> None:
        """删除项目及其所有关联数据
        
        删除项目时需要按以下顺序进行：
        1. 获取项目占用锁（确保项目不被其他用户使用）
        2. 删除项目文件记录（SQLite）
        3. 删除对话消息记录（SQLite）
        4. 删除对话摘要记录（SQLite）
        5. 删除操作日志记录（SQLite）
        6. 删除测试用例记录（SQLite）
        7. 删除接口记录（SQLite）
        8. 删除模块记录（SQLite）
        9. 删除项目文件向量（Milvus）
        10. 删除项目上下文向量（Milvus）
        11. 删除项目主记录（SQLite）
        12. 删除项目物理文件（data/project/{project_id}/*）
        
        Args:
            project: 项目对象
            user_id: 用户 ID，用于获取项目占用锁
            
        Raises:
            BusinessException: 系统创建的项目不允许删除或项目被占用
        """
        logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project.id} 开始删除项目")
        # 系统创建的项目不允许删除
        if project.creator_type == CreatorType.SYSTEM.value:
            raise BusinessException.from_error_message(ErrorMessage.PROJECT_SYSTEM_NOT_ALLOW_DELETE_ERROR)
        project_id = project.id
        # 尝试获取项目占用锁
        lock_result = await redis_service.get_project_occupy_lock(project_id, user_id)
        if not lock_result:
            raise BusinessException.from_error_message(ErrorMessage.PROJECT_OCCUPIED_ERROR)
        try:
            async with Project._meta.db.transaction(transaction_type=TransactionType.immediate):
                # 1. 删除项目文件记录（SQLite）
                await project_file_repository.delete_by_project(project_id)
                # 2. 删除对话消息记录（SQLite）
                await conversation_message_repository.delete_by_project(project_id)
                # 3. 删除对话摘要记录（SQLite）
                await conversation_summary_repository.delete_by_project(project_id)
                # 4. 删除操作日志记录（SQLite）
                await operation_log_repository.delete_by_project(project_id)
                # 5. 删除测试用例记录（SQLite）
                await test_case_repository.delete_by_project(project_id)
                # 6. 删除接口记录（SQLite）
                await api_repository.delete_by_project(project_id)
                # 7. 删除模块记录（SQLite）
                await module_repository.delete_by_project(project_id)
                # 8-9. 删除 Milvus 向量数据
                await milvus_service.delete_project(project_id)
                # 10. 删除项目主记录（SQLite）
                await project_repository.delete_by_id(project_id)
                # 11. 删除项目物理文件（最后删除）
                delete_project_directory(project_id)
                logger.info(f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 项目删除成功")
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id_ctx.get()} 项目Id:{project_id} 项目删除失败:{str(e)}\n异常栈:\n{traceback.format_exc()}")
            raise


# 导出单例
project_service = ProjectService()
