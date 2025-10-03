#!/usr/bin/env python3
"""
Animated sprite classes for GlitchyGames.

This module contains the animated sprite implementation that extends the
basic sprite functionality to support multi-frame animations with flexible
timing and playback control.
"""

import abc
import logging
from typing import Any, Self

import pygame

LOG = logging.getLogger("game.sprites.animated")


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
    def frames(self: Self) -> dict[str, list["SpriteFrame"]]:
        """Return all frames for all animations (including interpolated)."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def animations(self: Self) -> dict[str, dict]:
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
    def add_animation(self: Self, name: str, frames: list["SpriteFrame"], metadata: dict | None = None) -> None:
        """Add a new animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def remove_animation(self: Self, name: str) -> None:
        """Remove an animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_frame(self: Self, animation_name: str, frame_index: int) -> "SpriteFrame":
        """Get a specific frame from a specific animation."""
        raise NotImplementedError

    # File I/O methods
    @abc.abstractmethod
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from a file."""
        raise NotImplementedError

    @abc.abstractmethod
    def save(self: Self, filename: str, file_format: str = "ini") -> None:
        """Save animated sprite to a file."""
        raise NotImplementedError

    # Update method for animation timing
    @abc.abstractmethod
    def update(self: Self, dt: float) -> None:
        """Update animation timing."""
        raise NotImplementedError


