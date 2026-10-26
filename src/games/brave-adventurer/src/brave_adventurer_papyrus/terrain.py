"""Papyrus Edition terrain sprites.

GroundSegment and StoneWall are reused from the original edition (they use
variable-width primitives which don't suit TOML pixel art). GoldScarab is
replaced with a TOML animated version.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Self, override

from brave_adventurer.terrain import GroundSegment, StoneWall
from brave_adventurer_papyrus.constants import (
    LAYER_COLLECTIBLES,
    SPRITES_DIR,
)
from brave_adventurer_papyrus.sprite_utils import (
    apply_transparency_and_scale,
    prepare_papyrus_sprite,
)
from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace

if TYPE_CHECKING:
    import pygame

# Re-export terrain primitives for use by the level manager
__all__ = ['GroundSegment', 'PapyrusGoldScarab', 'StoneWall']


class PapyrusGoldScarab(AnimatedSprite):
    """Collectible gold scarab using TOML shimmer animation.

    Bobs up and down while shimmering. Awards bonus score when collected. A world
    sprite: the engine places it from the camera.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        world_x: float,
        world_y: float,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Initialize the gold scarab collectible.

        Args:
            world_x: X position in world coordinates.
            world_y: Y position in world coordinates.
            groups: The sprite group to add this sprite to.

        """
        self._layer = LAYER_COLLECTIBLES

        super().__init__(
            filename=str(SPRITES_DIR / 'gold_scarab.toml'),
            groups=groups,
        )
        prepare_papyrus_sprite(self)

        self.world_x: float = world_x
        self.world_y: float = world_y
        self.base_world_y: float = world_y
        self.bob_timer: float = 0.0

        self.play('shimmer')
        self.is_looping = True
        self.dirty = 2

    def dt_tick(self: Self, dt: float) -> None:
        """Update bobbing motion and advance shimmer animation.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        self.dt = dt
        self.bob_timer += dt
        self.world_y = self.base_world_y + math.sin(self.bob_timer * 3.0) * 4.0
        AnimatedSprite.update(self, dt)
        apply_transparency_and_scale(self)

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """No-op. Animation is advanced in dt_tick() instead."""
