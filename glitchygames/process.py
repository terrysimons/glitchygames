"""Child processes: ``run_command``, the engine's one child-process launcher.

Used by the determinism audit's replays (glitchygames/replay/audit.py), a watched replay's
restarts (glitchygames/replay/rebuild.py) and the replay pytest plugin
(glitchygames/testing/replays.py). Children are started with ``subprocess.run``: an argument list,
never a shell, with the environment in place before the child's interpreter starts.

The engine's child commands are its own command line with options changed, and the helpers here
are the one way they are changed (``without_option``, ``with_options_appended``): options are
added after the command's options and before any bare ``--``, after which nothing is an option.

This module is a leaf: it imports only the standard library (no engine, no pygame), so the pytest
plugin can import it at configuration time.
"""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import] — runs the engine's own game commands (argument list, no shell)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# What run_command raises for a child that outlives its timeout (subprocess's own exception,
# named here so callers need not import subprocess)
TimeoutExpired = subprocess.TimeoutExpired
# What run_command returns (subprocess's own class, named here for callers' annotations)
CompletedProcess = subprocess.CompletedProcess
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
