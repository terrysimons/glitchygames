"""The disk layer of the sound cache: compiled sounds kept between launches.

Sound engine implementation spec 6.4 (the layer, its layout and its limits; owner decisions) and
plans/2026-11-14-sound-cache-on-first-use.md (built before M2, opt-in). The rules:

1. One file per sound, ``<directory>/<key[:2]>/<key>.wav``: a mono 16-bit PCM WAV at the mixer
   rate that any WAV reader opens. The caller names the directory, versioned by the audio render
   version (``<cache>/sounds/<render_version>/``), so a render change never reads an old file.
2. Each file also carries the compile's exact peak, a little-endian float64 in a private RIFF
   chunk (``gGpk``, which WAV readers skip), because a sound's peak must never depend on the
   cache and 16-bit samples alone cannot give it back. Float samples are not kept.
3. A read checks everything it relies on: the RIFF and WAVE tags, PCM, one channel, 16 bits, the
   rate asked for, the peak chunk and exactly the frame count asked for. Anything else is a
   miss, and the file is deleted so the sound is compiled again and rewritten.
4. A write goes to a temporary file of its own in the same folder (``<key>.wav.writing-*``) and
   is then moved into place, so a reader never sees half a file and two writers of one sound
   never share a temporary file (``output_files.write_aside_then_replace`` uses one fixed
   partial name, which two processes would share).
5. A hit marks the file used (its modification time), and ``prune`` removes the least recently
   used files until the folder is at most its limit, and every temporary file a killed writer
   left. Files are read whole, so none is ever held open.
6. Where the cache lives is explicit (the plan's decision 7), never guessed from whether a test
   is running: ``GLITCHYGAMES_SOUND_CACHE_ROOT`` unset means the platform's cache folder
   (``state.paths.get_cache_directory``), a path means that folder, and an empty value means no
   disk layer at all (``sound_cache_root`` returns None, and cache ``disk`` runs as ``ram``).
   An environment variable rather than an option, because golden replays and bundled demos run
   as child processes, which inherit it. The test harness sets it empty (tests/harness.py), so
   no test writes to a user's cache folder; a test that wants the disk sets it to its own
   folder. Sounds live under ``<root>/sounds/<render_version>/`` (``sounds_directory``).

This module imports numpy, pydantic, the standard library and ``glitchygames.state.paths``.
"""

from __future__ import annotations

import contextlib
import operator
import os
import struct
import tempfile
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict

from glitchygames.state.paths import get_cache_directory

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
# Rule 6: where the cache lives, and the app name its platform folder is named after (one cache
# per machine, shared by every game: a sound's identity names everything that makes it)
SOUND_CACHE_ROOT_VARIABLE: Final[str] = 'GLITCHYGAMES_SOUND_CACHE_ROOT'
CACHE_APP_NAME: Final[str] = 'glitchygames'
SOUNDS_FOLDER: Final[str] = 'sounds'
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


def sounds_directory(*, root: Path, render_version: int) -> Path:
    """Name the folder a render version's sounds live in.

    Args:
        root: The cache root (``sound_cache_root``).
        render_version: The audio render version.

    Returns:
        ``<root>/sounds/<render_version>``.
    """
    return root / SOUNDS_FOLDER / str(render_version)


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
        with contextlib.suppress(OSError):
            os.utime(path)
        return cached

    def write(
        self,
        *,
        identity_key: str,
        samples_int16: npt.NDArray[np.int16],
        peak: float,
        sample_rate: int,
    ) -> None:
        """Keep a sound (rule 4).

        Args:
            identity_key: The sound's identity key.
            samples_int16: Its mono 16-bit samples.
            peak: The compile's exact peak.
            sample_rate: Its rate.
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
        finally:
            temporary.unlink(missing_ok=True)

    def size_bytes(self) -> int:
        """Total the folder's sound files.

        Returns:
            Their bytes (0 when the folder does not exist).
        """
        return sum(path.stat().st_size for path in self._sound_files())

    def prune(self) -> None:
        """Remove temporary files, then the least recently used sounds until under the limit."""
        if not self._directory.is_dir():
            return
        for leftover in self._directory.glob(f'*/*{TEMPORARY_MARKER}*'):
            leftover.unlink(missing_ok=True)
        files = sorted(
            ((path.stat().st_mtime, path.stat().st_size, path) for path in self._sound_files()),
            key=operator.itemgetter(0),
        )
        total = sum(size for _used, size, _path in files)
        for _used, size, path in files:
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


def _parse(*, data: bytes, sample_rate: int, frame_count: int) -> CachedSamples | None:
    """Read a sound's file, refusing anything rule 3 does not allow.

    Returns:
        Its samples and peak, or None.
    """
    is_wave = len(data) >= RIFF_HEADER_SIZE and data[:4] == RIFF_TAG and data[8:12] == WAVE_TAG
    chunks = _chunks(data=data) if is_wave else None
    if chunks is None:
        return None
    format_chunk = chunks.get(FORMAT_TAG, b'')
    peak_chunk = chunks.get(PEAK_TAG, b'')
    frames = chunks.get(DATA_TAG)
    if frames is None or len(format_chunk) < FORMAT_SIZE or len(peak_chunk) != PEAK_SIZE:
        return None
    audio_format, channels, rate, _byte_rate, _block_align, bits = struct.unpack(
        FORMAT_LAYOUT, format_chunk[:FORMAT_SIZE]
    )
    expected = (PCM_FORMAT, CHANNELS, BITS_PER_SAMPLE, sample_rate, frame_count * BYTES_PER_FRAME)
    if (audio_format, channels, bits, rate, len(frames)) != expected:
        return None
    (peak,) = struct.unpack(PEAK_LAYOUT, peak_chunk)
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
