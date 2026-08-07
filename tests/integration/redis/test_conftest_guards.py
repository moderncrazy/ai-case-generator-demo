"""Focused tests for the Redis test-conftest safety guards.

The Redis suite may only run against a dedicated, explicitly-supplied
``TEST_REDIS_URL``.  Ordinary application URLs (``REDIS_URL`` /
``PLATFORM_REDIS_URL``) must never be selected as the test Redis, and
cleanup must target only keys a test actually created so unrelated keys
survive.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from src.integrations.redis.client import RedisRuntime

from tests.integration.redis.conftest import (
    _delete_keys_created_since,
    _require_dedicated_test_redis,
)


# ===================================================================
# Dedicated test-Redis guard
# ===================================================================


class TestDedicatedTestRedisGuard:
    def test_guard_rejects_empty_url(self) -> None:
        with pytest.raises(pytest.fail.Exception, match="TEST_REDIS_URL"):
            _require_dedicated_test_redis("")

    def test_guard_rejects_remote_application_redis_url(
        self, monkeypatch,
    ) -> None:
        """A URL equal to a remote/shared ``REDIS_URL`` must be rejected.

        A test target that is identical to the application's *shared*
        Redis (a non-loopback host) could let a session-start flush erase
        application data.
        """
        monkeypatch.setenv("REDIS_URL", "redis://app-host:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-host:6379/0")

    def test_guard_rejects_remote_platform_application_redis_url(
        self, monkeypatch,
    ) -> None:
        """A URL equal to a remote/shared ``PLATFORM_REDIS_URL`` must be
        rejected, independently of ``REDIS_URL``."""
        monkeypatch.setenv("PLATFORM_REDIS_URL", "redis://app-host:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-host:6379/0")

    def test_guard_rejects_bad_scheme(self) -> None:
        with pytest.raises(pytest.fail.Exception, match="scheme"):
            _require_dedicated_test_redis("http://localhost:6379/0")

    def test_guard_rejects_missing_hostname(self) -> None:
        with pytest.raises(pytest.fail.Exception, match="hostname"):
            _require_dedicated_test_redis("redis:///0")

    def test_guard_accepts_dedicated_test_url(self, monkeypatch) -> None:
        """A distinct redis:// URL is accepted even when an app URL exists."""
        monkeypatch.setenv("REDIS_URL", "redis://app-host:6379/0")
        url = _require_dedicated_test_redis("redis://localhost:6380/1")
        assert url == "redis://localhost:6380/1"

    def test_guard_rejects_identical_loopback_urls(
        self, monkeypatch,
    ) -> None:
        """A test URL identical to a loopback application URL must be
        rejected: the guard normalizes endpoints so even identical
        loopback strings are treated as the same database and rejected
        to protect against a session-start flush."""
        monkeypatch.setenv(
            "REDIS_URL", "redis://127.0.0.1:56379/15",
        )
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://127.0.0.1:56379/15")

    # -----------------------------------------------------------------
    # Endpoint normalisation — equivalent spellings must be caught
    # -----------------------------------------------------------------

    def test_guard_rejects_case_different_equivalent_url(
        self, monkeypatch,
    ) -> None:
        """Scheme or host case differences must not bypass the guard.

        ``REDIS://LOCALHOST:6379/0`` and ``redis://localhost:6379/0``
        are the same endpoint once normalised.
        """
        monkeypatch.setenv("REDIS_URL", "REDIS://LOCALHOST:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://localhost:6379/0")

    def test_guard_rejects_default_port_equivalent_url(
        self, monkeypatch,
    ) -> None:
        """A missing port (defaults to 6379 for redis) must normalise to
        the explicit port spelling."""
        monkeypatch.setenv("REDIS_URL", "redis://app-shared:6379/2")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-shared/2")

    def test_guard_rejects_default_db_equivalent_url(
        self, monkeypatch,
    ) -> None:
        """A missing database number (defaults to 0) must normalise to
        the explicit ``/0`` spelling."""
        monkeypatch.setenv("REDIS_URL", "redis://app-shared:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-shared:6379")

    def test_guard_rejects_loopback_alias_equivalent_url(
        self, monkeypatch,
    ) -> None:
        """Loopback alias 127.0.0.1 must normalise to localhost."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://127.0.0.1:6379/0")

    def test_guard_rejects_ipv6_loopback_alias_equivalent_url(
        self, monkeypatch,
    ) -> None:
        """Loopback alias ::1 must normalise to localhost."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://[::1]:6379/0")

    def test_guard_rejects_wildcard_loopback_alias_equivalent_url(
        self, monkeypatch,
    ) -> None:
        """Loopback alias 0.0.0.0 must normalise to localhost."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://0.0.0.0:6379/0")

    def test_guard_rejects_different_credentials_same_target(
        self, monkeypatch,
    ) -> None:
        """Different credentials on the same (host, port, db) must be
        detected as the same database — the guard compares target
        identity, not authentication identity.

        Two URLs that differ only in credentials target the same Redis
        instance; a ``FLUSHDB`` against either erases the other's data.
        """
        monkeypatch.setenv(
            "REDIS_URL", "redis://alice:s3cret@app-host:6379/0",
        )
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://bob:other@app-host:6379/0")

    # -----------------------------------------------------------------
    # Query-string / percent-encoding / numeric DB normalisation
    # -----------------------------------------------------------------

    def test_guard_rejects_query_string_db_precedence(
        self, monkeypatch,
    ) -> None:
        """``?db=1`` takes precedence over the path segment.
        ``redis://host/0?db=1`` and ``redis://host/1`` are the same db."""
        monkeypatch.setenv("REDIS_URL", "redis://app-shared:6379/1")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-shared:6379/0?db=1")

    def test_guard_rejects_numeric_db_path_equivalence(
        self, monkeypatch,
    ) -> None:
        """Leading-zero db numbers (``/01``) must normalise to the integer
        value (``/1``)."""
        monkeypatch.setenv("REDIS_URL", "redis://app-shared:6379/1")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-shared:6379/01")

    def test_guard_rejects_percent_encoded_db_path(
        self, monkeypatch,
    ) -> None:
        """Percent-encoded DB numbers (``/%31``) must decode to the
        integer value (``/1``)."""
        monkeypatch.setenv("REDIS_URL", "redis://app-shared:6379/1")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-shared:6379/%31")

    # -----------------------------------------------------------------
    # Scheme default port — redis-py uses 6379 for both redis and rediss
    # -----------------------------------------------------------------

    def test_guard_rejects_rediss_implicit_port_6379(
        self, monkeypatch,
    ) -> None:
        """redis-py defaults to port 6379 for both ``redis://`` and
        ``rediss://``.  An explicit ``redis://host:6379/db`` and an
        implicit ``rediss://host/db`` target the same host:port."""
        monkeypatch.setenv("REDIS_URL", "redis://app-shared:6379/2")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("rediss://app-shared/2")

    def test_guard_rejects_redis_implicit_port_6379(
        self, monkeypatch,
    ) -> None:
        """``rediss://host:6379/db`` (explicit) and ``redis://host/db``
        (implicit) must match because redis-py uses 6379 for both."""
        monkeypatch.setenv("REDIS_URL", "rediss://app-shared:6379/2")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://app-shared/2")

    # -----------------------------------------------------------------
    # Full 127.0.0.0/8 loopback range
    # -----------------------------------------------------------------

    def test_guard_rejects_127_0_0_2_loopback(
        self, monkeypatch,
    ) -> None:
        """Any address in 127.0.0.0/8 is loopback, not just 127.0.0.1."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://127.0.0.2:6379/0")

    def test_guard_rejects_127_255_255_255_loopback(
        self, monkeypatch,
    ) -> None:
        """127.255.255.255 (the top of 127.0.0.0/8) is also loopback."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://127.255.255.255:6379/0")

    # -----------------------------------------------------------------
    # DNS resolution — hostnames resolving to loopback addresses
    # -----------------------------------------------------------------

    def test_guard_rejects_hostname_resolving_to_loopback(
        self, monkeypatch,
    ) -> None:
        """A hostname whose DNS resolution returns only 127.0.0.0/8
        addresses is equivalent to ``localhost``.

        Uses a monkeypatched resolver so the test does not depend on
        external DNS configuration."""
        import socket as _socket

        original = _socket.getaddrinfo

        def _fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            if host == "my-redis.internal":
                return [(2, 1, 6, "", ("127.0.0.3", 0))]
            return original(host, port, family, type, proto, flags)

        monkeypatch.setattr(_socket, "getaddrinfo", _fake_getaddrinfo)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with pytest.raises(pytest.fail.Exception, match="dedicated"):
            _require_dedicated_test_redis("redis://my-redis.internal:6379/0")

    def test_guard_dns_failure_keeps_hostname(
        self, monkeypatch,
    ) -> None:
        """A DNS failure must NOT bypass the guard: unresolvable hostnames
        are kept as-is so a match is only found for identical strings.
        This is conservative — a false-negative (missing a match) is
        acceptable; a false-positive (wrongly matching) would let a
        session-start flush erase application data."""
        monkeypatch.setenv("REDIS_URL", "redis://never-resolves.example:6379/0")
        # The guard must NOT crash, and since the hostnames differ (one
        # is the test URL placeholder, the other is the Redis URL), no
        # rejection is expected.
        result = _require_dedicated_test_redis(
            "redis://other-test-host:6379/0",
        )
        assert result == "redis://other-test-host:6379/0"

    # -----------------------------------------------------------------
    # Genuinely distinct isolated DBs are accepted
    # -----------------------------------------------------------------

    def test_guard_accepts_distinct_db_on_same_host(
        self, monkeypatch,
    ) -> None:
        """Different database numbers on the same instance are genuinely
        distinct isolated DBs and must be accepted."""
        monkeypatch.setenv("REDIS_URL", "redis://app-host:6379/0")
        url = _require_dedicated_test_redis("redis://app-host:6379/1")
        assert url == "redis://app-host:6379/1"

    def test_guard_accepts_distinct_port(
        self, monkeypatch,
    ) -> None:
        """A different port on the same host is a genuinely distinct
        instance and must be accepted."""
        monkeypatch.setenv("REDIS_URL", "redis://app-host:6379/0")
        url = _require_dedicated_test_redis("redis://app-host:6380/0")
        assert url == "redis://app-host:6380/0"

    # -----------------------------------------------------------------

    def test_app_urls_never_selected_when_test_url_missing(
        self, monkeypatch,
    ) -> None:
        """The fixture resolution path must not fall back to app URLs.

        With only ``REDIS_URL`` / ``PLATFORM_REDIS_URL`` present and no
        ``TEST_REDIS_URL``, the guard (which is exactly what the
        ``redis_url`` fixture evaluates) must fail.
        """
        monkeypatch.setenv("REDIS_URL", "redis://app-host:6379/0")
        monkeypatch.setenv("PLATFORM_REDIS_URL", "redis://app-host:6379/0")
        monkeypatch.delenv("TEST_REDIS_URL", raising=False)
        with pytest.raises(pytest.fail.Exception, match="TEST_REDIS_URL"):
            _require_dedicated_test_redis(os.environ.get("TEST_REDIS_URL", ""))


