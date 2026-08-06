"""Integration tests for migration 0002 — project and project_member tables.

Covers:
- DDL constraints (sync fixtures)
- Creation idempotency scoped to creator
- Creation conflict on request hash mismatch
- Member upsert (one row per project+user)
- Last-owner enforcement with row locking
- Repository transactional operations
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.modules.access.models import AppUser
from src.modules.profiles.models import DomainProfile
from src.modules.projects.repository import (
    CreationIdempotencyConflict,
    LastOwnerCannotBeRemoved,
    ProjectNotFound,
    ProjectRepository,
)


# ===================================================================
# Async fixtures
# ===================================================================


@pytest_asyncio.fixture
async def users(async_session: AsyncSession) -> SimpleNamespace:
    """Three test users: owner_a, owner_b, member."""
    now = datetime.now(UTC)
    ids = [uuid4() for _ in range(3)]
    displays = ["Owner A", "Owner B", "Member"]
    for uid, display in zip(ids, displays):
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
            {"id": uid, "un": f"proj-{uid.hex[:8]}", "dn": display, "now": now},
        )
    await async_session.flush()

    result = await async_session.execute(
        select(AppUser).where(AppUser.id.in_(ids))
    )
    users_list = list(result.scalars().all())
    user_map = {u.display_name: u for u in users_list}
    return SimpleNamespace(
        owner_a=user_map["Owner A"],
        owner_b=user_map["Owner B"],
        member=user_map["Member"],
    )


@pytest_asyncio.fixture
async def profile(
    async_session: AsyncSession, users: SimpleNamespace,
) -> DomainProfile:
    """A regular (non-builtin) domain profile for project binding.

    Uses a direct INSERT rather than ``ensure_builtin_general`` so the
    system-wide built-in row is never touched by project tests.
    """
    now = datetime.now(UTC)
    profile_id = uuid4()
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
            "id": profile_id,
            "code": f"proj-profile-{profile_id.hex[:8]}",
            "name": "Project Test Profile",
            "uid": users.owner_a.id,
            "now": now,
        },
    )
    await async_session.flush()

    result = await async_session.execute(
        select(DomainProfile).where(DomainProfile.id == profile_id)
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def project_repo(async_session: AsyncSession) -> ProjectRepository:
    """ProjectRepository bound to the test session."""
    return ProjectRepository(async_session)


@pytest_asyncio.fixture
async def project(
    async_session: AsyncSession,
    users: SimpleNamespace,
    profile: DomainProfile,
) -> "Project":
    """A pre-created project owned by owner_a."""
    from src.modules.projects.models import Project

    repo = ProjectRepository(async_session)
    return await repo.insert_project(
        users.owner_a.id, uuid4(), "hash-project-fixture", profile,
    )


# ===================================================================
# DDL constraint tests (sync)
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


def _insert_sync_profile(db: Session, user_id: str, code: str = "sync-prof") -> str:
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


# --- project CHECK constraints ---


def test_project_status_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project
                  (id, creation_idempotency_key, creation_request_hash,
                   name, status, truth, revision,
                   profile_id, profile_version, profile_hash,
                   profile_migration_status, artifact_counters,
                   default_branch, created_by_user_id, created_at, updated_at)
                VALUES
                  (:id, :key, :hash, 'Bad Project', 'DELETED', '{}'::jsonb, 0,
                   :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
                   'main', :uid, now(), now())
                """
            ),
            {
                "id": uuid4(),
                "key": uuid4(),
                "hash": "a" * 64,
                "pid": pid,
                "phash": "b" * 64,
                "uid": migrated_db_user,
            },
        )


