"""Integration test fixtures for Redis infrastructure.

The controller supplies the isolated Redis test URL through the
``TEST_REDIS_URL`` environment variable.  This module reads it without
printing, inspecting, or overriding it.  The application Redis URL
(``REDIS_URL`` / ``PLATFORM_REDIS_URL``) is never selected as the test
Redis: a dedicated database is required so tests can never flush
application data.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import parse_qs, unquote, urlparse

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
# Dedicated test-Redis guard
# ---------------------------------------------------------------------------

_DEFAULT_REDIS_PORT = 6379

# Static well-known aliases (0.0.0.0 = "any address", treated as localhost).
_LOOPBACK_ALIASES: dict[str, str] = {
    "::1": "localhost",
    "0.0.0.0": "localhost",
}


def _is_loopback_ip(addr: str) -> bool:
    """Return True when *addr* is an IPv4 127.0.0.0/8 or IPv6 ::1 address."""
    try:
        ip = ipaddress.ip_address(addr)
        return ip.is_loopback or ip == ipaddress.IPv4Address("0.0.0.0")
    except ValueError:
        return False


def _resolve_host_to_localhost(host: str) -> str:
    """Try to resolve *host* via DNS.

    If every resolved address is loopback, return ``"localhost"``.
    Otherwise return *host* unchanged.  A resolution failure keeps the
    original *host* — a false-negative (missing a match) is safe; a
    false-positive (wrongly matching) would let ``FLUSHDB`` erase
    application data.
    """
    try:
        addrs = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return host

    if not addrs:
        return host

    for info in addrs:
        resolved = info[4][0]
        if not _is_loopback_ip(resolved):
            return host

    return "localhost"


def _normalize_db_path(parsed) -> str:
    """Extract and normalise the database number from a parsed URL.

    The query-string ``?db=N`` takes precedence over the path segment.
    Percent-encoding is decoded and leading zeros are stripped so
    ``/01``, ``/%31``, and ``/1?db=0`` all normalise to ``1``.
    Non-numeric values are kept as-is (conservative comparison).
    """
    raw = "0"
    query_params = parse_qs(parsed.query)
    if "db" in query_params:
        raw = query_params["db"][0]
    else:
        raw = (parsed.path or "").lstrip("/") or "0"

    # Decode percent-encoding.  On malformed encoding, keep the raw
    # string unchanged — different spellings won't accidentally match.
    try:
        raw = unquote(raw)
    except (ValueError, TypeError):
        pass

    # Strip leading zeros for numeric values.
    try:
        return str(int(raw))
    except ValueError:
        return raw


def _normalize_redis_endpoint(url: str) -> str:
    """Return a canonical **target-identity** identifier for a Redis URL.

    Two URLs that target the same logical Redis database must normalise
    to the same string.  Credentials are deliberately **excluded** from
    the canonical form — the guard compares Redis target identity, not
    authentication identity.

    Normalisations applied:

    * scheme, host, and DB are lower-cased
    * percent-encoding is decoded in host and DB path
    * default port 6379 (redis-py's default for both ``redis://`` and
      ``rediss://``) is made explicit
    * missing DB defaults to ``0``
    * query-string ``?db=N`` takes precedence over the path number
    * leading zeros are stripped from numeric DB paths
    * all 127.0.0.0/8 and ``::1`` addresses resolve to ``localhost``
    * hostnames whose DNS resolves entirely to loopback addresses are
      normalised to ``localhost`` (DNS failures keep the original
      hostname to stay safe)
    * ``0.0.0.0`` (wildcard bind) is treated as ``localhost``
    """
    parsed = urlparse(url)

    # --- host ---
    host = (parsed.hostname or "").lower()

    # Decode percent-encoding in hostname.
    try:
        host = unquote(host)
    except (ValueError, TypeError):
        pass

    # Static aliases first.
    host = _LOOPBACK_ALIASES.get(host, host)

    # Any 127.0.0.0/8 or ::1 IP → localhost.
    if _is_loopback_ip(host):
        host = "localhost"

    # DNS resolution for non-IP hostnames not already canonicalised.
    if host != "localhost":
        host = _resolve_host_to_localhost(host)

    # --- port ---
    port = parsed.port
    if port is None:
        port = _DEFAULT_REDIS_PORT

    # --- database ---
    db = _normalize_db_path(parsed)

    # Canonical form: host:port/db only.
    # Scheme and credentials are deliberately excluded — the guard
    # compares Redis target identity (which process + database), not
    # connection parameters or authentication identity.
    return f"{host}:{port}/{db}"


def _require_dedicated_test_redis(url: str) -> str:
    """Reject any URL that is not a safe, dedicated test Redis.

    The suite may only run against an explicitly-supplied
    ``TEST_REDIS_URL``; it never falls back to the application Redis
    (``REDIS_URL`` / ``PLATFORM_REDIS_URL``).  Endpoints are compared
    after normalisation so equivalent spellings (case, default port,
    default database, loopback aliases, credentials, query-string DB,
    percent-encoding, numeric DB equivalence) are always detected as
    the same database — a session-start flush must never be able to
    erase application data.
    """
    if not url:
        pytest.fail(
            "TEST_REDIS_URL environment variable is not set; "
            "the controller must supply a dedicated test Redis URL"
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("redis", "rediss"):
        pytest.fail(
            f"TEST_REDIS_URL scheme must be redis or rediss, got "
            f"{parsed.scheme!r}"
        )
    if not parsed.hostname:
        pytest.fail(
            f"TEST_REDIS_URL must include a hostname, got {url!r}"
        )

    normalized_test = _normalize_redis_endpoint(url)

    for name in ("REDIS_URL", "PLATFORM_REDIS_URL"):
        app_url = os.environ.get(name, "")
        if not app_url:
            continue
        normalized_app = _normalize_redis_endpoint(app_url)
        if normalized_test == normalized_app:
            pytest.fail(
                f"TEST_REDIS_URL must be a dedicated URL, distinct from "
                f"{name} ({app_url!r}) so tests never flush a shared "
                f"application Redis"
            )
    return url


# ---------------------------------------------------------------------------
# Redis URL fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Return the dedicated test Redis URL supplied by the controller.

    Only ``TEST_REDIS_URL`` is accepted; ordinary application Redis URLs
    are rejected so test cleanup can never touch application data.
    """
    return _require_dedicated_test_redis(os.environ.get("TEST_REDIS_URL", ""))


# ---------------------------------------------------------------------------
# Per-session reset of the dedicated test Redis
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _reset_test_redis(redis_url: str) -> None:
    """Flush the dedicated test Redis once per session.

    This is the only ``FLUSHDB`` in the suite, and it targets exactly the
    dedicated ``TEST_REDIS_URL`` guarded above — never the application
    Redis.  Per-test cleanup removes only the keys each test creates.
    """

    async def _flush() -> None:
        runtime = RedisRuntime(url=redis_url)
        await runtime.open()
        try:
            await runtime.client.flushdb()
        finally:
            await runtime.close()

    asyncio.run(_flush())


# ---------------------------------------------------------------------------
# Targeted key cleanup
# ---------------------------------------------------------------------------


async def _current_keys(runtime: RedisRuntime) -> set[bytes]:
    """Return the set of keys currently present in the test Redis."""
    keys: set[bytes] = set()
    async for key in runtime.client.scan_iter():
        keys.add(key)
    return keys


async def _delete_keys_created_since(
    runtime: RedisRuntime,
    known_keys: set[bytes],
) -> None:
    """Delete only the keys created after *known_keys* was snapshotted.

    Keys that already existed before the test are preserved; only the
    keys the current test created are removed.
    """
    current = await _current_keys(runtime)
    created = current - known_keys
    if created:
        await runtime.client.delete(*created)


# ---------------------------------------------------------------------------
# RedisRuntime fixture (function-scoped to isolate test state)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_runtime(
    redis_url: str, _reset_test_redis: None,
) -> AsyncGenerator[RedisRuntime, None]:
    """Provide an opened RedisRuntime with targeted per-test cleanup.

    The session-scoped ``_reset_test_redis`` flush runs once before the
    first runtime is requested.  Teardown deletes only the keys this
    test created, preserving unrelated pre-existing keys.
    """
    runtime = RedisRuntime(url=redis_url)
    await runtime.open()
    known = await _current_keys(runtime)
    try:
        yield runtime
    finally:
        await _delete_keys_created_since(runtime, known)
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
