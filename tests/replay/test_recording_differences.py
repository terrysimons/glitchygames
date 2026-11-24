"""glitchygames/replay/recording_differences.py: a rebaseline changed only what was named.

The recordings are fabricated with ``TraceWriter``, in the shape a recorder writes (header
fields, then frames with sprites, ``dt``, ``event_batches`` and the format-3 fields), so each
test names exactly the one difference it plants.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pydantic
import pytest

from glitchygames.events.base import LEGACY_CUSTOM_EVENT_TYPES
from glitchygames.recording import (
    EXTERNAL_ORIGIN,
    INTERNAL_ORIGIN,
)
from glitchygames.replay.recording_differences import (
    AllowedField,
    RecordingAllowances,
    compare_recordings,
)
from glitchygames.tracing import TraceWriter

if TYPE_CHECKING:
    from pathlib import Path

GAME_EVENT_TYPE = 32867
WINDOW_SETTING_EVENT_TYPE = 32869
USER_EVENT_NAME = 'UserEvent'


def _sprite(sprite_id: str, *, x: int = 10, y: int = 20, visible: bool = True) -> dict[str, Any]:
    return {'id': sprite_id, 'rect': [x, y, 16, 16], 'visible': visible}


def _event(*, event_type: int, origin: str, **attributes: Any) -> dict[str, Any]:
    return {
        'type': event_type,
        'name': USER_EVENT_NAME if event_type >= GAME_EVENT_TYPE else 'KeyDown',
        'origin': origin,
        'attributes': attributes,
    }


KEY_DOWN = _event(event_type=768, origin=EXTERNAL_ORIGIN, key=32, scancode=44)
SCORE_POSTED = _event(event_type=GAME_EVENT_TYPE, origin=INTERNAL_ORIGIN, score=100)
WINDOW_SET = _event(event_type=WINDOW_SETTING_EVENT_TYPE, origin=INTERNAL_ORIGIN, title='Drawing')


def _header() -> dict[str, Any]:
    return {
        'source': 'recording',
        'frame_seconds': None,
        'game': 'games.space_game.game:SpaceScene',
        'engine_version': '1.0.0',
        'pygame_version': '2.5.8',
        'python_version': '3.15.2',
        'recorded_at': '2026-11-15T02:45:02.246900+00:00',
        'random_seed': 20261018,
        'custom_event_types': {'GAMEEVENT': GAME_EVENT_TYPE},
        'measurement_runs': [{'machine': 'old machine'}],
        'saves': {'space-game': {}},
    }


def _frames() -> list[dict[str, Any]]:
    frames = []
    for number in range(4):
        frame: dict[str, Any] = {
            'frame': number,
            'scene': 'SpaceScene',
            'sprites': [_sprite('Ship#0', x=10 + number), _sprite('Rock#0', y=50)],
            'dt': 0.016,
            'event_batches': [[]],
            'content_hash': ['aaaa'],
            'processing_seconds': [0.002],
        }
        frames.append(frame)
    frames[0]['scene_start'] = {
        'scene': 'games.space_game.game:SpaceScene',
        'arguments': {'level': 1},
    }
    frames[1]['event_batches'] = [[KEY_DOWN, SCORE_POSTED]]
    return frames


def _write(path: Path, *, header: dict[str, Any], frames: list[dict[str, Any]]) -> Path:
    writer = TraceWriter(path=path, header=header)
    for frame in frames:
        writer.write_frame(frame_record=frame)
    writer.close()
    return path


@pytest.fixture
def old_recording(tmp_path):
    """Return OLD: the fabricated session, written.

    Returns:
        Its file.

    """
    return _write(tmp_path / 'old.jsonl.gz', header=_header(), frames=_frames())


def _new(tmp_path, *, header=None, frames=None) -> Path:
    return _write(
        tmp_path / 'new.jsonl.gz',
        header=_header() if header is None else header,
        frames=_frames() if frames is None else frames,
    )


def _with_hud_labels(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the frames with a score label and its shadow drawn after the other sprites."""
    labelled = copy.deepcopy(frames)
    for frame in labelled:
        frame['sprites'] += [_sprite('HudLabel#0', x=11, y=11), _sprite('HudLabel#1', x=10, y=10)]
    return labelled


