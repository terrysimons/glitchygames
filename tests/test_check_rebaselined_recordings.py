"""scripts/check_rebaselined_recordings.py: the reviewed re-record's check, on the command line.

The recordings are fabricated with ``TraceWriter`` and the fingerprint runs as the frame
fingerprints plugin writes them (glitchygames/testing/frame_fingerprints.py), so each test plants
exactly one difference.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import pytest
import tomli_w
from scripts.check_rebaselined_recordings import main, run

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_fingerprints import FrameFingerprint, RecordedFrames
from glitchygames.tracing import TraceWriter

if TYPE_CHECKING:
    from pathlib import Path

NODE_A = 'tests/test_a.py::test_a'
NODE_B = 'tests/test_b.py::test_b'


def _frames(*, with_label: bool = False, rock_y: int = 50) -> list[dict[str, Any]]:
    frames = []
    for number in range(3):
        sprites = [
            {'id': 'Ship#0', 'rect': [10 + number, 20, 16, 16], 'visible': True},
            {'id': 'Rock#0', 'rect': [10, rock_y, 16, 16], 'visible': True},
        ]
        if with_label:
            sprites.append({'id': 'HudLabel#0', 'rect': [8, 8, 40, 12], 'visible': True})
        frames.append({
            'frame': number,
            'scene': 'SpaceScene',
            'sprites': sprites,
            'dt': 0.016,
            'event_batches': [[]],
        })
    return frames


def _recording(path: Path, *, frames: list[dict[str, Any]]) -> Path:
    writer = TraceWriter(path=path, header={'source': 'recording', 'frame_seconds': None})
    for frame in frames:
        writer.write_frame(frame_record=frame)
    writer.close()
    return path


def _plan(tmp_path: Path, text: str) -> Path:
    path = tmp_path / 'plan.toml'
    path.write_text(text, encoding='utf-8')
    return path


def _pair(old: Path, new: Path, **allowances: Any) -> dict[str, Any]:
    """Return one pair of a plan, with its allowances (none: the defaults)."""
    pair: dict[str, Any] = {'old': str(old), 'new': str(new)}
    if allowances:
        pair['allowances'] = allowances
    return pair


def _toml_plan(tmp_path: Path, *pairs: dict[str, Any], **sections: Any) -> Path:
    """Return a plan of these pairs, written by tomli_w so any path is quoted correctly.

    Returns:
        The plan's file.

    """
    return _plan(tmp_path, tomli_w.dumps({'pair': list(pairs), **sections}))


def _labelled_plan(tmp_path: Path, **sections: Any) -> Path:
    """Return a plan naming one pair whose NEW adds an allowed HUD label, and these sections.

    Returns:
        The plan's file.

    """
    old = _recording(tmp_path / 'old.jsonl.gz', frames=_frames())
    new = _recording(tmp_path / 'new.jsonl.gz', frames=_frames(with_label=True))
    return _toml_plan(tmp_path, _pair(old, new, sprite_ids=['HudLabel#0']), **sections)


@pytest.fixture
def labelled_pair(tmp_path) -> Path:
    """Return a plan naming one pair whose NEW adds an allowed HUD label.

    Returns:
        The plan's file.

    """
    return _labelled_plan(tmp_path)


def _fingerprints(directory: Path, records: list[RecordedFrames]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'gw0-1.jsonl').write_text(
        ''.join(record.model_dump_json() + '\n' for record in records), encoding='utf-8'
    )
    return directory


def _record(nodeid: str, *digests: str) -> RecordedFrames:
    frames = tuple(FrameFingerprint(width=4, height=3, digest=digest) for digest in digests)
    return RecordedFrames(nodeid=nodeid, outcome='passed', presented=frames[:-1], final=frames[-1])


def _same_frames(tmp_path: Path) -> list[str]:
    """Return the pixel-step arguments for two runs that presented the same frames.

    Returns:
        ``--fingerprints-before DIR --fingerprints-after DIR``.

    """
    records = [_record(NODE_A, 'red', 'green')]
    return [
        '--fingerprints-before',
        str(_fingerprints(tmp_path / 'same-before', records)),
        '--fingerprints-after',
        str(_fingerprints(tmp_path / 'same-after', records)),
    ]


class TestRecordings:
    """Each pair in the plan, compared with its allowances."""

    def test_a_plan_whose_pairs_pass_prints_each_report_and_succeeds(self, labelled_pair, capsys):
        assert (
            run(arguments=['--plan', str(labelled_pair), *_same_frames(labelled_pair.parent)])
            is ExitCode.SUCCESS
        )
        output = capsys.readouterr().out
        assert 'PASS ' in output
        assert '  allowed: sprite HudLabel#0 in 3 frames' in output
        assert output.rstrip().endswith('1 of 1 recordings changed only as allowed')

    def test_a_pair_with_another_difference_fails(self, tmp_path, capsys):
        old = _recording(tmp_path / 'old.jsonl.gz', frames=_frames())
        new = _recording(tmp_path / 'new.jsonl.gz', frames=_frames(rock_y=51))
        plan = _toml_plan(tmp_path, _pair(old, new))
        assert (
            run(arguments=['--plan', str(plan), *_same_frames(tmp_path)])
            is ExitCode.REPLAY_DIVERGED
        )
        output = capsys.readouterr().out
        assert 'FAIL ' in output
        assert (
            'differs: frame.0.sprites.Rock#0.rect: [10, 50, 16, 16] -> [10, 51, 16, 16]' in output
        )
        assert output.rstrip().endswith('0 of 1 recordings changed only as allowed')

    def test_the_report_lists_as_many_differences_as_asked(self, tmp_path, capsys):
        old = _recording(tmp_path / 'old.jsonl.gz', frames=_frames())
        new = _recording(tmp_path / 'new.jsonl.gz', frames=_frames(rock_y=51))
        plan = _toml_plan(tmp_path, _pair(old, new))
        run(arguments=['--plan', str(plan), '--limit', '1', *_same_frames(tmp_path)])
        assert '... and 2 more differences' in capsys.readouterr().out

    @pytest.mark.parametrize(
        'folder',
        [
            # No drive letter: joined to tmp_path, a drive path would replace it on Windows
            # (CircleCI job 5401 tried to make C:\Users\circleci). Windows makes two nested
            # folders here, other systems one folder with a backslash in its name: either way
            # the plan's path holds a backslash
            'Users\\circleci',
            "it's",
            pytest.param(
                'it\'s "quoted"',
                marks=pytest.mark.skipif(
                    sys.platform == 'win32', reason='a Windows file name cannot hold a double quote'
                ),
            ),
        ],
        ids=['a backslash (a Windows path)', 'a single quote', 'both quotes'],
    )
    def test_a_plan_reads_any_recording_path(self, tmp_path, folder):
        r"""A Windows path (``C:\Users``) in a hand-quoted plan read as a TOML escape (#279)."""
        directory = tmp_path / folder
        directory.mkdir(parents=True)
        old = _recording(directory / 'old.jsonl.gz', frames=_frames())
        new = _recording(directory / 'new.jsonl.gz', frames=_frames())
        plan = _toml_plan(tmp_path, _pair(old, new))
        assert run(arguments=['--plan', str(plan), *_same_frames(tmp_path)]) is ExitCode.SUCCESS

    def test_a_missing_recording_is_missing_input(self, tmp_path, capsys):
        plan = _plan(tmp_path, '[[pair]]\nold = "nowhere.jsonl.gz"\nnew = "neither.jsonl.gz"\n')
        assert (
            run(arguments=['--plan', str(plan), *_same_frames(tmp_path)]) is ExitCode.MISSING_INPUT
        )
        assert 'nowhere.jsonl.gz' in capsys.readouterr().err

    def test_a_missing_plan_is_missing_input(self, tmp_path):
        assert (
            run(arguments=['--plan', str(tmp_path / 'none.toml'), *_same_frames(tmp_path)])
            is ExitCode.MISSING_INPUT
        )

    @pytest.mark.parametrize(
        'text',
        [
            '',
            '[[pair]]\nold = "a"\nnew = "b"\nsprites = ["HudLabel#0"]\n',
            '[[pair]]\nold = "a"\n',
            'not toml [',
            '[[pair]]\nold = "a"\nnew = "b"\n[[pixels.only_after]]\nnodeid = "tests/t.py::t"\n',
        ],
        ids=[
            'no pairs',
            'an unknown key',
            'no new recording',
            'not TOML',
            'an allowed test without a reason',
        ],
    )
    def test_an_unusable_plan_is_refused(self, tmp_path, capsys, text):
        assert (
            run(arguments=['--plan', str(_plan(tmp_path, text)), *_same_frames(tmp_path)])
            is ExitCode.UNUSABLE_INPUT
        )
        assert 'plan' in capsys.readouterr().err


class TestPixels:
    """The suite's frames on the commit before the change and on the change, test by test."""

    def _check(self, labelled_pair, tmp_path, *, before, after) -> ExitCode:
        return run(
            arguments=[
                '--plan',
                str(labelled_pair),
                '--fingerprints-before',
                str(_fingerprints(tmp_path / 'before', before)),
                '--fingerprints-after',
                str(_fingerprints(tmp_path / 'after', after)),
            ]
        )

    def test_identical_frames_pass_and_count_what_was_compared(
        self, labelled_pair, tmp_path, capsys
    ):
        records = [_record(NODE_A, 'red', 'green'), _record(NODE_B, 'blue')]
        assert (
            self._check(labelled_pair, tmp_path, before=records, after=records) is ExitCode.SUCCESS
        )
        assert 'PASS pixels: 2 tests, 3 frames compared, none differ' in capsys.readouterr().out

    def test_tests_whose_frames_vary_are_counted_not_compared(
        self, labelled_pair, tmp_path, capsys
    ):
        varying = _record(NODE_B, 'blue').model_copy(update={'frames_vary_reason': 'a clock'})
        exit_code = self._check(
            labelled_pair,
            tmp_path,
            before=[_record(NODE_A, 'red'), varying],
            after=[_record(NODE_A, 'red'), varying.model_copy(update={'final': None})],
        )
        assert exit_code is ExitCode.SUCCESS
        output = capsys.readouterr().out
        assert 'PASS pixels: 1 tests, 1 frames compared, none differ' in output
        assert '  not compared (frames_vary): 1 tests' in output

    def test_a_differing_frame_fails_naming_the_test(self, labelled_pair, tmp_path, capsys):
        exit_code = self._check(
            labelled_pair,
            tmp_path,
            before=[_record(NODE_A, 'red', 'green')],
            after=[_record(NODE_A, 'red', 'magenta')],
        )
        assert exit_code is ExitCode.REPLAY_DIVERGED
        output = capsys.readouterr().out
        assert 'FAIL pixels: 1 tests, 2 frames compared' in output
        assert f'  differs: {NODE_A}' in output

    def test_a_test_in_one_run_only_fails(self, labelled_pair, tmp_path, capsys):
        exit_code = self._check(
            labelled_pair,
            tmp_path,
            before=[_record(NODE_A, 'red'), _record(NODE_B, 'blue')],
            after=[_record(NODE_A, 'red')],
        )
        assert exit_code is ExitCode.REPLAY_DIVERGED
        assert f'  only before: {NODE_B}' in capsys.readouterr().out

    @pytest.mark.parametrize(
        ('side', 'before', 'after'),
        [
            ('only_before', [NODE_A, NODE_B], [NODE_A]),
            ('only_after', [NODE_A], [NODE_A, NODE_B]),
        ],
        ids=['a removed or renamed test', 'a new test'],
    )
    def test_a_test_the_plan_allows_in_one_run_only_passes_and_is_listed(
        self, tmp_path, capsys, side, before, after
    ):
        """A change that adds or renames tests: the plan names each, with its reason."""
        plan = _labelled_plan(
            tmp_path, pixels={side: [{'nodeid': NODE_B, 'reason': 'the HUD tests, renamed'}]}
        )
        exit_code = self._check(
            plan,
            tmp_path,
            before=[_record(nodeid, 'red') for nodeid in before],
            after=[_record(nodeid, 'red') for nodeid in after],
        )
        assert exit_code is ExitCode.SUCCESS
        output = capsys.readouterr().out
        assert 'PASS pixels: 1 tests, 1 frames compared, none differ' in output
        where = side.replace('_', ' ')
        assert f'  allowed {where}: {NODE_B} (the HUD tests, renamed)' in output

    def test_an_allowed_test_in_both_runs_fails_as_not_met(self, tmp_path, capsys):
        """An allowance that matched nothing fails, as the recordings' allowances do."""
        plan = _labelled_plan(
            tmp_path, pixels={'only_after': [{'nodeid': NODE_B, 'reason': 'a new test'}]}
        )
        records = [_record(NODE_A, 'red'), _record(NODE_B, 'blue')]
        exit_code = self._check(plan, tmp_path, before=records, after=records)
        assert exit_code is ExitCode.REPLAY_DIVERGED
        output = capsys.readouterr().out
        assert 'FAIL pixels: 2 tests, 2 frames compared, none differ' in output
        assert f'  allowance not met: only after {NODE_B}' in output

    def test_an_allowance_on_one_side_does_not_cover_the_other(self, tmp_path, capsys):
        plan = _labelled_plan(
            tmp_path, pixels={'only_after': [{'nodeid': NODE_B, 'reason': 'a new test'}]}
        )
        exit_code = self._check(
            plan,
            tmp_path,
            before=[_record(NODE_A, 'red'), _record(NODE_B, 'blue')],
            after=[_record(NODE_A, 'red')],
        )
        assert exit_code is ExitCode.REPLAY_DIVERGED
        output = capsys.readouterr().out
        assert f'  only before: {NODE_B}' in output
        assert f'  allowance not met: only after {NODE_B}' in output

    def test_runs_that_recorded_no_test_are_refused(self, labelled_pair, tmp_path, capsys):
        exit_code = self._check(labelled_pair, tmp_path, before=[], after=[])
        assert exit_code is ExitCode.UNUSABLE_INPUT
        assert 'recorded no test' in capsys.readouterr().err

    def test_a_pixel_failure_fails_the_check_though_every_recording_passes(
        self, labelled_pair, tmp_path, capsys
    ):
        self._check(
            labelled_pair,
            tmp_path,
            before=[_record(NODE_A, 'red')],
            after=[_record(NODE_A, 'magenta')],
        )
        output = capsys.readouterr().out
        assert '1 of 1 recordings changed only as allowed' in output
        assert 'FAIL pixels' in output

    def test_an_allowed_label_one_pixel_off_fails_by_its_pixels(
        self, labelled_pair, tmp_path, capsys
    ):
        """An allowed sprite's records are not compared, so its place is the pixel step's."""
        exit_code = self._check(
            labelled_pair,
            tmp_path,
            before=[_record(NODE_A, 'score at 10,10')],
            after=[_record(NODE_A, 'score at 11,10')],
        )
        assert exit_code is ExitCode.REPLAY_DIVERGED
        output = capsys.readouterr().out
        assert '  allowed: sprite HudLabel#0 in 3 frames' in output
        assert f'  differs: {NODE_A}' in output

    @pytest.mark.parametrize(
        'given',
        [(), ('--fingerprints-before',), ('--fingerprints-after',)],
        ids=['neither', 'before only', 'after only'],
    )
    def test_the_pixel_step_is_required(self, labelled_pair, tmp_path, given):
        """Without it a moved new sprite would pass: the pixels are the only check of its place."""
        directory = str(_fingerprints(tmp_path / 'run', [_record(NODE_A, 'red')]))
        arguments = ['--plan', str(labelled_pair)]
        for option in given:
            arguments += [option, directory]
        with pytest.raises(SystemExit) as raised:
            run(arguments=arguments)
        assert raised.value.code == ExitCode.ARGUMENT_PARSER_ERROR


def test_main_exits_with_the_checks_exit_code(labelled_pair, mocker):
    """The script's entry point exits with what run returned."""
    arguments = ['--plan', str(labelled_pair), *_same_frames(labelled_pair.parent)]
    mocker.patch.object(sys, 'argv', ['check_rebaselined_recordings', *arguments])
    with pytest.raises(SystemExit) as raised:
        main()
    assert raised.value.code is ExitCode.SUCCESS
