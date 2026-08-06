# Platform V2 Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Superpowers owns task state, Spec Review, Code Quality Review, Final Review, and completion.

**Goal:** Establish the V2 Python runtime, PostgreSQL business schema, LangGraph PostgreSQL checkpointing, Redis infrastructure adapter, and independently startable API/Worker/Scheduler processes without implementing business workflows.

**Architecture:** Add the approved V2 modular-monolith directories beside the dormant V1 entrypoints, while keeping V2 as the only target of new work. Use SQLAlchemy 2 async with Psycopg 3 and Alembic for the 16 business tables, the official LangGraph PostgreSQL saver for checkpoint tables, and redis-py for expiring infrastructure state. Phase 1 exposes only shared ports, migrations, dependency health, and test fixtures.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy 2.0.x async, Alembic 1.18.x, Psycopg 3, Redis 7 client, LangGraph 1.1.x, `langgraph-checkpoint-postgres` 3.1.x, pytest.

## Global Constraints

- V2 directly replaces V1; do not add compatibility imports or dual-read/write behavior.
- Do not delete V1 files in this phase; V1 removal belongs to the final cutover task.
- Business tables use PostgreSQL; SQLite and Piccolo are not used by new V2 modules.
- Business state and LangGraph checkpoints use separate PostgreSQL schemas/connections; the Python checkpointer schema is isolated through its connection `search_path` because it does not expose a first-class schema argument.
- Do not add Manifest, Outbox, history, Session, Gate, Command, Event, Password Reset, Profile Revision, or migration-run tables.
- All timestamps are timezone-aware UTC; all IDs are application-generated UUIDs.
- Every Task is implemented test-first and ends with a focused verified commit.
- New dependency installation occurs only after the user approves this Plan and executor routing.

---

### Task 1: Pin the V2 Runtime Dependencies and Package Skeleton

```yaml
executor:
  agent: claude-code
  model: sonnet
  reason: bounded project scaffolding with no concurrency or business-state decisions
```

**Files:**
- Create: `requirements-v2.txt`
- Create: `src/bootstrap/__init__.py`
- Create: `src/modules/__init__.py`
- Create: `src/integrations/__init__.py`
- Create: `src/transport/__init__.py`
- Create: `src/persistence/__init__.py`
- Create: `src/shared/__init__.py`
- Create: `tests/unit/test_v2_import_boundaries.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces importable top-level V2 packages under `src`.
- Produces the dependency input consumed by all later Tasks.
- Must not import any module under `src.frontend`, `src.models.business`, `src.repositories`, or V1 Graph packages.

- [ ] **Step 1: Write the failing import-boundary test**

```python
from pathlib import Path


def test_v2_packages_exist_without_v1_imports() -> None:
    roots = ["bootstrap", "modules", "integrations", "transport", "persistence", "shared"]
    for root in roots:
        assert Path(f"src/{root}/__init__.py").is_file()

    forbidden = ("src.frontend", "src.models.business", "src.repositories")
    for root in roots:
        for path in Path("src", root).rglob("*.py"):
            text = path.read_text()
            assert not any(name in text for name in forbidden)
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest tests/unit/test_v2_import_boundaries.py -v`

Expected: FAIL because the V2 package files do not exist.

- [ ] **Step 3: Create the package files and dependency input**

`requirements-v2.txt` must contain compatible bounded ranges:

```text
fastapi>=0.115,<1
pydantic>=2.10,<3
pydantic-settings>=2.7,<3
sqlalchemy>=2.0,<2.1
alembic>=1.18,<1.19
psycopg[binary,pool]>=3.2,<4
redis>=7,<8
langgraph>=1.1,<1.2
langgraph-checkpoint-postgres>=3.1,<3.2
uvicorn[standard]>=0.43,<1
pytest>=8,<9
pytest-asyncio>=0.25,<1
httpx>=0.28,<1
```

Add `.venv/`, `.pytest_cache/`, coverage files, V2 local secrets, and generated OpenAPI output to `.gitignore` if absent. Do not remove V1 dependencies yet.

- [ ] **Step 4: Run the focused test**

Run: `pytest tests/unit/test_v2_import_boundaries.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add requirements-v2.txt .gitignore src/bootstrap src/modules src/integrations src/transport src/persistence src/shared tests/unit/test_v2_import_boundaries.py
git commit -m "build: scaffold platform v2 runtime"
```

---

### Task 2: Add Shared IDs, UTC Clock, Settings, and Problem Types

```yaml
executor:
  agent: claude-code
  model: sonnet
  reason: focused shared-kernel implementation with stable approved interfaces
