"""Shared SQLAlchemy declarative base for all V2 business tables.

Every ORM model under ``src/modules/`` and ``src/integrations/models/``
inherits from this base so that Alembic's ``target_metadata`` captures the
full schema.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for Platform V2 business tables."""
