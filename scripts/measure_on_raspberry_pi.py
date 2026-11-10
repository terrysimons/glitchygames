#!/usr/bin/env python3
"""The pre-push hook that also measures the replays on the Raspberry Pis and copies the rows here.

Run by the pre-commit framework before each push (``.pre-commit-config.yaml``, hook
``raspberry-pi-replay-metrics``), in addition to what this machine measures at each commit
(``scripts/measure_staged_replays.py``, which each Pi's clone runs too, so the rules are the same:
once per code tree per machine). It sends the commit being pushed to a clone on each Pi that only
this uses (``ansible/raspberry_pi_runner.yml`` makes it), measures there, and copies the row files
each Pi staged into this repository's ledger directory, staged.

The Pis (``RASPBERRY_PIS``, the hosts of ``ansible/inventory.yml``'s ``raspberry_pis``) work at
the same time, each in its own thread: the push to its clone, the measurement and fetching its
rows. Their row files never collide (each row file is named for its machine), so fetching needs no
lock. Staging is git's index, which one process at a time may change: it runs once, after every Pi
is done, for every Pi's rows (the owner, 2026-11-08: the row copying runs in parallel). Each line a
Pi prints is prefixed with its name. Any Pi that cannot be reached stops the push before anything
is measured.

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
import os
import shlex
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs ssh with fixed arguments
import sys
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from glitchygames.code_tree import run_git
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The login each Pi is reached with (ansible/inventory.yml's raspberry_pis ansible_user)
RASPBERRY_PI_USER = 'terry'
# The clone ansible/raspberry_pi_runner.yml makes in each Pi's home
RASPBERRY_PI_CLONE = 'glitchygames-measure'
# The branch in that clone that holds what is measured; its checkout is detached from it, as git
# refuses a push to a checked out branch
MEASURED_BRANCH = 'refs/heads/to-measure'
# How each Pi measures the checked out code and stages the rows
MEASURE_COMMAND = 'uv run --locked --extra dev nox -s measure-staged'
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

    """

    name: str
    script_runner: tuple[str, ...]
    clone_url: str
    clone_directory: str
    measure_command: str


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
        measure_status: The measurement's exit status (0: measured).
        fetched: The row files fetched from it, relative to the repository.
        fetch_error: Why its rows could not be fetched, or None.

    """

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    raspberry_pi: RaspberryPi
    measure_status: int
    fetched: tuple[str, ...] = ()
    fetch_error: RuntimeError | None = None


def measure_script(*, raspberry_pi: RaspberryPi, commit: str) -> str:
    """Return the script that measures a commit in the Pi's clone.

    ``git reset`` first: rows an earlier run staged stay on disk, untracked, where a forced
    checkout of a commit without them would delete them. Fetching ``origin/main`` keeps the
    history rows (``measure.rows_to_write``) those of what really landed.

    Args:
        raspberry_pi: The Pi.
        commit: The commit, already pushed to the clone.

    Returns:
        The script.

    """
    return f"""set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd {shlex.quote(raspberry_pi.clone_directory)}
git fetch --quiet origin main
git reset --quiet
git checkout --quiet --detach --force {shlex.quote(commit)}
{raspberry_pi.measure_command}
"""


def archive_script(*, raspberry_pi: RaspberryPi, ledger_directory: str) -> str:
    """Return the script that writes a tar of the Pi's staged row files to standard output.

    Args:
        raspberry_pi: The Pi.
        ledger_directory: Where the rows are, relative to the repository.

    Returns:
        The script.

    """
    return f"""set -euo pipefail
cd {shlex.quote(raspberry_pi.clone_directory)}
git diff --cached --name-only --diff-filter=AM -z -- {shlex.quote(ledger_directory)} |
  tar -cf - --null -T -
