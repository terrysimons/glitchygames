# Arcade Sub-plan 3: A Game Inside the Arcade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (execution is subagent-driven for every engine-context sub-plan: decision 4 of plans/2026-10-25-engine-context.md). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the full-Arcade spike's engine changes real: a game's own installed command runs,
unchanged, inside its own engine context, drawing into its own surface and reading its own event
queue, stepped by a host one frame at a time, its failures contained, so an outer game can show
several at once and each plays exactly as its headless replay does.

**Architecture:** The spike's design, as it was built (`arcade_spike_in_process.py`, below). A
context with a render target is an inner context: the engine draws there instead of opening the
window, never captions or icons the window, never changes SDL's drivers, and never presents. Its
posts go to a queue of its own, which its replay doors drain. In it `GameEngine.start()` is a
hosted start: it builds the game and hands the engine to the host instead of running the
blocking loop. `InnerGame` (a new engine module) is the host's handle on one such game.

**Tech Stack:** Python 3.14, pygame-ce, pydantic (frozen, `extra='forbid'`), pytest +
pytest-mock + xdist + pytest-benchmark, ruff, basedpyright, ty.

**Spec:** [2026-10-23-arcade-showcase.md](2026-10-23-arcade-showcase.md), Sub-plans item 3, and
its Decisions of 2026-11-12 (no game changes to wrap a game; build on the full-Arcade spike).
Evidence: the spike in the main checkout's `.superpowers/arcade-spike/`
(`arcade_spike_in_process.py`, built on `spike_two_games.py`; engine changes
`engine-changes-main.diff`; findings `engine-context-spike-findings.md`, 2026-10-27).

## Where this starts (2026-11-12)

The spike's engine changes are ported to main in this worktree, uncommitted (a three-way apply
of `engine-changes-main.diff`, without its two game-file edits; main's side kept where main
moved: the per-context state of #171 replaces its class-state workaround, main's channel
partition stays). Its check, adapted to the ten bundled demos (scratchpad copies of the two
spike scripts), passed for nine of ten tiles: each tile's digests equal its solo headless
replay, frame for frame, on every loop and after a live PaddleSlap session in between, and its
pixels equal the run without the live session. **Bitmappy fails** at frame 0: it sizes its film
strip from `pygame.display.get_surface()` (`film_strip_coordinator.py:348`), the Arcade's window
inside a tile. The owner left it failing (2026-11-12; `plans/future-work.md`).

## What else the spike did, and which sub-plan owns it

