# Gameplay Replay — Part 1: Replay Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Master plan:** [2026-10-19-gameplay-replay-implementation.md](2026-10-19-gameplay-replay-implementation.md)
(read its Global Constraints, Review Focus and Cross-part interfaces first; they apply to every
task here)

**Goal:** Put every input the engine takes from the outside world behind swappable doors, record
what passes through them, and replay a recording exactly with `--replay-trace`, reporting the first
divergence.

**Architecture:** `glitchygames/engine/sources.py` holds the doors and a module-level registry
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
- Spec section 3.4 lists the bypass sites; re-grep before and after Task 7 (the command is in
  Task 7) — the lists below were taken at commit `da29bf2`.

## Review Focus

From the master plan, owned here: items 1–4.

## Tasks

| # | Task | Produces |
|---|---|---|
| 1 | Trace format version 3 | `TRACE_FORMAT_VERSION = 3`, `READABLE_FORMAT_VERSIONS`, `TraceReader.format_version` |
| 2 | The doors and the registry | `EngineSources`, `LiveSources`, `active_sources`, `install_sources`, frame number |
| 3 | Input snapshots | `InputSnapshot`, `current_input`, capture after the pump, diffs |
| 4 | Game time and the frame clock | `Scene.game_time`, `frame_clock_seconds`, FPS events from frame time |
| 5 | The devices door | `DeviceRegistry`, live registry, stand-ins, device sites moved |
| 6 | The saves door | `open_saves`, `SandboxSaves`, the four games moved |
| 7 | Bypass sites and the guard test | polled input / wall clock moved; `tests/test_engine_doors.py` |
| 8 | Supervisor hook and control events | `add_supervisor`, `record_control_event`, handlers |
| 9 | `RecordingSources` | recorder folded into the doors; format-3 fields recorded |
| 10 | `ReplaySources` and `--replay-trace` | the replay, event merge, comparison, `Divergence` |
| 11 | `--audit` | two subprocess replays with per-frame digests |
| 12 | Documentation | CLAUDE.md, recording docstring, docs page, future-work |

---

### Task 1: Trace format version 3

**Files:**
- Modify: `glitchygames/tracing.py:1-60` (module docstring), `:89` (`TRACE_FORMAT_VERSION`),
  `:689-770` (`TraceReader`), `:852-886` (`TraceReadResult`, `read_trace_result`)
- Modify: `glitchygames/recording.py:117-120` (new frame-field constants)
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
- Create: `glitchygames/engine/sources.py`
- Modify: `glitchygames/engine/game_engine.py:1380-1406` (`_pump_events`), `:547-575`
  (`__init__`: reset the registry), new method `install_sources`
- Modify: `glitchygames/scenes/scene.py:121-175` (`SceneManager.__init__`: `frame_number`),
  `:784-821` (`start`), `:822-870` (`_finish_frame`), `:872-898` (`_run_frame`)
- Modify: `tests/conftest.py` (autouse registry reset)
- Test: `tests/engine/test_engine_sources.py` (new: a new module gets its own test file)

**Interfaces:**
- Consumes: nothing.
- Produces (this task's subset of the master's `EngineSources`; Tasks 3, 5, 6, 8 add methods):

```python
class EngineSources(Protocol):
    random_seed: int
    @property
    def stop_requested(self) -> bool: ...
    def pump_events(self) -> list[pygame.event.Event]: ...
    def frame_seconds(self, *, measured: float) -> float: ...
    def end_frame(self, *, frame_number: int, dt: float, scene: Scene | None) -> None: ...
def active_sources() -> EngineSources
def install_sources(*, sources: EngineSources) -> None   # raises SourcesAlreadyRunningError
def mark_frames_started() -> None
def reset_sources() -> None
def advance_frame_clock(*, seconds: float) -> None       # used by Task 4
def frame_clock_seconds() -> float                       # used by Task 4
GameEngine.install_sources(self, *, sources: EngineSources) -> None
SceneManager.frame_number: int     # frames finished so far this run
```

- [ ] **Step 1: Write the failing tests** (`tests/engine/test_engine_sources.py`)

```python
"""The engine's doors (glitchygames/engine/sources.py): live by default, swappable before the
first frame, and the only way the frame loop reads events and frame time."""

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

from glitchygames.engine.sources import (
    LiveSources,
    SourcesAlreadyRunningError,
    active_sources,
    install_sources,
    mark_frames_started,
)
from glitchygames.scenes import Scene

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

    def pump_events(self: Self) -> list[pygame.event.Event]:
        self.pump_count += 1
        pygame.event.get()  # the real queue is drained and ignored
        if self.pump_count == 1:
            return [pygame.event.Event(pygame.KEYDOWN, {'key': SCRIPTED_KEY, 'mod': 0,
                                                        'unicode': 'x', 'scancode': 27})]
        return []

    def end_frame(self: Self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        self.ended_frames.append(frame_number)


def start_engine(scene_class: type[Scene]) -> GoldenTraceSceneManager:
    manager = GoldenTraceSceneManager.install()
    with command_line(['--windowed', '--resolution', '320x240', '--log-level', 'warning']):
        engine = GoldenTraceEngine(game=scene_class)
    engine.install_game(scene_class=scene_class)
    return manager


class TestRegistry:
    def test_live_sources_are_the_default(self):
        assert isinstance(active_sources(), LiveSources)

    def test_installed_sources_become_active(self):
        sources = ScriptedSources()
        install_sources(sources=sources)
        assert active_sources() is sources

    def test_install_after_the_first_frame_is_refused(self):
        mark_frames_started()
        with pytest.raises(SourcesAlreadyRunningError):
            install_sources(sources=ScriptedSources())


class TestFrameLoopUsesTheDoors:
    def test_events_come_from_the_installed_pump(self):
        manager = start_engine(KeyCountingScene)
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
        manager = start_engine(KeyCountingScene)
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
        # GoldenTraceEngine.__init__ resets the registry, so install after constructing it
        manager = start_engine(KeyCountingScene)
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
    """Give every test fresh live doors (glitchygames/engine/sources.py)."""
    from glitchygames.engine.sources import reset_sources

    reset_sources()
    yield
    reset_sources()
```

- [ ] **Step 2: Run to see them fail**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/engine/test_engine_sources.py -q -p no:cacheprovider --no-cov`
Expected: FAIL with `ModuleNotFoundError: glitchygames.engine.sources`.

- [ ] **Step 3: Implement `glitchygames/engine/sources.py`**

```python
"""The engine's doors: every input the engine takes from the outside world.

The engine reads events, frame time, polled input, devices, saves and the random seed only
through the active ``EngineSources``. Live play uses ``LiveSources`` (pygame, the clock, the
disk); ``--record-trace`` wraps them in ``RecordingSources`` (glitchygames/recording.py);
``--replay-trace`` installs ``ReplaySources`` (glitchygames/replay/driver.py). Everything
downstream of the doors runs unchanged, so a replay goes through the real engine.

The registry is module state, like glitchygames/randomness.py's streams, so engine code, games
and widgets reach the active sources without an engine reference. ``install_sources`` may only be
called before the first frame (a run never mixes live and recorded input); in-game playback pushes
scoped sources on top instead (``push_scoped_sources``, Part 3 of plans/2026-10-19-gameplay-
replay-implementation.md). ``GameEngine.__init__`` calls ``reset_sources()`` so each run starts
with fresh live doors.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Protocol, Self

import pygame

from glitchygames.randomness import engine_random_seed

if TYPE_CHECKING:
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

    def pump_events(self) -> list[pygame.event.Event]:
        """Return the next batch of events (the only read of the event queue)."""
        ...

    def frame_seconds(self, *, measured: float) -> float:
        """Return the frame time logic receives, given the measured start-to-start time."""
        ...

    def end_frame(self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        """Called once after each frame (recording writes it, replay compares it)."""
        ...


class LiveSources:
    """The live doors: pygame's queue and the measured frame time."""

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
    _REGISTRY.installed = sources


