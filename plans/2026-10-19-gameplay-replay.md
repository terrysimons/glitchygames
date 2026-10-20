# Gameplay Replay — Design

- **Date:** 2026-10-19
- **Branch:** `feature/gameplay-replay` (from `feature/engine-world-space`, which added `--record-trace`)
- **Status:** Design approved in conversation. Amended 2026-10-19 (core Task 15) to match what
  Part 1 (the replay core) built: sections 1, 1.1, 1.3, 1.4, 3.1, 3.2, 3.4, 3.5, 6 and 7 carry
  the amendments, each marked "Amended". User docs: `docs/architecture/gameplay_replay.md`
- **Builds on:** `glitchygames/recording.py` (`--record-trace`), `glitchygames/tracing.py` (trace
  format v2), `glitchygames/randomness.py` (named seeded streams), the "Gameplay replay" entry in
  `plans/future-work.md` (replaced by this spec)

## Goal

Replay a recorded session exactly through the real engine, and build on that for tooling and
in-game playback. One spec covers three parts (user decision): the replay core, replay tooling, and
in-game playback. The implementation plan is a master plan with one sub-plan per part.

**Uses (all four chosen by the user)**

1. **Bug reproduction:** hand over a recording; watch it replay exactly, pause and step to the bug.
2. **Regression tests:** recordings of real play replay headless in pytest and fail on the first
   divergence.
3. **In-game playback:** attract-mode demos, instant replays, ghosts.
4. **Determinism auditing:** find anything that makes two runs of the same input differ.

**Success criteria**

- A recorded session of each example game replays headless with zero divergence: every frame's
  sprite rects and visibility equal the recording's.
- The first divergence, when there is one, is reported as frame, sprite and field, expected vs got.
- Nothing in `glitchygames/` reads input or time from outside the engine's doors (guard tests).
- Live play without recording behaves exactly as before (golden traces unchanged, except the
  behaviour fixes listed in section 3.4, each proven by an exact expected-difference rule).
- Demos and instant replays never touch real saves and never shift the live game's random draws.

**Definition of exact:** same engine version, same recording → bit-identical sprite traces. Audio
plays during replay but is not compared. Replaying across engine versions is not guaranteed
(replay warns on a version mismatch).

## Decisions (made in conversation)

| Question | Decision |
|---|---|
| Scope | One spec for core, tooling and in-game playback; master plan with sub-plans |
| How replay reaches the engine | Through declared **doors**: the engine's sources (event pump, frame time, polled input, devices, saves, random seed) are swappable providers; replay installs recorded providers; everything downstream runs for real |
| Code that bypasses the doors (polled input, wall clock) | Routed through the engine (`engine.input`, `scene.game_time`); guard tests reject direct polling and wall-clock reads; no patching of pygame or `time` |
| Save data | Snapshot of the game's save namespace in the recording header; replays and playback use an in-memory sandbox seeded from it; writes are discarded |
| In-game playback | Two mechanisms: demos and instant replays reuse input replay on a rebuilt scene; ghosts are lightweight state tracks |
| Instant replay start point | Re-simulate headless from the scene's start (no game-state serialization), within a time budget |
| Game Genie / cheat device | Not built. This spec builds the empty **supervisor hook** (fixed place in the frame) and the recorded **control-event** channel; cheats get their own spec later |

## 1. The doors

The engine has a small set of doors where the outside world enters. Each has a live provider by
default; replay plugs recorded providers into the same doors. The game cannot tell which it is
talking to.

```python
class EngineSources(Protocol):
    def pump_events(self) -> list[pygame.event.Event]: ...
    def frame_seconds(self, *, measured: float) -> float: ...
    def input_snapshot(self) -> InputSnapshot: ...
    def devices(self) -> DeviceRegistry: ...
    def saves(self, *, namespace: str) -> SaveStore: ...
    random_seed: int
```

