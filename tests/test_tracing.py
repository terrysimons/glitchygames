"""Tests for the sprite trace format (glitchygames/tracing.py).

Traces are gzip-compressed JSON Lines: a header line, then one line per frame. Frame 0 and
every frame whose scene differs from the previous frame are keyframes holding every sprite;
every other frame holds only the changes against the previous frame. In memory a trace is
always the full per-frame sprite lists.
"""

from __future__ import annotations

import copy
import dataclasses
import gzip
import json
import types
from typing import TYPE_CHECKING, Any, cast

import pygame
import pytest

from glitchygames.tracing import (
    TRACE_FORMAT_VERSION,
    StableSpriteIds,
    TraceFormatError,
    TraceReader,
    TraceWriter,
    decode_frame,
    encode_frame,
    read_trace,
    read_trace_result,
    sample_scene_frame,
    write_trace,
)

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.scenes import Scene


def _sprite(sprite_id: str, rect: list[float], *, visible: bool = True) -> dict[str, Any]:
    return {'id': sprite_id, 'rect': rect, 'visible': visible}


def _frame(
    frame_number: int, *sprites: dict[str, Any], scene: str | None = 'Level'
) -> dict[str, Any]:
    return {'frame': frame_number, 'scene': scene, 'sprites': list(sprites)}


def _trace(*frames: dict[str, Any]) -> dict[str, Any]:
    return {'game': 'example', 'frame_seconds': 1.0 / 60.0, 'frames': list(frames)}


def _lines(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, 'rt', encoding='utf-8') as trace_file:
        return [json.loads(line) for line in trace_file]


BALL = _sprite('Ball#0', [10, 20, 4, 4])
WALL = _sprite('Wall#0', [0, 0, 8, 100])


