"""The Channel Changer in a kid's hand: a world sprite placed on the hand point while shooting.

The props BOM's remote (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md), feature plan 6.
Its kid places it every frame it shoots (``hold``) and puts it away otherwise; it never moves
itself. Its 12x12 canvas's grip (column 6, row 6; column 5 when mirrored) goes on the hand
point, it mirrors with the kid's frame (through the scene's ``MirrorCache``, as the kid does),
and a zap leaves from its LED (``muzzle``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.art.weapon_rig import GRIP, SIZE, remote_tip

if TYPE_CHECKING:
    import pygame

    from zombies_aint_my_neighbors.kid import MirrorCache

SPRITE_FILE: Final = Path(__file__).resolve().parent / 'sprites' / 'channel_changer.toml'
SPRITE_NAME: Final = 'channel_changer'


class ChannelChanger(AnimatedSprite):
    """A kid's TV remote: shown on the hand while shooting, hidden otherwise."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self, *, mirror_cache: MirrorCache, groups: pygame.sprite.LayeredDirty[Any] | None
    ) -> None:
        """Load the remote, put away.

        Args:
            mirror_cache: The scene's cache of mirrored frames.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITE_FILE), groups=groups)
        self.mirror_cache = mirror_cache
        self.world_x = 0.0
        self.world_y = 0.0
        self.hidden = True
        # The facing whose tip a zap leaves from (down, up, left or right)
        self.tip_facing = 'down'
        self._started_animation: str | None = None

    def hold(
        self, *, hand_x: float, hand_y: float, drawn_facing: str, mirrored: bool, shown: bool
    ) -> None:
        """Place the remote's centre on a hand point, in the kid's drawn facing.

        Args:
            hand_x: The hand point's x in the world.
            hand_y: The hand point's y in the world.
            drawn_facing: The kid's drawn facing (down, up or left).
            mirrored: Whether the kid's frame is mirrored (it faces right).
            shown: Whether to show it (False while its kid blinks out).

        """
        # Mirrored, the grip's column 6 of 12 flips to column 5 (x' = 11 - x)
        grip_x = SIZE - 1 - GRIP[0] if mirrored else GRIP[0]
        self.world_x = hand_x - grip_x
        self.world_y = hand_y - GRIP[1]
        name = f'held_{drawn_facing}'
        if name != self._started_animation:
            self.play(name)
            self._started_animation = name
        self.mirror_cache.show_frame(sprite=self, sprite_name=SPRITE_NAME, mirrored=mirrored)
        self.tip_facing = 'right' if mirrored else drawn_facing
        self.hidden = not shown

    def put_away(self) -> None:
        """Hide the remote (the kid isn't shooting)."""
        self.hidden = True

    def muzzle(self) -> tuple[float, float]:
        """Return where a zap leaves: the middle of the LED's cell, in the world.

        Returns:
            The world point.

        """
        tip_x, tip_y = remote_tip(facing=self.tip_facing)
        return (self.world_x + tip_x + 0.5, self.world_y + tip_y + 0.5)

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: its kid places it in ``dt_tick`` (the pose rule)."""
