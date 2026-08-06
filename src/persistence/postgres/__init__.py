"""PostgreSQL persistence infrastructure for Platform V2.

Exports the shared :class:`Base`, engine factory, and async session factory
consumed by domain modules and integration tests.
"""

from src.persistence.postgres.base import Base
from src.persistence.postgres.session import create_engine, session_factory

__all__ = ["Base", "create_engine", "session_factory"]