```

**Files:**
- Create: `src/shared/ids/__init__.py`
- Create: `src/shared/ids/types.py`
- Create: `src/shared/time/__init__.py`
- Create: `src/shared/time/clock.py`
- Create: `src/shared/errors/__init__.py`
- Create: `src/shared/errors/problems.py`
- Create: `src/bootstrap/settings.py`
- Create: `tests/unit/shared/test_ids.py`
- Create: `tests/unit/shared/test_clock.py`
- Create: `tests/unit/shared/test_problems.py`
- Create: `tests/unit/bootstrap/test_settings.py`

**Interfaces:**
- Produces: `new_uuid() -> UUID`.
- Produces: `Clock.now() -> datetime` and `SystemClock`.
- Produces: `Problem(code, status, title, detail, retryable, context)`.
- Produces: `Settings` with `database_url`, `checkpoint_database_url`, `redis_url`, process role, pool limits, and environment.

- [ ] **Step 1: Write failing shared-kernel tests**

```python
from datetime import UTC

from src.shared.ids.types import new_uuid
from src.shared.time.clock import SystemClock
from src.shared.errors.problems import Problem


def test_generated_ids_and_clock_are_production_safe() -> None:
    assert new_uuid() != new_uuid()
    assert SystemClock().now().tzinfo is UTC


def test_problem_serializes_approved_fields() -> None:
    problem = Problem(
        code="RESOURCE_NOT_FOUND",
        status=404,
        title="Resource not found",
        detail="The resource is unavailable",
        retryable=False,
    )
    assert problem.model_dump()["code"] == "RESOURCE_NOT_FOUND"
    assert problem.model_dump()["status"] == 404
```

- [ ] **Step 2: Run tests to verify missing modules fail**

Run: `pytest tests/unit/shared tests/unit/bootstrap/test_settings.py -v`

Expected: collection FAIL with missing V2 shared modules.

- [ ] **Step 3: Implement the exact interfaces**

```python
class Clock(Protocol):
    def now(self) -> datetime:
        raise NotImplementedError


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class Problem(BaseModel):
    code: str
    status: int
    title: str
    detail: str
    retryable: bool
    context: dict[str, object] = Field(default_factory=dict)
```

`Settings` must reject missing production URLs and must not define SQLite defaults. Secret values use `SecretStr` and have redacted repr.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/unit/shared tests/unit/bootstrap/test_settings.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/shared src/bootstrap/settings.py tests/unit/shared tests/unit/bootstrap/test_settings.py
git commit -m "feat: add v2 shared runtime contracts"
```

---

### Task 3: Create PostgreSQL Infrastructure and Access/Profile/Model Tables

```yaml
executor:
  agent: claude-code
  model: opus
  reason: security-sensitive credential schema and irreversible PostgreSQL migration constraints
```

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/0001_access_profiles_models.py`
- Create: `src/persistence/postgres/__init__.py`
- Create: `src/persistence/postgres/base.py`
- Create: `src/persistence/postgres/session.py`
- Create: `src/modules/access/models.py`
- Create: `src/modules/profiles/models.py`
- Create: `src/integrations/models/__init__.py`
- Create: `src/integrations/models/profile_model.py`
- Create: `docs/operations/database-migration-policy.md`
- Create: `tests/integration/postgres/conftest.py`
- Create: `tests/integration/postgres/test_0001_access_profiles_models.py`

**Interfaces:**
- Produces: `create_engine(settings) -> AsyncEngine`.
- Produces: `session_factory(engine) -> async_sessionmaker[AsyncSession]`.
- Produces tables: `app_user`, `login_log`, `domain_profile`, `domain_profile_draft`, `domain_profile_version`, `profile_migration`, `model_profile`.
- Owns `model_profile` persistence under `src/integrations/models`; Profile modules must not absorb model-gateway configuration.
- Later Tasks consume the shared SQLAlchemy `Base` and transaction factory; domain modules never receive the raw engine.

- [ ] **Step 1: Write failing migration constraint tests**

```python
from sqlalchemy import text


