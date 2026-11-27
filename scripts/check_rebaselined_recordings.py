r"""Check a reviewed re-record: every rebaselined recording changed only as its plan allows.

A reviewed re-record (plans/2026-11-20-game-code-into-the-engine.md, Sub-plan 3, part C) replays
each recording under the change with ``--replay-trace OLD --rebaseline NEW --headless`` and
replaces OLD with NEW only once this check passes. It has two parts:

- The recordings. A plan file (TOML) lists each pair, OLD and NEW, with what may differ between
  them (``RecordingAllowances``: new sprite ids, new internal event types, named fields).
  Each pair is compared by glitchygames/replay/recording_differences.py, whose docstring says
  what is and is not compared; a pair fails on any other difference, and on an allowance that
  matched nothing. Paths are relative to the current directory (run it from the repository
  root). Write a Windows path in single quotes (a TOML literal string) or with forward slashes:
  in double quotes its backslashes are escapes, and ``C:\Users`` is refused as unusable::

      [[pair]]
      old = "build/re-record/old/golden-classic.jsonl.gz"
      new = "src/games/brave-adventurer/tests/fixtures/replays/golden-classic.jsonl.gz"

      [pair.allowances]
      sprite_ids = ["HudLabel#0", "HudLabel#1", "HudLabel#2", "HudLabel#3"]
      # or, for sprites OLD already has that are drawn at another size or place:
      # sprite_ids_whose_rect_changes = ["HudLabel#0", "HudLabel#1"]

      [[pair.allowances.fields]]
      where = ["frame", 291, "scene_start", "arguments", "run"]
      reason = "FeatureCardScene gained run (#215) after the recording was made"

      [[pixels.only_after]]
      nodeid = "src/games/clockwork-keep/tests/test_clockwork_keep.py::TestHud::test_..."
      reason = "a new test of the HUD labels"

- The pixels, always (``--fingerprints-before DIR`` and ``--fingerprints-after DIR`` are
  required): the records of an allowed sprite are not compared, so a new sprite one pixel off
  would pass the recordings' part; the pixels are what checks where it is drawn. Two runs of
  the suite under the frame fingerprints plugin (glitchygames/testing/frame_fingerprints.py),
  one on the commit before the change and one on the change. Every test both ran must present
  the same frames (glitchygames/testing/frame_comparison.py, the comparison
  ``compare_driver_frames.py`` uses), and the report counts the frames compared, so a pass is
  known to have compared something. Tests marked ``frames_vary`` are not compared, and are
  counted. No test may be in one run only unless the plan names it (``PixelAllowances``:
  ``[[pixels.only_before]]`` for a test the change removes or renames, ``[[pixels.only_after]]``
  for one it adds or renames, each with a reason); an allowance whose test is in both runs, or
  in neither, fails, as an unused recording allowance does.

- Pixels a change alters on purpose (a HUD in another font). ``[[pixels.changed]]`` names a test
  whose frames may differ, with a reason and the boxes they may differ in
  (``within = [[x, y, width, height], ...]``). Fingerprints are hashes, so the check judges such
  a test from saved images: it must present as many frames as before with the same outcome,
  and every frame whose fingerprint differs (not only the first) must differ only inside the
  boxes, judged from PNG files of both runs. ``--write-image-request FILE`` writes the frames
  needed; re-run those tests on each commit with ``--frame-images-request FILE`` and a new
  ``--frame-fingerprints DIR``, and pass the two directories as ``--images-before`` and
  ``--images-after``. Without them, or with an image missing or of another size, the test
  fails; an allowance whose test did not differ fails as unmet::

      [[pixels.changed]]
      nodeid = "src/games/clockwork-keep/tests/test_clockwork_keep.py::test_main_runs_the_game_..."
      reason = "the HUD is Vera Bold 16"
      within = [[10, 10, 103, 22], [690, 10, 74, 22]]

It prints one report per pair, the pixel report, and a summary, and exits
``ExitCode.SUCCESS`` when everything passed, ``ExitCode.REPLAY_DIVERGED`` when anything differed,
``ExitCode.MISSING_INPUT`` for a missing file or directory, and ``ExitCode.UNUSABLE_INPUT`` for
an unusable plan or recording, or a fingerprints run that recorded no test.

Usage:
    uv run python -m scripts.check_rebaselined_recordings --plan PLAN.toml \
        --fingerprints-before DIR --fingerprints-after DIR [--limit N] \
        [--write-image-request FILE] [--images-before DIR --images-after DIR]
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pydantic
import pygame

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.recording_differences import (
    REPORT_LIMIT,
    RecordingAllowances,
    RecordingComparison,
    compare_recordings,
)
from glitchygames.testing.frame_comparison import (
    compare_runs,
    frame_difference_kind,
    frames_vary_tests,
)
from glitchygames.testing.frame_fingerprints import (
    FrameImageRequest,
    RecordedFrames,
    frame_image_path,
    read_recorded_frames,
)
from glitchygames.tracing import TraceFormatError

if TYPE_CHECKING:
    from collections.abc import Sequence


class RecordingPair(pydantic.BaseModel):
    """One recording before the change and its rebaseline, with what may differ."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    old: Path
    new: Path
    allowances: RecordingAllowances = RecordingAllowances()