HUD_ALLOWANCES = RecordingAllowances(sprite_ids=frozenset({'HudLabel#0', 'HudLabel#1'}))


class TestTheSameSession:
    """Two recordings of the same session agree on everything the check compares."""

    def test_identical_recordings_pass_with_nothing_to_report(self, old_recording, tmp_path):
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path))
        assert comparison.passed
        assert comparison.differences == []
        assert comparison.frame_counts == (4, 4)

    def test_measurement_histories_and_rebaseline_bookkeeping_are_not_compared(
        self, old_recording, tmp_path
    ):
        header = _header() | {
            'measurement_runs': [{'machine': 'new machine'}, {'machine': 'old machine'}],
            'rebaselined_from': 'old.jsonl.gz',
            'engine_version': '1.1.0',
            'pygame_version': '2.5.9',
            'python_version': '3.15.3',
        }
        frames = _frames()
        for frame in frames:
            frame['content_hash'] = ['bbbb', 'aaaa']
            frame['processing_seconds'] = [0.001, 0.002]
            frame['audio_seconds'] = [0.0001]
            frame['audio_work'] = [{'voices': 1}]
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, header=header, frames=frames)
        )
        assert comparison.passed, comparison.report()

    def test_the_recorded_start_time_is_compared(self, old_recording, tmp_path):
        """A rebaseline keeps OLD's start time, so a different one is not the same session."""
        header = _header() | {'recorded_at': '2026-11-21T00:00:00+00:00'}
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, header=header))
        assert not comparison.passed
        assert [difference.where for difference in comparison.differences] == [
            ('header', 'recorded_at')
        ]


class TestSprites:
    """Every sprite record is the same once the allowed sprite ids are set aside."""

    def test_allowed_sprites_in_the_new_recording_only_pass_counted_per_id(
        self, old_recording, tmp_path
    ):
        new = _new(tmp_path, frames=_with_hud_labels(_frames()))
        comparison = compare_recordings(old=old_recording, new=new, allowances=HUD_ALLOWANCES)
        assert comparison.passed, comparison.report()
        assert comparison.allowed_counts == {
            'sprite HudLabel#0': 4,
            'sprite HudLabel#1': 4,
        }

    def test_an_allowed_sprite_one_pixel_off_still_passes_its_pixels_are_the_pixel_checks(
        self, old_recording, tmp_path
    ):
        frames = _with_hud_labels(_frames())
        frames[2]['sprites'][2]['rect'][0] += 1
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, frames=frames), allowances=HUD_ALLOWANCES
        )
        assert comparison.passed

    def test_a_sprite_moved_one_pixel_fails_naming_the_frame_and_both_rects(
        self, old_recording, tmp_path
    ):
        frames = _with_hud_labels(_frames())
        frames[2]['sprites'][1]['rect'][1] += 1
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, frames=frames), allowances=HUD_ALLOWANCES
        )
        assert not comparison.passed
        [difference] = comparison.differences
        assert difference.where == ('frame', 2, 'sprites', 'Rock#0', 'rect')
        assert difference.old == [10, 50, 16, 16]
        assert difference.new == [10, 51, 16, 16]

    def test_an_extra_sprite_of_another_class_fails(self, old_recording, tmp_path):
        frames = _with_hud_labels(_frames())
        frames[3]['sprites'].append(_sprite('Rock#1'))
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, frames=frames), allowances=HUD_ALLOWANCES
        )
        assert not comparison.passed
        assert [difference.where for difference in comparison.differences] == [
            ('frame', 3, 'sprites', 'Rock#1')
        ]

    def test_a_missing_sprite_fails(self, old_recording, tmp_path):
        frames = _frames()
        del frames[3]['sprites'][1]
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert [difference.where for difference in comparison.differences] == [
            ('frame', 3, 'sprites', 'Rock#0')
        ]

    def test_a_change_of_draw_order_fails(self, old_recording, tmp_path):
        frames = _frames()
        frames[1]['sprites'].reverse()
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert [difference.where for difference in comparison.differences] == [
            ('frame', 1, 'sprites', 'order')
        ]

    def test_an_allowed_sprite_id_the_old_recording_already_has_fails(
        self, old_recording, tmp_path
    ):
        allowances = RecordingAllowances(sprite_ids=frozenset({'Rock#0'}))
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path), allowances=allowances
        )
        assert not comparison.passed
        assert 'sprite Rock#0' in comparison.unused_allowances

    def test_an_allowed_sprite_id_the_new_recording_never_shows_fails(
        self, old_recording, tmp_path
    ):
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path), allowances=HUD_ALLOWANCES
        )
        assert not comparison.passed
        assert comparison.unused_allowances == ['sprite HudLabel#0', 'sprite HudLabel#1']


