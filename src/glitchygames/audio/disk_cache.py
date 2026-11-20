"""The disk layer of the sound cache: compiled sounds kept between launches.

Sound engine implementation spec 6.4 (the layer, its layout and its limits; owner decisions) and
plans/2026-11-14-sound-cache-on-first-use.md (built before M2, opt-in). The rules:

1. One file per sound, ``<directory>/<key[:2]>/<key>.wav``: a mono 16-bit PCM WAV at the mixer
   rate that any WAV reader opens. The caller names the directory: one per game, versioned by
   the audio render version (``<cache>/<game>/sounds/<render_version>/``, ``sounds_directory``),
   so a render change never reads an old file and a game's limit and pruning touch only its own
   files (the owner, 2026-11-15; the engine's own sounds are kept once per game, about 0.5 MB).
2. Each file also carries the compile's exact peak, a little-endian float64 in a private RIFF
   chunk (``gGpk``, which WAV readers skip), because a sound's peak must never depend on the
   cache and 16-bit samples alone cannot give it back. Float samples are not kept.
3. A read checks everything it relies on: the RIFF and WAVE tags, PCM, one channel, 16 bits, the
   rate asked for, the peak chunk and exactly the frame count asked for. Anything else is a
   miss, and the file is deleted so the sound is compiled again and rewritten.
4. A write goes to a temporary file of its own in the same folder (``<key>.wav.writing-*``) and
   is then moved into place, so a reader never sees half a file and two writers of one sound
   never share a temporary file (``output_files.write_aside_then_replace`` uses one fixed
   partial name, which two processes would share). A write the system refuses (Windows will not
   replace a file another process has open) is logged and reported, never raised: the sound is
   compiled either way. Reads take no lock: a file is whole or absent.
5a. Writers of one sound in several processes take its lock file first (``write_lock``:
   ``<key>.wav.lock``, a kernel lock through ``filelock``, released if its process dies), and
   the library reads again under it before compiling, so a sound is compiled and written once.
   A lock not had within ``WRITE_LOCK_TIMEOUT_SECONDS`` (another process compiling a long sound)
   gives way: the caller compiles without writing. In the browser (``sys.platform`` is
   ``emscripten``) a page runs one Python process, so there is no other process to wait for and
   no lock is taken; ``filelock`` is imported only where one is, because the browser bundle does
   not install it (every play page once stopped at startup on its import). Two tabs writing one
   sound write the same bytes, each through its own temporary file, and a read checks the file.
5. A hit writes nothing: a read is a pure read, because SD cards (a Raspberry Pi's) wear from
   writes (the owner, 2026-11-15). So ``prune`` removes the oldest written files until the
   folder is at most its limit, and every temporary file a killed writer left. Lock files
   (rule 5a) are never removed: one held by another process must stay the same file. They are
   empty, one per sound ever written. Files are read whole, so none is ever held open.
6. Where the cache lives is explicit (the plan's decision 7), never guessed from whether a test
   is running: ``GLITCHYGAMES_SOUND_CACHE_ROOT`` unset means the platform's cache folder
   (``state.paths.get_cache_directory``), a path means that folder, and an empty value means no
   disk layer at all (``sound_cache_root`` returns None, and cache ``disk`` runs as ``ram``).
   An environment variable rather than an option, because golden replays and bundled demos run
   as child processes, which inherit it. The test harness sets it empty (tests/harness.py), so
   no test writes to a user's cache folder; a test that wants the disk sets it to its own
   folder. Sounds live under ``<root>/<game>/sounds/<render_version>/`` (``sounds_directory``).

7. In the browser the layer works as on the desktop, in Pyodide's in-memory files, which the
   page (browser/boot.py) mounts on IndexedDB at the cache root, so sounds outlive the page.
   IndexedDB keeps those files only when told to: each written sound is told to the observers
   ``observe_sound_writes`` registers (the page's flush), after the file is in place. Nothing
   else in the engine knows about the browser's storage.

This module imports numpy, pydantic, the standard library and ``glitchygames.state.paths``,
and ``filelock`` only when it takes a write lock outside the browser (rule 5a).
"""

