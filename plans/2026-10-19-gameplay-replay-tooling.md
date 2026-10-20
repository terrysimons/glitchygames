# Gameplay Replay — Part 2: Replay Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Master plan:** [2026-10-19-gameplay-replay-implementation.md](2026-10-19-gameplay-replay-implementation.md)
(read its Global Constraints, Review Focus and Cross-part interfaces first)

**Goal:** Make replays usable: headless runs with exit codes and a readable report, a watched
replay with pause/step/speed/step-back/bookmarks and a status bar, recordings as pytest regression
tests, and `--rebaseline` for intentional changes.

**Architecture:** Everything builds on Part 1's `ReplaySources` and doors. Two new door methods
let a replay steer the frame loop without the loop knowing about replays:
`paced_frame_seconds()` (how long to pace this frame: `None` = normal pacing) and `hold_frame()`
(True while paused: the loop presents the held picture and polls the controls without running a
frame). Watched-replay controls live in `glitchygames/replay/controls.py` and see only real input,
which `ReplaySources.pump_events` already drains and keeps away from the game. Step back re-runs
the replay in a fresh process (`os.execv`) with `--replay-pause-at-frame N`, which fast-forwards
headless to frame N and pauses — exact and simple, because a fresh process has fresh engine state.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8, pytest (pytester), uv.

**Spec:** `plans/2026-10-19-gameplay-replay.md` (section 4)

## Global Constraints

See the master plan. Part 1 must be complete (all 15 tasks committed) before this part starts.

## Review Focus

Owned here: none of the master's five; but every task's tests cover its own failure cases
(unusable recording exit code 2, a divergence that is the very last frame, step back from frame 0,
an empty bookmark list on save).

## Tasks

| # | Task | Produces |
|---|---|---|
| 1 | `--headless`, exit codes and the divergence report | `paced_frame_seconds`, exit 0/1/2, report with sprite history |
| 2 | Watched pacing, status bar, pause / step / speed | `hold_frame`, `draw_overlay`, `ReplayControls` |
| 3 | Step back, Home and jump to divergence | `--replay-pause-at-frame`, re-exec |
| 4 | Bookmarks and saving a copy | `B` / `S`, breakpoints pause the watched replay |
| 5 | Recordings as pytest regression tests | `glitchygames/testing/replays.py` collecting `tests/fixtures/replays/` (recorder and fixtures from core Task 13c) |
| 6 | `--rebaseline` | `glitchygames/replay/rebaseline.py`, change summary |

---

### Task 1: `--headless`, exit codes and the divergence report

**Files:**
- Modify: `glitchygames/sources.py` (Protocol `paced_frame_seconds`),
  `glitchygames/live_sources.py` (`LiveSources.paced_frame_seconds` returns None)
- Modify: `glitchygames/recording.py` (`RecordingSources.paced_frame_seconds` delegates)
- Modify: `glitchygames/replay/driver.py` (`ReplaySources(..., headless=..., exit_policy=...)`;
  recent-frame history; `ReplayResult.exit_code`, `ReplayResult.report()`, `run_exit_code()`)
- Modify: `glitchygames/scenes/scene.py:784-821` (`start`), `:736-760` (`_handle_frame_pacing`:
  the unpaced path), `:822-870` (`_finish_frame` passes the pacing decision through)
