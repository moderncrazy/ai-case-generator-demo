"""Contract tests for Redis key builders.

Verifies that every key builder from ``src.integrations.redis.keys``
produces the exact shape and TTL prescribed by the database design
section 13.
"""

from __future__ import annotations

import pytest

from src.integrations.redis.keys import (
    conversation_owner_key,
    events_channel,
    session_key,
    user_cache_key,
    wakeup_channel,
)


class TestSessionKey:
    def test_format_is_session_colon_sha256(self) -> None:
        key = session_key(token_hash="abc123def456")
        assert key == "session:abc123def456"

    def test_ttl_is_7200_seconds(self) -> None:
        assert session_key.ttl_seconds == 7200


class TestUserCacheKey:
    def test_format_is_user_colon_user_id(self) -> None:
        key = user_cache_key(user_id="550e8400-e29b-41d4-a716-446655440000")
        assert key == "user:550e8400-e29b-41d4-a716-446655440000"

    def test_ttl_is_7200_seconds(self) -> None:
        assert user_cache_key.ttl_seconds == 7200


class TestConversationOwnerKey:
    def test_format_with_project_id(self) -> None:
        key = conversation_owner_key(
            project_id="660e8400-e29b-41d4-a716-446655440001"
        )
        assert key == "project:conversation-owner:660e8400-e29b-41d4-a716-446655440001"

    def test_ttl_is_300_seconds(self) -> None:
        assert conversation_owner_key.ttl_seconds == 300


class TestEventsChannel:
    def test_channel_format(self) -> None:
        channel = events_channel(
            project_id="770e8400-e29b-41d4-a716-446655440002"
        )
        assert channel == "project:events:770e8400-e29b-41d4-a716-446655440002"


class TestWakeupChannel:
    def test_channel_is_delivery_wakeup(self) -> None:
        assert wakeup_channel() == "delivery:wakeup"


class TestKeyUniqueness:
    """Ensure different inputs produce different keys."""

    def test_session_keys_differ_by_hash(self) -> None:
        k1 = session_key(token_hash="aaa")
        k2 = session_key(token_hash="bbb")
        assert k1 != k2

    def test_user_cache_keys_differ_by_user_id(self) -> None:
        k1 = user_cache_key(user_id="aaa")
        k2 = user_cache_key(user_id="bbb")
        assert k1 != k2

    def test_conversation_owner_keys_differ_by_project_id(self) -> None:
        k1 = conversation_owner_key(project_id="p1")
        k2 = conversation_owner_key(project_id="p2")
        assert k1 != k2

    def test_events_channels_differ_by_project_id(self) -> None:
        c1 = events_channel(project_id="p1")
        c2 = events_channel(project_id="p2")
        assert c1 != c2

    def test_wakeup_channel_is_constant(self) -> None:
        assert wakeup_channel() == wakeup_channel()
