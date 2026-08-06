"""Integration tests for migration 0004 — artifact_draft, artifact, and project_change tables.

Covers:
- DDL constraints (sync fixtures)
- New draft does not require artifact_code
- One current candidate per (project_id, artifact_type, canonical_key)
- Fixed reference array defaults (empty arrays, not NULL)
- Array GIN index existence
- Current artifact uniqueness constraints
- Terminal change requires git decision pointer
- project_change status CHECK and decision pointer invariant
- Absence of forbidden history/manifest/outbox tables
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import String, text
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


def _insert_sync_profile(db: Session, user_id: str, code: str = "art-prof") -> str:
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
    db: Session, user_id: str, profile_id: str, name: str = "Artifact Test Project",
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


def _insert_sync_stage(
    db: Session, project_id: str, stage: str, status: str = "BUILDING",
) -> str:
    sid = uuid4()
    db.execute(
        text(
            """
            INSERT INTO project_stage
              (id, project_id, stage, status, revision,
               baseline_version, publish_attempts,
               created_at, updated_at)
            VALUES
              (:id, :proj, :stage, :status, 0,
               0, 0, now(), now())
            """
        ),
        {"id": sid, "proj": project_id, "stage": stage, "status": status},
    )
    return str(sid)


def _insert_sync_message(
    db: Session, project_id: str, user_id: str,
) -> str:
    msg_id = uuid4()
    db.execute(
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
            "id": msg_id, "proj": project_id, "uid": user_id,
            "key": uuid4(), "hash": "c" * 64,
        },
    )
    return str(msg_id)


def _insert_sync_artifact(
    db: Session, project_id: str, profile_id: str,
    artifact_code: str = "REQ-001",
    artifact_type: str = "REQUIREMENT",
    canonical_key: str = "req-auth",
) -> str:
    aid = uuid4()
    db.execute(
        text(
            """
            INSERT INTO artifact
              (id, project_id, stage, artifact_type, artifact_code,
               canonical_key, title, artifact_version, schema_version,
               body, source_refs, requirement_refs, module_refs,
               decision_refs, architecture_refs, api_refs,
               read_table_refs, write_table_refs,
               content_hash, profile_id, profile_version, profile_hash,
               baseline_version, git_path, git_commit_sha,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', :atype, :code,
               :ckey, 'Test Artifact', 1, 1,
               '{}'::jsonb, '{}', '{}', '{}',
               '{}', '{}', '{}',
               '{}', '{}',
               :chash, :pid, 0, :phash,
               1, :gpath, :gsha,
               now(), now())
            """
        ),
        {
            "id": aid, "proj": project_id, "atype": artifact_type,
            "code": artifact_code, "ckey": canonical_key,
            "chash": "d" * 64, "pid": profile_id, "phash": "e" * 64,
            "gpath": f"artifacts/{artifact_code}.yaml", "gsha": "f" * 40,
        },
    )
    return str(aid)


# ===================================================================
# DDL constraint tests — artifact_draft (sync)
# ===================================================================


def test_new_draft_does_not_require_artifact_code(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """A new draft (operation='CREATE') must accept NULL artifact_code."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    draft_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO artifact_draft
              (id, project_id, stage, artifact_type, artifact_code,
               canonical_key, title, artifact_version, schema_version,
               body, source_refs, requirement_refs, module_refs,
               decision_refs, architecture_refs, api_refs,
               read_table_refs, write_table_refs,
               content_hash, profile_id, profile_version, profile_hash,
               base_artifact_id, operation, status,
               validation_result, review_result,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
               'new-req', 'New Requirement', 0, 1,
               '{}'::jsonb, '{}', '{}', '{}',
               '{}', '{}', '{}',
               '{}', '{}',
               :chash, :pid, 0, :phash,
               NULL, 'CREATE', 'DRAFT',
               '{}'::jsonb, '{}'::jsonb,
               now(), now())
            """
        ),
        {
            "id": draft_id, "proj": proj_id,
            "chash": "g" * 64, "pid": pid, "phash": "h" * 64,
        },
    )

    # Verify the draft was inserted with NULL artifact_code
    result = migrated_db.execute(
        text("SELECT artifact_code FROM artifact_draft WHERE id = :id"),
        {"id": draft_id},
    )
    assert result.scalar() is None


def test_draft_operation_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """artifact_draft.operation CHECK must reject invalid values."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact_draft
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   base_artifact_id, operation, status,
                   validation_result, review_result,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
                   'bad-op', 'Bad Op', 0, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   NULL, 'ARCHIVE', 'DRAFT',
                   '{}'::jsonb, '{}'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "chash": "i" * 64, "pid": pid, "phash": "j" * 64,
            },
        )


