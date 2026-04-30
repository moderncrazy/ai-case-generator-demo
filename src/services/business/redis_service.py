from loguru import logger
from redis.asyncio import Redis

from src.config import settings
from src.enums.redis_key import RedisKey
from src.schemas.project import ProjectBasicInfoResponse


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
        logger.info(f"Redis 初始化完成")

    async def close(self) -> None:
        """关闭连接"""
        if self.redis:
            await self.redis.aclose()
        logger.info(f"Redis 连接已关闭")

    async def get_create_project_lock(self, client_ip: str) -> bool:
        """项目创建并发锁"""
        key = RedisKey.CREATE_PROJECT_LOCK_KEY.format(client_ip=client_ip)
        return await self.redis.set(key, client_ip, nx=True, ex=settings.create_project_lock_expire)

    async def unlock_create_project_lock(self, client_ip: str):
        """项目创建并发解锁"""
        key = RedisKey.CREATE_PROJECT_LOCK_KEY.format(client_ip=client_ip)
        return await self.redis.delete(key)

    async def get_project_occupy_lock(self, project_id: str, user_id: str):
        """在设置时间内保持项目只被该用户使用"""
        key = RedisKey.PROJECT_OCCUPY_LOCK_KEY.value.format(project_id=project_id)
        result = await self.redis.set(key, user_id, nx=True, ex=settings.project_occupy_lock_expire)
        # 检查是否为同一用户 若是则延长时间
        if not result:
            if user_id == (await self.redis.get(key)).decode("utf-8"):
                await self.redis.expire(key, settings.project_occupy_lock_expire)
                return True
        return result

    async def get_project_discuss_lock(self, project_id: str) -> bool:
        """项目对话并发锁"""
        key = RedisKey.PROJECT_DISCUSS_LOCK_KEY.format(project_id=project_id)
        return await self.redis.set(key, project_id, nx=True, ex=settings.project_discuss_lock_expire)

    async def unlock_project_discuss_lock(self, project_id: str):
        """项目对话并发解锁"""
        key = RedisKey.PROJECT_DISCUSS_LOCK_KEY.format(project_id=project_id)
        return await self.redis.delete(key)

    async def get_compress_context_lock(self, project_id: str) -> bool:
        """上下文压缩并发锁"""
        key = RedisKey.COMPRESS_CONTEXT_LOCK_KEY.format(project_id=project_id)
        return await self.redis.set(key, project_id, nx=True, ex=settings.compress_context_lock_expire)

    async def unlock_compress_context_lock(self, project_id: str):
        """上下文压缩并发解锁"""
        key = RedisKey.COMPRESS_CONTEXT_LOCK_KEY.format(project_id=project_id)
        return await self.redis.delete(key)

    async def get_project_basic_info_cache(self, project_id: str) -> ProjectBasicInfoResponse | None:
        """获取项目基本信息缓存"""
        key = RedisKey.PROJECT_BASIC_INFO_CACHE_KEY.format(project_id=project_id)
        data = await self.redis.get(key)
        if data:
            return ProjectBasicInfoResponse.model_validate_json(data)
        return None

    async def set_project_basic_info_cache(self, project_id: str, data: ProjectBasicInfoResponse) -> None:
        """设置项目基本信息缓存"""
        key = RedisKey.PROJECT_BASIC_INFO_CACHE_KEY.format(project_id=project_id)
        await self.redis.set(key, data.model_dump_json(), ex=settings.project_basic_info_cache_expire)

    async def delete_project_basic_info_cache(self, project_id: str) -> None:
        """删除项目基本信息缓存"""
        key = RedisKey.PROJECT_BASIC_INFO_CACHE_KEY.format(project_id=project_id)
        await self.redis.delete(key)


# 初始化 RedisService
redis_service = RedisService()
