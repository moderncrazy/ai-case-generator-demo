import sys
from datetime import UTC, datetime
from pathlib import Path

# The V2 runtime is a top-level `src` package without an editable install, so
# expose the repository root when pytest is invoked from the worktree.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.shared.time.clock import Clock, SystemClock


def test_system_clock_now_is_utc_aware() -> None:
    assert SystemClock().now().tzinfo is UTC


def test_system_clock_now_returns_datetime() -> None:
    assert isinstance(SystemClock().now(), datetime)


def test_system_clock_satisfies_clock_protocol() -> None:
    def now_from(clock: Clock) -> datetime:
        return clock.now()

    assert now_from(SystemClock()).tzinfo is UTC
