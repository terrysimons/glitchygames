"""Terrain sprites for Brave Adventurer: ground, walls, and collectibles."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Self, override

import pygame

from glitchygames.examples.brave_adventurer.constants import (
    GOLD_SCARAB_SIZE,
    GROUND_HEIGHT,
    GROUND_Y,
    LAYER_COLLECTIBLES,
    LAYER_TERRAIN,
    STONE_WALL_WIDTH,
)
from glitchygames.examples.brave_adventurer.drawing import (
    draw_gold_scarab,
    draw_ground_segment,
    draw_stone_wall,
)
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from glitchygames.examples.brave_adventurer.camera import Camera


class GroundSegment(Sprite):
    """A solid ground platform the player can stand on.

    Ground segments are placed at GROUND_Y and have a fixed height.
    Gaps between segments form pits.
    """

    def __init__(
        self,
        world_x: float,
        segment_width: int,
        groups: pygame.sprite.LayeredDirty[Sprite],
    ) -> None:
        """Initialize a ground segment.

        Args:
            world_x: Left edge X position in world coordinates.
            segment_width: Width of this ground segment in pixels.
            groups: The sprite group to add this sprite to.

        """
        self._layer = LAYER_TERRAIN

        super().__init__(
            x=world_x,
            y=GROUND_Y,
            width=segment_width,
            height=GROUND_HEIGHT,
            name='Ground',
            groups=groups,
        )

        # Replace image with properly drawn ground
        self.image = pygame.Surface((segment_width, GROUND_HEIGHT))
        draw_ground_segment(self.image, segment_width)

        self.world_x: float = world_x
        self.segment_width: int = segment_width
        self.dirty = 1

    def apply_camera(self, camera: Camera) -> None:
        """Update screen position from camera transform.

        Args:
            camera: The camera providing the world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, GROUND_Y)
        self.rect.x = screen_x
        self.rect.y = screen_y

        if camera.is_visible(self.world_x, self.segment_width):
            self.visible = True
            self.dirty = 1
        else:
            self.visible = False
            self.dirty = 0


class StoneWall(Sprite):
    """A stone wall obstacle the player must jump over.

    Walls sit on top of the ground and have a configurable height.
    """

    def __init__(
        self,
        world_x: float,
        wall_height: int,
        groups: pygame.sprite.LayeredDirty[Sprite],
    ) -> None:
        """Initialize a stone wall.

        Args:
            world_x: Left edge X position in world coordinates.
            wall_height: Height of the wall in pixels.
            groups: The sprite group to add this sprite to.

        """
        world_y = GROUND_Y - wall_height
        self._layer = LAYER_TERRAIN

        super().__init__(
            x=world_x,
            y=world_y,
            width=STONE_WALL_WIDTH,
            height=wall_height,
            name='Wall',
            groups=groups,
        )

        self.image = pygame.Surface((STONE_WALL_WIDTH, wall_height))
        draw_stone_wall(self.image, STONE_WALL_WIDTH, wall_height)

        self.world_x: float = world_x
        self.world_y: float = world_y
        self.wall_height: int = wall_height
        self.dirty = 1

    def apply_camera(self, camera: Camera) -> None:
        """Update screen position from camera transform.

        Args:
            camera: The camera providing the world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y

        if camera.is_visible(self.world_x, STONE_WALL_WIDTH):
            self.visible = True
            self.dirty = 1
        else:
            self.visible = False
            self.dirty = 0


class GoldScarab(Sprite):
    """A collectible gold scarab that bobs up and down.

    Awards bonus score when collected by the player.
    """

    def __init__(
        self,
        world_x: float,
        world_y: float,
        groups: pygame.sprite.LayeredDirty[Sprite],
    ) -> None:
        """Initialize a gold scarab collectible.

        Args:
            world_x: X position in world coordinates.
            world_y: Y position in world coordinates.
            groups: The sprite group to add this sprite to.

        """
        self._layer = LAYER_COLLECTIBLES

        super().__init__(
            x=world_x,
            y=world_y,
            width=GOLD_SCARAB_SIZE,
            height=GOLD_SCARAB_SIZE,
            name='GoldScarab',
            groups=groups,
        )

        self.image = pygame.Surface((GOLD_SCARAB_SIZE, GOLD_SCARAB_SIZE), pygame.SRCALPHA)
        draw_gold_scarab(self.image)

        self.world_x: float = world_x
        self.world_y: float = world_y
        self.base_world_y: float = world_y
        self.bob_timer: float = 0.0
        self.dirty = 2  # Always redraw (bobbing animation)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the bobbing animation.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)
        self.bob_timer += dt
        self.world_y = self.base_world_y + math.sin(self.bob_timer * 3.0) * 4.0

    def apply_camera(self, camera: Camera) -> None:
        """Update screen position from camera transform.

        Args:
            camera: The camera providing the world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y

        if camera.is_visible(self.world_x, GOLD_SCARAB_SIZE):
            self.visible = True
        else:
            self.visible = False
            self.dirty = 0