def mark_frames_started() -> None:
    """Record that the frame loop has started (install_sources is refused from now on)."""
    _REGISTRY.frames_started = True


def advance_frame_clock(*, seconds: float) -> None:
    """Add one frame's raw dt to the frame clock (SceneManager, once per frame)."""
    _REGISTRY.frame_clock_seconds += seconds


def frame_clock_seconds() -> float:
    """Return the sum of every frame's raw dt this run.

    It replays exactly (dt comes through the frame-time door) and never pauses, so it is the
    clock for UI timing (cursor blinks) and FPS events. Gameplay uses ``Scene.game_time``.

    Returns:
        Seconds.

    """
    return _REGISTRY.frame_clock_seconds


def reset_sources() -> None:
    """Forget every installed and scoped source and the frame clock (a new run, or a test)."""
    _REGISTRY.installed = None
    _REGISTRY.scoped.clear()
    _REGISTRY.frames_started = False
    _REGISTRY.frame_clock_seconds = 0.0
```

In `GameEngine.__init__`, right after `self.random_seed = seed_engine_random(...)`:

```python
        # Fresh live doors for this run (glitchygames/engine/sources.py); --replay-trace and
        # --record-trace install their own before the first frame
        reset_sources()
        install_sources(sources=LiveSources(random_seed=self.random_seed,
                                            use_fastevents=self.USE_FASTEVENTS))
```

(check `USE_FASTEVENTS` is set before this point in `__init__`; it is a class attribute — read
where `__init__` assigns it and keep the documented fallback behaviour), and add:

```python
    def install_sources(self: Self, *, sources: EngineSources) -> None:
        """Make ``sources`` this run's doors (before the first frame; see engine/sources.py)."""
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

(Task 9 moves the recorder into `RecordingSources`; until then this check stays.) The
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
never calls `start()`, so `mark_frames_started()` is not called there — that is fine (tests that
need it call it).

- [ ] **Step 4: Run the new tests, then the frame tests and the golden test**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/engine/test_engine_sources.py tests/world tests/scenes tests/engine -q -p no:cacheprovider --no-cov`
Expected: PASS (golden unchanged).

- [ ] **Step 5: Lint, type-check, full suite, commit**

```bash
git add glitchygames/engine/sources.py glitchygames/engine/game_engine.py glitchygames/scenes/scene.py tests/conftest.py tests/engine/test_engine_sources.py
git commit -m "Add the engine's doors: events and frame time through swappable sources"
```

---

### Task 3: Input snapshots

**Files:**
- Create: `glitchygames/input/state.py`
- Modify: `glitchygames/engine/sources.py` (Protocol + `LiveSources.input_snapshot`)
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
        from glitchygames.engine import sources as sources_module

        captures: list[int] = []
        original_capture = sources_module.capture_live_snapshot

        def counting_capture(**keywords):
            captures.append(1)
            return original_capture(**keywords)

        # LiveSources calls the name it imported into glitchygames/engine/sources.py
        mocker.patch.object(sources_module, 'capture_live_snapshot', counting_capture)
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
asks the active sources (glitchygames/engine/sources.py) for an ``InputSnapshot`` and makes it
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
        """Return whether ``key`` (a pygame.K_* code) is held this frame."""
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
returns `capture_live_snapshot()` (Task 5 passes the device positions). Call
`reset_current_input()` from `reset_sources()` so a new run starts idle.

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
git add glitchygames/input/state.py glitchygames/engine/sources.py glitchygames/engine/game_engine.py tests/input/test_input_state.py tests/world/test_frame_integration.py
git commit -m "Add the polled-input door: one InputSnapshot per frame, taken after the pump"
```

---

### Task 4: Game time and the frame clock

