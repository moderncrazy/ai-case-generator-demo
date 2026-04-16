from fastapi.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.constant import TRANSACTION_ID
from src.context import request_ctx, trans_id_ctx


class RequestContextMiddleware(BaseHTTPMiddleware):
    """请求上下文中间件
    
    将 HTTP 请求对象和事务ID设置到上下文变量中，
    供后续业务代码获取当前请求信息。
    
    功能：
    - 将 FastAPI Request 对象存入请求上下文
    - 将事务ID（Transaction-ID）存入上下文
    - 请求结束后自动清理上下文资源
    """

    async def dispatch(self, request: Request, call_next):
        request_token = request_ctx.set(request)
        trans_id_token = trans_id_ctx.set(request.headers.get(TRANSACTION_ID))
        try:
            return await call_next(request)
        finally:
            trans_id_ctx.reset(trans_id_token)
            request_ctx.reset(request_token)
