"""SQLAlchemy ORM models for the Access domain — ``app_user`` and ``login_log``.

These models exactly match the columns, types, and constraints defined in
database design 1.1, sections 6.1 and 6.2.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistence.postgres.base import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    password_salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    system_role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    login_logs: Mapped[list["LoginLog"]] = relationship(
        "LoginLog", back_populates="user", foreign_keys="LoginLog.user_id"
    )

    __table_args__ = (
        CheckConstraint(
            "system_role IN ('ADMIN', 'USER')", name="ck_app_user_system_role"
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')", name="ck_app_user_status"
        ),
        Index(
            "uq_app_user_username_lower",
            text("lower(username)"),
            unique=True,
        ),
    )


class LoginLog(Base):
    __tablename__ = "login_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    username_attempted: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET(), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    user: Mapped["AppUser | None"] = relationship(
        "AppUser", back_populates="login_logs", foreign_keys=[user_id]
    )

    __table_args__ = (
        CheckConstraint(
            "result IN ('SUCCESS', 'FAILED')", name="ck_login_log_result"
        ),
        Index("ix_login_log_user_created", "user_id", text("created_at DESC")),
        Index(
            "ix_login_log_username_created",
            "username_attempted",
            text("created_at DESC"),
        ),
        Index("ix_login_log_created", text("created_at DESC")),
    )