**Files:**
- Modify: `glitchygames/scenes/scene.py` — `Scene.__init__` (`_game_time_seconds`), new property
  `Scene.game_time`; `SceneManager._update_scene` (`:1181-1189`); `SceneManager._run_frame`
  (`advance_frame_clock`); `SceneManager.start` and `_finish_frame` (FPS event timing from the
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

`SceneManager._run_frame`, first line after `frame_dt = self.dt`:

```python
        # The frame clock (engine/sources.py) is the sum of raw frame times: UI timing and FPS
        # events use it, so they replay exactly
        advance_frame_clock(seconds=frame_dt)
```

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

Expected: PASS, golden unchanged (the harness never posts FPS events).

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/scenes/scene.py tests/world/test_frame_integration.py tests/world/test_finish_frame.py
git commit -m "Add Scene.game_time and time FPS events from the replayable frame clock"
```

---

### Task 5: The devices door

**Files:**
- Create: `glitchygames/input/devices.py`
- Modify: `glitchygames/engine/sources.py` (`EngineSources.devices`, `LiveSources`)
- Modify device construction sites: `glitchygames/events/joystick.py:55-64, :302, :467`,
  `glitchygames/events/controller.py:76`, `glitchygames/input/rumble.py:64`,
  `glitchygames/examples/joystick_demo.py:383, :830, :943`,
  `glitchygames/bitmappy/controllers/event_handler.py:669-672, :709-711, :771-772`
- Test: `tests/input/test_devices.py` (new)

**Interfaces:**
- Consumes: `capture_live_snapshot` (Task 3).
- Produces:

```python
@dataclasses.dataclass(frozen=True)
class DeviceDescriptor:
    kind: str            # 'joystick' | 'controller'
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
class DeviceRegistry(Protocol):
    def joystick_count(self) -> int: ...
    def open_joystick(self, *, device_index: int) -> Any: ...
    def open_controller(self, *, device_index: int) -> Any: ...
    def joystick_for_instance(self, *, instance_id: int) -> Any | None: ...
    def take_opened_descriptors(self) -> list[DeviceDescriptor]: ...
class LiveDeviceRegistry: ...          # opens real pygame devices, polls them
class ReplayDeviceRegistry: ...        # stand-ins from descriptors (Task 10 builds it)
class ReplayJoystick / ReplayController  # read positions from current_input(); rumble no-op
EngineSources.devices(self) -> DeviceRegistry
```

- [ ] **Step 1: Write the failing tests** (`tests/input/test_devices.py`)

```python
"""The devices door (glitchygames/input/devices.py)."""

from __future__ import annotations

from glitchygames.input.devices import (
    DeviceDescriptor,
    ReplayController,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.input.state import InputSnapshot, set_current_input

PAD = DeviceDescriptor(kind='joystick', device_index=0, instance_id=7, name='Test Pad',
                       guid='abc', axis_count=2, button_count=3, hat_count=1, ball_count=0)


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
    registry = ReplayDeviceRegistry(descriptors=[PAD])
    joystick = registry.open_joystick(device_index=0)
    controller = registry.open_controller(device_index=0)
    assert isinstance(joystick, ReplayJoystick)
    assert isinstance(controller, ReplayController)
    assert registry.joystick_count() == 1
    assert registry.joystick_for_instance(instance_id=7) is joystick
    real_joystick.assert_not_called()
    real_controller.assert_not_called()


def test_replay_registry_unknown_device_gets_a_named_stand_in(caplog):
    registry = ReplayDeviceRegistry(descriptors=[])
    joystick = registry.open_joystick(device_index=3)
    assert joystick.get_name() == 'Unrecorded device 3'
    assert 'not in the recording' in caplog.text
```

Also add to `tests/events/` (find the existing joystick proxy test file with
`grep -rln "JoystickProxy\|JoystickManager" tests/events`) a test that constructing the proxy goes
through `active_sources().devices().open_joystick(...)` (patch the registry method with
`mocker.patch.object` and assert it was called with `device_index=0`).

- [ ] **Step 2: Run to see them fail**

Run: `SDL_VIDEODRIVER=dummy uv run pytest tests/input/test_devices.py -q -p no:cacheprovider --no-cov`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `glitchygames/input/devices.py`**

```python
"""The devices door: joysticks and controllers are opened only through the active registry.

Live play opens real pygame devices (``LiveDeviceRegistry``) and records a descriptor of each
one; a replay answers with stand-ins built from those descriptors (``ReplayJoystick``,
``ReplayController``), whose positions come from the frame's input snapshot
(glitchygames/input/state.py) and whose rumble is accepted and dropped. So a replay never needs
the recorded hardware and never opens a device that happens to be plugged in.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Protocol, Self

import pygame

from glitchygames.input.state import current_input

LOG = logging.getLogger('game.input.devices')
LOG.addHandler(logging.NullHandler())

JOYSTICK_KIND = 'joystick'
CONTROLLER_KIND = 'controller'


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


class DeviceRegistry(Protocol):
    """Opens devices for the engine and games (see the module docstring)."""

    def joystick_count(self) -> int: ...
    def open_joystick(self, *, device_index: int) -> Any: ...
    def open_controller(self, *, device_index: int) -> Any: ...
    def joystick_for_instance(self, *, instance_id: int) -> Any | None: ...
    def take_opened_descriptors(self) -> list[DeviceDescriptor]: ...


class LiveDeviceRegistry:
    """Opens real devices, remembers them by instance id and polls them for the snapshot."""

    def __init__(self: Self) -> None:
        """Start with no devices opened."""
        self._devices_by_instance: dict[int, Any] = {}
        self._new_descriptors: list[DeviceDescriptor] = []

    def joystick_count(self: Self) -> int:
        """Return how many joysticks SDL reports."""
        return pygame.joystick.get_count()

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

    def poll(self: Self) -> tuple[dict[int, tuple[float, ...]], dict[int, tuple[bool, ...]],
                                  dict[int, tuple[tuple[int, int], ...]]]:
        """Read every opened device's axes, buttons and hats (once per frame)."""
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


class ReplayJoystick:
    """A recorded joystick: answers from its descriptor and the frame's input snapshot."""

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
    """Stand-ins built from a recording's device descriptors (glitchygames/replay/driver.py)."""

    def __init__(self: Self, *, descriptors: list[DeviceDescriptor]) -> None:
        """Index the recorded descriptors by device index."""
        self._descriptors_by_index = {descriptor.device_index: descriptor
                                      for descriptor in descriptors}
        self._opened_by_instance: dict[int, ReplayJoystick] = {}

    def add_descriptors(self: Self, *, descriptors: list[DeviceDescriptor]) -> None:
        """Learn devices the recording opened later (``devices_opened`` frame fields)."""
        for descriptor in descriptors:
            self._descriptors_by_index[descriptor.device_index] = descriptor

    def joystick_count(self: Self) -> int:
        """Return how many devices the recording has seen so far."""
        return len(self._descriptors_by_index)

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
        """Stand-ins are already recorded: nothing new."""
        return []

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
installed version with `uv run python -c "import pygame._sdl2.controller as c; print(dir(c.Controller))"`;
if `as_joystick` is missing, remember the controller itself and read counts from `len(AXIS)` /
`len(BUTTONS)` as `events/controller.py` does. The replay stand-ins must offer every method the
proxies call — grep `self.joystick\.` and `self.controller\.` in `glitchygames/events/` and add any
missing method to the stand-ins with a recorded or neutral answer.)

`EngineSources.devices(self) -> DeviceRegistry`. `LiveSources.__init__` creates
`self._devices = LiveDeviceRegistry()`; `devices()` returns it; `input_snapshot()` becomes:

```python
        axes, buttons, hats = self._devices.poll()
        return capture_live_snapshot(device_axes=axes, device_buttons=buttons, device_hats=hats)
```

Replace each construction site with the registry, e.g. in `events/joystick.py`:

```python
                self.joystick = active_sources().devices().open_joystick(device_index=joystick_id)
```

Keep the existing `from_instance_id` branch's intent: read the comment above it; if it opens by
instance id, add `open_joystick_for_instance` only if a test shows the index path differs —
otherwise open by index as the fallback already does, and say so in the report. In
`bitmappy/controllers/event_handler.py` the three sites only poll trigger/button positions:
replace each `pygame.joystick.Joystick(...)` + `get_axis(...)` with
`current_input().axis(device_id=event.instance_id, axis=...)` (and `button(...)`). **Report this
bug:** the old code passed an *instance id* to `pygame.joystick.Joystick()`, which takes a
*device index*; they differ after a reconnect, so the wrong device (or `pygame.error`) was read.
The snapshot lookup by instance id fixes it.

- [ ] **Step 4: Run the device tests, `tests/events`, `tests/input`, the joystick demo tests,
  Bitmappy controller tests and the golden test**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/input tests/events tests/examples tests/world/test_golden_traces.py -q -p no:cacheprovider --no-cov`, then `grep -rln "event_handler\|controllers" tests/canvas tests/bitmappy 2>/dev/null` and run those too.
Expected: PASS.

- [ ] **Step 5: Lint, type-check, full suite, commit**

```bash
git add glitchygames/input/devices.py glitchygames/engine/sources.py glitchygames/events/joystick.py glitchygames/events/controller.py glitchygames/input/rumble.py glitchygames/examples/joystick_demo.py glitchygames/bitmappy/controllers/event_handler.py tests/input/test_devices.py <the events test file you changed>
git commit -m "Add the devices door: open joysticks and controllers through the registry"
```

---

### Task 6: The saves door

**Files:**
- Create: `glitchygames/state/sandbox.py`
- Modify: `glitchygames/state/__init__.py` (export `open_saves`, `SaveStore`, `SandboxSaves`)
- Modify: `glitchygames/engine/sources.py` (`EngineSources.saves`, `LiveSources.saves`)
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
LiveSources.opened_save_namespaces -> dict[str, SaveManager]   # for RecordingSources (Task 9)
```

- [ ] **Step 1: Write the failing tests** (`tests/state/test_sandbox.py`)

```python
"""The saves door (glitchygames/state/sandbox.py)."""

from __future__ import annotations

import pytest

from glitchygames.engine.sources import LiveSources, install_sources
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
        """Keep the data in memory only."""
        self._envelopes[slot_name] = {DATA_KEY: copy.deepcopy(data)}

    def exists(self: Self, slot_name: str) -> bool:
        """Return whether the slot exists in the sandbox."""
        return slot_name in self._envelopes

    def delete(self: Self, slot_name: str) -> None:
        """Remove the slot from the sandbox."""
        self._envelopes.pop(slot_name, None)


def save_namespace_snapshot(*, saves: SaveManager) -> dict[str, dict[str, Any]]:
    """Return every slot of a store as its full envelope (slot name -> envelope).

    Returns:
        The JSON-safe snapshot a recording stores.

    """
    return {slot.name: saves.load_raw(slot_name=slot.name) for slot in saves.list_slots()}


def open_saves(*, app_name: str) -> SaveStore:
    """Open a game's save store through the active sources (glitchygames/engine/sources.py).

    Returns:
        The store: a SaveManager live, a SandboxSaves in a replay.

    """
    from glitchygames.engine.sources import active_sources

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
git add glitchygames/state/sandbox.py glitchygames/state/__init__.py glitchygames/engine/sources.py glitchygames/examples/paddleslap.py glitchygames/examples/clockwork_keep/game.py glitchygames/examples/brave_adventurer/game.py glitchygames/examples/brave_adventurer_papyrus/game.py tests/state/test_sandbox.py
git commit -m "Add the saves door: games open saves through the sources; replay sandbox"
```

---

### Task 7: Bypass sites and the guard test

**Files:**
- Create: `tests/ast_scanning.py` (shared AST helpers moved out of `tests/test_randomness.py`)
- Create: `tests/test_engine_doors.py`
- Modify: `tests/test_randomness.py` (import the moved helpers)
- Modify (polled input → `current_input()`): `glitchygames/ui/inputs.py:528`,
  `glitchygames/ui/text_widgets.py:1207, :1487`, `glitchygames/scenes/scene.py:481` (debug overlay
  mouse), `glitchygames/examples/dt_demo.py:131`, `glitchygames/bitmappy/editor.py:485, :1392`,
  `glitchygames/bitmappy/film_strip_sprite.py:126-127, :182-183, :478`,
  `glitchygames/bitmappy/file_io.py:120`, `glitchygames/bitmappy/animated_canvas.py:916`
- Modify (wall clock): `glitchygames/examples/paddleslap.py:301, :650, :670` (→ `game_time`;
  drop `import time`), `glitchygames/ui/inputs.py:156` and `glitchygames/ui/text_widgets.py:711,
  :714, :1082, :1142, :1247` (→ `frame_clock_seconds()`)
- Modify: `scripts/record_golden_traces.py:458-487` (drop the `paddleslap.time` patch)
- Modify (if needed): `tests/world/test_golden_traces.py` (`EXPECTED_DIFFERENCES['paddleslap']`)
- Test: `tests/test_engine_doors.py`, plus each touched module's existing tests

**Interfaces:**
- Consumes: `current_input()` (Task 3), `Scene.game_time` and `frame_clock_seconds()` (Task 4).
- Produces: `tests/ast_scanning.py`: `import_bindings(tree) -> dict[str, str]`,
  `qualified_name(node, bindings) -> str | None`; `tests/test_engine_doors.py`:
  `door_bypasses(source_path) -> list[str]`, `ALLOWED_BYPASSES`.

- [ ] **Step 1: Re-grep the sites and write down the list in your report**

Run: `grep -rn -E "key\.get_pressed|key\.get_mods|mouse\.get_pos|mouse\.get_pressed|mouse\.get_focused|time\.time\(\)|time\.monotonic\(\)|pygame\.time\.get_ticks|datetime\.now|event\.post\(|joystick\.Joystick\(|controller\.Controller\(" glitchygames | grep -v "\.pyc"`

Every hit outside the allowed files below must be moved in this task.

- [ ] **Step 2: Move the AST helpers and write the failing guard test**

Move `_import_bindings`, `_dynamic_import_name` and `_qualified_name` from
`tests/test_randomness.py` into `tests/ast_scanning.py` as public `import_bindings`,
`dynamic_import_name`, `qualified_name` (same bodies, docstrings kept), and import them back in
`tests/test_randomness.py`. Run `tests/test_randomness.py` — it must still pass unchanged.

`tests/test_engine_doors.py`:

```python
"""Nothing in the package reads input or time from outside the engine's doors.

Polled input goes through glitchygames/input/state.py, devices through
glitchygames/input/devices.py, events through glitchygames/engine/sources.py and posted events
through glitchygames/recording.post_event, gameplay time through Scene.game_time and UI time
through glitchygames.engine.sources.frame_clock_seconds — so a replay reaches all of it
(plans/2026-10-19-gameplay-replay.md, section 3.4). time.perf_counter is not listed: it measures
the real run (pacing, statistics) and reaches logic only through the frame-time door.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.ast_scanning import import_bindings, qualified_name

PACKAGE = Path(__file__).resolve().parent.parent / 'glitchygames'

DOOR_BYPASSES = frozenset({
    'pygame.key.get_pressed', 'pygame.key.get_mods', 'pygame.mouse.get_pos',
    'pygame.mouse.get_pressed', 'pygame.mouse.get_focused',
    'pygame.event.get', 'pygame.event.post', 'pygame.fastevent.get',
    'pygame.joystick.Joystick', 'pygame._sdl2.controller.Controller',
    'pygame.controller.Controller',
    'time.time', 'time.monotonic', 'pygame.time.get_ticks', 'datetime.datetime.now',
})

# Files (or directories, ending in '/') allowed to use each bypass, with the reason
ALLOWED_BYPASSES: dict[str, frozenset[str]] = {
    'input/state.py': frozenset({'pygame.key.get_pressed', 'pygame.key.get_mods',
                                 'pygame.mouse.get_pos', 'pygame.mouse.get_pressed',
                                 'pygame.mouse.get_focused'}),          # the polled-input door
    'input/devices.py': frozenset({'pygame.joystick.Joystick',
                                   'pygame._sdl2.controller.Controller'}),  # the devices door
    'engine/sources.py': frozenset({'pygame.event.get', 'pygame.fastevent.get'}),  # event door
    'replay/driver.py': frozenset({'pygame.event.get'}),  # drains the real queue during replay
    'recording.py': frozenset({'pygame.event.post'}),     # post_event, the one poster
    'engine/game_engine.py': frozenset({'datetime.datetime.now'}),  # recording start stamp
    'state/manager.py': frozenset({'datetime.datetime.now'}),       # save metadata stamp
    'api/client.py': frozenset({'time.time'}),            # request timestamps (not gameplay)
    # Bitmappy's undo history, metrics and controller timing read the wall clock in ~80 places;
    # Bitmappy replay is best effort until they move (plans/future-work.md)
    'bitmappy/': frozenset({'time.time', 'pygame.time.get_ticks'}),
}


def _allowed(relative_path: str) -> frozenset[str]:
    allowed: set[str] = set()
    for location, names in ALLOWED_BYPASSES.items():
        if relative_path == location or (location.endswith('/') and
                                         relative_path.startswith(location)):
            allowed |= names
    return frozenset(allowed)


def door_bypasses(source_path: Path, *, allowed: frozenset[str] = frozenset()) -> list[str]:
    """Return 'line: name' for every bypass a module calls or references."""
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    bindings = import_bindings(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Name)):
            name = qualified_name(node, bindings)
            if name in DOOR_BYPASSES and name not in allowed:
                found.append(f'{node.lineno}: {name}')
    return sorted(set(found))


def test_package_reads_input_and_time_only_through_the_doors():
    offenders = {
        str(path.relative_to(PACKAGE)): bypasses
        for path in sorted(PACKAGE.rglob('*.py'))
        if (bypasses := door_bypasses(
            path, allowed=_allowed(str(path.relative_to(PACKAGE)).replace('\\', '/'))))
    }
    assert offenders == {}


OFFENDING_SOURCE = '''\
import time
import pygame
from pygame import key as keyboard
from datetime import datetime as clock

def poll():
    return pygame.key.get_pressed(), keyboard.get_mods(), time.time(), clock.now()

def post():
    pygame.event.post(pygame.event.Event(pygame.USEREVENT))
'''


@pytest.fixture
def offending_file(tmp_path) -> Path:
    path = tmp_path / 'offending.py'
    path.write_text(OFFENDING_SOURCE, encoding='utf-8')
    return path


def test_scan_finds_every_kind(offending_file):
    names = {entry.split(': ', 1)[1] for entry in door_bypasses(offending_file)}
    assert names == {'pygame.key.get_pressed', 'pygame.key.get_mods', 'time.time',
                     'datetime.datetime.now', 'pygame.event.post'}
```

(`qualified_name` must resolve `clock.now` to `datetime.datetime.now` through the
`from datetime import datetime as clock` binding; if the moved helper does not, extend it in
`tests/ast_scanning.py` and add a case to the randomness guard's tests too.)

- [ ] **Step 3: Run the guard to see it fail and list the offenders**

Run: `uv run pytest tests/test_engine_doors.py -q -p no:cacheprovider --no-cov`
Expected: the package test FAILS listing every site from Step 1; the fixture test passes once the
helper resolves aliases.

- [ ] **Step 4: Move every site**

Polled input, e.g. `bitmappy/editor.py:485`:

```python
        held_keys = current_input()
        is_shift_click = held_keys.key_pressed(pygame.K_LSHIFT) or held_keys.key_pressed(
            pygame.K_RSHIFT
        )
```

`ui/inputs.py:528`, `ui/text_widgets.py:1487`, `bitmappy/*` mouse reads:
`mouse_pos = current_input().mouse_position`. `ui/text_widgets.py:1207`:
`mods = current_input().modifiers`. Debug overlay `scenes/scene.py:481`:

```python
        frame_input = current_input()
        mouse_position = frame_input.mouse_position if frame_input.mouse_focused else None
```

Wall clock in PaddleSlap (read the comments at `:301-302` first):

```python
        # Game time of the last spawn (Scene.game_time); -inf so the first spawn is never held
        # back by the cooldown, as with the old wall-clock start of 0.0
        self.last_ball_spawn_time = -math.inf
```

`:650` `current_time = self.game_time`; `:670` `self.last_ball_spawn_time = self.game_time`;
remove `import time` if nothing else uses it. Cursor blinks: `ui/inputs.py:156`:

```python
        if frame_clock_seconds() % 1 > CURSOR_BLINK_HALF_SECOND and self.is_active:
```

`ui/text_widgets.py` keeps milliseconds: replace each `pygame.time.get_ticks()` with
`round(frame_clock_seconds() * 1000)` through one helper in that module:

```python
def _frame_clock_milliseconds() -> int:
    """The replayable frame clock in milliseconds (cursor blink timing)."""
    return round(frame_clock_seconds() * 1000)
```

Golden harness: remove `(paddleslap, 'time', types.SimpleNamespace(time=clock.now))` from
`deterministic_environment` and update its docstring ("Replace the save directory ... PaddleSlap's
cooldown now uses Scene.game_time, which the harness's fixed dt drives"). If `clock` is then
unused by `deterministic_environment`, keep the parameter only if other callers rely on it
(`grep -rn deterministic_environment tests scripts`); otherwise remove it and update callers.

- [ ] **Step 5: Golden check and the behaviour-fix rule**

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

- [ ] **Step 6: Run the guard, every touched module's tests, `tests/world`, the full suite**

Expected: PASS, no warnings.

- [ ] **Step 7: Lint, type-check, vulture, commit**

```bash
git add tests/ast_scanning.py tests/test_engine_doors.py tests/test_randomness.py scripts/record_golden_traces.py <every modified glitchygames file> <tests you changed>
git commit -m "Move polled input and wall-clock reads behind the doors; guard the package"
```

---

### Task 8: Supervisor hook and control events

**Files:**
- Create: `glitchygames/engine/supervision.py`
- Modify: `glitchygames/scenes/scene.py` — `SceneManager.__init__`, `_run_frame`,
  `_run_scene_frame` (the slot after `_process_events`), new methods `add_supervisor`,
  `remove_supervisor`, `record_control_event`, `add_control_event_handler`
- Modify: `glitchygames/engine/sources.py` (`control_events_for_frame`; `end_frame` gets
  `control_events`)
- Modify: `tests/engine/test_engine_sources.py` (`ScriptedSources.end_frame` takes the new
  `control_events` keyword)
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
        from glitchygames.engine.sources import active_sources
        from glitchygames.engine.supervision import BREAKPOINT_KIND, ControlEvent

        handled: list[ControlEvent] = []
        with running_scene(CameraFreeScene) as manager:
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=handled.append)
            end_frame = mocker.spy(active_sources(), 'end_frame')
            manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'here'})
            step(manager, frames=1)
        assert handled == [ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'here'})]
        assert end_frame.call_args.kwargs['control_events'] == handled

    def test_scheduled_control_events_are_applied_at_the_slot(self, mocker):
        from glitchygames.engine.sources import active_sources
        from glitchygames.engine.supervision import BREAKPOINT_KIND, ControlEvent

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
        from glitchygames.engine.supervision import ControlEvent

        event = ControlEvent(kind='breakpoint', data={'label': 'x'})
        assert event.to_json() == {'kind': 'breakpoint', 'label': 'x'}
        assert ControlEvent.from_json(event.to_json()) == event