class TestTheSession:
    """Frames, scenes, served input, dt, saves, devices and internal events, record by record."""

    def test_a_different_frame_count_fails(self, old_recording, tmp_path):
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=_frames()[:3]))
        assert not comparison.passed
        assert comparison.frame_counts == (4, 3)
        assert ('frames',) in [difference.where for difference in comparison.differences]

    def test_a_longer_new_recording_fails(self, old_recording, tmp_path):
        frames = _frames()
        frames.append({**copy.deepcopy(frames[-1]), 'frame': 4})
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert comparison.frame_counts == (4, 5)
        assert [difference.where for difference in comparison.differences] == [('frames',)]

    def test_a_frame_without_its_event_batches_fails(self, old_recording, tmp_path):
        frames = _frames()
        del frames[1]['event_batches']
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        [difference] = comparison.differences
        assert difference.where == ('frame', 1, 'event_batches')
        assert repr(difference.new) == 'absent'

    def test_a_different_scene_fails(self, old_recording, tmp_path):
        frames = _frames()
        frames[2]['scene'] = 'PauseScene'
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert ('frame', 2, 'scene') in [difference.where for difference in comparison.differences]

    @pytest.mark.parametrize(
        ('field', 'value'),
        [
            ('dt', 0.017),
            ('saves_opened', {'space-game': {}}),
            ('devices_opened', [{'name': 'pad'}]),
            ('input_changes', {'mouse_focused': True}),
        ],
    )
    def test_a_different_frame_field_fails(self, old_recording, tmp_path, field, value):
        frames = _frames()
        frames[2][field] = value
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert [difference.where for difference in comparison.differences] == [('frame', 2, field)]

    def test_a_number_of_another_type_fails(self, old_recording, tmp_path):
        """5 and 5.0 differ: a recording reads back with exactly the types written."""
        frames = _frames()
        frames[0]['scene_start']['arguments']['level'] = 1.0
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert [difference.where for difference in comparison.differences] == [
            ('frame', 0, 'scene_start', 'arguments', 'level')
        ]

    def test_a_different_served_input_fails(self, old_recording, tmp_path):
        frames = _frames()
        frames[1]['event_batches'][0][0] = KEY_DOWN | {'attributes': {'key': 33, 'scancode': 44}}
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert not comparison.passed
        assert comparison.differences[0].where[:3] == ('frame', 1, 'event_batches')

    def test_a_dropped_internal_event_fails(self, old_recording, tmp_path):
        frames = _frames()
        frames[1]['event_batches'] = [[KEY_DOWN]]
        comparison = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames))
        assert not comparison.passed
        assert comparison.differences[0].where[:3] == ('frame', 1, 'event_batches')


