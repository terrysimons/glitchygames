#!/usr/bin/env python3
"""The pre-push hook that also measures the replays on the Raspberry Pis and copies the rows here.

Run by the pre-commit framework before each push (``.pre-commit-config.yaml``, hook
``raspberry-pi-replay-metrics``), in addition to what this machine measures at each commit
(``scripts/measure_staged_replays.py``, which each Pi's clone runs too, so the rules are the same:
once per code tree per machine). It sends the commit being pushed to a clone on each Pi that only
this uses (``ansible/raspberry_pi_runner.yml`` makes it), measures there, and copies the row files
of the pushed commit's code tree into this repository's ledger directory, staged.

The Pis (``RASPBERRY_PIS``, the hosts of ``ansible/inventory.yml``'s ``raspberry_pis``) work at
the same time, each in its own thread: the push to its clone, the measurement and fetching its
rows. Their row files never collide (each row file is named for its machine), so fetching needs no
lock here. Staging is git's index, which one process at a time may change: it runs once, after
every Pi is done, for every Pi's rows (the owner, 2026-11-08: the row copying runs in parallel).
Each line a Pi prints is prefixed with its name. Any Pi that cannot be reached stops the push
before anything is measured.

One push at a time on each Pi (BUGS.md #273). Each Pi has one clone, and two pushes made at once
(two sessions, two branches) used to check their commits out into it in the middle of each
other's measurement: rows labelled with one push's code tree measured the other's code, replays
missed their recordings, and each push copied back the other's rows. Now one script, run in one
ssh session (``measure_script``), does a Pi's whole part under an exclusive ``flock`` on
``RASPBERRY_PI_LOCK``, beside the clone: the checkout, the measurement, a check that the clone's
HEAD is still the pushed commit, and the archive of its rows, sent back on standard output
(everything else the Pi prints goes to standard error, which the hook shows). Nothing can change
the clone between measuring and archiving, because they are the same locked run; the lock is the
kernel's, released when the script (and anything it started that still holds the descriptor)
exits, so a run killed part way leaves no stale lock. A run that finds the lock taken says once
that it is waiting, and gives up after ``LOCK_TIMEOUT_SECONDS``, failing the push (it never
measures without the lock). A clone per push would also keep pushes apart, but each would need
its own ``uv`` environment and checkout on the Pi's SD card, and two pushes would then measure at
once on the same small machine, skewing both measurements; one clone, taken in turn, measures
each push alone. ``flock`` is util-linux's, part of every Debian and Ubuntu install (the playbook
names it). The ``git push`` to the clone happens before the lock: it only moves the
``MEASURED_BRANCH`` ref, and the script checks the commit out by its hash, whose objects stay
(the ref's reflog holds them) whatever a later push does to the ref.

Only the pushed tree's rows come back. The archive holds only the staged row files whose names
lead with the pushed commit's code tree (``recording_metrics.row_file_name``), plus the history
rows the measurement wrote (``history-...``: a recording's earlier runs that landed, which name no
code tree). Here every fetched row is checked again, by its name and by the ``code_tree`` inside
it (the code tree this repository computes for the commit, as ``measure`` does:
``code_tree.commit_code_tree`` with the commit's own measured paths), and a Pi that sends any
other row has none of its rows copied: the hook fails naming them.

The push stops when that brought rows, so they can be committed first. ``quality/`` is outside the
code tree, so a commit of rows alone keeps the tree they name, and the next push finds the Pis
already measured.

Rows left in a Pi's clone by a measurement or push that went no further stay there, untracked:
the next measurement of the same tree counts them, staging them again rather than measuring twice.

``SKIP=raspberry-pi-replay-metrics git push ...`` pushes without measuring on the Pis.

Usage (the framework runs it through nox; by hand, then commit what it stages):
    nox -s measure-on-raspberry-pi
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs ssh with fixed arguments
import sys
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path, PurePosixPath
from typing import IO, cast

from pydantic import BaseModel, ConfigDict

from glitchygames.code_tree import (
    CodeTreePaths,
    commit_code_tree,
    commit_code_tree_paths,
    run_git,
)
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_metrics import (
    ROW_FILE_HISTORY_PREFIX,
    ROW_FILE_SUFFIX,
    ROW_FILE_TREE_CHARACTERS,
)
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The login each Pi is reached with (ansible/inventory.yml's raspberry_pis ansible_user)
RASPBERRY_PI_USER = 'terry'
# The clone ansible/raspberry_pi_runner.yml makes in each Pi's home
RASPBERRY_PI_CLONE = 'glitchygames-measure'
# The file each run locks, beside the clone (BUGS.md #273: one push at a time per Pi)
RASPBERRY_PI_LOCK = f'{RASPBERRY_PI_CLONE}.lock'
# How long a run waits for another push's run to let go of the lock before failing the push: a
# whole measurement on the Pi 4 (the slower) with room to spare
LOCK_TIMEOUT_SECONDS = 30 * 60
# The branch in that clone that holds what is measured; its checkout is detached from it, as git
# refuses a push to a checked out branch
MEASURED_BRANCH = 'refs/heads/to-measure'
# How each Pi measures the checked out code and stages the rows
MEASURE_COMMAND = 'uv run --locked --extra dev nox -s measure-staged'
# The measuring script's exit status when another push held the lock for the whole wait
LOCK_TIMED_OUT_STATUS = ExitCode.SERVICE_UNAVAILABLE
# Its exit status when the clone's HEAD was no longer the pushed commit after measuring
CHECKOUT_MOVED_STATUS = ExitCode.INTERNAL_ERROR
# Leads the script's standard output once it has measured: the line ``measured <status>``, then
# the archive of the rows
MEASURED_HEADER = b'measured '
# One writer at a time, so two Pis' lines never interleave mid-line
_OUTPUT_LOCK = threading.Lock()


@dataclass(frozen=True)
class RaspberryPi:
    """How to reach a Pi and what to run there.

    Attributes:
        name: Its host in ansible/inventory.yml (``raspberry-pi-4``), which prefixes its output.
        script_runner: The command that runs a script given on standard input on the Pi.
        clone_url: Where git pushes the commit to measure.
        clone_directory: The same clone, as the script runner sees it.
        measure_command: Measures the checked out code and stages the rows.
        lock_file: The file a run locks for its whole part, as the script runner sees it.
        lock_timeout_seconds: How long a run waits for that lock before failing.

    """

    name: str
    script_runner: tuple[str, ...]
    clone_url: str
    clone_directory: str
    measure_command: str
    lock_file: str
    lock_timeout_seconds: int


def raspberry_pi(*, name: str, address: str) -> RaspberryPi:
    """Return the Pi at an address, reached over ssh as RASPBERRY_PI_USER.

    Args:
        name: Its host in ansible/inventory.yml.
        address: Its ansible_host there.

    Returns:
        The Pi.

    """
    login = f'{RASPBERRY_PI_USER}@{address}'
    return RaspberryPi(
        name=name,
        # BatchMode: an unreachable or unknown Pi fails the hook, never waiting at a password
        # prompt
        script_runner=('ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', login, 'bash -s'),
        clone_url=f'{login}:{RASPBERRY_PI_CLONE}',
        clone_directory=RASPBERRY_PI_CLONE,
        measure_command=MEASURE_COMMAND,
        lock_file=RASPBERRY_PI_LOCK,
        lock_timeout_seconds=LOCK_TIMEOUT_SECONDS,
    )


# ansible/inventory.yml's raspberry_pis, host by host (tests/test_measure_on_raspberry_pi.py)
RASPBERRY_PIS = (
    raspberry_pi(name='raspberry-pi-4', address='172.23.23.155'),
    raspberry_pi(name='raspberry-pi-5', address='172.23.23.161'),
)


class PiOutcome(BaseModel):
    """How one Pi's measurement went, before its rows are staged.

    Attributes:
        raspberry_pi: The Pi.
        measure_status: The measurement's exit status (0: measured), or the script's own when it
            stopped before measuring or before sending rows.
        fetched: The row files fetched from it, relative to the repository.
        fetch_error: Why its rows could not be fetched, or None.
        refusal: Why the Pi measured nothing or sent no rows, for the hook's message (the lock
            not taken in time, the checkout moved), or None.

    """

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    raspberry_pi: RaspberryPi
    measure_status: int
    fetched: tuple[str, ...] = ()
    fetch_error: RuntimeError | None = None
    refusal: str | None = None


def _row_file_patterns(*, ledger_directory: str, code_tree: str) -> tuple[str, str]:
    """Return the git pathspecs of a code tree's row files and of history rows.

    Returns:
        The two pathspecs, relative to the repository.

    """
    tree_prefix = code_tree[:ROW_FILE_TREE_CHARACTERS]
    return (
        f'{ledger_directory}/{tree_prefix}-*{ROW_FILE_SUFFIX}',
        f'{ledger_directory}/{ROW_FILE_HISTORY_PREFIX}-*{ROW_FILE_SUFFIX}',
    )


def measure_script(
    *, raspberry_pi: RaspberryPi, commit: str, ledger_directory: str, code_tree: str
) -> str:
    """Return the script that does a Pi's whole part, under its lock (the module docstring).

    Everything it prints goes to standard error; standard output (descriptor 3 once redirected)
    carries only ``measured <status>`` and then the tar of the staged row files of ``code_tree``
    and history rows, written only when the measurement ran and the clone's HEAD is still
    ``commit``. ``git reset`` before the checkout: rows an earlier run staged stay on disk,
    untracked, where a forced checkout of a commit without them would delete them. Fetching
    ``origin/main`` keeps the history rows (``measure.rows_to_write``) those of what really
    landed. The measurement runs in a subshell, so a failure (or an ``exit`` in the command)
    still sends the rows it wrote: they are valid measurements.

    Args:
        raspberry_pi: The Pi.
        commit: The commit, already pushed to the clone (its full hash).
        ledger_directory: Where the rows are, relative to the repository.
        code_tree: The commit's code tree, whose rows are sent.

    Returns:
        The script.

    """
    lock = shlex.quote(raspberry_pi.lock_file)
    quoted_commit = shlex.quote(commit)
    timeout = raspberry_pi.lock_timeout_seconds
    patterns = ' '.join(
        shlex.quote(pattern)
        for pattern in _row_file_patterns(ledger_directory=ledger_directory, code_tree=code_tree)
    )
    return f"""set -euo pipefail