```

- [ ] **Step 2: Run to see them fail** — Expected: `AttributeError: ... add_supervisor`.

- [ ] **Step 3: Implement**

`glitchygames/engine/supervision.py`:

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
        """Call ``supervisor`` once per frame at the supervisor slot (engine/supervision.py)."""
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
the `control_events` parameter to `end_frame` (Live ignores it).

- [ ] **Step 4: Run** `tests/world`, `tests/scenes`, `tests/engine`, golden. Expected: PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/engine/supervision.py glitchygames/scenes/scene.py glitchygames/engine/sources.py tests/world/test_frame_integration.py
git commit -m "Add the supervisor slot and recorded control events to the frame"
```

---

### Task 9: `RecordingSources`

**Files:**
- Modify: `glitchygames/recording.py` (`RecordingSources`; `GameplayRecorder.record_frame` gains
  the format-3 fields; module docstring)
- Modify: `glitchygames/engine/game_engine.py:1118-1155` (`start_trace_recording` /
  `stop_trace_recording` install and finish `RecordingSources`), `:1380-1406` (`_pump_events`: the
  recorder check moves into the sources)
- Modify: `glitchygames/scenes/scene.py:872-898` (remove the direct `trace_recorder.record_frame`
  call; `end_frame` does it)
- Test: `tests/world/test_gameplay_recording.py`, `tests/test_recording.py`

