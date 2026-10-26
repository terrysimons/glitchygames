# GlitchyGames Arcade: a showcase and game picker (`uv run glitchygames`) — master spec

Status: SPEC (agreed with the user 2026-10-25; drafted 2026-10-23), not started. Tracked as
feature #43 in `plans/future-features.md`. This is the master plan: each piece below gets its own
sub-plan, linked both ways from here (sub-plans link back to this file).

Mockup (the owner's, 2026-10-25): https://claude.ai/artifact/3QKddtTADVqC1LVpvDSQSD, the screen with
real frames from each game's golden replay (a 5x2 grid of ten tiles; the tile count is still open).

## What it is

A `glitchygames` console script, from the Arcade app at `src/apps/arcade/` (its own workspace
package, distribution `arcade`; the owner, 2026-10-25), and a browser bundle (`nox -s browser -- glitchygames`) that open an arcade front end for every
game the engine ships. One screen, one process (the browser cannot start child processes:
Pyodide has no subprocesses, which is why Bitmappy's AI worker is off there and replay restarts
only show a message there).

```
+------------------------------------------------------------------+
|                                                                  |
|                                                                  |
|              CLOCKWORK KEEP: the same frames as its              |
|              tile below, scaled up, with sound                   |
|                                                                  |
|                                                                  |
+------------------------------------------------------------------+
====================================================================  <- separator
 +------------------+   +------------------+   +------------------+
 |                  |   |                  |   |                  |
 |   (demo, live,   |   |   (demo, live,   |   |   (demo, live,   |
 |     silent)      |   |     silent)      |   |     silent)      |
 |                  |   |                  |   |                  |
 +------------------+   +------------------+   +------------------+
      PaddleSlap          Brave Adventurer      Brave Adventurer:
                                                     Papyrus
 #==================#   +------------------+   +------------------+
 #                  #   |                  |   |                  |
 #   (demo, live;   #   |   (demo, live,   |   |   (demo, live,   |
 #    shown above)  #   |     silent)      |   |     silent)      |
 #                  #   |                  |   |                  |
 #==================#   +------------------+   +------------------+
  >> Clockwork Keep <<       Mr. Muncher             Bitmappy

 +------------------+   +------------------+   +------------------+
 |                  |   |                  |   |                  |
 |   (demo, live,   |   |   (demo, live,   |   |   (demo, live,   |
 |     silent)      |   |     silent)      |   |     silent)      |
 |                  |   |                  |   |                  |
 +------------------+   +------------------+   +------------------+
        dt demo             Joystick demo        Text input demo
```

- **Top frame:** the reel. It cycles through the games: for each, colour bars with the chime for
  about 3 s, then that game's demo with sound. What it shows is the highlighted tile's own
  player, scaled up with its sound on: one player per game, so the top and its tile are always
  in step. When the reel moves on, the bars and chime play in the top frame while the
  highlight moves to the next tile; that tile's demo keeps running underneath, and the top
  joins it wherever it is (it is never restarted for the top).
- **Separator:** a horizontal rule between the top frame and the grid.
- **Grid:** one boxed tile per game, its title below the box: all nine (the five example games,
  Bitmappy, and the dt, joystick and text input demos), a 3x3 grid. Every tile plays its game's
  demo live, silent, at the same time (real playback, not pre-rendered images). The tile shown
  in the top frame is highlighted.

### The chime

Original and pleasant, played over the bars (never a held test tone, never the emergency
broadcast's two-tone chord, never a broadcaster's trademark chimes):

- a gentle rising major arpeggio, C5 → E5 → G5 → C6, about 0.4 s apart;
- soft sine tones with a bell envelope (quick attack, long smooth decay), each ringing into the
  next; quiet (about 20% of full scale, well under a demo's sound), lightly low-passed, so warm
  rather than bright;
- the last note fades as the bars hand over to the demo; together about 3 s;
- a synth recipe (`src/glitchygames/audio/recipes.py`), rendered to a file for the user to listen to
  and adjust before it is wired in.

### Input

- **Move the highlight:** arrow keys, the d-pad or left stick, mouse hover, a tap. This takes
  over from the reel: the top switches straight to that tile's demo with its sound (no bars or
  chime, so browsing feels immediate) and the automatic cycling pauses.
- **Launch:** Enter, A or Start, a click, a tap.
- **Back to the reel:** about 30 s with no input, the reel resumes from the highlighted game,
  with bars and chime.
- **Quit the Arcade:** Esc, or B or Back on a gamepad (desktop). The browser version has no quit,
  as the games there have none.
- **In a launched game:** its own controls, keyboard and gamepad as the engine gives every game;
  its own quit comes back to the Arcade with the highlight still on that game.

## Architecture

### 1. The engine context (the D1 refactor)

Today the engine's per-run state is process-wide: the `SceneManager` singleton, the doors
(`src/glitchygames/sources.py`), the random streams (`src/glitchygames/randomness.py`), the frame clock,
the saves and the live audio. It moves into one `EngineContext` object. Ordinary games run in a
single default context and do not change. The Arcade creates one context per demo player and
switches into it around that player's frames; a launched game gets a fresh context of its own.

This is the largest and riskiest piece, so it gets its own master plan and sub-plans. Its guard:
the whole existing suite, every golden replay, the golden traces and the bundled demos pass
unchanged in the default context.

### 2. One playback core, then `DemoPlayer`

The engine already plays recordings four ways: the headless replay (`replay/driver.py`), the
watched replay's viewer (an outer game ticking an unpresented inner one), the playback scope
(`play_recording` demos and instant replay) and the rebuild that restarts a watched replay at a
frame (`replay/rebuild.py`). `DemoPlayer` must not be a fifth (DRY). First an audit maps what
each does and where they overlap (inner-frame ticking, the accumulator and budget,
`hold_frame`, scene rebuilding, input blocking, sandboxed saves, fast-forwarding); the shared
core becomes one inner-game runner, and the viewer, the playback scope and `DemoPlayer` are
rebuilt on it. Guard: every existing replay, demo and instant-replay test passes unchanged.

`DemoPlayer` wraps one recorded game in its own context:

- `tick(real_seconds, budget_seconds)`: runs the recorded frames that real time calls for, within
  the budget; frames owed past the budget carry over (slow motion), never skipped (a replay must
  run every frame to stay correct);
- the latest frame as a surface (never presented to the window);
- sound on or off (a muted player gets a silent audio context: its sounds never reach the mixer);
- its outcome (playing, looped, could not start, diverged, crashed);
- it loops: a demo reaching its end restarts from its own first frame, in its own context;
- `fast_forward(to_frame=N)`: runs frames 0..N-1 as fast as the machine allows, unpresented,
  unpaced and silent, within a time budget per Arcade frame (so the screen stays responsive),
  then shows frame N. It is the playback core's one fast-forward: the watched replay's rebuild
  (frames 0..N-1 before it pauses) and instant replay (`MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`)
  use it too. Rewind is later (it needs the state snapshots in `plans/future-work.md`).

**Poster frames.** At startup each tile picks a frame of its demo from the Arcade's seeded random
stream (`random_stream('arcade-posters')`) and fast-forwards there; meanwhile it shows its title
on the default test pattern, then the poster frame as a still; once every player is ready, each
plays live from where it stopped. The nine tiles therefore start at different points of their
demos, every run picks new frames, and a test reproduces any run from its seed.

The watched replay's viewer (`src/glitchygames/replay/viewer.py`: an outer game ticking an
unpresented inner game through `EngineSources.hold_frame`) is the model; its docstring already
lists "inner frames handed to a sink rather than presented" as a later user of that contract.

