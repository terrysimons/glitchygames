# Gameplay Replay — Part 3: In-Game Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Master plan:** [2026-10-19-gameplay-replay-implementation.md](2026-10-19-gameplay-replay-implementation.md)
(read its Global Constraints, Review Focus and Cross-part interfaces first)

**Goal:** Let games play recordings inside a running session — attract-mode demos and instant
replays, both exact input replays on a rebuilt scene — and show ghosts (recorded appearance
tracks) beside live play.

**Architecture:** A scene can be rebuilt as it began: `Scene.replay_arguments()` names its
constructor arguments, and the engine captures, when each scene is constructed and set up, those
arguments, every random stream's state, the frame clock and its save views. A playback scope runs a
rebuilt scene on scoped `PlaybackSources` (pushed on top of the live or recording sources):
the rebuilt scene gets the recording's events, input and frame times, while the base sources'
real input only feeds the "exit playback" check. The live scene is stashed, never cleaned up or set
up again, and the random streams, saves and frame clock are restored when the scope ends. Instant
replay keeps the current scene's inputs in memory and fast-forwards a rebuilt copy without
presenting. Ghosts are separate: a supervisor samples a sprite's appearance each frame into a track,
and a WORLD-space `GhostSprite` draws it later.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8, pytest + pytest-mock, uv.

**Spec:** `plans/2026-10-19-gameplay-replay.md` (section 5)

## Global Constraints

See the master plan. Part 1 must be complete. Part 2 is not required (this part does not use its
controls), but run it first per the master plan's order.

- A rebuilt scene must not depend on state outside what is captured; document in
  `Scene.replay_arguments`'s docstring that a scene supporting demos or instant replay must create
  its random draws from engine streams (it already must) and take everything it carries between
  scenes as constructor arguments.

## Review Focus

Owned here: master item 5 (error or divergence inside a scope restores the live game), plus each
task's own failure cases.

## Tasks

| # | Task | Produces |
|---|---|---|
| 1 | Rebuilding a scene from its start | `replay_arguments`, stream-state capture/restore, `scene_start` field |
| 2 | The playback scope | `PlaybackSources`, `SceneManager._enter_playback` / `_exit_playback` |
| 3 | Demos | `SceneManager.play_recording` |
| 4 | Instant-replay journal | `INSTANT_REPLAY_SECONDS`, in-memory inputs since scene start, budget |
| 5 | Instant replay | `SceneManager.instant_replay`, fast-forward without presenting |
| 6 | Ghosts | `GhostRecorder`, `GhostTrack`, `GhostSprite` |

---

### Task 1: Rebuilding a scene from its start

