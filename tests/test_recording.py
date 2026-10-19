"""Tests for gameplay recording (glitchygames/recording.py).

A recording is a trace (glitchygames/tracing.py) whose frames also carry the frame's ``dt``
and ``event_batches``: every batch the engine read from SDL's queue that frame, raw, each
event tagged with its origin (external from SDL, internal from code). Event attributes are
stored in a JSON-safe form that decodes back to the values pygame gave, with references for
pygame objects and a marker for values that cannot be stored.
"""

from __future__ import annotations

import ast
import gzip
import json
import math
import types
from pathlib import Path
from typing import Any

import numpy as np
import pygame
import pytest

from glitchygames import recording
from glitchygames.events import FPSEVENT, GAMEEVENT, MENUEVENT
from glitchygames.recording import (
    DT_FIELD,
    EVENT_BATCHES_FIELD,
    EXTERNAL_ORIGIN,
    INTERNAL_ORIGIN,
    RECORDING_SOURCE,
    GameplayRecorder,
    RecordedReference,
    UnrepresentableValue,
    event_from_record,
    event_to_record,
    json_safe_value,
    post_event,
    value_from_json,
)
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


# Calls that read (or drain) SDL's event queue; only a doors' event pump may use them
# (LiveSources.pump_events in glitchygames/live_sources.py, which GameEngine._pump_events calls)
_PUMP_SEAM_FUNCTION_NAME = 'pump_events'
_QUEUE_READING_ATTRIBUTES = frozenset({'get', 'poll', 'wait', 'peek', 'pump', 'clear'})
_EVENT_MODULE_NAMES = frozenset({'event', 'fastevent'})


def _is_queue_read(node: ast.AST) -> bool:
    """Report whether a node is ``pygame.event.<read>`` or ``pygame.fastevent.<read>``."""
    if not isinstance(node, ast.Attribute) or node.attr not in _QUEUE_READING_ATTRIBUTES:
        return False
    module = node.value
    if not isinstance(module, ast.Attribute) or module.attr not in _EVENT_MODULE_NAMES:
        return False
    return isinstance(module.value, ast.Name) and module.value.id == 'pygame'


def _queue_reads_outside_the_pump_seam(source_path: Path) -> list[str]:
    """List each reference to a queue-reading pygame call outside a ``pump_events`` method."""
    tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    allowed_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == _PUMP_SEAM_FUNCTION_NAME:
            allowed_nodes.update(id(child) for child in ast.walk(node))
    return [
        f'{source_path}:{node.lineno} pygame.{node.value.attr}.{node.attr}'
        for node in ast.walk(tree)
        if _is_queue_read(node)
        and id(node) not in allowed_nodes
        and isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
    ]


def test_pump_seam_is_the_only_place_the_engine_reads_sdl_queue():
    """Every read of SDL's queue in the package goes through the doors' event pump.

    A recording must see every batch, and a replay must be able to substitute every batch,
    so no other code may call pygame.event.get/poll/wait/peek/pump/clear.
    """
    package_root = Path(recording.__file__).parent
    offenders = [
        offender
        for source_path in sorted(package_root.rglob('*.py'))
        for offender in _queue_reads_outside_the_pump_seam(source_path)
    ]

    assert offenders == []


def test_pump_seam_scan_finds_a_read(tmp_path):
    """The scan above does report a read outside the seam (it is not vacuous)."""
    source_path = tmp_path / 'reader.py'
    source_path.write_text(
        'import pygame\n\n\ndef pump_events():\n    return pygame.event.get()\n\n\n'
        'def elsewhere():\n    return pygame.event.poll()\n',
        encoding='utf-8',
    )

    assert _queue_reads_outside_the_pump_seam(source_path) == [f'{source_path}:9 pygame.event.poll']
