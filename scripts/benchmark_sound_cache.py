"""Compare compiling a game's sounds with reading them from the disk cache, cold and warm.

Answers whether ``--sound-cache disk`` is faster than compiling on a given machine and storage
(an SD card on a Raspberry Pi, above all). For each game it times its declared sounds
(``Scene.SOUNDS``) through ``StartupSounds.finish``, the path a game's start takes:

- compile: the process store emptied, cache ``ram`` (every sound compiled);
- disk, cold: the store emptied and each cache file dropped from the page cache, so the read
  comes from the storage device;
- disk, warm: the store emptied, the files still in the page cache (a later launch);
- process store: nothing emptied (an Arcade tile's restart).

Cold reads need Linux: each file is flushed, dropped with ``posix_fadvise(POSIX_FADV_DONTNEED)``
(no root needed) and then checked with ``mincore``; a file with any page still in memory stops
the run, so a "cold" number is never secretly warm. Directory entries and inodes stay cached
(dropping those needs root), so a first launch after a reboot costs a little more than "cold".
On other systems the cold column is skipped.

Run: ``uv run python -m scripts.benchmark_sound_cache [--runs 7] [--cache-root DIR]``. The cache
root defaults to a new folder under the system's temporary folder; pass one on the storage you
want measured (on a Pi, under the home folder, which is on the SD card or NVMe drive).
"""

from __future__ import annotations

import argparse
import ctypes
import mmap
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glitchygames.audio.library import CacheStatistics, SoundSource


DEFAULT_RUNS = 7
SOUND_CACHE_ROOT_VARIABLE = 'GLITCHYGAMES_SOUND_CACHE_ROOT'


def games() -> list[tuple[str, Sequence[SoundSource]]]:
    """Each game's name and declared sounds.

    Returns:
        The games whose packages are installed.
    """
    from brave_adventurer.game import BraveAdventurerScene
    from clockwork_keep.game import ClockworkKeepScene
    from mr_muncher.game import MrMuncherScene

    return [
        ('clockwork-keep', ClockworkKeepScene.SOUNDS),
        ('mr-muncher', MrMuncherScene.SOUNDS),
        ('brave-adventurer', BraveAdventurerScene.SOUNDS),
    ]


def resident_pages(path: Path) -> int:
    """Count a file's pages in the page cache (Linux ``mincore``).

    Returns:
        The number of resident pages.

    Raises:
        OSError: mincore failed.
    """
    size = path.stat().st_size
    page_size = os.sysconf('SC_PAGE_SIZE')
    page_count = (size + page_size - 1) // page_size
    libc = ctypes.CDLL(None, use_errno=True)
    with (
        path.open('rb') as stream,
        mmap.mmap(stream.fileno(), size, access=mmap.ACCESS_COPY) as mapped,
    ):
        start = ctypes.c_char.from_buffer(mapped)
        try:
            residency = (ctypes.c_ubyte * page_count)()
            if libc.mincore(
                ctypes.c_void_p(ctypes.addressof(start)), ctypes.c_size_t(size), residency
            ):
                raise OSError(ctypes.get_errno(), f'mincore failed for {path}')
            return sum(page & 1 for page in residency)
        finally:
            del start  # the mapping cannot close while a pointer into it exists


def drop_from_page_cache(paths: Sequence[Path]) -> None:
    """Flush each file and drop it from the page cache, then prove nothing of it is left.

    Raises:
        RuntimeError: A file kept pages in memory, or this is not Linux.
    """
    if sys.platform != 'linux':
        message = 'dropping a file from the page cache needs Linux'
        raise RuntimeError(message)
    for path in paths:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
            os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(descriptor)
    still_cached = {path.name: resident_pages(path) for path in paths}
    still_cached = {name: pages for name, pages in still_cached.items() if pages}
    if still_cached:
        message = f'files still in the page cache after dropping them: {still_cached}'
        raise RuntimeError(message)


def can_read_cold() -> bool:
    """Whether this system can drop single files from the page cache.

    Returns:
        True on Linux.
    """
    return sys.platform.startswith('linux') and hasattr(os, 'posix_fadvise')


def start_game_sounds(
    sounds: Sequence[SoundSource], *, disk: bool
) -> tuple[float, CacheStatistics]:
    """Compile or read a game's declared sounds in a new engine context, as its start does.

    Returns:
        Milliseconds taken, and the library's statistics.
    """
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import CacheMode
    from glitchygames.audio.startup import StartupSounds
    from glitchygames.audio.voices import ChannelPartition
    from glitchygames.engine_context import EngineContext

    no_channels = ChannelPartition(live=(), library=(), legacy_count=0)
    with EngineContext(name='benchmark').active():
        audio = AudioEngine(partition=no_channels, cache=CacheMode.DISK if disk else CacheMode.RAM)
        started = time.perf_counter()
        StartupSounds(audio=audio, sources=sounds).finish()
        return (time.perf_counter() - started) * 1000.0, audio.sounds.statistics()