### 3. The Arcade

`src/apps/arcade/arcade/` (the app's package), an ordinary outer game: its scene holds nine `DemoPlayer`s, draws the
top frame, separator and grid, runs the reel (bars, chime, demo) and the highlight, and shares
the frame budget. One Arcade frame:

1. Read input in the Arcade's context (highlight, launch, quit, idle time).
2. Run the reel: hold the bars and chime for 3 s, or show the highlighted game.
3. Run the top player first, for as many of its recorded frames as real time calls for: full
   speed, sound on.
4. Share what is left of the frame budget (`INNER_FRAME_BUDGET_SECONDS`, as the watched replay
   uses) among the other eight, round-robin so none starves; a tile behind plays in slight slow
   motion, never stutters.
5. Draw each player's latest surface scaled into its box (aspect kept, letterboxed), the top
   frame from the same surface larger, then the separator, titles and highlight; present once.

Players never present to the window and never see real input: real input goes to the Arcade
only, as the watched replay's controls get it today.

### 4. Launching in the same process

The Arcade's `pyproject.toml` lists every game, demo and app it shows as a dependency (workspace
sources), so installing the Arcade installs them; a test keeps that list equal to the games,
demos and apps layers (adding a game without adding it to the Arcade fails the suite). Each of
them declares itself through an entry point (e.g. `[project.entry-points."glitchygames.games"]
paddleslap = "paddleslap:GAME"`: display name, demo recording, scene and startup: options,
`NAME`, `TARGET_FPS`), and the Arcade discovers them that way, knowing no module names (the
owner, 2026-10-25; it fits the recording ids of plans/future-features.md #55). The exact
entry-point contract is this sub-plan's to define. Launching builds the game in a fresh context and runs it until it quits; then
the Arcade's context comes back. The window takes the game's resolution, and the Arcade's again
after.

### 5. Demos for all nine

One recording per game, bundled inside each game's own package (`<package>/demos/<name>.jsonl.gz`,
e.g. `src/games/paddleslap/paddleslap/demos/rally.jsonl.gz` after the migration), recorded with `scripts/record_scripted_session.py --script-only
--output PATH`, each replayed headless by `tests/replay/test_bundled_demos.py`. Bitmappy's shows a
sprite being drawn; the joystick demo's shows its readout answering a recorded pad.

