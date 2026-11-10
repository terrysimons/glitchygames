"""Allocation churn in a headless, uncapped replay (as the clone runs), one measurement per process.

Kinds, each its own run so one doesn't skew another:

- gc: every collector pause (``gc.callbacks``: start to stop), its generation and frame, against
  each frame's processing time: which slow frames (over twice the median, and the slowest 1%)
  had a pause, and how much of their time pauses were; and the young objects' types, sampled at
  every 20th generation-0 collection (what churns)
- tracemalloc: Python allocations by file and line: the peak, what's held at the end, and what
  grew after frame 60 (the game built)
- surfaces: calls into pygame that make a Surface (``Surface()``, copy, convert,
  convert_alpha, subsurface, ``pygame.transform.*``, ``Font.render``), counted through
  ``sys.setprofile`` (and a counting subclass for ``Surface()``, a type call it doesn't report)
- sprites: each sprite class's construction, the count and time of its outermost ``__init__``
  (a wrapper on each ``pygame.sprite.Sprite`` subclass's own ``__init__``, installed as each
  class is made, so this run imports the engine only after installing it)

Usage:
    uv run python -m scripts.mirror_measurements.churn --output DIR [--only NAME ...]
        [--kinds gc tracemalloc surfaces sprites]
"""

from __future__ import annotations

import argparse
import collections
import gc
import json
import statistics
import sys
import time
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Any

# Imports neither pygame nor the engine, so the sprites run can still wrap every sprite class
from scripts.mirror_measurements.common import (
    RECORDING_NAMES,
    in_milliseconds,
    percentiles,
    recording_named,
    replace_attribute,
    replaced,
    replay_with_hook,
    run_measurement,
)

if TYPE_CHECKING:
    import tracemalloc
    from collections.abc import Callable, Sequence

    from glitchygames.scenes import Scene

MODULE = 'scripts.mirror_measurements.churn'
KINDS = ('gc', 'tracemalloc', 'surfaces', 'sprites')
BUILT_FRAME = 60
YOUNG_TYPE_SAMPLE_EVERY = 20
SLOW_FRAME_RATIO = 2.0
SURFACE_METHODS = frozenset({
    'Surface.copy',
    'Surface.convert',
    'Surface.convert_alpha',
    'Surface.subsurface',
    'Surface.premul_alpha',
    'Font.render',
    'Font.render_to',
})
TOP_COUNT = 15


class FrameLog:
    """Each frame's processing time, in frame order, as a replay runs."""

    def __init__(self) -> None:
        """Start with no frames."""
        self.processing: list[float] = []
        self.on_built: Callable[[], None] | None = None

    def on_frame(self, frame: int, _scene: Scene | None, processing_seconds: float | None) -> None:
        """Keep a frame's processing time (and call ``on_built`` at frame 60)."""
        self.processing.append(processing_seconds or 0.0)
        if frame == BUILT_FRAME and self.on_built is not None:
            self.on_built()

    @property
    def frame(self) -> int:
        """The frame running now (the next to end)."""
        return len(self.processing)


def replay(*, name: str, log: FrameLog) -> None:
    """Replay a recording, keeping its frames' processing times in ``log``."""
    replay_with_hook(recording=recording_named(name), on_frame=log.on_frame)


