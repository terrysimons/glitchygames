# Zombies Ain't My Neighbors, Feature 13: the attract demo

Master plan: [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(decision 6: "A title screen with a recorded attract-mode demo (bundled demos)"; "What is left of
level 1"). It fills the second slot of feature 12's idle loop
([2026-11-19-zombies-aint-my-neighbors-12-intro-and-idle-loop.md](2026-11-19-zombies-aint-my-neighbors-12-intro-and-idle-loop.md)).

Status: BUILT (2026-11-19), Tasks 1 to 6 committed on `feature/zombies-attract-demo`, the final
review's fixes too. The owner's browser check (2026-11-19) found two things, both fixed on the
branch: the browser bundle carried no package metadata, so the demo could not find its game
there (the bundle now ships each member's `.dist-info`, `scripts/build_browser_bundle.py`); and
the loop played the intro twice before the demo (launch, then the first idle). The owner's
call: each idle shows the demo or the intro in turn, the demo first (`title.Attraction`); the
intro now always ends into the title. The Pi measurement waits for the Pi. A builder check's seven
questions were settled as Claude's calls (marked below). Rulings made while building are in the
gitignored ledger (`.superpowers/sdd/2026-11-19-zombies-aint-my-neighbors-13-attract-demo/`) and
summarised here:

- **No walk out through the gate.** The game clears the stage when one kid touches the open
  gate, then everyone freezes and cheers; the demo ends halfway through that cheer.
- **The kids move as a group**, as the group's screen span makes them: steering each to its own
  neighbor ran 87 s with kids pinned against the span.
- **Steered live.** The recorder keeps real frame times and input reaches the kids a frame after
  it is posted, so routes planned ahead drifted (the first recording saved one neighbor and
  never cleared); the demo's input script steers from the running stage
  (`ZombiesDemoSteering`), and the planner only sets its length.

Measured (Task 6): building the demo (`AttractScene.setup()`) takes 224 to 336 ms on the development
Mac (five runs; the first in a process 940 ms), and a frame of it about 2 ms. The intro's
last frame holds on screen meanwhile. The Pi was down: not measured.

## Intent

The game is pitched as a four-player arcade cabinet. When nobody is playing, the title loops:
title, the intro, and then this demo. Someone walking past should see **multiplayer kids running
around killing zombies, destroying TVs, and saving neighbors** (the owner, 2026-11-19): a co-op
party game, worth picking up a pad for. The demo is a complete little story: the four kids clear
stage 1, **go out through the gate**, cheer, and the loop returns to the title (the owner: "Yeah
the stage clear and go through the gate").

## Decisions (the owner, 2026-11-19)

| # | Decision | Why |
|---|----------|-----|
| 1 | **Four kids** play, clearly together: zapping zombies, destroying TVs, saving neighbors | What a passer-by should see: a co-op party game |
| 2 | **It runs to the stage clear and out through the gate** (with the cheer), then the title | A complete story that ends on its best frame, not mid-fight |
| 3 | **A recording, replayed inside the game** (approach A, Claude's recommendation, taken) | Decision 6 asks for a recorded demo; no gameplay or engine change; the same file is the Arcade's Zombies tile |
| 4 | **No rumble** (feature 12's decision 3, "No rumble on the demo") | Nobody may be holding a pad |

## Approaches considered

- **A. A recording, replayed inside the game (chosen).** One bundled demo,
  `zombies_aint_my_neighbors/demos/neighborhood_four_kids.jsonl.gz`, recorded from an input
  script that a four-kid route planner writes. In the loop, an attract scene replays it with the
  engine's inner-game replay (`glitchygames.inner_game.InnerGame.replay`, the Arcade's tiles) and
  shows it full screen under a DEMO label. The same every time, tested like a golden, no gameplay
  change; costs a re-plan and re-record when gameplay changes (as the neighborhood golden does).
- **B. An autopilot, played live.** The planner's steering moves into the game and the attract
  scene runs a real neighborhood with four bot-driven kids. No file to go stale, but kids would
  need to take orders from something other than an input device (a change inside gameplay),
  every showing differs so no test pins what a passer-by sees, the Arcade gets nothing, and it
  contradicts decision 6. Rejected.
- **C. Pre-rendered frames** (an image sequence) were dropped at once: large, and stale on any
  art change.

## Goals

- The idle loop completes: TITLE, idle `IDLE_SECONDS`, INTRO, **DEMO**, TITLE, round and round.
- The demo: four joined kids (Dex on the keyboard, Marisol, Theo and June on pads) clear stage
  1: every neighbor rescued or lost, TVs destroyed along the way, zombies zapped, the gate opens,
  the kids walk out through it, the cheer. Roughly 20 to 30 seconds.
- A **DEMO** label on screen the whole time, in the game's own text style (`text.py`).
- Any key or pad button ends the demo at once and returns to the title; the press is consumed as
  feature 12's skip is (the title waits for that input's release, so it cannot join anyone).
- The demo is a bundled demo like every other game's: recorded by
  `scripts/record_bundled_demos.py`, replayed by `glitchygames verify` and
  `tests/replay/test_bundled_demos.py`, and so available to the Arcade.

## Non-goals

- The Arcade's Zombies tile itself (the Arcade's own plans pick bundled demos up).
- More than one demo, or a demo of a later stage.
- Any engine change (decision 12). An engine gap goes in the master plan's wishlist.
- Changing how kids read input (approach B's cost).

## Anti-goals (a failure even if it works)

- A real pad rumbling while the demo plays.
- The press that ends the demo joining a player or starting a stage.
- A broken or black screen when the demo cannot play: it must fall back to the title.
- Mixer channels or an engine context leaked when the demo ends by any path (its end, a skip, a
  failure, quitting the game while it plays): `InnerGame.finish()` runs on every one (rule 6 of
  `inner_game.py`: nothing gives channels back otherwise, and the next showing would fail).
- A demo that silently stops reaching the gate after a gameplay change while still replaying:
  a test must fail first.
- Either golden changing (the title's `golden.jsonl.gz`, the neighborhood's
  `golden-neighborhood.jsonl.gz`) because of this feature.

## How it behaves

### The loop

```
TITLE ──(idle 20 s)──► INTRO (loop showing) ──(its end)──► DEMO ──(its end)──► TITLE
  ▲                         │                                │
  └──── any key or button ──┴────────────────────────────────┘
```

- The intro's END cue in the **loop** showing now hands over to the demo; in the **launch**
  showing it still hands over to the title. A skip from the intro still goes straight to the
  title (no demo).
- The demo's end (the inner replay finished) hands over to a fresh title (`opening=False`, as
  every rebuilt title), which counts its idle time from zero.

### The attract scene (`attract.py`, Claude's call on the name)

- `AttractScene(PadTolerantScene)`: in `setup()` it builds the inner game,
  `InnerGame.replay(command='zombies-aint-my-neighbors', path=<the bundled demo>, name=...,
  size=<the demo's recorded size>)`, finds the demo through `glitchygames.bundled_demos` (the one
  lookup), makes it audible, and draws its `surface` through one full-screen sprite (every game
  object is a sprite), with the DEMO label sprite in front.
- **Size** (Claude's call, after the builder check): the engine refuses a replay at any size but
  the recorded one (`inner_game.py`, `replay`'s `size`), so the scene always passes the recorded
  size (800x480, the goldens') and the sprite scales the picture to the screen, letterboxed
  in the background colour when the aspect differs. A `--resolution` that differs therefore
  still shows the demo, never a failure each loop.
- **Where it runs** (Claude's call, after the builder check): wherever the loop runs, live,
  recorded, replayed and on the dummy driver, as feature 12's loop does. Two places are
  unverified and checked during this feature: the Pi (measure the build and the frame time; a
  build over a second goes to the owner) and the browser build (no inner game has run under
  Pyodide yet). If either cannot play it, the game skips the demo there by a check the scene
  owns (the loop's intro then ends into the title), and the gap goes in the master plan's
  wishlist; until then a failure falls back to the title as below.
- Each `dt_tick` steps the inner game one frame (`step()`; the host's frame is its pacing, so it
  plays at the speed it was recorded). When `step()` says it has ended, or its outcome is
  `FAILED`, the scene hands over to the title; a failure is logged as a warning, naming the
  outcome's text.
- Any key or pad button down hands over to the title (P and Esc included, as in the intro);
  releases, sticks, hats and devices arriving or leaving do nothing.
- Its cleanup finishes the inner game, exactly once, on every path.
- The game declares one inner game (`INNER_GAMES = 1`) on the scene class it hands the engine
  for a live run (the title), so the engine sets the inner game's sound channels aside at
  construction (rule 6 of `inner_game.py`).
- Rumble: inside the inner replay the pads are the recording's stand-ins, so a TV destroyed in
  the demo rumbles nothing real; no extra code (a test proves it, below).

### The demo's recording

- **Four kids from the first frame.** The recording begins in the neighborhood with four players
  joined: the keyboard as P1 and three stand-in pads (`DemoRecipe.stand_in_devices`, a
  `DeviceDescriptor` each, instance ids 0, 1 and 2) as P2 to P4. Claude's call: a
  `NeighborhoodScene` subclass in the game whose default roster is those four, recorded as the
  demo's scene, and recognised by `launcher.first_scene` as the neighborhood is (the engine
  refuses a recording whose header names another game). A plain `NeighborhoodScene` with a
  roster argument is not possible without an engine change: the scripted-session recorder
  (`replay/tools/scripted_sessions.py`, `record_scripted_session`) and `DemoRecipe` take a scene
  class only, built with no arguments. Its replay rebuilds the scene from its recorded scene
  start (`replay_arguments`, the roster included). The alternative, starting on the title with
  four joins and the STAGE 1 card, would show the title again right after the title; the
  builder may switch if the subclass meets an obstacle, recording why.
- **Pad identities.** A roster's `DeviceIdentity` is only a kind and an SDL instance id
  (`roster.py`), so the roster is `JoinRoster.empty().join(...)` four times: the keyboard, then
  gamepads 0, 1 and 2, the stand-ins' instance ids. Joining in that order gives slots 1 to 4,
  and so Dex, Marisol, Theo and June, as live joins do. One constant holds the three instance
  ids. The recipe's descriptors and the roster both read it.
- **The planner** (`scripts/plan_neighborhood_route.py`, extended rather than copied: one shared
  path for one kid or four) plays the stage under the goldens' seed and steers each kid every
  frame. Its starting rules (Claude's call; the builder tunes them for a good show):
  - Every kid holds fire the whole time.
  - Kids 1 to 3 each head for the nearest neighbor still standing that no other kid has claimed.
  - Kid 4 hunts the TVs still spawning and, when none are left, joins the rescue.
  - Once no neighbor stands, every kid heads for the gate.
  - The group's screen span (`neighborhood.py`, "the group's span") limits how far apart they
    get. The rules must work with it, not fight it.
- **Pads are driven on the joystick layer.** Scripted sessions force joystick mode
  (`controls.py`): stick axes 0 and 1, and the fire button.
- **The demo ends** as the last kid leaves through the gate, after the cheer, before the STAGE
  2 card (Claude's call: the card is a different scene and says nothing to a passer-by). It
  also ends with nothing held, the bundled demos' own rule: a held key or button would stick
  when the demo loops.
- **The planner prints:** the input script, the frame count, and what the run showed (neighbors
  rescued, TVs destroyed, zombies zapped, the frame of the clear and of the exit). The recipe
  takes that frame count.
- **Where the script lives** (Claude's call): its held stretches per kid are a constant in
  `scripts/demo_inputs.py`, beside the other bundled demos' inputs. The input-script callable
  sits there too.
- **Shipping:** the package builds with hatchling's wheel target, which ships every file under
  the package, so `demos/*.jsonl.gz` ships as the other games' demos do. The package-data
  test (`test_zombies_aint_my_neighbors_package_data.py`) and `tests/workspace_expectations.py`
  name the new demo.

## Constraints

- No engine changes (decision 12); game code in `src/games/zombies-aint-my-neighbors/`; the
  recipe in `scripts/record_bundled_demos.py`, its inputs in `scripts/` beside the golden's.
- Heavy work before play (decision 11): the inner game is built in `setup()`. Building it costs
  a second engine context and a neighborhood. Measure the build on the Mac (and note the Pi)
  and record it here. If the hitch shows on screen, building during the intro's last second is
  the builder's option.
- Clocks and randomness by the engine's rules. The demo plays its recording's own seed and
  frame times, so the outer run's random streams are untouched.
- The engine's inner-game rules (`inner_game.py` docstring) bind the attract scene: only a
  headless replay runs inner, the host finishes every inner game it drops, and only one inner
  game is heard at a time.
- `INNER_GAMES = 1` changes the mixer's partition for every live run that starts on the title.
  The title's golden must still replay unchanged. If the partition shows up in it, stop and
  bring it to the owner; don't re-record.
- Feature 12's anti-goal holds: every golden or bundled demo that starts on the title stays
  shorter than `IDLE_SECONDS`. This demo starts in the neighborhood.
- Unhandled events raise in every test: the attract scene handles every event it can receive.

## Tests (behaviours)

- **The demo shows what was promised.** Replaying the shipped demo:
  - all four kids move and fire;
  - at least one TV is destroyed and at least one zombie is zapped;
  - neighbors are rescued;
  - the stage clears;
  - every kid leaves through the gate;
  - it ends before the STAGE 2 card, with nothing held.
- **How those are observed** (Claude's call): the test plays the demo back and reads the
  scene's state each frame. It uses the kids, neighbors, TVs and exit door, through the same
  playback the golden route test uses (`start_playback`, `step_finishing`). It needs no new
  events and no gameplay hook.
- **The demo is still the plan.** The committed input script equals what the planner makes
  today, as the golden route test checks for the golden. A gameplay change, or a retune of the
  planner's rules, fails this test until the demo is re-planned and re-recorded on purpose.
- **The bundled demo rules.** The demo joins the workspace expectations, replays clean under
  `glitchygames verify`, and passes `test_no_bundled_demo_ends_with_input_held`.
- **The loop:**
  - the loop showing's intro ends into the demo;
  - the launch showing's intro ends into the title;
  - a skip from the intro goes to the title;
  - the demo's end goes to a fresh, non-opening title with its idle count at zero.
- **Skipping the demo:**
  - a key or a pad button, on the first frame, mid-way and on the last frame, ends it on that
    frame;
  - the new title waits for that input's release, so the press joins no one;
  - releases and stick motion don't end it.
- **Failure:** a missing or unreadable demo, or a replay that fails, goes to the title with a
  warning logged and no exception.
- **No leaks.** After the demo ends by each path (its end, a skip, a failure, the game quitting
  while it plays):
  - the inner game is finished exactly once;
  - its channels are given back;
  - a second showing builds and plays.
- **No rumble.** A stand-in pad connected to the outer game receives no rumble while the demo
  plays, across the TVs it destroys.
- **Pixels.** While the demo plays, the screen shows the inner game's picture (a pixel of the
  lawn where the replay draws lawn) and the DEMO label.
- **The goldens.** Both replay unchanged.

## Left to the builder

- The planner's steering rules beyond the starting ones above, tuned so the show reads well:
  kids spread out, TVs visibly destroyed, a rescue or two on screen. Show the owner a contact
  sheet or a short capture of key frames before recording for good, as the art features did.
- The demo's exact length (target 20 to 30 s; flag it if the plan runs past 45 s).
- The DEMO label's place, size and whether it blinks.
- The attract scene's layout of code beyond `attract.py`, and how the intro is told where to
  hand over.

---

# Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** the attract demo above: a four-kid stage-1 clear, planned, recorded as a bundled demo,
and replayed in the idle loop's second slot.

**Architecture:** a demo neighborhood that starts with four joined players
(`demo_neighborhood.py`); the route planner grown from one kid to four on one shared stepping
path (`scripts/plan_neighborhood_route.py`); the demo's input script and recipe beside the other
demos' (`scripts/demo_inputs.py`, `scripts/record_bundled_demos.py`); an `AttractScene` that
replays the shipped demo as an inner game and draws it scaled under a DEMO label (`attract.py`);
the loop's intro handing over to it.

**Tech stack:** Python 3.15 (parses as 3.14), pygame-ce, the GlitchyGames engine (`InnerGame`,
`bundled_demos`, the scripted-session recorder, `InputSnapshot`), pydantic, pytest with `mocker`.

**Spec:** this file's design above (the sections from "Intent" to "Left to the builder").

Paths below are relative to `src/games/zombies-aint-my-neighbors/` unless they start with
`src/glitchygames/`, `scripts/`, `tests/` (the engine's) or `plans/`. `Z` is
`src/zombies_aint_my_neighbors/`; `T` is `tests/`.

## Global constraints

- No engine changes (decision 12); game code in `src/games/zombies-aint-my-neighbors/`, the
  planner, inputs and recipe in `scripts/`, registrations in `tests/workspace_expectations.py`
  (decision 17).
- The demo: four kids (keyboard, then stand-in pads with instance ids 0, 1, 2), the goldens' seed
  (`RANDOM_SEED`), 800x480 at 1/60 s frames, no controls tail, ends with nothing held, before
  the STAGE 2 card; target 20 to 30 s, flag past 45 s.
- `INNER_GAMES = 1` on `TitleScene` only. Both goldens replay unchanged; if one doesn't, stop
  and bring it to the owner (never re-record a golden for this feature).
- Every object is a sprite in the scene's groups; heavy work in `setup()`; time from
  `Scene.game_time`; randomness only from named streams.
- `--no-unhandled-events` holds in every test.
- Data classes are pydantic `BaseModel` (`frozen=True`, `extra='forbid'`); keyword arguments;
  no `assert` outside tests; `mocker`, never `unittest.mock`.
- Ruff, then basedpyright and ty, then tests, per task; the whole gate after the last task.
- Commits only when the owner says so; pushes need `SKIP=raspberry-pi-replay-metrics` while the
  Pi is down.

## Review focus

1. A press on the very frame the intro hands over to the demo, or on the demo's first frame
   (feature 12's M1 met it on the title): it must end the demo, never be lost, never join. Task
   5 pins it (`test_a_press_on_the_hand_over_frame_still_returns_to_the_title`).
2. The demo shown a second and third time in one run: the first showing's channels and context
   must be back, so the next builds and plays. Task 4 pins it
   (`test_the_demo_plays_again_after_each_way_it_can_end`).
3. A skip while the demo's sounds and music play: the sound stops with the demo (unlike the
   intro's M2). Task 4 pins it (`test_skipping_the_demo_silences_it`).
4. A run recorded live that idles into the demo, then replayed: the outer replay matches,
   the demo included. Task 5 pins it with the idle and intro shortened by patching
   (`test_a_recorded_run_that_idles_into_the_demo_replays`).
5. The build's hitch on the first frame of the demo (a second engine context and a
   neighborhood): measured in Task 6, reported to the owner over a second.

---

### Task 1: The demo's neighborhood (four kids from the first frame)

**Files:**
- Create: `Z/demo_neighborhood.py`.
- Modify: `Z/launcher.py` (`first_scene`).
- Test: `T/test_zombies_aint_my_neighbors_neighborhood.py`, `T/test_zombies_aint_my_neighbors_launcher.py`.

**Interfaces:**
- Produces:
  - `DEMO_PAD_INSTANCE_IDS: Final = (0, 1, 2)`.
  - `demo_roster() -> JoinRoster`: the keyboard, then gamepads 0, 1, 2, joined in that order.
  - `DemoNeighborhoodScene(NeighborhoodScene)`: `roster` defaults to `demo_roster()`, every
    other argument as `NeighborhoodScene`'s; its own `NAME`.
  - `first_scene` returns `DemoNeighborhoodScene` for a recording whose header game is its
    logical name.

- [ ] **Step 1: Write the failing tests**
  - `test_the_demo_roster_joins_the_keyboard_then_three_pads_as_slots_one_to_four`: slots 0 to 3
    hold keyboard, gamepad 0, 1, 2.
  - `test_the_demo_neighborhood_starts_with_four_kids` (set up: `len(scene.kids) == 4`, one per
    slot, each kid's sprite its slot's).
  - `test_the_demo_neighborhood_rebuilds_from_its_replay_arguments` (the roster round-trips).
  - `test_a_recording_made_in_the_demo_neighborhood_starts_there` (launcher; a header written to
    `tmp_path`).
- [ ] **Step 2: Run; expect failures** (`ModuleNotFoundError` for `demo_neighborhood`).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; expect passes.**
- [ ] **Step 5: Commit.**

### Task 2: The planner, for four kids

**Files:**
- Modify: `scripts/plan_neighborhood_route.py`.
- Create: `T/test_zombies_aint_my_neighbors_demo_route.py` (the demo is its own subject; the
  golden's stays in `..._golden_route.py`).

**Interfaces:**
- Consumes: `DemoNeighborhoodScene`, `DEMO_PAD_INSTANCE_IDS` (Task 1).
- Produces:
  - `KidStretch(BaseModel)`: `direction: tuple[int, int]` (each -1, 0 or 1), `fire: bool`,
    `first_frame: int`, `end_frame: int` (exclusive).
  - `DemoPlan(BaseModel)`: `routes: tuple[tuple[KidStretch, ...], ...]` (one per slot, slot
    order), `cleared_at: int`, `exited_at: int` (the last kid through the gate),
    `recording_frames: int`, `rescued: int`, `televisions_destroyed: int`,
    `zombies_zapped: int`, `fired_by_slot: tuple[bool, ...]`, `moved_by_slot: tuple[bool, ...]`.
  - `plan_demo(*, seed: int = RANDOM_SEED) -> DemoPlan`; raises `RuntimeError` when the stage
    isn't cleared and left within `FRAME_LIMIT`.
  - `main` gains `--demo` to print the demo's plan.
- One shared stepping loop serves `plan_route` and `plan_demo` (a steering callable per frame
  returning the frame's `InputSnapshot`); `plan_route`'s result is unchanged (its tests prove it).
- Pads are steered on the joystick layer, as scripted sessions force: `device_axes` 0 and 1
  (full deflection, -1.0 or 1.0) and the fire button (`controls.py`'s fire button number) in
  `device_buttons`, keyed by instance id; the planning scene's `input_mode` is `joystick`.
- Steering, first cut (the design's starting rules): all fire; slots 0 to 2 each go to the
  nearest standing neighbor no other kid has claimed; slot 3 hunts the nearest live TV, then
  rescues; with no neighbor standing, every kid goes to the gate. The last frame releases
  everything.

- [ ] **Step 1: Write the failing tests**
  - No new test for `plan_route`: the existing `test_the_committed_route_is_still_the_plan`
    pins it; run it before and after the refactor.
  - `test_the_demo_plan_clears_the_stage_and_every_kid_leaves`: `cleared_at < exited_at <
    recording_frames`.
  - `test_every_kid_moves_and_fires_in_the_demo_plan`: all four of `moved_by_slot` and
    `fired_by_slot`.
  - `test_the_demo_plan_destroys_a_tv_zaps_zombies_and_rescues`: each count at least 1.
  - `test_the_demo_plan_ends_with_nothing_held`: every route's last stretch ends at or before
    the last frame with `direction == (0, 0)` and `fire is False` from then on.
  - `test_the_demo_plan_is_twenty_to_forty_five_seconds`: `recording_frames` between 1200 and
    2700 (flag to the owner rather than tune past 45 s).
- [ ] **Step 2: Run; expect failures** (`ImportError: plan_demo`).
- [ ] **Step 3: Implement; tune the steering until the tests pass and the show reads well.**
- [ ] **Step 4: Run; expect passes, `plan_route`'s tests unchanged.**
- [ ] **Step 5: Show the owner key frames** (a contact sheet of about eight frames rendered from
  the plan's run to the scratchpad: the spread, a TV destroyed, a rescue, the clear, the exit).
  Continue on their approval; their notes become steering changes.
- [ ] **Step 6: Commit.**

### Task 3: The demo's recording and its tests

**Files:**
- Modify: `scripts/demo_inputs.py` (the plan's stretches as a constant and the script callable),
  `scripts/record_bundled_demos.py` (the recipe), `tests/workspace_expectations.py`
  (`EXPECTED_BUNDLED_DEMOS`), `T/test_zombies_aint_my_neighbors_package_data.py`.
- Create: `Z/demos/neighborhood_four_kids.jsonl.gz` (recorded).
- Test: `T/test_zombies_aint_my_neighbors_demo_route.py`.

**Interfaces:**
- Consumes: `plan_demo`, `KidStretch` (Task 2); `DemoNeighborhoodScene` (Task 1).
- Produces:
  - `ZOMBIES_DEMO_ROUTES: tuple[tuple[KidStretch, ...], ...]` and
    `ZOMBIES_DEMO_FRAME_COUNT: int` in `scripts/demo_inputs.py` (pasted from the plan's print);
    `zombies_demo_script() -> InputScript` (the keyboard by held keys, as the golden's
    `held_keys_script`; each pad by its axis and button events, from its stand-in's instance id).
  - `ZOMBIES_DEMO_PADS`: three `DeviceDescriptor`s, instance ids from `DEMO_PAD_INSTANCE_IDS`.
  - Recipe `'zombies_aint_my_neighbors_four_kids'`: scene
    `zombies_aint_my_neighbors.demo_neighborhood:DemoNeighborhoodScene`, `polled_input=True`,
    `stand_in_devices=ZOMBIES_DEMO_PADS`, package `zombies_aint_my_neighbors`, name
    `neighborhood_four_kids.jsonl.gz`.

- [ ] **Step 1: Write the failing tests**
  - `test_the_committed_demo_routes_are_still_the_plan`: `ZOMBIES_DEMO_ROUTES ==
    plan_demo().routes` and the frame count equal.
  - `test_the_shipped_demo_shows_what_was_promised`: plays the shipped demo back
    (`start_playback`, `step_finishing`, as the golden route test) reading the scene each frame:
    four kids each move and fire, a TV destroyed, a zombie zapped, a neighbor rescued, the
    stage cleared, every kid out through the gate, no `STAGE 2` card scene started.
  - The package-data test names the demo; `EXPECTED_BUNDLED_DEMOS` gains
    `('zombies_aint_my_neighbors', 'neighborhood_four_kids.jsonl.gz')`.
- [ ] **Step 2: Run; expect failures** (the demo file is missing).
- [ ] **Step 3: Record:** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m
  scripts.record_bundled_demos --demo zombies_aint_my_neighbors_four_kids`.
- [ ] **Step 4: Run; expect passes, with `tests/replay/test_bundled_demos.py` (it replays every
  shipped demo and checks nothing is held at the end) and `uv run glitchygames verify`.**
- [ ] **Step 5: Commit** (the recording, the inputs, the recipe and the tests together).

### Task 4: The attract scene

**Files:**
- Create: `Z/attract.py`.
- Modify: `Z/title.py` (`INNER_GAMES = 1`).
- Create: `T/test_zombies_aint_my_neighbors_attract.py`.

**Interfaces:**
- Consumes: the shipped demo (Task 3).
- Produces:
  - `DEMO_SIZE: Final = (800, 480)`; `DEMO_NAME: Final = 'neighborhood_four_kids.jsonl.gz'`.
  - `attract_demo_path() -> Path | None`: the shipped demo through `glitchygames.bundled_demos`
    (package `zombies_aint_my_neighbors`), None when it isn't installed. Tests patch it through
    the module (`attract.attract_demo_path`), as feature 12's `launch_showing` is.
  - `AttractScene(PadTolerantScene)`, `NAME = 'Attract demo'` (since 2026-11-19 `f'{text.GAME_NAME} - Demo'`, the owner's naming), no constructor arguments beyond
    `options` and `groups`; `inner_game: InnerGame | None`.
  - `DemoPicture(RootSprite)`: full screen; each frame copies the inner surface, scaled to fit
    the screen, letterboxed in `BACKGROUND_COLOUR` when the aspect differs.
  - `DemoLabel`: "DEMO" in the game's text style (`text.py`), in front.
  - Hand-over (once, guarded as the intro's): `TitleScene(options=..., opening=False,
    awaiting_release=True)` after a press, and `TitleScene(options=..., opening=False)` after
    the demo ends or fails.

- [ ] **Step 1: Write the failing tests** (a short recording made in `tmp_path` with the
  scripted-session recorder stands in for the shipped demo where the full demo isn't needed)
  - `test_the_attract_scene_shows_the_demo_and_its_label` (pixels: a lawn pixel where the replay
    draws lawn; the label's pixels).
  - `test_the_picture_is_scaled_to_a_screen_of_another_size` (a `--resolution` of 1600x960 and
    one of 1280x720: the replay is never refused, the picture fills or letterboxes).
  - `test_the_demo_ends_into_a_fresh_title`.
  - `test_a_missing_or_failing_demo_returns_to_the_title_with_a_warning` (parametrized: path
    None, an unreadable file, a recording at another size; `caplog` holds one warning).
  - `test_any_key_or_pad_button_returns_to_the_title` (parametrized: P, Escape, a letter, a
    controller button, a joystick button; on the first frame, mid-way, on the last frame).
  - `test_releases_sticks_and_pads_arriving_change_nothing`.
  - `test_skipping_the_demo_silences_it` (Review focus 3).
  - `test_the_demo_plays_again_after_each_way_it_can_end` (Review focus 2; parametrized: its
    end, a skip, a failure, the game quitting while it plays; `finish()` ran exactly once; a
    second scene builds and steps).
  - `test_no_real_pad_rumbles_while_the_demo_plays` (a stand-in pad on the outer game,
    `tests/input/stand_in_devices.py`; the full demo, which destroys TVs).
  - `test_the_title_declares_one_inner_game`; both goldens replay unchanged.
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement.** The inner game is built in `setup()`, made audible, finished in
  `cleanup()` exactly once.
- [ ] **Step 4: Run; expect passes; the goldens' replay tests unchanged.**
- [ ] **Step 5: Commit.**

### Task 5: The loop

**Files:**
- Modify: `Z/intro.py` (`_act`'s END), `Z/title.py` only if Review focus 1 needs it.
- Test: `T/test_zombies_aint_my_neighbors_intro.py`, `T/test_zombies_aint_my_neighbors_title.py`.

**Interfaces:**
- Consumes: `AttractScene` (Task 4).
- Produces: the loop showing's END hands over to `AttractScene(options=...)`; the launch
  showing's END and every skip to the title, as now.

- [ ] **Step 1: Write the failing tests**
  - `test_the_loop_intro_ends_into_the_demo`.
  - `test_the_launch_intro_ends_into_the_title`.
  - `test_a_skip_from_the_loop_intro_goes_to_the_title_not_the_demo`.
  - `test_a_press_on_the_hand_over_frame_still_returns_to_the_title` (Review focus 1).
  - `test_a_recorded_run_that_idles_into_the_demo_replays` (Review focus 4; `IDLE_SECONDS` and
    the intro's END shortened with `mocker.patch`; the stand-in recording from Task 4).
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; expect passes.**
- [ ] **Step 5: Commit.**

### Task 6: Where it runs, the records, the gate

**Files:**
- Modify: this file's Status and a "Measured" note; `plans/2026-11-14-zombies-aint-my-neighbors.md`
  (feature 13 BUILT, the "What is left of level 1" item, the wishlist if the browser or the Pi
  can't play it); `docs/games/zombies_aint_my_neighbors.md` (the loop's chart and "The intro
  and the idle loop" section gain the demo).

- [ ] **Step 1: Measure the demo's build** (the `AttractScene.setup()` time, five runs, on the
  Mac; on the Pi when it is back up; `clock.measured_seconds`, in a script in the scratchpad,
  never in the suite). Over a second: bring it to the owner (Review focus 5).
- [ ] **Step 2: The browser:** build the bundle (`nox -s browser -- zombies-aint-my-neighbors`)
  and ask the owner to let the loop reach the demo. If it can't play there, add the skip check
  the design names (the loop's intro then ends into the title in the browser) with its test,
  and a wishlist row.
- [ ] **Step 3: Update the plans and the docs above.**
- [ ] **Step 4: Run the whole gate** (ruff format and check over `src tests scripts noxfile.py`,
  basedpyright, ty, `pytest`); 100% coverage; fix findings first.
- [ ] **Step 5: Commit.**
