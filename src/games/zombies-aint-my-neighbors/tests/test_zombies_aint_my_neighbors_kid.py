"""A kid on screen: which animation it plays, its mirrored right side, and the shared flip cache.

Feature plan 4 (plans/2026-11-14-zombies-aint-my-neighbors-4-walking.md), Task 1; the facing and
mirroring rules are the character BOM's section 1.
"""

from __future__ import annotations

import math

import pygame
import pytest

from zombies_aint_my_neighbors.art.hand_points import KID_HAND_POINTS
from zombies_aint_my_neighbors.art.weapon_rig import remote_tip
from zombies_aint_my_neighbors.kid import (
    BLINK_SECONDS,
    FIRE_SECONDS,
    KNOCKOUT_SECONDS,
    LYING_SECONDS,
    RESPAWN_SECONDS,
    SHOOT_POSE_SECONDS,
    UNTOUCHABLE_SECONDS,
    Kid,
    KidFacing,
    KidState,
    MirrorCache,
)

# The walk's frame interval (BOM section 3), and a step just past it
WALK_INTERVAL = 0.12
PAST_ONE_WALK_FRAME = WALK_INTERVAL + 0.01
SIXTIETH_OF_A_SECOND = 1.0 / 60.0
# The knockout's last frame: flat, with stars (BOM section 3)
KNOCKOUT_LAST_FRAME = 4


def same_pixels(first: pygame.Surface, second: pygame.Surface) -> bool:
    """Return whether two surfaces hold the same size and pixels.

    Returns:
        True when every pixel matches.

    """
    if first.get_size() != second.get_size():
        return False
    width, height = first.get_size()
    return all(
        first.get_at((x, y)) == second.get_at((x, y)) for y in range(height) for x in range(width)
    )


@pytest.fixture
def cache() -> MirrorCache:
    """A fresh flip cache, as a scene owns one."""
    return MirrorCache()


@pytest.fixture
def kid(cache: MirrorCache) -> Kid:
    """Dex, standing in the yard."""
    return Kid(look_name='dex', world_x=100.0, world_y=200.0, mirror_cache=cache, groups=None)


def test_a_new_kid_stands_facing_down(kid):
    """A kid starts idle, facing the viewer."""
    kid.dt_tick(0.0)

    assert kid.facing is KidFacing.DOWN
    assert kid.current_animation == 'idle_down'


@pytest.mark.parametrize(
    ('direction', 'facing', 'animation'),
    [
        ((0.0, 1.0), KidFacing.DOWN, 'walk_down'),
        ((0.0, -1.0), KidFacing.UP, 'walk_up'),
        ((-1.0, 0.0), KidFacing.LEFT, 'walk_left'),
        ((1.0, 0.0), KidFacing.RIGHT, 'walk_left'),
        # The diagonals: down-right and up-right play down-left and up-left, mirrored
        ((-0.7, 0.7), KidFacing.DOWN_LEFT, 'walk_down-left'),
        ((-0.7, -0.7), KidFacing.UP_LEFT, 'walk_up-left'),
        ((0.7, 0.7), KidFacing.DOWN_RIGHT, 'walk_down-left'),
        ((0.7, -0.7), KidFacing.UP_RIGHT, 'walk_up-left'),
        # The nearest of the eight: mostly up, a little right, is up
        ((0.3, -0.9), KidFacing.UP, 'walk_up'),
        ((0.9, 0.3), KidFacing.RIGHT, 'walk_left'),
    ],
)
def test_walking_faces_the_way_it_moves(kid, direction, facing, animation):
    """The nearest of eight facings; the right-hand ones play their left animations, mirrored."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])

    kid.dt_tick(0.0)

    assert kid.facing is facing
    assert kid.current_animation == animation


def test_stopping_idles_in_the_same_facing(kid):
    """A kid that stops keeps facing the way it went."""
    kid.walk(direction_x=0.0, direction_y=-1.0)
    kid.dt_tick(0.0)

    kid.walk(direction_x=0.0, direction_y=0.0)
    kid.dt_tick(0.0)

    assert kid.facing is KidFacing.UP
    assert kid.current_animation == 'idle_up'


def test_facing_right_shows_the_left_frame_mirrored(kid):
    """Right is left flipped (BOM section 1): the image is the drawn left frame, mirrored."""
    kid.walk(direction_x=1.0, direction_y=0.0)

    kid.dt_tick(0.0)

    mirrored = pygame.transform.flip(kid.drawn_frame_surface(), flip_x=True, flip_y=False)
    assert same_pixels(kid.image, mirrored)
    assert not same_pixels(kid.image, kid.drawn_frame_surface())


def test_facing_left_shows_the_frame_as_drawn(kid):
    """Left needs no flip: the image is the engine's drawn frame."""
    kid.walk(direction_x=-1.0, direction_y=0.0)

    kid.dt_tick(0.0)

    assert kid.image is kid.drawn_frame_surface()


