from fastapi.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.constant import TRANSACTION_ID
from src.context import request_ctx, trans_id_ctx


class RequestContextMiddleware(BaseHTTPMiddleware):
    """记录请求上下文"""

    async def dispatch(self, request: Request, call_next):
        request_token = request_ctx.set(request)
        trans_id_token = trans_id_ctx.set(request.headers.get(TRANSACTION_ID))
        try:
            return await call_next(request)
        finally:
            trans_id_ctx.reset(trans_id_token)
            request_ctx.reset(request_token)
