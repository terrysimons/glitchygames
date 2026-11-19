"""Measure a game's start-up compile against the CRT power-on, and ten Arcade tiles' memory.

The sound migration's two open measurements (plans/2026-11-14-sound-migration.md):

  start   Each game's declared sounds (``Scene.SOUNDS``) compiled through ``StartupSounds`` in
          the CRT power-on's slices (``compile_for(IDLE_WORK_SECONDS)`` a frame), as a launch
          does: how many of the power-on's frames the compile takes, and its longest slice (the
          most one frame's idle work can run over, about one sound's compile). Cold (cache
          ``ram``: every sound compiled) and, with ``--cache-root``, the disk cache's first
          launch (compile and write) and a later one (read back).
  tiles   Ten Arcade tiles, each its own engine context starting its game's sounds, as the
          Arcade builds them: the memory ``tracemalloc`` sees allocated by the first tile and by
          all ten. The process shares one copy of each compiled sound (``ENGINE_SOUND_CACHE``),
          so ten tiles should hold little more than one.

Run: ``uv run python -m scripts.measure_sound_start [start|tiles|both] [--cache-root DIR]``.
A machine's numbers belong with its name (the report's first line).
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import SoundSource
    from glitchygames.engine_context import EngineContext


TILE_COUNT = 10
MEGABYTE = 1024 * 1024


def _say(line: str) -> None:
    """Write one line of the report."""
    sys.stdout.write(f'{line}\n')


def games() -> list[tuple[str, Sequence[SoundSource]]]:
    """Each game's name and declared sounds.

    Returns:
        The games with sounds to compile.
    """
    from brave_adventurer.game import BraveAdventurerScene
    from clockwork_keep.game import ClockworkKeepScene
    from mr_muncher.game import MrMuncherScene
    from paddleslap import Game as PaddleSlapGame
    from zombies_aint_my_neighbors.roster_scene import RosterScene

    return [
        ('clockwork-keep', ClockworkKeepScene.SOUNDS),
        ('mr-muncher', MrMuncherScene.SOUNDS),
        ('brave-adventurer', BraveAdventurerScene.SOUNDS),
        ('paddleslap', PaddleSlapGame.SOUNDS),
        ('zombies-aint-my-neighbors', RosterScene.SOUNDS),
    ]


def audio_engine(*, disk: bool) -> AudioEngine:
    """A new audio engine with no channels (nothing is played), on the cache asked for.

    Returns:
        The engine.
    """
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import CacheMode
    from glitchygames.audio.voices import ChannelPartition

    no_channels = ChannelPartition(live=(), library=(), legacy_count=0)
    return AudioEngine(partition=no_channels, cache=CacheMode.DISK if disk else CacheMode.RAM)


def start_in_slices(sounds: Sequence[SoundSource], *, disk: bool) -> tuple[int, float, float]:
    """Compile a game's declared sounds a power-on slice a frame, in a new engine context.

    Returns:
        The frames it took, the longest slice and the total, both in milliseconds.
    """
    from glitchygames.audio.startup import StartupSounds
    from glitchygames.crt_power_on import IDLE_WORK_SECONDS
    from glitchygames.engine_context import EngineContext

    with EngineContext(name='start').active():
        startup = StartupSounds(audio=audio_engine(disk=disk), sources=sounds)
        frames = 0
        longest = 0.0
        total = 0.0
        while startup.remaining:
            started = time.perf_counter()
            startup.compile_for(IDLE_WORK_SECONDS)
            taken = (time.perf_counter() - started) * 1000.0
            longest = max(longest, taken)
            total += taken
            frames += 1
        return frames, longest, total


def report_start(cache_root: Path | None) -> None:
    """Print each game's start-up compile in power-on frames, cold and from the disk cache."""
    from glitchygames.audio.library import ENGINE_SOUND_CACHE
    from glitchygames.crt_power_on import FRAME_SECONDS, IDLE_WORK_SECONDS, SEQUENCE_SECONDS

    power_on_frames = round(SEQUENCE_SECONDS / FRAME_SECONDS)
    _say(
        f'CRT power-on: {power_on_frames} frames, {IDLE_WORK_SECONDS * 1000:.1f} ms of idle work '
        f'each ({power_on_frames * IDLE_WORK_SECONDS * 1000:.0f} ms to hide a compile in)\n'
    )
    _say(f'{"game":25s} {"sounds":>6s}   {"run":19s} {"frames":>7s} {"longest":>9s} {"total":>9s}')
    for name, sounds in games():
        runs = [('cold (compile)', False)]
        if cache_root is not None:
            runs += [('disk, first launch', True), ('disk, later launch', True)]
        for run, disk in runs:
            ENGINE_SOUND_CACHE.clear()  # each run a new process: nothing compiled yet
            frames, longest, total = start_in_slices(sounds, disk=disk)
            _say(
                f'{name:25s} {len(sounds):6d}   {run:19s} {frames:4d}/{power_on_frames} '
                f'{longest:7.2f}ms {total:7.2f}ms'
            )


