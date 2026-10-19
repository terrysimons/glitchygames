"""Golden traces: every game plays exactly as it did before the engine world-space change.

The baselines in ``tests/world/golden/`` were recorded by ``scripts/record_golden_traces.py``
before any world-space engine change (plans/2026-10-18-engine-world-space.md). Each test
replays the same scripted, deterministic run and compares every sprite's rect and visibility,
frame by frame.

A difference fails the test unless an entry in ``EXPECTED_DIFFERENCES`` explains it: same
field, frame inside the entry's range, sprite id matching its pattern, and either the current
value equal to the entry's pinned ``expected`` value or the entry's ``rule`` accepting the
(baseline, current) pair. An entry that explains no difference also fails, so the list cannot
go stale.
"""

from __future__ import annotations

import copy
import dataclasses
import fnmatch
import gzip
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from scripts.record_golden_traces import GAME_SCENES, golden_path, record_trace

from glitchygames.tracing import TraceReader, decode_frame, read_trace, write_trace

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# Marks an ExpectedDifference without a pinned value (None is a real value, so it can't be used)
NO_EXPECTED_VALUE: Any = object()
MISSING_EXPECTATION_MESSAGE = 'An ExpectedDifference needs an expected value or a rule'
# The seeded-reproducibility test: --random-seed value and frames per run
SEEDED_TRACE_SEED = 123
SEEDED_TRACE_FRAME_COUNT = 120