def collector_pauses(*, name: str) -> dict[str, Any]:
    """Every collector pause, by frame, against slow frames; and the young objects' types.

    Returns:
        The run's result.

    """
    log = FrameLog()
    pauses: list[tuple[int, int, float]] = []
    pause_start = [0.0]
    young_types: collections.Counter[str] = collections.Counter()
    young_collections = [0]

    def on_collection(phase: str, info: dict[str, int]) -> None:
        if phase == 'start':
            if info['generation'] == 0:
                young_collections[0] += 1
                if young_collections[0] % YOUNG_TYPE_SAMPLE_EVERY == 0:
                    young_types.update(
                        type(item).__qualname__ for item in gc.get_objects(generation=0)
                    )
            # Set after the sample, so the sampling's own time isn't counted as the pause
            pause_start[0] = time.perf_counter()
        else:
            pauses.append((log.frame, info['generation'], time.perf_counter() - pause_start[0]))

    gc.callbacks.append(on_collection)
    try:
        replay(name=name, log=log)
    finally:
        gc.callbacks.remove(on_collection)
    paused_by_frame: collections.defaultdict[int, float] = collections.defaultdict(float)
    for frame, _generation, seconds in pauses:
        paused_by_frame[frame] += seconds
    processing = log.processing
    steady = range(1, len(processing))
    median = statistics.median(processing[index] for index in steady)
    slowest_count = max(1, len(steady) // 100)
    slowest = sorted(steady, key=lambda index: processing[index])[-slowest_count:]
    slow = [index for index in steady if processing[index] > SLOW_FRAME_RATIO * median]

    def explained(frames: Sequence[int]) -> dict[str, float]:
        total = sum(processing[index] for index in frames)
        paused = sum(paused_by_frame.get(index, 0.0) for index in frames)
        return {
            'frames': len(frames),
            'with_a_pause': sum(1 for index in frames if paused_by_frame.get(index, 0.0) > 0),
            'pause_share_of_their_time': paused / total if total else 0.0,
        }

    by_generation: dict[str, dict[str, float]] = {}
    for generation in (0, 1, 2):
        seconds = [pause for _frame, kind, pause in pauses if kind == generation]
        by_generation[str(generation)] = {
            'count': len(seconds),
            'total_ms': 1000 * sum(seconds),
            'max_ms': 1000 * max(seconds, default=0.0),
        }
    return {
        'frames': len(processing),
        'processing_ms': in_milliseconds(
            percentiles([processing[index] for index in steady])
        ).model_dump(),
        'pauses_by_generation': by_generation,
        'frames_with_a_pause': sum(1 for index in steady if paused_by_frame.get(index, 0.0) > 0),
        'slow_frames_over_twice_the_median': explained(slow),
        'slowest_1_percent': explained(slowest),
        'young_types_top': young_types.most_common(TOP_COUNT),
    }


def short_location(statistic: tracemalloc.Statistic | tracemalloc.StatisticDiff) -> str:
    """An allocation's file and line, from inside the project or site-packages.

    Returns:
        ``path:line``.

    """
    frame = statistic.traceback[0]
    path = frame.filename
    for marker in ('site-packages/', '/src/'):
        if marker in path:
            path = path.split(marker, 1)[1]
    return f'{path}:{frame.lineno}'


def python_allocations(*, name: str) -> dict[str, Any]:
    """Python's allocations by line: the peak, held at the end, grown after the game was built.

    Returns:
        The run's result.

    """
    import tracemalloc

    log = FrameLog()
    built: list[tracemalloc.Snapshot] = []
    log.on_built = lambda: built.append(tracemalloc.take_snapshot())
    tracemalloc.start(1)
    try:
        replay(name=name, log=log)
        end = tracemalloc.take_snapshot()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    grew = end.compare_to(built[0], 'lineno') if built else []
    return {
        'frames': len(log.processing),
        'traced_peak_mb': peak / 1e6,
        'traced_at_end_mb': current / 1e6,
        'held_at_end_top': [
            (short_location(statistic), statistic.size / 1e3, statistic.count)
            for statistic in end.statistics('lineno')[:TOP_COUNT]
        ],
        'grew_after_the_game_was_built_top': [
            (short_location(statistic), statistic.size_diff / 1e3, statistic.count_diff)
            for statistic in grew[:TOP_COUNT]
        ],
    }


def surface_calls(*, name: str) -> dict[str, Any]:
    """Count the calls into pygame that make a Surface, by name.

    Returns:
        The run's result.

    """
    import pygame

    log = FrameLog()
    counts: collections.Counter[str] = collections.Counter()

    def profiler(_frame: FrameType, event: str, argument: object) -> None:
        if event != 'c_call':
            return
        qualified = getattr(argument, '__qualname__', '')
        module = getattr(argument, '__module__', None) or ''
        if module.startswith('pygame.transform'):
            counts[f'transform.{qualified}'] += 1
        elif qualified in SURFACE_METHODS:
            counts[qualified] += 1

    real_surface = pygame.Surface

    class CountedSurface(real_surface):
        """``pygame.Surface``, counting each one made (the profiler doesn't see type calls)."""

        def __init__(self, *arguments: Any, **keywords: Any) -> None:
            """Count it, then make it."""
            counts['Surface()'] += 1
            super().__init__(*arguments, **keywords)

    with replaced(owner=pygame, name='Surface', replacement=CountedSurface):
        sys.setprofile(profiler)
        try:
            replay(name=name, log=log)
        finally:
            sys.setprofile(None)
    frames = len(log.processing)
    return {
        'frames': frames,
        'per_frame': {kind: count / frames for kind, count in counts.most_common()},
    }


def sprite_construction(*, name: str) -> dict[str, Any]:
    """Each sprite class's construction: how many were built and how long each took.

    Returns:
        The run's result.

    """
    import pygame

    builds: collections.defaultdict[str, list[float]] = collections.defaultdict(list)
    building: set[int] = set()

    def wrap_initializer(cls: type) -> None:
        own_initializer = cls.__dict__.get('__init__')
        if own_initializer is None:
            return

        def timed_initializer(self: object, *arguments: object, **keywords: object) -> None:
            # Only the outermost: a subclass's __init__ calling its parent's is one build
            if id(self) in building:
                own_initializer(self, *arguments, **keywords)
                return
            building.add(id(self))
            start = time.perf_counter()
            try:
                own_initializer(self, *arguments, **keywords)
            finally:
                builds[type(self).__qualname__].append(time.perf_counter() - start)
                building.discard(id(self))

        replace_attribute(owner=cls, name='__init__', replacement=timed_initializer)

    original_init_subclass = pygame.sprite.Sprite.__init_subclass__

    def init_subclass(cls: type[pygame.sprite.Sprite], **keywords: object) -> None:
        original_init_subclass(**keywords)
        wrap_initializer(cls)

    # Before the engine is imported (replay imports it), so every sprite class gets the wrapper
    replace_attribute(
        owner=pygame.sprite.Sprite, name='__init_subclass__', replacement=classmethod(init_subclass)
    )
    log = FrameLog()
    replay(name=name, log=log)
    classes = [
        {
            'class': class_name,
            'built': len(times),
            'mean_ms': 1000 * statistics.fmean(times),
            'max_ms': 1000 * max(times),
            'total_ms': 1000 * sum(times),
        }
        for class_name, times in builds.items()
    ]
    return {
        'frames': len(log.processing),
        'classes': sorted(classes, key=lambda entry: -float(entry['total_ms'])),
    }


MEASUREMENTS: dict[str, Callable[..., dict[str, Any]]] = {
    'gc': collector_pauses,
    'tracemalloc': python_allocations,
    'surfaces': surface_calls,
    'sprites': sprite_construction,
}


def summary_lines(*, name: str, kind: str, result: dict[str, Any]) -> str:
    """One run's summary.

    Returns:
        Its lines.

    """
    if kind == 'gc':
        pauses = ', '.join(
            f'gen{generation} {values["count"]:.0f}x max {values["max_ms"]:.2f} ms'
            for generation, values in result['pauses_by_generation'].items()
        )
        slowest = result['slowest_1_percent']
        return (
            f'{name} gc: {pauses}; slowest 1%: {slowest["frames"]} frames, '
            f'{slowest["with_a_pause"]} with a pause\n'
        )
    if kind == 'tracemalloc':
        return f'{name} tracemalloc: peak {result["traced_peak_mb"]:.1f} MB\n'
    if kind == 'surfaces':
        top = ', '.join(
            f'{call} {count:.2f}' for call, count in list(result['per_frame'].items())[:5]
        )
        return f'{name} surfaces per frame: {top}\n'
    total = sum(entry['total_ms'] for entry in result['classes'])
    built = sum(entry['built'] for entry in result['classes'])
    return f'{name} sprites: {built} built, {total:.0f} ms\n'


def main(arguments: list[str] | None = None) -> int:
    """Run every recording's measurements, each its own process, or (``--child``) one.

    Returns:
        0, or the first failed run's exit code.

    """
    parser = argparse.ArgumentParser(
        description='Allocation churn in a headless, uncapped replay, one measurement per process'
    )
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', nargs='+', choices=RECORDING_NAMES, default=RECORDING_NAMES)
    parser.add_argument('--kinds', nargs='+', choices=KINDS, default=KINDS)
    parser.add_argument('--child', nargs=2, metavar=('NAME', 'KIND'), help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    options.output.mkdir(parents=True, exist_ok=True)
    if options.child is not None:
        name, kind = options.child
        result = {'name': name, 'kind': kind, **MEASUREMENTS[kind](name=name)}
        (options.output / f'{name}-{kind}.json').write_text(
            json.dumps(result, indent=1), encoding='utf-8'
        )
        return 0
    for name in options.only:
        for kind in options.kinds:
            exit_code = run_measurement(
                module=MODULE, arguments=['--output', str(options.output), '--child', name, kind]
            )
            if exit_code:
                return exit_code
            path = options.output / f'{name}-{kind}.json'
            result = json.loads(path.read_text(encoding='utf-8'))
            sys.stdout.write(summary_lines(name=name, kind=kind, result=result))
            sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