def report_tiles() -> None:
    """Print the memory one tile and ten tiles allocate starting Mr. Muncher's sounds."""
    from glitchygames.audio.library import ENGINE_SOUND_CACHE
    from glitchygames.audio.startup import StartupSounds
    from glitchygames.engine_context import EngineContext
    from mr_muncher.game import MrMuncherScene

    ENGINE_SOUND_CACHE.clear()
    engines: list[tuple[EngineContext, AudioEngine]] = []  # kept alive, as the Arcade's tiles
    tracemalloc.start()
    baseline = tracemalloc.take_snapshot()
    after: dict[int, float] = {}
    for tile in range(1, TILE_COUNT + 1):
        context = EngineContext(name=f'tile {tile}')
        with context.active():
            audio = audio_engine(disk=False)
            StartupSounds(audio=audio, sources=MrMuncherScene.SOUNDS).finish()
            engines.append((context, audio))
        if tile in {1, TILE_COUNT}:
            snapshot = tracemalloc.take_snapshot()
            grown = sum(stat.size_diff for stat in snapshot.compare_to(baseline, 'filename'))
            after[tile] = grown / MEGABYTE
    tracemalloc.stop()
    # Every tile's Sounds, each array counted once: shared arrays are the same object
    arrays = {
        id(samples): samples.nbytes
        for _context, audio in engines
        for source in MrMuncherScene.SOUNDS
        for samples in (audio.sound(source).samples_int16, audio.sound(source).samples_float)
        if samples is not None
    }
    shared = sum(arrays.values())
    _say(f"Mr. Muncher's {len(MrMuncherScene.SOUNDS)} sounds in {TILE_COUNT} Arcade tiles:")
    _say(f'  compiled samples, shared by the process: {shared / MEGABYTE:.2f} MB')
    _say(f'  allocated after 1 tile:   {after[1]:.2f} MB')
    _say(f'  allocated after {TILE_COUNT} tiles: {after[TILE_COUNT]:.2f} MB')
    _say(
        f'  each further tile:        {(after[TILE_COUNT] - after[1]) / (TILE_COUNT - 1):.3f} MB '
        f'(unshared, each would hold its own {shared / MEGABYTE:.2f} MB)'
    )


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the measurements asked for.

    Returns:
        The exit status.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    parser.add_argument('report', nargs='?', choices=('start', 'tiles', 'both'), default='both')
    parser.add_argument('--cache-root', type=Path, help='measure the disk cache in this folder')
    options = parser.parse_args(arguments)
    cache_root: Path | None = options.cache_root
    if cache_root is not None:
        cache_root.mkdir(parents=True, exist_ok=True)
        os.environ['GLITCHYGAMES_SOUND_CACHE_ROOT'] = str(Path(tempfile.mkdtemp(dir=cache_root)))
    else:
        os.environ['GLITCHYGAMES_SOUND_CACHE_ROOT'] = ''
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    _say(f'machine: {platform.node()} {platform.machine()} {platform.python_version()}\n')
    if options.report in {'start', 'both'}:
        report_start(cache_root)
        _say('')
    if options.report in {'tiles', 'both'}:
        report_tiles()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
