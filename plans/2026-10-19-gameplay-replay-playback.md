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

See the master plan. Parts 1 and 2 must be complete (master order): Task 4 uses Part 2's
scripted-session recorder and replay plugin, Task 6 its `presents_frames()` / `paced_frame_seconds()`
doors and unpaced path, Task 5 its `recording.recorded_dt`; Task 2 creates `tests/replay/__init__.py` only if
Part 2 did not.

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
| 4 | A bundled PaddleSlap demo and its replay test | `paddleslap_demos/rally.jsonl.gz`, `tests/replays/test_bundled_demos.py` |
| 5 | Instant-replay journal | `INSTANT_REPLAY_SECONDS`, in-memory inputs since scene start, budget |
| 6 | Instant replay | `SceneManager.instant_replay`, fast-forward without presenting |
| 7 | Ghosts | `GhostRecorder`, `GhostTrack`, `GhostSprite` |

---

### Task 1: Rebuilding a scene from its start

**Files:**
- Modify: `glitchygames/randomness.py` (`capture_stream_states`, `restore_stream_states`)
- Modify: `glitchygames/sources.py` (`set_frame_clock_seconds`)
- Modify: `glitchygames/scenes/scene.py` — `Scene.__init__` (capture streams first),
  `Scene.replay_arguments`, `SceneManager._setup_new_scene` (complete the start capture before
  `setup()`), `SceneManager.active_scene_start` (the active scene's capture)
- Modify: `glitchygames/examples/clockwork_keep/game.py` (`replay_arguments` for floors)
- Create: `glitchygames/replay/scene_start.py` (`SceneStart`, `rebuild_scene`,
  `scene_start_capture_enabled`)
- Modify: `glitchygames/recording.py` (`RecordingSources` writes `scene_start` on the frame a
  scene started, and the active scene's start on frame 0; `captures_scene_starts` is True)
- Modify: `glitchygames/sources.py` (Protocol `captures_scene_starts`, `opened_save_stores`),
  `glitchygames/live_sources.py` (False; the stores it opened), `glitchygames/replay/driver.py`
  (False; its sandboxes)
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
def scene_start_capture_enabled(*, scene_class: type[Scene]) -> bool
EngineSources.captures_scene_starts -> bool          # property: True while recording
EngineSources.opened_save_stores(self) -> dict[str, SaveStore]   # namespace -> store opened
```

`SceneStart` lives in a new `glitchygames/replay/scene_start.py`. Capture happens only while it
can be used (spec 5.1): `scene_start_capture_enabled(scene_class=...)` is True while the active
sources record (`captures_scene_starts`), while a playback scope is active (scoped sources pushed),
or when the scene class opts into instant replay (`INSTANT_REPLAY_SECONDS` is not None, Task 5);
otherwise nothing is captured and live play pays nothing (no save snapshots on scene switches).
Capture rules when enabled: `Scene.__init__` calls `capture_stream_states()` as its first
statement and keeps it (`self._start_random_states`) — before the subclass body after
`super().__init__()` draws anything; the frame clock is read at the same point. A scene instance's
start is completed only on its **first** setup: `_setup_new_scene`, before `setup()`, if the scene
has no `_scene_start` yet, completes it — `replay_arguments()` (JSON-safe; check with `json.dumps`
and raise `TypeError` naming the scene if not), the save views (`save_namespace_snapshot` of every
store in `active_sources().opened_save_stores()`, which handles sandboxes too) — and keeps it on the
scene. Resuming the scene from the pause screen runs `_setup_new_scene` again and must keep the
first capture (and Task 5's journal). `SceneManager.active_scene_start` returns the active scene's
`_scene_start` (None when not captured). `rebuild_scene`: `restore_stream_states(states=start.random_states)`,
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
    def test_start_capture_holds_arguments_and_streams(self, mocker):
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0, create=True)
        with running_scene(StartCapturedScene) as manager:
            start = manager.active_scene_start
            assert start is not None
            assert start.scene_class == 'StartCapturedScene'
            assert start.arguments == {'level': 1}

    def test_rebuilt_scene_draws_the_same_randomness(self, mocker):
        from glitchygames.replay.scene_start import rebuild_scene

        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0, create=True)
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
            INSTANT_REPLAY_SECONDS = 10.0

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
```

In `tests/world/test_frame_integration.py`:

```python
class TestSceneStartCaptureScope:
    def test_live_play_captures_nothing(self):
        with running_scene(StartCapturedScene) as manager:
            assert manager.active_scene_start is None

    def test_resume_from_pause_keeps_the_first_capture(self, mocker):
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0, create=True)
        with running_scene(StartCapturedScene) as manager:
            first = manager.active_scene_start
            game_scene = manager.active_scene
            step(manager, press(pygame.K_ESCAPE), release(pygame.K_ESCAPE), frames=2)  # pause
            step(manager, press(pygame.K_ESCAPE), release(pygame.K_ESCAPE), frames=2)  # resume
            assert manager.active_scene is game_scene
            assert manager.active_scene_start is first
```

(Use the pause/resume keys `TestResumeAfterPause` in that file uses; `StartCapturedScene` needs
the same pause handling as that test's scene — subclass it instead if `CameraFreeScene` does not
pause. `INSTANT_REPLAY_SECONDS` is declared on `Scene` in Task 5; until then
`scene_start_capture_enabled` reads it with `getattr(scene_class, 'INSTANT_REPLAY_SECONDS', None)`
and the tests patch it with `create=True`; Task 5 removes `create=True` once the attribute
exists.)

In `tests/world/test_gameplay_recording.py`:

```python
    def test_recording_holds_each_scene_start(self, mocker, tmp_path):
        recording_path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
        frames = read_trace_result(path=recording_path).trace['frames']
        assert frames[0]['scene_start']['scene_class'] == 'DepartureRecordedScene'
        arrival_starts = [frame['frame'] for frame in frames
                          if frame.get('scene_start', {}).get('scene_class')
                          == 'ArrivalRecordedScene']
        assert len(arrival_starts) == 1
```

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
git add glitchygames/randomness.py glitchygames/sources.py glitchygames/live_sources.py glitchygames/replay/driver.py glitchygames/scenes/scene.py glitchygames/replay/scene_start.py glitchygames/examples/clockwork_keep/game.py glitchygames/recording.py tests/test_randomness.py tests/world/test_frame_integration.py tests/world/test_gameplay_recording.py tests/examples/test_clockwork_keep.py
git commit -m "Capture how each scene began so it can be rebuilt for playback"
```

---

### Task 2: The playback scope

**Files:**
- Create: `glitchygames/replay/playback.py`
- Modify: `glitchygames/sources.py` (`push_scoped_sources`, `pop_scoped_sources`)
- Modify: `glitchygames/scenes/scene.py` (`_enter_playback`, `_exit_playback`,
  `playback_session`; `_run_frame` holds the end check and the error containment)
- Modify: `glitchygames/replay/driver.py` (`ReplaySources.for_playback(...)`: serves a recording
  from a given frame with no game check, no options, no controls and no overlay, and stops at its
  end or first divergence — it never pauses)
- Create (if missing): `tests/replay/__init__.py` (Part 2 Task 2 normally created it)
- Create: `tests/replay/playback_fixtures.py` (helpers, not a test file)
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
    saved_fps_event_seconds: float                     # SceneManager._previous_fps_event_seconds
    then: Scene                                        # scene to return to
    kind: str                                          # 'demo' | 'instant'
ReplaySources.for_playback(cls, *, header: dict[str, Any], frames: Sequence[dict[str, Any]],
                          start_frame: int = 0) -> ReplaySources   # serve from frame start_frame
def start_playback(*, manager: SceneManager, header: dict[str, Any],
                   frames: Sequence[dict[str, Any]], then: Scene, exit_on_input: bool = False,
                   kind: str = 'demo', start_frame: int = 0) -> bool
def start_playback_from_recording(*, manager: SceneManager, path: Path, then: Scene,
                                  exit_on_input: bool = False, kind: str = 'demo') -> bool
SceneManager._enter_playback(self, *, session: PlaybackSession) -> None
SceneManager._exit_playback(self) -> None
SceneManager.playback_session -> PlaybackSession | None
SceneManager.last_playback_result -> ReplayResult | None
PLAYBACK_EXIT_EVENT_TYPES = frozenset({pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN,
                                       pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN})
```

`start_frame` means "serve the recording from frame N" (Part 2's step-back uses a different
parameter, `pause_at_frame`); a playback never pauses. `start_playback` returns False (logging why)
when frame `start_frame` has no `scene_start` or the scene class cannot be found; the path variant
also returns False for an unreadable file. Both return True when the scope was entered.

Scope rules:
- **Starting** (`start_playback`): first save the live state — `capture_stream_states()`, the frame
  clock, `manager._previous_fps_event_seconds` — then `rebuild_scene(...)` (which restores the
  recording's streams and frame clock), then `_enter_playback(session=...)`.
- `PlaybackSources.pump_events`: call `base.pump_events()` once (real input live; the session's
  recorded batch in a replay of the session — so a recorded session reproduces the exit press).
  Its external events feed only the exit check (`exit_requested` when one has a type in
  `PLAYBACK_EXIT_EVENT_TYPES` and `exit_on_input`); a `pygame.QUIT` is kept (it still quits the
  game). Its internal events — the playback scene's own posts (FPS events from `_finish_frame`,
  game events), classified by the base — are handed to the replay:
  `replay.pump_events(real_events=<those internal events>)`, so the replay's exact merge (Part 1
  Task 13) sees them; the scope returns the replay's batch plus the QUIT.
- **Frame indexes**: the replay indexes its recording by its own count of `end_frame` calls (Part 1
  Task 12, rule 3), so session frame numbers (which do not start at 0 inside a scope) never index
  the playback recording; `start_frame` offsets that count at the scope's start.
- `input_snapshot`: call `base.input_snapshot()` (keeps the base's recording/journal in step) and
  return `replay.input_snapshot()`.
- `frame_seconds`: `replay.frame_seconds(measured=base.frame_seconds(measured=measured))` (the
  base's door still sees one call per frame).
- `saves`, `devices`, `control_events_for_frame`, `random_seed`, `wall_clock_time`,
  `opened_save_stores`: the replay's. (Elapsed seconds are the frame clock, not a door, since
  core Task 12b.)
- `end_frame`: `replay.end_frame(...)` (compare with the playback recording; a divergence or the
  end sets `ended`), then `base.end_frame(...)` (the session's recorder writes the frame).
- `stop_requested`: the base's (the scope never stops the run). `captures_scene_starts`: True.
- Part 2's doors (`paced_frame_seconds`, `hold_frame`, `draw_overlay`, `presents_frames`): the
  base's — a demo paces and presents like live play — except during Task 6's fast-forward, which
  overrides `paced_frame_seconds` (0.0) and `presents_frames` (False). Part 2 runs before Part 3
  (master order), so these doors exist.
- **Entering** (`_enter_playback`): record a `PLAYBACK_KIND` control event (`{'source': kind,
  'frames': <frame count>}`) — a marker, not re-applied (Part 1's
  `REAPPLIED_CONTROL_EVENT_KINDS`); stash `self.active_scene` without `cleanup()`; push the scoped
  sources; make the rebuilt scene active through the same steps as `_setup_new_scene` +
  `_configure_active_scene` (snap mode, `setup()`, caption, FPS) — read both and reuse them, do not
  copy them.
- **End check and error containment live in `_run_frame`**, so `start()` and the harness share
  them: `_run_frame` wraps the frame body, while a playback session is active, in
  `try: ... except Exception: LOG.exception(...); self._exit_playback()`, and after the body (and
  `end_frame`) calls `self._exit_playback()` when `exit_requested` or `ended`.
- **Exiting**: keep the replay's `ReplayResult` as `last_playback_result`; `cleanup()` the playback
  scene; pop the scoped sources; restore stream states, the frame clock and
  `_previous_fps_event_seconds` from the session; make `then` active again: if `then` is the
  stashed live scene, restore it directly (`self.active_scene = live_scene`, re-activate its snap
  mode, force a full redraw) **without** calling its `setup()` again; otherwise switch to `then`
  normally. The live scene is never touched.

- [ ] **Step 1: Write the failing tests** (`tests/replay/test_playback_scope.py`)

```python
"""The playback scope (glitchygames/replay/playback.py): a rebuilt scene plays a recording on
scoped sources while the live game waits untouched."""

from __future__ import annotations

import pygame
from scripts.record_golden_traces import press, release

from glitchygames.randomness import random_stream
from glitchygames.replay.playback import PlaybackSources, start_playback_from_recording
from glitchygames.sources import active_sources
from tests.replay.playback_fixtures import (
    CountingScene,
    SavingCountingScene,
    record_counting_scene,
)
from tests.world.test_frame_integration import running_scene, step


def test_playback_returns_to_the_untouched_live_scene(tmp_path):
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=10)
    with running_scene(CountingScene) as manager:
        step(manager, frames=3)
        live_scene = manager.active_scene
        live_state = live_scene.frames_ticked
        setup_calls = live_scene.setup_calls
        assert start_playback_from_recording(manager=manager, path=recording_path,
                                             then=live_scene)
        step(manager, frames=12)  # the 10-frame recording plays, then the scope ends
        assert manager.active_scene is live_scene
        assert live_scene.frames_ticked == live_state
        assert live_scene.setup_calls == setup_calls
        assert manager.last_playback_result.divergence is None


def test_random_streams_are_unchanged_by_a_playback(tmp_path):
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=10)
    with running_scene(CountingScene) as manager:
        step(manager, frames=2)
        expected_next = random_stream('test.counting').getstate()
        start_playback_from_recording(manager=manager, path=recording_path,
                                      then=manager.active_scene)
        step(manager, frames=12)
        assert random_stream('test.counting').getstate() == expected_next


def test_any_key_ends_a_demo(tmp_path):
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=100)
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
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=10)
    with running_scene(CountingScene) as manager:
        step(manager, frames=2)
        live_scene = manager.active_scene
        expected_next = random_stream('test.counting').getstate()
        sources_before = active_sources()
        start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
        mocker.patch.object(type(manager.active_scene), 'dt_tick',
                            side_effect=RuntimeError('boom'))
        step(manager, frames=1)
        assert manager.active_scene is live_scene
        assert active_sources() is sources_before
        assert not isinstance(active_sources(), PlaybackSources)
        assert random_stream('test.counting').getstate() == expected_next
        assert 'boom' in caplog.text


def test_real_saves_untouched_by_a_playback(tmp_path, mocker):
    from glitchygames.state import SaveManager

    save_directory = tmp_path / 'saves'
    mocker.patch('glitchygames.state.manager.get_save_directory',
                 side_effect=lambda app_name: save_directory / app_name)
    SaveManager(app_name='counting').save('slot', {'value': 1})
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=6,
                                           scene_class=SavingCountingScene)
    SaveManager(app_name='counting').save('slot', {'value': 1})  # undo the live write
    slot_file = next((save_directory / 'counting').iterdir())
    bytes_before = slot_file.read_bytes()
    with running_scene(CountingScene) as manager:
        start_playback_from_recording(manager=manager, path=recording_path,
                                      then=manager.active_scene)
        step(manager, frames=8)
    assert slot_file.read_bytes() == bytes_before


def test_playback_scene_posts_reach_the_replay_merge(tmp_path):
    """The playback scene's own internal posts are handed to the replay, which matches them
    against the recording (no 'missing internal event')."""
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=8,
                                           scene_class=PostingCountingScene)
    with running_scene(CountingScene) as manager:
        start_playback_from_recording(manager=manager, path=recording_path,
                                      then=manager.active_scene)
        step(manager, frames=10)
        assert manager.last_playback_result.divergence is None


def test_playback_frames_index_the_recording_from_its_start(tmp_path):
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=6)
    with running_scene(CountingScene) as manager:
        step(manager, frames=40)          # session frame numbers are far from 0
        start_playback_from_recording(manager=manager, path=recording_path,
                                      then=manager.active_scene)
        step(manager, frames=8)
        assert manager.last_playback_result.divergence is None
        assert manager.last_playback_result.frames_replayed == 6
```

`tests/replay/playback_fixtures.py` (a helper module, not a test file):

```python
"""Small scenes and a recorder for the playback tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from glitchygames.randomness import random_stream
from glitchygames.recording import post_event
from glitchygames.state.sandbox import open_saves
from tests.world.test_frame_integration import CameraFreeScene, running_scene, step

if TYPE_CHECKING:
    from pathlib import Path

POSTED_EVENT_TYPE = pygame.USEREVENT + 44


class CountingScene(CameraFreeScene):
    """Counts its ticks and setups, and draws from an engine stream every tick."""

    INSTANT_REPLAY_SECONDS = None

    def __init__(self, options=None, groups=None) -> None:
        super().__init__(options=options, groups=groups)
        self.frames_ticked = 0
        self.setup_calls = 0
        self.marker = pygame.sprite.DirtySprite()
        self.marker.image = pygame.Surface((4, 4))
        self.marker.rect = self.marker.image.get_rect()
        self.all_sprites.add(self.marker)

    def setup(self) -> None:
        super().setup()
        self.setup_calls += 1

    def dt_tick(self, dt: float) -> None:
        super().dt_tick(dt)
        self.frames_ticked += 1
        self.marker.rect.x = int(random_stream('test.counting').random() * 100)


class SavingCountingScene(CountingScene):
    """Writes its save slot on its third tick (open_saves goes through the saves door)."""

    def dt_tick(self, dt: float) -> None:
        super().dt_tick(dt)
        if self.frames_ticked == 3:
            open_saves(app_name='counting').save('slot', {'value': 2})


class PostingCountingScene(CountingScene):
    """Posts an internal event every tick (as engine code would)."""

    def dt_tick(self, dt: float) -> None:
        super().dt_tick(dt)
        post_event(pygame.event.Event(POSTED_EVENT_TYPE, {'tick': self.frames_ticked}))

    def on_user_event(self, event) -> None:
        """Handle the posted event so the engine does not report it as unhandled."""


def record_counting_scene(*, tmp_path: Path, frames: int,
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
`CameraFreeScene` already overrides `setup` or `dt_tick`, call `super()` as shown. Check which
handler the engine uses for a `USEREVENT + n` type and name `PostingCountingScene`'s handler to
match — the suite runs with `no_unhandled_events`.)

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement** `PlaybackSources`, `PlaybackSession`, the registry push/pop,
  `ReplaySources.for_playback`, `SceneManager._enter_playback`/`_exit_playback`/
  `playback_session`/`last_playback_result`, the end check and error containment in `_run_frame`,
  and `start_playback` plus its path wrapper (used by Tasks 3, 4 and 6).

- [ ] **Step 4: Run** `tests/replay`, `tests/world`, golden, full suite.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/replay/playback.py glitchygames/sources.py glitchygames/scenes/scene.py glitchygames/replay/driver.py tests/replay/__init__.py tests/replay/playback_fixtures.py tests/replay/test_playback_scope.py
git commit -m "Add the playback scope: rebuilt scenes play recordings on scoped sources"
```

---

### Task 3: Demos

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`SceneManager.play_recording`)
- Modify: `tests/replay/playback_fixtures.py` (`tamper_sprite_in_frame`)
- Test: `tests/replay/test_playback_scope.py`

**Interfaces:**
- Produces: `SceneManager.play_recording(self, *, path: Path, then: Scene) -> None` (master and
  spec signature). It starts a demo scope (`start_playback_from_recording(..., exit_on_input=True,
  kind='demo')`); an unusable recording (unreadable, a different game, no `scene_start`) is logged
  at WARNING with the word "demo" and the reason, and nothing starts; a divergence ends the demo
  early and is logged at WARNING ("demo diverged: <describe()>"). Callers that need to know check
  `playback_session`.

- [ ] **Step 1: Write the failing tests**

```python
def test_play_recording_runs_a_demo_and_returns(tmp_path):
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=5)
    with running_scene(CountingScene) as manager:
        title_scene = manager.active_scene
        manager.play_recording(path=recording_path, then=title_scene)
        assert manager.playback_session is not None
        step(manager, frames=7)
        assert manager.active_scene is title_scene
        assert manager.playback_session is None


def test_unusable_demo_is_logged_and_nothing_starts(tmp_path, caplog):
    broken = tmp_path / 'broken.jsonl.gz'
    broken.write_bytes(b'not a trace')
    with running_scene(CountingScene) as manager:
        manager.play_recording(path=broken, then=manager.active_scene)
        assert manager.playback_session is None
        assert 'demo' in caplog.text


def test_diverging_demo_ends_early(tmp_path, caplog):
    recording_path = record_counting_scene(tmp_path=tmp_path, frames=20)
    tamper_sprite_in_frame(recording_path=recording_path, frame_number=4)
    with running_scene(CountingScene) as manager:
        title_scene = manager.active_scene
        manager.play_recording(path=recording_path, then=title_scene)
        step(manager, frames=6)
        assert manager.active_scene is title_scene
        assert 'demo diverged' in caplog.text
```

(Import `tamper_sprite_in_frame` from `tests.replay.playback_fixtures`.) In
`tests/replay/playback_fixtures.py`:

```python
def tamper_sprite_in_frame(*, recording_path: Path, frame_number: int) -> None:
    """Move the counting scene's marker 1 px down from `frame_number` on."""
    from glitchygames.tracing import read_trace_result, write_trace

    trace = read_trace_result(path=recording_path).trace
    for frame in trace['frames'][frame_number:]:
        if frame['sprites']:
            frame['sprites'][0]['rect'][1] += 1
    write_trace(trace=trace, path=recording_path)
```

- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Implement** `play_recording` on top of `start_playback_from_recording`.
- [ ] **Step 4: Run** `tests/replay` and the full suite.
- [ ] **Step 5: Commit**

```bash
git add glitchygames/scenes/scene.py tests/replay/test_playback_scope.py tests/replay/playback_fixtures.py
git commit -m "Add SceneManager.play_recording for attract-mode demos"
```

---

### Task 4: A bundled PaddleSlap demo and its replay test

**Files:**
- Create: `glitchygames/examples/paddleslap_demos/rally.jsonl.gz` (a bundled demo, < 100 KB,
  recorded with Part 2's `scripts/record_scripted_session.py`; the folder holds only data)
- Modify: `glitchygames/examples/paddleslap.py` (after `TITLE_IDLE_SECONDS` of no input on its
  title/serve screen, play the bundled demo with `play_recording`, returning to the title)
- Modify: `pyproject.toml` package-data only if wheels must include `*.jsonl.gz` (check how
  `paddleslap`'s sprites are shipped today: if `[tool.setuptools.package-data]` or the build
  backend's include rules already cover non-Python files by pattern, add the pattern the same way;
  this is packaging, not lint/type config — but if it touches a tool section, stop and ask)
- Modify: `glitchygames/testing/replays.py` (`bundled_demo_paths()`; the subprocess replay check
  factored into `replay_recording_headless(...)`, which the plugin's items also use)
- Create: `tests/replays/test_bundled_demos.py` (one test per bundled demo; `tests/` is where the
  suite collects, so demos inside the package are reached through this module)
- Test: `tests/replays/test_bundled_demos.py`, `tests/examples/` (PaddleSlap's test file)

**Interfaces:**
- Consumes: `play_recording` (Task 3), `scripts/record_scripted_session.py` and the replay plugin
  (Part 2 Task 5).
- Produces: `PADDLESLAP_DEMO_PATH: Path` and `TITLE_IDLE_SECONDS: float` in `paddleslap.py`; in
  `glitchygames/testing/replays.py`: `BUNDLED_DEMO_DIRECTORY_SUFFIX = '_demos'`,
  `bundled_demo_paths() -> list[tuple[str, Path]]` (console script, demo path for every
  `glitchygames/examples/<game>_demos/*.jsonl.gz`, the console script being the one whose entry
  point lives in `glitchygames.examples.<game>`), and
  `replay_recording_headless(*, console_script: str, path: Path) -> subprocess.CompletedProcess[str]`.

Rules (spec 5.3): a bundled demo is an ordinary recording shipped in the game's package. Every
bundled demo gets a replay test, so a code change that makes it diverge fails CI before it ships;
`tests/replays/test_bundled_demos.py` parametrizes over `bundled_demo_paths()`, so any future demo
is covered without editing the test. Record the demo once and
commit it (test and package data, not a scratch file):

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python scripts/record_scripted_session.py \
    --game paddleslap --frames 900 \
    --output glitchygames/examples/paddleslap_demos/rally.jsonl.gz
ls -l glitchygames/examples/paddleslap_demos/rally.jsonl.gz   # must be < 100 KB
```


- [ ] **Step 1: Write the failing tests**

`tests/replays/test_bundled_demos.py`:

```python
"""Every demo bundled in a game's package replays without divergence (spec 5.3)."""

import pytest

from glitchygames.testing.replays import bundled_demo_paths, replay_recording_headless

BUNDLED_DEMOS = bundled_demo_paths()


def test_paddleslap_ships_a_demo():
    assert any(console_script == 'paddleslap' for console_script, _path in BUNDLED_DEMOS)


@pytest.mark.parametrize(('console_script', 'demo_path'), BUNDLED_DEMOS,
                         ids=[path.name for _script, path in BUNDLED_DEMOS])
def test_bundled_demo_replays_without_divergence(console_script, demo_path):
    completed = replay_recording_headless(console_script=console_script, path=demo_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
```

In PaddleSlap's test file (`grep -rln "paddleslap" tests/examples`):

```python
def test_idle_title_plays_the_bundled_demo(mocker):
    from glitchygames.examples import paddleslap

    scene = make_paddleslap_scene(mocker)          # the file's existing scene factory
    play_recording = mocker.patch.object(scene.scene_manager, 'play_recording')
    scene._idle_seconds = paddleslap.TITLE_IDLE_SECONDS   # read the real attribute name
    scene.dt_tick(0.0)
    play_recording.assert_called_once_with(path=paddleslap.PADDLESLAP_DEMO_PATH, then=scene)


def test_bundled_demo_exists_and_is_small():
    from glitchygames.examples.paddleslap import PADDLESLAP_DEMO_PATH

    assert PADDLESLAP_DEMO_PATH.is_file()
    assert PADDLESLAP_DEMO_PATH.stat().st_size < 100_000
```

(Implement the idle timer with `self.game_time` (Part 1 Task 4): idle seconds since the last
input event; read PaddleSlap's title/serve flow first and pick the state where attract mode makes
sense — if PaddleSlap has no title screen, use the moment before the first serve, and say so.)

- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Record the demo, implement the idle trigger, `bundled_demo_paths` and
  `replay_recording_headless` (move the plugin item's subprocess code into it).**
- [ ] **Step 4: Run** `tests/replay`, `tests/examples`, the full suite (the bundled demo's replay
  item must pass), the golden test (PaddleSlap's golden script must never sit idle long enough to
  trigger the demo — if it does, the golden differs: raise `TITLE_IDLE_SECONDS` above the script's
  longest idle stretch instead of adding an expected difference, and say so).
- [ ] **Step 5: Lint, type-check, commit**

```bash
git add glitchygames/examples/paddleslap_demos/rally.jsonl.gz glitchygames/examples/paddleslap.py glitchygames/testing/replays.py tests/replays/test_bundled_demos.py tests/examples/<PaddleSlap's test file, by name>
git commit -m "Bundle a PaddleSlap attract-mode demo, replay-tested like every bundled demo"
```

---

### Task 5: Instant-replay journal

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`Scene.INSTANT_REPLAY_SECONDS`,
  `Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`; the manager keeps a journal for the active
  scene when it opts in)
- Modify: `glitchygames/replay/playback.py` (`InstantReplayJournal`)
- Modify: `glitchygames/sources.py` (`FrameInputListener` Protocol; Protocol method
  `add_frame_input_listener` / `remove_frame_input_listener`), `glitchygames/live_sources.py`,
  `glitchygames/recording.py` and `glitchygames/replay/driver.py` (each hands its pumped batches,
  snapshot changes and frame time to the listeners, so the journal is fed live, while recording and
  in a replay of the session)
- Modify: `tests/world/test_frame_integration.py` (Task 1's tests drop `create=True`)
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
class FrameInputListener(Protocol):          # glitchygames/sources.py
    def on_frame_inputs(self, *, dt: float, event_batches: list[list[dict[str, Any]]],
                        input_changes: dict[str, Any]) -> None: ...
EngineSources.add_frame_input_listener(self, *, listener: FrameInputListener) -> None
EngineSources.remove_frame_input_listener(self, *, listener: FrameInputListener) -> None
JOURNAL_BYTES_PER_MINUTE_LIMIT = 400_000     # one sprite at 60 FPS; the memory test's bound
```

Rules: when a scene with `INSTANT_REPLAY_SECONDS` set becomes active (`_setup_new_scene`), the
manager starts a journal from `active_scene_start` (Task 1). After each frame of that scene, it
adds `{'frame': n, 'scene': ..., 'sprites': <sampled>, 'dt': ..., 'event_batches': [...],
'input_changes': {...}, 'control_events': [...]}` — the same records `RecordingSources` writes
(reuse the recorder's record-building functions; refactor them out of `GameplayRecorder` into
module functions in `recording.py` if needed, so both use one implementation). A journal belongs
to its scene instance: it is kept while the scene is stashed behind the pause screen (resuming runs
`_setup_new_scene` again, which must not restart it — Task 1's first-setup rule) and dropped when
the scene is cleaned up (`cleanup()`: a switch away, a transition, game over). Scenes without the
attribute keep none. Memory: event batches and input changes only grow on input; sprites are
sampled every frame (the replay's `end_frame` compares every replayed frame), which dominates —
the memory test pins it below `JOURNAL_BYTES_PER_MINUTE_LIMIT` for a one-sprite scene, and the
report gives the figure for PaddleSlap's golden script (3600 frames); Task 7's docs step adds that
figure to the spec's section 5.4.

- [ ] **Step 1: Write the failing tests** (`tests/replay/test_instant_replay.py`)

```python
"""The instant-replay journal (glitchygames/replay/playback.py)."""

import pygame
from scripts.record_golden_traces import FRAME_SECONDS, press, release

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
        assert sources.recording.recorded_dt(frame_index=0) == FRAME_SECONDS
```

(`ReplaySources.recording.recorded_dt` comes from Part 2 Task 2, which runs before this part.)

Also in `tests/replay/test_instant_replay.py`:

```python
def test_journal_memory_per_minute_stays_bounded():
    import json

    from glitchygames.replay.playback import JOURNAL_BYTES_PER_MINUTE_LIMIT

    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=3600)     # one minute at 60 FPS (the harness's FRAME_SECONDS)
        journal_bytes = len(json.dumps(manager.instant_replay_journal.frames).encode('utf-8'))
    assert journal_bytes < JOURNAL_BYTES_PER_MINUTE_LIMIT


def test_pause_and_resume_keep_the_journal():
    with running_scene(InstantCountingScene) as manager:
        step(manager, frames=5)
        journal = manager.instant_replay_journal
        step(manager, press(pygame.K_ESCAPE), release(pygame.K_ESCAPE), frames=2)  # pause
        step(manager, press(pygame.K_ESCAPE), release(pygame.K_ESCAPE), frames=2)  # resume
        assert manager.instant_replay_journal is journal
```

(Use the pause keys and scene from `TestResumeAfterPause` in `tests/world/test_frame_integration.py`;
make `InstantCountingScene` pause the same way if `CountingScene` does not.)

- [ ] **Step 2–4:** fail; implement; run `tests/replay`, `tests/world`, full suite; measure the
  journal's size for 3600 frames of PaddleSlap's golden script and put the number in the report.

- [ ] **Step 5: Commit**

```bash
git add glitchygames/scenes/scene.py glitchygames/replay/playback.py glitchygames/sources.py glitchygames/live_sources.py glitchygames/recording.py glitchygames/replay/driver.py tests/world/test_frame_integration.py tests/replay/test_instant_replay.py
git commit -m "Keep an in-memory input journal for scenes that offer instant replay"
```

---

### Task 6: Instant replay

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
  `game_seconds - INSTANT_REPLAY_SECONDS` are fast-forwarded (no presenting, no pacing: the
  scope's `presents_frames()` is False and `paced_frame_seconds()` 0.0 — Part 2's doors and its
  unpaced path), the rest play visibly; at the end of the journal the scope ends and the live
  scene continues exactly where it was. It is started with Task 2's in-memory entry point:
  `start_playback(manager=self, header=header, frames=frames, then=<the live scene>,
  exit_on_input=False, kind='instant')` with `header, frames = journal.as_recording()`. Any key does
  not end an instant replay; the game decides (it can call the public `end_playback()` — add it;
  it calls `_exit_playback()`).

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

(`SceneManager.last_playback_result` is Task 2's.
The `presented.call_count` assertion counts `_present_frame` calls during the scope: the step loop
of the harness calls `run_frame`, which presents once per visible frame.)

- [ ] **Step 2–4:** fail; implement; run `tests/replay`, `tests/world`, golden, full suite.

- [ ] **Step 5: Commit**

```bash
git add glitchygames/scenes/scene.py glitchygames/replay/playback.py tests/replay/test_instant_replay.py
git commit -m "Add instant replay: fast-forward a rebuilt scene, show the last seconds, return"
```

---

### Task 7: Ghosts

**Files:**
- Create: `glitchygames/replay/ghosts.py`
- Test: `tests/replay/test_ghosts.py` (new)
- Modify: `tests/world/test_frame_integration.py`, `tests/world/test_gameplay_replay.py`
- Docs: CLAUDE.md (in-game playback: `play_recording`, `instant_replay`, `INSTANT_REPLAY_SECONDS`,
  `replay_arguments`, bundled demos, ghosts), the replay docs page, the spec's section 5.4 (the
  journal's measured memory per minute from Task 5, sprites included), `plans/future-work.md`
  (state snapshots for long instant replays and fast step-back; the cheat-device spec using the
  supervisor hook and
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


def sample(*, seconds: float, x: float) -> GhostSample:
    return GhostSample(game_seconds=seconds, world_x=x, world_y=10.0, appearance={},
                       visible=True)


def test_sample_at_picks_the_last_sample_not_after_the_time():
    track = GhostTrack(samples=(sample(seconds=0.0, x=0.0), sample(seconds=0.5, x=5.0), sample(seconds=1.0, x=10.0)))
    assert track.sample_at(game_seconds=0.75).world_x == 5.0
    assert track.sample_at(game_seconds=-1.0) is None


def test_track_json_round_trip():
    track = GhostTrack(samples=(sample(seconds=0.0, x=1.5), sample(seconds=0.016, x=2.5)))
    assert GhostTrack.from_json(json.loads(json.dumps(track.to_json()))) == track


def test_ghost_sprite_is_world_positioned_and_follows_game_time():
    track = GhostTrack(samples=(sample(seconds=0.0, x=0.0), sample(seconds=1.0, x=50.0)))
    ghost = GhostSprite(track=track, image_for=lambda _sample: pygame.Surface((4, 4)))
    ghost.scene = type('SceneStandIn', (), {'game_time': 1.25})()
    ghost.update()
    assert is_world_positioned(ghost)
    assert ghost.COORDINATE_SPACE is CoordinateSpace.WORLD
    assert (ghost.world_x, ghost.world_y) == (50.0, 10.0)
    assert ghost.hidden is False


def test_ghost_plays_at_the_right_speed_at_another_frame_rate():
    track = GhostTrack(samples=tuple(sample(seconds=index / 60, x=float(index))
                                     for index in range(61)))
    ghost = GhostSprite(track=track, image_for=lambda _sample: pygame.Surface((4, 4)))
    ghost.scene = type('SceneStandIn', (), {'game_time': 0.5})()   # 30 FPS playback time
    ghost.update()
    assert ghost.world_x == 30.0
```

In `tests/world/test_frame_integration.py` (it has `running_scene`, `step`, `WorldSprite` and
`FollowingScene`, whose player moves each frame — read it and use its player attribute):

```python
class TestGhostsInTheFrame:
    def test_recorder_samples_once_per_frame_and_stops_on_finish(self):
        from glitchygames.replay.ghosts import GhostRecorder

        with running_scene(FollowingScene) as manager:
            scene = manager.active_scene
            recorder = GhostRecorder(sprite=scene.player)
            step(manager, frames=4)
            track = recorder.finish()
            step(manager, frames=2)
        assert len(track.samples) == 4
        assert [sample.game_seconds for sample in track.samples] == pytest.approx(
            [FRAME_SECONDS * index for index in range(1, 5)])

    def test_ghost_is_culled_like_any_world_sprite(self):
        from glitchygames.replay.ghosts import GhostSample, GhostSprite, GhostTrack

        far_away = GhostTrack(samples=(GhostSample(game_seconds=0.0, world_x=100_000.0,
                                                   world_y=0.0, appearance={}, visible=True),))
        with running_scene(CameraFreeScene) as manager:
            ghost = GhostSprite(track=far_away, image_for=lambda _sample: pygame.Surface((4, 4)))
            ghost.scene = manager.active_scene
            manager.active_scene.all_sprites.add(ghost)
            step(manager, frames=1)
        assert ghost.visible == 0           # outside the screen plus CULL_MARGIN_PIXELS
        assert ghost.hidden is False        # culled by the engine, not hidden by the track
```

And in `tests/world/test_gameplay_replay.py` (Part 1's file, whose `record_session` /
`replay_session` it reuses):

```python
def test_a_session_with_a_ghost_replays_without_divergence(mocker, tmp_path):
    from glitchygames.replay.ghosts import GhostSample, GhostSprite, GhostTrack
    from glitchygames.state import SaveManager
    from glitchygames.state.sandbox import open_saves

    save_directory = tmp_path / 'saves'
    mocker.patch('glitchygames.state.manager.get_save_directory',
                 side_effect=lambda app_name: save_directory / app_name)
    track = GhostTrack(samples=tuple(
        GhostSample(game_seconds=index * 0.016, world_x=float(index), world_y=5.0,
                    appearance={}, visible=True) for index in range(30)))
    SaveManager(app_name='ghost-test').save('best_run', track.to_json())

    def add_ghost_from_saves() -> None:
        scene = SceneManager().active_scene
        saved = GhostTrack.from_json(open_saves(app_name='ghost-test').load('best_run'))
        ghost = GhostSprite(track=saved, image_for=lambda _sample: pygame.Surface((4, 4)))
        ghost.scene = scene
        scene.all_sprites.add(ghost)

    recording_path = record_session(tmp_path=tmp_path, mocker=mocker,
                                    action=add_ghost_from_saves, action_frame=1)
    SaveManager(app_name='ghost-test').delete('best_run')   # the replay reads the recording's copy
    engine = replay_session(recording_path=recording_path, mocker=mocker,
                            action=add_ghost_from_saves, action_frame=1)
    assert engine.replay_sources.result.divergence is None
```

(The saves door snapshots `ghost-test` when it is opened during the recording; the replay's
sandbox serves the track even though the real slot is gone.)

- [ ] **Step 2–4:** fail; implement; run `tests/replay`, `tests/world`, full suite.

- [ ] **Step 5: Docs, lint, type-check, mkdocs strict, commit**

```bash
git add glitchygames/replay/ghosts.py tests/replay/test_ghosts.py tests/world/test_frame_integration.py tests/world/test_gameplay_replay.py CLAUDE.md plans/future-work.md plans/2026-10-19-gameplay-replay.md docs/<the replay page from Part 1 Task 15>
git commit -m "Add ghosts: record a sprite's appearance and play it beside live play"
```
