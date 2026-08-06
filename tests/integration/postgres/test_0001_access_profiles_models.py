"""Integration tests for migration 0001 — access, profile, and model tables.

These tests verify the schema constraints defined in database design 1.1:
- app_user: case-insensitive username uniqueness, non-null salt, system_role/status checks
- login_log: result check, foreign key cascade
- domain_profile: builtin-general uniqueness, code uniqueness, status check
- domain_profile_draft: one draft per profile, optimistic lock
- domain_profile_version: unique (profile_id, version), version>0, content_hash uniqueness
- profile_migration: unique (profile_id, from_version, to_version), adjacent version check
- model_profile: unique code, one active default per purpose, status check

Uses synchronous SQLAlchemy sessions so that constraint verification does
not require the ``greenlet`` library at the integration-test layer.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# app_user
# ---------------------------------------------------------------------------


def test_username_case_insensitive_unique(migrated_db: Session) -> None:
    """Inserting 'Admin' then 'admin' must violate the lower(username) unique index."""
    migrated_db.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, 'Admin', 'Admin User', 'hash-a', decode('00','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": uuid4()},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO app_user
                  (id, username, display_name, password_hash, password_salt,
                   system_role, status, must_change_password, created_at, updated_at)
                VALUES
                  (:id, 'admin', 'Duplicate Admin', 'hash-b', decode('01','hex'),
                   'USER', 'ACTIVE', true, now(), now())
                """
            ),
            {"id": uuid4()},
        )


def test_password_salt_not_null(migrated_db: Session) -> None:
    """Every user row must carry its own non-null salt."""
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO app_user
                  (id, username, display_name, password_hash, password_salt,
                   system_role, status, must_change_password, created_at, updated_at)
                VALUES
                  (:id, 'saltless', 'No Salt', 'hash', NULL,
                   'USER', 'ACTIVE', true, now(), now())
                """
            ),
            {"id": uuid4()},
        )


def test_system_role_check_rejects_bad_value(migrated_db: Session) -> None:
    """system_role must be 'ADMIN' or 'USER'."""
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO app_user
                  (id, username, display_name, password_hash, password_salt,
                   system_role, status, must_change_password, created_at, updated_at)
                VALUES
                  (:id, 'bad-role', 'Bad Role', 'hash', decode('02','hex'),
                   'SUPERUSER', 'ACTIVE', false, now(), now())
                """
            ),
            {"id": uuid4()},
        )


def test_status_check_rejects_bad_value(migrated_db: Session) -> None:
    """status must be 'ACTIVE' or 'DISABLED'."""
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO app_user
                  (id, username, display_name, password_hash, password_salt,
                   system_role, status, must_change_password, created_at, updated_at)
                VALUES
                  (:id, 'bad-status', 'Bad Status', 'hash', decode('03','hex'),
                   'USER', 'DELETED', false, now(), now())
                """
            ),
            {"id": uuid4()},
        )


# ---------------------------------------------------------------------------
# login_log
# ---------------------------------------------------------------------------


def test_login_log_result_check(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """result must be 'SUCCESS' or 'FAILED'."""
    migrated_db.execute(
        text(
            """
            INSERT INTO login_log
              (id, user_id, username_attempted, result, failure_code, created_at)
            VALUES
              (:id, :uid, 'Admin', 'SUCCESS', NULL, now())
            """
        ),
        {"id": uuid4(), "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO login_log
                  (id, user_id, username_attempted, result, failure_code, created_at)
                VALUES
                  (:id, :uid, 'Admin', 'TIMEOUT', NULL, now())
                """
            ),
            {"id": uuid4(), "uid": migrated_db_user},
        )


# ---------------------------------------------------------------------------
# domain_profile
# ---------------------------------------------------------------------------


def test_domain_profile_code_unique(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """profile code must be unique."""
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'gen', 'General', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": uuid4(), "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO domain_profile
                  (id, code, name, status, created_by_user_id, created_at, updated_at)
                VALUES (:id, 'gen', 'Duplicate General', 'ACTIVE', :uid, now(), now())
                """
            ),
            {"id": uuid4(), "uid": migrated_db_user},
        )


def test_only_one_builtin_general_profile(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """Only one domain_profile may have is_builtin_general=true."""
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, is_builtin_general,
               created_by_user_id, created_at, updated_at)
            VALUES (:id, 'builtin-1', 'Built-in General', 'ACTIVE', true,
                    :uid, now(), now())
            """
        ),
        {"id": uuid4(), "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO domain_profile
                  (id, code, name, status, is_builtin_general,
                   created_by_user_id, created_at, updated_at)
                VALUES (:id, 'builtin-2', 'Second Built-in', 'ACTIVE', true,
                        :uid, now(), now())
                """
            ),
            {"id": uuid4(), "uid": migrated_db_user},
        )


def test_domain_profile_status_check(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """status must be 'ACTIVE' or 'INACTIVE'."""
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO domain_profile
                  (id, code, name, status, created_by_user_id, created_at, updated_at)
                VALUES (:id, 'bad-status', 'Bad Status', 'ARCHIVED', :uid, now(), now())
                """
            ),
            {"id": uuid4(), "uid": migrated_db_user},
        )


