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


def build_worker_lifecycle(settings: Settings) -> ManagedLifecycle:
    """Build the Worker resource set: PostgreSQL, Redis, CheckpointStore.

    The Worker owns the CheckpointStore so future Graph execution can
    recover delivery runs from PostgreSQL checkpoints.
    """
    resources: dict[str, LifecycleResource] = {}
    if settings.database_url is not None:
        resources["postgres"] = AsyncEngineResource(create_engine(settings))
    if settings.redis_url is not None:
        resources["redis"] = RedisRuntime(url=settings.redis_url.get_secret_value())
    if settings.checkpoint_database_url is not None:
        resources["checkpoint"] = CheckpointStore(settings)
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
