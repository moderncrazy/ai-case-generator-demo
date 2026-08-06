"""Integration tests for migration 0001 — access, profile, and model tables.

Covers:
- DDL constraints (sync fixtures)
- Real async engine/session transaction (Finding 1)
- Profile repository transactional invariants (Finding 2)
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from src.modules.profiles.repository import (
    BuiltinProfileCannotBeDeleted,
    BuiltinProfileCannotBeDisabled,
    ProfileNotFound,
    ProfileRepository,
    ProfileVersionNotSequential,
)


# ===================================================================
# DDL constraint tests (sync)
# ===================================================================


def test_username_case_insensitive_unique(migrated_db: Session) -> None:
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


def test_login_log_result_check(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_domain_profile_code_unique(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_only_one_builtin_general_profile(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_domain_profile_status_check(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_one_draft_per_profile(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_profile_version_unique_per_profile(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_profile_version_must_be_positive(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_profile_version_content_hash_unique(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_migration_adjacent_version_check(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_migration_unique_from_to(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_model_profile_code_unique(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_one_active_default_per_purpose(migrated_db: Session, migrated_db_user: str) -> None:
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


def test_model_profile_status_check(migrated_db: Session, migrated_db_user: str) -> None:
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


# ===================================================================
# Finding 1 — real async engine/session transaction evidence
# ===================================================================


@pytest.mark.asyncio
async def test_async_engine_and_session_execute_real_query(
    async_session: AsyncSession,
) -> None:
    """``create_engine`` + ``session_factory`` round-trip with a real query."""
    result = await async_session.execute(text("SELECT 1 AS one"))
    row = result.one()
    assert row.one == 1


@pytest.mark.asyncio
async def test_async_session_can_insert_and_rollback(
    async_session: AsyncSession,
) -> None:
    """Insert through the async session, verify it reads back, rollback."""
    uid = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Async Test', 'hash', decode('ff','hex'),
               'USER', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": uid, "un": f"async-{uid.hex[:8]}"},
    )
    # Flush so we can read back within the same transaction
    await async_session.flush()
    result = await async_session.execute(
        text("SELECT display_name FROM app_user WHERE id = :uid"),
        {"uid": uid},
    )
    assert result.scalar() == "Async Test"
    # Transaction is rolled back by the fixture


# ===================================================================
# Finding 2 — profile repository transactional invariants
# ===================================================================


@pytest.mark.asyncio
async def test_ensure_builtin_general_is_idempotent(
    async_session: AsyncSession,
    migrated_db_user: str,
) -> None:
    """Two calls return the same built-in row."""
    admin_id = uuid4()
    # Insert the admin user for FK
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Admin', 'hash', decode('ee','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": admin_id, "un": f"repo-admin-{admin_id.hex[:8]}"},
    )
    await async_session.flush()

    repo = ProfileRepository(async_session)
    first = await repo.ensure_builtin_general(admin_id)
    second = await repo.ensure_builtin_general(admin_id)

    assert first.id == second.id
    assert first.is_builtin_general is True
    assert first.code == "BUILTIN_GENERAL"
    assert first.status == "ACTIVE"
    assert first.current_version == 0


@pytest.mark.asyncio
async def test_publish_version_advances_current_version_monotonically(
    async_session: AsyncSession,
) -> None:
    """Publishing version N updates current_version to N under row lock."""
    admin_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Publisher', 'hash', decode('dd','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": admin_id, "un": f"pub-{admin_id.hex[:8]}"},
    )
    await async_session.flush()

    repo = ProfileRepository(async_session)
    profile = await repo.ensure_builtin_general(admin_id)

    # First publication: version 1
    v1 = await repo.publish_version(
        profile.id, 1, {"key": "v1"}, "hash-v1",
        {"ok": True}, admin_id,
    )
    assert v1.version == 1

    # Second publication: version 2
    v2 = await repo.publish_version(
        profile.id, 2, {"key": "v2"}, "hash-v2",
        {"ok": True}, admin_id,
    )
    assert v2.version == 2

    # Verify current_version advanced
    from sqlalchemy import select as sa_select
    from src.modules.profiles.models import DomainProfile
    result = await async_session.execute(
        sa_select(DomainProfile).where(DomainProfile.id == profile.id)
    )
    refreshed = result.scalar_one()
    assert refreshed.current_version == 2


@pytest.mark.asyncio
async def test_publish_version_rejects_non_sequential(
    async_session: AsyncSession,
) -> None:
    """Version must be exactly current_version + 1."""
    admin_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Seq Admin', 'hash', decode('cc','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": admin_id, "un": f"seq-{admin_id.hex[:8]}"},
    )
    await async_session.flush()

    repo = ProfileRepository(async_session)
    profile = await repo.ensure_builtin_general(admin_id)

    # Publish version 1
    await repo.publish_version(
        profile.id, 1, {"a": 1}, "h1", {"ok": True}, admin_id,
    )

    # Try to publish version 3 — must fail (current_version = 1, expected 2)
    with pytest.raises(ProfileVersionNotSequential, match="Expected version 2"):
        await repo.publish_version(
            profile.id, 3, {"a": 3}, "h3", {"ok": True}, admin_id,
        )


@pytest.mark.asyncio
async def test_builtin_profile_cannot_be_disabled(
    async_session: AsyncSession,
) -> None:
    """Setting built-in general Profile to INACTIVE raises domain error."""
    admin_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Disable Admin', 'hash', decode('bb','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": admin_id, "un": f"dis-{admin_id.hex[:8]}"},
    )
    await async_session.flush()

    repo = ProfileRepository(async_session)
    builtin = await repo.ensure_builtin_general(admin_id)

    with pytest.raises(BuiltinProfileCannotBeDisabled):
        await repo.set_status(builtin.id, "INACTIVE", admin_id)


@pytest.mark.asyncio
async def test_non_builtin_profile_can_be_disabled(
    async_session: AsyncSession,
) -> None:
    """A regular Profile can be disabled."""
    admin_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Reg Admin', 'hash', decode('aa','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": admin_id, "un": f"reg-{admin_id.hex[:8]}"},
    )
    await async_session.flush()

    # Direct insert of a non-builtin profile
    pid = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'regular', 'Regular', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": pid, "uid": admin_id},
    )
    await async_session.flush()

    repo = ProfileRepository(async_session)
    updated = await repo.set_status(pid, "INACTIVE", admin_id)
    assert updated.status == "INACTIVE"


@pytest.mark.asyncio
async def test_builtin_profile_cannot_be_deleted(
    async_session: AsyncSession,
) -> None:
    """Deleting the built-in general Profile raises domain error."""
    admin_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Delete Admin', 'hash', decode('99','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": admin_id, "un": f"del-{admin_id.hex[:8]}"},
    )
    await async_session.flush()

    repo = ProfileRepository(async_session)
    builtin = await repo.ensure_builtin_general(admin_id)

    with pytest.raises(BuiltinProfileCannotBeDeleted):
        await repo.delete_profile(builtin.id)


@pytest.mark.asyncio
async def test_delete_non_builtin_profile_succeeds(
    async_session: AsyncSession,
) -> None:
    """A regular Profile can be deleted."""
    admin_id = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'DelReg Admin', 'hash', decode('88','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": admin_id, "un": f"delreg-{admin_id.hex[:8]}"},
    )
    await async_session.flush()

    pid = uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, created_by_user_id, created_at, updated_at)
            VALUES (:id, 'to-delete', 'Delete Me', 'ACTIVE', :uid, now(), now())
            """
        ),
        {"id": pid, "uid": admin_id},
    )
    await async_session.flush()

    repo = ProfileRepository(async_session)
    await repo.delete_profile(pid)

    with pytest.raises(ProfileNotFound):
        await repo.delete_profile(pid)


