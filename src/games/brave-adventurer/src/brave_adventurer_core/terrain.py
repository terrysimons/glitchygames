"""Terrain sprites both Brave Adventurer games share: ground segments and stone walls."""

from __future__ import annotations

import pygame

from brave_adventurer_core.constants import (
    GROUND_HEIGHT,
    GROUND_Y,
    LAYER_TERRAIN,
    STONE_WALL_WIDTH,
)
from brave_adventurer_core.drawing import draw_ground_segment, draw_stone_wall
from glitchygames.sprites import Sprite
from glitchygames.world import CoordinateSpace


class GroundSegment(Sprite):
    """A solid ground platform the player can stand on.

    Ground segments are placed at GROUND_Y and have a fixed height.
    Gaps between segments form pits. A world sprite: the engine places it from the camera.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

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
        self.world_y: float = float(GROUND_Y)
        self.segment_width: int = segment_width
        # Redrawn every frame: with a still camera nothing else dirties it, and it stayed on
        # screen only because the full-screen parallax layers redraw everything (BUGS.md #60).
        self.dirty = 2


class StoneWall(Sprite):
    """A stone wall obstacle the player must jump over.

    Walls sit on top of the ground and have a configurable height. A world sprite: the
    engine places it from the camera.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

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
        # Redrawn every frame: with a still camera nothing else dirties it, and it stayed on
        # screen only because the full-screen parallax layers redraw everything (BUGS.md #60).
        self.dirty = 2