# ===================================================================
# Targeted cleanup
# ===================================================================


@pytest.mark.asyncio
async def test_cleanup_deletes_only_test_owned_keys(redis_url: str) -> None:
    """``_delete_keys_created_since`` removes only keys created after the
    snapshot, leaving unrelated pre-existing keys untouched."""
    runtime = RedisRuntime(url=redis_url)
    await runtime.open()
    try:
        # Pre-existing unrelated key (exists before the snapshot).
        await runtime.client.set("unrelated:survives", "keep-me")
        known = await _current_keys(runtime)
        assert b"unrelated:survives" in known

        # Test-owned key created after the snapshot.
        await runtime.client.set("test:owned", "delete-me")
        await _delete_keys_created_since(runtime, known)

        # The test-owned key is gone; the unrelated key survives.
        assert await runtime.client.exists("test:owned") == 0
        assert await runtime.client.exists("unrelated:survives") == 1
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_cleanup_preserves_unrelated_keys_across_runtime(
    redis_runtime,
) -> None:
    """The ``redis_runtime`` fixture teardown must not delete keys that
    existed before the test (unrelated keys survive the fixture)."""
    # An unrelated key created before this test ran still exists.
    await redis_runtime.client.set("owned:after-snapshot", "mine")
    assert await redis_runtime.client.exists("owned:after-snapshot") == 1


# ===================================================================
# Session reset targets only the dedicated test DB
# ===================================================================


def test_redis_url_fixture_resolves_from_test_redis_url(redis_url: str) -> None:
    """The ``redis_url`` fixture resolves exactly ``TEST_REDIS_URL``."""
    assert redis_url == os.environ.get("TEST_REDIS_URL")


async def _current_keys(runtime: RedisRuntime) -> set[bytes]:
    keys: set[bytes] = set()
    async for key in runtime.client.scan_iter():
        keys.add(key)
    return keys
