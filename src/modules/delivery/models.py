"""SQLAlchemy ORM models for the Delivery domain.

Covers ``delivery_run`` and ``project_stage`` as defined in database
design 1.1, sections 8.2 and 9.1.
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
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.postgres.base import Base


class DeliveryRun(Base):
    """One-current-row per project — ``project_id`` is the primary key.

    ``target_run_id`` on ``project_message`` intentionally has no FK to
    this table because rows are overwritten when a new run starts.
    """

    __tablename__ = "delivery_run"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("project.id"), primary_key=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    trigger_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("project_message.id"), nullable=False
    )
    response_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("project_message.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    project_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("domain_profile.id"), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_baselines: Mapped[list] = mapped_column(
        JSONB(), nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    lease_owner: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_error: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'QUEUED', 'PREPARING', 'MIGRATING', 'RUNNING', "
            "'WAITING_FOR_HUMAN', 'STOPPING', "
            "'COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED')",
            name="ck_delivery_run_status",
        ),
        UniqueConstraint("run_id", name="uq_delivery_run_run_id"),
        Index(
            "ix_delivery_run_status_lease",
            "status",
            "lease_until",
        ),
        Index(
            "ix_delivery_run_updated",
            "updated_at",
        ),
    )


class ProjectStage(Base):
    """Per-stage current state and baseline pointer.

    Nine rows per project, created at project bootstrap.  The stage
    row is the single source of truth for stage progress and baseline
    Git refs — there is no separate baseline history table.
    """

    __tablename__ = "project_stage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("project.id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    baseline_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    git_commit_sha: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    git_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("domain_profile.id"), nullable=True
    )
    profile_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    profile_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    publish_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    publish_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    publish_error: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "stage IN ("
            "'PROJECT_CHARTER', 'REQUIREMENT_OUTLINE', "
            "'REQUIREMENT_MODULE', 'PRD', 'ARCHITECTURE', "
            "'SYSTEM_MODULE', 'API', 'DATABASE', 'TEST')",
            name="ck_project_stage_stage",
        ),
        CheckConstraint(
            "status IN ("
            "'NOT_STARTED', 'BUILDING', 'WAITING_FOR_HUMAN', "
            "'SEALING', 'SEALED', 'SEAL_FAILED', 'INVALIDATED')",
            name="ck_project_stage_status",
        ),
        CheckConstraint(
            "(status <> 'SEALED') OR ("
            "baseline_version > 0 AND "
            "git_commit_sha IS NOT NULL AND "
            "git_tag IS NOT NULL)",
            name="ck_project_stage_sealed_baseline",
        ),
        UniqueConstraint(
            "project_id", "stage", name="uq_project_stage_project_stage"
        ),
        # Partial unique indexes — only when the column is NOT NULL
        Index(
            "uq_project_stage_publish_key",
            "publish_key",
            unique=True,
            postgresql_where=text("publish_key IS NOT NULL"),
        ),
        Index(
            "uq_project_stage_git_tag",
            "project_id",
            "git_tag",
            unique=True,
            postgresql_where=text("git_tag IS NOT NULL"),
        ),
        Index(
            "ix_project_stage_project_status",
            "project_id",
            "status",
        ),
        Index(
            "ix_project_stage_status_updated",
            "status",
            "updated_at",
        ),
    )
