"""Migration 0001 — access, profile, and model tables.

Creates the seven tables defined in database design 1.1:

* ``app_user`` — user accounts, status, and password material
* ``login_log`` — successful and failed login records
* ``domain_profile`` — stable profile identity and current version
* ``domain_profile_draft`` — current editable profile draft
* ``domain_profile_version`` — immutable published versions
* ``profile_migration`` — current adjacent-version migration rules
* ``model_profile`` — stage model and parameter configuration

All timestamps are timezone-aware UTC.  IDs are application-generated UUIDs.
Status fields use varchar + CHECK constraints (no PostgreSQL ENUM types).
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # langgraph schema — owned by AsyncPostgresSaver.setup()
    # ------------------------------------------------------------------
    op.execute("CREATE SCHEMA IF NOT EXISTS langgraph")

    # ------------------------------------------------------------------
    # app_user
    # ------------------------------------------------------------------
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.VARCHAR(100), nullable=False),
        sa.Column("display_name", sa.VARCHAR(200), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("password_salt", sa.LargeBinary(), nullable=False),
        sa.Column(
            "system_role",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_app_user"),
        # CHECK constraints (varchar + CHECK, no PostgreSQL ENUM)
        sa.CheckConstraint(
            "system_role IN ('ADMIN', 'USER')",
            name="ck_app_user_system_role",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_app_user_status",
        ),
        # Self-referencing FK (created_by_user_id -> app_user.id)
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name="fk_app_user_created_by",
            ondelete="SET NULL",
        ),
    )
    # Unique index on lower(username) for case-insensitive uniqueness
    op.create_index(
        "uq_app_user_username_lower",
        "app_user",
        [sa.text("lower(username)")],
        unique=True,
    )

    # ------------------------------------------------------------------
    # login_log
    # ------------------------------------------------------------------
    op.create_table(
        "login_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("username_attempted", sa.VARCHAR(100), nullable=False),
        sa.Column(
            "result",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column("failure_code", sa.VARCHAR(32), nullable=True),
        sa.Column("ip_address", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_login_log"),
        # CHECK
        sa.CheckConstraint(
            "result IN ('SUCCESS', 'FAILED')",
            name="ck_login_log_result",
        ),
        # FK to app_user
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_login_log_user",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_login_log_user_created",
        "login_log",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_login_log_username_created",
        "login_log",
        ["username_attempted", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_login_log_created",
        "login_log",
        [sa.text("created_at DESC")],
    )

    # ------------------------------------------------------------------
    # domain_profile
    # ------------------------------------------------------------------
    op.create_table(
        "domain_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.VARCHAR(100), nullable=False),
        sa.Column("name", sa.VARCHAR(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column(
            "is_builtin_general",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "current_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name="pk_domain_profile"),
        # CHECK
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_domain_profile_status",
        ),
        # Unique code
        sa.UniqueConstraint("code", name="uq_domain_profile_code"),
        # FK
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name="fk_domain_profile_created_by",
        ),
    )
    # Partial unique index: only one row with is_builtin_general=true
    op.create_index(
        "uq_domain_profile_builtin_general",
        "domain_profile",
        ["is_builtin_general"],
        unique=True,
        postgresql_where=sa.text("is_builtin_general = true"),
    )

    # ------------------------------------------------------------------
    # domain_profile_draft
    # ------------------------------------------------------------------
    op.create_table(
        "domain_profile_draft",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("content", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.VARCHAR(64), nullable=False),
        sa.Column(
            "lock_version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name="pk_domain_profile_draft"),
        # One draft per profile
        sa.UniqueConstraint(
            "profile_id", name="uq_domain_profile_draft_profile"
        ),
        # FK
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_draft_profile",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["app_user.id"],
            name="fk_draft_updated_by",
        ),
    )

    # ------------------------------------------------------------------
    # domain_profile_version
    # ------------------------------------------------------------------
    op.create_table(
        "domain_profile_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.VARCHAR(64), nullable=False),
        sa.Column(
            "validation_result",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name="pk_domain_profile_version"),
        # CHECK version > 0
        sa.CheckConstraint(
            "version > 0", name="ck_profile_version_positive"
        ),
        # Unique (profile_id, version)
        sa.UniqueConstraint(
            "profile_id", "version", name="uq_profile_version_number"
        ),
        # Unique (profile_id, content_hash)
        sa.UniqueConstraint(
            "profile_id", "content_hash", name="uq_profile_version_hash"
        ),
        # FK
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_version_profile",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["app_user.id"],
            name="fk_version_published_by",
        ),
    )

    # ------------------------------------------------------------------
    # profile_migration
    # ------------------------------------------------------------------
    op.create_table(
        "profile_migration",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("from_version", sa.Integer(), nullable=False),
        sa.Column("to_version", sa.Integer(), nullable=False),
        sa.Column(
            "definition", sa.dialects.postgresql.JSONB(), nullable=False
        ),
        sa.Column("content_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name="pk_profile_migration"),
        # Adjacent version check
        sa.CheckConstraint(
            "to_version = from_version + 1",
            name="ck_migration_adjacent",
        ),
        # Unique (profile_id, from_version, to_version)
        sa.UniqueConstraint(
            "profile_id",
            "from_version",
            "to_version",
            name="uq_migration_from_to",
        ),
        # FK
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_migration_profile",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["app_user.id"],
            name="fk_migration_updated_by",
        ),
    )

    # ------------------------------------------------------------------
    # model_profile
    # ------------------------------------------------------------------
    op.create_table(
        "model_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.VARCHAR(100), nullable=False),
        sa.Column("name", sa.VARCHAR(200), nullable=False),
        sa.Column("purpose", sa.VARCHAR(40), nullable=False),
        sa.Column("provider", sa.VARCHAR(100), nullable=False),
        sa.Column("model_name", sa.VARCHAR(200), nullable=False),
        sa.Column(
            "parameters",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("secret_ref", sa.VARCHAR(200), nullable=False),
        sa.Column(
            "status",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name="pk_model_profile"),
        # CHECK
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_model_profile_status",
        ),
        # Unique code
        sa.UniqueConstraint("code", name="uq_model_profile_code"),
        # FK
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name="fk_model_profile_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["app_user.id"],
            name="fk_model_profile_updated_by",
        ),
    )
    # Partial unique index: at most one ACTIVE default per purpose
    op.create_index(
        "uq_model_profile_default_per_purpose",
        "model_profile",
        ["purpose"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'ACTIVE' AND is_default = true"
        ),
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS langgraph CASCADE")
    op.drop_table("model_profile")
    op.drop_table("profile_migration")
    op.drop_table("domain_profile_version")
    op.drop_table("domain_profile_draft")
    op.drop_table("domain_profile")
    op.drop_table("login_log")
    op.drop_table("app_user")
