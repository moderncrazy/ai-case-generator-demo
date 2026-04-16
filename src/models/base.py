import os
import pkgutil
import importlib
from loguru import logger
from piccolo.table import Table
from piccolo.engine.sqlite import SQLiteEngine

from src.config import settings

# 创建 SQLite 数据库引擎
DB = SQLiteEngine(path=str(settings.business_database_path))


class BaseModel(Table, db=DB):
    """Piccolo ORM 基类
    
    所有业务模型类的基类，继承自 Piccolo Table。
    自动绑定数据库引擎，提供通用的 to_dict() 方法。
    """

    class Meta:
        database = DB


def initialize_database():
    """自动发现并初始化所有 BaseModel 子类的数据库表
    
    遍历 src/models 目录下的所有模块，
    自动发现所有继承自 BaseModel 的类，
    并创建对应的数据库表。
    
    功能：
    - 创建数据库目录（如果不存在）
    - 自动发现 BaseModel 子类
    - 创建表（如果不存在）
    """
    # 创建数据库目录
    settings.business_database_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用 set 去重
    discovered_classes: set[type] = set()

    # 自动发现所有 BaseModel 子类
    for _, module_name, _ in pkgutil.iter_modules([os.path.dirname(os.path.abspath(__file__))]):
        module = importlib.import_module(f"{__package__}.{module_name}")
        for name in dir(module):
            cls = getattr(module, name)
            if (isinstance(cls, type) and
                    issubclass(cls, BaseModel) and
                    cls is not BaseModel):
                discovered_classes.add(cls)

    # 创建表
    for cls in discovered_classes:
        cls.create_table(if_not_exists=True).run_sync()
    logger.info("Business 数据库初始化完成")