from __future__ import annotations

import contextlib
import logging
import operator
import os
import re
import struct
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict

from glitchygames.state.paths import get_cache_directory

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

# Told the path of each sound file written, once it is in place (observe_sound_writes, rule 7):
# the browser's page flushes its IndexedDB-backed files there
_SOUND_WRITE_OBSERVERS: list[Callable[[Path], None]] = []


def observe_sound_writes(*, observer: Callable[[Path], None]) -> None:
    """Call ``observer`` with each sound file's path after a disk layer writes it (rule 7).

    Args:
        observer: Called with the written file's path, once it is in place.

    """
    _SOUND_WRITE_OBSERVERS.append(observer)


def stop_observing_sound_writes(*, observer: Callable[[Path], None]) -> None:
    """Stop calling ``observer`` (nothing if it was not observing).

    Args:
        observer: An observer given to ``observe_sound_writes``.

    """
    with contextlib.suppress(ValueError):
        _SOUND_WRITE_OBSERVERS.remove(observer)


def _notify_sound_written(*, path: Path) -> None:
    # A copy: an observer may stop observing while it is told
    for observer in _SOUND_WRITE_OBSERVERS.copy():
        observer(path)


# sys.platform in the browser (Pyodide): one Python process per page, so no write lock (rule 5a)
BROWSER_PLATFORM: Final[str] = 'emscripten'

# RIFF layout (little-endian throughout, as WAV requires)
RIFF_TAG: Final[bytes] = b'RIFF'
WAVE_TAG: Final[bytes] = b'WAVE'
FORMAT_TAG: Final[bytes] = b'fmt '
PEAK_TAG: Final[bytes] = b'gGpk'
DATA_TAG: Final[bytes] = b'data'
PCM_FORMAT: Final[int] = 1
CHANNELS: Final[int] = 1
BITS_PER_SAMPLE: Final[int] = 16
BYTES_PER_FRAME: Final[int] = CHANNELS * BITS_PER_SAMPLE // 8
# fmt chunk: format, channels, rate, byte rate, block align, bits per sample
FORMAT_LAYOUT: Final[str] = '<HHIIHH'
FORMAT_SIZE: Final[int] = 16  # struct.calcsize(FORMAT_LAYOUT), checked by its test
PEAK_LAYOUT: Final[str] = '<d'
PEAK_SIZE: Final[int] = 8  # struct.calcsize(PEAK_LAYOUT), checked by its test
CHUNK_HEADER_LAYOUT: Final[str] = '<4sI'
CHUNK_HEADER_SIZE: Final[int] = 8  # struct.calcsize(CHUNK_HEADER_LAYOUT), checked by its test
RIFF_HEADER_SIZE: Final[int] = 12
SOUND_SUFFIX: Final[str] = '.wav'
TEMPORARY_MARKER: Final[str] = '.writing-'
KEY_PREFIX_LENGTH: Final[int] = 2
LOCK_SUFFIX: Final[str] = '.lock'
# Rule 1: a game's folder is one plain name inside the root
GAME_FOLDER_NAME: Final[re.Pattern[str]] = re.compile(r'[A-Za-z0-9_.-]+')
# Rule 5a: how long a writer waits for another process writing the same sound
WRITE_LOCK_TIMEOUT_SECONDS: Final[float] = 5.0

log: logging.Logger = logging.getLogger('game.audio.disk_cache')
# Rule 6: where the cache lives, and the app name its platform folder is named after (one cache
# per machine, shared by every game: a sound's identity names everything that makes it)
SOUND_CACHE_ROOT_VARIABLE: Final[str] = 'GLITCHYGAMES_SOUND_CACHE_ROOT'
CACHE_APP_NAME: Final[str] = 'glitchygames'
SOUNDS_FOLDER: Final[str] = 'sounds'
# The listening WAVs' folder under the root, beside the games' (glitchygames/audio/listening):
# <root>/listening/<render version>/, no size limit, never pruned
LISTENING_FOLDER = 'listening'
# The disk layer's size limit, pruned to at startup (impl spec 6.4, the owner's 64 MB)
DISK_CACHE_LIMIT_BYTES: Final[int] = 64 * 1024 * 1024