# ===================================================================
# Fix Round 2 — concurrent idempotency (Finding 2)
# ===================================================================


@pytest.mark.asyncio
async def test_ensure_builtin_general_is_concurrently_idempotent(
    async_engine: AsyncEngine,
) -> None:
    """Two concurrent transactions both succeed — no IntegrityError or lost row.

    This test would have exposed the old check-then-insert race: two
    transactions both SELECT and see no row, both INSERT, and one
    crashes with a duplicate-key violation.  The fix uses ``INSERT
    ... ON CONFLICT DO NOTHING`` so the loser silently re-selects.
    """
    import asyncio

    from src.persistence.postgres.session import (
        session_factory as app_session_factory,
    )

    maker = app_session_factory(async_engine)

    # Pre-create two admin users in committed transactions so both
    # concurrent sessions have valid FK targets.
    admin_a_id = uuid4()
    admin_b_id = uuid4()
    for admin_id in (admin_a_id, admin_b_id):
        async with maker() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        INSERT INTO app_user
                          (id, username, display_name, password_hash,
                           password_salt, system_role, status,
                           must_change_password, created_at, updated_at)
                        VALUES
                          (:id, :un, 'Admin', 'hash', decode('00','hex'),
                           'ADMIN', 'ACTIVE', false, now(), now())
                        """
                    ),
                    {
                        "id": admin_id,
                        "un": f"cc-{admin_id.hex[:8]}",
                    },
                )

    async def ensure_in_session(admin_id: uuid4):
        async with maker() as session:
            async with session.begin():
                repo = ProfileRepository(session)
                profile = await repo.ensure_builtin_general(admin_id)
                return profile.id, profile.current_version, profile.code

    # Race two sessions — both start from no built-in row visible
    result_a, result_b = await asyncio.gather(
        ensure_in_session(admin_a_id),
        ensure_in_session(admin_b_id),
    )

    # Both must return the same row
    assert result_a[0] == result_b[0]  # same profile id
    assert result_a[1] == result_b[1] == 0  # current_version still 0
    assert result_a[2] == result_b[2] == "BUILTIN_GENERAL"


# ===================================================================
# Fix Round 2 — application factory round-trip (Finding 1)
# ===================================================================


@pytest.mark.asyncio
async def test_create_engine_and_session_factory_interfaces(
    async_engine: AsyncEngine,
) -> None:
    """Explicitly exercise ``create_engine(settings)`` and ``session_factory(engine)``.

    The async fixtures already use the application factories, so every
    async test implicitly validates the interface.  This test makes the
    exercise explicit: it imports the application functions and runs a
    complete insert→read→rollback through them.
    """
    from src.persistence.postgres.session import (
        create_engine as app_create_engine,
        session_factory as app_session_factory,
    )

    # create_engine's Settings argument is validated implicitly by the
    # async_engine fixture (which used it).  Here we exercise
    # session_factory against that engine directly.
    maker = app_session_factory(async_engine)
    uid = uuid4()
    async with maker() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO app_user
                      (id, username, display_name, password_hash,
                       password_salt, system_role, status,
                       must_change_password, created_at, updated_at)
                    VALUES
                      (:id, :un, 'Factory Test', 'hash', decode('fe','hex'),
                       'USER', 'ACTIVE', false, now(), now())
                    """
                ),
                {"id": uid, "un": f"factory-{uid.hex[:8]}"},
            )
            await session.flush()
            result = await session.execute(
                text("SELECT display_name FROM app_user WHERE id = :uid"),
                {"uid": uid},
            )
            assert result.scalar() == "Factory Test"
            await session.rollback()

    # Verify rollback actually happened
    async with maker() as session:
        async with session.begin():
            result = await session.execute(
                text("SELECT 1 FROM app_user WHERE id = :uid"),
                {"uid": uid},
            )
            assert result.scalar() is None


