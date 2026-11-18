"""The sprite spawn event (events/sprite_spawn.py) and the engine's handler for it.

The AI console's ``/sprite`` posts one; the engine adds the sprite to the game's scene, live and
in a replay (plans/2026-11-17-sprite-command.md, Task 2).
"""

import logging
from typing import TYPE_CHECKING

import pytest

from glitchygames import world
from glitchygames.events.base import unhandled_event
from glitchygames.events.sprite_spawn import (
    SPRITE_SPAWN_EVENT,
    SpriteSpawn,
    add_spawned_sprite,
)
from glitchygames.scenes import Scene
from glitchygames.sprites.spawned import SpawnedSprite
from tests.engine.test_game_engine import _make_engine

if TYPE_CHECKING:
    import pygame

# Four pixels wide, two high
BAR_TEXT = """\
[sprite]
name = "bar"
pixels = \"\"\"
####
####
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 255
"""


def _spawn(*, toml_text: str = BAR_TEXT) -> SpriteSpawn:
    return SpriteSpawn(toml_text=toml_text, sprite_name='bar', world_x=100.0, world_y=50.0)


def _spawned_sprites(scene: Scene) -> list[SpawnedSprite]:
    return [sprite for sprite in scene.all_sprites if isinstance(sprite, SpawnedSprite)]


class PresentingScene(Scene):
    """A scene that only presents another (as the pause screen presents the paused game)."""

    def __init__(self, *, presented: Scene) -> None:
        """Present ``presented``."""
        super().__init__(options={})
        self.presented = presented

    @property
    def debug_subject(self) -> Scene:
        """The presented scene."""
        return self.presented


class StrictScene(Scene):
    """A scene that keeps every user event it is handed: a spawn must never be one."""

    def __init__(self) -> None:
        """Keep nothing yet."""
        super().__init__(options={})
        self.handed: list[object] = []

    def on_user_event(self, event):
        """Keep the event."""
        self.handed.append(event)


class RawEventScene(Scene):
    """A scene that takes raw events, bypassing the engine's handler table."""

    def __init__(self) -> None:
        """Keep every raw event it is handed."""
        super().__init__(options={})
        self.raw_events: list[pygame.event.Event] = []

    def process_event(self, event: pygame.event.Event) -> None:
        """Keep the event."""
        self.raw_events.append(event)


def test_a_spawn_round_trips_through_its_event():
    """The event a spawn posts carries everything the handler needs, unchanged."""
    spawn = _spawn()

    event = spawn.to_event()

    assert event.type == SPRITE_SPAWN_EVENT
    assert SpriteSpawn.from_event(event) == spawn


@pytest.mark.parametrize(('camera_x', 'camera_y'), [(0.0, 0.0), (300.0, 40.0)])
def test_a_spawn_adds_a_world_sprite_centered_on_its_point(camera_x, camera_y):
    """Centered on the world point on a still camera and a moved one; the camera moves it."""
    scene = Scene(options={})
    scene.camera.world_x, scene.camera.world_y = camera_x, camera_y

    sprite = add_spawned_sprite(spawn=_spawn(), scene=scene)

    assert sprite is not None
    assert _spawned_sprites(scene) == [sprite]
    assert (sprite.world_x, sprite.world_y) == (98.0, 49.0)
    assert world.screen_position_for(sprite=sprite, camera=scene.camera) == (
        round(98.0 - camera_x),
        round(49.0 - camera_y),
    )


def test_a_spawn_under_the_pause_screen_goes_to_the_paused_game():
    """The game's own scene, as /inspect describes it, not the screen presenting it."""
    game = Scene(options={})
    pause = PresentingScene(presented=game)

    add_spawned_sprite(spawn=_spawn(), scene=pause)

    assert len(_spawned_sprites(game)) == 1
    assert _spawned_sprites(pause) == []


def test_a_spawn_that_cannot_build_adds_nothing_and_logs_once(caplog):
    """One warning line naming the sprite, no traceback; the game goes on."""
    scene = Scene(options={})

    with caplog.at_level(logging.WARNING):
        sprite = add_spawned_sprite(spawn=_spawn(toml_text='[sprite\n'), scene=scene)

    assert sprite is None
    assert _spawned_sprites(scene) == []
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert 'bar' in warnings[0].getMessage()
    assert warnings[0].exc_info is None


def test_a_spawn_never_reaches_the_games_handlers(mocker):
    """The engine handles it, under --no-unhandled-events, before any scene sees it."""
    engine = _make_engine(mocker, '--no-unhandled-events')
    scene = StrictScene()
    engine._active_scene = scene
    mocker.patch('pygame.event.get', return_value=[_spawn().to_event()])
    unhandled = mocker.patch('glitchygames.events.base.unhandled_event', wraps=unhandled_event)

    assert engine.process_events() is True

    assert len(_spawned_sprites(scene)) == 1
    assert scene.handed == []
    unhandled.assert_not_called()


def test_a_raw_event_scene_still_gets_the_spawn_added(mocker):
    """A scene that takes raw events gets the sprite, never the event."""
    engine = _make_engine(mocker)
    scene = RawEventScene()
    engine._active_scene = scene
    mocker.patch('pygame.event.get', return_value=[_spawn().to_event()])

    engine.process_events()

    assert len(_spawned_sprites(scene)) == 1
    assert scene.raw_events == []


def test_a_spawn_with_no_scene_yet_is_logged_and_dropped(mocker, caplog):
    """Nowhere to add it: one warning naming the sprite, and the event still counts as handled."""
    engine = _make_engine(mocker)
    engine._active_scene = None
    mocker.patch('pygame.event.get', return_value=[_spawn().to_event()])

    with caplog.at_level(logging.WARNING):
        assert engine.process_events() is True

    assert any(
        "'bar'" in record.getMessage() and 'no scene yet' in record.getMessage()
        for record in caplog.records
    )