def test_draft_status_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """artifact_draft.status CHECK must reject invalid values."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact_draft
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   base_artifact_id, operation, status,
                   validation_result, review_result,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
                   'bad-status', 'Bad Status', 0, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   NULL, 'CREATE', 'PUBLISHED',
                   '{}'::jsonb, '{}'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "chash": "k" * 64, "pid": pid, "phash": "l" * 64,
            },
        )


def test_draft_operation_update_delete_requires_base_artifact(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """UPDATE or DELETE operation without base_artifact_id must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact_draft
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   base_artifact_id, operation, status,
                   validation_result, review_result,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
                   'update-no-base', 'Update No Base', 0, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   NULL, 'UPDATE', 'DRAFT',
                   '{}'::jsonb, '{}'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "chash": "m" * 64, "pid": pid, "phash": "n" * 64,
            },
        )


def test_one_current_candidate_per_project_type_key(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Only one draft row per (project_id, artifact_type, canonical_key)."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    migrated_db.execute(
        text(
            """
            INSERT INTO artifact_draft
              (id, project_id, stage, artifact_type, artifact_code,
               canonical_key, title, artifact_version, schema_version,
               body, source_refs, requirement_refs, module_refs,
               decision_refs, architecture_refs, api_refs,
               read_table_refs, write_table_refs,
               content_hash, profile_id, profile_version, profile_hash,
               base_artifact_id, operation, status,
               validation_result, review_result,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
               'dup-key', 'First Draft', 0, 1,
               '{}'::jsonb, '{}', '{}', '{}',
               '{}', '{}', '{}',
               '{}', '{}',
               :chash, :pid, 0, :phash,
               NULL, 'CREATE', 'DRAFT',
               '{}'::jsonb, '{}'::jsonb,
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id,
            "chash": "o" * 64, "pid": pid, "phash": "p" * 64,
        },
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact_draft
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   base_artifact_id, operation, status,
                   validation_result, review_result,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
                   'dup-key', 'Second Draft', 0, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   NULL, 'CREATE', 'DRAFT',
                   '{}'::jsonb, '{}'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "chash": "q" * 64, "pid": pid, "phash": "r" * 64,
            },
        )


def test_draft_artifact_code_unique_when_not_null(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Partial unique on (project_id, artifact_code) WHERE NOT NULL."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    migrated_db.execute(
        text(
            """
            INSERT INTO artifact_draft
              (id, project_id, stage, artifact_type, artifact_code,
               canonical_key, title, artifact_version, schema_version,
               body, source_refs, requirement_refs, module_refs,
               decision_refs, architecture_refs, api_refs,
               read_table_refs, write_table_refs,
               content_hash, profile_id, profile_version, profile_hash,
               base_artifact_id, operation, status,
               validation_result, review_result,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', 'REQ-001',
               'key-a', 'Draft A', 0, 1,
               '{}'::jsonb, '{}', '{}', '{}',
               '{}', '{}', '{}',
               '{}', '{}',
               :chash, :pid, 0, :phash,
               NULL, 'CREATE', 'DRAFT',
               '{}'::jsonb, '{}'::jsonb,
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id,
            "chash": "s" * 64, "pid": pid, "phash": "t" * 64,
        },
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact_draft
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   base_artifact_id, operation, status,
                   validation_result, review_result,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', 'REQ-001',
                   'key-b', 'Draft B', 0, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   NULL, 'CREATE', 'DRAFT',
                   '{}'::jsonb, '{}'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "chash": "u" * 64, "pid": pid, "phash": "v" * 64,
            },
        )