def sound_cache_root() -> Path | None:
    """Find the cache root (rule 6).

    Returns:
        The platform cache folder when ``GLITCHYGAMES_SOUND_CACHE_ROOT`` is unset, its path when
        it is set, or None (no disk layer) when it is empty.
    """
    configured = os.environ.get(SOUND_CACHE_ROOT_VARIABLE)
    if configured is None:
        return get_cache_directory(CACHE_APP_NAME)
    return Path(configured) if configured else None


def sounds_directory(*, root: Path, game: str, render_version: int) -> Path:
    """Name the folder a game's sounds of one render version live in (rule 1).

    Args:
        root: The cache root (``sound_cache_root``).
        game: The game's folder name (its package name): one plain name, never a path.
        render_version: The audio render version.

    Returns:
        ``<root>/<game>/sounds/<render_version>``.

    Raises:
        ValueError: The game name is empty, ``.`` or ``..``, or has anything but letters,
            digits, ``_``, ``-`` and ``.``.
    """
    if GAME_FOLDER_NAME.fullmatch(game) is None or game in {'.', '..'}:
        message = f'a game cache folder is one plain name (letters, digits, _ - .), got {game!r}'
        raise ValueError(message)
    return root / game / SOUNDS_FOLDER / str(render_version)


class CachedSamples(BaseModel):
    """What a disk hit gives back: the compile's int16 samples and its exact peak.

    A frozen pydantic model, measured first since one is built on every hit (2026-11-14, Apple
    M4 Max): 0.36 us to construct, 1.2% of a whole disk read of a one-second sound (28.9 us).
    """

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    samples_int16: npt.NDArray[np.int16]
    peak: float


