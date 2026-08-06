"""Integration tests for migration 0003 — conversation, delivery, stage, and file tables.

Covers:
- DDL constraints (sync fixtures)
- Message idempotency key scoped to (project, user)
- One-current-run per project invariant
- Nine unique stage codes and SEALED baseline constraint
- Stable queue ordering by (created_at, id)
- Role/idempotency CHECK combinations
- Same-project filename uniqueness
- Required stop audit fields (CANCELLED / INTERRUPTED)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


# ===================================================================
# Helper — insert prerequisite rows (sync)
# ===================================================================


def _insert_sync_user(db: Session, username: str) -> str:
    uid = uuid4()
    db.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, :dn, 'hash', decode('aa','hex'),
               'USER', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": uid, "un": username, "dn": username},
    )
    return str(uid)


def _insert_sync_profile(db: Session, user_id: str, code: str = "msg-prof") -> str:
    pid = uuid4()
    db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, :code, :name, 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": pid, "code": code, "name": code, "uid": user_id},
    )
    return str(pid)


def _insert_sync_project(
    db: Session, user_id: str, profile_id: str, name: str = "Test Project",
) -> str:
    proj_id = uuid4()
    db.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, :name, 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": proj_id, "key": uuid4(), "hash": "a" * 64,
            "name": name, "pid": profile_id, "phash": "b" * 64, "uid": user_id,
        },
    )
    return str(proj_id)


# ===================================================================
# DDL constraint tests — project_message (sync)
# ===================================================================


def test_project_message_role_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, agent_role, content, delivery_mode, target_run_id,
                   status, process, process_version, diagnostics,
                   stopped_by_user_id, stopped_at, created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, :key, :hash,
                   'BOT', NULL, '', NULL, NULL,
                   'COMPLETED', '[]'::jsonb, 0, '[]'::jsonb,
                   NULL, NULL, now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
                "key": uuid4(), "hash": "c" * 64,
            },
        )


def test_project_message_status_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, :key, :hash,
                   'USER', '', 'DELETED', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
                "key": uuid4(), "hash": "d" * 64,
            },
        )


def test_project_message_delivery_mode_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, delivery_mode, status, process, process_version,
                   diagnostics, created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, :key, :hash,
                   'USER', '', 'BROADCAST', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
                "key": uuid4(), "hash": "e" * 64,
            },
        )


def test_project_message_user_role_must_have_user_id(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """USER role without user_id must be rejected by CHECK constraint."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, NULL, :key, :hash,
                   'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "key": uuid4(), "hash": "f" * 64,
            },
        )


def test_project_message_non_user_role_must_not_have_user_id(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """ASSISTANT role with user_id must be rejected by CHECK constraint."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, NULL, NULL,
                   'ASSISTANT', '', 'RUNNING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
            },
        )


def test_project_message_user_role_must_have_idempotency_key(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """USER role without idempotency_key must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, NULL, NULL,
                   'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
            },
        )


def test_project_message_non_user_role_must_not_have_idempotency_key(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """ASSISTANT role with idempotency_key must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, NULL, :key, :hash,
                   'ASSISTANT', '', 'RUNNING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "key": uuid4(), "hash": "g" * 64,
            },
        )


def test_project_message_stopped_at_check(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Non-terminal status must have stopped_at IS NULL."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   stopped_by_user_id, stopped_at, created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, :key, :hash,
                   'USER', '', 'COMPLETED', '[]'::jsonb, 0, '[]'::jsonb,
                   :uid, now(), now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
                "key": uuid4(), "hash": "h" * 64,
            },
        )


def test_project_message_idempotency_key_unique_per_project_user(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Same (project_id, user_id, idempotency_key) must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    key = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
            "key": key, "hash": "i" * 64,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, :key, :hash,
                   'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "uid": migrated_db_user,
                "key": key, "hash": "j" * 64,
            },
        )


# ===================================================================
# DDL constraint tests — delivery_run (sync)
# ===================================================================


def test_delivery_run_status_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    # Insert a user message (needed for FK)
    msg_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": proj_id, "uid": migrated_db_user,
            "key": uuid4(), "hash": "k" * 64,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO delivery_run
                  (project_id, run_id, trigger_message_id, response_message_id,
                   status, project_revision, profile_id, profile_version,
                   profile_hash, input_baselines, retry_count,
                   started_at, updated_at)
                VALUES
                  (:proj, :run, :trig, :resp,
                   'DELETED', 0, :pid, 0, :phash, '[]'::jsonb, 0,
                   now(), now())
                """
            ),
            {
                "proj": proj_id, "run": uuid4(),
                "trig": msg_id, "resp": msg_id,
                "pid": pid, "phash": "l" * 64,
            },
        )


