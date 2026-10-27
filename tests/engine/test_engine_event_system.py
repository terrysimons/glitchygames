"""Tests for GameEngine event system functionality.

This module tests GameEngine event handling, event processing, and event manager integration on
a real engine: real pygame events are posted to SDL's queue, pumped by the engine and routed by
its real event managers and the real SceneManager to the active scene, which records what it
receives. Only the joystick hardware is stood in for (no test machine has one attached).
"""

import os
import sys
from typing import TYPE_CHECKING, Any

import pygame
import pytest

from glitchygames import events
from glitchygames.engine import GameEngine
from glitchygames.events import HashableEvent
from glitchygames.input.devices import JOYSTICK_KIND, DeviceDescriptor
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.scenes import Scene, SceneManager
from tests.input.stand_in_devices import install_stand_in_devices

if TYPE_CHECKING:
    from collections.abc import Iterator

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

    def on_text_input_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_text_input_event', event))

    def on_text_editing_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_text_editing_event', event))

    def on_window_take_focus_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_window_take_focus_event', event))

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


class NativeWindowMessagesScene(RecordingScene):
    """A game that asks for the window system's own messages (SYSWMEVENT)."""

    NAME = 'NativeWindowMessagesScene'
    NATIVE_WINDOW_MESSAGES = True


def constructed_engine(*, mocker, game: type[Scene]) -> Iterator[GoldenTraceEngine]:
    """Construct a real engine for a game; afterwards put pygame's blocked types back.

    The engine is GoldenTraceEngine (glitchygames/replay/tools/golden_traces.py): GameEngine
    opening a plain window, because SDL's dummy video driver warns "no fast renderer available"
    for GameEngine's SCALED window, an error under pytest's filterwarnings.

    Args:
        mocker: pytest-mock's fixture.
        game: The game scene class.

    Yields:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    mocker.patch.object(sys, 'argv', ['test_engine_event_system', *ENGINE_ARGUMENTS])
    # The engine writes SDL hints to the environment; the test's own values come back after
    mocker.patch.dict(os.environ)
    blocked_before = [
        pygame.event.get_blocked(event_type) for event_type in range(pygame.NUMEVENTS)
    ]
    try:
        yield GoldenTraceEngine(game=game)
    finally:
        pygame.event.clear()
        # The event managers and the scene block and allow event types: put them back
        for event_type, was_blocked in enumerate(blocked_before):
            if was_blocked:
                pygame.event.set_blocked(event_type)
            else:
                pygame.event.set_allowed(event_type)


@pytest.fixture
def engine(mocker):
    """Construct a real engine for RecordingScene, leaving pygame as the test found it.

    Yields:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    yield from constructed_engine(mocker=mocker, game=RecordingScene)


@pytest.fixture
def native_window_messages_engine(mocker):
    """Construct a real engine for a game that opts in to SYSWMEVENT.

    Yields:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    yield from constructed_engine(mocker=mocker, game=NativeWindowMessagesScene)


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

    def test_text_events_reach_the_scenes_text_handlers(self, engine, scene):
        """TEXTINPUT and TEXTEDITING reach on_text_input/editing_event (BUGS.md #200 item 1).

        They went to process_unimplemented_event, so the scene's text handlers were never called.
        """
        handled = process_posted(
            engine,
            [
                pygame.event.Event(pygame.TEXTEDITING, text='ka', start=0, length=2),
                pygame.event.Event(pygame.TEXTINPUT, text='a'),
            ],
        )

        assert handled is True
        assert scene.received_handler_names() == ['on_text_editing_event', 'on_text_input_event']
        assert [event.text for _, event in scene.received] == ['ka', 'a']
        assert pygame.TEXTINPUT not in engine.unhandled_events

    def test_window_take_focus_reaches_the_scenes_handler(self, engine, scene):
        """WINDOWTAKEFOCUS reaches on_window_take_focus_event (BUGS.md #200 item 1)."""
        handled = process_posted(engine, [pygame.event.Event(pygame.WINDOWTAKEFOCUS)])

        assert handled is True
        assert scene.received_handler_names() == ['on_window_take_focus_event']

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

    def test_game_engine_sys_wm_event_handling(self, native_window_messages_engine):
        """A game that opts in gets SYSWMEVENT in on_sys_wm_event, a plain HashableEvent."""
        native_window_messages_engine.install_game(scene_class=NativeWindowMessagesScene)
        pygame.event.clear()
        scene = native_window_messages_engine.scene_manager.active_scene

        process_posted(
            native_window_messages_engine,
            [pygame.event.Event(pygame.SYSWMEVENT, msg='test_message')],
        )

        assert scene.received_handler_names() == ['on_sys_wm_event']
        assert scene.received[0][1].msg == 'test_message'
        assert type(scene.received[0][1]) is HashableEvent


class TestNativeWindowMessages:
    """SYSWMEVENT (the window system's raw messages) stays blocked unless the game opts in."""

    def test_blocked_by_default_even_after_something_allowed_it(self, mocker):
        """The engine's allow-all keeps SDL's default: no SYSWMEVENT for a game not asking."""
        pygame.event.set_allowed(pygame.SYSWMEVENT)
        engine_construction = constructed_engine(mocker=mocker, game=RecordingScene)
        engine = next(engine_construction)
        try:
            engine.install_game(scene_class=RecordingScene)
            pygame.event.clear()

            assert pygame.event.get_blocked(pygame.SYSWMEVENT) is True
            process_posted(engine, [pygame.event.Event(pygame.SYSWMEVENT, msg='dropped')])

            assert engine.scene_manager.active_scene.received == []
            # Every other type stays allowed
            assert pygame.event.get_blocked(pygame.ACTIVEEVENT) is False
        finally:
            engine_construction.close()
            pygame.event.set_blocked(pygame.SYSWMEVENT)

    def test_a_game_that_opts_in_is_allowed_them(self, native_window_messages_engine):
        """NATIVE_WINDOW_MESSAGES = True on the game unblocks SYSWMEVENT."""
        assert pygame.event.get_blocked(pygame.SYSWMEVENT) is False

    def test_the_opt_in_must_be_a_bool(self, mocker):
        """Anything but True or False is refused, naming the game."""
        # Made with type(): the class attribute is declared bool, and the engine must still
        # refuse a game that sets something else
        truthy_scene = type('TruthyScene', (RecordingScene,), {'NATIVE_WINDOW_MESSAGES': 'yes'})

        engine_construction = constructed_engine(mocker=mocker, game=truthy_scene)
        with pytest.raises(TypeError, match=r'TruthyScene\.NATIVE_WINDOW_MESSAGES must be a bool'):
            next(engine_construction)
        assert GameEngine.native_window_messages(game=NativeWindowMessagesScene()) is True

    def test_allowing_every_type_keeps_them_blocked_unless_asked(self):
        """allow_every_event_type unblocks every type, SYSWMEVENT only when asked."""
        pygame.event.set_blocked([pygame.KEYDOWN, pygame.SYSWMEVENT])
        try:
            events.allow_every_event_type(native_window_messages=False)
            assert pygame.event.get_blocked(pygame.KEYDOWN) is False
            assert pygame.event.get_blocked(pygame.SYSWMEVENT) is True

            events.allow_every_event_type(native_window_messages=True)
            assert pygame.event.get_blocked(pygame.SYSWMEVENT) is False
        finally:
            pygame.event.set_blocked(pygame.SYSWMEVENT)

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
