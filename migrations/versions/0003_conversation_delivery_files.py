"""Migration 0003 — conversation, delivery, stage, and file tables.

Creates the four tables defined in database design 1.1:

* ``project_message`` — shared timeline, queue, process, and diagnostics (sec 8.1)
* ``delivery_run`` — one-current-row per project (sec 8.2)
* ``project_stage`` — nine stage rows with current baseline pointer (sec 9.1)
* ``project_file`` — attachment metadata and object‑store key (sec 7.3)

All timestamps are timezone-aware UTC.  IDs are application-generated UUIDs.
Status fields use varchar + CHECK constraints (no PostgreSQL ENUM types).
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # project_message
    # ------------------------------------------------------------------
    op.create_table(
        "project_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=True),
        sa.Column("request_hash", sa.VARCHAR(64), nullable=True),
        sa.Column(
            "role",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column("agent_role", sa.VARCHAR(32), nullable=True),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("delivery_mode", sa.VARCHAR(16), nullable=True),
        sa.Column("target_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.VARCHAR(32),
            nullable=False,
        ),
        sa.Column(
            "process",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "process_version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "diagnostics",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("stopped_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_project_message"),
        # CHECK constraints
        sa.CheckConstraint(
            "role IN ('USER', 'ASSISTANT', 'SYSTEM')",
            name="ck_project_message_role",
        ),
        sa.CheckConstraint(
            "(role = 'USER' AND user_id IS NOT NULL) "
            "OR (role <> 'USER' AND user_id IS NULL)",
            name="ck_project_message_role_user",
        ),
        sa.CheckConstraint(
            "(role = 'USER' AND idempotency_key IS NOT NULL "
            "AND request_hash IS NOT NULL) "
            "OR (role <> 'USER' AND idempotency_key IS NULL "
            "AND request_hash IS NULL)",
            name="ck_project_message_role_key",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'PENDING', 'QUEUED', 'RUNNING', 'WAITING_FOR_HUMAN', "
            "'COMPLETED', 'FAILED', 'FAILED_BEFORE_PROCESSING', "
            "'CANCELLED', 'INTERRUPTED')",
            name="ck_project_message_status",
        ),
        sa.CheckConstraint(
            "delivery_mode IS NULL OR delivery_mode IN "
            "('DIRECT', 'STEER', 'QUEUE')",
            name="ck_project_message_delivery_mode",
        ),
        sa.CheckConstraint(
            "(status IN ('CANCELLED', 'INTERRUPTED') AND "
            "stopped_by_user_id IS NOT NULL AND stopped_at IS NOT NULL) "
            "OR (status NOT IN ('CANCELLED', 'INTERRUPTED') AND "
            "stopped_by_user_id IS NULL AND stopped_at IS NULL)",
            name="ck_project_message_stopped_at",
        ),
        # Candidate key — id is project-scoped so composite FKs from
        # delivery_run / project_file / project_change can enforce
        # same-project references.
        sa.UniqueConstraint(
            "project_id", "id", name="uq_project_message_project_id",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_project_message_project",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_project_message_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["stopped_by_user_id"],
            ["app_user.id"],
            name="fk_project_message_stopped_by",
            ondelete="SET NULL",
        ),
        # target_run_id intentionally has NO FK (delivery_run rows are
        # overwritten).
    )
    # Partial unique: (project_id, user_id, idempotency_key) only when key
    # is NOT NULL — idempotency is scoped to project + user.
    op.create_index(
        "uq_project_message_idempotency",
        "project_message",
        ["project_id", "user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    # Timeline index: (project_id, created_at DESC, id DESC)
    op.create_index(
        "ix_project_message_timeline",
        "project_message",
        ["project_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    # Queue partial index: (project_id, created_at, id) WHERE QUEUED
    op.create_index(
        "ix_project_message_queue",
        "project_message",
        ["project_id", "created_at", "id"],
        postgresql_where=sa.text(
            "delivery_mode = 'QUEUE' AND status = 'QUEUED'"
        ),
    )
    # Run query index: (project_id, target_run_id, created_at)
    op.create_index(
        "ix_project_message_run",
        "project_message",
        ["project_id", "target_run_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # delivery_run
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_run",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_message_id", sa.Uuid(), nullable=False),
        sa.Column("response_message_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.VARCHAR(32),
            nullable=False,
        ),
        sa.Column(
            "project_revision",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_hash", sa.VARCHAR(64), nullable=False),
        sa.Column(
            "input_baselines",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("lease_owner", sa.VARCHAR(200), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_error",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key: project_id ensures one current run per project
        sa.PrimaryKeyConstraint("project_id", name="pk_delivery_run"),
        # CHECK constraint
        sa.CheckConstraint(
            "status IN ("
            "'QUEUED', 'PREPARING', 'MIGRATING', 'RUNNING', "
            "'WAITING_FOR_HUMAN', 'STOPPING', "
            "'COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED')",
            name="ck_delivery_run_status",
        ),
        # Unique run_id
        sa.UniqueConstraint("run_id", name="uq_delivery_run_run_id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_delivery_run_project",
        ),
        # Same-project integrity — trigger/response messages must belong to
        # the run's project (composite FK on the project_message candidate key).
        sa.ForeignKeyConstraint(
            ["project_id", "trigger_message_id"],
            ["project_message.project_id", "project_message.id"],
            name="fk_delivery_run_trigger_message",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "response_message_id"],
            ["project_message.project_id", "project_message.id"],
            name="fk_delivery_run_response_message",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_delivery_run_profile",
        ),
    )
    # Worker claim / lease recovery index
    op.create_index(
        "ix_delivery_run_status_lease",
        "delivery_run",
        ["status", "lease_until"],
    )
    # Scheduler scan index
    op.create_index(
        "ix_delivery_run_updated",
        "delivery_run",
        ["updated_at"],
    )

    # ------------------------------------------------------------------
    # project_stage
    # ------------------------------------------------------------------
    op.create_table(
        "project_stage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "stage",
            sa.VARCHAR(40),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.VARCHAR(32),
            nullable=False,
        ),
        sa.Column(
            "revision",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "baseline_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("git_commit_sha", sa.VARCHAR(64), nullable=True),
        sa.Column("git_tag", sa.Text(), nullable=True),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("profile_version", sa.Integer(), nullable=True),
        sa.Column("profile_hash", sa.VARCHAR(64), nullable=True),
        sa.Column("publish_key", sa.VARCHAR(64), nullable=True),
        sa.Column(
            "publish_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "publish_error",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_project_stage"),
        # CHECK constraints
        sa.CheckConstraint(
            "stage IN ("
            "'PROJECT_CHARTER', 'REQUIREMENT_OUTLINE', "
            "'REQUIREMENT_MODULE', 'PRD', 'ARCHITECTURE', "
            "'SYSTEM_MODULE', 'API', 'DATABASE', 'TEST')",
            name="ck_project_stage_stage",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'NOT_STARTED', 'BUILDING', 'WAITING_FOR_HUMAN', "
            "'SEALING', 'SEALED', 'SEAL_FAILED', 'INVALIDATED')",
            name="ck_project_stage_status",
        ),
        sa.CheckConstraint(
            "(status <> 'SEALED') OR ("
            "baseline_version > 0 AND "
            "git_commit_sha IS NOT NULL AND "
            "git_tag IS NOT NULL)",
            name="ck_project_stage_sealed_baseline",
        ),
        # Unique constraints
        sa.UniqueConstraint(
            "project_id", "stage", name="uq_project_stage_project_stage",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_project_stage_project",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_project_stage_profile",
        ),
    )
    # Partial unique: publish_key only when NOT NULL
    op.create_index(
        "uq_project_stage_publish_key",
        "project_stage",
        ["publish_key"],
        unique=True,
        postgresql_where=sa.text("publish_key IS NOT NULL"),
    )
    # Partial unique: (project_id, git_tag) only when NOT NULL
    op.create_index(
        "uq_project_stage_git_tag",
        "project_stage",
        ["project_id", "git_tag"],
        unique=True,
        postgresql_where=sa.text("git_tag IS NOT NULL"),
    )
    # Status lookup indexes
    op.create_index(
        "ix_project_stage_project_status",
        "project_stage",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_project_stage_status_updated",
        "project_stage",
        ["status", "updated_at"],
    )

    # ------------------------------------------------------------------
    # project_file
    # ------------------------------------------------------------------
    op.create_table(
        "project_file",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.VARCHAR(200), nullable=False),
        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column("sha256", sa.VARCHAR(64), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("extracted_text_key", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.VARCHAR(24),
            nullable=False,
        ),
        sa.Column(
            "error",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_project_file"),
        # CHECK constraints
        sa.CheckConstraint(
            "size_bytes >= 0",
            name="ck_project_file_size_bytes",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'UPLOADED', 'SCANNING', 'PROCESSING', 'READY', 'FAILED')",
            name="ck_project_file_status",
        ),
        # Unique constraints
        sa.UniqueConstraint(
            "project_id", "filename",
            name="uq_project_file_project_filename",
        ),
        sa.UniqueConstraint(
            "object_key",
            name="uq_project_file_object_key",
        ),
        sa.UniqueConstraint(
            "extracted_text_key",
            name="uq_project_file_extracted_text_key",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_project_file_project",
        ),
        # Same-project integrity — a file's source message must belong to
        # the file's project.
        sa.ForeignKeyConstraint(
            ["project_id", "message_id"],
            ["project_message.project_id", "project_message.id"],
            name="fk_project_file_message",
        ),
    )
    # Indexes
    op.create_index(
        "ix_project_file_project_created",
        "project_file",
        ["project_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_project_file_message",
        "project_file",
        ["message_id"],
    )
    op.create_index(
        "ix_project_file_project_sha256",
        "project_file",
        ["project_id", "sha256"],
    )


def downgrade() -> None:
    op.drop_table("project_file")
    op.drop_table("project_stage")
    op.drop_table("delivery_run")
    op.drop_table("project_message")