@dataclass(frozen=True)
class ExpectedDifference:
    """Justified differences between a baseline trace and the current run.

    An entry explains a difference when the field is the same, the frame is in ``frames``, the
    sprite id matches ``sprite_pattern`` (fnmatch, e.g. ``'GroundSegment#*'``; ``''`` matches
    frame-level fields), and either the current value equals ``expected`` or ``rule`` returns
    True for (baseline value, current value).

    Attributes:
        frames: The frames the entry covers (``range(n, n + 1)`` for one frame).
        sprite_pattern: fnmatch pattern for sprite ids (``<ClassName>#<n>``).
        field: ``'rect'`` (list), ``'visible'`` (bool) or ``'present'`` (bool: is the sprite
            in the current run) for a sprite; ``'scene'`` or ``'frame_count'`` for the frame
            or the whole trace.
        reason: Why the difference is expected.
        expected: The value the current run must now produce.
        rule: Accepts (baseline value, current value) for a systematic difference.

    """

    frames: range
    sprite_pattern: str
    field: str
    reason: str
    expected: Any = NO_EXPECTED_VALUE
    rule: Callable[[Any, Any], bool] | None = dataclasses.field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Reject an entry that would explain any value.

        Raises:
            ValueError: If neither an expected value nor a rule is given.

        """
        if self.expected is NO_EXPECTED_VALUE and self.rule is None:
            raise ValueError(MISSING_EXPECTATION_MESSAGE)

    def explains(self, difference: TraceDifference) -> bool:
        """Report whether this entry explains a difference.

        Args:
            difference: A difference found between the traces.

        Returns:
            True if the difference matches this entry.

        """
        if (
            difference.field != self.field
            or difference.frame not in self.frames
            or not fnmatch.fnmatchcase(difference.sprite_id, self.sprite_pattern)
        ):
            return False
        if self.expected is not NO_EXPECTED_VALUE and difference.current == self.expected:
            return True
        return self.rule is not None and self.rule(difference.baseline, difference.current)


@dataclass(frozen=True)
class TraceDifference:
    """A difference found between the baseline and the current run.

    Attributes:
        frame: The frame number.
        sprite_id: The sprite id, or ``''`` for a frame-level field.
        field: Which field differs.
        baseline: The baseline value.
        current: The current value.

    """

    frame: int
    sprite_id: str
    field: str
    baseline: Any
    current: Any

    @property
    def key(self) -> tuple[int, str, str]:
        """The (frame, sprite id, field) that identifies this difference."""
        return (self.frame, self.sprite_id, self.field)


# Filled in by later tasks of the world-space plan; every entry must say why it is expected.
EXPECTED_DIFFERENCES: dict[str, list[ExpectedDifference]] = {
    'clockwork_keep': [],
    'brave_adventurer': [],
    'brave_adventurer_papyrus': [],
    'paddleslap': [],
}


def _sprite_fields(frame: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        sprite['id']: {'rect': sprite['rect'], 'visible': sprite['visible']}
        for sprite in frame['sprites']
    }


def _frame_differences(
    *, baseline_frame: dict[str, Any], current_frame: dict[str, Any]
) -> list[TraceDifference]:
    frame_number = baseline_frame['frame']
    differences: list[TraceDifference] = []
    if baseline_frame['scene'] != current_frame['scene']:
        differences.append(
            TraceDifference(
                frame=frame_number,
                sprite_id='',
                field='scene',
                baseline=baseline_frame['scene'],
                current=current_frame['scene'],
            )
        )
    baseline_sprites = _sprite_fields(baseline_frame)
    current_sprites = _sprite_fields(current_frame)
    # Baseline order first, then sprites only the current run has
    sprite_ids = list(baseline_sprites) + [
        sprite_id for sprite_id in current_sprites if sprite_id not in baseline_sprites
    ]
    for sprite_id in sprite_ids:
        baseline_sprite = baseline_sprites.get(sprite_id)
        current_sprite = current_sprites.get(sprite_id)
        if baseline_sprite is None or current_sprite is None:
            differences.append(
                TraceDifference(
                    frame=frame_number,
                    sprite_id=sprite_id,
                    field='present',
                    baseline=baseline_sprite is not None,
                    current=current_sprite is not None,
                )
            )
            continue
        differences.extend(
            TraceDifference(
                frame=frame_number,
                sprite_id=sprite_id,
                field=field_name,
                baseline=baseline_sprite[field_name],
                current=current_sprite[field_name],
            )
            for field_name in ('rect', 'visible')
            if baseline_sprite[field_name] != current_sprite[field_name]
        )
    return differences


def trace_differences(
    *, baseline: dict[str, Any], current: dict[str, Any]
) -> list[TraceDifference]:
    """Compare two traces frame by frame.

    Args:
        baseline: The recorded golden trace.
        current: The trace of the current run.

    Returns:
        Every difference, in frame order.

    """
    differences: list[TraceDifference] = []
    baseline_frames = baseline['frames']
    current_frames = current['frames']
    if len(baseline_frames) != len(current_frames):
        differences.append(
            TraceDifference(
                frame=min(len(baseline_frames), len(current_frames)),
                sprite_id='',
                field='frame_count',
                baseline=len(baseline_frames),
                current=len(current_frames),
            )
        )
    for baseline_frame, current_frame in zip(baseline_frames, current_frames, strict=False):
        differences.extend(
            _frame_differences(baseline_frame=baseline_frame, current_frame=current_frame)
        )
    return differences


def unexplained_and_stale(
    *, differences: list[TraceDifference], expected: list[ExpectedDifference]
) -> tuple[list[TraceDifference], list[ExpectedDifference]]:
    """Split differences into unexplained ones and expected ones that did not occur.

    Args:
        differences: The differences found.
        expected: The listed, justified differences.

    Returns:
        (differences not listed, listed differences that no longer occur).

    """
    used_entries: set[int] = set()
    unexplained: list[TraceDifference] = []
    for difference in differences:
        explaining_entries = [
            entry_index for entry_index, entry in enumerate(expected) if entry.explains(difference)
        ]
        if explaining_entries:
            used_entries.update(explaining_entries)
        else:
            unexplained.append(difference)
    stale = [entry for entry_index, entry in enumerate(expected) if entry_index not in used_entries]
    return unexplained, stale


def _describe(difference: TraceDifference) -> str:
    return (
        f'frame {difference.frame}, sprite {difference.sprite_id or "(frame)"}, '
        f'{difference.field}: baseline {difference.baseline!r}, current {difference.current!r}'
    )


def test_expected_differences_cover_every_game():
    """Every recorded game has an entry, so a new game cannot slip past the list."""
    assert set(EXPECTED_DIFFERENCES) == set(GAME_SCENES)


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_game_matches_golden_trace(game_key):
    """Replaying the game's script reproduces its golden trace, up to listed differences."""
    baseline = read_trace(path=golden_path(game_key))
    current = record_trace(game_key, frame_count=len(baseline['frames']))

    assert current['game'] == baseline['game']
    assert current['frame_seconds'] == baseline['frame_seconds']
    unexplained, stale = unexplained_and_stale(
        differences=trace_differences(baseline=baseline, current=current),
        expected=EXPECTED_DIFFERENCES[game_key],
    )
    if unexplained:
        pytest.fail(
            f'{game_key}: {len(unexplained)} unexpected difference(s); first at '
            f'{_describe(unexplained[0])}',
            pytrace=False,
        )
    if stale:
        pytest.fail(
            f'{game_key}: {len(stale)} expected difference(s) no longer occur; first: {stale[0]}',
            pytrace=False,
        )


