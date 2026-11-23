"""Compare the frames tests presented on different SDL video drivers (or in repeated runs).

The frame fingerprints plugin (glitchygames/testing/frame_fingerprints.py) records the frames;
this module compares two or more runs' records:

- ``compare_labelled_runs``: runs that share a label are repeats on the same driver (a test whose
  frames differ between them is nondeterministic, never a driver difference); the first run of
  each other label is compared with the first run of the first label, the baseline
  (``comparison_report`` says what differs, ``image_request_for`` what to save as PNG files in a
  re-run of the differing tests);
- ``images_report``: a re-run's saved frames, with a difference image for each still-differing
  frame (the baseline frame dimmed to grey, differing pixels magenta).

The suite's own driver comparison (tests/driver_comparison.py) and the command line tools
(scripts/compare_driver_frames.py, scripts/driver_frame_matrix.py) are built on it. Moved here
from scripts/compare_driver_frames.py (Part 3, Stage D, Task D9 fix round 1), so the test plugin
every engine test runs under imports no ``scripts.*``.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pygame
from PIL import Image
from pydantic import BaseModel, ConfigDict

from glitchygames.testing.frame_fingerprints import (
    FrameFingerprint,
    FrameImageRequest,
    RecordedFrames,
    frame_image_path,
    frame_position_name,
    images_folder_name,
    read_recorded_frames,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# A run's fingerprints directory: pydantic reads the models' field annotations when the module
# loads (Path at run time, not only for type checking), as settings.py's RecordingRenames does
type RunDirectory = Path
# Differing pixels in a difference image, and how bright the baseline frame shows under them
DIFFERENCE_COLOR = (255, 0, 255)
DIMMED_BRIGHTNESS = 0.3
# The frames a re-run saves on each side of a test's first difference (image_request_for):
# ...bbbbbdaaaaa..., the difference and five presents before and after it
IMAGE_WINDOW_PRESENTS = 5
# How long each frame of a window's animation shows: slow enough to see each frame change
WINDOW_ANIMATION_FRAME_MILLISECONDS = 250
# A window needs this many frames to be worth an animation
WINDOW_ANIMATION_MINIMUM_FRAMES = 2


class LabelledRun(BaseModel):
    """One run's fingerprints directory and its label (the driver it ran on)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    label: str
    directory: RunDirectory


class FrameSequenceDifference(BaseModel):
    """How one test's frames differ between two runs."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    nodeid: str
    # The first position (in RecordedFrames.frames) whose frames differ, in each run: the same
    # position unless the present counts differ and the final frames are the first to differ
    baseline_position: int
    candidate_position: int
    # What differs there: 'pixels', 'size', 'display' (a frame without a display in one run),
    # 'present count' (one run presented more frames; the shorter run's final frame is compared)
    # or 'outcome' (every frame matches, the test's outcome does not)
    kind: str
    baseline_frame_count: int
    candidate_frame_count: int
    baseline_outcome: str
    candidate_outcome: str

    def describe(self) -> str:
        """Describe the difference in one line.

        Returns:
            For example ``present 3 differs (pixels); outcome passed on both``.

        """
        baseline_name = frame_position_name(
            position=self.baseline_position, frame_count=self.baseline_frame_count
        )
        candidate_name = frame_position_name(
            position=self.candidate_position, frame_count=self.candidate_frame_count
        )
        where = (
            baseline_name
            if baseline_name == candidate_name
            else f'{baseline_name} | {candidate_name}'
        )
        counts = (
            f'{self.baseline_frame_count} frames'
            if self.baseline_frame_count == self.candidate_frame_count
            else f'{self.baseline_frame_count} | {self.candidate_frame_count} frames'
        )
        outcome = (
            f'{self.baseline_outcome} on both'
            if self.baseline_outcome == self.candidate_outcome
            else f'{self.baseline_outcome} | {self.candidate_outcome}'
        )
        return f'{where} differs ({self.kind}); {counts}; outcome {outcome}'


class DriverComparison(BaseModel):
    """A candidate driver's run compared with the baseline's."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    baseline: LabelledRun
    candidate: LabelledRun
    tests_in_both: int
    differences: tuple[FrameSequenceDifference, ...]
    only_in_baseline: tuple[str, ...]
    only_in_candidate: tuple[str, ...]
    # Tests marked frames_vary (in either run), not compared: their reasons by node id
    frames_vary: dict[str, str] = {}


