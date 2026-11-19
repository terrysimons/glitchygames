"""Measure the memory a game's declared sounds hold once compiled, and where it is.

Each game's ``Scene.SOUNDS`` compiled as a launch does (``StartupSounds``, in a new engine
context), then each sound's pygame mixer sound made, as playing makes it. Reported per game:

  held        Every Python allocation still held after compiling, then with the mixer sounds
              (``tracemalloc``: what was allocated and not freed).
  samples     The compiled sounds' float64 and int16 sample arrays, and the mixer sounds' bytes
              (stereo 16-bit copies of the mono samples, made by pygame).
  waves       What the waves built and keep (their band-limited tables): every allocation still
              held whose call stack passes through ``glitchygames/audio/waves.py``.
  sites       The files whose allocations are still held, largest first.

Without ``--cache-root`` every sound is compiled (cache ``ram``). With it, the disk cache in a
new folder under it: a first launch (compile and write) and a later one (read back), each as a
new process would see it (``ENGINE_SOUND_CACHE`` cleared). A library-compiled sound keeps its
int16 samples only, as a disk hit does (``Sound.release_float_samples``; the owner, 2026-11-18,
after this measured the zombies game holding 10.7 of its 19.8 MiB of sound in float64 copies).

Run: ``uv run python -m scripts.measure_sound_memory [--game NAME] [--cache-root DIR]``.
"""

from __future__ import annotations

import argparse
import gc
import os
import platform
import sys
import tempfile
import tracemalloc
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.library import SoundSource

MEGABYTE = 1024 * 1024
# How many allocation sites the report names
SITE_COUNT = 6
# Frames tracemalloc keeps for each allocation: deep enough to reach waves.py from numpy's fft
TRACEBACK_FRAMES = 25
WAVES_MODULE = 'glitchygames/audio/waves.py'


class SoundMemory(BaseModel):
    """What one game's compiled sounds hold, in bytes."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    sound_count: int
    held_after_compiling: int
    held_with_mixer_sounds: int
    float_samples: int
    int16_samples: int
    mixer_sounds: int
    wave_tables: int
    sites: tuple[tuple[str, int], ...]


def _say(line: str) -> None:
    """Write one line of the report."""
    sys.stdout.write(f'{line}\n')


def _site_name(filename: str) -> str:
    """Return an allocation site's file, short: from the package down.

    Returns:
        The path after ``site-packages/``, ``src/`` or the standard library's folder, else the
        whole path.
    """
    for marker in ('site-packages/', 'src/'):
        if marker in filename:
            return filename.split(marker, 1)[1]
    # The standard library's own modules: from the module down (lib/python3.15/tomllib/...)
    if '/lib/python' in filename:
        return filename.split('/lib/python', 1)[1].split('/', 1)[-1]
    return filename


def measure(sources: Sequence[SoundSource], *, disk: bool) -> SoundMemory:
    """Compile a game's declared sounds in a new engine context and measure what they hold.

    Returns:
        The measurement.
    """
    import pygame

    from glitchygames.audio.startup import StartupSounds
    from glitchygames.engine_context import EngineContext
    from scripts.measure_sound_start import audio_engine

    tracemalloc.start(TRACEBACK_FRAMES)
    gc.collect()
    before = tracemalloc.take_snapshot()
    before_bytes = tracemalloc.get_traced_memory()[0]
    with EngineContext(name='measure sound memory').active():
        audio = audio_engine(disk=disk)
        startup = StartupSounds(audio=audio, sources=sources)
        while startup.remaining:
            startup.compile_for(60.0)
        sounds = [audio.sound(source) for source in sources]
        gc.collect()
        after_compiling = tracemalloc.get_traced_memory()[0]
        mixer_bytes = 0
        if pygame.mixer.get_init() is not None:
            for sound in sounds:
                mixer_sound = sound.mixer_sound()
                if mixer_sound is not None:
                    mixer_bytes += len(mixer_sound.get_raw())
        gc.collect()
        with_mixer = tracemalloc.get_traced_memory()[0]
        after = tracemalloc.take_snapshot()
        wave_tables = sum(
            statistic.size_diff
            for statistic in after.compare_to(before, 'traceback')
            if any(frame.filename.endswith(WAVES_MODULE) for frame in statistic.traceback)
        )
        measured = SoundMemory(
            sound_count=len(sounds),
            held_after_compiling=after_compiling - before_bytes,
            held_with_mixer_sounds=with_mixer - before_bytes,
            float_samples=sum(
                0 if sound.samples_float is None else sound.samples_float.nbytes for sound in sounds
            ),
            int16_samples=sum(
                0 if sound.samples_int16 is None else sound.samples_int16.nbytes for sound in sounds
            ),
            mixer_sounds=mixer_bytes,
            wave_tables=wave_tables,
            sites=tuple(
                (_site_name(statistic.traceback[0].filename), statistic.size_diff)
                for statistic in after.compare_to(before, 'filename')[:SITE_COUNT]
            ),
        )
    tracemalloc.stop()
    return measured


def report(name: str, run: str, measured: SoundMemory) -> None:
    """Print one game's measurement."""

    def row(label: str, value: int) -> None:
        _say(f'  {label:44s} {value / MEGABYTE:8.2f} MiB')

    _say(f'{name}: {measured.sound_count} sounds, {run}')
    row('held after compiling', measured.held_after_compiling)
    row('held with the mixer sounds made', measured.held_with_mixer_sounds)
    row('float64 samples', measured.float_samples)
    row('int16 samples', measured.int16_samples)
    row('mixer sounds (stereo 16-bit)', measured.mixer_sounds)
    row('the waves (their band-limited tables)', measured.wave_tables)
    for site, size in measured.sites:
        row(f'  held by {site}', size)


def main(arguments: Sequence[str] | None = None) -> int:
    """Measure the games asked for.

    Returns:
        The exit status.
    """
    from scripts.measure_sound_start import games

    every_game = dict(games())
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    parser.add_argument('--game', choices=sorted(every_game), help='one game (default: every one)')
    parser.add_argument('--cache-root', type=Path, help='measure the disk cache in this folder')
    options = parser.parse_args(arguments)
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    cache_root: Path | None = options.cache_root
    if cache_root is None:
        os.environ['GLITCHYGAMES_SOUND_CACHE_ROOT'] = ''
    else:
        cache_root.mkdir(parents=True, exist_ok=True)
        os.environ['GLITCHYGAMES_SOUND_CACHE_ROOT'] = str(Path(tempfile.mkdtemp(dir=cache_root)))

    import pygame

    from glitchygames.audio.library import ENGINE_SOUND_CACHE

    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    _say(f'machine: {platform.node()} {platform.machine()} {platform.python_version()}\n')
    names = [options.game] if options.game else list(every_game)
    runs = [('compiled (cache ram)', False)]
    if cache_root is not None:
        runs = [('disk cache, first launch', True), ('disk cache, later launch', True)]
    for name in names:
        for run, disk in runs:
            ENGINE_SOUND_CACHE.clear()  # each run a new process: nothing compiled yet
            report(name, run, measure(every_game[name], disk=disk))
            _say('')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
