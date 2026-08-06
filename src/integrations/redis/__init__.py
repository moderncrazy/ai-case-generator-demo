"""Platform V2 Redis integration.

Redis is used as reconstructible infrastructure for short-lived
coordination (sessions, cache, occupancy locks, Pub/Sub) and must not
become a source of project truth.
"""

from src.integrations.redis.client import RedisRuntime
from src.integrations.redis.keys import (
    conversation_owner_key,
    events_channel,
    session_key,
    user_cache_key,
    wakeup_channel,
)
from src.integrations.redis.scripts import (
    NOT_OWNER,
    OCCUPIED,
    RELEASED,
    OccupancyManager,
    OccupancyResult,
)

__all__ = [
    "RedisRuntime",
    "session_key",
    "user_cache_key",
    "conversation_owner_key",
    "events_channel",
    "wakeup_channel",
    "OccupancyManager",
    "OccupancyResult",
    "NOT_OWNER",
    "OCCUPIED",
    "RELEASED",
]
