# Gameplay Replay Implementation Plan (master)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replay a `--record-trace` recording exactly through the real engine, and build replay tooling and in-game playback (demos, instant replays, ghosts) on top of it.

**Architecture:** The engine reads the outside world only through a small set of swappable
**doors** (`glitchygames/sources.py`): event pump, frame time, polled input, devices, saves
and the random seed. Live play uses `LiveSources`; `--record-trace` wraps them in
`RecordingSources`; `--replay-trace` installs `ReplaySources` built from a recording. Everything
downstream of the doors (dispatch, transitions, frame order, rendering) runs unchanged, and the
replay compares each frame's sprites with the recording. Tooling and in-game playback reuse
`ReplaySources`; playback runs in a scope on top of the live sources.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8, pytest + pytest-mock, uv, ruff, basedpyright, ty.

**Spec:** `plans/2026-10-19-gameplay-replay.md`

**Sub-plans (execute in this order):**

1. [Part 1 — Replay core](2026-10-19-gameplay-replay-core.md) (13 tasks)
2. [Part 2 — Replay tooling](2026-10-19-gameplay-replay-tooling.md) (6 tasks)
3. [Part 3 — In-game playback](2026-10-19-gameplay-replay-playback.md) (6 tasks)

Part 2 and Part 3 both depend on all of Part 1 and are independent of each other. Run Part 2
first anyway: Part 3 Task 5 (instant replay) reuses the `presents_frames()` and
`paced_frame_seconds()` doors Part 2 adds (Part 3 says what to add if Part 2 has not run).

## Global Constraints

- Python 3.14 target; manage everything with `uv` (`uv run ...`), never pip/venv/pyenv.
- Every time read in `glitchygames/` comes from `glitchygames/clock.py` or `Scene.game_time`;
  only the files in the guard test's allow list (`tests/test_engine_doors.py`) read the raw
  clock. No directory (Bitmappy included) is exempt.
- Exactness: same engine version + same recording → bit-identical sprite traces (every frame's
  sprite `rect` and `visible`, as `glitchygames.tracing.sample_scene_frame` samples them). Audio is
  played, never compared.
- Live play without recording must behave exactly as before: the golden traces
  (`tests/world/test_golden_traces.py`) stay unchanged, except the behaviour fixes of spec section
  3.4 (wall-clock cooldowns/blinks no longer advancing while paused); each such difference gets an
  exact `ExpectedDifference` rule that proves its cause — never edit a baseline.
- No lint or type suppressions of any kind (`# type: ignore`, `# noqa`, `# pyright: ignore`,
  `# ty: ignore`, `# ruff: ignore`) in new or changed lines; never change lint/type-checker config
  (`pyproject.toml` tool sections, `pyrightconfig.json`, `.pre-commit-config.yaml`,
  `vulture_whitelist.py`, `noxfile.py`). If a config change seems needed, stop and ask.
- Keyword arguments at call sites; keyword-only (`*,`) parameters for new public functions with
  more than one parameter.
- No abbreviated names (`event` not `evt`, `index` not `idx`, `snapshot` not `snap`).
- Google-style docstrings; ruff 100-character lines; match the surrounding code's comment density.
- Tests: pytest assertions; pytest-mock's `mocker` fixture (never `unittest.mock`); put new tests in
  existing test files where the subject already has one; descriptive test file names; TDD (write
  the failing test, run it, see it fail, then implement).
- Read comments attached to code before modifying it.
- Git: path-scoped `git add <paths>` only (the repo root holds untracked scratch files that must
  never be committed); never `git add -A`/`.`; never push, amend, rebase, stash, restore or
  checkout; never `sed -i`. One commit per task unless the task says otherwise; end commit messages
  with the attribution trailer given in the session.
- Run linters and type checkers before tests: `uv run ruff check glitchygames tests scripts
  noxfile.py`, `uv run ruff format --check glitchygames tests scripts noxfile.py`,
  `uv run basedpyright`, `uv run nox -s static-analysis-ty` (the 50 known warnings only),
  `uv run vulture glitchygames vulture_whitelist.py --min-confidence=80` (exit 0).