class RepeatComparison(BaseModel):
    """The tests whose frames differ between runs on the same driver (nondeterministic)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    label: str
    run_count: int
    differences: tuple[FrameSequenceDifference, ...]
    # Tests recorded in some of the label's runs but not all
    recorded_in_some_runs: tuple[str, ...]

    @property
    def nodeids(self) -> frozenset[str]:
        """Every test this comparison found nondeterministic.

        Returns:
            The differing and the partly recorded tests' node ids.

        """
        return frozenset(difference.nodeid for difference in self.differences) | frozenset(
            self.recorded_in_some_runs
        )


class WindowAnimations(BaseModel):
    """A re-run test's window of presents on both drivers, as animated PNGs (APNG)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    first_position: int
    last_position: int
    frame_count: int
    baseline_animation: Path
    candidate_animation: Path
    difference_animation: Path


class FrameImageComparison(BaseModel):
    """One frame of a re-run test on both drivers, as images."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    position_name: str
    # The frame's position in the baseline's frames, and whether it is the final frame
    position: int
    is_final: bool
    baseline_image: Path | None
    candidate_image: Path | None
    difference_image: Path | None
    # Pixels whose colour differs (None when the images are missing or their sizes differ)
    differing_pixels: int | None
    total_pixels: int | None
    note: str


def compare_frames(
    *, baseline: RecordedFrames, candidate: RecordedFrames
) -> FrameSequenceDifference | None:
    """Find where two runs' frames of one test first differ.

    The presents are compared in order, then the final frames. When one run presented more
    frames than the other and the shared presents match, the difference is the present count,
    at the shorter run's final frame. The final frames are compared only when both were drawn
    on their run's own driver (``RecordedFrames.final_on_run_driver``). When every frame
    matches but the outcomes differ (the test failed on one driver only), the difference is the
    outcome, at the final frames.

    Args:
        baseline: The test's record in the baseline run.
        candidate: The test's record in the other run.

    Returns:
        The first difference, or None when every frame matches.

    """
    shared_presents = min(len(baseline.presented), len(candidate.presented))
    for position in range(shared_presents):
        kind = frame_difference_kind(
            baseline=baseline.presented[position], candidate=candidate.presented[position]
        )
        if kind is not None:
            return _difference(
                baseline=baseline,
                candidate=candidate,
                baseline_position=position,
                candidate_position=position,
                kind=kind,
            )
    if len(baseline.presented) != len(candidate.presented):
        return _difference(
            baseline=baseline,
            candidate=candidate,
            baseline_position=shared_presents,
            candidate_position=shared_presents,
            kind='present count',
        )
    kind = frame_difference_kind(baseline=baseline.final, candidate=candidate.final)
    if kind is not None and not (baseline.final_on_run_driver and candidate.final_on_run_driver):
        # A final display missing or on another driver (a --headless engine moved it) is not
        # that run's own picture
        kind = None
    if kind is None:
        if baseline.outcome == candidate.outcome:
            return None
        kind = 'outcome'
    return _difference(
        baseline=baseline,
        candidate=candidate,
        baseline_position=len(baseline.presented),
        candidate_position=len(candidate.presented),
        kind=kind,
    )


def frame_difference_kind(
    *,
    baseline: FrameFingerprint | None,
    candidate: FrameFingerprint | None,
) -> str | None:
    """Tell how two fingerprints of the same frame differ.

    Args:
        baseline: The baseline run's frame (None: no display).
        candidate: The other run's frame.

    Returns:
        None when they match, else ``'display'``, ``'size'`` or ``'pixels'``.

    """
    if baseline == candidate:
        return None
    if baseline is None or candidate is None:
        return 'display'
    if (baseline.width, baseline.height) != (candidate.width, candidate.height):
        return 'size'
    return 'pixels'


def _difference(
    *,
    baseline: RecordedFrames,
    candidate: RecordedFrames,
    baseline_position: int,
    candidate_position: int,
    kind: str,
) -> FrameSequenceDifference:
    """Build a FrameSequenceDifference from both records.

    Returns:
        The difference.

    """
    return FrameSequenceDifference(
        nodeid=baseline.nodeid,
        baseline_position=baseline_position,
        candidate_position=candidate_position,
        kind=kind,
        baseline_frame_count=len(baseline.frames),
        candidate_frame_count=len(candidate.frames),
        baseline_outcome=baseline.outcome,
        candidate_outcome=candidate.outcome,
    )


def compare_runs(
    *, baseline: dict[str, RecordedFrames], candidate: dict[str, RecordedFrames]
) -> tuple[list[FrameSequenceDifference], list[str], list[str]]:
    """Compare every test two runs share, and list the tests only one of them recorded.

    Args:
        baseline: The baseline run's records by node id.
        candidate: The other run's records by node id.

    Tests marked frames_vary in either run are not compared (``frames_vary_tests``).

    Returns:
        The differences (sorted by node id), the node ids only in the baseline, and those only
        in the candidate (both sorted).

    """
    not_compared = frames_vary_tests(baseline, candidate)
    differences = [
        difference
        for nodeid in sorted(baseline.keys() & candidate.keys() - not_compared.keys())
        if (difference := compare_frames(baseline=baseline[nodeid], candidate=candidate[nodeid]))
        is not None
    ]
    only_in_baseline = sorted(baseline.keys() - candidate.keys())
    only_in_candidate = sorted(candidate.keys() - baseline.keys())
    return differences, only_in_baseline, only_in_candidate


def frames_vary_tests(*runs: dict[str, RecordedFrames]) -> dict[str, str]:
    """Return the tests marked frames_vary in any of the runs, with their reasons.

    Args:
        *runs: Runs' records by node id.

    Returns:
        The marked tests' reasons by node id, sorted by node id.

    """
    reasons = {
        nodeid: record.frames_vary_reason
        for records in runs
        for nodeid, record in records.items()
        if record.frames_vary_reason is not None
    }
    return dict(sorted(reasons.items()))


def compare_repeats(*, label: str, runs: Sequence[dict[str, RecordedFrames]]) -> RepeatComparison:
    """Find the tests whose frames differ between runs on the same driver.

    Each later run is compared with the first; a test that differs in any of them is listed
    once, with its first difference found.

    Args:
        label: The driver the runs share.
        runs: The runs' records, at least one.

    Returns:
        The nondeterministic tests.

    """
    differences: dict[str, FrameSequenceDifference] = {}
    recorded_in_some_runs: set[str] = set()
    first_run = runs[0]
    for later_run in runs[1:]:
        found, only_in_first, only_in_later = compare_runs(baseline=first_run, candidate=later_run)
        for difference in found:
            differences.setdefault(difference.nodeid, difference)
        recorded_in_some_runs.update(only_in_first, only_in_later)
    return RepeatComparison(
        label=label,
        run_count=len(runs),
        differences=tuple(differences[nodeid] for nodeid in sorted(differences)),
        recorded_in_some_runs=tuple(sorted(recorded_in_some_runs)),
    )


def compare_labelled_runs(
    *, runs: Sequence[LabelledRun]
) -> tuple[list[RepeatComparison], list[DriverComparison]]:
    """Compare runs by label: repeats on each driver, then each driver with the first one.

    Args:
        runs: The runs; the first one's label is the baseline driver.

    Returns:
        The repeat comparisons (one per label run more than once) and the driver comparisons
        (one per other label), with nondeterministic tests left out of the latter.

    """
    records_by_label: dict[str, list[dict[str, RecordedFrames]]] = {}
    first_run_by_label: dict[str, LabelledRun] = {}
    for run in runs:
        records_by_label.setdefault(run.label, []).append(
            read_recorded_frames(directory=run.directory)
        )
        first_run_by_label.setdefault(run.label, run)
    repeats = [
        compare_repeats(label=label, runs=label_runs)
        for label, label_runs in records_by_label.items()
        if len(label_runs) > 1
    ]
    nondeterministic = frozenset[str]().union(*(repeat.nodeids for repeat in repeats))
    baseline_label = runs[0].label
    baseline_records = records_by_label[baseline_label][0]
    drivers: list[DriverComparison] = []
    for label, label_runs in records_by_label.items():
        if label == baseline_label:
            continue
        differences, only_in_baseline, only_in_candidate = compare_runs(
            baseline=baseline_records, candidate=label_runs[0]
        )
        drivers.append(
            DriverComparison(
                baseline=first_run_by_label[baseline_label],
                candidate=first_run_by_label[label],
                tests_in_both=len(baseline_records.keys() & label_runs[0].keys()),
                differences=tuple(
                    difference
                    for difference in differences
                    if difference.nodeid not in nondeterministic
                ),
                only_in_baseline=tuple(only_in_baseline),
                only_in_candidate=tuple(only_in_candidate),
                frames_vary=frames_vary_tests(baseline_records, label_runs[0]),
            )
        )
    return repeats, drivers


def image_request_for(*, drivers: Sequence[DriverComparison]) -> FrameImageRequest:
    """Name the frames to save in a re-run of the differing tests, and where it may stop.

    A window around each test's first difference (``image_request_for_differences``).

    Args:
        drivers: The driver comparisons.

    Returns:
        The request, by node id.

    """
    return image_request_for_differences(
        differences=[difference for driver in drivers for difference in driver.differences]
    )


def image_request_for_differences(
    *, differences: Iterable[FrameSequenceDifference]
) -> FrameImageRequest:
    """Name the frames to save in a re-run of the tests these differences are in.

    Each difference's window: ``IMAGE_WINDOW_PRESENTS`` frames before and after its first
    differing frame, in both runs (from the first present to the final frame), so the images
    show what led up to the difference and what followed. A test cannot skip to its first
    difference, but its re-run need not play on past the window: when every frame of every
    window of the test is a present in both runs, the request says where the re-run may stop
    (``stop_after_by_test``, the window's last present). Otherwise (the window reaches the final
    frame, which only the test's end shows) both runs' final frames are saved too and the test
    runs to its end. A test in several differences (several driver pairs) has all their frames,
    and stops only if every one of them could.

    Args:
        differences: The differences.

    Returns:
        The request, by node id.

    """
    positions_by_test: dict[str, set[int]] = {}
    stop_after_by_test: dict[str, int] = {}
    runs_to_its_end: set[str] = set()
    for difference in differences:
        nodeid = difference.nodeid
        baseline_final = difference.baseline_frame_count - 1
        candidate_final = difference.candidate_frame_count - 1
        window = [
            (difference.baseline_position + offset, difference.candidate_position + offset)
            for offset in range(-IMAGE_WINDOW_PRESENTS, IMAGE_WINDOW_PRESENTS + 1)
        ]
        window = [
            (baseline, candidate)
            for baseline, candidate in window
            if 0 <= baseline <= baseline_final and 0 <= candidate <= candidate_final
        ]
        positions = positions_by_test.setdefault(nodeid, set())
        positions.update(position for pair in window for position in pair)
        if all(
            baseline < baseline_final and candidate < candidate_final
            for baseline, candidate in window
        ):
            last = max(position for pair in window for position in pair)
            stop_after_by_test[nodeid] = max(last, stop_after_by_test.get(nodeid, last))
        else:
            positions.update({baseline_final, candidate_final})
            runs_to_its_end.add(nodeid)
    return FrameImageRequest(
        positions_by_test={
            nodeid: tuple(sorted(positions))
            for nodeid, positions in sorted(positions_by_test.items())
        },
        stop_after_by_test={
            nodeid: stop
            for nodeid, stop in sorted(stop_after_by_test.items())
            if nodeid not in runs_to_its_end
        },
    )


def comparison_report(
    *, repeats: Sequence[RepeatComparison], drivers: Sequence[DriverComparison]
) -> str:
    """Write the compare command's report.

    Args:
        repeats: The repeat comparisons.
        drivers: The driver comparisons.

    Returns:
        The report, one item per line.

    """
    lines: list[str] = []
    for driver in drivers:
        baseline, candidate = driver.baseline, driver.candidate
        lines.extend((
            (
                f'{baseline.label} ({baseline.directory}) vs {candidate.label} '
                f'({candidate.directory}): {driver.tests_in_both} tests in both'
            ),
            f'  Driver differences: {len(driver.differences)}',
        ))
        lines.extend(
            f'    {difference.nodeid}: {difference.describe()}' for difference in driver.differences
        )
        for label, nodeids in (
            (baseline.label, driver.only_in_baseline),
            (candidate.label, driver.only_in_candidate),
        ):
            lines.append(f'  Recorded on {label} only: {len(nodeids)}')
            lines.extend(f'    {nodeid}' for nodeid in nodeids)
        lines.append(f'  Not compared (frames_vary): {len(driver.frames_vary)}')
        lines.extend(f'    {nodeid}: {reason}' for nodeid, reason in driver.frames_vary.items())
    for repeat in repeats:
        lines.append(
            f'Nondeterministic on {repeat.label} ({repeat.run_count} runs; not counted as '
            f'driver differences): {len(repeat.nodeids)}'
        )
        lines.extend(
            f'    {difference.nodeid}: {difference.describe()}' for difference in repeat.differences
        )
        lines.extend(
            f'    {nodeid}: recorded in some runs only' for nodeid in repeat.recorded_in_some_runs
        )
    return '\n'.join(lines) + '\n'


def compare_frame_images(
    *, baseline_image: Path, candidate_image: Path, difference_image: Path
) -> tuple[int, int] | None:
    """Count the pixels whose colour differs between two PNG frames; draw the difference.

    The difference image is the baseline frame dimmed to grey, with every differing pixel
    ``DIFFERENCE_COLOR``.

    Args:
        baseline_image: The baseline driver's frame.
        candidate_image: The other driver's frame.
        difference_image: Where the difference image is written.

    Returns:
        The differing and total pixel counts, or None when the sizes differ (no image is
        written).

    """
    baseline_surface = pygame.image.load(str(baseline_image))
    candidate_surface = pygame.image.load(str(candidate_image))
    if baseline_surface.get_size() != candidate_surface.get_size():
        return None
    width, height = baseline_surface.get_size()
    baseline_pixels = _rgb_array(surface=baseline_surface)
    candidate_pixels = _rgb_array(surface=candidate_surface)
    differing = (baseline_pixels != candidate_pixels).any(axis=2)
    grey = (baseline_pixels.mean(axis=2) * DIMMED_BRIGHTNESS).astype(np.uint8)
    difference = np.repeat(grey[:, :, np.newaxis], 3, axis=2)
    difference[differing] = DIFFERENCE_COLOR
    difference_image.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(
        pygame.image.frombytes(difference.tobytes(), (width, height), 'RGB'), str(difference_image)
    )
    return int(differing.sum()), width * height


def _rgb_array(*, surface: pygame.Surface) -> np.ndarray[tuple[int, int, int], np.dtype[np.uint8]]:
    """Return a surface's colours as a (height, width, 3) array.

    Returns:
        The red, green and blue bytes, row by row.

    """
    width, height = surface.get_size()
    return np.frombuffer(pygame.image.tobytes(surface, 'RGB'), dtype=np.uint8).reshape(
        height, width, 3
    )


def compare_rerun_images(
    *,
    baseline: LabelledRun,
    candidate: LabelledRun,
    baseline_record: RecordedFrames,
    candidate_record: RecordedFrames,
    output: Path,
) -> tuple[FrameSequenceDifference | None, list[FrameImageComparison], WindowAnimations | None]:
    """Compare one re-run test's saved frames: its first difference, its window and its end.

    The first differing frame comes first, then the other frames of its window that both
    re-runs saved (the frames around it, for context), then the final frames when they differ
    and are not among those. A re-run stopped after its window (``RecordedFrames.stopped_after``)
    has no final frames.

    Both drivers' images are copied to ``output/<test folder>/`` as ``<label>-frame-<N>.png``,
    next to ``difference-frame-<N>.png`` (named by the baseline's position). The window's
    presents are also played as animations, ``<label>-window.apng`` and
    ``difference-window.apng`` (``write_window_animations``).

    Args:
        baseline: The baseline driver's re-run.
        candidate: The other driver's re-run.
        baseline_record: The test's record in the baseline re-run.
        candidate_record: The test's record in the other re-run.
        output: The report folder.

    Returns:
        The re-run's difference (None when its frames all match: the difference did not
        reproduce), the image comparisons made, and the window's animations (None when fewer
        than two of its presents were compared as images).

    """
    difference = compare_frames(baseline=baseline_record, candidate=candidate_record)
    if difference is None:
        return None, [], None
    nodeid = baseline_record.nodeid
    final_positions = (len(baseline_record.frames) - 1, len(candidate_record.frames) - 1)
    positions = _rerun_positions(
        difference=difference,
        runs=(baseline, candidate),
        records=(baseline_record, candidate_record),
        final_positions=final_positions,
    )
    test_folder = output / images_folder_name(nodeid=nodeid)
    comparisons: list[FrameImageComparison] = []
    for baseline_position, candidate_position in positions:
        position_name = frame_position_name(
            position=baseline_position, frame_count=len(baseline_record.frames)
        )
        baseline_copy = _copy_frame_image(
            run=baseline, nodeid=nodeid, position=baseline_position, test_folder=test_folder
        )
        candidate_copy = _copy_frame_image(
            run=candidate, nodeid=nodeid, position=candidate_position, test_folder=test_folder
        )
        if baseline_copy is None or candidate_copy is None:
            comparisons.append(
                FrameImageComparison(
                    position_name=position_name,
                    position=baseline_position,
                    is_final=(baseline_position, candidate_position) == final_positions,
                    baseline_image=baseline_copy,
                    candidate_image=candidate_copy,
                    difference_image=None,
                    differing_pixels=None,
                    total_pixels=None,
                    note='no image saved on both drivers (no display, or not requested)',
                )
            )
            continue
        difference_image = test_folder / f'difference-frame-{baseline_position}.png'
        counts = compare_frame_images(
            baseline_image=baseline_copy,
            candidate_image=candidate_copy,
            difference_image=difference_image,
        )
        comparisons.append(
            FrameImageComparison(
                position_name=position_name,
                position=baseline_position,
                is_final=(baseline_position, candidate_position) == final_positions,
                baseline_image=baseline_copy,
                candidate_image=candidate_copy,
                difference_image=None if counts is None else difference_image,
                differing_pixels=None if counts is None else counts[0],
                total_pixels=None if counts is None else counts[1],
                note='sizes differ' if counts is None else '',
            )
        )
    animations = write_window_animations(
        comparisons=comparisons,
        test_folder=test_folder,
        baseline_label=baseline.label,
        candidate_label=candidate.label,
    )
    return difference, comparisons, animations


def _rerun_positions(
    *,
    difference: FrameSequenceDifference,
    runs: tuple[LabelledRun, LabelledRun],
    records: tuple[RecordedFrames, RecordedFrames],
    final_positions: tuple[int, int],
) -> list[tuple[int, int]]:
    """Choose a re-run test's frames to compare: first difference, saved window, final frames.

    Args:
        difference: The re-run's first difference.
        runs: The baseline and the other re-run.
        records: The test's record in each.
        final_positions: Each record's final frame position.

    Returns:
        The (baseline, other) positions, the first difference first.

    """
    baseline, candidate = runs
    baseline_record, candidate_record = records
    nodeid = baseline_record.nodeid
    first = (difference.baseline_position, difference.candidate_position)
    positions = [first]
    context = [
        (first[0] + offset, first[1] + offset)
        for offset in range(-IMAGE_WINDOW_PRESENTS, IMAGE_WINDOW_PRESENTS + 1)
        if offset and first[0] + offset >= 0 and first[1] + offset >= 0
    ]
    positions.extend(
        pair
        for pair in context
        if pair != final_positions
        and frame_image_path(
            directory=baseline.directory, nodeid=nodeid, position=pair[0]
        ).is_file()
        and frame_image_path(
            directory=candidate.directory, nodeid=nodeid, position=pair[1]
        ).is_file()
    )
    stopped = (
        baseline_record.stopped_after is not None or candidate_record.stopped_after is not None
    )
    final_frames_differ = (
        frame_difference_kind(baseline=baseline_record.final, candidate=candidate_record.final)
        is not None
    )
    if not stopped and final_frames_differ and final_positions not in positions:
        positions.append(final_positions)
    return positions


def write_window_animations(
    *,
    comparisons: Sequence[FrameImageComparison],
    test_folder: Path,
    baseline_label: str,
    candidate_label: str,
) -> WindowAnimations | None:
    """Play a re-run test's window of presents as animated PNGs: each driver's and the difference.

    The frames are the presents compared as images of one size on both drivers, in order (the
    final frame is left out: it is not part of the window's sequence), each shown for
    ``WINDOW_ANIMATION_FRAME_MILLISECONDS``, looping. Written with Pillow, an engine dependency.

    Args:
        comparisons: The test's image comparisons.
        test_folder: The test's report folder (holding the compared images).
        baseline_label: The baseline driver's label.
        candidate_label: The other driver's label.

    Returns:
        The animations, or None when fewer than ``WINDOW_ANIMATION_MINIMUM_FRAMES`` presents
        were compared.

    """
    frames = sorted(
        (
            comparison
            for comparison in comparisons
            if not comparison.is_final
            and comparison.baseline_image is not None
            and comparison.candidate_image is not None
            and comparison.difference_image is not None
        ),
        key=lambda comparison: comparison.position,
    )
    if len(frames) < WINDOW_ANIMATION_MINIMUM_FRAMES:
        return None
    animations = WindowAnimations(
        first_position=frames[0].position,
        last_position=frames[-1].position,
        frame_count=len(frames),
        baseline_animation=test_folder / f'{baseline_label}-window.apng',
        candidate_animation=test_folder / f'{candidate_label}-window.apng',
        difference_animation=test_folder / 'difference-window.apng',
    )
    for path, images in (
        (animations.baseline_animation, [frame.baseline_image for frame in frames]),
        (animations.candidate_animation, [frame.candidate_image for frame in frames]),
        (animations.difference_animation, [frame.difference_image for frame in frames]),
    ):
        _write_animation(path=path, images=[image for image in images if image is not None])
    return animations


def _write_animation(*, path: Path, images: Sequence[Path]) -> None:
    """Write PNG images as one looping animated PNG.

    Args:
        path: The animation (``.apng``).
        images: The frames, in order, all of one size.

    """
    frames = [Image.open(image).convert('RGB') for image in images]
    frames[0].save(
        path,
        format='PNG',
        save_all=True,
        append_images=frames[1:],
        duration=WINDOW_ANIMATION_FRAME_MILLISECONDS,
        loop=0,
    )


def _copy_frame_image(
    *, run: LabelledRun, nodeid: str, position: int, test_folder: Path
) -> Path | None:
    """Copy a re-run's saved frame into the report folder as ``<label>-frame-<N>.png``.

    Returns:
        The copy, or None when the re-run saved no image at that position.

    """
    source = frame_image_path(directory=run.directory, nodeid=nodeid, position=position)
    if not source.is_file():
        return None
    test_folder.mkdir(parents=True, exist_ok=True)
    copy = test_folder / f'{run.label}-frame-{position}.png'
    shutil.copyfile(source, copy)
    return copy


def images_report(
    *,
    request: FrameImageRequest,
    baseline: LabelledRun,
    candidate: LabelledRun,
    output: Path,
) -> str:
    """Compare a re-run's images for every requested test and write the images command's report.

    Args:
        request: The tests (and frames) the re-run saved.
        baseline: The baseline driver's re-run.
        candidate: The other driver's re-run.
        output: The report folder.

    Returns:
        The report.

    """
    baseline_records = read_recorded_frames(directory=baseline.directory)
    candidate_records = read_recorded_frames(directory=candidate.directory)
    lines = [
        (
            f'Re-run of {len(request.positions_by_test)} tests: {baseline.label} '
            f'({baseline.directory}) vs {candidate.label} ({candidate.directory}); '
            f'images in {output}'
        )
    ]
    for nodeid in request.positions_by_test:
        baseline_record = baseline_records.get(nodeid)
        candidate_record = candidate_records.get(nodeid)
        if baseline_record is None or candidate_record is None:
            lines.append(f'  {nodeid}: not recorded in both re-runs')
            continue
        difference, comparisons, animations = compare_rerun_images(
            baseline=baseline,
            candidate=candidate,
            baseline_record=baseline_record,
            candidate_record=candidate_record,
            output=output,
        )
        if difference is None:
            lines.append(
                f'  {nodeid}: the difference did not reproduce in the re-run (it depends on '
                'the tests that ran before it)'
            )
            continue
        lines.extend((
            f'  {nodeid}: {difference.describe()}',
            f'    images: {output / images_folder_name(nodeid=nodeid)}',
        ))
        lines.extend(
            _describe_image_comparison(comparison=comparison) for comparison in comparisons
        )
        if animations is not None:
            lines.append(
                f'    the window as animations, presents {animations.first_position} to '
                f'{animations.last_position} ({animations.frame_count} frames): '
                f'{animations.baseline_animation.name}, {animations.candidate_animation.name}, '
                f'{animations.difference_animation.name}'
            )
    return '\n'.join(lines) + '\n'


def _describe_image_comparison(*, comparison: FrameImageComparison) -> str:
    """Describe one frame's image comparison in a report line.

    Returns:
        The line: the pixel count and the images' file names (in the test's images folder),
        or why there is no count.

    """
    images = ', '.join(
        path.name
        for path in (
            comparison.baseline_image,
            comparison.candidate_image,
            comparison.difference_image,
        )
        if path is not None
    )
    if comparison.differing_pixels is None or comparison.total_pixels is None:
        summary = comparison.note
    else:
        summary = f'{comparison.differing_pixels} of {comparison.total_pixels} pixels differ'
    return f'    {comparison.position_name}: {summary}' + (f' ({images})' if images else '')
