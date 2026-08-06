"""Platform V2 Scheduler process entrypoint.

The Scheduler owns future recovery scans against PostgreSQL and uses
Redis only to lower polling latency. It must not open checkpoint or HTTP
resources — those belong to the Worker and API processes.
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
from src.persistence.postgres.session import create_engine


def build_scheduler_lifecycle(settings: Settings) -> ManagedLifecycle:
    """Build the Scheduler resource set: PostgreSQL + Redis only.

    The Scheduler never opens a CheckpointStore and never builds HTTP
    adapters; those are owned by the Worker and API processes.
    """
    resources: dict[str, LifecycleResource] = {}
    if settings.database_url is not None:
        resources["postgres"] = AsyncEngineResource(create_engine(settings))
    if settings.redis_url is not None:
        resources["redis"] = RedisRuntime(url=settings.redis_url.get_secret_value())
    return ManagedLifecycle(resources)


async def run_scheduler(settings: Settings | None = None) -> None:
    """Run the Scheduler until a termination signal arrives."""
    runtime_settings = settings if settings is not None else Settings()
    lifecycle = build_scheduler_lifecycle(runtime_settings)
    async with lifecycle:
        await wait_for_shutdown()


def main() -> None:
    """Scheduler entrypoint for ``python -m src.bootstrap.scheduler``."""
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
