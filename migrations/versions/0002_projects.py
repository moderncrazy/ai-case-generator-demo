"""Migration 0002 — project and project_member tables.

Creates the two tables defined in database design 1.1, sections 7.1–7.2:

* ``project`` — project identity, truth, profile binding, and GitLab fields
* ``project_member`` — project role memberships

All timestamps are timezone-aware UTC.  IDs are application-generated UUIDs.
Status fields use varchar + CHECK constraints (no PostgreSQL ENUM types).
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # project
    # ------------------------------------------------------------------
    op.create_table(
        "project",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creation_idempotency_key", sa.Uuid(), nullable=False),
        sa.Column(
            "creation_request_hash", sa.VARCHAR(64), nullable=False
        ),
        sa.Column("name", sa.VARCHAR(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.VARCHAR(24),
            nullable=False,
        ),
        sa.Column(
            "truth",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "revision",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_hash", sa.VARCHAR(64), nullable=False),
        sa.Column(
            "profile_migration_status",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column(
            "profile_migration_error",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "artifact_counters",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("gitlab_project_id", sa.BigInteger(), nullable=True),
        sa.Column("gitlab_path", sa.Text(), nullable=True),
        sa.Column(
            "default_branch",
            sa.VARCHAR(100),
            nullable=False,
            server_default=sa.text("'main'"),
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_project"),
        # CHECK constraints
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'REBASELINING', 'BLOCKED', 'COMPLETED', "
            "'ARCHIVED')",
            name="ck_project_status",
        ),
        sa.CheckConstraint(
            "profile_migration_status IN ('CURRENT', 'MIGRATING', 'WAITING', "
            "'FAILED')",
            name="ck_project_profile_migration_status",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_project_profile",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name="fk_project_created_by",
        ),
        # Unique constraints
        sa.UniqueConstraint(
            "created_by_user_id",
            "creation_idempotency_key",
            name="uq_project_creation_key",
        ),
        sa.UniqueConstraint(
            "gitlab_project_id",
            name="uq_project_gitlab_project_id",
        ),
        sa.UniqueConstraint(
            "gitlab_path",
            name="uq_project_gitlab_path",
        ),
    )
    # Indexes
    op.create_index(
        "ix_project_status_updated",
        "project",
        ["status", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_project_profile_version",
        "project",
        ["profile_id", "profile_version"],
    )
    op.create_index(
        "ix_project_created_by_created",
        "project",
        ["created_by_user_id", sa.text("created_at DESC")],
    )

    # ------------------------------------------------------------------
    # project_member
    # ------------------------------------------------------------------
    op.create_table(
        "project_member",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_project_member"),
        # CHECK constraint
        sa.CheckConstraint(
            "role IN ('OWNER', 'MEMBER', 'VIEWER')",
            name="ck_project_member_role",
        ),
        # Unique (project_id, user_id) — one row per user per project
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_member_project_user",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_project_member_project",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_project_member_user",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name="fk_project_member_created_by",
        ),
    )
    # User project list index
    op.create_index(
        "ix_project_member_user_project",
        "project_member",
        ["user_id", "project_id"],
    )


def downgrade() -> None:
    op.drop_table("project_member")
    op.drop_table("project")
