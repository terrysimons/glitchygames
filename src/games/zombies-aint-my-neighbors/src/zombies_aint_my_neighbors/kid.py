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
# How long each part of a knockout lasts (feature plan 5): the fall (the 5-frame knockout at 0.1 s),
# lying still, loading back in (the 4-frame respawn at 0.1 s), and then the untouchable blink
KNOCKOUT_SECONDS: Final = 0.5
LYING_SECONDS: Final = 1.0
RESPAWN_SECONDS: Final = 0.4
UNTOUCHABLE_SECONDS: Final = 2.0
BLINK_SECONDS: Final = 0.1
# Frame times add up in floats (30 sixtieths make 0.49999...): a step ends this close to its time
TIME_TOLERANCE: Final = 1e-9
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


class KidState(StrEnum):
    """What a kid is doing: playing, or somewhere in a knockout."""

    ACTIVE = 'active'
    KNOCKED_OUT = 'knocked-out'
    LYING = 'lying'
    RESPAWNING = 'respawning'


# Each knockout state, how long it lasts, and what follows it
_KNOCKOUT_STEPS: Final[dict[KidState, tuple[float, KidState]]] = {
    KidState.KNOCKED_OUT: (KNOCKOUT_SECONDS, KidState.LYING),
    KidState.LYING: (LYING_SECONDS, KidState.RESPAWNING),
    KidState.RESPAWNING: (RESPAWN_SECONDS, KidState.ACTIVE),
}


class MirrorCache:
    """Mirrored frames, made once each and shared by every kid and monster of a scene.

    Keyed by (sprite name, animation, frame), so two kids of the same look (or two zombies)
    share a flipped frame and different sprites never do. ``flips`` counts the flips made, for
    checking the reuse.
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

    def show_frame(self, *, sprite: AnimatedSprite, sprite_name: str, mirrored: bool) -> None:
        """Show an animated sprite's current frame, flipped when it faces right.

        The one place a kid or a monster takes its image, so mirroring and the hitbox's flip
        always agree.

        Args:
            sprite: The sprite, its animation already advanced this frame.
            sprite_name: The sprite's name (its TOML ``[sprite] name``), the cache's key.
            mirrored: Whether to show the frame flipped left to right.

        """
        drawn = sprite.drawn_frame_surface()
        image = (
            self.mirrored(
                sprite_name=sprite_name,
                animation=sprite.current_animation,
                frame=sprite.current_frame,
                drawn=drawn,
            )
            if mirrored
            else drawn
        )
        if sprite.image is not image:
            sprite.image = image
            sprite.dirty = 1
        sprite.hitbox_flip_x = mirrored


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
        self.state = KidState.ACTIVE
        # Seconds spent in the current knockout state, and untouchable seconds left
        self._state_seconds = 0.0
        self.untouchable_seconds = 0.0
        # Blinking while untouchable hides the kid (the engine reads ``hidden`` on world sprites)
        self.hidden = False
        # The animation last started (None: none yet), so each is started once
        self._started_animation: str | None = None

    @property
    def can_move(self) -> bool:
        """Whether the kid's player moves it (not while knocked out)."""
        return self.state is KidState.ACTIVE

    @property
    def is_touchable(self) -> bool:
        """Whether a monster can knock the kid out now."""
        return self.state is KidState.ACTIVE and self.untouchable_seconds <= TIME_TOLERANCE

    def knock_out(self) -> bool:
        """Knock the kid out, if it can be: it falls, lies still, loads back in, then blinks.

        Returns:
            True when the kid was knocked out; False when it already was, or is untouchable.

        """
        if not self.is_touchable:
            return False
        self.state = KidState.KNOCKED_OUT
        self._state_seconds = 0.0
        self.moving = False
        return True

    def walk(self, *, direction_x: float, direction_y: float) -> None:
        """Set which way the kid is going this frame (0, 0 to stand still).

        Args:
            direction_x: The horizontal part (negative is left).
            direction_y: The vertical part (negative is up).

        """
        if not self.can_move:
            self.moving = False
            return
        self.moving = direction_x != 0 or direction_y != 0
        self.facing = facing_for(
            direction_x=direction_x, direction_y=direction_y, current=self.facing
        )

    def animation_name(self) -> str:
        """Return the animation for the kid's state: idle or walk, in its drawn facing.

        Returns:
            The namespace (right plays left's).

        """
        if self.state in {KidState.KNOCKED_OUT, KidState.LYING}:
            return 'knocked-out'
        if self.state is KidState.RESPAWNING:
            return 'respawn'
        state = 'walk' if self.moving else 'idle'
        drawn_facing = _MIRRORED_FROM.get(self.facing, self.facing)
        return f'{state}_{drawn_facing}'

    def dt_tick(self, dt: float) -> None:
        """Pose the kid for this frame: its animation, advanced, and its image, mirrored or not.

        Args:
            dt: The frame's time, in seconds.

        """
        self._advance_knockout(dt)
        name = self.animation_name()
        if name != self._started_animation:
            self.play(name)
            self._started_animation = name
        AnimatedSprite.update(self, dt)
        # Only standing and walking are mirrored: the knockout and respawn face down
        facing_right = self.state is KidState.ACTIVE and self.facing in _MIRRORED_FROM
        self.mirror_cache.show_frame(sprite=self, sprite_name=self.look_name, mirrored=facing_right)
        self._blink()

    def _advance_knockout(self, dt: float) -> None:
        """Move through the knockout's steps, and count down the untouchable time."""
        step = _KNOCKOUT_STEPS.get(self.state)
        if step is not None:
            self._state_seconds += dt
            seconds, following = step
            if self._state_seconds >= seconds - TIME_TOLERANCE:
                self.state = following
                self._state_seconds = 0.0
                if following is KidState.ACTIVE:
                    self.untouchable_seconds = UNTOUCHABLE_SECONDS
                    self.facing = KidFacing.DOWN
            return
        self.untouchable_seconds = max(0.0, self.untouchable_seconds - dt)

    def _blink(self) -> None:
        """Blink while untouchable: hidden and shown by turns (world sprites hide by ``hidden``)."""
        if self.untouchable_seconds > TIME_TOLERANCE:
            blinks = int((UNTOUCHABLE_SECONDS - self.untouchable_seconds) / BLINK_SECONDS)
            self.hidden = blinks % 2 == 1
        else:
            self.hidden = False

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: the animation advances in ``dt_tick`` only."""