exec 3>&1 1>&2
export PATH="$HOME/.local/bin:$PATH"
if ! command -v flock >/dev/null; then
  echo "flock (util-linux) is not installed here, so nothing was measured"
  exit 127
fi
exec 9>>{lock}
if ! flock --nonblock 9; then
  echo "waiting for the lock {raspberry_pi.lock_file}: another push is measuring here"
  if ! flock --wait {timeout} 9; then
    echo "gave up waiting for the lock {raspberry_pi.lock_file} after {timeout} seconds: \\
another push is still measuring here; nothing was measured"
    exit {int(LOCK_TIMED_OUT_STATUS)}
  fi
fi
cd {shlex.quote(raspberry_pi.clone_directory)}
git fetch --quiet origin main
git reset --quiet
git checkout --quiet --detach --force {quoted_commit}
set +e
(
  set -e
  {raspberry_pi.measure_command}
)
measure_status=$?
set -e
measured_head=$(git rev-parse HEAD)
if [ "$measured_head" != {quoted_commit} ]; then
  echo "the clone's HEAD is $measured_head after measuring, not the pushed {commit}: \\
something moved the checkout during the measurement, so no rows are sent"
  exit {int(CHECKOUT_MOVED_STATUS)}
fi
printf '{MEASURED_HEADER.decode('ascii')}%d\\n' "$measure_status" >&3
git diff --cached --name-only --diff-filter=AM -z -- {patterns} | tar -cf - --null -T - >&3
"""


def _write_prefixed(*, raspberry_pi: RaspberryPi, line: bytes) -> None:
    """Write one line the Pi printed, prefixed with its name, whole."""
    text = line.decode('utf-8', errors='replace').rstrip('\n')
    with _OUTPUT_LOCK:
        sys.stdout.write(f'{raspberry_pi.name}: {text}\n')
        sys.stdout.flush()


def _write_each_line_prefixed(*, raspberry_pi: RaspberryPi, stream: IO[bytes]) -> None:
    """Write every line of a stream as the Pi prints it, prefixed with its name."""
    for line in stream:
        _write_prefixed(raspberry_pi=raspberry_pi, line=line)


def _run_on_raspberry_pi(
    *, raspberry_pi: RaspberryPi, script: str
) -> subprocess.CompletedProcess[bytes]:
    """Run a script on the Pi: its standard output returned, its standard error shown.

    Each line of standard error shows in the hook as the Pi prints it, prefixed with the Pi's
    name (read on a thread of its own, so neither pipe can fill while the other is read).

    Returns:
        The finished process, with its standard output.

    Raises:
        RuntimeError: If the script runner gave no pipes (never, for a Popen given PIPE).

    """
    with subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - see the import
        raspberry_pi.script_runner,
        # Unbuffered, so closing standard input has nothing left to flush into a closed pipe
        bufsize=0,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        # Popen given PIPE always has all three: the check is for the type checkers
        if process.stdin is None or process.stdout is None or process.stderr is None:
            message = f'no pipes to {raspberry_pi.name}'
            raise RuntimeError(message)
        printer = threading.Thread(
            target=_write_each_line_prefixed,
            kwargs={'raspberry_pi': raspberry_pi, 'stream': process.stderr},
        )
        printer.start()
        # A runner that exits without reading the script (ssh that could not connect) closes
        # the pipe: its exit status then reports the failure, as subprocess.run(input=...) does
        with contextlib.suppress(BrokenPipeError):
            process.stdin.write(script.encode('utf-8'))
        with contextlib.suppress(BrokenPipeError):
            process.stdin.close()
        output = process.stdout.read()
        returncode = process.wait()
        printer.join()
    return subprocess.CompletedProcess(
        args=raspberry_pi.script_runner, returncode=returncode, stdout=output
    )


def _is_row_of_tree(
    *, archive: tarfile.TarFile, member: tarfile.TarInfo, ledger_directory: str, code_tree: str
) -> bool:
    """Return whether an archived file is a row of the code tree, or a history row.

    By its place, its name and the ``code_tree`` it holds: a row named for the tree must hold
    the tree, and a history row must hold none.

    Returns:
        True for a row this push may stage.

    """
    path = PurePosixPath(member.name)
    is_tree_row = path.name.startswith(f'{code_tree[:ROW_FILE_TREE_CHARACTERS]}-')
    is_history_row = path.name.startswith(f'{ROW_FILE_HISTORY_PREFIX}-')
    is_row_file = (
        member.isfile()
        and path.parent == PurePosixPath(ledger_directory)
        and path.name.endswith(ROW_FILE_SUFFIX)
        and (is_tree_row or is_history_row)
    )
    # A regular file always has contents (extractfile gives None only for other members)
    contents = archive.extractfile(member) if is_row_file else None
    if contents is None:
        return False
    try:
        row: object = json.loads(contents.read())
    except ValueError:
        return False
    expected_tree = code_tree if is_tree_row else None
    return (
        isinstance(row, dict) and cast('dict[str, object]', row).get('code_tree') == expected_tree
    )


def _fetch_rows(
    *,
    repository: Path,
    raspberry_pi: RaspberryPi,
    archive: bytes,
    ledger_directory: str,
    code_tree: str,
) -> list[str]:
    """Copy the row files a Pi sent into the repository, without staging them.

    Every file must be a row of the pushed code tree (or a history row); otherwise none of the
    Pi's rows are copied. Safe beside other Pis' fetches: their row files are named for their
    machines, so no two write the same file, and the ledger directory is already there.

    Returns:
        The files written, relative to the repository.

    Raises:
        RuntimeError: If the Pi sent any file that is not a row of the pushed code tree.

    """
    # tar writes nothing at all for no files on some platforms, which tarfile refuses to read
    if not archive:
        return []
    with tarfile.open(fileobj=io.BytesIO(archive)) as opened:
        members = opened.getmembers()
        refused = [
            member.name
            for member in members
            if not _is_row_of_tree(
                archive=opened,
                member=member,
                ledger_directory=ledger_directory,
                code_tree=code_tree,
            )
        ]
        if refused:
            message = (
                f'{raspberry_pi.name} sent rows that are not of the pushed code tree '
                f'{code_tree[:ROW_FILE_TREE_CHARACTERS]}, so none of its rows were copied: '
                + ', '.join(refused)
            )
            raise RuntimeError(message)
        # filter='data' refuses a member that would land outside the repository
        opened.extractall(path=repository, filter='data')
    return [member.name for member in members]


def _stage_rows(*, repository: Path, names: list[str], code_tree: str) -> list[str]:
    """Stage the fetched row files: once, for every Pi's, as git's index takes one writer.

    Returns:
        The files that now differ from what this repository has committed, relative to it.

    Raises:
        RuntimeError: If a file is not named as a row of the code tree or a history row (never,
            after ``_fetch_rows``' check: nothing is staged then).

    """
    if not names:
        return []
    prefixes = (f'{code_tree[:ROW_FILE_TREE_CHARACTERS]}-', f'{ROW_FILE_HISTORY_PREFIX}-')
    refused = [name for name in names if not PurePosixPath(name).name.startswith(prefixes)]
    if refused:
        message = (
            f'refusing to stage rows that are not of the pushed code tree '
            f'{code_tree[:ROW_FILE_TREE_CHARACTERS]}: ' + ', '.join(refused)
        )
        raise RuntimeError(message)
    run_git(repository=repository, arguments=['add', '--', *names])
    return run_git(
        repository=repository, arguments=['diff', '--cached', '--name-only', '--', *names]
    ).splitlines()


def _refusal(*, raspberry_pi: RaspberryPi, status: int) -> str | None:
    """Return the hook's message for a run that stopped on its own before sending rows.

    Returns:
        The message, or None for any other failure (its own output says why).

    """
    if status == LOCK_TIMED_OUT_STATUS:
        return (
            f'another push is measuring on {raspberry_pi.name}: gave up waiting for its lock '
            f'{raspberry_pi.lock_file} after {raspberry_pi.lock_timeout_seconds} seconds, and '
            'measured nothing; push again once it is done'
        )
    if status == CHECKOUT_MOVED_STATUS:
        return (
            f'the checkout on {raspberry_pi.name} moved away from the pushed commit while it was '
            'measured, so none of its rows were copied; push again'
        )
    return None


def _measure_and_fetch(
    *,
    repository: Path,
    raspberry_pi: RaspberryPi,
    ledger_directory: str,
    commit: str,
    code_tree: str,
) -> PiOutcome:
    """Measure a commit on one Pi and fetch its rows: one Pi's whole part, run in its own thread.

    Returns:
        How it went. What a failed measurement wrote is still valid: fetched, as the commit hook
        stages it.

    """
    # --no-verify: this push goes to the Pi's clone, and must not start this hook again. Pushes to
    # different clones read this repository only, so the Pis' pushes may run together
    run_git(
        repository=repository,
        arguments=[
            'push',
            '--no-verify',
            '--force',
            '--quiet',
            raspberry_pi.clone_url,
            f'{commit}:{MEASURED_BRANCH}',
        ],
    )
    completed = _run_on_raspberry_pi(
        raspberry_pi=raspberry_pi,
        script=measure_script(
            raspberry_pi=raspberry_pi,
            commit=commit,
            ledger_directory=ledger_directory,
            code_tree=code_tree,
        ),
    )
    header, _, archive = completed.stdout.partition(b'\n')
    if not header.startswith(MEASURED_HEADER):
        # It stopped before measuring, or before sending rows: nothing to fetch
        return PiOutcome(
            raspberry_pi=raspberry_pi,
            measure_status=completed.returncode,
            refusal=_refusal(raspberry_pi=raspberry_pi, status=completed.returncode),
        )
    measure_status = int(header.removeprefix(MEASURED_HEADER))
    if completed.returncode != 0:
        error = RuntimeError(
            f'copying the rows from {raspberry_pi.name} failed with status {completed.returncode}'
        )
        return PiOutcome(
            raspberry_pi=raspberry_pi, measure_status=measure_status, fetch_error=error
        )
    try:
        fetched = _fetch_rows(
            repository=repository,
            raspberry_pi=raspberry_pi,
            archive=archive,
            ledger_directory=ledger_directory,
            code_tree=code_tree,
        )
    except RuntimeError as error:
        return PiOutcome(
            raspberry_pi=raspberry_pi, measure_status=measure_status, fetch_error=error
        )
    return PiOutcome(
        raspberry_pi=raspberry_pi, measure_status=measure_status, fetched=tuple(fetched)
    )


def _reach(raspberry_pi: RaspberryPi, *, script: str) -> subprocess.CompletedProcess[bytes]:
    """Run a script on a Pi, given positionally for ``ThreadPoolExecutor.map``.

    Returns:
        The finished process.

    """
    return _run_on_raspberry_pi(raspberry_pi=raspberry_pi, script=script)


def _measure_and_fetch_on(
    raspberry_pi: RaspberryPi,
    *,
    repository: Path,
    ledger_directory: str,
    commit: str,
    code_tree: str,
) -> PiOutcome:
    """``_measure_and_fetch``, the Pi given positionally for ``ThreadPoolExecutor.map``.

    Returns:
        How it went.

    """
    return _measure_and_fetch(
        repository=repository,
        raspberry_pi=raspberry_pi,
        ledger_directory=ledger_directory,
        commit=commit,
        code_tree=code_tree,
    )


def _unreachable(*, raspberry_pis: tuple[RaspberryPi, ...]) -> list[RaspberryPi]:
    """Return the Pis that cannot be reached, asking them all at once.

    Returns:
        Those Pis, in the order given.

    """
    reach = partial(_reach, script='true\n')
    with ThreadPoolExecutor(max_workers=len(raspberry_pis)) as pool:
        answers = list(pool.map(reach, raspberry_pis))
    return [
        each for each, answer in zip(raspberry_pis, answers, strict=True) if answer.returncode != 0
    ]


def measure_on_raspberry_pis(
    *,
    repository: Path,
    raspberry_pis: tuple[RaspberryPi, ...],
    ledger_directory: str,
    code_tree_paths: CodeTreePaths,
    commit_name: str,
) -> int:
    """Measure a commit on every Pi at once and bring their rows of its code tree here.

    Args:
        repository: This repository.
        raspberry_pis: The Pis.
        ledger_directory: Where the rows are, relative to the repository.
        code_tree_paths: What a code tree holds when the commit's own pyproject.toml names
            nothing (the project's settings).
        commit_name: The commit to measure, as git can name it here.

    Returns:
        ``SUCCESS`` when every Pi had measured it and no rows came back; ``OPTIONS_REFUSED`` to stop
        the push (a Pi could not be reached, or rows came back to commit first); or the first
        failed measurement's own status (``LOCK_TIMED_OUT_STATUS`` when another push held a Pi's
        lock throughout, ``CHECKOUT_MOVED_STATUS`` when a Pi's checkout moved).

    Raises:
        RuntimeError: If a Pi could not send its rows, or sent a row of another code tree (after
            the other Pis' rows are staged).

    """
    unreachable = _unreachable(raspberry_pis=raspberry_pis)
    if unreachable:
        names = ', '.join(each.name for each in unreachable)
        sys.stderr.write(
            f'raspberry-pi-replay-metrics: could not reach {names}; start it and push again, or '
            'push without measuring on the Pis: SKIP=raspberry-pi-replay-metrics git push ...\n'
        )
        return ExitCode.OPTIONS_REFUSED
    commit = run_git(repository=repository, arguments=['rev-parse', f'{commit_name}^{{commit}}'])
    # The commit's own measured paths, as its measurement on the Pi reads them from its checkout
    code_tree = commit_code_tree(
        repository=repository,
        commit=commit,
        paths=commit_code_tree_paths(
            repository=repository, commit=commit, fallback=code_tree_paths
        ),
    )
    measure_one = partial(
        _measure_and_fetch_on,
        repository=repository,
        ledger_directory=ledger_directory,
        commit=commit,
        code_tree=code_tree,
    )
    with ThreadPoolExecutor(max_workers=len(raspberry_pis)) as pool:
        outcomes = list(pool.map(measure_one, raspberry_pis))
    copied = _stage_rows(
        repository=repository,
        names=[name for outcome in outcomes for name in outcome.fetched],
        code_tree=code_tree,
    )
    for outcome in outcomes:
        if outcome.fetch_error is not None:
            raise RuntimeError(str(outcome.fetch_error)) from outcome.fetch_error
    failed = [outcome for outcome in outcomes if outcome.measure_status != 0]
    for outcome in failed:
        copied_here = [name for name in outcome.fetched if name in copied]
        reason = (
            outcome.refusal
            if outcome.refusal is not None
            else (
                f'measuring on {outcome.raspberry_pi.name} failed ({len(copied_here)} rows copied '
                'and staged); fix it and push again'
            )
        )
        sys.stderr.write(
            f'raspberry-pi-replay-metrics: {reason}, or push without measuring on the Pis: '
            'SKIP=raspberry-pi-replay-metrics git push ...\n'
        )
    if failed:
        return failed[0].measure_status
    if copied:
        sys.stderr.write(
            f'raspberry-pi-replay-metrics: {len(copied)} rows from the Pis are staged in '
            f'{ledger_directory}; commit them and push again\n'
        )
        return ExitCode.OPTIONS_REFUSED
    sys.stdout.write(f'raspberry-pi-replay-metrics: {commit[:12]} needs no new rows from the Pis\n')
    return ExitCode.SUCCESS


def main() -> int:
    """Run the hook on what is being pushed (the framework names it), or on HEAD by hand.

    Returns:
        ``measure_on_raspberry_pis``'s exit code.

    """
    settings = load_project_settings(project_root=PROJECT_ROOT)
    return measure_on_raspberry_pis(
        repository=PROJECT_ROOT,
        raspberry_pis=RASPBERRY_PIS,
        ledger_directory=str(settings.ledger_directory),
        code_tree_paths=settings.code_tree_paths,
        commit_name=os.environ.get('PRE_COMMIT_TO_REF', 'HEAD'),
    )


if __name__ == '__main__':
    sys.exit(main())
