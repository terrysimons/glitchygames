"""Integration tests for event system through GameEngine.

This module tests the full event flow: Engine -> Managers -> Scene -> Stubs.

Every test starts the real engine with a real scene (the golden-trace harness: the engine without
its frame loop) and hands the engine's pump a scripted batch of real pygame events through the
event door (``ScriptedBatchSources``). The engine's own managers route each event to the scene.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.record_golden_traces import GoldenTraceEngine, GoldenTraceSceneManager, command_line

from glitchygames.engine import GameEngine
from glitchygames.events import UnhandledEventError
from glitchygames.events.audio import AudioEventManager
from glitchygames.events.controller import ControllerEventManager
from glitchygames.input.devices import CONTROLLER_KIND, DeviceDescriptor, ReplayDeviceRegistry
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene
from glitchygames.sources import install_sources

# A controller plugged in at startup: its instance id equals its device index
STAND_IN_CONTROLLER = DeviceDescriptor(
    kind=CONTROLLER_KIND,
    device_index=0,
    instance_id=0,
    name='Stand-in Controller',
    guid=None,
    axis_count=6,
    button_count=15,
    hat_count=0,
    ball_count=0,
)
# The same slot after a reconnect: SDL gave the device a new instance id
RECONNECTED_STAND_IN_CONTROLLER = DeviceDescriptor(
    kind=CONTROLLER_KIND,
    device_index=0,
    instance_id=7,
    name='Stand-in Controller',
    guid=None,
    axis_count=6,
    button_count=15,
    hat_count=0,
    ball_count=0,
)


class ScriptedBatchSources(LiveSources):
    """Live doors whose first pump returns a scripted batch (the real queue is drained too).

    The devices door answers with a replay registry holding one stand-in controller, so a
    controller can be "plugged in" without hardware.
    """

    def __init__(self, *, batch, controller=STAND_IN_CONTROLLER):
        """Create the doors with the batch their first pump returns and the controller."""
        super().__init__(random_seed=1)
        self.pending_batches = [batch]
        self.stand_in_devices = ReplayDeviceRegistry(
            descriptors=[controller], enumeration_answers=[]
        )

    def pump_events(self):
        """Drain SDL's queue, then return the scripted batch once and empty batches after.

        Returns:
            list[pygame.event.Event]: The batch.

        """
        pygame.event.get()
        return self.pending_batches.pop(0) if self.pending_batches else []

    def devices(self):
        """Return the stand-in device registry.

        Returns:
            ReplayDeviceRegistry: The registry with the stand-in controller.

        """
        return self.stand_in_devices


class AudioAndControllerRecordingScene(Scene):
    """A real scene that records the audio and controller events it receives."""

    def __init__(self, options=None, groups=None):
        """Create the scene with nothing received yet."""
        super().__init__(options=options, groups=groups)
        self.audio_events_received = []
        self.controller_events_received = []

    def on_audio_device_added_event(self, event):
        """Record the event."""
        self.audio_events_received.append(event)

    def on_controller_device_added_event(self, event):
        """Record the event."""
        self.controller_events_received.append(event)

    def on_controller_axis_motion_event(self, event):
        """Record the event."""
        self.controller_events_received.append(event)


def start_engine_with_scene(*, scene_class, extra_arguments=()):
    """Start the real engine with ``scene_class`` active, as GameEngine.start() would.

    Returns:
        tuple: The engine and its active scene.

    """
    manager = GoldenTraceSceneManager.install()
    with command_line([
        '--windowed',
        '--resolution',
        '800x600',
        '--log-level',
        'warning',
        *extra_arguments,
    ]):
        engine = GoldenTraceEngine(game=scene_class)
    engine.install_game(scene_class=scene_class)
    return engine, manager.active_scene


class TestEventIntegration:
    """Test full event flow through GameEngine."""

    def test_audio_event_through_engine(self):
        """Audio events flow through the engine's audio manager to the scene."""
        engine, scene = start_engine_with_scene(
            scene_class=AudioAndControllerRecordingScene,
            extra_arguments=['--no-unhandled-events'],
        )
        assert isinstance(engine.audio_manager, AudioEventManager)
        install_sources(
            sources=ScriptedBatchSources(
                batch=[pygame.event.Event(pygame.AUDIODEVICEADDED, which=1, iscapture=0)]
            )
        )

        # Process events through the engine
        result = engine.process_events()

        # The event should be handled by the engine's audio manager and reach the scene
        assert result is True
        assert [event.which for event in scene.audio_events_received] == [1]

    @staticmethod
    def _plug_in_and_move_axis(*, controller):
        """Start the engine in controller mode; pump a device-added then an axis event.

        Returns:
            tuple: The engine, its scene and process_events()'s result.

        """
        engine, scene = start_engine_with_scene(
            scene_class=AudioAndControllerRecordingScene,
            extra_arguments=['--no-unhandled-events', '--input-mode', 'controller'],
        )
        assert isinstance(engine.controller_manager, ControllerEventManager)
        install_sources(
            sources=ScriptedBatchSources(
                batch=[
                    pygame.event.Event(
                        pygame.CONTROLLERDEVICEADDED, device_index=controller.device_index, guid=''
                    ),
                    pygame.event.Event(
                        pygame.CONTROLLERAXISMOTION,
                        instance_id=controller.instance_id,
                        axis=0,
                        value=16384,
                    ),
                ],
                controller=controller,
            )
        )
        result = engine.process_events()
        return engine, scene, result

    def test_controller_event_through_engine(self):
        """Controller events flow through the engine's controller manager to the scene."""
        engine, scene, result = self._plug_in_and_move_axis(controller=STAND_IN_CONTROLLER)

        assert result is True
        assert [event.type for event in scene.controller_events_received] == [
            pygame.CONTROLLERDEVICEADDED,
            pygame.CONTROLLERAXISMOTION,
        ]
        assert scene.controller_events_received[1].value == 16384
        # The controller's proxy kept the axis value
        controller_proxy = engine.controller_manager.controllers[STAND_IN_CONTROLLER.instance_id]
        assert controller_proxy._axes[0] == 16384

    def test_reconnected_controller_event_through_engine(self):
        """A controller whose instance id differs from its device index still reaches the scene."""
        _engine, scene, result = self._plug_in_and_move_axis(
            controller=RECONNECTED_STAND_IN_CONTROLLER
        )

        assert result is True
        assert [event.type for event in scene.controller_events_received] == [
            pygame.CONTROLLERDEVICEADDED,
            pygame.CONTROLLERAXISMOTION,
        ]

    def test_unhandled_event_falls_back_to_stubs(self, mocker):
        """An event the scene does not handle falls back to the stubs: UnhandledEventError."""
        # A plain Scene has no handler for app events: AllEventStubs' stub gets it
        engine, scene = start_engine_with_scene(
            scene_class=Scene, extra_arguments=['--no-unhandled-events']
        )
        assert scene.options['no_unhandled_events'] is True
        install_sources(
            sources=ScriptedBatchSources(batch=[pygame.event.Event(pygame.APP_LOWMEMORY)])
        )
        # Silence the expected error log
        mocker.patch('glitchygames.events.base.LOG.error')

        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            engine.process_events()

    def test_event_routing_through_managers(self):
        """Every event of a batch is routed, in order, through the managers to the scene."""
        engine, scene = start_engine_with_scene(scene_class=AudioAndControllerRecordingScene)
        install_sources(
            sources=ScriptedBatchSources(
                batch=[
                    pygame.event.Event(pygame.AUDIODEVICEADDED, which=1, iscapture=0),
                    pygame.event.Event(pygame.AUDIODEVICEADDED, which=2, iscapture=0),
                ]
            )
        )

        result = engine.process_events()

        # Events should be routed to the scene
        assert result is True
        assert len(scene.audio_events_received) == 2
        assert scene.audio_events_received[0].which == 1
        assert scene.audio_events_received[1].which == 2

    def test_engine_event_handlers_are_configured(self):
        """Test that the engine's event handlers are properly configured."""
        engine, _scene = start_engine_with_scene(scene_class=AudioAndControllerRecordingScene)

        # Check that event handlers are registered
        assert pygame.AUDIODEVICEADDED in GameEngine.EVENT_HANDLERS
        assert pygame.AUDIODEVICEREMOVED in GameEngine.EVENT_HANDLERS
        assert pygame.CONTROLLERAXISMOTION in GameEngine.EVENT_HANDLERS
        assert pygame.CONTROLLERBUTTONDOWN in GameEngine.EVENT_HANDLERS

        # Check that handlers point to the right methods
        assert GameEngine.EVENT_HANDLERS[pygame.AUDIODEVICEADDED] == engine.process_audio_event
        assert (
            GameEngine.EVENT_HANDLERS[pygame.CONTROLLERAXISMOTION]
            == engine.process_controller_event
        )
