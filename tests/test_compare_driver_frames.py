"""scripts/compare_driver_frames.py compares the frames tests presented on different drivers.

The runs are fabricated: fingerprint files written as the frame fingerprints plugin
(glitchygames/testing/frame_fingerprints.py) writes them, and PNG frames saved where its image
request saves them.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

import pygame
import pytest
from scripts.compare_driver_frames import main, parse_labelled_run, run

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_comparison import (
    DIFFERENCE_COLOR,
    FrameSequenceDifference,
    LabelledRun,
    compare_frame_images,
    compare_frames,
    compare_labelled_runs,
    compare_repeats,
    compare_runs,
    comparison_report,
    image_request_for,
    images_report,
)
from glitchygames.testing.frame_fingerprints import (
    FrameFingerprint,
    FrameImageRequest,
    RecordedFrames,
    frame_image_path,
    images_folder_name,
    save_frame_image,
)

if TYPE_CHECKING:
    from pathlib import Path

FRAME_SIZE = (4, 3)
RED = (200, 30, 40)
GREEN = (20, 180, 60)
BLUE = (30, 40, 210)
NODE_A = 'tests/test_a.py::test_a'
NODE_B = 'tests/test_b.py::test_b[x y]'
NODE_C = 'tests/test_c.py::test_c'


def frame(name: str, *, size: tuple[int, int] = FRAME_SIZE) -> FrameFingerprint:
    """Return a fabricated fingerprint (the digest is just the name).

    Returns:
        The fingerprint.

    """
    return FrameFingerprint(width=size[0], height=size[1], digest=name)


def record(
    *,
    nodeid: str = NODE_A,
    presented: tuple[FrameFingerprint | None, ...] = (),
    final: FrameFingerprint | None = None,
    outcome: str = 'passed',
) -> RecordedFrames:
    """Return a fabricated test record.

    Returns:
        The record.

    """
    return RecordedFrames(nodeid=nodeid, outcome=outcome, presented=presented, final=final)


def write_run(*, directory: Path, records: list[RecordedFrames]) -> Path:
    """Write records as a run's fingerprints file (as one worker would).

    Returns:
        The run's directory.

    """
    directory.mkdir(parents=True, exist_ok=True)
    lines = ''.join(f'{each.model_dump_json()}\n' for each in records)
    (directory / 'gw0-1.jsonl').write_text(lines, encoding='utf-8')
    return directory


def save_colour_frame(
    *,
    directory: Path,
    nodeid: str,
    position: int,
    color: tuple[int, int, int],
    changed_pixel: tuple[int, int] | None = None,
) -> None:
    """Save a FRAME_SIZE re-run frame image: one colour, optionally one pixel turned white."""
    width, height = FRAME_SIZE
    rgb = bytearray(bytes(color) * (width * height))
    if changed_pixel is not None:
        start = (changed_pixel[1] * width + changed_pixel[0]) * 3
        rgb[start : start + 3] = bytes((255, 255, 255))
    save_frame_image(
        path=frame_image_path(directory=directory, nodeid=nodeid, position=position),
        fingerprint=frame('saved'),
        rgb_bytes=bytes(rgb),
    )


def save_small_frame(*, directory: Path, nodeid: str, position: int) -> None:
    """Save a 2x2 red re-run frame image (a frame of another size than FRAME_SIZE)."""
    save_frame_image(
        path=frame_image_path(directory=directory, nodeid=nodeid, position=position),
        fingerprint=frame('small', size=(2, 2)),
        rgb_bytes=bytes(RED) * 4,
    )


class TestParseLabelledRun:
    """LABEL=DIRECTORY arguments."""

    def test_a_label_and_a_directory(self, tmp_path):
        """The label is before the first '='."""
        assert parse_labelled_run(f'cocoa={tmp_path}/a=b') == LabelledRun(
            label='cocoa', directory=tmp_path / 'a=b'
        )

    @pytest.mark.parametrize('text', ['dummy', '=run', 'dummy='])
    def test_a_missing_part_is_refused(self, text):
        """Both a label and a directory are needed."""
        with pytest.raises(argparse.ArgumentTypeError, match='expected LABEL=DIRECTORY'):
            parse_labelled_run(text)


class TestCompareFrames:
    """compare_frames finds where one test's frames first differ between two runs."""

    def test_identical_frames_do_not_differ(self):
        """Same presents, same final frame, same outcome."""
        same = record(presented=(frame('a'), frame('b')), final=frame('c'))

        assert compare_frames(baseline=same, candidate=same) is None

    @pytest.mark.parametrize(
        ('candidate_second_frame', 'kind'),
        [(frame('other'), 'pixels'), (frame('b', size=(8, 6)), 'size'), (None, 'display')],
        ids=['pixels', 'size', 'display'],
    )
    def test_the_first_differing_present(self, candidate_second_frame, kind):
        """Present 1 is the first difference; the kind says what differs."""
        baseline = record(presented=(frame('a'), frame('b'), frame('c')), final=frame('d'))
        candidate = record(
            presented=(frame('a'), candidate_second_frame, frame('x')), final=frame('y')
        )

        difference = compare_frames(baseline=baseline, candidate=candidate)

        assert difference == FrameSequenceDifference(
            nodeid=NODE_A,
            baseline_position=1,
            candidate_position=1,
            kind=kind,
            baseline_frame_count=4,
            candidate_frame_count=4,
            baseline_outcome='passed',
            candidate_outcome='passed',
        )

    def test_more_presents_in_one_run(self):
        """Matching shared presents, then one run presented more: the present count differs."""
        baseline = record(presented=(frame('a'),), final=frame('b'))
        candidate = record(presented=(frame('a'), frame('b')), final=frame('b'))

        difference = compare_frames(baseline=baseline, candidate=candidate)

        assert difference is not None
        assert (difference.kind, difference.baseline_position) == ('present count', 1)
        assert difference.describe() == (
            'the final frame | present 1 differs (present count); 2 | 3 frames; '
            'outcome passed on both'
        )

    def test_only_the_final_frame_differs(self):
        """The final frame's position in each run."""
        baseline = record(presented=(frame('a'),), final=frame('b'))
        candidate = record(presented=(frame('a'),), final=frame('c'))

        difference = compare_frames(baseline=baseline, candidate=candidate)

        assert difference is not None
        assert difference.describe() == (
            'the final frame differs (pixels); 2 frames; outcome passed on both'
        )

    def test_matching_frames_with_another_outcome(self):
        """The test failed on one driver only: an outcome difference."""
        baseline = record(final=frame('a'))
        candidate = record(final=frame('a'), outcome='failed')

        difference = compare_frames(baseline=baseline, candidate=candidate)

        assert difference is not None
        assert difference.describe() == (
            'the final frame differs (outcome); 1 frames; outcome passed | failed'
        )


