"""Clock abstractions for timezone-aware time sources."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """A time source that returns timezone-aware UTC datetimes."""

    def now(self) -> datetime:
        raise NotImplementedError


class SystemClock:
    """Production clock backed by the system time."""

    def now(self) -> datetime:
        return datetime.now(UTC)