def test_project_profile_migration_status_check(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project
                  (id, creation_idempotency_key, creation_request_hash,
                   name, status, truth, revision,
                   profile_id, profile_version, profile_hash,
                   profile_migration_status, artifact_counters,
                   default_branch, created_by_user_id, created_at, updated_at)
                VALUES
                  (:id, :key, :hash, 'Bad Mig', 'ACTIVE', '{}'::jsonb, 0,
                   :pid, 0, :phash, 'ROLLBACK', '{}'::jsonb,
                   'main', :uid, now(), now())
                """
            ),
            {
                "id": uuid4(),
                "key": uuid4(),
                "hash": "c" * 64,
                "pid": pid,
                "phash": "d" * 64,
                "uid": migrated_db_user,
            },
        )


# --- project unique constraints ---


def test_project_creation_key_unique_per_creator(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    key = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'First', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": uuid4(),
            "key": key,
            "hash": "e" * 64,
            "pid": pid,
            "phash": "f" * 64,
            "uid": migrated_db_user,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project
                  (id, creation_idempotency_key, creation_request_hash,
                   name, status, truth, revision,
                   profile_id, profile_version, profile_hash,
                   profile_migration_status, artifact_counters,
                   default_branch, created_by_user_id, created_at, updated_at)
                VALUES
                  (:id, :key, :hash, 'Second', 'ACTIVE', '{}'::jsonb, 0,
                   :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
                   'main', :uid, now(), now())
                """
            ),
            {
                "id": uuid4(),
                "key": key,
                "hash": "g" * 64,
                "pid": pid,
                "phash": "h" * 64,
                "uid": migrated_db_user,
            },
        )


def test_same_creation_key_different_creator_allowed(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Same key used by different creators must be allowed (key scoped to creator)."""
    user2 = _insert_sync_user(migrated_db, "second-creator")
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    _insert_sync_profile(migrated_db, user2, "sync-prof-2")
    key = uuid4()

    # First creator
    migrated_db.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'Creator 1', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": uuid4(), "key": key, "hash": "i" * 64,
            "pid": pid, "phash": "j" * 64, "uid": migrated_db_user,
        },
    )
    # Second creator, same key — must NOT raise
    migrated_db.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'Creator 2', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": uuid4(), "key": key, "hash": "k" * 64,
            "pid": pid, "phash": "l" * 64, "uid": user2,
        },
    )


def test_project_profile_fk_rejects_invalid_profile(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project
                  (id, creation_idempotency_key, creation_request_hash,
                   name, status, truth, revision,
                   profile_id, profile_version, profile_hash,
                   profile_migration_status, artifact_counters,
                   default_branch, created_by_user_id, created_at, updated_at)
                VALUES
                  (:id, :key, :hash, 'Bad FK', 'ACTIVE', '{}'::jsonb, 0,
                   :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
                   'main', :uid, now(), now())
                """
            ),
            {
                "id": uuid4(), "key": uuid4(), "hash": "m" * 64,
                "pid": uuid4(), "phash": "n" * 64, "uid": migrated_db_user,
            },
        )


def test_project_gitlab_project_id_unique_nullable(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Multiple NULL gitlab_project_id values are allowed (nullable UNIQUE)."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    # Two projects with NULL gitlab_project_id — both OK
    for _ in range(2):
        migrated_db.execute(
            text(
                """
                INSERT INTO project
                  (id, creation_idempotency_key, creation_request_hash,
                   name, status, truth, revision,
                   profile_id, profile_version, profile_hash,
                   profile_migration_status, artifact_counters,
                   default_branch, created_by_user_id, created_at, updated_at)
                VALUES
                  (:id, :key, :hash, 'GitLab NULL', 'ACTIVE', '{}'::jsonb, 0,
                   :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
                   'main', :uid, now(), now())
                """
            ),
            {
                "id": uuid4(), "key": uuid4(), "hash": f"gl-{uuid4().hex[:56]}",
                "pid": pid, "phash": f"glp-{uuid4().hex[:56]}", "uid": migrated_db_user,
            },
        )


def test_project_gitlab_project_id_unique_non_null(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    """Duplicate non-NULL gitlab_project_id must be rejected."""
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    gl_id = 12345
    migrated_db.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               gitlab_project_id, default_branch,
               created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'GL 1', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               :glid, 'main', :uid, now(), now())
            """
        ),
        {
            "id": uuid4(), "key": uuid4(), "hash": "o" * 64,
            "pid": pid, "phash": "p" * 64, "glid": gl_id, "uid": migrated_db_user,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project
                  (id, creation_idempotency_key, creation_request_hash,
                   name, status, truth, revision,
                   profile_id, profile_version, profile_hash,
                   profile_migration_status, artifact_counters,
                   gitlab_project_id, default_branch,
                   created_by_user_id, created_at, updated_at)
                VALUES
                  (:id, :key, :hash, 'GL 2', 'ACTIVE', '{}'::jsonb, 0,
                   :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
                   :glid, 'main', :uid, now(), now())
                """
            ),
            {
                "id": uuid4(), "key": uuid4(), "hash": "q" * 64,
                "pid": pid, "phash": "r" * 64, "glid": gl_id, "uid": migrated_db_user,
            },
        )


