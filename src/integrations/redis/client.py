"""RedisRuntime — lifecycle-managed async Redis client.

Provides ``open()``, ``close()``, and ``ping()`` over a single Redis
connection pool.  Test isolation (e.g. ``flushdb``) is the
responsibility of the test fixture, not of the production runtime.
"""

from __future__ import annotations

import redis.asyncio as aioredis


class RedisRuntime:
    """Lifecycle container for a Redis async client.

    Usage::

        runtime = RedisRuntime(url="redis://localhost:6379/0")
        await runtime.open()
        try:
            await runtime.ping()
            value = await runtime.client.get("some-key")
        finally:
            await runtime.close()
    """

    def __init__(self, *, url: str) -> None:
        self._url = url
        self._redis: aioredis.Redis | None = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        """Create the connection pool and connect."""
        self._redis = aioredis.from_url(self._url, decode_responses=False)

    async def close(self) -> None:
        """Close the connection pool and release all connections."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def ping(self) -> bool:
        """Return ``True`` when Redis responds to PING."""
        return await self.client.ping()

    # ------------------------------------------------------------------
    # accessor
    # ------------------------------------------------------------------

    @property
    def client(self) -> aioredis.Redis:
        """Return the underlying ``redis.asyncio.Redis`` client.

        Raises ``RuntimeError`` when accessed before ``open()`` or
        after ``close()``.
        """
        if self._redis is None:
            raise RuntimeError("RedisRuntime has not been opened")
        return self._redis
