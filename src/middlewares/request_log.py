import time

from loguru import logger
from fastapi import Request
from src.constant import TRANSACTION_ID
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLogMiddleware(BaseHTTPMiddleware):
    """请求日志中间件
    
    记录每个 HTTP 请求的详细信息，包括：
    - 请求方法、路径、查询参数
    - 事务ID（Transaction-ID）
    - 响应状态码和响应时间
    
    日志级别根据响应状态码划分：
    - 5xx：ERROR 级别
    - 4xx：WARNING 级别
    - 2xx：INFO 级别
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        transaction_id = request.headers.get(TRANSACTION_ID)
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            # 根据状态码选择日志级别
            if response.status_code >= 500:
                logger.error(
                    f"{request.method} {request.url.path} trance_id:{transaction_id} query:{dict(request.query_params)} "
                    f"resp_code:{response.status_code}  {process_time * 1000:.0f}ms"
                )
            elif response.status_code >= 400:
                logger.warning(
                    f"{request.method} {request.url.path} trance_id:{transaction_id} query:{dict(request.query_params)} "
                    f"resp_code:{response.status_code}  {process_time * 1000:.0f}ms"
                )
            else:
                logger.info(
                    f"{request.method} {request.url.path} trance_id:{transaction_id} query:{dict(request.query_params)} "
                    f"resp_code:{response.status_code}  {process_time * 1000:.0f}ms"
                )
            return response
        except Exception as e:
            process_time = time.perf_counter() - start_time
            logger.error(
                f"{request.method} {request.url.path} trance_id:{transaction_id} query:{dict(request.query_params)} "
                f"error:{e} | {process_time * 1000:.0f}ms"
            )