async def test_access_and_profile_constraints(migrated_db) -> None:
    await migrated_db.execute(text("""
        INSERT INTO app_user
          (id, username, display_name, password_hash, password_salt,
           system_role, status, must_change_password, created_at, updated_at)
        VALUES
          (:id, 'Admin', 'Admin', 'hash', decode('00','hex'),
           'ADMIN', 'ACTIVE', false, now(), now())
    """), {"id": uuid4()})

    with pytest.raises(IntegrityError):
        await migrated_db.execute(text("""
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, 'admin', 'Duplicate Admin', 'other-hash', decode('01','hex'),
               'USER', 'ACTIVE', true, now(), now())
        """), {"id": uuid4()})
```

The real test must also assert independent salt non-null, system/status checks, one built-in general Profile, continuous Profile version uniqueness, adjacent migration check, immutable published version policy at the repository boundary, and one active default Model Profile per purpose.

- [ ] **Step 2: Run the migration test before implementation**

Run: `pytest tests/integration/postgres/test_0001_access_profiles_models.py -v`

Expected: FAIL because Alembic and the tables do not exist.

- [ ] **Step 3: Implement async PostgreSQL infrastructure and migration 0001**

Use `postgresql+psycopg://` with `create_async_engine`. Model every fixed field from database design 1.1; use `varchar + CheckConstraint`, UUID keys, timezone-aware timestamps, bytea salt, JSONB content, partial unique indexes, and no PostgreSQL ENUM.

Document that production migration recovery is forward-only: restore or fix forward after a failed release. Alembic downgrade is a development/CI verification aid, not the production rollback mechanism. The document must include fresh install, pre-deployment backup, upgrade verification, application rollback compatibility boundary, and failed-migration operator steps.

- [ ] **Step 4: Verify migration and constraints**

Run: `alembic upgrade head`

Expected: migration reaches `0001` on an empty PostgreSQL database.

Run in the disposable integration database: `alembic downgrade base` followed by `alembic upgrade head`.

Expected: both commands exit 0 and migration returns to `0001`; this does not authorize production downgrade.

Run: `pytest tests/integration/postgres/test_0001_access_profiles_models.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add alembic.ini migrations src/persistence/postgres src/modules/access src/modules/profiles src/integrations/models docs/operations/database-migration-policy.md tests/integration/postgres
git commit -m "feat: add access and profile postgres schema"
```

---

### Task 4: Add Project and Membership Persistence

```yaml
executor:
  agent: claude-code
  model: opus
  reason: project idempotency, profile foreign keys, and last-owner consistency require cross-row constraint review
```

**Files:**
- Create: `migrations/versions/0002_projects.py`
- Create: `src/modules/projects/__init__.py`
- Create: `src/modules/projects/models.py`
- Create: `src/modules/projects/repository.py`
- Create: `tests/integration/postgres/test_0002_projects.py`

**Interfaces:**
- Produces tables: `project`, `project_member`.
- Produces repository transaction methods `get_project_for_update`, `find_by_creation_key`, `insert_project`, `put_member`, and `delete_member`.
- Does not implement HTTP or authorization behavior.

- [ ] **Step 1: Write failing project persistence tests**

