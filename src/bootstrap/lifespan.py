"""Shared process lifecycle machinery for V2 entrypoints.

Each V2 process owns a distinct set of resources. This module provides a
:class:`ManagedLifecycle` that opens resources in declaration order and
closes them in reverse order, plus an adapter that gives the SQLAlchemy
``AsyncEngine`` a uniform open/close/ping interface matching
``RedisRuntime``.
"""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Mapping
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class LifecycleResource(Protocol):
    """A process-owned resource with an open/close lifecycle."""

    async def open(self) -> None: ...

    async def close(self) -> None: ...


class ManagedLifecycle:
    """Open resources in order and close them in reverse order.

    ``start()`` and ``stop()`` are idempotent, so entrypoints can call
    them unconditionally. If ``start()`` fails partway, already-opened
    resources are closed in reverse order before the error propagates.
    """

    def __init__(self, resources: Mapping[str, LifecycleResource]) -> None:
        self._resources = dict(resources)
        self._opened: list[str] = []

    async def start(self) -> None:
        if self._opened:
            return
        try:
            for name, resource in self._resources.items():
                await resource.open()
                self._opened.append(name)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        errors: list[BaseException] = []
        for name in reversed(self._opened):
            resource = self._resources[name]
            try:
                await resource.close()
            except BaseException as exc:
                errors.append(exc)
        self._opened.clear()
        if errors:
            raise errors[0]

    async def __aenter__(self) -> "ManagedLifecycle":
        await self.start()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.stop()

    def get(self, name: str) -> LifecycleResource | None:
        """Return the named resource, or ``None`` when not configured."""
        return self._resources.get(name)


class AsyncEngineResource:
    """Adapt a SQLAlchemy ``AsyncEngine`` to the process lifecycle.

    Engine creation is lazy, so ``open()`` is a no-op; real connectivity
    is asserted by ``ping()`` during readiness checks.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        await self._engine.dispose()

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @property
    def engine(self) -> AsyncEngine:
        return self._engine


async def wait_for_shutdown() -> None:
    """Block until SIGINT or SIGTERM is received.

    Signal handlers can only be registered on the main thread's event
    loop; in restricted environments the process waits on an event that
    is never signalled, matching the long-running process contract.
    """
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    await stop.wait()
