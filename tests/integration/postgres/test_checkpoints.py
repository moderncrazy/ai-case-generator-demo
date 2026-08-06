"""Integration tests for the PostgreSQL LangGraph checkpointer.

Verifies round-trip isolation across threads, target-only thread
deletion, ``open()`` idempotency, URL-fallback normalisation,
production rejection, and schema-level isolation via catalog queries.
"""

from typing import TypedDict

import pytest
import pytest_asyncio
from langgraph.graph import END, StateGraph

from src.bootstrap.settings import Environment, Settings
from src.persistence.postgres.checkpoints import CheckpointStore


# ---------------------------------------------------------------------------
# minimal counter graph for checkpoint exercises
# ---------------------------------------------------------------------------


class CounterState(TypedDict):
    value: int


def _increment(state: CounterState) -> CounterState:
    return {"value": state["value"] + 1}


def _build_counter_graph(saver):
    builder = StateGraph(CounterState)
    builder.add_node("increment", _increment)
    builder.set_entry_point("increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=saver)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def checkpoint_store(
    _settings_for_test: Settings,
    _run_migrations: None,
) -> CheckpointStore:
    """Create an opened CheckpointStore with clean checkpoint tables."""
    store = CheckpointStore(_settings_for_test)
    await store.open()
    await store.setup()
    # Truncate checkpoint tables so fixed thread IDs don't leak across
    # tests.  The langgraph schema is isolated; this never touches
    # business tables.
    async with store._pool.connection() as conn:  # type: ignore[union-attr]
        await conn.execute("DELETE FROM checkpoints")
        await conn.execute("DELETE FROM checkpoint_blobs")
        await conn.execute("DELETE FROM checkpoint_writes")
    try:
        yield store
    finally:
        await store.close()


# ---------------------------------------------------------------------------
# settings-level tests
# ---------------------------------------------------------------------------


class TestSettingsFallback:
    """Non-production Settings normalise the checkpoint URL for libpq."""

    def test_fallback_strips_sqlalchemy_driver_from_env_url(
        self, _settings_for_test: Settings
    ) -> None:
        """The checkpoint URL derived from DATABASE_URL contains no ``+psycopg``."""
        url = _settings_for_test.checkpoint_database_url.get_secret_value()  # type: ignore[union-attr]
        assert "+psycopg" not in url, (
            f"checkpoint URL {url!r} still contains +psycopg driver prefix"
        )
        assert url.startswith("postgresql://") or url.startswith("postgres://")

    def test_checkpoint_store_opens_with_fallback_url(
        self, _settings_for_test: Settings, _run_migrations: None
    ) -> None:
        """End-to-end: a store using only the fallback URL opens and sets up."""
        # _settings_for_test has database_url set but no explicit
        # checkpoint_database_url — the fallback is in effect.
        assert _settings_for_test.checkpoint_database_url is not None
        # Prove we can open and get a saver with the fallback URL.
        import asyncio

        async def _probe() -> None:
            store = CheckpointStore(_settings_for_test)
            try:
                await store.open()
                await store.setup()
                assert store.saver is not None
            finally:
                await store.close()

        asyncio.run(_probe())

    def test_explicit_checkpoint_url_not_overwritten_by_fallback(self) -> None:
        """An explicit checkpoint URL survives the fallback validator."""
        settings = Settings(
            checkpoint_database_url="postgresql://explicit:url@h/db",
            environment="local",
        )
        url = settings.checkpoint_database_url.get_secret_value()  # type: ignore[union-attr]
        assert url == "postgresql://explicit:url@h/db"


class TestSettingsProduction:
    """Production must supply an explicit ``checkpoint_database_url``.

    The fallback validator (``_default_checkpoint_database_url``) returns
    early when ``environment is PRODUCTION``, so the checkpoint URL is
    never silently derived from the business URL.  These tests supply all
    three required URLs explicitly.
    """

    def test_production_with_all_urls_succeeds(self) -> None:
        """Production with all three URLs explicitly supplied is valid."""
        settings = Settings(
            database_url="postgresql+psycopg://u:p@h/biz",
            checkpoint_database_url="postgresql://u:p@h/chk",
            redis_url="redis://localhost:6379",
            environment="production",
        )
        assert settings.checkpoint_database_url is not None
        url = settings.checkpoint_database_url.get_secret_value()  # type: ignore[union-attr]
        # Fallback must NOT have normalised the explicit URL (it skips
        # production).  The explicit value survives as-is.
        assert url == "postgresql://u:p@h/chk"

    def test_production_rejects_missing_checkpoint_url(self, monkeypatch) -> None:
        """Production with business DB and Redis but no explicit checkpoint URL raises ``ValueError``."""
        monkeypatch.delenv("PLATFORM_CHECKPOINT_DATABASE_URL", raising=False)
        with pytest.raises(ValueError, match="external service URLs"):
            Settings(
                database_url="postgresql+psycopg://u:p@h/biz",
                redis_url="redis://localhost:6379",
                environment="production",
            )

    def test_production_rejects_missing_redis_url(self) -> None:
        """Production missing any required URL raises ``ValueError``."""
        with pytest.raises(ValueError, match="external service URLs"):
            Settings(
                database_url="postgresql+psycopg://u:p@h/biz",
                checkpoint_database_url="postgresql://u:p@h/chk",
                environment="production",
            )


# ---------------------------------------------------------------------------
# CheckpointStore lifecycle tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_is_idempotent(
    _settings_for_test: Settings,
    _run_migrations: None,
) -> None:
    """Calling ``open()`` twice does not create a second pool."""
    store = CheckpointStore(_settings_for_test)
    try:
        await store.open()
        first_pool = store._pool  # type: ignore[union-attr]
        await store.open()
        assert store._pool is first_pool  # type: ignore[union-attr]
    finally:
        await store.close()


