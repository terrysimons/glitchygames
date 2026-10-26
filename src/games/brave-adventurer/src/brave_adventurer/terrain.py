"""Terrain sprites for Brave Adventurer: its collectible gold scarab.

The ground segments and stone walls both games share are in brave_adventurer_core.terrain.
"""

from __future__ import annotations

import math
from typing import Self, override

import pygame

from brave_adventurer.constants import GOLD_SCARAB_SIZE
from brave_adventurer.drawing import draw_gold_scarab
from brave_adventurer_core.constants import LAYER_COLLECTIBLES
from glitchygames.sprites import Sprite
from glitchygames.world import CoordinateSpace


class GoldScarab(Sprite):
    """A collectible gold scarab that bobs up and down.

    Awards bonus score when collected by the player. A world sprite: the engine places it
    from the camera.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

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
