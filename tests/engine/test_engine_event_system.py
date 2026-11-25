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
from glitchygames.engine_context import EngineContext
from glitchygames.events import HashableEvent
from glitchygames.input.devices import (
    JOYSTICK_KIND,
    MIDI_READ_BATCH,
    DeviceDescriptor,
    LiveDeviceRegistry,
    MidiPortInfo,
)
from glitchygames.input.stand_in_devices import StandInDeviceSources, stand_in_registry
from glitchygames.render_target import set_render_target
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sources import active_sources
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


class MidiRecordingScene(RecordingScene):
    """A game that also records the MIDI events the engine routes to it."""

    NAME = 'MidiRecordingScene'

    def on_midi_in_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_midi_in_event', event))

    def on_midi_out_event(self, event: HashableEvent) -> None:
        """Record the event."""
        self.received.append(('on_midi_out_event', event))


def constructed_engine(
    *, mocker, game: type[Scene], arguments: tuple[str, ...] = ()
) -> Iterator[GoldenTraceEngine]:
    """Construct a real engine for a game; afterwards put pygame's blocked types back.

    The engine is GoldenTraceEngine (glitchygames/replay/tools/golden_traces.py): GameEngine
    opening a plain window, because SDL's dummy video driver warns "no fast renderer available"
    for GameEngine's SCALED window, an error under pytest's filterwarnings.

    Args:
        mocker: pytest-mock's fixture.
        game: The game scene class.
        arguments: Command-line arguments after the engine's usual ones.

    Yields:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    mocker.patch.object(sys, 'argv', ['test_engine_event_system', *ENGINE_ARGUMENTS, *arguments])
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
def midi_engine(mocker):
    """Construct a real engine for a game with MIDI handlers.

    Yields:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    yield from constructed_engine(mocker=mocker, game=MidiRecordingScene)


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


# One event of each family the engine builds an event manager for, by the manager's attribute:
# the invariant below hands each to the engine's handler for its type and expects that manager to
# receive it. A manager the engine builds that is missing here fails the invariant, so a new one
# gets an entry. The joystick and controller events name the stand-in joystick (an unmapped one,
# whose joystick events are dispatched; a remap is a device event, never gated by layer).
MANAGER_FAMILY_EVENTS: dict[str, pygame.event.Event] = {
    'app_manager': pygame.event.Event(pygame.APP_LOWMEMORY),
    'audio_manager': pygame.event.Event(pygame.AUDIODEVICEADDED, which=0, iscapture=0),
    'controller_manager': pygame.event.Event(
        pygame.CONTROLLERDEVICEREMAPPED, instance_id=JOYSTICK_INSTANCE_ID
    ),
    'drop_manager': pygame.event.Event(pygame.DROPBEGIN),
    'game_manager': pygame.event.Event(events.FPSEVENT, fps=60.0),
    'joystick_manager': pygame.event.Event(
        pygame.JOYBUTTONDOWN, button=0, instance_id=JOYSTICK_INSTANCE_ID
    ),
    'keyboard_manager': pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a'),
    'midi_manager': pygame.event.Event(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127),
    'mouse_manager': pygame.event.Event(pygame.MOUSEMOTION, pos=(1, 1), rel=(1, 1), buttons=()),
    'touch_manager': pygame.event.Event(pygame.FINGERDOWN, touch_id=0, finger_id=0, x=0.5, y=0.5),
    'window_manager': pygame.event.Event(pygame.WINDOWSHOWN),
}


def built_event_manager_names(engine: GameEngine) -> set[str]:
    """Return the attribute names of the event managers the engine built.

    Returns:
        set[str]: Each attribute holding an ``*EventManager`` (the font manager is no event
        manager, and the scene manager routes rather than receives).

    """
    return {
        name
        for name, value in vars(engine).items()
        if type(value).__name__.endswith('EventManager')
    }


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

    def test_midi_events_reach_the_scenes_midi_handlers(self, midi_engine):
        """MIDIIN and MIDIOUT reach on_midi_in/out_event through the MIDI manager.

        They went to SceneManager.handle_event, which ignores them, and counted as handled
        (bugs/2026-11-22-midi-events-skip-the-midi-manager.md).
        """
        midi_engine.install_game(scene_class=MidiRecordingScene)
        pygame.event.clear()
        scene = midi_engine.scene_manager.active_scene

        handled = process_posted(
            midi_engine,
            [
                pygame.event.Event(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127),
                pygame.event.Event(pygame.MIDIOUT, device_id=2, status=128, data1=60, data2=0),
            ],
        )

        assert handled is True
        assert scene.received_handler_names() == ['on_midi_in_event', 'on_midi_out_event']
        assert [(event.device_id, event.status, event.data1) for _, event in scene.received] == [
            (1, 144, 60),
            (2, 128, 60),
        ]

    def test_every_event_manager_the_engine_builds_is_the_one_its_events_go_through(
        self, engine, scene, mocker
    ):
        """Each family's event reaches the manager the engine built for it, and counts handled.

        The class of bugs/2026-11-22-midi-events-skip-the-midi-manager.md: the MIDI manager was
        built but its events went around it, so its handlers never ran. Each manager is stood in
        for by a recording double after it is built: the engine's handler for the family must
        read the manager it built, and hand it the event.
        """
        assert built_event_manager_names(engine) == set(MANAGER_FAMILY_EVENTS)
        for manager_name, pygame_event in MANAGER_FAMILY_EVENTS.items():
            recording_manager = mocker.Mock()
            mocker.patch.object(engine, manager_name, recording_manager)
            event = HashableEvent.from_pygame(pygame_event)

            handled = engine.event_handlers[event.type](event)

            assert handled is True, manager_name
            received = [call.args for call in recording_manager.method_calls]
            assert received == [(event,)], manager_name

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


