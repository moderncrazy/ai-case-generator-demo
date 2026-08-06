"""Lifecycle tests for the API, Worker, and Scheduler bootstrap processes.

Each process opens only the resources it owns and closes them in reverse
open order. The Worker owns the CheckpointStore; the Scheduler opens no
checkpoint or HTTP resources.
"""

import inspect
import os

import pytest
import pytest_asyncio

from src.bootstrap.api import build_api_lifecycle
from src.bootstrap.lifespan import ManagedLifecycle
from src.bootstrap.scheduler import build_scheduler_lifecycle
from src.bootstrap.settings import Settings
from src.bootstrap.worker import build_worker_lifecycle
from src.integrations.redis.client import RedisRuntime
from src.persistence.postgres.checkpoints import CheckpointStore


def _settings_from_env() -> Settings:
    """Build runtime settings from the controller-injected environment."""
    database_url = os.environ.get("PLATFORM_DATABASE_URL") or os.environ.get(
        "TEST_DATABASE_URL", ""
    )
    checkpoint_database_url = os.environ.get("PLATFORM_CHECKPOINT_DATABASE_URL", "")
    redis_url = os.environ.get("PLATFORM_REDIS_URL") or os.environ.get("REDIS_URL", "")
    if not database_url:
        pytest.fail("bootstrap lifecycle tests require a PostgreSQL URL")
    if not redis_url:
        pytest.fail("bootstrap lifecycle tests require a Redis URL")
    return Settings(
        database_url=database_url,
        checkpoint_database_url=checkpoint_database_url or None,
        redis_url=redis_url,
        environment="local",
        _env_file=None,
    )


@pytest.fixture
def test_settings() -> Settings:
    return _settings_from_env()


@pytest_asyncio.fixture
async def api_lifecycle(test_settings: Settings) -> ManagedLifecycle:
    lifecycle = build_api_lifecycle(test_settings)
    await lifecycle.start()
    try:
        yield lifecycle
    finally:
        await lifecycle.stop()


@pytest_asyncio.fixture
async def worker_lifecycle(test_settings: Settings) -> ManagedLifecycle:
    lifecycle = build_worker_lifecycle(test_settings)
    await lifecycle.start()
    try:
        yield lifecycle
    finally:
        await lifecycle.stop()


@pytest_asyncio.fixture
async def scheduler_lifecycle(test_settings: Settings) -> ManagedLifecycle:
    lifecycle = build_scheduler_lifecycle(test_settings)
    await lifecycle.start()
    try:
        yield lifecycle
    finally:
        await lifecycle.stop()


@pytest.mark.asyncio
async def test_api_lifecycle_opens_postgres_and_redis(api_lifecycle) -> None:
    postgres = api_lifecycle.get("postgres")
    redis = api_lifecycle.get("redis")
    assert postgres is not None
    assert redis is not None
    assert api_lifecycle.get("checkpoint") is None
    assert await postgres.ping()  # type: ignore[attr-defined]
    assert await redis.ping()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_worker_lifecycle_owns_checkpoint_store(worker_lifecycle) -> None:
    checkpoint = worker_lifecycle.get("checkpoint")
    assert isinstance(checkpoint, CheckpointStore)
    assert checkpoint.saver is not None
    assert worker_lifecycle.get("postgres") is not None
    assert worker_lifecycle.get("redis") is not None


@pytest.mark.asyncio
async def test_scheduler_lifecycle_opens_no_checkpoint_resource(
    scheduler_lifecycle,
) -> None:
    assert scheduler_lifecycle.get("checkpoint") is None
    assert scheduler_lifecycle.get("postgres") is not None
    assert scheduler_lifecycle.get("redis") is not None


def test_scheduler_module_has_no_http_or_checkpoint_dependencies() -> None:
    import src.bootstrap.scheduler as scheduler

    # The Scheduler module never imports checkpoint or HTTP adapters:
    # the class names are absent from the module namespace and no
    # transport package is referenced anywhere in the source.
    assert not hasattr(scheduler, "CheckpointStore")
    assert not hasattr(scheduler, "FastAPI")
    assert not hasattr(scheduler, "app")
    assert "src.transport" not in inspect.getsource(scheduler)


class _RecordingResource:
    """Minimal lifecycle resource that records open/close events."""

    def __init__(self, events: list[str], name: str) -> None:
        self._events = events
        self._name = name

    async def open(self) -> None:
        self._events.append(f"open:{self._name}")

    async def close(self) -> None:
        self._events.append(f"close:{self._name}")


@pytest.mark.asyncio
async def test_lifecycle_closes_resources_in_reverse_open_order() -> None:
    events: list[str] = []
    lifecycle = ManagedLifecycle(
        {
            "a": _RecordingResource(events, "a"),
            "b": _RecordingResource(events, "b"),
            "c": _RecordingResource(events, "c"),
        }
    )
    await lifecycle.start()
    assert events == ["open:a", "open:b", "open:c"]
    await lifecycle.stop()
    assert events == [
        "open:a",
        "open:b",
        "open:c",
        "close:c",
        "close:b",
        "close:a",
    ]


@pytest.mark.asyncio
async def test_lifecycle_start_and_stop_are_idempotent() -> None:
    events: list[str] = []
    lifecycle = ManagedLifecycle({"a": _RecordingResource(events, "a")})
    await lifecycle.start()
    await lifecycle.start()
    assert events == ["open:a"]
    await lifecycle.stop()
    await lifecycle.stop()
    assert events == ["open:a", "close:a"]


class _FailingOpenResource:
    """A resource whose ``open()`` always fails."""

    async def open(self) -> None:
        raise RuntimeError("open failed")

    async def close(self) -> None:
        pass


class _FailingCloseResource:
    """A resource that opens successfully but fails on close."""

    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def open(self) -> None:
        self._events.append("open:failing-close")

    async def close(self) -> None:
        self._events.append("close:failing-close")
        raise RuntimeError("close failed")


@pytest.mark.asyncio
async def test_start_preserves_original_failure_when_cleanup_fails() -> None:
    """A partial-open failure must not be masked by a cleanup error.

    ``start()`` opens ``a`` successfully, then ``b`` fails to open.
    During cleanup ``a.close()`` also fails; the original ``open failed``
    error must propagate with the cleanup failure retained as a note.
    """
    events: list[str] = []
    lifecycle = ManagedLifecycle(
        {
            "a": _FailingCloseResource(events),
            "b": _FailingOpenResource(),
        }
    )
    with pytest.raises(RuntimeError, match="open failed") as exc_info:
        await lifecycle.start()

    notes = getattr(exc_info.value, "__notes__", [])
    assert any("cleanup after partial startup failed" in note for note in notes)
    assert any("close failed" in note for note in notes)
    assert events == ["open:failing-close", "close:failing-close"]


def test_worker_and_scheduler_modules_expose_dash_m_entrypoints() -> None:
    import src.bootstrap.scheduler as scheduler
    import src.bootstrap.worker as worker

    assert callable(worker.main)
    assert callable(scheduler.main)
    assert '__name__ == "__main__"' in inspect.getsource(worker)
    assert '__name__ == "__main__"' in inspect.getsource(scheduler)