class TestCompareRuns:
    """Whole runs: shared tests compared, the rest listed per run."""

    def test_differences_and_tests_in_one_run_only(self):
        """Sorted differences; node ids only in either run."""
        baseline = {
            NODE_A: record(nodeid=NODE_A, final=frame('a')),
            NODE_B: record(nodeid=NODE_B, final=frame('b')),
        }
        candidate = {
            NODE_A: record(nodeid=NODE_A, final=frame('changed')),
            NODE_C: record(nodeid=NODE_C, final=frame('c')),
        }

        differences, only_in_baseline, only_in_candidate = compare_runs(
            baseline=baseline, candidate=candidate
        )

        assert [difference.nodeid for difference in differences] == [NODE_A]
        assert only_in_baseline == [NODE_B]
        assert only_in_candidate == [NODE_C]

    def test_repeats_list_each_nondeterministic_test_once(self):
        """Every later run is compared with the first; partly recorded tests count too."""
        first = {
            NODE_A: record(nodeid=NODE_A, final=frame('a')),
            NODE_B: record(nodeid=NODE_B, final=frame('b')),
        }
        second = {NODE_A: record(nodeid=NODE_A, final=frame('a2'))}
        third = {
            NODE_A: record(nodeid=NODE_A, final=frame('a3')),
            NODE_B: record(nodeid=NODE_B, final=frame('b')),
        }

        repeats = compare_repeats(label='dummy', runs=[first, second, third])

        assert repeats.run_count == 3
        assert [difference.nodeid for difference in repeats.differences] == [NODE_A]
        assert repeats.recorded_in_some_runs == (NODE_B,)
        assert repeats.nodeids == {NODE_A, NODE_B}


