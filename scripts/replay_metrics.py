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
2. for each golden replay (each workspace member's
   ``<member>/tests/fixtures/replays/golden.jsonl.gz``, and any in the root's
   ``tests/fixtures/replays/<console-script>/``, the plugin's layout for other projects, which
   holds no game here) and bundled demo
   (a member package's ``<package>/demos/*.jsonl.gz``) not already measured for this commit on
   this machine (published or pending; ``--force`` measures again): rebaselines it
   headless into a temporary file through its console script
   (``glitchygames.testing.replays.rebaseline_recording_headless``), so the run measures every
   frame's processing time and records its provenance (commit, machine state);
3. appends the rebaselined recording's rows (``ledger_rows_from_rebaseline``: the measurement,
   then each run the recording held, unless already in the ledger) to the pending file. A run the
   recording held is written (to the pending file, or with ``--rows-directory``, the
   pre-commit hook, as row files) only if it landed (``rows_to_write``: measured on a commit that is
   on ``origin/main``, without uncommitted changes; none at all without an ``origin/main``,
   said once). "Already in the ledger" compares rows with a moved recording's old path resolved
   to its new one (``LedgerRow.held_key``).

The children must run this checkout's package (an editable install, as ``uv run`` gives), or
they cannot name their commit: a row whose commit is not the checkout's is a failure.

``clear-published`` (docs-deploy, after ``mkdocs gh-deploy`` succeeded): removes the pending rows
that ``origin/gh-pages``'s ledger now holds; the rest stay pending.

Usage (a module: it imports scripts.workspace_packages):
    uv run python -m scripts.replay_metrics measure [--force] [--allow-dirty | --skip-dirty]
        [--only TEXT] [--pending PATH]
    uv run python -m scripts.replay_metrics clear-published [--pending PATH]

