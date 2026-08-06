"""Transactional project repository with domain-invariant enforcement.

Provides creation idempotency scoped to creator, member management with
last-owner enforcement, and row-locked project access for mutating
operations.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.delivery.models import ProjectStage
from src.modules.profiles.models import DomainProfile, DomainProfileVersion
from src.modules.projects.models import Project, ProjectMember


# The nine approved project stages created atomically at project creation
# (matches ``ck_project_stage_stage``).
PROJECT_STAGE_CODES = [
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


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class ProjectDomainError(Exception):
    """Base exception for Project domain rule violations."""


class CreationIdempotencyConflict(ProjectDomainError):
    """A project with the same creation key but a different request hash exists."""


class ProjectNotFound(ProjectDomainError):
    """The requested Project does not exist."""


class LastOwnerCannotBeRemoved(ProjectDomainError):
    """Cannot delete or downgrade the last OWNER of a project."""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class ProjectRepository:
    """Transactional operations on the Project domain tables.

    Every mutation method receives an ``AsyncSession`` that the caller
    manages (begin, commit, rollback).  The repository does not manage
    transaction boundaries itself.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    async def _resolve_profile_hash(
        self,
        profile: DomainProfile,
    ) -> tuple[int, str]:
        """Return ``(version, content_hash)`` from the current published version.

        Resolves the profile's current version from the database inside the
        transaction — the caller-supplied ``profile.current_version`` is
        ignored to prevent binding a stale/outdated version.

        Rejects profiles that have no published version
        (``current_version == 0``) or whose published version row is missing.
        """
        # Resolve current version from the database, not the caller object
        current_stmt = select(DomainProfile.current_version).where(
            DomainProfile.id == profile.id,
        )
        current_result = await self._session.execute(current_stmt)
        current_version: int | None = current_result.scalar_one_or_none()
        if current_version is None:
            raise ValueError(f"Profile {profile.id} not found")
        if current_version == 0:
            raise ValueError(
                f"Profile {profile.id} has no published version "
                f"(current_version is 0)"
            )

        stmt = select(DomainProfileVersion.content_hash).where(
            DomainProfileVersion.profile_id == profile.id,
            DomainProfileVersion.version == current_version,
        )
        result = await self._session.execute(stmt)
        content_hash: str | None = result.scalar_one_or_none()
        if content_hash is None:
            raise ValueError(
                f"Published version {current_version} for profile "
                f"{profile.id} not found in domain_profile_version"
            )
        return current_version, content_hash

    # ------------------------------------------------------------------
    # project access
    # ------------------------------------------------------------------

    async def get_project_for_update(self, project_id: uuid.UUID) -> Project:
        """Return the project with a ``FOR UPDATE`` row lock.

        Raises ``ProjectNotFound`` if no project matches ``project_id``.
        """
        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ProjectNotFound(f"Project {project_id} not found")
        return row

    async def find_by_creation_key(
        self,
        created_by_user_id: uuid.UUID,
        creation_idempotency_key: uuid.UUID,
    ) -> Project | None:
        """Return the project matching the creator + idempotency key, or None."""
        stmt = select(Project).where(
            Project.created_by_user_id == created_by_user_id,
            Project.creation_idempotency_key == creation_idempotency_key,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # creation idempotency
    # ------------------------------------------------------------------

    async def insert_project(
        self,
        created_by_user_id: uuid.UUID,
        creation_idempotency_key: uuid.UUID,
        creation_request_hash: str,
        profile: DomainProfile,
        name: str = "New Project",
    ) -> Project:
        """Idempotently insert a project scoped to the creating user.

        * Same creator, same key, same request hash → returns the existing
          project (idempotent replay).
        * Same creator, same key, different request hash → raises
          ``CreationIdempotencyConflict``.
        * Different creator, same key → a new project (key scoped to creator).

        The stored ``profile_hash`` is the actual ``content_hash`` from the
        published ``domain_profile_version`` row, resolved transactionally.

        Creator membership is inserted atomically — after a successful
        insert the project always has at least one OWNER.
        """
        # Resolve the published profile version's content hash
        profile_version, profile_hash = await self._resolve_profile_hash(profile)

        now = datetime.now(UTC)
        project_id = uuid.uuid4()

        # Atomic INSERT … ON CONFLICT DO NOTHING — no check-then-act window
        insert_stmt = (
            pg_insert(Project)
            .values(
                id=project_id,
                creation_idempotency_key=creation_idempotency_key,
                creation_request_hash=creation_request_hash,
                name=name,
                status="ACTIVE",
                revision=0,
                profile_id=profile.id,
                profile_version=profile_version,
                profile_hash=profile_hash,
                profile_migration_status="CURRENT",
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "created_by_user_id",
                    "creation_idempotency_key",
                ]
            )
            .returning(Project.id)
        )
        result = await self._session.execute(insert_stmt)
        inserted_id: uuid.UUID | None = result.scalar_one_or_none()

        if inserted_id is not None:
            # Insert succeeded — create the creator OWNER membership and the
            # nine mandatory stage rows atomically in the same transaction.
            member_stmt = pg_insert(ProjectMember).values(
                id=uuid.uuid4(),
                project_id=inserted_id,
                user_id=created_by_user_id,
                role="OWNER",
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            await self._session.execute(member_stmt)
            for stage in PROJECT_STAGE_CODES:
                stage_stmt = pg_insert(ProjectStage).values(
                    id=uuid.uuid4(),
                    project_id=inserted_id,
                    stage=stage,
                    status="NOT_STARTED",
                    revision=0,
                    baseline_version=0,
                    publish_attempts=0,
                    created_at=now,
                    updated_at=now,
                )
                await self._session.execute(stage_stmt)
            await self._session.flush()

            # Re-fetch to return a fully-populated ORM instance
            project = await self._session.get(Project, inserted_id)
            if project is None:  # pragma: no cover — defensive
                raise ProjectNotFound(
                    f"Project {inserted_id} disappeared after insert"
                )
            return project

        # Conflict — row already exists.  Compare hashes.
        existing = await self.find_by_creation_key(
            created_by_user_id, creation_idempotency_key
        )
        if (
            existing is not None
            and existing.creation_request_hash == creation_request_hash
        ):
            return existing

        raise CreationIdempotencyConflict(
            f"Creation key {creation_idempotency_key} already used by "
            f"user {created_by_user_id} with a different request hash"
        )

    # ------------------------------------------------------------------
    # member management
    # ------------------------------------------------------------------

    async def put_member(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        created_by_user_id: uuid.UUID,
    ) -> ProjectMember:
        """Upsert a project member.

        One row per ``(project_id, user_id)`` — calling with a different
        role updates the existing row in-place.

        All membership mutations are serialized on a shared project-row
        lock so that last-owner guards cannot be bypassed by concurrent
        sessions.
        """
        # Serialize all membership mutations on the project row
        await self.get_project_for_update(project_id)

        # Guard: downgrading the sole OWNER is forbidden
        if role != "OWNER":
            existing_stmt = select(ProjectMember.role).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
            existing_result = await self._session.execute(existing_stmt)
            existing_role: str | None = existing_result.scalar_one_or_none()
            if existing_role == "OWNER":
                other_stmt = (
                    select(ProjectMember.id)
                    .where(
                        ProjectMember.project_id == project_id,
                        ProjectMember.role == "OWNER",
                        ProjectMember.user_id != user_id,
                    )
                    .limit(1)
                )
                other_result = await self._session.execute(other_stmt)
                if other_result.scalar_one_or_none() is None:
                    raise LastOwnerCannotBeRemoved(
                        f"Cannot downgrade user {user_id}: they are the "
                        f"last OWNER of project {project_id}"
                    )

        now = datetime.now(UTC)
        upsert_stmt = (
            pg_insert(ProjectMember)
            .values(
                id=uuid.uuid4(),
                project_id=project_id,
                user_id=user_id,
                role=role,
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["project_id", "user_id"],
                set_={
                    "role": pg_insert(ProjectMember).excluded.role,
                    "updated_at": pg_insert(ProjectMember).excluded.updated_at,
                },
            )
        )
        await self._session.execute(upsert_stmt)
        await self._session.flush()

        # Return current persisted state, bypassing the identity map
        result = await self._session.execute(
            select(ProjectMember)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def delete_member(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete a project member with last-owner enforcement.

        Raises ``LastOwnerCannotBeRemoved`` when the target is the sole
        OWNER of the project.

        A shared project-row lock serializes all membership mutations so
        that concurrent owner deletions cannot bypass the last-owner guard.
        """
        # Serialize all membership mutations on the project row
        await self.get_project_for_update(project_id)

        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        member = result.scalar_one_or_none()

        if member is None:
            return  # idempotent no-op

        if member.role == "OWNER":
            # Check any other OWNER exists (we hold the project lock;
            # no concurrent membership changes can happen under this project)
            count_stmt = (
                select(ProjectMember.id)
                .where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.role == "OWNER",
                    ProjectMember.user_id != user_id,
                )
                .limit(1)
            )
            count_result = await self._session.execute(count_stmt)
            if count_result.scalar_one_or_none() is None:
                raise LastOwnerCannotBeRemoved(
                    f"User {user_id} is the last OWNER of project {project_id}"
                )

        await self._session.delete(member)
        await self._session.flush()

    async def member_count(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Return the number of member rows for a project-user pair (0 or 1)."""
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())
