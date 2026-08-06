"""Integration tests for the PostgreSQL LangGraph checkpointer.

Verifies round-trip isolation across threads and target-only thread
deletion.  The checkpoint store uses a dedicated psycopg connection
whose ``search_path`` targets only the ``langgraph`` schema.
"""

from typing import TypedDict

import pytest
import pytest_asyncio
from langgraph.graph import END, StateGraph

from src.bootstrap.settings import Settings
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
# fixture
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
# tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_round_trip_isolated_by_run(
    checkpoint_store: CheckpointStore,
) -> None:
    """A checkpoint written under one thread_id is invisible under another."""
    await checkpoint_store.setup()
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