class AllowedTest(pydantic.BaseModel):
    """A test the pixel step may find in one run only: one the change adds, renames or removes."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    nodeid: str
    # Why it is in one run only (for the reviewer)
    reason: str


class ChangedTest(pydantic.BaseModel):
    """A test whose frames the change may alter, but only inside the named boxes."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    nodeid: str
    # Why its frames change (for the reviewer)
    reason: str
    # Where they may change: boxes of [x, y, width, height] in screen pixels
    within: tuple[tuple[int, int, int, int], ...] = pydantic.Field(min_length=1)


class PixelAllowances(pydantic.BaseModel):
    """The tests the change adds, renames or removes, and those whose frames it may alter."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    only_before: tuple[AllowedTest, ...] = ()
    only_after: tuple[AllowedTest, ...] = ()
    changed: tuple[ChangedTest, ...] = ()


class ImageRuns(pydantic.BaseModel):
    """The re-runs that saved the changed tests' differing frames as PNG files."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    before: Path
    after: Path


class CheckPlan(pydantic.BaseModel):
    """Every pair a re-record replaces, and the tests the change adds, renames or removes."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    pair: tuple[RecordingPair, ...] = pydantic.Field(min_length=1)
    pixels: PixelAllowances = PixelAllowances()


class PixelComparison(pydantic.BaseModel):
    """The suite's frames before and after the change."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    tests_compared: int
    frames_compared: int
    differing_tests: tuple[str, ...]
    # Tests in one run only that the plan does not allow
    only_before: tuple[str, ...]
    only_after: tuple[str, ...]
    not_compared: tuple[str, ...]
    # Tests in one run only that the plan allows, and allowances that matched no such test
    allowed: tuple[str, ...] = ()
    unused_allowances: tuple[str, ...] = ()
    # Changed tests whose every differing frame changed inside their boxes, as report lines,
    # and what failed of the others
    changed_inside_boxes: tuple[str, ...] = ()
    changed_failures: tuple[str, ...] = ()
    # Every differing frame of each changed test: the image request their judging needs
    image_request: FrameImageRequest = FrameImageRequest(positions_by_test={})

    @property
    def passed(self) -> bool:
        """Whether every test both runs recorded presented the same frames, and none is missing.

        A test in one run only passes when the plan allows it; an allowance that matched no such
        test fails, as an unused recording allowance does.
        """
        return not (
            self.differing_tests
            or self.only_before
            or self.only_after
            or self.unused_allowances
            or self.changed_failures
        )

    def report(self) -> str:
        """Return the verdict and every test that differs or is in one run only.

        Returns:
            The report, one item per line.

        """
        verdict = 'PASS' if self.passed else 'FAIL'
        differing = len(self.differing_tests) or 'none'
        counts = f'{self.tests_compared} tests, {self.frames_compared} frames compared'
        lines = [f'{verdict} pixels: {counts}, {differing} differ']
        if self.not_compared:
            lines.append(f'  not compared (frames_vary): {len(self.not_compared)} tests')
        lines.extend(f'  differs: {nodeid}' for nodeid in self.differing_tests)
        lines.extend(f'  only before: {nodeid}' for nodeid in self.only_before)
        lines.extend(f'  only after: {nodeid}' for nodeid in self.only_after)
        lines.extend(f'  allowed {line}' for line in self.allowed)
        lines.extend(f'  allowed changed: {line}' for line in self.changed_inside_boxes)
        lines.extend(f'  {line}' for line in self.changed_failures)
        lines.extend(f'  allowance not met: {label}' for label in self.unused_allowances)
        return '\n'.join(lines)