def test_fixed_array_defaults_are_empty_arrays(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Fixed reference array columns default to '{}' (empty array), not NULL."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    draft_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO artifact_draft
              (id, project_id, stage, artifact_type,
               canonical_key, title, artifact_version, schema_version,
               body,
               content_hash, profile_id, profile_version, profile_hash,
               operation, status,
               validation_result, review_result,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT',
               'default-arrays', 'Default Arrays', 0, 1,
               '{}'::jsonb,
               :chash, :pid, 0, :phash,
               'CREATE', 'DRAFT',
               '{}'::jsonb, '{}'::jsonb,
               now(), now())
            """
        ),
        {
            "id": draft_id, "proj": proj_id,
            "chash": "w" * 64, "pid": pid, "phash": "x" * 64,
        },
    )

    result = migrated_db.execute(
        text(
            """
            SELECT source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs
            FROM artifact_draft WHERE id = :id
            """
        ),
        {"id": draft_id},
    )
    row = result.one()
    for col_name in [
        "source_refs", "requirement_refs", "module_refs",
        "decision_refs", "architecture_refs", "api_refs",
        "read_table_refs", "write_table_refs",
    ]:
        assert row._mapping[col_name] == [], (
            f"{col_name} default must be empty array, got {row._mapping[col_name]!r}"
        )


def test_artifact_fixed_array_defaults(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """artifact table fixed reference arrays default to empty arrays."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    art_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO artifact
              (id, project_id, stage, artifact_type, artifact_code,
               canonical_key, title, artifact_version, schema_version,
               body,
               content_hash, profile_id, profile_version, profile_hash,
               baseline_version, git_path, git_commit_sha,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', 'REQ-DEF',
               'art-default', 'Art Default', 1, 1,
               '{}'::jsonb,
               :chash, :pid, 0, :phash,
               1, :gpath, :gsha,
               now(), now())
            """
        ),
        {
            "id": art_id, "proj": proj_id,
            "chash": "y" * 64, "pid": pid, "phash": "z" * 64,
            "gpath": "artifacts/REQ-DEF.yaml", "gsha": "a1" + "b" * 62,
        },
    )

    result = migrated_db.execute(
        text(
            """
            SELECT source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs
            FROM artifact WHERE id = :id
            """
        ),
        {"id": art_id},
    )
    row = result.one()
    for col_name in [
        "source_refs", "requirement_refs", "module_refs",
        "decision_refs", "architecture_refs", "api_refs",
        "read_table_refs", "write_table_refs",
    ]:
        assert row._mapping[col_name] == [], (
            f"artifact {col_name} default must be empty array"
        )


# ===================================================================
# DDL constraint tests — artifact (sync)
# ===================================================================


def test_artifact_code_unique_per_project(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """(project_id, artifact_code) must be unique."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    _insert_sync_artifact(migrated_db, proj_id, pid, artifact_code="REQ-001")

    with pytest.raises(IntegrityError):
        _insert_sync_artifact(migrated_db, proj_id, pid, artifact_code="REQ-001",
                              canonical_key="different-key")


def test_artifact_type_canonical_key_unique_per_project(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """(project_id, artifact_type, canonical_key) must be unique."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    _insert_sync_artifact(
        migrated_db, proj_id, pid,
        artifact_code="REQ-001", artifact_type="REQUIREMENT",
        canonical_key="req-auth",
    )

    with pytest.raises(IntegrityError):
        _insert_sync_artifact(
            migrated_db, proj_id, pid,
            artifact_code="REQ-002", artifact_type="REQUIREMENT",
            canonical_key="req-auth",
        )


def test_artifact_git_path_unique_per_project(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """(project_id, git_path) must be unique."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    _insert_sync_stage(migrated_db, proj_id, "REQUIREMENT_MODULE")

    aid = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO artifact
              (id, project_id, stage, artifact_type, artifact_code,
               canonical_key, title, artifact_version, schema_version,
               body, source_refs, requirement_refs, module_refs,
               decision_refs, architecture_refs, api_refs,
               read_table_refs, write_table_refs,
               content_hash, profile_id, profile_version, profile_hash,
               baseline_version, git_path, git_commit_sha,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', 'REQ-GP1',
               'gp-key-a', 'GP Test A', 1, 1,
               '{}'::jsonb, '{}', '{}', '{}',
               '{}', '{}', '{}',
               '{}', '{}',
               :chash, :pid, 0, :phash,
               1, :gpath, :gsha,
               now(), now())
            """
        ),
        {
            "id": aid, "proj": proj_id,
            "chash": "a2" + "b" * 62, "pid": pid, "phash": "a3" + "c" * 62,
            "gpath": "artifacts/same-path.yaml", "gsha": "a4" + "d" * 62,
        },
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   baseline_version, git_path, git_commit_sha,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', 'REQ-GP2',
                   'gp-key-b', 'GP Test B', 1, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   1, :gpath, :gsha,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "chash": "a5" + "e" * 62, "pid": pid, "phash": "a6" + "f" * 62,
                "gpath": "artifacts/same-path.yaml", "gsha": "a7" + "g" * 62,
            },
        )


# ===================================================================
# DDL constraint tests — stage FK (sync)
# ===================================================================


def test_artifact_rejects_nonexistent_stage(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Inserting an artifact with a stage that has no matching row in
    project_stage must be rejected by the composite FK."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    # Intentionally skip _insert_sync_stage — no 'REQUIREMENT_MODULE'
    # row exists for this project.

    with pytest.raises(IntegrityError):
        _insert_sync_artifact(
            migrated_db, proj_id, pid,
            artifact_code="REQ-NOSTAGE",
            canonical_key="no-stage",
        )


def test_artifact_rejects_cross_project_stage(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """A (project_id, stage) pair must reference a project_stage row
    belonging to the *same* project — a stage from another project must
    be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_a = _insert_sync_project(
        migrated_db, migrated_db_user, pid, name="Proj A",
    )
    proj_b = _insert_sync_project(
        migrated_db, migrated_db_user, pid, name="Proj B",
    )
    # Create stage only in project B
    _insert_sync_stage(migrated_db, proj_b, "REQUIREMENT_MODULE")

    # Insert into project A — proj_a has no matching stage row
    with pytest.raises(IntegrityError):
        _insert_sync_artifact(
            migrated_db, proj_a, pid,
            artifact_code="REQ-CROSS",
            canonical_key="cross-project",
        )


def test_artifact_draft_rejects_nonexistent_stage(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Inserting an artifact_draft with a stage that has no matching row in
    project_stage must be rejected by the composite FK."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    # Skip _insert_sync_stage

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact_draft
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   base_artifact_id, operation, status,
                   validation_result, review_result,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
                   'nostage-draft', 'No Stage Draft', 0, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   NULL, 'CREATE', 'DRAFT',
                   '{}'::jsonb, '{}'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id,
                "chash": "ns1" + "a" * 61, "pid": pid, "phash": "ns2" + "b" * 61,
            },
        )


def test_artifact_draft_rejects_cross_project_stage(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """An artifact_draft (project_id, stage) pair must reference a stage
    belonging to the same project — cross-project pairs must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_a = _insert_sync_project(
        migrated_db, migrated_db_user, pid, name="Draft Proj A",
    )
    proj_b = _insert_sync_project(
        migrated_db, migrated_db_user, pid, name="Draft Proj B",
    )
    _insert_sync_stage(migrated_db, proj_b, "REQUIREMENT_MODULE")

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO artifact_draft
                  (id, project_id, stage, artifact_type, artifact_code,
                   canonical_key, title, artifact_version, schema_version,
                   body, source_refs, requirement_refs, module_refs,
                   decision_refs, architecture_refs, api_refs,
                   read_table_refs, write_table_refs,
                   content_hash, profile_id, profile_version, profile_hash,
                   base_artifact_id, operation, status,
                   validation_result, review_result,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, 'REQUIREMENT_MODULE', 'REQUIREMENT', NULL,
                   'xproj-draft', 'Cross Proj Draft', 0, 1,
                   '{}'::jsonb, '{}', '{}', '{}',
                   '{}', '{}', '{}',
                   '{}', '{}',
                   :chash, :pid, 0, :phash,
                   NULL, 'CREATE', 'DRAFT',
                   '{}'::jsonb, '{}'::jsonb,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_a,
                "chash": "xp1" + "c" * 61, "pid": pid, "phash": "xp2" + "d" * 61,
            },
        )


# ===================================================================
# DDL constraint tests — project_change (sync)
# ===================================================================


def test_project_change_status_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """project_change.status CHECK must reject invalid values."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = _insert_sync_message(migrated_db, proj_id, migrated_db_user)

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_change
                  (id, project_id, source_message_id, requested_by_user_id,
                   request_content, target_artifact_codes, base_baselines,
                   status, created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, :uid,
                   'Change request', '{}', '[]'::jsonb,
                   'DELETED', now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "msg": msg_id,
                "uid": migrated_db_user,
            },
        )


@pytest.mark.parametrize("null_field", [
    "decision",
    "decided_by_user_id",
    "decided_at",
    "decision_artifact_code",
    "decision_git_commit_sha",
])
def test_terminal_change_rejects_missing_pointer_field(
    migrated_db: Session, migrated_db_user: str, null_field: str,
) -> None:
    """APPLIED status must reject when any required terminal pointer field
    is NULL.

    The terminal CHECK requires all five fields to be non-null:
    decision, decided_by_user_id, decided_at, decision_artifact_code,
    decision_git_commit_sha.  This test nulls each independently while
    keeping the other four populated so only the targeted field triggers
    the violation.
    """
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = _insert_sync_message(migrated_db, proj_id, migrated_db_user)
    now = datetime.now(UTC)

    decision = None if null_field == "decision" else "APPROVED"
    dby = None if null_field == "decided_by_user_id" else migrated_db_user
    dat = None if null_field == "decided_at" else now
    dac = None if null_field == "decision_artifact_code" else "CHG-001"
    dgcs = None if null_field == "decision_git_commit_sha" else "b1" + "c" * 62

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_change
                  (id, project_id, source_message_id, requested_by_user_id,
                   request_content, target_artifact_codes, base_baselines,
                   status, decision, decided_by_user_id, decided_at,
                   decision_artifact_code, decision_git_commit_sha,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, :uid,
                   'Change request', '{}', '[]'::jsonb,
                   'APPLIED', :decision, :dby, :dat,
                   :dac, :dgcs,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "msg": msg_id,
                "uid": migrated_db_user,
                "decision": decision, "dby": dby, "dat": dat,
                "dac": dac, "dgcs": dgcs,
            },
        )


