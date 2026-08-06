"""SQLAlchemy ORM model for the File domain — ``project_file``.

Matches database design 1.1, section 7.3 exactly, including fixed columns,
CHECK constraints, and unique/index constraints.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.postgres.base import Base


class ProjectFile(Base):
    """Attachment metadata and object-store key.

    File content lives in MinIO/S3; this table only stores metadata,
    processing status, and object store locators.
    """

    __tablename__ = "project_file"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("project.id"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_text_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "size_bytes >= 0",
            name="ck_project_file_size_bytes",
        ),
        CheckConstraint(
            "status IN ("
            "'UPLOADED', 'SCANNING', 'PROCESSING', 'READY', 'FAILED')",
            name="ck_project_file_status",
        ),
        UniqueConstraint(
            "project_id", "filename",
            name="uq_project_file_project_filename",
        ),
        UniqueConstraint(
            "object_key",
            name="uq_project_file_object_key",
        ),
        UniqueConstraint(
            "extracted_text_key",
            name="uq_project_file_extracted_text_key",
        ),
        # Same-project integrity — a file's source message must belong to
        # the file's project.
        ForeignKeyConstraint(
            ["project_id", "message_id"],
            ["project_message.project_id", "project_message.id"],
            name="fk_project_file_message",
        ),
        Index(
            "ix_project_file_project_created",
            "project_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_project_file_message",
            "message_id",
        ),
        Index(
            "ix_project_file_project_sha256",
            "project_id",
            "sha256",
        ),
    )
