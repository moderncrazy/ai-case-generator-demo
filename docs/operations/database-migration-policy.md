# Database Migration Policy — Platform V2

| 属性 | 内容 |
| --- | --- |
| 文档状态 | `APPROVED` |
| 生效日期 | 2026-08-06 |
| 适用范围 | Platform V2 PostgreSQL business schema |
| 工具 | Alembic 1.18.x (`postgresql+psycopg://`) |

## 1. Policy Summary

Production migration recovery is **forward-only**. After a failed release,
operators restore the pre-migration database backup or fix forward with a
corrective migration. Alembic `downgrade` is a development and CI
verification aid — it must never be used as a production rollback mechanism.

## 2. Fresh Install

```bash
# From a clean checkout against an empty PostgreSQL database.
# Credentials are supplied via PGPASSWORD or ~/.pgpass, never on the command line.
export PGPASSWORD="<password>"
alembic upgrade head
```

This creates every table, constraint, and index from the initial migration
(`0001`) through the current head in a single atomic sequence. No seed data
scripts are applied by Alembic; initial ADMIN, general Profile, and default
Model Profiles are inserted by the application bootstrap process.

## 3. Pre-Deployment Backup

### 3.1 Credential Handling

All backup and restore tools use **libpq environment variables** or
**`~/.pgpass`**. The SQLAlchemy DSN (`postgresql+psycopg://`) is a
SQLAlchemy-only scheme that `pg_dump` and `psql` do not understand.
Passwords must never appear in `argv` where they are visible to `ps`, audit
logs, and process inspection tools.

Set credentials in the environment:

```bash
export PGHOST=<host>
export PGPORT=<port>
export PGDATABASE=<dbname>
export PGUSER=<user>
export PGPASSWORD=<password>       # or omit and use ~/.pgpass
```

### 3.2 Create an Encrypted Backup

```bash
# Binary custom-format dump, compressed and encrypted with AES-256-CBC.
# The symmetric encryption key is read from a secured file — never from argv.
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
umask 077

# 1. Dump to a temporary plaintext file (umask 077 restricts access).
pg_dump \
  --format=custom \
  --compress=9 \
  --no-owner \
  --exclude-schema=langgraph \
  --file="backup-${TIMESTAMP}.dump"

# 2. Encrypt the dump.  The passphrase file must be stored on a separate
#    filesystem or in a secrets manager with 0400 permissions.
#    The plaintext is deleted ONLY when encryption succeeds (&&).
#    On failure, openssl exits non-zero, the && short-circuits, the
#    plaintext dump is preserved, and the operator sees the openssl
#    error on stderr.
openssl enc -aes-256-cbc -pbkdf2 -iter 100000 \
  -salt \
  -in "backup-${TIMESTAMP}.dump" \
  -out "backup-${TIMESTAMP}.dump.enc" \
  -pass "file:/secure/backup-key" \
  && rm "backup-${TIMESTAMP}.dump"
```

- `--format=custom` produces a compressed binary archive suitable for `pg_restore`.
- `--exclude-schema=langgraph` excludes ephemeral checkpoint tables.
- `umask 077` restricts the temporary plaintext dump to the creating user.
- `openssl enc -aes-256-cbc -pbkdf2 -iter 100000` applies AES-256-CBC
  encryption with a key derived from the passphrase file; this is the
  encryption layer — not delegated to filesystem or volume assumptions.
- The plaintext dump is deleted only after `openssl` confirms successful
  encryption (exit 0).  If encryption fails the plaintext dump is preserved
  and the operator sees the error — no silent data loss.

### 3.3 Verify the Backup

```bash
# Verify the encrypted backup is complete and readable.  Exit code 0 means
# the archive is intact and the encryption key is valid.
# pg_restore reads stdin when no archive filename is given — do not pass "-".
openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
  -in "backup-${TIMESTAMP}.dump.enc" \
  -pass "file:/secure/backup-key" \
  | pg_restore --list > /dev/null
```

### 3.4 Restore into a Clean Target

Always restore into a **fresh, empty database** to avoid object conflicts
from post-backup schema changes:

```bash
# Create a clean target (the existing database must be dropped first if
# it is the same logical name):
createdb platform_v2_restore

# Decrypt and restore in a single pipeline — the plaintext never touches disk.
openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
  -in "backup-${TIMESTAMP}.dump.enc" \
  -pass "file:/secure/backup-key" \
  | pg_restore \
      --dbname=platform_v2_restore \
      --no-owner \
      --clean \
      --if-exists \
      --single-transaction
```

After verification, rename or promote the restored database as needed.

## 4. Upgrade Verification

### 4.1 Read-Only Production Verification

After `alembic upgrade head` succeeds in production, run a **read-only**
schema inspection to verify that every table, constraint, and index exists:

```bash
# Read-only introspection — no data mutation.
alembic check
```

The `alembic check` command compares the live schema against the declared
SQLAlchemy `Base.metadata`. A non-zero exit indicates a mismatch; do not
proceed with the release.

### 4.2 Mutation-Based Constraint Verification (Disposable Clone Only)

The full constraint test suite must **only** run against a disposable clone
using `TEST_DATABASE_URL`:

```bash
# TEST_DATABASE_URL must target the dedicated disposable database.
pytest tests/integration/postgres -v
```

The conftest guards enforce that `TEST_DATABASE_URL` targets the dedicated
`ai_case_v2_test` database — production data is never touched by mutation
tests.

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

Integration tests require `TEST_DATABASE_URL` to target the dedicated
disposable database `ai_case_v2_test`. The conftest enforces this at
collection time — any other target database causes immediate test failure.

- Migrations run once per session via `alembic upgrade head`.
- Tests use transaction rollback for isolation.
- No production data is ever touched.
- Async and sync fixtures are both available; the async path exercises the
  real `create_engine` / `session_factory` runtime stack.
