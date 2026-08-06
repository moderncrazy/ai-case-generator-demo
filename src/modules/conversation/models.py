"""SQLAlchemy ORM model for the Conversation domain — ``project_message``.

Matches database design 1.1, section 8.1 exactly, including fixed columns,
CHECK constraints, partial unique indexes, and timeline/queue/run indexes.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistence.postgres.base import Base


class ProjectMessage(Base):
    __tablename__ = "project_message"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("project.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), nullable=True
    )
    request_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    agent_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=text("''")
    )
    delivery_mode: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    target_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    process: Mapped[list] = mapped_column(
        JSONB(), nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    process_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    diagnostics: Mapped[list] = mapped_column(
        JSONB(), nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    stopped_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('USER', 'ASSISTANT', 'SYSTEM')",
            name="ck_project_message_role",
        ),
        CheckConstraint(
            "(role = 'USER' AND user_id IS NOT NULL) "
            "OR (role <> 'USER' AND user_id IS NULL)",
            name="ck_project_message_role_user",
        ),
        CheckConstraint(
            "(role = 'USER' AND idempotency_key IS NOT NULL "
            "AND request_hash IS NOT NULL) "
            "OR (role <> 'USER' AND idempotency_key IS NULL "
            "AND request_hash IS NULL)",
            name="ck_project_message_role_key",
        ),
        CheckConstraint(
            "status IN ("
            "'PENDING', 'QUEUED', 'RUNNING', 'WAITING_FOR_HUMAN', "
            "'COMPLETED', 'FAILED', 'FAILED_BEFORE_PROCESSING', "
            "'CANCELLED', 'INTERRUPTED')",
            name="ck_project_message_status",
        ),
        CheckConstraint(
            "delivery_mode IS NULL OR delivery_mode IN "
            "('DIRECT', 'STEER', 'QUEUE')",
            name="ck_project_message_delivery_mode",
        ),
        CheckConstraint(
            "(status IN ('CANCELLED', 'INTERRUPTED') AND "
            "stopped_by_user_id IS NOT NULL AND stopped_at IS NOT NULL) "
            "OR (status NOT IN ('CANCELLED', 'INTERRUPTED') AND "
            "stopped_by_user_id IS NULL AND stopped_at IS NULL)",
            name="ck_project_message_stopped_at",
        ),
        # Candidate key — id is project-scoped so composite FKs from
        # delivery_run / project_file / project_change can enforce
        # same-project references.
        UniqueConstraint(
            "project_id", "id", name="uq_project_message_project_id",
        ),
        # Partial unique index — scoped to project + user when key present
        Index(
            "uq_project_message_idempotency",
            "project_id",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        # Timeline index
        Index(
            "ix_project_message_timeline",
            "project_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
        # Queue partial index
        Index(
            "ix_project_message_queue",
            "project_id",
            "created_at",
            "id",
            postgresql_where=text(
                "delivery_mode = 'QUEUE' AND status = 'QUEUED'"
            ),
        ),
        # Run query index
        Index(
            "ix_project_message_run",
            "project_id",
            "target_run_id",
            "created_at",
        ),
    )