class TestCompareLabelledRuns:
    """Repeats per driver, then each driver against the first one."""

    @pytest.fixture
    def runs(self, tmp_path) -> list[LabelledRun]:
        """Two dummy runs (NODE_B nondeterministic) and one cocoa run (NODE_A and B differ).

        Returns:
            The labelled runs, dummy first.

        """
        dummy_records = [record(nodeid=NODE_A, final=frame('a')), record(nodeid=NODE_C)]
        write_run(
            directory=tmp_path / 'dummy-1',
            records=[*dummy_records, record(nodeid=NODE_B, final=frame('b1'))],
        )
        write_run(
            directory=tmp_path / 'dummy-2',
            records=[*dummy_records, record(nodeid=NODE_B, final=frame('b2'))],
        )
        write_run(
            directory=tmp_path / 'cocoa',
            records=[
                record(nodeid=NODE_A, presented=(frame('x'),), final=frame('a'), outcome='failed'),
                record(nodeid=NODE_B, final=frame('b3')),
            ],
        )
        return [
            LabelledRun(label='dummy', directory=tmp_path / 'dummy-1'),
            LabelledRun(label='cocoa', directory=tmp_path / 'cocoa'),
            LabelledRun(label='dummy', directory=tmp_path / 'dummy-2'),
        ]

    def test_nondeterministic_tests_are_not_driver_differences(self, runs):
        """NODE_B differs on dummy alone, so only NODE_A is a driver difference."""
        repeats, drivers = compare_labelled_runs(runs=runs)

        (dummy_repeats,) = repeats
        assert dummy_repeats.nodeids == {NODE_B}
        (cocoa,) = drivers
        assert (cocoa.baseline.label, cocoa.candidate.label) == ('dummy', 'cocoa')
        assert cocoa.tests_in_both == 2
        assert [difference.nodeid for difference in cocoa.differences] == [NODE_A]
        assert cocoa.only_in_baseline == (NODE_C,)
        assert cocoa.only_in_candidate == ()

    def test_the_report_lists_every_finding(self, runs):
        """Differences, one-run tests and nondeterministic tests, each under its heading."""
        repeats, drivers = compare_labelled_runs(runs=runs)

        report = comparison_report(repeats=repeats, drivers=drivers)

        assert report.splitlines() == [
            f'dummy ({runs[0].directory}) vs cocoa ({runs[1].directory}): 2 tests in both',
            '  Driver differences: 1',
            (
                f'    {NODE_A}: the final frame | present 0 differs (present count); 1 | 2 frames; '
                'outcome passed | failed'
            ),
            '  Recorded on dummy only: 1',
            f'    {NODE_C}',
            '  Recorded on cocoa only: 0',
            '  Not compared (frames_vary): 0',
            'Nondeterministic on dummy (2 runs; not counted as driver differences): 1',
            f'    {NODE_B}: the final frame differs (pixels); 1 frames; outcome passed on both',
        ]

    def test_a_partly_recorded_test_is_reported(self, tmp_path):
        """A test missing from one repeat is listed as recorded in some runs only."""
        write_run(directory=tmp_path / 'one', records=[record(nodeid=NODE_A)])
        write_run(directory=tmp_path / 'two', records=[])

        repeats, drivers = compare_labelled_runs(
            runs=[
                LabelledRun(label='dummy', directory=tmp_path / 'one'),
                LabelledRun(label='dummy', directory=tmp_path / 'two'),
            ]
        )

        assert drivers == []
        assert comparison_report(repeats=repeats, drivers=drivers).splitlines()[1:] == [
            f'    {NODE_A}: recorded in some runs only'
        ]

    def test_the_image_request_names_the_first_difference_and_both_final_frames(self, runs):
        """Positions to save in the re-run, per differing test."""
        _repeats, drivers = compare_labelled_runs(runs=runs)

        assert image_request_for(drivers=drivers) == FrameImageRequest(
            positions_by_test={NODE_A: (0, 1)}
        )


