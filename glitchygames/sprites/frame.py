"""Frame management classes for sprite animation.

This module contains:
- FrameManager: Centralized frame state management with observer pattern
- SpriteFrame: Represents a single frame of an animated sprite
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import pygame

# Imported under another name so it does not shadow SpriteFrame.opaque_bounds in reading
from glitchygames.collision.bounds import opaque_bounds as measure_opaque_bounds
from glitchygames.color import (
    RGBA_COMPONENT_COUNT,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.sprites.animated import AnimatedSprite


class FrameManager:
    """Centralized frame state management for animation system."""

    def __init__(self, animated_sprite: AnimatedSprite) -> None:
        """Initialize with reference to the animated sprite."""
        self.animated_sprite = animated_sprite
        self._current_animation = ''
        self._current_frame = 0
        self._observers: list[object] = []

    def add_observer(self, observer: object) -> None:
        """Add an observer that will be notified of frame changes."""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: object) -> None:
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(
        self,
        change_type: str,
        old_value: str | int,
        new_value: str | int,
    ) -> None:
        """Notify all observers of a frame change."""
        for observer in self._observers:
            on_frame_change = getattr(observer, 'on_frame_change', None)
            if callable(on_frame_change):
                on_frame_change(change_type, old_value, new_value)

    @property
    def current_animation(self) -> str:
        """The current animation name."""
        return self._current_animation

    @current_animation.setter
    def current_animation(self, value: str) -> None:
        """Set the current animation and notify observers."""
        if value != self._current_animation:
            old_value = self._current_animation
            self._current_animation = value
            self._current_frame = 0  # Reset frame when animation changes
            self.notify_observers('animation', old_value, value)

    @property
    def current_frame(self) -> int:
        """The current frame index."""
        return self._current_frame

    @current_frame.setter
    def current_frame(self, value: int) -> None:
        """Set the current frame and notify observers."""
        if value != self._current_frame:
            old_value = self._current_frame
            self._current_frame = value
            self.notify_observers('frame', old_value, value)

    def set_frame(self, frame_index: int) -> bool:
        """Set the current frame with bounds checking.

        Returns:
            bool: True if the frame was set successfully, False otherwise.

        """
        animation_data = self.animated_sprite.animation_data
        if self._current_animation in animation_data:
            max_frames = len(animation_data[self._current_animation])
            if 0 <= frame_index < max_frames:
                self.current_frame = frame_index
                return True
        return False

    def set_animation(self, animation_name: str) -> bool:
        """Set the current animation with validation.

        Returns:
            bool: True if the animation was set successfully, False otherwise.

        """
        if animation_name in self.animated_sprite.animation_data:
            self.current_animation = animation_name
            return True
        return False

    def get_frame_data(self) -> SpriteFrame | None:
        """Get the current frame data.

        Returns:
            The frame data for the current animation and frame, or None if not available.

        """
        animation_data = self.animated_sprite.animation_data
        if self._current_animation in animation_data and self._current_frame < len(
            animation_data[self._current_animation],
        ):
            return animation_data[self._current_animation][self._current_frame]
        return None

    def get_frame_count(self) -> int:
        """Get the number of frames in the current animation.

        Returns:
            int: The number of frames, or 0 if no current animation.

        """
        animation_data = self.animated_sprite.animation_data
        if self._current_animation in animation_data:
            return len(animation_data[self._current_animation])
        return 0


class SpriteFrame:
    """Represents a single frame of an animated sprite."""

    # Presence-based "image is stale" flag used by the Bitmappy canvas drag fast path
    # (glitchygames/bitmappy/animated_canvas.py). It is intentionally declared without a
    # value: the attribute only exists while ``pixels`` has been edited ahead of ``_image``,
    # and callers test for it with ``hasattr`` and clear it with ``del``. Leaving it
    # uninitialized is therefore deliberate.
    _image_stale: bool  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        surface: pygame.Surface,
        duration: float = 0.5,
        hitbox: pygame.Rect | None = None,
    ) -> None:
        """Initialize a sprite frame.

        Args:
            surface: The pygame surface for this frame
            duration: How long this frame should be displayed (in seconds)
            hitbox: Optional collision hitbox rect (offset from frame origin).
                    If None, hitbox defaults to the full frame dimensions.

        """
        self._image = surface
        self._rect = pygame.Rect((0, 0), surface.get_size())
        self.duration = duration
        self.pixels: list[tuple[int, ...]] = []
        self._hitbox: pygame.Rect | None = hitbox
        # (surface measured, its visible-pixel bounds); see opaque_bounds()
        self._opaque_bounds_cache: tuple[pygame.Surface, pygame.Rect] | None = None

    @property
    def image(self) -> pygame.Surface:
        """The flattened sprite stack image."""
        return self._image

    @image.setter
    def image(self, new_image: pygame.Surface) -> None:
        """Set the image."""
        self._image = new_image

    @property
    def rect(self) -> pygame.Rect:
        """The sprite stack pygame.Rect."""
        return self._rect

    @rect.setter
    def rect(self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        self._rect = new_rect

    @property
    def hitbox(self) -> pygame.Rect:
        """The collision hitbox for this frame.

        Returns the explicit hitbox if one was set, otherwise the full frame rect. That
        fallback is only SpriteFrame's own value: AnimatedSprite.hitbox, which is what
        collision uses, resolves an explicit frame hitbox first, then the sprite-level
        default hitbox, then the frame's visible pixels (see its resolution order), and
        checks has_explicit_hitbox rather than relying on this fallback. Always returns a
        valid pygame.Rect.
        """
        if self._hitbox is not None:
            return self._hitbox
        return self._rect

    @hitbox.setter
    def hitbox(self, value: pygame.Rect | None) -> None:
        """Set the collision hitbox, or None to clear the explicit hitbox."""
        self._hitbox = value

    def opaque_bounds(self) -> pygame.Rect:
        """Return the visible-pixel bounds of this frame's image, measured once per surface.

        Animation frame images are treated as immutable, so the bounds are cached. The
        cached value is tied to the surface it was measured from: assigning a new ``image``
        (as Papyrus's prepare_papyrus_sprite does after loading) measures the new surface.
        Drawing into a frame's surface in place is not detected (Bitmappy's editing fast path
        does that, but never uses hitboxes).

        Returns:
            pygame.Rect: A new rect (see glitchygames.collision.bounds.opaque_bounds).

        """
        cached_entry = self._opaque_bounds_cache
        if cached_entry is not None and cached_entry[0] is self._image:
            return cached_entry[1].copy()
        visible_bounds = measure_opaque_bounds(self._image)
        self._opaque_bounds_cache = (self._image, visible_bounds)
        return visible_bounds.copy()

    @property
    def has_explicit_hitbox(self) -> bool:
        """Whether this frame has an explicitly set hitbox.

        When False, the hitbox property returns the full frame rect as a fallback.
        """
        return self._hitbox is not None

    def __getitem__(self, index: int) -> SpriteFrame:
        """Return a sprite from the stack.

        Returns:
            'SpriteFrame': The item at the given index.

        """
        return self

    def get_size(self) -> tuple[int, int]:
        """Return the size of the surface.

        Returns:
            tuple[int, int]: The size.

        """
        return self._image.get_size()

    def get_alpha(self) -> int | None:
        """Return the alpha value of the surface.

        Returns:
            int | None: The alpha.

        """
        return self._image.get_alpha()

    def get_colorkey(self) -> tuple[int, int, int, int] | None:
        """Return the colorkey of the surface.

        Returns:
            tuple[int, int, int, int] | None: The colorkey.

        """
        return self._image.get_colorkey()

    def get_pixel_data(self) -> list[tuple[int, ...]]:
        """Get pixel data as a list of RGB or RGBA tuples.

        Returns:
            list[tuple[int, ...]]: The pixel data.

        """
        if self.pixels:
            return self.pixels.copy()
        # Extract pixels from the surface
        width, height = self._image.get_size()
        extracted_pixels: list[tuple[int, int, int, int]] = []
        for y in range(height):
            for x in range(width):
                # Surface.get_at always returns an RGBA Color
                color = self._image.get_at((x, y))
                extracted_pixels.append((color.r, color.g, color.b, color.a))
        return extracted_pixels  # ty: ignore[invalid-return-type]

    def set_pixel_data(self, pixels: Sequence[tuple[int, ...]]) -> None:
        """Set pixel data from a sequence of RGB or RGBA tuples.

        Accepts a read-only ``Sequence`` (rather than ``list``) so callers can pass
        lists of fixed-arity tuples such as ``list[tuple[int, int, int, int]]``;
        ``list`` is invariant, so those would not match ``list[tuple[int, ...]]``.
        The input is always copied into a new list.
        """
        self.pixels = list(pixels)
        # Update the surface with the new pixel data
        width, height = self._image.get_size()
        for i, pixel in enumerate(pixels):
            if i < width * height:
                x = i % width
                y = i // width
                if len(pixel) == RGBA_COMPONENT_COUNT:
                    # RGBA pixel
                    self._image.set_at((x, y), pixel)
                else:
                    # RGB pixel
                    self._image.set_at((x, y), pixel)

    @override
    def __repr__(self) -> str:
        """Return string representation of the frame.

        Returns:
            str: The string representation.

        """
        hitbox_info = f', hitbox={self._hitbox}' if self._hitbox is not None else ''
        return f'SpriteFrame(size={self._image.get_size()}, duration={self.duration}{hitbox_info})'