def test_delivery_run_one_per_project(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """delivery_run.project_id is PK — inserting a second row for same project
    must fail."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": proj_id, "uid": migrated_db_user,
            "key": uuid4(), "hash": "m" * 64,
        },
    )
    # First insert succeeds
    migrated_db.execute(
        text(
            """
            INSERT INTO delivery_run
              (project_id, run_id, trigger_message_id, response_message_id,
               status, project_revision, profile_id, profile_version,
               profile_hash, input_baselines, retry_count,
               started_at, updated_at)
            VALUES
              (:proj, :run, :trig, :resp,
               'QUEUED', 0, :pid, 0, :phash, '[]'::jsonb, 0,
               now(), now())
            """
        ),
        {
            "proj": proj_id, "run": uuid4(),
            "trig": msg_id, "resp": msg_id,
            "pid": pid, "phash": "n" * 64,
        },
    )
    # Second insert for same project must fail (PK collision)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO delivery_run
                  (project_id, run_id, trigger_message_id, response_message_id,
                   status, project_revision, profile_id, profile_version,
                   profile_hash, input_baselines, retry_count,
                   started_at, updated_at)
                VALUES
                  (:proj, :run, :trig, :resp,
                   'QUEUED', 0, :pid, 0, :phash, '[]'::jsonb, 0,
                   now(), now())
                """
            ),
            {
                "proj": proj_id, "run": uuid4(),
                "trig": msg_id, "resp": msg_id,
                "pid": pid, "phash": "o" * 64,
            },
        )


def test_delivery_run_unique_run_id(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """delivery_run.run_id has a UNIQUE constraint."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj1 = _insert_sync_project(migrated_db, migrated_db_user, pid, "Proj 1")
    proj2 = _insert_sync_project(
        migrated_db, migrated_db_user, pid, "Proj 2",
    )
    msg_id = uuid4()
    msg_id2 = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": proj1, "uid": migrated_db_user,
            "key": uuid4(), "hash": "p" * 64,
        },
    )
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id2, "proj": proj2, "uid": migrated_db_user,
            "key": uuid4(), "hash": "q" * 64,
        },
    )
    run_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO delivery_run
              (project_id, run_id, trigger_message_id, response_message_id,
               status, project_revision, profile_id, profile_version,
               profile_hash, input_baselines, retry_count,
               started_at, updated_at)
            VALUES
              (:proj, :run, :trig, :resp,
               'QUEUED', 0, :pid, 0, :phash, '[]'::jsonb, 0,
               now(), now())
            """
        ),
        {
            "proj": proj1, "run": run_id,
            "trig": msg_id, "resp": msg_id,
            "pid": pid, "phash": "r" * 64,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO delivery_run
                  (project_id, run_id, trigger_message_id, response_message_id,
                   status, project_revision, profile_id, profile_version,
                   profile_hash, input_baselines, retry_count,
                   started_at, updated_at)
                VALUES
                  (:proj, :run, :trig, :resp,
                   'QUEUED', 0, :pid, 0, :phash, '[]'::jsonb, 0,
                   now(), now())
                """
            ),
            {
                "proj": proj2, "run": run_id,
                "trig": msg_id2, "resp": msg_id2,
                "pid": pid, "phash": "s" * 64,
            },
        )


# ===================================================================
# DDL constraint tests — project_stage (sync)
# ===================================================================


STAGE_CODES = [
    "PROJECT_CHARTER",
    "REQUIREMENT_OUTLINE",
    "REQUIREMENT_MODULE",
    "PRD",
    "ARCHITECTURE",
    "SYSTEM_MODULE",
    "API",
    "DATABASE",
    "TEST",
]


def test_project_stage_stage_check_rejects_bad_code(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, publish_attempts,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'INVALID_STAGE', 'NOT_STARTED', 0,
                   0, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": proj_id},
        )


def test_project_stage_all_nine_codes_accepted(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """All nine stage codes must be accepted by the CHECK constraint."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    for code in STAGE_CODES:
        migrated_db.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, publish_attempts,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :stage, 'NOT_STARTED', 0,
                   0, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": proj_id, "stage": code},
        )


