#!/usr/bin/env python3
"""Measure every golden replay and bundled demo on this machine into the run ledger.

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md (Part 1 of
plans/2026-10-23-recording-metrics.md). The run ledger keeps one row per recording per run
(``glitchygames.recording_metrics.LedgerRow``) beyond the ten runs a recording holds. It is
published with the docs site, on the gh-pages branch (``PUBLISHED_LEDGER_PATH``); rows measured
here wait in ``PENDING_LEDGER_PATH`` (gitignored) until a deploy publishes them.

``measure`` (``nox -s replay-metrics``; ``nox -s docs-deploy`` runs it first):

1. refuses a checkout whose commit is unknown, and one with uncommitted changes unless
   ``--allow-dirty`` (the rows say so; such a trial never counts as measuring its commit) or
   ``--skip-dirty`` (measure nothing and succeed: what docs-deploy passes);
2. for each golden replay (``tests/fixtures/replays/<console-script>/golden.jsonl.gz``) and
   bundled demo (``glitchygames/examples/<game>_demos/*.jsonl.gz``) not already measured for this
   commit on this machine (published or pending; ``--force`` measures again): rebaselines it
   headless into a temporary file through its console script
   (``glitchygames.testing.replays.rebaseline_recording_headless``), so the run measures every
   frame's processing time and records its provenance (commit, machine state);
3. appends the rebaselined recording's rows (``ledger_rows_from_rebaseline``: the measurement,
   then each run the recording held, unless already in the ledger) to the pending file.

The children must run this checkout's package (an editable install, as ``uv run`` gives), or
they cannot name their commit: a row whose commit is not the checkout's is a failure.

``clear-published`` (docs-deploy, after ``mkdocs gh-deploy`` succeeded): removes the pending rows
that ``origin/gh-pages``'s ledger now holds; the rest stay pending.

Usage:
    uv run python scripts/replay_metrics.py measure [--force] [--allow-dirty | --skip-dirty]
        [--only TEXT] [--pending PATH]
    uv run python scripts/replay_metrics.py clear-published [--pending PATH]

Exit codes: ``SUCCESS``; ``OPTIONS_REFUSED`` for an unknown commit or uncommitted changes;
``INTERNAL_ERROR`` when a recording could not be measured (the others are still measured).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from glitchygames.build_info import (
    SourceRevision,
    source_revision,
)
from glitchygames.exit_codes import ExitCode
from glitchygames.machine_state import current_machine_state
from glitchygames.recording_metrics import (
    PENDING_LEDGER_RELATIVE_PATH,
    is_measured,
    ledger_rows_from_rebaseline,
    ledger_text,
    merge_ledgers,
    parse_ledger,
    published_ledger_text,
    read_ledger_file,
    read_row_files,
    write_row_files,
)
from glitchygames.replay.processing import machine_description
from glitchygames.testing.replays import bundled_demo_paths, rebaseline_recording_headless
from glitchygames.tracing import read_trace

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.recording_metrics import LedgerRow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PENDING_LEDGER_PATH = PROJECT_ROOT / PENDING_LEDGER_RELATIVE_PATH
GOLDEN_REPLAYS_GLOB = 'tests/fixtures/replays/*/golden.jsonl.gz'
EXAMPLES_PATH = Path('glitchygames') / 'examples'
# How many of a failed child's last output lines are shown
FAILURE_OUTPUT_LINES = 10
MILLISECONDS_PER_SECOND = 1000.0
# A rebaseline that wrote its recording: matched, or ran on after input the run never got
MEASURED_EXIT_CODES = frozenset({ExitCode.SUCCESS, ExitCode.REBASELINE_INPUT_LOST})
PARSER_DESCRIPTION = (
    'Measure every golden replay and bundled demo on this machine into the run ledger'
)


class MeasureResult(BaseModel):
    """What one ``measure`` did.

    Attributes:
        exit_code: The exit code.
        measured: The recordings measured (repository-relative).
        skipped: The recordings already measured for this commit on this machine.
        failures: The recordings that could not be measured.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    exit_code: ExitCode
    measured: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()