- Modify: `tests/world/test_gameplay_recording.py` (`RUN_ENGINE_ARGUMENTS`, `build_engine`)
- Modify: `glitchygames/engine/game_engine.py` (`--headless` option; SDL dummy drivers before the
  display opens; exit with the replay's code at the end of `start()`)
- Test: `tests/world/test_gameplay_replay.py`, `tests/world/test_finish_frame.py`

**Interfaces:**
- Consumes: Part 1 `ReplaySources`, `ReplayResult`, `Divergence`, `REPLAY_UNUSABLE_EXIT_CODE`.
- Produces:

```python
EngineSources.paced_frame_seconds(self) -> float | None   # None = the normal target-FPS pacing
REPLAY_MATCHED_EXIT_CODE = 0
REPLAY_DIVERGED_EXIT_CODE = 1
REPORT_HISTORY_FRAMES = 20
ReplayResult.exit_code -> int        # 0 matched/quit, 1 diverged, 2 truncated
ReplayResult.report(self) -> str     # multi-line, for stdout
class ReplayExitPolicy(enum.Enum):
    RESULT = 'result'                  # exit with ReplayResult.exit_code (replays)
    SUCCESS_AFTER_WRITING = 'success'  # exit 0 once the run is over (--rebaseline, Task 6)
ReplaySources.__init__(..., headless: bool = False,
                       exit_policy: ReplayExitPolicy = ReplayExitPolicy.RESULT)
ReplaySources.run_exit_code(self) -> int
```

Rules: headless replays return `0.0` from `paced_frame_seconds` (never sleep); watched replays
return `None` in this task (Task 2 changes it). `--headless` sets `SDL_VIDEODRIVER=dummy` and
`SDL_AUDIODRIVER=dummy` in `os.environ` in `GameEngine.__init__` right after the options are read
and before anything initializes the display or mixer — read `__init__` to find that point (the
display opens in `initialize_display`; pygame's mixer starts in `pygame.init()` — if `pygame.init()`
already ran at import time, document that audio is still initialized and only video is dummy, and
mute instead by not starting live audio: check how `--live-voice-pool 0` behaves). `--headless`
without `--replay-trace` is refused with a clear argparse error. At the end of `GameEngine.start()`
(after `_shutdown`), when replaying: print `result.report()` to stdout when headless (log it
otherwise) and `raise SystemExit(self.replay_sources.run_exit_code())` — the exit policy is a
parameter of the replay (Task 6's rebaseline exits 0 after writing).

Pacing (an explicit unpaced path): `paced_frame_seconds()` returns `None` (pace as today), `0.0`
(unpaced: a headless replay, a fast-forward) or a positive period. `SceneManager.start` reads it
once per frame and passes it to `_finish_frame` → `_handle_frame_pacing(..., paced_seconds=...)`.
For `0.0`, `_handle_frame_pacing` returns at once: no timer deadline and no `self.clock.tick` at
all (today's fallback `clock.tick(self.target_fps)` would still sleep). For a positive period it
paces to that period: with a timer backend, through `compute_deadline`/`sleep_until_next` with
`round(paced_seconds * 1_000_000_000)` as the period; without one, `self.clock.tick(1 / paced_seconds)`.
`None` keeps today's code path unchanged.

`report()` format:

```
Replay diverged at frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]
Ball#2, last 20 frames (expected | got):
  6100: [400, 290, 16, 16] visible | [400, 290, 16, 16] visible
  ...
  6120: [412, 300, 16, 16] visible | [412, 301, 16, 16] visible
```

or `Replay matched 9800 frames (end of recording)`, or `Replay ended early at frame 4312: the
recording is truncated`. The history comes from two `collections.deque(maxlen=REPORT_HISTORY_FRAMES
+ 1)` of (frame number, sprites by id) — recorded and sampled — kept in `end_frame`.

- [ ] **Step 1: Write the failing tests** (`tests/world/test_gameplay_replay.py`)

```python
class TestHeadless:
    def test_matching_replay_exits_zero_and_reports(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(recording_path=recording_path, mocker=mocker,
                                          arguments=('--headless',))
        assert exit_info.value.code == 0
        assert 'Replay matched' in capsys.readouterr().out

    def test_divergence_exits_one_with_the_sprite_history(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(recording_path=recording_path, mocker=mocker,
                                          arguments=('--headless',))
        output = capsys.readouterr().out
        assert exit_info.value.code == 1
        assert 'Replay diverged at frame 3' in output
        assert 'last 20 frames (expected | got)' in output

    def test_truncated_recording_exits_two(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(recording_path=recording_path, mocker=mocker,
                                          arguments=('--headless',))
        assert exit_info.value.code == 2

    def test_headless_never_sleeps(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine_sources = ReplaySources.from_path(path=recording_path, headless=True)
        assert engine_sources.paced_frame_seconds() == 0.0

    def test_headless_without_a_replay_is_refused(self, mocker):
        with pytest.raises(SystemExit) as exit_info, engine_run_environment(mocker):
            run_engine('--headless')
        assert exit_info.value.code == 2  # argparse's usage error
```

with the helper:

```python
def replay_session_with_arguments(*, recording_path: Path, mocker,
                                  arguments: tuple[str, ...],
                                  action: Callable[[], None] | None = None,
                                  action_frame: int = 1):
    with engine_run_environment(mocker):
        Script.action, Script.action_frame = action, action_frame
        return run_engine('--replay-trace', str(recording_path), *arguments)
```

(`ReplaySources.from_path` gains the `headless` keyword.)

Every replay now ends `start()` with `SystemExit(result.exit_code)`, so Part 1's
`replay_session` helper (which calls `run_engine`) must tolerate it, and from Task 2 on a watched
replay pauses instead of stopping, so the helper must also run headless. Change it to:

```python
def replay_session(*, recording_path: Path, mocker, events_by_frame=None, action=None,
                   action_frame: int = 1):
    with engine_run_environment(mocker):
        Script.events_by_frame = events_by_frame or {}
        Script.action, Script.action_frame = action, action_frame
        engine = build_engine(scene_class=DepartureRecordedScene, arguments=(
            *RUN_ENGINE_ARGUMENTS, '--replay-trace', str(recording_path), '--headless'))
        with contextlib.suppress(SystemExit):
            engine.start()
    return engine
```

where `RUN_ENGINE_ARGUMENTS` (the argument list `run_engine` uses) and
`build_engine(*, scene_class, arguments) -> GoldenTraceEngine` (the `command_line` + construction
`run_engine` does) move into module-level names in `tests/world/test_gameplay_recording.py`;
`run_engine` becomes `build_engine(...)` plus `start()`. `TestRefusals.test_wrong_game_is_refused` still sees `SystemExit(2)`: it is raised in
`GameEngine.__init__`, before `start()`. Run the whole Part 1 replay test file after the change.

In `tests/world/test_finish_frame.py`
add to `TestPacing`:

```python
    def test_sources_pacing_override_replaces_the_target(self, driver_factory, mocker):
        """A door that paces a frame to 0.0 seconds (a headless replay) never sleeps."""
        from glitchygames.sources import active_sources

        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        mocker.patch.object(active_sources(), 'paced_frame_seconds', return_value=0.0)
        driver.run(frame_count=FRAMES_TO_RUN)
        assert driver.timer.sleep_deadlines == []

    def test_unpaced_frames_without_a_timer_never_tick_the_clock(self, driver_factory, mocker):
        from glitchygames.sources import active_sources

        driver = driver_factory(target_fps=EXACT_TARGET_FPS, use_timer=False)
        mocker.patch.object(active_sources(), 'paced_frame_seconds', return_value=0.0)
        driver.run(frame_count=FRAMES_TO_RUN)
        driver.manager.clock.tick.assert_not_called()

    def test_a_positive_paced_period_replaces_the_target(self, driver_factory, mocker):
        from glitchygames.sources import active_sources

        driver = driver_factory(target_fps=EXACT_TARGET_FPS, use_timer=False)
        mocker.patch.object(active_sources(), 'paced_frame_seconds', return_value=0.05)
        driver.run(frame_count=FRAMES_TO_RUN)
        driver.manager.clock.tick.assert_called_with(pytest.approx(20.0))
```

(`FakeTimer.sleep_deadlines` is the list the fake timer appends to in `sleep_until_next`;
`driver.manager.clock` is a `Mock` in the driver.)

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement.** `SceneManager.start`, replacing the period computation:

```python
            timer = getattr(self.game_engine, 'timer', None)
            period_ns = 0
            # A replay may pace a frame itself (its recorded frame time, or 0.0 when headless)
            paced_seconds = active_sources().paced_frame_seconds()
            if timer is not None:
                period_ns = (
                    timer.start_frame(self.target_fps)
                    if paced_seconds is None
                    else round(paced_seconds * 1_000_000_000)
                )
```

(read `timer.start_frame` first: if it has side effects the deadline logic relies on, call it and
then override the returned period.) Then the unpaced path in `_handle_frame_pacing`, as the rules
above say — there is no existing "period 0 never sleeps" rule to rely on: today a zero period
falls through to `self.clock.tick(...)` (`scene.py:756-759`).
`ReplayResult.exit_code` and `report()`; the `--headless` option in the diagnostics group;
`GameEngine.start()`'s exit.

- [ ] **Step 4: Run** `tests/world/test_gameplay_replay.py`, `tests/world/test_finish_frame.py`,
  `tests/world`, golden, full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/sources.py glitchygames/live_sources.py glitchygames/recording.py glitchygames/replay/driver.py glitchygames/scenes/scene.py glitchygames/engine/game_engine.py tests/world/test_gameplay_recording.py tests/world/test_gameplay_replay.py tests/world/test_finish_frame.py
git commit -m "Add --headless replays with exit codes and a divergence report"
```

---

### Task 2: Watched pacing, status bar, pause / step / speed

**Files:**
- Create: `glitchygames/replay/controls.py`
- Modify: `glitchygames/sources.py` (`hold_frame`, `draw_overlay` on the Protocol),
  `glitchygames/live_sources.py` (False / no-op), `glitchygames/recording.py` (delegate)
- Modify: `glitchygames/replay/driver.py` (owns a `ReplayControls`; real KEYDOWNs go to it;
  `paced_frame_seconds` = next recorded dt / speed for watched replays; `hold_frame`)
- Modify: `glitchygames/scenes/scene.py` (`start`: held frames; `_present_frame`: `draw_overlay`)
- Test: `tests/replay/test_controls.py` (new folder with `__init__.py`), `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Produces:

```python
EngineSources.hold_frame(self) -> bool                       # True: do not run a frame now
EngineSources.draw_overlay(self, *, surface: pygame.Surface) -> None   # after the debug overlay
class ReplayControls:
    MIN_SPEED = 0.25; MAX_SPEED = 8.0
    def __init__(self, *, total_frames: int) -> None: ...
    paused: bool; speed: float; step_requested: bool; quit_requested: bool
    MESSAGE_PRESENTED_FRAMES = 120                            # a status message's lifetime
    def handle_key(self, *, key: int) -> None: ...           # Space . , ] [ Home D B S Esc
    def show_message(self, *, text: str) -> None: ...        # shown for 120 presented frames
    def message_for_presented_frame(self) -> str | None: ... # counts one presented frame down
    def take_step(self) -> bool: ...                          # consume one pending step
    def status_line(self, *, frame_number: int, seconds: float,
                    divergence_frame: int | None) -> str: ...
    def draw(self, *, surface: pygame.Surface, status_line: str) -> None: ...
```

Key map (spec 4.1; this task implements Space, `.`, `]`, `[`, Esc; Tasks 3–4 implement `,`,
Home, D, B, S): Space toggles `paused`; `.` while paused sets `step_requested`; `]`/`[` double/halve
`speed` within [0.25, 8.0]; Esc sets `quit_requested`, and `ReplaySources` then sets
`stop_requested` with `end_reason = 'quit'` — no event is posted (a code-posted QUIT would be an
internal event the recording lacks, i.e. a divergence). Transient status messages ("no bookmarks to
save", Task 4) last `MESSAGE_PRESENTED_FRAMES` (120) presented frames, counted by
`message_for_presented_frame()` each time the status bar is drawn, so they need no clock (every
clock export follows the frame clock in a replay, which stands still while paused). F3/F4 keep working: the debug overlay's keys must still reach the engine — in
`ReplaySources.pump_events`, real KEYDOWN/KEYUP for F3 and F4 are passed to the debug overlay
exactly as live (read how `SceneManager` handles F3/F4 today and route those two keys there),
not to the game.

`SceneManager.start` loop with holding:

```python
        while self.active_scene is not None and self.quit_requested is False and not (
            active_sources().stop_requested
        ):
            if active_sources().hold_frame():
                self._present_held_frame()
                continue
            ...
```

`_present_held_frame()`: pump through `self.game_engine._pump_events()` is **not** used (it would
consume a recorded batch); instead call `active_sources().poll_controls()` — add that method to
`ReplaySources` only (not the Protocol) and reach it through `hold_frame()`'s implementation: make
`ReplaySources.hold_frame()` itself drain the real queue into the controls before answering, so
`SceneManager` needs only `hold_frame()` and `_present_frame(full_update=True)` plus a short sleep
(`pygame.time.wait(HELD_FRAME_WAIT_MILLISECONDS)`, 16) so a paused replay does not spin. The status
bar is drawn in `_present_frame` after the debug overlay via `active_sources().draw_overlay(...)`,
so it is never in a screenshot or trace. Status line format:
`frame 6120 / 9800 · 1:42.0 · ×1 · paused · diverged at 6120` (omit absent parts).

Divergence and end in a watched replay (spec 3.3): Part 1 stops the run at a divergence or the
end. A watched replay instead pauses there: `ReplaySources` (not headless) sets
`controls.paused = True`, keeps `stop_requested` False, turns the debug overlay on
(`SceneManager().debug_overlay` — read its API for the toggle used by F3) and shows a banner line
above the status bar: `Diverged at frame 6120: <describe()>` or `End of recording`. Stepping
forward past the end does nothing; Esc quits. Headless replays keep Part 1's stop. Tests (in
`tests/world/test_gameplay_replay.py`; `start_replay_in_harness` is written in this task as
described under Task 3's tests, and reused by Tasks 3 and 4):

```python
def test_watched_replay_pauses_at_the_divergence_with_the_overlay_on(mocker, tmp_path):
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
    manager = start_replay_in_harness(recording_path=recording_path)
    sources = manager.game_engine.replay_sources
    for _ in range(4):
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
    assert sources.controls.paused
    assert not sources.stop_requested
    assert manager.debug_overlay.is_visible
    assert sources.banner_line().startswith('Diverged at frame 3')
    GoldenTraceSceneManager.uninstall()


def test_watched_replay_pauses_at_the_end(mocker, tmp_path):
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    manager = start_replay_in_harness(recording_path=recording_path)
    sources = manager.game_engine.replay_sources
    while not sources.controls.paused:
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
    assert sources.banner_line() == 'End of recording'
    assert not sources.stop_requested
    GoldenTraceSceneManager.uninstall()
```

(`ReplaySources.banner_line() -> str | None` is added here.)

- [ ] **Step 1: Write the failing tests** — `tests/replay/test_controls.py`:

```python
"""Watched-replay controls (glitchygames/replay/controls.py)."""

import pygame
import pytest

from glitchygames.replay.controls import ReplayControls


def test_space_toggles_pause():
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    assert controls.paused
    controls.handle_key(key=pygame.K_SPACE)
    assert not controls.paused


def test_step_only_while_paused_and_consumed_once():
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_PERIOD)
    assert not controls.take_step()
    controls.handle_key(key=pygame.K_SPACE)
    controls.handle_key(key=pygame.K_PERIOD)
    assert controls.take_step()
    assert not controls.take_step()


@pytest.mark.parametrize(('presses', 'expected'), [
    ([pygame.K_RIGHTBRACKET], 2.0),
    ([pygame.K_RIGHTBRACKET] * 5, 8.0),
    ([pygame.K_LEFTBRACKET] * 4, 0.25),
])
def test_speed_doubles_and_halves_within_limits(presses, expected):
    controls = ReplayControls(total_frames=100)
    for key in presses:
        controls.handle_key(key=key)
    assert controls.speed == expected


def test_escape_requests_quit_without_posting_an_event(mocker):
    post_event = mocker.patch('glitchygames.recording.post_event')
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_ESCAPE)
    assert controls.quit_requested
    post_event.assert_not_called()


def test_a_message_lasts_a_fixed_number_of_presented_frames():
    controls = ReplayControls(total_frames=100)
    controls.show_message(text='no bookmarks to save')
    shown = [controls.message_for_presented_frame()
             for _ in range(ReplayControls.MESSAGE_PRESENTED_FRAMES + 1)]
    assert shown[:-1] == ['no bookmarks to save'] * ReplayControls.MESSAGE_PRESENTED_FRAMES
    assert shown[-1] is None


def test_status_line():
    controls = ReplayControls(total_frames=9800)
    controls.handle_key(key=pygame.K_SPACE)
    line = controls.status_line(frame_number=6120, seconds=102.0, divergence_frame=6120)
    assert line == 'frame 6120 / 9800 · 1:42.0 · ×1 · paused · diverged at 6120'
```

In `tests/world/test_gameplay_replay.py`:

```python
class TestWatched:
    def test_escape_ends_a_watched_replay_as_quit(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = manager.game_engine.replay_sources
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
        sources.controls.handle_key(key=pygame.K_ESCAPE)
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
        assert sources.stop_requested
        assert sources.result.end_reason == 'quit'
        assert sources.result.divergence is None
        GoldenTraceSceneManager.uninstall()

    def test_watched_replay_paces_to_the_recorded_frame_time(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        first_dt = sources.frame_seconds(measured=0.0)
        assert sources.paced_frame_seconds() == pytest.approx(
            sources.recorded_dt(frame_number=1))
        sources.controls.handle_key(key=pygame.K_RIGHTBRACKET)
        assert sources.paced_frame_seconds() == pytest.approx(
            sources.recorded_dt(frame_number=1) / 2)
        assert first_dt == sources.recorded_dt(frame_number=0)

    def test_paused_replay_holds_until_a_step(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        sources.controls.handle_key(key=pygame.K_SPACE)
        assert sources.hold_frame()
        sources.controls.handle_key(key=pygame.K_PERIOD)
        assert not sources.hold_frame()   # one frame runs
        assert sources.hold_frame()       # then it holds again
```

(`ReplaySources.recorded_dt(*, frame_number) -> float` is a small public accessor added here.)

- [ ] **Step 2–4:** fail; implement `controls.py` (draw with the debug overlay's font helper —
  read `glitchygames/debug/` for how it renders cached text on a translucent backing and reuse
  that helper, do not create a new font path); wire the driver and `SceneManager`; run
  `tests/replay`, `tests/world`, golden, full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/replay/controls.py glitchygames/sources.py glitchygames/live_sources.py glitchygames/recording.py glitchygames/replay/driver.py glitchygames/scenes/scene.py tests/replay/__init__.py tests/replay/test_controls.py tests/world/test_gameplay_replay.py
git commit -m "Watch replays: recorded pacing, status bar, pause, step and speed"
```

---

### Task 3: Step back, Home and jump to divergence

**Files:**
- Modify: `glitchygames/replay/controls.py` (`,`, Home, D → `restart_request`)
- Modify: `glitchygames/replay/driver.py` (`--replay-pause-at-frame N`: fast-forward headless, then
  pause; perform a restart request with `os.execv`)
- Modify: `glitchygames/engine/game_engine.py` (`--replay-pause-at-frame` option)
- Modify: `glitchygames/scenes/scene.py` (`_present_frame` is skipped while fast-forwarding:
  `EngineSources.presents_frames()`)
- Modify: `glitchygames/sources.py` (Protocol `presents_frames`), `glitchygames/live_sources.py`
  (True), `glitchygames/recording.py` (delegates)
- Test: `tests/replay/test_controls.py`, `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Produces:

```python
ReplayControls.restart_request -> int | None     # frame to restart at, set by , / Home / D
EngineSources.presents_frames(self) -> bool       # False while fast-forwarding
ReplaySources.__init__(..., pause_at_frame: int | None = None)   # simulate 0..N-1, pause at N
def restart_command(*, original: list[str], recording_path: Path, pause_at_frame: int) -> list[str]
FAST_FORWARD_PROGRESS_INTERVAL_FRAMES = 60
```

Rules: `,` while paused at frame N (N > 0) requests a restart at N − 1; at frame 0 it does
nothing. Home requests 0. D requests the divergence frame (nothing when there is none). A restart
request is performed at the end of the current frame (`end_frame`): build the command with
`restart_command(original=sys.orig_argv, ...)` — it removes any previous `--replay-pause-at-frame`
and its value and appends `--replay-pause-at-frame N` (and replaces the `--replay-trace` value with
`recording_path`, which Task 4 uses for the bookmarked copy) — flush logs, then
`os.execv(sys.executable, command)` (command[0] is the interpreter path from `sys.orig_argv`; check
`sys.orig_argv[0]` and pass the arguments after it). With `pause_at_frame` N > 0 the replay
fast-forwards: `presents_frames()` False and `paced_frame_seconds()` 0.0 until frame N, printing
`Rebuilding: frame k / N` to stdout every 60 frames and presenting a plain progress screen at the
same interval (a one-line text on the cleared display, so the window does not look frozen); at
frame N it starts paused.

- [ ] **Step 1: Write the failing tests**

```python
# tests/replay/test_controls.py
def test_step_back_requests_the_previous_frame_while_paused():
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    controls.current_frame = 10
    controls.handle_key(key=pygame.K_COMMA)
    assert controls.restart_request == 9


def test_step_back_at_frame_zero_does_nothing():
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    controls.current_frame = 0
    controls.handle_key(key=pygame.K_COMMA)
    assert controls.restart_request is None


def test_home_and_jump_to_divergence():
    controls = ReplayControls(total_frames=100)
    controls.current_frame = 50
    controls.handle_key(key=pygame.K_d)
    assert controls.restart_request is None  # no divergence yet
    controls.divergence_frame = 42
    controls.handle_key(key=pygame.K_d)
    assert controls.restart_request == 42
    controls.handle_key(key=pygame.K_HOME)
    assert controls.restart_request == 0


# tests/world/test_gameplay_replay.py
def test_restart_command_replaces_the_pause_frame():
    from glitchygames.replay.driver import restart_command

    command = restart_command(
        original=['python', 'game.py', '--replay-trace', 'a.jsonl.gz',
                  '--replay-pause-at-frame', '5'],
        recording_path=Path('b.jsonl.gz'), pause_at_frame=9)
    assert command == ['python', 'game.py', '--replay-trace', 'b.jsonl.gz',
                       '--replay-pause-at-frame', '9']


def test_pause_at_frame_fast_forwards_without_presenting(mocker, tmp_path):
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    manager = start_replay_in_harness(recording_path=recording_path,
                                      extra_arguments=('--replay-pause-at-frame', '3'))
    sources = manager.game_engine.replay_sources
    presented = mocker.spy(manager, '_present_frame')
    for _ in range(3):
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
    assert presented.call_count == 0          # frames 0-2 fast-forwarded
    assert sources.controls.paused            # paused on arriving at frame 3
    assert sources.result.divergence is None
    GoldenTraceSceneManager.uninstall()


def test_headless_pause_at_frame_does_not_pause(mocker, tmp_path):
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    with pytest.raises(SystemExit) as exit_info:
        replay_session_with_arguments(recording_path=recording_path, mocker=mocker,
                                      arguments=('--replay-pause-at-frame', '3', '--headless'))
    assert exit_info.value.code == 0          # nobody can unpause a headless replay
```

`start_replay_in_harness(*, recording_path, extra_arguments=())` (written in Task 2, reused here
and in Task 4, in `tests/world/test_gameplay_replay.py`) must not copy `run_engine`'s setup a third
time: move `run_engine`'s argument list into a module constant `RUN_ENGINE_ARGUMENTS` and its
construction into `build_engine(*, scene_class, arguments) -> GoldenTraceEngine` in
`tests/world/test_gameplay_recording.py` (`run_engine` then calls `build_engine(...)` and
`start()`), and write:

```python
def start_replay_in_harness(*, recording_path: Path,
                            extra_arguments: tuple[str, ...] = ()) -> GoldenTraceSceneManager:
    """Build the replay engine in the harness and return the manager, without start()."""
    manager = GoldenTraceSceneManager.install()
    engine = build_engine(scene_class=DepartureRecordedScene, arguments=(
        *RUN_ENGINE_ARGUMENTS, '--replay-trace', str(recording_path), *extra_arguments))
    engine.install_game(scene_class=DepartureRecordedScene)
    return manager
```

`replay_session` (Task 1) uses `build_engine` too.

- [ ] **Step 2–4:** fail; implement; mock `os.execv` in a unit test of the restart path
  (`mocker.patch('glitchygames.replay.driver.os.execv')`) and assert it is called with the
  command from `restart_command`; run `tests/replay`, `tests/world`, full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/replay/controls.py glitchygames/replay/driver.py glitchygames/engine/game_engine.py glitchygames/sources.py glitchygames/live_sources.py glitchygames/recording.py glitchygames/scenes/scene.py tests/replay/test_controls.py tests/world/test_gameplay_replay.py
git commit -m "Step back, Home and jump to the divergence by re-running the replay to a frame"
```

---

### Task 4: Bookmarks and saving a copy

**Files:**
- Modify: `glitchygames/replay/controls.py` (B, S)
- Modify: `glitchygames/replay/driver.py` (bookmarks as `breakpoint` control events; save copy;
  a recorded breakpoint pauses a watched replay; restarts carry unsaved bookmarks)
- Test: `tests/replay/test_controls.py`, `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Produces:

```python
ReplayControls.bookmarks -> list[int]
def bookmarked_copy_path(*, recording_path: Path) -> Path   # x.jsonl.gz -> x.bookmarked.jsonl.gz
def write_bookmarked_copy(*, recording_path: Path, bookmarks: list[int],
                          destination: Path) -> None
ReplaySources.save_bookmarked_copy(self) -> Path | None    # S; None (and a message) when empty
ReplaySources.restart_at(self, *, pause_at_frame: int) -> None   # Task 3's re-exec; saves
                                                                 # unsaved bookmarks first
```

Rules: B adds the current frame to `bookmarks` (no duplicates, kept sorted). S writes the
recording with a `{'kind': 'breakpoint', 'label': 'bookmark'}` control event added to each
bookmarked frame (existing control events kept, the bookmark appended) to
`bookmarked_copy_path(...)` with `write_trace`, and logs the path; with no bookmarks it writes
nothing and calls `controls.show_message(text='no bookmarks to save')` (120 presented frames,
Task 2). A watched replay pauses
when it applies a recorded `breakpoint` control event (a `SceneManager.add_control_event_handler`
registered by the driver for `BREAKPOINT_KIND`), so a saved copy reopens and stops at each
bookmark. Before a restart (Task 3) with unsaved bookmarks, the driver writes the bookmarked copy
first and restarts on it, so bookmarks survive step back.

- [ ] **Step 1: Write the failing tests**

```python
# tests/world/test_gameplay_replay.py
def test_saving_with_no_bookmarks_writes_nothing_and_says_so(mocker, tmp_path):
    from glitchygames.replay.driver import bookmarked_copy_path

    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    sources = ReplaySources.from_path(path=recording_path)
    assert sources.save_bookmarked_copy() is None
    assert not bookmarked_copy_path(recording_path=recording_path).exists()
    assert sources.controls.message_for_presented_frame() == 'no bookmarks to save'


def test_restart_carries_unsaved_bookmarks(mocker, tmp_path):
    from glitchygames.replay import driver
    from glitchygames.replay.driver import bookmarked_copy_path

    execv = mocker.patch.object(driver.os, 'execv')
    mocker.patch.object(driver.sys, 'orig_argv',
                        ['python', 'game.py', '--replay-trace', 'session.jsonl.gz'])
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    sources = ReplaySources.from_path(path=recording_path)
    sources.controls.current_frame = 2
    sources.controls.handle_key(key=pygame.K_b)
    sources.restart_at(pause_at_frame=1)
    copy_path = bookmarked_copy_path(recording_path=recording_path)
    assert copy_path.exists()
    (_, command), _ = execv.call_args
    assert command[-4:] == ['--replay-trace', str(copy_path), '--replay-pause-at-frame', '1']


# tests/replay/test_controls.py
def test_bookmarks_are_unique_and_sorted():
    controls = ReplayControls(total_frames=100)
    for frame in (30, 10, 30):
        controls.current_frame = frame
        controls.handle_key(key=pygame.K_b)
    assert controls.bookmarks == [10, 30]


# tests/world/test_gameplay_replay.py
def test_bookmarked_copy_adds_breakpoints(mocker, tmp_path):
    from glitchygames.replay.driver import bookmarked_copy_path, write_bookmarked_copy
    from glitchygames.tracing import read_trace_result

    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    destination = bookmarked_copy_path(recording_path=recording_path)
    write_bookmarked_copy(recording_path=recording_path, bookmarks=[2], destination=destination)
    frames = read_trace_result(path=destination).trace['frames']
    assert frames[2]['control_events'] == [{'kind': 'breakpoint', 'label': 'bookmark'}]
    assert destination.name == 'session.bookmarked.jsonl.gz'


def test_watched_replay_pauses_at_a_recorded_breakpoint(mocker, tmp_path):
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    bookmarked_path = tmp_path / 'bookmarked.jsonl.gz'
    write_bookmarked_copy(recording_path=recording_path, bookmarks=[2],
                          destination=bookmarked_path)
    manager = start_replay_in_harness(recording_path=bookmarked_path)
    sources = manager.game_engine.replay_sources
    frame_number = 0
    while not sources.controls.paused:
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
        frame_number += 1
    assert frame_number == 3          # frame 2 ran and its breakpoint paused the replay
    GoldenTraceSceneManager.uninstall()
```

The replay runs watched (no `--headless`), stepped by the harness loop
(`manager.dt = sources.frame_seconds(...)`, `manager.run_frame()`), so nothing paces or presents
for real. `start_replay_in_harness` is the helper written in Task 2.

- [ ] **Step 2–4:** fail; implement; run `tests/replay`, `tests/world`, full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/replay/controls.py glitchygames/replay/driver.py tests/replay/test_controls.py tests/world/test_gameplay_replay.py
git commit -m "Bookmark replay frames and save them as breakpoints in a copy of the recording"
```

---

### Task 5: Recordings as pytest regression tests

**Already built (Part 1, core Task 13c, commit 19ce99a):** `scripts/record_scripted_session.py`
(records a game's golden input script through the real engine, `GameEngine.start`, with a
supervisor posting each frame's input one frame ahead; Part 3 Task 4 reuses it for the bundled
demo), its tests `tests/replay/test_record_scripted_session.py`, the golden replay fixtures
`tests/fixtures/replays/<console-script>/golden.jsonl.gz` (paddleslap, clockwork-keep,
brave-adventurer, brave-adventurer-papyrus; each < 100 KB), and
`tests/replay/test_golden_replays.py`, which replays every fixture in process through the real
loop (shared helpers in `tests/replay/replay_helpers.py`). This task reuses all of that; it does not
create the script or record a fixture of its own.

**Files:**
- Create: `glitchygames/testing/__init__.py`, `glitchygames/testing/replays.py`
- Modify: `conftest.py` (root: `pytest_plugins = ['pytester', 'glitchygames.testing.replays']`)
- Modify: `tests/replay/test_golden_replays.py` (drop `test_golden_replay_matches_every_frame`
  once the plugin collects the same fixtures, so each fixture is not replayed twice; keep the
  non-empty and console-script directory checks and the tamper test)
- Reuse: `scripts/record_scripted_session.py`, `tests/fixtures/replays/` (from core Task 13c)
- Test: `tests/replay/test_replay_plugin.py`

**Interfaces:**
- Consumes (from core Task 13c, `scripts/record_scripted_session.py`):

```python
INPUT_ONLY_PLACEMENT_GAMES = frozenset({'paddleslap'})   # placements that only steer input
REPLAY_FIXTURE_DIRECTORY = PROJECT_ROOT / 'tests' / 'fixtures' / 'replays'
REPLAY_FIXTURE_SUFFIX = '.jsonl.gz'
CONSOLE_SCRIPT_GAME_KEYS: dict[str, str]                 # console script -> game key
def fixture_path(*, game_key: str, name: str = 'golden') -> Path
class ScriptedInputSupervisor:   # a glitchygames.supervision.Supervisor
    def __init__(self, *, script: InputScript, game_key: str, frame_count: int,
                 scene_manager: SceneManager) -> None: ...
    def on_frame(self, *, frame_number: int, scene: Scene | None) -> None: ...
def record_scripted_session(*, game_key: str, frame_count: int, path: Path,
                            random_seed: int = RANDOM_SEED) -> None: ...
```

- Produces:

```python
REPLAY_FIXTURES_PATH_PARTS = ('fixtures', 'replays')       # collected under tests/fixtures/replays
def game_entry_point(*, console_script: str) -> str        # 'module:function' from metadata
class ReplayFile(pytest.File): ...                          # one item per recording
class ReplayItem(pytest.Item): ...                          # runs the headless replay subprocess
def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> ReplayFile | None
```

`pytest_collect_file` keeps pytest's hook signature (interface conformance, positional).

Rules: the plugin collects from `tests/fixtures/replays/`: a file
`.../fixtures/replays/<console-script>/<name>.jsonl.gz` (the directory name is the game's console
script from `[project.scripts]`, e.g. `paddleslap`, `clockwork-keep`) becomes one test item, id
`<console-script>/<name>`. Running it executes, in a subprocess with `SDL_VIDEODRIVER=dummy` and
`SDL_AUDIODRIVER=dummy`:
`[sys.executable, '-c', f'from {module} import {function}; {function}()', '--replay-trace', path,
'--headless']` (where `module:function` comes from `importlib.metadata.entry_points(
group='console_scripts')[console_script].value`; `sys.argv` in the child is `['-c', ...]` — set
it properly by passing the arguments after `-c` code, which Python places in `sys.argv[1:]`). Exit
0 passes; exit 1 fails with the child's stdout (the divergence report) as the failure message;
exit 2 fails with "unusable recording" plus stdout; any other code fails with stderr. A directory
name that is not a console script fails at collection with a clear message.

Fixtures must be recorded through the real engine (`scripts/record_scripted_session.py`), never
the golden harness: the harness steps frames without `_finish_frame`, so its recordings hold no FPS
events and its frame clock never moves, while the plugin's replay runs the real loop, which posts
FPS events — the replay would report each as an unexpected internal event. The script's module
docstring holds the one-command-per-game regeneration commands and the rule (regenerate only
deliberately, after reviewing why a golden replay changed).

- [ ] **Step 1: Write the failing tests** (`tests/replay/test_replay_plugin.py`, with pytester)

```python
"""Recordings under tests/fixtures/replays/<game>/ become pytest items (glitchygames/testing/replays.py)."""

import shutil

from scripts.record_scripted_session import fixture_path

REPO_FIXTURE = fixture_path(game_key='paddleslap')


def test_matching_recording_passes(pytester):
    target = pytester.path / 'fixtures' / 'replays' / 'paddleslap'
    target.mkdir(parents=True)
    shutil.copy(REPO_FIXTURE, target / 'rally.jsonl.gz')
    result = pytester.runpytest('-p', 'glitchygames.testing.replays', 'fixtures')
    result.assert_outcomes(passed=1)


def test_unknown_game_directory_fails_at_collection(pytester):
    target = pytester.path / 'fixtures' / 'replays' / 'no-such-game'
    target.mkdir(parents=True)
    shutil.copy(REPO_FIXTURE, target / 'rally.jsonl.gz')
    result = pytester.runpytest('-p', 'glitchygames.testing.replays', 'fixtures')
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(['*no-such-game*not a console script*'])


def test_tampered_recording_fails_with_the_report(pytester):
    from tests.replay.replay_helpers import tamper_first_sprite_rect

    target = pytester.path / 'fixtures' / 'replays' / 'paddleslap'
    target.mkdir(parents=True)
    tampered_path = target / 'tampered.jsonl.gz'
    shutil.copy(REPO_FIXTURE, tampered_path)
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=10)
    result = pytester.runpytest('-p', 'glitchygames.testing.replays', 'fixtures')
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*Replay diverged at frame 10*'])
```

(The root `conftest.py` loads the plugin for the real suite, so `tests/fixtures/replays/` runs with
the normal `pytest`; pytester runs need `-p` because they have their own config.)

- [ ] **Step 2–4:** fail; implement the plugin; drop the duplicate parametrized test from
  `tests/replay/test_golden_replays.py`; run
  `uv run pytest tests/fixtures/replays tests/replay -q -p no:cacheprovider --no-cov` and the full
  suite (the fixture items must pass in the full run and with `-n auto`).

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/testing/__init__.py glitchygames/testing/replays.py conftest.py tests/replay/test_replay_plugin.py tests/replay/test_golden_replays.py
git commit -m "Run recordings under tests/fixtures/replays as pytest regression tests"
```

---

### Task 6: `--rebaseline`

**Files:**
- Create: `glitchygames/replay/rebaseline.py`
- Modify: `glitchygames/replay/driver.py` (`ReplaySources(..., stop_on_divergence: bool = True)`;
  collecting mode for the summary)
- Modify: `glitchygames/engine/game_engine.py` (`--rebaseline PATH`, requires `--replay-trace`;
  installs `RecordingSources(inner=ReplaySources(..., stop_on_divergence=False,
  exit_policy=ReplayExitPolicy.SUCCESS_AFTER_WRITING), recorder=...)`)
- Modify: `glitchygames/recording.py` (`RecordingSources` over a replay copies the source
  recording's per-frame `saves_opened` / `devices_opened` / `device_enumeration`, and takes event
  origins from `last_batch_origins()` — core Task 11's rules; add any part core did not build)
- Modify: `CLAUDE.md`, the replay docs page from Part 1 Task 15 (Step 5)
- Test: `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Produces:

```python
@dataclasses.dataclass
class RebaselineSummary:
    first_divergence: Divergence | None
    frames_differing: int
    sprites_affected: list[str]
    frames_replayed: int
    def describe(self) -> str: ...
def rebaseline_header(*, original_header: dict[str, Any], original_path: Path) -> dict[str, Any]
```

Rules: `--replay-trace OLD --rebaseline NEW` replays OLD's inputs on the current code, never
stopping at a divergence, and writes NEW: the same header (seed, options, saves, devices) plus
`rebaselined_from: str(OLD)` and the current `engine_version`; the same inputs (event batches,
`input_changes`, `control_events`, `devices_opened`, `saves_opened`) — RecordingSources writes what
passes through the replay doors, which are OLD's inputs — and the sprites the current code
produced. It prints `summary.describe()`:
`Rebaselined 9800 frames to NEW: 412 frames differ (first at 6120: sprite Ball#2 rect ...);
sprites affected: Ball#2, Ball#3` or `... no frames differ`. The run exits 0 after writing NEW and
printing the summary (`ReplayExitPolicy.SUCCESS_AFTER_WRITING`, the replay's exit-policy
parameter from Task 1), or 2 when OLD is unusable. Header `saves`, `devices` and
`device_enumeration` are copied from OLD's header; per-frame `saves_opened`, `devices_opened` and
`device_enumeration` from OLD's frames; code-posted events keep their `internal` origin (taken from
the replay's merge, never re-classified), so replaying NEW delivers nothing twice. Replaying NEW
afterwards must match with no divergence (test it).

- [ ] **Step 1: Write the failing tests**

```python
class TestRebaseline:
    def test_rebaseline_writes_a_recording_that_then_matches(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(recording_path=recording_path, mocker=mocker,
                                          arguments=('--rebaseline', str(new_path),
                                                     '--headless'))
        assert exit_info.value.code == 0
        output = capsys.readouterr().out
        assert 'frames differ (first at 3' in output
        engine = replay_session(recording_path=new_path, mocker=mocker)
        assert engine.replay_sources.result.divergence is None

    def test_rebaselined_header_keeps_the_seed_and_names_the_original(self, tmp_path):
        from glitchygames.replay.rebaseline import rebaseline_header

        header = rebaseline_header(original_header={'random_seed': 5, 'engine_version': 'old'},
                                   original_path=tmp_path / 'old.jsonl.gz')
        assert header['random_seed'] == 5
        assert header['rebaselined_from'] == str(tmp_path / 'old.jsonl.gz')
        assert header['engine_version'] == importlib.metadata.version('glitchygames')
        # (add `import importlib.metadata` to the test file's imports)

    def test_rebaseline_keeps_internal_origins_and_late_saves(self, mocker, tmp_path):
        from glitchygames.recording import post_event
        from glitchygames.state.sandbox import open_saves
        from glitchygames.tracing import read_trace_result

        def post_and_save() -> None:
            post_event(pygame.event.Event(pygame.USEREVENT + 43, {}))
            open_saves(app_name='rebaseline-late').save('slot', {'value': 1})

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker,
                                        action=post_and_save, action_frame=1)
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        with pytest.raises(SystemExit):
            replay_session_with_arguments(recording_path=recording_path, mocker=mocker,
                                          arguments=('--rebaseline', str(new_path), '--headless'),
                                          action=post_and_save, action_frame=1)
        old_frames = read_trace_result(path=recording_path).trace['frames']
        new_frames = read_trace_result(path=new_path).trace['frames']
        assert new_frames[1].get('saves_opened') == old_frames[1].get('saves_opened')
        assert [record['origin'] for batch in new_frames[2]['event_batches'] for record in batch
                if record['type'] == pygame.USEREVENT + 43] == ['internal']
```

- [ ] **Step 2–4:** fail; implement; run `tests/world/test_gameplay_replay.py` and the full suite.

- [ ] **Step 5: Lint, type-check, docs, commit.** Add `--headless`, the watched-replay keys,
  step back, bookmarks, the pytest plugin and `--rebaseline` to CLAUDE.md's replay section and the
  docs page from Part 1 Task 15; run mkdocs strict.

```bash
git add glitchygames/replay/rebaseline.py glitchygames/replay/driver.py glitchygames/engine/game_engine.py glitchygames/recording.py tests/world/test_gameplay_replay.py CLAUDE.md docs/<the replay page from Part 1 Task 15>
git commit -m "Add --rebaseline: replay old inputs on new code and summarize what changed"
```
