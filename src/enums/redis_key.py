from enum import StrEnum


class RedisKey(StrEnum):
    """Redis 缓存 Key 枚举，统一管理所有 Redis Key"""

    PROJECT_OCCUPY_LOCK_KEY = "project_occupy_lock_{project_id}"
    """项目占用锁 Key，用于在设置时间内保持项目只被某用户使用"""

    DISCUSS_PROJECT_LOCK_KEY = "discuss_project_lock_{project_id}"
    """项目讨论锁 Key"""

    COMPRESS_CONTEXT_LOCK_KEY = "compress_context_lock_{project_id}"
    """上下文压缩锁 Key，用于防止并发压缩"""

    CREATE_PROJECT_LOCK_KEY = "create_project_lock_{client_ip}"
    """创建项目并发锁 Key，用于限制同一 IP 频繁创建项目"""

    PROJECT_DISCUSS_LOCK_KEY = "project_discuss_lock_{project_id}"
    """项目对话锁 Key，用于限制项目并发对话"""

    PROJECT_BASIC_INFO_CACHE_KEY = "project_basic_info_cache_{project_id}"
    """项目基本信息缓存 Key"""
