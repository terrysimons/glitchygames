r"""Time each phase of a game's frames, in the browser or on the desktop, and audit its surfaces.

A triage tool (first used on Zombies Ain't My Neighbors' title screen, whose blinking slots
hitch in the browser). It wraps the scene manager's frame phases and the draw calls under them,
so one frame's row says where its time went:

  update_scene, process_events, update_frame_services, render_scene, present_frame
      the scene manager's phases (``SceneManager._run_scene_frame``'s steps)
  sprites_clear, sprites_draw
      ``LayeredDirty.clear`` and ``LayeredDirty.draw`` (inside render_scene)
  make_opaque, display_update, display_flip
      the present step's work (inside present_frame): the whole-screen alpha fill, which runs
      only on a display with per-pixel alpha, and the copy to the window

Each row also has the frame's start (``clock.measured_seconds``, so intervals show hitches), its
scene, its dirty rects (count and area), how many sprites the draw blitted, and the garbage
collection pauses that fell inside it (``gc.callbacks``). Once, on the first measured frame, it
audits the surfaces: the display's format, and each sprite's image format against it (a
per-pixel alpha image blits through alpha blending; an image in another format is converted on
every blit).

It imports only the standard library, pygame and glitchygames, so the same file runs in the
browser bundle (scripts/measure_browser_frames.py copies it there, and browser/boot.py calls
``install_in_browser``) and on the desktop:

    uv run python -m scripts.frame_phase_probe zombies-aint-my-neighbors --seconds 8 \
        -- --crt-power-on off

The report is one JSON line: ``FRAME_PHASE_REPORT {...}`` (``REPORT_MARKER``).
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import gc
import importlib
import itertools
import json
import math
import statistics
import sys
import threading
from typing import TYPE_CHECKING, Any, Final

import pygame

from glitchygames import clock
from glitchygames.render_target import display_surface

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glitchygames.scenes.scene import Scene, SceneManager

# What starts the report's console line (scripts/measure_browser_frames.py looks for it)
REPORT_MARKER: Final = 'FRAME_PHASE_REPORT '
# The scene manager's frame phases (SceneManager._run_scene_frame's steps), by the name a row uses
MANAGER_PHASES: Final = {
    'update_scene': '_update_scene',
    'process_events': '_process_events',
    'update_frame_services': '_update_frame_services',
    'render_scene': '_render_scene',
    'present_frame': '_present_frame',
}
# The methods wrapped by more than timing: the scene frame (it opens and closes a row) and the
# sprite group's draw (it counts the sprites blitted)
FRAME_METHOD: Final = '_run_scene_frame'
DRAW_METHOD: Final = 'draw'
# The game host's pacing decision (glitchygames/host.py) and the two counts it keeps: the
# accumulator (periods that are no whole number of ticks) and the ticks since the last frame
PACER_METHOD: Final = 'should_run_frame'
PACER_ACCUMULATOR: Final = '_accumulated_seconds'
PACER_TICK_COUNT: Final = '_ticks_since_frame'
# Every timed phase a row can hold, in report order (those inside another follow it)
PHASE_NAMES: Final = (
    'update_scene',
    'process_events',
    'update_frame_services',
    'render_scene',
    'sprites_clear',
    'sprites_draw',
    'present_frame',
    'make_opaque',
    'display_update',
    'display_flip',
)
# A frame interval this many times the median is a hitch
HITCH_FACTOR: Final = 1.5
# The games the desktop run knows: their module and first scene class (as the browser bundle's)
DESKTOP_GAMES: Final = {
    'zombies-aint-my-neighbors': ('zombies_aint_my_neighbors.title', 'TitleScene'),
}

type Row = dict[str, Any]


class FrameProbe:
    """Collects one row per scene frame; reports once the measured frames span enough time."""

    def __init__(
        self,
        *,
        measure_seconds: float,
        warmup_seconds: float,
        scene_name: str | None,
        emit: Callable[[str], None],
    ) -> None:
        """Make a probe (``install`` wraps the engine).

        Args:
            measure_seconds: How long to measure, from the first measured frame.
            warmup_seconds: How long the measured scene runs before measuring starts.
            scene_name: Only frames of the scene of this class name count (None: every frame).
            emit: Where the report line goes (print, in the browser the console).

        """
        self.measure_seconds = measure_seconds
        self.warmup_seconds = warmup_seconds
        self.scene_name = scene_name
        self.emit = emit
        self.rows: list[Row] = []
        self.surface_audit: dict[str, Any] | None = None
        self.reported = False
        # The frame being run (None between frames): phases add their times to it
        self._frame: Row | None = None
        self._scene_first_seen: float | None = None
        self._gc_started: float | None = None
        # Every outer tick the pacer saw while measuring (the browser's animation frames):
        # its timestamp, the accumulator and tick count before and after, and whether a frame ran
        self.ticks: list[dict[str, Any]] = []

    # The wrappers ----------------------------------------------------------------------------

    def install(self) -> None:
        """Wrap the scene manager's phases, the sprite group's draw calls and the display's."""
        from glitchygames.scenes import scene as scene_module

        # Wrapped by name (getattr and setattr): the methods are the engine's private ones, and
        # a triage tool patching them is the point
        manager_class = scene_module.SceneManager
        original_frame: Callable[[SceneManager], None] = getattr(manager_class, FRAME_METHOD)
        probe = self

        @functools.wraps(original_frame)
        def run_scene_frame(manager: SceneManager) -> None:
            probe._begin_frame(manager=manager)
            try:
                original_frame(manager)
            finally:
                probe._end_frame(manager=manager)

        setattr(manager_class, FRAME_METHOD, run_scene_frame)
        for phase, method_name in MANAGER_PHASES.items():
            self._wrap(owner=manager_class, name=method_name, phase=phase)
        group_class = pygame.sprite.LayeredDirty
        self._wrap(owner=group_class, name='clear', phase='sprites_clear')
        original_draw: Callable[..., list[pygame.Rect]] = getattr(group_class, DRAW_METHOD)

        @functools.wraps(original_draw)
        def draw(
            group: pygame.sprite.LayeredDirty[pygame.sprite.DirtySprite],
            *arguments: object,
            **keywords: object,
        ) -> list[pygame.Rect]:
            if probe._frame is not None:
                # What draw blits: every visible sprite whose dirty flag is set
                probe._frame['sprites_blitted'] += sum(
                    1 for sprite in group.sprites() if sprite.visible and sprite.dirty
                )
            return original_draw(group, *arguments, **keywords)

        setattr(group_class, DRAW_METHOD, draw)
        self._wrap(owner=group_class, name=DRAW_METHOD, phase='sprites_draw')
        self._wrap(owner=scene_module, name='make_opaque', phase='make_opaque')
        self._wrap(owner=pygame.display, name='update', phase='display_update')
        self._wrap(owner=pygame.display, name='flip', phase='display_flip')
        self._wrap_pacer()
        gc.callbacks.append(self._on_garbage_collection)

    def _wrap_pacer(self) -> None:
        """Record each of the game host's pacing decisions (``TickPacer.should_run_frame``)."""
        from glitchygames import host

        pacer_class = host.TickPacer
        original: Callable[..., bool] = getattr(pacer_class, PACER_METHOD)
        probe = self

        @functools.wraps(original)
        def should_run_frame(
            pacer: host.TickPacer, *, tick_seconds: float, period_seconds: float
        ) -> bool:
            before = getattr(pacer, PACER_ACCUMULATOR)
            ticks_before = getattr(pacer, PACER_TICK_COUNT)
            runs = original(pacer, tick_seconds=tick_seconds, period_seconds=period_seconds)
            # Only while measuring: between the first measured frame and the report
            if probe.rows and not probe.reported:
                probe.ticks.append({
                    'tick_seconds': tick_seconds,
                    'period_seconds': period_seconds,
                    'accumulated_before': before,
                    'accumulated_after': getattr(pacer, PACER_ACCUMULATOR),
                    'ticks_since_frame_before': ticks_before,
                    'ticks_since_frame_after': getattr(pacer, PACER_TICK_COUNT),
                    'measured_tick_seconds': pacer.measured_tick_seconds(),
                    'ran_frame': runs,
                })
            return runs

        setattr(pacer_class, PACER_METHOD, should_run_frame)

    def _wrap(self, *, owner: object, name: str, phase: str) -> None:
        """Replace ``owner``'s attribute ``name`` with a timed wrapper (``_timed``)."""
        original: Callable[..., object] = getattr(owner, name)
        setattr(owner, name, self._timed(phase=phase, function=original))

    def _timed[**Parameters, Result](
        self, *, phase: str, function: Callable[Parameters, Result]
    ) -> Callable[Parameters, Result]:
        """Wrap ``function`` so its time inside a frame adds to that frame's ``phase``.

        Returns:
            The wrapper.

        """
        probe = self

        @functools.wraps(function)
        def timed(*arguments: Parameters.args, **keywords: Parameters.kwargs) -> Result:
            started = clock.measured_seconds()
            try:
                return function(*arguments, **keywords)
            finally:
                if probe._frame is not None:
                    phases = probe._frame['phases']
                    phases[phase] = phases.get(phase, 0.0) + clock.measured_seconds() - started

        return timed

    def _on_garbage_collection(self, phase: str, info: dict[str, Any]) -> None:
        if phase == 'start':
            self._gc_started = clock.measured_seconds()
            return
        if self._gc_started is None or self._frame is None:
            return
        self._frame['gc_pauses'].append({
            'generation': info.get('generation'),
            'seconds': clock.measured_seconds() - self._gc_started,
        })
        self._gc_started = None

    # The frames ------------------------------------------------------------------------------

    def _begin_frame(self, *, manager: SceneManager) -> None:
        if self.reported:
            return
        scene = manager.active_scene
        self._frame = {
            'start': clock.measured_seconds(),
            'scene': type(scene).__name__,
            'game_time': getattr(scene, 'game_time', None),
            'phases': {},
            'gc_pauses': [],
            'sprites_blitted': 0,
            'rect_count': 0,
            'rect_area': 0,
        }

    def _end_frame(self, *, manager: SceneManager) -> None:
        frame, self._frame = self._frame, None
        if frame is None or self.reported:
            return
        frame['duration'] = clock.measured_seconds() - frame['start']
        scene = manager.active_scene
        rects: list[pygame.Rect] = getattr(scene, 'rects', None) or []
        frame['rect_count'] = len(rects)
        frame['rect_area'] = sum(rect.width * rect.height for rect in rects)
        if not self._counts(frame=frame):
            return
        if self.surface_audit is None:
            self.surface_audit = audit_surfaces(
                display=display_surface(), sprites=_scene_sprites(scene=scene)
            )
        self.rows.append(frame)
        if frame['start'] - self.rows[0]['start'] >= self.measure_seconds:
            self.report()

    def _counts(self, *, frame: Row) -> bool:
        """Return whether ``frame`` is measured: of the scene asked for, after the warmup.

        Returns:
            True to keep its row.

        """
        if self.scene_name is not None and frame['scene'] != self.scene_name:
            return False
        if self._scene_first_seen is None:
            self._scene_first_seen = frame['start']
        return frame['start'] - self._scene_first_seen >= self.warmup_seconds

    def report(self) -> None:
        """Emit the report line once: the environment, the surface audit, a summary, the rows."""
        if self.reported:
            return
        self.reported = True
        report = {
            'environment': environment(),
            'surface_audit': self.surface_audit,
            'summary': summarize(rows=self.rows),
            'pacing': summarize_ticks(ticks=self.ticks),
            'rows': self.rows,
            'ticks': self.ticks,
        }
        self.emit(REPORT_MARKER + json.dumps(report))


