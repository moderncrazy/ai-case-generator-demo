"""Health endpoints for the V2 API process.

Phase 1 exposes exactly two endpoints:

- ``GET /health/live`` — process liveness with no external dependency.
- ``GET /health/ready`` — readiness against PostgreSQL and Redis.

The readiness payload reports dependency state only (``ready`` /
``unavailable``); it never includes URLs, hosts, ports, or credentials.
Probes are wired by the API lifespan through ``app.state.health_probes``,
a mapping of dependency name to an async ``Callable[[], Awaitable[bool]]``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

DependencyProbe = Callable[[], Awaitable[bool]]


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Report process liveness without touching any external service."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Report PostgreSQL and Redis readiness without exposing secrets."""
    probes: Mapping[str, DependencyProbe] = getattr(
        request.app.state, "health_probes", {}
    )
    states: dict[str, str] = {}
    all_ready = True
    for name, probe in probes.items():
        try:
            ready = bool(await probe())
        except Exception:
            ready = False
        states[name] = "ready" if ready else "unavailable"
        all_ready = all_ready and ready

    return JSONResponse(
        content={"status": "ready" if all_ready else "degraded", **states},
        status_code=200 if all_ready else 503,
    )
