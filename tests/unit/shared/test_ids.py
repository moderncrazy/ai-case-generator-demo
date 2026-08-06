import sys
from pathlib import Path
from uuid import UUID

# The V2 runtime is a top-level `src` package without an editable install, so
# expose the repository root when pytest is invoked from the worktree.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.shared.ids.types import new_uuid


def test_new_uuid_returns_uuid() -> None:
    assert isinstance(new_uuid(), UUID)


def test_generated_ids_are_unique() -> None:
    assert new_uuid() != new_uuid()
    assert new_uuid() != new_uuid()
