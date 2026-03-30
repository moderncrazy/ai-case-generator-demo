from loguru import logger
from fastapi import FastAPI

from src.middleware.log_request import LogRequestMiddleware

app = FastAPI()

# 添加日志中间件
app.add_middleware(LogRequestMiddleware)


@app.get("/")
def hello_world():
    logger.info(f"Hello World")
    return {"Hello": "World!"}


@app.get("/item/{item_id}")
def get_items(item_id: str, x: str):
    return {"item_id": item_id, "q": x}
