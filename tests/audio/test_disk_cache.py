"""Tests for the disk layer of the sound cache (sound engine implementation spec 6.4).

Plan: plans/2026-11-14-sound-cache-on-first-use.md. The layer keeps each compiled sound as a
16-bit mono WAV with the compile's exact peak in a private chunk, so a hit gives back exactly
what the compile made.
"""

from __future__ import annotations

import os
import struct
from typing import TYPE_CHECKING

import numpy as np
import pytest

from glitchygames.audio import disk_cache
from glitchygames.audio.disk_cache import DiskSoundCache

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE_RATE = 44100
KEY = 'ab' + '0' * 30
OTHER_KEY = 'cd' + '1' * 30
LIMIT_BYTES = 64 * 1024 * 1024


def samples(frame_count: int = 100) -> np.ndarray:
    """Return int16 samples that use the whole range, so a lossy round trip would show."""
    return np.linspace(-32768, 32767, num=frame_count).astype(np.int16)


def make_cache(directory: Path, *, limit_bytes: int = LIMIT_BYTES) -> DiskSoundCache:
    """Return a cache over a folder."""
    return DiskSoundCache(directory=directory, limit_bytes=limit_bytes)


def test_a_written_sound_reads_back_exactly(tmp_path: Path) -> None:
    """The samples come back byte for byte and the peak exactly."""
    cache = make_cache(tmp_path)
    written = samples()

    cache.write(
        identity_key=KEY, samples_int16=written, peak=1.2345678901234567, sample_rate=SAMPLE_RATE
    )
    cached = cache.read(identity_key=KEY, sample_rate=SAMPLE_RATE, frame_count=len(written))

    assert cached is not None
    assert cached.samples_int16.dtype == np.int16
    assert cached.samples_int16.tobytes() == written.tobytes()
    assert cached.peak == 1.2345678901234567


def test_a_sound_never_written_is_a_miss(tmp_path: Path) -> None:
    """Nothing kept for a key reads as None."""
    assert (
        make_cache(tmp_path).read(identity_key=KEY, sample_rate=SAMPLE_RATE, frame_count=100)
        is None
    )


def test_a_sound_is_kept_under_its_key_prefix(tmp_path: Path) -> None:
    """A sound lives at <directory>/<key[:2]>/<key>.wav (spec 6.4)."""
    make_cache(tmp_path).write(
        identity_key=KEY, samples_int16=samples(), peak=0.5, sample_rate=SAMPLE_RATE
    )

    assert (tmp_path / KEY[:2] / f'{KEY}.wav').is_file()


def test_the_file_is_a_wav_any_reader_opens(tmp_path: Path) -> None:
    """The standard library's reader opens it: mono, 16-bit, the rate, the frames."""
    import wave

    make_cache(tmp_path).write(
        identity_key=KEY, samples_int16=samples(), peak=0.5, sample_rate=SAMPLE_RATE
    )

    with wave.open(str(tmp_path / KEY[:2] / f'{KEY}.wav'), 'rb') as reader:
        assert (
            reader.getnchannels(),
            reader.getsampwidth(),
            reader.getframerate(),
            reader.getnframes(),
        ) == (1, 2, SAMPLE_RATE, 100)


def test_a_written_sound_leaves_no_temporary_file(tmp_path: Path) -> None:
    """Only the sound file is left once a write finishes."""
    make_cache(tmp_path).write(
        identity_key=KEY, samples_int16=samples(), peak=0.5, sample_rate=SAMPLE_RATE
    )

    assert sorted(path.name for path in (tmp_path / KEY[:2]).iterdir()) == [f'{KEY}.wav']


def test_writing_again_replaces_the_file(tmp_path: Path) -> None:
    """A second write of a key replaces the first."""
    cache = make_cache(tmp_path)
    cache.write(identity_key=KEY, samples_int16=samples(100), peak=0.5, sample_rate=SAMPLE_RATE)

    cache.write(identity_key=KEY, samples_int16=samples(50), peak=0.25, sample_rate=SAMPLE_RATE)
    cached = cache.read(identity_key=KEY, sample_rate=SAMPLE_RATE, frame_count=50)

    assert cached is not None
    assert cached.peak == 0.25


