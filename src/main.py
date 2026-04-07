from loguru import logger
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.routes import project_router
from src.config import settings, setup_logging
from src.services.milvus_service import milvus_service
from src.middlewares import RequestLogMiddleware, TransactionIdVerifyMiddleware
from src.exceptions import BusinessException, general_exception_handler, business_exception_handler

# 日志配置：模块加载时就生效
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")
    await milvus_service.initialize()
    logger.info("应用启动完成")

    yield

    # 关闭时
    logger.info("应用关闭中...")
    await milvus_service.close()
    logger.info("应用已关闭")


app = FastAPI(lifespan=lifespan)

# 添加日志中间件
app.add_middleware(TransactionIdVerifyMiddleware)
app.add_middleware(RequestLogMiddleware)

# 注册异常处理器
app.add_exception_handler(Exception, general_exception_handler)
app.add_exception_handler(BusinessException, business_exception_handler)

# 注册路由
app.include_router(project_router)
