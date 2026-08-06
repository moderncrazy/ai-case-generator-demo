"""Integration tests for migration 0002 — project and project_member tables.

Covers:
- DDL constraints (sync fixtures)
- Creation idempotency scoped to creator with atomic insert-or-replay
- Atomic creator OWNER membership on project creation
- Published profile content-hash binding
- Concurrent independent-session creation races
- Member upsert with project-lock serialisation
- Sole-owner downgrade rejection
- Last-owner enforcement with project-row locking
- Concurrent owner-removal serialisation
- Upsert return of fresh persisted state (populate_existing)
"""

import asyncio
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from src.modules.access.models import AppUser
from src.modules.profiles.models import DomainProfile
from src.modules.projects.models import Project, ProjectMember
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
    """A regular domain profile with a published version for project binding.

    Uses a direct INSERT rather than ``ensure_builtin_general`` so the
    system-wide built-in row is never touched by project tests.

    A published ``domain_profile_version`` row is included so that
    ``insert_project`` can resolve the actual ``content_hash``.
    """
    now = datetime.now(UTC)
    profile_id = uuid4()
    content_bytes = f"project-test-profile-{profile_id.hex}".encode()
    content_hash_val = hashlib.sha256(content_bytes).hexdigest()

    await async_session.execute(
        text(
            """
            INSERT INTO domain_profile
              (id, code, name, status, is_builtin_general,
               current_version, created_by_user_id, created_at, updated_at)
            VALUES (:id, :code, :name, 'ACTIVE', false,
                    1, :uid, :now, :now)
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
    await async_session.execute(
        text(
            """
            INSERT INTO domain_profile_version
              (id, profile_id, version, content, content_hash,
               validation_result, published_by_user_id, published_at)
            VALUES (:id, :pid, 1, '{}'::jsonb, :hash,
                    '{}'::jsonb, :uid, :now)
            """
        ),
        {
            "id": uuid4(),
            "pid": profile_id,
            "hash": content_hash_val,
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
async def unpublished_profile(
    async_session: AsyncSession, users: SimpleNamespace,
) -> DomainProfile:
    """A profile with ``current_version = 0`` — no published version yet."""
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
            "code": f"unpub-{profile_id.hex[:8]}",
            "name": "Unpublished Profile",
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
) -> Project:
    """A pre-created project owned by owner_a (owner created atomically)."""
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
# Atomic creator OWNER membership (Finding 2)
# ===================================================================


@pytest.mark.asyncio
async def test_insert_project_creates_creator_owner_membership(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
    profile: DomainProfile,
) -> None:
    """After insert_project the creator is automatically an OWNER member."""
    project = await project_repo.insert_project(
        users.owner_a.id, uuid4(), "hash-creator-owner", profile,
    )
    count = await project_repo.member_count(project.id, users.owner_a.id)
    assert count == 1

    # Verify the role is OWNER (not MEMBER or VIEWER)
    from sqlalchemy import select as sa_select
    result = await project_repo._session.execute(
        sa_select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == users.owner_a.id,
        )
    )
    member = result.scalar_one()
    assert member.role == "OWNER"


# ===================================================================
# Published profile content-hash binding (Finding 4)
# ===================================================================


@pytest.mark.asyncio
async def test_profile_hash_matches_published_content_hash(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
    profile: DomainProfile,
) -> None:
    """The stored profile_hash equals the published version's content_hash."""
    project = await project_repo.insert_project(
        users.owner_a.id, uuid4(), "hash-profile-binding", profile,
    )
    # Query the version row to get the expected content_hash
    from src.modules.profiles.models import DomainProfileVersion
    result = await project_repo._session.execute(
        select(DomainProfileVersion.content_hash).where(
            DomainProfileVersion.profile_id == profile.id,
            DomainProfileVersion.version == profile.current_version,
        )
    )
    expected_hash = result.scalar_one()
    assert project.profile_hash == expected_hash
    assert len(project.profile_hash) == 64


@pytest.mark.asyncio
async def test_insert_project_rejects_unpublished_profile(
    project_repo: ProjectRepository,
    users: SimpleNamespace,
    unpublished_profile: DomainProfile,
) -> None:
    """A profile with current_version=0 (no published version) is rejected."""
    with pytest.raises(ValueError, match="no published version"):
        await project_repo.insert_project(
            users.owner_a.id, uuid4(), "hash-unpub", unpublished_profile,
        )


# ===================================================================
# Independent-session creation race (Finding 1 / Finding 5)
# ===================================================================


@pytest.mark.asyncio
async def test_insert_project_concurrent_sessions_same_hash(
    async_engine: AsyncEngine,
    sync_engine,
) -> None:
    """Two independent sessions racing to insert with the same key+hash:
    both get the same project (atomic insert-or-replay)."""
    from src.persistence.postgres.session import session_factory as sf

    now = datetime.now(UTC)
    uid = uuid4()
    pid = uuid4()
    ver_id = uuid4()
    key = uuid4()
    content_hash_val = hashlib.sha256(b"concurrent-race").hexdigest()
    req_hash = "hash-concurrent-same"

    # Setup committed shared data via sync engine
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO app_user
                  (id, username, display_name, password_hash, password_salt,
                   system_role, status, must_change_password, created_at, updated_at)
                VALUES (:id, :un, :dn, 'hash', decode('aa','hex'),
                        'USER', 'ACTIVE', false, :now, :now)
                """
            ),
            {"id": uid, "un": f"cr-u-{uid.hex[:8]}", "dn": "CR User", "now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO domain_profile
                  (id, code, name, status, is_builtin_general,
                   current_version, created_by_user_id, created_at, updated_at)
                VALUES (:id, :code, :name, 'ACTIVE', false,
                        1, :uid, :now, :now)
                """
            ),
            {"id": pid, "code": f"cr-prof-{pid.hex[:8]}", "name": "CR Profile",
             "uid": uid, "now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO domain_profile_version
                  (id, profile_id, version, content, content_hash,
                   validation_result, published_by_user_id, published_at)
                VALUES (:id, :pid, 1, '{}'::jsonb, :hash,
                        '{}'::jsonb, :uid, :now)
                """
            ),
            {"id": ver_id, "pid": pid, "hash": content_hash_val, "uid": uid, "now": now},
        )

    maker = sf(async_engine)

    # Session A: insert and commit so the row is visible to other sessions
    async with maker() as session_a:
        repo_a = ProjectRepository(session_a)
        ra = await session_a.execute(
            select(DomainProfile).where(DomainProfile.id == pid)
        )
        pa = ra.scalar_one()
        proj_a = await repo_a.insert_project(uid, key, req_hash, pa)
        await session_a.commit()

    # Session B: same key + hash → idempotent replay, same project ID
    async with maker() as session_b:
        repo_b = ProjectRepository(session_b)
        rb = await session_b.execute(
            select(DomainProfile).where(DomainProfile.id == pid)
        )
        pb = rb.scalar_one()
        proj_b = await repo_b.insert_project(uid, key, req_hash, pb)
        assert proj_b.id == proj_a.id, (
            f"Independent session must return the same project on replay: "
            f"{proj_b.id} != {proj_a.id}"
        )
        await session_b.rollback()


@pytest.mark.asyncio
async def test_insert_project_concurrent_sessions_different_hash(
    async_engine: AsyncEngine,
    sync_engine,
) -> None:
    """Independent session gets CreationIdempotencyConflict when hash differs."""
    from src.persistence.postgres.session import session_factory as sf

    now = datetime.now(UTC)
    uid = uuid4()
    pid = uuid4()
    ver_id = uuid4()
    key = uuid4()
    content_hash_val = hashlib.sha256(b"concurrent-conflict").hexdigest()

    with sync_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO app_user
                  (id, username, display_name, password_hash, password_salt,
                   system_role, status, must_change_password, created_at, updated_at)
                VALUES (:id, :un, :dn, 'hash', decode('aa','hex'),
                        'USER', 'ACTIVE', false, :now, :now)
                """
            ),
            {"id": uid, "un": f"cc-u-{uid.hex[:8]}", "dn": "CC User", "now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO domain_profile
                  (id, code, name, status, is_builtin_general,
                   current_version, created_by_user_id, created_at, updated_at)
                VALUES (:id, :code, :name, 'ACTIVE', false,
                        1, :uid, :now, :now)
                """
            ),
            {"id": pid, "code": f"cc-prof-{pid.hex[:8]}", "name": "CC Profile",
             "uid": uid, "now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO domain_profile_version
                  (id, profile_id, version, content, content_hash,
                   validation_result, published_by_user_id, published_at)
                VALUES (:id, :pid, 1, '{}'::jsonb, :hash,
                        '{}'::jsonb, :uid, :now)
                """
            ),
            {"id": ver_id, "pid": pid, "hash": content_hash_val, "uid": uid, "now": now},
        )

    maker = sf(async_engine)

    # Session A creates the project with hash-A
    async with maker() as session_a:
        async with session_a.begin():
            repo_a = ProjectRepository(session_a)
            ra = await session_a.execute(
                select(DomainProfile).where(DomainProfile.id == pid)
            )
            pa = ra.scalar_one()
            await repo_a.insert_project(uid, key, "hash-alpha", pa)
            await session_a.commit()

    # Session B tries with same key but hash-B → conflict
    async with maker() as session_b:
        async with session_b.begin():
            repo_b = ProjectRepository(session_b)
            rb = await session_b.execute(
                select(DomainProfile).where(DomainProfile.id == pid)
            )
            pb = rb.scalar_one()
            with pytest.raises(CreationIdempotencyConflict):
                await repo_b.insert_project(uid, key, "hash-beta", pb)
            await session_b.rollback()