def test_project_stage_status_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, publish_attempts,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'PRD', 'COMPLETED', 0,
                   0, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": proj_id},
        )


def test_project_stage_unique_project_stage(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Duplicate (project_id, stage) must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    migrated_db.execute(
        text(
            """
            INSERT INTO project_stage
              (id, project_id, stage, status, revision,
               baseline_version, publish_attempts,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'PRD', 'NOT_STARTED', 0,
               0, 0, now(), now())
            """
        ),
        {"id": uuid4(), "proj": proj_id},
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, publish_attempts,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'PRD', 'BUILDING', 0,
                   0, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": proj_id},
        )


def test_project_stage_sealed_requires_baseline(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """SEALED status must have baseline_version > 0, git_commit_sha, and
    git_tag non-NULL."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    # SEALED without baseline fields must fail
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, git_commit_sha, git_tag,
                   publish_attempts, created_at, updated_at)
                VALUES
                  (:id, :proj, 'API', 'SEALED', 0,
                   0, NULL, NULL, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": proj_id},
        )


def test_project_stage_sealed_accepts_valid_baseline(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """SEALED with baseline_version > 0 and non-NULL commit/tag succeeds."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    migrated_db.execute(
        text(
            """
            INSERT INTO project_stage
              (id, project_id, stage, status, revision,
               baseline_version, git_commit_sha, git_tag,
               publish_attempts, created_at, updated_at)
            VALUES
              (:id, :proj, 'API', 'SEALED', 0,
               1, :sha, :tag, 0, now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id,
            "sha": "a" * 40, "tag": "v1.0.0-api",
        },
    )


def test_project_stage_publish_key_unique(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """publish_key must be unique (partial unique where NOT NULL)."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    key = "a" * 64
    migrated_db.execute(
        text(
            """
            INSERT INTO project_stage
              (id, project_id, stage, status, revision,
               baseline_version, publish_key, publish_attempts,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'API', 'SEALING', 0,
               0, :key, 1, now(), now())
            """
        ),
        {"id": uuid4(), "proj": proj_id, "key": key},
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, publish_key, publish_attempts,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'DATABASE', 'SEALING', 0,
                   0, :key, 1, now(), now())
                """
            ),
            {"id": uuid4(), "proj": proj_id, "key": key},
        )


# ===================================================================
# DDL constraint tests — project_file (sync)
# ===================================================================


def test_project_file_status_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": proj_id, "uid": migrated_db_user,
            "key": uuid4(), "hash": "t" * 64,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_file
                  (id, project_id, message_id, filename, content_type,
                   size_bytes, sha256, object_key, status,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, 'test.txt', 'text/plain',
                   100, :sha, :okey, 'ARCHIVED',
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "msg": msg_id,
                "sha": "u" * 64, "okey": f"files/{uuid4().hex}",
            },
        )


def test_project_file_size_bytes_check(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """size_bytes must be >= 0."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": proj_id, "uid": migrated_db_user,
            "key": uuid4(), "hash": "v" * 64,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_file
                  (id, project_id, message_id, filename, content_type,
                   size_bytes, sha256, object_key, status,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, 'neg.txt', 'text/plain',
                   -1, :sha, :okey, 'UPLOADED',
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "msg": msg_id,
                "sha": "w" * 64, "okey": f"files/{uuid4().hex}",
            },
        )


def test_project_file_unique_filename_per_project(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Same (project_id, filename) must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": proj_id, "uid": migrated_db_user,
            "key": uuid4(), "hash": "x" * 64,
        },
    )
    migrated_db.execute(
        text(
            """
            INSERT INTO project_file
              (id, project_id, message_id, filename, content_type,
               size_bytes, sha256, object_key, status,
               created_at, updated_at)
            VALUES
              (:id, :proj, :msg, 'readme.md', 'text/markdown',
               200, :sha, :okey, 'UPLOADED',
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id, "msg": msg_id,
            "sha": "y" * 64, "okey": f"files/{uuid4().hex}",
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_file
                  (id, project_id, message_id, filename, content_type,
                   size_bytes, sha256, object_key, status,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, 'readme.md', 'text/markdown',
                   300, :sha, :okey, 'UPLOADED',
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "msg": msg_id,
                "sha": "z" * 64, "okey": f"files/{uuid4().hex}",
            },
        )


def test_project_file_unique_object_key(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """object_key must be globally unique."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": proj_id, "uid": migrated_db_user,
            "key": uuid4(), "hash": "aa" + "c" * 62,
        },
    )
    okey = f"files/{uuid4().hex}"
    migrated_db.execute(
        text(
            """
            INSERT INTO project_file
              (id, project_id, message_id, filename, content_type,
               size_bytes, sha256, object_key, status,
               created_at, updated_at)
            VALUES
              (:id, :proj, :msg, 'a.txt', 'text/plain',
               10, :sha, :okey, 'UPLOADED',
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id, "msg": msg_id,
            "sha": "ab" + "d" * 62, "okey": okey,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_file
                  (id, project_id, message_id, filename, content_type,
                   size_bytes, sha256, object_key, status,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, 'b.txt', 'text/plain',
                   20, :sha, :okey, 'UPLOADED',
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "msg": msg_id,
                "sha": "ac" + "e" * 62, "okey": okey,
            },
        )


# ===================================================================
# Async fixtures
# ===================================================================


@pytest_asyncio.fixture
async def msg_users(async_session: AsyncSession):
    """Two test users: user_a, user_b."""
    from types import SimpleNamespace

    now = datetime.now(UTC)
    ids = [uuid4() for _ in range(2)]
    for uid in ids:
        await async_session.execute(
            text(
                """
                INSERT INTO app_user
                  (id, username, display_name, password_hash, password_salt,
                   system_role, status, must_change_password, created_at, updated_at)
                VALUES
                  (:id, :un, :dn, 'hash', decode('aa','hex'),
                   'USER', 'ACTIVE', false, :now, :now)
                """
            ),
            {"id": uid, "un": f"msg-{uid.hex[:8]}", "dn": f"Msg User {uid.hex[:6]}", "now": now},
        )
    await async_session.flush()
    return SimpleNamespace(a=ids[0], b=ids[1])


@pytest_asyncio.fixture
async def msg_profile(async_session: AsyncSession, msg_users):
    """A profile for message tests."""
    from sqlalchemy import select as sa_select

    now = datetime.now(UTC)
    pid = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, is_builtin_general,
               current_version, created_by_user_id, created_at, updated_at)
            VALUES (:id, :code, :name, 'ACTIVE', false,
                    0, :uid, :now, :now)
            """
        ),
        {
            "id": pid, "code": f"msgp-{pid.hex[:8]}",
            "name": "Message Test Profile", "uid": msg_users.a, "now": now,
        },
    )
    await async_session.flush()
    return pid


@pytest_asyncio.fixture
async def msg_project(async_session: AsyncSession, msg_users, msg_profile):
    """A project for message/delivery/stage/file tests."""
    proj_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'Message Test Project', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": proj_id, "key": uuid4(), "hash": "m1" + "c" * 62,
            "pid": msg_profile, "phash": "m2" + "d" * 62, "uid": msg_users.a,
        },
    )
    await async_session.flush()
    return proj_id


