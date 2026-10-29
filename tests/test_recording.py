"""Tests for gameplay recording (glitchygames/recording.py).

A recording is a trace (glitchygames/tracing.py) whose frames also carry the frame's ``dt``
and ``event_batches``: every batch the engine read from SDL's queue that frame, raw, each
event tagged with its origin (external from SDL, internal from code). Event attributes are
stored in a JSON-safe form that decodes back to the values pygame gave, with references for
pygame objects and a marker for values that cannot be stored.
"""

from __future__ import annotations

import dataclasses
import errno
import gzip
import json
import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np
import pygame
import pytest

from glitchygames import recording
from glitchygames.audio.accounting import AudioFrameAccount
from glitchygames.engine_context import EngineContext, default_context
from glitchygames.events import (
    FPSEVENT,
    GAMEEVENT,
    MENUEVENT,
    NAMED_CUSTOM_EVENT_TYPES,
    named_custom_event_type,
)
from glitchygames.events import base as events_base
from glitchygames.input import devices as devices_module
from glitchygames.input.state import IDLE_INPUT, held_key_codes
from glitchygames.live_sources import LiveSources
from glitchygames.recording import (
    CONTROL_EVENTS_FIELD,
    DEVICE_ENUMERATION_FIELD,
    DEVICES_OPENED_FIELD,
    DT_FIELD,
    EVENT_BATCHES_FIELD,
    EXTERNAL_ORIGIN,
    INPUT_CHANGES_FIELD,
    INTERNAL_ORIGIN,
    RECORDING_SOURCE,
    REDELIVERED_EVENTS_FIELD,
    SAVES_HEADER_FIELD,
    SAVES_OPENED_FIELD,
    SCENE_START_FIELD,
    GameplayRecorder,
    RecordedReference,
    RecordingSources,
    RecordingWriteError,
    UnrepresentableValue,
    custom_event_type_remap,
    custom_event_types_header,
    event_from_record,
    event_origin,
    event_to_record,
    forget_pending_posts,
    is_input_post,
    is_live_game_post,
    json_safe_value,
    live_game_code_running,
    live_game_posts,
    pending_code_post_count,
    pending_internal_posts,
    post_event,
    post_input_event,
    remapped_event_records,
    reset_internal_post_tracking,
    set_live_game_code_running,
    start_tracking_internal_posts,
    stop_tracking_internal_posts,
    value_from_json,
)
from glitchygames.recording_history import (
    AUDIO_SECONDS_FIELD,
    AUDIO_WORK_FIELD,
    CONTENT_HASH_FIELD,
    PROCESSING_SECONDS_FIELD,
    frame_content_hash,
)
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES, EventTypeBlock
from glitchygames.scenes import Scene
from glitchygames.sources import frame_clock_seconds, set_frame_clock_seconds
from glitchygames.supervision import ControlEvent
from glitchygames.tracing import TraceFormatError, TraceWriter, read_trace_result

if TYPE_CHECKING:
    from pathlib import Path

WINDOW_SIZE = (16, 16)
TEST_JOYSTICK_INSTANCE_ID = 7
# The event type posts_are_tracked() probes the tracker with: its own, so taking the probe back
# out of SDL's queue never takes a test's own USEREVENTs (review M-8)
PROBE_EVENT_TYPE = pygame.event.custom_type()


class Gamepad:
    """Stands in for any Python object a game puts on an event (JSON cannot hold it)."""


GAMEPAD_TYPE_NAME = f'{Gamepad.__module__}.Gamepad'


class FakeSprite:
    """The fields sample_scene_frame reads from a sprite."""

    def __init__(self, *, x: int, y: int) -> None:
        """Place the sprite."""
        self.rect = pygame.Rect(x, y, 8, 8)
        self.visible = 1


class FakeGroup:
    """The part of a sprite group sample_scene_frame reads."""

    def __init__(self, *sprites: FakeSprite) -> None:
        """Hold the sprites in draw order."""
        self._sprites = list(sprites)

    def sprites(self) -> list[FakeSprite]:
        """Return the sprites.

        Returns:
            The sprites in draw order.

        """
        return list(self._sprites)


def _scene(*sprites: FakeSprite) -> Any:
    """A real scene (capturing no scene start) whose sprite group holds these sprites."""
    scene = Scene(options={})
    scene.all_sprites = FakeGroup(*sprites)
    return scene


def _lines(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, 'rt', encoding='utf-8') as trace_file:
        return [json.loads(line) for line in trace_file]


def _json_round_trip(value: object) -> object:
    return value_from_json(json.loads(json.dumps(json_safe_value(value), allow_nan=False)))


def _pump_batch(recorder: GameplayRecorder) -> None:
    """Read SDL's queue and record the batch, as GameEngine._pump_events does."""
    recorder.record_event_batch(raw_events=pygame.event.get())


def posts_are_tracked() -> bool:
    """Whether a code post is tracked now: it waits in pending_internal_posts() (decision 1).

    Posts a USEREVENT probe with post_event, then takes it back out of the tracker's pending list
    and SDL's queue, so the tracker and the queue are as they were.

    Returns:
        True when the probe was tracked.

    Raises:
        AssertionError: If the live game's code is running: the probe would be recorded among
            the live game's posts too.

    """
    if live_game_code_running():
        message = (
            'posts_are_tracked() cannot probe while the live game code runs: the probe would be '
            "recorded among the live game's posts too"
        )
        raise AssertionError(message)
    pending_before = len(pending_internal_posts())
    post_event(pygame.event.Event(PROBE_EVENT_TYPE))
    is_tracked = len(pending_internal_posts()) > pending_before
    if is_tracked:
        pending_internal_posts().pop()
    pygame.event.get(eventtype=PROBE_EVENT_TYPE)
    return is_tracked


def _origins(frame: dict[str, Any]) -> list[tuple[int, str]]:
    return [(record['type'], record['origin']) for record in frame[EVENT_BATCHES_FIELD][0]]


@pytest.fixture(autouse=True)
def no_tracked_posts():
    """Give each test a fresh internal-post tracker (a recorder left open cannot leak).

    Yields:
        None, with the default context's tracker fresh (reset again afterwards).

    """
    default_context().reset_value(slot=recording.INTERNAL_POSTS_SLOT)
    yield
    default_context().reset_value(slot=recording.INTERNAL_POSTS_SLOT)


@pytest.fixture
def event_queue(monkeypatch):
    """Initialize pygame's display (dummy driver) so events can be posted; empty the queue.

    On a real driver (the native run of the driver comparison) the run's window is on screen,
    so the operating system can deliver its own events mid-test (a MOUSEMOTION when the mouse
    crosses the window broke an origin test, 2026-10-23): every real input and window type is
    blocked, except KEYDOWN, which these tests post, and each type's blocked state is put back
    afterwards.

    Yields:
        None, with an empty queue.

    """
    if not pygame.display.get_init():
        monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
        pygame.display.init()
    operating_system_events = EventTypeBlock(
        event_types=[
            event_type for event_type in REAL_INPUT_EVENT_TYPES if event_type != pygame.KEYDOWN
        ]
    )
    operating_system_events.block()
    pygame.event.clear()
    try:
        yield
    finally:
        pygame.event.clear()
        operating_system_events.restore()