def test_same_random_seed_gives_identical_paddleslap_traces():
    """--random-seed 123 twice plays PaddleSlap identically; seed 124 plays differently.

    Every random draw (serves, spawn positions, colours, shakes) comes from the run's seeded
    streams, so the harness needs no patching of the games' randomness.
    """
    first_run = record_trace(
        'paddleslap', frame_count=SEEDED_TRACE_FRAME_COUNT, random_seed=SEEDED_TRACE_SEED
    )
    second_run = record_trace(
        'paddleslap', frame_count=SEEDED_TRACE_FRAME_COUNT, random_seed=SEEDED_TRACE_SEED
    )
    other_seed_run = record_trace(
        'paddleslap', frame_count=SEEDED_TRACE_FRAME_COUNT, random_seed=SEEDED_TRACE_SEED + 1
    )

    assert second_run == first_run
    assert trace_differences(baseline=first_run, current=other_seed_run) != []


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_committed_trace_reencodes_to_identical_bytes(game_key, tmp_path):
    """Decoding then encoding a committed trace gives back every frame and the same bytes."""
    path = golden_path(game_key)
    baseline = read_trace(path=path)
    reencoded_path = tmp_path / path.name
    write_trace(baseline, path=reencoded_path)

    assert read_trace(path=reencoded_path) == baseline
    assert reencoded_path.read_bytes() == path.read_bytes()


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_streaming_reader_matches_read_trace_and_frame_by_frame_decoding(game_key):
    """TraceReader, read_trace and decode_frame chained by hand give the same frames."""
    path = golden_path(game_key)
    trace = read_trace(path=path)
    with TraceReader(path=path) as reader:
        streamed_frames = list(reader)
        streamed_header = reader.header

    assert streamed_frames == trace['frames']
    assert {**streamed_header, 'frames': streamed_frames} == trace
    previous_frame = None
    for line_record, streamed_frame in zip(_line_records(path), streamed_frames, strict=True):
        previous_frame = decode_frame(line_record=line_record, previous_frame_record=previous_frame)
        assert previous_frame == streamed_frame


