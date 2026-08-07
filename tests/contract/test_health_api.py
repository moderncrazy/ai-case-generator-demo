"""Contract tests for the V2 API health endpoints.

Phase 1 exposes exactly two endpoints: ``GET /health/live`` and
``GET /health/ready``. Liveness never touches external services;
readiness reports PostgreSQL and Redis state without exposing URLs,
hosts, ports, or credentials. Default FastAPI routes (OpenAPI, docs,
ReDoc) are disabled.
"""

import asyncio
import os

import httpx
import pytest
import pytest_asyncio

from src.bootstrap.api import app as default_app
from src.bootstrap.api import build_app
from src.bootstrap.settings import Settings
from src.transport.http.health import router as health_router


def _test_settings() -> Settings:
    """Build runtime settings from the controller-injected environment."""
    database_url = os.environ.get("PLATFORM_DATABASE_URL") or os.environ.get(
        "TEST_DATABASE_URL", ""
    )
    redis_url = os.environ.get("PLATFORM_REDIS_URL") or os.environ.get("REDIS_URL", "")
    if not database_url:
        pytest.fail(
            "contract health tests require PLATFORM_DATABASE_URL or TEST_DATABASE_URL"
        )
    if not redis_url:
        pytest.fail("contract health tests require PLATFORM_REDIS_URL or REDIS_URL")
    return Settings(
        database_url=database_url,
        redis_url=redis_url,
        environment="local",
        _env_file=None,
    )