class TestEncodeFrame:
    """One frame's line: a keyframe or the changes against the previous frame."""

    def test_first_frame_is_a_keyframe(self):
        frame = _frame(0, BALL, WALL)
        assert encode_frame(frame_record=frame, previous_frame_record=None) == {
            'frame': 0,
            'kind': 'keyframe',
            'scene': 'Level',
            'sprites': [BALL, WALL],
        }

    def test_unchanged_frame_encodes_to_no_changes(self):
        encoded = encode_frame(
            frame_record=_frame(1, BALL, WALL), previous_frame_record=_frame(0, BALL, WALL)
        )
        assert encoded == {'frame': 1, 'kind': 'delta'}

    def test_moved_sprite_records_only_its_integer_rect_delta(self):
        """A changed sprite carries only the fields that changed; an int rect as a delta."""
        moved_ball = _sprite('Ball#0', [11, 18, 4, 5])
        encoded = encode_frame(
            frame_record=_frame(1, moved_ball, WALL), previous_frame_record=_frame(0, BALL, WALL)
        )
        assert encoded == {
            'frame': 1,
            'kind': 'delta',
            'changed': [{'id': 'Ball#0', 'rect_delta': [1, -2, 0, 1]}],
        }

    def test_visibility_toggle_records_only_visible(self):
        hidden_wall = _sprite('Wall#0', [0, 0, 8, 100], visible=False)
        encoded = encode_frame(
            frame_record=_frame(1, BALL, hidden_wall), previous_frame_record=_frame(0, BALL, WALL)
        )
        assert encoded == {
            'frame': 1,
            'kind': 'delta',
            'changed': [{'id': 'Wall#0', 'visible': False}],
        }

    def test_moved_and_toggled_sprite_records_both(self):
        changed_ball = _sprite('Ball#0', [10, 21, 4, 4], visible=False)
        encoded = encode_frame(
            frame_record=_frame(1, changed_ball), previous_frame_record=_frame(0, BALL)
        )
        assert encoded['changed'] == [
            {'id': 'Ball#0', 'rect_delta': [0, 1, 0, 0], 'visible': False}
        ]

    def test_non_integer_rect_is_recorded_whole(self):
        """Float subtraction does not always add back exactly, so only ints become deltas."""
        float_ball = _sprite('Ball#0', [10.1, 20, 4, 4])
        encoded = encode_frame(
            frame_record=_frame(1, float_ball), previous_frame_record=_frame(0, BALL)
        )
        assert encoded['changed'] == [{'id': 'Ball#0', 'rect': [10.1, 20, 4, 4]}]

    def test_sprite_whose_fields_change_is_rejected(self):
        ball_with_layer = {**BALL, 'layer': 2}
        with pytest.raises(TraceFormatError, match='Ball#0'):
            encode_frame(
                frame_record=_frame(1, ball_with_layer), previous_frame_record=_frame(0, BALL)
            )

    def test_added_and_removed_sprites(self):
        coin = _sprite('Coin#0', [5, 5, 2, 2])
        encoded = encode_frame(
            frame_record=_frame(1, BALL, coin), previous_frame_record=_frame(0, BALL, WALL)
        )
        assert encoded == {'frame': 1, 'kind': 'delta', 'added': [coin], 'removed': ['Wall#0']}

    def test_scene_change_writes_a_keyframe(self):
        encoded = encode_frame(
            frame_record=_frame(1, BALL, scene='PauseScene'),
            previous_frame_record=_frame(0, BALL),
        )
        assert encoded == {
            'frame': 1,
            'kind': 'keyframe',
            'scene': 'PauseScene',
            'sprites': [BALL],
        }

    def test_reordered_sprites_record_the_new_order(self):
        """Draw order is kept: a frame whose order differs carries the full id order."""
        encoded = encode_frame(
            frame_record=_frame(1, WALL, BALL), previous_frame_record=_frame(0, BALL, WALL)
        )
        assert encoded == {'frame': 1, 'kind': 'delta', 'order': ['Wall#0', 'Ball#0']}

    def test_sprite_added_before_existing_ones_records_the_order(self):
        coin = _sprite('Coin#0', [5, 5, 2, 2])
        encoded = encode_frame(
            frame_record=_frame(1, coin, BALL), previous_frame_record=_frame(0, BALL)
        )
        assert encoded == {
            'frame': 1,
            'kind': 'delta',
            'added': [coin],
            'order': ['Coin#0', 'Ball#0'],
        }

    def test_extra_frame_fields_pass_through(self):
        """Fields other than scene and sprites (a recording's dt, events) are kept verbatim."""
        frame = {**_frame(1, BALL), 'dt': 0.016, 'events': [{'type': 'KEYDOWN'}]}
        encoded = encode_frame(frame_record=frame, previous_frame_record=_frame(0, BALL))
        assert encoded == {
            'frame': 1,
            'kind': 'delta',
            'dt': 0.016,
            'events': [{'type': 'KEYDOWN'}],
        }

    def test_duplicate_sprite_ids_are_rejected(self):
        with pytest.raises(TraceFormatError, match='Ball#0'):
            encode_frame(frame_record=_frame(0, BALL, BALL), previous_frame_record=None)

    def test_reserved_field_names_are_rejected(self):
        frame = {**_frame(0, BALL), 'changed': []}
        with pytest.raises(TraceFormatError, match='changed'):
            encode_frame(frame_record=frame, previous_frame_record=None)

    def test_int_to_float_in_a_rect_is_a_change(self):
        """5 == 5.0 in Python, but the trace must give back the new type."""
        float_ball = _sprite('Ball#0', [10.0, 20, 4, 4])
        encoded = encode_frame(
            frame_record=_frame(1, float_ball), previous_frame_record=_frame(0, BALL)
        )
        assert encoded['changed'] == [{'id': 'Ball#0', 'rect': [10.0, 20, 4, 4]}]

    def test_bool_to_int_visibility_is_a_change(self):
        """True == 1 in Python, but the trace must give back the new type."""
        integer_visible_ball = {**BALL, 'visible': 1}
        encoded = encode_frame(
            frame_record=_frame(1, integer_visible_ball), previous_frame_record=_frame(0, BALL)
        )
        assert encoded['changed'] == [{'id': 'Ball#0', 'visible': 1}]