**Interfaces:**
- Consumes: Tasks 2–8.
- Produces:

```python
class RecordingSources:   # implements EngineSources, wraps another
    def __init__(self, *, inner: EngineSources, recorder: GameplayRecorder) -> None: ...
    inner: EngineSources
GameplayRecorder.record_frame(self, *, dt: float, scene: Scene | None,
                              input_changes: dict[str, Any] | None = None,
                              control_events: list[dict[str, Any]] | None = None,
                              devices_opened: list[dict[str, Any]] | None = None,
                              saves_opened: dict[str, Any] | None = None) -> None
GameEngine.start_trace_recording(self, *, path: Path) -> GameplayRecorder   # unchanged signature
```

Rules:
- `start_trace_recording` builds the header (`trace_recording_header()` plus
  `saves`: `{namespace: save_namespace_snapshot(saves=store)}` for every store the inner live
  sources opened so far, and `devices`: descriptors of devices opened so far, taken from
  `inner.devices().take_opened_descriptors()`), creates the recorder and installs
  `RecordingSources(inner=<the active sources>, recorder=recorder)` (before the first frame — the
  golden harness and `GameEngine.start` both start recording before frames run).
- `pump_events`: inner batch, recorded with `record_event_batch` (moved from `_pump_events`).
- `input_snapshot`: inner snapshot; remember the changes from the previous frame's snapshot for
  this frame (first snapshot diffs against `IDLE_INPUT`).