- Full suite: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest -q -p no:cacheprovider`,
  read in the foreground. If you time it, zsh prints "... total", never "real" — do not wait for a
  "real" line. No warnings may appear; a warning is a bug to understand.
- Docs build: `uv run mkdocs build --strict -d <scratch dir>; echo EXIT=$?` must print `EXIT=0`.
- Report any bug you notice in passing (the report, and `BUGS.md` if not fixed).

## Review Focus

1. A replay started with a different game than the recording, a truncated file or a version-2
   recording: refused with exit 2 / replayed to the cut-off / replayed with one warning — never a
   traceback (Part 1 Task 11, tests `test_wrong_game_is_refused`, `test_truncated_recording_*`,
   `test_version_two_recording_replays_with_a_warning`).
2. Real keyboard, mouse and window events arriving during a replay (the user touching the keyboard,
   the window losing focus): they must never reach the game, and the replay stays exact (Part 1
   Task 11, `test_real_input_during_replay_never_reaches_the_game`).
3. A recorded internal event that the replayed code does not post again, or an extra one it posts:
   reported as an event divergence at the right frame, not silently merged (Part 1 Task 11,
   `test_missing_internal_event_is_a_divergence`).
4. A controller present while recording and absent while replaying (and the reverse): stand-ins
   answer, nothing raises `pygame.error`, and a real device plugged in during the replay is
   ignored (Part 1 Task 5, `test_replay_registry_never_opens_real_hardware`).
5. A demo or instant replay that raises inside its scope, or whose recording diverges: the scope
   ends, the live scene is untouched and the random streams/saves are restored (Part 3 Task 2,
   `test_error_inside_scope_restores_the_live_game`).

## File structure

| File | Responsibility | Part |
|---|---|---|
| `glitchygames/sources.py` (new) | `EngineSources` Protocol, `LiveSources`, the active-sources registry (`active_sources`, `install_sources`, `push_scoped_sources`, `pop_scoped_sources`), `frame_clock_seconds` | 1 |
| `glitchygames/clock.py` (new) | the clock exports: `frame_clock_seconds`, `frame_clock_milliseconds`, `wall_clock_time`, `wall_clock_epoch_seconds`, `elapsed_seconds` (live and replay providers behind the doors) | 1 |
| `glitchygames/input/state.py` (new) | `InputSnapshot`, `capture_live_snapshot`, `current_input`, snapshot diffs | 1 |
| `glitchygames/input/devices.py` (new) | `DeviceRegistry`, `LiveDeviceRegistry`, `DeviceDescriptor`, `ReplayJoystick`, `ReplayController` | 1 |
| `glitchygames/state/sandbox.py` (new) | `SaveStore` Protocol, `SandboxSaves`, `open_saves`, `save_namespace_snapshot` | 1 |
| `glitchygames/supervision.py` (new) | `Supervisor` Protocol, `ControlEvent`, control-event kinds | 1 |
| `glitchygames/recording.py` | `RecordingSources`; `GameplayRecorder` records format-3 fields | 1 |
| `glitchygames/tracing.py` | format version 3 (reads 2 and 3) | 1 |
| `glitchygames/replay/__init__.py`, `glitchygames/replay/driver.py` (new) | `ReplaySources`, `Divergence`, frame comparison, `ReplayResult`, option override | 1 |
| `glitchygames/replay/audit.py` (new) | `--audit`: two subprocess replays, per-frame digests | 1 |
| `glitchygames/engine/game_engine.py` | doors in `_pump_events`, input capture, `--replay-trace`/`--audit` options, install sources | 1, 2 |
| `glitchygames/scenes/scene.py` | `frame_number`, `Scene.game_time`, frame clock, supervisor slot, dt via doors, playback hooks | 1, 3 |
| bypass sites (spec 3.4) and every raw clock read in `glitchygames/` (Bitmappy's 74 included) | moved behind the doors / onto `glitchygames/clock.py` (Part 1 Tasks 7, 8) | 1 |
| `glitchygames/replay/controls.py` (new) | watched-replay controls, status bar, step back, bookmarks | 2 |
| `glitchygames/testing/__init__.py`, `glitchygames/testing/replays.py` (new) | pytest plugin | 2 |
| `glitchygames/replay/rebaseline.py` (new) | `--rebaseline` | 2 |
| `glitchygames/replay/playback.py` (new) | playback scope, `play_recording`, instant replay | 3 |
| `glitchygames/replay/ghosts.py` (new) | `GhostRecorder`, `GhostTrack`, `GhostSprite` | 3 |

## Cross-part interfaces (exact names every part uses)

```python
# glitchygames/sources.py (Part 1 Task 2)
class EngineSources(Protocol):
    random_seed: int
    @property
    def stop_requested(self) -> bool: ...                                   # Part 1 Task 2
    def pump_events(self) -> list[pygame.event.Event]: ...                 # Part 1 Task 2
    def frame_seconds(self, *, measured: float) -> float: ...              # Part 1 Task 2
    def input_snapshot(self) -> InputSnapshot: ...                          # Part 1 Task 3
    def devices(self) -> DeviceRegistry: ...                                # Part 1 Task 5
    def saves(self, *, namespace: str) -> SaveStore: ...                   # Part 1 Task 6
    def wall_clock_time(self) -> datetime.datetime: ...                     # Part 1 Task 7
    def elapsed_seconds(self) -> float: ...                                 # Part 1 Task 7
    def control_events_for_frame(self, *, frame_number: int) -> list[ControlEvent]: ...  # Task 9
    def end_frame(self, *, frame_number: int, dt: float, scene: Scene | None,
                  control_events: list[ControlEvent]) -> None: ...          # Part 1 Tasks 2, 9
    def paced_frame_seconds(self) -> float | None: ...                      # Part 2 Task 1
    def hold_frame(self) -> bool: ...                                        # Part 2 Task 2
    def draw_overlay(self, *, surface: pygame.Surface) -> None: ...        # Part 2 Task 2
    def presents_frames(self) -> bool: ...                                   # Part 2 Task 3

