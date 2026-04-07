from loguru import logger
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.enums import ErrorMessage


class TransactionIdVerifyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        transaction_id = request.headers.get('X-Transaction-Id')
        # 若没有 transaction_id 直接报错
        if not transaction_id:
            logger.warning(
                f"{request.method} {request.url.path} query:{dict(request.query_params)} error:X-Transaction-Id not found"
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