def _scene_sprites(*, scene: Scene | None) -> list[pygame.sprite.DirtySprite]:
    group = getattr(scene, 'all_sprites', None)
    return [] if group is None else list(group.sprites())


def surface_format(*, surface: pygame.Surface) -> dict[str, Any]:
    """Return what decides a surface's blit cost: its size, depth, alpha and channel masks.

    Returns:
        The format, JSON-ready.

    """
    colorkey = surface.get_colorkey()
    return {
        'size': list(surface.get_size()),
        'bitsize': surface.get_bitsize(),
        'per_pixel_alpha': bool(surface.get_flags() & pygame.SRCALPHA),
        'surface_alpha': surface.get_alpha(),
        'colorkey': None if colorkey is None else list(colorkey),
        'masks': list(surface.get_masks()),
    }


def audit_surfaces(*, display: pygame.Surface | None, sprites: Sequence[Any]) -> dict[str, Any]:
    """Return the display's format and each sprite image's, with whether a blit must convert.

    A blit between different masks or depths converts every pixel on every blit; a per-pixel
    alpha image blends every pixel; neither applies to an image in the display's own format
    without alpha.

    Returns:
        ``display`` (its format, or None without one) and ``sprites`` (name, dirty, visible,
        format, ``matches_display``: same depth and red, green and blue masks).

    """
    display_format = None if display is None else surface_format(surface=display)
    audited: list[dict[str, Any]] = []
    for sprite in sprites:
        image = getattr(sprite, 'image', None)
        if image is None:
            continue
        image_format = surface_format(surface=image)
        audited.append({
            'name': getattr(sprite, 'name', type(sprite).__name__),
            'dirty': sprite.dirty,
            'visible': sprite.visible,
            'format': image_format,
            'matches_display': display_format is not None
            and image_format['bitsize'] == display_format['bitsize']
            and image_format['masks'][:3] == display_format['masks'][:3],
        })
    return {'display': display_format, 'sprites': audited}