def test_terminal_change_with_valid_decision_pointer_succeeds(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """APPLIED with proper decision pointer succeeds."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = _insert_sync_message(migrated_db, proj_id, migrated_db_user)

    migrated_db.execute(
        text(
            """
            INSERT INTO project_change
              (id, project_id, source_message_id, requested_by_user_id,
               request_content, target_artifact_codes, base_baselines,
               status, decision, decided_by_user_id, decided_at,
               decision_artifact_code, decision_git_commit_sha,
               created_at, updated_at)
            VALUES
              (:id, :proj, :msg, :uid,
               'Change request', '{}', '[]'::jsonb,
               'APPLIED', 'APPROVED', :uid, now(),
               'CHG-001', :sha,
               now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id, "msg": msg_id,
            "uid": migrated_db_user, "sha": "b1" + "c" * 62,
        },
    )


def test_non_terminal_change_without_decision_succeeds(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """PROPOSED/ANALYZING without decision pointer must succeed."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = _insert_sync_message(migrated_db, proj_id, migrated_db_user)

    migrated_db.execute(
        text(
            """
            INSERT INTO project_change
              (id, project_id, source_message_id, requested_by_user_id,
               request_content, target_artifact_codes, base_baselines,
               status, created_at, updated_at)
            VALUES
              (:id, :proj, :msg, :uid,
               'Change request', '{}', '[]'::jsonb,
               'PROPOSED', now(), now())
            """
        ),
        {
            "id": uuid4(), "proj": proj_id, "msg": msg_id,
            "uid": migrated_db_user,
        },
    )


def test_project_change_decision_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """project_change.decision CHECK must reject invalid values."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = _insert_sync_message(migrated_db, proj_id, migrated_db_user)

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_change
                  (id, project_id, source_message_id, requested_by_user_id,
                   request_content, target_artifact_codes, base_baselines,
                   status, decision, decided_by_user_id, decided_at,
                   decision_artifact_code, decision_git_commit_sha,
                   created_at, updated_at)
                VALUES
                  (:id, :proj, :msg, :uid,
                   'Change request', '{}', '[]'::jsonb,
                   'APPLIED', 'PENDING', :uid, now(),
                   'CHG-001', :sha,
                   now(), now())
                """
            ),
            {
                "id": uuid4(), "proj": proj_id, "msg": msg_id,
                "uid": migrated_db_user, "sha": "b2" + "d" * 62,
            },
        )


def test_project_change_target_artifact_codes_default(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """target_artifact_codes defaults to empty array."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = _insert_sync_project(migrated_db, migrated_db_user, pid)
    msg_id = _insert_sync_message(migrated_db, proj_id, migrated_db_user)

    ch_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project_change
              (id, project_id, source_message_id, requested_by_user_id,
               request_content, base_baselines,
               status, created_at, updated_at)
            VALUES
              (:id, :proj, :msg, :uid,
               'Change request', '[]'::jsonb,
               'PROPOSED', now(), now())
            """
        ),
        {
            "id": ch_id, "proj": proj_id, "msg": msg_id,
            "uid": migrated_db_user,
        },
    )

    result = migrated_db.execute(
        text("SELECT target_artifact_codes FROM project_change WHERE id = :id"),
        {"id": ch_id},
    )
    assert result.scalar() == []


# ===================================================================
# GIN index existence tests (sync)
# ===================================================================


def _gin_index_exists(db: Session, table_name: str, column_name: str) -> bool:
    """Check whether a GIN index exists on the given table + column."""
    result = db.execute(
        text(
            """
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = :tbl
              AND indexdef ILIKE '%USING gin%'
              AND indexdef ILIKE '%' || :col || '%'
            """
        ),
        {"tbl": table_name, "col": column_name},
    )
    return result.scalar() is not None


REF_ARRAY_COLUMNS = [
    "requirement_refs",
    "module_refs",
    "decision_refs",
    "architecture_refs",
    "api_refs",
    "read_table_refs",
    "write_table_refs",
]


def test_artifact_gin_indexes_exist(
    migrated_db: Session,
) -> None:
    """Every fixed reference array column on ``artifact`` must have a GIN index."""
    for col in REF_ARRAY_COLUMNS:
        assert _gin_index_exists(migrated_db, "artifact", col), (
            f"Missing GIN index on artifact.{col}"
        )


def test_artifact_draft_gin_indexes_exist(
    migrated_db: Session,
) -> None:
    """Every fixed reference array column on ``artifact_draft`` must have a
    GIN index."""
    for col in REF_ARRAY_COLUMNS:
        assert _gin_index_exists(migrated_db, "artifact_draft", col), (
            f"Missing GIN index on artifact_draft.{col}"
        )


def test_project_change_gin_index_exists(
    migrated_db: Session,
) -> None:
    """``target_artifact_codes`` on ``project_change`` must have a GIN index."""
    assert _gin_index_exists(migrated_db, "project_change", "target_artifact_codes"), (
        "Missing GIN index on project_change.target_artifact_codes"
    )


# ===================================================================
# Forbidden tables test (sync)
# ===================================================================


FORBIDDEN_TABLES = [
    "artifact_history",
    "artifact_manifest",
    "artifact_relation",
    "stage_baseline_history",
    "git_publish_outbox",
    "delivery_run_history",
    "model_invocation",
    "profile_revision",
    "profile_migration_history",
    "profile_migration_run",
    "operation_log",
]


def test_no_forbidden_tables_exist(migrated_db: Session) -> None:
    """None of the tables explicitly excluded from V2 schema may exist."""
    result = migrated_db.execute(
        text(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
    )
    existing = {row[0] for row in result.all()}
    for forbidden in FORBIDDEN_TABLES:
        assert forbidden not in existing, (
            f"Forbidden table '{forbidden}' must not exist in V2 schema"
        )


# ===================================================================
# Async helper — insert prerequisite rows
# ===================================================================


@pytest_asyncio.fixture
async def art_users(async_session: AsyncSession):
    """A test user for artifact/change tests."""
    from types import SimpleNamespace

    now = datetime.now(UTC)
    uid = uuid4()
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
        {"id": uid, "un": f"art-{uid.hex[:8]}", "dn": "Art User", "now": now},
    )
    await async_session.flush()
    return SimpleNamespace(a=uid)


@pytest_asyncio.fixture
async def art_profile(async_session: AsyncSession, art_users):
    """A profile for artifact tests."""
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
            "id": pid, "code": f"ap-{pid.hex[:8]}",
            "name": "Artifact Profile", "uid": art_users.a, "now": now,
        },
    )
    await async_session.flush()
    return pid


@pytest_asyncio.fixture
async def art_project(async_session: AsyncSession, art_users, art_profile):
    """A project for artifact tests."""
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
              (:id, :key, :hash, 'Art Project', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": proj_id, "key": uuid4(), "hash": "c1" + "c" * 62,
            "pid": art_profile, "phash": "c2" + "d" * 62, "uid": art_users.a,
        },
    )
    await async_session.flush()
    return proj_id


@pytest_asyncio.fixture
async def art_stage(async_session: AsyncSession, art_project):
    """A REQUIREMENT_MODULE stage for artifact tests."""
    sid = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO project_stage
              (id, project_id, stage, status, revision,
               baseline_version, publish_attempts,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', 'BUILDING', 0,
               0, 0, now(), now())
            """
        ),
        {"id": sid, "proj": art_project},
    )
    await async_session.flush()
    return sid


