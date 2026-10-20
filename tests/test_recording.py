"""Tests for gameplay recording (glitchygames/recording.py).

A recording is a trace (glitchygames/tracing.py) whose frames also carry the frame's ``dt``
and ``event_batches``: every batch the engine read from SDL's queue that frame, raw, each
event tagged with its origin (external from SDL, internal from code). Event attributes are
stored in a JSON-safe form that decodes back to the values pygame gave, with references for
pygame objects and a marker for values that cannot be stored.
"""

from __future__ import annotations

import ast
import dataclasses
import gzip
import json
import math
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pygame
import pytest

from glitchygames import recording
from glitchygames.events import FPSEVENT, GAMEEVENT, MENUEVENT
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
    SAVES_HEADER_FIELD,
    SAVES_OPENED_FIELD,
    SCENE_START_FIELD,
    GameplayRecorder,
    RecordedReference,
    RecordingSources,
    UnrepresentableValue,
    event_from_record,
    event_origin,
    event_to_record,
    is_live_game_post,
    json_safe_value,
    live_game_posts,
    pending_internal_posts,
    post_event,
    reset_internal_post_tracking,
    set_live_game_code_running,
    start_tracking_internal_posts,
    stop_tracking_internal_posts,
    value_from_json,
)
from glitchygames.sources import frame_clock_seconds, set_frame_clock_seconds
from glitchygames.supervision import ControlEvent
from glitchygames.tracing import TraceFormatError, read_trace_result

WINDOW_SIZE = (16, 16)
TEST_JOYSTICK_INSTANCE_ID = 7


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
    return types.SimpleNamespace(all_sprites=FakeGroup(*sprites))


def _lines(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, 'rt', encoding='utf-8') as trace_file:
        return [json.loads(line) for line in trace_file]


def _json_round_trip(value: object) -> object:
    return value_from_json(json.loads(json.dumps(json_safe_value(value), allow_nan=False)))


def _pump_batch(recorder: GameplayRecorder) -> None:
    """Read SDL's queue and record the batch, as GameEngine._pump_events does."""
    recorder.record_event_batch(raw_events=pygame.event.get())


def _origins(frame: dict[str, Any]) -> list[tuple[int, str]]:
    return [(record['type'], record['origin']) for record in frame[EVENT_BATCHES_FIELD][0]]


@pytest.fixture(autouse=True)
def no_tracked_posts(mocker):
    """Give each test a fresh internal-post tracker (a recorder left open cannot leak)."""
    mocker.patch.object(recording, '_INTERNAL_POSTS', recording.InternalEventPosts())


@pytest.fixture
def event_queue(monkeypatch):
    """Initialize pygame's display (dummy driver) so events can be posted; empty the queue.

    Yields:
        None, with an empty queue.

    """
    if not pygame.display.get_init():
        monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
        pygame.display.init()
    pygame.event.clear()
    yield
    pygame.event.clear()


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
            pending_after_post = list(recording._INTERNAL_POSTS.pending)

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

    def test_posts_are_not_tracked_without_a_recorder(self, event_queue):
        """With no recording open, post_event only posts."""
        assert post_event(pygame.event.Event(pygame.QUIT)) is True
        assert recording._INTERNAL_POSTS.pending == []
        assert [event.type for event in pygame.event.get()] == [pygame.QUIT]


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

    def test_closing_stops_tracking_posts(self, tmp_path):
        """Post tracking runs only while a recorder is open."""
        recorder = GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={})
        tracking_while_open = recording._INTERNAL_POSTS.is_tracking
        recorder.close()

        assert tracking_while_open is True
        assert recording._INTERNAL_POSTS.is_tracking is False

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

    def test_tracking_runs_until_the_last_owner_stops(self):
        """A second owner keeps tracking on after the first one stops."""
        start_tracking_internal_posts()
        start_tracking_internal_posts()
        stop_tracking_internal_posts()
        tracking_with_one_owner = recording._INTERNAL_POSTS.is_tracking
        stop_tracking_internal_posts()

        assert tracking_with_one_owner is True
        assert recording._INTERNAL_POSTS.is_tracking is False

    def test_closing_a_recorder_leaves_another_owner_tracking(self, tmp_path, event_queue):
        """A recorder closing never switches tracking off under another owner (a replay)."""
        start_tracking_internal_posts()
        GameplayRecorder(path=tmp_path / 'play.jsonl.gz', header={}).close()
        post_event(pygame.event.Event(pygame.QUIT))

        assert recording._INTERNAL_POSTS.is_tracking is True
        assert pending_internal_posts() == [(pygame.QUIT, {})]
        stop_tracking_internal_posts()

    def test_stopping_with_no_owner_stays_at_zero(self):
        """An unmatched stop cannot make the count negative (a later start still tracks)."""
        stop_tracking_internal_posts()
        start_tracking_internal_posts()

        assert recording._INTERNAL_POSTS.is_tracking is True
        stop_tracking_internal_posts()
        assert recording._INTERNAL_POSTS.is_tracking is False

    def test_reset_forgets_owners_and_pending_posts(self, event_queue):
        """reset_internal_post_tracking: no owners and nothing pending (a new run, a test)."""
        start_tracking_internal_posts()
        post_event(pygame.event.Event(pygame.QUIT))
        reset_internal_post_tracking()

        assert recording._INTERNAL_POSTS.is_tracking is False
        assert pending_internal_posts() == []

    def test_pending_posts_are_the_trackers_own_list(self, event_queue):
        """event_origin removes a match from pending_internal_posts() (a replay's pump does)."""
        start_tracking_internal_posts()
        post_event(pygame.event.Event(pygame.QUIT))
        pending = pending_internal_posts()
        (pumped,) = pygame.event.get()

        assert event_origin(event=pumped, pending=pending) == INTERNAL_ORIGIN
        assert pending_internal_posts() == []
        stop_tracking_internal_posts()


