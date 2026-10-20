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

1. [Part 1 — Replay core](2026-10-19-gameplay-replay-core.md) (15 tasks)
2. [Part 2 — Replay tooling](2026-10-19-gameplay-replay-tooling.md) (6 tasks)
3. [Part 3 — In-game playback](2026-10-19-gameplay-replay-playback.md) (7 tasks)

Order: Part 1, then Part 2, then Part 3. Part 3 depends on Part 2: its bundled demo (Task 4) is
recorded with Part 2's `scripts/record_scripted_session.py` and tested through Part 2's replay
plugin, its instant replay (Task 6) uses Part 2's `presents_frames()` / `paced_frame_seconds()`
doors and unpaced pacing path, and its journal test uses `recorded_dt`.

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
  more than one parameter, test helpers included. Exception (interface conformance): drop-in
  stand-ins keep the signatures of the API they replace — `ReplayJoystick`/`ReplayController`
  methods (pygame's), `SaveStore`/`SandboxSaves` (`SaveManager`'s), `InputSnapshot.key_pressed`
  (`get_pressed()[key]`), pytest hooks — each says so in its docstring.
- Layering: `glitchygames/sources.py` and `glitchygames/clock.py` are leaves (see the layering
  rule under File structure); break import cycles with leaf modules and `TYPE_CHECKING`-only type
  imports, never with undocumented function-level imports.
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
   traceback (Part 1 Task 12, tests `test_wrong_game_is_refused`, `test_truncated_recording_*`,
   `test_version_two_recording_replays_with_a_warning`).
2. Real keyboard, mouse and window events arriving during a replay (the user touching the keyboard,
   the window losing focus): they must never reach the game, and the replay stays exact (Part 1
   Task 13, `test_real_input_during_replay_never_reaches_the_game`).
3. A recorded internal event that the replayed code does not post again, or an extra one it posts:
   reported as an event divergence at the right frame, not silently merged (Part 1 Task 13,
   `test_missing_internal_event_is_a_divergence`, `test_extra_internal_event_is_a_divergence`).
4. A controller present while recording and absent while replaying (and the reverse): stand-ins
   answer, enumeration answers come from the recording, nothing raises `pygame.error`, and a real
   device plugged in during the replay is ignored (Part 1 Task 5,
   `test_replay_registry_never_opens_real_hardware`,
   `test_replay_enumeration_answers_in_recorded_order_then_repeats_the_last`).
5. A demo or instant replay that raises inside its scope, or whose recording diverges: the scope
   ends, the live scene is untouched and the random streams/saves are restored (Part 3 Task 2,
   `test_error_inside_scope_restores_the_live_game`).

## File structure

