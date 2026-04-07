from enum import Enum
from pathlib import Path
from functools import cached_property


class ErrorMessage(Enum):
    """错误语"""

    TRANSACTION_ID_NOT_FOUND = (4001, "X-Transaction-Id not found")
    FILE_TYPE_ERROR = (4002, "文件类型错误")
    FILE_SIZE_ERROR = (4003, "文件过大")
    FILE_EXCEPTION_ERROR = (4004, "文件异常")
    PROJECT_FILE_TOTAL_SIZE_ERROR = (4005, "项目文件总体过大")
    PROJECT_FILE_EXIST_ERROR = (4006, "项目文件已存在")

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