def metric_recordings(*, project_root: Path) -> list[tuple[str, Path]]:
    """Return every golden replay and bundled demo, with the console script that replays it.

    Args:
        project_root: The repository.

    Returns:
        ``(console script, path)`` pairs: the golden replays, then the demos, each by path.

    """
    goldens = [(path.parent.name, path) for path in sorted(project_root.glob(GOLDEN_REPLAYS_GLOB))]
    demos = bundled_demo_paths(examples_directory=project_root / EXAMPLES_PATH)
    return [*goldens, *demos]


def this_machine() -> str:
    """Return this machine's label as ledger rows name it (``recording_metrics.machine_label``).

    Returns:
        The CPU model, else the platform.

    """
    return current_machine_state().cpu_model or machine_description()


class MeasureSettings(BaseModel):
    """How one ``measure`` runs.

    Attributes:
        project_root: The repository (recordings are named relative to it).
        pending_path: The pending ledger (appended to; created when missing).
        revision: This checkout's source revision.
        force: Measure even what is already measured for this commit and machine.
        allow_dirty: Measure despite uncommitted changes.
        code_tree: The code measured, as a git tree of what can change the replays (glitchygames/code_tree.py): the
            measuring pre-commit hook's (scripts/measure_staged_replays.py); the run it measures
            names it, and a recording already measured for it on this machine is skipped.
            None: measured and skipped by commit.
        rows_directory: Write the rows as row files there (``write_row_files``) instead of
            appending them to ``pending_path`` (the hook's quality/replay-ledger/).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    project_root: Path
    pending_path: Path
    revision: SourceRevision
    force: bool = False
    allow_dirty: bool = False
    code_tree: str | None = None
    rows_directory: Path | None = None


def _refusal(*, revision: SourceRevision, allow_dirty: bool) -> str | None:
    if revision.commit is None:
        return (
            f'Cannot measure: the engine source revision is {revision.source}, not a git '
            'checkout (run from a checkout, through uv run)'
        )
    if revision.uncommitted_changes and not allow_dirty:
        return (
            'Cannot measure: the checkout has uncommitted changes, so the rows would not '
            'measure their commit (commit first, or pass --allow-dirty for a trial)'
        )
    return None


def _failure(*, recording: str, message: str) -> None:
    sys.stderr.write(f'{recording}: {message}\n')


def _milliseconds(seconds: float) -> str:
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f} ms'


def measure_recording(
    *, settings: MeasureSettings, console_script: str, path: Path, new_path: Path
) -> list[LedgerRow] | None:
    """Rebaseline one recording into ``new_path`` and return its ledger rows.

    Args:
        settings: The measurement's settings.
        console_script: The game's console script.
        path: The recording.
        new_path: Where the rebaselined recording goes (a temporary file).

    Returns:
        Its rows (``ledger_rows_from_rebaseline``), or None when it could not be measured (the
        reason is written to standard error).

    """
    recording = path.relative_to(settings.project_root).as_posix()
    completed = rebaseline_recording_headless(
        console_script=console_script, path=path, new_path=new_path
    )
    if completed.returncode not in MEASURED_EXIT_CODES:
        output = '\n'.join((completed.stdout or '').splitlines()[-FAILURE_OUTPUT_LINES:])
        _failure(
            recording=recording,
            message=(
                f'the rebaseline exited {ExitCode.describe_status(completed.returncode)}\n{output}'
            ),
        )
        return None
    rows = ledger_rows_from_rebaseline(
        recording=recording,
        console_script=console_script,
        trace=read_trace(path=new_path),
        rebaseline_exit=ExitCode.describe_status(completed.returncode),
        allowed_uncommitted_changes=(
            settings.allow_dirty and bool(settings.revision.uncommitted_changes)
        ),
    )
    measured_commit = rows[0].commit
    if measured_commit != settings.revision.commit:
        _failure(
            recording=recording,
            message=(
                f"the replay measured commit {measured_commit}, not the checkout's "
                f'{settings.revision.commit} (is the package installed from this checkout? run '
                'through uv run)'
            ),
        )
        return None
    return rows


def describe_measurement(*, row: LedgerRow, seconds: float, pending_rows: int) -> str:
    """Describe one recording's measurement on one line.

    Args:
        row: Its measurement's row.
        seconds: How long the rebaseline took.
        pending_rows: How many rows it added to the pending ledger.

    Returns:
        ``RECORDING: N frames in S s, processing p50 ..., p99 ..., max ..., K frames changed
        behaviour, R rows pending``.

    """
    summary = row.summary
    timing = (
        'no processing times'
        if summary is None
        else (
            f'processing p50 {_milliseconds(summary.p50_processing_seconds)}, p99 '
            f'{_milliseconds(summary.p99_processing_seconds)}, max '
            f'{_milliseconds(summary.max_processing_seconds)}'
        )
    )
    return (
        f'{row.recording}: {row.frame_count} frames in {seconds:.1f} s, {timing}, '
        f'{row.frames_changed} frames changed behaviour, {pending_rows} rows pending'
    )


def _already_measured(
    *,
    settings: MeasureSettings,
    rows: Sequence[LedgerRow],
    recording: str,
    commit: str,
    machine: str,
) -> bool:
    """Return whether this recording was measured for this code on this machine already.

    By code tree when the measurement names one (the hook's), else by commit (``is_measured``).

    Returns:
        True to skip it.

    """
    if settings.code_tree is None:
        return is_measured(rows=rows, recording=recording, commit=commit, machine=machine)
    return any(
        row.code_tree == settings.code_tree
        and row.recording == recording
        and row.machine == machine
        for row in rows
    )


def measure(
    *, settings: MeasureSettings, recordings: Sequence[tuple[str, Path]], published_text: str
) -> MeasureResult:
    """Measure recordings and append their rows to the pending ledger (see the docstring).

    Args:
        settings: The measurement's settings.
        recordings: ``(console script, path)`` pairs to measure.
        published_text: The published ledger's text.

    Returns:
        What was measured, skipped and failed.

    """
    refusal = _refusal(revision=settings.revision, allow_dirty=settings.allow_dirty)
    if refusal is not None:
        sys.stderr.write(f'{refusal}\n')
        return MeasureResult(exit_code=ExitCode.OPTIONS_REFUSED)
    commit = settings.revision.commit
    assert commit is not None, 'refused above'
    machine = this_machine()
    known = merge_ledgers(
        ledgers=[
            parse_ledger(text=published_text).rows,
            read_ledger_file(path=settings.pending_path).rows,
            []
            if settings.rows_directory is None
            else read_row_files(directory=settings.rows_directory),
        ]
    )
    measured: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix='replay-metrics-') as temporary_name:
        for index, (console_script, path) in enumerate(recordings):
            recording = path.relative_to(settings.project_root).as_posix()
            if not settings.force and _already_measured(
                settings=settings, rows=known, recording=recording, commit=commit, machine=machine
            ):
                measured_code = (
                    commit[:7]
                    if settings.code_tree is None
                    else f'code tree {settings.code_tree[:12]}'
                )
                sys.stdout.write(f'{recording}: already measured at {measured_code} on {machine}\n')
                skipped.append(recording)
                continue
            started = time.perf_counter()
            rows = measure_recording(
                settings=settings,
                console_script=console_script,
                path=path,
                new_path=Path(temporary_name) / f'{index}-{path.name}',
            )
            if rows is None:
                failures.append(recording)
                continue
            if settings.code_tree is not None:
                # The run just measured (the newest) measured the code tree; the recording's
                # own earlier runs are history and keep naming their commits
                rows = [rows[0].model_copy(update={'code_tree': settings.code_tree}), *rows[1:]]
            known_keys = {row.key for row in known}
            new_rows = [row for row in rows if row.key not in known_keys]
            if settings.rows_directory is not None:
                write_row_files(rows=new_rows, directory=settings.rows_directory)
            else:
                settings.pending_path.parent.mkdir(parents=True, exist_ok=True)
                with settings.pending_path.open('a', encoding='utf-8') as pending:
                    pending.write(ledger_text(rows=new_rows))
            known.extend(new_rows)
            measured.append(recording)
            sys.stdout.write(
                describe_measurement(
                    row=rows[0], seconds=time.perf_counter() - started, pending_rows=len(new_rows)
                )
                + '\n'
            )
    count = len(measured)
    measured_code = (
        commit[:7] if settings.code_tree is None else f'code tree {settings.code_tree[:12]}'
    )
    destination = (
        settings.pending_path if settings.rows_directory is None else settings.rows_directory
    )
    sys.stdout.write(
        f'Measured {count} recording{"" if count == 1 else "s"} at {measured_code} on {machine} '
        f'({len(skipped)} already measured, {len(failures)} failed) into {destination}\n'
    )
    return MeasureResult(
        exit_code=ExitCode.INTERNAL_ERROR if failures else ExitCode.SUCCESS,
        measured=tuple(measured),
        skipped=tuple(skipped),
        failures=tuple(failures),
    )


def clear_published(*, pending_path: Path, published_text: str) -> None:
    """Remove the pending rows the published ledger holds (a deploy published them).

    Args:
        pending_path: The pending ledger (removed when no row is left).
        published_text: The published ledger's text (after the deploy).

    """
    pending = read_ledger_file(path=pending_path).rows
    if not pending:
        sys.stdout.write(f'No pending rows in {pending_path}\n')
        return
    published_keys = {row.key for row in parse_ledger(text=published_text).rows}
    remaining = [row for row in pending if row.key not in published_keys]
    if remaining:
        pending_path.write_text(ledger_text(rows=remaining), encoding='utf-8')
    else:
        pending_path.unlink()
    removed = len(pending) - len(remaining)
    sys.stdout.write(
        f'{removed} published row{"" if removed == 1 else "s"} removed, '
        f'{len(remaining)} still pending in {pending_path}\n'
    )


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    """Parse the command line.

    Returns:
        The options.

    """
    parser = argparse.ArgumentParser(description=PARSER_DESCRIPTION)
    commands = parser.add_subparsers(dest='command', required=True)
    measuring = commands.add_parser('measure', help='measure the recordings into pending rows')
    measuring.add_argument(
        '--force', action='store_true', help='measure even what this commit already measured'
    )
    dirty = measuring.add_mutually_exclusive_group()
    dirty.add_argument(
        '--allow-dirty', action='store_true', help='measure despite uncommitted changes (a trial)'
    )
    dirty.add_argument(
        '--skip-dirty',
        action='store_true',
        help='with uncommitted changes, measure nothing and succeed',
    )
    measuring.add_argument(
        '--only', help='measure only the recordings whose repository path contains this text'
    )
    measuring.add_argument(
        '--code-tree',
        help=(
            'the code measured, as a git tree of what can change the replays (glitchygames/code_tree.py): the '
            'measured run names it, and a recording measured for it on this machine is skipped '
            '(the pre-commit hook, scripts/measure_staged_replays.py)'
        ),
    )
    measuring.add_argument(
        '--rows-directory',
        type=Path,
        help='write the rows there as row files instead of appending them to --pending',
    )
    clearing = commands.add_parser('clear-published', help='drop pending rows now published')
    for command in (measuring, clearing):
        command.add_argument(
            '--pending', type=Path, default=PENDING_LEDGER_PATH, help='the pending ledger file'
        )
    return parser.parse_args(arguments)


def run(*, arguments: Sequence[str]) -> ExitCode:
    """Run the command line's command.

    Args:
        arguments: The command line, without the program.

    Returns:
        The exit code (see the module docstring).

    """
    options = parse_arguments(arguments)
    published_text = published_ledger_text(project_root=PROJECT_ROOT)
    if options.command == 'clear-published':
        clear_published(pending_path=options.pending, published_text=published_text)
        return ExitCode.SUCCESS
    revision = source_revision()
    if options.skip_dirty and revision.uncommitted_changes:
        sys.stdout.write('Not measuring the replays: the checkout has uncommitted changes\n')
        return ExitCode.SUCCESS
    recordings = [
        (console_script, path)
        for console_script, path in metric_recordings(project_root=PROJECT_ROOT)
        if options.only is None or options.only in path.relative_to(PROJECT_ROOT).as_posix()
    ]
    settings = MeasureSettings(
        project_root=PROJECT_ROOT,
        pending_path=options.pending,
        revision=revision,
        force=options.force,
        allow_dirty=options.allow_dirty,
        code_tree=options.code_tree,
        rows_directory=options.rows_directory,
    )
    return measure(
        settings=settings, recordings=recordings, published_text=published_text
    ).exit_code


def main() -> None:
    """Command line: see the module docstring."""
    sys.exit(run(arguments=sys.argv[1:]))


if __name__ == '__main__':
    main()
