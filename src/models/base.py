import pkgutil
import importlib
from pathlib import Path
from loguru import logger
from piccolo.table import Table
from piccolo.engine.sqlite import SQLiteEngine

from src.config import settings

# 创建 SQLite 数据库引擎
BUSINESS_DB = SQLiteEngine(path=str(settings.business_database_path))
CHECKPOINT_DB = SQLiteEngine(path=str(settings.langgraph_sqlite_checkpoint_path))


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
    package_path = Path(__file__).resolve().parent / "business"
    for _, module_name, _ in pkgutil.iter_modules([package_path]):
        module = importlib.import_module(f"{__package__}.business.{module_name}")
        for name in dir(module):
            cls = getattr(module, name)
            if (isinstance(cls, type) and
                    issubclass(cls, Table) and
                    cls is not Table):
                discovered_classes.add(cls)

    # 创建表
    for cls in discovered_classes:
        cls.create_table(if_not_exists=True).run_sync()
    logger.info("Business 数据库初始化完成")
