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


class FrameImageComparison(BaseModel):
    """One frame of a re-run test on both drivers, as images."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    position_name: str
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
    """Name the frames to save in a re-run of the differing tests.

    Each test's first differing frame (in both runs) and both runs' final frames.

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

    Each difference's first differing frame (in both runs) and both runs' final frames; a test
    in several differences (several driver pairs) has all their frames.

    Args:
        differences: The differences.

    Returns:
        The request, by node id.

    """
    positions_by_test: dict[str, set[int]] = {}
    for difference in differences:
        positions_by_test.setdefault(difference.nodeid, set()).update({
            difference.baseline_position,
            difference.candidate_position,
            difference.baseline_frame_count - 1,
            difference.candidate_frame_count - 1,
        })
    return FrameImageRequest(
        positions_by_test={
            nodeid: tuple(sorted(positions))
            for nodeid, positions in sorted(positions_by_test.items())
        }
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
) -> tuple[FrameSequenceDifference | None, list[FrameImageComparison]]:
    """Compare one re-run test's saved frames: its first differing frame and its final frames.

    The final frames are compared too when they differ (and are not the first difference).

    Both drivers' images are copied to ``output/<test folder>/`` as ``<label>-frame-<N>.png``,
    next to ``difference-frame-<N>.png`` (named by the baseline's position).

    Args:
        baseline: The baseline driver's re-run.
        candidate: The other driver's re-run.
        baseline_record: The test's record in the baseline re-run.
        candidate_record: The test's record in the other re-run.
        output: The report folder.

    Returns:
        The re-run's difference (None when its frames all match: the difference did not
        reproduce) and the image comparisons made.

    """
    difference = compare_frames(baseline=baseline_record, candidate=candidate_record)
    if difference is None:
        return None, []
    nodeid = baseline_record.nodeid
    positions = [(difference.baseline_position, difference.candidate_position)]
    final_positions = (len(baseline_record.frames) - 1, len(candidate_record.frames) - 1)
    final_frames_differ = (
        frame_difference_kind(baseline=baseline_record.final, candidate=candidate_record.final)
        is not None
    )
    if final_frames_differ and final_positions not in positions:
        positions.append(final_positions)
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
                baseline_image=baseline_copy,
                candidate_image=candidate_copy,
                difference_image=None if counts is None else difference_image,
                differing_pixels=None if counts is None else counts[0],
                total_pixels=None if counts is None else counts[1],
                note='sizes differ' if counts is None else '',
            )
        )
    return difference, comparisons


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
        difference, comparisons = compare_rerun_images(
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