class LiveSources: ...                     # implements EngineSources
def active_sources() -> EngineSources: ... # scoped sources if any, else installed, else LiveSources
def install_sources(*, sources: EngineSources) -> None: ...   # before the first frame only
def push_scoped_sources(*, sources: EngineSources) -> None: ...    # Part 3 Task 2
def pop_scoped_sources() -> EngineSources: ...                      # Part 3 Task 2
def frame_clock_seconds() -> float: ...    # sum of every frame's raw dt this run
class SourcesAlreadyRunningError(RuntimeError): ...

# glitchygames/clock.py (Part 1 Tasks 7, 8) — the only place code reads time from
def frame_clock_seconds() -> float: ...        # blinks, animation, FPS events, "how long since"
def frame_clock_milliseconds() -> int: ...     # the same, in ms (widget blink timers)
def wall_clock_time() -> datetime.datetime: ...   # UTC-aware; timestamps
def wall_clock_epoch_seconds() -> float: ...   # wall_clock_time().timestamp()
def elapsed_seconds() -> float: ...            # durations, metrics, controller timing
# live: now / time.monotonic(); replay: header recorded_at + frame clock / frame clock
# Scene.game_time (gameplay timers) stays on the scene.
# Raw clock only in: timing.py, SceneManager pacing (scenes/scene.py perf_counter),
# performance/, debug/, audio/diagnostics.py, the recorded_at stamp, api/client.py.

# glitchygames/input/state.py (Part 1 Task 3)
@dataclasses.dataclass(frozen=True)
class InputSnapshot:
    pressed_scancodes: frozenset[int]
    modifiers: int
    mouse_position: tuple[int, int]
    mouse_buttons: tuple[bool, bool, bool]
    mouse_focused: bool
    device_axes: Mapping[int, tuple[float, ...]]      # instance id -> axes
    device_buttons: Mapping[int, tuple[bool, ...]]
    device_hats: Mapping[int, tuple[tuple[int, int], ...]]
    def key_pressed(self, key: int) -> bool: ...
    @property
    def pressed_keys(self) -> pygame.key.ScancodeWrapper: ...  # drop-in for get_pressed()
    def axis(self, *, device_id: int, axis: int) -> float: ...
    def button(self, *, device_id: int, button: int) -> bool: ...
    def hat(self, *, device_id: int, hat: int) -> tuple[int, int]: ...
