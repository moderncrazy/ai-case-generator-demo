from uuid import UUID

from src.shared.ids.types import new_uuid


def test_new_uuid_returns_uuid() -> None:
    assert isinstance(new_uuid(), UUID)


def test_generated_ids_are_unique() -> None:
    assert new_uuid() != new_uuid()
    assert new_uuid() != new_uuid()
