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
from typing import NamedTuple, Protocol
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from redis.asyncio.connection import parse_url as _redis_parse_url

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


# ---------------------------------------------------------------------------
# Hostname resolution — fail-closed for safety
# ---------------------------------------------------------------------------

_HostIdentity = str  # "localhost", "10.1.2.3", or "10.1.2.3,10.1.2.4"


def _resolve_host_for_guard(host: str) -> _HostIdentity:
    """Resolve *host* to a canonical identifier for the safety guard.

    * Loopback IPs / static aliases → ``"localhost"``
    * Non-loopback literal IPs → the IP as-is
    * Hostnames → DNS resolution **must** succeed and be unambiguous

    Failures that make endpoint identity unprovable cause an immediate
    ``pytest.fail`` — the guard must **never** accept an unresolvable or
    ambiguous application endpoint as proven-distinct.
    """
    # Static aliases (::1, 0.0.0.0).
    mapped = _LOOPBACK_ALIASES.get(host)
    if mapped is not None:
        return mapped

    # Literal loopback IP.
    if _is_loopback_ip(host):
        return "localhost"

    # Non-loopback literal IP — canonicalize via ipaddress.
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass  # Not an IP → hostname, needs resolution.

    # ---- DNS resolution (fail-closed) ----
    try:
        addrs = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        pytest.fail(
            f"Cannot resolve Redis endpoint hostname {host!r}; "
            f"the safety guard requires provable endpoint identity "
            f"before allowing a FLUSHDB fixture to run"
        )

    if not addrs:
        pytest.fail(
            f"DNS resolution for Redis hostname {host!r} returned no "
            f"addresses; cannot verify endpoint identity"
        )

    ips: set[str] = set()
    has_loopback = False
    has_non_loopback = False

    for info in addrs:
        ip = info[4][0]
        # Canonicalize IP via ipaddress for stable comparison.
        try:
            ip = str(ipaddress.ip_address(ip))
        except ValueError:
            pass
        ips.add(ip)
        if _is_loopback_ip(ip):
            has_loopback = True
        else:
            has_non_loopback = True

    if has_loopback and has_non_loopback:
        pytest.fail(
            f"Redis hostname {host!r} resolves to mixed loopback and "
            f"non-loopback addresses; cannot verify endpoint identity"
        )

    if has_loopback:
        return "localhost"

    # All non-loopback — sorted, comma-separated for stable comparison.
    return ",".join(sorted(ips))


def _hosts_share_identity(test: _Endpoint, app: _Endpoint) -> bool:
    """Return True when two endpoints' resolved host identities target
    the same machine or have overlapping IP address sets."""
    if test.host == app.host:
        return True

    # Extract IP components from comma-separated lists.
    a_ips = set(test.host.split(","))
    b_ips = set(app.host.split(","))

    # "localhost" is not an IP — skip overlap check.
    if "localhost" in a_ips or "localhost" in b_ips:
        return False

    # Verify all components are valid IP addresses (IPv4 or IPv6).
    try:
        for ip in a_ips | b_ips:
            ipaddress.ip_address(ip)
    except ValueError:
        return False  # Non-IP component — can't verify overlap.

    # Overlapping IP sets → same endpoint.
    return bool(a_ips & b_ips)


# ---------------------------------------------------------------------------
# Structured endpoint representation — safe for IPv4 and IPv6
# ---------------------------------------------------------------------------


class _Endpoint(NamedTuple):
    """Immutable canonical endpoint identity.

    ``host`` is a resolved host identifier: ``"localhost"`` for loopback,
    a single canonicalised IP for literal addresses, or a comma-separated
    sorted list of canonicalised IPs for multi-address DNS answers.
    ``port`` and ``db`` are always integers.

    The structured representation avoids delimiter-parsing bugs (e.g.
    splitting ``2001:db8::1:6379/0`` on ``:`` for IPv6).
    """
    host: str
    port: int
    db: int


# ---------------------------------------------------------------------------
# Endpoint normalisation — delegates option precedence to redis-py parse_url
# ---------------------------------------------------------------------------


def _normalize_redis_endpoint(url: str) -> _Endpoint:
    """Return a canonical **target-identity** endpoint for a Redis URL.

    Option precedence (``?port=``, ``?db=``, path DB, scheme default
    port, percent-encoding) is delegated entirely to redis-py's own
    ``parse_url()`` — there is no hand-reimplementation of redis-py
    endpoint semantics.

    Credentials and scheme are deliberately **excluded** — the guard
    compares Redis target identity (which process + which database), not
    how you connect.

    Hostnames are resolved via DNS (fail-closed) and all IP addresses
    are canonicalised via ``ipaddress`` so equivalent spellings match.
    """
    try:
        params = _redis_parse_url(url)
    except (ValueError, TypeError) as exc:
        pytest.fail(
            f"redis-py cannot parse Redis URL {url!r}: {exc}"
        )

    host_raw = params.get("host")
    if not host_raw:
        pytest.fail(
            f"Redis URL {url!r} has no discernible host; "
            f"the safety guard requires a valid endpoint"
        )

    host = _resolve_host_for_guard(host_raw)

    # Apply redis-py defaults and coerce to int (parse_url stores
    # authority-port as int but unsupported query-string keys as str).
    try:
        port = int(params.get("port", _DEFAULT_REDIS_PORT))
    except (ValueError, TypeError):
        pytest.fail(
            f"Redis URL {url!r} has an invalid port value: {params['port']!r}"
        )
    try:
        db = int(params.get("db", 0))
    except (ValueError, TypeError):
        pytest.fail(
            f"Redis URL {url!r} has an invalid db value: {params['db']!r}"
        )

    return _Endpoint(host=host, port=port, db=db)


def _require_dedicated_test_redis(url: str) -> str:
    """Reject any URL that is not a safe, dedicated test Redis.

    The suite may only run against an explicitly-supplied
    ``TEST_REDIS_URL``; it never falls back to the application Redis
    (``REDIS_URL`` / ``PLATFORM_REDIS_URL``).  Endpoints are compared
    after full normalisation including DNS resolution so equivalent
    spellings are always detected.

    Malformed or unprovable application endpoints cause the guard to
    abort with a clear ``pytest.fail`` — the fixture must never risk
    flushing application data.
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

        # Exact match (host identity, port, db) → reject.
        if normalized_test == normalized_app:
            pytest.fail(
                f"TEST_REDIS_URL must be a dedicated URL, distinct from "
                f"{name} ({app_url!r}) so tests never flush a shared "
                f"application Redis"
            )

        # Ports or DBs differ → provably distinct endpoints.
        if (normalized_test.port != normalized_app.port
                or normalized_test.db != normalized_app.db):
            continue

        # Same port + db — check for overlapping IP address sets.
        if _hosts_share_identity(normalized_test, normalized_app):
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
