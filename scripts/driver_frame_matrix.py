r"""Compare the frames tests presented on every driver configuration with every other: a matrix.

``nox -s compare-drivers`` runs the suite on several configurations (scripts/
driver_configurations.py: dummy, cocoa, x11-macos, x11-linux, ...), each recorded by the frame
fingerprints plugin (glitchygames/testing/frame_fingerprints.py). This compares them all, pair by
pair (with glitchygames/testing/frame_comparison.py's ``compare_frames``), where
scripts/compare_driver_frames.py compares each driver with the baseline only:

- runs sharing a label are repeats on one configuration (dummy runs twice): a test whose frames
  differ between them is nondeterministic, listed apart and left out of every pair;
- every pair of configurations (in the order given; the first is the baseline) is compared:
  each test's first differing frame, or that one of them did not record the test;
- every test that differs anywhere gets its pattern: the configurations grouped by agreement
  (``cocoa differs from all others``, ``x11-macos and x11-linux differ from dummy and cocoa``).

Given re-runs of those tests that saved their frames (``--rerun LABEL=DIRECTORY``, made with
``--frame-images-request``), every differing pair's frames are compared as images too: both
PNG files and a difference image (glitchygames/testing/frame_comparison.py's) per pair under
``OUTPUT/differences/<first>-vs-<second>/<test folder>/``, and the count of differing pixels.

It writes ``OUTPUT/matrix.md`` (runs, a summary per pair, the patterns, a table per test file and
an expandable table per test with a column per pair, linking the difference images) and
``OUTPUT/matrix.json`` (the ``DriverMatrix``), and prints the pair summary and the patterns. It
reports, it does not judge: it exits ``SUCCESS`` whatever differs (``MISSING_INPUT`` for a run
directory that does not exist, ``UNUSABLE_INPUT`` for an unreadable record, ``CANNOT_WRITE_OUTPUT``
for an output that cannot be written).

A run that recorded no test (pytest ran none: ``-- --help`` or ``--collect-only`` handed to
every run exits 0 without a test) leaves nothing to compare, and a report of it would claim
every configuration agrees (BUGS.md #192): the command then writes nothing (no report, no image
request), names each such run on stderr and exits ``UNUSABLE_INPUT``.

Usage:
    uv run python -m scripts.driver_frame_matrix dummy=RUN1 dummy=RUN2 cocoa=RUN3 \\
        x11-macos=RUN4 --output DIR [--image-request FILE] [--run-seconds FILE] \\
        [--rerun dummy=RERUN1 --rerun cocoa=RERUN3 ...]
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pydantic
from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_comparison import (
    FrameImageComparison,
    FrameSequenceDifference,
    LabelledRun,
    RepeatComparison,
    compare_repeats,
    compare_rerun_images,
    compare_runs,
    frames_vary_tests,
    image_request_for_differences,
)
from glitchygames.testing.frame_fingerprints import RecordedFrames, read_recorded_frames
from scripts.compare_driver_frames import parse_labelled_run

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

MATRIX_MARKDOWN_NAME = 'matrix.md'
MATRIX_JSON_NAME = 'matrix.json'
DIFFERENCES_DIRECTORY_NAME = 'differences'
# Node ids are file::test; the file part groups the tests
NODE_FILE_SEPARATOR = '::'
# The kinds of difference compare_frames finds, in the summary's column order
DIFFERENCE_KINDS = ('pixels', 'size', 'present count', 'display', 'outcome')
OUTCOME_FAILED = 'failed'
# Two agreement groups: one side differs from the other
ONE_SIDE_AND_THE_OTHER = 2


class NoTestsRecordedError(Exception):
    """Some run recorded no test: there is nothing to compare, so no report is written."""


def runs_without_tests_message(*, runs: Sequence[RunSummary]) -> str:
    """Name the runs that recorded no test, for the refusal.

    Args:
        runs: The runs (at least one) whose ``tests_recorded`` is 0.

    Returns:
        One line: each run's directory name, configuration and directory, and why nothing was
        written.

    """
    named_runs = ', '.join(f'{run.directory.name} ({run.label}, {run.directory})' for run in runs)
    noun = 'run' if len(runs) == 1 else 'runs'
    return (
        f'No report written: {noun} {named_runs} recorded no test (did pytest run the suite? '
        f'--help or --collect-only run no test), so nothing could be compared'
    )


class PairDifferences(BaseModel):
    """Two configurations' first runs compared: the first is the baseline of the pair."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    first: str
    second: str
    tests_compared: int
    differences: tuple[FrameSequenceDifference, ...]
    only_in_first: tuple[str, ...]
    only_in_second: tuple[str, ...]

    @property
    def name(self) -> str:
        """The pair's name in tables: ``first/second``."""
        return f'{self.first}/{self.second}'

    @property
    def folder_name(self) -> str:
        """The pair's images folder name: ``first-vs-second``."""
        return f'{self.first}-vs-{self.second}'

    def difference_for(self, *, nodeid: str) -> FrameSequenceDifference | None:
        """Return a test's difference in this pair.

        Args:
            nodeid: The test.

        Returns:
            Its difference, or None when its frames agree (or it was not compared).

        """
        return next(
            (difference for difference in self.differences if difference.nodeid == nodeid), None
        )


