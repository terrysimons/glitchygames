"""Tests for GameEngine event system functionality.

This module tests GameEngine event handling, event processing, and event manager integration on
a real engine: real pygame events are posted to SDL's queue, pumped by the engine and routed by
its real event managers and the real SceneManager to the active scene, which records what it
receives. Only the joystick hardware is stood in for (no test machine has one attached).
"""

import os
import sys
from pathlib import Path
from typing import Any

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.record_golden_traces import GoldenTraceEngine

from glitchygames import events
from glitchygames.events import HashableEvent
from glitchygames.input.devices import JOYSTICK_KIND, DeviceDescriptor
from glitchygames.scenes import Scene, SceneManager
from tests.input.stand_in_devices import install_stand_in_devices

# GameEngine parses sys.argv when it is constructed: a small window (the conftest puts the
# 800x600 test display back after the test), no frame pacing, quiet logs
ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')

# The stand-in joystick's instance id, which its events carry
JOYSTICK_INSTANCE_ID = 0

# A game event subtype the tests register with the engine
TEST_GAME_EVENT_SUBTYPE = 7


class RecordingScene(Scene):
    """A game scene that records every event the engine routes to it, in order."""

    NAME = 'RecordingScene'
    VERSION = '1.0'

    def __init__(self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Start with no events received."""
        super().__init__(options=options, groups=groups)
        self.received: list[tuple[str, HashableEvent]] = []

    def on_key_down_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_key_down_event', event))

    def on_key_up_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_key_up_event', event))

    def on_mouse_button_down_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_mouse_button_down_event', event))

    def on_mouse_button_up_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_mouse_button_up_event', event))

    def on_mouse_motion_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_mouse_motion_event', event))

    def on_joy_button_down_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_joy_button_down_event', event))

    def on_joy_button_up_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_joy_button_up_event', event))

    def on_joy_axis_motion_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_joy_axis_motion_event', event))

    def on_joy_hat_motion_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_joy_hat_motion_event', event))

    def on_joy_ball_motion_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_joy_ball_motion_event', event))

    def on_active_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_active_event', event))

    def on_fps_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_fps_event', event))

    def on_menu_item_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_menu_item_event', event))

    def on_sys_wm_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_sys_wm_event', event))

    def received_handler_names(self) -> list[str]:
        """Return the names of the handlers called so far, in order.

        Returns:
            list[str]: The handler names.

        """
        return [handler_name for handler_name, _ in self.received]


# The stand-in joystick (an unmapped one: its joystick events reach the scene)
STAND_IN_JOYSTICK = DeviceDescriptor(
    kind=JOYSTICK_KIND,
    device_index=0,
    instance_id=JOYSTICK_INSTANCE_ID,
    name='Stand-in joystick',
    guid=None,
    axis_count=2,
    button_count=4,
    hat_count=1,
    ball_count=1,
)


@pytest.fixture
def engine(mocker):
    """Construct a real engine for RecordingScene, leaving pygame as the test found it.

    The engine is GoldenTraceEngine (scripts/record_golden_traces.py): GameEngine opening a
    plain window, because SDL's dummy video driver warns "no fast renderer available" for
    GameEngine's SCALED window, an error under pytest's filterwarnings.

    Yields:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    mocker.patch.object(sys, 'argv', ['test_engine_event_system', *ENGINE_ARGUMENTS])
    # The engine writes SDL hints to the environment; the test's own values come back after
    mocker.patch.dict(os.environ)
    blocked_before = [
        pygame.event.get_blocked(event_type) for event_type in range(pygame.NUMEVENTS)
    ]
    yield GoldenTraceEngine(game=RecordingScene)
    pygame.event.clear()
    # The event managers and the scene block and allow event types: put them back
    for event_type, was_blocked in enumerate(blocked_before):
        if was_blocked:
            pygame.event.set_blocked(event_type)
        else:
            pygame.event.set_allowed(event_type)


@pytest.fixture
def scene(engine):
    """Start the engine's event managers with RecordingScene active, as start() does.

    Returns:
        RecordingScene: The active game scene.

    """
    # Hardware: one joystick attached (a stand-in, through the devices door)
    install_stand_in_devices(descriptors=[STAND_IN_JOYSTICK])
    engine.install_game(scene_class=RecordingScene)
    pygame.event.clear()
    return engine.scene_manager.active_scene


def process_posted(engine, posted_events: list[pygame.event.Event]) -> bool:
    """Post events to SDL's queue and let the engine pump and process them.

    Returns:
        bool: What process_events returned (True: every event was handled).

    """
    for event in posted_events:
        pygame.event.post(event)
    return engine.process_events()


class TestEngineEventSystem:
    """Test GameEngine event system functionality."""

    def test_game_engine_event_handlers_registration(self, engine):
        """Construction maps every event category to the engine's processing method."""
        assert isinstance(engine.EVENT_HANDLERS, dict)
        expected_handlers = {
            pygame.KEYDOWN: engine.process_keyboard_event,
            pygame.KEYUP: engine.process_keyboard_event,
            pygame.MOUSEBUTTONDOWN: engine.process_mouse_event,
            pygame.MOUSEMOTION: engine.process_mouse_event,
            pygame.JOYBUTTONDOWN: engine.process_joystick_event,
            pygame.ACTIVEEVENT: engine.process_game_event,
            pygame.QUIT: engine.process_game_event,
            events.FPSEVENT: engine.process_game_event,
        }
        for event_type, processing_method in expected_handlers.items():
            assert engine.EVENT_HANDLERS[event_type] == processing_method
        for event_type in [*events.KEYBOARD_EVENTS, *events.MOUSE_EVENTS, *events.JOYSTICK_EVENTS]:
            assert event_type in engine.EVENT_HANDLERS

    def test_game_engine_event_processing(self, engine, scene):
        """Posted events of every input kind reach the active scene, in order, all handled."""
        handled = process_posted(
            engine,
            [
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=' '),
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100)),
                pygame.event.Event(
                    pygame.JOYBUTTONDOWN, button=0, instance_id=JOYSTICK_INSTANCE_ID
                ),
            ],
        )

        assert handled is True
        assert scene.received_handler_names() == [
            'on_key_down_event',
            'on_mouse_button_down_event',
            'on_joy_button_down_event',
        ]

    def test_an_empty_batch_is_not_reported_as_handled(self, engine, scene):
        """With nothing queued, process_events reports nothing handled."""
        assert process_posted(engine, []) is False
        assert scene.received == []

    def test_game_engine_quit_event_handling(self, engine, scene):
        """A QUIT event asks the scene manager to stop the game loop."""
        assert engine.scene_manager.quit_requested is False

        handled = process_posted(engine, [pygame.event.Event(pygame.QUIT)])

        assert handled is True
        assert engine.scene_manager.quit_requested is True

    def test_game_engine_quit_key_handling(self, engine, scene):
        """Q with no focused sprite asks the scene manager to stop, through handle_event."""
        engine.handle_event(HashableEvent(type=pygame.KEYDOWN, key=pygame.K_q, mod=0))

        assert engine.scene_manager.quit_requested is True
        assert scene.received == []

    def test_game_engine_keyboard_event_handling(self, engine, scene):
        """KEYDOWN and KEYUP reach the scene's key handlers with their key."""
        process_posted(
            engine,
            [
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=' '),
                pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE, mod=0, unicode=' '),
            ],
        )

        assert scene.received_handler_names() == ['on_key_down_event', 'on_key_up_event']
        assert [event.key for _, event in scene.received] == [pygame.K_SPACE, pygame.K_SPACE]

    def test_game_engine_mouse_event_handling(self, engine, scene):
        """Mouse button and motion events reach the scene with their positions."""
        process_posted(
            engine,
            [
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100)),
                pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100)),
                pygame.event.Event(
                    pygame.MOUSEMOTION, pos=(105, 105), rel=(5, 5), buttons=(0, 0, 0)
                ),
            ],
        )

        assert scene.received_handler_names() == [
            'on_mouse_button_down_event',
            'on_mouse_button_up_event',
            'on_mouse_motion_event',
        ]
        assert [event.pos for _, event in scene.received] == [(100, 100), (100, 100), (105, 105)]
        assert scene.received[2][1].rel == (5, 5)

    def test_game_engine_joystick_event_handling(self, engine, scene):
        """Joystick events reach the scene through the joystick's proxy, with their values."""
        joystick_events = [
            pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, instance_id=JOYSTICK_INSTANCE_ID),
            pygame.event.Event(pygame.JOYBUTTONUP, button=0, instance_id=JOYSTICK_INSTANCE_ID),
            pygame.event.Event(
                pygame.JOYAXISMOTION, axis=0, value=0.5, instance_id=JOYSTICK_INSTANCE_ID
            ),
            pygame.event.Event(
                pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=JOYSTICK_INSTANCE_ID
            ),
            pygame.event.Event(
                pygame.JOYBALLMOTION, ball=0, rel=(5, 5), instance_id=JOYSTICK_INSTANCE_ID
            ),
        ]

        handled = process_posted(engine, joystick_events)

        assert handled is True
        assert scene.received_handler_names() == [
            'on_joy_button_down_event',
            'on_joy_button_up_event',
            'on_joy_axis_motion_event',
            'on_joy_hat_motion_event',
            'on_joy_ball_motion_event',
        ]
        received = [event for _, event in scene.received]
        assert received[2].value == pytest.approx(0.5)
        assert received[3].value == (1, 0)
        assert received[4].rel == (5, 5)

    def test_game_engine_active_event_handling(self, engine, scene):
        """ACTIVEEVENT reaches the scene with its gain and state."""
        process_posted(engine, [pygame.event.Event(pygame.ACTIVEEVENT, gain=1, state=1)])

        assert scene.received_handler_names() == ['on_active_event']
        _, active_event = scene.received[0]
        assert (active_event.gain, active_event.state) == (1, 1)

    def test_game_engine_user_event_handling(self, engine, scene):
        """FPSEVENT, a registered GAMEEVENT and MENUEVENT reach their handlers."""
        game_events_received: list[HashableEvent] = []
        engine.register_game_event(
            event_type=TEST_GAME_EVENT_SUBTYPE, callback=game_events_received.append
        )

        process_posted(
            engine,
            [
                pygame.event.Event(events.FPSEVENT, fps=60.0),
                pygame.event.Event(events.GAMEEVENT, subtype=TEST_GAME_EVENT_SUBTYPE),
                pygame.event.Event(events.MENUEVENT, menu='File'),
            ],
        )

        assert scene.received_handler_names() == ['on_fps_event', 'on_menu_item_event']
        assert scene.received[0][1].fps == pytest.approx(60.0)
        assert scene.received[1][1].menu == 'File'
        assert [event.subtype for event in game_events_received] == [TEST_GAME_EVENT_SUBTYPE]

    def test_game_engine_sys_wm_event_handling(self, engine, scene):
        """SYSWMEVENT reaches the scene with its message."""
        process_posted(engine, [pygame.event.Event(pygame.SYSWMEVENT, msg='test_message')])

        assert scene.received_handler_names() == ['on_sys_wm_event']
        assert scene.received[0][1].msg == 'test_message'

    def test_game_engine_event_manager_integration(self, engine, scene):
        """The engine's managers route to the scene manager, whose active scene is the game."""
        assert engine.game is scene
        assert engine.scene_manager is SceneManager()
        assert engine.scene_manager.active_scene is scene
        for manager in (
            engine.keyboard_manager,
            engine.mouse_manager,
            engine.joystick_manager,
            engine.game_manager,
        ):
            assert manager.game is engine.scene_manager