> Amended (as built): the protocol lives in `glitchygames/sources.py` and grew while Part 1 was
> built: `saves()` returns a `SaveManager` (section 1.4), and the doors also answer
> `performance_frame_seconds` (`--replay-fps`, section 3.2), `wall_clock_time` (the clocks,
> section 3.4), `control_events_for_frame` (section 2), `opened_save_namespaces` (the recording
> header), `stop_requested`, `on_installed` / `on_uninstalled` and `end_frame`. The module
> docstring of `glitchygames/sources.py` is the reference.

| Door | `LiveSources` (default) | `ReplaySources` |
|---|---|---|
| Event pump | `pygame.event.get()` | recorded batch N for pump call N |
| Frame time | the measured start-to-start time, unchanged | the recorded `dt` |
| Polled input | captured from pygame once per frame | the recorded snapshot |
| Devices | real joysticks/controllers | stand-ins built from the recording |
| Saves | files on disk | sandbox from the recorded snapshot |
| Wall clock (amended) | the real time | the recording's `recorded_at` plus the frame clock |
| Random seed | `--random-seed` or 64 random bits | the recorded seed |

- `RecordingSources` wraps `LiveSources` and writes everything passing through to the recorder.
  The recorder's current hooks in `GameEngine._pump_events` and `SceneManager._run_frame` move into
  it.
- `glitchygames.sources.install_sources(*, sources: EngineSources) -> None` may only be called
  before the first frame; a later call raises (core Task 12b removed the `GameEngine` pass-through). A run never mixes live and recorded input. (In-game playback
  uses scoped sources, section 5.2, not a mid-run swap.)
- `GameEngine._pump_events` asks `sources.pump_events()`. Dispatch, transition discarding, the
  unhandled-event table and everything else downstream are unchanged.
- `SceneManager._finish_frame` measures as today, then sets `dt` from
  `sources.frame_seconds(measured=...)`. Logic always receives the recorded `dt`; a watched replay
  paces each frame to its recorded `dt` divided by the replay speed (so at ×1 it looks like the
  original); a headless replay does not pace.
- The input snapshot is taken once per frame, right after the frame's first pump, and does not
  change during the frame.

### 1.1 Input state

```python
engine.input.key_pressed(pygame.K_LEFT)       # held this frame
engine.input.modifiers                         # KMOD bits
engine.input.mouse_position                    # (x, y)
engine.input.mouse_buttons                     # (left, middle, right)
engine.input.axis(device_id=0, axis=1)         # -1.0 .. 1.0
engine.input.hat(device_id=0, hat=0)           # (x, y)
engine.input.button(device_id=0, button=3)     # bool
```

`InputSnapshot` is immutable. Recordings store only what changed from the previous frame
(`input_changes`); idle frames add nothing.

