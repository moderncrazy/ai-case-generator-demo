from loguru import logger
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.constant import TRANSACTION_ID
from src.enums.error_message import ErrorMessage


class TransactionIdVerifyMiddleware(BaseHTTPMiddleware):
    """事务ID验证中间件
    
    验证请求头中是否包含事务ID（Transaction-ID）。
    若缺少事务ID，直接返回 400 错误响应，不再继续处理请求。
    
    这确保了每个请求都能被追踪和关联。
    """

    async def dispatch(self, request: Request, call_next):
        transaction_id = request.headers.get(TRANSACTION_ID)
        # 若没有 transaction_id 直接报错
        if not transaction_id:
            logger.warning(
                f"{request.method} {request.url.path} query:{dict(request.query_params)} error:{TRANSACTION_ID} not found"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "code": ErrorMessage.TRANSACTION_ID_NOT_FOUND.code,
                    "message": ErrorMessage.TRANSACTION_ID_NOT_FOUND.message,
                    "error": None,
                }
            )
        return await call_next(request)
