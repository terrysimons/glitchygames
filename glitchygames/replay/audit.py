"""The determinism audit (``--audit``): replay a recording twice in fresh processes and compare.

``--replay-trace PATH --audit`` does not replay in-process. It runs the same command again
(``audit_command``: this interpreter, ``sys.orig_argv`` with ``--no-audit`` and
``--replay-unpaced`` added) as two child processes, each with ``--replay-digest <temp file>``,
``SDL_VIDEODRIVER=dummy``, ``SDL_AUDIODRIVER=dummy`` and ``PYTHONHASHSEED`` set to one of
``AUDIT_HASH_SEEDS``. Fresh processes are the point: they give fresh engine state and different
hash seeds, so set and dict ordering bugs show up. Each child replays as usual (with
``--replay-fps recorded``: the audit refuses ``real``) and writes its digest file
(``write_digest_file``): one SHA-256 per replayed frame (``frame_digest`` of the frame as the
replay sampled it), then its divergence summary.

What is compared: the sampled frame only (the active scene's class, and each sprite's ``rect``,
``visible`` and draw order), as the recording comparison samples it. Pixels, audio and game state
that is not sampled are not compared, so nondeterminism that never moves, hides or reorders a
sprite goes unnoticed.

The audit fails if either run diverged from the recording, exited with a nonzero status, or the
two digest streams differ (the first differing frame is reported: nondeterminism that slipped past
the doors, glitchygames/sources.py). A child that cannot be started, runs longer than
``AUDIT_REPLAY_TIMEOUT_SECONDS`` or writes no readable digest file is an ``AuditRunError``.
``GameEngine`` exits with 0 when the audit passes and 1 when it fails.

Children are started with ``subprocess.run``: an argument list, never a shell, with the
environment set before the child's interpreter starts (PYTHONHASHSEED is read only then). An
interpreter started with ``-E`` or ``-I`` would pass that option on to its children, which would
then ignore PYTHONHASHSEED; ``environment_reaches_children`` tells the engine to refuse.

The plan: plans/2026-10-19-gameplay-replay.md, section 3.5.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] — runs this game's own command again (argument list, no shell)
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# PYTHONHASHSEED per run, so set/dict-order bugs show up
AUDIT_HASH_SEEDS = ('1', '2')

# GameEngine's exit status after an audit
AUDIT_PASSED_EXIT_CODE = 0
AUDIT_FAILED_EXIT_CODE = 1

# Added to the audited command for each child: replay instead of auditing again, and never pace
# (the recorded frame times are served anyway; pacing would only make the audit take real time)
AUDIT_CHILD_ARGUMENTS = ('--no-audit', '--replay-unpaced')

# The child's option that names its digest file
REPLAY_DIGEST_ARGUMENT = '--replay-digest'

# Each child runs headless (read-only: the audit's children all use it)
HEADLESS_ENVIRONMENT_VARIABLES: Mapping[str, str] = MappingProxyType({
    'SDL_VIDEODRIVER': 'dummy',
    'SDL_AUDIODRIVER': 'dummy',
})

# A replay child still running after this long is killed and fails the audit (unpaced replays run
# far faster than real time, so this only catches a hung child)
AUDIT_REPLAY_TIMEOUT_SECONDS = 3600.0

# Digest file fields: one {"frame": n, "digest": "..."} line per frame, then
# {"divergence": <Divergence.describe() or null>}
DIGEST_FRAME_FIELD = 'frame'
DIGEST_FIELD = 'digest'
DIGEST_DIVERGENCE_FIELD = 'divergence'


class AuditRunError(RuntimeError):
    """A replay child of the audit could not be started, hung, or wrote no readable digests."""


@dataclasses.dataclass(frozen=True)
class ReplayDigestRun:
    """One finished replay child of the audit.

    Attributes:
        digests: One digest per replayed frame, in order.
        divergence: ``Divergence.describe()`` of that run, or None.
        exit_code: The child process's exit status.

    """

    digests: list[str]
    divergence: str | None
    exit_code: int


@dataclasses.dataclass(frozen=True)
class AuditResult:
    """Both replay runs of an audit, and where their digest streams first differ.

    Attributes:
        first_run: The run with ``PYTHONHASHSEED`` ``AUDIT_HASH_SEEDS[0]``.
        second_run: The run with ``PYTHONHASHSEED`` ``AUDIT_HASH_SEEDS[1]``.
        first_mismatch_frame: The first frame whose digests differ between the two runs (where
            the shorter stream ends when one is a prefix of the other), or None.

    """

    first_run: ReplayDigestRun
    second_run: ReplayDigestRun
    first_mismatch_frame: int | None

    def is_deterministic(self: Self) -> bool:
        """Return True when both runs matched the recording, exited cleanly and agree.

        Returns:
            True when the audit passes.

        """
        return self._first_failure() is None

    def summary(self: Self) -> str:
        """Describe the audit's outcome on one line.

        Returns:
            ``Audit passed: ...``, or ``Audit failed: `` and the first failure: a run that
            diverged from the recording, a run that exited with a nonzero status, or the first
            frame the two runs differ at.

        """
        failure = self._first_failure()
        if failure is not None:
            return f'Audit failed: {failure}'
        return (
            f'Audit passed: replays with PYTHONHASHSEED {" and ".join(AUDIT_HASH_SEEDS)} matched '
            f'the recording and each other on all {len(self.first_run.digests)} frames'
        )

    def _first_failure(self: Self) -> str | None:
        """Return what failed the audit first, or None when it passes."""
        runs = zip((self.first_run, self.second_run), AUDIT_HASH_SEEDS, strict=True)
        for run_number, (run, hash_seed) in enumerate(runs, start=1):
            run_name = f'replay {run_number} (PYTHONHASHSEED={hash_seed})'
            if run.divergence is not None:
                return f'{run_name} diverged from the recording: {run.divergence}'
            if run.exit_code != 0:
                return f'{run_name} exited with status {run.exit_code}'
        if self.first_mismatch_frame is not None:
            return (
                f'the two replays differ first at frame {self.first_mismatch_frame} '
                '(nondeterminism the recording comparison did not catch)'
            )
        return None


def frame_digest(*, frame_record: dict[str, Any]) -> str:
    """Return the SHA-256 of a frame record's canonical JSON (sorted keys, compact).

    Args:
        frame_record: A replayed frame, as ``glitchygames.tracing.sample_scene_frame`` samples it.

    Returns:
        The hex digest.

    """
    canonical = json.dumps(frame_record, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def write_digest_file(*, path: Path, digests: Sequence[str], divergence: str | None) -> None:
    """Write a replay's digest file: one line per frame, then the divergence line.

    Args:
        path: Where to write it.
        digests: One digest per replayed frame, in order.
        divergence: ``Divergence.describe()`` of the replay, or None.

    """
    lines = [
        json.dumps({DIGEST_FRAME_FIELD: frame_number, DIGEST_FIELD: digest})
        for frame_number, digest in enumerate(digests)
    ]
    lines.append(json.dumps({DIGEST_DIVERGENCE_FIELD: divergence}))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def read_digest_file(*, path: Path) -> tuple[list[str], str | None]:
    """Read a digest file written by ``write_digest_file``.

    Args:
        path: The digest file.

    Returns:
        The digests in frame order, and the divergence summary (None when the replay matched).

    Raises:
        ValueError: If the file cannot be read or is not a complete digest file (a line that is
            not JSON, frames out of order or without a digest, no divergence line last).

    """
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError as error:
        message = f'cannot read {path}: {error}'
        raise ValueError(message) from error
    try:
        records = [json.loads(line) for line in lines]
    except json.JSONDecodeError as error:
        message = f'{path} is not JSON lines: {error}'
        raise ValueError(message) from error
    if not records or DIGEST_DIVERGENCE_FIELD not in records[-1]:
        message = f'{path} does not end with a {DIGEST_DIVERGENCE_FIELD!r} line'
        raise ValueError(message)
    digests: list[str] = []
    for frame_number, record in enumerate(records[:-1]):
        if record.get(DIGEST_FRAME_FIELD) != frame_number or DIGEST_FIELD not in record:
            message = f'{path}: line {frame_number + 1} is not the digest of frame {frame_number}'
            raise ValueError(message)
        digests.append(str(record[DIGEST_FIELD]))
    divergence = records[-1][DIGEST_DIVERGENCE_FIELD]
    return digests, None if divergence is None else str(divergence)


def audit_command(*, original_argv: Sequence[str]) -> list[str]:
    """Return the command each replay child of an audit runs (before its digest file is added).

    Args:
        original_argv: The audited process's command line (``sys.orig_argv``: the interpreter,
            its options, the game and its arguments).

    Returns:
        The same command run by this interpreter (``sys.executable``, so a relative interpreter
        name needs no PATH lookup), with ``AUDIT_CHILD_ARGUMENTS`` added: ``--no-audit``
        overrides the ``--audit`` given earlier, as the last occurrence of an option wins.

    """
    return [sys.executable, *original_argv[1:], *AUDIT_CHILD_ARGUMENTS]


def environment_reaches_children() -> bool:
    """Return whether this interpreter's children will read PYTHONHASHSEED.

    ``audit_command`` runs the interpreter's own options again, so a parent started with ``-E``
    or ``-I`` (``sys.flags.ignore_environment``) would start children that ignore it.

    Returns:
        False when the interpreter ignores the environment (the audit must refuse to run).

    """
    return not sys.flags.ignore_environment


def run_command(
    *,
    command: Sequence[str],
    environment: Mapping[str, str],
    timeout_seconds: float,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command (an argument list, never a shell) as a child process and wait for it.

    The engine's one child-process launcher: the audit's replays use it, and so do the
    end-to-end audit tests.

    Args:
        command: The program and its arguments.
        environment: The child's whole environment, in place before its interpreter starts.
        timeout_seconds: Kill the child (subprocess.TimeoutExpired) after this long.
        capture_output: True to capture standard output and error together in ``stdout``;
            False to let the child write to this process's.

    Returns:
        The finished process (``returncode``; ``stdout`` when captured, else None).

    """
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] — sys.executable with the user's own command line plus fixed flags, as an argument list (no shell)
        list(command),
        env=dict(environment),
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.STDOUT if capture_output else None,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )


def _run_replay_subprocess(
    *,
    command: list[str],
    hash_seed: str,
    digest_path: Path,
    timeout_seconds: float = AUDIT_REPLAY_TIMEOUT_SECONDS,
) -> ReplayDigestRun:
    """Replay in a child process with ``PYTHONHASHSEED`` set and read back its digest file.

    The child writes to this process's standard output and error.

    Args:
        command: The replay command (``audit_command``).
        hash_seed: The child's ``PYTHONHASHSEED``.
        digest_path: Where the child writes its digests (``--replay-digest``).
        timeout_seconds: Kill the child after this long.

    Returns:
        The finished run.

    Raises:
        AuditRunError: If the child could not be started, ran longer than ``timeout_seconds``
            or wrote no readable digest file.

    """
    run_name = f'The replay with PYTHONHASHSEED={hash_seed}'
    environment = {**os.environ, **HEADLESS_ENVIRONMENT_VARIABLES, 'PYTHONHASHSEED': hash_seed}
    try:
        process = run_command(
            command=[*command, REPLAY_DIGEST_ARGUMENT, str(digest_path)],
            environment=environment,
            timeout_seconds=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        message = f'{run_name} was still running after {timeout_seconds} seconds; killed'
        raise AuditRunError(message) from error
    except OSError as error:
        message = f'{run_name} could not be started: {error}'
        raise AuditRunError(message) from error
    try:
        digests, divergence = read_digest_file(path=digest_path)
    except ValueError as error:
        message = (
            f'{run_name} exited with status {process.returncode} without writing its digests '
            f'({error})'
        )
        raise AuditRunError(message) from error
    return ReplayDigestRun(digests=digests, divergence=divergence, exit_code=process.returncode)


def _first_mismatch_frame(*, first_digests: list[str], second_digests: list[str]) -> int | None:
    """Return the first frame whose digests differ, or where the shorter stream ends, or None."""
    for frame_number, (first, second) in enumerate(
        zip(first_digests, second_digests, strict=False)
    ):
        if first != second:
            return frame_number
    if len(first_digests) != len(second_digests):
        return min(len(first_digests), len(second_digests))
    return None


def compare_runs(*, first_run: ReplayDigestRun, second_run: ReplayDigestRun) -> AuditResult:
    """Compare the two runs' digest streams.

    Args:
        first_run: The run with ``AUDIT_HASH_SEEDS[0]``.
        second_run: The run with ``AUDIT_HASH_SEEDS[1]``.

    Returns:
        The audit's result.

    """
    return AuditResult(
        first_run=first_run,
        second_run=second_run,
        first_mismatch_frame=_first_mismatch_frame(
            first_digests=first_run.digests, second_digests=second_run.digests
        ),
    )


def audit_recording(*, command: list[str], path: Path) -> AuditResult:
    """Replay a recording twice, in fresh processes with different hash seeds, and compare.

    Args:
        command: The replay command (``audit_command``), which names the recording itself.
        path: The recording (names the temporary digest files' directory and any error).

    Returns:
        The audit's result.

    Raises:
        AuditRunError: If a child could not be started, hung or wrote no readable digest file.

    """
    with tempfile.TemporaryDirectory(prefix=f'{path.name}-audit-') as digest_directory:
        try:
            first_run, second_run = (
                _run_replay_subprocess(
                    command=command,
                    hash_seed=hash_seed,
                    digest_path=Path(digest_directory) / f'replay-{hash_seed}.jsonl',
                )
                for hash_seed in AUDIT_HASH_SEEDS
            )
        except AuditRunError as error:
            message = f'{path}: {error}'
            raise AuditRunError(message) from error
    return compare_runs(first_run=first_run, second_run=second_run)