class TestDecodeFrame:
    """Decoding rebuilds the full frame from a line and the previous frame."""

    @pytest.mark.parametrize(
        ('previous_frame', 'frame'),
        [
            (None, _frame(0, BALL, WALL)),
            (_frame(0, BALL, WALL), _frame(1, BALL, WALL)),
            (_frame(0, BALL, WALL), _frame(1, _sprite('Ball#0', [11, 20, 4, 4]), WALL)),
            (_frame(0, BALL), _frame(1, _sprite('Ball#0', [9, 25, 4, 3], visible=False))),
            (_frame(0, BALL), _frame(1, _sprite('Ball#0', [10.5, 20, 4, 4]))),
            (_frame(0, BALL), _frame(1, _sprite('Coin#0', [5, 5, 2, 2]), BALL)),
            (_frame(0, BALL, WALL), _frame(1, WALL)),
            (_frame(0, BALL, WALL), _frame(1, WALL, BALL)),
            (_frame(0, BALL), _frame(1, BALL, scene='PauseScene')),
            (_frame(0, BALL), _frame(1, scene=None)),
        ],
    )
    def test_decode_inverts_encode(self, previous_frame, frame):
        line = encode_frame(frame_record=frame, previous_frame_record=previous_frame)
        decoded = decode_frame(line_record=line, previous_frame_record=previous_frame)
        assert decoded == frame
        assert list(decoded) == list(frame)

    def test_decode_does_not_share_or_change_the_previous_frame(self):
        previous_frame = _frame(0, BALL, WALL)
        previous_copy = copy.deepcopy(previous_frame)
        frame = _frame(1, _sprite('Ball#0', [11, 20, 4, 4]))
        line = encode_frame(frame_record=frame, previous_frame_record=previous_frame)
        decoded = decode_frame(line_record=line, previous_frame_record=previous_frame)
        assert previous_frame == previous_copy
        decoded['sprites'].clear()
        assert previous_frame == previous_copy

    def test_delta_without_a_previous_frame_is_rejected(self):
        with pytest.raises(TraceFormatError, match='delta'):
            decode_frame(line_record={'frame': 0, 'kind': 'delta'}, previous_frame_record=None)

    def test_change_to_an_unknown_sprite_is_rejected(self):
        line = {'frame': 1, 'kind': 'delta', 'changed': [_sprite('Coin#0', [0, 0, 1, 1])]}
        with pytest.raises(TraceFormatError, match='Coin#0'):
            decode_frame(line_record=line, previous_frame_record=_frame(0, BALL))

    def test_unknown_line_kind_is_rejected(self):
        with pytest.raises(TraceFormatError, match='sideways'):
            decode_frame(line_record={'frame': 0, 'kind': 'sideways'}, previous_frame_record=None)


