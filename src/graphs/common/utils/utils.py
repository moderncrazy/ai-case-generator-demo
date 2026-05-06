from langgraph.config import get_stream_writer

from src.enums.project_progress import ProjectProgress
from src.enums.group_member_role import GroupMemberRole
from src.enums.conversation_message_type import ConversationMessageType
from src.graphs.common.schemas.common_schemas import CustomMessage


def send_custom_message(message: str, role: GroupMemberRole,
                        type: ConversationMessageType = ConversationMessageType.STAGE):
    """发送自定义消息"""
    writer = get_stream_writer()
    writer(CustomMessage(type=type, role=role, message=message))


def get_role_optimization_by_project_progress(project_progress: ProjectProgress) -> GroupMemberRole:
    match project_progress:
        case ProjectProgress.REQUIREMENT_OUTLINE_DESIGN:
            return GroupMemberRole.PRODUCT
        case ProjectProgress.REQUIREMENT_MODULE_DESIGN:
            return GroupMemberRole.PRODUCT
        case ProjectProgress.REQUIREMENT_OVERALL_DESIGN:
            return GroupMemberRole.PRODUCT
        case ProjectProgress.SYSTEM_ARCHITECTURE_DESIGN:
            return GroupMemberRole.ARCHITECT
        case ProjectProgress.SYSTEM_MODULES_DESIGN:
            return GroupMemberRole.ARCHITECT
        case ProjectProgress.SYSTEM_DATABASE_DESIGN:
            return GroupMemberRole.DBA
        case ProjectProgress.SYSTEM_API_DESIGN:
            return GroupMemberRole.BACKEND
        case ProjectProgress.TEST_CASE_DESIGN:
            return GroupMemberRole.TEST
        case _:
            return GroupMemberRole.PRODUCT