IDLE_INPUT: InputSnapshot
def current_input() -> InputSnapshot: ...       # the frame's snapshot (GameEngine.input too)
def snapshot_changes(*, previous: InputSnapshot, current: InputSnapshot) -> dict[str, Any]: ...
def apply_snapshot_changes(*, previous: InputSnapshot, changes: dict[str, Any]) -> InputSnapshot: ...

# Scene (Part 1 Task 4)
Scene.game_time: float                          # property; logic seconds, stops while paused

# glitchygames/supervision.py (Part 1 Task 9)
class Supervisor(Protocol):
    def on_frame(self, *, frame_number: int, scene: Scene | None) -> None: ...
SceneManager.add_supervisor(*, supervisor: Supervisor) -> None
SceneManager.remove_supervisor(*, supervisor: Supervisor) -> None
SceneManager.record_control_event(*, kind: str, data: dict[str, Any]) -> None
SceneManager.add_control_event_handler(*, kind: str, handler: Callable[[ControlEvent], None]) -> None
@dataclasses.dataclass(frozen=True)
class ControlEvent:
    kind: str                # 'breakpoint' | 'playback' (Part 3) | future 'cheat'
    data: dict[str, Any]     # JSON-safe
# Recorded form: {"kind": "breakpoint", "label": "ball through paddle"} (data merged with kind)
BREAKPOINT_KIND = 'breakpoint'
PLAYBACK_KIND = 'playback'
REAPPLIED_CONTROL_EVENT_KINDS = frozenset({BREAKPOINT_KIND})  # markers are compared, not re-applied

# Trace format version 3 (Part 1 Task 1)
TRACE_FORMAT_VERSION = 3; READABLE_FORMAT_VERSIONS = (2, 3)
# per-frame fields (present only when non-empty): 'input_changes', 'control_events',
#   'devices_opened', 'saves_opened', 'scene_start' (Part 3)
# header fields: 'saves' ({namespace: {slot: envelope}}), 'devices' ([descriptor, ...])

# glitchygames/replay/driver.py (Part 1 Task 11; keywords added in Part 2)
class ReplaySources:   # implements EngineSources
    def __init__(self, *, header: dict[str, Any], frames: Sequence[dict[str, Any]],
                 format_version: int, is_truncated: bool = False,
                 headless: bool = False,              # Part 2 Task 1
                 start_frame: int = 0,                # Part 2 Task 3
                 stop_on_divergence: bool = True) -> None: ...   # Part 2 Task 6
    @classmethod
    def from_path(cls, *, path: Path, headless: bool = False) -> ReplaySources: ...
    @classmethod
    def for_playback(cls, *, header, frames, start_frame: int = 0) -> ReplaySources: ...  # Part 3
    def recorded_dt(self, *, frame_number: int) -> float: ...       # Part 2 Task 2
    result: ReplayResult
@dataclasses.dataclass(frozen=True)
class Divergence:
    frame_number: int
    kind: str          # 'sprite' | 'event' | 'length'
    subject: str       # sprite id, event name, or 'recording'
    field: str
    expected: object
    actual: object
    def describe(self) -> str: ...
@dataclasses.dataclass
class ReplayResult:
    frames_replayed: int
    divergence: Divergence | None
    end_reason: str    # 'end_of_recording' | 'diverged' | 'truncated' | 'quit'

# Part 3
Scene.replay_arguments(self) -> dict[str, Any]
Scene.INSTANT_REPLAY_SECONDS: ClassVar[float | None] = None
Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS: ClassVar[float] = 60.0
SceneManager.play_recording(*, path: Path, then: Scene) -> None
SceneManager.instant_replay() -> bool
```

## After all three parts

- Final whole-branch review (subagent-driven) against the spec and this plan.
- Update `plans/future-work.md` (Part 1 Task 13 replaces the "Gameplay replay" entry; Part 3 adds
  the state-snapshot and cheat-device follow-ups) and `CLAUDE.md`.
- Never push; the user pushes.
