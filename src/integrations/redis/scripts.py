"""Atomic occupancy primitives for project conversation ownership.

All acquire / renew / release operations use Redis Lua scripts so that
the stored user comparison and key mutation happen atomically.  Python
code must never emulate this behaviour with separate GET / SET calls.

Result vocabulary (exactly five values):

    ACQUIRED   — key was free; now owned by the calling user
    RENEWED    — key already owned by the calling user; TTL refreshed
    OCCUPIED   — key owned by a *different* user; no change made
    RELEASED   — key was owned by the calling user and has been deleted
    NOT_OWNER  — key is owned by a different user; release denied
"""

from __future__ import annotations

from enum import StrEnum

import redis.asyncio as aioredis

from src.integrations.redis.keys import conversation_owner_key


# ---------------------------------------------------------------------------
# Result vocabulary
# ---------------------------------------------------------------------------


class OccupancyResult(StrEnum):
    """The five atomic-occupancy outcome kinds."""

    ACQUIRED = "ACQUIRED"
    RENEWED = "RENEWED"
    OCCUPIED = "OCCUPIED"
    RELEASED = "RELEASED"
    NOT_OWNER = "NOT_OWNER"


# Convenience re-exports so callers can import these directly.
NOT_OWNER: str = OccupancyResult.NOT_OWNER
OCCUPIED: str = OccupancyResult.OCCUPIED
RELEASED: str = OccupancyResult.RELEASED


# ---------------------------------------------------------------------------
# Lua scripts
# ---------------------------------------------------------------------------

_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local user_id = ARGV[1]
local ttl = tonumber(ARGV[2])

local current = redis.call('GET', key)
if current == false then
    redis.call('SET', key, user_id, 'EX', ttl)
    return 'ACQUIRED'
elseif current == user_id then
    redis.call('EXPIRE', key, ttl)
    return 'RENEWED'
else
    return 'OCCUPIED'
end
"""

_RELEASE_SCRIPT = """
local key = KEYS[1]
local user_id = ARGV[1]

local current = redis.call('GET', key)
if current == false then
    return 'RELEASED'
elseif current == user_id then
    redis.call('DEL', key)
    return 'RELEASED'
else
    return 'NOT_OWNER'
end
"""


# ---------------------------------------------------------------------------
# OccupancyManager
# ---------------------------------------------------------------------------


class OccupancyManager:
    """Atomic project conversation-owner operations.

    This manager owns the Lua script registration and exposes
    ``acquire`` / ``release`` whose behaviour is entirely defined by
    the scripts above.

    It does *not* implement Access or Conversation domain policy
    (e.g. OWNER governance takeover is a higher-level concern).
    """

    def __init__(self, *, client: aioredis.Redis) -> None:
        self._client = client
        self._acquire_sha: str | None = None
        self._release_sha: str | None = None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def acquire(
        self,
        project_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> OccupancyResult:
        """Atomically acquire or renew the conversation owner for *project_id*.

        Returns one of ``ACQUIRED``, ``RENEWED``, or ``OCCUPIED``.
        """
        sha = await self._load_acquire()
        key = conversation_owner_key(project_id=project_id)
        raw: bytes = await self._client.evalsha(sha, 1, key, user_id, str(ttl_seconds))
        return OccupancyResult(raw.decode())

    async def release(
        self,
        project_id: str,
        user_id: str,
    ) -> OccupancyResult:
        """Atomically release the conversation owner for *project_id*.

        Returns ``RELEASED`` when the key was owned by *user_id* (or
        already absent), and ``NOT_OWNER`` when a different user holds
        the key.
        """
        sha = await self._load_release()
        key = conversation_owner_key(project_id=project_id)
        raw: bytes = await self._client.evalsha(sha, 1, key, user_id)
        return OccupancyResult(raw.decode())

    # ------------------------------------------------------------------
    # script loading
    # ------------------------------------------------------------------

    async def _load_acquire(self) -> str:
        if self._acquire_sha is None:
            self._acquire_sha = await self._client.script_load(_ACQUIRE_SCRIPT)
        return self._acquire_sha

    async def _load_release(self) -> str:
        if self._release_sha is None:
            self._release_sha = await self._client.script_load(_RELEASE_SCRIPT)
        return self._release_sha
