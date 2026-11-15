"""A Lawn Zombie in the yard: it shambles toward the nearest standing kid, and grabs.

Feature plan 5 (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md), Task 4.
"""

from __future__ import annotations

import itertools
import math

import pygame
import pytest

from zombies_aint_my_neighbors.kid import Kid, MirrorCache
from zombies_aint_my_neighbors.laser import LaserDot
from zombies_aint_my_neighbors.neighborhood import WALK_SPEED
from zombies_aint_my_neighbors.zombie import (
    CRUMBLE_SECONDS,
    FADE_SECONDS,
    FLASH_SECONDS,
    GRAB_SECONDS,
    LURE_DISTANCE,
    ZOMBIE_SPEED,
    Zombie,
    ZombieFacing,
    touches,
)

SIXTIETH = 1.0 / 60.0


@pytest.fixture
def cache() -> MirrorCache:
    """The scene's flip cache."""
    return MirrorCache()


def kid_at(cache: MirrorCache, x: float, y: float) -> Kid:
    """Return Dex standing at a place.

    Returns:
        The kid.

    """
    kid = Kid(look_name='dex', world_x=x, world_y=y, mirror_cache=cache, groups=None)
    kid.dt_tick(0.0)
    return kid


def zombie_at(cache: MirrorCache, x: float, y: float) -> Zombie:
    """Return a Lawn Zombie at a place.

    Returns:
        The zombie.

    """
    return Zombie(world_x=x, world_y=y, mirror_cache=cache, groups=None)


def shamble(zombie: Zombie, kids: list[Kid], *, seconds: float) -> None:
    """Let a zombie chase for some seconds at 60 frames a second."""
    for _ in range(round(seconds * 60)):
        zombie.chase(kids=kids, dt=SIXTIETH)
        zombie.dt_tick(SIXTIETH)


def test_a_zombie_shambles_toward_a_kid_at_zombie_speed(cache):
    """A second of chasing a kid to its right covers the zombie's speed."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 500.0, 100.0)

    shamble(zombie, [kid], seconds=1.0)

    assert zombie.world_x == pytest.approx(100.0 + ZOMBIE_SPEED, abs=1.0)
    assert zombie.world_y == pytest.approx(100.0)


def test_a_zombie_is_slower_than_a_kid():
    """The BOM: slower than a kid (a third of the walk)."""
    assert ZOMBIE_SPEED < WALK_SPEED / 2


def test_a_zombie_chases_the_nearest_standing_kid(cache):
    """Of two kids, the nearer; once that one is knocked out, the other."""
    zombie = zombie_at(cache, 100.0, 100.0)
    near = kid_at(cache, 160.0, 100.0)
    far = kid_at(cache, 100.0, 400.0)

    shamble(zombie, [near, far], seconds=0.25)
    assert zombie.facing is ZombieFacing.RIGHT

    near.knock_out()
    shamble(zombie, [near, far], seconds=0.25)
    assert zombie.facing is ZombieFacing.DOWN


def test_a_zombie_stands_when_no_kid_is_up(cache):
    """With every kid knocked out, the zombie holds still on walk frame 0 (its idle, BOM 5.1)."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 300.0, 100.0)
    kid.knock_out()

    shamble(zombie, [kid], seconds=0.5)

    assert (zombie.world_x, zombie.world_y) == (100.0, 100.0)
    assert zombie.current_frame == 0
    assert not zombie.is_playing


@pytest.mark.parametrize(
    ('kid_place', 'facing', 'animation'),
    [
        ((100.0, 300.0), ZombieFacing.DOWN, 'walk_down'),
        ((100.0, -200.0), ZombieFacing.UP, 'walk_up'),
        ((-200.0, 100.0), ZombieFacing.LEFT, 'walk_left'),
        ((400.0, 100.0), ZombieFacing.RIGHT, 'walk_left'),
    ],
)
def test_a_zombie_faces_the_way_it_shambles(cache, kid_place, facing, animation):
    """Four facings; right plays the left walk, mirrored."""
    zombie = zombie_at(cache, 100.0, 100.0)

    shamble(zombie, [kid_at(cache, *kid_place)], seconds=0.1)

    assert zombie.facing is facing
    assert zombie.current_animation == animation


