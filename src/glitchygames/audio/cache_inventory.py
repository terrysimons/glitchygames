"""The sound cache's operations: what it holds and clearing it (and, below, verifying and filling).

plans/2026-11-14-sound-cache-on-first-use.md, decision 8. GG Sound Studio's cache panel, the
``sound-cache-*`` commands and the tests all ask these functions, so they can never disagree;
nothing copies their logic. Results are frozen pydantic models.

Rules:

1. A cache folder is ``<root>/<game>/sounds/<render version>/`` (``disk_cache.sounds_directory``):
   anything else under the root (a stray file, a folder of another shape, a version that is not a
   number) is not the cache's and is never listed or removed, since the root may be a folder of
   the player's (``GLITCHYGAMES_SOUND_CACHE_ROOT``).
2. A folder's size and count are its sound files' (``*.wav``); a write's temporary files and the
   empty lock files are left out.
3. A render version older than the current one (``spec.AUDIO_RENDER_VERSION``) is **stale**: only
   an older engine wrote it. A newer one is not: another engine on the machine may be newer (a
   branch with a bumped render version shares the platform cache folder), and removing its files
   would make the two engines recompile everything on every launch.
4. ``clear`` removes cache folders only: one game's, every game's, or only the stale ones. A
   game's start clears its own stale versions (``engine._disk_layer``), beside pruning, which
   looks only at the current version's folder.

This module imports pydantic, the standard library and ``audio.disk_cache``/``audio.spec``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from glitchygames.audio.disk_cache import SOUND_SUFFIX, SOUNDS_FOLDER
from glitchygames.audio.spec import AUDIO_RENDER_VERSION


class CachedFolder(BaseModel):
    """One game's sounds for one render version (rule 1).

    Attributes:
        game: The game's folder name (its package name, or ``no-game``).
        render_version: The audio render version its sounds were compiled by.
        path: The folder.
        sound_count: Its sound files.
        size_bytes: Their bytes (rule 2).
        stale: Whether only an older engine could have written it (rule 3).
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    game: str
    render_version: int
    path: Path
    sound_count: int
    size_bytes: int
    stale: bool


class CacheInventory(BaseModel):
    """What a cache root holds, game by game and version by version (by game, then version).

    Attributes:
        root: The cache root.
        folders: Its cache folders.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    root: Path
    folders: tuple[CachedFolder, ...]

    @property
    def total_bytes(self) -> int:
        """Every cache folder's bytes."""
        return sum(folder.size_bytes for folder in self.folders)

    @property
    def stale_bytes(self) -> int:
        """The stale folders' bytes: what ``clear(stale_only=True)`` would free."""
        return sum(folder.size_bytes for folder in self.folders if folder.stale)


class ClearReport(BaseModel):
    """What a ``clear`` removed.

    Attributes:
        removed_sounds: Sound files removed.
        freed_bytes: Their bytes.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    removed_sounds: int
    freed_bytes: int


def inventory(*, root: Path | str) -> CacheInventory:
    """List a cache root's folders (rules 1-3).

    Args:
        root: The cache root (``disk_cache.sound_cache_root``), a path or its text.

    Returns:
        The inventory; empty when the root does not exist.
    """
    root = Path(root)
    folders: list[CachedFolder] = []
    for game_folder in _child_folders(root):
        for version_folder in _child_folders(game_folder / SOUNDS_FOLDER):
            if not version_folder.name.isdigit():
                continue
            sounds = sorted(version_folder.rglob(f'*{SOUND_SUFFIX}'))
            render_version = int(version_folder.name)
            folders.append(
                CachedFolder(
                    game=game_folder.name,
                    render_version=render_version,
                    path=version_folder,
                    sound_count=len(sounds),
                    size_bytes=sum(sound.stat().st_size for sound in sounds),
                    stale=render_version < AUDIO_RENDER_VERSION,
                )
            )
    folders.sort(key=lambda folder: (folder.game, folder.render_version))
    return CacheInventory(root=root, folders=tuple(folders))


def clear(*, root: Path | str, game: str | None = None, stale_only: bool = False) -> ClearReport:
    """Remove cache folders (rule 4): one game's or every game's, all or only the stale ones.

    Args:
        root: The cache root, a path or its text.
        game: Only this game's folders; None for every game's.
        stale_only: Only the stale render versions.

    Returns:
        What was removed.
    """
    chosen = [
        folder
        for folder in inventory(root=root).folders
        if (game is None or folder.game == game) and (folder.stale or not stale_only)
    ]
    for folder in chosen:
        shutil.rmtree(folder.path, ignore_errors=True)
        _remove_if_empty(folder.path.parent)  # <game>/sounds
        _remove_if_empty(folder.path.parent.parent)  # <game>
    return ClearReport(
        removed_sounds=sum(folder.sound_count for folder in chosen),
        freed_bytes=sum(folder.size_bytes for folder in chosen),
    )


def _child_folders(folder: Path) -> list[Path]:
    """A folder's sub-folders, by name (none when it is not a folder).

    Returns:
        The sub-folders.
    """
    if not folder.is_dir():
        return []
    return sorted(child for child in folder.iterdir() if child.is_dir())


def _remove_if_empty(folder: Path) -> None:
    """Remove a folder clearing left empty (one with anything else in it stays)."""
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
