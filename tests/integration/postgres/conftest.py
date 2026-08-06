"""Integration test fixtures for PostgreSQL schema verification.

The ``migrated_db`` sync fixture supports constraint-level DDL tests.
The ``async_session`` fixture provides a real ``create_async_engine`` /
``session_factory`` round-trip for runtime-path verification.

Mutation tests require ``TEST_DATABASE_URL`` to target the disposable
database ``ai_case_v2_test`` — production data is never touched.
"""

import os
from collections.abc import AsyncGenerator, Generator
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from src.bootstrap.settings import Settings
from src.persistence.postgres.session import (
    create_engine as app_create_engine,
    session_factory as app_session_factory,
)


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def _require_disposable_test_db(url: str) -> None:
    """Fail fast if the URL does not target the disposable test database."""
    if not url:
        pytest.fail("TEST_DATABASE_URL environment variable is not set")
    parsed = urlparse(url)
    dbname = parsed.path.lstrip("/")
    if dbname != "ai_case_v2_test":
        pytest.fail(
            f"TEST_DATABASE_URL must target 'ai_case_v2_test', "
            f"got {dbname!r}"
        )


# ---------------------------------------------------------------------------
# session-scoped resources
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "")
    _require_disposable_test_db(url)
    return url


@pytest.fixture(scope="session")
def alembic_config(test_database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_database_url)
    return cfg


@pytest.fixture(scope="session")
def _run_migrations(alembic_config: Config) -> None:
    """Run alembic migrations once per test session.

    The disposable test database is reset to ``base`` first, then rebuilt
    to ``head``, so committed fixtures from a previous run cannot leak
    into this session.  This makes the integration suite repeatably
    isolated: the same full suite passes twice consecutively without a
    manual Alembic reset between runs.
    """
    downgrade(alembic_config, "base")
    upgrade(alembic_config, "head")


# ---------------------------------------------------------------------------
# sync fixtures — constraint DDL tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sync_engine(test_database_url: str, _run_migrations: None) -> Generator[Engine, None, None]:
    """Session-scoped sync engine bound to the migrated test database."""
    eng = create_engine(test_database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def migrated_db(sync_engine: Engine) -> Generator[Session, None, None]:
    """Provide a sync session with per-test transaction rollback."""
    SessionLocal = sessionmaker(bind=sync_engine)
    session = SessionLocal()
    session.begin()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# async fixtures — runtime-path verification
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _settings_for_test(test_database_url: str) -> Settings:
    """Settings wired to the disposable test database."""
    return Settings(
        database_url=test_database_url,
        environment="local",
        process_role="api",
    )


@pytest_asyncio.fixture
async def async_engine(
    _settings_for_test: Settings, _run_migrations: None
) -> AsyncGenerator[AsyncEngine, None]:
    """Application ``create_engine(settings)`` async engine bound to the test database."""
    eng = app_create_engine(_settings_for_test)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def async_session(
    async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Application ``session_factory(engine)`` session for a single test transaction."""
    maker = app_session_factory(async_engine)
    async with maker() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ---------------------------------------------------------------------------
# shared helper fixture (sync)
# ---------------------------------------------------------------------------


@pytest.fixture
def migrated_db_user(migrated_db: Session) -> str:
    """Insert a single user and return its UUID string for FK references."""
    from uuid import uuid4

    uid = uuid4()
    migrated_db.execute(
        text(
            """
            INSERT INTO app_user
              (id, username, display_name, password_hash, password_salt,
               system_role, status, must_change_password, created_at, updated_at)
            VALUES
              (:id, :un, 'Fixture User', 'hash', decode('aa','hex'),
               'ADMIN', 'ACTIVE', false, now(), now())
            """
        ),
        {"id": uid, "un": f"fixture-{uid.hex[:8]}"},
    )
    return str(uid)
