"""A kid on screen: which animation it plays, its mirrored right side, and the shared flip cache.

Feature plan 4 (plans/2026-11-14-zombies-aint-my-neighbors-4-walking.md), Task 1; the facing and
mirroring rules are the character BOM's section 1.
"""

from __future__ import annotations

import pygame
import pytest

from zombies_aint_my_neighbors.kid import (
    KNOCKOUT_SECONDS,
    LYING_SECONDS,
    RESPAWN_SECONDS,
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