# ---------------------------------------------------------------------------
# checkpoint round-trip and isolation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_round_trip_isolated_by_run(
    checkpoint_store: CheckpointStore,
) -> None:
    """A checkpoint written under one thread_id is invisible under another."""
    graph = _build_counter_graph(checkpoint_store.saver)

    config_a = {"configurable": {"thread_id": "run-a"}}
    config_b = {"configurable": {"thread_id": "run-b"}}

    await graph.ainvoke({"value": 0}, config=config_a)

    assert (await graph.aget_state(config_a)).values["value"] == 1  # type: ignore[index]
    assert (await graph.aget_state(config_b)).values == {}  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_delete_thread_removes_only_target_run(
    checkpoint_store: CheckpointStore,
) -> None:
    """Deleting one thread leaves other threads and business tables intact."""
    graph = _build_counter_graph(checkpoint_store.saver)

    config_a = {"configurable": {"thread_id": "run-a"}}
    config_b = {"configurable": {"thread_id": "run-b"}}

    await graph.ainvoke({"value": 0}, config=config_a)
    await graph.ainvoke({"value": 5}, config=config_b)

    await checkpoint_store.delete_thread("run-a")

    assert (await graph.aget_state(config_a)).values == {}  # type: ignore[union-attr]
    assert (await graph.aget_state(config_b)).values["value"] == 6  # type: ignore[index]


# ---------------------------------------------------------------------------
# schema-level isolation evidence
# ---------------------------------------------------------------------------


class TestSchemaIsolation:
    """Prove checkpoint tables live ONLY in ``langgraph``, never in ``public``.

    Every test depends on ``checkpoint_store`` — a fixture that opens a
    store and runs the official ``AsyncPostgresSaver.setup()`` — so catalog
    assertions are always order-independent: the saver's tables (including
    ``checkpoint_migrations``) are guaranteed to exist before any query.
    """

    CHECKPOINT_TABLES = {
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
    }

    def test_checkpoint_tables_exist_only_in_langgraph(
        self, checkpoint_store: CheckpointStore, sync_engine, _run_migrations
    ) -> None:
        """After official saver setup, query ``information_schema``."""
        import sqlalchemy as sa

        with sync_engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_name = ANY(:names)
                      AND table_schema IN ('langgraph', 'public')
                    ORDER BY table_schema, table_name
                    """
                ),
                {"names": list(self.CHECKPOINT_TABLES)},
            ).fetchall()

        schemas_by_table: dict[str, set[str]] = {}
        for schema, table in rows:
            schemas_by_table.setdefault(table, set()).add(schema)

        for table in self.CHECKPOINT_TABLES:
            schemas = schemas_by_table.get(table, set())
            assert schemas == {"langgraph"}, (
                f"{table} found in {schemas}; expected only {{langgraph}}"
            )

    def test_no_checkpoint_tables_in_public(
        self, checkpoint_store: CheckpointStore, sync_engine, _run_migrations
    ) -> None:
        """Explicit negative check: zero checkpoint tables in ``public``."""
        import sqlalchemy as sa

        with sync_engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = ANY(:names)
                    """
                ),
                {"names": list(self.CHECKPOINT_TABLES)},
            ).fetchall()

        assert len(rows) == 0, (
            f"Checkpoint tables leaked into public: {[r[0] for r in rows]}"
        )


@pytest.mark.asyncio
async def test_business_row_survives_checkpoint_operations(
    checkpoint_store: CheckpointStore,
    sync_engine,
) -> None:
    """Public business row survives real checkpoint writes and thread deletion.

    Inserts a real ``app_user`` row, writes checkpoint state through a
    compiled graph under two distinct run IDs, deletes one thread via
    ``CheckpointStore.delete_thread``, and then verifies that the other
    checkpoint is intact and the business row remains untouched.
    """
    import uuid as _uuid
    import sqlalchemy as sa

    # -- insert a real public business row ---------------------------------
    uid = _uuid.uuid4()
    with sync_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                sa.text(
                    """
                    INSERT INTO app_user
                      (id, username, display_name, password_hash, password_salt,
                       system_role, status, must_change_password, created_at, updated_at)
                    VALUES
                      (:id, :un, 'Isolation Test', 'hash', decode('aa','hex'),
                       'ADMIN', 'ACTIVE', false, now(), now())
                    """
                ),
                {"id": uid, "un": f"iso-{uid.hex[:8]}"},
            )

    try:
        # -- write checkpoints under two distinct run IDs ------------------
        graph = _build_counter_graph(checkpoint_store.saver)

        config_a = {"configurable": {"thread_id": "iso-run-a"}}
        config_b = {"configurable": {"thread_id": "iso-run-b"}}

        await graph.ainvoke({"value": 0}, config=config_a)
        await graph.ainvoke({"value": 5}, config=config_b)

        # -- delete one target thread --------------------------------------
        await checkpoint_store.delete_thread("iso-run-a")

        # -- deleted thread is gone, the other survives --------------------
        assert (await graph.aget_state(config_a)).values == {}  # type: ignore[union-attr]
        assert (await graph.aget_state(config_b)).values["value"] == 6  # type: ignore[index]

        # -- public business row still exists ------------------------------
        with sync_engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT id, display_name FROM app_user WHERE id = :id"),
                {"id": uid},
            ).fetchone()

        assert row is not None, "business row vanished after checkpoint operations"
        assert row.display_name == "Isolation Test"  # type: ignore[union-attr]
    finally:
        # Cleanup: remove the business row we inserted
        with sync_engine.connect() as conn:
            with conn.begin():
                conn.execute(
                    sa.text("DELETE FROM app_user WHERE id = :id"),
                    {"id": uid},
                )
