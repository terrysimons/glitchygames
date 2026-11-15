"""A kid on screen: which animation it plays, its mirrored right side, and the shared flip cache.

Feature plan 4 (plans/2026-11-14-zombies-aint-my-neighbors-4-walking.md), Task 1; the facing and
mirroring rules are the character BOM's section 1.
"""

from __future__ import annotations

import pygame
import pytest

from zombies_aint_my_neighbors.kid import Kid, KidFacing, MirrorCache

# The walk's frame interval (BOM section 3), and a step just past it
WALK_INTERVAL = 0.12
PAST_ONE_WALK_FRAME = WALK_INTERVAL + 0.01
SIXTIETH_OF_A_SECOND = 1.0 / 60.0


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
