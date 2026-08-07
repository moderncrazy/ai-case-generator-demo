"""Health endpoints for the V2 API process.

Phase 1 exposes exactly two endpoints:

- ``GET /health/live`` — process liveness with no external dependency.
- ``GET /health/ready`` — readiness against PostgreSQL and Redis.

The readiness payload reports dependency state only (``ready`` /
``unavailable``); it never includes URLs, hosts, ports, or credentials.
Probes are wired by the API lifespan through ``app.state.health_probes``,
a mapping of dependency name to an async ``Callable[[], Awaitable[bool]]``.
Each probe runs under a deadline so a stalled dependency cannot hang the
readiness endpoint; a timeout becomes the same secret-safe
``unavailable`` state.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

DependencyProbe = Callable[[], Awaitable[bool]]

# Bound each readiness probe; tests may override the per-probe deadline
# via ``app.state.probe_timeout_seconds``.
PROBE_TIMEOUT_SECONDS = 1.0

# Readiness is authoritative only when every required dependency is
# confirmed ready; anything less (missing, failed, or timed out probe)
# is ``unavailable`` and degrades the endpoint.
REQUIRED_PROBES = ("postgres", "redis")


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Report process liveness without touching any external service."""
    return {"status": "alive"}


async def _run_probe(
    name: str, probe: DependencyProbe, timeout: float
) -> tuple[str, str]:
    """Run one dependency probe under a deadline.

    Returns the dependency state as a secret-safe string: ``ready`` on
    success, ``unavailable`` on failure, exception, or timeout.
    """
    try:
        ready = bool(await asyncio.wait_for(probe(), timeout=timeout))
        return name, "ready" if ready else "unavailable"
    except Exception:
        return name, "unavailable"


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Report PostgreSQL and Redis readiness without exposing secrets.

    Every required dependency must probe ``ready``; a missing, failed, or
    timed-out probe is reported as ``unavailable`` (never silently
    dropped) and degrades the endpoint to 503.
    """
    probes: Mapping[str, DependencyProbe] = getattr(
        request.app.state, "health_probes", {}
    )
    timeout: float = getattr(
        request.app.state, "probe_timeout_seconds", PROBE_TIMEOUT_SECONDS
    )
    # Execute only the required probes; extra entries in health_probes are
    # ignored — they must not run, delay readiness, or appear in the response.
    tasks = [
        _run_probe(name, probes[name], timeout)
        for name in REQUIRED_PROBES
        if name in probes
    ]
    states: dict[str, str] = (
        dict(await asyncio.gather(*tasks)) if tasks else {}
    )
    for name in REQUIRED_PROBES:
        states.setdefault(name, "unavailable")
    all_ready = all(states.get(name) == "ready" for name in REQUIRED_PROBES)
    return JSONResponse(
        content={"status": "ready" if all_ready else "degraded", **states},
        status_code=200 if all_ready else 503,
    )