class SpriteFrame:
    """Represents a single frame of an animated sprite."""
    
    def __init__(self, surface: pygame.Surface, duration: float = 0.5):
        """Initialize a sprite frame.
        
        Args:
            surface: The pygame surface for this frame
            duration: How long this frame should be displayed (in seconds)
        """
        self._image = surface
        self._rect = pygame.Rect((0, 0), surface.get_size())
        self.duration = duration
    
    @property
    def image(self) -> pygame.Surface:
        """Return the flattened sprite stack image."""
        return self._image
    
    @image.setter
    def image(self, new_image: pygame.Surface) -> None:
        """Set the image."""
        self._image = new_image
    
    @property
    def rect(self) -> pygame.Rect:
        """Return the sprite stack pygame.Rect."""
        return self._rect
    
    @rect.setter
    def rect(self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        self._rect = new_rect
    
    def __getitem__(self, index: int) -> "SpriteFrame":
        """Return a sprite from the stack."""
        return self
    
    def get_size(self) -> tuple[int, int]:
        """Return the size of the surface."""
        return self._image.get_size()
    
    def get_alpha(self) -> int:
        """Return the alpha value of the surface."""
        return self._image.get_alpha()
    
    def get_colorkey(self) -> int | None:
        """Return the colorkey of the surface."""
        return self._image.get_colorkey()
    
    def __repr__(self) -> str:
        """String representation of the frame."""
        return f"SpriteFrame(size={self._image.get_size()}, duration={self.duration})"


class AnimatedSprite(AnimatedSpriteInterface):
    """A prototype Sprite Animation class."""

    def __init__(self: Self, filename: str | None = None) -> None:
        """Initialize the Sprite Animation prototype."""
        super().__init__()
        self._animations = {}  # animation_name -> list of frames
        self._current_animation = ""
        self._current_frame = 0
        self._is_playing = False
        self._is_looping = False
        self._frame_timer = 0.0

        if filename:
            self.load(filename)

    def __getitem__(self: Self, animation_name: str) -> "SpriteFrame":
        """Return the current frame of the specified animation."""
        if animation_name in self._animations and self._animations[animation_name]:
            return self._animations[animation_name][self._current_frame]
        return None

    def get_current_frame(self: Self) -> "SpriteFrame":
        """Return the current frame as a "SpriteFrame"."""
        if self._current_animation in self._animations and self._animations[self._current_animation]:
            return self._animations[self._current_animation][self._current_frame]
        return None

    # Sprite properties - return current frame's surface information
    @property
    def image(self: Self) -> pygame.Surface:
        """Return current frame's surface."""
        frame = self.get_current_frame()
        if frame:
            return frame.surface
        return pygame.Surface((32, 32))  # Default empty surface

    @property
    def rect(self: Self) -> pygame.Rect:
        """Return current frame's rect."""
        frame = self.get_current_frame()
        if frame:
            return frame.rect
        return pygame.Rect(0, 0, 32, 32)  # Default rect

    # Animation state properties (read-only)
    @property
    def current_animation(self: Self) -> str:
        """Return the current animation name."""
        return self._current_animation

    @property
    def current_frame(self: Self) -> int:
        """Return the current frame index."""
        return self._current_frame

    @property
    def is_playing(self: Self) -> bool:
        """Return whether animation is currently playing."""
        return self._is_playing

    @property
    def is_looping(self: Self) -> bool:
        """Return whether current animation loops."""
        return self._is_looping

    @property
    def frames(self: Self) -> dict[str, list["SpriteFrame"]]:
        """Return all frames for all animations."""
        return self._animations.copy()

    @property
    def animations(self: Self) -> dict[str, dict]:
        """Return animation metadata for all animations."""
        # For now, return empty metadata - can be extended later
        return {name: {} for name in self._animations.keys()}

    @property
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        if self._current_animation in self._animations and self._animations[self._current_animation]:
            frame = self._animations[self._current_animation][self._current_frame]
            return frame.duration
        return 0.5  # Default frame interval

    @property
    def loop(self: Self) -> bool:
        """Return whether the current animation loops."""
        return self._is_looping

    @property
    def frame_count(self: Self) -> int:
        """Return the number of frames in the current animation."""
        if self._current_animation in self._animations:
            return len(self._animations[self._current_animation])
        return 0

    @property
    def next_animation(self: Self) -> str:
        """Return the next animation in the sequence."""
        if not self._animations:
            return ""
        animation_names = list(self._animations.keys())
        if not animation_names:
            return ""
        current_index = animation_names.index(self._current_animation) if self._current_animation in animation_names else -1
        next_index = (current_index + 1) % len(animation_names)
        return animation_names[next_index]

    # Animation control methods
    def play(self: Self, animation_name: str | None = None) -> None:
        """Start playing the specified animation (or current if None)."""
        if animation_name:
            self.set_animation(animation_name)
        self._is_playing = True
        self._frame_timer = 0.0

    def play_animation(self: Self, animation_name: str | None = None) -> None:
        """Alias for play method for backwards compatibility."""
        self.play(animation_name)

    def pause(self: Self) -> None:
        """Pause the current animation."""
        self._is_playing = False

    def stop(self: Self) -> None:
        """Stop the current animation and reset to frame 0."""
        self._is_playing = False
        self._current_frame = 0
        self._frame_timer = 0.0

    def set_frame(self: Self, frame_index: int) -> None:
        """Set the current frame index."""
        if self._current_animation in self._animations:
            max_frames = len(self._animations[self._current_animation])
            if 0 <= frame_index < max_frames:
                self._current_frame = frame_index
                self._frame_timer = 0.0

    def set_animation(self: Self, animation_name: str) -> None:
        """Set the current animation."""
        if animation_name in self._animations:
            self._current_animation = animation_name
            self._current_frame = 0
            self._frame_timer = 0.0

    # Animation data methods
    def add_animation(self: Self, name: str, frames: list["SpriteFrame"], metadata: dict | None = None) -> None:
        """Add a new animation."""
        self._animations[name] = frames.copy()
        if not self._current_animation:
            self._current_animation = name

    def remove_animation(self: Self, name: str) -> None:
        """Remove an animation."""
        if name in self._animations:
            del self._animations[name]
            if self._current_animation == name:
                # Switch to first available animation
                if self._animations:
                    self._current_animation = list(self._animations.keys())[0]
                    self._current_frame = 0
                else:
                    self._current_animation = ""
                    self._current_frame = 0

    def get_frame(self: Self, animation_name: str, frame_index: int) -> "SpriteFrame":
        """Get a specific frame from a specific animation."""
        if animation_name in self._animations:
            frames = self._animations[animation_name]
            if 0 <= frame_index < len(frames):
                return frames[frame_index]
        return None

    # File I/O methods
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from a file."""
        # For now, raise an error since AnimatedSprite load is not implemented
        raise NotImplementedError("AnimatedSprite load functionality not yet implemented")

    def save(self: Self, filename: str, file_format: str = "ini") -> None:
        """Save animated sprite to a file."""
        # For now, raise an error since AnimatedSprite save is not implemented
        raise NotImplementedError("AnimatedSprite save functionality not yet implemented")

    def _save(self: Self, filename: str, file_format: str = "ini") -> None:
        """Internal save method for animated sprites."""
        # This will be implemented when we add file format support
        raise NotImplementedError("AnimatedSprite save functionality not yet implemented")

    def update(self: Self, dt: float) -> None:
        """Update animation timing."""
        if not self._is_playing or not self._current_animation:
            return

        if self._current_animation not in self._animations:
            return

        frames = self._animations[self._current_animation]
        if not frames:
            return

        # Update frame timer
        self._frame_timer += dt
        current_frame = self.get_current_frame()
        
        if current_frame and self._frame_timer >= current_frame.duration:
            # Move to next frame
            self._frame_timer = 0.0
            self._current_frame += 1
            
            # Check if we've reached the end
            if self._current_frame >= len(frames):
                if self._is_looping:
                    self._current_frame = 0
                else:
                    self._current_frame = len(frames) - 1
                    self._is_playing = False
