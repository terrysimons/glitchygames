"""Canvas interfaces for supporting multiple sprite types in the bitmap editor.

This module defines the abstract interfaces that allow the bitmap editor to work
with both static BitmappySprites and animated sprites through a unified API.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

import pygame

# Import the default file format constant
from glitchygames.color import RGBA_COMPONENT_COUNT
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT
from pydantic import BaseModel

if TYPE_CHECKING:
    from glitchygames.sprites import BitmappySprite

LOG = logging.getLogger("game.tools.canvas_interfaces")
LOG.addHandler(logging.NullHandler())


class MockPixelEvent(BaseModel):
    """Lightweight mock event for internal pixel update calls."""

    model_config = {"arbitrary_types_allowed": True}


class MockTrigger(BaseModel):
    """Lightweight mock trigger for pixel update notifications."""

    pixel_number: int
    pixel_color: tuple[int, int, int] | tuple[int, int, int, int]


class CanvasInterface(Protocol):
    """Interface for canvas operations that work with any sprite type."""

    def get_pixel_data(self) -> list[tuple[int, int, int, int]]:
        """Get the current pixel data as a list of RGBA tuples."""
        ...

    def set_pixel_data(self, pixels: list[tuple[int, int, int, int]]) -> None:
        """Set the pixel data from a list of RGBA tuples."""
        ...

    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels."""
        ...

    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Get the color of a pixel at the given coordinates."""
        ...

    def set_pixel_at(
        self, x: int, y: int, color: tuple[int, int, int] | tuple[int, int, int, int]
    ) -> None:
        """Set the color of a pixel at the given coordinates."""
        ...

    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface."""
        ...

    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        ...


class SpriteSerializer(ABC):
    """Abstract base class for sprite serialization."""

    @abstractmethod
    def save(
        self, sprite: BitmappySprite, filename: str, file_format: str = DEFAULT_FILE_FORMAT
    ) -> None:
        """Save a sprite to a file.

        Args:
            sprite: The sprite to save
            filename: Path where to save the file
            file_format: Format to save in ("ini" or "yaml")

        """

    @abstractmethod
    def load(self, filename: str) -> BitmappySprite | None:
        """Load a sprite from a file.

        Args:
            filename: Path to the sprite file

        Returns:
            The loaded sprite

        """


class CanvasRenderer(ABC):
    """Abstract base class for canvas rendering."""

    @abstractmethod
    def render(self, sprite: BitmappySprite) -> pygame.Surface:
        """Render a sprite to a surface.

        Args:
            sprite: The sprite to render

        Returns:
            The rendered surface

        """

    @abstractmethod
    def force_redraw(self, sprite: BitmappySprite) -> pygame.Surface:
        """Force a complete redraw of the sprite.

        Args:
            sprite: The sprite to redraw

        Returns:
            The redrawn surface

        """

    @abstractmethod
    def get_pixel_size(self) -> tuple[int, int]:
        """Get the size of individual pixels in the renderer.

        Returns:
            Tuple of (pixel_width, pixel_height)

        """


class StaticCanvasInterface:
    """Canvas interface implementation for static BitmappySprites."""

    def __init__(self, canvas_sprite: BitmappySprite) -> None:
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite

    def get_pixel_data(self) -> list[tuple[int, int, int, int]]:
        """Get the current pixel data as a list of RGBA tuples.

        Returns:
            list[tuple[int, int, int, int]]: The pixel data.

        """
        return self.canvas_sprite.pixels.copy()

    def set_pixel_data(self, pixels: list[tuple[int, int, int, int]]) -> None:
        """Set the pixel data from a list of RGBA tuples."""
        self.canvas_sprite.pixels = pixels.copy()
        # Mark all pixels as dirty
        self.canvas_sprite.dirty_pixels = [True] * len(pixels)
        self.canvas_sprite.dirty = 1

    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels.

        Returns:
            tuple[int, int]: The dimensions.

        """
        return (self.canvas_sprite.pixels_across, self.canvas_sprite.pixels_tall)

    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Get the color of a pixel at the given coordinates.

        Returns:
            tuple[int, int, int, int]: The pixel at.

        """
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            pixel = self.canvas_sprite.pixels[pixel_num]
            if len(pixel) == RGBA_COMPONENT_COUNT:
                return pixel
            return (pixel[0], pixel[1], pixel[2], 255)
        return (255, 0, 255, 255)  # Return magenta for out-of-bounds

    def set_pixel_at(
        self, x: int, y: int, color: tuple[int, int, int] | tuple[int, int, int, int]
    ) -> None:
        """Set the color of a pixel at the given coordinates."""
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            self.canvas_sprite.pixels[pixel_num] = color
            self.canvas_sprite.dirty_pixels[pixel_num] = True
            self.canvas_sprite.dirty = 1

    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface.

        Returns:
            pygame.Surface: The surface.

        """
        return self.canvas_sprite.image

    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        self.canvas_sprite.dirty = 1


class StaticSpriteSerializer(SpriteSerializer):
    """Serializer for static BitmappySprites."""

    @staticmethod
    def save(sprite: BitmappySprite, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save a static sprite to a file."""
        # Delegate to the sprite's save method
        sprite.save(filename, file_format)

    def load(self, filename: str) -> BitmappySprite | None:
        """Load a static sprite from a file."""
        # This will be handled by the CanvasSprite's load method
        # which maintains the existing event callback structure


