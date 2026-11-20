# Arcade Sub-plan 5: One Playback Core, Then `DemoPlayer` — Implementation Plan

Status: PLAN, for the owner's review (written 2026-11-20 against main at 4e6c7144; nothing built).
Decided by the owner on 2026-11-20: the viewer's own-context move is a later sub-plan (question 1)
and the playback scope stays in its engine (question 2). One question is open (question 3, recast
after a root-cause triage of Bitmappy's tile); the rest are rulings the owner may overturn.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (execution is subagent-driven for every Arcade sub-plan: decision 4 of plans/2026-10-25-engine-context.md). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One place decides when a recorded game's frames run (owed time, a real-time budget,
slow motion, fast-forward), and `DemoPlayer` is a thin owner of one inner game on top of it, so
an Arcade can hold ten players, give each the frames real time calls for, loop them, and reach a
poster frame quickly, while the watched replay's viewer runs on the same pacing code and every
existing replay, demo and instant-replay test passes unchanged.

**Architecture:** An audit (below) shows the engine does not have four inner-game runners to
merge: today the watched replay is one engine whose doors are the viewer, the playback scope is
a mode of a live engine, and only `InnerGame` (Arcade sub-plan 3) runs a recording in a context
of its own. So the core is built from the pieces that really overlap: the viewer's pacing
accumulator becomes a pure `RecordedFramePacer` (plus a shared `TickBudget`), `InnerGame` gains
what a host needs to pace it (the next frame's recorded duration, the frame count, a budgeted
fast-forward), and `DemoPlayer` (engine module, no game imports) joins them: tick, surface,
sound, outcome, loop, fast-forward, poster frame. The viewer is moved onto the pacer in this
sub-plan; moving the viewer's inner game into a context of its own (engine context sub-plan 8)
is a larger change the Arcade does not need, so it is a later sub-plan (decided by the owner,
2026-11-20).

**Tech Stack:** Python 3.14 (runs on 3.15), pygame-ce, pydantic (frozen, `extra='forbid'`),
pytest + pytest-mock + xdist + pytest-benchmark, ruff, basedpyright, ty.

**Spec:** [2026-10-23-arcade-showcase.md](2026-10-23-arcade-showcase.md), Sub-plans item 5 and
Architecture section 2 (and its Decisions of 2026-11-12: no game changes; build on the
full-Arcade spike), together with engine context sub-plan 8
([2026-10-25-engine-context.md](2026-10-25-engine-context.md), "The replay viewer: the first
existing user"). Builds on [2026-11-12-arcade-3-inner-game.md](2026-11-12-arcade-3-inner-game.md)
(`InnerGame`, PR #185) and [2026-11-13-arcade-4-sound.md](2026-11-13-arcade-4-sound.md) (the
audible flag and the channels, PR #207), both merged. Evidence: the full-Arcade spike
(`.superpowers/arcade-spike/arcade_spike_in_process.py` on `spike_two_games.py`, in the main
checkout) and the measurements below.

## Where this starts: the audit (2026-11-20)

What the spec calls "four ways to play a recording" and one inner-game runner to extract:

| Path | What it is today | Frames run by | Overlap with the Arcade's need |
| --- | --- | --- | --- |
| Headless replay | The game's own engine, `ReplaySources` as its doors, `--headless` (`src/glitchygames/replay/driver.py`: `ReplaySources` at 1311, `paced_frame_seconds` 1670 returns 0.0, `hold_frame` 1681 returns False when headless) | `SceneManager.start`'s loop | Nothing to share but the doors; `InnerGame` already runs this in a context |
| Watched replay | The same single engine. The "viewer" is not an outer game: `ReplaySources.viewer` (driver.py:1426) is a `ReplayViewer` the doors call from `hold_frame` (driver.py:1681-1726) to decide, per outer tick, whether the next inner frame runs. `presents_frames` is False (driver.py:1415); the doors draw the status bar (`draw_overlay`, 1728) | `SceneManager.run_frame_step`, held by `hold_frame` | **The pacing accumulator** (`viewer.py`: `should_run_inner_frame` 348, `_owed_limit_seconds` 417, `_defers_to_the_next_tick` 448, `INNER_FRAME_BUDGET_SECONDS` 92, `MAX_OWED_INNER_FRAMES` 89). Its rules are exactly what a tile needs: owed time paid in recorded frame durations, a real-time budget per outer tick, never skipping a frame, an owed limit instead of a burst, "behind" reported |
| Rebuild (step back) | `Rebuild(FrameSilencer)` (`rebuild.py:296`) inside the watched `ReplaySources` (driver.py:1435-1438, 1702-1715, 1898-1905): frames 0..N-1 run unpresented, unpaced, silenced, with a progress hold every `REBUILD_PROGRESS_INTERVAL_SECONDS` (0.1 s of real time, `Rebuild.progress_is_due` 321). It exists because "the engine cannot be rebuilt in-process" (`rebuild.py:3`): step back restarts the process | The same loop, held every 0.1 s | A time-sliced fast-forward: run frames until a real-time slice is spent, then yield. That is `DemoPlayer.fast_forward` with a different yield |
| Playback scope | A mode of a live game's engine (`replay/playback.py`: `PlaybackSources` 414, rules 1-8 of its docstring): the live scene is stashed, a recording rebuilt into the same `SceneManager`, the live game's devices set aside, then the live scene restored. Demos (`play_recording`) and instant replay | The live loop, at the game's pace | Fast-forward by frame count (`fast_forward_frame_count` 1285; instant replay's whole-journal cap is `MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`, `scenes/scene.py:3158`, checked once when requested, not a time slice) and `FrameSilencer` (`silence.py:220`) |
| `InnerGame` (sub-plan 3) | A recording replayed headless in its own context, one `step()` a frame, unpaced (`inner_game.py`: `replay` 500, `step` 600, `finish` 626) | The host | The runner. It lacks pacing, the next frame's recorded duration, the frame count and fast-forward |

Four findings follow, and they shape the plan:

1. **There is no second runner to merge.** `InnerGame` is the only one that is a host-driven
   runner. The watched replay and the scope share an engine with the game; the pieces they and
   a tile share are the pacing accumulator, the time slice and the silencer.
2. **The viewer's pacing is the part worth reusing, and it is almost pure.** It touches
   `ReplayControls` only for `speed`, `awaiting_start`, `paused` and `take_step`
   (`viewer.py:361-376`) and the 60 Hz constant `CONTROL_TICK_SECONDS`
   (`replay/controls.py:85`). Its comment on rule 2 is also the tile's problem: a tile shows
   only the latest frame per outer tick, so a long frame and the short catch-up frame after it
   must not share a tick.
3. **The fast-forward is count-driven or whole-run today, never time-sliced for a host that
   must stay responsive** (scope: count in the live loop, rebuild: frames then a 0.1 s hold,
   instant replay: a cap at request). The Arcade needs a resumable slice per Arcade frame.
4. **The sound problem the replay fast-forwards solve with `FrameSilencer` is already solved
   for a context** (sub-plan 4): a silent inner game reaches no channel, so an inner
   fast-forward needs no silencer. In an inner context the silencer is only a guard
   (`silence.py` module docstring, last two paragraphs).

### Measured (2026-11-20, Apple M4 Max, dummy drivers, this worktree)

A scratch script (not kept) built each bundled demo as an `InnerGame` twice and stepped it to
its end, unpaced:

| Demo | Frames | Mean frame | Frames/s unpaced | Build, 2nd build |
| --- | --- | --- | --- | --- |
| PaddleSlap rally | 450 | 0.11 ms | about 8,500 | 13 ms, 10 ms |
| Mr. Muncher chase | 1,950 | 0.85 ms | about 1,190 | 280 ms, 29 ms |
| Brave Adventurer classic / papyrus | 400 | 1.85 ms | about 630 | 85 ms, 38 ms / 47 ms, 40 ms |
| Clockwork Keep climb | 330 | 0.48 ms | about 1,990 | 31 ms, 9 ms |
| Drawing Fire battle | 1,600 | 0.43 ms | about 2,320 | 23 ms, 16 ms |
| dt / joystick / text-input demos | 600 | 0.07 / 0.16 / 0.04 ms | 6,000 to 24,000 | 7 to 14 ms |
| Bitmappy drawing | 1 (diverges at frame 0, the known strict xfail) | n/a | n/a | 73 to 180 ms in two runs, 3.1 s in a third (not explained; Task 6 measures it properly) |

So the nine working tiles cost about 4 ms of frame work per Arcade frame here (against the
11 ms `INNER_FRAME_BUDGET_SECONDS`); on a Raspberry Pi the budget will bind, which is what slow
motion is for. A poster frame at the 90% mark of the slowest demo (Mr. Muncher, 1,755 frames)
costs about 1.5 s of fast-forward, and all ten posters together about 2 s on average: it must
be sliced across Arcade frames, as the spec says. A loop's restart is a build of 9 to 40 ms
(a frame or three at 60 Hz): it must be charged to the frame budget and spread, never done for
all tiles in one frame.

## What the spike did, and which part is this sub-plan's

| The spike's | Here |
| --- | --- |
| `Player.tick(steps=N)` (`spike_two_games.py:248`): a fixed step count per tick, no real time | Replaced by the pacer: frames owed by elapsed time, within a budget |
| Looping: `Wrapper.tick` builds a new `Player` in a new context when one is done (`spike_two_games.py:491-519`) | Kept: `DemoPlayer` finishes and rebuilds; the overlay-preference restore stays the Arcade's (sub-plan 6) through a hook |
| `make_opaque` after each frame in the player | Already the engine's (`_show_frame`, `scenes/scene.py:1589`) in an inner context; the player adds nothing |
| Per-player pixel digests (`--pixel-digests`) | The proof test's pixel hashes (`tests/test_every_recording_replays_inside_an_inner_game.py`) |
| A `LiveGame` for launching | Sub-plan 7 |
| The grid, highlight, top frame | Sub-plan 6 |

The spike has no budget, no slow motion, no fast-forward and no poster frame; those are new here.

## Global Constraints

- **No changes must be required for a game to be wrapped**: no file under `src/games/`,
  `src/demos/` or `src/apps/` changes (`git diff --stat` against the base branch empty there).
  `DemoPlayer` takes a console script and a recording, as `InnerGame.replay` does, and inherits
  its refusals.
- **Ordinary games do not change.** Every golden replay, golden trace, bundled demo and
  existing viewer, rebuild, playback-scope and instant-replay test passes unchanged: the
  guard of Task 1 and the end of every task. A watched replay's schedule is identical before
  and after the pacer moves (`tests/test_replay_schedule.py`, `scripts/replay_schedule.py`).
- **The engine never imports a member**; `DemoPlayer` is an engine module and imports no game.
- **Clocks** (CLAUDE.md): owed time comes from the elapsed time the caller serves (the Arcade's
  frame time, which a recorded Arcade session replays exactly), never from a clock read inside
  the player; the real-time budget reads `clock.measured_seconds` (as the viewer does today:
  it decides when frames run, never what they do) through an injectable parameter; tests pass
  a fake. The module is imported as `from glitchygames import clock`.
- **Randomness**: only named streams. The poster frame is a pure function of a stream the
  caller passes (the Arcade's `random_stream('arcade-posters')`, sub-plan 6).
- **Engine context**: any new per-game state is a `ContextSlot` with an `ISOLATION_CHECKS`
  entry. Nothing new here should need one: the pacer and the player belong to the host.
- New data classes: pydantic `BaseModel`, `frozen=True`, `extra='forbid'`; the pacer's mutable
  state is a plain class (hot path, measured: ten players per Arcade frame).
- Keyword arguments; full names; Google docstrings; no lint or type suppressions; no
  configuration edits; `assert` only in tests (the two in `inner_game.py` that this sub-plan
  touches are made raises, Task 2); 100% coverage; real pygame and real files in tests;
  pytest-mock only for what cannot run (the clock, injected failures).
- Benchmarks (master plan): the player's per-frame cost against `INNER_FRAME_BUDGET_SECONDS`
  goes in `tests/benchmarks/`, never a one-off script.
- Branch `arcade-5-playback-core` from main (all of 1-4 are merged), one PR, commits local until
  the owner says; commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  The viewer's own-context half is a later sub-plan (decided 2026-11-20).

## Decisions (the owner reviews them with the plan)

1. **The core is pieces, not a fifth runner.** `InnerGame` stays the one runner of a recording
   in a context (the audit's finding 1). Shared and new: `RecordedFramePacer` (the viewer's
   accumulator, pure), `TickBudget` (a real-time allowance), a time-sliced fast-forward on
   `InnerGame`, and one public "recorded duration of the next frame" on `ReplaySources`.
2. **`RecordedFramePacer` and `TickBudget` live in `src/glitchygames/replay/pacer.py`** (new).
   The pacer owns what `ReplayViewer` owns today that is not a key or a status line: the
   accumulator, the phase offset, the owed limit (`MAX_OWED_INNER_FRAMES`), rule 2's
   one-frame-a-tick-unless-behind, the "behind" window and `effective_speed`. It is told the
   speed, the nominal tick period and whether it is running as arguments, instead of reading
   `ReplayControls` and the 60 Hz constant, so the viewer passes `controls.speed` and
   `CONTROL_TICK_SECONDS` and its behaviour does not change by a frame (Task 1's guard); the
   Arcade passes 1.0 and its own frame period (a browser's 120 Hz tick is then not mistaken
   for a 60 Hz one). `ReplayViewer` keeps the cadence, the keys, the snapping of tick times and
   the start screen, and delegates the owing to the pacer. A source-guard test makes the pacer
   the only place that computes owed frames (no second accumulator can appear).
3. **`TickBudget`: one allowance read from an injectable clock, shared by every consumer.**
   `INNER_FRAME_BUDGET_SECONDS` (`viewer.py:92`, 11 ms) and `Rebuild`'s progress interval
   (0.1 s) and the player's fast-forward slice are one idea: "this much real time, then yield".
   A `TickBudget` is started with its length, answers `is_spent` and `remaining_seconds`, and
   is passed to several players in turn so what one leaves the next gets. This deviates from the
   spec's `tick(real_seconds, budget_seconds)` (a float per player), which could not pass the
   leftover on (the spec's step 4: share what is left among the other eight).
4. **`DemoPlayer` is an engine module, `src/glitchygames/demo_player.py`, not in the Arcade
   app.** It needs only `InnerGame`, the pacer and a recording, never a game; any outer host
   (the Arcade, a future attract screen, the browser bundle) can use it, and the engine's
   tests can test it with stand-in games without the Arcade existing. The Arcade app imports it.
5. **`DemoPlayer.tick(*, elapsed_seconds, budget)`** pays the pacer the caller's elapsed time,
   runs the frames the pacer allows within `budget`, and returns how many ran. It never reads a
   wall clock for owed time, so it is deterministic in a recorded Arcade session and safe in
   the browser (synchronous: no switch across an `await`, engine context sub-plan 3's rule).
   Frames are never skipped: a player that cannot keep up plays in slow motion, and
   `effective_speed` / `is_behind` say so (the Arcade may show it in the debug overlay). Time
   is dropped only past the owed limit (about half a second of frames), so a stalled Arcade (a
   launched game in front, sub-plan 7) does not make tiles burst on return.
6. **A demo's end loops it:** `DemoPlayer` finishes its `InnerGame` (which gives its channels
   back: rule 6 of `inner_game.py`, and the "host must finish every inner game it drops"
   follow-up in plans/future-work.md), builds a new one from the same command and recording in
   a new context, from frame 0 (not from the poster frame). A constructor hook,
   `on_new_game(inner_game)`, runs on each new game before its first frame, so the Arcade can
   restore a tile's debug-overlay setting (the master plan's Testing, from the spikes) without
   the player knowing about overlays. `generation` counts the builds.
7. **A restart's build is charged to the budget.** A build is one indivisible call of 9 to 40 ms
   warm (measured above), so the player builds when its turn comes and the budget is not
   already spent, and the build's cost is subtracted from the budget the other players share
   that tick: ten tiles looping at different times spread their hitches; no tile is skipped.
   Task 6 measures the real distribution (including Bitmappy's cold build and the odd 3 s
   reading) before the numbers here are trusted.
8. **Fast-forward is silent, sliced and resumable.** `fast_forward(*, to_frame, budget)` runs
   frames `[frames_run, to_frame)` of the current game until done or the budget is spent, and
   returns whether it reached `to_frame`; the next call continues. It is refused while the
   player is audible (the Arcade silences a player first; a switch to audible takes a heard
   set and would otherwise be raced by 1,000 frames of sound), and it never calls a
   silencer (finding 4). `to_frame` must be less than the recording's frame count (a
   `ValueError` otherwise). A divergence or a failure on the way ends the fast-forward with
   that outcome. Frame `to_frame` is then the next `tick` frame, and its pixels equal a headless
   replay's (the proof).
9. **Poster frames: `poster_frame(*, frame_count, stream)`** returns a frame drawn uniformly from
   the 10% to 90% span of the recording, from the stream the caller passes, so a title screen
   or an end screen is never the poster and the same seed gives the same frames. The span is
   a ruling (alternative: the whole recording; a demo's first frames are often a still
   scene, its last often a quit tail, so the whole span makes dull posters).
10. **Outcomes** map `InnerGameOutcome` (`inner_game.py:197`) to the spec's list in one enum,
    `DemoOutcome`: `PLAYING`; `COULD_NOT_START` (build failed, or `FAILED` with no frame run:
    a missing or unreadable recording, an older format, a refused argument); `CRASHED`
    (`FAILED` after at least one frame); `DIVERGED` (`ENDED` with `diverged` True, or a
    length divergence, which `ReplaySources.finish_run` makes `FAILED`: Task 4 tests both);
    and `LOOPED` as the transient state after a restart (the spec's "looped"; it reads as
    `PLAYING` from the next tick). The error text and the replay's report are kept for the
    Arcade's label. What a diverged demo does next is the recast question 3.
11. **Muted is the default and is the context's route.** A new `DemoPlayer` is silent (a new
    `InnerGame` is, rule 5). `audible` and `set_audible(*, audible)` delegate to the current
    `InnerGame`, and a looped player's new game gets the player's setting before its first
    frame, so a heard top frame stays heard across its demo's loop. Keeping one player heard
    is the Arcade's job (rule 7 of `inner_game.py`).
12. **The surface is the render target.** `DemoPlayer.surface` is the current `InnerGame`'s
    surface; after a loop it is a new surface object, so the Arcade reads it each frame and
    never holds it. It is never presented. The last frame stays readable after an end,
    divergence or crash (`InnerGame` keeps its surface), so a tile can freeze on it.
13. **The recording's size comes from its header**, as the proof test does
    (`recorded_screen_size`, driver.py:1107, through `TraceReader`): `DemoPlayer` opens the
    header once, at construction, and a recording with no screen size is `COULD_NOT_START`.
14. **Step back and instant replay do not move onto `InnerGame` in this sub-plan.** The spec's
    "rebuilt on it" for the playback scope and the rebuild does not survive the audit (Open
    questions 1 and 2). What they share is made shared: the time slice (decision 3), the frame
    count function and the silencer, with guard tests that no second copy exists.

## Decided by the owner (2026-11-20)

**1. The viewer's inner game moves into a context of its own (engine context sub-plan 8) in a
later sub-plan, not in this one (the owner, 2026-11-20).** The reasoning, in plain words:

Today, `uv run paddleslap --replay-trace run.jsonl.gz` starts one engine: PaddleSlap's own. The
"viewer" is not a second game; it is part of that engine's doors (`ReplaySources.viewer`,
driver.py:1426), which decide before each PaddleSlap frame whether it runs now or waits for the
next 60 Hz tick, and draw the status bar over it. Pressing `,` at frame 300 ends the process, and
a supervisor relaunches `paddleslap --replay-trace ... --replay-pause-at-frame 299` as a child,
which rebuilds 299 frames silently before pausing (`rebuild.py`, steps 1-4).

The alternative is the viewer as an outer game in the default context (window, keys, status bar,
bookmarks) that holds PaddleSlap as an `InnerGame` in its own context, the way the Arcade will
hold ten tiles. What it gains: step back becomes a new `InnerGame` plus `fast_forward(to_frame=299)`
in the same process, which deletes the supervisor, the handoff file and
`--replay-restart-handoff`, and makes `--compare-trace`'s OLD stream possible in-process
(plans/future-work.md); and the watched replay is then the first user of the Arcade's own design.
What it costs: a new outer viewer game around an `InnerGame` that today refuses to be watched
(rule 1 of `inner_game.py`), the known bug that a watched inner replay would drop real key
presses (plans/future-work.md), a restructure of how `GameEngine` starts a watched replay
(`game_engine.py:1520, 1647-1649, 3762`), and 45 viewer and 33 rebuild tests as the guard.
The Arcade (sub-plans 6 to 8) needs none of it, so it should not delay them. This sub-plan puts
the viewer on the shared pacer (Task 5, still in its own engine, no behaviour change); the
own-context move is planned afterwards, from what `DemoPlayer` and the pacer show it needs.

**2. The playback scope and instant replay stay in their engine and are not rebuilt on
`InnerGame` (the owner, 2026-11-20).** Example: PaddleSlap scores a goal at frame 1,200 and calls
`instant_replay`. The scope stashes the live scene, rebuilds the recorded scene into the same
`SceneManager` from the journal's `scene_start`, plays the last 5 s, then restores the live scene
exactly as it was, with the live game's devices, saves and pause screen untouched
(`playback.py` rules 2 and 4). An `InnerGame` is a second game in a second context; it cannot
return to the first game's live scene. What the scope does share (a time slice,
`fast_forward_frame_count`, `FrameSilencer`) is shared.

