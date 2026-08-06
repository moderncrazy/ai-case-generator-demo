"""Integration test fixtures for PostgreSQL schema verification.

Uses a synchronous engine so that ``greenlet`` is not required for
constraint-level integration tests.  The application-layer async engine
in ``src.persistence.postgres`` remains the canonical runtime path.
"""

import os
from collections.abc import Generator

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL environment variable is not set")
    return url


@pytest.fixture(scope="session")
def alembic_config(test_database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_database_url)
    return cfg


@pytest.fixture(scope="session")
def _run_migrations(alembic_config: Config) -> None:
    """Run alembic migrations once per test session."""
    upgrade(alembic_config, "head")


@pytest.fixture(scope="session")
def engine(test_database_url: str, _run_migrations: None) -> Engine:
    """Session-scoped sync engine bound to the migrated test database."""
    eng = create_engine(test_database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def migrated_db(engine: Engine) -> Generator[Session, None, None]:
    """Provide a session connected to the migrated test database.

    Each test runs inside a transaction that is rolled back, so test
    functions are isolated from each other.
    """
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    session.begin()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
