"""Parallax scrolling background layers for Brave Adventurer.

Each layer scrolls at a different rate relative to the camera position,
creating a depth illusion. Layers are rendered as Sprites within the
LayeredDirty group using z-layer ordering.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Self, override

import pygame

from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from collections.abc import Callable

# Threshold for comparing scroll factors to zero
STATIC_SCROLL_THRESHOLD = 1e-9


class ParallaxLayer(Sprite):
    """A full-screen background layer that scrolls at a fraction of camera speed.

    The layer uses a draw function to procedurally render its content
    each frame, offset by (camera_x * scroll_factor).

    Set dirty=2 for layers that change every frame (scrolling layers).
    Set dirty=1 for static layers (sky) that only need one render.
    """

    def __init__(  # noqa: PLR0913
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
            scroll_factor: How fast this layer scrolls relative to the camera.
                           0.0 = static, 1.0 = same speed as foreground.
            draw_function: A callable(surface, offset) that draws the layer content.
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

        # Replace default surface with one that supports transparency
        self.image = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)

        self.scroll_factor = scroll_factor
        self.draw_function = draw_function
        self.is_static = math.isclose(scroll_factor, 0.0, abs_tol=STATIC_SCROLL_THRESHOLD)

        # Set layer depth in the LayeredDirty group
        groups.change_layer(self, layer_depth)

        # Static layers only need to render once, scrolling layers redraw every frame
        if self.is_static:
            self.dirty = 1
            # Pre-render the static content immediately
            self.draw_function(self.image, 0.0)
        else:
            self.dirty = 2

    def update_scroll(self, camera_x: float) -> None:
        """Recalculate the parallax offset and redraw the layer.

        Only redraws if the layer actually scrolls. Static layers are skipped.

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
        """No-op update. Drawing is handled by update_scroll() in dt_tick."""