- `saves(namespace)`: inner store; a namespace opened after recording started is snapshotted into
  this frame's `saves_opened` before the game can write to it.
- `devices()`: inner registry; `end_frame` takes `take_opened_descriptors()` into
  `devices_opened`.
- `end_frame`: `recorder.record_frame(...)` with the frame's fields; then delegate to
  `inner.end_frame(...)`.
- `frame_seconds`, `control_events_for_frame`, `stop_requested`, `random_seed`: delegate.

- [ ] **Step 1: Write the failing tests** (append to `TestRecordingThroughTheEngine` in
  `tests/world/test_gameplay_recording.py`, using `engine_run_environment`, `run_engine` and
  `Script`)

```python
    def test_recording_holds_input_changes_and_control_events(self, mocker, tmp_path):
        from glitchygames.engine.supervision import BREAKPOINT_KIND
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

    def test_header_holds_the_save_snapshot(self, mocker, tmp_path):
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

    def test_saves_opened_before_recording_are_in_the_header(self, mocker, tmp_path):
        from glitchygames.engine.sources import active_sources
        from glitchygames.state import SaveManager

        save_directory = tmp_path / 'saves'
        mocker.patch('glitchygames.state.manager.get_save_directory',
                     side_effect=lambda app_name: save_directory / app_name)
        SaveManager(app_name='header-test').save('slot', {'value': 1})
        recording_path = tmp_path / 'session.jsonl.gz'
        record_trace('paddleslap', frame_count=2, recording_path=recording_path)
        header = read_trace_result(path=recording_path).trace
        # PaddleSlap opens its saves in __init__, before the harness starts recording
        assert 'paddleslap' in header['saves']
        assert active_sources() is not None

    def test_devices_opened_are_recorded(self, mocker, tmp_path):
        from glitchygames.engine.sources import active_sources
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
    from glitchygames.engine.sources import LiveSources
    from glitchygames.engine.supervision import ControlEvent
    from glitchygames.recording import GameplayRecorder, RecordingSources
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
git add glitchygames/recording.py glitchygames/engine/game_engine.py glitchygames/scenes/scene.py tests/world/test_gameplay_recording.py tests/test_recording.py
git commit -m "Record through the doors: RecordingSources writes input, devices, saves, control events"
```

---

### Task 10: `ReplaySources` and `--replay-trace`

**Files:**
- Create: `glitchygames/replay/__init__.py` (exports), `glitchygames/replay/driver.py`
- Modify: `glitchygames/engine/game_engine.py` — `args` (diagnostics group: `--replay-trace`),
  `__init__` (start a replay), `_shutdown` (log the result)
- Test: `tests/world/test_gameplay_replay.py` (new)

**Interfaces:**
- Consumes: everything above.
- Produces (exact):

```python
REPLAY_UNUSABLE_EXIT_CODE = 2
REPLAY_LOCAL_OPTIONS: frozenset[str]   # options the recording never overrides
class ReplayRefusedError(RuntimeError): ...
@dataclasses.dataclass(frozen=True)
class Divergence:
    frame_number: int
    kind: str          # SPRITE_DIVERGENCE | EVENT_DIVERGENCE | LENGTH_DIVERGENCE
    subject: str
    field: str
    expected: object
    actual: object
    def describe(self) -> str: ...
@dataclasses.dataclass
class ReplayResult:
    frames_replayed: int = 0
    divergence: Divergence | None = None
    end_reason: str = 'running'   # 'end_of_recording' | 'diverged' | 'truncated' | 'quit'
class ReplaySources:   # EngineSources
    def __init__(self, *, header: dict[str, Any], frames: Sequence[dict[str, Any]],
                 format_version: int, is_truncated: bool = False) -> None: ...
    @classmethod
    def from_path(cls, *, path: Path) -> ReplaySources: ...
    header: dict[str, Any]
    result: ReplayResult
    def check_game(self, *, game_class_name: str) -> None: ...   # raises ReplayRefusedError
def apply_recorded_options(*, options: dict[str, Any], recorded: dict[str, Any]) -> None: ...
def start_replay(*, engine: GameEngine, path: Path, game_class_name: str) -> ReplaySources: ...
```

Replay rules (implement exactly; they are what makes the replay exact):

1. **Start** (`start_replay`, called from `GameEngine.__init__` right after
   `initialize_arguments` when `options['replay_trace']` is set, before the random seed line):
   read the recording (`ReplaySources.from_path`); `check_game` (header `game_class` vs the
   game's class name; mismatch → `ReplayRefusedError`); `apply_recorded_options` (every recorded
   option except `REPLAY_LOCAL_OPTIONS` = `{'replay_trace', 'record_trace', 'audit',
   'replay_digest', 'headless', 'rebaseline', 'profile', 'log_level', 'windowed', 'video_driver',
   'debug_overlay', 'log_timer_jitter', 'timer_backend', 'sleep_granularity_ns',
   'windows_timer_1ms', 'perf_trim_percent', 'fps_histogram'}`) into `GameEngine.OPTIONS` and the
   local `options`; seed with `seed_engine_random(seed=header['random_seed'])`; after
   `reset_sources()` install the replay sources (the `GameEngine.__init__` code from Task 2 must
   install `ReplaySources` instead of `LiveSources` when replaying). A different `engine_version`
   logs one warning. `ReplayRefusedError` (and `TraceFormatError` from reading) → log the message
   at ERROR and `raise SystemExit(REPLAY_UNUSABLE_EXIT_CODE)`.
2. **Pump** (`pump_events`): drain the real queue with `pygame.event.get()`; classify each real
   event with `event_origin(event=..., pending=<the internal-post list>)` (start tracking posts
   when the replay sources are created, as `GameplayRecorder` does: add
   `start_tracking_internal_posts()` / `stop_tracking_internal_posts()` /
   `pending_internal_posts()` helpers to `recording.py` and use them in both). Real external events
   are dropped, except `pygame.QUIT` (window close), which is kept as the last event of the batch
   so closing the window ends the replay. Then build the batch from the recorded batch for this
   pump, in recorded order: an `external` record → `event_from_record(record)`; an `internal`
   record → take the first live internal event whose `event_to_record(event=..., origin='internal')`
   equals the record; none → `Divergence(kind=EVENT_DIVERGENCE, subject=record['name'],
   field='missing internal event', expected=record, actual=None)`. Live internal events left over →
   `Divergence(..., field='unexpected internal event', expected=None, actual=<record>)`. More
   pumps in a frame than recorded → `LENGTH_DIVERGENCE` (`field='pump count'`). Recorded
   references are mapped back before injecting (spec 1.3): a `RecordedReference` of kind
   `'window'` in an attribute becomes the current window (`pygame.display.get_surface()`'s
   window — check how pygame-ce exposes it: `pygame.Window.from_display_module()`), one of kind
   `'joystick'` becomes `devices().joystick_for_instance(instance_id=...)` (the stand-in, or
   the reference itself when none was opened); an `UnrepresentableValue` stays as it is and
   is logged once per type at DEBUG. Test both mappings in `tests/world/test_gameplay_replay.py`
   with a recorded `WINDOWFOCUSGAINED`-style event carrying a window reference.