def environment() -> dict[str, Any]:
    """Return where the probe ran: the platform, pygame and SDL versions and the video driver.

    Returns:
        The environment, JSON-ready.

    """
    return {
        'platform': sys.platform,
        'python': sys.version.split()[0],
        'pygame': pygame.version.ver,
        'sdl': '.'.join(str(part) for part in pygame.get_sdl_version()),
        'video_driver': pygame.display.get_driver() if pygame.display.get_init() else None,
    }


def distribution(*, values: Sequence[float]) -> dict[str, float]:
    """Return the count, median, 95th and 99th percentile and maximum of ``values``.

    Percentiles are nearest-rank (the value at or above that share of the sorted values).

    Returns:
        The distribution (zeros for no values).

    """
    if not values:
        return {'count': 0, 'median': 0.0, 'p95': 0.0, 'p99': 0.0, 'max': 0.0}
    ordered = sorted(values)

    def rank(share: float) -> float:
        return ordered[max(0, math.ceil(share * len(ordered)) - 1)]

    return {
        'count': len(ordered),
        'median': statistics.median(ordered),
        'p95': rank(0.95),
        'p99': rank(0.99),
        'max': ordered[-1],
    }


def summarize(*, rows: Sequence[Row]) -> dict[str, Any]:
    """Summarize measured frames: each phase, the frame intervals, and every hitch.

    A hitch is a frame interval (one frame's start to the next's) over ``HITCH_FACTOR`` times
    the median interval; it names the frame before the gap, its slowest phase and the garbage
    collection pauses inside it. A gap no frame's own phases explain is time spent outside the
    frame (the browser, the pacing, the host).

    Returns:
        ``frames`` (their count), ``frame_seconds`` and ``interval_seconds`` distributions,
        ``phase_seconds`` (a distribution per phase, over every frame, zero where it did not
        run), ``rects`` (count and area distributions), ``sprites_blitted`` and ``hitches``.

    """
    intervals = [later['start'] - earlier['start'] for earlier, later in itertools.pairwise(rows)]
    median_interval = statistics.median(intervals) if intervals else 0.0
    hitches: list[dict[str, Any]] = []
    for earlier, interval in zip(rows, intervals, strict=False):
        if median_interval and interval > HITCH_FACTOR * median_interval:
            phases = earlier['phases']
            slowest = max(phases, key=phases.get) if phases else None
            hitches.append({
                'game_time': earlier['game_time'],
                'interval': interval,
                'frame': earlier['duration'],
                'slowest_phase': slowest,
                'slowest_phase_seconds': phases.get(slowest, 0.0) if slowest else 0.0,
                'gc_seconds': sum(pause['seconds'] for pause in earlier['gc_pauses']),
            })
    return {
        'frames': len(rows),
        'frame_seconds': distribution(values=[row['duration'] for row in rows]),
        'interval_seconds': distribution(values=intervals),
        'phase_seconds': {
            phase: distribution(values=[row['phases'].get(phase, 0.0) for row in rows])
            for phase in PHASE_NAMES
        },
        'gc_pause_seconds': distribution(
            values=[pause['seconds'] for row in rows for pause in row['gc_pauses']]
        ),
        'rects': {
            'count': distribution(values=[row['rect_count'] for row in rows]),
            'area': distribution(values=[row['rect_area'] for row in rows]),
        },
        'sprites_blitted': distribution(values=[row['sprites_blitted'] for row in rows]),
        'hitches': hitches,
    }