def timed_runs(
    runs: int,
    *,
    before: Callable[[], None],
    run: Callable[[], tuple[float, CacheStatistics]],
    check: Callable[[CacheStatistics], bool],
) -> float:
    """Time a start ``runs`` times, preparing before each and checking what each did.

    Returns:
        The median milliseconds.

    Raises:
        RuntimeError: A run did not do what its column claims (compiled instead of read, ...).
    """
    milliseconds: list[float] = []
    for _ in range(runs):
        before()
        taken, statistics_after = run()
        if not check(statistics_after):
            message = f'a run did not do what was measured: {statistics_after}'
            raise RuntimeError(message)
        milliseconds.append(taken)
    return statistics.median(milliseconds)


def storage_of(path: Path) -> str:
    """Name the block device a folder is on (Linux), for the report.

    Returns:
        The device name and, for an MMC device, its type (SD or MMC), or 'unknown'.
    """
    device = path.stat().st_dev
    block = Path(f'/sys/dev/block/{os.major(device)}:{os.minor(device)}')
    if not block.exists():
        return 'unknown'
    resolved = block.resolve()
    disk = resolved.parent if (resolved / 'partition').exists() else resolved
    card_type = disk / 'device' / 'type'
    kind = card_type.read_text().strip() if card_type.exists() else ''
    return f'{resolved.name} on {disk.name}' + (f' ({kind})' if kind else '')


def _say(line: str) -> None:
    """Write one line of the report."""
    sys.stdout.write(f'{line}\n')


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the benchmark and print one row per game.

    Returns:
        The exit status.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    parser.add_argument('--runs', type=int, default=DEFAULT_RUNS, help='runs per column (median)')
    parser.add_argument(
        '--cache-root', type=Path, help='disk cache folder (default: a new temporary one)'
    )
    options = parser.parse_args(arguments)
    cache_root = options.cache_root or Path(tempfile.mkdtemp(prefix='sound-cache-benchmark-'))
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ[SOUND_CACHE_ROOT_VARIABLE] = str(cache_root)
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

    from glitchygames.audio.library import ENGINE_SOUND_CACHE

    cold = can_read_cold()
    _say(f'machine: {platform.node()} {platform.machine()} {platform.python_version()}')
    _say(f'cache:   {cache_root} on {storage_of(cache_root)}')
    _say(f'runs:    {options.runs} per column, median shown\n')
    columns = ('sounds', 'compile', 'disk cold', 'disk warm', 'store')
    _say(f'{"game":17s} ' + ' '.join(f'{column:>10s}' for column in columns))
    for name, sounds in games():
        count = len(sounds)
        compile_ms = timed_runs(
            options.runs,
            before=ENGINE_SOUND_CACHE.clear,
            run=lambda sounds=sounds: start_game_sounds(sounds, disk=False),
            check=lambda result, count=count: result.compiles == count,
        )
        ENGINE_SOUND_CACHE.clear()
        start_game_sounds(sounds, disk=True)  # writes the files the disk columns read
        files = sorted(cache_root.rglob('*.wav'))

        def read_everything(result: CacheStatistics, count: int = count) -> bool:
            return result.compiles == 0 and result.disk_hits == count

        def empty_and_drop(files: list[Path] = files) -> None:
            ENGINE_SOUND_CACHE.clear()
            drop_from_page_cache(files)

        cold_ms = (
            timed_runs(
                options.runs,
                before=empty_and_drop,
                run=lambda sounds=sounds: start_game_sounds(sounds, disk=True),
                check=read_everything,
            )
            if cold
            else None
        )
        warm_ms = timed_runs(
            options.runs,
            before=ENGINE_SOUND_CACHE.clear,
            run=lambda sounds=sounds: start_game_sounds(sounds, disk=True),
            check=read_everything,
        )
        store_ms = timed_runs(
            options.runs,
            before=lambda: None,
            run=lambda sounds=sounds: start_game_sounds(sounds, disk=True),
            check=lambda result, count=count: result.shared_hits == count,
        )
        cells = [f'{count:10d}', f'{compile_ms:8.2f}ms']
        cells.append(f'{cold_ms:8.2f}ms' if cold_ms is not None else f'{"n/a":>10s}')
        cells += [f'{warm_ms:8.2f}ms', f'{store_ms:8.3f}ms']
        _say(f'{name:17s} ' + ' '.join(cells))
    total = sum(path.stat().st_size for path in cache_root.rglob('*.wav'))
    _say(f'\ncache files: {len(list(cache_root.rglob("*.wav")))}, {total / 1024:.0f} KiB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
