"""Data models for the Bitmappy pixel art editor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class MockEvent(BaseModel):
    """Lightweight mock event for internal file-loading calls."""

    text: str


class GGUnhandledMenuItemError(Exception):
    """Glitchy Games Unhandled Menu Item Error."""


@dataclass
class AIRequest:
    """Data structure for AI sprite generation requests."""

    prompt: str
    request_id: str
    messages: list[dict[str, str]]


@dataclass
class AIResponse:
    """Data structure for AI responses."""

    content: str | None
    error: str | None = None


@dataclass
class AIRequestState:
    """Tracks state of an AI request including retries."""

    original_prompt: str
    retry_count: int = 0
    last_error: str | None = None
    training_examples: list[dict[str, Any]] | None = None
    conversation_history: list[dict[str, str]] | None = None  # For multi-turn refinement
    last_sprite_content: str | None = None  # Last successfully generated sprite
