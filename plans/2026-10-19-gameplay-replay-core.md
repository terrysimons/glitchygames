# Gameplay Replay — Part 1: Replay Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Master plan:** [2026-10-19-gameplay-replay-implementation.md](2026-10-19-gameplay-replay-implementation.md)
(read its Global Constraints, Review Focus and Cross-part interfaces first; they apply to every
task here)

**Goal:** Put every input the engine takes from the outside world behind swappable doors, record
what passes through them, and replay a recording exactly with `--replay-trace`, reporting the first
divergence.

**Architecture:** `glitchygames/sources.py` holds the doors and a module-level registry
(like `glitchygames/randomness.py`'s `_STATE`), so engine code, games and widgets reach the active
sources without an engine reference. `GameEngine._pump_events`, `SceneManager.start`/
`_finish_frame` and `GameEngine.process_events` ask the active sources; `RecordingSources` wraps
another sources object and writes what passes through; `ReplaySources` serves a recording and
compares each frame's sprites with it. Code that bypassed pygame's queue (polled input, wall-clock
reads, device construction, save files) moves behind the doors, enforced by an AST guard test.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8, pytest + pytest-mock, uv.

**Spec:** `plans/2026-10-19-gameplay-replay.md` (sections 1, 2, 3, 6)

## Global Constraints

See the master plan. In addition, for this part:

- `LiveSources` must reproduce today's behaviour exactly: the golden test passes after every task
  (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/world/test_golden_traces.py -q
  -p no:cacheprovider --no-cov`). The golden files stay format version 2 and are never re-recorded.
- Existing recordings (format version 2) must keep reading and replaying.
- Spec section 3.4 lists the bypass sites; re-grep before and after Task 8 (the command is in
  Task 8) — the lists below were taken at commit `da29bf2`.

## Review Focus

From the master plan, owned here: items 1–4.

## Tasks

| # | Task | Produces |
|---|---|---|
| 1 | Trace format version 3 | `TRACE_FORMAT_VERSION = 3`, `READABLE_FORMAT_VERSIONS`, `TraceReader.format_version` |
| 2 | The doors and the registry | `sources.py` (leaf), `live_sources.py`, `install_sources`, frame number |
| 3 | Input snapshots | `InputSnapshot`, `current_input`, capture after the pump, diffs |
| 4 | Game time and the frame clock | `Scene.game_time`, frame clock advanced in `_finish_frame`, FPS events from it |
| 5 | The devices door | `DeviceRegistry` (enumeration + opening + polling), stand-ins |
| 6 | Every device site through the devices door | construction, enumeration, polling moved |
| 7 | The saves door | `open_saves`, `SaveStore`, `SandboxSaves`, the four games moved |
| 8 | Clock exports; polled input, engine, UI and game clock sites | `glitchygames/clock.py`, sites moved |
| 9 | Bitmappy onto the clock exports, and the guard test | 74 Bitmappy sites; `tests/test_engine_doors.py` |
| 10 | Supervisor hook and control events | `add_supervisor`, `record_control_event`, handlers |
| 11 | `RecordingSources` | recorder folded into the doors; format-3 fields recorded |
| 12 | `ReplaySources`: startup, the replay doors and frame comparison | `--replay-trace`, `Divergence`, harness replay |
| 13 | Exact event merging, references and control-event markers | internal-event checks, reference mapping |
| 14 | `--audit` | two subprocess replays with per-frame digests |
| 15 | Documentation | CLAUDE.md, recording docstring, docs page, spec amendments, future-work |

---

### Task 1: Trace format version 3

**Files:**
- Modify: `glitchygames/tracing.py:1-60` (module docstring), `:89` (`TRACE_FORMAT_VERSION`),
  `:689-770` (`TraceReader`), `:852-886` (`TraceReadResult`, `read_trace_result`)
- Modify: `glitchygames/recording.py:126` (new frame-field constants after `EVENT_BATCHES_FIELD`)
- Test: `tests/test_tracing.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `TRACE_FORMAT_VERSION = 3`; `READABLE_FORMAT_VERSIONS = (2, 3)`;
  `TraceReader.format_version: int`; `TraceReadResult.format_version: int`; in `recording.py`:
  `INPUT_CHANGES_FIELD = 'input_changes'`, `CONTROL_EVENTS_FIELD = 'control_events'`,
  `DEVICES_OPENED_FIELD = 'devices_opened'`, `SAVES_OPENED_FIELD = 'saves_opened'`,
  `SCENE_START_FIELD = 'scene_start'`, `SAVES_HEADER_FIELD = 'saves'`,
  `DEVICES_HEADER_FIELD = 'devices'`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_tracing.py`; it already imports
  `gzip`, `json`, `TraceReader`, `TraceWriter`, `read_trace_result`, `TraceFormatError` — check the
  imports at the top and add any missing one)

```python
class TestFormatVersionThree:
    """Format version 3 adds recording fields; version 2 files still read."""

    def test_writer_writes_version_three(self, tmp_path):
        path = tmp_path / 'trace.jsonl.gz'
        with TraceWriter(path=path, header={'game': 'demo', 'frame_seconds': None}) as writer:
            writer.write_frame(frame_record={'frame': 0, 'scene': 'Demo', 'sprites': []})
        with gzip.open(path, 'rt', encoding='utf-8') as trace_file:
            header = json.loads(trace_file.readline())
        assert header['format_version'] == 3

    def test_reader_reports_the_file_version(self, tmp_path):
        path = tmp_path / 'trace.jsonl.gz'
        with TraceWriter(path=path, header={'game': 'demo', 'frame_seconds': None}) as writer:
            writer.write_frame(frame_record={'frame': 0, 'scene': 'Demo', 'sprites': []})
        result = read_trace_result(path=path)
        assert result.format_version == 3

    def test_version_two_file_still_reads(self, tmp_path):
        path = tmp_path / 'old.jsonl.gz'
        lines = [
            {'format_version': 2, 'game': 'demo', 'frame_seconds': None},
            {'frame': 0, 'kind': 'keyframe', 'scene': 'Demo', 'sprites': []},
        ]
        with gzip.open(path, 'wt', encoding='utf-8') as trace_file:
            trace_file.writelines(json.dumps(line) + '\n' for line in lines)
        with TraceReader(path=path) as reader:
            frames = list(reader)
        assert reader.format_version == 2
        assert frames == [{'frame': 0, 'scene': 'Demo', 'sprites': []}]

    def test_unknown_version_is_refused(self, tmp_path):
        path = tmp_path / 'future.jsonl.gz'
        with gzip.open(path, 'wt', encoding='utf-8') as trace_file:
            trace_file.write(json.dumps({'format_version': 4, 'game': 'demo'}) + '\n')
        with pytest.raises(TraceFormatError, match='format_version 4'):
            TraceReader(path=path)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SDL_VIDEODRIVER=dummy uv run pytest tests/test_tracing.py -k FormatVersionThree -q -p no:cacheprovider --no-cov`
Expected: FAIL (`format_version` is 2; `TraceReadResult` has no `format_version`).

- [ ] **Step 3: Implement**

In `glitchygames/tracing.py`:

```python
TRACE_FORMAT_VERSION = 3
# Versions this reader decodes: version 3 only adds frame and header fields a recording uses
# (glitchygames/recording.py), so a version 2 file decodes exactly as before
READABLE_FORMAT_VERSIONS = (2, 3)
```

In `TraceReader._read_header`, replace the version check and keep the version:

```python
        format_version = header.pop(FORMAT_VERSION_FIELD, None)
        if format_version not in READABLE_FORMAT_VERSIONS:
            message = (
                f'{self.path}: unsupported trace format_version {format_version} '
                f'(this reader understands {list(READABLE_FORMAT_VERSIONS)})'
            )
            raise TraceFormatError(message)
        self.format_version = cast('int', format_version)
        return header
```

and declare `self.format_version: int = TRACE_FORMAT_VERSION` in `__init__` before
`self.header = self._read_header()`; document `format_version` in the class's Attributes.
Add `format_version: int` to `TraceReadResult` (document it) and pass
`format_version=reader.format_version` in `read_trace_result`. Update the module docstring: "On disk
(format version 3, which reads version 2 files too) ..." and a paragraph listing the recording
fields version 3 adds (point to `glitchygames/recording.py`).

In `glitchygames/recording.py`, after `EVENT_BATCHES_FIELD`:

```python
# Frame fields format version 3 adds (each written only on frames where it is not empty)
INPUT_CHANGES_FIELD = 'input_changes'
CONTROL_EVENTS_FIELD = 'control_events'
DEVICES_OPENED_FIELD = 'devices_opened'
SAVES_OPENED_FIELD = 'saves_opened'
SCENE_START_FIELD = 'scene_start'
# Header fields format version 3 adds
SAVES_HEADER_FIELD = 'saves'
DEVICES_HEADER_FIELD = 'devices'
```

- [ ] **Step 4: Run the tests to see them pass, plus the existing trace and golden tests**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/test_tracing.py tests/test_recording.py tests/world/test_golden_traces.py tests/world/test_gameplay_recording.py -q -p no:cacheprovider --no-cov`
Expected: PASS. If a test pins `format_version == 2` for newly written files, update it to 3 (the
golden files on disk stay version 2 and still read).

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/tracing.py glitchygames/recording.py tests/test_tracing.py
git commit -m "Trace format version 3: read versions 2 and 3, name the recording fields"
```

---

### Task 2: The doors and the registry

**Files:**
- Create: `glitchygames/sources.py` (a leaf: the `EngineSources` Protocol, the registry, the frame
  clock; module-level imports are `glitchygames.randomness` and `TYPE_CHECKING`-only types)
- Create: `glitchygames/live_sources.py` (`LiveSources`, the live providers)
- Modify: `glitchygames/engine/game_engine.py:547-575` (`__init__`: reset and install the doors),
  `:1380-1406` (`_pump_events`), new method `install_sources`
- Modify: `glitchygames/scenes/scene.py:121-175` (`SceneManager.__init__`: `frame_number`),
  `:784-821` (`start`), `:822-870` (`_finish_frame`), `:872-898` (`_run_frame`)
- Modify: `tests/conftest.py` (autouse reset of the doors after each test)
- Test: `tests/engine/test_engine_sources.py` (new: a new module gets its own test file)

**Layering rule (applies to every later task):** `glitchygames/sources.py` and
`glitchygames/clock.py` are leaves. Any module may import them; they import nothing from the
package at module level except `glitchygames.randomness` (and `glitchygames.sources` for
`clock.py`); types they mention come in under `TYPE_CHECKING`. The providers that need the input,
devices and saves modules live in `glitchygames/live_sources.py`, `glitchygames/recording.py` and
`glitchygames/replay/`, which import the leaves, never the reverse. The one function-level import
is `active_sources()` creating the default `LiveSources` when nothing was installed; it is
documented at the import. Task 8 adds a test that imports each door module alone in a fresh
interpreter, so a cycle fails a test instead of a game start.

**Interfaces:**
- Consumes: nothing.
- Produces (this task's subset of the master's `EngineSources`; Tasks 3, 5, 7, 8 and 10 add
  methods):

```python
class EngineSources(Protocol):
    random_seed: int
    @property
    def stop_requested(self) -> bool: ...
    def on_installed(self) -> None: ...      # install_sources calls it (Task 12: replay starts
                                             # internal-post tracking here)
    def on_uninstalled(self) -> None: ...    # reset_sources calls it
    def pump_events(self) -> list[pygame.event.Event]: ...
    def frame_seconds(self, *, measured: float) -> float: ...
    def end_frame(self, *, frame_number: int, dt: float, scene: Scene | None) -> None: ...
def active_sources() -> EngineSources
def install_sources(*, sources: EngineSources) -> None   # raises SourcesAlreadyRunningError
def mark_frames_started() -> None
def reset_sources() -> None
def advance_frame_clock(*, seconds: float) -> None       # SceneManager._finish_frame (Task 4)
def frame_clock_seconds() -> float
class LiveSources:   # glitchygames/live_sources.py
    def __init__(self, *, random_seed: int, use_fastevents: bool = False) -> None: ...
GameEngine.install_sources(self, *, sources: EngineSources) -> None
SceneManager.frame_number: int     # frames finished so far this run
```

- [ ] **Step 1: Write the failing tests** (`tests/engine/test_engine_sources.py`)

```python
"""The engine's doors (glitchygames/sources.py): live by default, swappable before the first
frame, and the only way the frame loop reads events and frame time."""

from __future__ import annotations

from typing import Any, Self

import pygame
import pytest
from scripts.record_golden_traces import (
    FRAME_SECONDS,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)

from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene
from glitchygames.sources import (
    SourcesAlreadyRunningError,
    active_sources,
    install_sources,
    mark_frames_started,
    reset_sources,
)

SCRIPTED_KEY = pygame.K_x


class KeyCountingScene(Scene):
    """Counts the key-down events it receives."""

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        super().__init__(options=options, groups=groups)
        self.keys_seen: list[int] = []

    def on_key_down_event(self: Self, event: Any) -> None:
        self.keys_seen.append(event.key)


class ScriptedSources(LiveSources):
    """Live sources whose pump returns one scripted key press on the first pump only."""

    def __init__(self: Self) -> None:
        super().__init__(random_seed=1)
        self.pump_count = 0
        self.ended_frames: list[int] = []
        self.installed_calls = 0
        self.uninstalled_calls = 0

    def on_installed(self: Self) -> None:
        self.installed_calls += 1

    def on_uninstalled(self: Self) -> None:
        self.uninstalled_calls += 1

    def pump_events(self: Self) -> list[pygame.event.Event]:
        self.pump_count += 1
        pygame.event.get()  # the real queue is drained and ignored
        if self.pump_count == 1:
            return [pygame.event.Event(pygame.KEYDOWN, {'key': SCRIPTED_KEY, 'mod': 0,
                                                        'unicode': 'x', 'scancode': 27})]
        return []

    def end_frame(self: Self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        self.ended_frames.append(frame_number)


def start_engine(*, scene_class: type[Scene]) -> GoldenTraceSceneManager:
    manager = GoldenTraceSceneManager.install()
    with command_line(['--windowed', '--resolution', '320x240', '--log-level', 'warning']):
        engine = GoldenTraceEngine(game=scene_class)
    engine.install_game(scene_class=scene_class)
    return manager


class TestRegistry:
    def test_live_sources_are_the_default(self):
        assert isinstance(active_sources(), LiveSources)

    def test_installed_sources_become_active_and_are_told(self):
        sources = ScriptedSources()
        install_sources(sources=sources)
        assert active_sources() is sources
        assert sources.installed_calls == 1

    def test_reset_tells_the_installed_sources(self):
        sources = ScriptedSources()
        install_sources(sources=sources)
        reset_sources()
        assert sources.uninstalled_calls == 1
        assert active_sources() is not sources

    def test_install_after_the_first_frame_is_refused(self):
        mark_frames_started()
        with pytest.raises(SourcesAlreadyRunningError):
            install_sources(sources=ScriptedSources())


class TestFrameLoopUsesTheDoors:
    def test_events_come_from_the_installed_pump(self):
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            sources = ScriptedSources()
            install_sources(sources=sources)
            manager.dt = FRAME_SECONDS
            manager.run_frame()
            scene = manager.active_scene
            assert isinstance(scene, KeyCountingScene)
            assert scene.keys_seen == [SCRIPTED_KEY]
            assert sources.pump_count == 1
        finally:
            GoldenTraceSceneManager.uninstall()

    def test_every_frame_ends_through_the_sources_with_its_number(self):
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            sources = ScriptedSources()
            install_sources(sources=sources)
            for _ in range(3):
                manager.dt = FRAME_SECONDS
                manager.run_frame()
            assert sources.ended_frames == [0, 1, 2]
            assert manager.frame_number == 3
        finally:
            GoldenTraceSceneManager.uninstall()

    def test_frame_seconds_sets_dt(self, mocker):
        # GoldenTraceEngine.__init__ resets the doors, so install after constructing it
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            sources = LiveSources(random_seed=1)
            mocker.patch.object(sources, 'frame_seconds', return_value=0.25)
            install_sources(sources=sources)
            closing = manager._finish_frame(
                frame_start_seconds=0.0, timer=None, period_ns=0,
                previous_deadline_ns=None, processing_seconds=0.0,
            )
            assert manager.dt == 0.25
            assert closing > 0.0
        finally:
            GoldenTraceSceneManager.uninstall()
```

`tests/world/test_finish_frame.py`'s `FrameDriver` patches `scene.time` and runs `start()`; its
tests keep passing because `LiveSources.frame_seconds` returns the measurement unchanged. Run them
in Step 4.

In `tests/conftest.py` add an autouse fixture (next to the existing autouse class-attribute
restore fixture):

```python
@pytest.fixture(autouse=True)
def reset_engine_sources():
    """Give every test fresh live doors and reset them afterwards (glitchygames/sources.py).

    reset_sources() tells the installed sources (on_uninstalled), which is where a replay stops
    tracking code-posted events (Task 12), so no tracking leaks into the next test.
    """
    from glitchygames.sources import reset_sources

    reset_sources()
    yield
    reset_sources()
```

- [ ] **Step 2: Run to see them fail**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/engine/test_engine_sources.py -q -p no:cacheprovider --no-cov`
Expected: FAIL with `ModuleNotFoundError: glitchygames.live_sources`.

- [ ] **Step 3: Implement**

`glitchygames/sources.py`:

```python
"""The engine's doors: every input the engine takes from the outside world.

The engine reads events, frame time, polled input, devices, saves, the clocks and the random seed
only through the active ``EngineSources``. Live play uses ``LiveSources``
(glitchygames/live_sources.py); ``--record-trace`` wraps them in ``RecordingSources``
(glitchygames/recording.py); ``--replay-trace`` installs ``ReplaySources``
(glitchygames/replay/driver.py). Everything downstream of the doors runs unchanged, so a replay
goes through the real engine.

The registry is module state, like glitchygames/randomness.py's streams, so engine code, games
and widgets reach the active sources without an engine reference. ``install_sources`` may only be
called before the first frame (a run never mixes live and recorded input); in-game playback pushes
scoped sources on top instead (``push_scoped_sources``, Part 3 of
plans/2026-10-19-gameplay-replay-implementation.md). ``GameEngine.__init__`` calls
``reset_sources()`` so each run starts with fresh doors.

This module is a leaf (see the layering rule in plans/2026-10-19-gameplay-replay-core.md, Task
2): any module may import it, and it imports no package module at module level except
glitchygames.randomness.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Protocol

from glitchygames.randomness import engine_random_seed

if TYPE_CHECKING:
    import pygame

    from glitchygames.scenes import Scene


class SourcesAlreadyRunningError(RuntimeError):
    """install_sources() was called after the first frame started."""


class EngineSources(Protocol):
    """The doors (see the module docstring)."""

    random_seed: int

    @property
    def stop_requested(self) -> bool:
        """True when the sources want the run to end (a replay reached its end)."""
        ...

    def on_installed(self) -> None:
        """Called by install_sources() when these sources become the run's doors."""
        ...

    def on_uninstalled(self) -> None:
        """Called by reset_sources() when these sources stop being the run's doors."""
        ...

    def pump_events(self) -> list[pygame.event.Event]:
        """Return the next batch of events (the only read of the event queue)."""
        ...

    def frame_seconds(self, *, measured: float) -> float:
        """Return the frame time logic receives, given the measured start-to-start time."""
        ...

    def end_frame(self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        """Called once after each frame (recording writes it, replay compares it)."""
        ...


@dataclasses.dataclass
class _SourcesRegistry:
    installed: EngineSources | None = None
    scoped: list[EngineSources] = dataclasses.field(default_factory=list)
    frames_started: bool = False
    frame_clock_seconds: float = 0.0


_REGISTRY = _SourcesRegistry()


def active_sources() -> EngineSources:
    """Return the doors in use: scoped sources, else installed ones, else fresh live ones.

    Returns:
        The active sources.

    """
    if _REGISTRY.scoped:
        return _REGISTRY.scoped[-1]
    if _REGISTRY.installed is None:
        # The one function-level import of the door modules: live_sources imports the input,
        # devices and saves modules, which import this module, so importing it at the top would
        # make a cycle. It runs only when nothing was installed (unit tests, tools).
        from glitchygames.live_sources import LiveSources

        _REGISTRY.installed = LiveSources(random_seed=engine_random_seed())
    return _REGISTRY.installed


def install_sources(*, sources: EngineSources) -> None:
    """Make ``sources`` the run's doors; allowed only before the first frame.

    Raises:
        SourcesAlreadyRunningError: If a frame has already started.

    """
    if _REGISTRY.frames_started:
        message = 'install_sources() is allowed only before the first frame'
        raise SourcesAlreadyRunningError(message)
    if _REGISTRY.installed is not None and _REGISTRY.installed is not sources:
        _REGISTRY.installed.on_uninstalled()
    _REGISTRY.installed = sources
    sources.on_installed()


def mark_frames_started() -> None:
    """Record that the frame loop has started (install_sources is refused from now on)."""
    _REGISTRY.frames_started = True


def advance_frame_clock(*, seconds: float) -> None:
    """Add one closed frame's dt to the frame clock (SceneManager._finish_frame)."""
    _REGISTRY.frame_clock_seconds += seconds


def frame_clock_seconds() -> float:
    """Return the sum of every closed frame's dt this run.

    It replays exactly (dt comes through the frame-time door) and never pauses. Read it through
    glitchygames/clock.py (Task 8), which re-exports it.

    Returns:
        Seconds.

    """
    return _REGISTRY.frame_clock_seconds


def reset_sources() -> None:
    """Forget every installed and scoped source and the frame clock (a new run, or a test)."""
    for sources in [*_REGISTRY.scoped, _REGISTRY.installed]:
        if sources is not None:
            sources.on_uninstalled()
    _REGISTRY.installed = None
    _REGISTRY.scoped.clear()
    _REGISTRY.frames_started = False
    _REGISTRY.frame_clock_seconds = 0.0
```

`glitchygames/live_sources.py`:

```python
"""The live doors: pygame's queue, the measured frame time, and (from later tasks) pygame's
polled input, real devices, files on disk and the real clocks (glitchygames/sources.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pygame

if TYPE_CHECKING:
    from glitchygames.scenes import Scene


class LiveSources:
    """The live doors (implements glitchygames.sources.EngineSources)."""

    def __init__(self: Self, *, random_seed: int, use_fastevents: bool = False) -> None:
        """Create the live doors.

        Args:
            random_seed: The run's master seed (glitchygames/randomness.py).
            use_fastevents: Read events with pygame.fastevent when pygame has it
                (``GameEngine.USE_FASTEVENTS``; pygame < 2.2 only).

        """
        self.random_seed = random_seed
        self._use_fastevents = use_fastevents

    @property
    def stop_requested(self: Self) -> bool:
        """Live play never asks to stop."""
        return False

    def on_installed(self: Self) -> None:
        """Nothing to start for live play."""

    def on_uninstalled(self: Self) -> None:
        """Nothing to stop for live play."""

    def pump_events(self: Self) -> list[pygame.event.Event]:
        """Take every event from SDL's queue.

        Returns:
            The batch, in queue order.

        """
        # To use events in a different thread, use the fastevent package from pygame.
        # if you're using pygame < 2.2, you'll need to use pygame.fastevent.
        fastevent = getattr(pygame, 'fastevent', None)
        if self._use_fastevents and fastevent is not None:
            return list(fastevent.get())
        return list(pygame.event.get())

    def frame_seconds(self: Self, *, measured: float) -> float:
        """Live logic receives the measured frame time.

        Returns:
            ``measured``, unchanged.

        """
        return measured

    def end_frame(self: Self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        """Nothing to do after a live frame."""
```

In `GameEngine.__init__`, after `self.random_seed = seed_engine_random(...)` and after the
`USE_FASTEVENTS` decision (`:598-602`, which sets `GameEngine.USE_FASTEVENTS` — move the doors
block below it if it is not already below; read the order first):

```python
        # Fresh doors for this run (glitchygames/sources.py). Task 12 makes this install the
        # replay's sources instead when --replay-trace is given
        reset_sources()
        install_sources(sources=LiveSources(random_seed=self.random_seed,
                                            use_fastevents=GameEngine.USE_FASTEVENTS))
```

and add:

```python
    def install_sources(self: Self, *, sources: EngineSources) -> None:
        """Make ``sources`` this run's doors (before the first frame; see glitchygames/sources.py)."""
        install_sources(sources=sources)
```

Replace the body of `GameEngine._pump_events` (keep its docstring, updated: "Take the next batch
from the active sources' event pump: the one place the engine reads events"):

```python
        raw_events = active_sources().pump_events()
        # The only per-frame cost of recording when it is off: this check
        if self.trace_recorder is not None:
            self.trace_recorder.record_event_batch(raw_events=raw_events)
        return raw_events
```

(Task 11 moves the recorder into `RecordingSources`; until then this check stays.) The
fastevent comment block moves into `LiveSources.pump_events` (shown above).

In `SceneManager.__init__` add `self.frame_number: int = 0` (comment: "Frames finished this run;
the doors' end_frame receives each frame's number"). In `SceneManager.start`, before the loop:

```python
        frame_start_seconds: float = time.perf_counter()
        self._previous_fps_event_seconds = frame_start_seconds
        # The first frame has no previous frame: its dt is the short time since the reading
        # above, as before (a replay's frame-time door returns the recorded first dt)
        self.dt = active_sources().frame_seconds(
            measured=time.perf_counter() - frame_start_seconds
        )
        mark_frames_started()
```

and extend the loop condition: `while self.active_scene is not None and self.quit_requested is
False and not active_sources().stop_requested:`. In `_finish_frame` replace
`self.dt = closing_reading_seconds - frame_start_seconds` with:

```python
        self.dt = active_sources().frame_seconds(
            measured=closing_reading_seconds - frame_start_seconds
        )
```

and update its docstring ("set ``self.dt`` to the start-to-start period as the frame-time door
returns it: the measurement when live, the recorded dt in a replay"). In `_run_frame`, after the
recorder call:

```python
        active_sources().end_frame(frame_number=self.frame_number, dt=frame_dt,
                                   scene=self.active_scene)
        self.frame_number += 1
```

`GoldenTraceSceneManager.run_frame` calls `_run_frame`, so the harness needs no change; the harness
never calls `start()` or `_finish_frame`, so it never calls `mark_frames_started()` or advances
the frame clock (Task 4) — tests that need either call them.

- [ ] **Step 4: Run the new tests, then the frame tests and the golden test**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/engine/test_engine_sources.py tests/world tests/scenes tests/engine -q -p no:cacheprovider --no-cov`
Expected: PASS (golden unchanged).

- [ ] **Step 5: Lint, type-check, full suite, commit**

```bash
git add glitchygames/sources.py glitchygames/live_sources.py glitchygames/engine/game_engine.py glitchygames/scenes/scene.py tests/conftest.py tests/engine/test_engine_sources.py
git commit -m "Add the engine's doors: events and frame time through swappable sources"
```

---

### Task 3: Input snapshots

**Files:**
- Create: `glitchygames/input/state.py`
- Modify: `glitchygames/sources.py` (Protocol `input_snapshot`; `InputSnapshot` imported under
  `TYPE_CHECKING` only), `glitchygames/live_sources.py` (`LiveSources.input_snapshot`)
- Modify: `tests/conftest.py` (the Task 2 fixture also calls `reset_current_input()`)
- Modify: `glitchygames/engine/game_engine.py:1327-1378` (`process_events`: capture after the
  pump), new property `input`
- Test: `tests/input/test_input_state.py` (new)

**Interfaces:**
- Consumes: `active_sources()` (Task 2).
- Produces: `InputSnapshot`, `IDLE_INPUT`, `SCANCODE_COUNT = 512`,
  `capture_live_snapshot(*, device_axes=..., device_buttons=..., device_hats=...) -> InputSnapshot`,
  `current_input() -> InputSnapshot`, `set_current_input(*, snapshot: InputSnapshot) -> None`,
  `snapshot_changes(*, previous, current) -> dict[str, Any]`,
  `apply_snapshot_changes(*, previous, changes) -> InputSnapshot`;
  `EngineSources.input_snapshot(self) -> InputSnapshot`; `GameEngine.input -> InputSnapshot`.

- [ ] **Step 1: Write the failing tests** (`tests/input/test_input_state.py`)

```python
"""Polled input as one immutable snapshot per frame (glitchygames/input/state.py)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.input.state import (
    IDLE_INPUT,
    SCANCODE_COUNT,
    InputSnapshot,
    apply_snapshot_changes,
    current_input,
    set_current_input,
    snapshot_changes,
)

LEFT_ARROW_SCANCODE = 80  # SDL_SCANCODE_LEFT; pygame.K_LEFT maps to it


@pytest.fixture(autouse=True)
def initialized_pygame():
    """Key-code lookups (ScancodeWrapper[K_LEFT]) need SDL initialized: before pygame.init()
    every lookup is False. A running engine always has it; these unit tests make sure."""
    if not pygame.get_init():
        pygame.init()


def snapshot_with(**fields) -> InputSnapshot:
    values = {
        'pressed_scancodes': frozenset(), 'modifiers': 0, 'mouse_position': (0, 0),
        'mouse_buttons': (False, False, False), 'mouse_focused': True,
        'device_axes': {}, 'device_buttons': {}, 'device_hats': {},
    }
    values.update(fields)
    return InputSnapshot(**values)


class TestQueries:
    def test_key_pressed_maps_key_codes_to_scancodes(self):
        snapshot = snapshot_with(pressed_scancodes=frozenset({LEFT_ARROW_SCANCODE}))
        assert snapshot.key_pressed(pygame.K_LEFT)
        assert not snapshot.key_pressed(pygame.K_RIGHT)

    def test_pressed_keys_is_a_drop_in_for_get_pressed(self):
        snapshot = snapshot_with(pressed_scancodes=frozenset({LEFT_ARROW_SCANCODE}))
        pressed = snapshot.pressed_keys
        assert isinstance(pressed, pygame.key.ScancodeWrapper)
        assert len(pressed) == SCANCODE_COUNT
        assert pressed[pygame.K_LEFT]

    def test_device_queries_default_to_rest(self):
        snapshot = snapshot_with(device_axes={7: (0.5, -1.0)}, device_hats={7: ((1, 0),)},
                                 device_buttons={7: (True,)})
        assert snapshot.axis(device_id=7, axis=1) == -1.0
        assert snapshot.hat(device_id=7, hat=0) == (1, 0)
        assert snapshot.button(device_id=7, button=0)
        assert snapshot.axis(device_id=9, axis=0) == 0.0
        assert snapshot.button(device_id=7, button=5) is False
        assert snapshot.hat(device_id=7, hat=3) == (0, 0)


class TestCurrentInput:
    def test_idle_until_set(self):
        assert current_input() == IDLE_INPUT

    def test_set_current_input(self):
        snapshot = snapshot_with(modifiers=pygame.KMOD_LSHIFT)
        set_current_input(snapshot=snapshot)
        assert current_input() is snapshot


class TestChanges:
    def test_no_changes_is_an_empty_dict(self):
        assert snapshot_changes(previous=IDLE_INPUT, current=IDLE_INPUT) == {}

    @pytest.mark.parametrize('current', [
        snapshot_with(pressed_scancodes=frozenset({LEFT_ARROW_SCANCODE, 4})),
        snapshot_with(modifiers=pygame.KMOD_CTRL, mouse_position=(10, 20)),
        snapshot_with(mouse_buttons=(True, False, True), mouse_focused=False),
        snapshot_with(device_axes={3: (0.25,)}, device_buttons={3: (False, True)},
                      device_hats={3: ((0, -1),)}),
    ])
    def test_changes_round_trip_through_json(self, current):
        import json

        changes = json.loads(json.dumps(snapshot_changes(previous=IDLE_INPUT, current=current)))
        assert apply_snapshot_changes(previous=IDLE_INPUT, changes=changes) == current

    def test_a_removed_device_is_recorded_and_removed(self):
        previous = snapshot_with(device_axes={3: (0.25,)})
        changes = snapshot_changes(previous=previous, current=IDLE_INPUT)
        assert apply_snapshot_changes(previous=previous, changes=changes) == IDLE_INPUT
```

Add a frame-level test to `tests/world/test_frame_integration.py` (it already has `running_scene`
and `step`):

```python
class TestInputSnapshotInTheFrame:
    """The snapshot is taken once per frame, right after the pump, and stays fixed."""

    def test_snapshot_taken_after_the_pump_is_the_frames_input(self, mocker):
        from glitchygames import live_sources as live_sources_module

        captures: list[int] = []
        original_capture = live_sources_module.capture_live_snapshot

        def counting_capture(**keywords):
            captures.append(1)
            return original_capture(**keywords)

        # LiveSources calls the name it imported into glitchygames/live_sources.py
        mocker.patch.object(live_sources_module, 'capture_live_snapshot', counting_capture)
        with running_scene(CameraFreeScene) as manager:
            step(manager, frames=3)
        assert len(captures) == 3
```

- [ ] **Step 2: Run to see them fail**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/input/test_input_state.py tests/world/test_frame_integration.py -k "Input or Queries or Changes or Current" -q -p no:cacheprovider --no-cov`
Expected: FAIL (`ModuleNotFoundError: glitchygames.input.state`).

- [ ] **Step 3: Implement `glitchygames/input/state.py`**

```python
"""Polled input as one immutable snapshot per frame: the polled-input door.

Once per frame, right after the frame's first pump (``GameEngine.process_events``), the engine
asks the active sources (glitchygames/sources.py) for an ``InputSnapshot`` and makes it
the frame's ``current_input()``. Live sources read pygame (``capture_live_snapshot``); a replay
hands back the recorded snapshot. Code reads held keys, modifiers, the mouse and device positions
from the snapshot, never from pygame: ``tests/test_engine_doors.py`` rejects direct polling.

Recordings store only what changed from the previous frame (``snapshot_changes``), so idle
frames add nothing; ``apply_snapshot_changes`` rebuilds the snapshot.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import pygame

if TYPE_CHECKING:
    from collections.abc import Mapping

# Length of pygame.key.get_pressed(): one entry per SDL scancode
SCANCODE_COUNT = 512
MOUSE_BUTTON_COUNT = 3

_EMPTY: Mapping[int, Any] = MappingProxyType({})


@dataclasses.dataclass(frozen=True)
class InputSnapshot:
    """The polled input of one frame.

    Attributes:
        pressed_scancodes: SDL scancodes held this frame.
        modifiers: pygame KMOD bits.
        mouse_position: The mouse position in window pixels.
        mouse_buttons: (left, middle, right) held.
        mouse_focused: Whether the window has mouse focus.
        device_axes: Joystick/controller instance id -> axis positions (-1.0..1.0).
        device_buttons: Instance id -> buttons held.
        device_hats: Instance id -> hat positions.

    """

    pressed_scancodes: frozenset[int]
    modifiers: int
    mouse_position: tuple[int, int]
    mouse_buttons: tuple[bool, bool, bool]
    mouse_focused: bool
    device_axes: Mapping[int, tuple[float, ...]] = _EMPTY
    device_buttons: Mapping[int, tuple[bool, ...]] = _EMPTY
    device_hats: Mapping[int, tuple[tuple[int, int], ...]] = _EMPTY

    def __post_init__(self) -> None:
        """Freeze the device mappings (a snapshot never changes)."""
        for field_name in ('device_axes', 'device_buttons', 'device_hats'):
            object.__setattr__(
                self, field_name, MappingProxyType(dict(getattr(self, field_name)))
            )

    def __eq__(self, other: object) -> bool:
        """Compare field by field (the mapping proxies compare by content)."""
        if not isinstance(other, InputSnapshot):
            return NotImplemented
        return (
            self.pressed_scancodes == other.pressed_scancodes
            and self.modifiers == other.modifiers
            and self.mouse_position == other.mouse_position
            and self.mouse_buttons == other.mouse_buttons
            and self.mouse_focused == other.mouse_focused
            and dict(self.device_axes) == dict(other.device_axes)
            and dict(self.device_buttons) == dict(other.device_buttons)
            and dict(self.device_hats) == dict(other.device_hats)
        )

    def __hash__(self) -> int:
        """Hash the key and mouse state (device mappings are not hashable)."""
        return hash((self.pressed_scancodes, self.modifiers, self.mouse_position))

    @property
    def pressed_keys(self) -> pygame.key.ScancodeWrapper:
        """The held keys indexable by key code, exactly like ``pygame.key.get_pressed()``."""
        return pygame.key.ScancodeWrapper(
            tuple(scancode in self.pressed_scancodes for scancode in range(SCANCODE_COUNT))
        )

    def key_pressed(self, key: int) -> bool:
        """Return whether ``key`` (a pygame.K_* code) is held this frame.

        The key-code-to-scancode lookup needs SDL initialized (pygame.init()), which a running
        engine always has; before it, every lookup is False. ``key`` stays positional: this is a
        drop-in for ``pygame.key.get_pressed()[key]``.
        """
        return bool(self.pressed_keys[key])

    def axis(self, *, device_id: int, axis: int) -> float:
        """Return an axis position; 0.0 for an unknown device or axis."""
        axes = self.device_axes.get(device_id, ())
        return axes[axis] if 0 <= axis < len(axes) else 0.0

    def button(self, *, device_id: int, button: int) -> bool:
        """Return whether a device button is held; False when unknown."""
        buttons = self.device_buttons.get(device_id, ())
        return buttons[button] if 0 <= button < len(buttons) else False

    def hat(self, *, device_id: int, hat: int) -> tuple[int, int]:
        """Return a hat position; (0, 0) when unknown."""
        hats = self.device_hats.get(device_id, ())
        return hats[hat] if 0 <= hat < len(hats) else (0, 0)


IDLE_INPUT = InputSnapshot(
    pressed_scancodes=frozenset(),
    modifiers=0,
    mouse_position=(0, 0),
    mouse_buttons=(False, False, False),
    mouse_focused=False,
)

_CURRENT: list[InputSnapshot] = [IDLE_INPUT]


def capture_live_snapshot(
    *,
    device_axes: Mapping[int, tuple[float, ...]] = _EMPTY,
    device_buttons: Mapping[int, tuple[bool, ...]] = _EMPTY,
    device_hats: Mapping[int, tuple[tuple[int, int], ...]] = _EMPTY,
) -> InputSnapshot:
    """Read pygame's polled state now (the live door; the only polling in the package).

    Args:
        device_axes: Device positions read by the live device registry (Task 5).
        device_buttons: Device buttons read by the live device registry.
        device_hats: Device hats read by the live device registry.

    Returns:
        The snapshot.

    """
    pressed = pygame.key.get_pressed()
    mouse_x, mouse_y = pygame.mouse.get_pos()
    left, middle, right = pygame.mouse.get_pressed(num_buttons=MOUSE_BUTTON_COUNT)
    return InputSnapshot(
        pressed_scancodes=frozenset(scancode for scancode, held in enumerate(pressed) if held),
        modifiers=int(pygame.key.get_mods()),
        mouse_position=(int(mouse_x), int(mouse_y)),
        mouse_buttons=(bool(left), bool(middle), bool(right)),
        mouse_focused=bool(pygame.mouse.get_focused()),
        device_axes=device_axes,
        device_buttons=device_buttons,
        device_hats=device_hats,
    )


def current_input() -> InputSnapshot:
    """Return this frame's snapshot (IDLE_INPUT before the first pump)."""
    return _CURRENT[0]


def set_current_input(*, snapshot: InputSnapshot) -> None:
    """Make ``snapshot`` this frame's input (GameEngine.process_events, once per frame)."""
    _CURRENT[0] = snapshot


def reset_current_input() -> None:
    """Back to IDLE_INPUT (a new run, or a test)."""
    _CURRENT[0] = IDLE_INPUT


def _device_mapping_changes(
    previous: Mapping[int, tuple[Any, ...]], current: Mapping[int, tuple[Any, ...]]
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for device_id in sorted(set(previous) | set(current)):
        if device_id not in current:
            changes[str(device_id)] = None
        elif previous.get(device_id) != current[device_id]:
            changes[str(device_id)] = [
                list(value) if isinstance(value, tuple) else value for value in current[device_id]
            ]
    return changes


def snapshot_changes(*, previous: InputSnapshot, current: InputSnapshot) -> dict[str, Any]:
    """Return the JSON-safe fields of ``current`` that differ from ``previous``.

    Returns:
        A dict of changed fields; device fields hold only changed devices (None = removed).

    """
    changes: dict[str, Any] = {}
    if current.pressed_scancodes != previous.pressed_scancodes:
        changes['pressed_scancodes'] = sorted(current.pressed_scancodes)
    if current.modifiers != previous.modifiers:
        changes['modifiers'] = current.modifiers
    if current.mouse_position != previous.mouse_position:
        changes['mouse_position'] = list(current.mouse_position)
    if current.mouse_buttons != previous.mouse_buttons:
        changes['mouse_buttons'] = list(current.mouse_buttons)
    if current.mouse_focused != previous.mouse_focused:
        changes['mouse_focused'] = current.mouse_focused
    for field_name in ('device_axes', 'device_buttons', 'device_hats'):
        device_changes = _device_mapping_changes(
            getattr(previous, field_name), getattr(current, field_name)
        )
        if device_changes:
            changes[field_name] = device_changes
    return changes


def _apply_device_changes(
    previous: Mapping[int, tuple[Any, ...]], changes: dict[str, Any], *, is_hat: bool
) -> dict[int, tuple[Any, ...]]:
    devices = dict(previous)
    for device_text, values in changes.items():
        device_id = int(device_text)
        if values is None:
            devices.pop(device_id, None)
        elif is_hat:
            devices[device_id] = tuple((int(value[0]), int(value[1])) for value in values)
        else:
            devices[device_id] = tuple(values)
    return devices


def apply_snapshot_changes(*, previous: InputSnapshot, changes: dict[str, Any]) -> InputSnapshot:
    """Rebuild a snapshot from the previous one and recorded changes.

    Returns:
        The new snapshot.

    """
    mouse_buttons = changes.get('mouse_buttons', previous.mouse_buttons)
    mouse_position = changes.get('mouse_position', previous.mouse_position)
    return InputSnapshot(
        pressed_scancodes=frozenset(changes.get('pressed_scancodes', previous.pressed_scancodes)),
        modifiers=int(changes.get('modifiers', previous.modifiers)),
        mouse_position=(int(mouse_position[0]), int(mouse_position[1])),
        mouse_buttons=(bool(mouse_buttons[0]), bool(mouse_buttons[1]), bool(mouse_buttons[2])),
        mouse_focused=bool(changes.get('mouse_focused', previous.mouse_focused)),
        device_axes=_apply_device_changes(
            previous.device_axes, changes.get('device_axes', {}), is_hat=False
        ),
        device_buttons=_apply_device_changes(
            previous.device_buttons, changes.get('device_buttons', {}), is_hat=False
        ),
        device_hats=_apply_device_changes(
            previous.device_hats, changes.get('device_hats', {}), is_hat=True
        ),
    )
```

Add to `EngineSources`: `def input_snapshot(self) -> InputSnapshot: ...` ("this frame's polled
input, asked once per frame right after the frame's first pump"). `LiveSources.input_snapshot`
returns `capture_live_snapshot()` (Task 5 passes the device positions). `sources.py` must not
import `glitchygames.input` (its package `__init__` imports `input.rumble`, which imports
`glitchygames.sources` from Task 6 on — a cycle), so `reset_sources()` does not reset the input:
`GameEngine.__init__` calls `reset_current_input()` right after `reset_sources()`, and the
`reset_engine_sources` fixture in `tests/conftest.py` calls it too.

In `GameEngine.process_events`, right after `raw_events = self._pump_events()`:

```python
        # Polled input is read once per frame, right after the pump, so it agrees with this
        # frame's events and never changes during the frame (glitchygames/input/state.py)
        set_current_input(snapshot=active_sources().input_snapshot())
```

and add the property:

```python
    @property
    def input(self: Self) -> InputSnapshot:
        """This frame's polled input (glitchygames/input/state.py ``current_input``)."""
        return current_input()
```

- [ ] **Step 4: Run the tests, frame tests and golden test, and check the per-frame cost**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/input tests/world tests/engine -q -p no:cacheprovider --no-cov`
Expected: PASS.

The snapshot is the one per-frame cost this part adds to live play (spec 6: no measurable change).
Run `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest --benchmark-only -q -p no:cacheprovider`
on this commit and on the commit before Task 2, and put both results in the report; also time
`capture_live_snapshot()` alone (`uv run python -m timeit -s "..."` after a dummy display is set up)
— it should be a few microseconds. If it is not, cache `pressed_keys` (build the
`ScancodeWrapper` lazily, once per snapshot) before moving on.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/input/state.py glitchygames/sources.py glitchygames/live_sources.py glitchygames/engine/game_engine.py tests/conftest.py tests/input/test_input_state.py tests/world/test_frame_integration.py
git commit -m "Add the polled-input door: one InputSnapshot per frame, taken after the pump"
```

---

### Task 4: Game time and the frame clock

**Files:**
- Modify: `glitchygames/scenes/scene.py` — `Scene.__init__` (`_game_time_seconds`), new property
  `Scene.game_time`; `SceneManager._update_scene` (`:1181-1189`); `SceneManager._finish_frame`
  (`advance_frame_clock` right after `self.dt` is set); `SceneManager.start` and `_finish_frame`
  (FPS event timing from the
  frame clock)
- Test: `tests/world/test_finish_frame.py`, `tests/world/test_frame_integration.py`

**Interfaces:**
- Consumes: `advance_frame_clock`, `frame_clock_seconds` (Task 2).
- Produces: `Scene.game_time -> float` (logic seconds since the scene started; capped dt where
  `MAX_FRAME_SECONDS` is set; does not advance while the scene gets no `dt_tick`).

- [ ] **Step 1: Write the failing tests**

In `tests/world/test_frame_integration.py`:

```python
class GameTimeScene(CameraFreeScene):
    """Overrides dt_tick without calling super: game time is the engine's, not the scene's."""

    MAX_FRAME_SECONDS = 0.05

    def dt_tick(self, dt: float) -> None:
        self.last_dt = dt


class TestGameTime:
    def test_game_time_sums_the_scene_dt_even_without_super(self):
        with running_scene(GameTimeScene) as manager:
            step(manager, frames=4)
            assert manager.active_scene.game_time == pytest.approx(4 * FRAME_SECONDS)

    def test_game_time_uses_the_capped_dt(self):
        with running_scene(GameTimeScene) as manager:
            manager.dt = 2.0
            manager.run_frame()
            assert manager.active_scene.game_time == 0.05

    def test_game_time_stops_while_paused(self):
        with running_scene(StillCameraScene) as manager:
            step(manager, frames=2)
            game_scene = manager.active_scene
            paused_at = game_scene.game_time
            step(manager, press(pygame.K_ESCAPE), release(pygame.K_ESCAPE), frames=PAUSE_FRAMES)
            assert manager.active_scene is not game_scene  # the pause scene runs
            assert game_scene.game_time == paused_at
```

(`StillCameraScene` must pause on ESC for the last test — read `TestResumeAfterPause` in the same
file and reuse the scene it uses for pausing instead if `StillCameraScene` does not pause.)

In `tests/world/test_finish_frame.py`, inside `TestOneFrameTime` (next to
`test_fps_event_reports_the_frame_just_closed`, whose driver and constants it reuses):

```python
    def test_fps_events_follow_the_frame_clock(self, driver_factory, mocker):
        """FPS events are timed from the sum of frame times (the frame clock), not the wall
        clock: with the frame clock frozen, none is posted even though a second of wall time
        passes."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        mocker.patch('glitchygames.scenes.scene.frame_clock_seconds', return_value=0.0)

        driver.run(frame_count=round(EXACT_TARGET_FPS))

        assert driver.post_event.call_args_list == []
```

`test_fps_event_reports_the_frame_just_closed` (two events in one second) keeps passing unchanged:
its frame times sum exactly to the fake wall time, so the frame clock crosses the interval on the
same frames.

- [ ] **Step 2: Run to see them fail**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/world/test_frame_integration.py tests/world/test_finish_frame.py -k "GameTime or frame_clock" -q -p no:cacheprovider --no-cov`
Expected: FAIL (`'GameTimeScene' object has no attribute 'game_time'`).

- [ ] **Step 3: Implement**

`Scene.__init__`: `self._game_time_seconds: float = 0.0` (comment: "Logic seconds since this
scene started (game_time); the scene manager adds each frame's scene dt before dt_tick").

```python
    @property
    def game_time(self: Self) -> float:
        """Logic seconds since this scene started: the sum of the dt its dt_tick received.

        Capped by MAX_FRAME_SECONDS where set, and it does not advance while the scene is not
        running (paused, or switched away), so cooldowns and timers measured with it pause with
        the game and replay exactly. Use it for gameplay timing instead of the wall clock.
        """
        return self._game_time_seconds
```

`SceneManager._update_scene`:

```python
        assert self.active_scene is not None
        # Engine-owned, so a dt_tick override that skips super() still has game time
        if hasattr(self.active_scene, '_game_time_seconds'):
            self.active_scene._game_time_seconds += scene_dt
        self.active_scene.dt_tick(scene_dt)
```

(`_game_time_seconds` is accessed from `SceneManager` in the same module; basedpyright's
`reportPrivateUsage` does not fire inside the defining module — run basedpyright; if it does
fire, add a one-line `Scene._advance_game_time(self, *, seconds: float) -> None` method instead
and call that.)

`SceneManager._finish_frame`, right after `self.dt` is set from the frame-time door (so FPS events
and blinks see the frame just closed, with no one-frame offset):

```python
        # The frame clock (glitchygames/sources.py) is the sum of closed frames' dt: UI timing and
        # FPS events use it, so they replay exactly
        advance_frame_clock(seconds=self.dt)
```

The golden harness steps frames with `run_frame()` and never calls `_finish_frame`, so its frame
clock stays at 0 — harness runs (golden traces, harness recordings and harness replays) never
depend on it, and that is consistent between a harness recording and a harness replay.

`SceneManager.start`: `self._previous_fps_event_seconds = frame_clock_seconds()`.
`_finish_frame`: replace the FPS check with

```python
        frame_clock = frame_clock_seconds()
        if self._should_post_fps_event(frame_clock, self._previous_fps_event_seconds):
            self._post_fps_event()
            self._previous_fps_event_seconds = frame_clock
```

and update the docstring sentence "post the FPS event when its wall-clock interval has passed" to
"when its interval of frame-clock time has passed (the frame clock replays exactly)".

- [ ] **Step 4: Run the new tests, `tests/world`, `tests/scenes` and the golden test**

Expected: PASS, golden unchanged (the harness never posts FPS events or advances the frame
clock). Add, in `tests/world/test_finish_frame.py`'s `TestOneFrameTime`:

```python
    def test_frame_clock_includes_the_frame_just_closed(self, driver_factory):
        from glitchygames.sources import frame_clock_seconds

        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        driver.run(frame_count=FRAMES_TO_RUN)
        closing_samples = _closing_samples(driver)
        assert frame_clock_seconds() == pytest.approx(sum(closing_samples))
```

(`_closing_samples` is the file's helper returning each frame's closing dt.)

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/scenes/scene.py tests/world/test_frame_integration.py tests/world/test_finish_frame.py
git commit -m "Add Scene.game_time and time FPS events from the replayable frame clock"
```

---

### Task 5: The devices door

**Files:**
- Create: `glitchygames/input/devices.py` (imports `pygame`, `pygame._sdl2.controller` and
  `glitchygames.input.state` only)
- Modify: `glitchygames/sources.py` (`EngineSources.devices`), `glitchygames/live_sources.py`
  (`LiveSources.devices`, device positions in the snapshot)
- Modify: `glitchygames/recording.py` (`DEVICE_ENUMERATION_FIELD`)
- Test: `tests/input/test_devices.py` (new)

**Interfaces:**
- Consumes: `capture_live_snapshot` (Task 3).
- Produces:

```python
@dataclasses.dataclass(frozen=True)
class DeviceDescriptor:
    kind: str            # JOYSTICK_KIND | CONTROLLER_KIND
    device_index: int
    instance_id: int
    name: str
    guid: str | None
    axis_count: int
    button_count: int
    hat_count: int
    ball_count: int
    def to_json(self) -> dict[str, Any]: ...
    @classmethod
    def from_json(cls, record: dict[str, Any]) -> DeviceDescriptor: ...
@dataclasses.dataclass(frozen=True)
class EnumerationAnswer:   # one answered enumeration call, recorded so a replay answers the same
    call: str              # 'joystick_count' | 'controller_count' | 'is_controller' | 'name_for_index'
    device_index: int | None
    value: int | bool | str | None
    def to_json(self) -> dict[str, Any]: ...
    @classmethod
    def from_json(cls, record: dict[str, Any]) -> EnumerationAnswer: ...
class DeviceRegistry(Protocol):
    def joystick_count(self) -> int: ...
    def controller_count(self) -> int: ...
    def is_controller(self, *, device_index: int) -> bool: ...
    def name_for_index(self, *, device_index: int) -> str | None: ...
    def open_joystick(self, *, device_index: int) -> Any: ...
    def open_controller(self, *, device_index: int) -> Any: ...
    def joystick_for_instance(self, *, instance_id: int) -> Any | None: ...
    def take_opened_descriptors(self) -> list[DeviceDescriptor]: ...
    def take_enumeration_answers(self) -> list[EnumerationAnswer]: ...
class LiveDeviceRegistry: ...          # opens and enumerates real devices; polls opened ones
class ReplayDeviceRegistry: ...        # stand-ins and recorded answers (Task 12 builds it)
class ReplayJoystick / ReplayController  # read positions from current_input(); rumble no-op
EngineSources.devices(self) -> DeviceRegistry
DEVICE_ENUMERATION_FIELD = 'device_enumeration'   # recording.py: header and per-frame field
```

Rules:
- Enumeration is part of the door (spec 1.3): live answers come from pygame and are remembered
  as `EnumerationAnswer`s (taken by the recorder: answers given before recording started go in the
  header, later ones in the frame they were asked in); a replay answers each call from the
  recorded answers for that call and device index, in order, and after the last recorded answer
  for a key repeats it (a device count asked every frame stays constant). A key never recorded is
  answered from the stand-in descriptors (counts) or `None`/`False`, with one warning per key.
- Live play reads device positions from the frame's snapshot too (spec 1: one snapshot per frame,
  unchanged during the frame): `LiveSources.input_snapshot()` polls every opened device once, at
  the pump; Task 6 moves every mid-frame `get_axis/get_button/get_hat` read to
  `current_input()`. Live and replay then read the same thing.
- The stand-ins are drop-ins for pygame's `Joystick` / `Controller`: their methods keep pygame's
  positional signatures (`get_axis(axis)`, `rumble(low_frequency, high_frequency, duration)`),
  documented as interface conformance in each docstring. Every new engine-owned function or
  method (the registry's) is keyword-only.

- [ ] **Step 1: Write the failing tests** (`tests/input/test_devices.py`)

```python
"""The devices door (glitchygames/input/devices.py)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.input.devices import (
    DeviceDescriptor,
    EnumerationAnswer,
    LiveDeviceRegistry,
    ReplayController,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.input.state import InputSnapshot, set_current_input

PAD = DeviceDescriptor(kind='joystick', device_index=0, instance_id=7, name='Test Pad',
                       guid='abc', axis_count=2, button_count=3, hat_count=1, ball_count=0)


@pytest.fixture(autouse=True)
def initialized_pygame():
    """Key and device lookups need SDL initialized (always true in a running engine)."""
    if not pygame.get_init():
        pygame.init()


def test_descriptor_round_trips_through_json():
    assert DeviceDescriptor.from_json(PAD.to_json()) == PAD


def test_replay_joystick_answers_from_the_descriptor_and_the_snapshot():
    set_current_input(snapshot=InputSnapshot(
        pressed_scancodes=frozenset(), modifiers=0, mouse_position=(0, 0),
        mouse_buttons=(False, False, False), mouse_focused=True,
        device_axes={7: (0.5, -0.25)}, device_buttons={7: (False, True, False)},
        device_hats={7: ((0, 1),)},
    ))
    joystick = ReplayJoystick(descriptor=PAD)
    joystick.init()
    assert joystick.get_name() == 'Test Pad'
    assert joystick.get_instance_id() == 7
    assert joystick.get_numaxes() == 2
    assert joystick.get_axis(1) == -0.25
    assert joystick.get_button(1) is True
    assert joystick.get_hat(0) == (0, 1)
    assert joystick.rumble(0.5, 0.5, 100) is True  # accepted and dropped


def test_replay_registry_never_opens_real_hardware(mocker):
    real_joystick = mocker.patch('pygame.joystick.Joystick')
    real_controller = mocker.patch('pygame._sdl2.controller.Controller')
    real_count = mocker.patch('pygame.joystick.get_count', return_value=5)
    registry = ReplayDeviceRegistry(descriptors=[PAD], enumeration_answers=[])
    joystick = registry.open_joystick(device_index=0)
    controller = registry.open_controller(device_index=0)
    assert isinstance(joystick, ReplayJoystick)
    assert isinstance(controller, ReplayController)
    assert registry.joystick_count() == 1          # the recording's device, not the 5 plugged in
    assert registry.joystick_for_instance(instance_id=7) is controller
    real_joystick.assert_not_called()
    real_controller.assert_not_called()
    real_count.assert_not_called()


def test_replay_enumeration_answers_in_recorded_order_then_repeats_the_last():
    registry = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[
        EnumerationAnswer(call='controller_count', device_index=None, value=1),
        EnumerationAnswer(call='controller_count', device_index=None, value=2),
        EnumerationAnswer(call='is_controller', device_index=1, value=True),
    ])
    assert [registry.controller_count() for _ in range(3)] == [1, 2, 2]
    assert registry.is_controller(device_index=1) is True


def test_replay_registry_unknown_device_gets_a_named_stand_in(caplog):
    registry = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[])
    joystick = registry.open_joystick(device_index=3)
    assert joystick.get_name() == 'Unrecorded device 3'
    assert 'not in the recording' in caplog.text


def test_live_registry_remembers_enumeration_answers(mocker):
    mocker.patch('pygame.joystick.get_count', return_value=2)
    registry = LiveDeviceRegistry()
    assert registry.joystick_count() == 2
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='joystick_count', device_index=None, value=2)]
    assert registry.take_enumeration_answers() == []


def test_live_snapshot_holds_opened_device_positions(mocker):
    from glitchygames.live_sources import LiveSources

    fake_device = mocker.Mock(**{
        'get_instance_id.return_value': 4, 'get_name.return_value': 'Pad',
        'get_guid.return_value': 'g', 'get_numaxes.return_value': 1,
        'get_numbuttons.return_value': 1, 'get_numhats.return_value': 1,
        'get_numballs.return_value': 0, 'get_axis.return_value': 0.5,
        'get_button.return_value': True, 'get_hat.return_value': (1, 0),
    })
    mocker.patch('pygame.joystick.Joystick', return_value=fake_device)
    sources = LiveSources(random_seed=1)
    sources.devices().open_joystick(device_index=0)
    snapshot = sources.input_snapshot()
    assert snapshot.axis(device_id=4, axis=0) == 0.5
    assert snapshot.button(device_id=4, button=0) is True
    assert snapshot.hat(device_id=4, hat=0) == (1, 0)
```

- [ ] **Step 2: Run to see them fail**

Run: `SDL_VIDEODRIVER=dummy uv run pytest tests/input/test_devices.py -q -p no:cacheprovider --no-cov`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `glitchygames/input/devices.py`**

```python
"""The devices door: joysticks and controllers are enumerated and opened only here.

Live play enumerates and opens real pygame devices (``LiveDeviceRegistry``), remembering every
enumeration answer and a descriptor of each opened device for the recorder, and polls the opened
devices once per frame for the input snapshot (glitchygames/input/state.py). A replay answers with
stand-ins built from those descriptors (``ReplayJoystick``, ``ReplayController``), whose positions
come from the frame's snapshot and whose rumble is accepted and dropped, and answers enumeration
calls from the recorded answers. So a replay never needs the recorded hardware and never sees a
device that happens to be plugged in.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Protocol, Self

import pygame
import pygame._sdl2.controller

from glitchygames.input.state import current_input

LOG = logging.getLogger('game.input.devices')
LOG.addHandler(logging.NullHandler())

JOYSTICK_KIND = 'joystick'
CONTROLLER_KIND = 'controller'
JOYSTICK_COUNT_CALL = 'joystick_count'
CONTROLLER_COUNT_CALL = 'controller_count'
IS_CONTROLLER_CALL = 'is_controller'
NAME_FOR_INDEX_CALL = 'name_for_index'


@dataclasses.dataclass(frozen=True)
class DeviceDescriptor:
    """What a recording knows about a device it saw opened."""

    kind: str
    device_index: int
    instance_id: int
    name: str
    guid: str | None
    axis_count: int
    button_count: int
    hat_count: int
    ball_count: int

    def to_json(self: Self) -> dict[str, Any]:
        """Return the descriptor as a JSON-safe dict."""
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> DeviceDescriptor:
        """Read a descriptor written by ``to_json``."""
        return cls(**record)


@dataclasses.dataclass(frozen=True)
class EnumerationAnswer:
    """One answered enumeration call (recorded so a replay gives the same answer)."""

    call: str
    device_index: int | None
    value: int | bool | str | None

    def to_json(self: Self) -> dict[str, Any]:
        """Return the answer as a JSON-safe dict."""
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> EnumerationAnswer:
        """Read an answer written by ``to_json``."""
        return cls(**record)


class DeviceRegistry(Protocol):
    """Enumerates and opens devices for the engine and games (see the module docstring)."""

    def joystick_count(self) -> int: ...
    def controller_count(self) -> int: ...
    def is_controller(self, *, device_index: int) -> bool: ...
    def name_for_index(self, *, device_index: int) -> str | None: ...
    def open_joystick(self, *, device_index: int) -> Any: ...
    def open_controller(self, *, device_index: int) -> Any: ...
    def joystick_for_instance(self, *, instance_id: int) -> Any | None: ...
    def take_opened_descriptors(self) -> list[DeviceDescriptor]: ...
    def take_enumeration_answers(self) -> list[EnumerationAnswer]: ...


class LiveDeviceRegistry:
    """Enumerates and opens real devices, remembers them, and polls them for the snapshot."""

    def __init__(self: Self) -> None:
        """Start with no devices opened and nothing asked."""
        self._devices_by_instance: dict[int, Any] = {}
        self._new_descriptors: list[DeviceDescriptor] = []
        self._new_answers: list[EnumerationAnswer] = []

    def joystick_count(self: Self) -> int:
        """Return how many joysticks SDL reports (remembered for the recorder)."""
        return self._answer(call=JOYSTICK_COUNT_CALL, device_index=None,
                            value=pygame.joystick.get_count())

    def controller_count(self: Self) -> int:
        """Return how many game controllers SDL reports (remembered for the recorder)."""
        return self._answer(call=CONTROLLER_COUNT_CALL, device_index=None,
                            value=pygame._sdl2.controller.get_count())

    def is_controller(self: Self, *, device_index: int) -> bool:
        """Return whether the device at ``device_index`` is a game controller."""
        return self._answer(call=IS_CONTROLLER_CALL, device_index=device_index,
                            value=bool(pygame._sdl2.controller.is_controller(device_index)))

    def name_for_index(self: Self, *, device_index: int) -> str | None:
        """Return the controller name at ``device_index`` (None when SDL has none)."""
        name = pygame._sdl2.controller.name_forindex(device_index)
        return self._answer(call=NAME_FOR_INDEX_CALL, device_index=device_index,
                            value=None if name is None else str(name))

    def open_joystick(self: Self, *, device_index: int) -> Any:
        """Open the joystick at ``device_index`` and remember it."""
        joystick = pygame.joystick.Joystick(device_index)
        self._remember(kind=JOYSTICK_KIND, device_index=device_index, device=joystick)
        return joystick

    def open_controller(self: Self, *, device_index: int) -> Any:
        """Open the game controller at ``device_index`` and remember it."""
        controller = pygame._sdl2.controller.Controller(device_index)
        self._remember(kind=CONTROLLER_KIND, device_index=device_index,
                       device=controller.as_joystick())
        return controller

    def joystick_for_instance(self: Self, *, instance_id: int) -> Any | None:
        """Return an opened device by instance id, or None."""
        return self._devices_by_instance.get(instance_id)

    def take_opened_descriptors(self: Self) -> list[DeviceDescriptor]:
        """Return the descriptors of devices opened since the last call (the recorder's)."""
        descriptors, self._new_descriptors = self._new_descriptors, []
        return descriptors

    def take_enumeration_answers(self: Self) -> list[EnumerationAnswer]:
        """Return the enumeration answers given since the last call (the recorder's)."""
        answers, self._new_answers = self._new_answers, []
        return answers

    def poll(self: Self) -> tuple[dict[int, tuple[float, ...]], dict[int, tuple[bool, ...]],
                                  dict[int, tuple[tuple[int, int], ...]]]:
        """Read every opened device's axes, buttons and hats (once per frame, at the pump)."""
        axes: dict[int, tuple[float, ...]] = {}
        buttons: dict[int, tuple[bool, ...]] = {}
        hats: dict[int, tuple[tuple[int, int], ...]] = {}
        for instance_id, device in self._devices_by_instance.items():
            try:
                axes[instance_id] = tuple(float(device.get_axis(index))
                                          for index in range(device.get_numaxes()))
                buttons[instance_id] = tuple(bool(device.get_button(index))
                                             for index in range(device.get_numbuttons()))
                hats[instance_id] = tuple(tuple(device.get_hat(index))
                                          for index in range(device.get_numhats()))
            except pygame.error:
                # Unplugged since it was opened: it reads as absent this frame
                LOG.debug('Device %d vanished while polling', instance_id, exc_info=True)
        return axes, buttons, hats

    def _answer[AnswerValue: (int, bool, str | None)](
        self: Self, *, call: str, device_index: int | None, value: AnswerValue
    ) -> AnswerValue:
        self._new_answers.append(EnumerationAnswer(call=call, device_index=device_index,
                                                   value=value))
        return value

    def _remember(self: Self, *, kind: str, device_index: int, device: Any) -> None:
        instance_id = int(device.get_instance_id())
        self._devices_by_instance[instance_id] = device
        try:
            guid = device.get_guid()
        except AttributeError:
            guid = None
        self._new_descriptors.append(DeviceDescriptor(
            kind=kind, device_index=device_index, instance_id=instance_id,
            name=str(device.get_name()), guid=guid, axis_count=device.get_numaxes(),
            button_count=device.get_numbuttons(), hat_count=device.get_numhats(),
            ball_count=device.get_numballs(),
        ))
```

(If the generic method syntax `_answer[AnswerValue: ...]` trips basedpyright or ty, return
`Any`-free overloads instead: three small typed helpers `_answer_count`, `_answer_flag`,
`_answer_name`. Do not suppress.)

`ReplayJoystick`, `ReplayController` (as `ReplayJoystick` plus `name`, `attached()`,
`get_mapping()`, `as_joystick()`) and `ReplayDeviceRegistry`:

```python
class ReplayJoystick:
    """A recorded joystick: answers from its descriptor and the frame's input snapshot.

    A drop-in for pygame.joystick.JoystickType: its methods keep pygame's positional signatures
    (interface conformance), unlike the engine's keyword-only API.
    """

    def __init__(self: Self, *, descriptor: DeviceDescriptor) -> None:
        """Create the stand-in."""
        self._descriptor = descriptor
        self._initialized = False

    def init(self: Self) -> None:
        """Mark initialized (no hardware)."""
        self._initialized = True

    def quit(self: Self) -> None:
        """Mark uninitialized."""
        self._initialized = False

    def get_init(self: Self) -> bool:
        """Return whether init() was called."""
        return self._initialized

    def get_instance_id(self: Self) -> int:
        """Return the recorded instance id."""
        return self._descriptor.instance_id

    def get_id(self: Self) -> int:
        """Return the recorded device index."""
        return self._descriptor.device_index

    def get_name(self: Self) -> str:
        """Return the recorded name."""
        return self._descriptor.name

    def get_guid(self: Self) -> str | None:
        """Return the recorded GUID."""
        return self._descriptor.guid

    def get_power_level(self: Self) -> str:
        """Stand-ins have no battery."""
        return 'unknown'

    def get_numaxes(self: Self) -> int:
        """Return the recorded axis count."""
        return self._descriptor.axis_count

    def get_numbuttons(self: Self) -> int:
        """Return the recorded button count."""
        return self._descriptor.button_count

    def get_numhats(self: Self) -> int:
        """Return the recorded hat count."""
        return self._descriptor.hat_count

    def get_numballs(self: Self) -> int:
        """Return the recorded ball count."""
        return self._descriptor.ball_count

    def get_axis(self: Self, axis: int) -> float:
        """Return the axis position from the frame's snapshot."""
        return current_input().axis(device_id=self._descriptor.instance_id, axis=axis)

    def get_button(self: Self, button: int) -> bool:
        """Return the button state from the frame's snapshot."""
        return current_input().button(device_id=self._descriptor.instance_id, button=button)

    def get_hat(self: Self, hat: int) -> tuple[int, int]:
        """Return the hat position from the frame's snapshot."""
        return current_input().hat(device_id=self._descriptor.instance_id, hat=hat)

    def get_ball(self: Self, ball: int) -> tuple[int, int]:
        """Balls are not recorded; they read as still."""
        return (0, 0)

    def rumble(self: Self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        """Accept and drop a rumble request (no hardware in a replay)."""
        return True

    def stop_rumble(self: Self) -> None:
        """Nothing to stop."""


class ReplayController(ReplayJoystick):
    """A recorded game controller (the pygame._sdl2.controller.Controller surface used)."""

    @property
    def name(self: Self) -> str:
        """Return the recorded name."""
        return self._descriptor.name

    def attached(self: Self) -> bool:
        """A recorded controller counts as attached."""
        return True

    def get_mapping(self: Self) -> dict[str, str]:
        """Stand-ins have the default mapping."""
        return {}

    def as_joystick(self: Self) -> ReplayJoystick:
        """Return a joystick view of the same descriptor."""
        return ReplayJoystick(descriptor=self._descriptor)


class ReplayDeviceRegistry:
    """Stand-ins and recorded enumeration answers (glitchygames/replay/driver.py builds it)."""

    def __init__(self: Self, *, descriptors: list[DeviceDescriptor],
                 enumeration_answers: list[EnumerationAnswer]) -> None:
        """Index the recorded descriptors and queue the recorded answers by call."""
        self._descriptors_by_index = {descriptor.device_index: descriptor
                                      for descriptor in descriptors}
        self._opened_by_instance: dict[int, ReplayJoystick] = {}
        self._answers: dict[tuple[str, int | None], list[EnumerationAnswer]] = {}
        self._last_answers: dict[tuple[str, int | None], EnumerationAnswer] = {}
        self._learned_descriptors: list[DeviceDescriptor] = []
        self._warned_keys: set[tuple[str, int | None]] = set()
        self.add_enumeration_answers(answers=enumeration_answers)

    def add_descriptors(self: Self, *, descriptors: list[DeviceDescriptor]) -> None:
        """Learn devices the recording opened later (``devices_opened`` frame fields)."""
        for descriptor in descriptors:
            self._descriptors_by_index[descriptor.device_index] = descriptor
        self._learned_descriptors.extend(descriptors)

    def add_enumeration_answers(self: Self, *, answers: list[EnumerationAnswer]) -> None:
        """Queue answers the recording gave later (``device_enumeration`` frame fields)."""
        for answer in answers:
            self._answers.setdefault((answer.call, answer.device_index), []).append(answer)

    def joystick_count(self: Self) -> int:
        """Answer from the recording."""
        return int(self._recorded(call=JOYSTICK_COUNT_CALL, device_index=None,
                                  fallback=len(self._descriptors_by_index)))

    def controller_count(self: Self) -> int:
        """Answer from the recording."""
        fallback = sum(1 for descriptor in self._descriptors_by_index.values()
                       if descriptor.kind == CONTROLLER_KIND)
        return int(self._recorded(call=CONTROLLER_COUNT_CALL, device_index=None,
                                  fallback=fallback))

    def is_controller(self: Self, *, device_index: int) -> bool:
        """Answer from the recording."""
        descriptor = self._descriptors_by_index.get(device_index)
        fallback = descriptor is not None and descriptor.kind == CONTROLLER_KIND
        return bool(self._recorded(call=IS_CONTROLLER_CALL, device_index=device_index,
                                   fallback=fallback))

    def name_for_index(self: Self, *, device_index: int) -> str | None:
        """Answer from the recording."""
        descriptor = self._descriptors_by_index.get(device_index)
        fallback = None if descriptor is None else descriptor.name
        value = self._recorded(call=NAME_FOR_INDEX_CALL, device_index=device_index,
                               fallback=fallback)
        return None if value is None else str(value)

    def open_joystick(self: Self, *, device_index: int) -> ReplayJoystick:
        """Return a stand-in for the recorded joystick at ``device_index``."""
        joystick = ReplayJoystick(descriptor=self._descriptor(device_index=device_index,
                                                              kind=JOYSTICK_KIND))
        self._opened_by_instance[joystick.get_instance_id()] = joystick
        return joystick

    def open_controller(self: Self, *, device_index: int) -> ReplayController:
        """Return a stand-in for the recorded controller at ``device_index``."""
        controller = ReplayController(descriptor=self._descriptor(device_index=device_index,
                                                                  kind=CONTROLLER_KIND))
        self._opened_by_instance[controller.get_instance_id()] = controller
        return controller

    def joystick_for_instance(self: Self, *, instance_id: int) -> ReplayJoystick | None:
        """Return an opened stand-in by instance id, or None."""
        return self._opened_by_instance.get(instance_id)

    def take_opened_descriptors(self: Self) -> list[DeviceDescriptor]:
        """Return the descriptors learned from the recording since the last call, once each.

        A recording made over a replay (--rebaseline) writes them in the same frames.
        """
        descriptors, self._learned_descriptors = self._learned_descriptors, []
        return descriptors

    def take_enumeration_answers(self: Self) -> list[EnumerationAnswer]:
        """A rebaseline copies answers from the source recording (Task 12), not from here."""
        return []

    def _recorded(self: Self, *, call: str, device_index: int | None,
                  fallback: int | bool | str | None) -> int | bool | str | None:
        key = (call, device_index)
        queued = self._answers.get(key)
        if queued:
            self._last_answers[key] = queued.pop(0)
            return self._last_answers[key].value
        if key in self._last_answers:
            return self._last_answers[key].value
        if key not in self._warned_keys:
            self._warned_keys.add(key)
            LOG.warning('Device enumeration %s(%s) is not in the recording; answering %r',
                        call, device_index, fallback)
        return fallback

    def _descriptor(self: Self, *, device_index: int, kind: str) -> DeviceDescriptor:
        descriptor = self._descriptors_by_index.get(device_index)
        if descriptor is not None:
            return descriptor
        LOG.warning('Device %d is not in the recording; using a named stand-in', device_index)
        return DeviceDescriptor(kind=kind, device_index=device_index, instance_id=-1 - device_index,
                                name=f'Unrecorded device {device_index}', guid=None,
                                axis_count=0, button_count=0, hat_count=0, ball_count=0)
```

(Check pygame-ce's `Controller` for `as_joystick()`, `get_instance_id` and `get_numballs` in the
installed version with `uv run python -c "import pygame._sdl2.controller as controller_module;
print(dir(controller_module.Controller))"` — the pre-flight scan confirmed `as_joystick` exists in
2.5.8. The stand-ins must offer every method the proxies call: grep `self.joystick\.` and
`self.controller\.` in `glitchygames/events/` and add any missing method with a recorded or
neutral answer.)

`EngineSources.devices(self) -> DeviceRegistry` (type under `TYPE_CHECKING` in `sources.py`).
`LiveSources.__init__` creates `self._devices = LiveDeviceRegistry()`; `devices()` returns it;
`input_snapshot()` becomes:

```python
        axes, buttons, hats = self._devices.poll()
        return capture_live_snapshot(device_axes=axes, device_buttons=buttons, device_hats=hats)
```

`recording.py`: `DEVICE_ENUMERATION_FIELD = 'device_enumeration'` next to the Task 1 constants
(a header field for answers given before recording, and a per-frame field).

- [ ] **Step 4: Run** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/input -q -p no:cacheprovider --no-cov` — PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/input/devices.py glitchygames/sources.py glitchygames/live_sources.py glitchygames/recording.py tests/input/test_devices.py
git commit -m "Add the devices door: enumeration, opening and per-frame polling of devices"
```

---

### Task 6: Every device site through the devices door

**Files:**
- Modify (construction): `glitchygames/events/joystick.py:55-64, :302, :467, :507`,
  `glitchygames/events/controller.py:76`, `glitchygames/input/rumble.py:62-64`,
  `glitchygames/bitmappy/controllers/manager.py:118-120`,
  `glitchygames/examples/joystick_demo.py:381-383, :828-830, :941-943`
- Modify (enumeration): `glitchygames/events/joystick.py:301-302`,
  `glitchygames/events/controller.py:306-309`, `glitchygames/input/rumble.py:62`,
  `glitchygames/bitmappy/controllers/manager.py:118`,
  `glitchygames/examples/joystick_demo.py:449, :702-718, :868-922, :1139-1161`,
  `glitchygames/engine/game_engine.py:1891-1895` (debug log of the controller count)
- Modify (mid-frame polling → `current_input()`): `glitchygames/events/joystick.py:85-91`,
  `glitchygames/events/controller.py:88-90`, `glitchygames/examples/joystick_demo.py:502-556`,
  `glitchygames/bitmappy/controllers/event_handler.py:669-672, :708-711, :771-772`
- Test: `tests/input/test_devices.py`, the existing joystick/controller event tests
  (`grep -rln "JoystickEventManager\|ControllerEventManager\|JoystickProxy" tests/events`), the
  joystick demo and Bitmappy controller tests (`grep -rln "joystick_demo\|controllers.manager\|event_handler" tests`)

**Interfaces:**
- Consumes: `DeviceRegistry` (Task 5), `current_input()` (Task 3).
- Produces: no new names; after this task nothing outside `glitchygames/input/devices.py`
  constructs or enumerates devices, and nothing reads device positions mid-frame (Task 9's guard
  test enforces construction and enumeration by name; it cannot see method calls on device objects,
  so this task's grep in Step 1 and Step 4 is the check for polling).

Rules:
- Construction: `active_sources().devices().open_joystick(device_index=...)` /
  `open_controller(device_index=...)`. `events/joystick.py:507` resolves an instance id by opening
  the device: use `open_joystick` too. `bitmappy/controllers/manager.py:118-120` scans connected
  devices: `devices.joystick_count()` and `open_joystick(...)`.
- Enumeration: `joystick_count()`, `controller_count()`, `is_controller(device_index=...)`,
  `name_for_index(device_index=...)`.
- Polling: proxies keep their own `_axes`/`_buttons`/`_hats` caches, filled from
  `current_input().axis/button/hat(device_id=<instance id>, ...)` instead of the device; the demo's
  per-frame readout reads `current_input()` the same way. Read each site's comments first.
- **Report this bug:** `bitmappy/controllers/event_handler.py` passed an *instance id* to
  `pygame.joystick.Joystick()`, which takes a *device index*; they differ after a reconnect, so
  the wrong device (or `pygame.error`) was read. The snapshot lookup by instance id fixes it.

- [ ] **Step 1: Re-grep every device site**

Run: `grep -rn -E "joystick\.Joystick\(|controller\.Controller\(|joystick\.get_count|controller\.get_count|is_controller\(|name_forindex|\.get_axis\(|\.get_button\(|\.get_hat\(|\.get_ball\(" glitchygames | grep "\.py:" | grep -v "glitchygames/input/devices.py"`

Write the list in the report; every hit must be moved (proxy methods that *define* `get_axis` etc.
and return their cache are not reads of hardware — note them).

- [ ] **Step 2: Write the failing tests** (in the existing joystick/controller event test file;
  find it with the grep in Files)

```python
def test_joystick_proxy_opens_through_the_registry_and_reads_the_snapshot(mocker):
    from glitchygames.input.devices import DeviceDescriptor, ReplayDeviceRegistry
    from glitchygames.input.state import InputSnapshot, set_current_input
    from glitchygames.sources import active_sources

    descriptor = DeviceDescriptor(kind='joystick', device_index=0, instance_id=9, name='Pad',
                                  guid=None, axis_count=2, button_count=1, hat_count=0,
                                  ball_count=0)
    registry = ReplayDeviceRegistry(descriptors=[descriptor], enumeration_answers=[])
    mocker.patch.object(active_sources(), 'devices', return_value=registry)
    real_joystick = mocker.patch('pygame.joystick.Joystick')
    set_current_input(snapshot=InputSnapshot(
        pressed_scancodes=frozenset(), modifiers=0, mouse_position=(0, 0),
        mouse_buttons=(False, False, False), mouse_focused=True,
        device_axes={9: (0.25, -1.0)}, device_buttons={9: (True,)}))
    proxy = JoystickEventManager.JoystickEventProxy(joystick_id=0, game=None)
    real_joystick.assert_not_called()
    assert proxy.get_axis(1) == -1.0     # read through the proxy's cache, filled from the snapshot
```

(Use the proxy's real class path and constructor arguments — read `events/joystick.py` around
`:40-70`; adjust the keyword names to match. Add the same test for the controller proxy, and a
test that `ControllerEventManager` enumerates through `controller_count()` / `is_controller(...)`:
patch the registry, assert `pygame._sdl2.controller.get_count` is never called.)

```python
def test_bitmappy_trigger_values_come_from_the_snapshot_by_instance_id(mocker):
    from glitchygames.input.state import InputSnapshot, set_current_input

    real_joystick = mocker.patch('pygame.joystick.Joystick')
    set_current_input(snapshot=InputSnapshot(
        pressed_scancodes=frozenset(), modifiers=0, mouse_position=(0, 0),
        mouse_buttons=(False, False, False), mouse_focused=True,
        device_axes={12: (0.0, 0.0, 0.0, 0.0, 1.0, -1.0)}))
    handler = make_event_handler(mocker)          # the Bitmappy test file's existing factory
    event = pygame.event.Event(pygame.CONTROLLERAXISMOTION, {'instance_id': 12, 'axis': 4,
                                                             'value': 32767})
    left_trigger, right_trigger = handler._read_trigger_values(event, 12)
    assert (left_trigger, right_trigger) == (1.0, 0.0)
    real_joystick.assert_not_called()
```

(Find the Bitmappy controller test file and its handler factory; if it builds the handler
differently, follow it. The expected values follow the existing `(raw + 1.0) / 2.0` conversion.)

- [ ] **Step 3: Run to see them fail.**

- [ ] **Step 4: Move every site, re-run Step 1's grep (only `devices.py` and cache-returning proxy
  methods remain), run the tests listed in Files, `tests/input`, `tests/events`, `tests/examples`,
  the golden test and the full suite.** Expected: PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/events/joystick.py glitchygames/events/controller.py glitchygames/input/rumble.py glitchygames/bitmappy/controllers/manager.py glitchygames/bitmappy/controllers/event_handler.py glitchygames/examples/joystick_demo.py glitchygames/engine/game_engine.py <every test file you changed>
git commit -m "Route every device construction, enumeration and poll through the devices door"
```

---

### Task 7: The saves door

**Files:**
- Create: `glitchygames/state/sandbox.py`
- Modify: `glitchygames/state/__init__.py` (export `open_saves`, `SaveStore`, `SandboxSaves`)
- Modify: `glitchygames/sources.py` (Protocol `saves`; `SaveStore` under `TYPE_CHECKING`),
  `glitchygames/live_sources.py` (`LiveSources.saves`)
- Modify: `glitchygames/examples/paddleslap.py:300`, `glitchygames/examples/clockwork_keep/game.py:323`,
  `glitchygames/examples/brave_adventurer/game.py:173`,
  `glitchygames/examples/brave_adventurer_papyrus/game.py:173`
- Test: `tests/state/test_sandbox.py` (new)

**Interfaces:**
- Produces:

```python
class SaveStore(Protocol):
    app_name: str  (property)
    def load(self, slot_name: str) -> dict[str, Any]: ...
    def save(self, slot_name: str, data: dict[str, Any]) -> object: ...
    def exists(self, slot_name: str) -> bool: ...
    def delete(self, slot_name: str) -> None: ...
class SandboxSaves:  # implements SaveStore
    def __init__(self, *, app_name: str, envelopes: dict[str, dict[str, Any]]) -> None: ...
def open_saves(*, app_name: str) -> SaveStore      # through the active sources
def save_namespace_snapshot(*, saves: SaveManager) -> dict[str, dict[str, Any]]  # slot -> envelope
EngineSources.saves(self, *, namespace: str) -> SaveStore
LiveSources.opened_save_namespaces -> dict[str, SaveManager]   # for RecordingSources (Task 11)
```

- [ ] **Step 1: Write the failing tests** (`tests/state/test_sandbox.py`)

```python
"""The saves door (glitchygames/state/sandbox.py)."""

from __future__ import annotations

import pytest

from glitchygames.live_sources import LiveSources
from glitchygames.sources import install_sources
from glitchygames.state import SaveManager, SaveNotFoundError
from glitchygames.state.sandbox import SandboxSaves, open_saves, save_namespace_snapshot


def test_live_open_saves_is_a_save_manager(tmp_path, mocker):
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    saves = open_saves(app_name='demo')
    assert isinstance(saves, SaveManager)
    assert saves.app_name == 'demo'


def test_snapshot_holds_every_slot_envelope(tmp_path):
    saves = SaveManager(app_name='demo', save_dir=tmp_path)
    saves.save('high_scores', {'scores': [{'score': 900}]})
    snapshot = save_namespace_snapshot(saves=saves)
    assert snapshot['high_scores']['data'] == {'scores': [{'score': 900}]}


def test_sandbox_reads_the_snapshot_and_discards_writes(tmp_path):
    saves = SaveManager(app_name='demo', save_dir=tmp_path)
    saves.save('high_scores', {'scores': [{'score': 900}]})
    sandbox = SandboxSaves(app_name='demo', envelopes=save_namespace_snapshot(saves=saves))
    assert sandbox.load('high_scores') == {'scores': [{'score': 900}]}
    sandbox.save('high_scores', {'scores': [{'score': 800}]})
    assert sandbox.load('high_scores') == {'scores': [{'score': 800}]}
    assert saves.load('high_scores') == {'scores': [{'score': 900}]}  # the disk is untouched


def test_snapshot_of_a_sandbox_is_a_copy_of_its_envelopes():
    sandbox = SandboxSaves(app_name='demo', envelopes={'slot': {'data': {'value': 1}}})
    snapshot = save_namespace_snapshot(saves=sandbox)
    snapshot['slot']['data']['value'] = 2
    assert sandbox.load('slot') == {'value': 1}


def test_sandbox_missing_slot_raises_like_the_real_store():
    sandbox = SandboxSaves(app_name='demo', envelopes={})
    with pytest.raises(SaveNotFoundError):
        sandbox.load('high_scores')
    assert not sandbox.exists('high_scores')


def test_live_sources_remember_opened_namespaces(tmp_path, mocker):
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    sources = LiveSources(random_seed=1)
    install_sources(sources=sources)
    open_saves(app_name='demo')
    assert list(sources.opened_save_namespaces) == ['demo']
```

(Check how `SaveManager` imports `get_save_directory` — the golden harness patches
`save_manager_module.get_save_directory`; patch the same name.)

- [ ] **Step 2: Run to see them fail** — Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `glitchygames/state/sandbox.py`**

```python
"""The saves door: games open their save store through the active sources.

Live play gets a real ``SaveManager``. A recording stores each opened store's slots (their full
envelopes) when recording starts or when the store is opened later, and a replay or in-game
playback gets a ``SandboxSaves`` seeded from them: reads see what the original session saw, and
writes stay in memory and are discarded, so a replay never touches real saves.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Protocol, Self

from glitchygames.sources import active_sources
from glitchygames.state.exceptions import SaveNotFoundError

if TYPE_CHECKING:
    from glitchygames.state.manager import SaveManager

# The envelope key holding the game's data (glitchygames/state/manager.py _DATA_KEY)
DATA_KEY = 'data'


class SaveStore(Protocol):
    """What games use of a save store."""

    @property
    def app_name(self) -> str: ...
    def load(self, slot_name: str) -> dict[str, Any]: ...
    def save(self, slot_name: str, data: dict[str, Any]) -> object: ...
    def exists(self, slot_name: str) -> bool: ...
    def delete(self, slot_name: str) -> None: ...


class SandboxSaves:
    """An in-memory save store seeded from recorded envelopes; writes are discarded at exit."""

    def __init__(self: Self, *, app_name: str, envelopes: dict[str, dict[str, Any]]) -> None:
        """Copy the recorded envelopes (the recording is never modified)."""
        self._app_name = app_name
        self._envelopes = copy.deepcopy(envelopes)

    @property
    def app_name(self: Self) -> str:
        """The application name this store is scoped to."""
        return self._app_name

    def load(self: Self, slot_name: str) -> dict[str, Any]:
        """Return a slot's data.

        Raises:
            SaveNotFoundError: If the slot does not exist, as SaveManager does.

        """
        envelope = self._envelopes.get(slot_name)
        if envelope is None:
            message = f"No save slot '{slot_name}' in the replay's save snapshot"
            raise SaveNotFoundError(message, slot_name=slot_name)
        return copy.deepcopy(envelope[DATA_KEY])

    def save(self: Self, slot_name: str, data: dict[str, Any]) -> None:
        """Keep the data in memory only.

        Positional like ``SaveManager.save`` (a drop-in: interface conformance).
        """
        self._envelopes[slot_name] = {DATA_KEY: copy.deepcopy(data)}

    def exists(self: Self, slot_name: str) -> bool:
        """Return whether the slot exists in the sandbox."""
        return slot_name in self._envelopes

    def delete(self: Self, slot_name: str) -> None:
        """Remove the slot from the sandbox."""
        self._envelopes.pop(slot_name, None)

    def envelopes(self: Self) -> dict[str, dict[str, Any]]:
        """Return a deep copy of every slot's envelope (a recording made over a replay
        snapshots a sandbox, --rebaseline, and so does a scene start inside one)."""
        return copy.deepcopy(self._envelopes)


def save_namespace_snapshot(*, saves: SaveManager | SandboxSaves) -> dict[str, dict[str, Any]]:
    """Return every slot of a store as its full envelope (slot name -> envelope).

    Args:
        saves: A real store, or the sandbox a replay hands out.

    Returns:
        The JSON-safe snapshot a recording stores.

    """
    if isinstance(saves, SandboxSaves):
        return saves.envelopes()
    return {slot.name: saves.load_raw(slot_name=slot.name) for slot in saves.list_slots()}


def open_saves(*, app_name: str) -> SaveStore:
    """Open a game's save store through the active sources (glitchygames/sources.py).

    Returns:
        The store: a SaveManager live, a SandboxSaves in a replay.

    """
    return active_sources().saves(namespace=app_name)
```

`EngineSources.saves(self, *, namespace: str) -> SaveStore`. In `LiveSources.__init__` add
`self.opened_save_namespaces: dict[str, SaveManager] = {}` (comment: "Stores games opened, by
namespace; RecordingSources snapshots them"), and add the method:

```python
    def saves(self: Self, *, namespace: str) -> SaveStore:
        """Open (or return the already opened) real save store for ``namespace``."""
        store = self.opened_save_namespaces.get(namespace)
        if store is None:
            store = SaveManager(app_name=namespace)
            self.opened_save_namespaces[namespace] = store
        return store
```

Each game: `self.saves = open_saves(app_name='paddleslap')` (import from `glitchygames.state`),
and change the attribute's annotation (if any) to `SaveStore`. Check every other `self.saves.`
use in the four games uses only `load`/`save`/`exists`/`delete`.

- [ ] **Step 4: Run** `tests/state`, `tests/examples`, `tests/world` (golden harness patches
  `get_save_directory`, which `LiveSources.saves` still uses). Expected: PASS, golden unchanged.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/state/sandbox.py glitchygames/state/__init__.py glitchygames/sources.py glitchygames/live_sources.py glitchygames/examples/paddleslap.py glitchygames/examples/clockwork_keep/game.py glitchygames/examples/brave_adventurer/game.py glitchygames/examples/brave_adventurer_papyrus/game.py tests/state/test_sandbox.py
git commit -m "Add the saves door: games open saves through the sources; replay sandbox"
```

---

### Task 8: Clock exports; polled input, engine, UI and game clock sites

> Superseded in part by Task 12b: `elapsed_seconds()` is the frame clock live and replayed; there is no `EngineSources.elapsed_seconds` door.

**Files:**
- Create: `glitchygames/clock.py` (the public clock exports)
- Modify: `glitchygames/sources.py` (Protocol `wall_clock_time`, `elapsed_seconds`),
  `glitchygames/live_sources.py` (the live providers)
- Create: `tests/test_clock.py`
- Modify (polled input → `current_input()`): `glitchygames/ui/inputs.py:528`,
  `glitchygames/ui/text_widgets.py:1207, :1487`, `glitchygames/scenes/scene.py:481` (debug overlay
  mouse), `glitchygames/examples/dt_demo.py:131`, `glitchygames/bitmappy/editor.py:485, :1392`,
  `glitchygames/bitmappy/film_strip_sprite.py:126-127, :182-183, :478`,
  `glitchygames/bitmappy/file_io.py:120`, `glitchygames/bitmappy/animated_canvas.py:916`
- Modify (clock sites outside Bitmappy, table below): `glitchygames/examples/paddleslap.py`,
  `glitchygames/ui/inputs.py`, `glitchygames/ui/text_widgets.py`, `glitchygames/scenes/scene.py`,
  `glitchygames/engine/game_engine.py`, `glitchygames/state/manager.py`
- Modify: `scripts/record_golden_traces.py:458-487` (drop the `paddleslap.time` patch)
- Modify (if needed): `tests/world/test_golden_traces.py` (`EXPECTED_DIFFERENCES['paddleslap']`)
- Test: `tests/test_clock.py`, plus each touched module's existing tests

**Interfaces:**
- Consumes: `current_input()` (Task 3), `Scene.game_time` and the frame clock (Task 4).
- Produces (`glitchygames/clock.py`, the one module code imports clocks from):

```python
def frame_clock_seconds() -> float        # sum of frame times; re-exported from glitchygames.sources
def frame_clock_milliseconds() -> int     # the same in whole milliseconds (widget timers)
def wall_clock_time() -> datetime.datetime          # timezone-aware UTC
def wall_clock_epoch_seconds() -> float            # wall_clock_time().timestamp()
def elapsed_seconds() -> float                     # monotonic seconds; only differences mean anything
# Scene.game_time stays on the scene (Task 4); clock.py's docstring points to it.
EngineSources.wall_clock_time(self) -> datetime.datetime
EngineSources.elapsed_seconds(self) -> float
```

Providers: `LiveSources.wall_clock_time()` = `datetime.datetime.now(tz=datetime.UTC)`;
`LiveSources.elapsed_seconds()` = `time.monotonic()`. Replay (Task 12 implements it in
`ReplaySources`): `wall_clock_time()` = the header's `recorded_at` (`datetime.fromisoformat`) +
`timedelta(seconds=frame_clock_seconds())`; `elapsed_seconds()` = `frame_clock_seconds()`. So both
replay exactly. `RecordingSources` (Task 11) delegates both to its inner sources. Which export a
call site uses:

| Export | Use it for | Pauses with the game? |
|---|---|---|
| `scene.game_time` | gameplay timers and cooldowns | yes |
| `frame_clock_seconds()` | blinks, animation timing, FPS events, "how long since" in UI | no |
| `wall_clock_time()` / `wall_clock_epoch_seconds()` | timestamps: undo history, save and file metadata, log records, ids | no |
| `elapsed_seconds()` | durations, metrics, controller and input timing | no |

Only pacing (`glitchygames/timing.py`, the frame measurement in `SceneManager.start` /
`_finish_frame`), the performance statistics (`glitchygames/performance/`, the debug HUD's timing),
the audio-glitch probe (`glitchygames/audio/diagnostics.py`, which measures the real machine) and
the recording's own start stamp (`GameEngine.trace_recording_header`'s `recorded_at`) read the raw
clock; Task 9's guard test lists them by file.

Clock sites this task moves (taken at `414d080`; re-grep in Step 1):

| Site | Today | Export |
|---|---|---|
| `examples/paddleslap.py:650, :670` | ball-spawn cooldown, `time.time()` | `self.game_time` (and `:301` → `-math.inf`) |
| `ui/inputs.py:156` | cursor blink, `time.time() % 1` | `frame_clock_seconds()` |
| `ui/text_widgets.py:711, :714, :1082, :1142, :1247` | cursor blink and update interval, `get_ticks()` | `frame_clock_seconds()` (in ms, one helper) |
| `scenes/scene.py:2491` | FPS log interval in `Scene.on_fps_event`, `perf_counter()` | `frame_clock_seconds()` |
| `engine/game_engine.py:578, :1944` | unhandled-event first-seen time (teardown report), `perf_counter()` | `elapsed_seconds()` |
| `state/manager.py:144` | save envelope timestamp, `datetime.now(tz=UTC)` | `wall_clock_time()` |

Stays raw (allowed in Task 9's guard): `scenes/scene.py:791, :795, :809, :862` (pacing
measurement), `engine/game_engine.py:1114` (`recorded_at`), `performance/adaptive_clamping.py:147`,
`audio/diagnostics.py` (7 reads). Not clock reads (`time.sleep`): `engine/game_engine.py:2038`
(`sleep(0)`, a thread yield), `events/voice.py:230, :237` (voice-recognition retry back-off on its
own thread), `audio/controller_audio.py:739` (waits for a test tone to finish) — they block, they
do not read the time, so they cannot make a replay differ; leave them and say so in the report.
`api/client.py:341, :371` signs requests to a real server, which needs real time: allowed raw
(the guard lists it), not an export.

- [ ] **Step 1: Re-grep every site and compare with the tables (here and in Task 9)**

Run: `grep -rn -E "time\.time\(\)|time\.monotonic\(\)|time\.perf_counter\(\)|time\.perf_counter_ns\(\)|time\.monotonic_ns\(\)|time\.time_ns\(\)|datetime\.now|datetime\.utcnow|pygame\.time\.get_ticks|time\.sleep\(|time_module\.|key\.get_pressed|key\.get_mods|mouse\.get_pos|mouse\.get_pressed|mouse\.get_focused" glitchygames | grep "\.py:"`

Any site not in the tables: categorise it with the export table above and add it to this task
(outside `bitmappy/`) or Task 9 (inside), and list it in the report.

- [ ] **Step 2: Write the failing clock tests** (`tests/test_clock.py`)

```python
"""The engine's clock exports (glitchygames/clock.py): live and replay providers."""

from __future__ import annotations

import datetime
import subprocess
import sys
import types

import pytest

from glitchygames import clock
from glitchygames import live_sources as live_sources_module
from glitchygames.live_sources import LiveSources
from glitchygames.sources import advance_frame_clock, install_sources

# Every door and clock module, each imported first and alone in a fresh interpreter: an import
# cycle between them fails here instead of at game start (layering rule, core Task 2)
DOOR_MODULES = (
    'glitchygames.sources', 'glitchygames.clock', 'glitchygames.live_sources',
    'glitchygames.input.state', 'glitchygames.input.devices', 'glitchygames.input.rumble',
    'glitchygames.state.sandbox', 'glitchygames.state.manager', 'glitchygames.recording',
)


def test_live_wall_clock_is_aware_utc_now():
    before = datetime.datetime.now(tz=datetime.UTC)
    reading = LiveSources(random_seed=1).wall_clock_time()
    after = datetime.datetime.now(tz=datetime.UTC)
    assert reading.tzinfo is datetime.UTC
    assert before <= reading <= after


def test_wall_clock_epoch_seconds_matches_wall_clock_time(mocker):
    fixed = datetime.datetime(2026, 10, 19, 12, 0, tzinfo=datetime.UTC)
    mocker.patch.object(LiveSources, 'wall_clock_time', return_value=fixed)
    assert clock.wall_clock_epoch_seconds() == fixed.timestamp()


def test_live_elapsed_seconds_reads_monotonic_time(mocker):
    # Patch the module-level `time` name live_sources uses, never the global time module
    fake_time = types.SimpleNamespace(monotonic=mocker.Mock(side_effect=[10.0, 10.5]))
    mocker.patch.object(live_sources_module, 'time', fake_time)
    first = clock.elapsed_seconds()
    second = clock.elapsed_seconds()
    assert second - first == 0.5


def test_frame_clock_milliseconds():
    advance_frame_clock(seconds=1.25)
    advance_frame_clock(seconds=0.0625)
    assert clock.frame_clock_milliseconds() == 1312   # 1312.5 rounds to even


def test_frame_clock_is_the_sum_of_frame_times():
    advance_frame_clock(seconds=0.25)
    advance_frame_clock(seconds=0.5)
    assert clock.frame_clock_seconds() == 0.75


class FixedClockSources(LiveSources):
    """Stand-in for the replay providers Task 12 writes: start time + frame clock."""

    START = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.UTC)

    def wall_clock_time(self) -> datetime.datetime:
        return self.START + datetime.timedelta(seconds=clock.frame_clock_seconds())

    def elapsed_seconds(self) -> float:
        return clock.frame_clock_seconds()


@pytest.mark.parametrize('module_name', DOOR_MODULES)
def test_door_module_imports_alone(module_name):
    completed = subprocess.run([sys.executable, '-c', f'import {module_name}'],
                               capture_output=True, text=True, check=False, timeout=60)
    assert completed.returncode == 0, completed.stderr


def test_clock_exports_read_the_active_sources():
    install_sources(sources=FixedClockSources(random_seed=1))
    advance_frame_clock(seconds=2.0)
    assert clock.wall_clock_time() == FixedClockSources.START + datetime.timedelta(seconds=2)
    assert clock.elapsed_seconds() == pytest.approx(2.0)
```

(`glitchygames.replay.driver` joins `DOOR_MODULES` in Task 12, `glitchygames.supervision` in
Task 10: add each module to the tuple in the task that creates it.)

- [ ] **Step 3: Run to see them fail** — `ModuleNotFoundError: glitchygames.clock`.

- [ ] **Step 4: Implement `glitchygames/clock.py` and the providers**

```python
"""The engine's clocks: every time a game, widget or editor reads comes from here.

Pick by what the time is for:

- ``Scene.game_time`` (on the scene): gameplay timers and cooldowns; pauses with the scene.
- ``frame_clock_seconds()``: blinks, animation timing, FPS events, "how long since" in UI; the
  sum of frame times, never pauses.
- ``wall_clock_time()`` / ``wall_clock_epoch_seconds()``: timestamps (undo history, save and
  file metadata, log records, ids).
- ``elapsed_seconds()``: durations, metrics, controller and input timing; only differences
  between two readings mean anything.

Each reads the active sources (glitchygames/sources.py), so a replay serves them exactly: the
frame clock comes from recorded frame times, the wall clock is the recording's start time plus
the frame clock, and elapsed seconds are the frame clock. Only pacing, the performance statistics,
the audio-glitch probe and the recording's own start stamp read the raw clock
(tests/test_engine_doors.py lists them).
"""

from __future__ import annotations

import datetime

from glitchygames.sources import active_sources, frame_clock_seconds

__all__ = [
    'elapsed_seconds',
    'frame_clock_milliseconds',
    'frame_clock_seconds',
    'wall_clock_epoch_seconds',
    'wall_clock_time',
]


def frame_clock_milliseconds() -> int:
    """Return the frame clock in whole milliseconds (widget blink and update timers).

    Returns:
        ``round(frame_clock_seconds() * 1000)``.

    """
    return round(frame_clock_seconds() * 1000)


def wall_clock_time() -> datetime.datetime:
    """Return the current wall-clock time (timezone-aware UTC) from the active sources.

    Returns:
        Now, live; the recording's start time plus the frame clock, in a replay.

    """
    return active_sources().wall_clock_time()


def wall_clock_epoch_seconds() -> float:
    """Return ``wall_clock_time()`` as seconds since the Unix epoch (what ``time.time()`` gave).

    Returns:
        Seconds since 1970-01-01 UTC.

    """
    return wall_clock_time().timestamp()


def elapsed_seconds() -> float:
    """Return a monotonic reading in seconds; subtract two readings for a duration.

    Returns:
        ``time.monotonic()`` live; the frame clock in a replay.

    """
    return active_sources().elapsed_seconds()
```

In `glitchygames/sources.py` add the two methods to `EngineSources` (docstrings as above), and in
`glitchygames/live_sources.py` (which imports `datetime` and `time` at module level) to
`LiveSources`:

```python
    def wall_clock_time(self: Self) -> datetime.datetime:
        """Return now, in UTC (the live wall-clock provider)."""
        return datetime.datetime.now(tz=datetime.UTC)

    def elapsed_seconds(self: Self) -> float:
        """Return time.monotonic() (the live elapsed-time provider)."""
        return time.monotonic()
```

- [ ] **Step 5: Move the polled-input sites and the clock sites in the table**

Polled input, e.g. `bitmappy/editor.py:485`:

```python
        held_keys = current_input()
        is_shift_click = held_keys.key_pressed(pygame.K_LSHIFT) or held_keys.key_pressed(
            pygame.K_RSHIFT
        )
```

`ui/inputs.py:528`, `ui/text_widgets.py:1487`, `bitmappy/*` mouse reads:
`mouse_position = current_input().mouse_position`, renaming the old `mouse_pos` variable and
its uses in that function (no abbreviations in changed lines). `ui/text_widgets.py:1207`:
`modifiers = current_input().modifiers`, renaming `mods` and its uses in that function. Debug overlay `scenes/scene.py:481`:

```python
        frame_input = current_input()
        mouse_position = frame_input.mouse_position if frame_input.mouse_focused else None
```

PaddleSlap (read the comments at `:301-302` first):

```python
        # Game time of the last spawn (Scene.game_time); -inf so the first spawn is never held
        # back by the cooldown, as with the old wall-clock start of 0.0
        self.last_ball_spawn_time = -math.inf
```

`:650` `current_time = self.game_time`; `:670` `self.last_ball_spawn_time = self.game_time`;
remove `import time` if nothing else uses it. `ui/inputs.py:156`:

```python
        if frame_clock_seconds() % 1 > CURSOR_BLINK_HALF_SECOND and self.is_active:
```

`ui/text_widgets.py` keeps milliseconds: replace each `pygame.time.get_ticks()` with
`frame_clock_milliseconds()` from `glitchygames/clock.py`.

`scenes/scene.py:2491`: `current_time = frame_clock_seconds()` (and initialise
`_last_fps_log_time` from the same clock — read where it is set; it is `0.0` in `Scene.__init__`,
which stays correct). `engine/game_engine.py:578`: `self._started_at_seconds: float =
elapsed_seconds()`; `:1944`: `first_seen_seconds=elapsed_seconds() - self._started_at_seconds`.
`state/manager.py:144`: `'timestamp': wall_clock_time().isoformat(),` (drop the now-unused
`datetime`/`UTC` imports if nothing else uses them).

Golden harness: remove `(paddleslap, 'time', types.SimpleNamespace(time=clock.now))` from
`deterministic_environment` and update its docstring ("Replace the save directory ... PaddleSlap's
cooldown now uses Scene.game_time, which the harness's fixed dt drives"). If `clock` is then
unused by `deterministic_environment`, keep the parameter only if other callers rely on it
(`grep -rn deterministic_environment tests scripts`); otherwise remove it and update callers.

- [ ] **Step 6: Golden check and the behaviour-fix rule**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/world/test_golden_traces.py -q -p no:cacheprovider --no-cov`

The harness's fake clock advanced `FRAME_SECONDS` every frame, including paused frames; game time
does not advance while paused. If PaddleSlap's golden differs, every difference must be a spawn
that happens one or more frames later than in the baseline because the cooldown was measured in
wall time across the script's pause (`paddleslap_script` pauses; read it). Add one
`ExpectedDifference` per class with a `rule` that proves it exactly: from the frame observer
(Task 6 of the world-space plan added `frame_observer` sampling), record each frame's
`scene.game_time` and the fake wall time (`FAKE_CLOCK_START_SECONDS + frame * FRAME_SECONDS`);
the rule accepts a frame only if the baseline's ball count is explained by the wall-time cooldown
and the current one by the game-time cooldown (`last_ball_spawn_time` from the observer). Never
edit the baseline. If there is no difference, say so in the report (the script's spawns may all
be outside the pause window).

- [ ] **Step 7: Run every touched module's tests, `tests/world`, the full suite** — PASS, no
  warnings.

- [ ] **Step 8: Lint, type-check, vulture, commit**

```bash
git add glitchygames/clock.py glitchygames/sources.py glitchygames/live_sources.py tests/test_clock.py scripts/record_golden_traces.py glitchygames/examples/paddleslap.py glitchygames/ui/inputs.py glitchygames/ui/text_widgets.py glitchygames/scenes/scene.py glitchygames/engine/game_engine.py glitchygames/state/manager.py glitchygames/examples/dt_demo.py glitchygames/bitmappy/editor.py glitchygames/bitmappy/film_strip_sprite.py glitchygames/bitmappy/file_io.py glitchygames/bitmappy/animated_canvas.py <tests/world/test_golden_traces.py if a rule was added> <every other test file you changed>
git commit -m "Add the engine's clock exports; move polled input and engine/UI/game clocks"
```

---

### Task 9: Bitmappy onto the clock exports, and the guard test

> Superseded in part by Task 12b: `elapsed_seconds()` is the frame clock live and replayed; there is no `EngineSources.elapsed_seconds` door (diagnostic durations use `measured_seconds()`).

**Files:**
- Modify (every Bitmappy clock site, table below): `glitchygames/bitmappy/history/commands.py`,
  `history/undo_redo.py`, `controllers/selection.py`, `controllers/performance.py`,
  `controllers/manager.py`, `controllers/canvas_operations.py`, `controllers/event_handler.py`,
  `controllers/slider_operations.py`, `controllers/enhancements.py`, `controllers/strategies.py`,
  `controllers/error_handling.py`, `ai_worker.py`, `ai_manager.py`, `editor.py`,
  `canvas_interfaces.py`, `frame_operations.py`, `film_strip_rendering.py`, `film_strip_events.py`
  (all under `glitchygames/bitmappy/`)
- Create: `tests/ast_scanning.py` (shared AST helpers moved out of `tests/test_randomness.py`)
- Create: `tests/test_engine_doors.py`
- Modify: `tests/test_randomness.py` (import the moved helpers)
- Test: `tests/test_engine_doors.py`, plus the Bitmappy tests of every touched module
  (`grep -rln "<module name>" tests/` for each)

**Interfaces:**
- Consumes: `glitchygames/clock.py` (Task 8), `current_input()` (Task 3).
- Produces: `tests/ast_scanning.py` (keyword-only, generic over the watched modules):
  `import_bindings(*, tree, watched_modules: frozenset[str]) -> dict[str, str]`,
  `dynamic_import_name(*, node, watched_modules: frozenset[str]) -> str | None`,
  `qualified_name(*, node, bindings: dict[str, str], watched_modules: frozenset[str]) -> str | None`;
  `tests/test_engine_doors.py`: `door_bypasses(*, source_path, allowed) -> list[str]`,
  `WATCHED_DOOR_MODULES`, `DOOR_BYPASSES`, `ALLOWED_BYPASSES`.

Bitmappy clock sites (taken at `414d080`; 74 in all; re-grep with Task 8's Step 1 command):

| Site | What it is | Export |
|---|---|---|
| `history/commands.py:104, :198, :285, :367, :471, :645, :707, :826, :948, :1020, :1092, :1165, :1258` (13) | each command's `self.timestamp` (undo history) | `wall_clock_epoch_seconds()` |
| `history/undo_redo.py:327, :362` (2) | history entry `timestamp=` | `wall_clock_epoch_seconds()` |
| `controllers/selection.py:85, :125` (2) | selection-history `'timestamp'` records | `wall_clock_epoch_seconds()` |
| `controllers/canvas_operations.py:370` (1) | operation record `'timestamp'` | `wall_clock_epoch_seconds()` |
| `controllers/enhancements.py:311` (1) | action record `'timestamp'` | `wall_clock_epoch_seconds()` |
| `controllers/error_handling.py:109` (1) | error record `timestamp=` | `wall_clock_epoch_seconds()` |
| `ai_manager.py:322` (1) | `request_id = str(time.time())` | `wall_clock_epoch_seconds()` (an id; see note) |
| `history/commands.py:1202-1204` (1) | `import time as time_module`; mode switch time passed to `switch_to_mode` | `elapsed_seconds()` (drop the local import) |
| `controllers/selection.py:70, :89, :102, :130, :175, :197, :219, :273, :282, :325` (10) | `creation_time`, `last_update_time`, "seconds since last update" | `elapsed_seconds()` |
| `controllers/performance.py:65, :305, :315, :326, :329, :351, :356, :367, :437, :446, :474, :529` (12) | operation metrics and cleanup interval | `elapsed_seconds()` |
| `controllers/manager.py:110, :246, :247, :273, :338, :364` (6) | controller scan interval, assignment and activity times, inactivity cleanup | `elapsed_seconds()` |
| `controllers/canvas_operations.py:65, :530, :591` (3) | drag end time; continuous-movement start and repeat timing | `elapsed_seconds()` |
| `controllers/event_handler.py:465, :571` (2) | axis-motion and trigger mode-switch timing | `elapsed_seconds()` |
| `controllers/slider_operations.py:97, :176, :207` (3) | mode-switch times passed to `switch_to_mode` | `elapsed_seconds()` |
| `controllers/strategies.py:247` (1) | strategy `'start_time'` | `elapsed_seconds()` |
| `controllers/enhancements.py:168, :285` (2) | visual-update metric; update throttle | `elapsed_seconds()` |
| `ai_worker.py:436, :442, :574, :613, :619` (5) | AI request durations (worker thread) | `elapsed_seconds()` |
| `editor.py:858, :859` (2) | "log animation state about once per second" | `frame_clock_seconds()` |
| `canvas_interfaces.py:529` + `frame_operations.py:422` (2) | single-pixel change debounce: started / "more than 0.1 s since" | `frame_clock_seconds()` (both ends of the one timer) |
| `film_strip_rendering.py:587` + `film_strip_events.py:138, :287, :302` (4) | film-strip label cursor blink, `get_ticks()` ms | `frame_clock_seconds()` (ms helper, as `text_widgets.py`) |

Notes: every value read from `elapsed_seconds()` must be compared only with other
`elapsed_seconds()` readings — check each site's partner (e.g. `switch_to_mode(new_mode,
current_time)` stores the time; find where the mode switcher subtracts it and confirm the other
reading is also moved, or move it here). A timestamp field that some code *subtracts* is not a
timestamp but a duration source — if you find one (`grep` each `timestamp` field's readers), use
`elapsed_seconds()` for it instead and note it. `ai_worker.py` runs on a worker thread: reading
`elapsed_seconds()` there reads the active sources from another thread, which is safe (a float
read); in a replay the AI worker is not exercised (its requests are network calls, out of replay's
scope) — say so in the report. `ai_manager.py:322`'s request id only needs to be unique: if two
requests in one frame of a replay could get the same id (the frame clock does not advance within
a frame), append a per-process counter (`itertools.count()`) to the id and test that two ids made
in one frame differ.

- [ ] **Step 1: Move the AST helpers and write the failing guard test**

Move `_import_bindings`, `_dynamic_import_name` and `_qualified_name` from
`tests/test_randomness.py` into `tests/ast_scanning.py` as public, keyword-only
`import_bindings(*, tree, watched_modules)`, `dynamic_import_name(*, node, watched_modules)` and
`qualified_name(*, node, bindings, watched_modules)`: the bodies today read the randomness guard's
`WATCHED_MODULES` global; replace that read with the `watched_modules` parameter (docstrings kept
and updated). `tests/test_randomness.py` keeps its `WATCHED_MODULES` and passes it
(`watched_modules=WATCHED_MODULES`) at each call. Run `tests/test_randomness.py` — it must still
pass unchanged.

`tests/test_engine_doors.py`:

```python
"""Nothing in the package reads input or time from outside the engine's doors.

Polled input goes through glitchygames/input/state.py, devices through
glitchygames/input/devices.py, events through glitchygames/sources.py, posted events through
glitchygames/recording.post_event, and time through glitchygames/clock.py (or Scene.game_time),
so a replay reaches all of it (plans/2026-10-19-gameplay-replay.md, section 3.4). Only the files
in ALLOWED_BYPASSES read the raw clock or pygame directly, each for the reason given.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.ast_scanning import import_bindings, qualified_name

PACKAGE = Path(__file__).resolve().parent.parent / 'glitchygames'

# Modules whose names the scan resolves through imports and aliases
WATCHED_DOOR_MODULES = frozenset({
    'time', 'datetime', 'pygame', 'pygame.key', 'pygame.mouse', 'pygame.event', 'pygame.time',
    'pygame.joystick', 'pygame._sdl2', 'pygame._sdl2.controller', 'pygame.controller',
    'pygame.fastevent',
})

RAW_CLOCK_READS = frozenset({
    'time.time', 'time.time_ns', 'time.monotonic', 'time.monotonic_ns', 'time.perf_counter',
    'time.perf_counter_ns', 'datetime.datetime.now', 'datetime.datetime.utcnow',
    'pygame.time.get_ticks',
})

DOOR_BYPASSES = RAW_CLOCK_READS | frozenset({
    'pygame.key.get_pressed', 'pygame.key.get_mods', 'pygame.mouse.get_pos',
    'pygame.mouse.get_pressed', 'pygame.mouse.get_focused',
    'pygame.event.get', 'pygame.event.post', 'pygame.fastevent.get',
    'pygame.joystick.Joystick', 'pygame._sdl2.controller.Controller',
    'pygame.controller.Controller',
    # Device enumeration is part of the devices door too (spec 1.3)
    'pygame.joystick.get_count', 'pygame._sdl2.controller.get_count',
    'pygame._sdl2.controller.is_controller', 'pygame._sdl2.controller.name_forindex',
    'pygame.controller.get_count', 'pygame.controller.is_controller',
    'pygame.controller.name_forindex',
})

# Files (or directories, ending in '/') allowed to use each bypass, with the reason
ALLOWED_BYPASSES: dict[str, frozenset[str]] = {
    # The doors themselves
    'input/state.py': frozenset({'pygame.key.get_pressed', 'pygame.key.get_mods',
                                 'pygame.mouse.get_pos', 'pygame.mouse.get_pressed',
                                 'pygame.mouse.get_focused'}),
    'input/devices.py': frozenset({'pygame.joystick.Joystick', 'pygame.joystick.get_count',
                                   'pygame._sdl2.controller.Controller',
                                   'pygame._sdl2.controller.get_count',
                                   'pygame._sdl2.controller.is_controller',
                                   'pygame._sdl2.controller.name_forindex'}),
    'live_sources.py': frozenset({'pygame.event.get', 'pygame.fastevent.get', 'time.monotonic',
                                  'datetime.datetime.now'}),
    'replay/driver.py': frozenset({'pygame.event.get'}),  # drains the real queue during replay
    'recording.py': frozenset({'pygame.event.post'}),     # post_event, the one poster
    # Pacing measures the real run; logic gets frame time only through the frame-time door
    'timing.py': RAW_CLOCK_READS,
    'scenes/scene.py': frozenset({'time.perf_counter'}),  # SceneManager.start/_finish_frame
    # Performance statistics and the debug HUD describe the real run; never compared
    'performance/': RAW_CLOCK_READS,
    'debug/': RAW_CLOCK_READS,
    # The audio-glitch probe measures the real machine (scripts/audio_glitch_probe.py)
    'audio/diagnostics.py': RAW_CLOCK_READS,
    # The recording's own start stamp (header recorded_at, the replay wall clock's origin)
    'engine/game_engine.py': frozenset({'datetime.datetime.now'}),
    # Signs requests to a real server, which needs real time
    'api/client.py': frozenset({'time.time'}),
}


def _allowed(relative_path: str) -> frozenset[str]:
    allowed: set[str] = set()
    for location, names in ALLOWED_BYPASSES.items():
        if relative_path == location or (location.endswith('/') and
                                         relative_path.startswith(location)):
            allowed |= names
    return frozenset(allowed)


def door_bypasses(*, source_path: Path, allowed: frozenset[str] = frozenset()) -> list[str]:
    """Return 'line: name' for every bypass a module calls or references."""
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    bindings = import_bindings(tree=tree, watched_modules=WATCHED_DOOR_MODULES)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Name)):
            name = qualified_name(node=node, bindings=bindings,
                                  watched_modules=WATCHED_DOOR_MODULES)
            if name in DOOR_BYPASSES and name not in allowed:
                found.append(f'{node.lineno}: {name}')
    return sorted(set(found))


def test_package_reads_input_and_time_only_through_the_doors():
    offenders = {
        str(path.relative_to(PACKAGE)): bypasses
        for path in sorted(PACKAGE.rglob('*.py'))
        if (bypasses := door_bypasses(
            source_path=path, allowed=_allowed(path.relative_to(PACKAGE).as_posix())))
    }
    assert offenders == {}


OFFENDING_SOURCE = '''\
import time
import pygame
from pygame import key as keyboard
from datetime import datetime as clock

def poll():
    return pygame.key.get_pressed(), keyboard.get_mods(), time.time(), clock.now()

def measure():
    import time as time_module
    return time_module.perf_counter(), pygame.time.get_ticks()

def enumerate_devices():
    from pygame._sdl2 import controller as sdl2_controller
    return pygame.joystick.get_count(), sdl2_controller.is_controller(0)

def post():
    pygame.event.post(pygame.event.Event(pygame.USEREVENT))
'''


@pytest.fixture
def offending_file(tmp_path) -> Path:
    path = tmp_path / 'offending.py'
    path.write_text(OFFENDING_SOURCE, encoding='utf-8')
    return path


def test_scan_finds_every_kind(offending_file):
    names = {entry.split(': ', 1)[1] for entry in door_bypasses(source_path=offending_file)}
    assert names == {'pygame.key.get_pressed', 'pygame.key.get_mods', 'time.time',
                     'datetime.datetime.now', 'time.perf_counter', 'pygame.time.get_ticks',
                     'pygame.event.post', 'pygame.joystick.get_count',
                     'pygame._sdl2.controller.is_controller'}


def test_allowed_files_are_exact_paths_or_directories():
    assert _allowed('timing.py') == RAW_CLOCK_READS
    assert _allowed('performance/adaptive_clamping.py') == RAW_CLOCK_READS
    assert _allowed('bitmappy/editor.py') == frozenset()
```

(`qualified_name` must resolve `clock.now` through `from datetime import datetime as clock` and
`time_module.perf_counter` through a function-local `import time as time_module`; if the moved
helper does not, extend it in `tests/ast_scanning.py` and add the same cases to the randomness
guard's tests.)

- [ ] **Step 2: Run the guard to see it fail** — it lists every Bitmappy site in the table (and
  nothing else, since Task 8 moved the rest). Expected: `test_package_...` FAILS; the fixture tests
  pass once the helper resolves aliases.

- [ ] **Step 3: Move every Bitmappy site** per the table, e.g. `history/commands.py:104`:

```python
        # When the command was made (undo history); replays exactly (glitchygames/clock.py)
        self.timestamp: float = wall_clock_epoch_seconds()
```

`controllers/selection.py:282`:

```python
        return elapsed_seconds() - self.state.last_update_time
```

`film_strip_rendering.py:587` and `film_strip_events.py`: `frame_clock_milliseconds()` from
`glitchygames/clock.py` (Task 8 added it). Remove each `import time` the module no longer needs.

- [ ] **Step 4: Run the guard, every touched module's tests, `tests/world`, the full suite**

Run: `uv run pytest tests/test_engine_doors.py -q -p no:cacheprovider --no-cov`, then the Bitmappy
test folders (`tests/canvas`, the controller tests — find them with `grep -rln "controllers" tests`),
then the full suite. Expected: PASS, no warnings. Tests that patched `time.time` in a Bitmappy
module (`grep -rn "time.time\|'time'" tests/ | grep -i bitmappy`) must patch the clock export the
module now imports instead (`mocker.patch('glitchygames.bitmappy.<module>.elapsed_seconds',
...)`); keep each test's assertion unchanged.

- [ ] **Step 5: Lint, type-check, vulture, commit**

```bash
git add tests/ast_scanning.py tests/test_engine_doors.py tests/test_randomness.py <every modified glitchygames/bitmappy file from the table> <every test file you changed>
git commit -m "Move Bitmappy onto the clock exports and guard the package's doors"
```

---

### Task 10: Supervisor hook and control events

**Files:**
- Create: `glitchygames/supervision.py`
- Modify: `glitchygames/scenes/scene.py` — `SceneManager.__init__`, `_run_frame`,
  `_run_scene_frame` (the slot after `_process_events`), new methods `add_supervisor`,
  `remove_supervisor`, `record_control_event`, `add_control_event_handler`
- Modify: `glitchygames/sources.py` (`control_events_for_frame`; `end_frame` gets
  `control_events`)
- Modify: `tests/engine/test_engine_sources.py` (`ScriptedSources.end_frame` takes the new
  `control_events` keyword)
- Modify: `glitchygames/live_sources.py` (`control_events_for_frame` returns `[]`; `end_frame`
  takes `control_events`), `tests/test_clock.py` (`glitchygames.supervision` joins `DOOR_MODULES`)
- Test: `tests/world/test_frame_integration.py`

**Interfaces:**
- Produces (exact):

```python
class Supervisor(Protocol):
    def on_frame(self, *, frame_number: int, scene: Scene | None) -> None: ...
@dataclasses.dataclass(frozen=True)
class ControlEvent:
    kind: str
    data: dict[str, Any]
    def to_json(self) -> dict[str, Any]: ...          # {'kind': kind, **data}
    @classmethod
    def from_json(cls, record: dict[str, Any]) -> ControlEvent: ...
BREAKPOINT_KIND = 'breakpoint'
PLAYBACK_KIND = 'playback'
# Kinds a replay applies again on their frame (supervisor actions). Other kinds are markers
# the replayed code records again by itself (Part 3's playback scope); a replay compares them
# instead of applying them, so they are never doubled
REAPPLIED_CONTROL_EVENT_KINDS = frozenset({BREAKPOINT_KIND})
SceneManager.add_supervisor(*, supervisor) / remove_supervisor(*, supervisor)
SceneManager.record_control_event(*, kind: str, data: dict[str, Any]) -> None
SceneManager.add_control_event_handler(*, kind: str, handler: Callable[[ControlEvent], None]) -> None
EngineSources.control_events_for_frame(self, *, frame_number: int) -> list[ControlEvent]
EngineSources.end_frame(self, *, frame_number, dt, scene, control_events: list[ControlEvent]) -> None
```

Frame order (scene frames): `begin_frame → dt_tick → events → SUPERVISOR → frame services → aim →
position → render → still-camera shake → present`. Transition frames: `transition update →
events → SUPERVISOR → frame services → render → present`. At the slot the manager first takes
`active_sources().control_events_for_frame(frame_number=...)` and records each (so a replay
re-applies recorded control events on the same frame), then calls each supervisor in
registration order.

- [ ] **Step 1: Write the failing tests** (`tests/world/test_frame_integration.py`)

```python
class OrderRecordingSupervisor:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def on_frame(self, *, frame_number, scene) -> None:
        self.calls.append((frame_number, type(scene).__name__))


class TestSupervisorHook:
    def test_supervisors_run_once_per_frame_after_events(self, mocker):
        with running_scene(CameraFreeScene) as manager:
            supervisor = OrderRecordingSupervisor()
            manager.add_supervisor(supervisor=supervisor)
            order: list[str] = []
            mocker.patch.object(manager, '_process_events',
                                side_effect=lambda: order.append('events'))
            mocker.patch.object(manager, '_update_frame_services',
                                side_effect=lambda: order.append('services'))
            original_on_frame = supervisor.on_frame
            supervisor.on_frame = lambda **keywords: (order.append('supervisor'),
                                                      original_on_frame(**keywords))
            step(manager, frames=2)
        assert order == ['events', 'supervisor', 'services'] * 2
        assert supervisor.calls == [(0, 'CameraFreeScene'), (1, 'CameraFreeScene')]

    def test_removed_supervisor_is_not_called(self):
        with running_scene(CameraFreeScene) as manager:
            supervisor = OrderRecordingSupervisor()
            manager.add_supervisor(supervisor=supervisor)
            manager.remove_supervisor(supervisor=supervisor)
            step(manager, frames=1)
        assert supervisor.calls == []


class TestControlEvents:
    def test_recorded_control_events_reach_handlers_and_end_frame(self, mocker):
        from glitchygames.sources import active_sources
        from glitchygames.supervision import BREAKPOINT_KIND, ControlEvent

        handled: list[ControlEvent] = []
        with running_scene(CameraFreeScene) as manager:
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=handled.append)
            end_frame = mocker.spy(active_sources(), 'end_frame')
            manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'here'})
            step(manager, frames=1)
        assert handled == [ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'here'})]
        assert end_frame.call_args.kwargs['control_events'] == handled

    def test_scheduled_control_events_are_applied_at_the_slot(self, mocker):
        from glitchygames.sources import active_sources
        from glitchygames.supervision import BREAKPOINT_KIND, ControlEvent

        scheduled = ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'from recording'})
        handled: list[ControlEvent] = []
        with running_scene(CameraFreeScene) as manager:
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=handled.append)
            mocker.patch.object(active_sources(), 'control_events_for_frame',
                                side_effect=lambda frame_number: [scheduled] if frame_number == 1
                                else [])
            step(manager, frames=3)
        assert handled == [scheduled]

    def test_control_event_json_round_trip(self):
        from glitchygames.supervision import ControlEvent

        event = ControlEvent(kind='breakpoint', data={'label': 'x'})
        assert event.to_json() == {'kind': 'breakpoint', 'label': 'x'}
        assert ControlEvent.from_json(event.to_json()) == event
```

- [ ] **Step 2: Run to see them fail** — Expected: `AttributeError: ... add_supervisor`.

- [ ] **Step 3: Implement**

`glitchygames/supervision.py`:

```python
"""The supervisor hook and control events.

A supervisor is called once per frame at a fixed place in the frame (after logic and events,
before frame services, camera aim and positioning — see SceneManager._run_scene_frame), so what
it reads is the frame's final logic state and what it changes is drawn this frame and seen by
collision next frame. Replay controls and recorded breakpoints use it today; a future cheat device
plugs in here (plans/2026-10-19-gameplay-replay.md, section 2).

A control event is a supervisor action recorded with the frame it happened in; a replay
re-applies recorded control events on the same frame, so sessions with supervisor actions replay
exactly.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Protocol, Self

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

BREAKPOINT_KIND = 'breakpoint'
PLAYBACK_KIND = 'playback'
KIND_FIELD = 'kind'
# Kinds a replay applies again on their frame (supervisor actions); every other kind is a
# marker the replayed code records again by itself, which a replay compares instead
REAPPLIED_CONTROL_EVENT_KINDS = frozenset({BREAKPOINT_KIND})


class Supervisor(Protocol):
    """Called once per frame at the supervisor slot."""

    def on_frame(self, *, frame_number: int, scene: Scene | None) -> None: ...


@dataclasses.dataclass(frozen=True)
class ControlEvent:
    """A recorded supervisor action: its kind and JSON-safe data."""

    kind: str
    data: dict[str, Any]

    def to_json(self: Self) -> dict[str, Any]:
        """Return ``{'kind': kind, **data}``."""
        return {KIND_FIELD: self.kind, **self.data}

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> ControlEvent:
        """Read a record written by ``to_json``."""
        data = {name: value for name, value in record.items() if name != KIND_FIELD}
        return cls(kind=str(record[KIND_FIELD]), data=data)
```

`SceneManager.__init__`: `self._supervisors: list[Supervisor] = []`,
`self._control_event_handlers: dict[str, list[Callable[[ControlEvent], None]]] = {}`,
`self._frame_control_events: list[ControlEvent] = []`. Methods:

```python
    def add_supervisor(self: Self, *, supervisor: Supervisor) -> None:
        """Call ``supervisor`` once per frame at the supervisor slot (supervision.py)."""
        self._supervisors.append(supervisor)

    def remove_supervisor(self: Self, *, supervisor: Supervisor) -> None:
        """Stop calling ``supervisor``; unknown supervisors are ignored."""
        if supervisor in self._supervisors:
            self._supervisors.remove(supervisor)

    def add_control_event_handler(
        self: Self, *, kind: str, handler: Callable[[ControlEvent], None]
    ) -> None:
        """Call ``handler`` for every control event of ``kind`` (live or replayed)."""
        self._control_event_handlers.setdefault(kind, []).append(handler)

    def record_control_event(self: Self, *, kind: str, data: dict[str, Any]) -> None:
        """Record a supervisor action in this frame and hand it to its handlers."""
        control_event = ControlEvent(kind=kind, data=data)
        self._frame_control_events.append(control_event)
        for handler in self._control_event_handlers.get(kind, []):
            handler(control_event)

    def _run_supervisor_slot(self: Self) -> None:
        """Apply this frame's scheduled control events, then call every supervisor."""
        for control_event in active_sources().control_events_for_frame(
            frame_number=self.frame_number
        ):
            self.record_control_event(kind=control_event.kind, data=control_event.data)
        for supervisor in list(self._supervisors):
            supervisor.on_frame(frame_number=self.frame_number, scene=self.active_scene)
```

Call `self._run_supervisor_slot()` right after `self._process_events()` in `_run_scene_frame`
(update its docstring and the ordering comment block) and right after
`self._process_transition_events()` in `_run_frame`'s transition branch. In `_run_frame` pass
`control_events=self._frame_control_events` to `end_frame` and then reset
`self._frame_control_events = []`. Sources: add `control_events_for_frame` (Live returns `[]`) and
the `control_events` parameter to `end_frame` (`LiveSources` in `live_sources.py` ignores it).

- [ ] **Step 4: Run** `tests/world`, `tests/scenes`, `tests/engine`, golden. Expected: PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/supervision.py glitchygames/scenes/scene.py glitchygames/sources.py glitchygames/live_sources.py tests/engine/test_engine_sources.py tests/test_clock.py tests/world/test_frame_integration.py
git commit -m "Add the supervisor slot and recorded control events to the frame"
```

---

### Task 11: `RecordingSources`

**Files:**
- Modify: `glitchygames/recording.py` (`RecordingSources`; `GameplayRecorder.record_frame` gains
  the format-3 fields; module docstring)
- Modify: `glitchygames/engine/game_engine.py:1118-1155` (`start_trace_recording` /
  `stop_trace_recording` install and finish `RecordingSources`), `:1380-1406` (`_pump_events`: the
  recorder check moves into the sources)
- Modify: `glitchygames/scenes/scene.py:872-898` (remove the direct `trace_recorder.record_frame`
  call; `end_frame` does it)
- Modify: `tests/world/test_finish_frame.py` (the recorder test reaches the recorder through the
  sources)
- Modify: `scripts/record_golden_traces.py` (`record_trace(..., before_recording=None)`: a callable
  given the game scene after it is installed and before recording starts; keyword-only, default
  None, so existing callers are unchanged)
- Modify: `tests/conftest.py` (`reset_engine_sources` also calls `reset_internal_post_tracking()`)
- Test: `tests/world/test_gameplay_recording.py`, `tests/test_recording.py`

**Interfaces:**
- Consumes: Tasks 2–10.
- Produces:

```python
class RecordingSources:   # implements EngineSources, wraps another
    def __init__(self, *, inner: EngineSources, recorder: GameplayRecorder) -> None: ...
    inner: EngineSources
GameplayRecorder.record_frame(self, *, dt: float, scene: Scene | None,
                              input_changes: dict[str, Any] | None = None,
                              control_events: list[dict[str, Any]] | None = None,
                              devices_opened: list[dict[str, Any]] | None = None,
                              saves_opened: dict[str, Any] | None = None,
                              device_enumeration: list[dict[str, Any]] | None = None) -> None
GameEngine.start_trace_recording(self, *, path: Path) -> GameplayRecorder   # unchanged signature
def start_tracking_internal_posts() -> None    # recording.py: one more owner of the tracker
def stop_tracking_internal_posts() -> None     # one owner fewer; tracking stops at zero owners
def reset_internal_post_tracking() -> None     # zero owners, nothing pending (tests, new run)
def pending_internal_posts() -> list[tuple[int, dict[str, Any]]]   # the tracker's unmatched posts
```

Rules:
- `start_trace_recording` builds the header (`trace_recording_header()` plus
  `saves`: `{namespace: save_namespace_snapshot(saves=store)}` for every store the inner sources
  opened so far, `devices`: descriptors of devices opened so far
  (`inner.devices().take_opened_descriptors()`) and `device_enumeration`: enumeration answers given
  so far (`take_enumeration_answers()`)), creates the recorder and installs
  `RecordingSources(inner=<the active sources>, recorder=recorder)` (before the first frame — the
  golden harness and `GameEngine.start` both start recording before frames run). When the inner
  sources are a `ReplaySources` (`--rebaseline`, Part 2), the header's `saves`, `devices` and
  `device_enumeration` are copied from the source recording's header instead (Part 2 Task 6's
  `rebaseline_header`), and each frame's `saves_opened`, `devices_opened` and
  `device_enumeration` are copied from the source recording's frame
  (`ReplaySources.recorded_frame_fields(...)`, Task 12) — the replay's doors serve those, so they
  are the run's inputs.
- Internal-post tracking has owners: `GameplayRecorder.__init__` calls
  `start_tracking_internal_posts()` and `close()` calls `stop_tracking_internal_posts()` (replacing
  the direct `_INTERNAL_POSTS.is_tracking = ...` writes), and a `ReplaySources` owns it from
  `on_installed` to `on_uninstalled` (Task 12), so closing a recorder never switches tracking off
  under a live replay. `reset_internal_post_tracking()` is called by the `reset_engine_sources`
  fixture in `tests/conftest.py` and by `GameEngine.__init__` next to `reset_sources()`.
- `pump_events`: the inner batch, recorded with `record_event_batch` (moved from
  `_pump_events`). Origins: live inner sources → classified with the tracker, as today; a
  `ReplaySources` inner → taken from the replay's own merge (`inner.last_batch_origins()`, Task 12):
  served recorded events are external by construction and the merged live events internal, so the
  recorder never re-classifies them. `record_event_batch` gains an optional keyword
  `origins: list[str] | None = None` for that.
- `input_snapshot`: inner snapshot; remember the changes from the previous frame's snapshot for
  this frame (first snapshot diffs against `IDLE_INPUT`).
- `saves(namespace)`: inner store; a namespace opened after recording started is snapshotted into
  this frame's `saves_opened` before the game can write to it.
- `devices()`: inner registry; `end_frame` takes `take_opened_descriptors()` into
  `devices_opened` and `take_enumeration_answers()` into `device_enumeration`.
- `end_frame`: `recorder.record_frame(...)` with the frame's fields; then delegate to
  `inner.end_frame(...)`.
- `frame_seconds`, `control_events_for_frame`, `stop_requested`, `random_seed`,
  `wall_clock_time`, `elapsed_seconds`: delegate.

- [ ] **Step 1: Write the failing tests** (append to `TestRecordingThroughTheEngine` in
  `tests/world/test_gameplay_recording.py`, using `engine_run_environment`, `run_engine` and
  `Script`)

```python
    def test_recording_holds_input_changes_and_control_events(self, mocker, tmp_path):
        from glitchygames.supervision import BREAKPOINT_KIND
        from glitchygames.recording import CONTROL_EVENTS_FIELD, INPUT_CHANGES_FIELD

        recording_path = tmp_path / 'session.jsonl.gz'
        # engine_run_environment resets Script, so the script is set inside it
        with engine_run_environment(mocker):
            Script.events_by_frame = {1: [_key(pygame.KEYDOWN, pygame.K_a, unicode='a')],
                                      2: [_key(pygame.KEYUP, pygame.K_a)]}
            Script.action_frame = 1
            Script.action = lambda: SceneManager().record_control_event(
                kind=BREAKPOINT_KIND, data={'label': 'scripted'})
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
        trace = read_trace_result(path=recording_path).trace
        frames = trace['frames']
        assert frames[1][CONTROL_EVENTS_FIELD] == [{'kind': 'breakpoint', 'label': 'scripted'}]
        assert all(CONTROL_EVENTS_FIELD not in frame for frame in frames if frame['frame'] != 1)
        # Keys posted to pygame's real queue update its key state at the pump; the dummy video
        # driver may not, so only assert the field's form, not the scancode
        assert all(isinstance(frame.get(INPUT_CHANGES_FIELD, {}), dict) for frame in frames)

    def test_saves_opened_after_recording_started_are_snapshotted_in_their_frame(
        self, mocker, tmp_path
    ):
        from glitchygames.state import SaveManager
        from glitchygames.state.sandbox import open_saves

        save_directory = tmp_path / 'saves'
        mocker.patch('glitchygames.state.manager.get_save_directory',
                     side_effect=lambda app_name: save_directory / app_name)
        SaveManager(app_name='recording-test').save('high_scores', {'scores': [{'score': 900}]})
        recording_path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            Script.action_frame = 0
            Script.action = lambda: open_saves(app_name='recording-test')
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
        frames = read_trace_result(path=recording_path).trace['frames']
        # Opened in frame 0, after recording started: snapshotted into that frame
        (opened,) = [frame['saves_opened'] for frame in frames if 'saves_opened' in frame]
        assert opened['recording-test']['high_scores']['data'] == {'scores': [{'score': 900}]}
        assert frames[0]['frame'] == 0 and 'saves_opened' in frames[0]

    def test_saves_opened_before_recording_are_in_the_header(self, tmp_path):
        recording_path = tmp_path / 'session.jsonl.gz'

        def write_a_score(scene) -> None:
            # PaddleSlap opened its saves in __init__, before recording starts
            scene.saves.save('high_scores', {'scores': [{'score': 7}]})

        record_trace('paddleslap', frame_count=2, recording_path=recording_path,
                     before_recording=write_a_score)
        header = read_trace_result(path=recording_path).trace
        assert header['saves']['paddleslap']['high_scores']['data'] == {'scores': [{'score': 7}]}

    def test_devices_opened_are_recorded(self, mocker, tmp_path):
        from glitchygames.sources import active_sources
        from glitchygames.input import devices as devices_module

        fake_device = mocker.Mock(**{
            'get_instance_id.return_value': 5, 'get_name.return_value': 'Fake Pad',
            'get_guid.return_value': 'guid', 'get_numaxes.return_value': 2,
            'get_numbuttons.return_value': 4, 'get_numhats.return_value': 1,
            'get_numballs.return_value': 0,
        })
        mocker.patch.object(devices_module.pygame.joystick, 'Joystick', return_value=fake_device)
        recording_path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            Script.action_frame = 1
            Script.action = lambda: active_sources().devices().open_joystick(device_index=0)
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
        frames = read_trace_result(path=recording_path).trace['frames']
        assert frames[1]['devices_opened'] == [{
            'kind': 'joystick', 'device_index': 0, 'instance_id': 5, 'name': 'Fake Pad',
            'guid': 'guid', 'axis_count': 2, 'button_count': 4, 'hat_count': 1, 'ball_count': 0,
        }]
```

(`Script.action` runs in the departure scene's `dt_tick` of `action_frame`; add `record_trace` to
the file's import from `scripts.record_golden_traces` if it is not imported yet — it is.)

In `tests/test_recording.py`:

```python
def test_recording_sources_write_only_non_empty_fields(tmp_path, mocker):
    from glitchygames.live_sources import LiveSources
    from glitchygames.recording import GameplayRecorder, RecordingSources
    from glitchygames.supervision import ControlEvent
    from glitchygames.tracing import read_trace_result

    path = tmp_path / 'unit.jsonl.gz'
    recorder = GameplayRecorder(path=path, header={'game_class': 'Unit'})
    sources = RecordingSources(inner=LiveSources(random_seed=1), recorder=recorder)
    sources.end_frame(frame_number=0, dt=0.016, scene=None, control_events=[])
    sources.end_frame(frame_number=1, dt=0.016, scene=None,
                      control_events=[ControlEvent(kind='breakpoint', data={'label': 'b'})])
    recorder.close()
    first, second = read_trace_result(path=path).trace['frames']
    assert 'control_events' not in first
    assert second['control_events'] == [{'kind': 'breakpoint', 'label': 'b'}]
```

`tests/world/test_finish_frame.py::test_trace_recorder_gets_the_dt_logic_received_once_per_frame`
sets `manager.trace_recorder` and expects `record_frame` calls; after this task the recorder is
reached through the sources. Update that test to install
`RecordingSources(inner=LiveSources(random_seed=1), recorder=recorder)` (with the `Mock` recorder)
and assert on `recorder.record_frame` the same way — the assertion (one call per frame with the
dt logic received) is unchanged.

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement** `RecordingSources` per the rules above (full docstrings; JSON-safe
  values only — device descriptors via `to_json()`, control events via `to_json()`, saves via
  `save_namespace_snapshot`), extend `GameplayRecorder.record_frame` to write each field only when
  non-empty (constants from Task 1), remove the recorder check from `_pump_events` and the direct
  `record_frame` call from `_run_frame` (keep `frame_dt` for `end_frame`), and make
  `stop_trace_recording` uninstall nothing (the run is ending) but close the recorder. Keep
  `GameEngine.trace_recorder` / `SceneManager.trace_recorder` attributes: tests and the harness
  read them (`grep -rn trace_recorder tests scripts`); `SceneManager.trace_recorder` may become
  unused in `scene.py` — if vulture flags it, keep it only if tests use it, otherwise remove it and
  its tests' references.

Update the `recording.py` module docstring: the per-frame and header fields of format version 3
(the five fields and two header fields, with their meaning), and remove "Polled input ... is not
recorded" (it is now) — say instead that polled input is recorded as `input_changes`.

- [ ] **Step 4: Run** `tests/world/test_gameplay_recording.py tests/test_recording.py tests/world`.
  The existing recording tests must pass unchanged except where they assert the absence of the new
  fields. Golden unchanged.

- [ ] **Step 5: Lint, type-check, full suite, commit**

```bash
git add glitchygames/recording.py glitchygames/engine/game_engine.py glitchygames/scenes/scene.py scripts/record_golden_traces.py tests/conftest.py tests/world/test_gameplay_recording.py tests/world/test_finish_frame.py tests/test_recording.py
git commit -m "Record through the doors: RecordingSources writes input, devices, saves, control events"
```

---

### Task 12: `ReplaySources`: startup, the replay doors and frame comparison

**Files:**
- Create: `glitchygames/replay/__init__.py` (exports), `glitchygames/replay/driver.py`
- Modify: `glitchygames/engine/game_engine.py` — `args` (diagnostics group: `--replay-trace`),
  `__init__` (the one startup path, rule 1), `_shutdown` (log the result)
- Modify: `glitchygames/recording.py` (`start_tracking_internal_posts` /
  `stop_tracking_internal_posts` used by `ReplaySources.on_installed` / `on_uninstalled`)
- Modify: `scripts/record_golden_traces.py` (`_golden_game` context manager shared by
  `record_trace` and the new `replay_golden_recording`; `_start_game(..., extra_arguments=None)`)
- Modify: `tests/test_clock.py` (`glitchygames.replay.driver` joins `DOOR_MODULES`)
- Test: `tests/world/test_gameplay_replay.py` (new)

**Interfaces:**
- Consumes: everything above.
- Produces (exact):

```python
REPLAY_UNUSABLE_EXIT_CODE = 2
REPLAY_LOCAL_OPTIONS: frozenset[str]   # options the recording never overrides
SPRITE_DIVERGENCE = 'sprite'; EVENT_DIVERGENCE = 'event'; LENGTH_DIVERGENCE = 'length'
class ReplayRefusedError(RuntimeError): ...
@dataclasses.dataclass(frozen=True)
class Divergence:
    frame_number: int      # the recording's frame index
    kind: str              # SPRITE_DIVERGENCE | EVENT_DIVERGENCE | LENGTH_DIVERGENCE
    subject: str
    field: str
    expected: object
    actual: object
    def describe(self) -> str: ...
@dataclasses.dataclass
class ReplayResult:
    frames_replayed: int = 0
    divergence: Divergence | None = None
    end_reason: str = 'running'   # 'running' | 'end_of_recording' | 'diverged' | 'truncated' | 'quit'
class ReplaySources:   # EngineSources
    def __init__(self, *, header: dict[str, Any], frames: Sequence[dict[str, Any]],
                 format_version: int, is_truncated: bool = False) -> None: ...
    @classmethod
    def from_path(cls, *, path: Path) -> ReplaySources: ...
    header: dict[str, Any]
    result: ReplayResult
    def check_game(self, *, game_class_name: str) -> None: ...   # raises ReplayRefusedError
    def pump_events(self, *, real_events: list[pygame.event.Event] | None = None
                    ) -> list[pygame.event.Event]: ...           # real_events: Part 3 scopes
    def last_batch_origins(self) -> list[str]: ...              # Task 11's recorder over a replay
    def recorded_frame_fields(self, *, frame_index: int) -> dict[str, Any]: ...   # rebaseline
def apply_recorded_options(*, options: dict[str, Any], recorded: dict[str, Any]) -> None: ...
def start_replay(*, path: Path, game_class_name: str, options: dict[str, Any]) -> ReplaySources: ...
GameEngine.replay_sources: ReplaySources | None
def replay_golden_recording(*, game_key: str, path: Path) -> ReplayResult   # the harness
```

Replay rules (implement exactly; they are what makes the replay exact):

1. **Startup, in one place** (`GameEngine.__init__`): options are parsed
   (`initialize_arguments`); if `options['replay_trace']` is set,
   `self.replay_sources = start_replay(path=..., game_class_name=..., options=options)`, which reads
   the recording (`ReplaySources.from_path`), runs `check_game` (header `game_class` vs the game's
   class name — `game.__name__` for a class, `type(game).__name__` for an instance; mismatch →
   `ReplayRefusedError`), applies the recorded options (`apply_recorded_options`: every recorded
   option except `REPLAY_LOCAL_OPTIONS` = `{'replay_trace', 'record_trace', 'audit',
   'replay_digest', 'headless', 'rebaseline', 'replay_pause_at_frame', 'profile', 'log_level',
   'windowed', 'video_driver', 'debug_overlay', 'log_timer_jitter', 'timer_backend',
   'sleep_granularity_ns', 'windows_timer_1ms', 'perf_trim_percent', 'fps_histogram'}` into
   `GameEngine.OPTIONS` and `options`), seeds with `seed_engine_random(seed=header['random_seed'])`
   and returns the sources **without installing them**. Otherwise `self.replay_sources = None`.
   `self.random_seed` is the replay's seed when replaying, else `seed_engine_random(...)` as today.
   Task 2's block then installs `self.replay_sources or LiveSources(...)` before the first frame;
   `install_sources` calls `on_installed()`, where `ReplaySources` starts internal-post tracking
   (`start_tracking_internal_posts()`); `on_uninstalled()` (from `reset_sources()`) stops it. A
   different `engine_version` logs one warning. `ReplayRefusedError` (and `TraceFormatError` from
   reading) → log the message at ERROR and `raise SystemExit(REPLAY_UNUSABLE_EXIT_CODE)`.
2. **Pump** (this task's form; Task 13 makes the merge exact): drain the real queue with
   `pygame.event.get()` (or take `real_events` when given — a Part 3 playback scope passes the
   base pump's batch); real external events are dropped, except `pygame.QUIT` (window close), kept
   as the last event so closing the window ends the replay; live internal events are passed
   through after the recorded batch; serve the recording's batch for this pump: its `external`
   records via `event_from_record`. Remember each served event's origin for
   `last_batch_origins()` (recorded events `external`, passed-through ones `internal`).
3. **Frame indexes**: `ReplaySources` counts its own `end_frame` calls (`frame_index`, from 0);
   every recorded frame it serves — batches, `dt`, input, devices, saves, control events — is
   indexed by that counter, never by the `frame_number` the scene manager passes (inside a Part 3
   playback scope the session's frame numbers do not start at 0). The passed number is only used
   in log messages.
4. **Frame time** (`frame_seconds`): the first call returns frame 0's `dt`; each later call returns
   the next frame's `dt`; past the end, `measured`.
5. **Input** (`input_snapshot`): the current frame's snapshot, rebuilt by applying each frame's
   `input_changes` in order (format version 2 → `IDLE_INPUT` and one warning: "recorded before
   input-state capture; polled input will read as idle").
6. **Devices** (`devices()`): a `ReplayDeviceRegistry(descriptors=<header devices>,
   enumeration_answers=<header device_enumeration>)`, learning each frame's `devices_opened` and
   `device_enumeration` at that frame's first pump.
7. **Saves** (`saves(namespace)`): `SandboxSaves(app_name=namespace, envelopes=...)` from the
   header's `saves` (or the frame's `saves_opened`); unknown namespace → empty sandbox.
8. **End of frame** (`end_frame`): sample with `sample_scene_frame` and the sources' own
   `StableSpriteIds`; compare `scene` and then sprites in order with the recorded frame (first
   difference only: a missing or extra sprite id → `field='present'`; else `rect` then `visible`);
   record `frames_replayed`; on a divergence or after the last recorded frame set
   `stop_requested` and `end_reason` (`'truncated'` when the file was cut off).
9. **Clocks** (Task 8): `wall_clock_time()` is the header's `recorded_at`
   (`datetime.datetime.fromisoformat`, made UTC-aware if the string has no offset) plus
   `timedelta(seconds=frame_clock_seconds())`; `elapsed_seconds()` is `frame_clock_seconds()`.
10. **Recorded fields for a rebaseline**: `recorded_frame_fields(frame_index=n)` returns frame
    n's `saves_opened`, `devices_opened` and `device_enumeration` (whichever exist).
11. **End of run**: `GameEngine._shutdown` logs `result.divergence.describe()` at ERROR or "Replay
    matched N frames" at INFO.

`Divergence.describe()` format: `"frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got
[412, 301, 16, 16]"`.

- [ ] **Step 1: Write the failing tests** (`tests/world/test_gameplay_replay.py`)

```python
"""Replays through the real engine: record a session, replay it, compare every frame."""

from __future__ import annotations

import zlib
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest
from scripts.record_golden_traces import GAME_SCENES, record_trace, replay_golden_recording

from glitchygames.recording import RECORDING_FORMAT_THREE_FIELDS
from glitchygames.replay.driver import (
    REPLAY_UNUSABLE_EXIT_CODE,
    SPRITE_DIVERGENCE,
)
from glitchygames.tracing import GZIP_WINDOW_BITS, read_trace_result, write_trace
from tests.world.test_gameplay_recording import (
    RANDOM_SEED,
    Script,
    _key,
    _schedule_quit_in_arrival,
    engine_run_environment,
    run_engine,
)

if TYPE_CHECKING:
    from collections.abc import Callable

GOLDEN_SCRIPT_FRAMES = 300


def record_session(*, tmp_path: Path, mocker, action: Callable[[], None] | None = None,
                   action_frame: int = 1) -> Path:
    """Record the departure/arrival scripted session (with an optional scripted action)."""
    recording_path = tmp_path / 'session.jsonl.gz'
    # engine_run_environment resets Script, so the script is set inside it
    with engine_run_environment(mocker):
        Script.events_by_frame = {1: [_key(pygame.KEYDOWN, pygame.K_a, unicode='a')],
                                  2: [_key(pygame.KEYUP, pygame.K_a)]}
        Script.action, Script.action_frame = action, action_frame
        _schedule_quit_in_arrival()
        run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
    return recording_path


def replay_session(*, recording_path: Path, mocker,
                   events_by_frame: dict[int, list[pygame.event.Event]] | None = None,
                   action: Callable[[], None] | None = None, action_frame: int = 1):
    """Replay through the real engine.

    The test scenes post their scripted input with raw pygame.event.post, so the recording holds
    it as external events and the replay serves it from the recording: by default the scenes post
    nothing during the replay. `events_by_frame` makes them post real events anyway (they must be
    dropped); `action` repeats a scripted action that is not input (a save write, a control event).
    """
    with engine_run_environment(mocker):
        Script.events_by_frame = events_by_frame or {}
        Script.action, Script.action_frame = action, action_frame
        engine = run_engine('--replay-trace', str(recording_path))
    return engine


def rewrite_recording(*, recording_path: Path, change: Callable[[dict], None]) -> None:
    """Read a recording, let `change` edit the in-memory trace, write it back (format 3)."""
    trace = read_trace_result(path=recording_path).trace
    change(trace)
    write_trace(trace=trace, path=recording_path)


def tamper_first_sprite_rect(*, recording_path: Path, frame_number: int) -> None:
    """Move the first sprite 1 px down from `frame_number` on."""
    def move(trace: dict) -> None:
        for frame in trace['frames'][frame_number:]:
            if frame['sprites']:
                frame['sprites'][0]['rect'][1] += 1
    rewrite_recording(recording_path=recording_path, change=move)


def cut_off_after_frame(*, recording_path: Path, frame_number: int) -> None:
    """Keep the header and frames 0..frame_number, then half of the next line, with no gzip
    end-of-stream (what a killed recorder leaves)."""
    lines = gzip_lines(recording_path=recording_path)
    partial_line = lines[frame_number + 2]
    kept = b''.join(lines[: frame_number + 2]) + partial_line[: len(partial_line) // 2]
    compressor = zlib.compressobj(wbits=GZIP_WINDOW_BITS)
    recording_path.write_bytes(compressor.compress(kept) + compressor.flush(zlib.Z_SYNC_FLUSH))


def gzip_lines(*, recording_path: Path) -> list[bytes]:
    import gzip

    with gzip.open(recording_path, 'rb') as recording_file:
        return recording_file.readlines()


def downgrade_to_version_two(*, recording_path: Path) -> None:
    """Drop the format-3 fields and write the file as format version 2."""
    import gzip
    import json

    trace = read_trace_result(path=recording_path).trace
    for frame in trace['frames']:
        for field in RECORDING_FORMAT_THREE_FIELDS:
            frame.pop(field, None)
    write_trace(trace=trace, path=recording_path)
    lines = gzip_lines(recording_path=recording_path)
    header = json.loads(lines[0])
    header['format_version'] = 2
    for field in ('saves', 'devices', 'device_enumeration'):
        header.pop(field, None)
    with gzip.open(recording_path, 'wb') as recording_file:
        recording_file.write((json.dumps(header) + '\n').encode('utf-8'))
        recording_file.writelines(lines[1:])


class TestRoundTrip:
    def test_scripted_session_replays_without_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        result = engine.replay_sources.result
        assert result.divergence is None
        assert result.end_reason == 'end_of_recording'

    @pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
    def test_golden_script_recording_replays_without_divergence(self, game_key, tmp_path):
        recording_path = tmp_path / f'{game_key}.jsonl.gz'
        record_trace(game_key, frame_count=GOLDEN_SCRIPT_FRAMES, recording_path=recording_path)
        result = replay_golden_recording(game_key=game_key, path=recording_path)
        assert result.divergence is None
        assert result.frames_replayed == GOLDEN_SCRIPT_FRAMES

    def test_clock_reads_replay_exactly(self, mocker, tmp_path):
        from glitchygames.clock import elapsed_seconds, wall_clock_epoch_seconds

        def place_marker_from_clocks() -> None:
            scene = SceneManager().active_scene
            marker = next(iter(scene.all_sprites))
            marker.rect.x = int(wall_clock_epoch_seconds()) % 1000
            marker.rect.y = int(elapsed_seconds() * 1000) % 1000

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker,
                                        action=place_marker_from_clocks, action_frame=3)
        mocker.patch('glitchygames.live_sources.datetime')  # the replay must not read real time
        engine = replay_session(recording_path=recording_path, mocker=mocker,
                                action=place_marker_from_clocks, action_frame=3)
        assert engine.replay_sources.result.divergence is None


class TestDivergence:
    def test_a_one_pixel_change_is_reported_at_its_frame(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        assert (divergence.frame_number, divergence.kind, divergence.field) == (
            3, SPRITE_DIVERGENCE, 'rect')


class TestRefusals:
    def test_wrong_game_is_refused(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        rewrite_recording(recording_path=recording_path,
                          change=lambda trace: trace.update(game_class='SomeOtherGame'))
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=recording_path, mocker=mocker)
        assert exit_info.value.code == REPLAY_UNUSABLE_EXIT_CODE

    def test_truncated_recording_replays_to_the_cut_off(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources.result.end_reason == 'truncated'
        assert engine.replay_sources.result.frames_replayed == 3

    def test_version_two_recording_replays_with_a_warning(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        downgrade_to_version_two(recording_path=recording_path)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources.result.divergence is None
        assert 'polled input will read as idle' in caplog.text


class TestSaves:
    def test_replay_never_writes_real_saves(self, mocker, tmp_path):
        from glitchygames.state import SaveManager
        from glitchygames.state.sandbox import open_saves

        save_directory = tmp_path / 'saves'
        mocker.patch('glitchygames.state.manager.get_save_directory',
                     side_effect=lambda app_name: save_directory / app_name)
        SaveManager(app_name='replay-test').save('slot', {'value': 1})

        def write_slot() -> None:
            open_saves(app_name='replay-test').save('slot', {'value': 2})

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker, action=write_slot)
        SaveManager(app_name='replay-test').save('slot', {'value': 1})  # undo the live write
        slot_file = next((save_directory / 'replay-test').iterdir())
        bytes_before = slot_file.read_bytes()
        engine = replay_session(recording_path=recording_path, mocker=mocker, action=write_slot)
        assert engine.replay_sources.result.divergence is None
        assert slot_file.read_bytes() == bytes_before
```

(Add `from glitchygames.scenes import SceneManager` to the imports. `RECORDING_FORMAT_THREE_FIELDS`
is a new tuple in `recording.py` naming the per-frame fields of Task 1 and Task 5. The
`mocker.patch('glitchygames.live_sources.datetime')` line makes the test fail if anything in the
replay still reaches the live wall clock. `test_clock_reads_replay_exactly` uses the departure
scene's marker sprite — read `DepartureRecordedScene` and use its sprite attribute by name instead
of `next(iter(...))` if it has one.)

`scripts/record_golden_traces.py` — factor the setup `record_trace` already has into one context
manager, then use it in both:

```python
@contextlib.contextmanager
def _golden_game(game_key: str, *, random_seed: int,
                 extra_arguments: list[str] | None = None) -> Generator[GoldenTraceSceneManager]:
    """Start a game in the harness with temporary saves; tear it all down afterwards."""
    clock = FakeClock(start_seconds=FAKE_CLOCK_START_SECONDS)
    with (
        tempfile.TemporaryDirectory(prefix='golden-trace-saves-') as save_directory,
        deterministic_environment(clock=clock, save_root=Path(save_directory)),
    ):
        manager = _start_game(game_key, random_seed=random_seed,
                              extra_arguments=extra_arguments)
        try:
            yield manager
        finally:
            engine = manager.game_engine
            if engine is not None:
                engine.stop_trace_recording()
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()


def replay_golden_recording(*, game_key: str, path: Path) -> ReplayResult:
    """Replay a recording made by record_trace(recording_path=...) through the harness.

    Key events and per-frame input come from the recording (the replay's event pump), so they
    are not posted again. The script's placements are not input — they move sprites directly,
    like a supervisor — so they are applied again on the same frames, before the frame runs, as
    record_trace applies them.
    """
    script = SCRIPT_BUILDERS[game_key]()
    with _golden_game(game_key, random_seed=RANDOM_SEED,
                      extra_arguments=['--replay-trace', str(path)]) as manager:
        sources = manager.game_engine.replay_sources
        frame_number = 0
        while not sources.stop_requested and manager.active_scene is not None:
            manager.dt = sources.frame_seconds(measured=FRAME_SECONDS)
            for placement in script.placements.get(frame_number, []):
                placement(manager.active_scene)
            manager.run_frame()
            frame_number += 1
    return sources.result
```

`record_trace` keeps its signature and behaviour but uses `_golden_game` (and still advances its
own `clock` — pass it in through `_golden_game` if `record_trace` needs the same `FakeClock`
object: make `_golden_game` yield `(manager, clock)` in that case). If Task 8 removed the `clock`
parameter of `deterministic_environment`, drop it here too. `manager.dt` is set from the frame-time
door because the harness steps frames without `start()`/`_finish_frame`; the first call returns
frame 0's `dt`, each later call the next frame's (rule 4).

- [ ] **Step 2: Run to see them fail** — Expected: `ModuleNotFoundError: glitchygames.replay`.

- [ ] **Step 3: Implement `glitchygames/replay/driver.py`** following rules 1–11 (module docstring
  restating them briefly; every public item documented), the `--replay-trace` option:

```python
        group.add_argument(
            '--replay-trace',
            metavar='PATH',
            help=(
                'replay a --record-trace recording exactly through the engine, comparing every '
                'frame with it and reporting the first divergence (default: off)'
            ),
            default=None,
        )
```

  and the `GameEngine.__init__` / `_shutdown` integration.

- [ ] **Step 4: Run** `tests/world/test_gameplay_replay.py`, then `tests/world`, `tests/engine`,
  `tests/test_clock.py`, the golden test and the full suite. Expected: PASS, no warnings.

- [ ] **Step 5: Lint, type-check, vulture, commit**

```bash
git add glitchygames/replay/__init__.py glitchygames/replay/driver.py glitchygames/engine/game_engine.py glitchygames/recording.py scripts/record_golden_traces.py tests/test_clock.py tests/world/test_gameplay_replay.py
git commit -m "Replay recordings through the engine with --replay-trace and compare every frame"
```

---

### Task 13: Exact event merging, references and control-event markers

**Files:**
- Modify: `glitchygames/replay/driver.py` (rule 2 exact merge; references; markers)
- Test: `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Consumes: Task 12, `REAPPLIED_CONTROL_EVENT_KINDS` (Task 10), `event_origin` /
  `pending_internal_posts()` (Task 11's tracker in `recording.py`).
- Produces: no new public names; `ReplaySources.pump_events` and `end_frame` behave as below.

Rules:
1. **Exact merge**: classify each real (or passed-in) event with `event_origin(event=...,
   pending=pending_internal_posts())` — live pumps classify; events served from the recording are
   external by construction and never classified. Build the batch in the recorded batch's order:
   an `external` record → `event_from_record(record)`; an `internal` record → take the first live
   internal event whose `event_to_record(event=..., origin='internal')` equals the record; none →
   `Divergence(kind=EVENT_DIVERGENCE, subject=record['name'], field='missing internal event',
   expected=record, actual=None)`. Live internal events left over →
   `Divergence(..., field='unexpected internal event', expected=None, actual=<record>)`. More pumps
   in a frame than recorded → `LENGTH_DIVERGENCE` (`field='pump count'`). Real external events are
   still dropped (window close kept, Task 12).
2. **References** (spec 1.3, 6): before injecting, a `RecordedReference` of kind `'window'` in an
   attribute becomes the current window (`pygame.Window.from_display_module()`); one of kind
   `'joystick'` becomes `devices().joystick_for_instance(instance_id=...)`; if no stand-in was
   opened for that instance id, the event cannot be mapped and is dropped with one warning per
   instance id ("recorded joystick event for instance 5 has no device; dropped"). An
   `UnrepresentableValue` stays as it is, logged once per type at DEBUG.
3. **Markers**: in `end_frame`, the frame's control events of a kind not in
   `REAPPLIED_CONTROL_EVENT_KINDS` that the replayed code recorded itself must equal the
   recording's markers of that frame, in order; a mismatch is an `EVENT_DIVERGENCE`
   (`field='control event'`).

- [ ] **Step 1: Write the failing tests** (`tests/world/test_gameplay_replay.py`)

```python
def add_recorded_internal_event(*, recording_path: Path, frame_number: int) -> None:
    def add(trace: dict) -> None:
        trace['frames'][frame_number]['event_batches'][0].append({
            'type': pygame.USEREVENT + 41, 'name': 'UserEvent', 'origin': 'internal',
            'attributes': {}})
    rewrite_recording(recording_path=recording_path, change=add)


def add_recorded_external_event(*, recording_path: Path, frame_number: int,
                                record: dict) -> None:
    def add(trace: dict) -> None:
        trace['frames'][frame_number]['event_batches'][0].append(record)
    rewrite_recording(recording_path=recording_path, change=add)


class TestEventMerge:
    def test_missing_internal_event_is_a_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        add_recorded_internal_event(recording_path=recording_path, frame_number=2)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        divergence = engine.replay_sources.result.divergence
        assert (divergence.kind, divergence.field, divergence.frame_number) == (
            EVENT_DIVERGENCE, 'missing internal event', 2)

    def test_extra_internal_event_is_a_divergence(self, mocker, tmp_path):
        from glitchygames.recording import post_event

        def post_extra() -> None:
            post_event(pygame.event.Event(pygame.USEREVENT + 42, {}))

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine = replay_session(recording_path=recording_path, mocker=mocker,
                                action=post_extra, action_frame=2)
        divergence = engine.replay_sources.result.divergence
        assert (divergence.kind, divergence.field, divergence.frame_number) == (
            EVENT_DIVERGENCE, 'unexpected internal event', 3)   # posted in 2, pumped in 3

    def test_real_input_during_replay_never_reaches_the_game(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        # A real key press, and the window losing focus, arrive during the replay: both dropped
        engine = replay_session(recording_path=recording_path, mocker=mocker, events_by_frame={
            1: [_key(pygame.KEYDOWN, pygame.K_z, unicode='z'),
                pygame.event.Event(pygame.WINDOWFOCUSLOST, {})]})
        assert engine.replay_sources.result.divergence is None


class TestReferences:
    def test_window_reference_maps_to_the_current_window(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        add_recorded_external_event(recording_path=recording_path, frame_number=1, record={
            'type': pygame.WINDOWFOCUSGAINED, 'name': 'WindowFocusGained', 'origin': 'external',
            'attributes': {'window': {'__ref__': 'window', 'id': 1}}})
        delivered = mocker.spy(SceneManager, 'handle_event')
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        windows = [call.args[1].window for call in delivered.call_args_list
                   if call.args[1].type == pygame.WINDOWFOCUSGAINED]
        assert windows == [pygame.Window.from_display_module()]
        assert engine.replay_sources.result.divergence is None

    def test_unmappable_joystick_event_is_dropped_with_a_warning(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        add_recorded_external_event(recording_path=recording_path, frame_number=1, record={
            'type': pygame.JOYBUTTONDOWN, 'name': 'JoyButtonDown', 'origin': 'external',
            'attributes': {'instance_id': 5, 'button': 0,
                           'joy': {'__ref__': 'joystick', 'instance_id': 5}}})
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert 'instance 5 has no device; dropped' in caplog.text
        assert engine.replay_sources.result.divergence is None


class TestControlEventMarkers:
    def test_markers_recorded_again_by_the_code_match(self, mocker, tmp_path):
        def mark() -> None:
            SceneManager().record_control_event(kind='test-marker', data={'note': 'n'})

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker, action=mark)
        engine = replay_session(recording_path=recording_path, mocker=mocker, action=mark)
        assert engine.replay_sources.result.divergence is None

    def test_a_missing_marker_is_a_divergence(self, mocker, tmp_path):
        def mark() -> None:
            SceneManager().record_control_event(kind='test-marker', data={'note': 'n'})

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker, action=mark)
        engine = replay_session(recording_path=recording_path, mocker=mocker)  # no marker now
        divergence = engine.replay_sources.result.divergence
        assert (divergence.kind, divergence.field) == (EVENT_DIVERGENCE, 'control event')
```

(Import `EVENT_DIVERGENCE` from `glitchygames.replay.driver`. `SceneManager.handle_event` is the
manager's per-event entry from `GameEngine.handle_event` — check the name and how the event is
passed, and spy on the method that receives each delivered event.)

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement** rules 1–3 in `glitchygames/replay/driver.py`.

- [ ] **Step 4: Run** `tests/world/test_gameplay_replay.py`, `tests/world`, the full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/replay/driver.py tests/world/test_gameplay_replay.py
git commit -m "Make the replay's event merge exact: internal events, references, markers"
```

---

### Task 14: `--audit`

**Files:**
- Create: `glitchygames/replay/audit.py`
- Modify: `glitchygames/replay/driver.py` (`--replay-digest PATH`: write one SHA-256 per frame)
- Modify: `glitchygames/engine/game_engine.py` (`--audit`, `--replay-digest` options; run the
  audit instead of a replay)
- Test: `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Produces:

```python
def frame_digest(*, frame_record: dict[str, Any]) -> str   # sha256 of canonical JSON (sorted keys)
@dataclasses.dataclass(frozen=True)
class ReplayDigestRun:
    digests: list[str]          # one per replayed frame, in order
    divergence: str | None      # Divergence.describe() of that run, or None
    exit_code: int              # the subprocess's exit status
def audit_recording(*, command: list[str], path: Path) -> AuditResult
@dataclasses.dataclass(frozen=True)
class AuditResult:
    first_run: ReplayDigestRun
    second_run: ReplayDigestRun
    first_mismatch_frame: int | None    # between the two runs
    def is_deterministic(self) -> bool: ...
AUDIT_HASH_SEEDS = ('1', '2')          # PYTHONHASHSEED per run, so set/dict-order bugs show up
```

`--audit` (with `--replay-trace PATH`): instead of replaying in-process, run the same command
(`sys.orig_argv` without `--audit`, plus `--replay-digest <temp file>`) twice as subprocesses with
`SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` and `PYTHONHASHSEED` set to each of
`AUDIT_HASH_SEEDS`; each run replays and writes its per-frame digests and its divergence summary
(JSON lines: `{"frame": n, "digest": "..."}`, last line `{"divergence": <describe() or null>}`).
The audit fails (exit 1) if either run diverged from the recording or the two digest streams differ
(report the first differing frame); otherwise exit 0. Fresh processes are the point: they give
fresh engine state and different hash seeds.

- [ ] **Step 1: Write the failing tests**

```python
def fake_run(*, digests: list[str], divergence: str | None) -> ReplayDigestRun:
    """A finished replay subprocess, without running one."""
    return ReplayDigestRun(digests=digests, divergence=divergence,
                           exit_code=0 if divergence is None else 1)


class TestAudit:
    def test_frame_digest_is_canonical(self):
        from glitchygames.replay.audit import frame_digest

        first = frame_digest(frame_record={'b': 1, 'a': [1, 2]})
        second = frame_digest(frame_record={'a': [1, 2], 'b': 1})
        assert first == second

    def test_identical_runs_are_deterministic(self, tmp_path, mocker):
        from glitchygames.replay import audit

        mocker.patch.object(audit, '_run_replay_subprocess',
                            side_effect=[fake_run(digests=['a', 'b'], divergence=None),
                                         fake_run(digests=['a', 'b'], divergence=None)])
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.is_deterministic()

    def test_runs_that_differ_report_the_first_frame(self, tmp_path, mocker):
        from glitchygames.replay import audit

        mocker.patch.object(audit, '_run_replay_subprocess',
                            side_effect=[fake_run(digests=['a', 'b', 'c'], divergence=None),
                                         fake_run(digests=['a', 'x', 'c'], divergence=None)])
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.first_mismatch_frame == 1
        assert not result.is_deterministic()

    def test_a_run_that_diverged_from_the_recording_fails_the_audit(self, tmp_path, mocker):
        from glitchygames.replay import audit

        diverged = 'frame 1: sprite Marker#0 rect expected [0, 0, 4, 4], got [3, 0, 4, 4]'
        mocker.patch.object(audit, '_run_replay_subprocess',
                            side_effect=[fake_run(digests=['a', 'b'], divergence=diverged),
                                         fake_run(digests=['a', 'b'], divergence=diverged)])
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.first_mismatch_frame is None
        assert not result.is_deterministic()

    def test_unseeded_randomness_makes_the_real_audit_fail(self, tmp_path):
        """End to end: a game drawing from an unseeded source is caught by --audit."""
        game_file = tmp_path / 'unseeded_game.py'
        game_file.write_text(UNSEEDED_GAME_SOURCE, encoding='utf-8')
        recording_path = tmp_path / 'unseeded.jsonl.gz'
        environment = {**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'}
        common = [sys.executable, str(game_file), '--target-fps', '0', '--log-level', 'error',
                  '--resolution', '320x240']
        subprocess.run([*common, '--record-trace', str(recording_path)], env=environment,
                       check=True, timeout=120)
        audit_run = subprocess.run([*common, '--replay-trace', str(recording_path), '--audit'],
                                   env=environment, capture_output=True, text=True, check=False,
                                   timeout=240)
        assert audit_run.returncode == 1
        assert 'diverged' in audit_run.stdout + audit_run.stderr
```

with, at module level (add `import os`, `import subprocess`, `import sys` and
`from glitchygames.replay.audit import ReplayDigestRun` to the imports):

```python
# A game whose sprite moves by an unseeded random amount (the guard test forbids this inside the
# package; a game file outside it can still do it, which is what --audit is for). It quits
# itself after FRAMES_BEFORE_QUIT frames.
UNSEEDED_GAME_SOURCE = '''\
import random

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

FRAMES_BEFORE_QUIT = 20


class Mover(pygame.sprite.DirtySprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((4, 4))
        self.rect = self.image.get_rect()
        self.dirty = 2

    def update_nested_sprites(self):
        pass


class UnseededGame(Scene):
    NAME = 'UnseededGame'

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        self.mover = Mover()
        self.all_sprites.add(self.mover)
        self.frames = 0

    def dt_tick(self, dt):
        self.frames += 1
        self.mover.rect.x += int(random.SystemRandom().random() * 10)
        if self.frames == FRAMES_BEFORE_QUIT:
            GameEngine.quit_game()


if __name__ == '__main__':
    GameEngine(game=UnseededGame).start()
'''
```

(Read an example game's `main()` — e.g. `glitchygames/examples/paddleslap.py` — and match how it
constructs and starts the engine if `GameEngine(game=...).start()` differs. The audit's summary line
must contain the word "diverged" when a run diverged; `ReplayResult`'s summary uses it.)

- [ ] **Step 2–4:** fail, implement `audit.py` (`_run_replay_subprocess(*, command, hash_seed,
  digest_path) -> ReplayDigestRun` uses `subprocess.run(..., check=False, env=...)`), the digest
  writer in `ReplaySources.end_frame`, the two options and the `GameEngine` branch (after
  `start_replay` would run: if `options['audit']`, call `audit_recording` and
  `raise SystemExit(0 if result.is_deterministic() else 1)`, printing a one-line summary).
  Run `tests/world/test_gameplay_replay.py` and the full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/replay/audit.py glitchygames/replay/driver.py glitchygames/engine/game_engine.py tests/world/test_gameplay_replay.py
git commit -m "Add --audit: two fresh-process replays with per-frame digests"
```

---

### Task 15: Documentation

**Files:**
- Modify: `CLAUDE.md` (a "Clocks" paragraph: the four exports of `glitchygames/clock.py` and
  `Scene.game_time`, which to use for what, and the raw-clock allow list; Gameplay Recording
  section → "Gameplay Recording and Replay"; doors,
  `current_input()`/`GameEngine.input`, `Scene.game_time`, `frame_clock_seconds`, `open_saves`,
  the devices registry, supervisor hook, control events, `--replay-trace`, `--audit`, format 3)
- Modify: `glitchygames/recording.py` module docstring (already updated in Task 11; check it
  mentions replay as implemented, not planned)
- Create or modify: a docs page — find where recording is documented under `docs/`
  (`grep -rln "record-trace" docs mkdocs.yml`); add a "Replay" page or section and its nav entry
- Modify: `plans/future-work.md` — replace the "Gameplay replay" entry with a pointer to the
  spec and these plans; keep anything from the replay entry not done here (Bitmappy's clocks
  are migrated by Task 9, so no Bitmappy item remains)
- Modify: `plans/2026-10-19-gameplay-replay.md` (the spec) — amend it to match what was built:
  section 7's module table (`glitchygames/sources.py` (leaf registry), `glitchygames/live_sources.py`,
  `glitchygames/clock.py`, `glitchygames/supervision.py`, `RecordingSources` in
  `glitchygames/recording.py`, `glitchygames/replay/audit.py`; Part 2 and 3 add
  `replay/rebaseline.py` and `replay/scene_start.py`), with one sentence on why (the registry has
  no engine dependency, which avoids an engine ↔ scenes import cycle); section 1's "glitchygames/
  engine/sources.py" → "glitchygames/sources.py"; section 3.4's allow list → the guard test's
  `ALLOWED_BYPASSES` (timing, SceneManager pacing, performance/, debug/, audio/diagnostics.py,
  the recording's start stamp, api/client.py); section 3.5's "replays twice in one process" →
  "replays twice in two fresh subprocesses with different PYTHONHASHSEED values"; section 1.3's
  devices sentence gains enumeration (counts, is-controller, names) as part of the door.
- Test: `uv run mkdocs build --strict -d <scratch>; echo EXIT=$?`

- [ ] **Step 1:** Write the CLAUDE.md section (replace the "Replay (`--replay-trace`) is planned"
  sentence), each fact checked against the code (file:line in your report).
- [ ] **Step 2:** Docs page + nav; run mkdocs strict; `EXIT=0`.
- [ ] **Step 3:** future-work update and the spec amendments listed in Files.
- [ ] **Step 4:** Lint (docs only: none), full suite once, commit (name the docs page you
  created or changed in the add):

```bash
git add CLAUDE.md mkdocs.yml plans/future-work.md plans/2026-10-19-gameplay-replay.md docs/<the replay page>
git commit -m "Document the engine doors and gameplay replay; amend the spec to what was built"
```

---

## Self-review notes (for the executor)

- `EngineSources` grows across Tasks 2, 3, 5, 7, 8, 10; the final shape is in the master plan's
  Cross-part interfaces. Every implementation (`LiveSources`, `RecordingSources`,
  `ReplaySources`, and Part 3's scoped sources) must implement all of it.
- The golden test runs after every task; it must never change except by Task 8's exact rule.