class AnimatedCanvasInterface:
    """Canvas interface implementation for animated sprites."""

    def __init__(self, canvas_sprite: BitmappySprite) -> None:
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite
        # Set initial animation using sprite introspection
        if hasattr(canvas_sprite, "animated_sprite") and canvas_sprite.animated_sprite:
            if canvas_sprite.animated_sprite._animations:
                if (
                    hasattr(canvas_sprite.animated_sprite, "_animation_order")
                    and canvas_sprite.animated_sprite._animation_order
                ):
                    # Use the first animation in the file order
                    self.current_animation = canvas_sprite.animated_sprite._animation_order[0]
                else:
                    # Fall back to the first key in _animations
                    self.current_animation = next(
                        iter(canvas_sprite.animated_sprite._animations.keys())
                    )
            else:
                self.current_animation = ""
        else:
            self.current_animation = ""
        self.current_frame = 0

    def get_pixel_data(self) -> list[tuple[int, int, int, int]]:
        """Get the current pixel data as a list of RGBA tuples.

        Returns:
            list[tuple[int, int, int, int]]: The pixel data.

        """
        if hasattr(self.canvas_sprite, "animated_sprite"):
            frame = self.canvas_sprite.animated_sprite._animations[self.current_animation][
                self.current_frame
            ]
            pixels = frame.get_pixel_data()
        else:
            pixels = self.canvas_sprite.pixels.copy()

        # Ensure all pixels are RGBA format
        rgba_pixels = []
        for pixel in pixels:
            if len(pixel) == RGBA_COMPONENT_COUNT:
                rgba_pixels.append(pixel)
            else:
                # Convert RGB to RGBA with full opacity
                rgba_pixels.append((pixel[0], pixel[1], pixel[2], 255))

        return rgba_pixels

    def set_pixel_data(self, pixels: list[tuple[int, int, int, int]]) -> None:
        """Set the pixel data from a list of RGBA tuples."""
        if hasattr(self.canvas_sprite, "animated_sprite"):
            frame = self.canvas_sprite.animated_sprite._animations[self.current_animation][
                self.current_frame
            ]
            frame.set_pixel_data(pixels)
        else:
            self.canvas_sprite.pixels = pixels.copy()
            # Mark all pixels as dirty
            self.canvas_sprite.dirty_pixels = [True] * len(pixels)
            self.canvas_sprite.dirty = 1

    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels.

        Returns:
            tuple[int, int]: The dimensions.

        """
        return (self.canvas_sprite.pixels_across, self.canvas_sprite.pixels_tall)

    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Get the color of a pixel at the given coordinates.

        Returns:
            tuple[int, int, int, int]: The pixel at.

        """
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            if hasattr(self.canvas_sprite, "animated_sprite"):
                # Get the current frame from the canvas (not the animated sprite)
                current_animation = self.canvas_sprite.current_animation
                current_frame_index = self.canvas_sprite.current_frame

                # Access the frame through the animated sprite's frames property
                if current_animation in self.canvas_sprite.animated_sprite.frames:
                    frame = self.canvas_sprite.animated_sprite._animations[current_animation][
                        current_frame_index
                    ]
                    pixel = frame.get_pixel_data()[pixel_num]
                    if len(pixel) == RGBA_COMPONENT_COUNT:
                        return pixel
                    return (pixel[0], pixel[1], pixel[2], 255)
            pixel = self.canvas_sprite.pixels[pixel_num]
            if len(pixel) == RGBA_COMPONENT_COUNT:
                return pixel
            return (pixel[0], pixel[1], pixel[2], 255)
        return (255, 0, 255, 255)  # Return magenta for out-of-bounds

    def _should_track_color_change(
        self,
        old_color: object,
        new_color: object,
        *,
        controller_drag_active: bool,
    ) -> bool:
        """Check if a color change should be tracked for undo/redo.

        Args:
            old_color: The previous color value.
            new_color: The new color value.
            controller_drag_active: Whether a controller drag is active.

        Returns:
            True if the color change should be tracked.

        """
        if old_color == new_color or controller_drag_active:
            return False
        if not (hasattr(self.canvas_sprite, "parent_scene") and self.canvas_sprite.parent_scene):
            return False
        parent = self.canvas_sprite.parent_scene
        return (
            hasattr(parent, "canvas_operation_tracker")
            and not getattr(parent, "_applying_undo_redo", False)
        )

    def set_pixel_at(
        self,
        x: int,
        y: int,
        color: tuple[int, int, int] | tuple[int, int, int, int],
        *,
        skip_drag_ops: bool = False,
    ) -> None:
        """Set the color of a pixel at the given coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            color: Color tuple
            skip_drag_ops: If True, skip expensive operations during drag (used for optimization)

        """
        if not (
            0 <= x < self.canvas_sprite.pixels_across
            and 0 <= y < self.canvas_sprite.pixels_tall
        ):
            return

        pixel_num = y * self.canvas_sprite.pixels_across + x

        # Get the old color for undo tracking
        old_color = self._get_old_pixel_color(pixel_num)

        # Skip expensive operations during drag if flag is set
        if skip_drag_ops:
            # Fast path: just update the pixel data, skip everything else
            self.canvas_sprite.pixels[pixel_num] = color
            self.canvas_sprite.dirty_pixels[pixel_num] = True
            self.canvas_sprite.dirty = 1
            return

        # Track the pixel change for undo/redo
        controller_drag_active = self._is_controller_drag_active()

        if self._should_track_color_change(
            old_color, color, controller_drag_active=controller_drag_active
        ):
            self._collect_pixel_change(x, y, old_color, color)
        elif controller_drag_active:
            # Controller drag is active with pixels, don't collect pixels in canvas interface
            LOG.debug(
                "Controller drag active with pixels, skipping canvas interface pixel collection"
            )
            # But still update the frame data - don't return early

        self._update_frame_pixel_data(pixel_num, color)

    def _get_old_pixel_color(self, pixel_num: int) -> tuple | None:
        """Get the old color of a pixel for undo tracking.

        Returns:
            The old color tuple, or None.

        """
        if hasattr(self.canvas_sprite, "animated_sprite"):
            current_animation = self.canvas_sprite.current_animation
            current_frame_index = self.canvas_sprite.current_frame
            if current_animation in self.canvas_sprite.animated_sprite.frames:
                frame = self.canvas_sprite.animated_sprite._animations[current_animation][
                    current_frame_index
                ]
                frame_pixels = frame.get_pixel_data()
                return frame_pixels[pixel_num]
            return None
        return self.canvas_sprite.pixels[pixel_num]

    def _is_controller_drag_active(self) -> bool:
        """Check if any controller has an active drag with pixels drawn.

        Returns:
            True if a controller drag is active with drawn pixels.

        """
        if not (
            hasattr(self.canvas_sprite, "parent_scene")
            and self.canvas_sprite.parent_scene
            and hasattr(self.canvas_sprite.parent_scene, "controller_drags")
        ):
            return False

        for controller_id, drag_info in self.canvas_sprite.parent_scene.controller_drags.items():
            if drag_info.get("active", False) and len(drag_info.get("pixels_drawn", [])) > 0:
                LOG.debug(
                    "Controller drag active with pixels"
                    " for controller %s, skipping"
                    " canvas interface tracking",
                    controller_id,
                )
                return True
        return False

    def _collect_pixel_change(
        self,
        x: int,
        y: int,
        old_color: tuple | None,
        color: tuple[int, int, int] | tuple[int, int, int, int],
    ) -> None:
        """Collect pixel changes for undo/redo tracking."""
        parent_scene = self.canvas_sprite.parent_scene

        # Ensure tracking structures exist
        if not hasattr(parent_scene, "_current_pixel_changes"):
            parent_scene._current_pixel_changes = []
        if not hasattr(parent_scene, "_current_pixel_changes_dict"):
            # Use a dict for O(1) deduplication lookups during drag
            # Maps (x, y) -> (x, y, old_color, new_color) for fast replacement
            parent_scene._current_pixel_changes_dict = {}

        # Performance optimization: Use dict for O(1) deduplication to prevent memory bloat
        # If the same pixel was already changed in this drag, replace the old entry
        # This prevents unbounded growth during long drags on the same pixels
        pixel_key = (x, y)
        pixel_changes_dict = parent_scene._current_pixel_changes_dict

        # Store or update the pixel change (keeps original old_color, updates new_color)
        if pixel_key in pixel_changes_dict:
            # Update existing: keep original old_color, update to latest new_color
            existing = pixel_changes_dict[pixel_key]
            pixel_changes_dict[pixel_key] = (x, y, existing[2], color)
        else:
            # New pixel change
            pixel_changes_dict[pixel_key] = (x, y, old_color, color)

        # Convert dict to list format for compatibility (only when needed, not every time)
        # We'll convert to list format when submitting, but keep dict for efficient updates
        # Update the list periodically or convert on-demand
        if not hasattr(parent_scene, "_pixel_changes_list_dirty"):
            parent_scene._pixel_changes_list_dirty = True

        # Only convert to list occasionally or when submitting
        # - this avoids O(n) conversion every drag event
        # The dict will be converted to list when _submit_pixel_changes_if_ready is called

        # Safety limit: If collection grows beyond 2000 unique pixels, trim oldest entries
        # (Unlikely with deduplication, but protects against edge cases)
        max_pixel_changes = 2000
        if len(pixel_changes_dict) > max_pixel_changes:
            # Keep only the most recent entries (dict keeps insertion order in Python 3.7+)
            items = list(pixel_changes_dict.items())[-1500:]
            pixel_changes_dict.clear()
            pixel_changes_dict.update(items)

        # Only log debug info occasionally to reduce overhead
        if len(pixel_changes_dict) % 100 == 0:
            LOG.debug(
                f"Canvas interface pixel changes: {len(pixel_changes_dict)} unique pixels"
            )

        # Start a timer for single clicks (if this is the first pixel)
        if len(parent_scene._current_pixel_changes_dict) == 1:
            import time

            parent_scene._pixel_change_timer = time.time()
            LOG.debug("Canvas interface started pixel change timer for single click")

    def _update_frame_pixel_data(
        self,
        pixel_num: int,
        color: tuple[int, int, int] | tuple[int, int, int, int],
    ) -> None:
        """Update the pixel data in the frame or static sprite."""
        if hasattr(self.canvas_sprite, "animated_sprite"):
            current_animation = self.canvas_sprite.current_animation
            current_frame_index = self.canvas_sprite.current_frame

            # Access the frame through the animated sprite's frames property
            if current_animation in self.canvas_sprite.animated_sprite.frames:
                frame = self.canvas_sprite.animated_sprite._animations[current_animation][
                    current_frame_index
                ]
                frame_pixels = frame.get_pixel_data()
                frame_pixels[pixel_num] = color
                frame.set_pixel_data(frame_pixels)

                # Clear the surface cache for this frame so it gets regenerated
                if hasattr(self.canvas_sprite.animated_sprite, "_surface_cache"):
                    cache_key = f"{current_animation}_{current_frame_index}"
                    if cache_key in self.canvas_sprite.animated_sprite._surface_cache:
                        del self.canvas_sprite.animated_sprite._surface_cache[cache_key]

                # Mark canvas as dirty so it will redraw
                self.canvas_sprite.dirty_pixels[pixel_num] = True
                self.canvas_sprite.dirty = 1

                # Trigger pixel update event to notify film strip
                if hasattr(self.canvas_sprite, "on_pixel_update_event"):
                    mock_event = MockPixelEvent()
                    mock_trigger = MockTrigger(pixel_number=pixel_num, pixel_color=color)
                    self.canvas_sprite.on_pixel_update_event(mock_event, mock_trigger)
        else:
            self.canvas_sprite.pixels[pixel_num] = color
            self.canvas_sprite.dirty_pixels[pixel_num] = True
            self.canvas_sprite.dirty = 1

    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface.

        Returns:
            pygame.Surface: The surface.

        """
        return self.canvas_sprite.image

    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        self.canvas_sprite.dirty = 1

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current animation and frame."""
        self.current_animation = animation
        self.current_frame = frame
        # Don't call show_frame here to avoid recursion
        # The canvas sprite will handle the frame switching

    def get_current_frame(self) -> tuple[str, int]:
        """Get the current animation and frame.

        Returns:
            tuple[str, int]: The current frame.

        """
        return (self.current_animation, self.current_frame)