```python
async def test_project_creation_key_is_scoped_to_creator(project_repo, users, profile) -> None:
    key = uuid4()
    first = await project_repo.insert_project(users.owner_a, key, "hash-a", profile)
    same_other_user = await project_repo.insert_project(users.owner_b, key, "hash-b", profile)
    assert first.id != same_other_user.id


async def test_project_has_exactly_one_row_per_member(project_repo, project, users) -> None:
    await project_repo.put_member(project.id, users.member.id, "MEMBER")
    await project_repo.put_member(project.id, users.member.id, "VIEWER")
    assert await project_repo.member_count(project.id, users.member.id) == 1
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/integration/postgres/test_0002_projects.py -v`

Expected: FAIL because migration 0002 and repository do not exist.

- [ ] **Step 3: Implement project migration and repository**

Include server-generated project UUID, scoped creation idempotency key/hash, truth JSONB, revision, Profile binding/hash/migration state, artifact counters, GitLab fields, member roles, and all indexes in database design 1.1. Last-owner enforcement remains a transaction-level repository operation with row locks and a negative integration test.

- [ ] **Step 4: Run migration and focused tests**

Run: `alembic upgrade head && pytest tests/integration/postgres/test_0002_projects.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/0002_projects.py src/modules/projects tests/integration/postgres/test_0002_projects.py
git commit -m "feat: add project persistence foundation"
```

---

### Task 5: Add Message, Current Run, Stage, and File Persistence

```yaml
executor:
  agent: claude-code
  model: opus
  reason: concurrent queue ordering, one-current-run invariant, and message idempotency span several tables
```

**Files:**
- Create: `migrations/versions/0003_conversation_delivery_files.py`
- Create: `src/modules/conversation/__init__.py`
- Create: `src/modules/conversation/models.py`
- Create: `src/modules/delivery/__init__.py`
- Create: `src/modules/delivery/models.py`
- Create: `src/modules/files/__init__.py`
- Create: `src/modules/files/models.py`
- Create: `tests/integration/postgres/test_0003_conversation_delivery_files.py`

**Interfaces:**
- Produces tables: `project_message`, `delivery_run`, `project_stage`, `project_file`.
- Produces persistence primitives only; state transitions are implemented in Phase 3.

- [ ] **Step 1: Write failing invariant tests**

```python
async def test_message_key_scope_and_server_id(db, project, users) -> None:
    key = uuid4()
    first_id = await insert_user_message(db, project.id, users.a.id, key, "hash")
    assert first_id != key
    with pytest.raises(IntegrityError):
        await insert_user_message(db, project.id, users.a.id, key, "other-hash")
    await insert_user_message(db, project.id, users.b.id, key, "hash")


async def test_only_one_current_run_per_project(db, project) -> None:
    await insert_run(db, project.id, uuid4())
    with pytest.raises(IntegrityError):
        await insert_run(db, project.id, uuid4())
```

Also test nine unique Stage codes, SEALED baseline constraint, stable Queue ordering, role/idempotency CHECK combinations, same-project filename uniqueness, and required stop audit fields.

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/integration/postgres/test_0003_conversation_delivery_files.py -v`

Expected: FAIL because migration 0003 does not exist.

- [ ] **Step 3: Implement migration 0003 and focused models**

Use the exact states and fixed columns from database design 1.1. `delivery_run.project_id` is its primary key; `target_run_id` intentionally has no FK; process and diagnostics remain JSONB without GIN indexes.

- [ ] **Step 4: Verify**

Run: `alembic upgrade head && pytest tests/integration/postgres/test_0003_conversation_delivery_files.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/0003_conversation_delivery_files.py src/modules/conversation src/modules/delivery src/modules/files tests/integration/postgres/test_0003_conversation_delivery_files.py
git commit -m "feat: add conversation and delivery persistence"
```

---

### Task 6: Add Artifact Draft, Current Artifact, and Change Persistence

```yaml
executor:
  agent: claude-code
  model: opus
  reason: artifact numbering, fixed references, and terminal change invariants affect approved-history correctness