Exit codes: ``SUCCESS``; ``OPTIONS_REFUSED`` for an unknown commit or uncommitted changes;
``INTERNAL_ERROR`` when a recording could not be measured (the others are still measured),
a golden replay no installed console script replays included: a workspace member that is not
installed is reported on one line naming the fix, ``uv sync --all-packages``
(``metric_recordings``' ``unreplayable``).
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
from glitchygames.bundled_demos import bundled_demos
from glitchygames.code_tree import commit_is_on_origin_main, origin_main_exists
from glitchygames.exit_codes import ExitCode
from glitchygames.logical_names import MEMBER_LAYERS
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
from glitchygames.testing.replays import rebaseline_recording_headless, recording_console_script
from glitchygames.tracing import is_bookmarked_copy, read_trace
from scripts.workspace_packages import workspace_members

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.recording_metrics import LedgerRow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PENDING_LEDGER_PATH = PROJECT_ROOT / PENDING_LEDGER_RELATIVE_PATH
# Golden replays in the root's tests/fixtures/replays/<console-script>/ (the replay plugin's layout
# for other projects: none here, every game is a member); each workspace member's
# are directly in its replay fixtures directory (golden_replay_globs): golden.jsonl.gz, or one
# golden-<game>.jsonl.gz per game in a member with several (Brave Adventurer's golden-classic
# and golden-papyrus; docs/architecture/game_packages.md)
ENGINE_GOLDEN_REPLAYS_GLOB = 'tests/fixtures/replays/*/golden.jsonl.gz'
MEMBER_GOLDEN_REPLAYS_GLOB = 'golden*.jsonl.gz'
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


def golden_replay_globs(*, project_root: Path) -> list[str]:
    """Return the globs, relative to the repository, that find every golden replay.

    Args:
        project_root: The repository.

    Returns:
        The engine's glob, then each workspace member's.

    """
    return [
        ENGINE_GOLDEN_REPLAYS_GLOB,
        *(
            (
                member.replay_fixtures_directory.relative_to(project_root)
                / MEMBER_GOLDEN_REPLAYS_GLOB
            ).as_posix()
            for member in workspace_members(project_root=project_root)
        ),
    ]


class UnreplayableRecording(BaseModel):
    """A recording no installed console script replays, and why (one line).

    Attributes:
        path: The recording.
        reason: Why it cannot be replayed, naming the fix (``recording_console_script``'s
            refusal: a workspace member a plain ``uv sync`` uninstalled, say).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    path: Path
    reason: str


class MetricRecordings(BaseModel):
    """Every golden replay and bundled demo, as ``metric_recordings`` found them.

    Attributes:
        replayable: ``(console script, path)`` pairs: the golden replays, then the demos, each
            by path.
        unreplayable: The golden replays and demos no installed console script replays:
            reported and counted as failures, while the others are still measured.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    replayable: tuple[tuple[str, Path], ...]
    unreplayable: tuple[UnreplayableRecording, ...] = ()


def metric_recordings(
    *, project_root: Path, demo_packages: tuple[str, ...] = tuple(MEMBER_LAYERS)
) -> MetricRecordings:
    """Return every golden replay and bundled demo, with the console script that replays it.

    The goldens are the repository's (``golden_replay_globs``); the demos are the installed
    packages' (``glitchygames.bundled_demos.bundled_demos``, the lookup the replay plugin uses
    too): under a development install (editable, as ``uv sync`` installs) they are the
    repository's files, under a built one ``site-packages``' (``recording_ledger_name`` names
    either).

    Args:
        project_root: The repository.
        demo_packages: The import packages whose bundled demos are measured: every workspace
            member's unless given.

    Returns:
        The recordings: those a console script replays, and those none does (a workspace member
        not installed: ``uv sync --all-packages`` installs every member; a package with demos
        but no console script). Bookmarked copies (``glitchygames.tracing.is_bookmarked_copy``)
        are left out.

    """
    goldens: list[tuple[str, Path]] = []
    unreplayable: list[UnreplayableRecording] = []
    # A bookmarked copy (S saves one beside a recording a watched replay plays:
    # golden-classic.bookmarked.jsonl.gz) matches a member's glob but is no golden
    for path in sorted(
        path
        for glob in golden_replay_globs(project_root=project_root)
        for path in project_root.glob(glob)
        if not is_bookmarked_copy(path=path)
    ):
        try:
            goldens.append((recording_console_script(path=path), path))
        except KeyError as error:
            # The refusal's message (not KeyError's quoted repr), without the path it starts
            # with: the failure line names the recording
            reason = str(error.args[0]).removeprefix(f'{path}: ')
            unreplayable.append(UnreplayableRecording(path=path, reason=reason))
    demos: list[tuple[str, Path]] = []
    for demo in bundled_demos(packages=demo_packages):
        # This caller's reaction to a demo no console script replays: reported, not raised
        if demo.console_script is None:
            reason = f'no installed console script has its entry point in {demo.package}'
            unreplayable.append(UnreplayableRecording(path=demo.path, reason=reason))
            continue
        demos.append((demo.console_script, demo.path))
    return MetricRecordings(replayable=(*goldens, *demos), unreplayable=tuple(unreplayable))


def recording_ledger_name(*, path: Path, project_root: Path) -> str:
    """Return the name the ledger gives a recording.

    A recording in the repository is named by its repository path
    (``src/games/paddleslap/paddleslap/demos/rally.jsonl.gz``: what a development install, which
    is editable, finds). One outside it (a bundled demo of a built install, in
    ``site-packages``) is named by its path relative to the import path it is installed under
    (``paddleslap/demos/rally.jsonl.gz``, ``glitchygames.bundled_demos.BundledDemo.install_name``).

    Args:
        path: The recording.
        project_root: The repository.

    Returns:
        The name.

    Raises:
        ValueError: If the recording is neither in the repository nor under an import path.

    """
    resolved = path.resolve()
    repository = project_root.resolve()
    if resolved.is_relative_to(repository):
        return resolved.relative_to(repository).as_posix()
    install_roots = [
        root
        for root in (Path(entry).resolve() for entry in sys.path if entry)
        if resolved.is_relative_to(root)
    ]
    if not install_roots:
        message = f'{path}: neither in the repository {project_root} nor under an import path'
        raise ValueError(message)
    # The innermost import path: site-packages, not a directory above it on sys.path
    install_root = max(install_roots, key=lambda root: len(root.parts))
    return resolved.relative_to(install_root).as_posix()


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
        code_tree: The code measured, as a git tree of what can change the replays
            (glitchygames/code_tree.py): the measuring pre-commit hook's
            (scripts/measure_staged_replays.py); the run it measures names it, and a recording
            already measured for it on this machine is skipped.
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
    recording = recording_ledger_name(path=path, project_root=settings.project_root)
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


def rows_to_write(
    *,
    rows: Sequence[LedgerRow],
    held_keys: set[str],
    repository: Path,
    origin_main_present: bool,
) -> list[LedgerRow]:
    """Return the rows of a rebaselined recording that a row-file measurement writes.

    The newest run (``rows[0]``, the one just measured) is written unless held. A history row (a
    run the recording held) is written only when no row holds it, and its run was measured on a
    commit that is on ``origin/main`` with no uncommitted changes: a run of code that never
    landed would be published unconditionally (it names no code tree). With no ``origin/main``
    to compare with, none is written. "Held" compares keys with the recording at its current
    path (``LedgerRow.held_key``), so a moved recording's earlier runs are not written again.

    Args:
        rows: The recording's rows, newest first (``ledger_rows_from_rebaseline``).
        held_keys: The ``held_key`` of every row already held.
        repository: The repository whose ``origin/main`` decides what landed.
        origin_main_present: Whether the repository has ``origin/main`` (looked up once).

    Returns:
        The rows to write, in order.

    """
    newest, *history = rows
    written = [] if newest.held_key in held_keys else [newest]
    for row in history:
        commit = row.commit
        if (
            row.held_key in held_keys
            or not origin_main_present
            or commit is None
            or row.measured_uncommitted_changes
            or not commit_is_on_origin_main(repository=repository, commit=commit)
        ):
            continue
        written.append(row)
    return written


def _origin_main_present(*, settings: MeasureSettings) -> bool:
    """Return whether the repository has ``origin/main``, which history runs are judged by.

    Says so once when it has none (no history row is written then).

    Returns:
        True when ``origin/main`` exists.

    """
    if origin_main_exists(repository=settings.project_root):
        return True
    sys.stdout.write(
        'No origin/main in this repository: no history rows written (earlier runs count as '
        'landed only on that branch)\n'
    )
    return False


def _write_new_rows(
    *,
    settings: MeasureSettings,
    rows: list[LedgerRow],
    held_keys: set[str],
    origin_main_present: bool,
) -> list[LedgerRow]:
    """Write a recording's rows no row holds yet (see ``rows_to_write``) and return them.

    They are written as row files with ``--rows-directory``, else appended to the pending file
    (which the docs deploy publishes, so the same landed rules apply).

    Returns:
        The rows written.

    """
    new_rows = rows_to_write(
        rows=rows,
        held_keys=held_keys,
        repository=settings.project_root,
        origin_main_present=origin_main_present,
    )
    if settings.rows_directory is None:
        settings.pending_path.parent.mkdir(parents=True, exist_ok=True)
        with settings.pending_path.open('a', encoding='utf-8') as pending:
            pending.write(ledger_text(rows=new_rows))
    else:
        write_row_files(rows=new_rows, directory=settings.rows_directory)
    return new_rows


def measure(
    *,
    settings: MeasureSettings,
    recordings: Sequence[tuple[str, Path]],
    published_text: str,
    unreplayable: Sequence[UnreplayableRecording] = (),
) -> MeasureResult:
    """Measure recordings and append their rows to the pending ledger (see the docstring).

    Args:
        settings: The measurement's settings.
        recordings: ``(console script, path)`` pairs to measure.
        published_text: The published ledger's text.
        unreplayable: Recordings no console script replays: each is a failure, reported on one
            line with its reason, and the others are still measured.

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
    origin_main_present = _origin_main_present(settings=settings)
    measured: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    for unreplayable_recording in unreplayable:
        recording = recording_ledger_name(
            path=unreplayable_recording.path, project_root=settings.project_root
        )
        _failure(recording=recording, message=unreplayable_recording.reason)
        failures.append(recording)
    with tempfile.TemporaryDirectory(prefix='replay-metrics-') as temporary_name:
        for index, (console_script, path) in enumerate(recordings):
            recording = recording_ledger_name(path=path, project_root=settings.project_root)
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
            new_rows = _write_new_rows(
                settings=settings,
                rows=rows,
                held_keys={row.held_key for row in known},
                origin_main_present=origin_main_present,
            )
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
            'the code measured, as a git tree of what can change the replays '
            '(glitchygames/code_tree.py): the measured run names it, and a recording measured '
            'for it on this machine is skipped (the pre-commit hook, '
            'scripts/measure_staged_replays.py)'
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

    def selected(path: Path) -> bool:
        return options.only is None or options.only in recording_ledger_name(
            path=path, project_root=PROJECT_ROOT
        )

    found = metric_recordings(project_root=PROJECT_ROOT)
    recordings = [
        (console_script, path) for console_script, path in found.replayable if selected(path)
    ]
    unreplayable = [recording for recording in found.unreplayable if selected(recording.path)]
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
        settings=settings,
        recordings=recordings,
        published_text=published_text,
        unreplayable=unreplayable,
    ).exit_code


def main() -> None:
    """Command line: see the module docstring."""
    sys.exit(run(arguments=sys.argv[1:]))


if __name__ == '__main__':
    main()
