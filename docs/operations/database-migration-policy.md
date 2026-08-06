# Database Migration Policy — Platform V2

| 属性 | 内容 |
| --- | --- |
| 文档状态 | `APPROVED` |
| 生效日期 | 2026-08-06 |
| 适用范围 | Platform V2 PostgreSQL business schema |
| 工具 | Alembic 1.18.x (async, `postgresql+psycopg://`) |

## 1. Policy Summary

Production migration recovery is **forward-only**. After a failed release,
operators restore the pre-migration database backup or fix forward with a
corrective migration. Alembic `downgrade` is a development and CI verification
aid — it must never be used as a production rollback mechanism.

## 2. Fresh Install

```bash
# From a clean checkout against an empty PostgreSQL database:
export PLATFORM_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/platform_v2"
alembic upgrade head
```

This creates every table, constraint, and index from the initial migration
(`0001`) through the current head in a single atomic sequence. No seed data
scripts are applied by Alembic; initial ADMIN, general Profile, and default
Model Profiles are inserted by the application bootstrap process.

## 3. Pre-Deployment Backup

Before every production migration, take a logical backup of the target
database:

```bash
pg_dump --no-owner --clean --if-exists \
  --exclude-schema=langgraph \
  "$PLATFORM_DATABASE_URL" > backup-$(date -u +%Y%m%dT%H%M%SZ).sql
```

The `langgraph` schema is excluded because its checkpoint tables are
ephemeral and are owned by the official LangGraph PostgreSQL checkpointer,
whose internal migration is handled separately (see Section 7).

**Restore from backup (if needed):**

```bash
psql "$PLATFORM_DATABASE_URL" < backup-YYYYMMDDTHHMMSSZ.sql
```

## 4. Upgrade Verification

After `alembic upgrade head` succeeds in production, run the focused
integration test suite against the migrated database to verify that every
constraint, index, and foreign key is in place:

```bash
PLATFORM_DATABASE_URL="<production-url>" \
  pytest tests/integration/postgres -v
```

Do not proceed with the release if any constraint test fails. A passing
suite confirms that the live schema matches the expected design.

## 5. Application Rollback Compatibility Boundary

V2 migrations are designed to be **additive and non-breaking**:

- New columns must have `DEFAULT` values or be `NULL`-able so that the
  previous application revision continues to function.
- Existing columns, constraints, or indexes must not be dropped or renamed
  in a migration that ships alongside application changes that still
  reference them.
- When a column or table must be removed, use a **two-release cycle**:
  1. Release N: stop writing to the column; mark it deprecated.
  2. Release N+1: drop the column via migration after confirming no
     running process references it.

Rolling back the **application** to the prior revision is safe as long as
the migration(s) introduced since that revision follow the additive rule
above. If a migration is not additive, a database restore is required
before rolling back the application.

## 6. Failed-Migration Operator Steps

### 6.1 Migration fails at `alembic upgrade head`

1. Capture the full Alembic error output and the migration revision that failed.
2. **Do not** run `alembic downgrade` in production.
3. Determine whether the failure is transient (connection timeout, lock
   contention) or permanent (constraint violation, type mismatch).

**Transient failure:**
```bash
# Verify the database is reachable and retry:
alembic upgrade head
```

**Permanent failure:**
1. Restore the pre-migration backup (Section 3).
2. Identify the root cause in a staging environment that mirrors production.
3. Fix the migration script or the data that caused the violation.
4. Re-deploy the corrected migration.

### 6.2 Migration succeeded but application is broken

1. If the migration was additive, roll back the application to the prior
   revision — the database is backward-compatible.
2. If the migration was not additive, restore the pre-migration backup
   and roll back the application.
3. Fix the application or migration in a staging environment.
4. Re-deploy.

### 6.3 Alembic version table is out of sync

If the `alembic_version` table was manually altered or a migration was
applied outside of Alembic:

```bash
# Stamp the database to a known-good revision so Alembic can resume:
alembic stamp <known-good-revision>
alembic upgrade head
```

Only use `alembic stamp` when you have independently verified that the
schema matches the stamped revision exactly.

## 7. LangGraph Checkpoint Schema

The `langgraph` schema and its internal checkpoint tables are managed by
the official `langgraph-checkpoint-postgres` package's `setup()` method,
not by the business Alembic migrations. The checkpoint schema uses a
separate database connection whose `search_path` targets `langgraph`.

- Checkpoint migrations run at application startup via `CheckpointStore.setup()`.
- The checkpoint schema is excluded from business backups (Section 3).
- Checkpoint data is ephemeral; thread cleanup follows the run lifecycle
  rules defined in the database design document.

## 8. CI / Development Downgrade Verification

In CI and local development only, the following cycle verifies that every
migration is independently downgradable:

```bash
alembic downgrade base
alembic upgrade head
```

Both commands must exit 0. This ensures that `downgrade()` operations are
syntactically correct and drop objects in the right order, which is
required for disposable-database test fixtures. **This does not authorize
production downgrade.**

## 9. Disposable-Database Test Fixtures

Integration tests use `TEST_DATABASE_URL` to create ephemeral PostgreSQL
databases. The test conftest runs `alembic upgrade head` on a fresh
database and uses transaction rollback for test isolation. No production
data is touched.