```

**Files:**
- Create: `migrations/versions/0004_artifacts_changes.py`
- Create: `src/modules/artifacts/__init__.py`
- Create: `src/modules/artifacts/models.py`
- Create: `src/modules/changes/__init__.py`
- Create: `src/modules/changes/models.py`
- Create: `tests/integration/postgres/test_0004_artifacts_changes.py`

**Interfaces:**
- Produces tables: `artifact_draft`, `artifact`, `project_change`.
- Produces fixed reference arrays and their GIN indexes.
- Does not allocate codes or write Git in this phase.

- [ ] **Step 1: Write failing schema tests**

```python
async def test_new_draft_does_not_require_artifact_code(db, stage) -> None:
    draft_id = await insert_draft(db, stage, artifact_code=None)
    assert draft_id is not None


async def test_terminal_change_requires_git_decision_pointer(db, change) -> None:
    with pytest.raises(IntegrityError):
        await mark_change_applied_without_decision_commit(db, change.id)
```

Also test one current candidate per project/type/canonical key, fixed array defaults, array GIN index existence, current Artifact uniqueness, and absence of all forbidden history/manifest/outbox tables.

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/integration/postgres/test_0004_artifacts_changes.py -v`

Expected: FAIL because migration 0004 does not exist.

- [ ] **Step 3: Implement migration 0004**

Match database design 1.1 exactly. Keep stage publication state on `project_stage`; do not add publication columns to individual drafts.

- [ ] **Step 4: Verify**

Run: `alembic upgrade head && pytest tests/integration/postgres/test_0004_artifacts_changes.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/0004_artifacts_changes.py src/modules/artifacts src/modules/changes tests/integration/postgres/test_0004_artifacts_changes.py
git commit -m "feat: add artifact and change persistence"
```

---

### Task 7: Add Redis Infrastructure with Namespaced Expiring Keys

```yaml
executor:
  agent: claude-code
  model: opus
  reason: atomic occupancy and sliding-expiry primitives are concurrency-sensitive and security-adjacent
```

**Files:**
- Create: `src/integrations/redis/__init__.py`
- Create: `src/integrations/redis/client.py`
- Create: `src/integrations/redis/keys.py`
- Create: `src/integrations/redis/scripts.py`
- Create: `tests/integration/redis/conftest.py`
- Create: `tests/integration/redis/test_key_contracts.py`
- Create: `tests/integration/redis/test_atomic_occupancy.py`

**Interfaces:**
- Produces: `RedisRuntime` lifecycle with `open`, `close`, `ping`.
- Produces typed key builders for Session, User Cache, Conversation Owner, Events, and Worker Wakeup.
- Produces atomic occupancy script result `ACQUIRED/RENEWED/OCCUPIED/RELEASED/NOT_OWNER`.
- Does not implement Access or Conversation domain policy.

- [ ] **Step 1: Write failing Redis contract tests**

```python
async def test_two_users_cannot_acquire_same_project(redis_runtime, occupancy) -> None:
    for attempt in range(50):
        project_id = f"p-{attempt}"
        first, second = await asyncio.gather(
            occupancy.acquire(project_id=project_id, user_id="u1", ttl_seconds=300),
            occupancy.acquire(project_id=project_id, user_id="u2", ttl_seconds=300),
        )
        assert sorted([first.kind, second.kind]) == ["ACQUIRED", "OCCUPIED"]


async def test_same_user_renews_to_full_ttl(occupancy, fake_clock) -> None:
    await occupancy.acquire("p1", "u1", 300)
    fake_clock.advance(seconds=240)
    assert (await occupancy.acquire("p1", "u1", 300)).kind == "RENEWED"
```

- [ ] **Step 2: Run against the Redis test service**

Run: `pytest tests/integration/redis -v`

Expected: FAIL because RedisRuntime and scripts do not exist.

- [ ] **Step 3: Implement namespaced keys and Lua scripts**

Use the exact approved key shapes and TTLs. Lua must compare the stored user before renew/release; Python code must not emulate atomic behavior with separate GET/SET calls.

