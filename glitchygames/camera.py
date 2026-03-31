"""2D camera system for viewport tracking, world-to-screen conversion, and parallax.

Provides Camera2D for any scrolling game. Supports smooth follow,
world bounds clamping, visibility culling, and built-in parallax
background layer management.

Promoted from brave_adventurer/camera.py and parallax.py into the
engine so every game gets viewport support for free.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Self, override

import pygame

from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from collections.abc import Callable

log: logging.Logger = logging.getLogger('game.camera')

# Threshold for comparing scroll factors to zero
STATIC_SCROLL_THRESHOLD = 1e-9

# Default smooth follow factor (0.0 = no movement, 1.0 = instant snap)
DEFAULT_SMOOTH_FACTOR = 0.1

# Default visibility culling margin in pixels
DEFAULT_VISIBILITY_MARGIN = 64.0

# Reference frame rate for frame-rate-independent smoothing
REFERENCE_FPS = 60.0


class ParallaxLayer(Sprite):
    """A full-screen background layer that scrolls relative to the camera.

    Scrolls at `scroll_factor` times the camera speed, creating depth
    illusion. Static layers (scroll_factor ~0) render once; scrolling
    layers redraw every frame.
    """

    def __init__(
        self,
        *,
        scroll_factor: float,
        draw_function: Callable[[pygame.Surface, float], None],
        layer_depth: int,
        groups: pygame.sprite.LayeredDirty[Sprite],
        screen_width: int,
        screen_height: int,
    ) -> None:
        """Initialize a parallax background layer.

        Args:
            scroll_factor: Scroll rate relative to camera (0.0=static, 1.0=foreground).
            draw_function: Callable(surface, offset) that draws the layer content.
            layer_depth: Z-layer for rendering order (lower = further back).
            groups: The sprite group to add this layer to.
            screen_width: Width of the display.
            screen_height: Height of the display.

        """
        super().__init__(
            x=0,
            y=0,
            width=screen_width,
            height=screen_height,
            name=f'ParallaxLayer_{layer_depth}',
            groups=groups,
        )

        self.image = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.scroll_factor = scroll_factor
        self.draw_function = draw_function
        self.is_static = math.isclose(
            scroll_factor,
            0.0,
            abs_tol=STATIC_SCROLL_THRESHOLD,
        )

        groups.change_layer(self, layer_depth)

        if self.is_static:
            self.dirty = 1
            self.draw_function(self.image, 0.0)
        else:
            self.dirty = 2

    def update_scroll(self, camera_x: float) -> None:
        """Recalculate the parallax offset and redraw the layer.

        Args:
            camera_x: The camera's current world X position.

        """
        if self.is_static:
            return

        offset = camera_x * self.scroll_factor
        self.image.fill((0, 0, 0, 0))
        self.draw_function(self.image, offset)

    @override
    def update(self: Self) -> None:
        """No-op. Drawing is handled by update_scroll()."""


class Camera2D:
    """2D viewport camera with smooth follow, bounds, and parallax.

    Tracks a target position with configurable lead offset and smooth
    interpolation. Converts world coordinates to screen coordinates
    for rendering. Manages parallax background layers.

    Args:
        screen_width: Viewport width in pixels.
        screen_height: Viewport height in pixels.
        smooth_factor: Follow responsiveness (0.0=frozen, 1.0=instant).
        lead_x: Horizontal offset from target to viewport left edge.
        lead_y: Vertical offset from target to viewport top edge.
        visibility_margin: Extra pixels around viewport for culling checks.

    """

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        *,
        smooth_factor: float = DEFAULT_SMOOTH_FACTOR,
        lead_x: float = 0.0,
        lead_y: float = 0.0,
        visibility_margin: float = DEFAULT_VISIBILITY_MARGIN,
    ) -> None:
        """Initialize the camera."""
        self.world_x: float = 0.0
        self.world_y: float = 0.0
        self.screen_width: int = screen_width
        self.screen_height: int = screen_height
        self.smooth_factor: float = smooth_factor
        self.lead_x: float = lead_x
        self.lead_y: float = lead_y
        self.visibility_margin: float = visibility_margin

        # World bounds (None = unbounded in that direction)
        self._min_x: float | None = None
        self._min_y: float | None = None
        self._max_x: float | None = None
        self._max_y: float | None = None

        # Parallax layers
        self._parallax_layers: list[ParallaxLayer] = []

    def set_bounds(
        self,
        *,
        min_x: float | None = None,
        min_y: float | None = None,
        max_x: float | None = None,
        max_y: float | None = None,
    ) -> None:
        """Set world bounds to clamp camera position.

        Pass None for any edge to leave it unbounded.

        Args:
            min_x: Minimum camera X (left boundary).
            min_y: Minimum camera Y (top boundary).
            max_x: Maximum camera X (right boundary).
            max_y: Maximum camera Y (bottom boundary).

        """
        self._min_x = min_x
        self._min_y = min_y
        self._max_x = max_x
        self._max_y = max_y

    def update(self, target_x: float, target_y: float, dt: float) -> None:
        """Smoothly move the camera toward the target position.

        Uses frame-rate-independent exponential smoothing. The lead
        offset is subtracted from the target so the tracked object
        appears at that offset from the viewport edge.

        Args:
            target_x: Target X position in world coordinates.
            target_y: Target Y position in world coordinates.
            dt: Delta time in seconds since last frame.

        """
        goal_x = target_x - self.lead_x
        goal_y = target_y - self.lead_y

        # Frame-rate-independent exponential smoothing
        smoothing = 1.0 - (1.0 - self.smooth_factor) ** (dt * REFERENCE_FPS)

        self.world_x += (goal_x - self.world_x) * smoothing
        self.world_y += (goal_y - self.world_y) * smoothing

        # Clamp to world bounds
        self._clamp_to_bounds()

        # Update parallax layers
        for layer in self._parallax_layers:
            layer.update_scroll(self.world_x)

    def _clamp_to_bounds(self) -> None:
        """Clamp camera position to configured world bounds."""
        if self._min_x is not None:
            self.world_x = max(self.world_x, self._min_x)
        if self._min_y is not None:
            self.world_y = max(self.world_y, self._min_y)
        if self._max_x is not None:
            self.world_x = min(self.world_x, self._max_x)
        if self._max_y is not None:
            self.world_y = min(self.world_y, self._max_y)

    def apply(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates.

        Args:
            world_x: X position in world space.
            world_y: Y position in world space.

        Returns:
            A tuple of (screen_x, screen_y) pixel coordinates.

        """
        return (round(world_x - self.world_x), round(world_y - self.world_y))

    def is_visible(
        self,
        world_x: float,
        width: float,
        world_y: float = 0.0,
        height: float = 0.0,
    ) -> bool:
        """Check if a world-space object overlaps the visible viewport.

        Uses a configurable margin so sprites are drawn just before
        scrolling into view.

        Args:
            world_x: Left edge X in world space.
            width: Object width.
            world_y: Top edge Y in world space (0.0 for X-only check).
            height: Object height (0.0 for X-only check).

        Returns:
            True if the object overlaps the visible area (with margin).

        """
        margin = self.visibility_margin

        # X-axis check
        x_visible = (
            world_x + width > self.world_x - margin
            and world_x < self.world_x + self.screen_width + margin
        )

        # Y-axis check (skip if height is 0, for backward compatibility)
        if height == 0.0:  # noqa: RUF069 - exact zero means "X-only check"
            return x_visible

        y_visible = (
            world_y + height > self.world_y - margin
            and world_y < self.world_y + self.screen_height + margin
        )

        return x_visible and y_visible

    def add_background_layer(
        self,
        *,
        scroll_factor: float,
        draw_function: Callable[[pygame.Surface, float], None],
        layer_depth: int,
        groups: pygame.sprite.LayeredDirty[Sprite],
        screen_width: int | None = None,
        screen_height: int | None = None,
    ) -> ParallaxLayer:
        """Add a parallax background layer managed by this camera.

        Args:
            scroll_factor: Scroll rate (0.0=static, 1.0=foreground speed).
            draw_function: Callable(surface, offset) that draws the layer.
            layer_depth: Z-layer for rendering order (lower = further back).
            groups: Sprite group for the layer.
            screen_width: Layer width (defaults to camera viewport width).
            screen_height: Layer height (defaults to camera viewport height).

        Returns:
            The created ParallaxLayer.

        """
        layer = ParallaxLayer(
            scroll_factor=scroll_factor,
            draw_function=draw_function,
            layer_depth=layer_depth,
            groups=groups,
            screen_width=screen_width or self.screen_width,
            screen_height=screen_height or self.screen_height,
        )
        self._parallax_layers.append(layer)
        return layer
