r"""Make the installed pre-push hook survive a non-blocking stdout and stderr.

The rule: **the pre-push hook must clear O_NONBLOCK on its stdout and stderr before it runs
pre-commit.** OpenSSH's ``ssh`` (git's transport for ``git@github.com``) sets O_NONBLOCK on its
inherited stdout and stderr when they are not terminals, and git runs the pre-push hook with
those same open file descriptions, so the flag reaches the hook. pre-commit prints each hook's
captured output in one burst when the hook ends, and ``test-random``'s is large: into a pipe
whose reader lags (``git push 2>&1 | tail``) the write fails with ``BlockingIOError`` (errno 35)
and the push dies after the whole gate passed. The flag belongs to the shared open file
description, so clearing it once persists; ssh does not set it again. On a terminal or into a
file the clear is harmless (bugs/2026-11-20-pre-push-crashed-writing-to-a-non-blocking-pipe.md).

``pre-commit install`` generates the hook (a bash shim), so it is patched afterwards: this
script inserts the clearing step before the shim starts pre-commit. ``.envrc`` runs it after
``pre-commit install`` and also when the hooks already exist, so an existing clone gets it too;
a later ``pre-commit install`` rewrites the shim, and the next ``.envrc`` run patches it again.
It is idempotent, and finds the hooks folder as git does (``git rev-parse --git-path hooks``:
a worktree shares its repository's hooks, and ``core.hooksPath`` is honoured).

Exit codes: ``SUCCESS`` (patched, or already patched); ``MISSING_INPUT`` when there is no
pre-push hook; ``UNUSABLE_INPUT`` when the hook is not a shim this script knows how to patch
(pre-commit's template changed: the rule above still holds, so the script must be updated).

Usage:
    uv run python -m scripts.patch_pre_push_hook [--hook PATH]
"""

from __future__ import annotations

import argparse
import os
import sys
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final, TextIO

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command

if TYPE_CHECKING:
    from collections.abc import Sequence

# Present in a patched hook: what makes patching idempotent
PATCH_MARKER: Final = '# glitchygames: clear O_NONBLOCK'
# The line of pre-commit's shim before which the clearing step goes: the one that starts
# pre-commit (pre-commit's hook template, ``hook-tmpl``)
SHIM_ANCHOR: Final = 'if [ -x "$INSTALL_PYTHON" ]; then'
# What the step runs. It must never fail or block the hook: a descriptor that cannot be made
# blocking (on Windows, where Git for Windows runs this same shim through its bash,
# ``os.set_blocking`` only works on pipes and raises ``OSError`` on a console or a file) is
# left as it is, silently. On POSIX it clears the flag on a pipe, a terminal or a file alike
CLEARING_CODE: Final = """import os
for descriptor in (1, 2):
    try:
        os.set_blocking(descriptor, True)
    except OSError:
        pass"""
# Run before pre-commit starts: the first interpreter found runs CLEARING_CODE (stdout and
# stderr never redirected here: the redirect would be the descriptor cleared). Without an
# interpreter, or if it fails, the hook still runs, as before
CLEARING_STEP: Final = f"""{PATCH_MARKER} on stdout and stderr (scripts/patch_pre_push_hook.py)
for blocking_python in "$INSTALL_PYTHON" python3; do
    if command -v "$blocking_python" > /dev/null; then
        "$blocking_python" -c '{CLEARING_CODE}' || true
        break
    fi
done

"""
GIT_TIMEOUT_SECONDS: Final = 30.0


class PatchOutcome(StrEnum):
    """What ``patch_hook`` did.

    Attributes:
        PATCHED: The clearing step was inserted.
        ALREADY_PATCHED: The hook had it.
        MISSING: There is no hook.
        UNRECOGNISED: The hook has no line to insert the step before.

    """

    PATCHED = 'patched'
    ALREADY_PATCHED = 'already patched'
    MISSING = 'missing'
    UNRECOGNISED = 'unrecognised'


def patched_text(*, text: str) -> str | None:
    """Return a pre-commit shim with the clearing step inserted, or None if it has no anchor.

    Args:
        text: The shim (without the step).

    Returns:
        The shim with the step before the line that starts pre-commit; None when no line is the
        anchor.

    """
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(SHIM_ANCHOR):
            return ''.join([*lines[:index], CLEARING_STEP, *lines[index:]])
    return None


def patch_hook(*, path: Path) -> PatchOutcome:
    """Insert the clearing step into the hook at ``path``, once.

    Args:
        path: The installed ``pre-push`` hook.

    Returns:
        What happened; the file is written only for ``PATCHED`` (permissions kept).

    """
    if not path.is_file():
        return PatchOutcome.MISSING
    text = path.read_text(encoding='utf-8')
    if PATCH_MARKER in text:
        return PatchOutcome.ALREADY_PATCHED
    patched = patched_text(text=text)
    if patched is None:
        return PatchOutcome.UNRECOGNISED
    path.write_text(patched, encoding='utf-8')
    return PatchOutcome.PATCHED


def pre_push_hook_path(*, working_directory: Path) -> Path:
    """Return the pre-push hook's path, as git resolves the hooks folder from a directory.

    Args:
        working_directory: A directory in the repository or one of its worktrees.

    Returns:
        ``<hooks folder>/pre-push``.

    Raises:
        RuntimeError: If git cannot say (not a repository).

    """
    finished = run_command(
        command=['git', 'rev-parse', '--git-path', 'hooks'],
        environment=os.environ,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
        working_directory=working_directory,
    )
    if finished.returncode != 0:
        message = f'git rev-parse --git-path hooks failed: {finished.stderr.strip()}'
        raise RuntimeError(message)
    hooks = Path(finished.stdout.strip())
    return (hooks if hooks.is_absolute() else working_directory / hooks) / 'pre-push'


def run(*, arguments: Sequence[str], log: TextIO) -> ExitCode:
    """Patch the pre-push hook: see the module docstring.

    Args:
        arguments: The command line, without the program name.
        log: Where the verdict goes.

    Returns:
        The exit code.

    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument('--hook', type=Path, help='the hook (default: this repository pre-push)')
    options = parser.parse_args(arguments)
    path = options.hook or pre_push_hook_path(working_directory=Path.cwd())
    outcome = patch_hook(path=path)
    log.write(f'{path}: {outcome.value}\n')
    if outcome is PatchOutcome.MISSING:
        return ExitCode.MISSING_INPUT
    if outcome is PatchOutcome.UNRECOGNISED:
        log.write(f'it has no "{SHIM_ANCHOR}" line (pre-commit changed its hook template?)\n')
        return ExitCode.UNUSABLE_INPUT
    return ExitCode.SUCCESS


def main() -> None:
    """Command line: see the module docstring."""
    sys.exit(run(arguments=sys.argv[1:], log=sys.stderr))


if __name__ == '__main__':
    main()
