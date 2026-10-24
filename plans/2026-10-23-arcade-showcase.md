# GlitchyGames Arcade: a showcase and game picker (`uv run glitchygames`) — design draft

Status: DESIGN DRAFT (2026-10-23), not started. Tracked as feature #43 in
`plans/future-features.md`. Decisions still open are marked **Open**.

## What it is

A `glitchygames` console script (`[project.scripts] glitchygames =
"glitchygames.arcade:main"`) that opens an arcade front end for the example games:

```
+--------------------------------------------------------------+
|                 DEMO REEL (one demo, with sound)              |
|   PaddleSlap demo ... [colour bars 3 s] *beep* Clockwork ... |
+--------------------------------------------------------------+
| [PaddleSlap]  | [Clockwork Keep] | [Brave Adv.] | [Papyrus]  |
|  replay loop  |   replay loop    | replay loop  | replay loop |
+---------------+------------------+--------------+------------+
| [Mr. Muncher] |  ...                                         |
+---------------+----------------------------------------------+
```

- **Demo reel (top):** one game's demo at a time, with sound. Between demos the reel shows the
  engine's colour bars (`BackgroundPattern.TEST_PATTERN`) for a few seconds, then a beep (a synth
  recipe, like Mr. Muncher's 1 kHz film-leader `countdown_beep`), then the next game's demo.
- **Game grid (below):** one boxed tile per game, each looping that game's replay silently, with
  its name. Arrows, WASD or a gamepad move a highlight; Enter, Space or A starts the game.
- **Playing:** the chosen game runs as the engine normally runs it. When it ends (quit or
  game over and ESC), the arcade comes back.

## The constraint that shapes everything

The engine plays recordings through one `SceneManager` singleton with at most one playback
scope at a time (`glitchygames/replay/playback.py`). Random streams, the frame clock, the doors
(`glitchygames/sources.py`) and saves are process-wide. So **one process can play one demo live,
not a grid of them at once.** The reel fits the engine as is
(`SceneManager.play_recording(path=..., then=...)`); the grid needs another approach.

### How the grid tiles get their moving pictures — options

Worked example: five games, tiles of 240x144 (the 800x480 games scaled by 0.3), 20 s loops.

- **A. Pre-rendered thumbnails (recommended to start).** A build step (a script, and a nox
  session) replays each game's demo headless with `--replay-trace ... --headless` and saves every
  Nth frame, scaled down, to an image strip under `glitchygames/examples/<game>_demos/` (or a
  cache). At 15 fps and about 6 KB a JPEG frame, a 20 s tile is about 1.8 MB, and five games
  about 9 MB. The arcade only flips images: cheap, smooth, no engine changes. The cost is a
  build step, a size budget and strips going stale when a game changes. A test can check that
  each strip is newer than its recording.
