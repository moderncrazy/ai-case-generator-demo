from redis.asyncio import Redis

from src.config import settings

PROJECT_OCCUPY_LOCK_KEY = "project_occupy_lock_{project_id}"
DISCUSS_PROJECT_LOCK_KEY = "discuss_project_lock_{project_id}"
COMPRESS_CONTEXT_LOCK_KEY = "compress_context_lock_{project_id}"


class RedisService:

    def __init__(self):
        self.redis: Redis | None = None

    async def initialize(self) -> None:
        """初始化Redis"""
        self.redis = await Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password
        )

    async def close(self) -> None:
        """关闭连接"""
        if self.redis:
            await self.redis.aclose()

    async def get_project_occupy_lock(self, project_id: str, user_id: str):
        """在设置时间内保持项目只被该用户使用"""
        key = PROJECT_OCCUPY_LOCK_KEY.format(project_id=project_id)
        result = await self.redis.set(key, user_id, nx=True, ex=settings.project_occupy_lock_expire)
        # 检查是否为同一用户 若是则延长时间
        if not result:
            if user_id == (await self.redis.get(key)).decode("utf-8"):
                await self.redis.expire(key, settings.project_occupy_lock_expire)
                return True
        return result

    async def get_compress_context_lock(self, project_id: str):
        """上下文压缩并发锁"""
        key = COMPRESS_CONTEXT_LOCK_KEY.format(project_id=project_id)
        return await self.redis.set(key, project_id, nx=True, ex=settings.compress_context_lock_expire)

    async def unlock_compress_context_lock(self, project_id: str):
        """上下文压缩并发解锁"""
        key = COMPRESS_CONTEXT_LOCK_KEY.format(project_id=project_id)
        return await self.redis.delete(key)


# 初始化 RedisService
redis_service = RedisService()