# ---------------------------------------------------------------------------
# domain_profile_draft
# ---------------------------------------------------------------------------


def test_one_draft_per_profile(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """Each profile can have at most one current draft (UNIQUE profile_id)."""
    profile_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'dp-draft', 'Draft Profile', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": profile_id, "uid": migrated_db_user},
    )

    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile_draft
              (id, profile_id, base_version, content, content_hash,
               updated_by_user_id, created_at, updated_at)
            VALUES (:id, :pid, 0, '{}'::jsonb, 'hash-1', :uid, now(), now())
            """
        ),
        {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO domain_profile_draft
                  (id, profile_id, base_version, content, content_hash,
                   updated_by_user_id, created_at, updated_at)
                VALUES (:id, :pid, 0, '{}'::jsonb, 'hash-2', :uid, now(), now())
                """
            ),
            {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
        )


# ---------------------------------------------------------------------------
# domain_profile_version
# ---------------------------------------------------------------------------


def test_profile_version_unique_per_profile(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """UNIQUE(profile_id, version) — no duplicate version numbers per profile."""
    profile_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'dp-ver', 'Versioned Profile', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": profile_id, "uid": migrated_db_user},
    )

    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile_version
              (id, profile_id, version, content, content_hash, validation_result,
               published_by_user_id, published_at)
            VALUES (:id, :pid, 1, '{}'::jsonb, 'ch-1', '{}'::jsonb, :uid, now())
            """
        ),
        {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO domain_profile_version
                  (id, profile_id, version, content, content_hash, validation_result,
                   published_by_user_id, published_at)
                VALUES (:id, :pid, 1, '{"v": 2}'::jsonb, 'ch-2', '{}'::jsonb, :uid, now())
                """
            ),
            {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
        )


def test_profile_version_must_be_positive(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """version CHECK > 0 — version 0 must be rejected."""
    profile_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'dp-pos', 'Positive Version', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": profile_id, "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO domain_profile_version
                  (id, profile_id, version, content, content_hash, validation_result,
                   published_by_user_id, published_at)
                VALUES (:id, :pid, 0, '{}'::jsonb, 'ch-0', '{}'::jsonb, :uid, now())
                """
            ),
            {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
        )


def test_profile_version_content_hash_unique(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """UNIQUE(profile_id, content_hash) — same content hash in same profile is duplicate."""
    profile_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'dp-chash', 'Hash Profile', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": profile_id, "uid": migrated_db_user},
    )

    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile_version
              (id, profile_id, version, content, content_hash, validation_result,
               published_by_user_id, published_at)
            VALUES (:id, :pid, 1, '{}'::jsonb, 'same-hash', '{}'::jsonb, :uid, now())
            """
        ),
        {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO domain_profile_version
                  (id, profile_id, version, content, content_hash, validation_result,
                   published_by_user_id, published_at)
                VALUES (:id, :pid, 2, '{}'::jsonb, 'same-hash', '{}'::jsonb, :uid, now())
                """
            ),
            {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
        )


# ---------------------------------------------------------------------------
# profile_migration
# ---------------------------------------------------------------------------


def test_migration_adjacent_version_check(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """to_version MUST equal from_version + 1 (adjacent migration only)."""
    profile_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'dp-mig', 'Migration Profile', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": profile_id, "uid": migrated_db_user},
    )

    # Valid adjacent: 1 -> 2
    migrated_db.execute(
        text(
            """
            INSERT INTO profile_migration
              (id, profile_id, from_version, to_version, definition, content_hash,
               updated_by_user_id, created_at, updated_at)
            VALUES (:id, :pid, 1, 2, '{}'::jsonb, 'mh-1', :uid, now(), now())
            """
        ),
        {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
    )

    # Invalid skip: 2 -> 4 (must be 3)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO profile_migration
                  (id, profile_id, from_version, to_version, definition, content_hash,
                   updated_by_user_id, created_at, updated_at)
                VALUES (:id, :pid, 2, 4, '{}'::jsonb, 'mh-2', :uid, now(), now())
                """
            ),
            {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
        )