# ===================================================================
# Async helper functions
# ===================================================================


async def _insert_user_message(
    session: AsyncSession,
    project_id,
    user_id,
    idempotency_key,
    request_hash: str,
) -> str:
    """Insert a USER project_message and return its server-generated UUID."""
    msg_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', 'test message', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": project_id, "uid": user_id,
            "key": idempotency_key, "hash": request_hash,
        },
    )
    await session.flush()
    return str(msg_id)


async def _insert_assistant_message(
    session: AsyncSession, project_id, target_run_id=None,
) -> str:
    """Insert an ASSISTANT project_message."""
    msg_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, agent_role, content, delivery_mode, target_run_id,
               status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, NULL, NULL, NULL,
               'ASSISTANT', 'PM', '', NULL, :trun,
               'RUNNING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {"id": msg_id, "proj": project_id, "trun": target_run_id},
    )
    await session.flush()
    return str(msg_id)


async def _insert_run(
    session: AsyncSession, project_id, run_id, user_id, profile_id,
) -> None:
    """Insert a delivery_run row.  Requires valid user_id and profile_id
    for the FK relationships."""
    trig_id = await _insert_user_message(
        session, project_id, user_id, uuid4(), "run-trigger-hash",
    )
    resp_id = await _insert_assistant_message(session, project_id)
    await session.execute(
        text(
            """
            INSERT INTO delivery_run
              (project_id, run_id, trigger_message_id, response_message_id,
               status, project_revision, profile_id, profile_version,
               profile_hash, input_baselines, retry_count,
               started_at, updated_at)
            VALUES
              (:proj, :run, :trig, :resp,
               'QUEUED', 0, :pid, 0, :phash, '[]'::jsonb, 0,
               now(), now())
            """
        ),
        {
            "proj": project_id, "run": run_id,
            "trig": trig_id, "resp": resp_id,
            "pid": profile_id, "phash": "rh" + "e" * 62,
        },
    )
    await session.flush()