def test_the_hitbox_mirrors_only_when_facing_right(kid):
    """``hitbox_flip_x`` follows the mirrored side."""
    kid.walk(direction_x=1.0, direction_y=0.0)
    kid.dt_tick(0.0)
    assert kid.hitbox_flip_x

    kid.walk(direction_x=-1.0, direction_y=0.0)
    kid.dt_tick(0.0)
    assert not kid.hitbox_flip_x


def test_the_walk_cycle_advances_across_ticks_and_is_never_restarted(kid):
    """Walking the same way every tick keeps the cycle going (``play`` resets its timer).

    At 60 frames a second each tick is shorter than a walk frame, so a kid that restarted its
    animation every tick would never leave frame 0.
    """
    kid.walk(direction_x=0.0, direction_y=1.0)
    kid.dt_tick(0.0)
    for _ in range(20):
        kid.walk(direction_x=0.0, direction_y=1.0)
        kid.dt_tick(SIXTIETH_OF_A_SECOND)

    # 20/60 s is 0.33 s: two whole 0.12 s walk frames
    assert kid.current_frame == 2


def test_turning_from_left_to_right_keeps_the_cycle_going(kid):
    """Left and right share one animation, so turning round does not restart the walk."""
    kid.walk(direction_x=-1.0, direction_y=0.0)
    kid.dt_tick(0.0)
    kid.walk(direction_x=-1.0, direction_y=0.0)
    kid.dt_tick(PAST_ONE_WALK_FRAME)

    kid.walk(direction_x=1.0, direction_y=0.0)
    kid.dt_tick(0.0)

    assert kid.current_frame == 1


def test_update_does_not_advance_the_animation(kid):
    """The animation moves only in ``dt_tick`` (the pose rule), never twice a frame."""
    kid.walk(direction_x=0.0, direction_y=1.0)
    kid.dt_tick(0.0)

    kid.update(PAST_ONE_WALK_FRAME)

    assert kid.current_frame == 0


def test_kids_sharing_a_cache_flip_each_frame_once(cache):
    """The cache flips each (sprite, animation, frame) once, when first shown, then reuses it."""
    first = Kid(look_name='dex', world_x=0.0, world_y=0.0, mirror_cache=cache, groups=None)
    second = Kid(look_name='dex', world_x=50.0, world_y=0.0, mirror_cache=cache, groups=None)
    for kid in (first, second):
        kid.walk(direction_x=1.0, direction_y=0.0)
        kid.dt_tick(0.0)

    assert cache.flips == 1
    assert first.image is second.image


def test_different_kids_never_share_a_mirrored_frame(cache):
    """The cache keys by sprite too: Marisol's mirrored frame is hers, not Dex's."""
    dex = Kid(look_name='dex', world_x=0.0, world_y=0.0, mirror_cache=cache, groups=None)
    marisol = Kid(look_name='marisol', world_x=0.0, world_y=0.0, mirror_cache=cache, groups=None)
    for kid in (dex, marisol):
        kid.walk(direction_x=1.0, direction_y=0.0)
        kid.dt_tick(0.0)

    assert cache.flips == 2
    assert not same_pixels(dex.image, marisol.image)