**Also agreed (the owner, 2026-11-20):** the three `assert`s in `inner_game.py` become raises in
Task 2 (the sweep of the rest is in Follow-ups); and the master plan's sentence about
`MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS` is corrected in the spec itself (done in this commit:
it is a cap on a whole journal checked once when instant replay is requested,
`scenes/scene.py:3158` and `replay/playback.py:1346`, not a fast-forward).

## Root cause: why Bitmappy's tile diverges at frame 0 (triage, 2026-11-20)

Reproduced, instrumented and measured with scratch scripts (not kept; Apple M4 Max, dummy
drivers, this worktree), without changing any engine or Bitmappy code.

1. **Reproduction.** The bundled demo `bitmappy/demos/drawing.jsonl.gz` replayed as an
   `InnerGame` inside an outer window of 1280x720: `Replay diverged at frame 0: sprite
   FilmStripSprite#0 rect expected [350, 24, 450, 124], got [350, 24, 930, 124]`, outcome ended
   after 1 frame. Inside an outer window of 800x480 (the demo's own size) the same replay
   matches all 900 frames. This is the strict xfail in
   `tests/test_every_recording_replays_inside_an_inner_game.py` (`DIVERGES_INSIDE_A_TILE`).
2. **The first differing value is one field of one sprite: the film strip's width**, 450 recorded
   and 930 in the tile. The recorded 450 is 800 - 350 (the tile's width less the strip's left
   edge); 930 is 1280 - 350 (the outer window's width less the same edge).
3. **The door is not an engine door: it is a direct pygame call.** A spy on
   `pygame.display.get_surface` (scratch, restored after) saw Bitmappy call it at
   `film_strip_coordinator.py:348` (`_calculate_film_strip_dimensions`, once, at frame 0, answered
   with the 1280x720 outer window) and at `controllers/visual_indicators.py:326` (every frame,
   900 times in the matching run). `animated_canvas.py:1631` was not reached by this demo.
   `film_strip_coordinator.py:348` computes `film_strip_width = max(300, window width - film_strip_x)`.
4. **Proof that this is the whole cause.** In a scratch run only, `get_surface` was answered with
   the inner context's render target (`glitchygames.render_target.display_surface()`, which the
   engine already reads instead of `pygame.display.get_surface()`, `render_target.py:95`): the
   tile in the 1280x720 window then matched all 900 frames.

So the divergence is deterministic and has nothing to do with the replay's pacing, the
recording or the demo: Bitmappy sizes itself from the process's one display surface, and in a
tile that is the host's window. pygame has one display surface per process, and a game's direct
`pygame.display.get_surface()` cannot be answered per context by an engine that replaces no pygame
function (sub-plan 3's rule).

**The other strict xfail is the same family, a different direction.** The text-input demo's tile
changes the outer game's key repeat. Measured: the outer set `(0, 0)`; after the tile's build
`pygame.key.get_repeat()` was `(350, 350)` (the demo's own `setup()`, `text_input_demo/__init__.py:69`);
after its 600 frames `(200, 200)` (17 calls of the engine's `ui/inputs.py:195` on key releases).
Its replay still matched all 600 frames. The class, stated as a property: **code running in a
context calls a pygame function whose state is the process's, not the context's**. Bitmappy
*reads* one (the answer is the host's, so the tile misbehaves: it diverges); the text-input demo
*writes* one (the tile is right, the host's state is changed). The same class is the remaining
rows of `plans/future-work.md`: text input start and stop (`ui/text_widgets.py:1218-1511`), the
mouse cursor (`bitmappy/animated_canvas.py:1156, 1178`), the font resolution, and a third member
found here: **Bitmappy's `main()` calls `multiprocessing.set_start_method('spawn', force=True)`**
(`editor.py:1643`), and a tile run changed the host's start method from None to `spawn` (measured
below). Sweeping for siblings, the callers of the display, key and mouse state in `src/` that
engine code makes are `ui/inputs.py:195` and `ui/text_widgets.py` (the engine's own, fixable
in the engine); the rest are game or app code (Bitmappy, the text-input demo).

### Question 3, recast: is a diverging demo a policy question or a bug? (open)

It is a bug, for the demos that diverge today; the divergence policy is a small defence for a
demo that drifts later. The fix options for the bug:

- **A (recommended): a context-scoped answer for the process-global pygame calls**, installed by
  `InnerGame` while an inner context's code runs and removed after (the display surface answers
  with the render target; the key repeat, text input and cursor calls act on the context's own
  copy and reach SDL only for the context that owns the window). It fixes Bitmappy and the
  text-input demo with no game change, which the owner's rule requires, and the whole class at
  one place. Its cost: it replaces pygame functions for the duration of a tile's frames, which
  sub-plan 3 and 4 ruled out ("no pygame function is replaced", written about the mixer). The
  owner would have to say that rule does not cover this scoped case. It is not this sub-plan's
  work; it is a small sub-plan of its own, before the Arcade screen needs Bitmappy.
- **B: Bitmappy reads its scene's screen** (`display_surface()` or `self.screen`) at the three
  sites (`film_strip_coordinator.py:348`, `visual_indicators.py:326`, `animated_canvas.py:1631`),
  and the demo drops its `set_repeat`. It is the cleaner code, and the app is a member of this
  repository, but it breaks "wrapping a game needs no changes to the game". Bitmappy's bug exists
  outside the Arcade too (a window not 800x480).
- **C: keep the strict xfails and hold the policy.** The Arcade would show Bitmappy frozen after
  one frame from its first run.

Then the divergence policy, for a demo that drifts after it was recorded: **restart once, and
if the next run diverges at the same frame, freeze on the last frame with the "error" label and
stop restarting** (recommended), against the spec's "the tile restarts its demo and goes on,
logged once". With today's Bitmappy and no fix, "restart each time" would rebuild it (73 to 180
ms measured, 3.1 s in one run) every other Arcade frame. With fix A the policy is rarely
reached, and the recommendation costs a few lines. The owner decides A, B or C first; the
policy follows.

## Review Focus

1. **The viewer's schedule is bit-for-bit the same after the pacer moves.** The existing
   viewer, replay-schedule and instant-replay tests are the guard (Task 1 records their counts
   first); the new pacer tests also compare the pacer's decisions with a table of the viewer's
   documented rules (rule 2 up to and above 1x, the owed limit, the stall rule).
2. **A `DemoPlayer`'s frames equal a headless replay's, however the frames are paced**:
   digests equal for generous budgets, for a budget of one frame, for slow motion, interleaved
   beside another player, across a loop, and after a fast-forward (Tasks 4 and 6).
3. **No frame is ever skipped and no player starves**: with a fake clock the frame sequence
   run is 0, 1, 2, ... in order; a player behind runs in slow motion; with ten players and a
   budget for three frames, every player still runs within a few ticks (rotation, Task 4).
4. **A looping player gives its channels back.** Looping each of ten players twenty times
   neither exhausts the declared live pools nor grows the mixer (the follow-up "the host must
   finish every inner game it drops").
5. **A silent player stays silent through fast-forward and loops, and a heard one stays heard
   across its loop** (the sub-plan 4 helper `assert_no_tile_is_heard`).
6. **Nothing reads a real clock except the budget**, through its injected parameter (a source
   guard in the style of `tests/test_engine_doors.py`).

---

### Task 1: The pacer, extracted from the viewer, with the guard first

**Files:** Create `src/glitchygames/replay/pacer.py` (`RecordedFramePacer`, `TickBudget`, the
constants moved from `viewer.py`: `MAX_OWED_INNER_FRAMES`, `INNER_FRAME_BUDGET_SECONDS`,
`STALL_TICK_SECONDS`, `EFFECTIVE_SPEED_WINDOW_TICKS`, `BEHIND_SPEED_FRACTION`, re-exported by
`viewer.py` so imports of them keep working); modify `src/glitchygames/replay/viewer.py`
(delegates the owing); `scripts/replay_schedule.py` if it reaches into a moved attribute
(`accumulated_seconds`, `last_inner_frame_ran_behind` stay properties of the viewer). Tests:
`tests/replay/test_pacer.py` (new subject), the existing `tests/replay/test_viewer.py` and
`tests/test_replay_schedule.py` unchanged.

- [ ] Guard first: run `tests/replay/test_viewer.py`, `tests/test_replay_schedule.py`,
  `tests/replay/test_rebuild.py`, `tests/replay/test_playback_scope.py`,
  `tests/replay/test_instant_replay.py` and the golden replays, and record the counts passed.
- [ ] Tests (behaviours of the pacer, written to the viewer's documented rules): at speed 1 and
  a 60 FPS recording, one frame is owed each 1/60 s of elapsed time and exactly one runs per
  tick; a long frame followed by a short catch-up frame never share a tick up to 1x, and do
  above 1x only after a frame of at least a tick of inner time; owed time past the owed limit
  is dropped and the pacer reports behind for the next second of ticks; a stall (elapsed over
  `STALL_TICK_SECONDS`) pays as one nominal tick; paused or not running, the accumulator
  empties and the next run starts with half a frame; a frame of zero duration owes nothing;
  `effective_speed` is inner seconds over real seconds over the last second, and
  `real_speed_if_behind` is None while the pace is within `BEHIND_SPEED_FRACTION`; frames run
  by the pacer are always the next frame in order (a property over generated elapsed-time
  sequences: never skipped, never repeated); a different nominal tick (120 Hz) keeps the rate.
  `TickBudget`: `is_spent` flips when the injected clock passes its length; `remaining_seconds`
  never goes below zero; two consumers sharing one see each other's spending.
- [ ] Implement; the viewer delegates; the viewer's own tests pass unchanged; a source guard:
  no module but `pacer.py` computes owed frames (an `accumulated_seconds` subtraction).
- [ ] Commit (`Replay: the viewer's pacing accumulator is a pacer a tile can share`).

### Task 2: `InnerGame` as the runner: what a host needs to pace it

**Files:** `src/glitchygames/replay/driver.py` (`_inner_frame_seconds` becomes public
`ReplaySources.next_frame_seconds`; `hold_frame` calls it), `src/glitchygames/inner_game.py`
(`next_frame_seconds`, `frame_count`, `frame_index`; the two `assert engine is not None` at
610 and 643 and the one at 792 become raises of `InnerGameStartError`-style errors, since
the owner agreed 2026-11-20 that these are a rule breach; the sweep of the rest is below), tests in
`tests/engine/test_inner_game.py` and the driver's test file.

- [ ] Tests: `next_frame_seconds` equals the viewer's rule (the next frame's recorded `dt`, the
  current frame's for the last, 0.0 past the end) on a recording with uneven `dt`s, before frame
  0, mid-run and at the end; `frame_count` equals the recording's; `frame_index` is the next
  frame to run and equals `outcome.frames_run`; all three read as defined after the game ended
  or failed; a stepped game that was finished raises a clear error where the old code asserted.
- [ ] Implement; full suite; commit (`Inner game: the host can ask for the next frame's recorded duration`).

### Task 3: A time-sliced fast-forward on `InnerGame`

**Files:** `src/glitchygames/inner_game.py` (`fast_forward(*, to_frame, budget)`, using Task 1's
`TickBudget`; refused while audible), `src/glitchygames/replay/rebuild.py` (`progress_is_due`
reads a `TickBudget` instead of its own interval arithmetic; observable behaviour unchanged),
tests in `tests/engine/test_inner_game.py` and `tests/replay/test_rebuild.py` (unchanged).

- [ ] Tests: a fast-forward in one call with a large budget reaches `to_frame` and the next
  `step()` is frame `to_frame`; with a budget of one frame it takes `to_frame` calls and each
  call runs at least one frame (progress is guaranteed), never past `to_frame`; the frame
  after it, and every later frame, has the digest of a headless replay's (the proof's
  helper); nothing it ran was heard (`assert_no_tile_is_heard`) and an audible game is
  refused with the error naming `set_audible(audible=False)`; `to_frame` at or past the frame
  count is a `ValueError`; a divergence or failure partway ends it with that outcome and
  returns "not reached"; a fast-forward called with `to_frame` already passed is a no-op.
- [ ] `Rebuild`'s existing tests pass unchanged on the shared `TickBudget`.
- [ ] Commit (`Inner game: a silent, budgeted fast-forward`).

### Task 4: `DemoPlayer`

**Files:** Create `src/glitchygames/demo_player.py` (`DemoPlayer`, `DemoOutcome`,
`poster_frame`); tests `tests/test_demo_player.py` (stand-in games from
`tests/stand_in_games.py`, so the engine's tests need no member).

- [ ] Tests, each a behaviour of the contract (decisions 5 to 13):
  - tick: with elapsed time for three frames and an ample budget, three frames run; with a
    one-frame budget, one runs and the rest are owed and run on the next ticks (nothing lost,
    none skipped); the digests of every frame equal the recording's headless replay.
  - slow motion: a budget that fits half the owed frames runs the whole recording, in order,
    taking twice as many ticks, `is_behind` true and `effective_speed` about 0.5; when the
    stall rule applies a long gap does not burst more than the owed limit.
  - beside another player: two players with different recordings ticked unevenly (the proof's
    `INTERLEAVED_STEPS`) each equal their alone digests (sub-plan 3's proof, through the player).
  - shared budget: ten players and a budget for three frames per tick, with the start
    rotating: no player waits more than a few ticks for a frame (decision 3's reason).
  - loop: at the end the player rebuilds from frame 0 in a new context, `generation` increments,
    the second run's digests equal the first's, `on_new_game` ran before the new game's first
    frame, the old game's channels are back (twenty loops of ten players: no declaration
    exhausted), and a restart's build is charged to the budget.
  - sound: a new player is silent; `set_audible(audible=True)` is heard; the setting survives
    a loop; `fast_forward` refuses while audible.
  - fast_forward and `poster_frame`: Task 3's contract through the player; `poster_frame` is
    within the 10% to 90% span, the same stream seed gives the same frames, and a one-frame or
    empty recording is handled (the only frame / a `ValueError`).
  - outcomes: a missing recording and an unreadable one are `COULD_NOT_START` with the reason;
    a recording with no screen size likewise; a stand-in game whose scene raises on frame 3 is
    `CRASHED` with the traceback logged and the last frame still readable; a stand-in game
    that behaves differently from its recording is `DIVERGED` (a mismatched frame, and a
    recording longer than the run: the length divergence that arrives as `FAILED`); the other
    players are unaffected by any of these.
  - the divergence policy as the owner decides (question 3: restart once then freeze, or restart).
  - guard: the module imports no game and reads no clock but the budget's.
- [ ] Implement; full suite; commit (`Demo player: a recorded game that loops, fast-forwards and paces itself`).

### Task 5: The viewer on the shared pacer (still its own engine)

**Files:** `src/glitchygames/replay/viewer.py`, `src/glitchygames/replay/driver.py` only where
Task 1 left a seam. Tests: the existing viewer, schedule and rebuild tests.

- [ ] Task 1 already moved the owing; this task removes what Task 1 left duplicated in
  `viewer.py` and `driver.py` (comments that describe a rule now documented in `pacer.py`),
  and reduces `viewer.py`'s docstring to the outer loop's contract plus a pointer to the
  pacer's. Every watched-replay test and golden replay is run watched on the native driver
  (`nox -s compare-drivers`): unchanged.
- [ ] Commit (`Replay viewer: its docstring and seams follow the pacer`).

### Task 6: The proof, the benchmark and the documents

**Files:** `tests/test_every_recording_replays_inside_an_inner_game.py` (a variant that runs
each pair through `DemoPlayer`s, ticked unevenly, with a loop, a fast-forward to a seeded poster
frame and a switch heard and back; Bitmappy and the text-input demo keep their strict xfails),
`tests/benchmarks/test_demo_player_benchmarks.py` (ten players per Arcade frame with the real
bundled demos against `INNER_FRAME_BUDGET_SECONDS`; one restart's build for each demo, cold and
warm; the ten posters' fast-forward in total; `nox -s performance-test` runs them), docs:
`CLAUDE.md` (Gameplay Recording and Replay, Engine Context), `docs/architecture/playback/`
(`how-a-frame-runs.md`, `speeds-and-timing.md`), `docs/architecture/engine_context.md`,
`docs/architecture/gameplay_replay.md`, `plans/2026-10-23-arcade-showcase.md` (item 5),
`plans/2026-10-25-engine-context.md` (sub-plan 8: moved or done, as the owner decides),
`plans/future-work.md`, and `FEATURE.md` / `TODO.md` or the project's equivalents.

- [ ] Proof tests as above: every golden and bundled demo, as a `DemoPlayer` beside another,
  equals its alone replay frame for frame; the slow-motion and one-frame-budget runs too.
- [ ] Benchmark: a stand-in-free measurement of the table above on the real demos, so the
  build-time numbers (Bitmappy's 73 ms to 3.1 s spread) are explained or recorded as a range;
  the engine context page's Performance table gains the player's row (checked by
  `tests/test_read_only_views.py`'s pattern if it applies).
- [ ] Docs: grep every `.md` (CLAUDE.md, memory, plans, docs) for paths and names this changed
  (`INNER_FRAME_BUDGET_SECONDS` in `viewer.py`, `_inner_frame_seconds`); fix them.
- [ ] `uv run pytest`, `nox -s lint`, `nox -s static-analysis`, `nox -s compare-drivers --
  --drivers native --fail-on-difference` (the controller runs the last; pre-push does too);
  commit (`Demo player: the proof, the benchmark and the documents`).

---

## The viewer's own context (engine context sub-plan 8): a later sub-plan

Decided by the owner 2026-11-20 to be later; not planned in tasks here. Its design questions, found by the audit, so the
later plan starts from them: where the outer viewer game lives (an outer `GameEngine` in the
default context that hosts the game's engine in a context, instead of the game's own engine
being the viewer's doors: `game_engine.py:1520, 1647-1649, 3762`); how a watched `InnerGame`
reads real keys (the known `_has_blocked_real_input` bug, driver.py:1483, 2473, 2536);
where `ReplayControls`, the status bar, bookmarks, onion skin and the frame sink live
(`ReplaySources` fields, driver.py:1311-1460); and what in-process step back replaces
(`rebuild.py`'s supervisor, handoff and `--replay-restart-handoff`) while `--replay-pause-at-frame`
stays valid. Its guard is every watched-replay test and golden replay, unchanged.

## What later sub-plans take from this

- **6 (the Arcade screen):** holds ten `DemoPlayer`s; owns the top-player-first policy
  (passes one `TickBudget` to the top player, then the leftover to the others, starting at a
  rotating index), the heard player (`set_audible`), the poster stream
  (`random_stream('arcade-posters')`) and the "title on the test pattern until ready" screen
  (`fast_forward` returning not-reached), the overlay restore (`on_new_game`), the "no demo" /
  "error" labels (`DemoOutcome`) and the freeze for a diverged demo. Bitmappy's tile stays a
  strict xfail until its bug is fixed.
- **7 (launching in the same process):** a launched game pauses the tiles; the pacer's stall
  rule keeps them from bursting on return. A live game is not a `DemoPlayer`.
- **8 (browser):** `tick` is synchronous and takes elapsed time as an argument, so one Arcade
  tick runs its players inside `with player.context.active()` without an `await` between.

## Follow-ups and bugs found while planning (2026-11-20)

- **`assert` in engine code, a class (the owner agreed it is a rule breach).** The class:
  engine invariant checks written as `assert`, which `python -O` strips, with bandit's B101
  filtered out of its configuration. Swept: `grep -E '^\s*assert\b'` over `src/` outside
  `tests/` directories finds **154** (none in `glitchygames/testing/`): `src/apps/bitmappy` 37,
  `glitchygames/scenes/scene.py` 24 (the owner remembered about ten, e.g. 2595, 2669, 2700),
  `audio/library.py` 9, `game_objects/paddle.py` 7, `replay/driver.py` 6,
  `replay/tools/golden_traces.py` 6, `replay/tools/compare.py` 6, `audio/assets.py` 5,
  `ai_console.py` 5, `ui/dialogs.py` 4, `src/games/drawing-fire` 4, `src/games/brave-adventurer`
  4, `inner_game.py` 3, and 29 more in 20 other files (the list is a one-line grep to redo).
  Where it is filtered: ruff's S101 is **ignored for the whole project** at `pyproject.toml:495`
  ("assert is used intentionally for type narrowing and runtime invariant checks"), and bandit
  runs at medium severity and confidence (`pyproject.toml:780-787`, `noxfile.py:2358-2359`:
  `-ll -ii`) with the comment "B101 (assert_used) is Low severity and gets filtered out by this.
  TODO: Replace remaining assert usage with explicit raises, then tighten to low/low". Both
  came in with `c9b9f5fa` (2026-03-21, "Miscellaneous Bug Fixes (#71)", `git log -S`); the TODO
  still stands. This sub-plan fixes only the three in `inner_game.py` (Task 2). Fixing the rest
  is its own task (raise a named error, then drop the S101 ignore and tighten bandit), and the
  S101 ignore is a global suppression the owner's rules say to ask about.
- **Spec correction:** done in the spec file (above).
- **A Bitmappy tile starts a child process (confirmed), and my measuring script ran three
  times because of it.** Evidence: a spy on `multiprocessing.process.BaseProcess.start` while a
  Bitmappy tile was built as an `InnerGame` saw the call, from `ai_manager.py:182`
  (`AIManager.setup`, started from `bitmappy/editor.py:866` during the scene's setup, reached
  through `scenes/scene.py:2987, 1674, 1665`) and the child got a pid; it was in the host's
  process tree. It happens in a headless replay too. The cause of the three runs: `main()` in
  `editor.py:1643` sets the start method `spawn`, and a spawned child re-imports the parent's
  `__main__`; my scratch script had no `__main__` guard, so each child ran it again. With a guard
  it ran once. Also measured: the host's start method was None before the tile and `spawn`
  after (a process-global leak, the same class as above). On this machine the worker was not
  alive by the end of the build (`multiprocessing.active_children()` empty, no process left
  after the tile finished, `ps` clean; I did not trace why it exits, so a configured AI backend
  may keep it alive and I did not test that). So: it does not need a game change to wrap
  Bitmappy, but it breaks the Arcade's "one process, no children" intent (the master plan, B and
  D2 set aside) and would be caught by `tests/child_process_guard.py` if a test left it
  running. Fix options for sub-plan 6 or the class fix above: no AI worker in an inner context
  (`AIManager.setup` is Bitmappy's, so again an engine-side answer is needed, for example
  `multiprocessing.current_process().name`, which the manager already tests), and a scoped
  start-method answer. The Arcade should also make a tile's `finish()` reach the scene's
  cleanup (`AIManager.cleanup`); I did not verify that it does.
