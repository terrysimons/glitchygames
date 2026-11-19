"""A neighbor in the yard: idle, panicking when a zombie comes near, saved or lost, then gone.

Feature plan 7, Task 5; character BOM section 6. Saving and losing play their effects where the
neighbor stood (``saved`` 5 frames of 0.06 s, ``lost`` 5 of 0.08 s), then everything leaves.
"""

from __future__ import annotations

import math
import random

import pygame
import pytest

from zombies_aint_my_neighbors.kid import Kid, MirrorCache
from zombies_aint_my_neighbors.neighbor import (
    LOST_SECONDS,
    NEIGHBOR_PLACES,
    PANIC_DISTANCE,
    SAVED_SECONDS,
    Neighbor,
    NeighborState,
    neighbor_places,
    touching,
)
from zombies_aint_my_neighbors.neighborhood import TV_PLACES, YARD_HEIGHT, YARD_WIDTH
from zombies_aint_my_neighbors.run_state import NeighborKind
from zombies_aint_my_neighbors.tv import TV_SIZE
from zombies_aint_my_neighbors.zombie import Zombie

SIXTIETH = 1.0 / 60.0


@pytest.fixture
def group() -> pygame.sprite.LayeredDirty:
    """The scene's sprites."""
    return pygame.sprite.LayeredDirty()


def neighbor_at(group, x=400.0, y=300.0, kind=NeighborKind.PIZZA_TEEN) -> Neighbor:
    """Return a neighbor standing at a place, posed.

    Returns:
        The neighbor.

    """
    neighbor = Neighbor(kind=kind, world_x=x, world_y=y, groups=group)
    neighbor.dt_tick(0.0)
    return neighbor


def zombie_at(x: float, y: float) -> Zombie:
    """Return a zombie standing at a place.

    Returns:
        The zombie.

    """
    return Zombie(world_x=x, world_y=y, mirror_cache=MirrorCache(), groups=None)


def run(neighbor: Neighbor, *, frames: int) -> None:
    """Tick a neighbor some sixtieths of a second."""
    for _ in range(frames):
        neighbor.dt_tick(SIXTIETH)


def test_the_plan_values():
    """96 px of panic; saved lasts 5 x 0.06 s and lost 5 x 0.08 s."""
    assert PANIC_DISTANCE == 96
    assert pytest.approx((0.3, 0.4)) == (SAVED_SECONDS, LOST_SECONDS)


@pytest.mark.parametrize('kind', list(NeighborKind))
def test_a_neighbor_stands_idle_by_default(group, kind):
    """Each kind loads its own sprite and idles."""
    neighbor = neighbor_at(group, kind=kind)

    assert neighbor.state is NeighborState.STANDING
    assert neighbor.current_animation == 'idle'
    assert neighbor.is_standing


@pytest.mark.parametrize(('offset', 'panics'), [(90.0, True), (100.0, False)])
def test_a_neighbor_panics_with_a_zombie_near(group, offset, panics):
    """Within 96 px (frame to frame), panic; farther, idle."""
    neighbor = neighbor_at(group)

    neighbor.notice(zombies=[zombie_at(400.0 + offset, 300.0)])
    neighbor.dt_tick(SIXTIETH)

    assert neighbor.current_animation == ('panic' if panics else 'idle')


def test_a_crumbling_zombie_frightens_nobody(group):
    """A zapped zombie is no threat."""
    neighbor = neighbor_at(group)
    zombie = zombie_at(420.0, 300.0)
    zombie.zap()

    neighbor.notice(zombies=[zombie])
    neighbor.dt_tick(SIXTIETH)

    assert neighbor.current_animation == 'idle'


