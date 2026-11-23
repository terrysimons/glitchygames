r"""Check a reviewed re-record: every rebaselined recording changed only as its plan allows.

A reviewed re-record (plans/2026-11-20-game-code-into-the-engine.md, Sub-plan 3, part C) replays
each recording under the change with ``--replay-trace OLD --rebaseline NEW --headless`` and
replaces OLD with NEW only once this check passes. It has two parts:

- The recordings. A plan file (TOML) lists each pair, OLD and NEW, with what may differ between
  them (``RecordingAllowances``: new sprite ids, new internal event types, named fields).
  Each pair is compared by glitchygames/replay/recording_differences.py, whose docstring says
  what is and is not compared; a pair fails on any other difference, and on an allowance that
  matched nothing. Paths are relative to the current directory (run it from the repository
  root)::

      [[pair]]
      old = "build/re-record/old/golden-classic.jsonl.gz"
      new = "src/games/brave-adventurer/tests/fixtures/replays/golden-classic.jsonl.gz"

      [pair.allowances]
      sprite_ids = ["HudLabel#0", "HudLabel#1", "HudLabel#2", "HudLabel#3"]

      [[pair.allowances.fields]]
      where = ["frame", 291, "scene_start", "arguments", "run"]
      reason = "FeatureCardScene gained run (#215) after the recording was made"

- The pixels, always (``--fingerprints-before DIR`` and ``--fingerprints-after DIR`` are
  required): the records of an allowed sprite are not compared, so a new sprite one pixel off
  would pass the recordings' part; the pixels are what checks where it is drawn. Two runs of
  the suite under the frame fingerprints plugin (glitchygames/testing/frame_fingerprints.py),
  one on the commit before the change and one on the change. Every test both ran must present
  the same frames (glitchygames/testing/frame_comparison.py, the comparison
  ``compare_driver_frames.py`` uses), no test may be in one run only, and the report counts the
  frames compared, so a pass is known to have compared something. Tests marked ``frames_vary``
  are not compared, and are counted.

It prints one report per pair, the pixel report, and a summary, and exits
``ExitCode.SUCCESS`` when everything passed, ``ExitCode.REPLAY_DIVERGED`` when anything differed,
``ExitCode.MISSING_INPUT`` for a missing file or directory, and ``ExitCode.UNUSABLE_INPUT`` for
an unusable plan or recording, or a fingerprints run that recorded no test.

Usage:
    uv run python -m scripts.check_rebaselined_recordings --plan PLAN.toml \
        --fingerprints-before DIR --fingerprints-after DIR [--limit N]
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pydantic

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.recording_differences import (
    REPORT_LIMIT,
    RecordingAllowances,
    RecordingComparison,
    compare_recordings,
)
from glitchygames.testing.frame_comparison import compare_runs, frames_vary_tests
from glitchygames.testing.frame_fingerprints import read_recorded_frames
from glitchygames.tracing import TraceFormatError

if TYPE_CHECKING:
    from collections.abc import Sequence


class RecordingPair(pydantic.BaseModel):
    """One recording before the change and its rebaseline, with what may differ."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    old: Path
    new: Path
    allowances: RecordingAllowances = RecordingAllowances()


class CheckPlan(pydantic.BaseModel):
    """Every pair a re-record replaces."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    pair: tuple[RecordingPair, ...] = pydantic.Field(min_length=1)


class PixelComparison(pydantic.BaseModel):
    """The suite's frames before and after the change."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    tests_compared: int
    frames_compared: int
    differing_tests: tuple[str, ...]
    only_before: tuple[str, ...]
    only_after: tuple[str, ...]
    not_compared: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Whether every test both runs recorded presented the same frames, and none is missing."""
        return not (self.differing_tests or self.only_before or self.only_after)

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


def compare_pixels(*, before: Path, after: Path) -> PixelComparison:
    """Compare two fingerprints runs of the suite, test by test.

    Args:
        before: The run on the commit before the change.
        after: The run on the change.

    Returns:
        The comparison.

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
    differences, only_before, only_after = compare_runs(
        baseline=before_records, candidate=after_records
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
        differing_tests=tuple(difference.nodeid for difference in differences),
        only_before=tuple(only_before),
        only_after=tuple(only_after),
        not_compared=tuple(sorted(not_compared)),
    )


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
    options = argument_parser().parse_args(arguments)
    try:
        plan = load_plan(path=options.plan)
        comparisons = [
            compare_recordings(old=pair.old, new=pair.new, allowances=pair.allowances)
            for pair in plan.pair
        ]
        pixels = compare_pixels(
            before=options.fingerprints_before, after=options.fingerprints_after
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