class TestTraceFiles:
    """Whole traces on disk: header line, frame lines, determinism, versioning, truncation."""

    @staticmethod
    def _example_trace() -> dict[str, Any]:
        coin = _sprite('Coin#0', [5, 5, 2, 2])
        return _trace(
            _frame(0, BALL, WALL),
            _frame(1, BALL, WALL),
            _frame(2, _sprite('Ball#0', [11, 20, 4, 4]), WALL, coin),
            _frame(3, _sprite('Ball#0', [11, 20, 4, 4]), coin),
            _frame(4, BALL, scene='PauseScene'),
            _frame(5, BALL, scene='PauseScene'),
        )

    def test_round_trip_gives_every_frame_back(self, tmp_path):
        trace = self._example_trace()
        path = tmp_path / 'trace.jsonl.gz'
        write_trace(trace, path=path)
        assert read_trace(path=path) == trace

    def test_file_is_header_then_one_line_per_frame(self, tmp_path):
        path = tmp_path / 'trace.jsonl.gz'
        write_trace(self._example_trace(), path=path)
        lines = _lines(path)
        assert lines[0] == {
            'format_version': TRACE_FORMAT_VERSION,
            'game': 'example',
            'frame_seconds': 1.0 / 60.0,
        }
        assert [line['kind'] for line in lines[1:]] == [
            'keyframe',
            'delta',
            'delta',
            'delta',
            'keyframe',
            'delta',
        ]

    def test_writing_twice_gives_identical_bytes(self, tmp_path):
        first_path = tmp_path / 'first.jsonl.gz'
        second_path = tmp_path / 'second.jsonl.gz'
        write_trace(self._example_trace(), path=first_path)
        write_trace(self._example_trace(), path=second_path)
        assert first_path.read_bytes() == second_path.read_bytes()

    def test_gzip_header_has_no_time_or_file_name(self, tmp_path):
        path = tmp_path / 'trace.jsonl.gz'
        write_trace(self._example_trace(), path=path)
        header_bytes = path.read_bytes()[:10]
        flags = header_bytes[3]
        modification_time = int.from_bytes(header_bytes[4:8], 'little')
        file_name_flag = 0x08
        assert flags & file_name_flag == 0
        assert modification_time == 0

    def test_unknown_format_version_is_rejected(self, tmp_path):
        path = tmp_path / 'future.jsonl.gz'
        with gzip.open(path, 'wt', encoding='utf-8') as trace_file:
            trace_file.write('{"format_version":99,"game":"example"}\n')
        with pytest.raises(TraceFormatError, match='format_version 99'):
            read_trace(path=path)

    def test_format_version_1_document_is_rejected_clearly(self, tmp_path):
        """The old single-document format's first line is not a JSON object on its own."""
        path = tmp_path / 'old.json.gz'
        with gzip.open(path, 'wt', encoding='utf-8') as trace_file:
            trace_file.write('{"game":"example","frame_seconds":0.016,"frames":[\n]}\n')
        with pytest.raises(TraceFormatError, match='header'):
            read_trace(path=path)

    def test_empty_file_is_rejected(self, tmp_path):
        path = tmp_path / 'empty.jsonl.gz'
        with gzip.open(path, 'wt', encoding='utf-8'):
            pass
        with pytest.raises(TraceFormatError, match='header'):
            read_trace(path=path)

    def test_complete_file_reports_nothing_dropped(self, tmp_path):
        path = tmp_path / 'trace.jsonl.gz'
        write_trace(self._example_trace(), path=path)
        result = read_trace_result(path=path)
        assert result.dropped_partial_line is None
        assert result.is_complete is True

    def test_truncated_final_line_is_dropped_and_reported(self, tmp_path):
        """A recording cut off mid-line keeps every complete frame."""
        trace = self._example_trace()
        path = tmp_path / 'cut.jsonl.gz'
        write_trace(trace, path=path)
        text = gzip.decompress(path.read_bytes()).decode('utf-8')
        cut_text = text[: text.rindex('\n', 0, len(text) - 1) + 12]
        path.write_bytes(gzip.compress(cut_text.encode('utf-8'), mtime=0))
        result = read_trace_result(path=path)
        assert result.trace['frames'] == trace['frames'][:-1]
        assert result.dropped_partial_line == cut_text[cut_text.rindex('\n') + 1 :]
        assert result.dropped_partial_line

    def test_read_trace_logs_the_dropped_line(self, tmp_path, caplog):
        path = tmp_path / 'cut.jsonl.gz'
        write_trace(self._example_trace(), path=path)
        text = gzip.decompress(path.read_bytes()).decode('utf-8')
        path.write_bytes(gzip.compress(text[:-5].encode('utf-8'), mtime=0))
        with caplog.at_level('WARNING', logger='glitchygames.tracing'):
            trace = read_trace(path=path)
        assert len(trace['frames']) == len(self._example_trace()['frames']) - 1
        assert 'cut.jsonl.gz' in caplog.text
        assert 'partial' in caplog.text

    def test_corrupt_line_before_the_last_is_an_error(self, tmp_path):
        path = tmp_path / 'corrupt.jsonl.gz'
        write_trace(self._example_trace(), path=path)
        lines = gzip.decompress(path.read_bytes()).decode('utf-8').split('\n')
        lines[2] = lines[2][:-3]
        path.write_bytes(gzip.compress('\n'.join(lines).encode('utf-8'), mtime=0))
        with pytest.raises(TraceFormatError, match='line 3'):
            read_trace(path=path)

    def test_header_may_not_set_reserved_fields(self, tmp_path):
        with pytest.raises(TraceFormatError, match='format_version'):
            TraceWriter(path=tmp_path / 'trace.jsonl.gz', header={'format_version': 1})


