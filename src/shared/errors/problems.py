"""Serializable error problem payloads shared across V2 boundaries."""

from pydantic import BaseModel, Field


class Problem(BaseModel):
    """A normalized, serializable error payload."""

    code: str
    status: int
    title: str
    detail: str
    retryable: bool
    context: dict[str, object] = Field(default_factory=dict)