def test_a_kid_is_a_world_sprite_with_its_position(kid):
    """The engine places it from its world position (CLAUDE.md, World Space)."""
    from glitchygames.world import CoordinateSpace, is_world_positioned

    assert Kid.COORDINATE_SPACE is CoordinateSpace.WORLD
    assert is_world_positioned(kid)
    assert (kid.world_x, kid.world_y) == (100.0, 200.0)


@pytest.mark.parametrize(
    ('direction', 'animation'),
    [((0.7, 0.7), 'walk_down-left'), ((0.7, -0.7), 'walk_up-left'), ((1.0, 0.0), 'walk_left')],
)
def test_every_right_hand_facing_shows_its_left_frame_mirrored(kid, direction, animation):
    """Right, down-right and up-right are their left-hand facings flipped (BOM section 1)."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])

    kid.dt_tick(0.0)

    assert kid.current_animation == animation
    mirrored = pygame.transform.flip(kid.drawn_frame_surface(), flip_x=True, flip_y=False)
    assert same_pixels(kid.image, mirrored)
    assert kid.hitbox_flip_x


@pytest.mark.parametrize('direction', [(-0.7, 0.7), (-0.7, -0.7)])
def test_left_hand_diagonals_show_their_frames_as_drawn(kid, direction):
    """Down-left and up-left need no flip."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])

    kid.dt_tick(0.0)

    assert kid.image is kid.drawn_frame_surface()
    assert not kid.hitbox_flip_x


# --- Knocked out (feature plan 5, Task 6) -----------------------------------------------------


# A minute of frames: a kid that has not reached a state by then never will
FRAME_LIMIT = 60 * 60


def tick_while(kid: Kid, *, state: KidState, reached: bool = False) -> list[int]:
    """Tick a kid while it is in a state (or, with ``reached``, until it is), failing at the limit.

    Returns:
        The frame index shown before each tick.

    """
    frames: list[int] = []
    for _ in range(FRAME_LIMIT):
        if (kid.state is state) is reached:
            return frames
        frames.append(kid.current_frame)
        kid.dt_tick(SIXTIETH_OF_A_SECOND)
    pytest.fail(f'the kid never {"reached" if reached else "left"} {state}')


def run_for(kid: Kid, *, seconds: float) -> None:
    """Tick a kid for some seconds at 60 frames a second."""
    for _ in range(round(seconds * 60)):
        kid.dt_tick(SIXTIETH_OF_A_SECOND)


def test_a_knocked_out_kid_plays_its_knockout_and_cannot_move(kid):
    """A zombie's touch: the knockout plays, and the player's input no longer moves the kid."""
    kid.dt_tick(0.0)

    assert kid.knock_out()

    kid.walk(direction_x=1.0, direction_y=0.0)
    kid.dt_tick(0.0)
    assert kid.state is KidState.KNOCKED_OUT
    assert kid.current_animation == 'knocked-out'
    assert not kid.can_move
    assert not kid.moving
    assert not kid.is_touchable


def test_a_knocked_out_kid_lies_still_then_loads_back_in(kid):
    """The knockout (0.5 s), lying still (1.0 s), then the respawn plays (0.4 s)."""
    kid.knock_out()

    run_for(kid, seconds=KNOCKOUT_SECONDS + 0.05)
    assert kid.state is KidState.LYING
    assert kid.current_animation == 'knocked-out'
    # Lying still holds the knockout's last frame (flat, with stars): it never plays again
    frames_while_lying = set(tick_while(kid, state=KidState.LYING))
    assert frames_while_lying == {KNOCKOUT_LAST_FRAME}
    assert kid.state is KidState.RESPAWNING
    assert kid.current_animation == 'respawn'
    run_for(kid, seconds=RESPAWN_SECONDS)

    assert kid.state is KidState.ACTIVE
    assert kid.can_move
    assert kid.current_animation == 'idle_down'