| The spike's | Owner |
| --- | --- |
| Audio route (`audio/route.py`): audible/silent per context, a channel block per context, one-shots stopped on a highlight move, the routing spy | Sub-plan 4 (sound), a separate piece in the engine; the two game-file edits it needed must become engine-side routing |
| A tile restarting in a fresh context when its recording ends (`--loop`, generations), Brave Adventurer's tile alternating Classic and Papyrus | Sub-plan 5 (`DemoPlayer`, looping) |
| Per-tile debug overlays (F3 all, Shift+F3 one, F4 panel, the setting kept across restarts, drawn on a copy) | Sub-plan 6 (master spec, Testing) |
| The outer game reading SDL's queue only through its own doors; tiles never pump | Sub-plan 6 (input); this plan's private queue keeps tiles off SDL's queue |
| The live game: hosted start in a context that owns the window, mouse mapping and letterbox scaling (`WindowToTarget`, fit or stretch, nearest or smooth), tiles paused, window state kept | Sub-plan 7 (launching) |
| Uneven stepping (`--steps`), pixel digests, the comparison with solo replays | This plan, Task 4 |
| Context-switch timing, frame-time statistics | `tests/benchmarks/` (sub-plan 1's context costs; Task 4's ten tiles per frame) |
| The class-state swap | Obsolete (#171) |

## Global Constraints

- **No changes must be required for a game to be wrapped** (the owner, 2026-11-12): no file
  under `src/games/`, `src/demos/` or `src/apps/` changes; the branch ends with
  `git diff --stat origin/main -- src/games src/demos src/apps` empty.
- **No pygame function is replaced** (the owner, 2026-11-12: "no need to monkey with the call
  tree"). The engine changes only its own code.
- Ordinary games do not change: every existing test, golden replay, golden trace and bundled
  demo passes unchanged in the default context. No golden or demo is re-recorded.
- Sound is Arcade sub-plan 4's, the live game and mouse mapping sub-plan 7's.
- New data classes: pydantic `BaseModel`, `frozen=True`, `extra='forbid'`; a slot value that
  holds a Surface or a list it mutates stays a plain class.
- Keyword arguments; full names; Google-style docstrings; no lint or type suppressions and no
  configuration edits; 100% coverage; real pygame and real files in tests, pytest-mock only for
  what cannot run.
- Every new `ContextSlot` gets an isolation check in `ISOLATION_CHECKS`
  (`tests/test_engine_context.py`).
- A root test that reads the workspace's members goes in its own file, listed in
  `REPOSITORY_TEST_FILES` (`tests/test_suite_collection.py`) with its reason.
- One branch, `arcade-3-inner-game`, one PR; commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; nothing is committed or pushed
  without the owner's say.

## Decisions (the owner reviews them with the plan)

1. **An inner context is one with a render target** (`is_inner_context()`, the spike's rule).
2. **A failure belongs to the `InnerGame`**: `InnerGame.outcome` carries it (state `FAILED`,
   the error's text); the context stays a bag of slots.
3. **An inner engine writes nothing to stdout**: its replay report goes to `InnerGame.outcome`
   and the log (INFO).
4. **Containment catches `Exception` and `SystemExit`** (a game's `sys.exit()`, `exit_with`,
   argparse); `KeyboardInterrupt` and `GeneratorExit` propagate.
5. **Only recordings run inner** here: `InnerGame` refuses live play, every tool flag,
   `--record-trace`, `--rebaseline`, `--audit` and `--compare-trace` before anything is built
   (`InnerGameRefusedError`). The live game is sub-plan 7's.
6. **Unpresented frames are made opaque** (`make_opaque` on the render target after each
   frame; BUGS.md #142's rule, the spike's `SPIKE_NO_OPAQUE_TILES` finding).
7. **A game's arguments arrive through `sys.argv`**, swapped by `InnerGame` only while the
   command's entry point builds the game (the spike's swap; Brave Adventurer's launcher
   rewrites `sys.argv` itself). Frame steps never read it.

## Review Focus

1. **A recorded quit** (every golden ends with one): it ends only that `InnerGame` (outcome
   `ENDED`, matched), never the outer run; no QUIT reaches SDL's queue. Test in Task 3.
2. **A replay that diverges inside a tile**: outcome `ENDED` with the divergence report, not
   `FAILED`; stdout empty. Test in Task 3.
3. **A game that raises or exits while building or stepping**: that game `FAILED`, the others
   go on, the default context is current afterwards. Test in Task 3.
4. **The text-input demo's key repeat** (`set_repeat(350)` in its setup): the check never looked
   at the Arcade's own repeat. Measure it in Task 4 and log a bug if a tile changes it.
5. **A tile on a display format with per-pixel alpha** (cocoa): no alpha-0 byte in the render
   target after a frame. Test in Task 1.

---

### Task 1: The render target and the hosted start, made real

**Files:**
- Modify: `src/glitchygames/render_target.py` (drop `WindowToTarget`, `set_window_mapping`,
  `window_point_to_target`, `map_window_events` and `mapped_mouse_events`: sub-plan 7's;
  drop every `SPIKE` marker), `src/glitchygames/live_sources.py` (back to main: no mapping;
  `presents_frames` stays `not is_inner_context()`), `game_engine.py` and `scenes/scene.py`
  and `sprites/sprite.py` (the ported sites, markers replaced by real comments),
  `src/glitchygames/audio/route.py`, `audio/live.py`, `audio/recipes.py`, `game_objects/ball.py`
  (the audio route removed from this branch: sub-plan 4's)
- Test: `tests/test_render_target.py`, `tests/engine/test_inner_engine.py`,
  `tests/test_engine_context.py` (`ISOLATION_CHECKS['render target']`)

**Interfaces:**
- Produces: `RENDER_TARGET_SLOT`; `set_render_target(*, surface: pygame.Surface | None)`;
  `render_target() -> pygame.Surface | None`; `is_inner_context() -> bool`;
  `display_surface() -> pygame.Surface | None`; `request_hosted_start()`,
  `hosted_start_requested() -> bool`, `note_started_engine(*, engine: GameEngine)`,
  `take_started_engine() -> GameEngine | None` (typed through `TYPE_CHECKING`).

- [x] **Step 1: Write the failing tests**: an inner context reads its own target and the
  default context the window (`display_surface`); a sprite made inner measures against the
  target; building a replay engine inner leaves the window's size and caption, SDL's driver
  variables and the icon unchanged; `start()` inner builds the game, returns, and
  `take_started_engine()` gives that engine once; the default context's `start()` is unchanged;
  an inner frame on a per-pixel-alpha target leaves no alpha below 255 (Review Focus 5).
- [x] **Step 2: Run them; expected FAIL where the port lacks the behaviour** (the opaque frame,
  the typed handoff)
- [x] **Step 3: Implement**; `_show_frame` runs `make_opaque` on an unpresented inner frame.
- [ ] **Step 4: Run `tests/`; expected PASS**
- [x] **Step 5: Commit** (`Render target: an inner context draws on its own surface; the hosted start`)

### Task 2: The private event queue, made real

**Files:**
- Modify: `src/glitchygames/recording.py` (`PrivateEventQueue`, `PRIVATE_EVENT_QUEUE_SLOT`,
  `private_event_queue`, `_post_tracked`), `src/glitchygames/replay/driver.py`
  (`_drain_real_queue`)
- Test: `tests/test_recording.py`, the file holding `_drain_real_queue`'s tests,
  `tests/test_engine_context.py` (`ISOLATION_CHECKS['private event queue']`)

**Interfaces:**
- Produces: the queue enabled for every inner context by `InnerGame` (Task 3); while enabled,
  `post_event`/`post_input_event` append there and the replay doors drain it, never SDL's.

- [ ] **Step 1: Write the tests**: a post inner never reaches SDL's queue; an inner replay's
  pump leaves an owner's event in SDL's queue; the inner replay serves its own posts as
  internal (the spike's frame-30 theft).
- [ ] **Step 2: Run them**; the port may already pass some; any that fail are fixed in Step 3
- [ ] **Step 3: Implement what fails; replace the markers with real comments**
- [ ] **Step 4: Run `tests/`; expected PASS**
- [ ] **Step 5: Commit** (`Events: an inner context posts to and drains a queue of its own`)

### Task 3: `InnerGame`

**Files:**
- Create: `src/glitchygames/inner_game.py`
- Test: `tests/engine/test_inner_game.py`

**Interfaces:**
- Consumes: Tasks 1 and 2; the console-script lookup (the spike's `command_main`:
  `importlib.metadata.entry_points(group='console_scripts', name=...)`; `replay/tools/children.py`
  has the engine's own).
- Produces:
  - `InnerGameState(StrEnum)`: `RUNNING`, `ENDED`, `FAILED`.
  - `InnerGameOutcome(BaseModel, frozen, extra='forbid')`: `state`, `frames_run: int`,
    `report: str | None`, `error: str | None`.
  - `InnerGameRefusedError(ValueError)`.
  - `InnerGame.replay(*, command: str, path: Path, name: str, size: tuple[int, int],
    arguments: Sequence[str] = ()) -> InnerGame`: refuses decision 5's arguments; makes
    `EngineContext(name=name)`; in it sets a render target of `size` in the display's format,
    enables the private queue, swaps `sys.argv` to `[command, '--replay-trace', str(path),
    '--headless', *arguments]` for the entry point's call (decision 7), calls the command's
    entry point with nothing, takes the started engine, calls `scene_manager.begin_frames()`.
  - `step() -> bool`: one `run_frame_step(frame_start_seconds=..., paced=False)` in its
    context; False once ended or failed.
  - `surface`, `outcome`, `context` properties.
  - `finish() -> InnerGameOutcome`: the spike's `LiveGame.finish` (`end_frames`,
    `stop_trace_recording`, the timer closed) plus the replay's result read into the outcome;
    never `pygame.quit()`, signal or environment restoring, `exit_with`. Idempotent; `step()`
    calls it at the end.
  - Containment (decision 4) around `replay`, `step` and `finish`.

- [ ] **Step 1: Write the failing tests** (a stand-in game installed as a command, the
  unseen-game test's pattern): plays to `ENDED` and `Replay matched`; Review Focus 1, 2 and 3;
  each refused argument set.
- [ ] **Step 2: Run them; expected FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run `tests/engine/`; expected PASS**
- [ ] **Step 5: Commit** (`Inner game: a game's own command replayed inside its own engine context`)

### Task 4: The proof, the benchmark and the documents

**Files:**
- Create: `tests/test_every_recording_replays_inside_an_inner_game.py` (in
  `REPOSITORY_TEST_FILES`)
- Modify: `tests/benchmarks/test_engine_context_benchmarks.py`, `tests/test_suite_collection.py`,
  `CLAUDE.md` (Engine Context), `docs/architecture/engine_context.md`,
  `plans/2026-10-25-engine-context.md` (the rows and sub-plans this covers),
  `plans/2026-10-23-arcade-showcase.md` (item 3 done), `plans/future-work.md`

- [ ] **Step 1: Write the proof test**, parametrized over every golden and bundled demo
  (`tests/workspace_goldens.every_golden_and_bundled_demo`), each paired with the next: the
  reference is a child headless replay with `--replay-digest`; both replayed as `InnerGame`s,
  stepped unevenly interleaved, each with its own digest. Each digest equals its reference;
  each tile's per-frame pixel hash interleaved equals the same recording alone. Bitmappy's
  `drawing` demo is `pytest.mark.xfail(strict=True, reason=...)` naming the future-work entry.
  Record the Arcade's `pygame.key.get_repeat()` before and after (Review Focus 4).
- [ ] **Step 2: Run it**; expected PASS (Bitmappy XFAIL). A new failure is a real collision:
  root-cause it, never relax the comparison.
- [ ] **Step 3: Add `test_ten_inner_games_per_outer_frame`** (one call steps ten stand-in
  `InnerGame`s once); run with `--benchmark-only -n 0`.
- [ ] **Step 4: Update the documents**, then `uv run pytest`, `nox -s lint`,
  `nox -s static-analysis`; expected green.
- [ ] **Step 5: Commit** (`Inner game: every golden and bundled demo replays inside an inner context as it does alone`)

The branch ends with the whole suite green, `nox -s compare-drivers -- --drivers native
--fail-on-difference` clean, a PR, CI green and the owner's merge.
