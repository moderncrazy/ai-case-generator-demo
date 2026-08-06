"""Async engine and session factories.

Domain modules receive an ``async_sessionmaker`` via dependency injection;
they never import or configure the raw engine directly.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.bootstrap.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from runtime settings.

    Uses ``postgresql+psycopg://`` as the async driver.  The database URL
    is read from ``settings.database_url`` which holds a ``SecretStr``.
    """
    url = settings.database_url.get_secret_value()  # type: ignore[union-attr]
    return create_async_engine(
        url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )


def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Return a configured ``async_sessionmaker`` for the given engine."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