class NoTestsRecordedError(Exception):
    """A fingerprints run recorded no test: comparing it would compare nothing (BUGS.md #256)."""


def load_plan(*, path: Path) -> CheckPlan:
    """Read and validate a plan file.

    Args:
        path: The plan (TOML).

    Returns:
        The plan.

    """
    with path.open('rb') as plan_file:
        return CheckPlan.model_validate(tomllib.load(plan_file))


def compare_pixels(
    *,
    before: Path,
    after: Path,
    allowances: PixelAllowances | None = None,
    images: ImageRuns | None = None,
) -> PixelComparison:
    """Compare two fingerprints runs of the suite, test by test.

    A run that recorded no test is refused (``NoTestsRecordedError``, from ``_read_runs``).

    Args:
        before: The run on the commit before the change.
        after: The run on the change.
        allowances: The tests the plan allows in one run only or changed (None: none).
        images: The re-runs holding the changed tests' differing frames (None: not given).

    Returns:
        The comparison.

    """
    before_records, after_records = _read_runs(before=before, after=after)
    differences, only_before, only_after = compare_runs(
        baseline=before_records, candidate=after_records
    )
    plan = allowances or PixelAllowances()
    unallowed_before, unallowed_after, allowed, unused = _apply_allowances(
        only_before=only_before, only_after=only_after, allowances=plan
    )
    differing = {difference.nodeid for difference in differences}
    changed = _judge_changed_tests(
        changed_tests=plan.changed,
        differing=differing,
        before_records=before_records,
        after_records=after_records,
        images=images,
    )
    not_compared = frames_vary_tests(before_records, after_records)
    compared = sorted(before_records.keys() & after_records.keys() - not_compared.keys())
    frames_compared = sum(
        len(before_records[nodeid].presented) + (before_records[nodeid].final is not None)
        for nodeid in compared
    )
    return PixelComparison(
        tests_compared=len(compared),
        frames_compared=frames_compared,
        differing_tests=tuple(
            difference.nodeid
            for difference in differences
            if difference.nodeid not in changed.allowed_nodeids
        ),
        only_before=unallowed_before,
        only_after=unallowed_after,
        not_compared=tuple(sorted(not_compared)),
        allowed=allowed,
        unused_allowances=(*unused, *changed.unused_allowances),
        changed_inside_boxes=changed.inside_boxes,
        changed_failures=changed.failures,
        image_request=FrameImageRequest(positions_by_test=changed.positions_by_test),
    )


def _read_runs(
    *, before: Path, after: Path
) -> tuple[dict[str, RecordedFrames], dict[str, RecordedFrames]]:
    """Read both fingerprints runs, refusing one that recorded no test.

    Returns:
        The before and after runs' records by node id.

    Raises:
        NoTestsRecordedError: A run recorded no test.

    """
    before_records = read_recorded_frames(directory=before)
    after_records = read_recorded_frames(directory=after)
    for label, records, directory in (
        ('before', before_records, before),
        ('after', after_records, after),
    ):
        if not records:
            message = f'Nothing compared: the {label} run ({directory}) recorded no test'
            raise NoTestsRecordedError(message)
    return before_records, after_records


