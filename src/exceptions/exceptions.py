from loguru import logger
from fastapi import Request
from fastapi.responses import JSONResponse

from src.enums import ErrorMessage


class BusinessException(Exception):
    """业务异常"""

    def __init__(self, code: int, message: str, error: str = None):
        self.code = code
        self.message = message
        self.error = error
        super().__init__(message)

    @classmethod
    def from_error_message(cls, err_msg: ErrorMessage, error: str = None):
        return cls(code=err_msg.code, message=err_msg.message, error=error)


async def business_exception_handler(request: Request, e: BusinessException):
    """业务异常处理"""
    transaction_id = request.headers.get('X-Transaction-Id')
    logger.warning(f"trance_id:{transaction_id} error_type:{type(e).__name__} error:{str(e)}")
    return JSONResponse(
        status_code=400,
        content={
            "code": e.code,
            "message": e.message,
            "error": e.error,
        },
    )


async def general_exception_handler(request: Request, e: Exception):
    """通用异常处理"""
    transaction_id = request.headers.get('X-Transaction-Id')
    logger.warning(f"trance_id:{transaction_id} error_type:{type(e).__name__} error:{str(e)}")
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "error": str(e),
        },
    )
