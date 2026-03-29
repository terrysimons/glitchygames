"""Abstract interface for animated sprites.

This module contains the AnimatedSpriteInterface ABC that defines the
contract for all animated sprite implementations.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Self

from .constants import DEFAULT_FILE_FORMAT

if TYPE_CHECKING:
    from .frame import SpriteFrame


class AnimatedSpriteInterface(abc.ABC):
    """A formal interface for animated sprites."""

    # Animation state properties (read-only)
    @property
    @abc.abstractmethod
    def current_animation(self: Self) -> str:
        """Return the current animation name."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def current_frame(self: Self) -> int:
        """Return the current frame index."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_playing(self: Self) -> bool:
        """Return whether animation is currently playing."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_looping(self: Self) -> bool:
        """Return whether current animation loops."""
        raise NotImplementedError

    # Animation information properties
    @property
    @abc.abstractmethod
    def frames(self: Self) -> dict[str, list[SpriteFrame]]:
        """Return all frames for all animations (including interpolated)."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def animations(self: Self) -> dict[str, dict[str, object]]:
        """Return animation metadata for all animations."""
        raise NotImplementedError

    # Direct animation metadata access (current animation)
    @property
    @abc.abstractmethod
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def loop(self: Self) -> bool:
        """Return whether the current animation loops."""
        raise NotImplementedError

    # Animation control methods
    @abc.abstractmethod
    def play(self: Self, animation_name: str | None = None) -> None:
        """Start playing the specified animation (or current if None)."""
        raise NotImplementedError

    @abc.abstractmethod
    def pause(self: Self) -> None:
        """Pause the current animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self: Self) -> None:
        """Stop the current animation and reset to frame 0."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_frame(self: Self, frame_index: int) -> None:
        """Set the current frame index."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_animation(self: Self, animation_name: str) -> None:
        """Set the current animation."""
        raise NotImplementedError

    # Animation data methods
    @abc.abstractmethod
    def add_animation(
        self: Self,
        name: str,
        frames: list[SpriteFrame],
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Add a new animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def remove_animation(self: Self, name: str) -> None:
        """Remove an animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_frame(self: Self, animation_name: str, frame_index: int) -> SpriteFrame:
        """Get a specific frame from a specific animation."""
        raise NotImplementedError

    # File I/O methods
    @abc.abstractmethod
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from a file."""
        raise NotImplementedError

    @abc.abstractmethod
    def save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save animated sprite to a file."""
        raise NotImplementedError

    # Update method for animation timing
    @abc.abstractmethod
    def update(self: Self, dt: float) -> None:
        """Update animation timing."""
        raise NotImplementedError