class TestFrameImages:
    """compare_frame_images counts differing pixels and draws them."""

    def test_differing_pixels_are_counted_and_shown_in_magenta(self, tmp_path):
        """One pixel differs: magenta there, the rest the baseline dimmed to grey."""
        save_colour_frame(directory=tmp_path, nodeid=NODE_A, position=0, color=GREEN)
        save_colour_frame(
            directory=tmp_path, nodeid=NODE_A, position=1, color=GREEN, changed_pixel=(2, 1)
        )
        difference_image = tmp_path / 'out' / 'difference.png'

        counts = compare_frame_images(
            baseline_image=frame_image_path(directory=tmp_path, nodeid=NODE_A, position=0),
            candidate_image=frame_image_path(directory=tmp_path, nodeid=NODE_A, position=1),
            difference_image=difference_image,
        )

        assert counts == (1, 12)
        difference = pygame.image.load(difference_image)
        assert difference.get_at((2, 1))[:3] == DIFFERENCE_COLOR
        grey = int(sum(GREEN) / 3 * 0.3)
        assert difference.get_at((0, 0))[:3] == (grey, grey, grey)

    def test_frames_of_different_sizes_are_not_compared(self, tmp_path):
        """No count and no difference image."""
        save_colour_frame(directory=tmp_path, nodeid=NODE_A, position=0, color=GREEN)
        save_small_frame(directory=tmp_path, nodeid=NODE_A, position=1)
        difference_image = tmp_path / 'difference.png'

        counts = compare_frame_images(
            baseline_image=frame_image_path(directory=tmp_path, nodeid=NODE_A, position=0),
            candidate_image=frame_image_path(directory=tmp_path, nodeid=NODE_A, position=1),
            difference_image=difference_image,
        )

        assert counts is None
        assert not difference_image.exists()


