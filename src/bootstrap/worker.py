"""Platform V2 Worker process entrypoint.

The Worker owns the PostgreSQL business engine, Redis infrastructure,
and the LangGraph CheckpointStore. Phase 1 performs no delivery work;
the process opens its resources, waits for a termination signal, and
closes resources in reverse order.
"""

from __future__ import annotations

import asyncio

from src.bootstrap.lifespan import (
    AsyncEngineResource,
    LifecycleResource,
    ManagedLifecycle,
    wait_for_shutdown,
)
from src.bootstrap.settings import Settings
from src.integrations.redis.client import RedisRuntime
from src.persistence.postgres.checkpoints import CheckpointStore
from src.persistence.postgres.session import create_engine


class CheckpointSetupResource:
    """Adapt a ``CheckpointStore`` so opening the resource also runs setup.

    The Worker owns the official LangGraph checkpoint tables.  When its
    lifecycle opens this resource, the store is opened and
    ``AsyncPostgresSaver.setup()`` is run, guaranteeing the checkpoint
    tables exist before any Graph invocation.  The API and Scheduler
    never construct this resource, so they stay free of checkpoint
    ownership.
    """

    def __init__(self, store: CheckpointStore) -> None:
        self._store = store

    async def open(self) -> None:
        await self._store.open()
        await self._store.setup()

    async def close(self) -> None:
        await self._store.close()

    @property
    def store(self) -> CheckpointStore:
        """The wrapped store, for graph compilation and diagnostics."""
        return self._store


def build_worker_lifecycle(settings: Settings) -> ManagedLifecycle:
    """Build the Worker resource set: PostgreSQL, Redis, CheckpointStore.

    The Worker owns the CheckpointStore so future Graph execution can
    recover delivery runs from PostgreSQL checkpoints.  Startup runs the
    official ``AsyncPostgresSaver.setup()`` so the checkpoint tables are
    initialized before the store is usable.
    """
    resources: dict[str, LifecycleResource] = {}
    if settings.database_url is not None:
        resources["postgres"] = AsyncEngineResource(create_engine(settings))
    if settings.redis_url is not None:
        resources["redis"] = RedisRuntime(url=settings.redis_url.get_secret_value())
    if settings.checkpoint_database_url is not None:
        resources["checkpoint"] = CheckpointSetupResource(CheckpointStore(settings))
    return ManagedLifecycle(resources)


async def run_worker(settings: Settings | None = None) -> None:
    """Run the Worker until a termination signal arrives."""
    runtime_settings = settings if settings is not None else Settings()
    lifecycle = build_worker_lifecycle(runtime_settings)
    async with lifecycle:
        await wait_for_shutdown()


def main() -> None:
    """Worker entrypoint for ``python -m src.bootstrap.worker``."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