def test_a_respawned_kid_blinks_and_cannot_be_knocked_out_for_a_while(kid):
    """Untouchable for 2 s after loading back in, blinking; then touchable and steady again."""
    kid.knock_out()
    run_for(kid, seconds=KNOCKOUT_SECONDS + LYING_SECONDS + RESPAWN_SECONDS + 0.05)
    assert kid.state is KidState.ACTIVE
    hidden_seen = set()
    for _ in range(30):
        kid.dt_tick(SIXTIETH_OF_A_SECOND)
        hidden_seen.add(kid.hidden)

    assert hidden_seen == {True, False}
    assert not kid.is_touchable
    assert not kid.knock_out()
    run_for(kid, seconds=UNTOUCHABLE_SECONDS)
    assert kid.is_touchable
    assert not kid.hidden


def test_a_kid_already_knocked_out_is_not_knocked_out_again(kid):
    """A second touch during the knockout changes nothing (no restart of the fall)."""
    kid.knock_out()
    run_for(kid, seconds=0.2)
    frame = kid.current_frame

    assert not kid.knock_out()
    kid.dt_tick(0.0)
    assert kid.state is KidState.KNOCKED_OUT
    assert kid.current_frame == frame


def test_knocked_out_frames_are_never_mirrored(kid):
    """The knockout is drawn facing down only: a kid that faced right still falls as drawn."""
    kid.walk(direction_x=1.0, direction_y=0.0)
    kid.dt_tick(0.0)

    kid.knock_out()
    kid.dt_tick(0.0)

    assert kid.image is kid.drawn_frame_surface()
    assert not kid.hitbox_flip_x


@pytest.mark.parametrize(
    ('state', 'seconds', 'following'),
    [
        (KidState.KNOCKED_OUT, KNOCKOUT_SECONDS, KidState.LYING),
        (KidState.LYING, LYING_SECONDS, KidState.RESPAWNING),
        (KidState.RESPAWNING, RESPAWN_SECONDS, KidState.ACTIVE),
    ],
)
def test_each_knockout_step_lasts_exactly_its_frames(kid, state, seconds, following):
    """At 60 frames a second, a 0.5 s step ends on frame 30, not 31 (frame times sum in floats)."""
    kid.knock_out()
    tick_while(kid, state=state, reached=True)
    frames = round(seconds * 60)

    run_for(kid, seconds=(frames - 1) / 60)
    assert kid.state is state
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    assert kid.state is following


def test_untouchable_lasts_exactly_its_frames(kid):
    """Two seconds untouchable is 120 frames."""
    kid.knock_out()
    tick_while(kid, state=KidState.ACTIVE, reached=True)

    run_for(kid, seconds=(round(UNTOUCHABLE_SECONDS * 60) - 1) / 60)
    assert not kid.is_touchable
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    assert kid.is_touchable


# Shooting the Channel Changer (feature plan 6): a press fires at once, holding fires every
# 0.25 s; the kid poses shoot_<f> standing and walk-shoot_<f> moving; the remote is drawn at the
# frame's hand point only while shooting


def frames_firing(kid: Kid, *, frames: int, held: bool = True) -> list[int]:
    """Tick a kid ``frames`` sixtieths with the trigger ``held``; return the frames that fired.

    Returns:
        The frame numbers that fired, from 0.

    """
    fired = []
    for frame in range(frames):
        if kid.pull_trigger(held=held):
            fired.append(frame)
        kid.dt_tick(SIXTIETH_OF_A_SECOND)
    return fired


def test_a_press_fires_at_once(kid):
    """The first frame the trigger is held fires."""
    kid.dt_tick(0.0)

    assert kid.pull_trigger(held=True)


def test_nothing_fires_while_the_trigger_is_up(kid):
    """No trigger, no shot."""
    assert frames_firing(kid, frames=60, held=False) == []


def test_holding_fires_four_times_a_second_on_exact_frames(kid):
    """Every 0.25 s: frames 0, 15, 30 and 45 of a second at 60 frames a second."""
    assert FIRE_SECONDS == 0.25
    assert frames_firing(kid, frames=60) == [0, 15, 30, 45]


def test_tapping_faster_than_the_rhythm_is_capped(kid):
    """A press within 0.25 s of the last shot waits: four shots a second at most."""
    assert kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    kid.pull_trigger(held=False)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert not kid.pull_trigger(held=True)


