"""Ask git which files a checkout tracks, without the ambient ``GIT_*`` variables."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from glitchygames.process import run_command

GIT_TIMEOUT_SECONDS = 30.0


class NotAGitCheckoutError(RuntimeError):
    """A directory is not inside a git checkout, so git cannot say which files it tracks."""


def environment_without_git_variables() -> dict[str, str]:
    """Return the environment with every ``GIT_*`` variable removed.

    Inside a git hook, ``GIT_DIR`` and ``GIT_INDEX_FILE`` point at the real repository: a git
    command run from a temporary directory would act on that repository instead.

    Returns:
        A copy of ``os.environ`` without the variables git reads.

    """
    return {name: value for name, value in os.environ.items() if not name.startswith('GIT_')}


def run_git(*, arguments: list[str], directory: Path) -> tuple[int, str]:
    """Run git in ``directory`` without the ambient ``GIT_*`` variables.

    Args:
        arguments: The git arguments, after the program.
        directory: The working directory.

    Returns:
        git's exit code and its standard output and error.

    Raises:
        FileNotFoundError: When git is not on PATH.

    """
    git_program = shutil.which('git')
    if git_program is None:
        message = 'git is not on PATH'
        raise FileNotFoundError(message)
    completed = run_command(
        command=[git_program, *arguments],
        environment=environment_without_git_variables(),
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=directory,
    )
    return completed.returncode, completed.stdout


def tracked_files(*, directory: Path) -> list[Path]:
    """Return the files git tracks at or below a directory, relative to it.

    A file git ignores (macOS Finder's ``.DS_Store``) or has not been told about is not tracked,
    so it is not here.

    Args:
        directory: A directory inside a git checkout.

    Returns:
        The tracked files' paths relative to ``directory``, in git's order.

    Raises:
        NotAGitCheckoutError: When ``directory`` is not inside a git checkout.

    """
    returncode, output = run_git(arguments=['ls-files', '-z', '--', '.'], directory=directory)
    if returncode != 0:
        message = f'{directory} is not in a git checkout (git ls-files said: {output.strip()})'
        raise NotAGitCheckoutError(message)
    return [Path(tracked_path) for tracked_path in output.split('\0') if tracked_path]