## Errors and odd cases

- **A tile still fast-forwarding to its poster frame:** its title on the default test pattern
  (never blank); the reel does not show it until it is ready.
- **A demo that cannot play** (missing, unreadable, an older format): its tile shows the default
  test pattern with its title and a small "no demo" label; the game can still be launched; the
  reel skips it; logged once at WARNING (as `play_recording` logs "No demo: ...").
- **A demo that diverges** (the code changed): the tile restarts its demo and goes on, logged
  once. Tests catch this long before: every Arcade demo is a bundled-demo test.
- **A player that raises:** that player stops, its tile freezes on its last frame with an
  "error" label, the traceback is logged, the reel skips it; the Arcade and the other players
  go on. An error in the Arcade itself goes through the engine's crash boundary and exit codes.
- **A launched game that crashes:** its context is torn down, the traceback logged, and the
  Arcade comes back with "<game> stopped: error" (in the browser this keeps the page alive).
- **A launched game's `sys.exit()` or quit** ends the game, not the Arcade.
- **Saves:** demos play against in-memory saves only (`MemorySaveManager`), never the real ones;
  a launched game uses its real saves, as when started on its own.
- **Window size:** the Arcade's window is its own size; tiles keep their aspect ratio,
  letterboxed; a launched game gets its own resolution.

## Testing

- **Engine context:** the existing suite, every golden replay, the golden traces and the bundled
  demos unchanged in the default context. New tests run two contexts in one process and prove
  nothing leaks between them: random streams, frame clocks, doors, saves, and sound only from the
  context that has it.
- **The playback core:** the viewer, the playback scope, the rebuild and instant replay pass
  their existing tests unchanged on it.
