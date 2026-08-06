"""Atomic occupancy tests with real Redis.

Verifies the Lua-script-backed acquire / renew / release semantics
against a real Redis instance.  The 50-key race test is the primary
concurrency guard.

Fix Round 1 adds:
- NoScriptError recovery tests (acquire and release).
- Meaningful sliding-renewal TTL evidence via explicit Redis EXPIRE.
- TTL-constant contract tests.
"""

from __future__ import annotations

import asyncio

import pytest

from src.integrations.redis.client import RedisRuntime
from src.integrations.redis.keys import conversation_owner_key
from src.integrations.redis.scripts import (
    NOT_OWNER,
    OCCUPANCY_TTL_SECONDS,
    OCCUPIED,
    RELEASED,
    OccupancyManager,
    OccupancyResult,
)


# ---------------------------------------------------------------------------
# Single-key correctness
# ---------------------------------------------------------------------------


class TestAcquireFresh:
    @pytest.mark.asyncio
    async def test_first_acquire_returns_acquired(
        self, occupancy: OccupancyManager,
    ) -> None:
        result = await occupancy.acquire("p-fresh", "u1")
        assert result == OccupancyResult.ACQUIRED

    @pytest.mark.asyncio
    async def test_acquire_stores_user_id(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-store", "u1")
        stored = await redis_runtime.client.get("project:conversation-owner:p-store")
        assert stored == b"u1" or stored == "u1"

    @pytest.mark.asyncio
    async def test_acquire_sets_ttl(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-ttl", "u1")
        ttl = await redis_runtime.client.ttl("project:conversation-owner:p-ttl")
        assert 290 <= ttl <= 300


class TestRenew:
    @pytest.mark.asyncio
    async def test_same_user_second_acquire_is_renewed(
        self, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-renew", "u1")
        result = await occupancy.acquire("p-renew", "u1")
        assert result == OccupancyResult.RENEWED

    @pytest.mark.asyncio
    async def test_renew_restores_ttl_to_full_after_explicit_shorten(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        """Lower the Redis key TTL directly, then verify re-acquire
        restores it to the full 300 seconds."""
        await occupancy.acquire("p-ttl-reset", "u1")
        key = conversation_owner_key(project_id="p-ttl-reset")
        # Shorten the key TTL via Redis directly — no fake clock.
        await redis_runtime.client.expire(key, 10)
        shortened = await redis_runtime.client.ttl(key)
        assert 1 <= shortened <= 10

        # Same-user re-acquire must restore to full 300 s.
        await occupancy.acquire("p-ttl-reset", "u1")
        restored = await redis_runtime.client.ttl(key)
        assert 290 <= restored <= 300


class TestOccupyReject:
    @pytest.mark.asyncio
    async def test_different_user_acquire_returns_occupied(
        self, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-occ", "u1")
        result = await occupancy.acquire("p-occ", "u2")
        assert result == OccupancyResult.OCCUPIED

    @pytest.mark.asyncio
    async def test_different_user_does_not_overwrite(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-no-ow", "u1")
        await occupancy.acquire("p-no-ow", "u2")
        stored = await redis_runtime.client.get("project:conversation-owner:p-no-ow")
        assert stored == b"u1" or stored == "u1"


class TestRelease:
    @pytest.mark.asyncio
    async def test_owner_releases_returns_released(
        self, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-rel", "u1")
        result = await occupancy.release(project_id="p-rel", user_id="u1")
        assert result == OccupancyResult.RELEASED

    @pytest.mark.asyncio
    async def test_owner_release_deletes_key(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-del", "u1")
        await occupancy.release("p-del", "u1")
        exists = await redis_runtime.client.exists("project:conversation-owner:p-del")
        assert exists == 0

    @pytest.mark.asyncio
    async def test_non_owner_release_returns_not_owner(
        self, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-no-rel", "u1")
        result = await occupancy.release(project_id="p-no-rel", user_id="u2")
        assert result == OccupancyResult.NOT_OWNER

    @pytest.mark.asyncio
    async def test_non_owner_release_does_not_delete_key(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        await occupancy.acquire("p-keep", "u1")
        await occupancy.release("p-keep", "u2")
        stored = await redis_runtime.client.get("project:conversation-owner:p-keep")
        assert stored == b"u1" or stored == "u1"

    @pytest.mark.asyncio
    async def test_release_when_not_occupied_returns_released(
        self, occupancy: OccupancyManager,
    ) -> None:
        result = await occupancy.release(project_id="p-gone", user_id="u1")
        assert result == OccupancyResult.RELEASED


# ---------------------------------------------------------------------------
# TTL constant contract
# ---------------------------------------------------------------------------


class TestOccupancyTtlConstant:
    def test_constant_matches_key_ttl(self) -> None:
        assert OCCUPANCY_TTL_SECONDS == conversation_owner_key.ttl_seconds

    def test_constant_is_exactly_300(self) -> None:
        assert OCCUPANCY_TTL_SECONDS == 300


# ---------------------------------------------------------------------------
# Result vocabulary exhaustiveness
# ---------------------------------------------------------------------------


class TestResultVocabulary:
    """Ensure every result kind is exactly one of the five allowed values."""

    ALLOWED = frozenset({"ACQUIRED", "RENEWED", "OCCUPIED", "RELEASED", "NOT_OWNER"})

    def test_allowed_set_is_exactly_five(self) -> None:
        assert self.ALLOWED == {
            OccupancyResult.ACQUIRED,
            OccupancyResult.RENEWED,
            OccupancyResult.OCCUPIED,
            OccupancyResult.RELEASED,
            OccupancyResult.NOT_OWNER,
        }

    def test_constants_match_enum(self) -> None:
        assert OccupancyResult.ACQUIRED == "ACQUIRED"
        assert OccupancyResult.RENEWED == "RENEWED"
        assert OccupancyResult.OCCUPIED == "OCCUPIED"
        assert OccupancyResult.RELEASED == "RELEASED"
        assert OccupancyResult.NOT_OWNER == "NOT_OWNER"


# ---------------------------------------------------------------------------
# 50-key concurrency race
# ---------------------------------------------------------------------------


class TestRaceFiftyKeys:
    @pytest.mark.asyncio
    async def test_two_users_cannot_acquire_same_project(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        """Execute 50 concurrent acquire-pair races against distinct keys.

        Each project key is fresh (never occupied), so the two
        concurrent ``acquire`` calls must return exactly one ACQUIRED and
        one OCCUPIED — regardless of which call wins the race.
        """
        for attempt in range(50):
            project_id = f"p-race-{attempt}"
            first, second = await asyncio.gather(
                occupancy.acquire(project_id, "u1"),
                occupancy.acquire(project_id, "u2"),
            )
            assert sorted([first, second]) == [
                OccupancyResult.ACQUIRED,
                OccupancyResult.OCCUPIED,
            ], f"Race failure at attempt {attempt} for project {project_id}"


# ---------------------------------------------------------------------------
# NoScriptError recovery (Fix 1)
# ---------------------------------------------------------------------------


class TestScriptRecovery:
    """Verify that OccupancyManager transparently recovers after the
    cached script SHA is invalidated (Redis restart / SCRIPT FLUSH)."""

    @pytest.mark.asyncio
    async def test_acquire_recovers_after_script_flush(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        # Prime the script cache with a first call.
        result = await occupancy.acquire("p-recover-a", "u1")
        assert result == OccupancyResult.ACQUIRED

        # Simulate SCRIPT FLUSH (server restart / failover).
        await redis_runtime.client.script_flush()

        # Next acquire must recover transparently.
        result = await occupancy.acquire("p-recover-b", "u1")
        assert result == OccupancyResult.ACQUIRED

    @pytest.mark.asyncio
    async def test_release_recovers_after_script_flush(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        # Prime the script cache.
        await occupancy.acquire("p-recover-c", "u1")
        result = await occupancy.release("p-recover-c", "u1")
        assert result == OccupancyResult.RELEASED

        # Invalidate scripts, then acquire + release through recovery.
        await redis_runtime.client.script_flush()

        await occupancy.acquire("p-recover-d", "u1")
        result = await occupancy.release("p-recover-d", "u1")
        assert result == OccupancyResult.RELEASED

    @pytest.mark.asyncio
    async def test_renew_works_after_script_flush(
        self, redis_runtime: RedisRuntime, occupancy: OccupancyManager,
    ) -> None:
        # Prime scripts, then flush.
        await occupancy.acquire("p-recover-e", "u1")
        await redis_runtime.client.script_flush()

        # Fresh acquire + renew after recovery.
        await occupancy.acquire("p-recover-f", "u1")
        result = await occupancy.acquire("p-recover-f", "u1")
        assert result == OccupancyResult.RENEWED


# ---------------------------------------------------------------------------
# NOT_OWNER constant re-export
# ---------------------------------------------------------------------------


def test_not_owner_constant_is_correct() -> None:
    assert NOT_OWNER == "NOT_OWNER"


def test_occupied_constant_is_correct() -> None:
    assert OCCUPIED == "OCCUPIED"


def test_released_constant_is_correct() -> None:
    assert RELEASED == "RELEASED"