# --- project_member CHECK constraints ---


def test_project_member_role_check_rejects_bad_value(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'Role Test', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": proj_id, "key": uuid4(), "hash": "s" * 64,
            "pid": pid, "phash": "t" * 64, "uid": migrated_db_user,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_member
                  (id, project_id, user_id, role,
                   created_by_user_id, created_at, updated_at)
                VALUES (:id, :pid, :uid, 'ADMIN', :cuid, now(), now())
                """
            ),
            {
                "id": uuid4(), "pid": str(proj_id),
                "uid": migrated_db_user, "cuid": migrated_db_user,
            },
        )


def test_project_member_unique_project_user(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    pid = _insert_sync_profile(migrated_db, migrated_db_user)
    proj_id = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO project
              (id, creation_idempotency_key, creation_request_hash,
               name, status, truth, revision,
               profile_id, profile_version, profile_hash,
               profile_migration_status, artifact_counters,
               default_branch, created_by_user_id, created_at, updated_at)
            VALUES
              (:id, :key, :hash, 'Member Unique', 'ACTIVE', '{}'::jsonb, 0,
               :pid, 0, :phash, 'CURRENT', '{}'::jsonb,
               'main', :uid, now(), now())
            """
        ),
        {
            "id": proj_id, "key": uuid4(), "hash": "u" * 64,
            "pid": pid, "phash": "v" * 64, "uid": migrated_db_user,
        },
    )
    migrated_db.execute(
        text(
            """
            INSERT INTO project_member
              (id, project_id, user_id, role,
               created_by_user_id, created_at, updated_at)
            VALUES (:id, :pid, :uid, 'OWNER', :cuid, now(), now())
            """
        ),
        {
            "id": uuid4(), "pid": str(proj_id),
            "uid": migrated_db_user, "cuid": migrated_db_user,
        },
    )
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_member
                  (id, project_id, user_id, role,
                   created_by_user_id, created_at, updated_at)
                VALUES (:id, :pid, :uid, 'VIEWER', :cuid, now(), now())
                """
            ),
            {
                "id": uuid4(), "pid": str(proj_id),
                "uid": migrated_db_user, "cuid": migrated_db_user,
            },
        )


def test_project_member_project_fk_rejects_invalid_project(
    migrated_db: Session, migrated_db_user: str,
) -> None:
    with pytest.raises(IntegrityError):
        migrated_db.execute(
            text(
                """
                INSERT INTO project_member
                  (id, project_id, user_id, role,
                   created_by_user_id, created_at, updated_at)
                VALUES (:id, :pid, :uid, 'VIEWER', :cuid, now(), now())
                """
            ),
            {
                "id": uuid4(), "pid": str(uuid4()),
                "uid": migrated_db_user, "cuid": migrated_db_user,
            },
        )


# ===================================================================
# Creation idempotency and scoping (async)
# ===================================================================


@pytest.mark.asyncio
async def test_project_creation_key_is_scoped_to_creator(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
    profile: DomainProfile,
) -> None:
    """Same creation key from different creators produces different projects."""
    key = uuid4()
    first = await project_repo.insert_project(
        users.owner_a.id, key, "hash-scope-a", profile,
    )
    same_other_user = await project_repo.insert_project(
        users.owner_b.id, key, "hash-scope-b", profile,
    )
    assert first.id != same_other_user.id


@pytest.mark.asyncio
async def test_project_insert_is_idempotent_same_hash(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
    profile: DomainProfile,
) -> None:
    """Same creator, same key, same hash returns the existing project."""
    key = uuid4()
    first = await project_repo.insert_project(
        users.owner_a.id, key, "hash-idem", profile,
    )
    second = await project_repo.insert_project(
        users.owner_a.id, key, "hash-idem", profile,
    )
    assert first.id == second.id
    assert first.name == second.name


@pytest.mark.asyncio
async def test_project_insert_conflict_on_hash_mismatch(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
    profile: DomainProfile,
) -> None:
    """Same creator, same key, but different hash raises conflict."""
    key = uuid4()
    await project_repo.insert_project(
        users.owner_a.id, key, "hash-one", profile,
    )
    with pytest.raises(CreationIdempotencyConflict):
        await project_repo.insert_project(
            users.owner_a.id, key, "hash-two", profile,
        )


# ===================================================================
# Member management (async)
# ===================================================================


@pytest.mark.asyncio
async def test_project_has_exactly_one_row_per_member(
    project_repo: ProjectRepository,
    project: "Project",
    users: SimpleNamespace,
) -> None:
    """put_member upserts: calling twice with different roles yields one row."""
    await project_repo.put_member(
        project.id, users.member.id, "MEMBER", users.owner_a.id,
    )
    await project_repo.put_member(
        project.id, users.member.id, "VIEWER", users.owner_a.id,
    )
    assert await project_repo.member_count(project.id, users.member.id) == 1


@pytest.mark.asyncio
async def test_put_member_updates_role(
    project_repo: ProjectRepository,
    project: "Project",
    users: SimpleNamespace,
) -> None:
    """Upserting with a new role updates the existing row."""
    await project_repo.put_member(
        project.id, users.member.id, "MEMBER", users.owner_a.id,
    )
    await project_repo.put_member(
        project.id, users.member.id, "VIEWER", users.owner_a.id,
    )
    from src.modules.projects.models import ProjectMember
    result = await project_repo._session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == users.member.id,
        )
    )
    row = result.scalar_one()
    assert row.role == "VIEWER"


# ===================================================================
# Last-owner enforcement (async)
# ===================================================================


@pytest.mark.asyncio
async def test_delete_last_owner_raises(
    project_repo: ProjectRepository,
    project: "Project",
    users: SimpleNamespace,
) -> None:
    """Deleting the sole OWNER must raise LastOwnerCannotBeRemoved."""
    # The project fixture creates the project with owner_a as creator.
    # We need owner_a to be an OWNER member first.
    await project_repo.put_member(
        project.id, users.owner_a.id, "OWNER", users.owner_a.id,
    )
    with pytest.raises(LastOwnerCannotBeRemoved):
        await project_repo.delete_member(project.id, users.owner_a.id)


@pytest.mark.asyncio
async def test_delete_member_succeeds_with_multiple_owners(
    project_repo: ProjectRepository,
    project: "Project",
    users: SimpleNamespace,
) -> None:
    """Deleting one OWNER when another OWNER exists succeeds."""
    await project_repo.put_member(
        project.id, users.owner_a.id, "OWNER", users.owner_a.id,
    )
    await project_repo.put_member(
        project.id, users.owner_b.id, "OWNER", users.owner_a.id,
    )
    # Should not raise
    await project_repo.delete_member(project.id, users.owner_b.id)
    # owner_a still exists as OWNER
    count = await project_repo.member_count(project.id, users.owner_a.id)
    assert count == 1


@pytest.mark.asyncio
async def test_delete_nonexistent_member_returns_silently(
    project_repo: ProjectRepository,
    project: "Project",
    users: SimpleNamespace,
) -> None:
    """Deleting a member that doesn't exist is a no-op."""
    await project_repo.delete_member(project.id, users.member.id)