> Amended (as built): code reads the snapshot with `glitchygames.input.state.current_input()`
> (`GameEngine.input` returns the same); widgets and games have no engine reference. Devices are
> keyed by instance id, and a game controller is polled on two layers every frame: the joystick
> layer above (`axis`, `button`, `hat`) and the controller layer (`controller_axis`,
> `controller_button` by `CONTROLLER_AXIS_*` / `CONTROLLER_BUTTON_*` id, on pygame's int scale),
> so each replay stand-in answers exactly as its live counterpart.

### 1.2 Game time

`Scene.game_time` (float seconds): the sum of the `dt` the scene's `dt_tick` received
(`MAX_FRAME_SECONDS`-capped where set); starts at 0 when the scene starts; does not advance while the
scene is paused (it gets no `dt_tick`).

### 1.3 Devices

A controller present while recording is usually absent while replaying. `ReplaySources` registers a
stand-in for each recorded device that answers name, GUID and id queries from the recording; rumble
requests are accepted and dropped. Stick, hat and button positions come from the input snapshot.
Enumeration is part of the door too: joystick and controller counts, `is_controller` and names by
device index are answered live and recorded (failures included, re-raised as `pygame.error` in a
replay), and a replay answers them from the recording, so it never sees real hardware.
Window references in recorded events map to None (amended: live events of the display window
always carry `window=None`, so None is exact and needs no deprecated pygame call).

### 1.4 Saves

When recording starts, the recorder stores the game's save namespace (`self.saves`) in the header.
`ReplaySources.saves(...)` returns a `SandboxSaves` seeded from it: reads see what the original
session saw, writes stay in memory and are discarded at exit.

> Amended (as built, user decision): games open their store with
> `glitchygames.state.open_saves(app_name=...)`. There is no separate `SaveStore` protocol or
> `SandboxSaves`: `SaveManager` is a base class holding every rule of the save format, with
> `DiskSaveManager` (live) and `MemorySaveManager` (replay, `glitchygames/state/sandbox.py`)
> storing slots. The header holds every store opened before recording started; a store first
> opened later is snapshotted in that frame's `saves_opened`. Unreadable slots are recorded as
> such and fail the same way in a replay.

## 2. The frame, supervisor hook and control events

```
begin_frame → dt_tick → events → SUPERVISOR → frame services → aim → position → render → present → _finish_frame
```

- **Supervisor hook:** `SceneManager` calls each registered supervisor with the frame number and the
  active scene after logic and events, before frame services, camera aim and positioning. With none
  registered it does nothing. Changes a supervisor makes are drawn this frame and seen by collision
  next frame. Users in this spec: replay controls and recorded breakpoints. A future cheat device
  plugs in here (out of scope).
- **Control events:** each recorded frame gains `control_events`, supervisor actions that happened
  that frame, e.g. `{"kind": "breakpoint", "label": "ball through paddle"}`,
  `{"kind": "playback", ...}` (section 5.2). Replay re-applies them on the same frame. Future kinds
  (such as cheats) use the same channel.

## 3. Replay core (`--replay-trace PATH`)

### 3.1 Start

- Read the header. A recording of a different game: refuse, exit 2 (amended: `ExitCode.UNUSABLE_INPUT`,
  65; see `glitchygames/exit_codes.py`). A different engine version: warn once and continue. An
  unreadable format version: refuse, exit 2 (amended: 65; a missing file 66).
- Seed the random streams with the recorded seed; apply the recorded options that affect play
  (screen size, input mode, target FPS); install `ReplaySources`; start the game as it started when
  recording began.
- Amended (as built): every recorded option is applied except `REPLAY_LOCAL_OPTIONS`
  (`glitchygames/replay/driver.py`). `--record-trace` with `--replay-trace` is refused (exit 64,
  `OPTIONS_REFUSED`); Part 2's `--rebaseline NEW --headless` is the one way to record over a
  replay (it wires the replay's event origins and recorded fields into the recorder).

### 3.2 Each frame

1. `dt` from the recording (via `frame_seconds`).
2. Pump call N returns the recording's batch N, external events only. Internal events (FPS, game and
   menu events, the QUIT `quit_game()` posts) are not injected: the replayed code posts them again;
   the recording's internal entries are only used to check they were.
3. Real keyboard and mouse input reach only the replay controls (section 4) and the window's close
   button. Amended (as built, user direction): real input, device and window events are blocked at
   SDL (`glitchygames/replay/input_blocking.py`), re-blocked on every pump and restored exactly to
   their earlier state when the replay ends; QUIT, the close event and custom types are never
   blocked. Part 2's watched controls leave KEYDOWN/KEYUP unblocked and route them only to the
   controls.
4. The input snapshot is the recorded frame's.
5. After rendering, the frame's sprites (sampled as the recorder samples them) are compared with the
   recorded frame.
6. Amended (user request): `--replay-fps {recorded,real}`, default `recorded`. FPS events, the
   performance statistics and the debug overlay's performance panel use the recorded frame times
   (exact; FPS events compared) or this machine's measured ones (FPS events not compared). Logic
   always receives the recorded `dt`.

### 3.3 Divergence and end

- The first difference is the only one reported (later frames almost always differ too): frame,
  sprite id, field, expected, got. A watched replay pauses on that frame with the debug overlay on
  and a banner; a headless replay prints the report plus that sprite's previous 20 frames and exits
  1.
- On the final recorded frame a watched replay pauses ("end of recording"); a headless replay exits
  0 if nothing diverged.
- A truncated file replays every complete frame and reports where it ends (watched: pause; headless:
  exit 65, `UNUSABLE_INPUT`).
- Version 2 recordings (no input snapshots, no control events) replay with one warning: polled input
  reads as idle.

### 3.4 Bypass sites moved behind the doors

- Polled input → `engine.input`: `pygame.key.get_pressed` (`bitmappy/editor.py`,
  `bitmappy/film_strip_sprite.py`, `bitmappy/animated_canvas.py`, `examples/dt_demo.py`),
  `pygame.key.get_mods` (`ui/text_widgets.py`), `pygame.mouse.get_pos` / `get_pressed`
  (`ui/inputs.py`, `ui/text_widgets.py`, `bitmappy/editor.py`, `bitmappy/film_strip_sprite.py`,
  `bitmappy/file_io.py`, the debug overlay's mouse readout), device `get_axis` / `get_hat` /
  `get_button` (`bitmappy/controllers/event_handler.py`, `events/joystick.py`,
  `events/controller.py`, `examples/joystick_demo.py`). The plan re-greps before and after.
- Wall clock → `scene.game_time`: PaddleSlap's ball-spawn cooldown (`time.time()`), the cursor
  blinks in `ui/inputs.py` (`time.time()`) and `ui/text_widgets.py` (`pygame.time.get_ticks()`).
  Behaviour fix: these no longer advance while the game is paused.
  Amended (ruling, core Task 8): the cursor blinks read `frame_clock_seconds()` /
  `frame_clock_milliseconds()`, not `Scene.game_time`: widgets have no scene reference, and a paused
  scene's widgets are neither updated nor drawn (the pause scene is active), so no blink is seen
  advancing while paused and the blink stays replay-exact. A blink's phase can differ by up to one
  blink period after resume.
- Amended (as built): every time read in `glitchygames/` goes through `glitchygames/clock.py` or
  `Scene.game_time`. `elapsed_seconds()` (throttles, debounces, timeouts) is the frame clock live
  and replayed (ruling, core Task 12b: a live monotonic clock would let replays decide timers
  differently near thresholds); `measured_seconds()` is real monotonic time for logs and metrics
  only and is never replayed.
- FPS events: posted from engine frame time instead of wall-clock intervals.
- Raw `pygame.event.post` of SDL-type events → `glitchygames.recording.post_event` (otherwise replay
  delivers them twice).
- Guard tests (AST scans like `tests/test_randomness.py`) fail if anything in `glitchygames/` polls
  pygame input or reads the wall clock outside the doors. Allowed by file: the doors themselves,
  pacing (`timing.py`), performance statistics, the debug HUD's timing, the recording's start-time
  stamp, `api/client.py` request timestamps.
  Amended (as built): the allow list is `ALLOWED_BYPASSES` in `tests/test_engine_doors.py`: the
  doors (`input/state.py`, `input/devices.py`, `live_sources.py`, `recording.py`'s `post_event`),
  pacing (`timing.py`, `SceneManager.start` / `_finish_frame` in `scenes/scene.py`),
  `performance/`, `debug/`, `audio/diagnostics.py` (measures real audio timing), the recording's
  start stamp (`engine/game_engine.py`) and `api/client.py`; plus, by function,
  `clock.measured_seconds` (`ALLOWED_FUNCTION_BYPASSES`). Device enumeration and construction are
  watched as well, and no directory (Bitmappy included) is exempt.

### 3.5 Determinism audit (`--audit`)

Replays twice in two fresh subprocesses with different PYTHONHASHSEED values (amended; user
approved), comparing both runs with the recording and with each other through per-frame digests.
A mismatch between the two runs is reported as nondeterminism that slipped past the doors. As
built (`glitchygames/replay/audit.py`): it compares what the replay samples (scene class, each
sprite's `rect`, `visible` and draw order), exits 0, 3 (`AUDIT_NONDETERMINISTIC`) or 70
(`INTERNAL_ERROR`: a run could not finish), and is refused (exit 64) with `--replay-fps real` or
under `python -E` / `-I`.

## 4. Replay tooling

### 4.1 Watched replay

| Key | Action |
|---|---|
| Space | pause / resume |
| `.` / `,` | step forward / back one frame (paused) |
| `]` / `[` | speed ×2 / ÷2 (¼× to 8×; every frame is still simulated) |
| Home | back to the start |
| D | jump to the divergence |
| B | bookmark the frame (a `breakpoint` control event) |
| S | save a copy of the recording with bookmarks |
| F3 / F4 | debug overlay / panels |
| Esc | quit |

- A status bar (drawn like the debug overlay, never in a trace): frame / total, time, speed, paused,
  divergence frame.
- Step back to frame N rebuilds the game and re-simulates headless to N (about 1–2 ms per frame),
  with a progress line. Faster step-back needs state snapshots (out of scope).

### 4.2 Headless replay

`--replay-trace PATH --headless`: no window, no pacing. Exit codes: 0 no divergence, 1 diverged,
2 unusable recording.

### 4.3 Recordings as regression tests

- Pytest plugin `glitchygames.testing.replays`: every `.jsonl.gz` under
  `tests/fixtures/replays/<console-script>/` is a test that replays headless and fails with the
  divergence report.
- `--replay-trace OLD --rebaseline NEW` replays the same inputs on the current code and writes a new
  recording (same inputs, new sprites), printing a summary of what changed (first divergence, frames
  and sprites affected). Replacing a test recording is a deliberate, reviewed step.

## 5. In-game playback

### 5.1 Rebuilding a scene from its start

- `Scene.replay_arguments(self) -> dict[str, Any]` (JSON-safe; default `{}`): the arguments that
  rebuild the scene as it began, e.g. Clockwork Keep's `floor_index`, `player_score`,
  `player_lives`.
- While recording or instant replay is on, the engine captures at each scene start: those
  arguments, every random stream's state (`random.Random.getstate()`, numpy bit-generator state),
  and the scene's save view. Rebuild = `type(scene)(**arguments, options=...)`, restore the streams,
  sandbox the saves.

### 5.2 Playback scope

Demos and instant replays run inside a playback scope, not a new engine run:

- The scope has its own `ReplaySources`. The engine's live sources keep pumping real input, which
  during the scope only reaches the "exit playback" check (any key or button).
- Random stream states are saved on entry and restored on exit.
- Saves are sandboxed.
- When the live session is being recorded, the scope is written as a `playback` control event;
  replaying the session replays the playback too (derived from recorded input, so identical).
- An error inside the scope ends the scope, logs it and returns to the caller's scene, which is
  untouched.

### 5.3 Demos

`scene_manager.play_recording(*, path, then)`: plays a recording in a playback scope; any key or
button returns to `then`. Bundled demos are recordings shipped in the game's package. A demo that
diverges (the game changed since it was recorded) stops at the divergence and returns to `then`,
logging the report in debug runs; a replay test per bundled demo catches this in CI.

### 5.4 Instant replay

- Opt-in: `Scene.INSTANT_REPLAY_SECONDS: ClassVar[float | None] = None`.
- While on, the engine keeps the scene's input since its start in memory (event batches, input
  changes, `dt`), dropped when the scene ends. Amended (as built in Part 3 Task 5): it keeps the
  whole recording of each frame, sprites included (a replay compares every frame), as compact
  JSON trace lines: about 0.5 MB per minute for one sprite moving every frame (487,718 bytes in
  3600 frames) and about 1.5 MB per minute for PaddleSlap's golden script (1,547,920 bytes in
  3600 frames, 11 sprites), plus Python's per-frame object overhead. The sprites dominate; the
  input itself is kilobytes per minute. The journal ends past the fast-forward budget (frame
  time of every kept frame, paused ones included), so it never holds much more than that.
- `scene_manager.instant_replay() -> bool` rebuilds the scene (5.1), re-simulates headless to N
  seconds ago, plays N seconds visibly, then returns to the live scene where it was (the live scene
  is never touched). Amended (as built in Part 3 Task 6): N seconds of frame time, not game
  time (the shown part takes N seconds to watch, a paused stretch in it included); the
  fast-forwarded frames run unpresented, unpaced and silent (the rebuild's `FrameSilencer`),
  the shown ones at the game's pace with their sounds. The player's presses do not end it;
  `scene_manager.end_playback()` does (reason `ended_by_game`). A request made by the scene's
  own code inside a playback of its journal gets the recorded answer, so replays after every
  goal play back across one another.
- Budget `Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS` (default 60 s of scene time; about 1–2 ms
  per headless frame). Past it, `instant_replay()` returns `False`. Longer scenes need state
  snapshots (out of scope). Amended (Part 3 Task 5): the budget is measured as the frame time
  of every journaled frame, paused frames included (all are re-simulated), and a playback
  scope's frames are not journaled: the scene resumes its journal after the scope with a
  resume bridge, so instant replays can follow one another.

### 5.5 Ghosts

- `GhostRecorder(*, sprite)` samples each frame: world x/y, animation name, frame index, horizontal
  flip, visible; keyed by the scene's `game_time`.
- `GhostTrack` (`to_json()` / `from_json()`), stored by the game, typically in saves.
- `GhostSprite(*, track, alpha)`: a WORLD-space sprite positioned and culled by the engine; no hitbox,
  no collision.
- Ghosts are appearance, not play: they cannot diverge. A replayed session with a ghost matches,
  since the track comes from saves, which the sandbox reproduces.
- Amended (as built in Part 3 Task 7, `glitchygames/replay/ghosts.py`): `GhostSample` and
  `GhostTrack` are frozen pydantic models (the appearance read-only).
  `GhostRecorder(*, sprite, scene)` is a supervisor that samples only live frames (never inside
  a playback scope) of the scene it is given, and only frames in which that scene's
  `game_time` advanced (not behind the pause screen); supervisors added while a playback scope
  plays belong to it and are removed when it ends; "visible" is the game's
  `not hidden` for a world sprite (its `visible` is the engine's culling), and the appearance
  adds the `AnimatedSprite`'s `draw_offset`. `GhostSprite(*, track, image_for, alpha)` takes
  the function that draws a sample (`images_from_animated_sprite`), follows the `game_time` of
  the scene the game sets as `ghost.scene`, and reads `world_x`/`world_y`/`draw_offset` from
  the track when they are read, so the engine's positioning (before the render phase) places
  this frame's sample. With nothing to show its image is empty, which the engine culls;
  `hidden` stays the game's own flag. A ghost is in the sprite trace like any sprite.

## 6. Errors, performance, format

- Errors: wrong game or unreadable format → exit 65 (missing file 66); truncated file → replay to the cut-off;
  version mismatch → warn; unknown device kind → stand-in with name and id, events it cannot map
  dropped with a warning; playback errors never crash the game (5.2).
- Performance: live play without recording costs one provider call per pump and per frame; the
  input snapshot is taken once per frame either way. Target: no measurable change in the existing
  benchmarks.
- Trace format version 3: per frame `input_changes` and `control_events`; header `saves` and the
  scene-start captures. Version 2 recordings still replay (3.3).
  Amended (as built in Part 1): frames also carry `devices_opened`, `saves_opened` and
  `device_enumeration`, and the header `devices` and `device_enumeration`; each frame field is
  written only when not empty. Scene-start captures come with Part 3. The format is documented in
  the `glitchygames/recording.py` module docstring.

## 7. Modules

| Module | Holds |
|---|---|
| `glitchygames/sources.py` (new, leaf) | `EngineSources`, the active-sources registry, the frame clock |
| `glitchygames/live_sources.py` (new) | `LiveSources` |
| `glitchygames/clock.py` (new, leaf) | the clock exports (section 3.4) |
| `glitchygames/supervision.py` (new) | `Supervisor`, `ControlEvent` |
| `glitchygames/input/state.py` (new) | `InputSnapshot`, `current_input` |
| `glitchygames/input/devices.py` (new) | the devices door: live and replay registries, stand-ins |
| `glitchygames/state/sandbox.py` (new) | `MemorySaveManager`, `open_saves`, save snapshots |
| `glitchygames/replay/driver.py` (new) | `ReplaySources`, the replay loop, comparison and report |
| `glitchygames/replay/input_blocking.py` (new) | blocking real input at SDL during a replay |
| `glitchygames/replay/audit.py` (new) | `--audit`: two subprocess replays, per-frame digests |
| `glitchygames/replay/rebaseline.py` (new, Part 2) | `--rebaseline` |
| `glitchygames/scene_start.py` (new, leaf, Part 3) | scene-start captures, `rebuild_scene` (amended in Part 3 Task 1: a leaf outside the replay package, so `glitchygames.scenes` never imports the replay driver) |
| `glitchygames/replay/controls.py` (new) | watched-replay controls, status bar, step back, bookmarks |
| `glitchygames/replay/playback.py` (new) | playback scope, `play_recording`, instant replay |
| `glitchygames/replay/ghosts.py` (new) | `GhostRecorder`, `GhostTrack`, `GhostSprite` |
| `glitchygames/testing/replays.py` (new) | pytest plugin (collects `tests/fixtures/replays/`) |
| `scripts/record_scripted_session.py` (new) | records golden replay fixtures through the real engine |
| `recording.py`, `tracing.py` | `RecordingSources` (in `recording.py`); format v3 |
| `engine/game_engine.py`, `scenes/scene.py` | doors, supervisor hook, `game_time`, `replay_arguments`, `INSTANT_REPLAY_SECONDS` |
| bypass sites (3.4) | moved behind the doors |

Amended (ruling 27): the plan's layout wins over this table's first draft. The registry lives in
`glitchygames/sources.py`, not `glitchygames/engine/sources.py`, because it has no engine
dependency: inside the engine package it would make an engine ↔ scenes import cycle. The live
providers are in `glitchygames/live_sources.py` and `RecordingSources` in
`glitchygames/recording.py`, all importing the leaf, never the reverse.

## Testing

- Doors: each provider; `install_sources` refused after the first frame; live sources keep the
  golden traces unchanged; each guard test proven to fail on a fixture snippet.
- Round trip: a scripted session of each example game recorded then replayed headless through the
  real `GameEngine` / `SceneManager`, zero divergence.
- Divergence: a deliberate 1 px change during replay is reported at the right frame, sprite and
  field.
- Audit: a deliberately unseeded draw in a test scene makes `--audit` fail.
- Control events: a recorded breakpoint fires on the same frame in replay.
- Playback scope: after a demo the random streams' next values equal those without it; real saves
  untouched; the live scene unchanged after an instant replay; the budget refusal.
- Ghosts: sampling by game time at different frame rates; positioned and culled as a WORLD sprite.
- Tooling: step back lands exactly (sprites at N equal a straight replay's); rebaseline summary;
  pytest plugin collection.
- Golden traces unchanged except the behaviour fixes in 3.4, each with an exact
  expected-difference rule.

## Documentation

CLAUDE.md (doors, `engine.input`, `scene.game_time`, `--replay-trace` and its flags, playback APIs,
ghosts, supervisor hook), `glitchygames/recording.py` module docstring (format v3, replay, limits
removed), docs pages for replay and playback, `plans/future-work.md` (replace the "Gameplay replay"
entry; add the cheat-device spec and state snapshots as follow-ups).

## Out of scope

- The cheat device (cheatable-field declarations, codes, UI) — own spec; uses the supervisor hook
  and control events built here.
- State snapshots (fast step-back, instant replay of long scenes).
- Replaying across engine versions; comparing audio output.
- Network play and multi-process replay.