def test_a_zombie_facing_right_shows_its_left_frame_mirrored(cache):
    """Right is left flipped, through the scene's cache, with the hitbox flipped."""
    zombie = zombie_at(cache, 100.0, 100.0)

    shamble(zombie, [kid_at(cache, 400.0, 100.0)], seconds=0.1)

    mirrored = pygame.transform.flip(zombie.drawn_frame_surface(), flip_x=True, flip_y=False)
    width, height = mirrored.get_size()
    assert all(
        zombie.image.get_at((x, y)) == mirrored.get_at((x, y))
        for y in range(height)
        for x in range(width)
    )
    assert zombie.hitbox_flip_x


def test_a_grab_plays_then_the_zombie_walks_on(cache):
    """The lunge and clamp (0.2 s), then the shamble again."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 100.0, 300.0)
    shamble(zombie, [kid], seconds=0.1)

    zombie.grab()
    zombie.dt_tick(0.0)
    assert zombie.current_animation == 'grab_down'

    shamble(zombie, [kid], seconds=GRAB_SECONDS + 0.05)
    assert zombie.current_animation == 'walk_down'


def test_a_grabbing_zombie_stands_still(cache):
    """While it grabs, the zombie does not move."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 100.0, 300.0)
    zombie.grab()
    before = (zombie.world_x, zombie.world_y)

    zombie.chase(kids=[kid], dt=SIXTIETH)

    assert (zombie.world_x, zombie.world_y) == before


def test_touching_means_the_hitboxes_meet_with_the_forgiveness_margin(cache):
    """Overlapping bodies touch; frames that only brush within the margin do not."""
    zombie = zombie_at(cache, 100.0, 100.0)
    overlapping = kid_at(cache, 110.0, 100.0)
    # Both bodies are 20 wide from x+6 (106-126 and 122-142): they overlap by 4 px, which the
    # 4 px margin on each side forgives
    brushing = kid_at(cache, 116.0, 100.0)
    apart = kid_at(cache, 300.0, 100.0)

    assert touches(zombie=zombie, kid=overlapping)
    assert not touches(zombie=zombie, kid=brushing)
    assert not touches(zombie=zombie, kid=apart)


def test_a_zombie_never_walks_faster_diagonally(cache):
    """Chasing diagonally covers the same distance a second."""
    zombie = zombie_at(cache, 100.0, 100.0)

    shamble(zombie, [kid_at(cache, 500.0, 500.0)], seconds=1.0)

    travelled = math.hypot(zombie.world_x - 100.0, zombie.world_y - 100.0)
    assert travelled == pytest.approx(ZOMBIE_SPEED, abs=1.0)


# A zapped zombie (feature plan 6): one zap; a 0.05 s white flash; crumble (5 frames, 0.5 s),
# touching no one; the slippers (crumble's last frame) fade out over 0.5 s; then it is gone