class TestImagesReport:
    """The images command: each requested test's re-run frames, compared as images."""

    @pytest.fixture
    def reruns(self, tmp_path) -> tuple[LabelledRun, LabelledRun]:
        """Re-runs on dummy and cocoa of four requested tests.

        NODE_A differs at present 1 and in its final frame (images of both); NODE_B's
        difference did not reproduce; NODE_C differs in size with no image saved on cocoa.
        'tests/test_d.py::test_d' was recorded on dummy only.

        Returns:
            The dummy and the cocoa re-run.

        """
        dummy = tmp_path / 'dummy-images'
        cocoa = tmp_path / 'cocoa-images'
        write_run(
            directory=dummy,
            records=[
                record(nodeid=NODE_A, presented=(frame('a'), frame('b')), final=frame('c')),
                record(nodeid=NODE_B, final=frame('b')),
                record(nodeid=NODE_C, final=frame('c')),
                record(nodeid='tests/test_d.py::test_d'),
            ],
        )
        write_run(
            directory=cocoa,
            records=[
                record(nodeid=NODE_A, presented=(frame('a'), frame('x')), final=frame('y')),
                record(nodeid=NODE_B, final=frame('b')),
                record(nodeid=NODE_C, final=frame('c', size=(2, 2))),
            ],
        )
        for position, changed_pixel in ((1, (0, 0)), (2, None)):
            save_colour_frame(directory=dummy, nodeid=NODE_A, position=position, color=RED)
            save_colour_frame(
                directory=cocoa,
                nodeid=NODE_A,
                position=position,
                color=RED if changed_pixel else BLUE,
                changed_pixel=changed_pixel,
            )
        save_colour_frame(directory=dummy, nodeid=NODE_C, position=0, color=RED)
        return (
            LabelledRun(label='dummy', directory=dummy),
            LabelledRun(label='cocoa', directory=cocoa),
        )

    def test_the_report_names_every_image(self, reruns, tmp_path):
        """Counts and file names per differing frame; why where there are none."""
        dummy, cocoa = reruns
        output = tmp_path / 'differences'
        request = FrameImageRequest(
            positions_by_test={
                NODE_A: (1, 2),
                NODE_B: (0,),
                NODE_C: (0,),
                'tests/test_d.py::test_d': (0,),
            }
        )

        report = images_report(request=request, baseline=dummy, candidate=cocoa, output=output)

        folder_a = output / images_folder_name(nodeid=NODE_A)
        assert report.splitlines() == [
            (
                f'Re-run of 4 tests: dummy ({dummy.directory}) vs cocoa ({cocoa.directory}); '
                f'images in {output}'
            ),
            f'  {NODE_A}: present 1 differs (pixels); 3 frames; outcome passed on both',
            f'    images: {folder_a}',
            (
                '    present 1: 1 of 12 pixels differ '
                '(dummy-frame-1.png, cocoa-frame-1.png, difference-frame-1.png)'
            ),
            (
                '    the final frame: 12 of 12 pixels differ '
                '(dummy-frame-2.png, cocoa-frame-2.png, difference-frame-2.png)'
            ),
            (
                f'  {NODE_B}: the difference did not reproduce in the re-run (it depends on the '
                'tests that ran before it)'
            ),
            f'  {NODE_C}: the final frame differs (size); 1 frames; outcome passed on both',
            f'    images: {output / images_folder_name(nodeid=NODE_C)}',
            (
                '    the final frame: no image saved on both drivers '
                '(no display, or not requested) (dummy-frame-0.png)'
            ),
            '  tests/test_d.py::test_d: not recorded in both re-runs',
        ]
        assert pygame.image.load(folder_a / 'cocoa-frame-2.png').get_at((0, 0))[:3] == BLUE

    def test_frames_of_different_sizes_are_noted(self, reruns, tmp_path):
        """Both images saved, sizes differ: the note and both file names."""
        dummy, cocoa = reruns
        save_small_frame(directory=cocoa.directory, nodeid=NODE_C, position=0)
        request = FrameImageRequest(positions_by_test={NODE_C: (0,)})

        report = images_report(
            request=request, baseline=dummy, candidate=cocoa, output=tmp_path / 'out'
        )

        assert report.splitlines()[-1] == (
            '    the final frame: sizes differ (dummy-frame-0.png, cocoa-frame-0.png)'
        )