def _recording_sources(*, path: Path) -> tuple[RecordingSources, GameplayRecorder, LiveSources]:
    recorder = GameplayRecorder(path=path, header={'game_class': 'Unit'})
    inner = LiveSources(random_seed=1)
    return RecordingSources(inner=inner, recorder=recorder), recorder, inner


def _end_frame(sources: RecordingSources, *, frame_number: int) -> None:
    sources.end_frame(frame_number=frame_number, dt=0.016, scene=None, control_events=[])


class TestRecordingSources:
    """RecordingSources records what passes through the doors it wraps."""

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

    def test_a_scene_stand_in_has_no_scene_start(self, tmp_path):
        """A SceneInterface stand-in without a start capture is recorded without scene_start."""
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


# Calls that read (or drain) SDL's event queue. Only the doors' event pumps may use them, each
# named by (file relative to the package, qualified function name); GameEngine._pump_events
# reads through the active sources. A new pump (e.g. a replay's) is added here on purpose
_PUMP_SEAMS = frozenset({('live_sources.py', 'LiveSources.pump_events')})
_QUEUE_READING_ATTRIBUTES = frozenset({'get', 'poll', 'wait', 'peek', 'pump', 'clear'})
_EVENT_MODULE_NAMES = frozenset({'event', 'fastevent'})
_GETATTR_MINIMUM_ARGUMENTS = 2


def _is_pygame_event_module(node: ast.AST) -> bool:
    """Report whether a node is ``pygame.event``/``pygame.fastevent`` or a getattr of one."""
    if isinstance(node, ast.Attribute):
        return (
            node.attr in _EVENT_MODULE_NAMES
            and isinstance(node.value, ast.Name)
            and node.value.id == 'pygame'
        )
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr':
        # getattr(object, name[, default]): fewer arguments cannot name a module
        if len(node.args) < _GETATTR_MINIMUM_ARGUMENTS:
            return False
        target, name = node.args[0], node.args[1]
        return (
            isinstance(target, ast.Name)
            and target.id == 'pygame'
            and isinstance(name, ast.Constant)
            and name.value in _EVENT_MODULE_NAMES
        )
    return False


def _event_module_aliases(tree: ast.AST) -> set[str]:
    """Return the names the file binds to a pygame event module (``x = getattr(pygame, ...)``).

    Returns:
        Every name assigned a pygame event module anywhere in the file.

    """
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_pygame_event_module(node.value):
            aliases.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and _is_pygame_event_module(node.value)
            and isinstance(node.target, ast.Name)
        ):
            aliases.add(node.target.id)
    return aliases


def _queue_read_description(*, node: ast.AST, aliases: set[str]) -> str | None:
    """Describe a queue read (``pygame.event.get``, or ``<alias>.get`` through an alias).

    Returns:
        The read as written, or None when the node is not a queue read.

    """
    if not isinstance(node, ast.Attribute) or node.attr not in _QUEUE_READING_ATTRIBUTES:
        return None
    module = node.value
    if _is_pygame_event_module(module) and isinstance(module, ast.Attribute):
        return f'pygame.{module.attr}.{node.attr}'
    if isinstance(module, ast.Name) and module.id in aliases:
        return f'{module.id}.{node.attr}'
    return None