# ===================================================================
# Member management (async)
# ===================================================================


@pytest.mark.asyncio
async def test_project_has_exactly_one_row_per_member(
    project_repo: ProjectRepository,
    project: Project,
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
    project: Project,
    users: SimpleNamespace,
) -> None:
    """Upserting with a new role updates the existing row."""
    await project_repo.put_member(
        project.id, users.member.id, "MEMBER", users.owner_a.id,
    )
    await project_repo.put_member(
        project.id, users.member.id, "VIEWER", users.owner_a.id,
    )
    result = await project_repo._session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == users.member.id,
        )
    )
    row = result.scalar_one()
    assert row.role == "VIEWER"


# ===================================================================
# Upsert returns fresh state — populate_existing (Finding 6)
# ===================================================================


@pytest.mark.asyncio
async def test_put_member_returns_fresh_state_after_upsert(
    project_repo: ProjectRepository,
    project: Project,
    users: SimpleNamespace,
) -> None:
    """Calling put_member twice returns the updated role (no stale identity map)."""
    m1 = await project_repo.put_member(
        project.id, users.member.id, "MEMBER", users.owner_a.id,
    )
    assert m1.role == "MEMBER"

    # Second call updates the same row.  The returned object must reflect
    # the new role, not the cached state from m1.
    m2 = await project_repo.put_member(
        project.id, users.member.id, "VIEWER", users.owner_a.id,
    )
    assert m2.role == "VIEWER"
    # Verify m2 is a distinct instance with updated data
    assert m2.id == m1.id
    assert m2.updated_at >= m1.updated_at


