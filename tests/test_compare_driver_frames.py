"""scripts/compare_driver_frames.py compares the frames tests presented on different drivers.

The runs are fabricated: fingerprint files written as the frame fingerprints plugin
(glitchygames/testing/frame_fingerprints.py) writes them, and PNG frames saved where its image
request saves them.
"""

from __future__ import annotations

import argparse
import struct
import sys
from typing import TYPE_CHECKING

import pygame
import pytest
from PIL import Image
from scripts.compare_driver_frames import main, parse_labelled_run, run

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_comparison import (
    DIFFERENCE_COLOR,
    DIFFERENCE_PANEL_CAPTION,
    FIRST_DIFFERENCE_COLOR,
    WINDOW_ANIMATION_FRAME_MILLISECONDS,
    WINDOW_ANIMATION_HEADER_HEIGHT,
    WINDOW_ANIMATION_HOLD_MILLISECONDS,
    WINDOW_ANIMATION_MINIMUM_GAP_MILLISECONDS,
    FrameSequenceDifference,
    LabelledRun,
    compare_frame_images,
    compare_frames,
    compare_labelled_runs,
    compare_repeats,
    compare_runs,
    comparison_report,
    image_request_for,
    image_request_for_differences,
    images_report,
    window_panel_caption,
    window_title,
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


# The window animation tests' frames: big enough for the stamp and the marker
WINDOW_FRAME_SIZE = (160, 120)
CHANGED_PIXEL = (40, 60)
# The dummy run's frame clock at each saved present (seconds): a zero gap after present 3, no
# reading at present 7
WINDOW_FRAME_CLOCK = {
    0: 0.0,
    1: 0.0166,
    2: 0.0499,
    3: 0.0999,
    4: 0.0999,
    5: 0.1999,
    6: 0.2166,
    8: 0.3,
    9: 0.3166,
    10: 0.3333,
}


def save_window_frame(
    *,
    directory: Path,
    position: int,
    color: tuple[int, int, int],
    changed_pixel: tuple[int, int] | None = None,
) -> None:
    """Save a WINDOW_FRAME_SIZE re-run frame of NODE_A: one colour, optionally one white pixel."""
    width, height = WINDOW_FRAME_SIZE
    rgb = bytearray(bytes(color) * (width * height))
    if changed_pixel is not None:
        start = (changed_pixel[1] * width + changed_pixel[0]) * 3
        rgb[start : start + 3] = bytes((255, 255, 255))
    save_frame_image(
        path=frame_image_path(directory=directory, nodeid=NODE_A, position=position),
        fingerprint=frame('saved', size=WINDOW_FRAME_SIZE),
        rgb_bytes=bytes(rgb),
    )


# PNG's colour types (IHDR byte 9): truecolour, truecolour with alpha
PNG_COLOUR_TYPE_RGB = 2
PNG_COLOUR_TYPE_RGBA = 6
# The sRGB chunk's rendering intent for photographs and games: perceptual
SRGB_RENDERING_INTENT_PERCEPTUAL = 0


def png_chunks(path: Path) -> list[tuple[bytes, bytes]]:
    """Read a PNG (or APNG) file's chunks, in order, as written.

    Returns:
        Each chunk's type and data.

    """
    data = path.read_bytes()
    chunks: list[tuple[bytes, bytes]] = []
    position = len(b'\x89PNG\r\n\x1a\n')
    while position < len(data):
        length, chunk_type = struct.unpack('>I4s', data[position : position + 8])
        chunks.append((chunk_type, data[position + 8 : position + 8 + length]))
        position += 12 + length
    return chunks


def animation_durations(path: Path) -> list[int]:
    """Read each frame's duration (milliseconds) from an animated PNG.

    Returns:
        The durations, in frame order.

    """
    durations = []
    with Image.open(path) as animation:
        for index in range(animation.n_frames):
            animation.seek(index)
            durations.append(animation.info['duration'])
    return durations


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


def present_difference(
    *, nodeid: str = NODE_A, position: int, presents: int, kind: str = 'pixels'
) -> FrameSequenceDifference:
    """Return a difference at a position of a test that presented ``presents`` frames on both.

    Returns:
        The difference (frame count: the presents and the final frame).

    """
    return FrameSequenceDifference(
        nodeid=nodeid,
        baseline_position=position,
        candidate_position=position,
        kind=kind,
        baseline_frame_count=presents + 1,
        candidate_frame_count=presents + 1,
        baseline_outcome='passed',
        candidate_outcome='passed',
    )


class TestImageRequestWindow:
    """The re-run saves a window of frames around the first difference, and stops after it.

    A test cannot skip to its first differing frame, but its re-run need not go further than
    the frames it saves: when every frame of the window is a present on both drivers, the
    request says where the re-run may stop, and the final frames (which only the test's end
    shows) are not asked for.
    """

    def test_a_difference_mid_test_saves_its_window_and_stops_after_it(self):
        """Present 10 of 100: presents 5 to 15 (five each side), the re-run stops after 15."""
        request = image_request_for_differences(
            differences=[present_difference(position=10, presents=100)]
        )

        assert request == FrameImageRequest(
            positions_by_test={NODE_A: tuple(range(5, 16))}, stop_after_by_test={NODE_A: 15}
        )

    def test_a_window_near_the_start_begins_at_the_first_present(self):
        """Present 1: no position before 0."""
        request = image_request_for_differences(
            differences=[present_difference(position=1, presents=100)]
        )

        assert request.positions_by_test == {NODE_A: (0, 1, 2, 3, 4, 5, 6)}
        assert request.stop_after_by_test == {NODE_A: 6}

    def test_a_window_reaching_the_final_frame_runs_the_test_to_its_end(self):
        """Present 98 of 100: the window takes in the final frame (100), so no stop."""
        request = image_request_for_differences(
            differences=[present_difference(position=98, presents=100)]
        )

        assert request.positions_by_test == {NODE_A: tuple(range(93, 101))}
        assert request.stop_after_by_test == {}

    def test_a_final_frame_difference_saves_the_final_frames_and_never_stops(self):
        """The final frame differs (position 100 of 100 presents): only the test's end shows it."""
        request = image_request_for_differences(
            differences=[present_difference(position=100, presents=100)]
        )

        assert request.positions_by_test == {NODE_A: (95, 96, 97, 98, 99, 100)}
        assert request.stop_after_by_test == {}

    def test_a_test_differing_in_two_pairs_stops_only_if_both_could(self):
        """One pair differs mid-test, another at the end: both windows, and the end, are saved."""
        request = image_request_for_differences(
            differences=[
                present_difference(position=10, presents=100),
                present_difference(position=100, presents=100),
            ]
        )

        assert request.positions_by_test == {NODE_A: (*range(5, 16), 95, 96, 97, 98, 99, 100)}
        assert request.stop_after_by_test == {}

    def test_each_test_has_its_own_window_and_stop(self):
        """Two differing tests: each its window and its stop."""
        request = image_request_for_differences(
            differences=[
                present_difference(nodeid=NODE_A, position=10, presents=100),
                present_difference(nodeid=NODE_B, position=40, presents=50),
            ]
        )

        assert request.stop_after_by_test == {NODE_A: 15, NODE_B: 45}


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

    @pytest.fixture
    def stopped_reruns(self, tmp_path) -> tuple[LabelledRun, LabelledRun]:
        """Re-runs of NODE_A stopped after present 10: present 5 differs (one pixel on cocoa).

        Each saved its window, presents 0 to 10, as WINDOW_FRAME_SIZE frames, frame N filled
        with grey N*20 (cocoa's present 5 has one white pixel at CHANGED_PIXEL). The dummy run
        read the frame clock at each present it saved (WINDOW_FRAME_CLOCK: a zero gap after
        present 3, no reading at present 7).

        Returns:
            The dummy and the cocoa re-run.

        """
        dummy = tmp_path / 'dummy-images'
        cocoa = tmp_path / 'cocoa-images'
        presents = tuple(frame(str(position)) for position in range(11))
        differing = (*presents[:5], frame('x'), *presents[6:])
        for directory, presented, frame_clock in (
            (dummy, presents, WINDOW_FRAME_CLOCK),
            (cocoa, differing, {}),
        ):
            write_run(
                directory=directory,
                records=[
                    RecordedFrames(
                        nodeid=NODE_A,
                        outcome='skipped',
                        presented=presented,
                        final=None,
                        stopped_after=10,
                        frame_clock_at=frame_clock,
                    )
                ],
            )
        for position in range(11):
            grey = (position * 20, position * 20, position * 20)
            save_window_frame(directory=dummy, position=position, color=grey)
            save_window_frame(
                directory=cocoa,
                position=position,
                color=grey,
                changed_pixel=CHANGED_PIXEL if position == 5 else None,
            )
        return (
            LabelledRun(label='dummy', directory=dummy),
            LabelledRun(label='cocoa', directory=cocoa),
        )

    def animations_of(
        self, *, reruns: tuple[LabelledRun, LabelledRun], output: Path
    ) -> tuple[Path, Path]:
        """Write the stopped re-runs' report and return the two animations' paths.

        Returns:
            The game-speed and the 250 ms animation.

        """
        dummy, cocoa = reruns
        request = FrameImageRequest(
            positions_by_test={NODE_A: tuple(range(11))}, stop_after_by_test={NODE_A: 10}
        )
        images_report(request=request, baseline=dummy, candidate=cocoa, output=output)
        folder = output / images_folder_name(nodeid=NODE_A)
        return (
            folder / 'window-side-by-side-game-speed.apng',
            folder / 'window-side-by-side-250ms.apng',
        )

    def test_a_stopped_rerun_shows_the_window_and_no_final_frame(self, stopped_reruns, tmp_path):
        """The first difference first, then each other frame of the window; no final frame."""
        dummy, cocoa = stopped_reruns
        request = FrameImageRequest(
            positions_by_test={NODE_A: tuple(range(11))}, stop_after_by_test={NODE_A: 10}
        )

        report = images_report(
            request=request, baseline=dummy, candidate=cocoa, output=tmp_path / 'differences'
        )

        lines = report.splitlines()
        pixels = WINDOW_FRAME_SIZE[0] * WINDOW_FRAME_SIZE[1]
        assert lines[1] == (
            f'  {NODE_A}: present 5 differs (pixels); 12 frames; outcome skipped on both'
        )
        assert lines[3] == (
            f'    present 5: 1 of {pixels} pixels differ '
            '(dummy-frame-5.png, cocoa-frame-5.png, difference-frame-5.png)'
        )
        assert lines[4:14] == [
            f'    present {position}: 0 of {pixels} pixels differ (dummy-frame-{position}.png, '
            f'cocoa-frame-{position}.png, difference-frame-{position}.png)'
            for position in (0, 1, 2, 3, 4, 6, 7, 8, 9, 10)
        ]
        assert lines[14:] == [
            (
                '    the window as one animation (cocoa | dummy | difference), presents 0 to 10 '
                '(11 frames): window-side-by-side-game-speed.apng (at game speed: the dummy '
                "run's served frame times), window-side-by-side-250ms.apng (250 ms a frame)"
            )
        ]

    def test_the_strip_shows_both_drivers_and_the_difference_in_step(
        self, stopped_reruns, tmp_path
    ):
        """Each frame is cocoa | dummy | difference, one present of the window, in order."""
        _game_speed, fixed = self.animations_of(reruns=stopped_reruns, output=tmp_path / 'out')

        width, height = WINDOW_FRAME_SIZE
        with Image.open(fixed) as animation:
            assert animation.n_frames == 11
            assert animation.size == (3 * width, height + WINDOW_ANIMATION_HEADER_HEIGHT)
            inside = (width // 2, WINDOW_ANIMATION_HEADER_HEIGHT + height // 4)
            for index in range(animation.n_frames):
                animation.seek(index)
                strip = animation.convert('RGB')
                grey = (index * 20,) * 3
                assert strip.getpixel(inside) == grey, index
                assert strip.getpixel((width + inside[0], inside[1])) == grey, index
            animation.seek(5)
            strip = animation.convert('RGB')
            changed = (
                2 * width + CHANGED_PIXEL[0],
                WINDOW_ANIMATION_HEADER_HEIGHT + CHANGED_PIXEL[1],
            )
            assert strip.getpixel(changed) == DIFFERENCE_COLOR

    def test_the_fixed_animation_shows_each_frame_for_250_ms_and_holds_the_last(
        self, stopped_reruns, tmp_path
    ):
        """250 ms a frame, the last held for a second before it loops."""
        _game_speed, fixed = self.animations_of(reruns=stopped_reruns, output=tmp_path / 'out')

        assert animation_durations(fixed) == [WINDOW_ANIMATION_FRAME_MILLISECONDS] * 10 + [
            WINDOW_ANIMATION_HOLD_MILLISECONDS
        ]
        assert (WINDOW_ANIMATION_FRAME_MILLISECONDS, WINDOW_ANIMATION_HOLD_MILLISECONDS) == (
            250,
            1000,
        )

    def test_the_game_speed_animation_takes_its_gaps_from_the_served_frame_times(
        self, stopped_reruns, tmp_path
    ):
        """Each gap is the dummy run's frame clock between two presents, in whole milliseconds.

        A zero gap (a clock that did not move) and a gap with no reading take the minimum; the
        last frame is held.
        """
        game_speed, _fixed = self.animations_of(reruns=stopped_reruns, output=tmp_path / 'out')

        minimum = WINDOW_ANIMATION_MINIMUM_GAP_MILLISECONDS
        assert animation_durations(game_speed) == [
            17,  # 0 -> 1: 16.6 ms, rounded
            33,  # 1 -> 2
            50,  # 2 -> 3
            minimum,  # 3 -> 4: the clock did not move
            100,  # 4 -> 5
            17,  # 5 -> 6
            minimum,  # 6 -> 7: no reading at 7
            minimum,  # 7 -> 8: no reading at 7
            17,  # 8 -> 9
            17,  # 9 -> 10
            WINDOW_ANIMATION_HOLD_MILLISECONDS,
        ]
        assert minimum == round(1000 / 60)

    def test_each_frame_is_stamped_with_its_present_and_game_time(self, stopped_reruns, tmp_path):
        """A dark box in each panel's bottom-left corner holds the stamp; the rest is as saved."""
        _game_speed, fixed = self.animations_of(reruns=stopped_reruns, output=tmp_path / 'out')

        width, height = WINDOW_FRAME_SIZE
        corner = (3, WINDOW_ANIMATION_HEADER_HEIGHT + height - 3)
        with Image.open(fixed) as animation:
            animation.seek(10)
            strip = animation.convert('RGB')
        # Frame 10 is grey 200: the stamp's box darkens the corner
        assert max(strip.getpixel(corner)) < 200
        assert strip.getpixel((width // 2, WINDOW_ANIMATION_HEADER_HEIGHT + height // 4)) == (
            200,
            200,
            200,
        )

    def test_only_the_first_differing_frame_is_marked(self, stopped_reruns, tmp_path):
        """A red border on present 5's frame, on no other."""
        _game_speed, fixed = self.animations_of(reruns=stopped_reruns, output=tmp_path / 'out')

        with Image.open(fixed) as animation:
            borders = []
            for index in range(animation.n_frames):
                animation.seek(index)
                borders.append(
                    animation.convert('RGB').getpixel((0, WINDOW_ANIMATION_HEADER_HEIGHT + 1))
                )
        assert [
            index for index, color in enumerate(borders) if color == FIRST_DIFFERENCE_COLOR
        ] == [5]

    def test_every_animation_keeps_exact_colour_tagged_as_srgb(self, stopped_reruns, tmp_path):
        """Lossless truecolour, no palette, tagged sRGB with its fallbacks and no ICC profile.

        SDL does no colour management: the frames are plain sRGB values on both drivers, so the
        files say so, and every viewer shows the same colours.
        """
        animations = self.animations_of(reruns=stopped_reruns, output=tmp_path / 'out')

        for path in animations:
            chunks = png_chunks(path)
            types = [chunk_type for chunk_type, _data in chunks]
            header = dict(chunks)[b'IHDR']
            assert header[9] in {PNG_COLOUR_TYPE_RGB, PNG_COLOUR_TYPE_RGBA}, path.name
            assert b'PLTE' not in types, path.name
            assert b'iCCP' not in types, path.name
            assert dict(chunks)[b'sRGB'] == bytes([SRGB_RENDERING_INTENT_PERCEPTUAL]), path.name
            assert dict(chunks)[b'gAMA'] == struct.pack('>I', 45455), path.name
            assert dict(chunks)[b'cHRM'] == struct.pack(
                '>8I', 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000
            ), path.name
            first_image_data = types.index(b'IDAT')
            assert {b'sRGB', b'gAMA', b'cHRM'} <= set(types[:first_image_data]), path.name

    def test_the_saved_frames_stay_raw(self, stopped_reruns, tmp_path):
        """Only the animations are stamped: each copied PNG holds the re-run's frame exactly."""
        dummy, _cocoa = stopped_reruns
        output = tmp_path / 'out'
        self.animations_of(reruns=stopped_reruns, output=output)

        folder = output / images_folder_name(nodeid=NODE_A)
        for position in range(11):
            copied = pygame.image.load(folder / f'dummy-frame-{position}.png')
            saved = pygame.image.load(
                frame_image_path(directory=dummy.directory, nodeid=NODE_A, position=position)
            )
            assert pygame.image.tobytes(copied, 'RGB') == pygame.image.tobytes(saved, 'RGB')

    def test_the_strip_has_a_title_bar_and_a_caption_bar_above_the_frames(
        self, stopped_reruns, tmp_path
    ):
        """The bars are above the game's pixels: every frame pixel is below the header."""
        _game_speed, fixed = self.animations_of(reruns=stopped_reruns, output=tmp_path / 'out')

        width = WINDOW_FRAME_SIZE[0]
        with Image.open(fixed) as animation:
            animation.seek(0)
            strip = animation.convert('RGB')
        # Frame 0 is black (grey 0): the header is drawn on its own background, not on it
        header_pixels = {
            strip.getpixel((x, y))
            for x in range(0, 3 * width, 7)
            for y in range(WINDOW_ANIMATION_HEADER_HEIGHT)
        }
        assert header_pixels != {(0, 0, 0)}
        assert WINDOW_ANIMATION_HEADER_HEIGHT > 0

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

    def test_a_run_that_recorded_no_test_is_refused(self, tmp_path, capsys):
        """An empty run would compare as full agreement (BUGS.md #256): refused, named."""
        write_run(directory=tmp_path / 'dummy', records=[record()])
        (tmp_path / 'cocoa').mkdir()

        exit_code = run(
            arguments=['compare', f'dummy={tmp_path / "dummy"}', f'cocoa={tmp_path / "cocoa"}']
        )

        assert exit_code == ExitCode.UNUSABLE_INPUT
        captured = capsys.readouterr()
        assert 'cocoa' in captured.err
        assert 'recorded no test' in captured.err
        assert not captured.out

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
        write_run(directory=tmp_path, records=[record()])
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


class TestWindowCaptions:
    """The facts each panel's caption and the strip's title state, from the run's record."""

    def test_a_dummy_panel_has_no_refresh_rate(self):
        """The dummy driver has no display to refresh: "n/a", never a made-up number."""
        record = RecordedFrames(
            nodeid=NODE_A,
            outcome='skipped',
            presented=(),
            final=None,
            run_driver='dummy',
            refresh_rate_hz=0,
            configured_fps=60.01,
        )

        assert window_panel_caption(record=record, size=(800, 600)) == (
            'dummy · refresh n/a · 60.01 FPS · 800x600'
        )

    def test_a_native_panel_states_its_refresh_rate_and_an_uncapped_target(self):
        """0 FPS is uncapped; the refresh rate is what the native run's display reported."""
        record = RecordedFrames(
            nodeid=NODE_A,
            outcome='skipped',
            presented=(),
            final=None,
            run_driver='cocoa',
            refresh_rate_hz=120,
            configured_fps=0.0,
        )

        assert window_panel_caption(record=record, size=(800, 480)) == (
            'cocoa · 120 Hz · uncapped · 800x480'
        )

    def test_values_a_run_did_not_record_are_not_available(self):
        """No engine (no configured FPS), no driver, no refresh reading: each "n/a"."""
        record = RecordedFrames(nodeid=NODE_A, outcome='skipped', presented=(), final=None)

        assert window_panel_caption(record=record, size=(160, 120)) == (
            'n/a · refresh n/a · FPS n/a · 160x120'
        )

    def test_the_title_names_the_test_and_a_shuffled_runs_seed(self):
        """The node id; the seed only when the run was shuffled."""
        shuffled = RecordedFrames(
            nodeid=NODE_A, outcome='skipped', presented=(), final=None, test_order_seed=4163716522
        )
        fixed = RecordedFrames(nodeid=NODE_A, outcome='skipped', presented=(), final=None)

        assert window_title(record=shuffled) == f'{NODE_A} · shuffled, seed 4163716522'
        assert window_title(record=fixed) == NODE_A

    def test_the_difference_panel_says_what_it_shows(self):
        """Its caption names the magenta pixels."""
        assert DIFFERENCE_PANEL_CAPTION == 'pixels that differ (magenta)'
