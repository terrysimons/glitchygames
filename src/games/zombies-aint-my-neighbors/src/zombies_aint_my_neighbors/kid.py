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

Feature plan 6 (plans/2026-11-15-zombies-aint-my-neighbors-6-channel-changer.md): the kid shoots
the Channel Changer. ``pull_trigger`` is called once a frame, before ``dt_tick``, with whether
its player holds fire: a press fires at once and holding fires every 0.25 s. Standing, a shot
plays ``shoot_<f>`` (its two frames); moving, ``walk-shoot_<f>`` plays while fire is held or the
last shot is under 0.25 s old. The poses use the nearest straight facing (the side one at
exactly 45 degrees); the shot flies the eight-way facing (``aim``). The remote is drawn on the
frame's hand point only while a weapon animation plays, behind the kid when it faces up.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md): lives. A
knockout on the player's last life (``knock_out(last_life=True)``) never gets back up: the kid
lies on its last knockout frame, fades out over 1 s, and is out (hidden) for the stage.

Feature plan 8 (plans/2026-11-15-zombies-aint-my-neighbors-8-laser-pointer.md): the laser pointer.
``switch_weapon`` swaps between it and the Channel Changer. Holding fire with it shines while
the battery (``laser.LaserBattery``) has charge: the kid holds its aim (``shoot_<f>``'s first
frame, or ``walk-shoot_<f>`` moving), the laser pointer in its hand, and after a warm-up of
``WARM_UP_SECONDS`` (the battery drawing through it) its dot sits ``DOT_DISTANCE`` ahead of its
feet along the aim, inside the yard (``bounds``). The battery
ticks every frame, so a resting laser refills whatever the kid holds.
"""

from __future__ import annotations

import math
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Self, override

import pygame

from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.art.hand_points import KID_HAND_POINTS
from zombies_aint_my_neighbors.channel_changer import ChannelChanger, LaserPointer
from zombies_aint_my_neighbors.hit_effects import faded
from zombies_aint_my_neighbors.laser import (
    DOT_DISTANCE,
    WARM_UP_SECONDS,
    LaserBattery,
    LaserBeam,
    LaserDot,
)
from zombies_aint_my_neighbors.run_state import Weapon
from zombies_aint_my_neighbors.tolerances import TIME_TOLERANCE

# The kids' sprite files (package data), written by zombies_aint_my_neighbors.art.build
SPRITES_DIRECTORY: Final = Path(__file__).resolve().parent / 'sprites'
# How long each part of a knockout lasts (feature plan 5): the fall (the 5-frame knockout at 0.1 s),
# lying still, loading back in (the 4-frame respawn at 0.1 s), and then the untouchable blink
KNOCKOUT_SECONDS: Final = 0.5
LYING_SECONDS: Final = 1.0
RESPAWN_SECONDS: Final = 0.4
UNTOUCHABLE_SECONDS: Final = 2.0
BLINK_SECONDS: Final = 0.1
# Feature plan 7: a kid out of lives fades out over this long, lying on its last knockout frame
OUT_FADE_SECONDS: Final = 1.0
OPAQUE: Final = 255
# Shooting (feature plan 6): seconds between held shots (4 a second), and how long a standing
# shot's pose lasts (shoot_<f>: two frames of 0.08 s)
FIRE_SECONDS: Final = 0.25
SHOOT_POSE_SECONDS: Final = 0.16
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


# The straight pose a facing shoots in: diagonals take the side one (feature plan 6)
_SHOOTING_FACING: Final[dict[KidFacing, KidFacing]] = {
    KidFacing.DOWN_LEFT: KidFacing.LEFT,
    KidFacing.UP_LEFT: KidFacing.LEFT,
    KidFacing.DOWN_RIGHT: KidFacing.RIGHT,
    KidFacing.UP_RIGHT: KidFacing.RIGHT,
}
_DIAGONAL: Final = math.sqrt(0.5)
# Which way a shot flies from each facing, at unit length (the screen's y is down)
_AIMS: Final[dict[KidFacing, tuple[float, float]]] = {
    KidFacing.RIGHT: (1.0, 0.0),
    KidFacing.DOWN_RIGHT: (_DIAGONAL, _DIAGONAL),
    KidFacing.DOWN: (0.0, 1.0),
    KidFacing.DOWN_LEFT: (-_DIAGONAL, _DIAGONAL),
    KidFacing.LEFT: (-1.0, 0.0),
    KidFacing.UP_LEFT: (-_DIAGONAL, -_DIAGONAL),
    KidFacing.UP: (0.0, -1.0),
    KidFacing.UP_RIGHT: (_DIAGONAL, -_DIAGONAL),
}


class KidState(StrEnum):
    """What a kid is doing: playing, or somewhere in a knockout."""

    ACTIVE = 'active'
    KNOCKED_OUT = 'knocked-out'
    LYING = 'lying'
    RESPAWNING = 'respawning'
    # Out of lives (feature plan 7): fading on the ground, then out for the stage
    FADING = 'fading'
    OUT = 'out'
    # Stage clear (feature plan 7): fists up, facing down, safe and still
    CHEERING = 'cheering'


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
        # Shooting: whether fire is held this frame, seconds until the next shot may fire, the
        # last shot's age (infinite: none yet), and whether a shot fired this frame
        self._trigger_held = False
        self._fire_cooldown = 0.0
        self._shot_age = math.inf
        self._fired_this_frame = False
        self.remote = ChannelChanger(mirror_cache=mirror_cache, groups=groups)
        # The laser pointer (feature plan 8): its prop, its battery, its dot, whether it shines
        self.laser_pointer = LaserPointer(mirror_cache=mirror_cache, groups=groups)
        self.battery = LaserBattery()
        self.dot = LaserDot(groups=groups)
        self.beam = LaserBeam(groups=groups)
        # Whether the battery draws (the kid aims), whether the dot shines (after the warm-up),
        # and how long the battery has drawn without a break
        self.laser_aiming = False
        self.laser_lit = False
        self._warm_seconds = 0.0
        # The yard: the laser's dot stays inside it (anywhere when None; the scene sets it)
        self.bounds: pygame.Rect | None = None
        # Whether the current knockout took the last life
        self._last_life = False
        # The weapon held (feature plan 8): every kid starts with the Channel Changer
        self.weapon = Weapon.CHANNEL_CHANGER

    @property
    def can_move(self) -> bool:
        """Whether the kid's player moves it (not while knocked out)."""
        return self.state is KidState.ACTIVE

    @property
    def is_touchable(self) -> bool:
        """Whether a monster can knock the kid out now."""
        return self.state is KidState.ACTIVE and self.untouchable_seconds <= TIME_TOLERANCE

    @property
    def is_out(self) -> bool:
        """Whether the kid is out of lives (fading on the ground, or gone for the stage)."""
        return self.state in {KidState.FADING, KidState.OUT}

    def switch_weapon(self) -> None:
        """Swap between the Channel Changer and the laser pointer, at once.

        A switch lets go of the trigger: the new weapon's first shot is a fresh press, so time
        spent holding the other weapon is never banked into the remote's rhythm.
        """
        self._trigger_held = False
        # The remote's last shot pose ends with the switch: the other weapon never wears it
        self._shot_age = math.inf
        self.weapon = (
            Weapon.LASER_POINTER
            if self.weapon is Weapon.CHANNEL_CHANGER
            else Weapon.CHANNEL_CHANGER
        )

    def cheer(self) -> None:
        """Cheer the stage clear (``cheer``, facing down): still, safe, not firing; not when out."""
        if self.is_out or self.state is not KidState.ACTIVE:
            return
        self.state = KidState.CHEERING
        self.moving = False
        self.untouchable_seconds = 0.0
        self.facing = KidFacing.DOWN

    def knock_out(self, *, last_life: bool = False) -> bool:
        """Knock the kid out, if it can be: it falls, lies still, loads back in, then blinks.

        Args:
            last_life: Whether this knockout took the player's last life: then the kid falls,
                fades out and is out for the stage.

        Returns:
            True when the kid was knocked out; False when it already was, or is untouchable.

        """
        if not self.is_touchable:
            return False
        self.state = KidState.KNOCKED_OUT
        self._state_seconds = 0.0
        self.moving = False
        self._last_life = last_life
        self._douse_laser()
        return True

    def _douse_laser(self) -> None:
        """Put the laser out now, within the frame (its warm-up starts again next time)."""
        self.laser_aiming = False
        self.laser_lit = False
        self._warm_seconds = 0.0
        self.dot.go_out()
        self.beam.go_out()

    def pull_trigger(self, *, held: bool) -> bool:
        """Say whether fire is held this frame; fire when it may (call before ``dt_tick``).

        Args:
            held: Whether the kid's player holds fire.

        Returns:
            True when a shot fires this frame.

        """
        held_before = self._trigger_held
        self._trigger_held = held and self.can_move
        if self.weapon is Weapon.LASER_POINTER:
            # The laser shines while held (dt_tick asks its battery); it fires nothing
            return False
        if not self._trigger_held or self._fire_cooldown > TIME_TOLERANCE:
            return False
        if held_before:
            # Held on: the part of a frame past the last 0.25 s counts toward the next (at most
            # one rhythm's worth, after a hitch), so the rhythm holds at any frame rate
            self._fire_cooldown = max(self._fire_cooldown, -FIRE_SECONDS) + FIRE_SECONDS
        else:
            # A fresh press starts the rhythm from now: time while released is never banked
            self._fire_cooldown = FIRE_SECONDS
        self._shot_age = 0.0
        self._fired_this_frame = True
        return True

    def aim(self) -> tuple[float, float]:
        """Return which way a shot flies: the kid's eight-way facing, at unit length.

        Returns:
            The direction (the screen's y is down).

        """
        return _AIMS[self.facing]

    def muzzle(self) -> tuple[float, float]:
        """Return where a shot starts: the remote's LED, in the world (after ``dt_tick``).

        Returns:
            The world point.

        """
        return self.remote.muzzle()

    @property
    def remote_in_front(self) -> bool:
        """Whether the remote is drawn in front of the kid (not when it faces up)."""
        return _SHOOTING_FACING.get(self.facing, self.facing) is not KidFacing.UP

    def _shooting_state(self) -> str | None:
        """Return the weapon animation's state this frame, or None when not shooting.

        Returns:
            ``shoot``, ``walk-shoot`` or None.

        """
        if self.state is not KidState.ACTIVE:
            return None
        pose = 'walk-shoot' if self.moving else 'shoot'
        # The laser aiming, or the frame a shot fires (shown however long the frame: a hitch
        # longer than the pose would otherwise skip it, leaving the remote out of the hand)
        if self.laser_aiming or self._fired_this_frame:
            return pose
        # Moving, the pose holds while fire is held or the last shot is under 0.25 s old;
        # standing, for the standing shot's two frames
        pose_seconds = FIRE_SECONDS if self.moving else SHOOT_POSE_SECONDS
        # Fire held on the move keeps the remote's pose; a laser poses only while it draws
        held_on_the_move = (
            self.moving and self._trigger_held and self.weapon is Weapon.CHANNEL_CHANGER
        )
        if held_on_the_move or self._shot_age < pose_seconds - TIME_TOLERANCE:
            return pose
        return None

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
        if self.state in {KidState.KNOCKED_OUT, KidState.LYING, KidState.FADING, KidState.OUT}:
            return 'knocked-out'
        if self.state is KidState.CHEERING:
            return 'cheer'
        if self.state is KidState.RESPAWNING:
            return 'respawn'
        shooting = self._shooting_state()
        if shooting is not None:
            facing = _SHOOTING_FACING.get(self.facing, self.facing)
            return f'{shooting}_{_MIRRORED_FROM.get(facing, facing)}'
        state = 'walk' if self.moving else 'idle'
        drawn_facing = _MIRRORED_FROM.get(self.facing, self.facing)
        return f'{state}_{drawn_facing}'

    def dt_tick(self, dt: float) -> None:
        """Pose the kid for this frame: its animation, advanced, and its image, mirrored or not.

        Args:
            dt: The frame's time, in seconds.

        """
        self._advance_knockout(dt)
        self._fire_cooldown -= dt
        self._shot_age += dt
        wants_light = (
            self.weapon is Weapon.LASER_POINTER
            and self._trigger_held
            and self.state is KidState.ACTIVE
        )
        self.laser_aiming = self.battery.tick(dt=dt, wants_light=wants_light)
        self._warm_seconds = self._warm_seconds + dt if self.laser_aiming else 0.0
        self.laser_lit = (
            self.laser_aiming and self._warm_seconds >= WARM_UP_SECONDS - TIME_TOLERANCE
        )
        name = self.animation_name()
        # Each standing shot plays its pose from the first frame
        restart = self._fired_this_frame and name.startswith('shoot_')
        self._fired_this_frame = False
        if name != self._started_animation or restart:
            self.play(name)
            self._started_animation = name
        AnimatedSprite.update(self, dt)
        if self.laser_aiming and name.startswith('shoot_'):
            # Shining standing: the aim held, the arm out (shoot's first frame)
            self.set_frame(0)
        # Only standing, walking and shooting are mirrored: the knockout and respawn face down
        posed_facing = (
            _SHOOTING_FACING.get(self.facing, self.facing)
            if name in KID_HAND_POINTS
            else self.facing
        )
        facing_right = self.state is KidState.ACTIVE and posed_facing in _MIRRORED_FROM
        self.mirror_cache.show_frame(sprite=self, sprite_name=self.look_name, mirrored=facing_right)
        if self.state is KidState.FADING:
            left = 1.0 - self._state_seconds / OUT_FADE_SECONDS
            self.image = faded(self.drawn_frame_surface(), alpha=round(OPAQUE * left))
            self.dirty = 1
        self._blink()
        self._place_remote(mirrored=facing_right)
        self._place_dot(dt)

    def _place_dot(self, dt: float) -> None:
        """Shine the dot ahead of the kid's feet along its aim, inside the yard; or put it out."""
        if not self.laser_lit:
            self.dot.go_out()
            self.beam.go_out()
            return
        aim_x, aim_y = self.aim()
        centre_x = self.world_x + KID_WIDTH / 2 + aim_x * DOT_DISTANCE
        centre_y = self.world_y + KID_HEIGHT + aim_y * DOT_DISTANCE
        if self.bounds is not None:
            # Far enough in that a zombie standing on it (feet on the dot; its frame is a kid's,
            # 32x48) fits in the yard: half a frame from the sides, a frame's height from the top
            half_width = KID_WIDTH / 2
            centre_x = min(
                max(centre_x, self.bounds.left + half_width), self.bounds.right - half_width
            )
            centre_y = min(max(centre_y, self.bounds.top + KID_HEIGHT), self.bounds.bottom)
        self.dot.show_at(centre=(centre_x, centre_y))
        self.dot.dt_tick(dt)
        self.beam.shine(start=self.laser_pointer.muzzle(), end=(centre_x, centre_y), dt=dt)

    def _place_remote(self, *, mirrored: bool) -> None:
        """Put the held weapon on the hand point while a weapon animation plays; away otherwise."""
        held, other = (
            (self.laser_pointer, self.remote)
            if self.weapon is Weapon.LASER_POINTER
            else (self.remote, self.laser_pointer)
        )
        other.put_away()
        hand_points = KID_HAND_POINTS.get(self.current_animation)
        if hand_points is None:
            held.put_away()
            return
        hand_x, hand_y = hand_points[self.current_frame]
        if mirrored:
            hand_x = KID_WIDTH - 1 - hand_x
        held.hold(
            hand_x=self.world_x + hand_x,
            hand_y=self.world_y + hand_y,
            drawn_facing=self.current_animation.rpartition('_')[2],
            mirrored=mirrored,
            shown=not self.hidden,
        )

    @override
    def kill(self) -> None:
        """Leave the yard, with the remote, the laser pointer and its dot."""
        self.remote.kill()
        self.laser_pointer.kill()
        self.dot.kill()
        self.beam.kill()
        super().kill()

    def _advance_knockout(self, dt: float) -> None:
        """Move through the knockout's steps, and count down the untouchable time."""
        if self.state is KidState.OUT:
            return
        if self.state is KidState.FADING:
            self._state_seconds += dt
            if self._state_seconds >= OUT_FADE_SECONDS - TIME_TOLERANCE:
                self.state = KidState.OUT
            return
        step = _KNOCKOUT_STEPS.get(self.state)
        if step is not None:
            self._state_seconds += dt
            seconds, following = step
            if self.state is KidState.KNOCKED_OUT and self._last_life:
                following = KidState.FADING
            if self._state_seconds >= seconds - TIME_TOLERANCE:
                self.state = following
                self._state_seconds = 0.0
                if following is KidState.ACTIVE:
                    self.untouchable_seconds = UNTOUCHABLE_SECONDS
                    self.facing = KidFacing.DOWN
            return
        self.untouchable_seconds = max(0.0, self.untouchable_seconds - dt)

    def _blink(self) -> None:
        """Blink while untouchable: hidden and shown by turns (world sprites hide by ``hidden``).

        A kid out of lives is hidden for good.
        """
        if self.state is KidState.OUT:
            self.hidden = True
        elif self.untouchable_seconds > TIME_TOLERANCE:
            blinks = int((UNTOUCHABLE_SECONDS - self.untouchable_seconds) / BLINK_SECONDS)
            self.hidden = blinks % 2 == 1
        else:
            self.hidden = False

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: the animation advances in ``dt_tick`` only."""
