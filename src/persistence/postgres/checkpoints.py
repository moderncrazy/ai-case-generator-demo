"""PostgreSQL LangGraph checkpointer.

Provides :class:`CheckpointStore` — a lightweight lifecycle wrapper
around the official ``AsyncPostgresSaver``.  The store opens a dedicated
psycopg connection pool whose ``search_path`` targets **only** the
``langgraph`` schema so that checkpoint tables never leak into the
business schema.

Official checkpoint tables are owned entirely by
``AsyncPostgresSaver.setup()``; this module never copies or models them.
"""

from __future__ import annotations

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.bootstrap.settings import Settings


class CheckpointStore:
    """Lifecycle wrapper for the official LangGraph PostgreSQL checkpointer.

    Typical usage::

        store = CheckpointStore(settings)
        await store.open()
        await store.setup()          # create langgraph tables on first use
        graph = builder.compile(checkpointer=store.saver)
        ...
        await store.delete_thread(run_id)
        await store.close()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: AsyncConnectionPool[AsyncConnection[DictRow]] | None = None
        self._saver: AsyncPostgresSaver | None = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        """Open the dedicated psycopg connection pool.

        Connections are configured with ``autocommit=True``,
        ``row_factory=dict_row``, and ``search_path=langgraph`` so that
        the official saver's internal tables are isolated from business
        tables.
        """
        url = self._settings.checkpoint_database_url.get_secret_value()  # type: ignore[union-attr]
        self._pool = AsyncConnectionPool[AsyncConnection[DictRow]](
            conninfo=url,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
                "options": "-c search_path=langgraph",
            },
            min_size=self._settings.checkpoint_pool_size,
            max_size=self._settings.checkpoint_pool_size
            + self._settings.checkpoint_max_overflow,
            open=False,
        )
        await self._pool.open()
        self._saver = AsyncPostgresSaver(conn=self._pool)

    async def setup(self) -> None:
        """Create or migrate the official checkpoint tables.

        Must be called after :meth:`open` and before any graph
        invocation.  Idempotent — safe to call on every process start.
        """
        if self._saver is None:
            raise RuntimeError("CheckpointStore is not open — call open() first")
        # Ensure the langgraph schema exists before the saver creates its
        # internal tables.  Alembic also creates this schema, but setup()
        # is the authoritative guard for checkpoint-only deployments.
        async with self._pool.connection() as conn:
            await conn.execute("CREATE SCHEMA IF NOT EXISTS langgraph")
        await self._saver.setup()

    async def close(self) -> None:
        """Close the connection pool and release all resources."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._saver = None

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------

    @property
    def saver(self) -> AsyncPostgresSaver:
        """The underlying ``AsyncPostgresSaver`` for graph compilation."""
        if self._saver is None:
            raise RuntimeError("CheckpointStore is not open — call open() first")
        return self._saver

    # ------------------------------------------------------------------
    # operations
    # ------------------------------------------------------------------

    async def delete_thread(self, run_id: str) -> None:
        """Delete all checkpoint state for a single delivery run thread.

        Removes every checkpoint, blob, and write row whose
        ``thread_id`` matches *run_id* without touching other threads or
        the business schema.
        """
        if self._saver is None:
            raise RuntimeError("CheckpointStore is not open — call open() first")
        await self._saver.adelete_thread(str(run_id))