class TestTypeChangesRoundTrip:
    """A value that changes only its JSON type reads back with the new type."""

    @pytest.mark.parametrize(
        ('field', 'previous_value', 'current_value'),
        [('rect', [5, 20, 4, 4], [5.0, 20, 4, 4]), ('visible', True, 1)],
    )
    def test_new_type_survives_a_file_round_trip(
        self, tmp_path, field, previous_value, current_value
    ):
        previous_sprite = {'id': 'Ball#0', 'rect': [5, 20, 4, 4], 'visible': True}
        previous_sprite[field] = previous_value
        current_sprite = {**previous_sprite, field: current_value}
        path = tmp_path / 'types.jsonl.gz'
        write_trace(_trace(_frame(0, previous_sprite), _frame(1, current_sprite)), path=path)

        frames = read_trace(path=path)['frames']

        assert frames[1]['sprites'][0][field] == current_value
        read_back = frames[1]['sprites'][0][field]
        if field == 'rect':
            assert [type(component) for component in read_back] == [float, int, int, int]
        else:
            assert type(read_back) is int
        assert type(frames[0]['sprites'][0]['visible']) is bool


class TestMalformedLines:
    """Damaged records raise TraceFormatError naming the frame, never a bare Python error."""

    @pytest.mark.parametrize(
        'line_record',
        [
            {'frame': 1, 'kind': 'delta', 'changed': [{'id': 'Ball#0', 'rect_delta': [1, 2]}]},
            {'frame': 1, 'kind': 'delta', 'changed': [{'rect_delta': [1, 0, 0, 0]}]},
            {'frame': 1, 'kind': 'delta', 'changed': ['Ball#0']},
            {'frame': 1, 'kind': 'delta', 'removed': 7},
            {'frame': 1, 'kind': 'delta', 'added': [['Coin#0']]},
            {'frame': 1, 'kind': 'delta', 'order': 'Ball#0'},
            {'frame': 1, 'kind': 'keyframe', 'scene': 'Level', 'sprites': None},
            {'frame': 1, 'kind': 'keyframe', 'sprites': []},
        ],
        ids=[
            'short-rect-delta',
            'change-without-id',
            'change-not-an-object',
            'removed-not-a-list',
            'added-sprite-not-an-object',
            'order-not-a-list',
            'keyframe-sprites-null',
            'keyframe-without-scene',
        ],
    )
    def test_damaged_record_raises_trace_format_error(self, line_record):
        with pytest.raises(TraceFormatError, match='Frame 1'):
            decode_frame(line_record=line_record, previous_frame_record=_frame(0, BALL))

    def test_damaged_line_in_a_file_names_the_line_and_frame(self, tmp_path):
        path = tmp_path / 'damaged.jsonl.gz'
        lines = [
            '{"format_version":2,"game":"example"}',
            json.dumps(encode_frame(frame_record=_frame(0, BALL), previous_frame_record=None)),
            '{"frame":1,"kind":"delta","changed":[{"id":"Ball#0","rect_delta":[1]}]}',
        ]
        path.write_bytes(gzip.compress(('\n'.join(lines) + '\n').encode('utf-8'), mtime=0))
        with pytest.raises(TraceFormatError, match=r'line 3.*Frame 1'):
            read_trace(path=path)