"""


def _write_prefixed(*, raspberry_pi: RaspberryPi, line: bytes) -> None:
    """Write one line the Pi printed, prefixed with its name, whole."""
    text = line.decode('utf-8', errors='replace').rstrip('\n')
    with _OUTPUT_LOCK:
        sys.stdout.write(f'{raspberry_pi.name}: {text}\n')
        sys.stdout.flush()


def _run_on_raspberry_pi(
    *, raspberry_pi: RaspberryPi, script: str, capture: bool
) -> subprocess.CompletedProcess[bytes]:
    """Run a script on the Pi.

    Captured, its standard output is returned (standard error shows in the hook). Not captured,
    both show in the hook as the Pi prints them, each line prefixed with the Pi's name.

    Returns:
        The finished process.

    Raises:
        RuntimeError: If the script runner gave no pipes (never, for a Popen given PIPE).

    """
    if capture:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - see the import
            raspberry_pi.script_runner,
            input=script.encode('utf-8'),
            stdout=subprocess.PIPE,
            check=False,
        )
    with subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - see the import
        raspberry_pi.script_runner,
        # Unbuffered, so closing standard input has nothing left to flush into a closed pipe
        bufsize=0,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as process:
        # Popen given PIPE always has both: the check is for the type checkers
        if process.stdin is None or process.stdout is None:
            message = f'no pipes to {raspberry_pi.name}'
            raise RuntimeError(message)
        # A runner that exits without reading the script (ssh that could not connect) closes
        # the pipe: its exit status then reports the failure, as subprocess.run(input=...) does
        with contextlib.suppress(BrokenPipeError):
            process.stdin.write(script.encode('utf-8'))
        with contextlib.suppress(BrokenPipeError):
            process.stdin.close()
        for line in process.stdout:
            _write_prefixed(raspberry_pi=raspberry_pi, line=line)
        returncode = process.wait()
    return subprocess.CompletedProcess(args=raspberry_pi.script_runner, returncode=returncode)


def _fetch_rows(*, repository: Path, raspberry_pi: RaspberryPi, ledger_directory: str) -> list[str]:
    """Copy the Pi's staged row files into the repository, without staging them.

    Safe beside other Pis' fetches: their row files are named for their machines, so no two write
    the same file, and the ledger directory is already there.

    Returns:
        The files written, relative to the repository.

    Raises:
        RuntimeError: If the Pi could not list or send them.

    """
    completed = _run_on_raspberry_pi(
        raspberry_pi=raspberry_pi,
        script=archive_script(raspberry_pi=raspberry_pi, ledger_directory=ledger_directory),
        capture=True,
    )
    if completed.returncode != 0:
        message = (
            f'copying the rows from {raspberry_pi.name} failed with status {completed.returncode}'
        )
        raise RuntimeError(message)
    # tar writes nothing at all for no files on some platforms, which tarfile refuses to read
    if not completed.stdout:
        return []
    with tarfile.open(fileobj=io.BytesIO(completed.stdout)) as archive:
        names = archive.getnames()
        # filter='data' refuses a member that would land outside the repository
        archive.extractall(path=repository, filter='data')
    return names


def _stage_rows(*, repository: Path, names: list[str]) -> list[str]:
    """Stage the fetched row files: once, for every Pi's, as git's index takes one writer.

    Returns:
        The files that now differ from what this repository has committed, relative to it.

    """
    if not names:
        return []
    run_git(repository=repository, arguments=['add', '--', *names])
    return run_git(
        repository=repository, arguments=['diff', '--cached', '--name-only', '--', *names]
    ).splitlines()


def _measure_and_fetch(
    *, repository: Path, raspberry_pi: RaspberryPi, ledger_directory: str, commit: str
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
    measured = _run_on_raspberry_pi(
        raspberry_pi=raspberry_pi,
        script=measure_script(raspberry_pi=raspberry_pi, commit=commit),
        capture=False,
    )
    try:
        fetched = _fetch_rows(
            repository=repository, raspberry_pi=raspberry_pi, ledger_directory=ledger_directory
        )
    except RuntimeError as error:
        return PiOutcome(
            raspberry_pi=raspberry_pi, measure_status=measured.returncode, fetch_error=error
        )
    return PiOutcome(
        raspberry_pi=raspberry_pi, measure_status=measured.returncode, fetched=tuple(fetched)
    )


def _reach(raspberry_pi: RaspberryPi, *, script: str) -> subprocess.CompletedProcess[bytes]:
    """Run a script on a Pi, given positionally for ``ThreadPoolExecutor.map``.

    Returns:
        The finished process.

    """
    return _run_on_raspberry_pi(raspberry_pi=raspberry_pi, script=script, capture=False)


def _measure_and_fetch_on(
    raspberry_pi: RaspberryPi, *, repository: Path, ledger_directory: str, commit: str
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
    commit_name: str,
) -> int:
    """Measure a commit on every Pi at once and bring their rows into the repository.

    Args:
        repository: This repository.
        raspberry_pis: The Pis.
        ledger_directory: Where the rows are, relative to the repository.
        commit_name: The commit to measure, as git can name it here.

    Returns:
        ``SUCCESS`` when every Pi had measured it and no rows came back; ``OPTIONS_REFUSED`` to stop
        the push (a Pi could not be reached, or rows came back to commit first); or the first
        failed measurement's own status.

    Raises:
        RuntimeError: If a Pi could not send its rows (after the other Pis' rows are staged).

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
    measure_one = partial(
        _measure_and_fetch_on,
        repository=repository,
        ledger_directory=ledger_directory,
        commit=commit,
    )
    with ThreadPoolExecutor(max_workers=len(raspberry_pis)) as pool:
        outcomes = list(pool.map(measure_one, raspberry_pis))
    copied = _stage_rows(
        repository=repository, names=[name for outcome in outcomes for name in outcome.fetched]
    )
    for outcome in outcomes:
        if outcome.fetch_error is not None:
            raise RuntimeError(str(outcome.fetch_error)) from outcome.fetch_error
    failed = [outcome for outcome in outcomes if outcome.measure_status != 0]
    for outcome in failed:
        copied_here = [name for name in outcome.fetched if name in copied]
        sys.stderr.write(
            f'raspberry-pi-replay-metrics: measuring on {outcome.raspberry_pi.name} failed '
            f'({len(copied_here)} rows copied and staged); fix it and push again, or push without '
            'measuring on the Pis: SKIP=raspberry-pi-replay-metrics git push ...\n'
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
        commit_name=os.environ.get('PRE_COMMIT_TO_REF', 'HEAD'),
    )


if __name__ == '__main__':
    sys.exit(main())
