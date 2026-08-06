"""Integration test fixtures for Redis infrastructure.

The controller supplies the isolated Redis test URL through the process
environment.  This module reads it without printing, inspecting, or
overriding it.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Protocol

import pytest
import pytest_asyncio

from src.integrations.redis.client import RedisRuntime
from src.integrations.redis.scripts import OccupancyManager


# ---------------------------------------------------------------------------
# Fake clock for TTL-sensitive tests
# ---------------------------------------------------------------------------


class FakeClock:
    """A controllable clock for testing TTL-sensitive occupancy logic."""

    def __init__(self) -> None:
        self._now = datetime.now(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, *, seconds: int = 0) -> None:
        self._now += timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Redis URL fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Return the Redis URL supplied by the controller.

    The controller sets the test Redis URL through the process environment.
    This fixture reads it and fails fast if it is missing.
    """
    for name in ("REDIS_URL", "PLATFORM_REDIS_URL"):
        url = os.environ.get(name, "")
        if url:
            return url
    pytest.fail(
        "Redis test URL not found in environment; "
        "the controller must supply REDIS_URL or PLATFORM_REDIS_URL"
    )


# ---------------------------------------------------------------------------
# RedisRuntime fixture (function-scoped to isolate test state)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_runtime(redis_url: str) -> AsyncGenerator[RedisRuntime, None]:
    """Provide an opened RedisRuntime that is flushed and closed per test."""
    runtime = RedisRuntime(url=redis_url)
    await runtime.open()
    # Flush the test database so every test starts with clean state.
    await runtime.flushdb()
    try:
        yield runtime
    finally:
        await runtime.close()


# ---------------------------------------------------------------------------
# OccupancyManager fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def occupancy(redis_runtime: RedisRuntime) -> OccupancyManager:
    """Return an OccupancyManager backed by the test Redis runtime."""
    return OccupancyManager(client=redis_runtime.client)


# ---------------------------------------------------------------------------
# FakeClock fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_clock() -> FakeClock:
    """Return a controllable fake clock for TTL-sensitive tests."""
    return FakeClock()