@pytest_asyncio.fixture
async def art_message(async_session: AsyncSession, art_project, art_users):
    """A project_message for change FK."""
    msg_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO project_message
              (id, project_id, user_id, idempotency_key, request_hash,
               role, content, status, process, process_version, diagnostics,
               created_at, updated_at)
            VALUES
              (:id, :proj, :uid, :key, :hash,
               'USER', 'change request', 'PENDING', '[]'::jsonb, 0, '[]'::jsonb,
               now(), now())
            """
        ),
        {
            "id": msg_id, "proj": art_project, "uid": art_users.a,
            "key": uuid4(), "hash": "c3" + "e" * 62,
        },
    )
    await async_session.flush()
    return msg_id


# ===================================================================
# Async helper functions
# ===================================================================


async def _insert_draft(
    session: AsyncSession,
    project_id,
    stage_id,
    profile_id,
    artifact_code=None,
    artifact_type: str = "REQUIREMENT",
    canonical_key: str = None,
    operation: str = "CREATE",
    status: str = "DRAFT",
    base_artifact_id=None,
) -> str:
    """Insert an artifact_draft row and return its UUID."""
    import hashlib
    if canonical_key is None:
        canonical_key = f"ck-{uuid4().hex[:12]}"
    now = datetime.now(UTC)
    draft_id = uuid4()
    body = {"key": f"val-{draft_id.hex[:8]}"}
    content_hash = hashlib.sha256(repr(body).encode()).hexdigest()
    await session.execute(
        text(
            """
            INSERT INTO artifact_draft
              (id, project_id, stage, artifact_type, artifact_code,
               canonical_key, title, artifact_version, schema_version,
               body, source_refs, requirement_refs, module_refs,
               decision_refs, architecture_refs, api_refs,
               read_table_refs, write_table_refs,
               content_hash, profile_id, profile_version, profile_hash,
               base_artifact_id, operation, status,
               validation_result, review_result,
               created_at, updated_at)
            VALUES
              (:id, :proj, 'REQUIREMENT_MODULE', :atype, :acode,
               :ckey, :title, 0, 1,
               CAST(:body AS jsonb), '{}', '{}', '{}',
               '{}', '{}', '{}',
               '{}', '{}',
               :chash, :pid, 0, :phash,
               :baid, :op, :st,
               '{}'::jsonb, '{}'::jsonb,
               :now, :now)
            """
        ),
        {
            "id": draft_id, "proj": project_id, "atype": artifact_type,
            "acode": artifact_code, "ckey": canonical_key,
            "title": f"Draft {canonical_key}",
            "body": '{}',
            "chash": content_hash, "pid": profile_id, "phash": content_hash,
            "baid": base_artifact_id, "op": operation, "st": status,
            "now": now,
        },
    )
    await session.flush()
    return str(draft_id)


async def _insert_change(
    session: AsyncSession,
    project_id,
    message_id,
    user_id,
    status: str = "PROPOSED",
    decision: str | None = None,
    decided_by_user_id=None,
    decided_at=None,
    decision_artifact_code: str | None = None,
    decision_git_commit_sha: str | None = None,
) -> str:
    """Insert a project_change row and return its UUID."""
    now = datetime.now(UTC)
    ch_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO project_change
              (id, project_id, source_message_id, requested_by_user_id,
               request_content, target_artifact_codes, base_baselines,
               status, decision, decided_by_user_id, decided_at,
               decision_artifact_code, decision_git_commit_sha,
               created_at, updated_at)
            VALUES
              (:id, :proj, :msg, :uid,
               :content, :targets, CAST(:baselines AS jsonb),
               :status, :decision, :dby, :dat,
               :dac, :dgcs,
               :now, :now)
            """
        ),
        {
            "id": ch_id, "proj": project_id, "msg": message_id,
            "uid": user_id, "content": "Test change request",
            "targets": "{}", "baselines": "[]",
            "status": status, "decision": decision,
            "dby": decided_by_user_id, "dat": decided_at,
            "dac": decision_artifact_code, "dgcs": decision_git_commit_sha,
            "now": now,
        },
    )
    await session.flush()
    return str(ch_id)


