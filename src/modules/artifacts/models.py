"""SQLAlchemy models for artifact and artifact_draft.

Corresponds to database design 1.1 sections 9.2–9.4.

Fixed reference arrays use PostgreSQL ``text[]`` with server-side empty-array
defaults.  Every reference array column carries a GIN index for reverse-impact
analysis (on ``artifact``) and candidate impact checking (on ``artifact_draft``).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistence.postgres.base import Base


class Artifact(Base):
    """Current approved artifact projection (sec 9.3).

    Only the latest approved version is stored; history lives in Git.
    """

    __tablename__ = "artifact"

    # ------------------------------------------------------------------
    # primary key
    # ------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # ------------------------------------------------------------------
    # identity and scoping
    # ------------------------------------------------------------------
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", name="fk_artifact_project"), nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_code: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(300), nullable=False)

    # ------------------------------------------------------------------
    # content
    # ------------------------------------------------------------------
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    artifact_version: Mapped[int] = mapped_column(nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False)
    body: Mapped[dict] = mapped_column(JSONB(), nullable=False)

    # ------------------------------------------------------------------
    # fixed reference arrays
    # ------------------------------------------------------------------
    source_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    requirement_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    module_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    decision_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    architecture_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    api_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    read_table_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    write_table_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )

    # ------------------------------------------------------------------
    # content integrity
    # ------------------------------------------------------------------
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # ------------------------------------------------------------------
    # profile binding
    # ------------------------------------------------------------------
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("domain_profile.id", name="fk_artifact_profile"),
        nullable=False,
    )
    profile_version: Mapped[int] = mapped_column(nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # ------------------------------------------------------------------
    # approval metadata
    # ------------------------------------------------------------------
    baseline_version: Mapped[int] = mapped_column(nullable=False)
    git_path: Mapped[str] = mapped_column(Text(), nullable=False)
    git_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)

    # ------------------------------------------------------------------
    # timestamps
    # ------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # ------------------------------------------------------------------
    # table-level constraints
    # ------------------------------------------------------------------
    __table_args__ = (
        UniqueConstraint(
            "project_id", "artifact_code", name="uq_artifact_code",
        ),
        UniqueConstraint(
            "project_id", "artifact_type", "canonical_key",
            name="uq_artifact_type_canonical_key",
        ),
        UniqueConstraint(
            "project_id", "git_path", name="uq_artifact_git_path",
        ),
        ForeignKeyConstraint(
            ["project_id", "stage"],
            ["project_stage.project_id", "project_stage.stage"],
            name="fk_artifact_project_stage",
        ),
        Index("ix_artifact_project_stage", "project_id", "stage"),
        Index("ix_artifact_project_type", "project_id", "artifact_type"),
        *[
            Index(f"ix_artifact_{col}_gin", col, postgresql_using="gin")
            for col in [
                "requirement_refs", "module_refs", "decision_refs",
                "architecture_refs", "api_refs",
                "read_table_refs", "write_table_refs",
            ]
        ],
    )


class ArtifactDraft(Base):
    """Current candidate artifact projection (sec 9.4).

    Each (project, type, canonical_key) has at most one draft row.
    New drafts leave ``artifact_code`` NULL until sealing reserves codes.
    ``base_artifact_id`` is NULL for CREATE operations only.
    """

    __tablename__ = "artifact_draft"

    # ------------------------------------------------------------------
    # primary key
    # ------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # ------------------------------------------------------------------
    # identity and scoping
    # ------------------------------------------------------------------
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", name="fk_artifact_draft_project"),
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    canonical_key: Mapped[str] = mapped_column(String(300), nullable=False)

    # ------------------------------------------------------------------
    # content
    # ------------------------------------------------------------------
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    artifact_version: Mapped[int] = mapped_column(nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False)
    body: Mapped[dict] = mapped_column(JSONB(), nullable=False)

    # ------------------------------------------------------------------
    # fixed reference arrays
    # ------------------------------------------------------------------
    source_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    requirement_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    module_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    decision_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    architecture_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    api_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    read_table_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    write_table_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )

    # ------------------------------------------------------------------
    # content integrity
    # ------------------------------------------------------------------
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # ------------------------------------------------------------------
    # profile binding
    # ------------------------------------------------------------------
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("domain_profile.id", name="fk_artifact_draft_profile"),
        nullable=False,
    )
    profile_version: Mapped[int] = mapped_column(nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # ------------------------------------------------------------------
    # base artifact (NULL for CREATE)
    # ------------------------------------------------------------------
    base_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifact.id", name="fk_artifact_draft_base_artifact"),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    validation_result: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default="{}",
    )
    review_result: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default="{}",
    )

    # ------------------------------------------------------------------
    # timestamps
    # ------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # ------------------------------------------------------------------
    # relationships
    # ------------------------------------------------------------------
    base_artifact: Mapped["Artifact | None"] = relationship(
        "Artifact", foreign_keys=[base_artifact_id],
    )

    # ------------------------------------------------------------------
    # table-level constraints
    # ------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint(
            "operation IN ('CREATE', 'UPDATE', 'DELETE')",
            name="ck_artifact_draft_operation",
        ),
        CheckConstraint(
            "status IN ("
            "'DRAFT', 'VALIDATING', 'REVISING', 'READY_TO_SEAL', "
            "'DELETING')",
            name="ck_artifact_draft_status",
        ),
        CheckConstraint(
            "operation = 'CREATE' OR base_artifact_id IS NOT NULL",
            name="ck_artifact_draft_operation_base",
        ),
        UniqueConstraint(
            "project_id", "artifact_type", "canonical_key",
            name="uq_artifact_draft_type_canonical_key",
        ),
        ForeignKeyConstraint(
            ["project_id", "stage"],
            ["project_stage.project_id", "project_stage.stage"],
            name="fk_artifact_draft_project_stage",
        ),
        Index(
            "uq_artifact_draft_code",
            "project_id", "artifact_code",
            unique=True,
            postgresql_where=text("artifact_code IS NOT NULL"),
        ),
        Index(
            "ix_artifact_draft_project_stage_status",
            "project_id", "stage", "status",
        ),
        Index("ix_artifact_draft_base_artifact", "base_artifact_id"),
        *[
            Index(f"ix_artifact_draft_{col}_gin", col, postgresql_using="gin")
            for col in [
                "requirement_refs", "module_refs", "decision_refs",
                "architecture_refs", "api_refs",
                "read_table_refs", "write_table_refs",
            ]
        ],
    )


