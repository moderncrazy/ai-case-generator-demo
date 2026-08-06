"""Application-generated UUID identifier primitives."""

from uuid import UUID, uuid4


def new_uuid() -> UUID:
    """Return a new application-generated UUID4 identifier."""
    return uuid4()
