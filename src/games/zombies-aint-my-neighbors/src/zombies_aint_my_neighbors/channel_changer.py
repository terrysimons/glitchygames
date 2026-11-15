"""What a kid holds while shooting: the Channel Changer, or the laser pointer.

The props BOM's remote (feature plan 6) and laser pointer (feature plan 8): world sprites placed
on the kid's hand point each frame the kid uses them (``hold``) and put away otherwise; they
never move themselves. Both share one class (``HandProp``), told apart by their sprite file and
their tips. A 12x12 canvas's grip (column 6, row 6; column 5 when mirrored) goes on the hand
point; it mirrors with the kid's frame (through the scene's ``MirrorCache``, as the kid does);
and its tip (``muzzle``) is where a zap, or a laser's light, leaves.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.art.weapon_rig import GRIP, LASER_TIPS, REMOTE_TIPS, SIZE

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pygame

    from zombies_aint_my_neighbors.kid import MirrorCache

SPRITES_DIRECTORY: Final = Path(__file__).resolve().parent / 'sprites'


class HandProp(AnimatedSprite):
    """Something a kid holds: shown on the hand while used, hidden otherwise."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        *,
        sprite_name: str,
        tips: Mapping[str, tuple[int, int]],
        mirror_cache: MirrorCache,
        groups: pygame.sprite.LayeredDirty[Any] | None,
    ) -> None:
        """Load the prop, put away.

        Args:
            sprite_name: Its sprite file's name (the mirror cache's key too).
            tips: Its tip's cell per facing (down, up, left, right).
            mirror_cache: The scene's cache of mirrored frames.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / f'{sprite_name}.toml'), groups=groups)
        self.sprite_name = sprite_name
        self.tips = tips
        self.mirror_cache = mirror_cache
        self.world_x = 0.0
        self.world_y = 0.0
        self.hidden = True
        # The facing whose tip the light or zap leaves from (down, up, left or right)
        self.tip_facing = 'down'
        self._started_animation: str | None = None

    def hold(
        self, *, hand_x: float, hand_y: float, drawn_facing: str, mirrored: bool, shown: bool
    ) -> None:
        """Place the prop's grip on a hand point, in the kid's drawn facing.

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
        self.mirror_cache.show_frame(sprite=self, sprite_name=self.sprite_name, mirrored=mirrored)
        self.tip_facing = 'right' if mirrored else drawn_facing
        self.hidden = not shown

    def put_away(self) -> None:
        """Hide the prop (the kid isn't using it)."""
        self.hidden = True

    def muzzle(self) -> tuple[float, float]:
        """Return where a zap or a light leaves: the middle of the tip's cell, in the world.

        Returns:
            The world point.

        """
        tip_x, tip_y = self.tips[self.tip_facing]
        return (self.world_x + tip_x + 0.5, self.world_y + tip_y + 0.5)

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: its kid places it in ``dt_tick`` (the pose rule)."""


class ChannelChanger(HandProp):
    """A kid's TV remote (feature plan 6)."""

    def __init__(
        self, *, mirror_cache: MirrorCache, groups: pygame.sprite.LayeredDirty[Any] | None
    ) -> None:
        """Load the remote, put away."""
        super().__init__(
            sprite_name='channel_changer',
            tips=REMOTE_TIPS,
            mirror_cache=mirror_cache,
            groups=groups,
        )


class LaserPointer(HandProp):
    """A kid's laser pointer (feature plan 8)."""

    def __init__(
        self, *, mirror_cache: MirrorCache, groups: pygame.sprite.LayeredDirty[Any] | None
    ) -> None:
        """Load the laser pointer, put away."""
        super().__init__(
            sprite_name='laser_pointer', tips=LASER_TIPS, mirror_cache=mirror_cache, groups=groups
        )