# ===================================================================
# Last-owner enforcement (async)
# ===================================================================


@pytest.mark.asyncio
async def test_delete_last_owner_raises(
    project_repo: ProjectRepository,
    project: Project,
    users: SimpleNamespace,
) -> None:
    """Deleting the sole OWNER must raise LastOwnerCannotBeRemoved."""
    # project fixture already creates owner_a as OWNER via insert_project.
    # Deleting that sole OWNER must be rejected.
    with pytest.raises(LastOwnerCannotBeRemoved):
        await project_repo.delete_member(project.id, users.owner_a.id)


@pytest.mark.asyncio
async def test_delete_member_succeeds_with_multiple_owners(
    project_repo: ProjectRepository,
    project: Project,
    users: SimpleNamespace,
) -> None:
    """Deleting one OWNER when another OWNER exists succeeds."""
    # project fixture already has owner_a as OWNER.  Add owner_b as OWNER.
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
    project: Project,
    users: SimpleNamespace,
) -> None:
    """Deleting a member that doesn't exist is a no-op."""
    await project_repo.delete_member(project.id, users.member.id)


# ===================================================================
# Sole-owner downgrade rejection (Finding 3)
# ===================================================================


@pytest.mark.asyncio
async def test_put_member_rejects_sole_owner_downgrade(
    project_repo: ProjectRepository,
    project: Project,
    users: SimpleNamespace,
) -> None:
    """Cannot downgrade the only OWNER to a non-OWNER role."""
    # project fixture creates owner_a as the sole OWNER
    with pytest.raises(LastOwnerCannotBeRemoved, match="downgrade"):
        await project_repo.put_member(
            project.id, users.owner_a.id, "MEMBER", users.owner_a.id,
        )


@pytest.mark.asyncio
async def test_put_member_allows_downgrade_with_other_owner(
    project_repo: ProjectRepository,
    project: Project,
    users: SimpleNamespace,
) -> None:
    """Downgrading one OWNER to MEMBER succeeds when another OWNER exists."""
    # project fixture already has owner_a as OWNER.  Add owner_b as OWNER.
    await project_repo.put_member(
        project.id, users.owner_b.id, "OWNER", users.owner_a.id,
    )
    # Now downgrade owner_a — should succeed
    updated = await project_repo.put_member(
        project.id, users.owner_a.id, "MEMBER", users.owner_a.id,
    )
    assert updated.role == "MEMBER"
    # owner_b is still OWNER
    result = await project_repo._session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == users.owner_b.id,
        )
    )
    assert result.scalar_one().role == "OWNER"


