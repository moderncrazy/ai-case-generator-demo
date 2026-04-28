from piccolo.table import Table
from piccolo.columns import Text, Bytea

from src.models.base import CHECKPOINT_DB


class Checkpoints(Table, db=CHECKPOINT_DB):
    """LangGraph Checkpoint 表
    
    存储 LangGraph 状态检查点。
    """

    thread_id = Text(null=False)
    checkpoint_ns = Text(default='', null=False)
    checkpoint_id = Text(null=False)
    parent_checkpoint_id = Text()
    type = Text()
    checkpoint = Bytea()
    metadata = Bytea()

    class Meta:
        table_name = "checkpoints"