def visible_and_clear_pixels(surface: pygame.Surface) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return one drawn pixel and one transparent pixel of a frame.

    Returns:
        (a drawn pixel's position, a transparent pixel's position).

    """
    mask = pygame.mask.from_surface(surface)
    width, height = surface.get_size()
    cells = [(x, y) for y in range(height) for x in range(width)]
    drawn = next(cell for cell in cells if mask.get_at(cell))
    clear = next(cell for cell in cells if not mask.get_at(cell))
    return drawn, clear


def test_a_zapped_zombie_crumbles(cache):
    """One zap: it plays crumble, facing down, never mirrored."""
    zombie = zombie_at(cache, 100.0, 100.0)
    zombie.facing = ZombieFacing.RIGHT
    zombie.dt_tick(SIXTIETH)

    assert zombie.zap()
    zombie.dt_tick(SIXTIETH)

    assert zombie.current_animation == 'crumble'
    assert zombie.is_dying
    assert zombie.hitbox_flip_x is False


def test_a_crumbling_zombie_takes_no_second_zap(cache):
    """A zap passing a dying zombie is not spent on it."""
    zombie = zombie_at(cache, 100.0, 100.0)
    zombie.zap()

    assert not zombie.zap()


def test_a_crumbling_zombie_neither_chases_nor_touches(cache):
    """It stays where it fell, and a kid standing in it is not knocked out."""
    kid = kid_at(cache, 100.0, 100.0)
    zombie = zombie_at(cache, 100.0, 100.0)
    zombie.zap()

    shamble(zombie, [kid], seconds=0.25)

    assert (zombie.world_x, zombie.world_y) == (100.0, 100.0)
    assert not touches(zombie=zombie, kid=kid)


def test_a_zapped_zombie_flashes_white_for_its_flash_time(cache):
    """For 0.05 s its drawn pixels are white and its clear ones stay clear; then it crumbles."""
    assert FLASH_SECONDS == 0.05
    zombie = zombie_at(cache, 100.0, 100.0)
    zombie.zap()
    zombie.dt_tick(SIXTIETH)
    drawn, clear = visible_and_clear_pixels(zombie.drawn_frame_surface())

    assert tuple(zombie.image.get_at(drawn))[:3] == (255, 255, 255)
    assert pygame.mask.from_surface(zombie.image).get_at(clear) == 0
    for _ in range(2):
        zombie.dt_tick(SIXTIETH)
    assert zombie.image is zombie.drawn_frame_surface()


def test_the_crumble_lasts_its_five_frames_then_the_slippers_fade(cache):
    """30 frames of crumble at full strength; then each frame fainter than the last."""
    zombie = zombie_at(cache, 100.0, 100.0)
    zombie.zap()
    for _ in range(round(CRUMBLE_SECONDS / SIXTIETH)):
        zombie.dt_tick(SIXTIETH)
    assert zombie.current_frame == 4
    alphas = []
    for _ in range(round(FADE_SECONDS / SIXTIETH) - 1):
        zombie.dt_tick(SIXTIETH)
        alphas.append(zombie.image.get_alpha())

    assert all(later < earlier for earlier, later in itertools.pairwise(alphas))


def test_a_faded_zombie_is_gone(cache):
    """After its crumble and fade (1.0 s) it is gone: hidden, but still in its group.

    The scene's pool reuses it, and a sprite removed from every group must not be held
    (tests/replay/test_removed_sprites_are_freed.py), so it is hidden, never removed.
    """
    group = pygame.sprite.LayeredDirty()
    zombie = Zombie(world_x=0.0, world_y=0.0, mirror_cache=cache, groups=group)
    zombie.zap()
    total = round((CRUMBLE_SECONDS + FADE_SECONDS) / SIXTIETH)
    for _ in range(total - 1):
        zombie.dt_tick(SIXTIETH)
    assert not zombie.hidden

    zombie.dt_tick(SIXTIETH)

    assert zombie.is_gone
    assert zombie.hidden
    assert zombie.alive()


def test_a_faded_zombie_comes_back_fresh(cache):
    """Reused from the pool: standing, walking, untouched by its last life."""
    group = pygame.sprite.LayeredDirty()
    zombie = Zombie(world_x=0.0, world_y=0.0, mirror_cache=cache, groups=group)
    zombie.zap()
    for _ in range(round((CRUMBLE_SECONDS + FADE_SECONDS) / SIXTIETH)):
        zombie.dt_tick(SIXTIETH)
    assert zombie.is_gone

    zombie.spawn_at(world_x=50.0, world_y=60.0)
    zombie.dt_tick(SIXTIETH)

    assert not zombie.hidden

    assert (zombie.world_x, zombie.world_y) == (50.0, 60.0)
    assert not zombie.is_dying
    assert not zombie.is_gone
    assert zombie.facing is ZombieFacing.DOWN
    assert zombie.current_animation == 'walk_down'
    assert zombie.image is zombie.drawn_frame_surface()


def test_a_zombie_chases_the_nearest_of_kids_and_standing_neighbors(cache):
    """Feature plan 7: neighbors are prey too; a saved or lost one is not."""
    from zombies_aint_my_neighbors.neighbor import Neighbor
    from zombies_aint_my_neighbors.run_state import NeighborKind

    kid = kid_at(cache, 400.0, 100.0)
    neighbor = Neighbor(kind=NeighborKind.PIZZA_TEEN, world_x=100.0, world_y=160.0, groups=None)
    zombie = zombie_at(cache, 100.0, 100.0)

    zombie.chase(kids=[kid], neighbors=[neighbor], dt=0.5)
    assert zombie.facing is ZombieFacing.DOWN

    neighbor.rescue()
    zombie.chase(kids=[kid], neighbors=[neighbor], dt=0.5)
    assert zombie.facing is ZombieFacing.RIGHT


# The lure (feature plan 8): a zombie whose feet are within 240 px of a lit dot chases the nearest
# dot instead of any kid or neighbor, and stands on it once there


def dot_at(x: float, y: float) -> LaserDot:
    """Return a lit dot centred on a point.

    Returns:
        The dot.

    """
    dot = LaserDot(groups=None)
    dot.show_at(centre=(x, y))
    return dot


def zombie_feet(zombie: Zombie) -> tuple[float, float]:
    """Return the middle of a zombie's feet.

    Returns:
        The point.

    """
    return (zombie.world_x + 16, zombie.world_y + 48)


def test_a_zombie_near_a_dot_chases_it_over_a_nearer_kid(cache):
    """The kid is right beside it; the dot 200 px off: it turns for the dot."""
    zombie = zombie_at(cache, 400.0, 300.0)
    kid = kid_at(cache, 440.0, 300.0)
    dot = dot_at(416.0, 348.0 + 200.0)

    zombie.chase(kids=[kid], dt=0.5, dots=[dot])

    assert zombie.facing is ZombieFacing.DOWN
    assert zombie.world_y > 300.0


def test_a_zombie_beyond_the_lures_reach_ignores_the_dot(cache):
    """250 px away (feet to dot), it keeps after the kid."""
    assert LURE_DISTANCE == 240
    zombie = zombie_at(cache, 400.0, 300.0)
    kid = kid_at(cache, 480.0, 300.0)
    dot = dot_at(416.0, 348.0 + 250.0)

    zombie.chase(kids=[kid], dt=0.5, dots=[dot])

    assert zombie.facing is ZombieFacing.RIGHT


def test_a_lured_zombie_stands_on_the_dot(cache):
    """It walks until its feet are on the dot, then stands still there."""
    zombie = zombie_at(cache, 400.0, 300.0)
    dot = dot_at(500.0, 400.0)

    for _ in range(round(10.0 * 60)):
        zombie.chase(kids=[], dt=SIXTIETH, dots=[dot])
        zombie.dt_tick(SIXTIETH)

    assert zombie_feet(zombie) == pytest.approx((500.0, 400.0), abs=1.0)
    assert not zombie.moving


def test_a_zombie_goes_for_the_nearest_of_two_dots(cache):
    """Two lit dots in reach: the nearer wins."""
    zombie = zombie_at(cache, 400.0, 300.0)
    near = dot_at(416.0 - 100.0, 348.0)
    far = dot_at(416.0 + 200.0, 348.0)

    zombie.chase(kids=[], dt=0.5, dots=[far, near])

    assert zombie.facing is ZombieFacing.LEFT


def test_a_dot_that_has_gone_out_lures_nobody(cache):
    """Only a shining dot pulls."""
    zombie = zombie_at(cache, 400.0, 300.0)
    kid = kid_at(cache, 480.0, 300.0)
    dot = dot_at(416.0, 348.0 + 100.0)
    dot.go_out()

    zombie.chase(kids=[kid], dt=0.5, dots=[dot])

    assert zombie.facing is ZombieFacing.RIGHT