KEYBOARD_PORT = MidiPortInfo(interface='CoreMIDI', name='Keys', is_input=True, is_output=False)
NOTE_ON = [0x90, 60, 100, 0]


class TestMidiInputInTheFrame:
    """MIDI input arrives in the frame's event batch, like every other event."""

    @staticmethod
    def start_scene(midi_engine, *, port_count=4):
        """Install stand-in doors with input ports, open them all, and return (scene, doors)."""
        devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYBOARD_PORT] * port_count)
        midi_engine.install_game(scene_class=MidiRecordingScene)
        pygame.event.clear()
        for port_id in range(port_count):
            devices.open_midi_input(port_id=port_id)
        return midi_engine.scene_manager.active_scene, devices

    def test_midi_input_reaches_the_scenes_handler_in_its_frame(self, midi_engine):
        """A queued note-on is one MidiEvent in on_midi_in_event, in the frame it was queued."""
        scene, devices = self.start_scene(midi_engine)
        devices.queue_midi_input(port_id=3, messages=[(NOTE_ON, 1234)])

        handled = midi_engine.process_events()

        assert handled is True
        assert scene.received_handler_names() == ['on_midi_in_event']
        event = scene.received[0][1]
        assert (event.status, event.data1, event.data2, event.data3) == (0x90, 60, 100, 0)
        assert (event.timestamp, event.vice_id) == (1234, 3)

    def test_a_burst_larger_than_one_read_arrives_whole_and_in_order(self, midi_engine):
        """More messages than one read takes all arrive, oldest first, in one frame."""
        scene, devices = self.start_scene(midi_engine)
        count = MIDI_READ_BATCH * 3 + 8
        devices.queue_midi_input(
            port_id=0, messages=[(NOTE_ON, timestamp) for timestamp in range(count)]
        )

        midi_engine.process_events()

        assert count == 200
        assert [event.timestamp for _, event in scene.received] == list(range(count))
        assert scene.received_handler_names() == ['on_midi_in_event'] * count

    def test_a_failing_midi_port_is_dropped_and_the_others_still_read(self, midi_engine, caplog):
        """A port raising a plain Exception (PortMidi's way) is logged once and then not read."""
        scene, devices = self.start_scene(midi_engine, port_count=2)
        devices.fail_midi_input(port_id=0)
        devices.queue_midi_input(port_id=0, messages=[(NOTE_ON, 1)])
        devices.queue_midi_input(port_id=1, messages=[(NOTE_ON, 2)])

        with caplog.at_level('ERROR', logger='game.input.devices'):
            midi_engine.process_events()
            devices.queue_midi_input(port_id=1, messages=[(NOTE_ON, 3)])
            midi_engine.process_events()

        assert [(event.vice_id, event.timestamp) for _, event in scene.received] == [(1, 2), (1, 3)]
        failures = [record.getMessage() for record in caplog.records if 'failed' in record.message]
        assert len(failures) == 1
        assert 'port 0 (Keys)' in failures[0]


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

    def test_setting_event_types_allowed_changes_sdl_outside_an_inner_context(self):
        """The default context allows and blocks at SDL, as pygame.event.set_allowed/blocked do."""
        try:
            events.set_event_types_allowed(event_types=pygame.MOUSEWHEEL, allowed=False)
            assert pygame.event.get_blocked(pygame.MOUSEWHEEL) is True

            events.set_event_types_allowed(event_types=[pygame.MOUSEWHEEL], allowed=True)
            assert pygame.event.get_blocked(pygame.MOUSEWHEEL) is False
        finally:
            pygame.event.set_allowed(pygame.MOUSEWHEEL)

    def test_setting_event_types_allowed_changes_nothing_in_an_inner_context(self):
        """Row S6: an inner context (one with a render target) never changes SDL's blocked set."""
        inner_context = EngineContext(name='inner')
        pygame.event.set_blocked(pygame.MOUSEWHEEL)
        try:
            with inner_context.active():
                set_render_target(surface=pygame.Surface((8, 8)))
                events.set_event_types_allowed(event_types=None, allowed=True)
                events.allow_every_event_type(native_window_messages=True)
                events.set_event_types_allowed(event_types=pygame.KEYDOWN, allowed=False)

            assert pygame.event.get_blocked(pygame.MOUSEWHEEL) is True
            assert pygame.event.get_blocked(pygame.SYSWMEVENT) is True
            assert pygame.event.get_blocked(pygame.KEYDOWN) is False
        finally:
            pygame.event.set_allowed(pygame.MOUSEWHEEL)

    def test_game_engine_event_manager_integration(self, engine, scene):
        """The engine's managers route to the scene manager, whose active scene is the game."""
        assert engine.running_game.instance is scene
        assert engine.game is type(scene)
        assert engine.scene_manager is SceneManager()
        assert engine.scene_manager.active_scene is scene
        for manager in (
            engine.keyboard_manager,
            engine.mouse_manager,
            engine.joystick_manager,
            engine.game_manager,
        ):
            assert manager.game is engine.scene_manager