# ===================================================================
# Async invariant tests — message idempotency
# ===================================================================


@pytest.mark.asyncio
async def test_message_key_scope_and_server_id(
    async_session: AsyncSession, msg_project, msg_users,
) -> None:
    """Server generates message UUID different from client idempotency key.

    Same (project, user, key) is unique per the partial unique index.
    A nested savepoint absorbs the expected violation so the outer
    transaction stays usable for the different-user assertion that follows.
    """
    key = uuid4()
    # First message: server ID != client key
    first_id = await _insert_user_message(
        async_session, msg_project, msg_users.a, key, "hash-msg-1",
    )
    assert first_id != str(key), "Server-generated ID must differ from idempotency key"

    # Same project, same user, same key → IntegrityError.
    # Wrap in a nested savepoint so the outer transaction is not poisoned.
    savepoint = await async_session.begin_nested()
    try:
        await _insert_user_message(
            async_session, msg_project, msg_users.a, key, "hash-msg-2",
        )
        raise AssertionError(
            "Expected IntegrityError for duplicate idempotency key"
        )
    except IntegrityError:
        await savepoint.rollback()

    # Different user, same key, same project — must be allowed.
    second_id = await _insert_user_message(
        async_session, msg_project, msg_users.b, key, "hash-u2",
    )
    assert first_id != second_id


# ===================================================================
# Async invariant tests — one current run
# ===================================================================


@pytest.mark.asyncio
async def test_only_one_current_run_per_project(
    async_session: AsyncSession, msg_project, msg_users, msg_profile,
) -> None:
    """Inserting a second delivery_run for the same project must fail
    because project_id is the PK."""
    run_id_1 = uuid4()
    await _insert_run(
        async_session, msg_project, run_id_1, msg_users.a, msg_profile,
    )

    with pytest.raises(IntegrityError):
        await _insert_run(
            async_session, msg_project, uuid4(), msg_users.a, msg_profile,
        )


# ===================================================================
# Async invariant tests — nine stage codes
# ===================================================================


