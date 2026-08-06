"""SQLAlchemy ORM models for the Project domain.

Covers ``project`` and ``project_member`` as defined in database design 1.1,
sections 7.1 and 7.2.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistence.postgres.base import Base


class Project(Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    creation_idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(), nullable=False
    )
    creation_request_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    truth: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("domain_profile.id"), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_migration_status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    profile_migration_error: Mapped[dict | None] = mapped_column(
        JSONB(), nullable=True
    )
    artifact_counters: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    gitlab_project_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    gitlab_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(
        String(100), nullable=False, default="main", server_default=text("'main'")
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("app_user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'REBASELINING', 'BLOCKED', 'COMPLETED', "
            "'ARCHIVED')",
            name="ck_project_status",
        ),
        CheckConstraint(
            "profile_migration_status IN ('CURRENT', 'MIGRATING', 'WAITING', "
            "'FAILED')",
            name="ck_project_profile_migration_status",
        ),
        UniqueConstraint(
            "created_by_user_id",
            "creation_idempotency_key",
            name="uq_project_creation_key",
        ),
        UniqueConstraint(
            "gitlab_project_id",
            name="uq_project_gitlab_project_id",
        ),
        UniqueConstraint(
            "gitlab_path",
            name="uq_project_gitlab_path",
        ),
        Index(
            "ix_project_status_updated",
            "status",
            text("updated_at DESC"),
        ),
        Index(
            "ix_project_profile_version",
            "profile_id",
            "profile_version",
        ),
        Index(
            "ix_project_created_by_created",
            "created_by_user_id",
            text("created_at DESC"),
        ),
    )


class ProjectMember(Base):
    __tablename__ = "project_member"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("project.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("app_user.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("app_user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project", back_populates="members"
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('OWNER', 'MEMBER', 'VIEWER')",
            name="ck_project_member_role",
        ),
        UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_member_project_user",
        ),
        Index(
            "ix_project_member_user_project",
            "user_id",
            "project_id",
        ),
    )