def summarize_ticks(*, ticks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the outer ticks: their intervals, and how many ticks each frame waited.

    A browser's ticks follow the display's refresh (8.33 ms at 120 Hz); a 60 FPS game should run
    a frame on every second one. ``ticks_per_frame`` counts, for each frame after the first,
    how many ticks passed since the previous frame; ``skipped_tick_gaps`` lists every tick
    interval over ``HITCH_FACTOR`` times the median (the browser itself late: a missed
    animation frame).

    Returns:
        ``ticks`` (their count), ``interval_seconds`` (a distribution), ``ticks_per_frame``
        (waits and how often each happened) and ``skipped_tick_gaps``.

    """
    intervals = [
        later['tick_seconds'] - earlier['tick_seconds']
        for earlier, later in itertools.pairwise(ticks)
    ]
    median_interval = statistics.median(intervals) if intervals else 0.0
    ticks_per_frame: dict[int, int] = {}
    waited = 0
    seen_frame = False
    for tick in ticks:
        waited += 1
        if tick['ran_frame']:
            if seen_frame:
                ticks_per_frame[waited] = ticks_per_frame.get(waited, 0) + 1
            seen_frame = True
            waited = 0
    return {
        'ticks': len(ticks),
        'interval_seconds': distribution(values=intervals),
        'ticks_per_frame': {
            str(count): ticks_per_frame[count] for count in sorted(ticks_per_frame)
        },
        'skipped_tick_gaps': [
            {'tick_seconds': later['tick_seconds'], 'interval': interval}
            for later, interval in zip(ticks[1:], intervals, strict=True)
            if median_interval and interval > HITCH_FACTOR * median_interval
        ],
    }


def install_in_browser(*, settings: dict[str, Any], emit: Callable[[str], None]) -> FrameProbe:
    """Install a probe from boot_config.json's ``frame_probe`` settings (browser/boot.py).

    Args:
        settings: ``measure_seconds``, ``warmup_seconds`` and ``scene_name`` (optional).
        emit: Where the report goes (print: the browser console).

    Returns:
        The installed probe.

    """
    probe = FrameProbe(
        measure_seconds=float(settings['measure_seconds']),
        warmup_seconds=float(settings['warmup_seconds']),
        scene_name=settings.get('scene_name'),
        emit=emit,
    )
    probe.install()
    return probe


def main(argv: list[str] | None = None) -> int:
    """Run a game on the desktop with the probe, print its report and quit.

    Returns:
        0 once reported; 1 when the game ended before the probe reported.

    """
    parser = argparse.ArgumentParser(description="Time a game's frame phases on the desktop.")
    parser.add_argument('game', choices=sorted(DESKTOP_GAMES))
    parser.add_argument('--seconds', type=float, default=8.0, help='how long to measure')
    parser.add_argument('--warmup', type=float, default=2.0, help='seconds before measuring')
    parser.add_argument('--scene', default=None, help='measure only this scene class')
    parser.add_argument('game_arguments', nargs='*', help='after --: the game command line')
    arguments = parser.parse_args(argv)
    module_name, scene_class_name = DESKTOP_GAMES[arguments.game]
    game_class = getattr(importlib.import_module(module_name), scene_class_name)
    finished = threading.Event()

    def emit(line: str) -> None:
        sys.stdout.write(line + '\n')
        sys.stdout.flush()
        finished.set()
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    probe = FrameProbe(
        measure_seconds=arguments.seconds,
        warmup_seconds=arguments.warmup,
        scene_name=arguments.scene or scene_class_name,
        emit=emit,
    )
    probe.install()
    from glitchygames.engine import GameEngine

    sys.argv = [arguments.game, *arguments.game_arguments]
    # The engine exits through SystemExit once the probe's QUIT is handled
    with contextlib.suppress(SystemExit):
        GameEngine(game=game_class).start()
    return 0 if finished.is_set() else 1


if __name__ == '__main__':
    sys.exit(main())
