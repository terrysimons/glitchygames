"""Tests for GameEngine properties.

This module tests GameEngine properties like input_devices, scene_manager, game, etc., on a real
engine: real pygame, the real display and real event managers. Only the joystick hardware is
stood in for (no test machine has joysticks attached).
"""

import os
import sys

import pygame
import pytest

from glitchygames.events.joystick import JoystickEventManager
from glitchygames.input.devices import JOYSTICK_KIND, DeviceDescriptor
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.scenes import Scene, SceneManager
from tests.input.stand_in_devices import install_stand_in_devices

# GameEngine parses sys.argv when it is constructed: a small window (the conftest puts the
# 800x600 test display back after the test), no frame pacing, quiet logs
ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')


class PropertiesTestGame(Scene):
    """The game scene the engines here are built with."""

    NAME = 'PropertiesTestGame'
    VERSION = '1.0'


def stand_in_joystick(*, device_index: int) -> DeviceDescriptor:
    """Describe a stand-in joystick (the replay's, which needs no hardware) at a device index.

    Returns:
        DeviceDescriptor: A joystick whose instance id is its device index.

    """
    return DeviceDescriptor(
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


@pytest.fixture
def real_engine(mocker):
    """Construct a real engine for PropertiesTestGame, leaving pygame as the test found it.

    The engine is GoldenTraceEngine (glitchygames/replay/tools/golden_traces.py): GameEngine
    opening a plain window, because SDL's dummy video driver warns "no fast renderer available"
    for GameEngine's SCALED window, an error under pytest's filterwarnings.

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

    def test_game_engine_input_devices_before_start(self, real_engine):
        """Before the event managers start, the engine sees no devices."""
        assert list(real_engine.input_devices) == []

    def test_game_engine_input_devices_property(self, real_engine):
        """Starting the event managers finds the attached joysticks, one device each."""
        # Hardware: two joysticks attached (stand-ins, through the devices door)
        install_stand_in_devices(
            descriptors=[stand_in_joystick(device_index=index) for index in range(2)]
        )

        real_engine.install_game(scene_class=PropertiesTestGame)

        assert [device.name for device in real_engine.input_devices] == [
            'Stand-in joystick 0',
            'Stand-in joystick 1',
        ]
        assert all(
            isinstance(proxy, JoystickEventManager.JoystickEventProxy)
            for proxy in real_engine.joystick_manager.joysticks.values()
        )
        assert sorted(real_engine.joystick_manager.joysticks) == [0, 1]
        # Scenes read the same registry
        assert real_engine.scene_manager.input_devices is real_engine.input_devices