async def _mark_change_applied_without_decision_commit(
    session: AsyncSession, change_id,
) -> None:
    """Attempt to set a change to APPLIED without decision_git_commit_sha."""
    await session.execute(
        text(
            """
            UPDATE project_change
            SET status = 'APPLIED',
                decision = 'APPROVED',
                decided_by_user_id = requested_by_user_id,
                decided_at = now(),
                updated_at = now()
            WHERE id = :id
            """
        ),
        {"id": change_id},
    )
    await session.flush()


# ===================================================================
# Async invariant tests
# ===================================================================


@pytest.mark.asyncio
async def test_new_draft_does_not_require_artifact_code_async(
    async_session: AsyncSession,
    art_project, art_stage, art_profile,
) -> None:
    """A new draft inserted with artifact_code=NULL must succeed."""
    draft_id = await _insert_draft(
        async_session, art_project, art_stage, art_profile,
        artifact_code=None, canonical_key="async-null-code",
    )
    assert draft_id is not None

    # Verify NULL persisted
    result = await async_session.execute(
        text("SELECT artifact_code FROM artifact_draft WHERE id = :id"),
        {"id": draft_id},
    )
    assert result.scalar() is None


@pytest.mark.asyncio
async def test_terminal_change_requires_git_decision_pointer_async(
    async_session: AsyncSession,
    art_project, art_message, art_users,
) -> None:
    """Marking a change as APPLIED without decision_git_commit_sha must
    raise IntegrityError because of the CHECK constraint."""
    # Insert a proposed change first
    ch_id = await _insert_change(
        async_session, art_project, art_message, art_users.a,
        status="PROPOSED",
    )

    # Attempt to mark it APPLIED without the required decision pointer
    with pytest.raises(IntegrityError):
        await _mark_change_applied_without_decision_commit(
            async_session, ch_id,
        )


