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

The occupancy TTL is fixed at 300 seconds per the database design
section 13.3.  Callers cannot vary it.
"""

from __future__ import annotations

from enum import StrEnum

import redis.asyncio as aioredis
from redis.exceptions import NoScriptError

from src.integrations.redis.keys import conversation_owner_key

# ---------------------------------------------------------------------------
# Occupancy TTL — section 13.3
# ---------------------------------------------------------------------------

OCCUPANCY_TTL_SECONDS: int = 300
"""Approved conversation-owner key TTL (seconds).

TTL: 300 seconds sliding or worker renewal (database design §13.3).
"""


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

    Cached script SHAs are recovered transparently after Redis
    restarts, failovers, or ``SCRIPT FLUSH``: the first ``NoScriptError``
    triggers a reload, cache update, and single retry.

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
    ) -> OccupancyResult:
        """Atomically acquire or renew the conversation owner for *project_id*.

        The occupancy TTL is always ``OCCUPANCY_TTL_SECONDS`` (300 s).
        Returns one of ``ACQUIRED``, ``RENEWED``, or ``OCCUPIED``.
        """
        sha = await self._load_acquire()
        key = conversation_owner_key(project_id=project_id)
        raw: bytes = await self._evalsha_acquire(sha, key, user_id)
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
        raw: bytes = await self._evalsha_release(sha, key, user_id)
        return OccupancyResult(raw.decode())

    # ------------------------------------------------------------------
    # script loading (with NoScriptError recovery)
    # ------------------------------------------------------------------

    async def _load_acquire(self) -> str:
        if self._acquire_sha is None:
            self._acquire_sha = await self._client.script_load(_ACQUIRE_SCRIPT)
        return self._acquire_sha

    async def _load_release(self) -> str:
        if self._release_sha is None:
            self._release_sha = await self._client.script_load(_RELEASE_SCRIPT)
        return self._release_sha

    async def _evalsha_acquire(
        self, sha: str, key: str, user_id: str,
    ) -> bytes:
        ttl_str = str(OCCUPANCY_TTL_SECONDS)
        try:
            return await self._client.evalsha(sha, 1, key, user_id, ttl_str)
        except NoScriptError:
            self._acquire_sha = await self._client.script_load(_ACQUIRE_SCRIPT)
            return await self._client.evalsha(
                self._acquire_sha, 1, key, user_id, ttl_str,
            )

    async def _evalsha_release(
        self, sha: str, key: str, user_id: str,
    ) -> bytes:
        try:
            return await self._client.evalsha(sha, 1, key, user_id)
        except NoScriptError:
            self._release_sha = await self._client.script_load(_RELEASE_SCRIPT)
            return await self._client.evalsha(
                self._release_sha, 1, key, user_id,
            )
