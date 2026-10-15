"""Terrain sprites for Clockwork Keep — platforms, elevators, moving gears."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.examples.clockwork_keep.constants import (
    ELEVATOR_HEIGHT,
    ELEVATOR_WIDTH,
    LAYER_TERRAIN,
    PLATFORM_HEIGHT,
)
from glitchygames.examples.clockwork_keep.drawing import draw_elevator, draw_platform
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from glitchygames.camera import Camera2D


class Platform(Sprite):
    """A static metallic platform.

    Args:
        world_x: X position in world space.
        world_y: Y position in world space.
        width: Platform width in pixels.
        platform_color: Main body color.
        top_color: Highlighted top edge color.
        groups: Sprite group to add to.

    """

    def __init__(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
        self,
        world_x: float,
        world_y: float,
        width: int,
        platform_color: tuple[int, int, int],
        top_color: tuple[int, int, int],
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Initialize the platform."""
        self._layer = LAYER_TERRAIN
        super().__init__(
            x=world_x,
            y=world_y,
            width=width,
            height=PLATFORM_HEIGHT,
            name='Platform',
            groups=groups,
        )
        self.world_x = world_x
        self.world_y = world_y
        self.image = pygame.Surface((width, PLATFORM_HEIGHT), pygame.SRCALPHA)
        draw_platform(self.image, platform_color, top_color)
        self.dirty = 1

    def apply_camera(self, camera: Camera2D) -> None:
        """Update screen position from camera.

        Args:
            camera: The camera for world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y


class Elevator(Sprite):
    """An interactable elevator that triggers floor transitions.

    The player stands on it and presses up/interact to ride it.

    Args:
        world_x: X position in world space.
        world_y: Y position in world space.
        groups: Sprite group to add to.

    """

    def __init__(
        self,
        world_x: float,
        world_y: float,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Initialize the elevator."""
        self._layer = LAYER_TERRAIN
        super().__init__(
            x=world_x,
            y=world_y,
            width=ELEVATOR_WIDTH,
            height=ELEVATOR_HEIGHT,
            name='Elevator',
            groups=groups,
        )
        self.world_x = world_x
        self.world_y = world_y
        self.image = pygame.Surface((ELEVATOR_WIDTH, ELEVATOR_HEIGHT), pygame.SRCALPHA)
        draw_elevator(self.image)
        self.dirty = 1

    def apply_camera(self, camera: Camera2D) -> None:
        """Update screen position from camera.

        Args:
            camera: The camera for world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y


class MovingGear(Sprite):
    """A gear-shaped platform that moves on a sine path.

    Args:
        world_x: Center X of the movement range.
        world_y: Center Y of the movement range.
        move_range_x: Horizontal movement amplitude in pixels.
        move_range_y: Vertical movement amplitude in pixels.
        speed: Movement speed (radians/sec).
        size: Gear diameter in pixels.
        groups: Sprite group to add to.

    """

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        world_x: float,
        world_y: float,
        groups: pygame.sprite.LayeredDirty[Any],
        *,
        move_range_x: float = 0.0,
        move_range_y: float = 0.0,
        speed: float = 1.5,
        size: int = 40,
    ) -> None:
        """Initialize the moving gear."""
        self._layer = LAYER_TERRAIN
        super().__init__(
            x=world_x,
            y=world_y,
            width=size,
            height=size // 4,
            name='MovingGear',
            groups=groups,
        )
        self._center_x = world_x
        self._center_y = world_y
        self._move_range_x = move_range_x
        self._move_range_y = move_range_y
        self._speed = speed
        self._timer: float = 0.0
        self.world_x = world_x
        self.world_y = world_y

        self.image = pygame.Surface((size, size // 4), pygame.SRCALPHA)
        self.image.fill((140, 130, 110))
        # Gear teeth along edges
        for tooth_x in range(0, size, 8):
            pygame.draw.rect(self.image, (120, 110, 90), (tooth_x, 0, 4, 2))
        self.dirty = 2  # Always redraw (moving)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move the gear along its path.

        Args:
            dt: Delta time in seconds.

        """
        super().dt_tick(dt)
        self._timer += dt
        self.world_x = self._center_x + self._move_range_x * math.sin(self._timer * self._speed)
        self.world_y = self._center_y + self._move_range_y * math.sin(self._timer * self._speed)

    def apply_camera(self, camera: Camera2D) -> None:
        """Update screen position from camera.

        Args:
            camera: The camera for world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y