# ===================================================================
# Concurrent owner removal serialisation (Finding 3 / Finding 5)
# ===================================================================


@pytest.mark.asyncio
async def test_concurrent_owner_removal_prevents_empty_owners(
    async_engine: AsyncEngine,
    sync_engine,
) -> None:
    """Two sessions concurrently deleting the last two OWNERs:
    only one removal succeeds; the other is blocked by last-owner guard."""
    from src.persistence.postgres.session import session_factory as sf

    now = datetime.now(UTC)
    uid_a = uuid4()
    uid_b = uuid4()
    pid = uuid4()
    proj_id = uuid4()
    content_hash_val = hashlib.sha256(b"owner-race").hexdigest()

    with sync_engine.begin() as conn:
        for uid, uname in [(uid_a, "OwnerA"), (uid_b, "OwnerB")]:
            conn.execute(
                text(
                    """
                    INSERT INTO app_user
                      (id, username, display_name, password_hash, password_salt,
                       system_role, status, must_change_password, created_at, updated_at)
                    VALUES (:id, :un, :dn, 'hash', decode('aa','hex'),
                            'USER', 'ACTIVE', false, :now, :now)
                    """
                ),
                {"id": uid, "un": f"or-{uid.hex[:8]}", "dn": uname, "now": now},
            )
        conn.execute(
            text(
                """
                INSERT INTO domain_profile
                  (id, code, name, status, is_builtin_general,
                   current_version, created_by_user_id, created_at, updated_at)
                VALUES (:id, :code, :name, 'ACTIVE', false,
                        1, :uid, :now, :now)
                """
            ),
            {"id": pid, "code": f"or-prof-{pid.hex[:8]}", "name": "OR Profile",
             "uid": uid_a, "now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO domain_profile_version
                  (id, profile_id, version, content, content_hash,
                   validation_result, published_by_user_id, published_at)
                VALUES (:id, :pid, 1, '{}'::jsonb, :hash,
                        '{}'::jsonb, :uid, :now)
                """
            ),
            {"id": uuid4(), "pid": pid, "hash": content_hash_val, "uid": uid_a, "now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO project
                  (id, creation_idempotency_key, creation_request_hash,
                   name, status, truth, revision,
                   profile_id, profile_version, profile_hash,
                   profile_migration_status, artifact_counters,
                   default_branch, created_by_user_id, created_at, updated_at)
                VALUES (:id, :key, :hash, 'Owner Race', 'ACTIVE', '{}'::jsonb, 0,
                        :pid, 1, :phash, 'CURRENT', '{}'::jsonb,
                        'main', :uid, :now, :now)
                """
            ),
            {"id": proj_id, "key": uuid4(), "hash": "c" * 64,
             "pid": pid, "phash": content_hash_val, "uid": uid_a, "now": now},
        )
        # Two OWNER members
        for uid in [uid_a, uid_b]:
            conn.execute(
                text(
                    """
                    INSERT INTO project_member
                      (id, project_id, user_id, role,
                       created_by_user_id, created_at, updated_at)
                    VALUES (:id, :pid, :uid, 'OWNER', :cuid, :now, :now)
                    """
                ),
                {"id": uuid4(), "pid": proj_id, "uid": uid, "cuid": uid_a, "now": now},
            )

    maker = sf(async_engine)
    results: list[str] = []

    async def remove_owner(to_remove, label: str) -> None:
        async with maker() as session:
            repo = ProjectRepository(session)
            try:
                await repo.delete_member(proj_id, to_remove)
                await session.commit()
                results.append(f"{label}_removed")
            except LastOwnerCannotBeRemoved:
                await session.rollback()
                results.append(f"{label}_blocked")
            except Exception:
                await session.rollback()
                raise

    # Concurrently remove both owners — only one should succeed
    await asyncio.gather(
        remove_owner(uid_a, "a"),
        remove_owner(uid_b, "b"),
    )

    assert len(results) == 2
    assert "removed" in results[0] or "removed" in results[1]
    assert "blocked" in results[0] or "blocked" in results[1]
    # The project-row lock ensures exactly one removal succeeded
    removed_count = sum(1 for r in results if r.endswith("removed"))
    blocked_count = sum(1 for r in results if r.endswith("blocked"))
    assert removed_count == 1, f"Expected 1 removal, got {results}"
    assert blocked_count == 1, f"Expected 1 blocked, got {results}"


# ===================================================================
# get_project_for_update (async)
# ===================================================================


@pytest.mark.asyncio
async def test_get_project_for_update_returns_project(
    project_repo: ProjectRepository,
    project: Project,
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
