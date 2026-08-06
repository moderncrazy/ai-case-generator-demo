"""Alembic target-metadata parity tests (Finding 2).

``migrations/env.py`` must register every business model on
``Base.metadata`` so the 16 approved V2 tables are fully represented.
This module proves:

- ``env.py`` imports every business model module (read from source, so the
  check passes without entering an Alembic context).
- ``Base.metadata`` after importing those modules matches the tables that
  ``alembic upgrade head`` creates in the disposable database.

The second assertion is the stronger one: it compares the ORM metadata
against the *migrated* database, so any table created by a migration but
missing from the metadata (or vice versa) fails loudly.
"""

from pathlib import Path

from sqlalchemy import text

# The 16 approved business tables (alembic_version and the langgraph
# schema are excluded by construction).
EXPECTED_BUSINESS_TABLES = {
    # 0001 — access / profiles / models
    "app_user",
    "login_log",
    "domain_profile",
    "domain_profile_draft",
    "domain_profile_version",
    "profile_migration",
    "model_profile",
    # 0002 — projects
    "project",
    "project_member",
    # 0003 — conversation / delivery / files
    "project_message",
    "delivery_run",
    "project_stage",
    "project_file",
    # 0004 — artifacts / changes
    "artifact",
    "artifact_draft",
    "project_change",
}

# Every model module that ``migrations/env.py`` must import so
# ``Base.metadata`` carries the full V2 schema.
REQUIRED_MODEL_IMPORTS = [
    "src.modules.access.models",
    "src.modules.profiles.models",
    "src.integrations.models.profile_model",
    "src.modules.projects.models",
    "src.modules.conversation.models",
    "src.modules.delivery.models",
    "src.modules.files.models",
    "src.modules.artifacts.models",
    "src.modules.changes.models",
]


def test_env_imports_all_model_modules() -> None:
    """``migrations/env.py`` must import every business model module.

    Reading the module source (rather than importing it) keeps the check
    independent of an Alembic context, which is unavailable in pytest.
    """
    repo_root = Path(__file__).resolve().parents[3]
    env_path = repo_root / "migrations" / "env.py"
    source = env_path.read_text(encoding="utf-8")
    for module in REQUIRED_MODEL_IMPORTS:
        assert module in source, (
            f"migrations/env.py must import {module} so the model is "
            f"registered on Base.metadata"
        )


def _all_model_metadata():
    """Import every business model module and return ``Base.metadata``."""
    import src.integrations.models.profile_model  # noqa: F401
    import src.modules.access.models  # noqa: F401
    import src.modules.artifacts.models  # noqa: F401
    import src.modules.changes.models  # noqa: F401
    import src.modules.conversation.models  # noqa: F401
    import src.modules.delivery.models  # noqa: F401
    import src.modules.files.models  # noqa: F401
    import src.modules.profiles.models  # noqa: F401
    import src.modules.projects.models  # noqa: F401
    from src.persistence.postgres.base import Base

    return Base


def test_metadata_registers_all_business_tables() -> None:
    """After importing every model module, all 16 approved tables are on
    ``Base.metadata``."""
    base = _all_model_metadata()
    registered = set(base.metadata.tables)
    missing = EXPECTED_BUSINESS_TABLES - registered
    assert not missing, (
        f"Base.metadata is missing approved tables: {sorted(missing)}"
    )


def test_metadata_matches_migrated_database(sync_engine) -> None:
    """``Base.metadata`` tables must equal the ``alembic upgrade head``
    result in the disposable database.

    Any table created by a migration but absent from the metadata (or
    registered in metadata but not created) fails the comparison — so a
    future migration that adds a table without registering its model is
    caught here.
    """
    base = _all_model_metadata()
    registered = set(base.metadata.tables)

    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        db_tables = {row[0] for row in rows}

    db_tables -= {"alembic_version"}
    assert registered == db_tables, (
        f"Metadata/Db mismatch: "
        f"in metadata only: {sorted(registered - db_tables)}, "
        f"in db only: {sorted(db_tables - registered)}"
    )
