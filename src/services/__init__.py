# Services Module

from src.services.milvus_service import MilvusService, milvus_service
from src.services.project_service import ProjectService, project_service

__all__ = [
    'MilvusService',
    'ProjectService',
    # 全局单例实例
    'milvus_service',
    'project_service'
]
