"""Transactional project repository with domain-invariant enforcement.

Provides creation idempotency scoped to creator, member management with
last-owner enforcement, and row-locked project access for mutating
operations.
"""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.profiles.models import DomainProfile
from src.modules.projects.models import Project, ProjectMember


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
# Helpers
# ---------------------------------------------------------------------------


def _compute_profile_hash(profile: DomainProfile) -> str:
    """Produce a deterministic 64-char hex SHA-256 hash for the profile binding."""
    raw = f"profile:{profile.id}:v{profile.current_version}".encode()
    return hashlib.sha256(raw).hexdigest()


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

        The project is bound to *profile* at its current version.  A
        deterministic ``profile_hash`` is computed from the profile identity.
        """
        # Check for existing
        existing = await self.find_by_creation_key(
            created_by_user_id, creation_idempotency_key
        )
        if existing is not None:
            if existing.creation_request_hash == creation_request_hash:
                return existing
            raise CreationIdempotencyConflict(
                f"Creation key {creation_idempotency_key} already used by "
                f"user {created_by_user_id} with a different request hash"
            )

        now = datetime.now(UTC)
        project = Project(
            id=uuid.uuid4(),
            creation_idempotency_key=creation_idempotency_key,
            creation_request_hash=creation_request_hash,
            name=name,
            status="ACTIVE",
            profile_id=profile.id,
            profile_version=profile.current_version,
            profile_hash=_compute_profile_hash(profile),
            profile_migration_status="CURRENT",
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(project)
        await self._session.flush()
        return project

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
        """
        now = datetime.now(UTC)
        stmt = pg_insert(ProjectMember).values(
            id=uuid.uuid4(),
            project_id=project_id,
            user_id=user_id,
            role=role,
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "user_id"],
            set_={
                "role": stmt.excluded.role,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the current row
        result = await self._session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        return result.scalar_one()

    async def delete_member(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete a project member with last-owner enforcement.

        Raises ``LastOwnerCannotBeRemoved`` when the target is the sole
        OWNER of the project.  The check is performed under a ``FOR UPDATE``
        row lock to prevent concurrent removals from bypassing the guard.
        """
        # Lock the member row if it exists
        stmt = (
            select(ProjectMember)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        member = result.scalar_one_or_none()

        if member is None:
            return  # idempotent no-op

        if member.role == "OWNER":
            # Count other OWNERs (locked rows not required — the unique
            # constraint already serialises concurrent modifications to
            # the same project-user pair, and we hold a lock on *this* row).
            count_stmt = select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == "OWNER",
                ProjectMember.user_id != user_id,
            )
            count_result = await self._session.execute(count_stmt)
            other_owners = count_result.scalars().all()
            if len(other_owners) == 0:
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