class DiskSoundCache:
    """Compiled sounds as files in one folder, pruned to a size limit (rules in the module doc)."""

    def __init__(self, *, directory: Path, limit_bytes: int) -> None:
        """Keep sounds in a folder.

        Args:
            directory: The folder, already versioned by the audio render version; made on the
                first write.
            limit_bytes: The most the folder's sound files may hold after ``prune``.
        """
        self._directory = directory
        self._limit_bytes = limit_bytes

    def path_for(self, *, identity_key: str) -> Path:
        """Name a sound's file.

        Args:
            identity_key: The sound's identity key.

        Returns:
            ``<directory>/<key[:2]>/<key>.wav``.
        """
        return self._directory / identity_key[:KEY_PREFIX_LENGTH] / f'{identity_key}{SOUND_SUFFIX}'

    def read(
        self, *, identity_key: str, sample_rate: int, frame_count: int
    ) -> CachedSamples | None:
        """Read a sound, if a good file holds it (rule 3).

        Args:
            identity_key: The sound's identity key.
            sample_rate: The rate it must be at.
            frame_count: The frames it must hold.

        Returns:
            Its samples and peak, or None for a miss (a damaged file is deleted).
        """
        path = self.path_for(identity_key=identity_key)
        try:
            data = path.read_bytes()
        except OSError:
            return None
        cached = _parse(data=data, sample_rate=sample_rate, frame_count=frame_count)
        if cached is None:
            path.unlink(missing_ok=True)
            return None
        return cached

    @contextlib.contextmanager
    def write_lock(self, *, identity_key: str) -> Generator[bool]:
        """Hold a sound's cross-process write lock while it is read again, compiled and written.

        Args:
            identity_key: The sound's identity key.

        Yields:
            Whether the lock is held (False after ``WRITE_LOCK_TIMEOUT_SECONDS``: write nothing).
            Always True in the browser, which takes no lock (rule 5a).
        """
        path = self.path_for(identity_key=identity_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform == BROWSER_PLATFORM:
            yield True
            return
        # Here, not at the top: the browser bundle does not install filelock (rule 5a)
        from filelock import FileLock, Timeout

        lock = FileLock(f'{path}{LOCK_SUFFIX}', timeout=WRITE_LOCK_TIMEOUT_SECONDS)
        try:
            lock.acquire()
        except Timeout:
            log.info('Sound %s: another process holds its cache lock; not writing it', identity_key)
            yield False
            return
        try:
            yield True
        finally:
            lock.release()

    def write(
        self,
        *,
        identity_key: str,
        samples_int16: npt.NDArray[np.int16],
        peak: float,
        sample_rate: int,
    ) -> bool:
        """Keep a sound (rule 4).

        Args:
            identity_key: The sound's identity key.
            samples_int16: Its mono 16-bit samples.
            peak: The compile's exact peak.
            sample_rate: Its rate.

        Returns:
            Whether it was written (a write the system refused is logged instead). A written
            sound is told to ``observe_sound_writes``' observers (rule 7).
        """
        path = self.path_for(identity_key=identity_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f'{path.name}{TEMPORARY_MARKER}', dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(
                    _wav_bytes(samples_int16=samples_int16, peak=peak, sample_rate=sample_rate)
                )
            temporary.replace(path)
        except OSError as error:
            log.warning('Sound %s was not written to the disk cache: %s', identity_key, error)
            return False
        finally:
            temporary.unlink(missing_ok=True)
        _notify_sound_written(path=path)
        return True

    def size_bytes(self) -> int:
        """Total the folder's sound files.

        Returns:
            Their bytes (0 when the folder does not exist).
        """
        return sum(path.stat().st_size for path in self._sound_files())

    def prune(self) -> None:
        """Remove temporary files, then the oldest written sounds until under the limit."""
        if not self._directory.is_dir():
            return
        for leftover in self._directory.glob(f'*/*{TEMPORARY_MARKER}*'):
            leftover.unlink(missing_ok=True)
        files = sorted(
            ((path.stat().st_mtime, path.stat().st_size, path) for path in self._sound_files()),
            key=operator.itemgetter(0),
        )
        total = sum(size for _written, size, _path in files)
        for _written, size, path in files:
            if total <= self._limit_bytes:
                break
            path.unlink(missing_ok=True)
            total -= size

    def _sound_files(self) -> list[Path]:
        if not self._directory.is_dir():
            return []
        return sorted(self._directory.glob(f'*/*{SOUND_SUFFIX}'))


def _wav_bytes(*, samples_int16: npt.NDArray[np.int16], peak: float, sample_rate: int) -> bytes:
    """Build a sound's file: RIFF header, fmt, the peak chunk, then the samples (rules 1-2).

    Returns:
        The file's bytes.
    """
    frames = samples_int16.astype('<i2').tobytes()
    format_chunk = struct.pack(
        FORMAT_LAYOUT,
        PCM_FORMAT,
        CHANNELS,
        sample_rate,
        sample_rate * BYTES_PER_FRAME,
        BYTES_PER_FRAME,
        BITS_PER_SAMPLE,
    )
    body = (
        struct.pack(CHUNK_HEADER_LAYOUT, FORMAT_TAG, len(format_chunk))
        + format_chunk
        + struct.pack(CHUNK_HEADER_LAYOUT, PEAK_TAG, PEAK_SIZE)
        + struct.pack(PEAK_LAYOUT, peak)
        + struct.pack(CHUNK_HEADER_LAYOUT, DATA_TAG, len(frames))
        + frames
    )
    return RIFF_TAG + struct.pack('<I', len(WAVE_TAG) + len(body)) + WAVE_TAG + body


def file_problem(data: bytes) -> str | None:
    """Say why a file is not a well-formed cache file, if it is not (rule 3, without the sound).

    What a file can be checked for without knowing its sound: the RIFF and WAVE tags, chunks
    that fit the file, 16-bit mono PCM, the peak chunk, whole samples. A read also checks the
    rate and the frame count its sound asks for (``_parse``); ``cache_inventory.verify`` reports
    this for every file.

    Args:
        data: The file's bytes.

    Returns:
        Why it is not one, or None for a well-formed file.
    """
    problem, _chunks_found = _checked_chunks(data=data)
    return problem


def _checked_chunks(*, data: bytes) -> tuple[str | None, dict[bytes, bytes]]:
    """Split a cache file into its chunks, checking what can be checked without its sound.

    Returns:
        Why the file is not well formed (None when it is), and its chunks by tag (empty when
        they could not be read).
    """
    if len(data) < RIFF_HEADER_SIZE or data[:4] != RIFF_TAG or data[8:12] != WAVE_TAG:
        return 'not a WAV file (no RIFF and WAVE header)', {}
    chunks = _chunks(data=data)
    if chunks is None:
        return 'a chunk runs past the end of the file (cut short)', {}
    return _chunk_problem(chunks=chunks), chunks


def _chunk_problem(*, chunks: dict[bytes, bytes]) -> str | None:
    """Say what is wrong with a cache file's chunks, the first problem found.

    Returns:
        The problem, or None.
    """
    format_chunk = chunks.get(FORMAT_TAG, b'')
    if len(format_chunk) < FORMAT_SIZE:
        return 'no format chunk'
    audio_format, channels, _rate, _byte_rate, _block_align, bits = struct.unpack(
        FORMAT_LAYOUT, format_chunk[:FORMAT_SIZE]
    )
    frames = chunks.get(DATA_TAG)
    problems = (
        (
            (audio_format, channels, bits) != (PCM_FORMAT, CHANNELS, BITS_PER_SAMPLE),
            f'not 16-bit mono PCM (format {audio_format}, {channels} channels, {bits} bits)',
        ),
        (len(chunks.get(PEAK_TAG, b'')) != PEAK_SIZE, 'no peak chunk (gGpk)'),
        (frames is None, 'no data chunk'),
        (
            frames is not None and len(frames) % BYTES_PER_FRAME != 0,
            'its data is not whole 16-bit samples',
        ),
    )
    return next((message for failed, message in problems if failed), None)


def _parse(*, data: bytes, sample_rate: int, frame_count: int) -> CachedSamples | None:
    """Read a sound's file, refusing anything rule 3 does not allow.

    Returns:
        Its samples and peak, or None.
    """
    problem, chunks = _checked_chunks(data=data)
    if problem is not None:
        return None
    _format, _channels, rate, _byte_rate, _block_align, _bits = struct.unpack(
        FORMAT_LAYOUT, chunks[FORMAT_TAG][:FORMAT_SIZE]
    )
    frames = chunks[DATA_TAG]
    if (rate, len(frames)) != (sample_rate, frame_count * BYTES_PER_FRAME):
        return None
    (peak,) = struct.unpack(PEAK_LAYOUT, chunks[PEAK_TAG])
    return CachedSamples(
        samples_int16=np.frombuffer(frames, dtype='<i2').astype(np.int16), peak=peak
    )


def _chunks(*, data: bytes) -> dict[bytes, bytes] | None:
    """Split a RIFF file's body into its chunks.

    Returns:
        Each chunk's bytes by tag, or None when a chunk runs past the end.
    """
    chunks: dict[bytes, bytes] = {}
    position = RIFF_HEADER_SIZE
    while position + CHUNK_HEADER_SIZE <= len(data):
        tag, size = struct.unpack(
            CHUNK_HEADER_LAYOUT, data[position : position + CHUNK_HEADER_SIZE]
        )
        start = position + CHUNK_HEADER_SIZE
        if start + size > len(data):
            return None
        chunks[tag] = data[start : start + size]
        # RIFF pads an odd-sized chunk to an even length
        position = start + size + (size % 2)
    return chunks