def test_a_knocked_out_kid_cannot_fire(kid):
    """Down, no shots; nor while it lies still or loads back in."""
    kid.knock_out()

    total = round((KNOCKOUT_SECONDS + LYING_SECONDS + RESPAWN_SECONDS) / SIXTIETH_OF_A_SECOND)
    assert frames_firing(kid, frames=total - 1) == []


@pytest.mark.parametrize(
    ('direction', 'animation', 'mirrored'),
    [
        ((0.0, 1.0), 'shoot_down', False),
        ((0.0, -1.0), 'shoot_up', False),
        ((-1.0, 0.0), 'shoot_left', False),
        ((1.0, 0.0), 'shoot_left', True),
        # Diagonals use the nearest straight pose, the side one at exactly 45 degrees
        ((-0.7, 0.7), 'shoot_left', False),
        ((-0.7, -0.7), 'shoot_left', False),
        ((0.7, 0.7), 'shoot_left', True),
        ((0.7, -0.7), 'shoot_left', True),
    ],
)
def test_a_standing_shot_poses_the_nearest_straight_facing(kid, direction, animation, mirrored):
    """The kid turns as it walks, stops, then shoots in its facing's pose."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    kid.walk(direction_x=0.0, direction_y=0.0)
    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert kid.current_animation == animation
    assert kid.hitbox_flip_x is mirrored


def test_the_standing_pose_ends_after_its_two_frames(kid):
    """shoot_<f> lasts 0.16 s (two 0.08 s frames), then the kid idles."""
    kid.pull_trigger(held=True)
    for _ in range(round(SHOOT_POSE_SECONDS / SIXTIETH_OF_A_SECOND) - 1):
        kid.dt_tick(SIXTIETH_OF_A_SECOND)
        kid.pull_trigger(held=False)
        assert kid.current_animation == 'shoot_down'
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert kid.current_animation == 'idle_down'


def test_each_held_shot_restarts_the_standing_pose(kid):
    """A shot 0.25 s after the last plays shoot_<f> from its first frame again."""
    frames_firing(kid, frames=15)
    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert (kid.current_animation, kid.current_frame) == ('shoot_down', 0)


def test_walking_while_firing_plays_walk_shoot(kid):
    """Moving with the trigger held: walk-shoot_<f>, the walk's legs with the arms forward."""
    kid.walk(direction_x=-1.0, direction_y=0.0)
    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert kid.current_animation == 'walk-shoot_left'


def test_walk_shoot_holds_for_a_shot_under_a_quarter_second_old(kid):
    """Released after a shot, the kid keeps walk-shoot until the shot is 0.25 s old, then walks."""
    kid.walk(direction_x=0.0, direction_y=1.0)
    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    for _ in range(13):
        kid.walk(direction_x=0.0, direction_y=1.0)
        kid.pull_trigger(held=False)
        kid.dt_tick(SIXTIETH_OF_A_SECOND)
    assert kid.current_animation == 'walk-shoot_down'
    kid.walk(direction_x=0.0, direction_y=1.0)
    kid.pull_trigger(held=False)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert kid.current_animation == 'walk_down'


def test_the_remote_shows_only_while_shooting(kid):
    """Hidden standing; shown on the shot; hidden again when the pose ends."""
    kid.dt_tick(0.0)
    assert kid.remote.hidden

    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    assert not kid.remote.hidden

    for _ in range(round(SHOOT_POSE_SECONDS / SIXTIETH_OF_A_SECOND)):
        kid.pull_trigger(held=False)
        kid.dt_tick(SIXTIETH_OF_A_SECOND)
    assert kid.remote.hidden


