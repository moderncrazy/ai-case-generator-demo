import time

from loguru import logger
from fastapi import Request
from src.constant import TRANSACTION_ID
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLogMiddleware(BaseHTTPMiddleware):

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