def _line_records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, 'rt', encoding='utf-8') as trace_file:
        return [json.loads(line) for line in trace_file][1:]


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_altered_middle_frame_is_found_at_its_frame_and_sprite(game_key, tmp_path):
    """Delta encoding hides nothing: one value changed in one middle frame is one difference."""
    baseline = read_trace(path=golden_path(game_key))
    altered = copy.deepcopy(baseline)
    middle_frame = next(
        frame for frame in altered['frames'][len(altered['frames']) // 2 :] if frame['sprites']
    )
    altered_sprite = middle_frame['sprites'][len(middle_frame['sprites']) // 2]
    altered_sprite['rect'][0] += 1
    altered_path = tmp_path / 'altered.jsonl.gz'
    write_trace(altered, path=altered_path)

    differences = trace_differences(baseline=baseline, current=read_trace(path=altered_path))

    assert [difference.key for difference in differences] == [
        (middle_frame['frame'], altered_sprite['id'], 'rect')
    ]
    unexplained, _ = unexplained_and_stale(differences=differences, expected=[])
    assert unexplained == differences


class TestTraceComparison:
    """The comparison itself: it finds, explains and goes stale exactly as documented."""

    @staticmethod
    def _trace(*frames: dict[str, Any]) -> dict[str, Any]:
        return {'game': 'example', 'frame_seconds': 1.0 / 60.0, 'frames': list(frames)}

    @staticmethod
    def _frame(frame_number: int, *sprites: dict[str, Any], scene: str = 'Example'):
        return {'frame': frame_number, 'scene': scene, 'sprites': list(sprites)}

    @staticmethod
    def _sprite(sprite_id: str, rect: list[int], *, visible: bool = True) -> dict[str, Any]:
        return {'id': sprite_id, 'rect': rect, 'visible': visible}

    def test_identical_traces_have_no_differences(self):
        trace = self._trace(self._frame(0, self._sprite('Ball#0', [1, 2, 3, 4])))
        assert trace_differences(baseline=trace, current=trace) == []

    def test_rect_visible_scene_and_presence_differences_are_found(self):
        baseline = self._trace(
            self._frame(0, self._sprite('Ball#0', [1, 2, 3, 4]), self._sprite('Wall#0', [0] * 4)),
        )
        current = self._trace(
            self._frame(
                0,
                self._sprite('Ball#0', [1, 3, 3, 4], visible=False),
                self._sprite('Coin#0', [5, 5, 5, 5]),
                scene='Other',
            ),
        )
        keys = [
            difference.key for difference in trace_differences(baseline=baseline, current=current)
        ]
        assert keys == [
            (0, '', 'scene'),
            (0, 'Ball#0', 'rect'),
            (0, 'Ball#0', 'visible'),
            (0, 'Wall#0', 'present'),
            (0, 'Coin#0', 'present'),
        ]

    def test_frame_count_difference_is_found(self):
        baseline = self._trace(self._frame(0), self._frame(1))
        current = self._trace(self._frame(0))
        differences = trace_differences(baseline=baseline, current=current)
        assert [difference.key for difference in differences] == [(1, '', 'frame_count')]

    @classmethod
    def _one_rect_change(cls, *, frame_count: int = 1, sprite_id: str = 'Ball#0'):
        """Traces where one sprite's x moves from 1 to 2 on every frame."""
        baseline = cls._trace(*[
            cls._frame(frame_number, cls._sprite(sprite_id, [1, 2, 3, 4]))
            for frame_number in range(frame_count)
        ])
        current = cls._trace(*[
            cls._frame(frame_number, cls._sprite(sprite_id, [2, 2, 3, 4]))
            for frame_number in range(frame_count)
        ])
        return trace_differences(baseline=baseline, current=current)

    def test_listed_difference_with_its_value_is_explained(self):
        expected = [
            ExpectedDifference(
                frames=range(1),
                sprite_pattern='Ball#0',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=self._one_rect_change(), expected=expected
        )
        assert unexplained == []
        assert stale == []

    def test_listed_difference_with_another_value_is_unexplained(self):
        expected = [
            ExpectedDifference(
                frames=range(1),
                sprite_pattern='Ball#0',
                field='rect',
                expected=[3, 2, 3, 4],
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=self._one_rect_change(), expected=expected
        )
        assert [difference.key for difference in unexplained] == [(0, 'Ball#0', 'rect')]
        assert stale == expected

    def test_absent_sprite_is_explained_by_expected_false(self):
        baseline = self._trace(self._frame(0, self._sprite('Coin#0', [0, 0, 1, 1])))
        current = self._trace(self._frame(0))
        expected = [
            ExpectedDifference(
                frames=range(1),
                sprite_pattern='Coin#0',
                field='present',
                expected=False,
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=trace_differences(baseline=baseline, current=current),
            expected=expected,
        )
        assert unexplained == []
        assert stale == []

    def test_unlisted_difference_is_unexplained(self):
        unexplained, stale = unexplained_and_stale(differences=self._one_rect_change(), expected=[])
        assert [difference.key for difference in unexplained] == [(0, 'Ball#0', 'rect')]
        assert stale == []

    def test_frame_range_explains_every_frame_inside_it_only(self):
        expected = [
            ExpectedDifference(
                frames=range(1, 3),
                sprite_pattern='Ball#0',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=4), expected=expected
        )
        assert [difference.frame for difference in unexplained] == [0, 3]
        assert stale == []

    def test_sprite_pattern_matches_with_fnmatch(self):
        expected = [
            ExpectedDifference(
                frames=range(2),
                sprite_pattern='GroundSegment#*',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='test',
            )
        ]
        ground_unexplained, _ = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=2, sprite_id='GroundSegment#7'),
            expected=expected,
        )
        wall_unexplained, wall_stale = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=2, sprite_id='StoneWall#0'),
            expected=expected,
        )
        assert ground_unexplained == []
        assert len(wall_unexplained) == 2
        assert wall_stale == expected

    def test_rule_explains_the_differences_it_accepts(self):
        def shifted_right_by_one(baseline_value, current_value):
            return current_value == [baseline_value[0] + 1, *baseline_value[1:]]

        def shifted_left_by_one(baseline_value, current_value):
            return current_value == [baseline_value[0] - 1, *baseline_value[1:]]

        accepted_unexplained, accepted_stale = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=3),
            expected=[
                ExpectedDifference(
                    frames=range(3),
                    sprite_pattern='*',
                    field='rect',
                    rule=shifted_right_by_one,
                    reason='test',
                )
            ],
        )
        rejected_unexplained, _ = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=3),
            expected=[
                ExpectedDifference(
                    frames=range(3),
                    sprite_pattern='*',
                    field='rect',
                    rule=shifted_left_by_one,
                    reason='test',
                )
            ],
        )
        assert accepted_unexplained == []
        assert accepted_stale == []
        assert len(rejected_unexplained) == 3

    def test_range_entry_that_explains_nothing_is_stale(self):
        trace = self._trace(self._frame(0, self._sprite('Ball#0', [1, 2, 3, 4])))
        expected = [
            ExpectedDifference(
                frames=range(100),
                sprite_pattern='*',
                field='rect',
                rule=lambda baseline_value, current_value: True,
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=trace_differences(baseline=trace, current=trace), expected=expected
        )
        assert unexplained == []
        assert stale == expected

    def test_entry_needs_an_expected_value_or_a_rule(self):
        with pytest.raises(ValueError, match='expected value or a rule'):
            ExpectedDifference(frames=range(1), sprite_pattern='*', field='rect', reason='test')
