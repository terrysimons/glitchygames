"""A world-space sprite built from a sprite file's text, centered on a point.

The AI console's ``/sprite`` adds one to the game's scene through a recorded spawn event
(``glitchygames.events.sprite_spawn``; plans/2026-11-17-sprite-command.md). The sprite file
itself holds no position or coordinate space: this class only declares that the engine positions
the sprite in the world, applying the camera at render time, as for every world sprite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from glitchygames.world import CoordinateSpace

from .animated import AnimatedSprite
from .factory import SpriteFactory

if TYPE_CHECKING:
    import pygame


class SpawnedSprite(AnimatedSprite):
    """An ``AnimatedSprite`` the engine positions in the world (``world_x``, ``world_y``)."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self: Self,
        filename: str | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Create an empty sprite at the world's origin; ``from_text`` loads and places it.

        Args:
            filename: Passed to ``AnimatedSprite`` (None: nothing loaded).
            groups: Passed to ``AnimatedSprite`` (None: a group of its own).

        """
        super().__init__(filename, groups=groups)
        self.world_x = 0.0
        self.world_y = 0.0
        # The game's own flag, as for every world sprite (the engine's culling reads it)
        self.hidden = False

    @classmethod
    def from_text(
        cls, *, text: str, source_name: str, center_x: float, center_y: float
    ) -> SpawnedSprite:
        """Load the sprite from text and center it on a world point, at its native size.

        Args:
            text: The sprite file's TOML text.
            source_name: What the text came from, named in errors.
            center_x: The world x its center is placed at.
            center_y: The world y its center is placed at.

        Returns:
            The sprite, in no scene yet. Text that cannot build a sprite is refused with the
            factory's ValueError naming ``source_name``.

        """
        sprite = SpriteFactory.load_sprite_from_text(
            text=text, source_name=source_name, sprite_class=cls
        )
        sprite.world_x = center_x - sprite.rect.width / 2
        sprite.world_y = center_y - sprite.rect.height / 2
        return sprite
