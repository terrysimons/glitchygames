"""A scene's sprites always draw in dirty-rect mode, whatever the machine's speed (BUGS.md #190).

pygame's ``LayeredDirty.draw`` times itself and switches the next frame to full-screen mode when
a draw was slower than its threshold, so a slow machine drew different frames: forcing
full-screen mode changed the frames 184 tests present. ``Scene.all_sprites`` pins every group
it is given to dirty-rect mode (``pin_dirty_rect_drawing``).
"""

from __future__ import annotations

import itertools
import math

import pygame
import pytest

from glitchygames.scenes import Scene
from glitchygames.scenes.scene import pin_dirty_rect_drawing

# A clock where every draw seems to take 100 ms, far past pygame's 1000/80 ms threshold
SLOW_DRAW_MILLISECONDS = 100


@pytest.fixture
def slow_draws(monkeypatch):
    """Make every LayeredDirty draw look slow (each get_ticks call 100 ms after the last)."""
    ticks = itertools.count(step=SLOW_DRAW_MILLISECONDS)
    monkeypatch.setattr(pygame.sprite, 'get_ticks', lambda: next(ticks))


def _draw_twice(group: pygame.sprite.LayeredDirty) -> None:
    """Draw a group twice on a scratch surface (the first draw is always full-screen)."""
    surface = pygame.Surface((8, 8))
    group.draw(surface)
    group.draw(surface)


@pytest.mark.usefixtures('slow_draws')
def test_pygame_switches_a_slow_group_to_full_screen_drawing():
    """The mechanism: an unpinned group draws full-screen after a slow draw."""
    group = pygame.sprite.LayeredDirty()

    _draw_twice(group)

    assert group._use_update is False


@pytest.mark.usefixtures('slow_draws')
def test_a_pinned_group_keeps_dirty_rect_drawing_after_slow_draws():
    """However slow the draws, the next one is dirty-rect."""
    group = pygame.sprite.LayeredDirty()
    pin_dirty_rect_drawing(group)

    _draw_twice(group)

    assert group._use_update is True


def test_a_scenes_groups_are_pinned_however_they_are_given():
    """The default group, a given one, and one assigned later (as PaddleSlap does)."""
    default_scene = Scene()
    given_group = pygame.sprite.LayeredDirty()
    given_scene = Scene(groups=given_group)
    later_group = pygame.sprite.LayeredDirty()
    given_scene.all_sprites = later_group

    for group in (default_scene.all_sprites, given_group, later_group):
        assert group._time_threshold == math.inf
    assert given_scene.all_sprites is later_group


def test_a_group_that_is_not_layered_dirty_is_left_alone():
    """A plain group (a test's stand-in) has no drawing mode to pin."""
    group = pygame.sprite.Group()

    pin_dirty_rect_drawing(group)

    assert not hasattr(group, '_time_threshold')