class TestTraceReader:
    """Streaming reads: one frame at a time, header first, truncation reported at the end."""

    @staticmethod
    def _moving_trace(*, frame_count: int) -> dict[str, Any]:
        return _trace(*[
            _frame(
                frame_number,
                _sprite('Ball#0', [frame_number * 7 % 800, frame_number * 13 % 480, 4, 4]),
                WALL,
            )
            for frame_number in range(frame_count)
        ])

    def test_header_and_frames_match_read_trace(self, tmp_path):
        trace = self._moving_trace(frame_count=50)
        path = tmp_path / 'trace.jsonl.gz'
        write_trace(trace, path=path)
        with TraceReader(path=path) as reader:
            assert reader.header == {'game': 'example', 'frame_seconds': 1.0 / 60.0}
            frames = list(reader)
        assert frames == trace['frames']
        assert reader.dropped_partial_line is None
        assert reader.is_complete is True

    def test_yields_frames_before_the_file_is_fully_read(self, tmp_path):
        """Frames come one at a time: the first arrives while most of the file is unread."""
        path = tmp_path / 'long.jsonl.gz'
        write_trace(self._moving_trace(frame_count=2000), path=path)
        file_size = path.stat().st_size
        with TraceReader(path=path, chunk_bytes=64) as reader:
            frame_iterator = iter(reader)
            first_frame = next(frame_iterator)
            assert first_frame['frame'] == 0
            assert reader.bytes_read < file_size // 4
            remaining_frame_count = sum(1 for _ in frame_iterator)
        assert remaining_frame_count == 1999
        assert reader.bytes_read == file_size

    def test_yielded_frames_are_independent(self, tmp_path):
        """Changing a yielded frame cannot change the frames that follow it."""
        trace = self._moving_trace(frame_count=3)
        path = tmp_path / 'trace.jsonl.gz'
        write_trace(trace, path=path)
        frames = []
        with TraceReader(path=path) as reader:
            for frame in reader:
                frames.append(frame)
                frame['sprites'][1]['rect'][0] = -1
                frame['sprites'].reverse()
        assert [frame['sprites'][0]['id'] for frame in frames] == ['Wall#0'] * 3
        assert [frame['sprites'][1]['rect'] for frame in frames] == [
            sprite['rect'] for sprite in (frame['sprites'][0] for frame in trace['frames'])
        ]

    def test_truncated_file_reports_the_partial_line_after_iteration(self, tmp_path):
        trace = self._moving_trace(frame_count=5)
        path = tmp_path / 'cut.jsonl.gz'
        write_trace(trace, path=path)
        text = gzip.decompress(path.read_bytes()).decode('utf-8')
        path.write_bytes(gzip.compress(text[:-4].encode('utf-8'), mtime=0))
        with TraceReader(path=path) as reader:
            frames = list(reader)
        assert frames == trace['frames'][:-1]
        assert reader.dropped_partial_line == text[:-4][text[:-4].rindex('\n') + 1 :]

    def test_unclosed_writer_file_reads_as_incomplete(self, tmp_path):
        path = tmp_path / 'live.jsonl.gz'
        writer = TraceWriter(path=path, header={'source': 'recording'})
        writer.write_frame(_frame(0, BALL))
        with TraceReader(path=path) as reader:
            assert list(reader) == [_frame(0, BALL)]
        assert reader.is_complete is False
        writer.close()

    def test_frames_can_be_iterated_only_once(self, tmp_path):
        path = tmp_path / 'trace.jsonl.gz'
        write_trace(self._moving_trace(frame_count=2), path=path)
        with TraceReader(path=path) as reader:
            list(reader)
            with pytest.raises(ValueError, match='once'):
                list(reader)

    def test_unknown_format_version_is_rejected_on_open(self, tmp_path):
        path = tmp_path / 'future.jsonl.gz'
        path.write_bytes(gzip.compress(b'{"format_version":3}\n', mtime=0))
        with pytest.raises(TraceFormatError, match='format_version 3'):
            TraceReader(path=path)


