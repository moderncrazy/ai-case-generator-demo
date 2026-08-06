"""Transactional profile repository with domain-invariant enforcement.

All write operations use ``SELECT ... FOR UPDATE`` row locks and raise
domain-specific errors when invariants would be violated.  Published
versions have no update or delete API at this repository boundary.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.profiles.models import (
    DomainProfile,
    DomainProfileVersion,
    ProfileMigration,
)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class ProfileDomainError(Exception):
    """Base exception for Profile domain rule violations."""


class BuiltinProfileCannotBeDisabled(ProfileDomainError):
    """The built-in general Profile must remain ACTIVE."""


class BuiltinProfileCannotBeDeleted(ProfileDomainError):
    """The built-in general Profile cannot be deleted."""


class ProfileNotFound(ProfileDomainError):
    """The requested Profile does not exist."""


class ProfileVersionNotSequential(ProfileDomainError):
    """The published version must be exactly current_version + 1."""


class ProfileVersionAlreadyExists(ProfileDomainError):
    """A version with this number or content hash already exists for this profile."""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class ProfileRepository:
    """Transactional operations on the Profile domain tables.

    Every mutation method receives an ``AsyncSession`` that the caller
    manages (begin, commit, rollback).  The repository does not manage
    transaction boundaries itself.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # built-in general Profile
    # ------------------------------------------------------------------

    async def ensure_builtin_general(
        self, created_by_user_id: uuid.UUID
    ) -> DomainProfile:
        """Idempotently return the single built-in general Profile row.

        If the row does not exist it is created with ``current_version = 0``.
        The initial published content and version belong to the later Profile
        feature — Task 3 only guarantees the row is present.

        Concurrent callers are safe: the INSERT uses ``ON CONFLICT DO
        NOTHING`` against the partial unique index so that only one
        transaction creates the row and the other(s) re-select the winner.
        """
        stmt = select(DomainProfile).where(
            DomainProfile.is_builtin_general == True  # noqa: E712
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        profile_id = uuid.uuid4()
        await self._session.execute(
            text(
                """
                INSERT INTO domain_profile
                  (id, code, name, description, status, is_builtin_general,
                   current_version, created_by_user_id, created_at, updated_at)
                VALUES
                  (:id, :code, :name, :desc, :status, :is_builtin_general,
                   :current_version, :created_by_user_id, :created_at, :updated_at)
                ON CONFLICT (is_builtin_general)
                  WHERE is_builtin_general = true
                DO NOTHING
                """
            ),
            {
                "id": profile_id,
                "code": "BUILTIN_GENERAL",
                "name": "Built-in General",
                "desc": "System built-in general-purpose domain profile",
                "status": "ACTIVE",
                "is_builtin_general": True,
                "current_version": 0,
                "created_by_user_id": created_by_user_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        await self._session.flush()

        # Re-select the winner — our insert or the concurrent transaction's.
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # publication
    # ------------------------------------------------------------------

    async def publish_version(
        self,
        profile_id: uuid.UUID,
        version: int,
        content: dict,
        content_hash: str,
        validation_result: dict,
        published_by_user_id: uuid.UUID,
    ) -> DomainProfileVersion:
        """Publish a new immutable version under a ``FOR UPDATE`` row lock.

        Requirements:
        * ``version`` must equal ``current_version + 1``.
        * ``current_version`` is incremented atomically in the same
          transaction.
        """
        # Lock the profile row for the duration of the transaction
        stmt = (
            select(DomainProfile)
            .where(DomainProfile.id == profile_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ProfileNotFound(f"Profile {profile_id} not found")

        expected = profile.current_version + 1
        if version != expected:
            raise ProfileVersionNotSequential(
                f"Expected version {expected}, got {version}"
            )

        now = datetime.now(UTC)
        version_row = DomainProfileVersion(
            id=uuid.uuid4(),
            profile_id=profile_id,
            version=version,
            content=content,
            content_hash=content_hash,
            validation_result=validation_result,
            published_by_user_id=published_by_user_id,
            published_at=now,
        )
        self._session.add(version_row)

        # Advance current_version atomically
        await self._session.execute(
            update(DomainProfile)
            .where(DomainProfile.id == profile_id)
            .values(current_version=version, updated_at=now)
        )

        await self._session.flush()
        return version_row

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------

    async def set_status(
        self,
        profile_id: uuid.UUID,
        status: str,
        actor_user_id: uuid.UUID,  # noqa: ARG002 — reserved for audit
    ) -> DomainProfile:
        """Change the status of a Profile.

        Raises ``BuiltinProfileCannotBeDisabled`` if the caller attempts to
        set the built-in general Profile to ``INACTIVE``.
        """
        stmt = (
            select(DomainProfile)
            .where(DomainProfile.id == profile_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ProfileNotFound(f"Profile {profile_id} not found")

        if profile.is_builtin_general and status == "INACTIVE":
            raise BuiltinProfileCannotBeDisabled(
                "The built-in general Profile cannot be disabled"
            )

        now = datetime.now(UTC)
        await self._session.execute(
            update(DomainProfile)
            .where(DomainProfile.id == profile_id)
            .values(status=status, updated_at=now)
        )

        await self._session.flush()
        profile.status = status
        profile.updated_at = now
        return profile

    # ------------------------------------------------------------------
    # deletion
    # ------------------------------------------------------------------

    async def delete_profile(self, profile_id: uuid.UUID) -> None:
        """Delete a Profile row.

        Raises ``BuiltinProfileCannotBeDeleted`` if the target is the
        built-in general Profile.
        """
        stmt = (
            select(DomainProfile)
            .where(DomainProfile.id == profile_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ProfileNotFound(f"Profile {profile_id} not found")

        if profile.is_builtin_general:
            raise BuiltinProfileCannotBeDeleted(
                "The built-in general Profile cannot be deleted"
            )

        await self._session.delete(profile)
        await self._session.flush()

    # ------------------------------------------------------------------
    # migration
    # ------------------------------------------------------------------

    async def upsert_migration(
        self,
        profile_id: uuid.UUID,
        from_version: int,
        to_version: int,
        definition: dict,
        content_hash: str,
        updated_by_user_id: uuid.UUID,
    ) -> ProfileMigration:
        """Insert or update the adjacent migration rule (from_version -> to_version)."""
        stmt = select(ProfileMigration).where(
            ProfileMigration.profile_id == profile_id,
            ProfileMigration.from_version == from_version,
            ProfileMigration.to_version == to_version,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is not None:
            existing.definition = definition
            existing.content_hash = content_hash
            existing.updated_by_user_id = updated_by_user_id
            existing.updated_at = now
            await self._session.flush()
            return existing

        migration = ProfileMigration(
            id=uuid.uuid4(),
            profile_id=profile_id,
            from_version=from_version,
            to_version=to_version,
            definition=definition,
            content_hash=content_hash,
            updated_by_user_id=updated_by_user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(migration)
        await self._session.flush()
        return migration