def _nodes_with_qualified_names(*, node: ast.AST, qualified_name: str) -> list[tuple[ast.AST, str]]:
    """List every node under ``node`` with the qualified name of the def/class enclosing it.

    Returns:
        (node, qualified name) pairs; module-level nodes have the name ''.

    """
    pairs: list[tuple[ast.AST, str]] = []
    for child in ast.iter_child_nodes(node):
        child_qualified_name = qualified_name
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            child_qualified_name = (
                f'{qualified_name}.{child.name}' if qualified_name else child.name
            )
        pairs.append((child, child_qualified_name))
        pairs.extend(_nodes_with_qualified_names(node=child, qualified_name=child_qualified_name))
    return pairs


def _queue_reads_outside_the_pump_seam(*, source_path: Path, relative_path: str) -> list[str]:
    """List each queue read in a file outside the pump seams named in ``_PUMP_SEAMS``.

    Args:
        source_path: The file to scan.
        relative_path: Its path relative to the package root, as ``_PUMP_SEAMS`` names it.

    Returns:
        One ``path:line qualified.name read`` entry per offending read.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    aliases = _event_module_aliases(tree)
    offenders: list[str] = []
    for node, qualified_name in _nodes_with_qualified_names(node=tree, qualified_name=''):
        description = _queue_read_description(node=node, aliases=aliases)
        if description is None or (relative_path, qualified_name) in _PUMP_SEAMS:
            continue
        line_number = getattr(node, 'lineno', 0)
        offenders.append(f'{relative_path}:{line_number} {qualified_name} {description}')
    return offenders


def test_pump_seam_is_the_only_place_the_engine_reads_sdl_queue():
    """Every read of SDL's queue in the package goes through the doors' event pump.

    A recording must see every batch, and a replay must be able to substitute every batch,
    so no other code may call pygame.event.get/poll/wait/peek/pump/clear (directly or through
    an alias such as ``getattr(pygame, 'fastevent')``).
    """
    package_root = Path(recording.__file__).parent
    offenders = [
        offender
        for source_path in sorted(package_root.rglob('*.py'))
        for offender in _queue_reads_outside_the_pump_seam(
            source_path=source_path,
            relative_path=source_path.relative_to(package_root).as_posix(),
        )
    ]

    assert offenders == []


def test_every_pump_seam_still_reads_the_queue():
    """Each allowed seam exists and reads the queue (the allow list cannot go stale)."""
    package_root = Path(recording.__file__).parent
    for relative_path, qualified_name in _PUMP_SEAMS:
        source_path = package_root / relative_path
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        aliases = _event_module_aliases(tree)
        seam_reads = [
            description
            for node, node_qualified_name in _nodes_with_qualified_names(
                node=tree, qualified_name=''
            )
            if node_qualified_name == qualified_name
            and (description := _queue_read_description(node=node, aliases=aliases)) is not None
        ]
        # LiveSources.pump_events reads pygame.event.get and the fastevent alias's get
        assert seam_reads, (relative_path, qualified_name)


_OFFENDER_FIXTURE = """import pygame


class LiveSources:
    def pump_events(self):
        fastevent = getattr(pygame, 'fastevent', None)
        if fastevent is not None:
            return list(fastevent.get())
        return list(pygame.event.get())


class OtherSources:
    def pump_events(self):
        return pygame.event.get()


def elsewhere():
    return pygame.event.poll()


def sneaky():
    queue = getattr(pygame, 'event')
    return queue.peek()
"""


def test_pump_seam_scan_allows_only_the_named_seam(tmp_path):
    """The scan reports reads outside the named (file, function), aliases included."""
    source_path = tmp_path / 'live_sources.py'
    source_path.write_text(_OFFENDER_FIXTURE, encoding='utf-8')

    assert _queue_reads_outside_the_pump_seam(
        source_path=source_path, relative_path='live_sources.py'
    ) == [
        'live_sources.py:14 OtherSources.pump_events pygame.event.get',
        'live_sources.py:18 elsewhere pygame.event.poll',
        'live_sources.py:23 sneaky queue.peek',
    ]


def test_pump_seam_scan_names_the_file_too(tmp_path):
    """The same LiveSources.pump_events in another file is not a seam."""
    source_path = tmp_path / 'reader.py'
    source_path.write_text(_OFFENDER_FIXTURE, encoding='utf-8')

    offenders = _queue_reads_outside_the_pump_seam(
        source_path=source_path, relative_path='reader.py'
    )

    assert offenders[:2] == [
        'reader.py:8 LiveSources.pump_events fastevent.get',
        'reader.py:9 LiveSources.pump_events pygame.event.get',
    ]
    assert len(offenders) == 5