class TestCommandLine:
    """run() and main(): the commands, their reports and exit codes."""

    def test_compare_prints_the_report_and_writes_the_request(self, tmp_path, capsys):
        """The compare command: report on stdout, the request file in a new folder."""
        write_run(directory=tmp_path / 'dummy', records=[record(final=frame('a'))])
        write_run(directory=tmp_path / 'cocoa', records=[record(final=frame('b'))])
        request_path = tmp_path / 'new' / 'request.json'

        exit_code = run(
            arguments=[
                'compare',
                f'dummy={tmp_path / "dummy"}',
                f'cocoa={tmp_path / "cocoa"}',
                '--image-request',
                str(request_path),
            ]
        )

        assert exit_code == ExitCode.SUCCESS
        assert '  Driver differences: 1' in capsys.readouterr().out
        request = FrameImageRequest.model_validate_json(request_path.read_text(encoding='utf-8'))
        assert request.positions_by_test == {NODE_A: (0,)}

    def test_compare_without_a_request(self, tmp_path, capsys):
        """No --image-request: the report only."""
        write_run(directory=tmp_path / 'dummy', records=[record()])

        exit_code = run(arguments=['compare', f'dummy={tmp_path / "dummy"}'])

        assert exit_code == ExitCode.SUCCESS
        assert capsys.readouterr().out == '\n'

    def test_images_prints_its_report(self, tmp_path, capsys):
        """The images command reads the request and both re-runs."""
        write_run(directory=tmp_path / 'dummy', records=[record()])
        write_run(directory=tmp_path / 'cocoa', records=[record()])
        request_path = tmp_path / 'request.json'
        request_path.write_text(
            FrameImageRequest(positions_by_test={NODE_A: (0,)}).model_dump_json(),
            encoding='utf-8',
        )

        exit_code = run(
            arguments=[
                'images',
                f'dummy={tmp_path / "dummy"}',
                f'cocoa={tmp_path / "cocoa"}',
                '--request',
                str(request_path),
                '--output',
                str(tmp_path / 'out'),
            ]
        )

        assert exit_code == ExitCode.SUCCESS
        assert 'did not reproduce' in capsys.readouterr().out

    def test_a_missing_run_is_missing_input(self, tmp_path, capsys):
        """A directory that does not exist."""
        exit_code = run(arguments=['compare', f'dummy={tmp_path / "absent"}'])

        assert exit_code == ExitCode.MISSING_INPUT
        assert 'no such fingerprints directory' in capsys.readouterr().err

    def test_a_malformed_record_is_unusable_input(self, tmp_path, capsys):
        """A line that is not a record."""
        (tmp_path / 'run').mkdir()
        (tmp_path / 'run' / 'gw0-1.jsonl').write_text('{"nodeid": 1}\n', encoding='utf-8')

        exit_code = run(arguments=['compare', f'dummy={tmp_path / "run"}'])

        assert exit_code == ExitCode.UNUSABLE_INPUT
        assert 'unusable record or request' in capsys.readouterr().err

    def test_an_unwritable_request_cannot_be_written(self, tmp_path, capsys):
        """The request path is a directory."""
        write_run(directory=tmp_path / 'dummy', records=[record()])

        exit_code = run(
            arguments=['compare', f'dummy={tmp_path / "dummy"}', '--image-request', str(tmp_path)]
        )

        assert exit_code == ExitCode.CANNOT_WRITE_OUTPUT
        assert 'cannot write the output' in capsys.readouterr().err

    def test_main_exits_with_the_exit_code(self, tmp_path, monkeypatch):
        """main() reads sys.argv and exits with run()'s code."""
        monkeypatch.setattr(sys, 'argv', ['compare_driver_frames.py', 'compare', f'x={tmp_path}'])

        with pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == ExitCode.SUCCESS


class TestWhatIsNotCompared:
    """frames_vary tests and final frames off their run's driver are not compared."""

    def test_frames_vary_tests_are_listed_not_compared(self, tmp_path):
        """A marked test whose frames differ is no driver difference; its reason is listed."""
        varying = record(final=frame('a')).model_copy(
            update={'frames_vary_reason': 'measured frame times'}
        )
        write_run(directory=tmp_path / 'dummy', records=[varying])
        write_run(directory=tmp_path / 'cocoa', records=[record(final=frame('b'))])

        repeats, drivers = compare_labelled_runs(
            runs=[
                LabelledRun(label='dummy', directory=tmp_path / 'dummy'),
                LabelledRun(label='cocoa', directory=tmp_path / 'cocoa'),
            ]
        )

        (driver,) = drivers
        assert driver.differences == ()
        assert driver.frames_vary == {NODE_A: 'measured frame times'}
        assert comparison_report(repeats=repeats, drivers=drivers).splitlines()[-2:] == [
            '  Not compared (frames_vary): 1',
            f'    {NODE_A}: measured frame times',
        ]

    def test_a_final_display_off_the_runs_driver_is_not_compared(self):
        """A --headless engine moved the real-driver run's display: its final frame is skipped."""
        baseline = record(presented=(frame('a'),), final=frame('b')).model_copy(
            update={'run_driver': 'dummy', 'final_driver': 'dummy'}
        )
        moved = record(presented=(frame('a'),), final=None).model_copy(
            update={'run_driver': 'cocoa', 'final_driver': None}
        )

        assert compare_frames(baseline=baseline, candidate=moved) is None