3. **Frame time** (`frame_seconds`): the first call returns frame 0's `dt`; each later call returns
   the next frame's `dt`; past the end, `measured`.
4. **Input** (`input_snapshot`): the current frame's snapshot, rebuilt by applying each frame's
   `input_changes` in order (format version 2 → `IDLE_INPUT` and one warning: "recorded before
   input-state capture; polled input will read as idle").
5. **Devices** (`devices()`): a `ReplayDeviceRegistry` from the header's `devices`, learning each
   frame's `devices_opened` at that frame's first pump.
6. **Saves** (`saves(namespace)`): `SandboxSaves(app_name=namespace, envelopes=...)` from the
   header's `saves` (or the frame's `saves_opened`); unknown namespace → empty sandbox.
7. **Control events** (`control_events_for_frame`): the frame's recorded `control_events` of a
   kind in `REAPPLIED_CONTROL_EVENT_KINDS`, as `ControlEvent.from_json`. In `end_frame`, the
   frame's other (marker) control events — the ones the replayed code recorded by itself —
   must equal the recorded markers of that frame, in order; a mismatch is an
   `EVENT_DIVERGENCE` (`field='control event'`). Test it with a marker kind registered only in
   the test (`'test-marker'`) recorded live by a scripted action and again on replay.
8. **End of frame** (`end_frame`): sample with `sample_scene_frame` and the sources' own
   `StableSpriteIds`; compare `scene` and then sprites in order with the recorded frame (first
   difference only: a missing or extra sprite id → `field='present'`; else `rect` then `visible`);
   record `frames_replayed`; on a divergence or after the last recorded frame set
   `stop_requested` and `end_reason` (`'truncated'` when the file was cut off).
9. **End of run**: `GameEngine._shutdown` logs `result.divergence.describe()` at ERROR or "Replay
   matched N frames" at INFO, and stops tracking posts.

`Divergence.describe()` format: `"frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got
[412, 301, 16, 16]"`.

- [ ] **Step 1: Write the failing tests** (`tests/world/test_gameplay_replay.py`)

```python
"""Replays through the real engine: record a session, replay it, compare every frame."""

from __future__ import annotations

import gzip
import json
from typing import TYPE_CHECKING

import pygame
import pytest
from scripts.record_golden_traces import GAME_SCENES, record_trace, replay_golden_recording

from glitchygames.replay.driver import (
    EVENT_DIVERGENCE,
    REPLAY_UNUSABLE_EXIT_CODE,
    SPRITE_DIVERGENCE,
    ReplaySources,
)
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
    from pathlib import Path

GOLDEN_SCRIPT_FRAMES = 300


def record_session(tmp_path: Path, mocker, *, action: Callable[[], None] | None = None,
                   action_frame: int = 1) -> Path:
    recording_path = tmp_path / 'session.jsonl.gz'
    # engine_run_environment resets Script, so the script is set inside it
    with engine_run_environment(mocker):
        Script.events_by_frame = {1: [_key(pygame.KEYDOWN, pygame.K_a, unicode='a')],
                                  2: [_key(pygame.KEYUP, pygame.K_a)]}
        Script.action, Script.action_frame = action, action_frame
        _schedule_quit_in_arrival()
        run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
    return recording_path


def replay_session(recording_path: Path, mocker, *,
                   events_by_frame: dict[int, list[pygame.event.Event]] | None = None,
                   action: Callable[[], None] | None = None, action_frame: int = 1):
    """Replay through the real engine; the scenes' own scripted posts happen again, as they
    would in the game (the departure scene posts its events from dt_tick, i.e. as code)."""
    with engine_run_environment(mocker):
        Script.events_by_frame = events_by_frame or {}
        Script.action, Script.action_frame = action, action_frame
        engine = run_engine('--replay-trace', str(recording_path))
    return engine


class TestRoundTrip:
    def test_scripted_session_replays_without_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path, mocker)
        engine = replay_session(recording_path, mocker)
        result = engine.replay_sources.result
        assert result.divergence is None
        assert result.end_reason == 'end_of_recording'

    @pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
    def test_golden_script_recording_replays_without_divergence(self, game_key, tmp_path, mocker):
        recording_path = tmp_path / f'{game_key}.jsonl.gz'
        record_trace(game_key, frame_count=GOLDEN_SCRIPT_FRAMES, recording_path=recording_path)
        result = replay_golden_recording(game_key=game_key, path=recording_path)
        assert result.divergence is None
        assert result.frames_replayed == GOLDEN_SCRIPT_FRAMES


class TestDivergence:
    def test_a_one_pixel_change_is_reported_at_its_frame(self, mocker, tmp_path):
        recording_path = record_session(tmp_path, mocker)
        tamper_first_sprite_rect(recording_path, frame_number=3)
        engine = replay_session(recording_path, mocker)
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        assert (divergence.frame_number, divergence.kind, divergence.field) == (
            3, SPRITE_DIVERGENCE, 'rect')

    def test_missing_internal_event_is_a_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path, mocker)
        add_recorded_internal_event(recording_path, frame_number=2)
        engine = replay_session(recording_path, mocker)
        divergence = engine.replay_sources.result.divergence
        assert divergence.kind == EVENT_DIVERGENCE
        assert divergence.field == 'missing internal event'
        assert divergence.frame_number == 2


class TestRefusals:
    def test_wrong_game_is_refused(self, mocker, tmp_path):
        recording_path = record_session(tmp_path, mocker)
        rewrite_header(recording_path, game_class='SomeOtherGame')
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path, mocker)
        assert exit_info.value.code == REPLAY_UNUSABLE_EXIT_CODE

    def test_truncated_recording_replays_to_the_cut_off(self, mocker, tmp_path):
        recording_path = record_session(tmp_path, mocker)
        cut_off_after_frame(recording_path, frame_number=2)
        engine = replay_session(recording_path, mocker)
        assert engine.replay_sources.result.end_reason == 'truncated'
        assert engine.replay_sources.result.frames_replayed == 3

    def test_version_two_recording_replays_with_a_warning(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path, mocker)
        downgrade_to_version_two(recording_path)
        engine = replay_session(recording_path, mocker)
        assert engine.replay_sources.result.divergence is None
        assert 'polled input will read as idle' in caplog.text


class TestIsolation:
    def test_real_input_during_replay_never_reaches_the_game(self, mocker, tmp_path):
        recording_path = record_session(tmp_path, mocker)
        # A real key press arrives in pygame's queue during the replay: it must be dropped
        engine = replay_session(recording_path, mocker, events_by_frame={
            1: [_key(pygame.KEYDOWN, pygame.K_z, unicode='z')]})
        assert engine.replay_sources.result.divergence is None

    def test_replay_never_writes_real_saves(self, mocker, tmp_path):
        from glitchygames.state import SaveManager
        from glitchygames.state.sandbox import open_saves

        save_directory = tmp_path / 'saves'
        mocker.patch('glitchygames.state.manager.get_save_directory',
                     side_effect=lambda app_name: save_directory / app_name)
        SaveManager(app_name='replay-test').save('slot', {'value': 1})

        def write_slot() -> None:
            open_saves(app_name='replay-test').save('slot', {'value': 2})

        recording_path = record_session(tmp_path, mocker, action=write_slot)
        SaveManager(app_name='replay-test').save('slot', {'value': 1})  # undo the live write
        slot_file = next((save_directory / 'replay-test').iterdir())
        bytes_before = slot_file.read_bytes()
        engine = replay_session(recording_path, mocker, action=write_slot)
        assert engine.replay_sources.result.divergence is None
        assert slot_file.read_bytes() == bytes_before
```

