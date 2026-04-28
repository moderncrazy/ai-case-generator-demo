from enum import Enum

from src.constant import TRANSACTION_ID


class ErrorMessage(Enum):
    """错误消息枚举"""

    TRANSACTION_ID_NOT_FOUND = (4001, f"{TRANSACTION_ID} not found")
    PROJECT_NOT_FOUND_ERROR = (4002, "项目不存在")
    FILE_TYPE_ERROR = (4003, "文件类型错误")
    FILE_SIZE_ERROR = (4004, "文件过大")
    FILE_EXCEPTION_ERROR = (4005, "文件异常")
    PROJECT_FILE_TOTAL_SIZE_ERROR = (4006, "项目文件总体过大")
    PROJECT_FILE_EXIST_ERROR = (4007, "项目文件已存在")
    PROJECT_NAME_EXIST_ERROR = (4008, "项目名称已存在")
    PROJECT_OCCUPIED_ERROR = (4009, "项目被其他用户使用中")
    PROJECT_SYSTEM_NOT_ALLOW_DELETE_ERROR = (4010, "系统创建的项目不允许删除")
    LLM_ERROR = (4100, "模型调用异常")
    FLOW_VALIDATE_FAILED = (4101, "流程验证失败")

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
