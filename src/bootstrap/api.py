"""Platform V2 API process entrypoint.

The API process owns the HTTP/SSE adapters. Phase 1 exposes only
``GET /health/live`` and ``GET /health/ready``; business HTTP adapters
land in later phases. Resources are opened in lifespan startup and
closed in reverse order on shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.bootstrap.lifespan import (
    AsyncEngineResource,
    LifecycleResource,
    ManagedLifecycle,
)
from src.bootstrap.settings import Settings
from src.integrations.redis.client import RedisRuntime
from src.persistence.postgres.session import create_engine
from src.transport.http.health import router as health_router


def build_api_lifecycle(settings: Settings) -> ManagedLifecycle:
    """Build the API process resource set: PostgreSQL + Redis.

    The API does not own the CheckpointStore — that belongs to the
    Worker. Resources are opened in declaration order and closed in
    reverse order.
    """
    resources: dict[str, LifecycleResource] = {}
    if settings.database_url is not None:
        resources["postgres"] = AsyncEngineResource(create_engine(settings))
    if settings.redis_url is not None:
        resources["redis"] = RedisRuntime(url=settings.redis_url.get_secret_value())
    return ManagedLifecycle(resources)


def _dependency_probe(
    lifecycle: ManagedLifecycle, name: str
) -> Callable[[], Awaitable[bool]]:
    """Return an async probe reporting whether the named resource is ready.

    An unconfigured resource (no URL) reports ``False`` so readiness can
    surface a missing dependency as ``unavailable``.
    """

    async def _probe() -> bool:
        resource = lifecycle.get(name)
        if resource is None:
            return False
        ping = getattr(resource, "ping", None)
        if ping is None:
            return False
        try:
            return bool(await ping())
        except Exception:
            return False

    return _probe


def build_app(settings: Settings | None = None) -> FastAPI:
    """Create the V2 FastAPI application.

    The lifespan builds the API resource set lazily so importing the
    module never requires external services. Tests pass explicit
    settings; production deployments rely on the injected ``PLATFORM_*``
    environment.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime_settings = settings if settings is not None else Settings()
        lifecycle = build_api_lifecycle(runtime_settings)
        await lifecycle.start()
        app.state.lifecycle = lifecycle
        app.state.health_probes = {
            "postgres": _dependency_probe(lifecycle, "postgres"),
            "redis": _dependency_probe(lifecycle, "redis"),
        }
        try:
            yield
        finally:
            await lifecycle.stop()

    # Phase 1 exposes only the two health routes: the default OpenAPI,
    # Swagger docs, ReDoc, and OAuth2 redirect routes are disabled.
    app = FastAPI(
        lifespan=lifespan,
        title="Platform V2 API",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(health_router)
    return app


app = build_app()
