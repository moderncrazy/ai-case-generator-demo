from loguru import logger
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.config import settings, setup_logging
from src.models.base import initialize_database
from src.services.milvus_service import milvus_service
from src.routes.project import router as project_router
from src.routes.module import router as module_router
from src.routes.test_case import router as test_case_router
from src.routes.api import router as api_router
from src.routes.conversation_message import router as conversation_message_router
from src.middlewares.request_log import RequestLogMiddleware
from src.middlewares.request_context import RequestContextMiddleware
from src.middlewares.transaction_id_verify import TransactionIdVerifyMiddleware
from src.exceptions.exceptions import BusinessException, general_exception_handler, business_exception_handler

# 日志配置：模块加载时就生效
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")
    initialize_database()
    await milvus_service.initialize()
    logger.info("应用启动完成")

    yield

    # 关闭时
    logger.info("应用关闭中...")
    await milvus_service.close()
    logger.info("应用已关闭")


app = FastAPI(lifespan=lifespan)

# 添加日志中间件
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TransactionIdVerifyMiddleware)
app.add_middleware(RequestLogMiddleware)

# 注册异常处理器
app.add_exception_handler(Exception, general_exception_handler)
app.add_exception_handler(BusinessException, business_exception_handler)

# 注册路由
app.include_router(project_router)
app.include_router(module_router)
app.include_router(test_case_router)
app.include_router(api_router)
app.include_router(conversation_message_router)
