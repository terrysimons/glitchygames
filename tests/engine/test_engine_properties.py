"""Tests for GameEngine properties.

This module tests GameEngine properties like joysticks, scene_manager, game, etc., on a real
engine: real pygame, the real display and real event managers. Only the joystick hardware is
stood in for (no test machine has joysticks attached).
"""

import os
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.record_golden_traces import GoldenTraceEngine

from glitchygames.events.joystick import JoystickEventManager
from glitchygames.input.devices import (
    JOYSTICK_KIND,
    DeviceDescriptor,
    LiveDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.scenes import Scene, SceneManager

# Constants for magic values
TEST_JOYSTICK_COUNT_2 = 2

# GameEngine parses sys.argv when it is constructed: a small window (the conftest puts the
# 800x600 test display back after the test), no frame pacing, quiet logs
ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')


class PropertiesTestGame(Scene):
    """The game scene the engines here are built with."""

    NAME = 'PropertiesTestGame'
    VERSION = '1.0'


def stand_in_joystick(*, device_index: int) -> ReplayJoystick:
    """Return a joystick stand-in (the replay's, which needs no hardware) for a device index.

    Returns:
        ReplayJoystick: A joystick whose instance id is its device index.

    """
    return ReplayJoystick(
        descriptor=DeviceDescriptor(
            kind=JOYSTICK_KIND,
            device_index=device_index,
            instance_id=device_index,
            name=f'Stand-in joystick {device_index}',
            guid=None,
            axis_count=2,
            button_count=4,
            hat_count=1,
            ball_count=0,
        )
    )


@pytest.fixture
def real_engine(mocker):
    """Construct a real engine for PropertiesTestGame, leaving pygame as the test found it.

    The engine is GoldenTraceEngine (scripts/record_golden_traces.py): GameEngine opening a
    plain window, because SDL's dummy video driver warns "no fast renderer available" for
    GameEngine's SCALED window, an error under pytest's filterwarnings.

    Yields:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    mocker.patch.object(sys, 'argv', ['test_engine_properties', *ENGINE_ARGUMENTS])
    # The engine writes SDL hints to the environment; the test's own values come back after
    mocker.patch.dict(os.environ)
    blocked_before = [
        pygame.event.get_blocked(event_type) for event_type in range(pygame.NUMEVENTS)
    ]
    yield GoldenTraceEngine(game=PropertiesTestGame)
    pygame.event.clear()
    # The event managers and the scene block and allow event types: put them back
    for event_type, was_blocked in enumerate(blocked_before):
        if was_blocked:
            pygame.event.set_blocked(event_type)
        else:
            pygame.event.set_allowed(event_type)


class TestEngineProperties:
    """Test GameEngine properties."""

    def test_game_engine_game_property(self, real_engine):
        """Before start(), the engine's game is the game class it was built with."""
        assert real_engine.game is PropertiesTestGame
        assert PropertiesTestGame.options is not None

    def test_game_engine_scene_manager_property(self, real_engine):
        """The engine adopts the SceneManager singleton, with its screen on the real display."""
        assert real_engine.scene_manager is SceneManager()
        assert real_engine.scene_manager.screen is pygame.display.get_surface()
        assert real_engine.scene_manager.screen.get_size() == real_engine.screen.get_size()

    def test_game_engine_joysticks_before_start(self, real_engine):
        """Before the event managers start, the engine knows no joysticks."""
        assert real_engine.joysticks == []
        assert real_engine.joystick_count == 0

    def test_game_engine_joystick_count_property(self, real_engine, mocker):
        """Starting the event managers counts the attached joysticks."""
        # Hardware: two joysticks attached
        mocker.patch.object(
            LiveDeviceRegistry, 'joystick_count', return_value=TEST_JOYSTICK_COUNT_2
        )
        mocker.patch.object(LiveDeviceRegistry, 'open_joystick', side_effect=stand_in_joystick)

        real_engine.install_game(scene_class=PropertiesTestGame)

        assert real_engine.joystick_count == TEST_JOYSTICK_COUNT_2

    def test_game_engine_joysticks_property(self, real_engine, mocker):
        """The engine's joysticks are the joystick manager's proxies, one per joystick."""
        # Hardware: two joysticks attached
        mocker.patch.object(
            LiveDeviceRegistry, 'joystick_count', return_value=TEST_JOYSTICK_COUNT_2
        )
        mocker.patch.object(LiveDeviceRegistry, 'open_joystick', side_effect=stand_in_joystick)

        real_engine.install_game(scene_class=PropertiesTestGame)

        assert len(real_engine.joysticks) == TEST_JOYSTICK_COUNT_2
        assert real_engine.joysticks == list(real_engine.joystick_manager.joysticks.values())
        assert all(
            isinstance(joystick, JoystickEventManager.JoystickEventProxy)
            for joystick in real_engine.joysticks
        )
        assert sorted(real_engine.joystick_manager.joysticks) == [0, 1]