@pytest.mark.parametrize(
    ('act', 'animation', 'seconds'),
    [('rescue', 'saved', SAVED_SECONDS), ('lose', 'lost', LOST_SECONDS)],
)
def test_a_neighbor_rescued_or_lost_plays_its_effect_then_is_gone(group, act, animation, seconds):
    """The neighbor hides, its effect plays where it stood, and then both leave the yard."""
    neighbor = neighbor_at(group)

    assert getattr(neighbor, act)()
    neighbor.dt_tick(SIXTIETH)

    assert neighbor.hidden
    assert not neighbor.is_standing
    effect = neighbor.effect
    assert effect is not None
    assert not effect.hidden
    assert effect.current_animation == animation
    assert (effect.world_x, effect.world_y) == (neighbor.world_x, neighbor.world_y)
    run(neighbor, frames=math.ceil(seconds / SIXTIETH) - 2)
    assert not neighbor.is_gone
    run(neighbor, frames=1)
    assert neighbor.is_gone
    assert not group.sprites()


def test_a_neighbor_is_rescued_or_lost_once(group):
    """Once rescued, a zombie can't lose them; once lost, a kid can't rescue them."""
    rescued = neighbor_at(group)
    lost = neighbor_at(group, x=600.0)

    assert rescued.rescue()
    assert lost.lose()

    assert not rescued.lose()
    assert not rescued.rescue()
    assert not lost.rescue()
    assert rescued.state is NeighborState.SAVED
    assert lost.state is NeighborState.LOST


def test_a_kid_touching_a_neighbor_is_touching(group):
    """The hitboxes meet, each shrunk by the 4 px margin, as zombies and kids touch."""
    neighbor = neighbor_at(group)
    near = Kid(
        look_name='dex', world_x=410.0, world_y=300.0, mirror_cache=MirrorCache(), groups=None
    )
    far = Kid(
        look_name='dex', world_x=440.0, world_y=300.0, mirror_cache=MirrorCache(), groups=None
    )
    near.dt_tick(0.0)
    far.dt_tick(0.0)

    assert touching(near, neighbor)
    assert not touching(far, neighbor)


def test_neighbor_places_are_drawn_from_the_stream_distinct_and_repeatable():
    """Eight of the twelve places, none twice; the same seed draws the same eight."""
    first = neighbor_places(stream=random.Random(5), count=8)
    again = neighbor_places(stream=random.Random(5), count=8)

    assert first == again
    assert len(set(first)) == 8
    assert set(first) <= set(NEIGHBOR_PLACES)
    assert len(NEIGHBOR_PLACES) == 12


def test_every_place_is_in_the_yard_clear_of_the_tvs_the_huddle_and_the_door():
    """Inside the hedges; a frame's width clear of each TV; away from the start and the exit."""
    huddle = pygame.Rect(YARD_WIDTH // 2 - 80, YARD_HEIGHT // 2 - 80, 160, 160)
    door = pygame.Rect(YARD_WIDTH // 2 - 80, 0, 160, 96)
    tvs = [pygame.Rect(int(x), int(y), TV_SIZE, TV_SIZE).inflate(64, 64) for x, y in TV_PLACES]
    for x, y in NEIGHBOR_PLACES:
        frame = pygame.Rect(x, y, 32, 48)
        assert pygame.Rect(16, 16, YARD_WIDTH - 32, YARD_HEIGHT - 32).contains(frame), (x, y)
        assert not frame.colliderect(huddle), (x, y)
        assert not frame.colliderect(door), (x, y)
        assert not any(frame.colliderect(tv) for tv in tvs), (x, y)


def test_a_standing_neighbor_has_no_playing_effect(group):
    """Asked for its effect before a rescue or loss, a neighbor says it still stands."""
    neighbor = neighbor_at(group)

    with pytest.raises(RuntimeError, match='still stands'):
        _ = neighbor.playing_effect


def test_a_rescued_neighbors_playing_effect_is_its_rescue(group):
    """Once rescued, its playing effect is the rescue, where it stood."""
    neighbor = neighbor_at(group)

    neighbor.rescue()

    assert neighbor.playing_effect is neighbor.effect
    assert neighbor.playing_effect.current_animation == 'saved'