- [ ] **Step 4: Run focused concurrency tests**

Run: `pytest tests/integration/redis -v`

Expected: PASS; the test itself executes 50 fresh-key races.

- [ ] **Step 5: Commit**

```bash
git add src/integrations/redis tests/integration/redis
git commit -m "feat: add v2 redis infrastructure"
```

---

### Task 8: Configure the Official PostgreSQL Checkpointer

```yaml
executor:
  agent: claude-code
  model: opus
  reason: checkpoint schema isolation and cleanup semantics are recovery-critical and version-sensitive
```

**Files:**
- Create: `src/persistence/postgres/checkpoints.py`
- Create: `tests/integration/postgres/test_checkpoints.py`
- Modify: `src/bootstrap/settings.py`
- Modify: `migrations/versions/0001_access_profiles_models.py`

**Interfaces:**
- Produces: `CheckpointStore.open()`, `setup()`, `saver`, `delete_thread(run_id)`, `close()`.
- Uses `AsyncPostgresSaver` from the official package.
- Uses `thread_id = delivery_run.run_id` and a connection whose `search_path` targets `langgraph`.

- [ ] **Step 1: Write failing round-trip and isolation tests**

```python
from typing import TypedDict

from langgraph.graph import END, StateGraph


class CounterState(TypedDict):
    value: int


def increment(state: CounterState) -> CounterState:
    return {"value": state["value"] + 1}


def build_counter_graph(saver):
    builder = StateGraph(CounterState)
    builder.add_node("increment", increment)
    builder.set_entry_point("increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=saver)


async def test_checkpoint_round_trip_isolated_by_run(checkpoint_store) -> None:
    await checkpoint_store.setup()
    graph = build_counter_graph(checkpoint_store.saver)
    config_a = {"configurable": {"thread_id": "run-a"}}
    config_b = {"configurable": {"thread_id": "run-b"}}
    await graph.ainvoke({"value": 0}, config=config_a)
    assert (await graph.aget_state(config_a)).values["value"] == 1
    assert (await graph.aget_state(config_b)).values == {}


async def test_delete_thread_removes_only_target_run(checkpoint_store) -> None:
    graph = build_counter_graph(checkpoint_store.saver)
    config_a = {"configurable": {"thread_id": "run-a"}}
    config_b = {"configurable": {"thread_id": "run-b"}}
    await graph.ainvoke({"value": 0}, config=config_a)
    await graph.ainvoke({"value": 5}, config=config_b)
    await checkpoint_store.delete_thread("run-a")
    assert (await graph.aget_state(config_a)).values == {}
    assert (await graph.aget_state(config_b)).values["value"] == 6
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/integration/postgres/test_checkpoints.py -v`

Expected: FAIL because CheckpointStore does not exist.

- [ ] **Step 3: Implement CheckpointStore and schema setup**

Create the `langgraph` schema in Alembic, but let the official saver own its internal tables through `setup()`. Configure Psycopg with the required autocommit and dict-row behavior. Do not copy official checkpoint DDL into business ORM models.

- [ ] **Step 4: Verify business/checkpoint separation**

Run: `alembic upgrade head && pytest tests/integration/postgres/test_checkpoints.py -v`

Expected: PASS; business tables are outside `langgraph`, and deleting one thread does not affect business rows.

- [ ] **Step 5: Commit**

```bash
git add src/persistence/postgres/checkpoints.py src/bootstrap/settings.py migrations/versions/0001_access_profiles_models.py tests/integration/postgres/test_checkpoints.py
git commit -m "feat: add postgres graph checkpoint store"
```

---

### Task 9: Add API, Worker, and Scheduler Bootstrap Health

```yaml
executor:
  agent: claude-code
  model: sonnet
  reason: bounded process lifecycle wiring over interfaces established by earlier Tasks
```