class TestMidiPortOptions:
    """--midi-input and --midi-output name the ports the engine opens; none named, none asked."""

    def test_no_named_port_means_portmidi_is_never_initialized(self, mocker, midi_engine):
        """Default options: pygame.midi.init is never called and no MIDI answer is recorded."""
        initialize = mocker.patch('pygame.midi.init')

        midi_engine.install_game(scene_class=MidiRecordingScene)

        initialize.assert_not_called()
        assert midi_engine.midi_manager.ports == {}
        answers = active_sources().devices().take_enumeration_answers()
        assert [answer.call for answer in answers if 'midi' in answer.call] == []

    def test_the_named_ports_open_through_the_engines_doors(self, mocker):
        """--midi-input Keys --midi-output Synth: one proxy each, answers recorded."""
        synth = MidiPortInfo(interface='CoreMIDI', name='Synth', is_input=False, is_output=True)
        engine_construction = constructed_engine(
            mocker=mocker,
            game=MidiRecordingScene,
            arguments=('--midi-input', 'Keys', '--midi-output', 'Synth'),
        )
        engine = next(engine_construction)
        try:
            devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYBOARD_PORT, synth])
            engine.install_game(scene_class=MidiRecordingScene)

            assert engine.options['midi_input'] == ['Keys']
            assert engine.options['midi_output'] == ['Synth']
            assert list(engine.midi_manager.ports) == [('midi_input', 0), ('midi_output', 1)]
            calls = [answer.call for answer in devices.take_enumeration_answers()]
            assert 'open_midi_input' in calls
            assert 'open_midi_output' in calls
        finally:
            engine_construction.close()

    def test_a_port_that_is_not_there_does_not_stop_the_run(self, mocker, caplog):
        """A named port that is absent is logged and the engine still installs its game."""
        engine_construction = constructed_engine(
            mocker=mocker, game=MidiRecordingScene, arguments=('--midi-input', 'Nope')
        )
        engine = next(engine_construction)
        try:
            install_stand_in_devices(descriptors=[], midi_ports=[KEYBOARD_PORT])
            with caplog.at_level('WARNING', logger='game.midi'):
                engine.install_game(scene_class=MidiRecordingScene)

            assert engine.midi_manager.ports == {}
            assert 'Nope' in caplog.text
        finally:
            engine_construction.close()

    def test_a_real_teardown_closes_the_ports(self, mocker, midi_engine):
        """_shutdown reaches the live registry's close: deleting the call fails this test."""
        close = mocker.patch.object(LiveDeviceRegistry, 'close_midi_ports')
        mocker.patch('pygame.display.quit')
        mocker.patch('pygame.quit')

        midi_engine._shutdown()

        close.assert_called_once_with()

    def test_a_failing_close_does_not_stop_the_teardown(self, mocker, midi_engine, caplog):
        """A close that raises is logged, and pygame still shuts down."""
        mocker.patch.object(
            LiveDeviceRegistry, 'close_midi_ports', side_effect=RuntimeError('quit failed')
        )
        mocker.patch('pygame.display.quit')
        pygame_quit = mocker.patch('pygame.quit')

        with caplog.at_level('ERROR', logger='game.engine'):
            midi_engine._shutdown()

        pygame_quit.assert_called_once_with()
        assert 'Closing the MIDI ports failed' in caplog.text

    def test_a_replay_has_no_live_ports_to_close(self, mocker, midi_engine):
        """A replay has no live doors: nothing is closed."""
        close = mocker.patch.object(LiveDeviceRegistry, 'close_midi_ports')
        midi_engine.live_sources = None

        midi_engine._close_midi_ports()

        close.assert_not_called()

    def test_stand_in_devices_have_no_port_to_close(self, mocker, midi_engine):
        """Live doors over stand-in devices hold no PortMidi port: nothing is closed."""
        close = mocker.patch.object(LiveDeviceRegistry, 'close_midi_ports')
        midi_engine.live_sources = StandInDeviceSources(
            registry=stand_in_registry(descriptors=[]), random_seed=1
        )

        midi_engine._close_midi_ports()

        close.assert_not_called()
