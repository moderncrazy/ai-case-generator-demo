from piccolo.table import Table
from piccolo.engine.sqlite import SQLiteEngine

from src.config import settings

# 创建 SQLite 数据库引擎
DB = SQLiteEngine(path=str(settings.business_database_path))


class BaseModel(Table, db=DB):
    """Piccolo ORM 基类"""

    class Meta:
        database = DB