@pytest.mark.asyncio
async def test_one_candidate_per_project_type_key_async(
    async_session: AsyncSession,
    art_project, art_stage, art_profile,
) -> None:
    """Duplicate (project_id, artifact_type, canonical_key) on artifact_draft
    must raise IntegrityError."""
    await _insert_draft(
        async_session, art_project, art_stage, art_profile,
        canonical_key="dup-async-key",
    )

    with pytest.raises(IntegrityError):
        await _insert_draft(
            async_session, art_project, art_stage, art_profile,
            canonical_key="dup-async-key",
        )


@pytest.mark.asyncio
async def test_draft_update_requires_base_artifact_async(
    async_session: AsyncSession,
    art_project, art_stage, art_profile,
) -> None:
    """UPDATE operation without base_artifact_id must fail CHECK."""
    with pytest.raises(IntegrityError):
        await _insert_draft(
            async_session, art_project, art_stage, art_profile,
            canonical_key="update-no-ref", operation="UPDATE",
            base_artifact_id=None,
        )


@pytest.mark.asyncio
async def test_draft_delete_requires_base_artifact_async(
    async_session: AsyncSession,
    art_project, art_stage, art_profile,
) -> None:
    """DELETE operation without base_artifact_id must fail CHECK."""
    with pytest.raises(IntegrityError):
        await _insert_draft(
            async_session, art_project, art_stage, art_profile,
            canonical_key="delete-no-ref", operation="DELETE",
            base_artifact_id=None,
        )


