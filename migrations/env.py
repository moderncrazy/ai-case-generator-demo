"""Alembic environment configuration for PostgreSQL migrations.

Reads ``PLATFORM_DATABASE_URL`` from the process environment.  Callers
(including the integration-test conftest) may override the URL via
``alembic_cfg.set_main_option("sqlalchemy.url", url)`` before invoking
``upgrade`` or ``downgrade``.

Uses a synchronous engine so that ``greenlet`` is not required at the
migration layer.  The async engine factory in ``src.persistence.postgres``
remains the canonical entrypoint for application code.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from src.persistence.postgres.base import Base

# Import all model modules so their table metadata registers with Base
# before Alembic inspects target_metadata.
import src.modules.access.models  # noqa: E402, F401  # AppUser, LoginLog
import src.modules.profiles.models  # noqa: E402, F401  # DomainProfile, …
import src.integrations.models.profile_model  # noqa: E402, F401  # ModelProfile
import src.modules.projects.models  # noqa: E402, F401  # Project, ProjectMember
import src.modules.conversation.models  # noqa: E402, F401  # ProjectMessage
import src.modules.delivery.models  # noqa: E402, F401  # DeliveryRun, ProjectStage
import src.modules.files.models  # noqa: E402, F401  # ProjectFile
import src.modules.artifacts.models  # noqa: E402, F401  # Artifact, ArtifactDraft
import src.modules.changes.models  # noqa: E402, F401  # ProjectChange

# ---------------------------------------------------------------------------
# Alembic Config object (read from alembic.ini)
# ---------------------------------------------------------------------------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    """Resolve the database URL from config option or environment variable."""
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    url = os.environ.get("PLATFORM_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "PLATFORM_DATABASE_URL is not set in the environment "
            "and sqlalchemy.url is not configured in alembic.ini"
        )
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without connecting)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous engine."""
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