class TestJsonSafeValue:
    """Event attribute values become JSON and decode back to the same Python values."""

    @pytest.mark.parametrize(
        'value',
        [
            None,
            True,
            False,
            0,
            -7,
            2**70,
            1.5,
            -0.0,
            '',
            'é',
            '☃',
            (1, 2),
            (),
            ((1, 2), (3, (4.5, 'x'))),
            [1, (2, 3)],
            [],
            {'a': 1, 'b': (2, 3)},
            {},
            b'\x00\xff',
        ],
    )
    def test_round_trip_through_json_text(self, value):
        """The value survives json.dumps/json.loads with its type (tuples stay tuples)."""
        decoded = _json_round_trip(value)

        assert decoded == value
        assert type(decoded) is type(value)

    def test_tuples_are_plain_arrays_and_lists_are_tagged(self):
        """Tuples (what pygame uses) cost nothing; the rarer list carries a tag."""
        assert json_safe_value((1, 2)) == [1, 2]
        assert json_safe_value([1, 2]) == {'__list__': [1, 2]}

    def test_unicode_is_stored_as_is(self):
        """Text is not escaped or transliterated: the JSON value is the same string."""
        assert json_safe_value('é☃') == 'é☃'

    def test_nested_containers_keep_their_types(self):
        """A list inside a tuple inside a dict keeps every container type."""
        value = {'outer': ([1, 2], {'inner': (3,)})}

        decoded = _json_round_trip(value)

        assert decoded == value
        assert isinstance(decoded, dict)
        outer = decoded['outer']
        assert isinstance(outer, tuple)
        assert isinstance(outer[0], list)
        assert isinstance(outer[1], dict)
        assert isinstance(outer[1]['inner'], tuple)

    @pytest.mark.parametrize('value', [math.inf, -math.inf])
    def test_infinite_floats_round_trip(self, value):
        """JSON has no infinity; it is tagged and comes back."""
        assert _json_round_trip(value) == value

    def test_nan_round_trips(self):
        """JSON has no NaN; it is tagged and comes back as NaN."""
        decoded = _json_round_trip(math.nan)

        assert isinstance(decoded, float)
        assert math.isnan(decoded)

    def test_int_subclass_is_stored_as_its_int_value(self):
        """An IntEnum-like value (bool excepted) is stored as a plain int."""

        class Button(int):
            pass

        encoded = json_safe_value(Button(3))

        assert encoded == 3
        assert type(encoded) is int

    @pytest.mark.parametrize(
        ('value', 'expected', 'expected_type'),
        [
            (np.int64(7), 7, int),
            (np.float32(0.5), 0.5, float),
            (np.True_, True, bool),
        ],
    )
    def test_numpy_scalar_is_stored_as_a_plain_json_value(self, value, expected, expected_type):
        """A numpy scalar (a game's computed axis or index) is a plain number or bool."""
        encoded = json_safe_value(value)

        assert encoded == expected
        assert type(encoded) is expected_type
        assert json.loads(json.dumps(encoded, allow_nan=False)) == expected

    def test_non_finite_numpy_float_is_tagged(self):
        """A numpy infinity is tagged like a Python one."""
        assert json_safe_value(np.float32(math.inf)) == {'__float__': 'inf'}

    def test_vector_is_stored_as_a_tuple(self):
        """A pygame Vector2 becomes a tuple of its components."""
        assert value_from_json(json_safe_value(pygame.Vector2(1.5, -2))) == (1.5, -2.0)

    def test_dict_with_non_string_keys_is_kept_as_pairs(self):
        """Integer and tuple keys come back as themselves."""
        value = {1: 'one', (2, 3): 'pair'}

        assert _json_round_trip(value) == value

    def test_window_is_a_reference_by_id(self, event_queue):
        """A pygame Window (on window events) is stored as a reference to its id."""
        window = pygame.Window(title='recording test', size=WINDOW_SIZE)
        try:
            window_id = window.id
            encoded = json_safe_value(window)
            decoded = _json_round_trip(window)
        finally:
            window.destroy()

        assert encoded == {'__ref__': 'window', 'id': window_id}
        assert decoded == RecordedReference(kind='window', identifier=window_id)

    def test_joystick_is_a_reference_by_instance_id(self, mocker):
        """A joystick object is stored as a reference to its instance id."""
        joystick = mocker.Mock(spec=pygame.joystick.JoystickType)
        joystick.get_instance_id.return_value = TEST_JOYSTICK_INSTANCE_ID

        encoded = json_safe_value(joystick)

        assert encoded == {'__ref__': 'joystick', 'instance_id': TEST_JOYSTICK_INSTANCE_ID}
        assert _json_round_trip(joystick) == RecordedReference(
            kind='joystick', identifier=TEST_JOYSTICK_INSTANCE_ID
        )

    def test_other_objects_are_unrepresentable_by_type_name(self):
        """An object JSON cannot hold is marked with its type name and never raises."""
        encoded = json_safe_value(Gamepad())

        assert encoded == {'__unrepresentable__': GAMEPAD_TYPE_NAME}
        assert _json_round_trip(Gamepad()) == UnrepresentableValue(type_name=GAMEPAD_TYPE_NAME)

    def test_a_numpy_scalar_with_no_plain_form_is_unrepresentable(self):
        """A numpy complex scalar unwraps to a Python complex, which JSON cannot hold."""
        encoded = json_safe_value(np.complex128(1 + 2j))

        assert encoded == {'__unrepresentable__': 'numpy.complex128'}
        assert _json_round_trip(np.complex128(1 + 2j)) == UnrepresentableValue(
            type_name='numpy.complex128'
        )

    def test_unrepresentable_value_inside_a_container(self):
        """A sprite inside a payload dict marks only itself; the rest of the payload is kept."""
        value = {'menu_item': Gamepad(), 'index': 2}

        assert _json_round_trip(value) == {
            'menu_item': UnrepresentableValue(type_name=GAMEPAD_TYPE_NAME),
            'index': 2,
        }

    @pytest.mark.parametrize(
        'encoded',
        [
            {'unknown_tag': 1},
            {'__float__': 'big'},
            {'__list__': [1], 'extra': 2},
            {'__bytes__': 'zz'},
            {'__pairs__': [[1]]},
            {'__ref__': 'sprite', 'id': 1},
            {'__ref__': 'window', 'instance_id': 1},
            {'__ref__': 'window', 'id': 'one'},
            {'__ref__': 'window', 'id': True},
            {'__unrepresentable__': 3},
            {'__list__': 'not a list'},
            {'__mapping__': [1]},
            {'__float__': 5},
            {'__pairs__': 'not pairs'},
            {'__bytes__': 12},
        ],
    )
    def test_malformed_tagged_values_raise(self, encoded):
        """A JSON object that is not one of the tags is a format error, not a silent dict."""
        with pytest.raises(TraceFormatError):
            value_from_json(encoded)


