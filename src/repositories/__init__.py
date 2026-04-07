# Repositories Module

from src.repositories.project_repository import ProjectRepository, project_repository
from src.repositories.module_repository import ModuleRepository, module_repository
from src.repositories.test_case_repository import TestCaseRepository, test_case_repository
from src.repositories.api_repository import ApiRepository, api_repository
from src.repositories.conversation_message_repository import (
    ConversationMessageRepository,
    conversation_message_repository,
)
from src.repositories.operation_log_repository import (
    OperationLogRepository,
    operation_log_repository,
)
from src.repositories.project_file_repository import (
    ProjectFileCreate,
    ProjectFileRepository,
    project_file_repository,
)

__all__ = [
    "ProjectRepository",
    "ModuleRepository",
    "TestCaseRepository",
    "ApiRepository",
    "ConversationMessageRepository",
    "OperationLogRepository",
    "ProjectFileRepository",
    "ProjectFileCreate",
    # 全局单例实例
    "project_repository",
    "module_repository",
    "test_case_repository",
    "api_repository",
    "conversation_message_repository",
    "operation_log_repository",
    "project_file_repository",
]