# ===================================================================
# get_project_for_update (async)
# ===================================================================


@pytest.mark.asyncio
async def test_get_project_for_update_returns_project(
    project_repo: ProjectRepository,
    project: "Project",
) -> None:
    """get_project_for_update returns the project with a row lock."""
    locked = await project_repo.get_project_for_update(project.id)
    assert locked.id == project.id
    assert locked.name == project.name


@pytest.mark.asyncio
async def test_get_project_for_update_raises_on_missing(
    project_repo: ProjectRepository,
) -> None:
    """get_project_for_update raises ProjectNotFound for missing project."""
    with pytest.raises(ProjectNotFound):
        await project_repo.get_project_for_update(uuid4())


# ===================================================================
# find_by_creation_key (async)
# ===================================================================


@pytest.mark.asyncio
async def test_find_by_creation_key_returns_project(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
    profile: DomainProfile,
) -> None:
    """find_by_creation_key locates project by creator + key."""
    key = uuid4()
    created = await project_repo.insert_project(
        users.owner_a.id, key, "hash-find", profile,
    )
    found = await project_repo.find_by_creation_key(users.owner_a.id, key)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_find_by_creation_key_returns_none_for_unknown(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
) -> None:
    """find_by_creation_key returns None when no match."""
    found = await project_repo.find_by_creation_key(users.owner_a.id, uuid4())
    assert found is None
