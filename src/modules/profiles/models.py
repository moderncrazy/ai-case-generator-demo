"""SQLAlchemy ORM models for the Profile domain.

Covers ``domain_profile``, ``domain_profile_draft``,
``domain_profile_version``, and ``profile_migration`` as defined in
database design 1.1, sections 11.1–11.4.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class DomainProfile(Base):
    __tablename__ = "domain_profile"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_builtin_general: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
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
    draft: Mapped["DomainProfileDraft | None"] = relationship(
        "DomainProfileDraft", back_populates="profile", uselist=False
    )
    versions: Mapped[list["DomainProfileVersion"]] = relationship(
        "DomainProfileVersion", back_populates="profile"
    )
    migrations: Mapped[list["ProfileMigration"]] = relationship(
        "ProfileMigration", back_populates="profile"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name="ck_domain_profile_status"
        ),
        Index(
            "uq_domain_profile_builtin_general",
            "is_builtin_general",
            unique=True,
            postgresql_where=text("is_builtin_general = true"),
        ),
    )


class DomainProfileDraft(Base):
    __tablename__ = "domain_profile_draft"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("domain_profile.id"),
        nullable=False,
        unique=True,  # one draft per profile
    )
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("app_user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    profile: Mapped["DomainProfile"] = relationship(
        "DomainProfile", back_populates="draft"
    )


class DomainProfileVersion(Base):
    __tablename__ = "domain_profile_version"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("domain_profile.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_result: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    published_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("app_user.id"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    profile: Mapped["DomainProfile"] = relationship(
        "DomainProfile", back_populates="versions"
    )

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_profile_version_positive"),
        UniqueConstraint("profile_id", "version", name="uq_profile_version_number"),
        UniqueConstraint("profile_id", "content_hash", name="uq_profile_version_hash"),
    )


class ProfileMigration(Base):
    __tablename__ = "profile_migration"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("domain_profile.id"), nullable=False
    )
    from_version: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("app_user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    profile: Mapped["DomainProfile"] = relationship(
        "DomainProfile", back_populates="migrations"
    )

    __table_args__ = (
        CheckConstraint(
            "to_version = from_version + 1", name="ck_migration_adjacent"
        ),
        UniqueConstraint(
            "profile_id",
            "from_version",
            "to_version",
            name="uq_migration_from_to",
        ),
    )