| File | Responsibility | Part |
|---|---|---|
| `glitchygames/sources.py` (new, leaf) | `EngineSources` Protocol, `FrameInputListener`, the active-sources registry (`active_sources`, `install_sources`, `push_scoped_sources`, `pop_scoped_sources`, `reset_sources`), the frame clock | 1, 3 |
| `glitchygames/live_sources.py` (new) | `LiveSources`, the live providers | 1 |
| `glitchygames/clock.py` (new, leaf) | the clock exports: `frame_clock_seconds`, `frame_clock_milliseconds`, `wall_clock_time`, `wall_clock_epoch_seconds`, `elapsed_seconds`, `measured_seconds` | 1 |
| `glitchygames/input/state.py` (new) | `InputSnapshot`, `capture_live_snapshot`, `current_input`, snapshot diffs | 1 |
| `glitchygames/input/devices.py` (new) | `DeviceRegistry` (enumeration, opening, polling), `LiveDeviceRegistry`, `ReplayDeviceRegistry`, `DeviceDescriptor`, `EnumerationAnswer`, `ReplayJoystick`, `ReplayController` | 1 |
| `glitchygames/state/sandbox.py` (new) | `SaveStore` Protocol, `SandboxSaves`, `open_saves`, `save_namespace_snapshot` | 1 |
| `glitchygames/supervision.py` (new) | `Supervisor` Protocol, `ControlEvent`, control-event kinds | 1 |
| `glitchygames/recording.py` | `RecordingSources`; `GameplayRecorder` records format-3 fields; internal-post tracker with owners | 1 |
| `glitchygames/tracing.py` | format version 3 (reads 2 and 3) | 1 |
| `glitchygames/replay/__init__.py`, `glitchygames/replay/driver.py` (new) | `ReplaySources`, `Divergence`, frame comparison, `ReplayResult`, startup, option override | 1, 2, 3 |
| `glitchygames/replay/audit.py` (new) | `--audit`: two subprocess replays, per-frame digests | 1 |
| `glitchygames/engine/game_engine.py` | doors in `_pump_events`, input capture, the one replay startup path, options | 1, 2 |
| `glitchygames/scenes/scene.py` | `frame_number`, `Scene.game_time`, frame clock, supervisor slot, dt via doors, unpaced path, playback hooks | 1, 2, 3 |
| bypass sites (spec 3.4) and every raw clock read in `glitchygames/` (Bitmappy's 74 included) | moved behind the doors / onto `glitchygames/clock.py` (Part 1 Tasks 6, 8, 9) | 1 |
| `tests/ast_scanning.py` (new) | keyword-only AST helpers shared by the randomness and door guards | 1 |
| `scripts/record_golden_traces.py` | `_golden_game`, `replay_golden_recording`, `record_trace(..., before_recording=)` | 1 |
| `glitchygames/replay/controls.py` (new) | watched-replay controls, status bar, step back, bookmarks | 2 |
| `glitchygames/testing/__init__.py`, `glitchygames/testing/replays.py` (new) | pytest plugin; `bundled_demo_paths`, `replay_recording_headless` | 2, 3 |
| `scripts/record_scripted_session.py` (new) | records a golden input script through the real engine (fixtures, bundled demos) | 2 |
| `glitchygames/replay/rebaseline.py` (new) | `--rebaseline` | 2 |
| `glitchygames/replay/scene_start.py` (new) | `SceneStart`, `rebuild_scene`, `scene_start_capture_enabled` | 3 |
| `glitchygames/replay/playback.py` (new) | playback scope, `start_playback`, demos, instant-replay journal | 3 |
| `glitchygames/examples/paddleslap_demos/rally.jsonl.gz` (new) | the bundled PaddleSlap demo | 3 |
| `glitchygames/replay/ghosts.py` (new) | `GhostRecorder`, `GhostTrack`, `GhostSprite` | 3 |

**Layering rule:** `glitchygames/sources.py` and `glitchygames/clock.py` are leaves (module-level
imports: `glitchygames.randomness`, and `glitchygames.sources` for `clock.py`; types under
`TYPE_CHECKING`). Providers live in `live_sources.py`, `recording.py` and `replay/`, which import the
leaves, never the reverse. The one function-level import is `active_sources()` creating the default
`LiveSources`, documented at the import. `tests/test_clock.py::test_door_module_imports_alone`
imports each door module first and alone in a fresh interpreter.

## Cross-part interfaces (exact names every part uses)

```python
# glitchygames/sources.py — the final EngineSources (the task that adds each member in comments)
class EngineSources(Protocol):
    random_seed: int
    @property
    def stop_requested(self) -> bool: ...                                    # Part 1 Task 2
    def on_installed(self) -> None: ...                                      # Part 1 Task 2
    def on_uninstalled(self) -> None: ...                                    # Part 1 Task 2
    def pump_events(self) -> list[pygame.event.Event]: ...                  # Part 1 Task 2
    def frame_seconds(self, *, measured: float) -> float: ...               # Part 1 Task 2
    def input_snapshot(self) -> InputSnapshot: ...                           # Part 1 Task 3
    def devices(self) -> DeviceRegistry: ...                                 # Part 1 Task 5
    def saves(self, *, namespace: str) -> SaveStore: ...                    # Part 1 Task 7
    def wall_clock_time(self) -> datetime.datetime: ...                      # Part 1 Task 8
    # (elapsed_seconds was a door from Task 8 until Task 12b made it the frame clock everywhere)
    def control_events_for_frame(self, *, frame_number: int) -> list[ControlEvent]: ...  # Part 1 Task 10
    def end_frame(self, *, frame_number: int, dt: float, scene: Scene | None,
                  control_events: list[ControlEvent]) -> None: ...           # Part 1 Tasks 2, 10
    def paced_frame_seconds(self) -> float | None: ...                       # Part 2 Task 1
    def hold_frame(self) -> bool: ...                                         # Part 2 Task 2
    def draw_overlay(self, *, surface: pygame.Surface) -> None: ...         # Part 2 Task 2
    def presents_frames(self) -> bool: ...                                    # Part 2 Task 3
    @property
    def captures_scene_starts(self) -> bool: ...                             # Part 3 Task 1
    def opened_save_stores(self) -> dict[str, SaveStore]: ...                # Part 3 Task 1
    def add_frame_input_listener(self, *, listener: FrameInputListener) -> None: ...  # Part 3 Task 5
    def remove_frame_input_listener(self, *, listener: FrameInputListener) -> None: ...  # Part 3 Task 5
def active_sources() -> EngineSources: ...  # scoped sources if any, else installed, else LiveSources
def install_sources(*, sources: EngineSources) -> None: ...   # before the first frame only
def push_scoped_sources(*, sources: EngineSources) -> None: ...    # Part 3 Task 2
def pop_scoped_sources() -> EngineSources: ...                      # Part 3 Task 2
def reset_sources() -> None: ...
def advance_frame_clock(*, seconds: float) -> None: ...   # SceneManager._finish_frame only
def frame_clock_seconds() -> float: ...    # sum of every closed frame's dt this run
class SourcesAlreadyRunningError(RuntimeError): ...
class LiveSources: ...                     # glitchygames/live_sources.py

# glitchygames/clock.py (Part 1 Tasks 8, 9) — the only place code reads time from
def frame_clock_seconds() -> float: ...        # blinks, animation, FPS events, "how long since"
def frame_clock_milliseconds() -> int: ...     # the same, in ms (widget blink timers)
def wall_clock_time() -> datetime.datetime: ...   # UTC-aware; timestamps
def wall_clock_epoch_seconds() -> float: ...   # wall_clock_time().timestamp()
def elapsed_seconds() -> float: ...            # throttles, cooldowns, timeouts (Task 12b)
def measured_seconds() -> float: ...           # real durations for logs/metrics only (Task 12b)
# wall clock live: now; replay: header recorded_at + frame clock. elapsed_seconds is the frame
# clock live and replayed; measured_seconds is time.monotonic(), never replayed, never decides
# Scene.game_time (gameplay timers) stays on the scene.
# Raw clock only in: timing.py, SceneManager pacing (scenes/scene.py perf_counter),
# performance/, debug/, audio/diagnostics.py, the recorded_at stamp, api/client.py, the
# live providers in live_sources.py, and clock.measured_seconds (Task 12b).

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
    def key_pressed(self, key: int) -> bool: ...      # positional: drop-in for get_pressed()[key]
    @property
    def pressed_keys(self) -> pygame.key.ScancodeWrapper: ...
    def axis(self, *, device_id: int, axis: int) -> float: ...
    def button(self, *, device_id: int, button: int) -> bool: ...
    def hat(self, *, device_id: int, hat: int) -> tuple[int, int]: ...
IDLE_INPUT: InputSnapshot
def current_input() -> InputSnapshot: ...       # the frame's snapshot (GameEngine.input too)
def snapshot_changes(*, previous: InputSnapshot, current: InputSnapshot) -> dict[str, Any]: ...
def apply_snapshot_changes(*, previous: InputSnapshot, changes: dict[str, Any]) -> InputSnapshot: ...

# glitchygames/input/devices.py (Part 1 Task 5)
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
# ReplayJoystick / ReplayController keep pygame's positional method signatures (drop-ins)

# glitchygames/state/sandbox.py (Part 1 Task 7)
class SaveStore(Protocol): ...   # load(slot_name), save(slot_name, data), exists, delete — the
                                 # SaveManager API, positional (drop-in)
def open_saves(*, app_name: str) -> SaveStore: ...
def save_namespace_snapshot(*, saves: SaveManager | SandboxSaves) -> dict[str, dict[str, Any]]: ...

# Scene (Part 1 Task 4)
Scene.game_time: float                          # property; logic seconds, stops while paused

# glitchygames/supervision.py (Part 1 Task 10)
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

# Trace format version 3 (Part 1 Tasks 1, 5)
TRACE_FORMAT_VERSION = 3; READABLE_FORMAT_VERSIONS = (2, 3)
# per-frame fields (present only when non-empty): 'input_changes', 'control_events',
#   'devices_opened', 'device_enumeration', 'saves_opened', 'scene_start' (Part 3)
# header fields: 'saves' ({namespace: {slot: envelope}}), 'devices' ([descriptor, ...]),
#   'device_enumeration' ([answer, ...])

# glitchygames/recording.py (Part 1 Task 11)
class RecordingSources:   # EngineSources, wraps another
    def __init__(self, *, inner: EngineSources, recorder: GameplayRecorder) -> None: ...
def start_tracking_internal_posts() -> None: ...   # one more owner
def stop_tracking_internal_posts() -> None: ...    # one owner fewer
def reset_internal_post_tracking() -> None: ...
def pending_internal_posts() -> list[tuple[int, dict[str, Any]]]: ...

# glitchygames/replay/driver.py (Part 1 Tasks 12, 13; keywords added in Parts 2 and 3)
class ReplayExitPolicy(enum.Enum):                 # Part 2 Task 1
    RESULT = 'result'                               # exit with ReplayResult.exit_code
    SUCCESS_AFTER_WRITING = 'success'               # exit 0 once the run is over (--rebaseline)
class ReplaySources:   # implements EngineSources
    def __init__(self, *, header: dict[str, Any], frames: Sequence[dict[str, Any]],
                 format_version: int, is_truncated: bool = False,
                 headless: bool = False,                          # Part 2 Task 1
                 exit_policy: ReplayExitPolicy = ReplayExitPolicy.RESULT,   # Part 2 Task 1
                 pause_at_frame: int | None = None,               # Part 2 Task 3
                 stop_on_divergence: bool = True) -> None: ...    # Part 2 Task 6
    @classmethod
    def from_path(cls, *, path: Path, headless: bool = False) -> ReplaySources: ...
    @classmethod
    def for_playback(cls, *, header: dict[str, Any], frames: Sequence[dict[str, Any]],
                     start_frame: int = 0) -> ReplaySources: ...  # Part 3 Task 2; never pauses
    def pump_events(self, *, real_events: list[pygame.event.Event] | None = None
                    ) -> list[pygame.event.Event]: ...
    def last_batch_origins(self) -> list[str]: ...
    def recorded_frame_fields(self, *, frame_index: int) -> dict[str, Any]: ...
    def recorded_dt(self, *, frame_number: int) -> float: ...     # Part 2 Task 2
    def run_exit_code(self) -> int: ...                           # Part 2 Task 1
    header: dict[str, Any]
    result: ReplayResult
def start_replay(*, path: Path, game_class_name: str, options: dict[str, Any]) -> ReplaySources: ...
GameEngine.replay_sources: ReplaySources | None
@dataclasses.dataclass(frozen=True)
class Divergence:
    frame_number: int  # the recording's frame index
    kind: str          # 'sprite' | 'event' | 'length'
    subject: str       # sprite id, event name, or 'recording'
    field: str
    expected: object
    actual: object
    def describe(self) -> str: ...
@dataclasses.dataclass
class ReplayResult:
    frames_replayed: int = 0
    divergence: Divergence | None = None
    end_reason: str = 'running'  # 'running' | 'end_of_recording' | 'diverged' | 'truncated' | 'quit'

# Part 3
Scene.replay_arguments(self) -> dict[str, Any]
Scene.INSTANT_REPLAY_SECONDS: ClassVar[float | None] = None
Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS: ClassVar[float] = 60.0
def start_playback(*, manager: SceneManager, header: dict[str, Any],
                   frames: Sequence[dict[str, Any]], then: Scene, exit_on_input: bool = False,
                   kind: str = 'demo', start_frame: int = 0) -> bool: ...
def start_playback_from_recording(*, manager: SceneManager, path: Path, then: Scene,
                                  exit_on_input: bool = False, kind: str = 'demo') -> bool: ...
SceneManager.play_recording(*, path: Path, then: Scene) -> None   # failures logged
SceneManager.instant_replay() -> bool
SceneManager.end_playback() -> None
SceneManager.playback_session -> PlaybackSession | None
SceneManager.last_playback_result -> ReplayResult | None
```

## After all three parts

- Final whole-branch review (subagent-driven) against the spec and this plan.
- Update `plans/future-work.md` (Part 1 Task 15 replaces the "Gameplay replay" entry and amends the
  spec; Part 3 Task 7 adds the state-snapshot and cheat-device follow-ups) and `CLAUDE.md`.
- Never push; the user pushes.
