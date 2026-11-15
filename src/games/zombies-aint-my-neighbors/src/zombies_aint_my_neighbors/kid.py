"""A kid in the neighborhood: a world sprite that walks, faces, and mirrors its right side.

The kid's TOML holds facings down, up, left, down-left and up-left; the right-hand facings play
their left animations with each frame flipped (character BOM, section 1). A flipped frame is
made once and kept in a ``MirrorCache`` the scene owns and hands to every kid, keyed by sprite,
animation and frame, so four kids walking right flip each frame once between them.
``hitbox_flip_x`` mirrors the hitbox with the image.

The animation advances in ``dt_tick`` (the pose rule, CLAUDE.md World Space) and ``update`` does
nothing, so it never advances twice a frame; this follows Brave Adventurer's Papyrus player
(src/games/brave-adventurer/src/brave_adventurer_papyrus/player.py). An animation is only
started when its name changes, since ``AnimatedSprite.play`` resets the frame timer, so walking
the same way every tick keeps the cycle going.
"""

from __future__ import annotations

import math
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Self, override

import pygame

from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace

# The kids' sprite files (package data), written by zombies_aint_my_neighbors.art.build
SPRITES_DIRECTORY: Final = Path(__file__).resolve().parent / 'sprites'
# A kid's frame, in native pixels (BOM decision 10)
KID_WIDTH: Final = 32
KID_HEIGHT: Final = 48


class KidFacing(StrEnum):
    """Where a kid faces: eight ways; the right-hand ones are drawn as their left mirrored."""

    DOWN = 'down'
    UP = 'up'
    LEFT = 'left'
    RIGHT = 'right'
    DOWN_LEFT = 'down-left'
    UP_LEFT = 'up-left'
    DOWN_RIGHT = 'down-right'
    UP_RIGHT = 'up-right'


# The facings drawn as another facing mirrored (BOM section 1): right is left flipped
_MIRRORED_FROM: Final[dict[KidFacing, KidFacing]] = {
    KidFacing.RIGHT: KidFacing.LEFT,
    KidFacing.DOWN_RIGHT: KidFacing.DOWN_LEFT,
    KidFacing.UP_RIGHT: KidFacing.UP_LEFT,
}
# The eight facings by 45-degree sector, counting clockwise from right (the screen's y is down)
_FACINGS_BY_SECTOR: Final = (
    KidFacing.RIGHT,
    KidFacing.DOWN_RIGHT,
    KidFacing.DOWN,
    KidFacing.DOWN_LEFT,
    KidFacing.LEFT,
    KidFacing.UP_LEFT,
    KidFacing.UP,
    KidFacing.UP_RIGHT,
)


class MirrorCache:
    """Mirrored frames, made once each and shared by every kid of a scene.

    Keyed by (sprite name, animation, frame), so two kids of the same look share a flipped frame
    and different kids never do. ``flips`` counts the flips made, for checking the reuse.
    """

    def __init__(self) -> None:
        """Make an empty cache."""
        self._mirrored: dict[tuple[str, str, int], pygame.Surface] = {}
        self.flips = 0

    def mirrored(
        self, *, sprite_name: str, animation: str, frame: int, drawn: pygame.Surface
    ) -> pygame.Surface:
        """Return a frame flipped left to right, flipping it only the first time it is asked for.

        Args:
            sprite_name: The sprite's name (its TOML ``[sprite] name``).
            animation: The animation the frame belongs to.
            frame: The frame's index.
            drawn: The frame as the engine draws it (``drawn_frame_surface``).

        Returns:
            The flipped frame (a new surface; the engine's cached frame is never changed).

        """
        key = (sprite_name, animation, frame)
        surface = self._mirrored.get(key)
        if surface is None:
            surface = pygame.transform.flip(drawn, flip_x=True, flip_y=False)
            self._mirrored[key] = surface
            self.flips += 1
        return surface


def facing_for(*, direction_x: float, direction_y: float, current: KidFacing) -> KidFacing:
    """Return the nearest of the eight facings to a movement.

    Args:
        direction_x: The movement's horizontal part (negative is left).
        direction_y: The movement's vertical part (negative is up).
        current: The facing kept when there is no movement.

    Returns:
        The facing.

    """
    if direction_x == 0 and direction_y == 0:
        return current
    sector = round(math.atan2(direction_y, direction_x) / (math.pi / 4)) % len(_FACINGS_BY_SECTOR)
    return _FACINGS_BY_SECTOR[sector]


class Kid(AnimatedSprite):
    """A player's kid: walks, faces the way it goes, mirrors its right side."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        *,
        look_name: str,
        world_x: float,
        world_y: float,
        mirror_cache: MirrorCache,
        groups: pygame.sprite.LayeredDirty[Any] | None,
    ) -> None:
        """Load a kid's sprite and place it in the world.

        Args:
            look_name: The kid (``dex``, ``marisol``, ``theo``, ``june``): its sprite file's name.
            world_x: The frame's left edge in the world.
            world_y: The frame's top edge in the world.
            mirror_cache: The scene's cache of mirrored frames.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / f'{look_name}.toml'), groups=groups)
        self.look_name = look_name
        self.world_x = world_x
        self.world_y = world_y
        self.mirror_cache = mirror_cache
        self.facing = KidFacing.DOWN
        self.moving = False

    def walk(self, *, direction_x: float, direction_y: float) -> None:
        """Set which way the kid is going this frame (0, 0 to stand still).

        Args:
            direction_x: The horizontal part (negative is left).
            direction_y: The vertical part (negative is up).

        """
        self.moving = direction_x != 0 or direction_y != 0
        self.facing = facing_for(
            direction_x=direction_x, direction_y=direction_y, current=self.facing
        )

    def animation_name(self) -> str:
        """Return the animation for the kid's state: idle or walk, in its drawn facing.

        Returns:
            The namespace (right plays left's).

        """
        state = 'walk' if self.moving else 'idle'
        drawn_facing = _MIRRORED_FROM.get(self.facing, self.facing)
        return f'{state}_{drawn_facing}'

    def dt_tick(self, dt: float) -> None:
        """Pose the kid for this frame: its animation, advanced, and its image, mirrored or not.

        Args:
            dt: The frame's time, in seconds.

        """
        name = self.animation_name()
        if self.current_animation != name or not self.is_playing:
            self.play(name)
        AnimatedSprite.update(self, dt)
        facing_right = self.facing in _MIRRORED_FROM
        if facing_right:
            image = self.mirror_cache.mirrored(
                sprite_name=self.look_name,
                animation=self.current_animation,
                frame=self.current_frame,
                drawn=self.drawn_frame_surface(),
            )
        else:
            image = self.drawn_frame_surface()
        if self.image is not image:
            self.image = image
            self.dirty = 1
        self.hitbox_flip_x = facing_right

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: the animation advances in ``dt_tick`` only."""