class _ChangedTestsVerdict(pydantic.BaseModel):
    """What the changed tests' allowances found."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    # The differing tests an allowance covers (their failures, if any, are in failures)
    allowed_nodeids: frozenset[str]
    inside_boxes: tuple[str, ...]
    failures: tuple[str, ...]
    unused_allowances: tuple[str, ...]
    positions_by_test: dict[str, tuple[int, ...]]


def _judge_changed_tests(
    *,
    changed_tests: Sequence[ChangedTest],
    differing: set[str],
    before_records: dict[str, RecordedFrames],
    after_records: dict[str, RecordedFrames],
    images: ImageRuns | None,
) -> _ChangedTestsVerdict:
    """Judge each changed test's differing frames from the saved images.

    A changed test must present as many frames as before, with the same outcome, so only its
    pixels changed; then every frame whose fingerprint differs (not only the first) is loaded
    from both image runs, and any differing pixel outside its boxes fails it.

    Returns:
        The verdict.

    """
    allowed: set[str] = set()
    inside: list[str] = []
    failures: list[str] = []
    unused: list[str] = []
    positions_by_test: dict[str, tuple[int, ...]] = {}
    for test in changed_tests:
        if test.nodeid not in differing:
            unused.append(f'changed {test.nodeid}')
            continue
        allowed.add(test.nodeid)
        before_record = before_records[test.nodeid]
        after_record = after_records[test.nodeid]
        if (
            len(before_record.presented) != len(after_record.presented)
            or before_record.outcome != after_record.outcome
        ):
            failures.append(f'changed more than its pixels: {test.nodeid}')
            continue
        positions = _differing_positions(before=before_record, after=after_record)
        positions_by_test[test.nodeid] = positions
        if images is None:
            failures.append(f'changed, no images given: {test.nodeid} ({len(positions)} frames)')
            continue
        test_failures, differing_pixels = _judge_frames(
            test=test, positions=positions, images=images
        )
        failures.extend(test_failures)
        if not test_failures:
            inside.append(
                f'{test.nodeid} ({len(positions)} frames, {differing_pixels} pixels differ, all '
                f'inside its boxes; {test.reason})'
            )
    return _ChangedTestsVerdict(
        allowed_nodeids=frozenset(allowed),
        inside_boxes=tuple(inside),
        failures=tuple(failures),
        unused_allowances=tuple(unused),
        positions_by_test=positions_by_test,
    )


def _differing_positions(*, before: RecordedFrames, after: RecordedFrames) -> tuple[int, ...]:
    """Return every frame position whose fingerprints differ (presents, then the final frame).

    The final frame counts only when both runs drew it on their own driver, as
    ``frame_comparison.compare_frames`` judges it.

    Returns:
        The positions, in order.

    """
    positions = [
        position
        for position, (old, new) in enumerate(zip(before.presented, after.presented, strict=True))
        if frame_difference_kind(baseline=old, candidate=new) is not None
    ]
    final_differs = frame_difference_kind(baseline=before.final, candidate=after.final) is not None
    if final_differs and before.final_on_run_driver and after.final_on_run_driver:
        positions.append(len(before.presented))
    return tuple(positions)


def _judge_frames(
    *, test: ChangedTest, positions: Sequence[int], images: ImageRuns
) -> tuple[list[str], int]:
    """Compare each differing frame's saved images, inside and outside the test's boxes.

    Returns:
        The failures (report lines) and the number of differing pixels.

    """
    failures: list[str] = []
    differing_pixels = 0
    for position in positions:
        frame = f'{test.nodeid} frame {position}'
        paths = {
            side: frame_image_path(directory=directory, nodeid=test.nodeid, position=position)
            for side, directory in (('before', images.before), ('after', images.after))
        }
        missing = [side for side, path in paths.items() if not path.is_file()]
        if missing:
            failures.append(f'changed, no image to judge: {frame} ({", ".join(missing)})')
            continue
        old_pixels = pygame.surfarray.array3d(pygame.image.load(paths['before']))
        new_pixels = pygame.surfarray.array3d(pygame.image.load(paths['after']))
        if old_pixels.shape != new_pixels.shape:
            old_width, old_height = old_pixels.shape[:2]
            new_width, new_height = new_pixels.shape[:2]
            failures.append(
                f'changed size: {frame}: {old_width}x{old_height} -> {new_width}x{new_height}'
            )
            continue
        # surfarray indexes [x, y]
        differs = np.any(old_pixels != new_pixels, axis=2)
        inside = np.zeros_like(differs)
        for x, y, width, height in test.within:
            inside[x : x + width, y : y + height] = True
        outside = int(np.count_nonzero(differs & ~inside))
        if outside:
            failures.append(f'changed outside its boxes: {frame}: {outside} pixels')
        differing_pixels += int(np.count_nonzero(differs))
    return failures, differing_pixels


def _apply_allowances(
    *, only_before: Sequence[str], only_after: Sequence[str], allowances: PixelAllowances
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Split the tests in one run only by the plan's allowances, side by side.

    Args:
        only_before: The tests found in the before run only.
        only_after: The tests found in the after run only.
        allowances: The tests the plan allows in one run only.

    Returns:
        The tests not allowed before, and after; the allowed ones as report lines; and the
        allowances that matched no test, as report labels.

    """
    unallowed: list[tuple[str, ...]] = []
    allowed: list[str] = []
    unused: list[str] = []
    for side, found, allowed_tests in (
        ('only before', only_before, allowances.only_before),
        ('only after', only_after, allowances.only_after),
    ):
        reasons = {test.nodeid: test.reason for test in allowed_tests}
        unallowed.append(tuple(nodeid for nodeid in found if nodeid not in reasons))
        allowed.extend(
            f'{side}: {nodeid} ({reasons[nodeid]})' for nodeid in found if nodeid in reasons
        )
        unused.extend(f'{side} {test.nodeid}' for test in allowed_tests if test.nodeid not in found)
    return unallowed[0], unallowed[1], tuple(allowed), tuple(unused)