class TestTraceWriter:
    """Streaming writes: every frame is readable as soon as write_frame returns."""

    @pytest.mark.parametrize('reserved_field', ['kind', 'changed', 'added', 'removed', 'order'])
    def test_write_frame_rejects_reserved_frame_fields(self, tmp_path, reserved_field):
        with TraceWriter(path=tmp_path / 'trace.jsonl.gz', header={}) as writer:
            with pytest.raises(TraceFormatError, match=rf'reserved.*{reserved_field}'):
                writer.write_frame({**_frame(0, BALL), reserved_field: 'data'})
            assert writer.frame_count == 0

    def test_streamed_frames_read_back_without_close(self, tmp_path):
        """A crashed recorder (close never called) leaves every written frame readable."""
        path = tmp_path / 'live.jsonl.gz'
        writer = TraceWriter(path=path, header={'source': 'recording', 'frame_seconds': None})
        frames = [_frame(0, BALL), _frame(1, _sprite('Ball#0', [12, 20, 4, 4]))]
        for frame in frames:
            writer.write_frame(frame)
        result = read_trace_result(path=path)
        assert result.trace == {'source': 'recording', 'frame_seconds': None, 'frames': frames}
        assert result.is_complete is False
        assert result.dropped_partial_line is None
        writer.close()
        assert read_trace_result(path=path).is_complete is True

    def test_context_manager_closes_and_counts_frames(self, tmp_path):
        path = tmp_path / 'trace.jsonl.gz'
        with TraceWriter(path=path, header={'game': 'example'}) as writer:
            writer.write_frame(_frame(0, BALL))
            writer.write_frame(_frame(1, BALL))
        assert writer.frame_count == 2
        assert read_trace_result(path=path).is_complete is True

    def test_write_after_close_is_an_error(self, tmp_path):
        writer = TraceWriter(path=tmp_path / 'trace.jsonl.gz', header={})
        writer.close()
        with pytest.raises(ValueError, match='closed'):
            writer.write_frame(_frame(0, BALL))

    def test_writer_keeps_its_own_copy_of_the_previous_frame(self, tmp_path):
        """A caller that mutates a frame after writing it cannot corrupt the next delta."""
        path = tmp_path / 'trace.jsonl.gz'
        frame = _frame(0, _sprite('Ball#0', [10, 20, 4, 4]))
        with TraceWriter(path=path, header={}) as writer:
            writer.write_frame(frame)
            frame['sprites'][0]['rect'][0] = 99
            frame['frame'] = 1
            writer.write_frame(frame)
        frames = read_trace(path=path)['frames']
        assert frames[0]['sprites'][0]['rect'] == [10, 20, 4, 4]
        assert frames[1]['sprites'][0]['rect'] == [99, 20, 4, 4]

    def test_force_keyframe_writes_a_keyframe_for_an_unchanged_scene_name(self, tmp_path):
        """A forced keyframe holds every sprite and decodes like the delta would have."""
        path = tmp_path / 'trace.jsonl.gz'
        frames = [
            _frame(0, BALL),
            _frame(1, _sprite('Ball#0', [11, 20, 4, 4])),
            _frame(2, _sprite('Ball#1', [0, 0, 4, 4])),
        ]
        with TraceWriter(path=path, header={}) as writer:
            writer.write_frame(frames[0])
            writer.write_frame(frames[1])
            writer.write_frame(frames[2], force_keyframe=True)
        assert [line['kind'] for line in _lines(path)[1:]] == ['keyframe', 'delta', 'keyframe']
        assert read_trace(path=path)['frames'] == frames


class TestStableSpriteIds:
    """Sprite ids count each class in order of first appearance and never renumber."""

    def test_ids_survive_removal_of_an_earlier_sprite(self):
        class Coin:
            pass

        first_coin, second_coin, third_coin = Coin(), Coin(), Coin()
        sprite_ids = StableSpriteIds()
        assert [sprite_ids.id_for(coin) for coin in (first_coin, second_coin)] == [
            'Coin#0',
            'Coin#1',
        ]
        # The first coin is collected: the second keeps its id and a new coin gets the next one
        assert sprite_ids.id_for(second_coin) == 'Coin#1'
        assert sprite_ids.id_for(third_coin) == 'Coin#2'
        assert sprite_ids.id_for(first_coin) == 'Coin#0'


@dataclasses.dataclass
class LevelScene:
    """A stand-in scene: sample_scene_frame reads only all_sprites and the class name."""

    all_sprites: types.SimpleNamespace


def _scene_with(*sprites: types.SimpleNamespace) -> LevelScene:
    sprite_list = list(sprites)
    return LevelScene(all_sprites=types.SimpleNamespace(sprites=lambda: list(sprite_list)))


class TestSampleSceneFrame:
    """A frame record lists every sprite in the scene's all_sprites, in group order."""

    def test_records_id_rect_and_visibility_in_order(self):
        player = types.SimpleNamespace(rect=pygame.Rect(1, 2, 3, 4), visible=1)
        hidden = types.SimpleNamespace(rect=pygame.Rect(5, 6, 7, 8), visible=0)
        scene = _scene_with(player, hidden)
        frame = sample_scene_frame(
            frame_number=7,
            scene=cast('Scene', scene),
            sprite_ids=StableSpriteIds(),
        )
        assert frame == {
            'frame': 7,
            'scene': 'LevelScene',
            'sprites': [
                {'id': 'SimpleNamespace#0', 'rect': [1, 2, 3, 4], 'visible': True},
                {'id': 'SimpleNamespace#1', 'rect': [5, 6, 7, 8], 'visible': False},
            ],
        }

    def test_no_active_scene_records_no_sprites(self):
        frame = sample_scene_frame(frame_number=0, scene=None, sprite_ids=StableSpriteIds())
        assert frame == {'frame': 0, 'scene': None, 'sprites': []}
