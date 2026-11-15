"""A Lawn Zombie in the yard: a world sprite that shambles toward the nearest standing kid.

Feature plan 5 (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md), Task 4. It chases at
40 px/s (a third of a kid's walk), facing the nearest of four ways (right plays the left walk
mirrored, through the scene's ``MirrorCache``, as the kids do); with no kid standing, it holds
walk frame 0 (its idle, character BOM 5.1). ``grab`` plays the lunge and clamp, standing still,
then the shamble resumes. Touching is the two hitboxes meeting after each is shrunk by a 4 px
forgiveness margin (the engine's ``get_collision_rect_with_margin``).

Feature plan 6 (plans/2026-11-15-zombies-aint-my-neighbors-6-channel-changer.md): one zap
(``zap``) kills it. It flashes white for 0.05 s, plays ``crumble`` (5 frames, 0.5 s) where it
fell, touching and chasing no one, then its last frame (the slippers) fades out over 0.5 s and
it leaves its groups (``is_gone``).

Like the kid, it chooses and advances its animation in ``dt_tick`` (the pose rule, CLAUDE.md
World Space), and ``update`` does nothing.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.collision.detection import get_collision_rect_with_margin
from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.hit_effects import faded, white_silhouette
from zombies_aint_my_neighbors.kid import SPRITES_DIRECTORY, TIME_TOLERANCE, KidState

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pygame

    from zombies_aint_my_neighbors.kid import Kid, MirrorCache

# Feature plan 5: a third of a kid's walk (the BOM's "slower than a kid")
ZOMBIE_SPEED: Final = 40.0
# The grab: 2 frames at 0.1 s (character BOM 5.1)
GRAB_SECONDS: Final = 0.2
# Pixels each hitbox is shrunk by on every side before touching is tested (feature plan 5)
TOUCH_MARGIN: Final = 4
# The sprite file's name (its TOML [sprite] name), the mirror cache's key
SPRITE_NAME: Final = 'lawn_zombie'
# A zombie's frame (and a kid's), in native pixels: chasing aims centre to centre
FRAME_WIDTH: Final = 32
FRAME_HEIGHT: Final = 48
# Closer than this, the zombie stops rather than jitter about its target
ARRIVED_DISTANCE: Final = 0.5
# Feature plan 6: a hit's white flash, the crumble (5 frames of 0.1 s), the slippers' fade
FLASH_SECONDS: Final = 0.05
CRUMBLE_SECONDS: Final = 0.5
FADE_SECONDS: Final = 0.5
OPAQUE: Final = 255


class ZombieFacing(StrEnum):
    """Where a zombie faces: four ways; right is drawn as left mirrored."""

    DOWN = 'down'
    UP = 'up'
    LEFT = 'left'
    RIGHT = 'right'


def facing_toward(*, offset_x: float, offset_y: float, current: ZombieFacing) -> ZombieFacing:
    """Return the nearest of the four facings to an offset (ties go to the vertical facing).

    Args:
        offset_x: How far right the target is (negative is left).
        offset_y: How far down the target is (negative is up).
        current: The facing kept when the offset is nothing.

    Returns:
        The facing.

    """
    if offset_x == 0 and offset_y == 0:
        return current
    if abs(offset_x) > abs(offset_y):
        return ZombieFacing.RIGHT if offset_x > 0 else ZombieFacing.LEFT
    return ZombieFacing.DOWN if offset_y > 0 else ZombieFacing.UP


def touches(*, zombie: Zombie, kid: Kid) -> bool:
    """Return whether a zombie and a kid touch: their hitboxes, each shrunk by the margin, meet.

    Returns:
        True when they touch.

    """
    if zombie.is_dying:
        return False
    zombie_rect = get_collision_rect_with_margin(
        zombie, zombie.world_x, zombie.world_y, margin=TOUCH_MARGIN
    )
    kid_rect = get_collision_rect_with_margin(kid, kid.world_x, kid.world_y, margin=TOUCH_MARGIN)
    return zombie_rect.colliderect(kid_rect)


class Zombie(AnimatedSprite):
    """A Lawn Zombie: shambles toward the nearest standing kid and grabs."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        *,
        world_x: float,
        world_y: float,
        mirror_cache: MirrorCache,
        groups: pygame.sprite.LayeredDirty[Any] | None,
    ) -> None:
        """Load the zombie's sprite and place it in the world.

        Args:
            world_x: The frame's left edge in the world.
            world_y: The frame's top edge in the world.
            mirror_cache: The scene's cache of mirrored frames.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / f'{SPRITE_NAME}.toml'), groups=groups)
        self.mirror_cache = mirror_cache
        self.spawn_at(world_x=world_x, world_y=world_y)

    def spawn_at(self, *, world_x: float, world_y: float) -> None:
        """Start a fresh life at a place: as new, or reused from the scene's pool.

        Args:
            world_x: Its frame's left edge in the world.
            world_y: Its frame's top edge in the world.

        """
        self.world_x = world_x
        self.world_y = world_y
        self.facing = ZombieFacing.DOWN
        self.moving = False
        # Seconds of the grab left (0: not grabbing)
        self.grab_seconds = 0.0
        # The animation last started (None: none yet), so each is started once
        self._started_animation: str | None = None
        # Seconds since the zap (None: not zapped), seconds of white flash left, and whether it
        # has faded out and left its groups
        self.dying_seconds: float | None = None
        self.flash_seconds = 0.0
        self.is_gone = False

    @property
    def is_dying(self) -> bool:
        """Whether the zombie has been zapped (crumbling or fading)."""
        return self.dying_seconds is not None

    def zap(self) -> bool:
        """Take a zap: flash, crumble, fade, go.

        Returns:
            True when the zap killed it; False when it was already dying.

        """
        if self.is_dying:
            return False
        self.dying_seconds = 0.0
        self.flash_seconds = FLASH_SECONDS
        self.grab_seconds = 0.0
        self.moving = False
        return True

    @property
    def is_grabbing(self) -> bool:
        """Whether the zombie is in its grab."""
        return self.grab_seconds > TIME_TOLERANCE

    def grab(self) -> None:
        """Lunge and clamp (the grab), standing still until it is done."""
        self.grab_seconds = GRAB_SECONDS
        self.moving = False

    def chase(self, *, kids: Sequence[Kid], dt: float) -> None:
        """Shamble toward the nearest kid who is not knocked out, or stand when there is none.

        Args:
            kids: Every kid in the yard.
            dt: The frame's time, in seconds.

        """
        if self.is_grabbing or self.is_dying:
            return
        standing = [kid for kid in kids if kid.state is KidState.ACTIVE]
        if not standing:
            self.moving = False
            return
        target = min(
            standing,
            key=lambda kid: math.hypot(kid.world_x - self.world_x, kid.world_y - self.world_y),
        )
        offset_x = target.world_x - self.world_x
        offset_y = target.world_y - self.world_y
        distance = math.hypot(offset_x, offset_y)
        self.facing = facing_toward(offset_x=offset_x, offset_y=offset_y, current=self.facing)
        if distance < ARRIVED_DISTANCE:
            self.moving = False
            return
        step = min(ZOMBIE_SPEED * dt, distance)
        self.world_x += offset_x / distance * step
        self.world_y += offset_y / distance * step
        self.moving = True

    def animation_name(self) -> str:
        """Return the animation for the zombie's state: grab or walk, in its drawn facing.

        Returns:
            The namespace (right plays left's).

        """
        if self.is_dying:
            return 'crumble'
        state = 'grab' if self.is_grabbing else 'walk'
        drawn_facing = ZombieFacing.LEFT if self.facing is ZombieFacing.RIGHT else self.facing
        return f'{state}_{drawn_facing}'

    def dt_tick(self, dt: float) -> None:
        """Pose the zombie for this frame: its animation, advanced, and its image, mirrored or not.

        Args:
            dt: The frame's time, in seconds.

        """
        if self.dying_seconds is not None:
            self._crumble(dt)
            return
        if self.is_grabbing:
            self.grab_seconds = max(0.0, self.grab_seconds - dt)
        name = self.animation_name()
        standing_still = not self.moving and not self.is_grabbing
        if name != self._started_animation:
            self.play(name)
            self._started_animation = name
        if standing_still:
            # Idle is walk frame 0 held (character BOM 5.1)
            self.stop()
        elif not self.is_playing:
            self.play(name)
        AnimatedSprite.update(self, dt)
        self.mirror_cache.show_frame(
            sprite=self, sprite_name=SPRITE_NAME, mirrored=self.facing is ZombieFacing.RIGHT
        )

    def _crumble(self, dt: float) -> None:
        """Flash, crumble where it fell, fade the slippers, then leave the yard."""
        if self.dying_seconds is None:  # pragma: no cover - dt_tick calls this only when dying
            return
        self.dying_seconds += dt
        self.flash_seconds = max(0.0, self.flash_seconds - dt)
        if self.dying_seconds >= CRUMBLE_SECONDS + FADE_SECONDS - TIME_TOLERANCE:
            self.is_gone = True
            self.kill()
            return
        if self._started_animation != 'crumble':
            self.play('crumble')
            self._started_animation = 'crumble'
        AnimatedSprite.update(self, dt)
        self.mirror_cache.show_frame(sprite=self, sprite_name=SPRITE_NAME, mirrored=False)
        frame = self.drawn_frame_surface()
        if self.flash_seconds > TIME_TOLERANCE:
            self.image = white_silhouette(frame)
            self.dirty = 1
        elif self.dying_seconds > CRUMBLE_SECONDS + TIME_TOLERANCE:
            left = 1.0 - (self.dying_seconds - CRUMBLE_SECONDS) / FADE_SECONDS
            self.image = faded(frame, alpha=round(OPAQUE * left))
            self.dirty = 1

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: the animation advances in ``dt_tick`` only."""
