"""The sound cache's operations: what it holds, clearing it, verifying it, filling it.

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
5. ``verify`` reads every sound file back and reports each one that is not well formed, and why
   (``disk_cache.file_problem``, the same check a read makes). It removes nothing: a game's read
   already deletes such a file and compiles the sound again, but silently.
6. ``fill`` puts a game's sounds in its folder ahead of time, with the CRT power-on's (both
   backgrounds'), so even a first launch reads them all (a slow machine's first-launch stall).
   It requests them the way a game's start does, through an ``AudioEngine`` on cache ``disk``
   over the root given, then writes any cacheable sound still without a file: the process shares
   compiled samples, so a sound it held already (GG Sound Studio's case) was neither compiled nor
   written. A live sound compiles nothing and a recorded file is never cached: both are skipped.
   It is idempotent: a sound already kept is counted, not written again.

This module imports pydantic, the standard library and ``audio.disk_cache``/``audio.spec``;
``fill`` imports the audio engine and the CRT power-on's sounds when called (the engine imports
this module).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from glitchygames.audio.disk_cache import (
    DISK_CACHE_LIMIT_BYTES,
    SOUND_SUFFIX,
    SOUNDS_FOLDER,
    DiskSoundCache,
    file_problem,
    sounds_directory,
)
from glitchygames.audio.spec import AUDIO_RENDER_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.effects import Effect
    from glitchygames.audio.instrument import Instrument

    type SoundSource = str | Instrument | Effect


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


class DamagedFile(BaseModel):
    """A sound file that is not well formed (rule 5).

    Attributes:
        path: The file.
        reason: Why.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    path: Path
    reason: str


class VerifyReport(BaseModel):
    """What ``verify`` found.

    Attributes:
        checked: Sound files read.
        damaged: The ones not well formed, in path order.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    checked: int
    damaged: tuple[DamagedFile, ...]


class FillReport(BaseModel):
    """What a ``fill`` did (rule 6).

    Attributes:
        folder: The game's folder for the current render version.
        written: Sounds written now.
        already_kept: Sounds that had their file already.
        skipped: Sounds never cached (live sounds, recorded files).
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    folder: Path
    written: int
    already_kept: int
    skipped: int


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


def verify(*, root: Path | str) -> VerifyReport:
    """Read every cache folder's sound files back and report the damaged ones (rule 5).

    Args:
        root: The cache root, a path or its text.

    Returns:
        What was checked and found.
    """
    checked = 0
    damaged: list[DamagedFile] = []
    for folder in inventory(root=root).folders:
        for path in sorted(folder.path.rglob(f'*{SOUND_SUFFIX}')):
            checked += 1
            try:
                data = path.read_bytes()
            except OSError as error:
                damaged.append(
                    DamagedFile(path=path, reason=f'cannot be read: {error.strerror or error}')
                )
                continue
            problem = file_problem(data)
            if problem is not None:
                damaged.append(DamagedFile(path=path, reason=problem))
    return VerifyReport(checked=checked, damaged=tuple(damaged))


def fill(*, root: Path | str, game_name: str, sounds: Sequence[SoundSource]) -> FillReport:
    """Put a game's sounds, and the CRT power-on's, in its folder ahead of time (rule 6).

    Args:
        root: The cache root, a path or its text.
        game_name: The game's folder (its package name: ``identity.game_package``).
        sounds: Its declared sounds (``Scene.SOUNDS``).

    Returns:
        What was written, already kept and skipped.
    """
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import CacheMode
    from glitchygames.audio.voices import ChannelPartition
    from glitchygames.backgrounds import BackgroundPattern
    from glitchygames.crt_power_on_sound import crt_sound_schedule

    root = Path(root)
    folder = sounds_directory(root=root, game=game_name, render_version=AUDIO_RENDER_VERSION)
    kept_before = {path.stem for path in folder.rglob(f'*{SOUND_SUFFIX}')}
    audio = AudioEngine(
        partition=ChannelPartition(live=(), library=(), legacy_count=0),
        cache=CacheMode.DISK,
        game_name=game_name,
        disk_root=root,
    )
    power_on = {
        crt_sound.name: crt_sound
        for background in BackgroundPattern
        for crt_sound in crt_sound_schedule(background=background)
    }
    requested = [
        *(
            audio.engine_sound(crt_sound.instrument, pitch=crt_sound.pitch, length=crt_sound.length)
            for crt_sound in power_on.values()
        ),
        *(audio.sound(source) for source in sounds),
    ]
    cacheable = {
        sound.identity_key: sound
        for sound in requested
        if not sound.is_live and sound.recorded_file is None
    }
    disk = DiskSoundCache(directory=folder, limit_bytes=DISK_CACHE_LIMIT_BYTES)
    for key, sound in cacheable.items():
        if disk.path_for(identity_key=key).exists() or sound.samples_int16 is None:
            continue
        disk.write(
            identity_key=key,
            samples_int16=sound.samples_int16,
            peak=sound.peak,
            sample_rate=sound.sample_rate,
        )
    # Counted from the folder, not from what was meant to be written
    kept_after = {path.stem for path in folder.rglob(f'*{SOUND_SUFFIX}')}
    already_kept = len(kept_before & cacheable.keys())
    return FillReport(
        folder=folder,
        written=len((kept_after - kept_before) & cacheable.keys()),
        already_kept=already_kept,
        skipped=len({sound.identity_key for sound in requested}) - len(cacheable),
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