- **B. One child process per tile.** Each child replays headless and streams small frames back
  over a pipe (`glitchygames.process`). The tiles are always fresh, but that is five extra
  pygame processes (CPU on the user's machine) plus the pipes and lifecycle to manage.
- **C. Several engines in one process.** The SceneManager, doors, streams and clocks would have
  to become per-instance. That is the most invasive option and is not worth it for a menu.

**Direction from the user (2026-10-23):** the gallery should be *a game that wraps the game
wrapper that runs demos, and can do multiple*. That is option D below, which takes the place of
A to C as the plan; A to C stay as notes.

- **D. The gallery is an outer game hosting several demo wrappers.** The engine already has the
  wrapper. A watched replay is "a read-only game inside a game" (`glitchygames/replay/viewer.py`):
  - The OUTER `ReplayViewer` owns the window, ticks at 60 Hz in real time and presents.
  - The INNER recorded game runs whole frames at its recorded times, unpresented
    (`EngineSources.presents_frames` False).
  - They meet in the `EngineSources.hold_frame` contract. The viewer's docstring already lists
    "inner frames handed to a sink rather than presented" as a later user of that contract.

  The gallery generalises this: an outer `GalleryScene` owns the window and holds N
  `DemoPlayer`s. Each one wraps one inner recorded game, has its own accumulator, and hands its
  latest frame to a sink: a tile, or the reel's band. One player has sound on (the reel); the
  others are muted.
- **What "can do multiple" needs.** Today the inner game is the process's only `SceneManager`,
  with process-wide doors (`sources.py`), random streams, frame clock and saves. A `DemoPlayer`
  needs those per player. There are two ways to get them:
  - **D1, in-process:** an engine context object (scene manager, doors, streams, clocks, saves,
    live audio) that each `DemoPlayer` owns and switches in around its inner frames. This is
    the engine refactor that option C called invasive. It is the cleanest end state, and it is
    what "a game that wraps the wrapper" literally means.
  - **D2, child process per player:** each `DemoPlayer` runs its inner game in a headless child
    (`glitchygames.process`) and sends frames over a pipe to its sink. The `DemoPlayer`
    interface is the same, so D1 can replace it later without touching the gallery.
  - Either way, the first step is the same: define the `DemoPlayer` interface (start a
    recording, `tick(real_seconds)`, latest frame as a surface, muted or not, ended or diverged
    outcome). Then turn the current single watched replay into its first implementation.
- **Game-ception: what we already have, and what is missing.**
  - Have:
    - The outer/inner loop and its `hold_frame` contract (the watched replay viewer).
    - Unpresented inner frames (`presents_frames`).
    - A live game hosting a replay (playback scopes: `play_recording`, instant replay), with
      its voices paused behind it.
    - Scene rebuilding from recordings (`scene_start.py`).
    - Sandboxed saves (`MemorySaveManager`) and recorded devices.
    - Headless child replays (`--replay-trace --headless`, `glitchygames.process`).
  - Missing:
    - More than one inner game at a time. The doors, streams, clocks and scene manager are
      process-wide, and only one playback scope exists.
    - Handing an inner frame to a sink (a tile) rather than the window.
    - Muting per inner game.
- **Open:** D1 now (engine context refactor, its own master plan and sub-plans), or D2 first
  with D1 later?

### The demo reel

- Each game ships a demo recording. PaddleSlap already has `paddleslap_demos/rally.jsonl.gz`.
  The others record theirs with `scripts/record_scripted_session.py --output ...`; their golden
  replays could serve for a start.
- The reel is an arcade `Scene` that cycles through three states: colour bars (about 3 s), a
  beep, then `play_recording(path=..., then=self)` for that game's demo. `last_playback_outcome`
  says when the demo ended, and the cycle moves to the next game.
- **Sound:** the demo plays with sound. The grid tiles are images or silent children, so only
  the reel makes noise.
- **Open, layout:** `play_recording` presents a whole frame. To show the demo in the top band
  rather than full screen, the playback scope needs a presentation target or region. That is an
  engine change (a "present into this rect, scaled" option on the playback), so it gets its own
  sub-plan. A first version could alternate full-screen attract mode (bars, beep, demo) with the
  menu screen instead of showing both at once.

### Starting a game and coming back

- **Simplest:** launch the game's console script as a child process
  (`glitchygames.process.run_command`) and wait. The arcade's window hides or minimises, and
  the game gets a clean engine (singletons, seeds, saves) of its own.
- **Alternative:** switch scenes in-process with `GameEngine.game` set to the chosen scene. The
  engine's per-game bootstrapping (options, `NAME`, `TARGET_FPS`) makes this harder, so the
  child process is the recommendation.

## Pieces (each a sub-plan later, linked both ways from here)

0. The `DemoPlayer` wrapper interface and the multiple-inner-games backend (option D: D1
   engine context, or D2 child processes); the reel and the tiles are both `DemoPlayer`s.

1. `glitchygames/arcade/` package, `main()`, the console script, an `ArcadeScene` with the grid
   menu (highlight and launch).
2. A registry of games: console script, display name, demo recording, tile strip. Derived from
   `[project.scripts]`, as `glitchygames.testing.replays.console_script_in_module` already does.
3. Demo recordings for every game, plus a test that replays each (as
   `tests/replay/test_bundled_demos.py` does for PaddleSlap).
4. Tile strips (option A): a builder script, a nox session and a freshness test.
5. The reel: bars, beep and demo, cycling. Then the engine change to play a demo into a region.
6. Launching a game as a child process and returning; window handling on macOS.

## Open questions for the user

- Option D: D1 (per-player engine context in one process) or D2 (child processes) first?
- The reel and grid on one screen at once (needs the engine change), or alternating
  full-screen attract mode and menu for a first version?
- How long the colour bars show (about 3 s?), and which beep (the 1 kHz film-leader one?).
- Which games: the five examples only, or also the demos (dt_demo, joystick_demo,
  text_input_demo)?
- Does picking a game play its sound from the reel's demo until the game starts?
