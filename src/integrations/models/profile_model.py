"""SQLAlchemy ORM model for ``model_profile``.

Defined in database design 1.1, section 12.1.  Owned by the integrations
layer to keep model-gateway configuration separate from the Profile domain.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.postgres.base import Base


class ModelProfile(Base):
    __tablename__ = "model_profile"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    secret_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("app_user.id"), nullable=False
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

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name="ck_model_profile_status"
        ),
        Index(
            "uq_model_profile_default_per_purpose",
            "purpose",
            unique=True,
            postgresql_where=text("status = 'ACTIVE' AND is_default = true"),
        ),
    )
