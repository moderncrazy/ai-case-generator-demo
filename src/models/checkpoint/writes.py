from piccolo.table import Table
from piccolo.columns import Text, Bytea, Integer

from src.models.base import CHECKPOINT_DB


class Writes(Table, db=CHECKPOINT_DB):
    """LangGraph Write 表
    
    存储 LangGraph 检查点写入记录。
    """

    thread_id = Text(null=False)
    checkpoint_ns = Text(default='', null=False)
    checkpoint_id = Text(null=False)
    task_id = Text(null=False)
    idx = Integer(null=False)
    channel = Text(null=False)
    type = Text()
    value = Bytea()

    class Meta:
        table_name = "writes"