@pytest_asyncio.fixture
async def api_client() -> httpx.AsyncClient:
    """An httpx client driving the V2 API with its real lifespan."""
    app = build_app(_test_settings())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_liveness_does_not_require_dependencies() -> None:
    """Liveness answers 200 even when every dependency is down."""
    from fastapi import FastAPI

    app = FastAPI()

    async def _down() -> bool:
        return False

    app.state.health_probes = {"postgres": _down, "redis": _down}
    app.include_router(health_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")
    assert live.status_code == 200
    assert live.json() == {"status": "alive"}
    assert ready.status_code == 503
    assert ready.json()["postgres"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_reports_dependency_state(api_client) -> None:
    response = await api_client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["postgres"] == "ready"
    assert body["redis"] == "ready"


@pytest.mark.asyncio
async def test_readiness_payload_exposes_no_secrets(api_client) -> None:
    response = await api_client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    payload = str(body)
    assert "://" not in payload
    assert set(body) == {"status", "postgres", "redis"}


@pytest.mark.asyncio
async def test_readiness_returns_503_when_dependency_unavailable() -> None:
    from fastapi import FastAPI

    app = FastAPI()

    async def _down() -> bool:
        return False

    app.state.health_probes = {"postgres": _down, "redis": _down}
    app.include_router(health_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["postgres"] == "unavailable"
    assert body["redis"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_bounds_a_stalled_probe() -> None:
    """A never-returning probe becomes ``unavailable`` instead of hanging."""
    from fastapi import FastAPI

    app = FastAPI()

    async def _never() -> bool:
        await asyncio.Event().wait()
        return True

    async def _down() -> bool:
        return False

    app.state.health_probes = {"postgres": _never, "redis": _down}
    app.state.probe_timeout_seconds = 0.1
    app.include_router(health_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # Bound the request from the test side so an unbounded regression
        # fails with a timeout instead of hanging the suite.
        response = await asyncio.wait_for(client.get("/health/ready"), timeout=2.0)
    assert response.status_code == 503
    body = response.json()
    assert body["postgres"] == "unavailable"
    assert body["redis"] == "unavailable"
    assert set(body) == {"status", "postgres", "redis"}


@pytest.mark.asyncio
async def test_readiness_fails_closed_with_no_probes() -> None:
    """With no probes registered, readiness must report both dependencies
    ``unavailable`` with 503 — never an empty ``ready`` (fail open)."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(health_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["postgres"] == "unavailable"
    assert body["redis"] == "unavailable"
    assert set(body) == {"status", "postgres", "redis"}


@pytest.mark.asyncio
async def test_readiness_reports_missing_probe_unavailable() -> None:
    """A partially-registered probe set must still report the missing
    dependency as ``unavailable`` (503), never silently succeed."""
    from fastapi import FastAPI

    app = FastAPI()

    async def _down() -> bool:
        return False

    # Only ``postgres`` is wired; ``redis`` is missing entirely.
    app.state.health_probes = {"postgres": _down}
    app.include_router(health_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["postgres"] == "unavailable"
    assert body["redis"] == "unavailable"
    assert set(body) == {"status", "postgres", "redis"}


@pytest.mark.asyncio
async def test_readiness_ignores_extra_probes_not_in_required_set() -> None:
    """Extra entries in ``health_probes`` must not execute or appear in
    the response — only the required ``postgres`` and ``redis`` probes
    are exposed."""
    from fastapi import FastAPI

    app = FastAPI()

    extra_called = False

    async def _ready() -> bool:
        return True

    async def _extra() -> bool:
        nonlocal extra_called
        extra_called = True
        return True

    app.state.health_probes = {
        "postgres": _ready,
        "redis": _ready,
        "sidecar": _extra,  # NOT in REQUIRED_PROBES
    }
    app.include_router(health_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    # Exact contract: only {status, postgres, redis}
    assert set(body) == {"status", "postgres", "redis"}
    assert body["postgres"] == "ready"
    assert body["redis"] == "ready"
    assert extra_called is False, "extra probe must not execute"


@pytest.mark.asyncio
async def test_readiness_extra_probe_does_not_affect_503_decision() -> None:
    """An extra probe that would fail must neither execute nor influence
    the readiness status — only the two required probes matter."""
    from fastapi import FastAPI

    app = FastAPI()

    extra_called = False

    async def _ready() -> bool:
        return True

    async def _down() -> bool:
        return False

    async def _failing_extra() -> bool:
        nonlocal extra_called
        extra_called = True
        raise RuntimeError("boom")

    # redis is down; sidecar exists but must be ignored
    app.state.health_probes = {
        "postgres": _ready,
        "redis": _down,
        "sidecar": _failing_extra,
    }
    app.include_router(health_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert set(body) == {"status", "postgres", "redis"}
    assert body["postgres"] == "ready"
    assert body["redis"] == "unavailable"
    assert extra_called is False, (
        "extra probe must not execute even when required probes degrade"
    )


def _registered_paths(routes: object) -> set[str]:
    """Collect served route paths, recursing through included routers.

    FastAPI stores ``include_router`` results as ``_IncludedRouter``
    wrappers (``original_router.routes``) rather than flattening them
    into ``app.routes``, so the walk descends any route exposing a
    wrapped ``.original_router`` before falling back to ``.path``.
    """

    paths: set[str] = set()
    for route in routes:  # type: ignore[union-attr]
        subroutes = getattr(getattr(route, "original_router", None), "routes", None)
        if subroutes is not None:
            paths |= _registered_paths(subroutes)
            continue
        path = getattr(route, "path", None)
        if path is not None:
            paths.add(path)
    return paths


@pytest.mark.asyncio
async def test_api_app_exposes_only_health_routes() -> None:
    """The V2 app serves exactly the two health routes.

    Default FastAPI routes (``/openapi.json``, ``/docs``,
    ``/docs/oauth2-redirect``, ``/redoc``) are disabled in Phase 1, and
    no business routes exist yet. The registered-route walk and the HTTP
    probes below agree: only the two health paths are served.
    """
    assert _registered_paths(default_app.routes) == {"/health/live", "/health/ready"}

    transport = httpx.ASGITransport(app=default_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")
        forbidden = {
            "/openapi.json",
            "/docs",
            "/docs/oauth2-redirect",
            "/redoc",
            "/api/projects",
            "/projects",
            "/api/",
            "/unknown",
        }
        forbidden_responses = {path: await client.get(path) for path in forbidden}

    assert live.status_code == 200
    assert ready.status_code in (200, 503)  # served, never 404
    for path, response in forbidden_responses.items():
        assert response.status_code == 404, path