@pytest.mark.asyncio
async def test_all_nine_stage_codes_insert(
    async_session: AsyncSession, msg_project,
) -> None:
    """All nine stage codes can be inserted for a project."""
    for code in STAGE_CODES:
        await async_session.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, publish_attempts,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :stage, 'NOT_STARTED', 0,
                   0, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project, "stage": code},
        )
    await async_session.flush()

    # Verify exactly 9 rows exist for this project
    result = await async_session.execute(
        text(
            "SELECT COUNT(*) FROM project_stage WHERE project_id = :proj"
        ),
        {"proj": msg_project},
    )
    assert result.scalar() == 9


@pytest.mark.asyncio
async def test_nine_stage_codes_are_unique_per_project(
    async_session: AsyncSession, msg_project,
) -> None:
    """Cannot insert duplicate stage code for same project."""
    await async_session.execute(
        text(
            """
            INSERT INTO project_stage
              (id, project_id, stage, status, revision,
               baseline_version, publish_attempts,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'PRD', 'NOT_STARTED', 0,
               0, 0, now(), now())
            """
        ),
        {"id": uuid4(), "proj": msg_project},
    )
    await async_session.flush()

    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, publish_attempts,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'PRD', 'BUILDING', 0,
                   0, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project},
        )


# ===================================================================
# Async invariant tests — SEALED baseline constraint
# ===================================================================


@pytest.mark.asyncio
async def test_sealed_requires_baseline_fields(
    async_session: AsyncSession, msg_project,
) -> None:
    """SEALED status rejects missing baseline_version, git_commit_sha, or git_tag."""
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_stage
                  (id, project_id, stage, status, revision,
                   baseline_version, git_commit_sha, git_tag,
                   publish_attempts, created_at, updated_at)
                VALUES
                  (:id, :proj, 'API', 'SEALED', 0,
                   1, :sha, NULL, 0, now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project, "sha": "a" * 40},
        )


@pytest.mark.asyncio
async def test_non_sealed_does_not_require_baseline(
    async_session: AsyncSession, msg_project,
) -> None:
    """BUILDING status does not need baseline fields."""
    await async_session.execute(
        text(
            """
            INSERT INTO project_stage
              (id, project_id, stage, status, revision,
               baseline_version, publish_attempts,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'PRD', 'BUILDING', 0,
               0, 0, now(), now())
            """
        ),
        {"id": uuid4(), "proj": msg_project},
    )
    await async_session.flush()


# ===================================================================
# Async invariant tests — stable queue ordering
# ===================================================================


@pytest.mark.asyncio
async def test_queue_ordering_by_created_at_and_id(
    async_session: AsyncSession, msg_project, msg_users,
) -> None:
    """Queue messages are ordered by (created_at, id) with ``id`` providing
    deterministic tie-breaking when ``created_at`` values are equal."""
    from uuid import UUID

    now = datetime.now(UTC)
    key_a, key_b = uuid4(), uuid4()

    # Deterministic ordered UUIDs — a < b in UUID byte ordering
    msg_id_a = UUID("00000000-0000-0000-0000-000000000001")
    msg_id_b = UUID("00000000-0000-0000-0000-000000000002")

    # Insert in REVERSE order (b first, a second) with the SAME timestamp.
    # If created_at alone determined ordering, b would appear first.
    # With (created_at, id) ordering, a must sort before b because
    # timestamps are equal and UUID(id_a) < UUID(id_b).
    await async_session.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, delivery_mode, status, process, process_version,
               diagnostics, created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'QUEUE', 'QUEUED', '[]'::jsonb, 0, '[]'::jsonb,
               :ts, :ts)
            """
        ),
        {
            "id": msg_id_b, "proj": msg_project, "uid": msg_users.a,
            "key": key_b, "hash": "hash-qb", "ts": now,
        },
    )
    await async_session.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, delivery_mode, status, process, process_version,
               diagnostics, created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'QUEUE', 'QUEUED', '[]'::jsonb, 0, '[]'::jsonb,
               :ts, :ts)
            """
        ),
        {
            "id": msg_id_a, "proj": msg_project, "uid": msg_users.a,
            "key": key_a, "hash": "hash-qa", "ts": now,
        },
    )
    await async_session.flush()

    result = await async_session.execute(
        text(
            """
            SELECT id FROM project_message
            WHERE project_id = :proj
              AND delivery_mode = 'QUEUE'
              AND status = 'QUEUED'
            ORDER BY created_at, id
            """
        ),
        {"proj": msg_project},
    )
    ordered = [row[0] for row in result.all()]
    assert len(ordered) == 2
    assert msg_id_a in ordered
    assert msg_id_b in ordered
    # With equal timestamps, id tie-breaking must sort a before b
    assert ordered[0] == msg_id_a, (
        f"Queue ordering: with equal created_at, id tie-breaking must sort "
        f"lower UUID first; got {ordered[0]}, expected {msg_id_a}"
    )
    assert ordered[1] == msg_id_b