@pytest.mark.asyncio
async def test_create_operation_accepts_null_base_artifact_async(
    async_session: AsyncSession,
    art_project, art_stage, art_profile,
) -> None:
    """CREATE operation with NULL base_artifact_id must succeed."""
    draft_id = await _insert_draft(
        async_session, art_project, art_stage, art_profile,
        canonical_key="create-ok", operation="CREATE",
        base_artifact_id=None,
    )
    assert draft_id is not None


@pytest.mark.asyncio
async def test_artifact_code_unique_non_null_async(
    async_session: AsyncSession,
    art_project, art_stage, art_profile,
) -> None:
    """Partial unique on (project_id, artifact_code) WHERE NOT NULL."""
    await _insert_draft(
        async_session, art_project, art_stage, art_profile,
        artifact_code="REQ-ASYNC-001", canonical_key="key-async-1",
    )

    with pytest.raises(IntegrityError):
        await _insert_draft(
            async_session, art_project, art_stage, art_profile,
            artifact_code="REQ-ASYNC-001", canonical_key="key-async-2",
        )


# ===================================================================
# ORM metadata type-assertion tests
# ===================================================================


def test_artifact_datetime_columns_are_timezone_aware() -> None:
    """All datetime columns on Artifact must declare DateTime(timezone=True)."""
    from src.modules.artifacts.models import Artifact
    for col_name in ("created_at", "updated_at"):
        col = Artifact.__table__.c[col_name]
        assert col.type.timezone is True, (
            f"Artifact.{col_name} must be DateTime(timezone=True), "
            f"got {col.type}"
        )


def test_artifact_draft_datetime_columns_are_timezone_aware() -> None:
    """All datetime columns on ArtifactDraft must declare DateTime(timezone=True)."""
    from src.modules.artifacts.models import ArtifactDraft
    for col_name in ("created_at", "updated_at"):
        col = ArtifactDraft.__table__.c[col_name]
        assert col.type.timezone is True, (
            f"ArtifactDraft.{col_name} must be DateTime(timezone=True), "
            f"got {col.type}"
        )


def test_project_change_datetime_columns_are_timezone_aware() -> None:
    """All datetime columns on ProjectChange must declare DateTime(timezone=True)."""
    from src.modules.changes.models import ProjectChange
    for col_name in ("created_at", "updated_at", "decided_at"):
        col = ProjectChange.__table__.c[col_name]
        assert col.type.timezone is True, (
            f"ProjectChange.{col_name} must be DateTime(timezone=True), "
            f"got {col.type}"
        )


def test_artifact_varchar_columns_have_explicit_lengths() -> None:
    """Constrained varchar columns on Artifact must declare String(N)
    with authoritative lengths matching the migration DDL."""
    from src.modules.artifacts.models import Artifact

    expected: dict[str, int] = {
        "stage": 40,
        "artifact_type": 40,
        "artifact_code": 40,
        "canonical_key": 300,
        "content_hash": 64,
        "profile_hash": 64,
        "git_commit_sha": 64,
    }
    for col_name, length in expected.items():
        col = Artifact.__table__.c[col_name]
        assert isinstance(col.type, String), (
            f"Artifact.{col_name} must be String, got {type(col.type).__name__}"
        )
        assert col.type.length == length, (
            f"Artifact.{col_name} length expected {length}, got {col.type.length}"
        )


def test_artifact_draft_varchar_columns_have_explicit_lengths() -> None:
    """Constrained varchar columns on ArtifactDraft must declare String(N)
    with authoritative lengths matching the migration DDL."""
    from src.modules.artifacts.models import ArtifactDraft

    expected: dict[str, int] = {
        "stage": 40,
        "artifact_type": 40,
        "artifact_code": 40,
        "canonical_key": 300,
        "content_hash": 64,
        "profile_hash": 64,
        "operation": 16,
        "status": 24,
    }
    for col_name, length in expected.items():
        col = ArtifactDraft.__table__.c[col_name]
        assert isinstance(col.type, String), (
            f"ArtifactDraft.{col_name} must be String, "
            f"got {type(col.type).__name__}"
        )
        assert col.type.length == length, (
            f"ArtifactDraft.{col_name} length expected {length}, "
            f"got {col.type.length}"
        )


def test_project_change_varchar_columns_have_explicit_lengths() -> None:
    """Constrained varchar columns on ProjectChange must declare String(N)
    with authoritative lengths matching the migration DDL."""
    from src.modules.changes.models import ProjectChange

    expected: dict[str, int] = {
        "status": 24,
        "decision": 16,
        "decision_artifact_code": 40,
        "decision_git_commit_sha": 64,
    }
    for col_name, length in expected.items():
        col = ProjectChange.__table__.c[col_name]
        assert isinstance(col.type, String), (
            f"ProjectChange.{col_name} must be String, "
            f"got {type(col.type).__name__}"
        )
        assert col.type.length == length, (
            f"ProjectChange.{col_name} length expected {length}, "
            f"got {col.type.length}"
        )