class TestEventRecords:
    """A pygame event becomes a JSON record with its origin and every attribute, and back."""

    def test_key_event_record_holds_type_name_origin_and_attributes(self):
        """A KEYDOWN keeps its number, pygame's name, its origin and every attribute."""
        event = pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='é', scancode=4, window=None
        )

        record = event_to_record(event=event, origin=EXTERNAL_ORIGIN)

        assert record == {
            'type': pygame.KEYDOWN,
            'name': pygame.event.event_name(pygame.KEYDOWN),
            'origin': 'external',
            'attributes': {
                'key': pygame.K_a,
                'mod': 0,
                'unicode': 'é',
                'scancode': 4,
                'window': None,
            },
        }

    @pytest.mark.parametrize(
        'event',
        [
            pygame.event.Event(
                pygame.MOUSEMOTION, pos=(10, 20), rel=(-1, 2), buttons=(1, 0, 0), touch=False
            ),
            pygame.event.Event(pygame.JOYHATMOTION, instance_id=0, hat=0, value=(1, -1)),
            pygame.event.Event(pygame.JOYAXISMOTION, instance_id=2, axis=1, value=-0.25),
            pygame.event.Event(pygame.USEREVENT + 3, payload={'nested': [1, (2,)]}),
            pygame.event.Event(pygame.QUIT),
            # A game that opts in to the window system's messages records them: on x11 pygame
            # gives the raw XEvent as bytes
            pygame.event.Event(pygame.SYSWMEVENT, event=b'\x1c\x00\x00\x00\xf6\x30'),
        ],
    )
    def test_event_round_trips_through_json(self, event):
        """Decoding the JSON record gives an equal event (same type and attribute values)."""
        record = json.loads(
            json.dumps(event_to_record(event=event, origin=EXTERNAL_ORIGIN), allow_nan=False)
        )

        decoded = event_from_record(record)

        assert decoded.type == event.type
        assert decoded.dict == event.dict
        for name, value in event.dict.items():
            assert type(decoded.dict[name]) is type(value)

    def test_menu_event_with_sprites_is_recorded_not_dropped(self):
        """A MENUEVENT carrying sprite objects keeps the event; the sprites are marked."""
        event = pygame.event.Event(MENUEVENT, menu=Gamepad(), menu_item=Gamepad())

        record = json.loads(json.dumps(event_to_record(event=event, origin=INTERNAL_ORIGIN)))

        assert event_from_record(record).dict == {
            'menu': UnrepresentableValue(type_name=GAMEPAD_TYPE_NAME),
            'menu_item': UnrepresentableValue(type_name=GAMEPAD_TYPE_NAME),
        }

    @pytest.mark.parametrize(
        'record',
        [
            {'type': 'keydown', 'attributes': {}},
            {'type': pygame.KEYDOWN},
            {'type': pygame.KEYDOWN, 'attributes': [1, 2]},
        ],
    )
    def test_malformed_event_record_raises(self, record):
        """A record with no usable type or attributes is a format error naming the record."""
        with pytest.raises(TraceFormatError, match='Malformed event record'):
            event_from_record(record)


class TestCustomEventTypeRemap:
    """A recording's named custom event ids move to this process's (BUGS.md #211.1)."""

    def test_a_recording_made_now_names_every_registered_type(self):
        """The header holds the registry as this process allocated it."""
        assert custom_event_types_header() == dict(NAMED_CUSTOM_EVENT_TYPES)
        assert custom_event_types_header()['FPSEVENT'] == FPSEVENT

    def test_a_recording_with_this_processs_ids_moves_nothing(self):
        """The usual case: the same ids, so no frame is copied."""
        assert (
            custom_event_type_remap(header={'custom_event_types': custom_event_types_header()})
            == {}
        )

    def test_a_legacy_recording_in_an_unshifted_process_moves_nothing(self):
        """No field: made with USEREVENT + 1..3, which an unshifted process allocates too."""
        assert custom_event_type_remap(header={}) == {}

    def test_ids_recorded_otherwise_move_to_this_processs(self):
        """Each named type the header gives another id moves to this process's id."""
        header = {
            'custom_event_types': {'FPSEVENT': 40001, 'GAMEEVENT': GAMEEVENT, 'MENUEVENT': 40003}
        }

        assert custom_event_type_remap(header=header) == {40001: FPSEVENT, 40003: MENUEVENT}

    def test_a_games_named_type_moves_too(self, mocker):
        """A type a game registered by name is moved like the engine's."""
        mocker.patch.dict(events_base._NAMED_CUSTOM_EVENT_TYPES)
        level_up = named_custom_event_type('TEST_LEVEL_UP')
        header = {'custom_event_types': {**custom_event_types_header(), 'TEST_LEVEL_UP': 40010}}

        assert custom_event_type_remap(header=header) == {40010: level_up}

    def test_a_name_this_process_never_registered_is_left_as_recorded(self):
        """A newer engine's or another game's type: nothing to move it to."""
        header = {'custom_event_types': {**custom_event_types_header(), 'NOT_HERE': 40020}}

        assert custom_event_type_remap(header=header) == {}

    @pytest.mark.parametrize(
        'recorded', [[32866], {'FPSEVENT': '32866'}, {'FPSEVENT': True}, {'FPSEVENT': 1.5}, None]
    )
    def test_a_malformed_field_is_refused(self, recorded):
        """Not names to integer ids: the recording is malformed (bools are not ids)."""
        with pytest.raises(TraceFormatError, match='custom_event_types must map'):
            custom_event_type_remap(header={'custom_event_types': recorded})

    def test_records_move_in_batches_and_redelivered_events_only(self):
        """Every batch and redelivered record of a moved type moves; nothing else changes."""
        moved_type, kept_type = 40001, pygame.KEYDOWN
        frames = [
            {
                'dt': 0.1,
                EVENT_BATCHES_FIELD: [
                    [{'type': moved_type, 'attributes': {}}, {'type': kept_type, 'attributes': {}}],
                    [],
                ],
                REDELIVERED_EVENTS_FIELD: [{'type': moved_type, 'attributes': {'n': 1}}],
            },
            {'dt': 0.1},
        ]
        original = json.loads(json.dumps(frames))

        moved = remapped_event_records(frames=frames, remap={moved_type: FPSEVENT})

        assert moved[0][EVENT_BATCHES_FIELD] == [
            [{'type': FPSEVENT, 'attributes': {}}, {'type': kept_type, 'attributes': {}}],
            [],
        ]
        assert moved[0][REDELIVERED_EVENTS_FIELD] == [{'type': FPSEVENT, 'attributes': {'n': 1}}]
        assert moved[0]['dt'] == 0.1
        # A frame without event records is the same frame; the input is never changed (frames
        # share their records)
        assert moved[1] is frames[1]
        assert frames == original

    def test_a_frame_with_only_redelivered_events_moves_them(self):
        """No event batches (a frame a playback scope's held events reach first)."""
        frames = [{REDELIVERED_EVENTS_FIELD: [{'type': 40001, 'attributes': {}}]}]

        (moved,) = remapped_event_records(frames=frames, remap={40001: FPSEVENT})

        assert moved == {REDELIVERED_EVENTS_FIELD: [{'type': FPSEVENT, 'attributes': {}}]}

    def test_nothing_to_move_returns_the_same_frames(self):
        """The usual case costs nothing."""
        frames = [{EVENT_BATCHES_FIELD: [[{'type': FPSEVENT, 'attributes': {}}]]}]

        assert remapped_event_records(frames=frames, remap={}) is frames


