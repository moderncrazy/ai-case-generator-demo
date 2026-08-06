"""Contract tests for the V2 API health endpoints.

Phase 1 exposes exactly two endpoints: ``GET /health/live`` and
``GET /health/ready``. Liveness never touches external services;
readiness reports PostgreSQL and Redis state without exposing URLs,
hosts, ports, or credentials.
"""

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
async def test_liveness_does_not_require_dependencies(api_client) -> None:
    response = await api_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


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


def test_api_app_exposes_only_health_routes() -> None:
    paths = set(default_app.openapi()["paths"])
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert not any(p.startswith("/api/") for p in paths)
    assert not any(p.startswith("/projects") for p in paths)
