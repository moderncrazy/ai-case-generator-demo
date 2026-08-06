"""SQLAlchemy model for project_change.

Corresponds to database design 1.1 section 10.1.

Terminal states (APPLIED, REJECTED, WITHDRAWN) require a completed decision
pointer via CHECK constraint.  The table serves as a compact processing index;
full decision text is rendered into approved artifacts in Git.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.postgres.base import Base


class ProjectChange(Base):
    """Change processing and terminal-state index (sec 10.1).

    Terminal states enforce:
        decision IS NOT NULL
        AND decided_by_user_id IS NOT NULL
        AND decided_at IS NOT NULL
        AND decision_git_commit_sha IS NOT NULL
    """

    __tablename__ = "project_change"

    # ------------------------------------------------------------------
    # primary key
    # ------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # ------------------------------------------------------------------
    # identity and scoping
    # ------------------------------------------------------------------
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", name="fk_project_change_project"),
        nullable=False,
    )
    source_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_message.id", name="fk_project_change_source_message"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", name="fk_project_change_requested_by"),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # request
    # ------------------------------------------------------------------
    request_content: Mapped[str] = mapped_column(nullable=False)
    target_artifact_codes: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}",
    )
    base_baselines: Mapped[dict] = mapped_column(JSONB(), nullable=False)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    status: Mapped[str] = mapped_column(nullable=False)
    impact: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)

    # ------------------------------------------------------------------
    # decision
    # ------------------------------------------------------------------
    decision: Mapped[str | None] = mapped_column(nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", name="fk_project_change_decided_by"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decision_artifact_code: Mapped[str | None] = mapped_column(nullable=True)
    decision_git_commit_sha: Mapped[str | None] = mapped_column(nullable=True)

    # ------------------------------------------------------------------
    # application result
    # ------------------------------------------------------------------
    applied_baselines: Mapped[dict | None] = mapped_column(
        JSONB(), nullable=True,
    )
    last_error: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)

    # ------------------------------------------------------------------
    # timestamps
    # ------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    # ------------------------------------------------------------------
    # table-level constraints
    # ------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'PROPOSED', 'ANALYZING', 'WAITING_FOR_HUMAN', "
            "'APPROVED', 'APPLYING', 'APPLIED', "
            "'REJECTED', 'WITHDRAWN', 'FAILED')",
            name="ck_project_change_status",
        ),
        CheckConstraint(
            "decision IS NULL OR decision IN "
            "('APPROVED', 'REJECTED', 'WITHDRAWN')",
            name="ck_project_change_decision",
        ),
        CheckConstraint(
            "(status NOT IN ('APPLIED', 'REJECTED', 'WITHDRAWN')) OR ("
            "decision IS NOT NULL AND "
            "decided_by_user_id IS NOT NULL AND "
            "decided_at IS NOT NULL AND "
            "decision_git_commit_sha IS NOT NULL)",
            name="ck_project_change_terminal_decision",
        ),
        Index(
            "ix_project_change_project_created",
            "project_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_project_change_project_status_updated",
            "project_id", "status", "updated_at",
        ),
        Index(
            "ix_project_change_target_codes_gin",
            "target_artifact_codes",
            postgresql_using="gin",
        ),
    )