class TestEventOrigin:
    """External events came from SDL; internal ones were posted by engine or game code."""

    def test_key_press_from_sdl_is_external(self, tmp_path, event_queue):
        """An event that did not go through post_event (here a stand-in for SDL) is external."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)

        assert _origins(read_trace_result(path=path).trace['frames'][0]) == [
            (pygame.KEYDOWN, EXTERNAL_ORIGIN)
        ]

    def test_fps_and_game_events_are_internal(self, tmp_path, event_queue):
        """Engine custom types are internal by type, however they were posted."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            post_event(pygame.event.Event(FPSEVENT, fps=60.0))
            pygame.event.post(pygame.event.Event(GAMEEVENT, subtype=1))
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)

        assert _origins(read_trace_result(path=path).trace['frames'][0]) == [
            (FPSEVENT, INTERNAL_ORIGIN),
            (GAMEEVENT, INTERNAL_ORIGIN),
        ]

    def test_code_posted_quit_is_internal_and_sdl_quit_is_external(self, tmp_path, event_queue):
        """A QUIT from post_event (quit_game) is internal; one from SDL (window close) is not."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            post_event(pygame.event.Event(pygame.QUIT))
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)
            # Stands in for SDL's window-close QUIT: not posted through post_event
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)

        frames = read_trace_result(path=path).trace['frames']
        assert _origins(frames[0]) == [(pygame.QUIT, INTERNAL_ORIGIN)]
        assert _origins(frames[1]) == [(pygame.QUIT, EXTERNAL_ORIGIN)]

    def test_matching_uses_attributes(self, tmp_path, event_queue):
        """A posted key event marks only the pumped event with the same attributes."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
            post_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b))
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)

        batch = read_trace_result(path=path).trace['frames'][0][EVENT_BATCHES_FIELD][0]
        assert [(record['attributes']['key'], record['origin']) for record in batch] == [
            (pygame.K_a, EXTERNAL_ORIGIN),
            (pygame.K_b, INTERNAL_ORIGIN),
        ]

    def test_post_the_pump_never_returned_is_forgotten(self, tmp_path, event_queue):
        """A post cleared from the queue cannot make a later SDL event look internal."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            post_event(pygame.event.Event(pygame.QUIT))
            pygame.event.clear()
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)

        frames = read_trace_result(path=path).trace['frames']
        assert frames[0][EVENT_BATCHES_FIELD] == [[]]
        assert _origins(frames[1]) == [(pygame.QUIT, EXTERNAL_ORIGIN)]

    def test_blocked_post_is_not_tracked(self, tmp_path, event_queue):
        """post_event reports a blocked type and does not wait for it to be pumped."""
        with GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={}):
            pygame.event.set_blocked(pygame.KEYDOWN)
            try:
                was_posted = post_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
            finally:
                pygame.event.set_allowed(pygame.KEYDOWN)
            pending_after_post = list(pending_internal_posts())

        assert was_posted is False
        assert pending_after_post == []

    def test_a_live_game_post_is_told_from_an_equal_scope_post(self, tmp_path, event_queue):
        """Posts made while the live game's code runs in a scope are marked, by identity."""
        with GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={}):
            post_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1}))
            set_live_game_code_running(running=True)
            try:
                post_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1}))
            finally:
                set_live_game_code_running(running=False)
            scope_post, live_post = pending_internal_posts()
            assert scope_post == live_post
            assert is_live_game_post(post=live_post) is True
            assert is_live_game_post(post=scope_post) is False
        # Closing the last recorder forgets them, as it forgets the pending posts
        assert live_game_posts() == []
        pygame.event.clear()

    def test_an_input_post_is_external_whatever_its_type(self, tmp_path, event_queue):
        """post_input_event is input to the game (a replay serves it), even a custom type."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            post_input_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1}))
            post_event(pygame.event.Event(pygame.USEREVENT, {'goal': 2}))
            post_input_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None)

        assert _origins(read_trace_result(path=path).trace['frames'][0]) == [
            (pygame.USEREVENT, EXTERNAL_ORIGIN),
            (pygame.USEREVENT, INTERNAL_ORIGIN),
            (pygame.KEYDOWN, EXTERNAL_ORIGIN),
        ]

    def test_an_input_post_is_told_from_an_equal_code_post(self, event_queue):
        """Matched by identity: an equal post_event queued first is still the game's own."""
        start_tracking_internal_posts()
        post_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1}))
        post_input_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1}))
        pending = pending_internal_posts()
        first, second = pygame.event.get()

        assert event_origin(event=first, pending=pending) == INTERNAL_ORIGIN
        assert event_origin(event=second, pending=pending) == EXTERNAL_ORIGIN
        stop_tracking_internal_posts()

    def test_pending_code_posts_leave_out_input_posts(self, event_queue):
        """A scene start's earlier internal events are the game's own posts only."""
        start_tracking_internal_posts()
        post_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1}))
        post_input_event(pygame.event.Event(pygame.USEREVENT, {'goal': 2}))

        assert len(pending_internal_posts()) == 2
        assert pending_code_post_count() == 1
        stop_tracking_internal_posts()

    def test_forgetting_pending_posts_forgets_input_posts(self, event_queue):
        start_tracking_internal_posts()
        post_input_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1}))
        input_post = pending_internal_posts()[0]
        forget_pending_posts()

        assert pending_internal_posts() == []
        assert is_input_post(post=input_post) is False
        stop_tracking_internal_posts()

    def test_input_posts_are_not_tracked_without_a_recorder(self, event_queue):
        """With no recording open, post_input_event only posts."""
        input_post = (pygame.USEREVENT, {'goal': 1})
        assert post_input_event(pygame.event.Event(pygame.USEREVENT, {'goal': 1})) is True
        assert pending_internal_posts() == []
        assert is_input_post(post=input_post) is False
        assert [event.type for event in pygame.event.get()] == [pygame.USEREVENT]

    def test_posts_are_not_tracked_without_a_recorder(self, event_queue):
        """With no recording open, post_event only posts."""
        assert post_event(pygame.event.Event(pygame.QUIT)) is True
        assert pending_internal_posts() == []
        assert [event.type for event in pygame.event.get()] == [pygame.QUIT]


