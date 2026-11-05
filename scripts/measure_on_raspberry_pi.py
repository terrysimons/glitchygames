#!/usr/bin/env python3
"""The pre-push hook that also measures the replays on the Raspberry Pi and copies the rows here.

Run by the pre-commit framework before each push (``.pre-commit-config.yaml``, hook
``raspberry-pi-replay-metrics``), in addition to what this machine measures at each commit
(``scripts/measure_staged_replays.py``, which the Pi's clone runs too, so the rules are the same:
once per code tree per machine). It sends the commit being pushed to a clone on the Pi that only
this uses (``ansible/raspberry_pi_runner.yml`` makes it), measures there, and copies the row files
the Pi staged into this repository's ledger directory, staged.

The push stops when that brought rows, so they can be committed first. ``quality/`` is outside the
code tree, so a commit of rows alone keeps the tree they name, and the next push finds the Pi
already measured.

Rows left in the Pi's clone by a measurement or push that went no further stay there, untracked:
the next measurement of the same tree counts them, staging them again rather than measuring twice.

``SKIP=raspberry-pi-replay-metrics git push ...`` pushes without measuring on the Pi.

Usage (the framework runs it through nox; by hand, then commit what it stages):
    nox -s measure-on-raspberry-pi
"""

from __future__ import annotations

import io
import os
import shlex
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs ssh with fixed arguments
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path

from glitchygames.code_tree import run_git
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# ansible/inventory.yml's host, and the clone ansible/raspberry_pi_runner.yml makes in its home
RASPBERRY_PI_HOST = 'terry@172.23.23.155'
RASPBERRY_PI_CLONE = 'glitchygames-measure'
# The branch in that clone that holds what is measured; its checkout is detached from it, as git
# refuses a push to a checked out branch
MEASURED_BRANCH = 'refs/heads/to-measure'


@dataclass(frozen=True)
class RaspberryPi:
    """How to reach the Pi and what to run there.

    Attributes:
        script_runner: The command that runs a script given on standard input on the Pi.
        clone_url: Where git pushes the commit to measure.
        clone_directory: The same clone, as the script runner sees it.
        measure_command: Measures the checked out code and stages the rows.

    """

    script_runner: tuple[str, ...]
    clone_url: str
    clone_directory: str
    measure_command: str


THE_RASPBERRY_PI = RaspberryPi(
    # BatchMode: an unreachable or unknown Pi fails the hook, never waiting at a password prompt
    script_runner=(
        'ssh',
        '-o',
        'BatchMode=yes',
        '-o',
        'ConnectTimeout=10',
        RASPBERRY_PI_HOST,
        'bash -s',
    ),
    clone_url=f'{RASPBERRY_PI_HOST}:{RASPBERRY_PI_CLONE}',
    clone_directory=RASPBERRY_PI_CLONE,
    measure_command='uv run --locked --extra dev nox -s measure-staged',
)


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


def _run_on_raspberry_pi(
    *, raspberry_pi: RaspberryPi, script: str, capture: bool
) -> subprocess.CompletedProcess[bytes]:
    """Run a script on the Pi; its standard error, and output unless captured, show in the hook.

    Returns:
        The finished process.

    """
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - see the import
        raspberry_pi.script_runner,
        input=script.encode('utf-8'),
        stdout=subprocess.PIPE if capture else None,
        check=False,
    )


def _copy_rows(*, repository: Path, raspberry_pi: RaspberryPi, ledger_directory: str) -> list[str]:
    """Copy the Pi's staged row files into the repository and stage them.

    Returns:
        The copied files that now differ from what this repository has committed, relative to it.

    Raises:
        RuntimeError: If the Pi could not list or send them.

    """
    completed = _run_on_raspberry_pi(
        raspberry_pi=raspberry_pi,
        script=archive_script(raspberry_pi=raspberry_pi, ledger_directory=ledger_directory),
        capture=True,
    )
    if completed.returncode != 0:
        message = f'copying the rows from the Pi failed with status {completed.returncode}'
        raise RuntimeError(message)
    # tar writes nothing at all for no files on some platforms, which tarfile refuses to read
    if not completed.stdout:
        return []
    with tarfile.open(fileobj=io.BytesIO(completed.stdout)) as archive:
        names = archive.getnames()
        # filter='data' refuses a member that would land outside the repository
        archive.extractall(path=repository, filter='data')
    if not names:
        return []
    run_git(repository=repository, arguments=['add', '--', *names])
    return run_git(
        repository=repository, arguments=['diff', '--cached', '--name-only', '--', *names]
    ).splitlines()


def measure_on_raspberry_pi(
    *, repository: Path, raspberry_pi: RaspberryPi, ledger_directory: str, commit_name: str
) -> int:
    """Measure a commit on the Pi and bring its rows into the repository.

    Args:
        repository: This repository.
        raspberry_pi: The Pi.
        ledger_directory: Where the rows are, relative to the repository.
        commit_name: The commit to measure, as git can name it here.

    Returns:
        ``SUCCESS`` when the Pi had measured it and no rows came back; ``OPTIONS_REFUSED`` to stop
        the push (the Pi could not be reached, or rows came back to commit first); or the
        measurement's own failure status.

    """
    reachable = _run_on_raspberry_pi(raspberry_pi=raspberry_pi, script='true\n', capture=False)
    if reachable.returncode != 0:
        sys.stderr.write(
            'raspberry-pi-replay-metrics: could not reach the Pi; start it and push again, or '
            'push without measuring there: SKIP=raspberry-pi-replay-metrics git push ...\n'
        )
        return ExitCode.OPTIONS_REFUSED
    commit = run_git(repository=repository, arguments=['rev-parse', f'{commit_name}^{{commit}}'])
    # --no-verify: this push goes to the Pi's clone, and must not start this hook again
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
    # What a failed measurement wrote is still valid: copied, as the commit hook stages it
    copied = _copy_rows(
        repository=repository, raspberry_pi=raspberry_pi, ledger_directory=ledger_directory
    )
    if measured.returncode != 0:
        sys.stderr.write(
            f'raspberry-pi-replay-metrics: measuring on the Pi failed ({len(copied)} rows copied '
            'and staged); fix it and push again, or push without measuring there: '
            'SKIP=raspberry-pi-replay-metrics git push ...\n'
        )
        return measured.returncode
    if copied:
        sys.stderr.write(
            f'raspberry-pi-replay-metrics: {len(copied)} rows from the Pi are staged in '
            f'{ledger_directory}; commit them and push again\n'
        )
        return ExitCode.OPTIONS_REFUSED
    sys.stdout.write(f'raspberry-pi-replay-metrics: {commit[:12]} needs no new rows from the Pi\n')
    return ExitCode.SUCCESS


def main() -> int:
    """Run the hook on what is being pushed (the framework names it), or on HEAD by hand.

    Returns:
        ``measure_on_raspberry_pi``'s exit code.

    """
    settings = load_project_settings(project_root=PROJECT_ROOT)
    return measure_on_raspberry_pi(
        repository=PROJECT_ROOT,
        raspberry_pi=THE_RASPBERRY_PI,
        ledger_directory=str(settings.ledger_directory),
        commit_name=os.environ.get('PRE_COMMIT_TO_REF', 'HEAD'),
    )


if __name__ == '__main__':
    sys.exit(main())