def argument_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(
        description='Check that rebaselined recordings changed only as their plan allows'
    )
    parser.add_argument('--plan', type=Path, required=True, help='the pairs and allowances (TOML)')
    # Required: an allowed sprite's records are not compared, so the pixels are the only check
    # that a new sprite (a HUD label) sits where the old drawing did
    parser.add_argument(
        '--fingerprints-before',
        type=Path,
        required=True,
        help="the suite's frame fingerprints on the commit before the change",
    )
    parser.add_argument(
        '--fingerprints-after',
        type=Path,
        required=True,
        help="the suite's frame fingerprints on the change",
    )
    # The changed tests' differing frames as PNG files: re-runs of those tests on each commit
    # with --frame-images-request (the request --write-image-request writes)
    parser.add_argument(
        '--images-before',
        type=Path,
        help="a re-run on the commit before the change that saved the changed tests' frames",
    )
    parser.add_argument(
        '--images-after',
        type=Path,
        help="a re-run on the change that saved the changed tests' frames",
    )
    parser.add_argument(
        '--write-image-request',
        type=Path,
        help="write the frames the changed tests' judging needs to this file (JSON)",
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=REPORT_LIMIT,
        help=f'differences listed per recording (default {REPORT_LIMIT})',
    )
    return parser


def run(*, arguments: Sequence[str]) -> ExitCode:
    """Run the check and print its reports.

    Args:
        arguments: The command line arguments (without the program name).

    Returns:
        The exit code.

    """
    parser = argument_parser()
    options = parser.parse_args(arguments)
    if (options.images_before is None) != (options.images_after is None):
        parser.error('give --images-before and --images-after together, or neither')
    images = (
        None
        if options.images_before is None
        else ImageRuns(before=options.images_before, after=options.images_after)
    )
    try:
        plan = load_plan(path=options.plan)
        comparisons = [
            compare_recordings(old=pair.old, new=pair.new, allowances=pair.allowances)
            for pair in plan.pair
        ]
        pixels = compare_pixels(
            before=options.fingerprints_before,
            after=options.fingerprints_after,
            allowances=plan.pixels,
            images=images,
        )
    except FileNotFoundError as error:
        sys.stderr.write(f'{error}\n')
        return ExitCode.MISSING_INPUT
    except (tomllib.TOMLDecodeError, pydantic.ValidationError) as error:
        sys.stderr.write(f'unusable plan {options.plan}: {error}\n')
        return ExitCode.UNUSABLE_INPUT
    except (TraceFormatError, NoTestsRecordedError) as error:
        sys.stderr.write(f'{error}\n')
        return ExitCode.UNUSABLE_INPUT
    if options.write_image_request is not None:
        options.write_image_request.write_text(
            pixels.image_request.model_dump_json(indent=2), encoding='utf-8'
        )
    sys.stdout.write(_summary(comparisons=comparisons, pixels=pixels, limit=options.limit))
    passed = all(comparison.passed for comparison in comparisons) and pixels.passed
    return ExitCode.SUCCESS if passed else ExitCode.REPLAY_DIVERGED


def _summary(
    *, comparisons: Sequence[RecordingComparison], pixels: PixelComparison, limit: int
) -> str:
    """Return every report and the closing count.

    Returns:
        The output, ending with a newline.

    """
    reports = [comparison.report(limit=limit) for comparison in comparisons]
    reports.append(pixels.report())
    passed_count = sum(comparison.passed for comparison in comparisons)
    reports.append(f'{passed_count} of {len(comparisons)} recordings changed only as allowed')
    return '\n'.join(reports) + '\n'


def main() -> None:
    """Command line: see the module docstring."""
    sys.exit(run(arguments=sys.argv[1:]))


if __name__ == '__main__':
    main()