class TestAgreement(BaseModel):
    """Which configurations agree on a test that differs somewhere."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    nodeid: str
    # The configurations that recorded it, grouped by agreement (the baseline's group first)
    groups: tuple[tuple[str, ...], ...]
    not_recorded: tuple[str, ...]
    pattern: str

    @property
    def file(self) -> str:
        """The test's file (its node id before ``::``)."""
        return self.nodeid.split(NODE_FILE_SEPARATOR, 1)[0]


class PairImages(BaseModel):
    """A differing pair's re-run frames compared as images, for one test."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    first: str
    second: str
    nodeid: str
    # The re-runs differ too (False: the difference did not reproduce, or a re-run lacks it)
    reproduced: bool
    comparisons: tuple[FrameImageComparison, ...]


class RunSummary(BaseModel):
    """One run: its configuration, directory, size and time."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    label: str
    directory: Path
    tests_recorded: int
    tests_failed: int
    seconds: float | None


class DriverMatrix(BaseModel):
    """Every configuration compared with every other."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    configurations: tuple[str, ...]
    runs: tuple[RunSummary, ...]
    pairs: tuple[PairDifferences, ...]
    # The tests that differ in some pair, or that some configuration did not record
    tests: tuple[TestAgreement, ...]
    repeats: tuple[RepeatComparison, ...]
    frames_vary: dict[str, str]
    images: tuple[PairImages, ...] = ()

    def images_for(self, *, pair: PairDifferences, nodeid: str) -> PairImages | None:
        """Return a pair's image comparison of a test, if made.

        Args:
            pair: The pair.
            nodeid: The test.

        Returns:
            The images, or None.

        """
        return next(
            (
                images
                for images in self.images
                if (images.first, images.second, images.nodeid) == (pair.first, pair.second, nodeid)
            ),
            None,
        )


def name_list(names: Sequence[str]) -> str:
    """Join names for a sentence: ``a``, ``a and b``, ``a, b and c``.

    Args:
        names: The names.

    Returns:
        The joined names.

    """
    if len(names) <= 1:
        return ''.join(names)
    return f'{", ".join(names[:-1])} and {names[-1]}'


def describe_groups(
    *, groups: Sequence[Sequence[str]], not_recorded: Sequence[str], baseline: str
) -> str:
    """Describe how configurations agree on a test, in words.

    Args:
        groups: The configurations grouped by agreement.
        not_recorded: The configurations that did not record the test.
        baseline: The baseline configuration.

    Returns:
        For example ``cocoa differs from all others``, ``x11-macos and x11-linux differ from
        dummy and cocoa``, ``all differ``, or ``split: dummy | cocoa and x11-macos | x11-linux``,
        with ``; not recorded on ...`` when some did not record it.

    """
    if len(groups) <= 1:
        pattern = 'all agree'
    elif len(groups) == ONE_SIDE_AND_THE_OTHER:
        rest, odd = sorted(groups, key=lambda group: baseline not in group)
        if len(rest) == 1 and len(odd) > 1:
            rest, odd = odd, rest
        if len(odd) == 1 and len(rest) > 1:
            pattern = f'{odd[0]} differs from all others'
        else:
            verb = 'differs' if len(odd) == 1 else 'differ'
            pattern = f'{name_list(odd)} {verb} from {name_list(rest)}'
    elif all(len(group) == 1 for group in groups):
        pattern = 'all differ'
    else:
        pattern = 'split: ' + ' | '.join(name_list(group) for group in groups)
    if not_recorded:
        pattern += f'; not recorded on {name_list(not_recorded)}'
    return pattern


def agreement_groups(
    *, nodeid: str, labels: Sequence[str], pairs: Mapping[tuple[str, str], PairDifferences]
) -> list[list[str]]:
    """Group the configurations that recorded a test by whether their frames agree.

    Each configuration joins the first group whose first member it agrees with.

    Args:
        nodeid: The test.
        labels: The configurations that recorded it, in matrix order.
        pairs: Every pair, by (first, second) in matrix order.

    Returns:
        The groups, the first configuration's group first.

    """
    groups: list[list[str]] = []
    for label in labels:
        for group in groups:
            if pairs[group[0], label].difference_for(nodeid=nodeid) is None:
                group.append(label)
                break
        else:
            groups.append([label])
    return groups


def run_summary(
    *, run: LabelledRun, records: Mapping[str, RecordedFrames], run_seconds: Mapping[str, float]
) -> RunSummary:
    """Summarize one run.

    Args:
        run: The run.
        records: Its records by node id.
        run_seconds: The runs' durations by directory name.

    Returns:
        Its configuration, directory, test and failure counts, and seconds (if known).

    """
    return RunSummary(
        label=run.label,
        directory=run.directory,
        tests_recorded=len(records),
        tests_failed=sum(record.outcome == OUTCOME_FAILED for record in records.values()),
        seconds=run_seconds.get(run.directory.name),
    )


def compare_pairs(
    *, first_runs: Mapping[str, dict[str, RecordedFrames]], excluded: frozenset[str]
) -> dict[tuple[str, str], PairDifferences]:
    """Compare every pair of configurations' first runs.

    Args:
        first_runs: Each configuration's first run's records, in matrix order.
        excluded: Tests left out of every pair (nondeterministic or frames_vary; compare_runs
            already leaves frames_vary tests out of the differences).

    Returns:
        The pairs, by (first, second) in matrix order.

    """
    pairs: dict[tuple[str, str], PairDifferences] = {}
    for first, second in itertools.combinations(first_runs, 2):
        differences, only_in_first, only_in_second = compare_runs(
            baseline=first_runs[first], candidate=first_runs[second]
        )
        pairs[first, second] = PairDifferences(
            first=first,
            second=second,
            tests_compared=len((first_runs[first].keys() & first_runs[second].keys()) - excluded),
            differences=tuple(
                difference for difference in differences if difference.nodeid not in excluded
            ),
            only_in_first=tuple(only_in_first),
            only_in_second=tuple(only_in_second),
        )
    return pairs


def build_matrix(
    *, runs: Sequence[LabelledRun], run_seconds: Mapping[str, float] | None = None
) -> DriverMatrix:
    """Compare every configuration's first run with every other's.

    Args:
        runs: The runs; the first one's label is the baseline. Runs sharing a label are
            repeats (their differences are nondeterminism, left out of the pairs).
        run_seconds: Each run's duration by its directory's name, if known.

    Returns:
        The matrix (without images).

    """
    records_by_label: dict[str, list[dict[str, RecordedFrames]]] = {}
    summaries: list[RunSummary] = []
    for run in runs:
        records = read_recorded_frames(directory=run.directory)
        records_by_label.setdefault(run.label, []).append(records)
        summaries.append(run_summary(run=run, records=records, run_seconds=run_seconds or {}))
    labels = list(records_by_label)
    repeats = [
        compare_repeats(label=label, runs=label_runs)
        for label, label_runs in records_by_label.items()
        if len(label_runs) > 1
    ]
    nondeterministic = frozenset[str]().union(*(repeat.nodeids for repeat in repeats))
    first_runs = {label: label_runs[0] for label, label_runs in records_by_label.items()}
    frames_vary = frames_vary_tests(*first_runs.values())
    pairs = compare_pairs(first_runs=first_runs, excluded=frozenset(frames_vary) | nondeterministic)
    differing_tests = {
        nodeid
        for pair in pairs.values()
        for nodeid in itertools.chain(
            (difference.nodeid for difference in pair.differences),
            pair.only_in_first,
            pair.only_in_second,
        )
    } - nondeterministic
    tests: list[TestAgreement] = []
    for nodeid in sorted(differing_tests):
        recorded = [label for label in labels if nodeid in first_runs[label]]
        not_recorded = [label for label in labels if label not in recorded]
        groups = agreement_groups(nodeid=nodeid, labels=recorded, pairs=pairs)
        tests.append(
            TestAgreement(
                nodeid=nodeid,
                groups=tuple(tuple(group) for group in groups),
                not_recorded=tuple(not_recorded),
                pattern=describe_groups(
                    groups=groups, not_recorded=not_recorded, baseline=labels[0]
                ),
            )
        )
    return DriverMatrix(
        configurations=tuple(labels),
        runs=tuple(summaries),
        pairs=tuple(pairs.values()),
        tests=tuple(tests),
        repeats=tuple(repeats),
        frames_vary=frames_vary,
    )


def compare_pair_images(
    *, matrix: DriverMatrix, reruns: Sequence[LabelledRun], output: Path
) -> DriverMatrix:
    """Compare every differing pair's re-run frames as images.

    Args:
        matrix: The matrix (from the first runs).
        reruns: Each configuration's re-run of the differing tests, saving their frames.
        output: The report folder (images under ``differences/<first>-vs-<second>/``).

    Returns:
        The matrix with its images.

    """
    rerun_by_label = {rerun.label: rerun for rerun in reruns}
    records_by_label = {
        rerun.label: read_recorded_frames(directory=rerun.directory) for rerun in reruns
    }
    images: list[PairImages] = []
    for pair in matrix.pairs:
        for difference in pair.differences:
            first_record = records_by_label.get(pair.first, {}).get(difference.nodeid)
            second_record = records_by_label.get(pair.second, {}).get(difference.nodeid)
            if first_record is None or second_record is None:
                images.append(
                    PairImages(
                        first=pair.first,
                        second=pair.second,
                        nodeid=difference.nodeid,
                        reproduced=False,
                        comparisons=(),
                    )
                )
                continue
            rerun_difference, comparisons = compare_rerun_images(
                baseline=rerun_by_label[pair.first],
                candidate=rerun_by_label[pair.second],
                baseline_record=first_record,
                candidate_record=second_record,
                output=output / DIFFERENCES_DIRECTORY_NAME / pair.folder_name,
            )
            images.append(
                PairImages(
                    first=pair.first,
                    second=pair.second,
                    nodeid=difference.nodeid,
                    reproduced=rerun_difference is not None,
                    comparisons=tuple(comparisons),
                )
            )
    return matrix.model_copy(update={'images': tuple(images)})


def markdown_cell(text: str) -> str:
    """Make text safe in a Markdown table cell (a node id may hold ``|``).

    Args:
        text: The text.

    Returns:
        The text with ``|`` escaped.

    """
    return text.replace('|', '\\|')


def difference_cell(
    *, matrix: DriverMatrix, pair: PairDifferences, nodeid: str, output: Path
) -> str:
    """Write one test's cell for one pair.

    Args:
        matrix: The matrix.
        pair: The pair.
        nodeid: The test.
        output: The report folder (links are relative to it).

    Returns:
        ``agree``, ``n/a`` (not recorded by both), or the first differing frame's index (each
        side's, ``first/second``, when they differ: ``final`` marks a run's final frame) and
        kind, with the differing pixel count linked to the difference image when compared.

    """
    if nodeid in pair.only_in_first or nodeid in pair.only_in_second:
        return 'n/a'
    difference = pair.difference_for(nodeid=nodeid)
    if difference is None:
        return 'agree'
    sides = [
        f'{position}' + (' final' if position == frame_count - 1 else '')
        for position, frame_count in (
            (difference.baseline_position, difference.baseline_frame_count),
            (difference.candidate_position, difference.candidate_frame_count),
        )
    ]
    where = sides[0] if sides[0] == sides[1] else '/'.join(sides)
    cell = f'**frame {where}** ({difference.kind})'
    images = matrix.images_for(pair=pair, nodeid=nodeid)
    if images is None:
        return cell
    if not images.reproduced:
        return f'{cell}: not reproduced'
    first_comparison = images.comparisons[0]
    if first_comparison.differing_pixels is None or first_comparison.difference_image is None:
        return f'{cell}: {first_comparison.note}'
    link = first_comparison.difference_image.relative_to(output).as_posix()
    return f'{cell}: [{first_comparison.differing_pixels:,} px]({link})'


def pair_summary_table(*, matrix: DriverMatrix) -> list[str]:
    """Write the summary table: one row per pair.

    Args:
        matrix: The matrix.

    Returns:
        The table's lines.

    """
    kinds = ' | '.join(DIFFERENCE_KINDS)
    lines = [
        f'| Pair | Compared | Differ | {kinds} | Only in first | Only in second |',
        '|' + ' --- |' * (len(DIFFERENCE_KINDS) + 5),
    ]
    for pair in matrix.pairs:
        counts = ' | '.join(
            str(sum(difference.kind == kind for difference in pair.differences))
            for kind in DIFFERENCE_KINDS
        )
        lines.append(
            f'| {pair.name} | {pair.tests_compared} | {len(pair.differences)} | {counts} | '
            f'{len(pair.only_in_first)} | {len(pair.only_in_second)} |'
        )
    return lines


def pattern_table(*, matrix: DriverMatrix) -> list[str]:
    """Write the patterns table: how many tests show each pattern of agreement.

    Args:
        matrix: The matrix.

    Returns:
        The table's lines (most common first), or a line saying all agree.

    """
    if not matrix.tests:
        return ['Every configuration agrees on every compared test.']
    counts: dict[str, int] = {}
    for test in matrix.tests:
        counts[test.pattern] = counts.get(test.pattern, 0) + 1
    lines = ['| Pattern | Tests |', '| --- | --- |']
    lines.extend(
        f'| {pattern} | {count} |'
        for pattern, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    )
    return lines


def summary_text(*, matrix: DriverMatrix) -> str:
    """Write the session's closing summary: the pair table, then the patterns.

    Args:
        matrix: The matrix.

    Returns:
        The summary.

    """
    lines = [
        f'Driver matrix: {", ".join(matrix.configurations)} (baseline {matrix.configurations[0]})',
        '',
        *pair_summary_table(matrix=matrix),
        '',
        *pattern_table(matrix=matrix),
    ]
    nondeterministic = sorted({nodeid for repeat in matrix.repeats for nodeid in repeat.nodeids})
    if nondeterministic:
        lines.extend(('', f'Nondeterministic (not compared): {len(nondeterministic)}'))
        lines.extend(f'  {nodeid}' for nodeid in nondeterministic)
    return '\n'.join(lines) + '\n'


def matrix_markdown(*, matrix: DriverMatrix, output: Path) -> str:
    """Write the whole report as Markdown.

    Args:
        matrix: The matrix.
        output: The report folder (where the file goes; links are relative to it).

    Returns:
        The Markdown.

    """
    pair_names = ' | '.join(pair.name for pair in matrix.pairs)
    pair_rule = ' --- |' * len(matrix.pairs)
    lines = [
        '# Driver comparison matrix',
        '',
        (
            f'Configurations: {", ".join(matrix.configurations)}; baseline '
            f'{matrix.configurations[0]}. A cell gives the first frame (its index among the '
            "test's presents, then its final frame) where the pair differs, the kind of "
            'difference and, when the re-run saved both frames, the differing pixel count '
            'linked to the difference image (the first frame dimmed to grey, differing pixels '
            'magenta).'
        ),
        '',
        '## Runs',
        '',
        '| Run | Configuration | Tests recorded | Failed | Seconds |',
        '| --- | --- | --- | --- | --- |',
    ]
    lines.extend(
        f'| {run.directory.name} | {run.label} | {run.tests_recorded} | {run.tests_failed} | '
        f'{"" if run.seconds is None else f"{run.seconds:.0f}"} |'
        for run in matrix.runs
    )
    lines.extend(('', '## Pairs', '', *pair_summary_table(matrix=matrix)))
    lines.extend(('', '## Patterns', '', *pattern_table(matrix=matrix)))
    tests_by_file: dict[str, list[TestAgreement]] = {}
    for test in matrix.tests:
        tests_by_file.setdefault(test.file, []).append(test)
    if tests_by_file:
        lines.extend((
            '',
            '## Tests by file',
            '',
            f'| File | Tests | {pair_names} |',
            f'| --- | --- |{pair_rule}',
        ))
        for file, tests in tests_by_file.items():
            differing = ' | '.join(
                str(sum(pair.difference_for(nodeid=test.nodeid) is not None for test in tests))
                for pair in matrix.pairs
            )
            lines.append(f'| {markdown_cell(file)} | {len(tests)} | {differing} |')
        lines.extend(('', '## Tests'))
        for file, tests in tests_by_file.items():
            lines.extend((
                '',
                f'<details><summary>{file} ({len(tests)} tests)</summary>',
                '',
                f'| Test | Pattern | {pair_names} |',
                f'| --- | --- |{pair_rule}',
            ))
            for test in tests:
                cells = ' | '.join(
                    difference_cell(matrix=matrix, pair=pair, nodeid=test.nodeid, output=output)
                    for pair in matrix.pairs
                )
                name = test.nodeid.removeprefix(file + NODE_FILE_SEPARATOR)
                lines.append(f'| {markdown_cell(name)} | {test.pattern} | {cells} |')
            lines.extend(('', '</details>'))
    for repeat in matrix.repeats:
        lines.extend((
            '',
            f'## Nondeterministic on {repeat.label} ({repeat.run_count} runs; not compared)',
            '',
        ))
        lines.extend(
            f'- {markdown_cell(difference.nodeid)}: {difference.describe()}'
            for difference in repeat.differences
        )
        lines.extend(
            f'- {markdown_cell(nodeid)}: recorded in some runs only'
            for nodeid in repeat.recorded_in_some_runs
        )
    if matrix.frames_vary:
        lines.extend(('', '## Not compared (frames_vary)', ''))
        lines.extend(
            f'- {markdown_cell(nodeid)}: {reason}' for nodeid, reason in matrix.frames_vary.items()
        )
    return '\n'.join(lines) + '\n'


def argument_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(
        description='Compare every driver configuration with every other (a matrix)'
    )
    parser.add_argument(
        'runs',
        nargs='+',
        type=parse_labelled_run,
        metavar='LABEL=DIRECTORY',
        help='fingerprints directories; the first label is the baseline configuration',
    )
    parser.add_argument('--output', type=Path, required=True, help='the report folder')
    parser.add_argument(
        '--image-request',
        type=Path,
        default=None,
        help='write the frames to save in a re-run of the differing tests to this file',
    )
    parser.add_argument(
        '--rerun',
        type=parse_labelled_run,
        action='append',
        default=[],
        metavar='LABEL=DIRECTORY',
        help="a configuration's re-run of the differing tests (saving frames); repeatable",
    )
    parser.add_argument(
        '--run-seconds',
        type=Path,
        default=None,
        help="a JSON file of each run's seconds by its directory's name",
    )
    return parser


def write_report(
    *,
    runs: Sequence[LabelledRun],
    output: Path,
    image_request_path: Path | None,
    reruns: Sequence[LabelledRun],
    run_seconds_path: Path | None,
) -> str:
    """Build the matrix, write its files, and return the summary.

    Args:
        runs: The labelled runs, the baseline's first.
        output: The report folder.
        image_request_path: Where to write the image request, or None.
        reruns: The re-runs with saved frames (none: no images).
        run_seconds_path: The runs' durations file, or None.

    Returns:
        The summary.

    Raises:
        NoTestsRecordedError: If a run recorded no test (nothing is written then).

    """
    run_seconds: dict[str, float] = (
        {} if run_seconds_path is None else json.loads(run_seconds_path.read_text(encoding='utf-8'))
    )
    matrix = build_matrix(runs=runs, run_seconds=run_seconds)
    runs_without_tests = [summary for summary in matrix.runs if summary.tests_recorded == 0]
    if runs_without_tests:
        raise NoTestsRecordedError(runs_without_tests_message(runs=runs_without_tests))
    if reruns:
        matrix = compare_pair_images(matrix=matrix, reruns=reruns, output=output)
    output.mkdir(parents=True, exist_ok=True)
    if image_request_path is not None:
        request = image_request_for_differences(
            differences=[difference for pair in matrix.pairs for difference in pair.differences]
        )
        image_request_path.write_text(request.model_dump_json(indent=2), encoding='utf-8')
    (output / MATRIX_JSON_NAME).write_text(matrix.model_dump_json(indent=2), encoding='utf-8')
    (output / MATRIX_MARKDOWN_NAME).write_text(
        matrix_markdown(matrix=matrix, output=output), encoding='utf-8'
    )
    return summary_text(matrix=matrix) + f'Report: {output / MATRIX_MARKDOWN_NAME}\n'


def run(*, arguments: Sequence[str]) -> ExitCode:
    """Run the command and print its summary.

    Args:
        arguments: The command line arguments (without the program name).

    Returns:
        The exit code.

    """
    options = argument_parser().parse_args(arguments)
    try:
        summary = write_report(
            runs=options.runs,
            output=options.output,
            image_request_path=options.image_request,
            reruns=options.rerun,
            run_seconds_path=options.run_seconds,
        )
    except FileNotFoundError as error:
        sys.stderr.write(f'{error}\n')
        return ExitCode.MISSING_INPUT
    except NoTestsRecordedError as error:
        sys.stderr.write(f'{error}\n')
        return ExitCode.UNUSABLE_INPUT
    except pydantic.ValidationError, json.JSONDecodeError:
        sys.stderr.write(f'unusable record or run times: {sys.exception()}\n')
        return ExitCode.UNUSABLE_INPUT
    except OSError as error:
        sys.stderr.write(f'cannot write the output: {error}\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    sys.stdout.write(summary)
    return ExitCode.SUCCESS


def main() -> None:
    """Command line: see the module docstring."""
    sys.exit(run(arguments=sys.argv[1:]))


if __name__ == '__main__':
    main()