def test_migration_unique_from_to(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """UNIQUE(profile_id, from_version, to_version) — no duplicate migration edges."""
    profile_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'dp-mig2', 'Migration 2', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": profile_id, "uid": migrated_db_user},
    )

    migrated_db.execute(
        text(
            """
            INSERT INTO profile_migration
              (id, profile_id, from_version, to_version, definition, content_hash,
               updated_by_user_id, created_at, updated_at)
            VALUES (:id, :pid, 1, 2, '{}'::jsonb, 'mh-3', :uid, now(), now())
            """
        ),
        {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO profile_migration
                  (id, profile_id, from_version, to_version, definition, content_hash,
                   updated_by_user_id, created_at, updated_at)
                VALUES (:id, :pid, 1, 2, '{"alt": true}'::jsonb, 'mh-4', :uid, now(), now())
                """
            ),
            {"id": uuid4(), "pid": profile_id, "uid": migrated_db_user},
        )


# ---------------------------------------------------------------------------
# model_profile
# ---------------------------------------------------------------------------


def test_model_profile_code_unique(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """model_profile code must be unique."""
    migrated_db.execute(
        text(
            """
            INSERT INTO model_profile
              (id, code, name, purpose, provider, model_name,
               secret_ref, status, created_by_user_id, updated_by_user_id,
               created_at, updated_at)
            VALUES (:id, 'mp-intent', 'Intent Model', 'INTENT', 'anthropic',
                    'claude-sonnet-5', 'sec://models/anthropic', 'ACTIVE',
                    :uid, :uid, now(), now())
            """
        ),
        {"id": uuid4(), "uid": migrated_db_user},
    )

    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO model_profile
                  (id, code, name, purpose, provider, model_name,
                   secret_ref, status, created_by_user_id, updated_by_user_id,
                   created_at, updated_at)
                VALUES (:id, 'mp-intent', 'Duplicate Intent', 'INTENT', 'anthropic',
                        'claude-opus-5', 'sec://models/anthropic', 'ACTIVE',
                        :uid, :uid, now(), now())
                """
            ),
            {"id": uuid4(), "uid": migrated_db_user},
        )


def test_one_active_default_per_purpose(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """At most one ACTIVE model_profile with is_default=true per purpose."""
    # First default for INTENT — succeeds
    migrated_db.execute(
        text(
            """
            INSERT INTO model_profile
              (id, code, name, purpose, provider, model_name,
               secret_ref, status, is_default,
               created_by_user_id, updated_by_user_id, created_at, updated_at)
            VALUES (:id, 'mp-def-1', 'Default Intent', 'INTENT', 'anthropic',
                    'claude-sonnet-5', 'sec://models/anthropic', 'ACTIVE', true,
                    :uid, :uid, now(), now())
            """
        ),
        {"id": uuid4(), "uid": migrated_db_user},
    )

    # Second default for INTENT — must be rejected
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO model_profile
                  (id, code, name, purpose, provider, model_name,
                   secret_ref, status, is_default,
                   created_by_user_id, updated_by_user_id, created_at, updated_at)
                VALUES (:id, 'mp-def-2', 'Second Default Intent', 'INTENT', 'anthropic',
                        'claude-opus-5', 'sec://models/anthropic', 'ACTIVE', true,
                        :uid, :uid, now(), now())
                """
            ),
            {"id": uuid4(), "uid": migrated_db_user},
        )


def test_default_for_different_purposes_allowed(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Different purposes can each have their own active default."""
    migrated_db.execute(
        text(
            """
            INSERT INTO model_profile
              (id, code, name, purpose, provider, model_name,
               secret_ref, status, is_default,
               created_by_user_id, updated_by_user_id, created_at, updated_at)
            VALUES (:id, 'mp-intent-def', 'Intent Default', 'INTENT', 'anthropic',
                    'claude-sonnet-5', 'sec://models/anthropic', 'ACTIVE', true,
                    :uid, :uid, now(), now())
            """
        ),
        {"id": uuid4(), "uid": migrated_db_user},
    )

    # Different purpose — should succeed
    migrated_db.execute(
        text(
            """
            INSERT INTO model_profile
              (id, code, name, purpose, provider, model_name,
               secret_ref, status, is_default,
               created_by_user_id, updated_by_user_id, created_at, updated_at)
            VALUES (:id, 'mp-author-def', 'Author Default', 'AUTHOR', 'anthropic',
                    'claude-opus-5', 'sec://models/anthropic', 'ACTIVE', true,
                    :uid, :uid, now(), now())
            """
        ),
        {"id": uuid4(), "uid": migrated_db_user},
    )


def test_model_profile_status_check(
    migrated_db: Session, migrated_db_user: str
) -> None:
    """model_profile status must be 'ACTIVE' or 'INACTIVE'."""
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO model_profile
                  (id, code, name, purpose, provider, model_name,
                   secret_ref, status, created_by_user_id, updated_by_user_id,
                   created_at, updated_at)
                VALUES (:id, 'mp-bad', 'Bad Status', 'INTENT', 'anthropic',
                        'claude-sonnet-5', 'sec://models/anthropic', 'DEPRECATED',
                        :uid, :uid, now(), now())
                """
            ),
            {"id": uuid4(), "uid": migrated_db_user},
        )


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def migrated_db_user(migrated_db: Session) -> str:
    """Insert a single user and return its UUID for FK references in other tests."""
    uid = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Fixture User', 'hash', decode('aa','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": uid, "un": f"fixture-{uid.hex[:8]}"},
    )
    return str(uid)