**Files:**
- Modify: `glitchygames/randomness.py` (`capture_stream_states`, `restore_stream_states`)
- Modify: `glitchygames/engine/sources.py` (`set_frame_clock_seconds`)
- Modify: `glitchygames/scenes/scene.py` — `Scene.__init__` (capture streams first),
  `Scene.replay_arguments`, `SceneManager._setup_new_scene` (complete the start capture before
  `setup()`), `SceneManager.active_scene_start` (the active scene's capture)
- Modify: `glitchygames/examples/clockwork_keep/game.py` (`replay_arguments` for floors)
- Modify: `glitchygames/recording.py` (`RecordingSources` writes `scene_start` on the frame a
  scene started, and the active scene's start on frame 0)
- Test: `tests/test_randomness.py`, `tests/world/test_frame_integration.py`,
  `tests/world/test_gameplay_recording.py`, `tests/examples/` (Clockwork Keep's test file)

**Interfaces:**
- Produces:

```python
def capture_stream_states() -> dict[str, Any]      # JSON-safe: seed + every stream's state
def restore_stream_states(*, states: dict[str, Any]) -> None
def set_frame_clock_seconds(*, seconds: float) -> None
Scene.replay_arguments(self) -> dict[str, Any]     # default {}
@dataclasses.dataclass(frozen=True)
class SceneStart:
    scene_class: str
    arguments: dict[str, Any]
    random_states: dict[str, Any]
    frame_clock_seconds: float
    saves: dict[str, dict[str, Any]]                # namespace -> slot -> envelope
    def to_json(self) -> dict[str, Any]: ...
    @classmethod
    def from_json(cls, record: dict[str, Any]) -> SceneStart: ...
SceneManager.active_scene_start -> SceneStart | None
def rebuild_scene(*, start: SceneStart, scene_class: type[Scene], options: dict[str, Any]) -> Scene
```

`SceneStart` lives in a new `glitchygames/replay/scene_start.py`. Capture rules: `Scene.__init__`
calls `capture_stream_states()` as its first statement and keeps it (`self._start_random_states`)
— before the subclass body after `super().__init__()` draws anything; the frame clock is read at
the same point. `_setup_new_scene`, before `setup()`, completes the capture: `replay_arguments()`
(JSON-safe; check with `json.dumps` and raise `TypeError` naming the scene if not), the save views
(every namespace the active sources' live layer has opened, snapshotted with
`save_namespace_snapshot`; `SandboxSaves` contents when in a replay), then stores
`self.active_scene_start`. `rebuild_scene`: `restore_stream_states(states=start.random_states)`,
`set_frame_clock_seconds(seconds=start.frame_clock_seconds)`, then
`scene_class(**start.arguments, options=options)` — it does not call `setup()` (the scope does it
through `_setup_new_scene`-equivalent steps, Task 2).

`capture_stream_states` format:

```python
{'seed': 123,
 'random': {'shake': [3, [<625 ints>], None]},          # random.Random.getstate(), as lists
 'numpy': {'audio.live': {...bit_generator.state...}}}
```

(`getstate()` returns `(version, tuple_of_625_ints, gauss_next)`; store lists, rebuild tuples on
restore. `restore_stream_states` sets the seed without clearing, recreates each named stream with
`random.Random()` then `setstate(...)` (the `random.Random()` constructor needs a seed argument for
the guard test — construct with `random.Random(0)` and immediately `setstate`), and numpy streams
with `np.random.default_rng(0)` then `.bit_generator.state = state`; streams not in the capture are
dropped, so they are recreated from the seed on first use exactly as at capture time.)

- [ ] **Step 1: Write the failing tests**

`tests/test_randomness.py`:

```python
class TestStreamStates:
    def test_restore_reproduces_the_next_draws(self):
        reset_streams(seed=TEST_SEED)
        random_stream('shake').random()
        numpy_stream('audio.live').random()
        states = capture_stream_states()
        expected = (random_stream('shake').random(), numpy_stream('audio.live').random(),
                    random_stream('new').random())
        reset_streams(seed=999)
        restore_stream_states(states=states)
        assert (random_stream('shake').random(), numpy_stream('audio.live').random(),
                random_stream('new').random()) == expected

    def test_states_are_json_safe(self):
        import json

        reset_streams(seed=TEST_SEED)
        random_stream('shake').random()
        states = capture_stream_states()
        assert json.loads(json.dumps(states)) == states
```

`tests/world/test_frame_integration.py`:

```python
class StartCapturedScene(CameraFreeScene):
    def __init__(self, options=None, groups=None, level: int = 1) -> None:
        super().__init__(options=options, groups=groups)
        self.level = level
        self.spawn_x = random_stream('test.spawn').randrange(0, 100)

    def replay_arguments(self) -> dict:
        return {'level': self.level}


class TestSceneStart:
    def test_start_capture_holds_arguments_and_streams(self):
        with running_scene(StartCapturedScene) as manager:
            start = manager.active_scene_start
            assert start.scene_class == 'StartCapturedScene'
            assert start.arguments == {'level': 1}

    def test_rebuilt_scene_draws_the_same_randomness(self):
        from glitchygames.replay.scene_start import rebuild_scene

        with running_scene(StartCapturedScene) as manager:
            original = manager.active_scene
            step(manager, frames=2)
            random_stream('test.spawn').random()  # advance the stream after the start
            rebuilt = rebuild_scene(start=manager.active_scene_start,
                                    scene_class=StartCapturedScene, options=original.options)
            assert rebuilt.spawn_x == original.spawn_x
            assert rebuilt.level == 1

    def test_non_json_arguments_are_refused(self):
        class BadArguments(StartCapturedScene):
            def replay_arguments(self) -> dict:
                return {'surface': object()}

        with pytest.raises(TypeError, match='BadArguments'), running_scene(BadArguments):
            pass
```

(Add `from glitchygames.randomness import random_stream` to the file's imports.)

In `tests/examples/test_clockwork_keep.py` (next to `test_floor_three_scene_renders_a_frame`,
whose display setup it copies):

```python
    def test_floor_replay_arguments_rebuild_the_floor(self):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 480))
        scene = ClockworkKeepScene(floor_index=2, player_score=1450, player_lives=2,
                                   options={'input_mode': 'joystick'})
        assert scene.replay_arguments() == {'floor_index': 2, 'player_score': 1450,
                                            'player_lives': 2}
``` In
`tests/world/test_gameplay_recording.py`: a recording's frame 0 holds `scene_start` for the game
scene, and the frame where the arrival scene starts holds its `scene_start`.

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement** the randomness functions (module docstring gains a paragraph:
  "``capture_stream_states``/``restore_stream_states`` save and restore every stream exactly
  (in-game playback, plans/2026-10-19-gameplay-replay-playback.md)"), `SceneStart`/
  `rebuild_scene`, the `Scene`/`SceneManager` capture, Clockwork's `replay_arguments` (the three
  constructor arguments it carries between floors — read `ClockworkKeepScene.__init__`), and the
  recorder field. Brave Adventurer, Papyrus and PaddleSlap construct their game scene from options
  only (check: their `__init__` takes no carried arguments); keep the default `{}` there and say so
  in the report.

- [ ] **Step 4: Run** `tests/test_randomness.py tests/world tests/examples`, golden, full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/randomness.py glitchygames/engine/sources.py glitchygames/scenes/scene.py glitchygames/replay/scene_start.py glitchygames/examples/clockwork_keep/game.py glitchygames/recording.py tests/test_randomness.py tests/world/test_frame_integration.py tests/world/test_gameplay_recording.py <clockwork test file>
git commit -m "Capture how each scene began so it can be rebuilt for playback"
```

---

### Task 2: The playback scope

**Files:**
- Create: `glitchygames/replay/playback.py`
- Modify: `glitchygames/engine/sources.py` (`push_scoped_sources`, `pop_scoped_sources`)
- Modify: `glitchygames/scenes/scene.py` (`_enter_playback`, `_exit_playback`, the frame loop runs
  the playback scene; scope end checks after each frame)
- Modify: `glitchygames/replay/driver.py` (`ReplaySources` can serve a recording from a given
  frame without engine-level checks: `ReplaySources.for_playback(...)`)
- Test: `tests/replay/test_playback_scope.py` (new)

**Interfaces:**
- Produces:

```python
def push_scoped_sources(*, sources: EngineSources) -> None
def pop_scoped_sources() -> EngineSources              # raises RuntimeError when none
class PlaybackSources:      # EngineSources; wraps the base and a ReplaySources
    def __init__(self, *, base: EngineSources, replay: ReplaySources,
                 exit_on_input: bool) -> None: ...
    exit_requested: bool
    ended: bool                                        # recording finished or diverged
@dataclasses.dataclass
class PlaybackSession:
    scene: Scene
    sources: PlaybackSources
    live_scene: Scene
    saved_random_states: dict[str, Any]
    saved_frame_clock_seconds: float
    then: Scene                                        # scene to return to
    kind: str                                          # 'demo' | 'instant'
ReplaySources.for_playback(cls, *, header: dict[str, Any], frames: Sequence[dict[str, Any]],
                          start_frame: int = 0) -> ReplaySources   # no game check, no options
SceneManager._enter_playback(self, *, session: PlaybackSession) -> None
SceneManager._exit_playback(self) -> None
SceneManager.playback_session -> PlaybackSession | None
PLAYBACK_EXIT_EVENT_TYPES = frozenset({pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN,
                                       pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN})
```

Scope rules:
- `PlaybackSources.pump_events`: call `base.pump_events()` (real input live; the session's recorded
  batch in a replay of the session — so a recorded session reproduces the exit press), set
  `exit_requested` if it holds an event of a type in `PLAYBACK_EXIT_EVENT_TYPES` (when
  `exit_on_input`), keep a `pygame.QUIT` (it still quits the game), and return the playback
  recording's batch from `replay.pump_events()` (its own internal-event merging) plus that QUIT.
- `input_snapshot`: call `base.input_snapshot()` (keeps the base's recording/journal in step) and
  return `replay.input_snapshot()`.
- `frame_seconds`: `replay.frame_seconds(measured=base.frame_seconds(measured=measured))` (the
  base's door still sees one call per frame).
- `saves`, `devices`, `control_events_for_frame`, `random_seed`: the replay's.
- `end_frame`: `replay.end_frame(...)` (compare with the playback recording; a divergence or the
  end sets `ended`), then `base.end_frame(...)` (the session's recorder writes the frame).
- `stop_requested`: the base's (the scope never stops the run).
- Part 2's doors (`paced_frame_seconds`, `hold_frame`, `draw_overlay`, `presents_frames`):
  the base's — a demo paces and presents like live play — except during Task 5's
  fast-forward, which overrides `paced_frame_seconds` (0.0) and `presents_frames` (False).
  If Part 2 has not run, these doors do not exist yet: skip them here and add them in Task 5.
- Entering (`_enter_playback`): record a `PLAYBACK_KIND` control event (`{'source': kind,
  'frames': <frame count>}`) — a marker, not re-applied (Part 1's
  `REAPPLIED_CONTROL_EVENT_KINDS`); stash `self.active_scene` without `cleanup()`; save stream
  states and the frame clock; push the scoped sources; make the rebuilt scene active through the
  same steps as `_setup_new_scene` + `_configure_active_scene` (snap mode, `setup()`, caption, FPS)
  — read both and reuse them, do not copy them.
- Each frame, after `_run_frame`: if `exit_requested` or `ended` → `_exit_playback()`.
- Exiting: `cleanup()` the playback scene; pop the scoped sources; restore stream states and the
  frame clock; make `then` active again: if `then` is the stashed live scene, restore it directly
  (`self.active_scene = live_scene`, re-activate its snap mode, force a full redraw) **without**
  calling its `setup()` again; otherwise switch to `then` normally.
- Errors: an exception raised while running a playback frame is caught in the frame loop
  (`except Exception` around the playback frame only, logged with `LOG.exception`), and the scope
  exits as above. The live scene is never touched.

- [ ] **Step 1: Write the failing tests** (`tests/replay/test_playback_scope.py`)

```python
"""The playback scope (glitchygames/replay/playback.py): a rebuilt scene plays a recording on
scoped sources while the live game waits untouched."""

from __future__ import annotations

import pygame
import pytest
from scripts.record_golden_traces import FRAME_SECONDS, GoldenTraceSceneManager, press, release

from glitchygames.engine.sources import active_sources
from glitchygames.randomness import random_stream
from glitchygames.replay.playback import PlaybackSources, start_playback_from_recording
from tests.world.test_frame_integration import running_scene, step

from .playback_fixtures import CountingScene, record_counting_scene  # see below


def test_playback_returns_to_the_untouched_live_scene(tmp_path):
    recording_path = record_counting_scene(tmp_path, frames=10)
    with running_scene(CountingScene) as manager:
        step(manager, frames=3)
        live_scene = manager.active_scene
        live_state = live_scene.frames_ticked
        setup_calls = live_scene.setup_calls
        start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
        step(manager, frames=12)  # the 10-frame recording plays, then the scope ends
        assert manager.active_scene is live_scene
        assert live_scene.frames_ticked == live_state
        assert live_scene.setup_calls == setup_calls


def test_random_streams_are_unchanged_by_a_playback(tmp_path):
    recording_path = record_counting_scene(tmp_path, frames=10)
    with running_scene(CountingScene) as manager:
        step(manager, frames=2)
        expected_next = random_stream('test.counting').getstate()
        start_playback_from_recording(manager=manager, path=recording_path,
                                      then=manager.active_scene)
        step(manager, frames=12)
        assert random_stream('test.counting').getstate() == expected_next


def test_any_key_ends_a_demo(tmp_path):
    recording_path = record_counting_scene(tmp_path, frames=100)
    with running_scene(CountingScene) as manager:
        live_scene = manager.active_scene
        start_playback_from_recording(manager=manager, path=recording_path, then=live_scene,
                                      exit_on_input=True)
        step(manager, frames=2)
        assert manager.playback_session is not None
        step(manager, press(pygame.K_SPACE), frames=1)
        step(manager, release(pygame.K_SPACE), frames=1)
        assert manager.playback_session is None
        assert manager.active_scene is live_scene


def test_error_inside_scope_restores_the_live_game(tmp_path, mocker, caplog):
    recording_path = record_counting_scene(tmp_path, frames=10)
    with running_scene(CountingScene) as manager:
        live_scene = manager.active_scene
        start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
        mocker.patch.object(type(manager.active_scene), 'dt_tick',
                            side_effect=RuntimeError('boom'))
        step(manager, frames=1)
        assert manager.active_scene is live_scene
        assert isinstance(active_sources(), type(active_sources()))
        assert not isinstance(active_sources(), PlaybackSources)
        assert 'boom' in caplog.text


def test_real_saves_untouched_by_a_playback(tmp_path, mocker):
    from glitchygames.state import SaveManager

    save_directory = tmp_path / 'saves'
    mocker.patch('glitchygames.state.manager.get_save_directory',
                 side_effect=lambda app_name: save_directory / app_name)
    SaveManager(app_name='counting').save('slot', {'value': 1})
    recording_path = record_counting_scene(tmp_path, frames=6, scene_class=SavingCountingScene)
    SaveManager(app_name='counting').save('slot', {'value': 1})  # undo the live write
    slot_file = next((save_directory / 'counting').iterdir())
    bytes_before = slot_file.read_bytes()
    with running_scene(CountingScene) as manager:
        start_playback_from_recording(manager=manager, path=recording_path,
                                      then=manager.active_scene)
        step(manager, frames=8)
    assert slot_file.read_bytes() == bytes_before
```

(import `SavingCountingScene` from `playback_fixtures` too.)

`tests/replay/playback_fixtures.py` (a helper module, not a test file):

```python
"""A small scene and a recorder for the playback-scope tests."""

from __future__ import annotations

from pathlib import Path

from scripts.record_golden_traces import FRAME_SECONDS

from glitchygames.randomness import random_stream
from glitchygames.state.sandbox import open_saves
from tests.world.test_frame_integration import CameraFreeScene, running_scene, step


class CountingScene(CameraFreeScene):
    """Counts its ticks and setups, and draws from an engine stream every tick."""

    def __init__(self, options=None, groups=None) -> None:
        super().__init__(options=options, groups=groups)
        self.frames_ticked = 0
        self.setup_calls = 0

    def setup(self) -> None:
        super().setup()
        self.setup_calls += 1

    def dt_tick(self, dt: float) -> None:
        super().dt_tick(dt)
        self.frames_ticked += 1
        random_stream('test.counting').random()


class SavingCountingScene(CountingScene):
    """Writes its save slot on its third tick (open_saves goes through the saves door)."""

    def dt_tick(self, dt: float) -> None:
        super().dt_tick(dt)
        if self.frames_ticked == 3:
            open_saves(app_name='counting').save('slot', {'value': 2})


def record_counting_scene(tmp_path: Path, *, frames: int,
                          scene_class: type[CountingScene] = CountingScene) -> Path:
    """Record `frames` frames of a counting scene through the harness and return the path."""
    recording_path = tmp_path / 'counting.jsonl.gz'
    with running_scene(scene_class) as manager:
        manager.game_engine.start_trace_recording(path=recording_path)
        step(manager, frames=frames)
        manager.game_engine.stop_trace_recording()
    return recording_path
```

(Check `running_scene`'s signature and teardown; it must uninstall the scene manager on exit. If
`CameraFreeScene` already overrides `setup` or `dt_tick`, call `super()` as shown.)

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement** `PlaybackSources`, `PlaybackSession`, the registry push/pop,
  `SceneManager._enter_playback`/`_exit_playback`/`playback_session`, the per-frame end check and
  the error containment, and a helper used by Tasks 3 and 5:

```python
def start_playback_from_recording(*, manager: SceneManager, path: Path, then: Scene,
                                  exit_on_input: bool = False, kind: str = 'demo',
                                  start_frame: int = 0) -> None:
    """Rebuild the recording's scene from its frame-`start_frame` scene_start and enter a scope."""
```

  (frame `start_frame` must hold a `scene_start`; frame 0 always does since Task 1 — otherwise
  log and return without entering.)

- [ ] **Step 4: Run** `tests/replay`, `tests/world`, golden, full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/replay/playback.py glitchygames/engine/sources.py glitchygames/scenes/scene.py glitchygames/replay/driver.py tests/replay/test_playback_scope.py tests/replay/playback_fixtures.py
git commit -m "Add the playback scope: rebuilt scenes play recordings on scoped sources"
```

---

### Task 3: Demos

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`SceneManager.play_recording`)
- Test: `tests/replay/test_playback_scope.py`

**Interfaces:**
- Produces: `SceneManager.play_recording(self, *, path: Path, then: Scene) -> bool` — True when the
  demo started; False (and one warning) when the recording is unusable (unreadable, a different
  game, no `scene_start`). Exit on any key/button press (`exit_on_input=True`), `kind='demo'`; a
  divergence ends the demo early and logs the divergence at WARNING.

- [ ] **Step 1: Write the failing tests**

```python
def test_play_recording_runs_a_demo_and_returns(tmp_path):
    recording_path = record_counting_scene(tmp_path, frames=5)
    with running_scene(CountingScene) as manager:
        title_scene = manager.active_scene
        assert manager.play_recording(path=recording_path, then=title_scene)
        step(manager, frames=7)
        assert manager.active_scene is title_scene


def test_unusable_demo_is_refused(tmp_path, caplog):
    broken = tmp_path / 'broken.jsonl.gz'
    broken.write_bytes(b'not a trace')
    with running_scene(CountingScene) as manager:
        assert not manager.play_recording(path=broken, then=manager.active_scene)
        assert 'demo' in caplog.text


def test_diverging_demo_ends_early(tmp_path, caplog):
    recording_path = record_counting_scene(tmp_path, frames=20)
    tamper_sprite_in_frame(recording_path, frame_number=4)   # helper in playback_fixtures
    with running_scene(CountingScene) as manager:
        title_scene = manager.active_scene
        manager.play_recording(path=recording_path, then=title_scene)
        step(manager, frames=6)
        assert manager.active_scene is title_scene
        assert 'diverged' in caplog.text
```

(Add `tamper_sprite_in_frame` to `playback_fixtures.py`, written like Part 1's
`tamper_first_sprite_rect`. `CountingScene` needs at least one sprite in `all_sprites` for the
tamper to have something to change: add a small `pygame.sprite.DirtySprite` in its `__init__`.)

- [ ] **Step 2–4:** fail; implement `play_recording` on top of `start_playback_from_recording`;
  run `tests/replay` and the full suite.

- [ ] **Step 5: Commit**

```bash
git add glitchygames/scenes/scene.py tests/replay/test_playback_scope.py tests/replay/playback_fixtures.py
git commit -m "Add SceneManager.play_recording for attract-mode demos"
```

---

### Task 4: Instant-replay journal

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`Scene.INSTANT_REPLAY_SECONDS`,
  `Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`; the manager keeps a journal for the active
  scene when it opts in)
- Modify: `glitchygames/replay/playback.py` (`InstantReplayJournal`)
- Modify: `glitchygames/engine/sources.py` (`LiveSources`: hand each frame's batches and snapshot
  to the journal — through a small `FrameInputListener` Protocol the manager registers, so
  `RecordingSources` and `ReplaySources` feed it too)
- Test: `tests/replay/test_instant_replay.py` (new)

**Interfaces:**
- Produces:

```python
Scene.INSTANT_REPLAY_SECONDS: ClassVar[float | None] = None
Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS: ClassVar[float] = 60.0
class InstantReplayJournal:
    def __init__(self, *, start: SceneStart) -> None: ...
    def add_frame(self, *, frame_record: dict[str, Any]) -> None: ...   # dt, batches, input changes
    frames: list[dict[str, Any]]
    game_seconds: float
    def as_recording(self) -> tuple[dict[str, Any], list[dict[str, Any]]]: ...  # header, frames
    def within_budget(self, *, maximum_seconds: float) -> bool: ...
SceneManager.instant_replay_journal -> InstantReplayJournal | None
```

Rules: when a scene with `INSTANT_REPLAY_SECONDS` set becomes active (`_setup_new_scene`), the
manager starts a journal from `active_scene_start` (Task 1). After each frame of that scene, it
adds `{'frame': n, 'scene': ..., 'sprites': <sampled>, 'dt': ..., 'event_batches': [...],
'input_changes': {...}, 'control_events': [...]}` — the same records `RecordingSources` writes
(reuse the recorder's record-building functions; refactor them out of `GameplayRecorder` into
module functions in `recording.py` if needed, so both use one implementation). The journal is
dropped when the scene stops being active (switch, transition), and not kept for scenes without
the attribute. Memory: event batches and input changes only grow on input; sprites are sampled —
keep sprites only for the frames the replay will show visibly? No: keep them for all frames, as
`end_frame` compares every replayed frame; document the measured size (bytes per minute from a
test run) in the report.

- [ ] **Step 1: Write the failing tests** (`tests/replay/test_instant_replay.py`)

```python
"""The instant-replay journal (glitchygames/replay/playback.py)."""

from scripts.record_golden_traces import FRAME_SECONDS

from tests.replay.playback_fixtures import CountingScene
from tests.world.test_frame_integration import running_scene, step


class InstantCountingScene(CountingScene):
    INSTANT_REPLAY_SECONDS = 10.0


def test_journal_records_every_frame_of_an_opted_in_scene():
    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=5)
        journal = manager.instant_replay_journal
        assert len(journal.frames) == 5
        assert journal.game_seconds == 5 * FRAME_SECONDS


def test_scenes_without_the_attribute_keep_no_journal():
    with running_scene(CountingScene) as manager:
        step(manager, frames=5)
        assert manager.instant_replay_journal is None


def test_budget():
    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=10)
        journal = manager.instant_replay_journal
        assert journal.within_budget(maximum_seconds=1.0)
        assert not journal.within_budget(maximum_seconds=5 * FRAME_SECONDS)


def test_journal_as_recording_replays_through_replay_sources():
    from glitchygames.replay.driver import ReplaySources

    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=4)
        header, frames = manager.instant_replay_journal.as_recording()
        sources = ReplaySources(header=header, frames=frames, format_version=3)
        assert sources.recorded_dt(frame_number=0) == FRAME_SECONDS
```

(`ReplaySources.recorded_dt` comes from Part 2 Task 2; if Part 2 has not run, add the accessor
here — it is one line returning `self._frames[frame_number]['dt']`.)

- [ ] **Step 2–4:** fail; implement; run `tests/replay`, `tests/world`, full suite; measure the
  journal's size for 3600 frames of PaddleSlap's golden script and put the number in the report.

- [ ] **Step 5: Commit**

```bash
git add glitchygames/scenes/scene.py glitchygames/replay/playback.py glitchygames/engine/sources.py glitchygames/recording.py tests/replay/test_instant_replay.py
git commit -m "Keep an in-memory input journal for scenes that offer instant replay"
```

---

### Task 5: Instant replay

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`SceneManager.instant_replay`; fast-forward frames skip
  `_present_frame`)
- Modify: `glitchygames/replay/playback.py` (scope kind `'instant'`: fast-forward, then visible,
  then return to the live scene where it was)
- Test: `tests/replay/test_instant_replay.py`

**Interfaces:**
- Produces: `SceneManager.instant_replay(self) -> bool`. False (nothing happens) when the active
  scene has no journal or the journal exceeds `MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`. True:
  a scope of kind `'instant'` starts: the rebuilt scene replays the journal's frames; frames before
  `game_seconds - INSTANT_REPLAY_SECONDS` are fast-forwarded (no presenting, no pacing — reuse
  Part 2's `presents_frames()`/`paced_frame_seconds()` doors when present, or add them here if
  Part 2 has not run), the rest play visibly; at the end of the journal the scope ends and the live
  scene continues exactly where it was. Any key does not end an instant replay
  (`exit_on_input=False`); the game decides (it can call `SceneManager._exit_playback` through a
  public `end_playback()` — add it).

- [ ] **Step 1: Write the failing tests**

```python
def test_instant_replay_shows_the_last_seconds_and_returns(mocker):
    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=30)
        live_scene = manager.active_scene
        ticked = live_scene.frames_ticked
        presented = mocker.spy(manager, '_present_frame')
        mocker.patch.object(InstantCountingScene, 'INSTANT_REPLAY_SECONDS', 10 * FRAME_SECONDS)
        assert manager.instant_replay()
        step(manager, frames=30)
        assert manager.active_scene is live_scene
        assert live_scene.frames_ticked == ticked
        assert presented.call_count == 10   # only the last ten frames were shown


def test_instant_replay_refused_past_the_budget(mocker):
    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=30)
        mocker.patch.object(InstantCountingScene, 'MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS',
                            5 * FRAME_SECONDS)
        assert not manager.instant_replay()
        assert manager.playback_session is None


def test_instant_replay_matches_the_live_frames():
    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=20)
        assert manager.instant_replay()
        step(manager, frames=20)
        assert manager.last_playback_result.divergence is None
```

(`SceneManager.last_playback_result` keeps the ended scope's `ReplayResult`; add it in this task.
The `presented.call_count` assertion counts `_present_frame` calls during the scope: the step loop
of the harness calls `run_frame`, which presents once per visible frame.)

- [ ] **Step 2–4:** fail; implement; run `tests/replay`, `tests/world`, golden, full suite.

- [ ] **Step 5: Commit**

```bash
git add glitchygames/scenes/scene.py glitchygames/replay/playback.py tests/replay/test_instant_replay.py
git commit -m "Add instant replay: fast-forward a rebuilt scene, show the last seconds, return"
```

---

### Task 6: Ghosts

**Files:**
- Create: `glitchygames/replay/ghosts.py`
- Test: `tests/replay/test_ghosts.py` (new)
- Docs: CLAUDE.md (in-game playback: `play_recording`, `instant_replay`, `INSTANT_REPLAY_SECONDS`,
  `replay_arguments`, ghosts), the replay docs page, `plans/future-work.md` (state snapshots for
  long instant replays and fast step-back; the cheat-device spec using the supervisor hook and
  control events)

**Interfaces:**
- Produces:

```python
@dataclasses.dataclass(frozen=True)
class GhostSample:
    game_seconds: float
    world_x: float
    world_y: float
    appearance: dict[str, Any]       # JSON-safe; default: animation, frame, flip_x
    visible: bool
class GhostTrack:
    samples: tuple[GhostSample, ...]
    def sample_at(self, *, game_seconds: float) -> GhostSample | None: ...  # last sample <= t
    def to_json(self) -> dict[str, Any]: ...
    @classmethod
    def from_json(cls, record: dict[str, Any]) -> GhostTrack: ...
def default_appearance(sprite: object) -> dict[str, Any]
class GhostRecorder:                 # a Supervisor
    def __init__(self, *, sprite: object,
                 appearance: Callable[[object], dict[str, Any]] = default_appearance) -> None: ...
    def on_frame(self, *, frame_number: int, scene: Scene | None) -> None: ...
    def finish(self) -> GhostTrack: ...
def images_from_animated_sprite(source: AnimatedSprite) -> Callable[[GhostSample], pygame.Surface]
class GhostSprite(pygame.sprite.DirtySprite):
    COORDINATE_SPACE = CoordinateSpace.WORLD
    def __init__(self, *, track: GhostTrack, image_for: Callable[[GhostSample], pygame.Surface],
                 alpha: int = 96) -> None: ...
    world_x: float; world_y: float
    def update(self) -> None: ...    # reads the scene's game_time through its `scene` attribute
```

Rules: the recorder registers itself with `SceneManager().add_supervisor(supervisor=self)` in its
constructor and removes itself in `finish()`; each frame it samples `scene.game_time`,
`sprite.world_x`/`world_y`, `appearance(sprite)` and `bool(sprite.visible)`.
`default_appearance` returns `{'animation': sprite.current_animation, 'frame':
sprite.current_frame, 'flip_x': bool(getattr(sprite, 'hitbox_flip_x', False))}` for an
`AnimatedSprite` and `{}` otherwise. `images_from_animated_sprite(source)` returns a function that
takes a sample and returns `source.frames[animation][frame].image`, flipped horizontally when
`flip_x`. `GhostSprite.update()` reads `self.scene.game_time` (the game sets `ghost.scene = self`
when adding it — document it), picks `track.sample_at(...)`, sets `world_x`/`world_y`, its image
(with `set_alpha(alpha)` on a copy) and `hidden = not sample.visible` (Part of the world-space API:
`hidden` keeps the engine's culling in charge of `visible`). A ghost has no hitbox: it is never
added to a collision group, and `TRIM_TRANSPARENT_HITBOX` is irrelevant. Ghosts take no part in
replay comparison beyond being sprites: their track comes from saves (sandboxed in a replay), so a
replayed session with a ghost matches.

- [ ] **Step 1: Write the failing tests** (`tests/replay/test_ghosts.py`)

```python
"""Ghosts (glitchygames/replay/ghosts.py): recorded appearance played beside live play."""

import json

import pygame

from glitchygames.replay.ghosts import GhostSample, GhostSprite, GhostTrack
from glitchygames.world import CoordinateSpace, is_world_positioned


def sample(seconds: float, x: float) -> GhostSample:
    return GhostSample(game_seconds=seconds, world_x=x, world_y=10.0, appearance={},
                       visible=True)


def test_sample_at_picks_the_last_sample_not_after_the_time():
    track = GhostTrack(samples=(sample(0.0, 0.0), sample(0.5, 5.0), sample(1.0, 10.0)))
    assert track.sample_at(game_seconds=0.75).world_x == 5.0
    assert track.sample_at(game_seconds=-1.0) is None


def test_track_json_round_trip():
    track = GhostTrack(samples=(sample(0.0, 1.5), sample(0.016, 2.5)))
    assert GhostTrack.from_json(json.loads(json.dumps(track.to_json()))) == track


def test_ghost_sprite_is_world_positioned_and_follows_game_time():
    track = GhostTrack(samples=(sample(0.0, 0.0), sample(1.0, 50.0)))
    ghost = GhostSprite(track=track, image_for=lambda _sample: pygame.Surface((4, 4)))
    ghost.scene = type('SceneStandIn', (), {'game_time': 1.25})()
    ghost.update()
    assert is_world_positioned(ghost)
    assert ghost.COORDINATE_SPACE is CoordinateSpace.WORLD
    assert (ghost.world_x, ghost.world_y) == (50.0, 10.0)
    assert ghost.hidden is False


def test_ghost_plays_at_the_right_speed_at_another_frame_rate():
    track = GhostTrack(samples=tuple(sample(index / 60, float(index)) for index in range(61)))
    ghost = GhostSprite(track=track, image_for=lambda _sample: pygame.Surface((4, 4)))
    ghost.scene = type('SceneStandIn', (), {'game_time': 0.5})()   # 30 FPS playback time
    ghost.update()
    assert ghost.world_x == 30.0
```

Plus a recorder test in `tests/world/test_frame_integration.py` with `running_scene`: a
`GhostRecorder` on a `WorldSprite` that moves each frame records one sample per frame with the
scene's `game_time`, and `finish()` unregisters it (a later frame adds nothing).

- [ ] **Step 2–4:** fail; implement; run `tests/replay`, `tests/world`, full suite.

- [ ] **Step 5: Docs, lint, type-check, mkdocs strict, commit**

```bash
git add glitchygames/replay/ghosts.py tests/replay/test_ghosts.py tests/world/test_frame_integration.py CLAUDE.md docs/<replay page> plans/future-work.md
git commit -m "Add ghosts: record a sprite's appearance and play it beside live play"
```