class TestCustomEvents:
    """A rebaseline renumbers custom events into its own process's numbers (BUGS.md #211.1)."""

    @staticmethod
    def _renumbered(*, event_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        header = {
            **_header(),
            'custom_event_types': {'FPSEVENT': GAME_EVENT_TYPE, 'GAMEEVENT': 32870},
        }
        frames = _frames()
        renumbered = header['custom_event_types'][event_name]
        frames[1]['event_batches'] = [[KEY_DOWN, SCORE_POSTED | {'type': renumbered}]]
        return header, frames

    def test_a_renumbered_custom_event_type_compares_by_its_name(self, old_recording, tmp_path):
        header, frames = self._renumbered(event_name='GAMEEVENT')
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, header=header, frames=frames)
        )
        assert comparison.passed, comparison.report()

    def test_an_event_now_of_another_custom_type_fails_though_its_number_is_the_same(
        self, old_recording, tmp_path
    ):
        header, frames = self._renumbered(event_name='FPSEVENT')
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, header=header, frames=frames)
        )
        [difference] = comparison.differences
        assert difference.where == ('frame', 1, 'event_batches', 0, 1, 'type')
        assert (difference.old, difference.new) == ('GAMEEVENT', 'FPSEVENT')

    def test_a_recording_without_custom_event_types_has_the_legacy_numbers(self, tmp_path):
        """A recording made before the header named them reads with the legacy numbers.

        As a replay reads it (custom_event_type_remap).
        """
        legacy_game_event = LEGACY_CUSTOM_EVENT_TYPES['GAMEEVENT']
        old_header = _header()
        del old_header['custom_event_types']
        old_frames = _frames()
        old_frames[1]['event_batches'] = [[KEY_DOWN, SCORE_POSTED | {'type': legacy_game_event}]]
        old = _write(tmp_path / 'legacy.jsonl.gz', header=old_header, frames=old_frames)
        header, frames = self._renumbered(event_name='GAMEEVENT')
        comparison = compare_recordings(old=old, new=_new(tmp_path, header=header, frames=frames))
        assert comparison.passed, comparison.report()


class TestAllowedInternalEvents:
    """Internal events of an allowed custom event type, in the new recording only."""

    @staticmethod
    def _with_window_events(header: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        custom_event_types = {
            **header['custom_event_types'],
            'WINDOWSETTINGEVENT': WINDOW_SETTING_EVENT_TYPE,
        }
        frames = _frames()
        frames[0]['event_batches'] = [[WINDOW_SET]]
        return {**header, 'custom_event_types': custom_event_types}, frames

    WINDOW_ALLOWANCES = RecordingAllowances(internal_event_types=frozenset({'WINDOWSETTINGEVENT'}))

    def test_allowed_internal_events_pass_counted(self, old_recording, tmp_path):
        header, frames = self._with_window_events(_header())
        comparison = compare_recordings(
            old=old_recording,
            new=_new(tmp_path, header=header, frames=frames),
            allowances=self.WINDOW_ALLOWANCES,
        )
        assert comparison.passed, comparison.report()
        assert comparison.allowed_counts == {'internal event WINDOWSETTINGEVENT': 1}

    def test_a_window_setting_event_in_a_recording_not_allowed_it_fails(
        self, old_recording, tmp_path
    ):
        header, frames = self._with_window_events(_header())
        comparison = compare_recordings(
            old=old_recording,
            new=_new(tmp_path, header=header, frames=frames),
            allowances=HUD_ALLOWANCES.model_copy(update={'sprite_ids': frozenset()}),
        )
        assert not comparison.passed
        assert [difference.where[:3] for difference in comparison.differences] == [
            ('frame', 0, 'event_batches')
        ]

    def test_an_allowed_internal_event_type_the_old_recording_already_posts_fails(self, tmp_path):
        header, frames = self._with_window_events(_header())
        old = _write(tmp_path / 'old-with-window.jsonl.gz', header=header, frames=frames)
        comparison = compare_recordings(
            old=old,
            new=_new(tmp_path, header=header, frames=frames),
            allowances=self.WINDOW_ALLOWANCES,
        )
        assert comparison.unused_allowances == ['internal event WINDOWSETTINGEVENT']
        assert comparison.allowed_counts == {}

    def test_an_external_event_of_an_allowed_type_is_still_compared(self, old_recording, tmp_path):
        header, frames = self._with_window_events(_header())
        frames[0]['event_batches'] = [[WINDOW_SET | {'origin': EXTERNAL_ORIGIN}]]
        comparison = compare_recordings(
            old=old_recording,
            new=_new(tmp_path, header=header, frames=frames),
            allowances=self.WINDOW_ALLOWANCES,
        )
        assert not comparison.passed


class TestAllowedFields:
    """A named header or frame field may differ, and each allowance must be used."""

    RUN_ALLOWANCE = RecordingAllowances(
        fields=(
            AllowedField(
                where=('frame', 0, 'scene_start', 'arguments', 'run'),
                reason='the scene start gained run (#215)',
            ),
        )
    )

    def test_an_allowed_scene_argument_passes(self, old_recording, tmp_path):
        frames = _frames()
        frames[0]['scene_start']['arguments']['run'] = {'score': 0}
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, frames=frames), allowances=self.RUN_ALLOWANCE
        )
        assert comparison.passed, comparison.report()
        assert comparison.allowed_counts == {'frame.0.scene_start.arguments.run': 1}

    def test_a_third_scene_argument_change_fails(self, old_recording, tmp_path):
        frames = _frames()
        frames[0]['scene_start']['arguments'] |= {'run': {'score': 0}, 'difficulty': 'hard'}
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path, frames=frames), allowances=self.RUN_ALLOWANCE
        )
        assert [difference.where for difference in comparison.differences] == [
            ('frame', 0, 'scene_start', 'arguments', 'difficulty')
        ]

    def test_an_allowance_that_matches_nothing_fails(self, old_recording, tmp_path):
        comparison = compare_recordings(
            old=old_recording, new=_new(tmp_path), allowances=self.RUN_ALLOWANCE
        )
        assert not comparison.passed
        assert comparison.unused_allowances == ['frame.0.scene_start.arguments.run']

    def test_allowances_are_strict_models(self):
        with pytest.raises(pydantic.ValidationError):
            RecordingAllowances.model_validate({
                'sprite_ids': ['HudLabel#0'],
                'sprite_classes': ['HudLabel'],
            })