class TestRecorderWriteFailures:
    """A recording that cannot be written part way (the disk fills): BUGS.md #82."""

    def test_a_failed_frame_write_raises_and_keeps_the_frames_before(
        self, tmp_path, mocker, event_queue
    ):
        path = tmp_path / 'play.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={})
        recorder.record_frame(dt=0.01, scene=None)
        mocker.patch.object(
            TraceWriter, 'write_frame', side_effect=OSError(28, 'No space left on device')
        )
        with pytest.raises(RecordingWriteError, match='No space left on device') as error_info:
            recorder.record_frame(dt=0.01, scene=None)
        assert error_info.value.path == path
        assert recorder.write_failed is True
        # Abandoned: closed, posts no longer tracked, later frames are not written
        assert posts_are_tracked() is False
        recorder.record_frame(dt=0.01, scene=None)
        recorder.close()
        result = read_trace_result(path=path)
        assert result.is_complete
        assert len(result.trace['frames']) == 1

    def test_a_failed_close_is_noted_not_raised(self, tmp_path, mocker, caplog):
        """The teardown goes on; the engine reads write_failed and exits CANNOT_WRITE_OUTPUT."""
        recorder = GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={})
        real_close = TraceWriter.close

        def close_then_fail(writer: TraceWriter) -> None:
            real_close(writer)
            raise OSError(errno.EIO, 'Input/output error')

        mocker.patch.object(TraceWriter, 'close', autospec=True, side_effect=close_then_fail)
        recorder.close()
        assert recorder.write_failed is True
        assert 'could not be written' in caplog.text

    def test_a_close_that_fails_after_a_failed_frame_write_is_logged_once(
        self, tmp_path, mocker, caplog
    ):
        """After a failed frame write the close fails too: one error line, not two."""
        recorder = GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={})
        real_close = TraceWriter.close

        def close_then_fail(writer: TraceWriter) -> None:
            real_close(writer)
            raise OSError(errno.ENOSPC, 'No space left on device')

        mocker.patch.object(TraceWriter, 'close', autospec=True, side_effect=close_then_fail)
        mocker.patch.object(
            TraceWriter, 'write_frame', side_effect=OSError(errno.ENOSPC, 'No space left on device')
        )
        with caplog.at_level(logging.ERROR, logger=recording.LOG.name):
            with pytest.raises(RecordingWriteError):
                recorder.record_frame(dt=0.01, scene=None)
            recorder.close()

        assert recorder.write_failed is True
        error_records = [record for record in caplog.records if record.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert 'could not be written' in error_records[0].getMessage()


class TestFrameHistories:
    """Each written frame carries its content hash and processing time, newest first."""

    def test_a_fresh_recording_starts_each_history_with_one_entry(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(dt=0.01, scene=None, processing_seconds=0.0021)
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[PROCESSING_SECONDS_FIELD] == [0.0021]
        assert frame[CONTENT_HASH_FIELD] == [frame_content_hash(frame_record=frame)]

    def test_a_frame_with_audio_work_carries_its_audio_measurements(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        account = AudioFrameAccount(
            audio_seconds=0.00212345678, audio_work=(('compile', 'coin', 2100), ('decode', 's', 23))
        )
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(dt=0.01, scene=None, audio_frame=account)
            recorder.record_frame(
                dt=0.01, scene=None, audio_frame=AudioFrameAccount(audio_seconds=0.0, audio_work=())
            )
            recorder.record_frame(dt=0.01, scene=None)
        worked, idle, unaccounted = read_trace_result(path=path).trace['frames']
        assert worked[AUDIO_SECONDS_FIELD] == 0.002123
        assert worked[AUDIO_WORK_FIELD] == [['compile', 'coin', 2100], ['decode', 's', 23]]
        assert worked[CONTENT_HASH_FIELD] == [frame_content_hash(frame_record=worked)]
        for frame in (idle, unaccounted):
            assert AUDIO_SECONDS_FIELD not in frame
            assert AUDIO_WORK_FIELD not in frame

    def test_an_unmeasured_frame_keeps_its_place(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(dt=0.01, scene=None)
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[PROCESSING_SECONDS_FIELD] == [None]

    def test_a_recording_over_a_replay_stacks_onto_the_replayed_frame(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(
                dt=0.01,
                scene=None,
                processing_seconds=0.003,
                previous_histories={
                    PROCESSING_SECONDS_FIELD: [0.002],
                    CONTENT_HASH_FIELD: ['0123456789abcdef'],
                },
            )
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[PROCESSING_SECONDS_FIELD] == [0.003, 0.002]
        assert frame[CONTENT_HASH_FIELD][1] == '0123456789abcdef'

    def test_the_stored_hash_is_the_hash_of_the_frame_read_back(self, tmp_path, event_queue):
        """A reader recomputes the hash from what it decodes: tagged floats, tuples, non-ASCII."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            post_event(
                pygame.event.Event(
                    pygame.USEREVENT, {'speed': float('inf'), 'pair': (1, 2), 'name': 'Ünïcødé'}
                )
            )
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None, processing_seconds=0.001)
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[CONTENT_HASH_FIELD][0] == frame_content_hash(frame_record=frame)


class TestFrameHashesDescribeWhatAReaderGets:
    """The hash is of the frame as JSON decodes it: keys become strings (final review #1)."""

    def test_integer_keys_hash_as_the_string_keys_a_reader_gets(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(
                dt=0.01,
                scene=None,
                control_events=[{'kind': 'cheat', 'data': {'slots': {1: 'a', 10: 'b', 2: 'c'}}}],
            )
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[CONTENT_HASH_FIELD][0] == frame_content_hash(frame_record=frame)

    def test_mixed_key_types_still_record(self, tmp_path):
        """Sorting int and str keys together raised TypeError and ended the run."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(
                dt=0.01,
                scene=None,
                control_events=[{'kind': 'cheat', 'data': {1: 'a', 'x': 'b'}}],
            )
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[CONTENT_HASH_FIELD][0] == frame_content_hash(frame_record=frame)


class TestGameplayRecorder:
    """The recorder writes one trace frame per record_frame, carrying dt and event batches."""

    def test_header_marks_a_recording(self, tmp_path):
        """The header has source 'recording', no fixed frame time and the given fields."""
        path = tmp_path / 'play.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={'random_seed': 5})
        recorder.close()

        header = _lines(path)[0]

        assert header['source'] == RECORDING_SOURCE
        assert header['frame_seconds'] is None
        assert header['random_seed'] == 5

    def test_frames_carry_dt_batches_and_sprites(self, tmp_path):
        """Batches recorded before a frame land in that frame, in order, then reset."""
        path = tmp_path / 'play.jsonl.gz'
        sprite = FakeSprite(x=0, y=0)
        scene = _scene(sprite)
        press = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        release = pygame.event.Event(pygame.KEYUP, key=pygame.K_a, mod=0, unicode='a')
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_event_batch(raw_events=[press, release])
            recorder.record_frame(dt=0.016, scene=scene)
            sprite.rect.x = 3
            recorder.record_frame(dt=0.017, scene=scene)

        frames = read_trace_result(path=path).trace['frames']

        assert [frame[DT_FIELD] for frame in frames] == [0.016, 0.017]
        assert [
            [record['type'] for record in batch] for batch in frames[0][EVENT_BATCHES_FIELD]
        ] == [[pygame.KEYDOWN, pygame.KEYUP]]
        # A frame that never read the queue has no batches
        assert frames[1][EVENT_BATCHES_FIELD] == []
        assert frames[1]['sprites'][0]['rect'] == [3, 0, 8, 8]

    def test_batch_boundaries_and_empty_batches_are_kept(self, tmp_path):
        """Two pumps in one frame give two batches, in order; an empty pump is an empty batch."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_event_batch(raw_events=[pygame.event.Event(pygame.KEYDOWN, key=1)])
            recorder.record_event_batch(raw_events=[])
            recorder.record_event_batch(
                raw_events=[
                    pygame.event.Event(pygame.KEYUP, key=1),
                    pygame.event.Event(pygame.KEYDOWN, key=2),
                ]
            )
            recorder.record_frame(dt=0.01, scene=None)

        batches = read_trace_result(path=path).trace['frames'][0][EVENT_BATCHES_FIELD]

        assert [[record['attributes']['key'] for record in batch] for batch in batches] == [
            [1],
            [],
            [1, 2],
        ]

    def test_given_origins_are_recorded_without_classifying(self, tmp_path, event_queue):
        """A pump that knows its origins (a replay's merge) is not re-classified by the tracker."""
        path = tmp_path / 'play.jsonl.gz'
        quit_event = pygame.event.Event(pygame.QUIT)
        with GameplayRecorder(path=path, header={}) as recorder:
            post_event(quit_event)
            recorder.record_event_batch(
                raw_events=[pygame.event.Event(pygame.KEYDOWN, key=1), quit_event],
                origins=[INTERNAL_ORIGIN, EXTERNAL_ORIGIN],
            )
            pending_after_batch = list(pending_internal_posts())
            recorder.record_frame(dt=0.01, scene=None)

        (frame,) = read_trace_result(path=path).trace['frames']
        assert _origins(frame) == [
            (pygame.KEYDOWN, INTERNAL_ORIGIN),
            (pygame.QUIT, EXTERNAL_ORIGIN),
        ]
        # The tracker's pending post was neither matched nor forgotten by this batch
        assert pending_after_batch == [(pygame.QUIT, {})]

    def test_new_scene_object_starts_a_keyframe_even_with_the_same_class(self, tmp_path):
        """A switch between two scenes of one class (two floors) writes a keyframe."""
        path = tmp_path / 'play.jsonl.gz'
        first_floor = _scene(FakeSprite(x=0, y=0))
        second_floor = _scene(FakeSprite(x=5, y=5))
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(dt=0.01, scene=first_floor)
            recorder.record_frame(dt=0.01, scene=first_floor)
            recorder.record_frame(dt=0.01, scene=second_floor)

        kinds = [line['kind'] for line in _lines(path)[1:]]

        assert kinds == ['keyframe', 'delta', 'keyframe']

    def test_frame_with_no_scene_is_written(self, tmp_path):
        """A frame whose active scene is None is a frame with scene null and no sprites."""
        path = tmp_path / 'play.jsonl.gz'
        scene = _scene(FakeSprite(x=0, y=0))
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(dt=0.01, scene=scene)
            recorder.record_frame(dt=0.01, scene=None)
            recorder.record_frame(dt=0.01, scene=scene)

        frames = read_trace_result(path=path).trace['frames']

        assert [frame['frame'] for frame in frames] == [0, 1, 2]
        assert frames[1]['scene'] is None
        assert frames[1]['sprites'] == []

    def test_frame_count_and_close_log(self, tmp_path, caplog):
        """Closing logs the path and how many frames were recorded; closing twice is fine."""
        path = tmp_path / 'play.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={})
        recorder.record_frame(dt=0.01, scene=None)
        recorder.record_frame(dt=0.01, scene=None)
        with caplog.at_level('INFO', logger='game.recording'):
            recorder.close()
            recorder.close()

        assert recorder.frame_count == 2
        messages = [record.getMessage() for record in caplog.records]
        assert messages == [f'Recorded 2 frames to {path}']

    def test_closing_stops_tracking_posts(self, tmp_path, event_queue):
        """Post tracking runs only while a recorder is open."""
        recorder = GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={})
        tracking_while_open = posts_are_tracked()
        recorder.close()

        assert tracking_while_open is True
        assert posts_are_tracked() is False

    def test_unclosed_recording_reads_every_frame(self, tmp_path):
        """A recorder never closed (the process was killed) leaves every frame readable."""
        path = tmp_path / 'play.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={})
        for frame_number in range(5):
            recorder.record_frame(dt=0.01 * (frame_number + 1), scene=None)

        result = read_trace_result(path=path)

        assert [frame[DT_FIELD] for frame in result.trace['frames']] == [
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
        ]
        assert not result.is_complete
        recorder.close()

    def test_killed_mid_frame_keeps_complete_frames_and_reports_the_partial_line(self, tmp_path):
        """A file cut inside its last frame reads back every complete frame."""
        path = tmp_path / 'play.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={})
        sprite = FakeSprite(x=0, y=0)
        scene = _scene(sprite)
        for frame_number in range(4):
            sprite.rect.x = frame_number
            recorder.record_frame(dt=0.01, scene=scene)
        complete_size = path.stat().st_size
        # A long last frame, so cutting its flushed block still leaves part of its line
        recorder.record_event_batch(
            raw_events=[pygame.event.Event(pygame.USEREVENT, text='x' * 400)]
        )
        recorder.record_frame(dt=0.01, scene=scene)
        file_bytes = path.read_bytes()
        cut_path = tmp_path / 'cut.jsonl.gz'
        cut_path.write_bytes(file_bytes[: complete_size + (len(file_bytes) - complete_size) // 2])

        result = read_trace_result(path=cut_path)

        assert [frame['frame'] for frame in result.trace['frames']] == [0, 1, 2, 3]
        assert result.dropped_partial_line
        assert not result.is_complete
        recorder.close()


class TestInternalPostTracking:
    """Post tracking has owners: it runs while at least one owner holds it."""

    def test_tracking_runs_until_the_last_owner_stops(self, event_queue):
        """A second owner keeps tracking on after the first one stops."""
        start_tracking_internal_posts()
        start_tracking_internal_posts()
        stop_tracking_internal_posts()
        tracking_with_one_owner = posts_are_tracked()
        stop_tracking_internal_posts()

        assert tracking_with_one_owner is True
        assert posts_are_tracked() is False

    def test_closing_a_recorder_leaves_another_owner_tracking(self, tmp_path, event_queue):
        """A recorder closing never switches tracking off under another owner (a replay)."""
        start_tracking_internal_posts()
        GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={}).close()
        post_event(pygame.event.Event(pygame.QUIT))

        assert posts_are_tracked() is True
        assert pending_internal_posts() == [(pygame.QUIT, {})]
        stop_tracking_internal_posts()

    def test_stopping_with_no_owner_stays_at_zero(self, event_queue):
        """An unmatched stop cannot make the count negative (a later start still tracks)."""
        stop_tracking_internal_posts()
        start_tracking_internal_posts()

        assert posts_are_tracked() is True
        stop_tracking_internal_posts()
        assert posts_are_tracked() is False

    def test_reset_forgets_owners_and_pending_posts(self, event_queue):
        """reset_internal_post_tracking: no owners and nothing pending (a new run, a test)."""
        start_tracking_internal_posts()
        post_event(pygame.event.Event(pygame.QUIT))
        reset_internal_post_tracking()

        assert posts_are_tracked() is False
        assert pending_internal_posts() == []

    def test_pending_posts_are_the_trackers_own_list(self, event_queue):
        """event_origin removes a match from pending_internal_posts() (a replay's pump does)."""
        start_tracking_internal_posts()
        post_event(pygame.event.Event(pygame.QUIT))
        pending = pending_internal_posts()
        (pumped,) = pygame.event.get()

        assert event_origin(event=pumped, pending=pending) == INTERNAL_ORIGIN
        assert pending_internal_posts() == []

    def test_one_contexts_pump_never_forgets_another_contexts_posts(self, event_queue):
        """A pump in one context forgets only that context's pending posts (audit C19).

        The engine context spike (2026-10-27): the second game's pump forgot the first game's
        posted QUIT, so the first game's replay no longer knew it as its own.
        """
        first = EngineContext(name='first')
        second = EngineContext(name='second')
        with first.active():
            start_tracking_internal_posts()
            post_event(pygame.event.Event(pygame.QUIT))
        with second.active():
            start_tracking_internal_posts()
            forget_pending_posts()
            stop_tracking_internal_posts()
        with first.active():
            first_pending = list(pending_internal_posts())
            stop_tracking_internal_posts()
        pygame.event.clear()

        assert first_pending == [(pygame.QUIT, {})]

    def test_a_new_run_in_one_context_keeps_another_contexts_tracking(self, event_queue):
        """reset_internal_post_tracking (every GameEngine.__init__) resets only its context."""
        first = EngineContext(name='first')
        with first.active():
            start_tracking_internal_posts()
        with EngineContext(name='second').active():
            reset_internal_post_tracking()
        with first.active():
            first_still_tracks = posts_are_tracked()
            stop_tracking_internal_posts()

        assert first_still_tracks is True
        stop_tracking_internal_posts()


def _recording_sources(*, path: Path) -> tuple[RecordingSources, GameplayRecorder, LiveSources]:
    recorder = GameplayRecorder(path=path, header={'game_class': 'Unit'})
    inner = LiveSources(random_seed=1)
    return RecordingSources(inner=inner, recorder=recorder), recorder, inner


def _end_frame(sources: RecordingSources, *, frame_number: int) -> None:
    sources.end_frame(frame_number=frame_number, dt=0.016, scene=None, control_events=[])


class OverlayDrawingSources(LiveSources):
    """Live doors that draw an overlay of their own: a white top-left pixel."""

    @property
    def draws_overlay(self) -> bool:
        """These doors draw an overlay."""
        return True

    def draw_overlay(self, *, surface: pygame.Surface) -> None:
        """Mark the top-left pixel white."""
        surface.set_at((0, 0), (255, 255, 255))


class TestRecordingSources:
    """RecordingSources records what passes through the doors it wraps."""

    def test_the_overlay_is_the_inner_doors_and_is_not_recorded(self, tmp_path):
        """The wrapped doors draw their overlay on the surface; nothing of it is recorded."""
        path = tmp_path / 'unit.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={'game_class': 'Unit'})
        sources = RecordingSources(inner=OverlayDrawingSources(random_seed=1), recorder=recorder)
        surface = pygame.Surface((4, 4))
        surface.fill((0, 0, 0))

        sources.draw_overlay(surface=surface)
        _end_frame(sources, frame_number=0)
        recorder.close()

        assert sources.draws_overlay
        assert tuple(surface.get_at((0, 0))) == (255, 255, 255, 255)
        assert tuple(surface.get_at((1, 1))) == (0, 0, 0, 255)
        (frame,) = read_trace_result(path=path).trace['frames']
        assert 'overlay' not in json.dumps(frame)

    def test_recording_sources_write_the_frames_audio_account(self, tmp_path):
        """Only the recording doors write the account; the inner doors get it too."""
        path = tmp_path / 'unit.jsonl.gz'
        sources, recorder, _inner = _recording_sources(path=path)
        account = AudioFrameAccount(audio_seconds=0.001, audio_work=(('compile', 'coin', 1000),))

        sources.end_frame(
            frame_number=0, dt=0.016, scene=None, control_events=[], audio_frame=account
        )
        recorder.close()

        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[AUDIO_WORK_FIELD] == [['compile', 'coin', 1000]]

    def test_recording_sources_write_only_non_empty_fields(self, tmp_path):
        """A frame with no control events has no control_events field."""
        path = tmp_path / 'unit.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={'game_class': 'Unit'})
        sources = RecordingSources(inner=LiveSources(random_seed=1), recorder=recorder)
        sources.end_frame(frame_number=0, dt=0.016, scene=None, control_events=[])
        sources.end_frame(
            frame_number=1,
            dt=0.016,
            scene=None,
            control_events=[ControlEvent(kind='breakpoint', data={'label': 'b'})],
        )
        recorder.close()
        first, second = read_trace_result(path=path).trace['frames']
        assert CONTROL_EVENTS_FIELD not in first
        assert second[CONTROL_EVENTS_FIELD] == [{'kind': 'breakpoint', 'label': 'b'}]
        for field in (
            INPUT_CHANGES_FIELD,
            DEVICES_OPENED_FIELD,
            SAVES_OPENED_FIELD,
            DEVICE_ENUMERATION_FIELD,
        ):
            assert field not in first
            assert field not in second

    def test_input_changes_diff_against_the_previous_frame(self, tmp_path, mocker):
        """The first snapshot diffs against IDLE_INPUT; an unchanged frame records nothing."""
        path = tmp_path / 'unit.jsonl.gz'
        sources, recorder, inner = _recording_sources(path=path)
        held_a = dataclasses.replace(IDLE_INPUT, pressed_scancodes=frozenset({4}))
        mocker.patch.object(inner, 'input_snapshot', side_effect=[held_a, held_a, IDLE_INPUT])
        served_snapshots = []
        for frame_number in range(3):
            served_snapshots.append(sources.input_snapshot())
            _end_frame(sources, frame_number=frame_number)
        # A frame that took no snapshot (none asked) records no change either
        _end_frame(sources, frame_number=3)
        recorder.close()

        frames = read_trace_result(path=path).trace['frames']
        assert served_snapshots == [held_a, held_a, IDLE_INPUT]
        # Scancode 4 is held as the key code this machine's keymap gives it (A on QWERTY)
        assert frames[0][INPUT_CHANGES_FIELD] == {
            'pressed_scancodes': [4],
            'held_key_codes': sorted(held_key_codes(snapshot=held_a)),
        }
        assert INPUT_CHANGES_FIELD not in frames[1]
        assert frames[2][INPUT_CHANGES_FIELD] == {'pressed_scancodes': [], 'held_key_codes': []}
        assert INPUT_CHANGES_FIELD not in frames[3]

    def test_a_save_namespace_is_snapshotted_once_when_first_opened(self, tmp_path, mocker):
        """Opened during recording: snapshotted in that frame, before the game writes to it."""
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: tmp_path / 'saves' / app_name,
        )
        path = tmp_path / 'unit.jsonl.gz'
        sources, recorder, inner = _recording_sources(path=path)
        store = sources.saves(namespace='unit-game')
        store.save('progress', {'level': 3})
        reopened = sources.saves(namespace='unit-game')
        _end_frame(sources, frame_number=0)
        sources.saves(namespace='unit-game')
        _end_frame(sources, frame_number=1)
        recorder.close()

        frames = read_trace_result(path=path).trace['frames']
        assert reopened is store
        assert store is inner.opened_save_namespaces['unit-game']
        # Snapshotted when opened, while it was still empty
        assert frames[0][SAVES_OPENED_FIELD] == {'unit-game': {}}
        assert SAVES_OPENED_FIELD not in frames[1]

    def test_a_namespace_in_the_header_is_not_snapshotted_again(self, tmp_path, mocker):
        """A store the header already holds (opened before recording) is not re-recorded."""
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: tmp_path / 'saves' / app_name,
        )
        path = tmp_path / 'unit.jsonl.gz'
        recorder = GameplayRecorder(path=path, header={SAVES_HEADER_FIELD: {'unit-game': {}}})
        sources = RecordingSources(inner=LiveSources(random_seed=1), recorder=recorder)
        sources.saves(namespace='unit-game')
        _end_frame(sources, frame_number=0)
        recorder.close()

        (frame,) = read_trace_result(path=path).trace['frames']
        assert SAVES_OPENED_FIELD not in frame

    def test_pumped_batches_are_recorded_with_their_origins(self, tmp_path, event_queue):
        """Each pump's batch is recorded raw; a post_event post is internal."""
        path = tmp_path / 'unit.jsonl.gz'
        sources, recorder, _inner = _recording_sources(path=path)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
        post_event(pygame.event.Event(pygame.QUIT))
        batch = sources.pump_events()
        empty_batch = sources.pump_events()
        _end_frame(sources, frame_number=0)
        recorder.close()

        (frame,) = read_trace_result(path=path).trace['frames']
        assert [event.type for event in batch] == [pygame.KEYDOWN, pygame.QUIT]
        assert empty_batch == []
        assert _origins(frame) == [
            (pygame.KEYDOWN, EXTERNAL_ORIGIN),
            (pygame.QUIT, INTERNAL_ORIGIN),
        ]
        assert frame[EVENT_BATCHES_FIELD][1] == []

    def test_untaken_device_answers_are_recorded_before_the_inner_end_frame(self, tmp_path, mocker):
        """Answers given in a frame are taken before LiveSources.end_frame discards them."""
        mocker.patch.object(devices_module.pygame.joystick, 'get_count', return_value=2)
        path = tmp_path / 'unit.jsonl.gz'
        sources, recorder, inner = _recording_sources(path=path)
        inner_end_frame = mocker.spy(inner, 'end_frame')
        assert sources.devices() is inner.devices()
        assert sources.devices().joystick_count() == 2
        _end_frame(sources, frame_number=0)
        _end_frame(sources, frame_number=1)
        recorder.close()

        first, second = read_trace_result(path=path).trace['frames']
        assert first[DEVICE_ENUMERATION_FIELD] == [
            {'call': 'joystick_count', 'device_index': None, 'value': 2, 'error': None}
        ]
        assert DEVICE_ENUMERATION_FIELD not in second
        assert inner_end_frame.call_count == 2

    def test_everything_else_is_delegated(self, tmp_path, mocker):
        """Seed, opened stores, stop request, frame time, clocks and control events: inner's."""
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: tmp_path / 'saves' / app_name,
        )
        sources, recorder, inner = _recording_sources(path=tmp_path / 'unit.jsonl.gz')
        recorder.close()
        opened_by_inner = inner.saves(namespace='opened-inside')

        assert sources.inner is inner
        assert sources.random_seed == 1
        assert dict(sources.opened_save_namespaces) == {'opened-inside': opened_by_inner}
        assert sources.stop_requested is False
        assert sources.frame_seconds(measured=0.25) == 0.25
        assert sources.control_events_for_frame(frame_number=3) == []
        assert sources.wall_clock_time().tzinfo is not None

    def test_the_wall_clock_is_the_recorded_start_plus_the_frame_clock(self, tmp_path):
        """A recorded run reads the wall clock its replay will serve, so it replays exactly."""
        recorder = GameplayRecorder(
            path=tmp_path / 'unit.jsonl.gz',
            header={'game_class': 'Unit', 'recorded_at': '2026-10-19T12:00:00+00:00'},
        )
        sources = RecordingSources(inner=LiveSources(random_seed=1), recorder=recorder)
        frame_clock_before = frame_clock_seconds()
        try:
            set_frame_clock_seconds(seconds=2.5)
            assert sources.wall_clock_time() == datetime(2026, 10, 19, 12, 0, 2, 500000, tzinfo=UTC)
        finally:
            set_frame_clock_seconds(seconds=frame_clock_before)
            recorder.close()

    def test_scene_starts_are_captured_while_recording(self, tmp_path):
        """Open, the doors capture scene starts; closed, they answer as the inner doors do."""
        sources, recorder, inner = _recording_sources(path=tmp_path / 'unit.jsonl.gz')

        assert inner.captures_scene_starts is False
        assert sources.captures_scene_starts is True
        recorder.close()
        assert sources.captures_scene_starts is False

    def test_a_scene_without_a_start_capture_has_no_scene_start(self, tmp_path):
        """A scene made while starts were not captured is recorded without scene_start."""
        path = tmp_path / 'unit.jsonl.gz'
        sources, recorder, _inner = _recording_sources(path=path)
        sources.end_frame(
            frame_number=0, dt=0.016, scene=_scene(FakeSprite(x=0, y=0)), control_events=[]
        )
        recorder.close()

        (frame,) = read_trace_result(path=path).trace['frames']
        assert SCENE_START_FIELD not in frame

    def test_a_closed_recorder_records_nothing_more(self, tmp_path, event_queue):
        """After stop_trace_recording closes the recorder, the doors only delegate."""
        path = tmp_path / 'unit.jsonl.gz'
        sources, recorder, _inner = _recording_sources(path=path)
        _end_frame(sources, frame_number=0)
        recorder.close()
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        batch = sources.pump_events()
        _end_frame(sources, frame_number=1)

        assert [event.type for event in batch] == [pygame.QUIT]
        assert recorder.frame_count == 1
        assert len(read_trace_result(path=path).trace['frames']) == 1