Write the helpers in the same file: `tamper_first_sprite_rect` (read with `read_trace_result`,
add 1 to `rect[1]` of the first sprite of `frame_number` and every later frame, write back with
`write_trace(trace=..., path=...)` — format 3 keeps the extra fields), `add_recorded_internal_event`
(append an internal `USEREVENT + 41` record to that frame's batch), `rewrite_header`,
`cut_off_after_frame` (write the gzip bytes of the first `frame_number + 2` lines, then half of the
next line, with no gzip end-of-stream: `zlib.compressobj(wbits=GZIP_WINDOW_BITS)` without
`flush(Z_FINISH)`), `downgrade_to_version_two` (drop the format-3 fields and write
`format_version: 2`), and `replay_golden_recording(*, game_key, path) -> ReplayResult`. Put
`replay_golden_recording` in `scripts/record_golden_traces.py` next to `record_trace` (keep
`record_trace` unchanged) so it shares the harness setup:

```python
def replay_golden_recording(*, game_key: str, path: Path) -> ReplayResult:
    """Replay a recording made by record_trace(recording_path=...) through the harness.

    Key events and per-frame input come from the recording (the replay's event pump), so they
    are not posted again. The script's placements are not input — they move sprites directly,
    like a supervisor — so they are applied again on the same frames, before the frame runs, as
    record_trace applies them.
    """
    script = SCRIPT_BUILDERS[game_key]()
    with (
        tempfile.TemporaryDirectory(prefix='golden-replay-saves-') as save_directory,
        deterministic_environment(clock=FakeClock(start_seconds=FAKE_CLOCK_START_SECONDS),
                                  save_root=Path(save_directory)),
    ):
        manager = _start_game(game_key, random_seed=RANDOM_SEED,
                              extra_arguments=['--replay-trace', str(path)])
        engine = manager.game_engine
        assert engine is not None and engine.replay_sources is not None
        sources = engine.replay_sources
        try:
            frame_number = 0
            while not sources.stop_requested and manager.active_scene is not None:
                manager.dt = sources.frame_seconds(measured=FRAME_SECONDS)
                for placement in script.placements.get(frame_number, []):
                    placement(manager.active_scene)
                manager.run_frame()
                frame_number += 1
        finally:
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()
    return sources.result
```

`_start_game` gains `extra_arguments: list[str] | None = None` appended to its command line
(`--random-seed` is then overridden by the recording's seed, as rules 1 says). If Task 7 removed
the `clock` parameter of `deterministic_environment`, drop it here too. `manager.dt` is set from
the frame-time door because the harness steps frames without `start()`/`_finish_frame`; the first
call returns frame 0's `dt`, each later call the next frame's, exactly as rule 3 describes. `GameEngine.replay_sources`
is the attribute `start_replay` sets (None when not replaying). The `Script.events_by_frame` in
`test_real_input_during_replay_never_reaches_the_game` makes the departure scene post a real `z`
press during the replay: it must be dropped (it is external), so the replay still matches.

- [ ] **Step 2: Run to see them fail** — Expected: `ModuleNotFoundError: glitchygames.replay`.

- [ ] **Step 3: Implement `glitchygames/replay/driver.py`** following rules 1–9 (module docstring
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
  the golden test and the full suite. Expected: PASS, no warnings.

- [ ] **Step 5: Lint, type-check, vulture, commit**

```bash
git add glitchygames/replay/__init__.py glitchygames/replay/driver.py glitchygames/engine/game_engine.py glitchygames/recording.py tests/world/test_gameplay_replay.py <harness file if changed>
git commit -m "Replay recordings exactly through the engine with --replay-trace"
```

---

### Task 11: `--audit`

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
class TestAudit:
    def test_frame_digest_is_canonical(self):
        from glitchygames.replay.audit import frame_digest

        first = frame_digest(frame_record={'b': 1, 'a': [1, 2]})
        second = frame_digest(frame_record={'a': [1, 2], 'b': 1})
        assert first == second

    def test_identical_runs_are_deterministic(self, tmp_path, mocker):
        from glitchygames.replay import audit

        mocker.patch.object(audit, '_run_replay_subprocess',
                            side_effect=[fake_run(['a', 'b'], None), fake_run(['a', 'b'], None)])
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.is_deterministic()

    def test_runs_that_differ_report_the_first_frame(self, tmp_path, mocker):
        from glitchygames.replay import audit

        mocker.patch.object(audit, '_run_replay_subprocess',
                            side_effect=[fake_run(['a', 'b', 'c'], None),
                                         fake_run(['a', 'x', 'c'], None)])
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.first_mismatch_frame == 1
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

with, at module level (add `import os`, `import subprocess`, `import sys` to the imports):

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

### Task 12: Documentation

**Files:**
- Modify: `CLAUDE.md` (Gameplay Recording section → "Gameplay Recording and Replay"; doors,
  `current_input()`/`GameEngine.input`, `Scene.game_time`, `frame_clock_seconds`, `open_saves`,
  the devices registry, supervisor hook, control events, `--replay-trace`, `--audit`, format 3)
- Modify: `glitchygames/recording.py` module docstring (already updated in Task 9; check it
  mentions replay as implemented, not planned)
- Create or modify: a docs page — find where recording is documented under `docs/`
  (`grep -rln "record-trace" docs mkdocs.yml`); add a "Replay" page or section and its nav entry
- Modify: `plans/future-work.md` — replace the "Gameplay replay" entry with a pointer to the
  spec and these plans; keep and update: Bitmappy wall-clock reads (now listed as the guard
  test's `bitmappy/` allowance), anything from the replay entry not done here
- Test: `uv run mkdocs build --strict -d <scratch>; echo EXIT=$?`

- [ ] **Step 1:** Write the CLAUDE.md section (replace the "Replay (`--replay-trace`) is planned"
  sentence), each fact checked against the code (file:line in your report).
- [ ] **Step 2:** Docs page + nav; run mkdocs strict; `EXIT=0`.
- [ ] **Step 3:** future-work update.
- [ ] **Step 4:** Lint (docs only: none), full suite once, commit:

```bash
git add CLAUDE.md docs/<page> mkdocs.yml plans/future-work.md
git commit -m "Document the engine doors and gameplay replay"
```

---

## Self-review notes (for the executor)

- `EngineSources` grows across Tasks 2, 3, 5, 6, 8; the final shape is in the master plan's
  Cross-part interfaces. Every implementation (`LiveSources`, `RecordingSources`,
  `ReplaySources`, and Part 3's scoped sources) must implement all of it.
- The golden test runs after every task; it must never change except by Task 7's exact rule.
