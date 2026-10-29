"""The ``measure``, ``unmeasured`` and ``clear-published`` tools: recordings in the run ledger.

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md (Part 1 of
plans/2026-10-23-recording-metrics.md); moved here from scripts/replay_metrics.py (Part 3,
Stage D, Task D6). The run ledger keeps one row per recording per run
(``glitchygames.recording_metrics.LedgerRow``) beyond the ten runs a recording holds. A project
may publish it (``[tool.glitchygames]`` ``published-ledger``: ours, with the docs site on
gh-pages); rows measured here wait in the pending ledger (``pending-ledger``) until a publish
takes them, or go into the ledger directory as row files (``--rows-directory``: our pre-commit
hook, scripts/measure_staged_replays.py).

``measure`` (``nox -s replay-metrics``; ``nox -s docs-deploy`` runs it first):

1. refuses a game whose commit is unknown, and one with uncommitted changes, unless
   ``--allow-dirty`` (the rows say so; such a trial never counts as measuring its commit) or
   ``--skip-dirty`` (measure nothing and succeed: what docs-deploy passes). The revision is the
   game's (``identity.game_source_revision``; the engine's for a game whose package isn't
   found), the commit a ledger row names (Task D3), so a game outside the engine's checkout is
   judged by its own;
2. for each of the game's recordings (``recordings.game_recordings``: its goldens in the
   project and its bundled demos; or the PATHs given) not already measured for this commit on
   this machine (published, pending or a row file; ``--force`` measures again): rebaselines it
   headless into a temporary file through the game's console script
   (``children.rebaseline_recording_headless``), so the run measures every frame's processing
   time and records its provenance. Each replays under its own recorded seed (Stage D's
   decision 17): ``--random-seed`` is refused, as verify refuses it;
3. appends the rebaselined recording's rows (``ledger_rows_from_rebaseline``: the measurement,
   then each run the recording held, unless already in the ledger) to the pending ledger. A run
   the recording held is written (to the pending file, or with ``--rows-directory`` as row
   files) only if it landed (``rows_to_write``: measured on a commit that is on the project's
   ``landed-ref`` without uncommitted changes; none at all without that ref, said once). "Already
   in the ledger" compares rows with a moved recording's old path resolved to its new one
   (``LedgerRow.held_key``, by the project's ``recording-renames``).

The children must run the game's own package (an editable install, as ``uv run`` gives), or they
cannot name its commit: a row whose commit is not the game's is a failure.

``unmeasured`` lists the recordings ``measure`` would measure (without ``--force``): one ledger
name per line on standard output, then a summary on standard error. ``clear-published`` (after a
publish succeeded) removes the pending rows the published ledger now holds; the rest stay
pending.

The front ends (glitchygames/replay/tools/registry.py):

- **On the game**: ``--measure [PATH ...]`` (``measure_on_the_game``), ``--unmeasured`` and
  ``--clear-published`` run from ``GameEngine.__init__``, before the engine starts pygame: the
  game is neither built nor shown. With no PATHs, ``--measure`` measures the game's own
  recordings, as ``--unmeasured`` lists them.
- **The command**: ``glitchygames measure [PATH ...] [--game GAME ...]`` (``measure_command``)
  starts each game (``--game``, else the project's ``[tool.glitchygames] games``) as a child
  with ``--measure`` and combines their exit codes (``combined_exit_code``); with PATHs, each
  is measured by the game its header names, or by the one ``--game``. When the games come from
  the settings, a golden none of them replays is a failure, named with why (a workspace member
  that is not installed: ``uv sync --all-packages``). ``glitchygames unmeasured [--game GAME
  ...]`` reads the recordings and the ledger itself, without starting a game it can name by its
  console script; ``glitchygames clear-published`` is the game flag's work.

Every tool finds the project as verify does (``verify.verify_project_root``: the nearest
directory with ``[tool.glitchygames]``, else the nearest pyproject.toml) and reads its settings
from there; a pending ledger or rows directory in the project's local directory
(``.glitchygames/``) is created through ``settings.ensure_local_directory``.

Exit codes: ``SUCCESS``; ``OPTIONS_REFUSED`` for an unknown commit or uncommitted changes (and
for a seed, ``--allow-dirty`` with ``--skip-dirty``, a game no console script starts given PATHs,
or a ``GAME`` that names nothing); ``UNUSABLE_INPUT`` for settings that can't be read, or a
pending ledger that exists but can't be read (no permission, not UTF-8: ``UnreadableLedgerError``,
naming it, as ``performance-pages`` says it); ``INTERNAL_ERROR`` when a recording could not be
measured (the others are still measured).
"""

from __future__ import annotations