class AnimatedSpriteSerializer(SpriteSerializer):
    """Serializer for animated sprites."""

    @staticmethod
    def save(sprite: BitmappySprite, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save an animated sprite to a file."""
        # Delegate to the sprite's save method
        sprite.save(filename, file_format)

    def load(self, filename: str) -> BitmappySprite | None:
        """Load an animated sprite from a file."""
        # This will be handled by the CanvasSprite's load method
        # which maintains the existing event callback structure


class AnimatedCanvasRenderer(CanvasRenderer):
    """Renderer for animated sprites."""

    def __init__(self, canvas_sprite: BitmappySprite) -> None:
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite

    def render(self, sprite: BitmappySprite) -> pygame.Surface:
        """Render an animated sprite to a surface.

        Returns:
            pygame.Surface: The result.

        """
        # Use the force_redraw method to avoid recursion
        return self.force_redraw(sprite)

    def force_redraw(self, sprite: BitmappySprite) -> pygame.Surface:
        """Force a complete redraw of the animated sprite.

        Returns:
            pygame.Surface: The result.

        """
        LOG.debug("DEBUG: AnimatedCanvasRenderer.force_redraw called")
        if hasattr(self.canvas_sprite, "animated_sprite"):
            self._redraw_animated_sprite()
        else:
            # Fall back to static rendering
            self._redraw_static_pixels(self.canvas_sprite.pixels)

        self._draw_hover_effects()

        return self.canvas_sprite.image

    def _redraw_animated_sprite(self) -> None:
        """Redraw the canvas with animated sprite data."""
        current_animation = self.canvas_sprite.current_animation
        current_frame = self.canvas_sprite.current_frame
        frames = self.canvas_sprite.animated_sprite.frames

        LOG.debug(
            f"DEBUG: current_animation={current_animation}, current_frame={current_frame}"
        )
        LOG.debug(f"DEBUG: frames keys={list(frames.keys()) if frames else 'None'}")
        LOG.debug(
            f"DEBUG: frames[current_animation] length="
            f"{len(frames[current_animation]) if current_animation in frames else 'N/A'}"
        )

        if current_animation not in frames or current_frame >= len(frames[current_animation]):
            # Fall back to static rendering if frame not found
            self._redraw_static_pixels(self.canvas_sprite.pixels)
            return

        # Create a single transparent buffer for all frames (hardware accelerated)
        self.canvas_sprite.image = pygame.Surface(
            (self.canvas_sprite.width, self.canvas_sprite.height),
            pygame.SRCALPHA,
        )
        self.canvas_sprite.image = self.canvas_sprite.image.convert_alpha()
        # Use magenta background pixel (opaque) as the canvas background
        # Per-pixel alpha pixels will be blended on top
        self.canvas_sprite.image.fill((255, 0, 255, 255))

        self._render_onion_layers(frames, current_animation, current_frame)

        # Get the frame pixel data
        frame_pixels = self._get_current_frame_pixels(frames, current_animation, current_frame)

        # Check if selected frame should be visible (for comparison mode)
        selected_frame_visible = True
        if hasattr(self.canvas_sprite, "parent_scene") and self.canvas_sprite.parent_scene:
            selected_frame_visible = getattr(
                self.canvas_sprite.parent_scene, "selected_frame_visible", True
            )

        border_thickness = self.canvas_sprite.border_thickness
        LOG.debug(f"DEBUG RENDERER: border_thickness={border_thickness}")

        if selected_frame_visible:
            self._draw_visible_frame_pixels(frame_pixels)
        else:
            self._draw_controller_indicators_only(frame_pixels)

        # Draw borders on the main canvas (only if selected frame is visible)
        if selected_frame_visible and border_thickness > 0:
            self._draw_pixel_grid_borders(frame_pixels, border_thickness)

    def _render_onion_layers(
        self, frames: dict, current_animation: str, current_frame: int
    ) -> None:
        """Render onion skinning layers onto the canvas."""
        from .onion_skinning import get_onion_skinning_manager

        onion_manager = get_onion_skinning_manager()

        if not onion_manager.is_global_onion_skinning_enabled():
            return

        # Get only frames that have onion skinning explicitly enabled
        onion_frames = {
            frame_idx
            for frame_idx in range(len(frames[current_animation]))
            if frame_idx != current_frame
            and onion_manager.is_frame_onion_skinned(current_animation, frame_idx)
        }
        LOG.debug(f"Rendering onion frames: {onion_frames}")

        # Create a temporary surface to accumulate onion layers (hardware accelerated)
        onion_accumulator = pygame.Surface(
            (self.canvas_sprite.width, self.canvas_sprite.height),
            pygame.SRCALPHA,
        )
        onion_accumulator = onion_accumulator.convert_alpha()
        onion_accumulator.fill((0, 0, 0, 0))  # Transparent background

        # Blend each onion frame into the accumulator
        alpha = int(255 * onion_manager.onion_transparency)
        for frame_idx in onion_frames:
            if frame_idx < len(frames[current_animation]):
                frame = frames[current_animation][frame_idx]
                frame_pixels = self._get_frame_pixel_data(frame)
                frame_surface = self._render_onion_frame(frame_pixels, alpha)
                onion_accumulator.blit(
                    frame_surface, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2
                )

        # Blit the accumulated onion layers onto the main canvas
        self.canvas_sprite.image.blit(onion_accumulator, (0, 0))

    def _get_frame_pixel_data(self, frame: object) -> list:
        """Get pixel data from a frame object.

        Returns:
            List of pixel tuples.

        """
        if hasattr(frame, "get_pixel_data"):
            return frame.get_pixel_data()
        return getattr(
            frame,
            "pixels",
            [(255, 0, 255)]
            * (self.canvas_sprite.pixels_across * self.canvas_sprite.pixels_tall),
        )

    def _render_onion_frame(self, frame_pixels: list, alpha: int) -> pygame.Surface:
        """Render a single onion skinning frame.

        Returns:
            Surface with the onion frame drawn at the specified transparency.

        """
        frame_surface = pygame.Surface(
            (self.canvas_sprite.width, self.canvas_sprite.height),
            pygame.SRCALPHA,
        )
        frame_surface = frame_surface.convert_alpha()
        frame_surface.fill((0, 0, 0, 0))  # Transparent background

        # Draw each pixel with onion transparency (skip 255,0,255 pixels).
        # NOTE: Onion layers should NOT be panned - they stay in original position
        for i, pixel in enumerate(frame_pixels):
            # Skip transparent pixels (magenta) - 100% transparent
            if pixel in {(255, 0, 255), (255, 0, 255, 255)}:
                continue

            x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
            y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height

            # Handle both RGB and RGBA pixels
            if len(pixel) == RGBA_COMPONENT_COUNT:
                # Already RGBA - combine with onion transparency
                r, g, b, pixel_alpha = pixel
                combined_alpha = int((pixel_alpha * alpha) / 255)
                transparent_pixel = (r, g, b, combined_alpha)
            else:
                # RGB pixel - add onion transparency
                transparent_pixel = (*pixel, alpha)

            pygame.draw.rect(
                frame_surface,
                transparent_pixel,
                (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
            )

        return frame_surface

    def _get_current_frame_pixels(
        self, frames: dict, current_animation: str, current_frame: int
    ) -> list:
        """Get pixel data for the current frame, accounting for panning.

        Returns:
            List of pixel tuples for the current frame.

        """
        frame = frames[current_animation][current_frame]

        # Use panned pixel data if panning is active, otherwise use original frame data
        if (
            hasattr(self.canvas_sprite, "_panning_active")
            and self.canvas_sprite._panning_active
            and hasattr(self.canvas_sprite, "pixels")
        ):
            frame_pixels = self.canvas_sprite.pixels
            LOG.debug(
                f"DEBUG: Using panned canvas pixels: "
                f"{len(frame_pixels)} pixels, "
                f"first few: {frame_pixels[:3]}"
            )
        elif hasattr(frame, "get_pixel_data"):
            frame_pixels = frame.get_pixel_data()
            LOG.debug(
                f"DEBUG: Using frame.get_pixel_data(): "
                f"{len(frame_pixels)} pixels, "
                f"first few: {frame_pixels[:3]}"
            )
        else:
            frame_pixels = getattr(
                frame,
                "pixels",
                [(255, 0, 255)]
                * (self.canvas_sprite.pixels_across * self.canvas_sprite.pixels_tall),
            )
            LOG.debug(
                f"DEBUG: Using fallback frame pixels: "
                f"{len(frame_pixels)} pixels, "
                f"first few: {frame_pixels[:3]}"
            )
        return frame_pixels

    def _draw_pixel_on_canvas(self, pixel: tuple, x: int, y: int) -> None:
        """Draw a single pixel on the canvas, handling RGB/RGBA conversion."""
        if len(pixel) == RGBA_COMPONENT_COUNT:
            pygame.draw.rect(
                self.canvas_sprite.image,
                pixel,
                (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
            )
        else:
            # RGB pixel - convert to RGBA for alpha surface
            rgba_pixel = (pixel[0], pixel[1], pixel[2], 255)
            pygame.draw.rect(
                self.canvas_sprite.image,
                rgba_pixel,
                (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
            )

    def _draw_visible_frame_pixels(self, frame_pixels: list) -> None:
        """Draw all visible frame pixels with controller indicators."""
        for i, pixel in enumerate(frame_pixels):
            x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
            y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height

            # Do NOT apply panning offset to drawing coordinates - grid stays fixed
            # Panning is handled by extracting different pixel data, not moving the grid

            # Check if any controller is active on this pixel (even for transparent pixels)
            controller_indicator_color = None
            if self._has_active_controllers_in_canvas_mode():
                controller_indicator_color = self._get_controller_indicator_for_pixel(i)

            # Skip transparent pixels (magenta) - they should show the background
            if pixel in {(255, 0, 255), (255, 0, 255, 255)}:
                # Still draw controller indicators even for transparent pixels
                if controller_indicator_color:
                    self._draw_plus_indicator(
                        self.canvas_sprite.image,
                        controller_indicator_color,
                        x, y,
                        self.canvas_sprite.pixel_width,
                        self.canvas_sprite.pixel_height,
                    )
                continue

            # Draw the pixel
            self._draw_pixel_on_canvas(pixel, x, y)

            # Draw plus sign indicator on top if a controller is on this pixel
            if controller_indicator_color:
                self._draw_plus_indicator(
                    self.canvas_sprite.image,
                    controller_indicator_color,
                    x, y,
                    self.canvas_sprite.pixel_width,
                    self.canvas_sprite.pixel_height,
                )

    def _draw_controller_indicators_only(self, frame_pixels: list) -> None:
        """Draw only controller indicators (selected frame is hidden)."""
        for i in range(len(frame_pixels)):
            x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
            y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height

            # Do NOT apply panning offset to drawing coordinates - grid stays fixed

            controller_indicator_color = None
            if self._has_active_controllers_in_canvas_mode():
                controller_indicator_color = self._get_controller_indicator_for_pixel(i)

            if controller_indicator_color:
                self._draw_plus_indicator(
                    self.canvas_sprite.image,
                    controller_indicator_color,
                    x, y,
                    self.canvas_sprite.pixel_width,
                    self.canvas_sprite.pixel_height,
                )

    def _draw_pixel_grid_borders(self, frame_pixels: list, border_thickness: int) -> None:
        """Draw grid borders on the canvas."""
        for i in range(len(frame_pixels)):
            x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
            y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height

            # Do NOT apply panning offset to drawing coordinates - grid stays fixed

            pygame.draw.rect(
                self.canvas_sprite.image,
                (64, 64, 64),
                (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                border_thickness,
            )

    def _redraw_static_pixels(self, pixels: list) -> None:
        """Redraw the canvas with static pixel data."""
        self.canvas_sprite.image.fill(self.canvas_sprite.background_color)
        border_thickness = self.canvas_sprite.border_thickness

        for i, pixel in enumerate(pixels):
            x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
            y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height

            # Do NOT apply panning offset to drawing coordinates - grid stays fixed

            # Check if any controller is active on this pixel
            controller_indicator_color = None
            if self._has_active_controllers_in_canvas_mode():
                controller_indicator_color = self._get_controller_indicator_for_pixel(i)
            if controller_indicator_color:
                # Draw normal pixel first
                pygame.draw.rect(
                    self.canvas_sprite.image,
                    pixel,
                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                )
                # Draw plus sign indicator on top
                self._draw_plus_indicator(
                    self.canvas_sprite.image,
                    controller_indicator_color,
                    x, y,
                    self.canvas_sprite.pixel_width,
                    self.canvas_sprite.pixel_height,
                )
            else:
                # Draw normal pixel
                pygame.draw.rect(
                    self.canvas_sprite.image,
                    pixel,
                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                )

            # Only draw border if border_thickness > 0
            if border_thickness > 0:
                pygame.draw.rect(
                    self.canvas_sprite.image,
                    (64, 64, 64),
                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                    border_thickness,
                )

    def _draw_hover_effects(self) -> None:
        """Draw hover effects on the canvas (pixel hover + canvas border)."""
        # Draw hover effect for the hovered pixel (white border to match keyboard selector)
        if (
            hasattr(self.canvas_sprite, "hovered_pixel")
            and self.canvas_sprite.hovered_pixel is not None
        ):
            hover_x, hover_y = self.canvas_sprite.hovered_pixel
            pixel_x = hover_x * self.canvas_sprite.pixel_width
            pixel_y = hover_y * self.canvas_sprite.pixel_height

            # Draw white border around the hovered pixel
            # (2px thick to match keyboard selector style)
            pygame.draw.rect(
                self.canvas_sprite.image,
                (255, 255, 255),  # White color
                (pixel_x, pixel_y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                2,  # 2px border thickness
            )

        # Draw canvas hover border (1px white border around entire canvas perimeter)
        if hasattr(self.canvas_sprite, "is_hovered") and self.canvas_sprite.is_hovered:
            # Draw white border around the entire canvas perimeter
            pygame.draw.rect(
                self.canvas_sprite.image,
                (255, 255, 255),  # White color
                (0, 0, self.canvas_sprite.image.get_width(), self.canvas_sprite.image.get_height()),
                1,  # 1px border thickness
            )

    def get_pixel_size(self) -> tuple[int, int]:
        """Get the size of individual pixels in the renderer.

        Returns:
            tuple[int, int]: The pixel size.

        """
        return (self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height)

    def _get_controller_scene(self) -> object | None:
        """Get the parent scene if it has controller support.

        Returns:
            The parent scene with controller data, or None.

        """
        if not (hasattr(self.canvas_sprite, "parent_scene") and self.canvas_sprite.parent_scene):
            return None
        scene = self.canvas_sprite.parent_scene
        if hasattr(scene, "controller_selections") and hasattr(scene, "mode_switcher"):
            return scene
        return None

    def _has_active_controllers_in_canvas_mode(self) -> bool:
        """Check if there are any active controllers in canvas mode.

        Returns:
            True if any controller is active in canvas mode, False otherwise

        """
        scene = self._get_controller_scene()
        if not scene:
            return False
        # Check if any controller is active in canvas mode
        for controller_id in scene.controller_selections:
            controller_mode = scene.mode_switcher.get_controller_mode(controller_id)
            if not (controller_mode and controller_mode.value == "canvas"):
                continue
            # Get controller position
            position = scene.mode_switcher.get_controller_position(controller_id)
            if not (position and position.is_valid):
                continue
            # Check if position is within canvas bounds
            x, y = position.position
            if (
                0 <= x < self.canvas_sprite.pixels_across
                and 0 <= y < self.canvas_sprite.pixels_tall
            ):
                return True
        return False

    def _get_controller_indicator_for_pixel(self, pixel_index: int) -> tuple[int, int, int] | None:
        """Check if any controller is active on this pixel and return indicator color.

        Returns:
            tuple[int, int, int] | None: The controller indicator for pixel.

        """
        scene = self._get_controller_scene()
        if not scene:
            return None
        # Check all controllers for canvas mode
        for controller_id in scene.controller_selections:
            controller_mode = scene.mode_switcher.get_controller_mode(controller_id)
            if not (controller_mode and controller_mode.value == "canvas"):
                continue
            position = scene.mode_switcher.get_controller_position(controller_id)
            if not (position and position.is_valid):
                continue
            x, y = position.position
            if not (
                0 <= x < self.canvas_sprite.pixels_across
                and 0 <= y < self.canvas_sprite.pixels_tall
            ):
                continue
            controller_pixel_index = y * self.canvas_sprite.pixels_across + x
            if controller_pixel_index != pixel_index:
                continue
            if not hasattr(scene, "multi_controller_manager"):
                continue
            controller_info = scene.multi_controller_manager.get_controller_info(controller_id)
            if controller_info:
                return controller_info.color
        return None

    def _draw_plus_indicator(
        self,
        surface: pygame.Surface,
        color: tuple[int, int, int],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        """Draw a box indicator with controller color and inverse color borders."""
        # The x,y coordinates are the top-left corner of the pixel box
        # Calculate the center of the pixel box in screen coordinates
        center_x = x + self.canvas_sprite.pixel_width // 2
        center_y = y + self.canvas_sprite.pixel_height // 2

        # Convert screen coordinates to pixel coordinates
        pixel_x = center_x // self.canvas_sprite.pixel_width
        pixel_y = center_y // self.canvas_sprite.pixel_height

        # Get the color of the specific pixel
        pixel_color = self._get_pixel_color_at_position(pixel_x, pixel_y)
        inverse_color = self._get_inverse_color(pixel_color)

        # Draw outer box with controller color (1 pixel wide)
        pygame.draw.rect(surface, color, (x + 1, y + 1, width - 2, height - 2), 1)

        # Draw inner box with inverse color for contrast (2 pixels wide)
        pygame.draw.rect(surface, inverse_color, (x + 2, y + 2, width - 4, height - 4), 2)

    def _get_pixel_color_at_position(self, x: int, y: int) -> tuple[int, int, int]:
        """Get the pixel color at the specified position.

        Returns:
            tuple[int, int, int]: The pixel color at position.

        """
        if hasattr(self, "canvas_sprite") and self.canvas_sprite:
            if (
                0 <= x < self.canvas_sprite.pixels_across
                and 0 <= y < self.canvas_sprite.pixels_tall
            ):
                pixel_index = y * self.canvas_sprite.pixels_across + x
                if pixel_index < len(self.canvas_sprite.pixels):
                    return self.canvas_sprite.pixels[pixel_index]
                LOG.debug(
                    "Pixel index %s out of range (max: %s)",
                    pixel_index,
                    len(self.canvas_sprite.pixels) - 1,
                )
            else:
                LOG.debug("Coordinates (%s, %s) out of bounds", x, y)
        LOG.debug("Pixel not found at (%s, %s), returning black", x, y)
        return (0, 0, 0)  # Default to black if pixel not found

    def _get_inverse_color(self, color: tuple[int, int, int]) -> tuple[int, int, int]:
        """Get the inverse color for contrast.

        Returns:
            tuple[int, int, int]: The inverse color.

        """
        return (255 - color[0], 255 - color[1], 255 - color[2])