# ===================================================================
# Fix Round 2 — guard rejects empty database name (Finding 4)
# ===================================================================


def test_guard_rejects_url_without_database_name() -> None:
    """A URL with no explicit database name must fail the guard."""
    from tests.integration.postgres.conftest import _require_disposable_test_db

    with pytest.raises(pytest.fail.Exception):  # type: ignore[attr-defined]
        _require_disposable_test_db("postgresql://localhost/")

    with pytest.raises(pytest.fail.Exception):  # type: ignore[attr-defined]
        _require_disposable_test_db("postgresql+psycopg://host/")


def test_guard_rejects_wrong_database_name() -> None:
    """A URL targeting the wrong database must fail."""
    from tests.integration.postgres.conftest import _require_disposable_test_db

    with pytest.raises(pytest.fail.Exception):  # type: ignore[attr-defined]
        _require_disposable_test_db("postgresql://localhost/production_db")


def test_guard_accepts_correct_database_name() -> None:
    """The correct database name passes the guard."""
    from tests.integration.postgres.conftest import _require_disposable_test_db

    # Must not raise
    _require_disposable_test_db(
        "postgresql+psycopg://user:pass@localhost:5432/ai_case_v2_test"
    )


def test_guard_rejects_empty_url() -> None:
    """An empty URL must fail the guard."""
    from tests.integration.postgres.conftest import _require_disposable_test_db

    with pytest.raises(pytest.fail.Exception):  # type: ignore[attr-defined]
        _require_disposable_test_db("")