import argparse
import dataclasses
import operator
import os
import re
import sys
import tempfile
import time
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from glitchygames.__main__ import PYGAME_BANNER_VARIABLE
from glitchygames.build_info import SourceRevision, package_source_revision, source_revision
from glitchygames.bundled_demos import BUNDLED_DEMO_DIRECTORY_NAME, DEMO_SUFFIX, bundled_demos
from glitchygames.code_tree import commit_has_landed, landed_ref_exists
from glitchygames.exit_codes import ExitCode
from glitchygames.machine_state import current_machine_state
from glitchygames.process import OutputCapture, TimeoutExpired, run_command
from glitchygames.recording_metrics import (
    describe_processing_fps,
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
from glitchygames.replay.tools.children import (
    ENTRY_POINT_SEPARATOR,
    SCRIPT_PATH_SEPARATOR,
    SCRIPT_SUFFIX,
    UnknownGameError,
    rebaseline_recording_headless,
    recording_console_script,
)
from glitchygames.replay.tools.identity import (
    console_script_identity,
    game_identity,
    game_source_revision,
)
from glitchygames.replay.tools.recordings import game_recordings, golden_paths
from glitchygames.replay.tools.settings import (
    LOCAL_DIRECTORY_NAME,
    PYPROJECT_FILE_NAME,
    ProjectSettings,
    ProjectSettingsError,
    ensure_local_directory,
    load_project_settings,
)
from glitchygames.replay.tools.traces import (
    FORM_DESCRIPTIONS,
    RecordedGameRefusal,
    find_recorded_game,
    refused,
    resolve_named_game,
    run_game_with_tool,
    say,
)
from glitchygames.replay.tools.verify import seed_given, verify_project_root
from glitchygames.tracing import is_bookmarked_copy, read_trace

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from glitchygames.recording_metrics import LedgerRow
    from glitchygames.replay.tools.children import GameLaunch
    from glitchygames.replay.tools.identity import GameIdentity
    from glitchygames.replay.tools.registry import Tool
    from glitchygames.scenes import Scene

# How many of a failed child's last output lines are shown
FAILURE_OUTPUT_LINES = 10
MILLISECONDS_PER_SECOND = 1000.0
# A rebaseline that wrote its recording: matched, or ran on after input the run never got
MEASURED_EXIT_CODES = frozenset({ExitCode.SUCCESS, ExitCode.REBASELINE_INPUT_LOST})
# How many characters of a code tree a line names (a commit is named by its first 7)
CODE_TREE_LABEL_CHARACTERS = 12
COMMIT_LABEL_CHARACTERS = 7
# How a line names a measurement of a game whose commit is unknown (allowed by --allow-dirty)
UNKNOWN_COMMIT_LABEL = 'an unknown commit'
# What starts the tools' own lines on the game (the command's say() names the tool itself)
MEASURE_PREFIX = 'measure:'
UNMEASURED_PREFIX = 'unmeasured:'
# The option measure refuses (registry.RANDOM_SEED_OPTION's flag: the registry imports this
# module), and the two that refuse each other
RANDOM_SEED_FLAG = '--random-seed'
DIRTY_FLAGS = ('--allow-dirty', '--skip-dirty')
# How resolve_game names a GAME read as an installed console script (children.GameForm)
CONSOLE_SCRIPT_FORM = 'console-script'
# What an unmeasured listing's summary counts, "N of M recording(s) not measured": one format
# that report_unmeasured writes (unmeasured_counts) and the command reads back from a child game
# (unmeasured_total), so the two can't drift
UNMEASURED_COUNTS = '{missing} of {total} {noun} not measured'
RECORDING_NOUN = 'recording'
RECORDINGS_NOUN = 'recordings'
UNMEASURED_SUMMARY = re.compile(
    re
    .escape(UNMEASURED_COUNTS)
    .replace(re.escape('{missing}'), r'(?P<missing>\d+)')
    .replace(re.escape('{total}'), r'(?P<total>\d+)')
    .replace(re.escape('{noun}'), f'(?:{RECORDINGS_NOUN}|{RECORDING_NOUN})')
)
# How long a git listing of the project may take (git_listed_files)
GIT_TIMEOUT_SECONDS = 60.0
# What makes a directory a regular package
PACKAGE_MARKER = '__init__.py'
# Directories the project walk for bundled demos never enters: a virtual environment (holding
# this file), caches and installed copies (hidden directories are skipped too)
VIRTUAL_ENVIRONMENT_MARKER = 'pyvenv.cfg'
SKIPPED_DIRECTORY_NAMES = frozenset({'__pycache__', 'node_modules', 'site-packages'})


class MeasureResult(BaseModel):
    """What one ``measure`` did.

    Attributes:
        exit_code: The exit code.
        measured: The recordings measured (by ledger name).
        skipped: The recordings already measured for this commit on this machine.
        failures: The recordings that could not be measured.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    exit_code: ExitCode
    measured: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()


class UnreadableLedgerError(ValueError):
    """A ledger file that exists but can't be read (no permission, not UTF-8), with its path.

    Every tool that reads the pending ledger reports it as ``ExitCode.UNUSABLE_INPUT`` with this
    message: ``measure``, ``unmeasured`` and ``clear-published`` (``read_pending_ledger``) and
    ``performance-pages`` (glitchygames/replay/tools/performance_pages.py).
    """

    def __init__(self, *, path: Path, cause: OSError | UnicodeDecodeError) -> None:
        """Name the file and why it can't be read.

        Args:
            path: The ledger file.
            cause: What reading it raised.

        """
        super().__init__(f'{path}: the ledger cannot be read ({cause})')
        self.path = path


class UnreplayableRecording(BaseModel):
    """A recording no game measured replays, and why (one line).

    Attributes:
        path: The recording.
        reason: Why it cannot be replayed, naming the fix (``recording_console_script``'s
            refusal: a workspace member a plain ``uv sync`` uninstalled, say).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    path: Path
    reason: str


def recording_ledger_name(*, path: Path, project_root: Path, demo_packages: Sequence[str]) -> str:
    """Return the name the ledger gives a recording.

    A recording in the project is named by its path relative to the project
    (``src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz``: what a development install,
    which is editable, finds). One outside it (a bundled demo of a built install, in
    ``site-packages``) is named by its bundled demo record's install name
    (``paddleslap/demos/rally.jsonl.gz``, ``glitchygames.bundled_demos.BundledDemo.install_name``),
    so the record is the name's one source.

    Args:
        path: The recording.
        project_root: The project.
        demo_packages: The import packages whose bundled demos may hold a recording outside the
            project (the game's own).

    Returns:
        The name.

    Raises:
        ValueError: If the recording is neither in the project nor a bundled demo of one of
            those packages.

    """
    resolved = path.resolve()
    root = project_root.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    for demo in bundled_demos(packages=tuple(demo_packages)):
        if demo.path.resolve() == resolved:
            return demo.install_name
    message = f'{path}: neither in the project {project_root} nor an installed bundled demo'
    raise ValueError(message)


def this_machine() -> str:
    """Return this machine's label as ledger rows name it (``recording_metrics.machine_label``).

    Returns:
        The CPU model, else the platform.

    """
    return current_machine_state().cpu_model or machine_description()


class MeasureSettings(BaseModel):
    """How one ``measure`` runs.

    Attributes:
        project_root: The project (recordings are named relative to it).
        project_settings: Its ``[tool.glitchygames]`` (the landed ref, the moved recordings).
        pending_path: The pending ledger (appended to; created when missing).
        revision: The game's source revision: the commit its rows name.
        force: Measure even what is already measured for this commit and machine.
        allow_dirty: Measure despite uncommitted changes, or a commit that is unknown.
        code_tree: The code measured, as a git tree of what can change the replays
            (glitchygames/code_tree.py): the measuring pre-commit hook's
            (scripts/measure_staged_replays.py); the run it measures names it, and a recording
            already measured for it on this machine is skipped. None: measured and skipped by
            commit.
        rows_directory: Write the rows as row files there (``write_row_files``) instead of
            appending them to ``pending_path`` (the hook's quality/replay-ledger/).
        demo_packages: The import packages whose bundled demos are named by their install name
            when outside the project (the game's own).
        game_arguments: More arguments for each rebaselining game, after the rebaseline's.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    project_root: Path
    project_settings: ProjectSettings
    pending_path: Path
    revision: SourceRevision
    force: bool = False
    allow_dirty: bool = False
    code_tree: str | None = None
    rows_directory: Path | None = None
    demo_packages: tuple[str, ...] = ()
    game_arguments: tuple[str, ...] = ()


def is_trial(*, revision: SourceRevision) -> bool:
    """Tell whether a revision's rows can't stand for a commit: uncommitted changes, or none known.

    Args:
        revision: The game's revision.

    Returns:
        True for a checkout with uncommitted changes or an unknown commit.

    """
    return revision.commit is None or bool(revision.uncommitted_changes)


def _refusal(*, revision: SourceRevision, allow_dirty: bool) -> str | None:
    """Say why a revision can't be measured, or None when it can.

    An unknown commit is refused as uncommitted changes are, unless ``--allow-dirty`` (the
    controller's ruling, Task D3: the game's revision, not the engine's).

    Returns:
        The refusal, or None.

    """
    if allow_dirty:
        return None
    if revision.commit is None:
        return (
            f"Cannot measure: the game's source revision is {revision.source}, not a git "
            'checkout, so its commit is unknown (run it from a checkout, through uv run, or '
            'pass --allow-dirty for a trial)'
        )
    if revision.uncommitted_changes:
        return (
            "Cannot measure: the game's checkout has uncommitted changes, so the rows would not "
            'measure their commit (commit first, or pass --allow-dirty for a trial)'
        )
    return None


def _failure(*, recording: str, message: str) -> None:
    sys.stderr.write(f'{recording}: {message}\n')


def _milliseconds(seconds: float) -> str:
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f} ms'


def measured_code_label(*, commit: str | None, code_tree: str | None) -> str:
    """Name the code a measurement measures, for its lines.

    Args:
        commit: The game's commit, or None when unknown.
        code_tree: The code tree measured, or None (by commit).

    Returns:
        ``code tree <first 12>``, else the commit's first 7 characters, else
        ``UNKNOWN_COMMIT_LABEL``.

    """
    if code_tree is not None:
        return f'code tree {code_tree[:CODE_TREE_LABEL_CHARACTERS]}'
    if commit is None:
        return UNKNOWN_COMMIT_LABEL
    return commit[:COMMIT_LABEL_CHARACTERS]


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
    recording = recording_ledger_name(
        path=path, project_root=settings.project_root, demo_packages=settings.demo_packages
    )
    completed = rebaseline_recording_headless(
        console_script=console_script,
        path=path,
        new_path=new_path,
        game_arguments=settings.game_arguments,
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
        # A trial: uncommitted changes, or an unknown commit, measured under --allow-dirty
        allowed_uncommitted_changes=settings.allow_dirty and is_trial(revision=settings.revision),
    )
    measured_commit = rows[0].commit
    if measured_commit != settings.revision.commit:
        _failure(
            recording=recording,
            message=(
                f"the replay measured commit {measured_commit}, not the game's "
                f'{settings.revision.commit} (is the game installed from its checkout? run '
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
        ``RECORDING: N frames in S s, processing p50 ..., p99 ..., max ..., headroom avg ...
        fps (5% low ..., 5% high ...), K frames changed behaviour, R rows pending`` (the
        headroom FPS of the unpaced replay's processing times:
        ``recording_metrics.describe_processing_fps``; left out for a summary without its
        slice means).

    """
    summary = row.summary
    timing = 'no processing times'
    if summary is not None:
        timing = (
            f'processing p50 {_milliseconds(summary.p50_processing_seconds)}, p99 '
            f'{_milliseconds(summary.p99_processing_seconds)}, max '
            f'{_milliseconds(summary.max_processing_seconds)}'
        )
        headroom = describe_processing_fps(summary=summary)
        if headroom is not None:
            timing = f'{timing}, headroom {headroom}'
    return (
        f'{row.recording}: {row.frame_count} frames in {seconds:.1f} s, {timing}, '
        f'{row.frames_changed} frames changed behaviour, {pending_rows} rows pending'
    )


def is_measured_here(
    *,
    rows: Iterable[LedgerRow],
    recording: str,
    code_tree: str | None,
    commit: str | None,
    machine: str,
) -> bool:
    """Tell whether a recording was measured for this code on this machine already.

    By code tree when one is given (the hook's): any row of that tree, recording and machine.
    Else by commit (``is_measured``); a commit that is unknown is never measured (each trial
    measures again).

    Args:
        rows: The rows known (published, pending and row files).
        recording: The recording's ledger name.
        code_tree: The code tree measured, or None.
        commit: The game's commit, or None when unknown.
        machine: This machine's label.

    Returns:
        True when it is measured.

    """
    if code_tree is not None:
        return any(
            row.code_tree == code_tree and row.recording == recording and row.machine == machine
            for row in rows
        )
    if commit is None:
        return False
    return is_measured(rows=rows, recording=recording, commit=commit, machine=machine)


def _already_measured(
    *,
    settings: MeasureSettings,
    rows: Sequence[LedgerRow],
    recording: str,
    commit: str | None,
    machine: str,
) -> bool:
    """Return whether this recording was measured for this code on this machine already.

    By code tree when the measurement names one (the hook's), else by commit
    (``is_measured_here``).

    Returns:
        True to skip it.

    """
    return is_measured_here(
        rows=rows, recording=recording, code_tree=settings.code_tree, commit=commit, machine=machine
    )


def missing_measurements(
    *,
    rows: Iterable[LedgerRow],
    recordings: Sequence[str],
    code_tree: str | None,
    machine: str,
    commit: str | None = None,
) -> list[str]:
    """Return the recordings with no row for this code on this machine (what ``measure`` measures).

    Moved from scripts/measure_staged_replays.py's ``_fully_measured_here``, which asked whether
    this list was empty.

    Args:
        rows: The rows known (published, pending and row files).
        recordings: The recordings' ledger names.
        code_tree: The code tree measured (the hook's), or None to judge by ``commit``.
        machine: This machine's label (``this_machine``).
        commit: The game's commit when there is no code tree (None: unknown, so nothing is
            measured).

    Returns:
        The recordings not measured, in order.

    """
    known = list(rows)
    return [
        recording
        for recording in recordings
        if not is_measured_here(
            rows=known, recording=recording, code_tree=code_tree, commit=commit, machine=machine
        )
    ]


def rows_to_write(
    *,
    rows: Sequence[LedgerRow],
    held_keys: set[str],
    repository: Path,
    origin_main_present: bool,
    settings: ProjectSettings,
) -> list[LedgerRow]:
    """Return the rows of a rebaselined recording that a measurement writes.

    The newest run (``rows[0]``, the one just measured) is written unless held. A history row (a
    run the recording held) is written only when no row holds it, and its run was measured on a
    commit that is on the project's ``landed-ref`` (``settings.landed_ref``: ours is
    ``origin/main``) with no uncommitted changes: a run of code that never landed would be
    published unconditionally (it names no code tree). With no landed ref to compare with, none
    is written. "Held" compares keys with the recording at its current path
    (``LedgerRow.held_key`` with the project's ``recording-renames``), so a moved recording's
    earlier runs are not written again.

    Args:
        rows: The recording's rows, newest first (``ledger_rows_from_rebaseline``).
        held_keys: The ``held_key`` of every row already held.
        repository: The repository whose landed ref decides what landed.
        origin_main_present: Whether the repository has its landed ref (looked up once).
        settings: The project's settings (``landed-ref``, ``recording-renames``).

    Returns:
        The rows to write, in order.

    """
    renames = settings.recording_renames
    newest, *history = rows
    written = [] if newest.held_key(recording_renames=renames) in held_keys else [newest]
    for row in history:
        commit = row.commit
        if (
            row.held_key(recording_renames=renames) in held_keys
            or not origin_main_present
            or commit is None
            or row.measured_uncommitted_changes
            or not commit_has_landed(
                repository=repository, commit=commit, landed_ref=settings.landed_ref
            )
        ):
            continue
        written.append(row)
    return written


def _origin_main_present(*, settings: MeasureSettings) -> bool:
    """Return whether the repository has its landed ref, which history runs are judged by.

    Says so once when it has none (no history row is written then).

    Returns:
        True when the landed ref (``origin/main`` here) exists.

    """
    landed_ref = settings.project_settings.landed_ref
    if landed_ref_exists(repository=settings.project_root, landed_ref=landed_ref):
        return True
    sys.stdout.write(
        f'No {landed_ref} in this repository: no history rows written (earlier runs count as '
        'landed only on that branch)\n'
    )
    return False


def ensure_directory(*, directory: Path, project_root: Path) -> Path:
    """Create a directory the tools write into, through the local-directory helper when needed.

    One inside the project's local directory (``.glitchygames/``, the default pending ledger's)
    gets that directory made by ``settings.ensure_local_directory`` first, so its ``.gitignore``
    keeps git out of it.

    Args:
        directory: The directory.
        project_root: The project.

    Returns:
        The directory.

    """
    local_directory = project_root / LOCAL_DIRECTORY_NAME
    if directory.absolute().is_relative_to(local_directory.absolute()):
        ensure_local_directory(directory=local_directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write_new_rows(
    *,
    settings: MeasureSettings,
    rows: list[LedgerRow],
    held_keys: set[str],
    origin_main_present: bool,
) -> list[LedgerRow]:
    """Write a recording's rows no row holds yet (see ``rows_to_write``) and return them.

    They are written as row files with ``--rows-directory``, else appended to the pending file
    (which a publish takes, so the same landed rules apply).

    Returns:
        The rows written.

    """
    new_rows = rows_to_write(
        rows=rows,
        held_keys=held_keys,
        repository=settings.project_root,
        origin_main_present=origin_main_present,
        settings=settings.project_settings,
    )
    if settings.rows_directory is None:
        ensure_directory(directory=settings.pending_path.parent, project_root=settings.project_root)
        with settings.pending_path.open('a', encoding='utf-8') as pending:
            pending.write(ledger_text(rows=new_rows))
    else:
        write_row_files(
            rows=new_rows,
            directory=ensure_directory(
                directory=settings.rows_directory, project_root=settings.project_root
            ),
        )
    return new_rows


def read_pending_ledger(*, path: Path) -> list[LedgerRow]:
    """Read the pending ledger's rows (a missing one has none).

    Args:
        path: The pending ledger.

    Returns:
        Its rows.

    Raises:
        UnreadableLedgerError: If it exists but can't be read (no permission, not UTF-8).

    """
    try:
        return list(read_ledger_file(path=path).rows)
    except (OSError, UnicodeDecodeError) as error:
        raise UnreadableLedgerError(path=path, cause=error) from error


def known_rows(
    *, published_text: str, pending_path: Path, rows_directory: Path | None
) -> list[LedgerRow]:
    """Return every row already held: published, pending and in the rows directory.

    Args:
        published_text: The published ledger's text.
        pending_path: The pending ledger.
        rows_directory: The rows directory, or None.

    Returns:
        The rows, merged (``merge_ledgers``). A pending ledger that exists but can't be read
        raises ``read_pending_ledger``'s ``UnreadableLedgerError``.

    """
    return merge_ledgers(
        ledgers=[
            parse_ledger(text=published_text).rows,
            read_pending_ledger(path=pending_path),
            [] if rows_directory is None else read_row_files(directory=rows_directory),
        ]
    )


def measure(
    *,
    settings: MeasureSettings,
    recordings: Sequence[tuple[str, Path]],
    published_text: str,
) -> MeasureResult:
    """Measure recordings and append their rows to the pending ledger (see the docstring).

    Args:
        settings: The measurement's settings.
        recordings: ``(console script, path)`` pairs to measure.
        published_text: The published ledger's text.

    Returns:
        What was measured, skipped and failed; ``ExitCode.UNUSABLE_INPUT`` and nothing measured
        when the pending ledger exists but can't be read (said on standard error).

    """
    refusal = _refusal(revision=settings.revision, allow_dirty=settings.allow_dirty)
    if refusal is not None:
        sys.stderr.write(f'{refusal}\n')
        return MeasureResult(exit_code=ExitCode.OPTIONS_REFUSED)
    commit = settings.revision.commit
    machine = this_machine()
    try:
        known = known_rows(
            published_text=published_text,
            pending_path=settings.pending_path,
            rows_directory=settings.rows_directory,
        )
    except UnreadableLedgerError as error:
        sys.stderr.write(f'{MEASURE_PREFIX} {error}\n')
        return MeasureResult(exit_code=ExitCode.UNUSABLE_INPUT)
    origin_main_present = _origin_main_present(settings=settings)
    measured_code = measured_code_label(commit=commit, code_tree=settings.code_tree)
    measured: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix='replay-metrics-') as temporary_name:
        for index, (console_script, path) in enumerate(recordings):
            try:
                recording = recording_ledger_name(
                    path=path,
                    project_root=settings.project_root,
                    demo_packages=settings.demo_packages,
                )
            except ValueError as error:
                # A PATH given outside the project: it has no ledger name
                _failure(recording=path.as_posix(), message=str(error.args[0]))
                failures.append(path.as_posix())
                continue
            if not settings.force and _already_measured(
                settings=settings, rows=known, recording=recording, commit=commit, machine=machine
            ):
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
                held_keys={
                    row.held_key(recording_renames=settings.project_settings.recording_renames)
                    for row in known
                },
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
    sys.stdout.write(
        f'Measured {count} recording{"" if count == 1 else "s"} at {measured_code} on {machine} '
        f'({len(skipped)} already measured, {len(failures)} failed) into '
        f'{settings.pending_path if settings.rows_directory is None else settings.rows_directory}\n'
    )
    return MeasureResult(
        exit_code=ExitCode.INTERNAL_ERROR if failures else ExitCode.SUCCESS,
        measured=tuple(measured),
        skipped=tuple(skipped),
        failures=tuple(failures),
    )


def clear_published(*, pending_path: Path, published_text: str) -> None:
    """Remove the pending rows the published ledger holds (a publish took them).

    Args:
        pending_path: The pending ledger (removed when no row is left).
        published_text: The published ledger's text (after the publish).

    A pending ledger that exists but can't be read raises ``read_pending_ledger``'s
    ``UnreadableLedgerError``, before anything is changed.

    """
    pending = read_pending_ledger(path=pending_path)
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


def unclaimed_goldens(
    *, games: Sequence[str], settings: ProjectSettings, project_root: Path
) -> list[UnreplayableRecording]:
    """Return the project's goldens that none of its games replays, each with why.

    What measuring every game would silently leave out: a golden of a workspace member that is
    not installed (a plain ``uv sync``), or one whose game is not among the games measured.

    Args:
        games: The games measured (``[tool.glitchygames] games``).
        settings: The project's settings (``golden-globs``).
        project_root: The project.

    Returns:
        The goldens, by path, with the reason each is not measured.

    """
    unclaimed: list[UnreplayableRecording] = []
    for path in golden_paths(settings=settings, project_root=project_root):
        try:
            console_script = recording_console_script(path=path)
        except KeyError as error:
            # The refusal's message (not KeyError's quoted repr), without the path it starts
            # with: the failure line names the recording
            reason = str(error.args[0]).removeprefix(f'{path.as_posix()}: ')
            unclaimed.append(UnreplayableRecording(path=path, reason=reason))
            continue
        if console_script not in games:
            unclaimed.append(
                UnreplayableRecording(
                    path=path,
                    reason=(
                        f'replayed by {console_script}, which is not one of the games measured '
                        '([tool.glitchygames] games)'
                    ),
                )
            )
    return unclaimed


def is_bundled_demo(*, path: Path) -> bool:
    """Tell whether a file is a top-level package's bundled demo: ``<package>/demos/*.jsonl.gz``.

    Its ``demos/`` directory's parent holds ``__init__.py`` and the directory above that none,
    as ``glitchygames.bundled_demos`` finds them in an installed package; bookmarked copies are
    not demos.

    Args:
        path: The file.

    Returns:
        True for a bundled demo; False for a path that is no file (a tracked demo deleted only
        from the working tree, which git still lists).

    """
    package = path.parent.parent
    return (
        path.is_file()
        and path.parent.name == BUNDLED_DEMO_DIRECTORY_NAME
        and path.name.endswith(DEMO_SUFFIX)
        and (package / PACKAGE_MARKER).is_file()
        and not (package.parent / PACKAGE_MARKER).is_file()
        and not is_bookmarked_copy(path=path)
    )


def git_listed_files(*, project_root: Path) -> list[Path] | None:
    """Return the files git keeps in a checkout: tracked, and untracked but not ignored.

    The browser bundles' rule (``git ls-files --cached --others --exclude-standard``,
    scripts/git_checkout.py), so ignored trees (``build/``, ``dist/``, other checkouts inside
    the repository) are none of the project's.

    Args:
        project_root: The project.

    Returns:
        The files (absolute), or None when the project is not in a git checkout (or git is
        missing, or does not answer within ``GIT_TIMEOUT_SECONDS``): the caller then walks the
        project (``walked_files``).

    """
    try:
        listed = run_command(
            command=['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            environment=os.environ,
            timeout_seconds=GIT_TIMEOUT_SECONDS,
            capture_output=OutputCapture.APART,
            working_directory=project_root,
        )
    except OSError, TimeoutExpired:
        return None
    if listed.returncode != 0:
        return None
    return [project_root / name for name in (listed.stdout or '').split('\0') if name]


def walked_files(*, project_root: Path) -> list[Path]:
    """Return the files of a project that is no git checkout, but its hidden trees and environments.

    Hidden directories, virtual environments (``pyvenv.cfg``), caches and installed copies are
    not entered.

    Args:
        project_root: The project.

    Returns:
        The files.

    """
    found: list[Path] = []
    for directory, subdirectories, files in os.walk(project_root):
        here = Path(directory)
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if not name.startswith('.')
            and name not in SKIPPED_DIRECTORY_NAMES
            and not (here / name / VIRTUAL_ENVIRONMENT_MARKER).exists()
        )
        found.extend(here / name for name in files)
    return found


def project_demo_paths(*, project_root: Path) -> list[Path]:
    """Return the bundled demos in the project's own packages (``is_bundled_demo``).

    In a git checkout, among the files git keeps (``git_listed_files``: ignored trees are none of
    the project's); otherwise among all of its files (``walked_files``).

    Args:
        project_root: The project.

    Returns:
        The demos' paths, sorted.

    """
    files = git_listed_files(project_root=project_root)
    if files is None:
        files = walked_files(project_root=project_root)
    return sorted(path for path in files if is_bundled_demo(path=path))


def top_level_package_of_script(*, script: Path) -> str | None:
    """Return the top-level package a script is in (the highest directory with ``__init__.py``).

    Args:
        script: The script.

    Returns:
        The package's name, or None for a script in no package.

    """
    package: str | None = None
    directory = script.resolve().parent
    while (directory / PACKAGE_MARKER).is_file():
        package = directory.name
        directory = directory.parent
    return package


def game_package(*, game: str) -> str | None:
    """Return the top-level import package of a game, in any of the forms GAME takes.

    As ``children.resolve_game`` reads them: a script path (the package it is in, if any), an
    entry point ``MODULE:CALLABLE`` (its module's), an installed console script
    (``identity.console_script_identity``'s), else a module (its own top-level package).

    Args:
        game: The game, as ``[tool.glitchygames] games`` or ``--game`` names it.

    Returns:
        The package, or None for a script in no package.

    """
    if SCRIPT_PATH_SEPARATOR in game or game.endswith(SCRIPT_SUFFIX):
        return top_level_package_of_script(script=Path(game))
    if ENTRY_POINT_SEPARATOR in game:
        return game.partition(ENTRY_POINT_SEPARATOR)[0].partition('.')[0]
    try:
        return console_script_identity(console_script=game).package
    except KeyError:
        return game.partition('.')[0]


def game_packages(*, games: Sequence[str]) -> set[str]:
    """Return the import packages of the games (``game_package``, every GAME form).

    Args:
        games: The games (``[tool.glitchygames] games``).

    Returns:
        Their packages.

    """
    return {package for game in games if (package := game_package(game=game)) is not None}


def unclaimed_demos(*, games: Sequence[str], project_root: Path) -> list[UnreplayableRecording]:
    """Return the demos bundled in the project's packages that none of its games measures.

    A game measures only its own package's demos (``recordings.game_recordings``), so a demo in
    any other package of the project would otherwise be left out without a word (BASE's
    scripts/replay_metrics.py searched every member package and reported it).

    Args:
        games: The games measured (``[tool.glitchygames] games``).
        project_root: The project.

    Returns:
        The demos, by path, with the reason each is not measured and the fix.

    """
    claimed = game_packages(games=games)
    return [
        UnreplayableRecording(
            path=path,
            reason=(
                f'a demo bundled in {path.parent.parent.name}, which none of the games measured '
                'starts: add the console script that starts its game to [tool.glitchygames] '
                'games (one in its [project.scripts] whose entry point is in that package)'
            ),
        )
        for path in project_demo_paths(project_root=project_root)
        if path.parent.parent.name not in claimed
    ]


def unclaimed_recordings(
    *, games: Sequence[str], settings: ProjectSettings, project_root: Path
) -> list[UnreplayableRecording]:
    """Return the project's goldens and demos none of its games measures, each with why.

    Args:
        games: The games measured (``[tool.glitchygames] games``).
        settings: The project's settings (``golden-globs``).
        project_root: The project.

    Returns:
        ``unclaimed_goldens``', then ``unclaimed_demos``'.

    """
    return [
        *unclaimed_goldens(games=games, settings=settings, project_root=project_root),
        *unclaimed_demos(games=games, project_root=project_root),
    ]


def combined_exit_code(*, statuses: Sequence[int]) -> ExitCode:
    """Return how a run over several games (or recordings) exits, from each one's exit status.

    Args:
        statuses: The exit statuses, in the order they ran.

    Returns:
        ``ExitCode.SUCCESS`` when every one succeeded (or there was none); otherwise the first
        failure's own code, or ``ExitCode.INTERNAL_ERROR`` for a status that is no ``ExitCode``
        (a child killed by a signal).

    """
    for status in statuses:
        if status == ExitCode.SUCCESS:
            continue
        try:
            return ExitCode(status)
        except ValueError:
            return ExitCode.INTERNAL_ERROR
    return ExitCode.SUCCESS


def seed_refusal() -> str:
    """Say why measure refuses a seed.

    Returns:
        The message.

    """
    return (
        'measure always rebaselines each recording under its recorded seed (Stage D decision '
        f'17), so that its rows measure the recording as it was made: {RANDOM_SEED_FLAG} is '
        f'refused (to play a recording out under another seed: --replay-trace PATH '
        f'{RANDOM_SEED_FLAG} N)'
    )


def dirty_flags_refusal() -> str:
    """Say why ``--allow-dirty`` and ``--skip-dirty`` are refused together.

    Returns:
        The message.

    """
    return f'{DIRTY_FLAGS[0]} and {DIRTY_FLAGS[1]} are refused together: choose one'


def read_settings(*, project_root: Path, prefix: str) -> ProjectSettings:
    """Read the project's settings, saying so when it has no pyproject.toml (the defaults).

    Args:
        project_root: The project.
        prefix: What starts the line (the tool's).

    Returns:
        The settings (``load_project_settings``', which raises ``ProjectSettingsError`` for
        settings that can't be read).

    """
    if not (project_root / PYPROJECT_FILE_NAME).is_file():
        sys.stderr.write(
            f'{prefix} no {PYPROJECT_FILE_NAME} in {project_root}: using the default settings\n'
        )
    return load_project_settings(project_root=project_root)


def game_revision(*, game: type[Scene] | Scene) -> SourceRevision:
    """Return the revision a game's rows name: its own, else the engine's.

    As ``MeasurementRun.game_or_engine_revision`` reads a run: the engine's only when the game's
    package isn't found (``game_source_revision`` returns None).

    Args:
        game: The game.

    Returns:
        The revision.

    """
    revision = game_source_revision(game=game)
    return source_revision() if revision is None else revision


def identity_revision(*, identity: GameIdentity) -> SourceRevision:
    """Return the revision a game's rows name, from its identity (``game_revision``'s rule).

    Args:
        identity: The game's identity.

    Returns:
        The revision.

    """
    if identity.package_directory is None:
        return source_revision()
    return package_source_revision(package_directory=identity.package_directory)


def pending_path_of(*, given: str | None, settings: ProjectSettings, project_root: Path) -> Path:
    """Return the pending ledger: ``--pending``, else the project's ``pending-ledger``.

    Args:
        given: ``--pending``'s value, or None.
        settings: The project's settings.
        project_root: The project.

    Returns:
        The path.

    """
    return project_root / settings.pending_ledger if given is None else Path(given)


def measure_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--measure [PATH ...]`` on a game: rebaseline its recordings into the ledger.

    Runs in place of the game's run (``run_game_flag_tool``, from ``GameEngine.__init__``): the
    game is never built. Each recording is rebaselined through the game's console script, with
    the game's arguments other than measure's own (``registry.tool_free_arguments``), as the
    command passes those after ``--``.

    Args:
        options: The game's parsed options (``measure``: the PATHs given; ``force``,
            ``allow_dirty``, ``skip_dirty``, ``only``, ``code_tree``, ``rows_directory``,
            ``pending``).
        game: The game (its class, or a scene the game passed in).

    Returns:
        ``measure``'s exit code; ``ExitCode.SUCCESS`` for ``--skip-dirty`` on a trial;
        ``ExitCode.OPTIONS_REFUSED`` for a seed, both dirty flags, or PATHs for a game no
        console script starts; ``ExitCode.UNUSABLE_INPUT`` for settings or a pending ledger
        that can't be read.

    """
    # Imported here: the tool table imports this module
    from glitchygames.replay.tools.registry import tool_free_arguments, tool_named

    if options.get('random_seed') is not None:
        return refused(message=f'--measure: {seed_refusal()}', exit_code=ExitCode.OPTIONS_REFUSED)
    if options.get('allow_dirty') and options.get('skip_dirty'):
        return refused(
            message=f'--measure: {dirty_flags_refusal()}', exit_code=ExitCode.OPTIONS_REFUSED
        )
    root = verify_project_root(given=None)
    try:
        project_settings = read_settings(project_root=root, prefix=MEASURE_PREFIX)
    except ProjectSettingsError as error:
        return refused(message=f'--measure: {error}', exit_code=ExitCode.UNUSABLE_INPUT)
    revision = game_revision(game=game)
    if options.get('skip_dirty') and is_trial(revision=revision):
        sys.stdout.write(
            "Not measuring the replays: the game's checkout has uncommitted changes, or its "
            'commit is unknown\n'
        )
        return ExitCode.SUCCESS
    identity = game_identity(game=game)
    console_script = identity.console_script
    given: list[str] = options['measure']
    if console_script is None:
        if given:
            return refused(
                message=(
                    '--measure: no console script starts this game, and a ledger row names the '
                    'console script that replays its recording (install the game with one in '
                    '[project.scripts])'
                ),
                exit_code=ExitCode.OPTIONS_REFUSED,
            )
        paths: list[Path] = []
    elif given:
        paths = [Path(path).absolute() for path in given]
    else:
        paths = [
            recording.path
            for recording in game_recordings(
                identity=identity, settings=project_settings, project_root=root
            )
        ]
    only: str | None = options.get('only')
    demo_packages = (identity.package,)
    settings = MeasureSettings(
        project_root=root,
        project_settings=project_settings,
        pending_path=pending_path_of(
            given=options.get('pending'), settings=project_settings, project_root=root
        ),
        revision=revision,
        force=bool(options.get('force')),
        allow_dirty=bool(options.get('allow_dirty')),
        code_tree=options.get('code_tree'),
        rows_directory=(
            None if options.get('rows_directory') is None else Path(options['rows_directory'])
        ),
        demo_packages=demo_packages,
        game_arguments=tuple(
            tool_free_arguments(arguments=sys.argv[1:], tool=tool_named(name='measure'))
        ),
    )
    return measure(
        settings=settings,
        recordings=[
            (console_script, path)
            for path in paths
            if console_script is not None
            and selected(path=path, only=only, project_root=root, demo_packages=demo_packages)
        ],
        published_text=published_ledger_text(
            project_root=root, published_ledger=project_settings.published_ledger
        ),
    ).exit_code


def selected(
    *, path: Path, only: str | None, project_root: Path, demo_packages: Sequence[str]
) -> bool:
    """Tell whether ``--only TEXT`` keeps a recording: its ledger name contains TEXT.

    Args:
        path: The recording.
        only: The text, or None to keep every one.
        project_root: The project.
        demo_packages: The packages whose demos are named by their install name.

    Returns:
        True to measure it (a PATH with no ledger name is kept: measuring it says why).

    """
    if only is None:
        return True
    try:
        name = recording_ledger_name(
            path=path, project_root=project_root, demo_packages=demo_packages
        )
    except ValueError:
        return True
    return only in name


def measure_named_recordings(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames measure PATH ...``: each recording measured by its game.

    Its game is the one ``--game`` names, else the one its header names (``find_recorded_game``,
    as ``replay-trace`` finds it); the recordings of one game are measured by one child, given
    them as PATHs, and stopped if it is still running after the project's
    ``game-timeout-seconds``.

    Args:
        tool: The measure tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for each game.

    Returns:
        ``combined_exit_code`` of the children's and the refusals' statuses (a child stopped at
        its timeout: ``ExitCode.INTERNAL_ERROR``), ``ExitCode.OPTIONS_REFUSED`` for more than
        one ``--game`` or one that names nothing, or ``ExitCode.UNUSABLE_INPUT`` when the
        settings can't be read.

    """
    games: list[str] | None = arguments.game
    root: Path = arguments.project_root
    try:
        settings = read_settings(project_root=root, prefix=f'{tool.name}:')
    except ProjectSettingsError as error:
        say(tool=tool, message=str(error))
        return ExitCode.UNUSABLE_INPUT
    paths = [Path(path).absolute() for path in arguments.measure]
    targets: list[tuple[str, GameLaunch, Path]] = []
    statuses: list[int] = []
    if games is not None:
        if len(games) > 1:
            say(
                tool=tool,
                message=(
                    'with PATHs, one --game at most: it names the game that measures them '
                    f'({len(games)} were given)'
                ),
            )
            return ExitCode.OPTIONS_REFUSED
        (game,) = games
        try:
            launch = resolve_named_game(tool=tool, game=game, arguments=arguments)
        except UnknownGameError:
            return ExitCode.OPTIONS_REFUSED
        targets = [(game, launch, path) for path in paths]
    else:
        for path in paths:
            found = find_recorded_game(recording=path, project_root=root)
            if isinstance(found, RecordedGameRefusal):
                _failure(
                    recording=path.as_posix(),
                    message=found.reason.removeprefix(f'{path.as_posix()}: '),
                )
                statuses.append(found.exit_code)
                continue
            name, launch = found
            targets.append((name, launch, path))
    for game, group in groupby(targets, key=operator.itemgetter(0)):
        members = list(group)
        launch = members[0][1]
        statuses.append(
            run_game_with_tool(
                tool=tool,
                arguments=argparse.Namespace(**{
                    **vars(arguments),
                    'measure': [str(path) for _, _, path in members],
                }),
                game_arguments=game_arguments,
                game=game,
                launch=dataclasses.replace(launch, timeout_seconds=settings.game_timeout_seconds),
            )
        )
    return combined_exit_code(statuses=statuses)


def games_to_run(
    *, tool: Tool, arguments: argparse.Namespace
) -> tuple[list[str], ProjectSettings, bool] | ExitCode:
    """Return the games a command runs (``--game``'s, else the settings'), and the settings.

    Args:
        tool: The tool.
        arguments: The subcommand's parsed arguments (``project_root`` already found).

    Returns:
        The games, the project's settings, and whether the games came from the settings; or
        ``ExitCode.UNUSABLE_INPUT`` when the settings can't be read (said on standard error).

    """
    try:
        settings = read_settings(project_root=arguments.project_root, prefix=f'{tool.name}:')
    except ProjectSettingsError as error:
        say(tool=tool, message=str(error))
        return ExitCode.UNUSABLE_INPUT
    games: list[str] | None = arguments.game
    if games is not None:
        return games, settings, False
    return list(settings.games), settings, True


def measure_each_game(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames measure``: each game started with ``--measure``, measuring its own.

    When the games come from the settings, the project's goldens none of them replays are
    failures first (``unclaimed_goldens``), named with why.

    Args:
        tool: The measure tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for each game.

    Returns:
        ``combined_exit_code`` of the statuses (``ExitCode.INTERNAL_ERROR`` for an unclaimed
        golden or a game stopped at the project's ``game-timeout-seconds``,
        ``ExitCode.OPTIONS_REFUSED`` for a game that names nothing; the other games still run),
        or ``ExitCode.UNUSABLE_INPUT`` when the settings can't be read.

    """
    found = games_to_run(tool=tool, arguments=arguments)
    if isinstance(found, ExitCode):
        return found
    games, settings, from_settings = found
    root: Path = arguments.project_root
    statuses: list[int] = []
    if from_settings:
        only: str | None = arguments.only
        for unclaimed in unclaimed_recordings(games=games, settings=settings, project_root=root):
            name = recording_ledger_name(path=unclaimed.path, project_root=root, demo_packages=())
            if only is not None and only not in name:
                continue
            _failure(recording=name, message=unclaimed.reason)
            statuses.append(ExitCode.INTERNAL_ERROR)
    if not games:
        say(
            tool=tool,
            message=(
                'no games to measure: the project names none in [tool.glitchygames] games (or '
                '[project.scripts]), and no --game was given'
            ),
        )
    for game in games:
        try:
            launch = resolve_named_game(tool=tool, game=game, arguments=arguments)
        except UnknownGameError:
            statuses.append(ExitCode.OPTIONS_REFUSED)
            continue
        statuses.append(
            run_game_with_tool(
                tool=tool,
                arguments=arguments,
                game_arguments=game_arguments,
                game=game,
                launch=dataclasses.replace(launch, timeout_seconds=settings.game_timeout_seconds),
            )
        )
    return combined_exit_code(statuses=statuses)


def measure_command(*, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]) -> int:
    """Run ``glitchygames measure [PATH ...] [options] [--game GAME ...]``.

    Args:
        tool: The measure tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for each game started.

    Returns:
        ``measure_named_recordings``' exit code with PATHs, ``measure_each_game``'s without;
        ``ExitCode.OPTIONS_REFUSED`` for a seed or both dirty flags (nothing is started).

    """
    if arguments.random_seed is not None or seed_given(arguments=game_arguments):
        say(tool=tool, message=seed_refusal())
        return ExitCode.OPTIONS_REFUSED
    if arguments.allow_dirty and arguments.skip_dirty:
        say(tool=tool, message=dirty_flags_refusal())
        return ExitCode.OPTIONS_REFUSED
    # One project for everything below, found as the game finds it
    arguments.project_root = verify_project_root(given=arguments.project_root)
    if arguments.measure:
        return measure_named_recordings(
            tool=tool, arguments=arguments, game_arguments=game_arguments
        )
    return measure_each_game(tool=tool, arguments=arguments, game_arguments=game_arguments)


def report_unmeasured(
    *, missing: Sequence[str], total: int, code_tree: str | None, machine: str, prefix: str
) -> None:
    """List the unmeasured recordings: one ledger name per line, then a summary on stderr.

    Args:
        missing: The unmeasured recordings' ledger names.
        total: How many recordings were looked at.
        code_tree: The code tree they were judged by, or None (each game's commit).
        machine: This machine's label.
        prefix: What starts the summary (the tool's).

    """
    for name in missing:
        sys.stdout.write(f'{name}\n')
    sys.stdout.flush()
    judged_by = (
        f'for code tree {code_tree[:CODE_TREE_LABEL_CHARACTERS]}'
        if code_tree is not None
        else "at their game's commit"
    )
    counts = unmeasured_counts(missing=len(missing), total=total)
    sys.stderr.write(f'{prefix} {counts} {judged_by} on {machine}\n')


def unmeasured_counts(*, missing: int, total: int) -> str:
    """Return an unmeasured listing's counts, as its summary says them (``UNMEASURED_COUNTS``).

    Args:
        missing: How many are unmeasured.
        total: How many were looked at.

    Returns:
        ``N of M recording(s) not measured``.

    """
    return UNMEASURED_COUNTS.format(
        missing=missing, total=total, noun=RECORDING_NOUN if total == 1 else RECORDINGS_NOUN
    )


def unmeasured_total(*, text: str) -> int | None:
    """Read how many recordings an unmeasured listing looked at, from its summary.

    Args:
        text: The listing's standard error (``report_unmeasured``'s summary is in it).

    Returns:
        The summary's total, or None when there is no summary.

    """
    summary = UNMEASURED_SUMMARY.search(text)
    return None if summary is None else int(summary.group('total'))


def ledger_names(
    *, identity: GameIdentity, settings: ProjectSettings, project_root: Path
) -> list[str]:
    """Return the ledger names of a game's own recordings (``recordings.game_recordings``).

    Args:
        identity: The game's identity.
        settings: The project's settings.
        project_root: The project.

    Returns:
        The names, in ``game_recordings``' order.

    """
    return [
        recording_ledger_name(
            path=recording.path, project_root=project_root, demo_packages=(identity.package,)
        )
        for recording in game_recordings(
            identity=identity, settings=settings, project_root=project_root
        )
    ]


def unmeasured_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--unmeasured`` on a game: list its recordings ``--measure`` would measure.

    Runs in place of the game's run, which never starts.

    Args:
        options: The game's parsed options (``code_tree``, ``rows_directory``, ``pending``).
        game: The game (its class, or a scene the game passed in).

    Returns:
        ``ExitCode.SUCCESS``, or ``ExitCode.UNUSABLE_INPUT`` for settings or a pending ledger
        that can't be read.

    """
    root = verify_project_root(given=None)
    try:
        settings = read_settings(project_root=root, prefix=UNMEASURED_PREFIX)
    except ProjectSettingsError as error:
        return refused(message=f'--unmeasured: {error}', exit_code=ExitCode.UNUSABLE_INPUT)
    names = ledger_names(identity=game_identity(game=game), settings=settings, project_root=root)
    machine = this_machine()
    code_tree: str | None = options.get('code_tree')
    try:
        known = known_rows(
            published_text=published_ledger_text(
                project_root=root, published_ledger=settings.published_ledger
            ),
            pending_path=pending_path_of(
                given=options.get('pending'), settings=settings, project_root=root
            ),
            rows_directory=(
                None if options.get('rows_directory') is None else Path(options['rows_directory'])
            ),
        )
    except UnreadableLedgerError as error:
        return refused(message=f'--unmeasured: {error}', exit_code=ExitCode.UNUSABLE_INPUT)
    missing = missing_measurements(
        rows=known,
        recordings=names,
        code_tree=code_tree,
        machine=machine,
        commit=game_revision(game=game).commit,
    )
    report_unmeasured(
        missing=missing,
        total=len(names),
        code_tree=code_tree,
        machine=machine,
        prefix=UNMEASURED_PREFIX,
    )
    return ExitCode.SUCCESS


def console_script_unmeasured(
    *,
    console_script: str,
    settings: ProjectSettings,
    project_root: Path,
    known: Sequence[LedgerRow],
    code_tree: str | None,
) -> tuple[int, list[str]]:
    """Return how many recordings a console script's game has, and which are unmeasured.

    Read here, without starting the game (``identity.console_script_identity``): its recordings
    (``ledger_names``), judged by its own commit (``identity_revision``) or the code tree.

    Args:
        console_script: The game's installed console script.
        settings: The project's settings.
        project_root: The project.
        known: The rows already held.
        code_tree: The code tree to judge by, or None (the game's commit).

    Returns:
        The number of its recordings, and the unmeasured ones' ledger names.

    """
    identity = console_script_identity(console_script=console_script)
    names = ledger_names(identity=identity, settings=settings, project_root=project_root)
    return len(names), missing_measurements(
        rows=known,
        recordings=names,
        code_tree=code_tree,
        machine=this_machine(),
        commit=identity_revision(identity=identity).commit,
    )


def child_unmeasured(
    *, tool: Tool, arguments: argparse.Namespace, game: str, launch: GameLaunch
) -> tuple[int, int, list[str]]:
    """List a game's unmeasured recordings by starting it with ``--unmeasured``, and read it back.

    For a game the command can't read without starting it (a script path, ``MODULE:CALLABLE``,
    a module). The child's standard output (its listing) is captured and returned, so it joins
    the command's own listing (which the pre-commit hook reads, redirected in its own process),
    and its summary's count joins the command's; its standard error is passed on. pygame's
    banner is hidden in the child, so its standard output is the listing alone.

    Args:
        tool: The unmeasured tool.
        arguments: The subcommand's parsed arguments.
        game: The game, as named.
        launch: How to start it.

    Returns:
        The child's exit status, how many recordings it looked at (its summary's count, else
        how many it listed), and the ledger names it listed.

    """
    say(tool=tool, message=f'running {game} ({FORM_DESCRIPTIONS[launch.form]})')
    finished = run_command(
        command=[*launch.command, *tool.child_arguments(arguments=arguments)],
        environment={**os.environ, PYGAME_BANNER_VARIABLE: '1'},
        timeout_seconds=None,
        capture_output=OutputCapture.APART,
        working_directory=arguments.project_root,
    )
    error = finished.stderr or ''
    sys.stderr.write(error)
    listed = [line for line in (finished.stdout or '').splitlines() if line.strip()]
    total = unmeasured_total(text=error)
    return finished.returncode, len(listed) if total is None else total, listed


def unmeasured_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames unmeasured [options] [--game GAME ...]``.

    A game named by its installed console script is read here, without starting it
    (``console_script_unmeasured``). A game in another form is started as a child with
    ``--unmeasured``, which lists its own. When the games come from the settings, a golden none
    of them replays is listed too (it is never measured; ``measure`` reports it as a failure),
    its reason on standard error.

    Args:
        tool: The unmeasured tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: Always empty (the tool runs no game: the command refuses ``--``).

    Returns:
        ``combined_exit_code`` of the games' statuses (``ExitCode.OPTIONS_REFUSED`` for a game
        that names nothing or isn't installed), or ``ExitCode.UNUSABLE_INPUT`` when the
        settings or the pending ledger can't be read.

    """
    # The tool runs no game, so the command refuses arguments after --: always empty
    del game_arguments
    arguments.project_root = verify_project_root(given=arguments.project_root)
    root: Path = arguments.project_root
    found = games_to_run(tool=tool, arguments=arguments)
    if isinstance(found, ExitCode):
        return found
    games, settings, from_settings = found
    code_tree: str | None = arguments.code_tree
    try:
        known = known_rows(
            published_text=published_ledger_text(
                project_root=root, published_ledger=settings.published_ledger
            ),
            pending_path=pending_path_of(
                given=arguments.pending, settings=settings, project_root=root
            ),
            # A path option's value is the text given (registry.KIND_SETTINGS)
            rows_directory=(
                None if arguments.rows_directory is None else Path(arguments.rows_directory)
            ),
        )
    except UnreadableLedgerError as error:
        say(tool=tool, message=str(error))
        return ExitCode.UNUSABLE_INPUT
    statuses: list[int] = []
    missing: list[str] = []
    total = 0
    for game in games:
        try:
            launch = resolve_named_game(tool=tool, game=game, arguments=arguments)
        except UnknownGameError:
            statuses.append(ExitCode.OPTIONS_REFUSED)
            continue
        if launch.form != CONSOLE_SCRIPT_FORM:
            status, count, unmeasured = child_unmeasured(
                tool=tool, arguments=arguments, game=game, launch=launch
            )
            statuses.append(status)
            total += count
            missing.extend(unmeasured)
            continue
        count, unmeasured = console_script_unmeasured(
            console_script=game,
            settings=settings,
            project_root=root,
            known=known,
            code_tree=code_tree,
        )
        total += count
        missing.extend(unmeasured)
    if from_settings:
        for unclaimed in unclaimed_recordings(games=games, settings=settings, project_root=root):
            name = recording_ledger_name(path=unclaimed.path, project_root=root, demo_packages=())
            say(tool=tool, message=f'{name}: {unclaimed.reason}')
            missing.append(name)
            total += 1
    report_unmeasured(
        missing=missing,
        total=total,
        code_tree=code_tree,
        machine=this_machine(),
        prefix=f'glitchygames {tool.name}:',
    )
    return combined_exit_code(statuses=statuses)


def clear_published_in(*, project_root: Path, pending: str | None, prefix: str) -> ExitCode:
    """Remove the pending rows the project's published ledger holds.

    Args:
        project_root: The project.
        pending: ``--pending``'s value, or None (the project's ``pending-ledger``).
        prefix: What starts a line about the settings (the tool's).

    Returns:
        ``ExitCode.SUCCESS``, or ``ExitCode.UNUSABLE_INPUT`` for settings or a pending ledger
        that can't be read (said on standard error).

    """
    try:
        settings = read_settings(project_root=project_root, prefix=prefix)
    except ProjectSettingsError as error:
        sys.stderr.write(f'{prefix} {error}\n')
        return ExitCode.UNUSABLE_INPUT
    try:
        clear_published(
            pending_path=pending_path_of(
                given=pending, settings=settings, project_root=project_root
            ),
            published_text=published_ledger_text(
                project_root=project_root, published_ledger=settings.published_ledger
            ),
        )
    except UnreadableLedgerError as error:
        sys.stderr.write(f'{prefix} {error}\n')
        return ExitCode.UNUSABLE_INPUT
    return ExitCode.SUCCESS


def clear_published_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--clear-published`` on a game (the game takes no part: the project's ledger does).

    Args:
        options: The game's parsed options (``pending``).
        game: The game (unused: the pending ledger is the project's).

    Returns:
        ``clear_published_in``'s exit code.

    """
    del game
    return clear_published_in(
        project_root=verify_project_root(given=None),
        pending=options.get('pending'),
        prefix='clear-published:',
    )


def clear_published_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames clear-published [--pending PATH]``.

    Args:
        tool: The clear-published tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: Always empty (the tool runs no game).

    Returns:
        ``clear_published_in``'s exit code.

    """
    del game_arguments
    return clear_published_in(
        project_root=verify_project_root(given=arguments.project_root),
        pending=arguments.pending,
        prefix=f'glitchygames {tool.name}:',
    )
