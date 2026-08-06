"""Migration 0004 — artifact_draft, artifact, and project_change tables.

Creates the three tables defined in database design 1.1:

* ``artifact_draft`` — current candidate artifact projection (sec 9.4)
* ``artifact`` — current approved artifact projection (sec 9.3)
* ``project_change`` — change processing and terminal-state index (sec 10.1)

All timestamps are timezone-aware UTC.  IDs are application-generated UUIDs.
Status fields use varchar + CHECK constraints (no PostgreSQL ENUM types).
Fixed reference arrays use text[] with GIN indexes.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Fixed reference array columns shared by artifact and artifact_draft.
_REF_ARRAY_COLS = [
    "requirement_refs",
    "module_refs",
    "decision_refs",
    "architecture_refs",
    "api_refs",
    "read_table_refs",
    "write_table_refs",
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # artifact
    # ------------------------------------------------------------------
    op.create_table(
        "artifact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.VARCHAR(40), nullable=False),
        sa.Column("artifact_type", sa.VARCHAR(40), nullable=False),
        sa.Column("artifact_code", sa.VARCHAR(40), nullable=False),
        sa.Column("canonical_key", sa.VARCHAR(300), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column(
            "body",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "source_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "requirement_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "module_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "decision_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "architecture_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "api_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "read_table_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "write_table_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("content_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("baseline_version", sa.Integer(), nullable=False),
        sa.Column("git_path", sa.Text(), nullable=False),
        sa.Column("git_commit_sha", sa.VARCHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_artifact"),
        # Unique constraints
        sa.UniqueConstraint(
            "project_id", "artifact_code", name="uq_artifact_code",
        ),
        sa.UniqueConstraint(
            "project_id", "artifact_type", "canonical_key",
            name="uq_artifact_type_canonical_key",
        ),
        sa.UniqueConstraint(
            "project_id", "git_path", name="uq_artifact_git_path",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_artifact_project",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_artifact_profile",
        ),
    )
    # Indexes
    op.create_index(
        "ix_artifact_project_stage",
        "artifact",
        ["project_id", "stage"],
    )
    op.create_index(
        "ix_artifact_project_type",
        "artifact",
        ["project_id", "artifact_type"],
    )
    # GIN indexes for reverse-impact analysis on fixed reference arrays
    for col in _REF_ARRAY_COLS:
        op.create_index(
            f"ix_artifact_{col}_gin",
            "artifact",
            [col],
            postgresql_using="gin",
        )

    # ------------------------------------------------------------------
    # artifact_draft
    # ------------------------------------------------------------------
    op.create_table(
        "artifact_draft",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.VARCHAR(40), nullable=False),
        sa.Column("artifact_type", sa.VARCHAR(40), nullable=False),
        sa.Column("artifact_code", sa.VARCHAR(40), nullable=True),
        sa.Column("canonical_key", sa.VARCHAR(300), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column(
            "body",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "source_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "requirement_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "module_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "decision_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "architecture_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "api_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "read_table_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "write_table_refs",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("content_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("base_artifact_id", sa.Uuid(), nullable=True),
        sa.Column(
            "operation",
            sa.VARCHAR(16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.VARCHAR(24),
            nullable=False,
        ),
        sa.Column(
            "validation_result",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "review_result",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_artifact_draft"),
        # CHECK constraints
        sa.CheckConstraint(
            "operation IN ('CREATE', 'UPDATE', 'DELETE')",
            name="ck_artifact_draft_operation",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'DRAFT', 'VALIDATING', 'REVISING', 'READY_TO_SEAL', "
            "'DELETING')",
            name="ck_artifact_draft_status",
        ),
        sa.CheckConstraint(
            "operation = 'CREATE' OR base_artifact_id IS NOT NULL",
            name="ck_artifact_draft_operation_base",
        ),
        # Unique constraints
        sa.UniqueConstraint(
            "project_id", "artifact_type", "canonical_key",
            name="uq_artifact_draft_type_canonical_key",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_artifact_draft_project",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["domain_profile.id"],
            name="fk_artifact_draft_profile",
        ),
        sa.ForeignKeyConstraint(
            ["base_artifact_id"],
            ["artifact.id"],
            name="fk_artifact_draft_base_artifact",
        ),
    )
    # Partial unique: (project_id, artifact_code) WHERE NOT NULL
    op.create_index(
        "uq_artifact_draft_code",
        "artifact_draft",
        ["project_id", "artifact_code"],
        unique=True,
        postgresql_where=sa.text("artifact_code IS NOT NULL"),
    )
    # Indexes
    op.create_index(
        "ix_artifact_draft_project_stage_status",
        "artifact_draft",
        ["project_id", "stage", "status"],
    )
    op.create_index(
        "ix_artifact_draft_base_artifact",
        "artifact_draft",
        ["base_artifact_id"],
    )
    # GIN indexes for candidate impact checking
    for col in _REF_ARRAY_COLS:
        op.create_index(
            f"ix_artifact_draft_{col}_gin",
            "artifact_draft",
            [col],
            postgresql_using="gin",
        )

    # ------------------------------------------------------------------
    # project_change
    # ------------------------------------------------------------------
    op.create_table(
        "project_change",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("request_content", sa.Text(), nullable=False),
        sa.Column(
            "target_artifact_codes",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "base_baselines",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.VARCHAR(24),
            nullable=False,
        ),
        sa.Column(
            "impact",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "decision",
            sa.VARCHAR(16),
            nullable=True,
        ),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decision_artifact_code", sa.VARCHAR(40), nullable=True,
        ),
        sa.Column(
            "decision_git_commit_sha", sa.VARCHAR(64), nullable=True,
        ),
        sa.Column(
            "applied_baselines",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id", name="pk_project_change"),
        # CHECK constraints
        sa.CheckConstraint(
            "status IN ("
            "'PROPOSED', 'ANALYZING', 'WAITING_FOR_HUMAN', "
            "'APPROVED', 'APPLYING', 'APPLIED', "
            "'REJECTED', 'WITHDRAWN', 'FAILED')",
            name="ck_project_change_status",
        ),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN "
            "('APPROVED', 'REJECTED', 'WITHDRAWN')",
            name="ck_project_change_decision",
        ),
        # Terminal states must have decision, decider, decided_at, and
        # decision_git_commit_sha.
        sa.CheckConstraint(
            "(status NOT IN ('APPLIED', 'REJECTED', 'WITHDRAWN')) OR ("
            "decision IS NOT NULL AND "
            "decided_by_user_id IS NOT NULL AND "
            "decided_at IS NOT NULL AND "
            "decision_git_commit_sha IS NOT NULL)",
            name="ck_project_change_terminal_decision",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name="fk_project_change_project",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["project_message.id"],
            name="fk_project_change_source_message",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["app_user.id"],
            name="fk_project_change_requested_by",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["app_user.id"],
            name="fk_project_change_decided_by",
        ),
    )
    # Indexes
    op.create_index(
        "ix_project_change_project_created",
        "project_change",
        ["project_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_project_change_project_status_updated",
        "project_change",
        ["project_id", "status", "updated_at"],
    )
    # GIN index for target_artifact_codes queries
    op.create_index(
        "ix_project_change_target_codes_gin",
        "project_change",
        ["target_artifact_codes"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("project_change")
    op.drop_table("artifact_draft")
    op.drop_table("artifact")
