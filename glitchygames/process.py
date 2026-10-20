"""Child processes: ``run_command``, the engine's one child-process launcher.

Used by the determinism audit's replays (glitchygames/replay/audit.py), a watched replay's
restarts (glitchygames/replay/rebuild.py) and the replay pytest plugin
(glitchygames/testing/replays.py). Children are started with ``subprocess.run``: an argument list,
never a shell, with the environment in place before the child's interpreter starts.

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