**Files:**
- Create: `src/bootstrap/lifespan.py`
- Create: `src/bootstrap/api.py`
- Create: `src/bootstrap/worker.py`
- Create: `src/bootstrap/scheduler.py`
- Create: `src/transport/http/__init__.py`
- Create: `src/transport/http/health.py`
- Create: `tests/contract/test_health_api.py`
- Create: `tests/integration/bootstrap/test_process_lifecycle.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces entrypoints: `src.bootstrap.api:app`, `python -m src.bootstrap.worker`, `python -m src.bootstrap.scheduler`.
- Produces `GET /health/live` and `GET /health/ready` only; no business API in Phase 1.
- Readiness checks PostgreSQL and Redis; liveness does not depend on external services.

- [ ] **Step 1: Write failing API and lifecycle tests**

```python
async def test_liveness_does_not_require_dependencies(api_client) -> None:
    response = await api_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_readiness_reports_dependency_state(api_client) -> None:
    response = await api_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["postgres"] == "ready"
    assert response.json()["redis"] == "ready"
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/contract/test_health_api.py tests/integration/bootstrap/test_process_lifecycle.py -v`

Expected: FAIL because V2 process entrypoints do not exist.

- [ ] **Step 3: Implement explicit process lifecycles**

API owns HTTP/SSE adapters; Worker owns Checkpoint and future Graph execution; Scheduler owns future recovery scans. Each process opens only required resources and closes them in reverse order. `pyproject.toml` points FastAPI tooling to `src.bootstrap.api:app` only after tests pass.

- [ ] **Step 4: Run Phase 1 verification**

Run: `alembic upgrade head`

Run: `pytest tests/unit tests/contract tests/integration/postgres tests/integration/redis tests/integration/bootstrap -v`

Run: `python -m compileall src/bootstrap src/modules src/integrations src/persistence src/shared src/transport`

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/bootstrap src/transport/http pyproject.toml tests/contract tests/integration/bootstrap
git commit -m "feat: add v2 process bootstrap health"
```

---

## Plan Self-Review Checklist

- [ ] All nine Tasks contain exactly one valid executor contract.
- [ ] No two concurrently available Tasks claim overlapping source or migration files.
- [ ] Migrations are sequential: 0001 → 0002 → 0003 → 0004.
- [ ] All 16 approved business tables are present by Task 6.
- [ ] LangGraph owns its internal checkpoint tables; business ORM does not duplicate them.
- [ ] No forbidden table appears in migrations or models.
- [ ] Phase 1 exposes no business HTTP endpoints and performs no model/Git/object-store action.
- [ ] Phase 1 verification can run from a fresh database and Redis instance.

## Executor Route Summary

| Task | Depends on | Agent | Model | Routing reason |
|---|---|---|---|---|
| 1. Runtime dependencies and skeleton | — | `claude-code` | `sonnet` | Bounded scaffolding |
| 2. Shared runtime contracts | 1 | `claude-code` | `sonnet` | Stable, focused interfaces |
| 3. PostgreSQL base and access/profile/model tables | 1, 2 | `claude-code` | `opus` | Security and migration constraints |
| 4. Project persistence | 3 | `claude-code` | `opus` | Cross-row consistency |
| 5. Conversation/delivery/file persistence | 4 | `claude-code` | `opus` | Queue and current-run concurrency |
| 6. Artifact/change persistence | 5 | `claude-code` | `opus` | Approved-history correctness |
| 7. Redis infrastructure | 1, 2 | `claude-code` | `opus` | Atomic occupancy and expiry |
| 8. PostgreSQL checkpointer | 1, 2, 3 | `claude-code` | `opus` | Recovery-critical schema isolation |
| 9. Process bootstrap health | 2, 3, 7, 8 | `claude-code` | `sonnet` | Lifecycle wiring over established ports |

Tasks 4 and 7 become independently available after their prerequisites and own disjoint files. Tasks 5–6 form the ordered business-migration chain; Task 8 waits for migration 0001 because it deliberately extends that migration with the dedicated `langgraph` schema. Codex coordinates execution, performs Spec Review and Code Quality Review after every Task, performs the final whole-change review, and owns branch completion.