# ===================================================================
# Async invariant tests — role/idempotency CHECK combinations
# ===================================================================


@pytest.mark.asyncio
async def test_user_message_without_user_id_rejected(
    async_session: AsyncSession, msg_project,
) -> None:
    """USER message without user_id must be rejected by CHECK constraint."""
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, NULL, :key, :hash,
                   'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project, "key": uuid4(), "hash": "c1" + "c" * 62},
        )


@pytest.mark.asyncio
async def test_user_message_without_idempotency_key_rejected(
    async_session: AsyncSession, msg_project,
) -> None:
    """USER message without idempotency_key must be rejected by CHECK constraint."""
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, NULL, NULL,
                   'USER', '', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project, "uid": uuid4()},
        )


@pytest.mark.asyncio
async def test_assistant_message_with_user_id_rejected(
    async_session: AsyncSession, msg_project,
) -> None:
    """ASSISTANT message with user_id must be rejected by CHECK constraint."""
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, NULL, NULL,
                   'ASSISTANT', '', 'RUNNING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project, "uid": uuid4()},
        )


@pytest.mark.asyncio
async def test_assistant_message_with_idempotency_key_rejected(
    async_session: AsyncSession, msg_project,
) -> None:
    """ASSISTANT message with idempotency_key must be rejected by CHECK
    constraint."""
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, NULL, :key, :hash,
                   'ASSISTANT', '', 'RUNNING', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project, "key": uuid4(), "hash": "d1" + "d" * 62},
        )


@pytest.mark.asyncio
async def test_system_message_must_not_have_user_fields(
    async_session: AsyncSession, msg_project,
) -> None:
    """SYSTEM message with user_id must be rejected."""
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, NULL, NULL,
                   'SYSTEM', '', 'COMPLETED', '[]'::jsonb, 0, '[]'::jsonb,
                   now(), now())
                """
            ),
            {"id": uuid4(), "proj": msg_project, "uid": uuid4()},
        )


# ===================================================================
# Async invariant tests — same-project filename uniqueness
# ===================================================================


@pytest.mark.asyncio
async def test_same_project_filename_unique(
    async_session: AsyncSession, msg_project, msg_users,
) -> None:
    """Duplicate filename in the same project must be rejected."""
    msg_id = await _insert_user_message(
        async_session, msg_project, msg_users.a, uuid4(), "hash-file-1",
    )
    await async_session.execute(
        text(
            """
            INSERT INTO project_file
              (id, project_id, message_id, filename, content_type,
               size_bytes, sha256, object_key, status,
               created_at, updated_at)
            VALUES
              (:id, :proj, :msg, 'config.yaml', 'text/yaml',
               512, :sha, :okey, 'UPLOADED',
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": msg_project, "msg": msg_id,
            "sha": "e1" + "f" * 62, "okey": f"files/{uuid4().hex}",
        },
    )
    await async_session.flush()

    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_file
                  (id, project_id, message_id, filename, content_type,
                   size_bytes, sha256, object_key, status,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, 'config.yaml', 'text/yaml',
                   1024, :sha, :okey, 'UPLOADED',
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": msg_project, "msg": msg_id,
                "sha": "e2" + "f" * 62, "okey": f"files/{uuid4().hex}",
            },
        )