def _write_then_damage(directory: Path, damage: str) -> Path:
    """Write a good file, then damage it one way; return its path."""
    make_cache(directory).write(
        identity_key=KEY, samples_int16=samples(), peak=0.5, sample_rate=SAMPLE_RATE
    )
    path = directory / KEY[:2] / f'{KEY}.wav'
    data = path.read_bytes()
    if damage == 'truncated':
        path.write_bytes(data[: len(data) // 2])
    elif damage == 'not-a-wav':
        path.write_bytes(b'not a wav file at all')
    elif damage == 'no-peak-chunk':
        position = data.index(b'gGpk')
        chunk_size = struct.unpack('<I', data[position + 4 : position + 8])[0]
        without = data[:position] + data[position + 8 + chunk_size :]
        path.write_bytes(without[:4] + struct.pack('<I', len(without) - 8) + without[8:])
    elif damage == 'stereo':
        position = data.index(b'fmt ')
        path.write_bytes(data[: position + 10] + struct.pack('<H', 2) + data[position + 12 :])
    elif damage == 'short-peak-chunk':
        position = data.index(b'gGpk')
        shortened = (
            data[: position + 4]
            + struct.pack('<I', 4)
            + data[position + 8 : position + 12]
            + data[position + 16 :]
        )
        path.write_bytes(shortened[:4] + struct.pack('<I', len(shortened) - 8) + shortened[8:])
    elif damage == 'eight-bit':
        position = data.index(b'fmt ')
        path.write_bytes(data[: position + 22] + struct.pack('<H', 8) + data[position + 24 :])
    return path


@pytest.mark.parametrize(
    'damage',
    ['truncated', 'not-a-wav', 'no-peak-chunk', 'short-peak-chunk', 'stereo', 'eight-bit'],
)
def test_a_damaged_file_is_a_miss_and_is_deleted(tmp_path: Path, damage: str) -> None:
    """Each kind of damage reads as a miss, and the file goes so it is rewritten."""
    path = _write_then_damage(tmp_path, damage)

    assert (
        make_cache(tmp_path).read(identity_key=KEY, sample_rate=SAMPLE_RATE, frame_count=100)
        is None
    )
    assert not path.exists()


def test_a_file_at_another_rate_is_a_miss_and_is_deleted(tmp_path: Path) -> None:
    """A file at another mixer rate is not used."""
    cache = make_cache(tmp_path)
    cache.write(identity_key=KEY, samples_int16=samples(), peak=0.5, sample_rate=22050)

    assert cache.read(identity_key=KEY, sample_rate=SAMPLE_RATE, frame_count=100) is None
    assert not (tmp_path / KEY[:2] / f'{KEY}.wav').exists()


def test_a_file_of_another_length_is_a_miss_and_is_deleted(tmp_path: Path) -> None:
    """A file whose frame count differs from the compile it stands for is not used."""
    cache = make_cache(tmp_path)
    cache.write(identity_key=KEY, samples_int16=samples(100), peak=0.5, sample_rate=SAMPLE_RATE)

    assert cache.read(identity_key=KEY, sample_rate=SAMPLE_RATE, frame_count=99) is None
    assert not (tmp_path / KEY[:2] / f'{KEY}.wav').exists()


def test_the_size_counts_every_kept_file(tmp_path: Path) -> None:
    """The size is the total of the folder's sound files."""
    cache = make_cache(tmp_path)
    assert cache.size_bytes() == 0

    cache.write(identity_key=KEY, samples_int16=samples(), peak=0.5, sample_rate=SAMPLE_RATE)
    cache.write(identity_key=OTHER_KEY, samples_int16=samples(), peak=0.5, sample_rate=SAMPLE_RATE)

    assert cache.size_bytes() == sum(path.stat().st_size for path in tmp_path.rglob('*.wav'))


def test_pruning_removes_the_least_recently_used_files_until_under_the_limit(
    tmp_path: Path,
) -> None:
    """The least recently used files go first, and only until the folder fits."""
    writer = make_cache(tmp_path)
    keys = [f'{index:02x}' + '0' * 30 for index in range(4)]
    for key in keys:
        writer.write(
            identity_key=key, samples_int16=samples(1000), peak=0.5, sample_rate=SAMPLE_RATE
        )
    file_size = (tmp_path / keys[0][:2] / f'{keys[0]}.wav').stat().st_size
    for age, key in enumerate(keys):
        # keys[0] used longest ago, keys[3] most recently
        os.utime(tmp_path / key[:2] / f'{key}.wav', (1_000_000 + age, 1_000_000 + age))

    make_cache(tmp_path, limit_bytes=file_size * 2).prune()

    assert sorted(path.stem for path in tmp_path.rglob('*.wav')) == keys[2:]


def test_reading_a_file_marks_it_used(tmp_path: Path) -> None:
    """A hit refreshes the file, so pruning keeps what is played."""
    cache = make_cache(tmp_path)
    cache.write(identity_key=KEY, samples_int16=samples(), peak=0.5, sample_rate=SAMPLE_RATE)
    path = tmp_path / KEY[:2] / f'{KEY}.wav'
    os.utime(path, (1_000_000, 1_000_000))

    cache.read(identity_key=KEY, sample_rate=SAMPLE_RATE, frame_count=100)

    assert path.stat().st_mtime > 1_000_000


def test_pruning_removes_temporary_files_a_killed_writer_left(tmp_path: Path) -> None:
    """A killed writer's temporary file never stays."""
    (tmp_path / KEY[:2]).mkdir(parents=True)
    leftover = tmp_path / KEY[:2] / f'{KEY}.wav.writing-12345'
    leftover.write_bytes(b'half a sound')

    make_cache(tmp_path).prune()

    assert not leftover.exists()


def test_pruning_an_absent_folder_does_nothing(tmp_path: Path) -> None:
    """Pruning creates nothing."""
    make_cache(tmp_path / 'never-made').prune()

    assert not (tmp_path / 'never-made').exists()


def test_the_size_of_an_absent_folder_is_zero(tmp_path: Path) -> None:
    """A folder never written to holds nothing, and asking makes no folder."""
    assert make_cache(tmp_path / 'never-made').size_bytes() == 0
    assert not (tmp_path / 'never-made').exists()


@pytest.mark.parametrize(
    ('size', 'layout'),
    [
        (disk_cache.FORMAT_SIZE, disk_cache.FORMAT_LAYOUT),
        (disk_cache.PEAK_SIZE, disk_cache.PEAK_LAYOUT),
        (disk_cache.CHUNK_HEADER_SIZE, disk_cache.CHUNK_HEADER_LAYOUT),
    ],
)
def test_each_written_size_matches_its_layout(size: int, layout: str) -> None:
    """The sizes are literals (module state must be plain values); each equals its layout's."""
    assert size == struct.calcsize(layout)
