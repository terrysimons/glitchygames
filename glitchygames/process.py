"""Child processes: ``run_command`` and ``start_command``, the engine's child-process launchers.

``run_command`` waits for its child: used by the determinism audit's replays
(glitchygames/replay/audit.py), a watched replay's restarts (glitchygames/replay/rebuild.py) and
the replay pytest plugin (glitchygames/testing/replays.py). ``start_command`` does not: the test
suite's driver comparison (tests/driver_comparison.py) runs the suite on the native driver
alongside the dummy run, and ``stop_command`` ends that child with every process it started.
Children get an argument list, never a shell, with the environment in place before the child's
interpreter starts.

The engine's child commands are its own command line with options changed, and the helpers here
are the one way they are changed (``without_option``, ``with_options_appended``): options are
added after the command's options and before any bare ``--``, after which nothing is an option.

This module is a leaf: it imports only the standard library (no engine, no pygame), so the pytest
plugin can import it at configuration time.
"""

from __future__ import annotations

import os
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] — runs the engine's own game commands (argument list, no shell)
import sys
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# What run_command raises for a child that outlives its timeout (subprocess's own exception,
# named here so callers need not import subprocess)
TimeoutExpired = subprocess.TimeoutExpired
# What run_command returns (subprocess's own class, named here for callers' annotations)
CompletedProcess = subprocess.CompletedProcess
# What start_command returns (subprocess's own class, named here for callers' annotations)
RunningProcess = subprocess.Popen
# How long stop_command lets a child end on its own before killing it
STOP_GRACE_SECONDS = 10.0
# Arguments after a bare -- are not options: appended options go before it
END_OF_OPTIONS = '--'


def split_at_end_of_options(*, arguments: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split a command line before its first bare ``--``.

    Args:
        arguments: A command line.

    Returns:
        The arguments before the ``--``, and the ``--`` with everything after it (empty when
        there is none).

    """
    if END_OF_OPTIONS in arguments:
        index = list(arguments).index(END_OF_OPTIONS)
        return list(arguments[:index]), list(arguments[index:])
    return list(arguments), []


def without_option(*, arguments: Sequence[str], option: str, takes_value: bool) -> list[str]:
    """Return ``arguments`` without any occurrence of a long option before a bare ``--``.

    Args:
        arguments: A command line.
        option: The option, e.g. ``--replay-trace``.
        takes_value: True for an option given as ``option VALUE`` or ``option=VALUE`` (both
            removed); False for a flag.

    Returns:
        The other arguments, in order (after a ``--``, all of them).

    """
    options, rest = split_at_end_of_options(arguments=arguments)
    kept: list[str] = []
    skips_next = False
    for argument in options:
        if skips_next:
            skips_next = False
            continue
        if argument == option:
            skips_next = takes_value
            continue
        if takes_value and argument.startswith(f'{option}='):
            continue
        kept.append(argument)
    return [*kept, *rest]


def with_options_appended(*, arguments: Sequence[str], appended: Sequence[str]) -> list[str]:
    """Return ``arguments`` with ``appended`` added after its options (before a bare ``--``).

    Args:
        arguments: A command line.
        appended: Options and their values, in order.

    Returns:
        The command line.

    """
    options, rest = split_at_end_of_options(arguments=arguments)
    return [*options, *appended, *rest]


def run_command(
    *,
    command: Sequence[str],
    environment: Mapping[str, str],
    timeout_seconds: float | None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command (an argument list, never a shell) as a child process and wait for it.

    The engine's one child-process launcher: the audit's replays use it, so do a watched
    replay's restarts (glitchygames/replay/rebuild.py), the replay pytest plugin and the
    end-to-end audit tests.

    Args:
        command: The program and its arguments.
        environment: The child's whole environment, in place before its interpreter starts.
        timeout_seconds: Kill the child (TimeoutExpired) after this long; None waits for as long
            as it runs (a restarted watched replay, glitchygames/replay/rebuild.py).
        capture_output: True to capture standard output and error together in ``stdout``;
            False to let the child write to this process's.

    Returns:
        The finished process (``returncode``; ``stdout`` when captured, else None).

    """
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] — sys.executable with a game's command line plus fixed flags, as an argument list (no shell)
        list(command),
        env=dict(environment),
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.STDOUT if capture_output else None,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )


def start_command(
    *, command: Sequence[str], environment: Mapping[str, str], output: TextIO
) -> subprocess.Popen[str]:
    """Start a command (an argument list, never a shell) as a child process; do not wait.

    On POSIX the child leads a session of its own, so ``stop_command`` can end it with every
    process it started (a pytest run's xdist workers), and a terminal's Ctrl-C reaches only this
    process, which then stops the child.

    Args:
        command: The program and its arguments.
        environment: The child's whole environment, in place before its interpreter starts.
        output: Where the child's standard output and error go (an open file).

    Returns:
        The running process (``wait()`` for its ``returncode``).

    """
    return subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] — sys.executable with the suite's own command line plus fixed flags, as an argument list (no shell)
        list(command),
        env=dict(environment),
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
        # POSIX only (Windows ignores it): stop_command terminates a Windows child alone
        start_new_session=True,
    )


def stop_command(*, process: subprocess.Popen[str]) -> None:
    """End a child ``start_command`` started, with every process in its group, and reap it.

    The group is asked to stop (SIGTERM; on Windows, the child is terminated) and killed if it
    is still running after STOP_GRACE_SECONDS. A child that has already ended is only reaped.

    Args:
        process: The child.

    """
    if process.poll() is not None:
        return
    if sys.platform == 'win32':  # pragma: no cover - the suite runs on macOS and Linux
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        if sys.platform == 'win32':  # pragma: no cover - the suite runs on macOS and Linux
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