@pytest.mark.parametrize(
    ('direction', 'namespace', 'mirrored'),
    [
        ((0.0, 1.0), 'shoot_down', False),
        ((0.0, -1.0), 'shoot_up', False),
        ((-1.0, 0.0), 'shoot_left', False),
        ((1.0, 0.0), 'shoot_left', True),
    ],
)
def test_the_remote_is_centred_on_the_hand_point(kid, direction, namespace, mirrored):
    """The remote's centre (6, 6) sits on the frame's hand point; a mirrored point is 31 - x."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    kid.walk(direction_x=0.0, direction_y=0.0)
    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    hand_x, hand_y = KID_HAND_POINTS[namespace][kid.current_frame]
    if mirrored:
        hand_x = 31 - hand_x

    assert (kid.remote.world_x + 6, kid.remote.world_y + 6) == (
        kid.world_x + hand_x,
        kid.world_y + hand_y,
    )
    assert kid.remote.hitbox_flip_x is mirrored


@pytest.mark.parametrize(
    ('direction', 'in_front'),
    [((0.0, 1.0), True), ((-1.0, 0.0), True), ((1.0, 0.0), True), ((0.0, -1.0), False)],
)
def test_the_remote_is_behind_the_kid_only_when_it_faces_up(kid, direction, in_front):
    """Facing up, the hands are in front of the body, away from the viewer."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert kid.remote_in_front is in_front


@pytest.mark.parametrize(
    ('direction', 'tip_facing'),
    [((0.0, 1.0), 'down'), ((0.0, -1.0), 'up'), ((-1.0, 0.0), 'left'), ((1.0, 0.0), 'right')],
)
def test_the_muzzle_is_the_remotes_led(kid, direction, tip_facing):
    """A zap starts at the middle of the LED's cell, wherever the remote is."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    kid.walk(direction_x=0.0, direction_y=0.0)
    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    tip_x, tip_y = remote_tip(facing=tip_facing)

    assert kid.muzzle() == (kid.remote.world_x + tip_x + 0.5, kid.remote.world_y + tip_y + 0.5)


@pytest.mark.parametrize(
    ('direction', 'aim'),
    [
        ((1.0, 0.0), (1.0, 0.0)),
        ((-1.0, 0.0), (-1.0, 0.0)),
        ((0.0, 1.0), (0.0, 1.0)),
        ((0.0, -1.0), (0.0, -1.0)),
        ((0.7, 0.7), (math.sqrt(0.5), math.sqrt(0.5))),
        ((-0.7, 0.7), (-math.sqrt(0.5), math.sqrt(0.5))),
        ((0.7, -0.7), (math.sqrt(0.5), -math.sqrt(0.5))),
        ((-0.7, -0.7), (-math.sqrt(0.5), -math.sqrt(0.5))),
    ],
)
def test_the_aim_is_the_eight_way_facing(kid, direction, aim):
    """Shots fly the way the kid faces, diagonals included, at unit length."""
    kid.walk(direction_x=direction[0], direction_y=direction[1])

    assert kid.aim() == pytest.approx(aim)


def test_a_blinking_kid_hides_its_remote_with_itself(kid):
    """Untouchable kids may shoot; when the blink hides the kid, the remote goes too."""
    kid.untouchable_seconds = UNTOUCHABLE_SECONDS - BLINK_SECONDS - 0.01
    kid.pull_trigger(held=True)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)

    assert kid.hidden
    assert kid.remote.hidden


def test_killing_a_kid_takes_its_remote(cache):
    """An unplugged pad's kid leaves the yard with its remote."""
    group = pygame.sprite.LayeredDirty()
    kid = Kid(look_name='dex', world_x=0.0, world_y=0.0, mirror_cache=cache, groups=group)

    kid.kill()

    assert not group.sprites()


def test_a_standing_shot_on_a_slow_frame_still_poses_and_places_the_remote(kid):
    """A slow frame still shows the shot and puts the remote in the hand.

    A frame longer than the pose (0.2 s, a hitch) must not leave the zap to start where the
    remote last was (or at the yard's corner, before any shot).
    """
    kid.walk(direction_x=-1.0, direction_y=0.0)
    kid.dt_tick(SIXTIETH_OF_A_SECOND)
    kid.walk(direction_x=0.0, direction_y=0.0)
    kid.pull_trigger(held=True)
    kid.dt_tick(0.2)
    hand_x, hand_y = KID_HAND_POINTS['shoot_left'][kid.current_frame]

    assert kid.current_animation == 'shoot_left'
    assert not kid.remote.hidden
    assert (kid.remote.world_x + 6, kid.remote.world_y + 6) == (
        kid.world_x + hand_x,
        kid.world_y + hand_y,
    )
