"""Tests for the Drawing Fire scene, on real pygame (the dummy driver)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from glitchygames.examples import drawing_fire
from glitchygames.examples.drawing_fire import game as drawing_fire_game
from glitchygames.examples.drawing_fire.game import PAPER_COLOR, PENCIL_COLOR, DrawingFireScene
from glitchygames.randomness import reset_streams

SCREEN_SIZE = (800, 480)
TEST_SEED = 20261025


@pytest.fixture(autouse=True)
def display():
    """The game's display: 800x480."""
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != SCREEN_SIZE:
        set_display_mode(size=SCREEN_SIZE)


@pytest.fixture
def scene():
    """A new battlefield, its random streams seeded."""
    reset_streams(seed=TEST_SEED)
    return DrawingFireScene(options={'input_mode': 'joystick'})


def test_the_scene_draws_paper_and_ground(scene):
    """The paper fills the screen and the ground line is pencilled on it."""
    scene.render(scene.screen)
    assert scene.screen.get_at((5, 5))[:3] == PAPER_COLOR
    ground_x = 400
    ground_y = round(scene.terrain.ground_y(ground_x))
    column = [scene.screen.get_at((ground_x, y))[:3] for y in range(ground_y - 2, ground_y + 3)]
    assert PENCIL_COLOR in column


def test_the_terrain_fits_the_screen_and_is_seeded(scene):
    """The terrain has a ground y per screen pixel, from the seeded stream."""
    assert len(scene.terrain.ground) == SCREEN_SIZE[0]
    reset_streams(seed=TEST_SEED)
    assert DrawingFireScene(options={'input_mode': 'joystick'}).terrain == scene.terrain


def test_main_runs_the_scene(mocker):
    """main() starts the engine with the Drawing Fire scene."""
    engine = mocker.patch.object(drawing_fire_game, 'GameEngine')
    drawing_fire.main()
    engine.assert_called_once_with(game=DrawingFireScene)
    engine.return_value.start.assert_called_once_with()


def test_the_scene_uses_the_sprite_group_it_is_given():
    """A given sprite group is the scene's group."""
    reset_streams(seed=TEST_SEED)
    groups = pygame.sprite.LayeredDirty()
    assert DrawingFireScene(options={'input_mode': 'joystick'}, groups=groups).all_sprites is groups