class TestTheReport:
    """The report a reviewer reads: the verdict, the allowed counts, every other difference."""

    def test_a_passing_report_names_the_frames_and_each_allowance(self, old_recording, tmp_path):
        new = _new(tmp_path, frames=_with_hud_labels(_frames()))
        report = compare_recordings(old=old_recording, new=new, allowances=HUD_ALLOWANCES).report()
        assert report.splitlines() == [
            f'PASS {old_recording} -> {new}: 4 frames each',
            '  allowed: sprite HudLabel#0 in 4 frames',
            '  allowed: sprite HudLabel#1 in 4 frames',
        ]

    def test_the_report_counts_events_and_field_differences(self, old_recording, tmp_path):
        header = {
            **_header(),
            'custom_event_types': {**_header()['custom_event_types'], 'WINDOWSETTINGEVENT': 32869},
        }
        frames = _frames()
        frames[0]['event_batches'] = [[WINDOW_SET]]
        frames[0]['scene_start']['arguments']['run'] = {'score': 0}
        allowances = RecordingAllowances(
            internal_event_types=frozenset({'WINDOWSETTINGEVENT'}),
            fields=(AllowedField(where=('frame', 0, 'scene_start'), reason='gained run'),),
        )
        report = compare_recordings(
            old=old_recording,
            new=_new(tmp_path, header=header, frames=frames),
            allowances=allowances,
        ).report()
        assert report.splitlines()[1:] == [
            '  allowed: internal event WINDOWSETTINGEVENT 1 events',
            '  allowed: frame.0.scene_start 1 differences',
        ]

    def test_a_failing_report_lists_each_difference_up_to_a_limit(self, old_recording, tmp_path):
        frames = _frames()
        for frame in frames:
            frame['dt'] = 0.5
        report = compare_recordings(old=old_recording, new=_new(tmp_path, frames=frames)).report(
            limit=2
        )
        lines = report.splitlines()
        assert lines[0].startswith('FAIL ')
        assert lines[1:] == [
            '  differs: frame.0.dt: 0.016 -> 0.5',
            '  differs: frame.1.dt: 0.016 -> 0.5',
            '  ... and 2 more differences',
        ]