- **`DemoPlayer`:** its frames equal a headless replay of the same recording, frame for frame,
  also beside other players and in slow motion; looping restarts cleanly; a missing, diverging
  or crashing demo gives the outcomes above.
- **Fast-forward:** frame N after `fast_forward(to_frame=N)` equals frame N of a headless replay;
  it keeps within its budget per Arcade frame; poster frames come from the seeded stream (the
  same seed, the same frames).
- **The budget:** with a stand-in clock, the top player always gets its frames and the tiles
  share the rest in turn; none starves.
- **The screen, by pixels:** the top frame, the separator, nine boxes with titles, the highlight
  on the right tile, the "no demo" and "error" tiles.
- **Input:** keyboard, mouse, touch and gamepad (`tests/input/stand_in_devices.py`) moving,
  launching and the idle time-out.
- **Launch and return, every game:** launch, play briefly, quit, and the Arcade is back with the
  highlight on that game.
- **The chime:** its waveform has the four notes, the level and the fades; a rendered file to
  listen to.
- **Browser:** the Arcade bundle builds and `nox -s browser -- glitchygames` runs it.

## Sub-plans (each written before its work starts, linked both ways)

1. **Engine context** (its own master plan with sub-plans,
   [2026-10-25-engine-context.md](2026-10-25-engine-context.md)): `EngineContext`, the default
   context, switching, the isolation tests. First.
2. **Audit and refactor playback into one core, then `DemoPlayer`:** the audit, the shared
   inner-game runner, the viewer and playback scope on it, fast-forward, the frame budget,
   poster frames.
3. **Demos for all nine games** (can run beside 1 and 2).
4. **The Arcade screen, reel and chime:** the app `src/apps/arcade/`, the console script, layout,
   highlight, input, idle time-out, the chime recipe.
5. **Launching in the same process:** discovery by entry point, fresh contexts for games, return,
   window size.
6. **The browser bundle:** `nox -s browser -- glitchygames`.

## Decisions (the user, 2026-10-23 and 2026-10-25)

- The Arcade is an app, `src/apps/arcade/` (2026-10-25): not in the engine (the engine cannot
  depend on the games that depend on it) and not in `src/games/` (it is not a game, so every
  "for each game" rule stays exceptionless). It depends on every game, demo and app it shows,
  kept equal to the layers by a test, and discovers them by entry point. Where it appears in the
  showcase (first on the play page) is presentation, not its directory.
- **Open:** the tile count. The grid was drawn as 3x3 for nine (five games, Bitmappy, three
  demos); Drawing Fire makes ten. To decide before the screen sub-plan: a 4x3 grid with two
  empty cells, a scrolling grid, or which entries get a tile.

- One process, in-process engine contexts (D1); child processes are not a fallback (the browser
  has none). Launching a game is in-process too.
- One screen: the top frame and the grid together, a separator between them.
- The top frame is the highlighted tile's own player, scaled up, with sound; tiles are live,
  silent playback of every game's demo at once.
- All nine games get a tile.
- `DemoPlayer` is built on one playback core refactored out of the existing four (DRY), not a
  new mechanism; it gets fast-forward now (shared with rebuild and instant replay), rewind later.
- Tiles start on a poster frame: a frame chosen from the seeded random stream, reached by
  fast-forwarding, shown as a still, then played live from there.
- Bars about 3 s with an original, pleasant chime (the rising major arpeggio above).
- When the machine cannot keep up: the top runs at full speed, the tiles share the rest and fall
  into slow motion.
- Input as above: browsing takes over from the reel, launch by Enter/A/Start/click/tap, quit
  returns to the Arcade, 30 s idle resumes the reel; full gamepad support.

## Options considered and set aside (2026-10-23)

- **A. Pre-rendered thumbnail strips** per tile: cheap, but stale when a game changes, and the
  user wants live playback.
- **B / D2. One child process per tile:** not possible in the browser.
- **C. Several engines in one process:** this is D1, chosen; called invasive then, it is now
  planned as the engine context refactor.
