"""Files the player brings into the game and takes away, where the game's files are not theirs.

On the desktop the game reads and writes the player's own files, so nothing is installed
(``installed_user_files()`` is None) and editors ask for file names in their own dialogs. In a
browser the game's files live in Pyodide's in-memory file system, which the player cannot see,
so the page installs a ``UserFiles`` (browser/browser_user_files.py): opening a file shows the
browser's file picker and copies the chosen file in, and saving hands the saved file to the
player as a download.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path


class UserFiles(Protocol):
    """Moves files between the player's device and the game's file system."""

    def open_file(
        self, *, accepted_extensions: Sequence[str], on_opened: Callable[[Path], None]
    ) -> None:
        """Ask the player for a file; ``on_opened`` gets its copy in the game's file system.

        Returns at once: ``on_opened`` is called later, between frames, and never when the
        player chooses nothing.

        Args:
            accepted_extensions: The extensions offered (``.toml``).
            on_opened: Called with the copy's path.

        """
        ...

    def save_file(self, *, path: Path) -> None:
        """Give the player the file the game saved at ``path`` (a download).

        Args:
            path: The saved file, in the game's file system.

        """
        ...


class _UserFilesRegistry:
    """The process's user files: installed by a platform that needs them (None otherwise)."""

    def __init__(self: Self) -> None:
        """Start with none."""
        self.user_files: UserFiles | None = None


_REGISTRY = _UserFilesRegistry()


def install_user_files(*, user_files: UserFiles | None) -> None:
    """Make ``user_files`` the ones ``installed_user_files()`` returns (None: the desktop's way).

    Args:
        user_files: A browser's user files, or None.

    """
    _REGISTRY.user_files = user_files


def installed_user_files() -> UserFiles | None:
    """Return the installed user files.

    Returns:
        The user files, or None where the game's files are the player's own (the desktop).

    """
    return _REGISTRY.user_files