@pytest.mark.asyncio
async def test_same_filename_different_project_allowed(
    async_session: AsyncSession, msg_project, msg_users, msg_profile,
) -> None:
    """Same filename in different projects must be allowed."""
    # Create a second project
    proj2 = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'Second Project', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": proj2, "key": uuid4(), "hash": "f1" + "c" * 62,
            "pid": msg_profile, "phash": "f2" + "d" * 62, "uid": msg_users.a,
        },
    )
    await async_session.flush()

    msg_id1 = await _insert_user_message(
        async_session, msg_project, msg_users.a, uuid4(), "hash-file-proj1",
    )
    msg_id2 = await _insert_user_message(
        async_session, proj2, msg_users.a, uuid4(), "hash-file-proj2",
    )

    # Same filename in both projects — both must succeed
    await async_session.execute(
        text(
            """
            INSERT INTO project_file
              (id, project_id, message_id, filename, content_type,
               size_bytes, sha256, object_key, status,
               created_at, updated_at)
            VALUES
              (:id, :proj, :msg, 'shared.txt', 'text/plain',
               100, :sha, :okey, 'UPLOADED',
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": msg_project, "msg": msg_id1,
            "sha": "f3" + "f" * 62, "okey": f"files/{uuid4().hex}",
        },
    )
    # Same filename, different project — must not raise
    await async_session.execute(
        text(
            """
            INSERT INTO project_file
              (id, project_id, message_id, filename, content_type,
               size_bytes, sha256, object_key, status,
               created_at, updated_at)
            VALUES
              (:id, :proj, :msg, 'shared.txt', 'text/plain',
               200, :sha, :okey, 'UPLOADED',
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj2, "msg": msg_id2,
            "sha": "f4" + "f" * 62, "okey": f"files/{uuid4().hex}",
        },
    )


# ===================================================================
# Async invariant tests — stop audit fields
# ===================================================================


@pytest.mark.asyncio
async def test_non_terminal_message_with_stopped_at_rejected(
    async_session: AsyncSession, msg_project, msg_users,
) -> None:
    """Non-terminal status (COMPLETED) with non-NULL stopped_at must be
    rejected by CHECK constraint."""
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                """
                INSERT INTO project_message
                  (id, project_id, user_id, idempotency_key, request_hash,
                   role, content, status, process, process_version, diagnostics,
                   stopped_by_user_id, stopped_at, created_at, updated_at)
                VALUES
                  (:id, :proj, :uid, :key, :hash,
                   'USER', '', 'COMPLETED', '[]'::jsonb, 0, '[]'::jsonb,
                   :uid, now(), now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": msg_project, "uid": msg_users.a,
                "key": uuid4(), "hash": "g1" + "c" * 62,
            },
        )


@pytest.mark.asyncio
async def test_cancelled_with_stop_audit_succeeds(
    async_session: AsyncSession, msg_project, msg_users,
) -> None:
    """CANCELLED with proper stopped_by_user_id and stopped_at succeeds."""
    now = datetime.now(UTC)
    await async_session.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               stopped_by_user_id, stopped_at, created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'CANCELLED', '[]'::jsonb, 0, '[]'::jsonb,
               :uid, :now, :now, :now)
            """
        ),
        {
            "id": uuid4(), "proj": msg_project, "uid": msg_users.a,
            "key": uuid4(), "hash": "g3" + "c" * 62, "now": now,
        },
    )
    await async_session.flush()


@pytest.mark.asyncio
async def test_non_terminal_status_without_stop_audit_succeeds(
    async_session: AsyncSession, msg_project, msg_users,
) -> None:
    """COMPLETED without stopped_at must succeed (stops only required for
    CANCELLED/INTERRUPTED)."""
    await async_session.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', '', 'COMPLETED', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": msg_project, "uid": msg_users.a,
            "key": uuid4(), "hash": "g4" + "c" * 62,
        },
    )
    await async_session.flush()
