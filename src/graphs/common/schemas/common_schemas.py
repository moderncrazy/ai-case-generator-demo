import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import TypedDict, Optional

from src.enums.http_method import HttpMethod
from src.enums.test_case_type import TestCaseType
from src.enums.http_param_type import HttpParamType
from src.enums.test_case_level import TestCaseLevel
from src.enums.group_member_role import GroupMemberRole
from src.enums.requirement_module_status import RequirementModuleStatus
from src.enums.conversation_message_type import ConversationMessageType
from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult


class CustomMessage(BaseModel):
    """自定义消息结构（用于流式输出）
    
    前端展示用的进度提示消息。
    """
    type: ConversationMessageType = Field(description="消息类型")
    """消息类型"""

    role: GroupMemberRole = Field(description="发送消息的角色")
    """发送消息的角色"""

    message: str = Field(description="消息内容")
    """提示消息内容"""
