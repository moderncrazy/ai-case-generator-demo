"""Typed Redis key builders for V2 namespace isolation.

Every key follows the exact shapes and TTLs prescribed by
`docs/database/platform-v2-database-design.md` section 13.

All keys are flat strings — no JSON structures are embedded in key
names.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Session — 13.1
# ---------------------------------------------------------------------------


def session_key(*, token_hash: str) -> str:
    """Build a session key from the SHA-256 hex digest of the bearer token.

    Shape: ``session:<sha256(token)>``
    TTL:   7200 seconds sliding
    Value: ``{ user_id, csrf_hash }``
    """
    return f"session:{token_hash}"


session_key.ttl_seconds = 7200  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# User cache — 13.2
# ---------------------------------------------------------------------------


def user_cache_key(*, user_id: str) -> str:
    """Build a user-cache key from a user UUID.

    Shape: ``user:<user_id>``
    TTL:   7200 seconds sliding
    Value: ``{ id, username, display_name, system_role, status,
             must_change_password }``
    """
    return f"user:{user_id}"


user_cache_key.ttl_seconds = 7200  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Project conversation owner — 13.3
# ---------------------------------------------------------------------------


def conversation_owner_key(*, project_id: str) -> str:
    """Build a project conversation-owner key from a project UUID.

    Shape: ``project:conversation-owner:<project_id>``
    TTL:   300 seconds sliding or worker renewal
    Value: ``user_id``
    """
    return f"project:conversation-owner:{project_id}"


conversation_owner_key.ttl_seconds = 300  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Online events — 13.4
# ---------------------------------------------------------------------------


def events_channel(*, project_id: str) -> str:
    """Build a Pub/Sub channel name for per-project online event notifications.

    Shape: ``project:events:<project_id>``
    Type:  Pub/Sub channel
    """
    return f"project:events:{project_id}"


# ---------------------------------------------------------------------------
# Worker wakeup — 13.5
# ---------------------------------------------------------------------------


def wakeup_channel() -> str:
    """Return the global worker-wakeup Pub/Sub channel name.

    Shape: ``delivery:wakeup``
    Type:  Pub/Sub channel
    """
    return "delivery:wakeup"
