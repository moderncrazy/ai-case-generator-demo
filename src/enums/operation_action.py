from enum import Enum


class OperationAction(str, Enum):
    """操作类型枚举，与数据库 operation_logs.action 字段一致"""

    CREATE = "create"
    """创建"""

    UPDATE = "update"
    """更新"""

    DELETE = "delete"
    """删除"""

    EXPORT = "export"
    """导出"""

    IMPORT = "import"
    """导入"""

    COPY = "copy"
    """复制"""
