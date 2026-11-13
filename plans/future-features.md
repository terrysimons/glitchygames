# Future Features for GlitchyGames

> Moved from the repository root (`FUTURE_FEATURES.md`, previously untracked) into `plans/` on
> 2026-10-18. Newer plans: `plans/engine-audit.md` (engine roadmap), `plans/future-work.md`
> (backlog) and `plans/2026-10-18-level-tools.md` (Glitchy Studio).
>
> Paths: the editor modules named below (once `tools/bitmappy.py` and the like, in the engine's
> `tools` package) were moved into the `src/glitchygames/bitmappy/` package by the Bitmappy refactor (#87, `4bdc966c`): the editor scene
> is `bitmappy/editor.py`, the film strip `bitmappy/film_strip*.py`, `canvas_interfaces.py` and
> `onion_skinning.py` keep their names, the undo/redo manager and operation trackers are
> `bitmappy/history/undo_redo.py` and `history/operations.py`, the multi-controller manager and
> controller selection `bitmappy/controllers/manager.py` and `controllers/selection.py`, and the
> visual collision manager `bitmappy/indicators/collision.py`. `src/glitchygames/tools/` now holds only
> the ASCII renderer (`ascii_renderer.py`, `charmap.py`, `terminal_utils.py`). Other
> `src/glitchygames/tools/...` files listed under planned features were never created. The
> entries below name these files at their present paths.

This document tracks planned future features for the GlitchyGames project. Features are listed in priority order and will be implemented as time and priorities allow.

## High Priority Features

### 63. Sound Engine: One-Call Sound API, Instruments and the CRT's Sound — M1 BUILT
- **Description**: sound becomes a first-class retro feature (the user, 2026-11-02). One call,
  `audio.sound(...)`, takes a short name, a path or an `Instrument`. The first request compiles
  the sound, later requests return it from the engine's cache, and getting a sound never plays it
  ("the way you load it is the same as the way you'd use it in the game - one API"). Pitches can
  be notes, hertz, MIDI or scale steps, side by side. Named waves can be mixed, blended, put in
  wavetables, drawn as points or built from harmonics, with named constants for their numbers.
  TOML instruments; live sounds driven by game parameters; buses; offline render to WAV; retro
  profiles; demos (Sound Board first).
- **Spec**: `docs/specs/2026-11-02-sound-engine-feature-spec.md` and
  `docs/specs/2026-11-02-sound-engine-implementation-spec.md` (from the user's brief,
  `~/Documents/ChatGPT/GlitchyGames/glitchygames-sound-engine-development-brief.md`)
- **Order (the user, 2026-11-02)**: M1 the one-call API (pitch and wave types, notes and chords,
  the cache as `None`/`'ram'`, per-frame audio accounting, buses and voices, offline render, the
  CRT power-on sound (#53's follow-up), the Sound Board demo); M2 live instruments, migration of
  all five games and removal of the old sound paths; M3 measurement with the cache off, then
  `'ram'`, then `'disk'`, with a *Sound Performance* docs page of plots; then instrument depth,
  music and authoring
- **Status**: M1 BUILT on `docs/sound-engine-specs` (2026-11-02; plan
  `plans/2026-11-02-sound-engine-m1-implementation.md`, user docs `docs/architecture/sound.md`):
  the one-call API, pitches and waves, sound files, the `none` and `ram` caches, accounting,
  voices and buses, the Audio debug panel, offline render, the CRT power-on sound and the Sound
  Board. The owner's listening check passed (2026-11-02: the Sound Board, the CRT power-on and
  its skip with no clicks, and the browser build). The instrument catalog (2026-11-03, the
  owner's "every instrument, every variant"): `glitchygames.audio.instruments`, 431 instruments
  in 18 families with their ranges, voices from soprano to basso profundo on five vowels
  (`docs/architecture/sound.md`, "The instrument catalog"), audited against published references
  the same day: 28 ranges, the soprano and tenor "o" formants and the chime, bell and tine
  partials corrected. M2 next, in the order above
- **Priority**: High (requested 2026-11-02)

### 1. Memory Optimization
- **Description**: Implement configurable buffer sizes and automatic cleanup for long-running games
- **Use Case**: Reduced memory footprint for extended gameplay sessions, 5 9s reliability (100,000+ data points)
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - Increase FPS history buffer to 100,000 frames
  - Add configurable buffer sizes
  - Implement automatic cleanup for memory management

### 2. Real-time Performance Monitoring
- **Description**: Add live performance dashboard during gameplay with FPS overlay and performance warnings
- **Use Case**: Essential for debugging and performance monitoring during development
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - Refactor existing FPS blit functionality
  - Add live FPS counter overlay
  - Implement performance warnings (FPS drops, memory usage)
  - Track sprite count and memory usage
  - Estimate CPU usage from frame times
- **Progress**: the FPS overlay is done: the debug overlay's performance panel
  (`src/glitchygames/debug/`, `--debug-overlay` / F3) shows FPS, frame time, the 1% low and a
  frame-time graph. Warnings, sprite count and memory usage are still open.

### 3. Enhanced Metrics Collection
- **Description**: Comprehensive performance metrics beyond basic FPS tracking
- **Use Case**: Better performance insights and bottleneck identification
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - Frame time variance (jitter analysis)
  - Input lag measurement
  - Audio latency tracking
  - Network performance (for multiplayer)
  - GPU utilization (if available)

### 43. GlitchyGames Arcade: Showcase and Game Picker (`uv run arcade`) — TODO
- **Description**: An `arcade` console script that opens an arcade front end. A demo reel
  across the top plays each game's demo with sound, with the colour bars for a few seconds and
  a beep between games. Below it, a boxed grid of the games, each tile looping its replay
  silently; pick one to play it.
- **Status**: TODO: spec agreed 2026-10-25 in `plans/2026-10-23-arcade-showcase.md` (the master
  plan): one screen, one process (the browser has no child processes), nine live silent tiles
  under a top frame showing the highlighted one with sound, an original chime over the bars.
  First sub-plan: the engine context (one per demo player); its sub-plan 1 (state:
  EngineContext, the default context, six pieces of state moved) is done, and its sub-plan 2
  (the engine's own state per context, the read-only views and the guards; the Arcade's
  sub-plan 1) is done (PR #171, verified and through its performance gate); the Arcade's
  sub-plan 2 (demos for every tile: `plans/2026-11-11-arcade-2-demos.md`, branch
  `arcade-2-demos`) is done: all ten tiles have a bundled demo, recorded by
  `scripts/record_bundled_demos.py`; sub-plan 3 (a game inside the Arcade) is next
- **Priority**: High (requested 2026-10-23)

### 46. Recording Metrics: History, Headroom and Gameplay Analytics — TODO
- **Description**: Historical metrics from what recordings store (frame performance by run and
  commit, a behaviour-change map from the content hashes, pacing steadiness, machine
  comparison, gameplay analytics with game-defined stat events), richer per-frame measurements
  (step timings, GC pauses and memory, drawing cost, audio health), run provenance (git commit,
  machine state, a per-run summary in the header), a run ledger beyond 10 runs with graphs on
  the docs site, and frame headroom: measured, then spent on AI and GPU work through a
  spare-time queue whose results reach the game through the doors (recorded, served in replays)
- **Status**: TODO: design in `plans/2026-10-23-recording-metrics.md` (Parts 0-7, all chosen by
  the user 2026-10-23; open decisions listed there)
  Done: Part 0 (2026-10-23): the engine's source revision, the machine's state and a run
  summary in every run (`src/glitchygames/build_info.py`, `machine_state.py`, `recording_history.py`)
  Done: Parts 1 and 2 (2026-10-23): the run ledger on gh-pages (`nox -s replay-metrics`, the docs
  site's Replay Performance page) and `scripts/recording_report.py` (speed changes and the
  behaviour-change map; `src/glitchygames/recording_metrics.py`)
  Done (2026-10-25): measured rows in the repository: a pre-commit hook measures every commit
  that can change the replays into row files keyed by code tree, the docs publish the rows whose
  code landed on main, CircleCI deploys after each merge, and the gh-pages history moved in
  (plans/2026-10-25-measured-rows-in-the-repository.md)
- **Priority**: High (requested 2026-10-23)

### 47. Controller Layout Mapper: PlayStation-Style Pads (PS3, PS4, PS5) — TODO
- **Description**: A game-style tool that draws a PlayStation-ish controller (PS3, PS4 and PS5
  layouts: face buttons, D-pad, shoulders and triggers, sticks and their clicks, Start/Select or
  Options/Share/Create, PS button, touchpad and its click on PS4/PS5, mute on PS5), points at one
  control at a time ("press this"), and records what the pad actually sent for it: the joystick
  layer (button, axis and direction, or hat value) and the controller layer
  (`CONTROLLER_BUTTON_*`/`CONTROLLER_AXIS_*`) when SDL maps the pad. It writes the layout to a
  file (TOML, like sprites) with the controller's information: name, GUID, vendor and product
  ids, whether SDL has a mapping, the instance's button/axis/hat counts, the platform, SDL and
  pygame versions, and when it was recorded. Skip and redo per control; a stick or trigger is
  recorded by moving it past a threshold
- **Why**: the same pad reports different indexes per platform, driver and connection (USB or
  Bluetooth); recorded layouts let games and Bitmappy show the right glyphs, check or build SDL
  mappings, and give the tests stand-in pads that match real ones (the gamepad golden replays,
  feature #44's follow-up, need exactly that). DualSense notes: memory
  `project_dualsense_speaker.md` (HID enable on macOS, button mappings)
- **Status**: TODO: write the plan first (`plans/YYYY-MM-DD-controller-layout-mapper.md`):
  drawing the three layouts, the prompt order, the file format, where layouts are stored (with
  the engine, so tests and games can load them), and how it reads input (through the engine's
  doors and `input_devices`, so a mapping session can itself be recorded and replayed)
- **Priority**: Medium (requested 2026-10-23)

### 48. Make `--use-gfxdraw` Draw With pygame.gfxdraw — TODO
- **Description**: `--use-gfxdraw` (Graphics Options) is parsed and stored as
  `GameEngine.use_gfxdraw`, but nothing reads it: the ball (`game_objects/ball.py`) and paddles
  (`game_objects/paddle.py`) set their own `use_gfxdraw = True`, which nothing reads either
  (BUGS.md #210). Make the option real: shapes the engine draws (the balls' circles, the paddles,
  the primitives editions' figures) use `pygame.gfxdraw`'s anti-aliased forms (`aacircle` with
  `filled_circle`, `aapolygon` with `filled_polygon`, ...) when it is on, and `pygame.draw`
  otherwise
- **Status**: TODO. To settle: which shapes switch (engine game objects only, or a shared drawing
  helper the games use too); whether anti-aliased edges change hitboxes (they are measured from
  visible pixels, `collision/bounds.py`) and so what golden traces and replays compare; the
  default (off keeps today's pixels); and the per-object `use_gfxdraw` attributes, which become
  the option's value or go away
- **Priority**: Medium (requested 2026-10-23)

### 52. Golden Replays With Debugging On: Same Gameplay, Measured Cost — TODO
- **Goal**: show that turning debugging on never changes gameplay, and measure what it costs
  (2026-10-24, the user's idea: parametrize runs on debug off and on, the "on" runs keeping the
  books)
- **Approach**: parametrize the golden replays (not the whole suite: most tests draw no frame)
  over debug off and on (the debug overlay and each of its panels: collision, physics, camera,
  performance; `--debug-events`). The "on" variants must still match every recorded frame (a
  divergence is a bug: debugging changed gameplay), and they keep the books through the existing
  run ledger (`src/glitchygames/recording_metrics.py`, `nox -s replay-metrics`): one more row per
  recording per run, tagged with what debugging was on, so the performance page
  (docs/quality/performance.md) graphs the off and on series side by side across commits and
  machines. Later: the games' own tests (`src/games/<game>/tests`, after the workspace-packages
  plan) take the same parametrization
- **Open questions**:
  - the overlay is drawn when a frame is presented (`SceneManager._present_frame`); headless
    replays do not present, so the overlay may need drawing without presenting, or the measured
    run presents on the dummy driver
  - a replay applies the recorded run's options: the debug options must become replay-local, as
    `--replay-fps` is (`REPLAY_LOCAL_OPTIONS`)
  - whether each panel is its own parametrized case (likely: their costs differ)
- **Status**: TODO

### 53. A CRT Power-On Startup Sequence — BUILT (being tested by the user)
- **Goal**: the engine's startup looks like an analogue CRT switching on, showing the configured
  default background (`--default-background`: the TV test pattern's colour bars, or the channel
  3 blue VCR screen; src/glitchygames/backgrounds.py), flickering like a real set before it settles
  and the game's first scene appears (the user's idea, 2026-10-24)
- **Sequence** (about a second; each stage's timing a constant):
  1. black, then a bright dot in the centre (the electron beam before deflection)
  2. the dot stretches into a thin horizontal line (horizontal sweep), then opens vertically
     into the full picture (vertical sweep), brightest along the line as it opens
  3. warm-up: brightness overshoots and sags, the picture flickers (a few uneven frames of
     brightness, a frame or two of vertical roll or jitter), slight bloom and scanlines, a
     brief degauss-style colour wobble
  4. settles into the steady pattern, then the first scene's frame replaces it
- **Possible extras**: the power-on sound (BUILT 2026-11-02 with the sound engine's M1, #63:
  `src/glitchygames/crt_power_on_sound.py`), a matching CRT power-off collapse when the game quits
- **Rules it must keep**:
  - visual only, before frame 0: never in recordings, screenshots or golden traces, and it
    changes no game state, random stream or clock a replay serves
  - skipped where it would get in the way: `--headless`, replays and audits, the tests (the
    test display rule expects the canvas: tests/display_canvas.py), the browser bundles if it
    delays their first frame noticeably; any key or button skips it
  - an option to turn it off (and probably one to force it on for a replay watched by a person)
  - drawn from the background pattern the run is configured with, at the display's size
    (`BackgroundPattern`, cached per size), opaque on cocoa (src/glitchygames/opacity.py)
- **Where** (the user, 2026-10-24: "wired up to the front of every game"): the engine runs it
  for every game, on the game's own canvas (its display, at its resolution), after the display
  opens and before control is handed to the game: before the first scene's setup and first
  frame, with no input reaching the game while it plays. No game opts in or writes code for it.
  The engine already paints a new display with the default background before the first frame
  (CLAUDE.md, Scene backgrounds); the sequence replaces that single paint
- **Status**: BUILT 2026-10-24 (`src/glitchygames/crt_power_on.py`, plan
  plans/2026-10-24-crt-power-on.md); being tested by the user, the stage constants tuned by eye
  from that. The power-on sound is built (2026-11-02, #63's M1: a power click, the degauss thump,
  the flyback whine, static, then the bars' tone or channel 3's hiss; `--crt-power-on-sound`);
  a power-off collapse is a follow-up

### 57. A pygame-examples-Like Demos Experience — TODO (plan later)
- **Description**: the demos (today `dt_demo`, `joystick_demo` and `text_input_demo`, each a member of the
  demos layer) become a browsable set of small, focused examples of what the
  engine does, in the spirit of pygame's own examples (`python -m pygame.examples.aliens`): easy to
  list and run, each showing one engine feature. They left the engine's examples for the demos
  layer, each its own member (the user, 2026-10-26: `src/demos/dt-demo/`, `src/demos/joystick-demo/`,
  `src/demos/text-input-demo/`, Part 3 of #56), not inside Bitmappy, which takes only its own
  resources (Part 4)
- **Use Case**: a newcomer runs one command, sees what the engine can do and reads short code that
  does it; the demos double as living documentation
- **Status**: TODO: make a plan later; the user has thoughts to bring to it (2026-10-26)
- **Priority**: Medium

### 56. Games, Demos and Apps as Their Own Packages (uv workspace) — IN PROGRESS
- **Description**: the engine moved to `src/glitchygames`; each game, demo and app becomes a
  uv workspace member under `src/games|demos|apps`, with its tests and recordings beside it;
  recordings name games by logical names. Master plan: `plans/2026-10-24-workspace-packages.md`
- **Status**: Part 1 (foundation and the Mr. Muncher pilot) merged (#105); Part 2 (every game
  its own package: mr-muncher, clockwork-keep, brave-adventurer as one project with a launcher,
  paddleslap, drawing-fire) merged (#109); Part 4 (Bitmappy as an app, `src/apps/bitmappy/`)
  DONE on `feature/workspace-packages-4-bitmappy`, not yet merged; Parts 3 (the demos) and 5 (the
  browser IDE) TODO
- **Part 2 leftovers** (deferred review findings, 2026-10-25; none blocks the merge):
  - Brave Adventurer (`src/games/brave-adventurer/`): no golden replay exercises the title
    screen's controls; `tests/engine/test_engine_lifecycle.py`'s power-on test has no direct
    `--game papyrus` case; a recording whose header cannot be read is refused through the title
    flow, so the refusal cannot name a game
  - Brave Adventurer code noticed while sharing the scenes (behaviour, so left for a change that
    re-checks the goldens): `brave_adventurer_core/scene.py` set `_was_airborne` and never read
    it (resolved 2026-10-31: the landing sound already played from a local); the respawn clamp `max(0, self.player.world_x - RESPAWN_OFFSET)` can make the respawn x
    the int 0 (resolved 2026-10-31: `max(0.0, ...)`) (both tracked in BUGS.md, #229 and #230); both games' `game.py` import their scarab
    lazily inside a method although nothing needs it deferred
  - Member tests use the engine's test seams (`SceneManager._reset`, `FontManager._font_cache`),
    a known exemption from the public-API rule (`docs/architecture/game_packages.md`); member
    game code may not. A public testing helper for them (in `src/glitchygames/testing/`) would
    end the exemption
  - The core scene's setup log record's `msg` is now a format string (`'%s setup complete'`; the
    text is unchanged), which a test matching `record.msg` would see
  - Papyrus's sprite-file test imports the engine's checks from
    `tests.examples.test_examples_sprites`; if a second game needs them, they belong in
    `src/glitchygames/testing/` (a sprite-files helper). Bitmappy is now the second importer;
    Part 3 does the move (`src/glitchygames/testing/sprite_files.py`, the user, 2026-10-26)
  - With member packages first-party, isort orders `glitchygames` imports after a game's own in
    member files (cosmetic)
  - `tests/test_build_browser_bundle.py`'s stand-in `record_archive` takes `**_ignored`: a name
    saying which keyword arguments it drops would read better
  - The `replay-metrics` hook measures every installed bundled demo, and a built install
    (`site-packages`) names a demo by its install name, so its ledger rows form a series apart
    from the repository path's

### 55. Recording Naming Convention and Logical Recording Ids — TODO
- **Goal**: every recording is named and placed by one convention, and has a logical id that
  survives moves (the user, 2026-10-25)
- **Convention**: golden replays at `<member>/tests/fixtures/replays/golden.jsonl.gz` (extra ones
  `golden-<purpose>.jsonl.gz`); demos inside the game's package at `<package>/demos/<name>.jsonl.gz`;
  later roles (`ghost`, `bookmark`) get their own folders
- **Ids**: the game's logical name (`games.mr_muncher`, see the workspace packages plan), the role
  and the name: `games.mr_muncher:golden`, `games.paddleslap:demo/rally`, derived from the
  location; a test checks every recording follows the convention and its id agrees with its
  header's logical name
- **Uses**: the run ledger and performance graphs key history by id, so moving a recording needs
  no `RECORDING_PATH_RENAMES` entry (the map is removed); the Arcade asks a game for its
  `demo/*` recordings instead of knowing paths
- **Status**: TODO, after workspace packages Parts 1 and 2 (`plans/2026-10-24-workspace-packages.md`)
- **Priority**: Medium

### 68. Docs Deploys That Cannot Go Stale — TODO
- **Goal**: the published docs (https://terrysimons.github.io/glitchygames/) are always `main`'s
  latest, not just usually (the user, 2026-10-25)
- **Today**: CircleCI's `deploy-docs` publishes its own pipeline's commit after every merge to
  main, one deploy at a time (`serial-group`). GitHub's "require branches to be up to date
  before merging" keeps merges at least a CI run apart, so deploys queue, and publish, in merge
  order. Two gaps remain, both rare:
  - an admin merge or a skipped check can bring two merges within one CI run; an older
    pipeline's deploy can then run after a newer one's and publish older docs
  - a failed deploy leaves the site one merge behind until the next merge (fix by hand now:
    re-run that pipeline's `deploy-docs` in CircleCI)
- **Plan**:
  - a tip check in `deploy-docs`: fetch `main`, and skip unless this pipeline's commit is still
    its tip (a newer pipeline will deploy); with the serial group, the last publish is always
    the tip
  - a daily scheduled pipeline (a CircleCI trigger on `main`, set up once in the project's
    settings): compare the commit gh-pages names ("Deployed <sha>") with `main`'s tip, and
    deploy the tip when they differ
  - tests in `tests/test_ci_config.py` for both
- **When**: if a deploy is ever seen to fail or publish out of order
- **Status**: TODO

## Medium Priority Features
### 49. Pyodide pygame-ce Wheels for Every Upstream Version (experimental CI) — IN PROGRESS
- **Description**: A CI pipeline (on the fork `terrysimons/pygame-ce`) that builds our patched
  Pyodide wheel for the current pygame-ce and Pyodide versions, and then tries every newer
  version too. For each pygame-ce release (and `main`) × each Pyodide release that PyScript
  pins or that is newer, it checks out a fresh tree, applies our WebAssembly patches (the
  `glitchygames-wasm` branch's commits, or `patches/` from the feasibility study), builds with
  `buildconfig/glitchygames/build_pyodide_wheel.sh` against that Pyodide's cross-build
  environment, runs the browser checks (pygame-ce's freetype, ftfont, controller, touch and
  display tests, plus the static-module probe), and publishes the wheels that pass (with
  `build-info.json`) as experimental releases. The matrix reports, per pair: patches applied
  cleanly / needed rework / no longer needed (fixed upstream), build ok, tests ok.
- **Why**: Pyodide repackages pygame-ce on its own schedule (it still ships 2.5.7 while 2.5.8 is
  out), and PyScript pins one Pyodide. Knowing early which newer versions build and pass with
  our patches, and when upstream makes a patch unnecessary, keeps the browser target from
  freezing on one version. (The user, 2026-10-23.)
- **Status**: TODO. Building blocks done on 2026-10-23:
  - the build script and a single-version workflow on the fork
    (`.github/workflows/glitchygames-wasm-wheel.yml`; pushing it needs the `gh` token's
    `workflow` scope);
  - reproducible builds (`SOURCE_DATE_EPOCH`);
  - the in-browser test runner (`../pygame-ce-wasm/tools/run_pygame_tests_in_browser.py`).
  Implemented 2026-10-24 on the fork's `glitchygames-wasm` (`e9d46a7cd`; the workflow file is
  also on the fork's `main`, `96e04db5a`, so its weekly schedule runs):
  - `buildconfig/glitchygames/version_matrix.py` (discover, run one pair, report, all): fresh
    worktree per pair, each patch classified (clean / 3-way / already upstream / conflict),
    reproducible build, browser checks, JSON and markdown reports;
  - `buildconfig/glitchygames/browser_checks/` (from the feasibility study's runner);
  - `.github/workflows/glitchygames-wasm-version-matrix.yml` (weekly and on demand; passing
    pairs published as `experimental-...` pre-releases); `build_pyodide_wheel.sh` takes
    `PYODIDE_VERSION`.
  - Run locally: 2.5.8 and `main` (3.0.0.dev1) on Pyodide 314.0.3 take all three patches
    cleanly, build, and pass in Chromium and WebKit. 2.5.8 without the patches fails every
    probe: all three are still needed.
  - First GitHub run (40131798850, manual, publish off), 2026-10-24: all 6 pairs (2.5.7, 2.5.8
    and `main` on Pyodide 314.0.3 and 314.0.7) apply the patches cleanly, build and pass in
    Chromium and WebKit; the 2.5.8 and `main` wheels are byte-identical to the macOS builds,
    and each pygame-ce version's wheel is the same on both Pyodide releases.
  - 2026-10-24: the branch moved to 2.5.8 (`a293e2c75`, below); the matrix's base is 2.5.8, so
    it tries 2.5.8 and `main`.
  - Wheels with the same version but another sha256 (the matrix's 2.5.7 `16ac6c2d...` and the
    branch's `777cfa26...`) hold byte-identical files: only the zip entries' timestamps differ,
    which `SOURCE_DATE_EPOCH` takes from the source commit's date (the matrix commits on
    upstream's date, the branch has its own commits).
  Open: scheduled runs publish passing pairs as pre-releases (`publish` defaults to true);
  315.x needs a Python 3.15 build venv.
- **Priority**: Medium (experimental)

### 50. Browser Builds: PyScript/Pyodide Runner and the Game Host — IN PROGRESS
- **Description**: Run the games in a browser through PyScript (Pyodide 314, Python 3.14) with
  our pygame-ce fork's wheel. The engine gains an outer game on every live run (`GameHost`,
  `src/glitchygames/host.py`: transparent doors beneath the recorder for later AI and event
  injection, and an async frame driver paced at the target FPS whatever the display's refresh),
  plus a local launcher (`nox -s browser`).
- **Status**: IN PROGRESS on branch `wasm/pygame-ce-fork` (worktree `../glitchygames-wasm`). Plan
  `plans/2026-10-23-game-host-and-browser-runner.md`; feasibility study in `../pygame-ce-wasm/`.
  Done 2026-10-23 (uncommitted, for the user's testing):
  - the game host;
  - `GameEngine.start_async`;
  - optional MIDI and controller modules;
  - save observers;
  - `nox -s browser -- <game>`, with all four games running in Chromium and WebKit;
  - Bitmappy (`-- bitmappy`), with its AI feature flag off in browser builds.
  Done 2026-10-24: the startup focus-loss pause (BUGS.md #216), no timer calibration for async
  runs, Bitmappy Save/Load (file picker, downloads) and a clipboard factory, watched replays
  (`--replay-trace`) and attract mode in the browser, iOS Simulator Safari (no JSPI) runs the
  games, and every game published with the docs as play/ (`nox -s docs-deploy`).
  Done 2026-10-25: touch controls (`browser/touch_controls.js`, per-game `TOUCH_LAYOUTS`):
  verified on emulated phones (Pixel 7 in Chromium, iPhone 13 in WebKit), portrait and
  landscape: taps, held buttons, sliding across the D-pad. Fixed: a failed Bitmappy save ended
  the editor (BUGS.md #217).
- **Priority**: High (requested 2026-10-23)


### 4. Performance Profiling Integration
- **Description**: Detailed profiling capabilities for per-scene performance breakdown
- **Use Case**: Better development tools and performance optimization
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - Per-scene performance breakdown (update vs render time)
  - Sprite/object performance impact analysis
  - Event processing time tracking
  - Memory allocation tracking

### 5. Adaptive Quality Settings
- **Description**: Dynamic quality scaling based on performance
- **Use Case**: Improves user experience on lower-end hardware
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - Automatic resolution scaling
  - Dynamic sprite detail reduction
  - Adaptive particle system density
  - Smart LOD (Level of Detail) for complex scenes

## Low Priority Features

### 6. Performance Benchmarking
- **Description**: Built-in performance test suite and automated testing
- **Use Case**: Performance regression testing and optimization
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Automated performance regression testing
  - Hardware-specific performance profiles
  - Performance comparison tools
  - Bottleneck identification

### 7. Debug Performance Tools
- **Description**: Advanced debugging capabilities for performance analysis
- **Use Case**: Advanced debugging features for developers
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Performance bottleneck visualization
  - Frame time graph overlay (done: the debug overlay's performance panel, `src/glitchygames/debug/panels.py`)
  - Performance hotspot identification
  - Memory leak detection

### 8. Performance Configuration System
- **Description**: User-configurable performance profiles and settings
- **Use Case**: Customizable performance for different hardware capabilities
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Performance presets (High/Medium/Low)
  - Custom performance profiles
  - Automatic performance optimization
  - Performance-based settings recommendations

### 9. Platform-Specific Optimizations
- **Description**: Platform-aware performance optimizations and tuning
- **Use Case**: Optimized performance for different platforms
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Mobile-specific performance tuning
  - Desktop vs console optimizations
  - Platform-specific frame rate targets
  - Hardware capability detection
  - Per-platform super accurate timers

### 10. Performance Data Export
- **Description**: Data export and analysis tools for performance data
- **Use Case**: Performance analysis and historical tracking
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - CSV/JSON performance data export
  - Performance visualization tools
  - Historical performance tracking
  - Performance trend analysis

## Code Architecture Features

### 62. Reserve the Game Package Names on PyPI Before Publishing the Engine — TODO
- **Goal**: never let `pip install glitchygames[games]` (or `[demos]`, `[apps]`) install a package someone else registered (the owner, 2026-10-30)
- **Why**: `pyproject.toml`'s extras `games`, `demos` and `apps` list the workspace members by distribution name (`mr-muncher`, `brave-adventurer`, `clockwork-keep`, `paddleslap`, `drawing-fire`, `dt-demo`, `joystick-demo`, `text-input-demo`, `bitmappy`). In the workspace they resolve to the members; from PyPI they resolve to whatever is registered under those names, and none is registered by this project yet. Publishing the engine first would let anyone register one of those names and be installed by the extra (dependency confusion)
- **Before the engine is published**: either publish (or reserve) every member under its name first, or drop the extras from the published engine (keep them for the workspace only), or rename the distributions under a prefix this project owns (e.g. `glitchygames-mr-muncher`). A test could refuse a publish build whose extras name a distribution not owned on PyPI
- **Found**: comparing the workspace migration plan with #109 (2026-10-26)
- **Status**: TODO, before any PyPI publish
- **Priority**: High at publish time, none until then

### 61. Swatches Into the Engine: Recolouring Sprites by Palette Swap — TODO
- **Numbering**: was a second #55 (the Recording Naming Convention entry kept #55, which other plans cite); renumbered 2026-10-30
- **Goal**: move the mechanic Drawing Fire proved (plans/2026-10-25-drawing-fire-design.md,
  section 7) from `src/games/drawing-fire/drawing_fire/swatches.py` into the engine, so any
  game recolours a sprite's parts (a helmet, a uniform) by palette swap, its shades following.
  The user's rule: every new game proves a mechanic, and a proven one is considered for the
  engine
- **What Drawing Fire proved**: one soldier sprite (`drawing_fire/sprites/soldier.toml`) drawn
  once, worn in two liveries (the Pencil Platoon's pencil yellow, the Graphite Brigade's
  graphite grey) with every shadow staying a darker shade of its part's new colour. The sprite
  file never changes; each scheme's frames are built once, in memory
- **The API as built** (`swatches.py`; nothing in it names the game):
  - In the sprite file, beside `[colors]`: `[swatches.<set>.<part>]` tables, each with
    `colors` (palette characters: the base colour first, then its shades) and an optional
    `role` (`"primary"`, `"secondary"`)
  - `load_swatch_sets(path=...) -> dict[str, SwatchSet]`: reads the sets, each part's colours
    looked up in the palette; `SwatchError` (naming the file and part) for a character not in
    `[colors]`, a part with no colours, or a character in two parts of one set
  - `SwatchPart(name, colors, role)` and `SwatchSet(name, parts)`: frozen dataclasses
  - `Scheme(primary=..., secondary=..., parts={name: colour})`: colours by role, a named part
    overriding its role; hashable (its parts kept as sorted pairs), so it keys a cache.
    `Scheme.color_for(part)`
  - `shade_map(part=..., color=...)`: the base becomes the new colour, each shade is scaled
    per channel by new base / old base (rounded, clamped; a 0 base channel takes the new
    channel as it is)
  - `recolor_surface(surface=..., swatch_set=..., scheme=...)`: a recoloured copy, matched by
    exact RGB; alpha and the colorkey kept, transparent pixels never replaced, parts the scheme
    leaves out unchanged
  - `load_frames(path=...)`: every animation's frames through the engine's `AnimatedSprite`
    loader; `RecoloredFrames(frames=..., swatch_set=...).frames_for(scheme)`: each scheme's
    frames built on first use, then the same surfaces
- **What moving it into `src/glitchygames/sprites/` would take**:
  - the module moves as it is (a `src/glitchygames/sprites/swatches.py`), with its tests, and
    `AnimatedSprite` (or the sprite loader) learns to read `[swatches]` itself, so a game asks
    the sprite for its frames in a scheme rather than loading the file twice
  - the sprite format's docs and Bitmappy: `AnimatedSprite._save_toml` (which Bitmappy saves
    through) writes the sprite, animations, colours and transitions only, so a sprite saved from
    Bitmappy loses its `[swatches]` today; the save must keep them, and Bitmappy could preview
    a scheme
  - the review notes from Drawing Fire's Task 4, to settle on the way in:
    - RGB collisions are not validated: two parts whose palette characters share an RGB, or a
      part colour equal to a colour no part lists, are recoloured together, silently.
      `load_swatch_sets` checks characters, not colours; it should refuse (or warn about)
      colliding RGBs
    - the engine's `AnimatedSprite` leaves magenta (transparent) pixels opaque in a frame's
      image (the engine skips them when it draws; a plain blit would not), so `load_frames`
      clears them itself (`_with_transparency`). In the engine the loader should hand out
      frames whose transparent pixels are transparent, and this step goes away
    - the per-pixel loops (`_with_transparency`, `recolor_surface`) use `get_at`/`set_at`;
      they should become `pygame.PixelArray` (or `PixelArray.replace` per colour), which
      matters once sprites are larger or schemes many
    - the `RecoloredFrames` cache is unbounded: a game that makes schemes on the fly (a
      colour per player, a fading tint) grows it forever. An engine version needs a bound (an
      LRU) or a documented "schemes are few" contract
    - the returned surfaces are mutable and shared: a caller that draws on a frame changes it
      for every later caller of that scheme. Document it, or hand out copies (or read-only
      views) where that matters
- **Status**: TODO (proven in Drawing Fire, 2026-10-25)

### 11. Event Manager Naming Convention Refactor
- **Description**: Refactor all event managers to use consistent `FooEventManager` naming convention instead of `FooManager`
- **Use Case**: Improves code clarity and consistency by making it explicit that these classes manage events
- **Status**: Planned. The rename is done: every manager in `src/glitchygames/events/` is a
  `*EventManager` (voice: `VoiceEventManager`; no `VoiceRecognitionManager` remains). The Vosk
  backend item below is still open
- **Priority**: Medium
- **Implementation**:
  - Renamed to EventManagers:
- Voice recognition:
  - Add optional Vosk backend using miniaudio capture for fully offline STT
    - Capture via MiniaudioMicrophone, segment/buffer, feed Vosk model
    - Expose backend selection flag and graceful fallback to speech_recognition
    - `GameEventManager`
    - `ControllerEventManager`
    - `AppEventManager`
    - `MouseEventManager`
    - `JoystickEventManager`
    - `MidiEventManager`
    - `WindowEventManager`
  - Rename `VoiceRecognitionManager` → `VoiceRecognitionEventManager`
  - Update all imports and references throughout the codebase
  - Update documentation and comments
  - Ensure backward compatibility during transition period

## Game Mechanics Features

### 12. Stuck Ball Recovery System
- **Description**: Game mechanic for handling balls that get stuck at zero speed (0, 0), turning it into a strategic gameplay element rather than a bug
- **Use Case**: Creates strategic depth where players must manage stuck balls, adds recovery mechanics, and prevents game-breaking scenarios
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Stuck Detection**: Detect when ball speed magnitude falls below threshold (e.g., < 1.0 pixels/second)
  - **Stuck State Tracking**: Track how long ball has been stuck and position where it became stuck
  - **Visual Indicators**: Clear UI feedback showing stuck state (color change, pulsing, special effects)
  - **Recovery Mechanisms**:
    - Limited "kick" attempts to free stuck balls (e.g., 3 kicks per ball)
    - Directional kicks (left, right, up, down, random)
    - Automatic recovery after paddle contact
  - **Strategic Elements**:
    - Stuck balls could count differently in scoring
    - Time limits for stuck balls before special events
    - Risk/reward of intentionally creating stuck balls
  - **Game Events**: Special events triggered by critically stuck balls (stuck too long)
  - **UI Features**: 
    - Stuck ball counter/indicator
    - Recovery kick counter
    - Stuck time display
    - Recovery attempt feedback

### 13. Air Brake Paddle Movement System
- **Description**: Paddles that continuously move with air resistance, requiring constant input to maintain position
- **Use Case**: Creates more dynamic and challenging paddle control where paddles naturally drift and require active management
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Continuous Movement**: Paddles always have some movement unless actively controlled
  - **Air Resistance**: Natural deceleration when not actively moving
  - **Momentum System**: Paddles build up momentum and require counter-input to stop
  - **Drift Mechanics**: Paddles naturally drift in one direction unless actively opposed
  - **Control Feedback**: Visual/audio feedback for momentum and drift direction
  - **Difficulty Scaling**: Adjustable drift speed and resistance for different skill levels

### 14. Enhanced Ball Boundary Physics ✅ COMPLETED
- **Description**: Improved ball collision and boundary behavior with proper physics
- **Use Case**: More realistic ball behavior, better collision detection, and smoother gameplay
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - ✅ **Proper Boundary Checking**: Ball should not clip through screen edges
  - ✅ **Collision Response**: Realistic bounce angles and energy conservation
  - ✅ **Edge Case Handling**: Better behavior when ball hits corners or edges
  - ✅ **Physics Accuracy**: Proper momentum transfer and angle calculations
  - ✅ **Visual Feedback**: Clear indication of collision points and bounce directions
- **Files Modified**:
  - `src/glitchygames/game_objects/ball.py` - Enhanced physics with realistic collision response
  - `tests/game_objects/test_ball_boundary_physics.py` - Comprehensive test suite

### 15. Momentum Dampening System
- **Description**: Gradual deceleration system for movement objects to create more natural motion
- **Use Case**: Smoother, more realistic movement that feels more natural and controllable
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Gradual Deceleration**: Objects slow down over time instead of instant stops
  - **Configurable Damping**: Adjustable deceleration rates for different objects
  - **Momentum Preservation**: Maintains some momentum for more realistic physics
  - **Input Response**: Responsive to input while maintaining natural deceleration
  - **Performance Optimization**: Efficient calculation of dampening effects

## Recently Completed Features

### 51. `--list-input-devices`: Every Joystick and Game Controller the Game Would See ✅ COMPLETED
- **Description**: An engine option (every game has it) that lists the devices SDL offers and
  exits, instead of guessing from a game's behaviour why a pad does or does not work (2026-10-24)
- **Status**: ✅ COMPLETED
- **Implementation**:
  - `src/glitchygames/input/device_listing.py`: starts the joystick and controller subsystems,
    counts the devices before SDL's queue is pumped, listens for `LISTEN_SECONDS` (1 s; macOS
    reports connected pads as device-added events) keeping each device added/removed event with
    its time, opens each device through the devices door (as a game controller when SDL maps it)
    and prints its index, instance id, name, GUID, mapping and axes, buttons, hats and balls; a
    device that cannot be opened is listed with SDL's error. At a terminal (stdin and stdout),
    finding none prints `NO_DEVICES_PROMPT` and waits for the first device added. The count
    before pumping and the event times tell a pad SDL knew at startup from one it reported only
    later (the suspected "already plugged in is not seen" bug)
  - `GameEngine._run_game` runs it in place of the game (the scene is never built, nothing
    recorded) and the run ends `SUCCESS`; `--replay-trace` and `--record-trace` with it are
    refused (`OPTIONS_REFUSED`)
  - Tests: `tests/input/test_device_listing.py` (stand-in devices through the door),
    `tests/engine/test_engine_lifecycle.py::TestListInputDevices`
- **Follow-up**: a `--watch` mode printing devices as they connect and disconnect (offered and
  not chosen yet); once the "already plugged in" question is settled, the prompt only shows when
  nothing is connected at all

### 44. Golden Replays Exercise Every Control, Pause and Quit ✅ COMPLETED
- **Description**: Q did nothing in four games and no golden replay noticed (BUGS.md #202): every
  session ended with the recorder's own `quit_requested`, and Clockwork Keep's never paused.
  Every golden replay now pauses and resumes, presses every keyboard control its game binds, and
  ends with the game's own quit control (2026-10-23)
- **Status**: ✅ COMPLETED (keyboard; gamepad is the follow-up below)
- **Implementation**:
  - `scripts/record_scripted_session.py`: a per-game controls tail (`CONTROLS_TAIL_BUILDERS`)
    played after the golden script's frames (session-only: the golden traces never see it); it
    releases held keys, presses what the script does not (Brave: LEFT, SPACE; Clockwork Keep:
    left shift + RIGHT, SPACE, W, ESC pause; Mr. Muncher: WASD, P pause; PaddleSlap: Q and ESC
    released together, two QUITs), then the quit key; the game must quit within
    `QUIT_WAIT_FRAMES` (`GameDidNotQuitError`); `--script-only` for demos
  - Brave Adventurer (both editions) and Clockwork Keep build their ActionMap in a static
    `_create_action_map(*, input_mode)` (as Mr. Muncher and PaddleSlap already did), so tests
    read the game's own bindings
  - `tests/replay/test_golden_replays.py`: `test_every_golden_replay_exercises_every_control`
    (bindings from `ActionMap.to_dict()` plus the engine scenes' hard-coded keys, matched against
    each recording's external events by receiving scene; `UNEXERCISED_CONTROLS` with reasons,
    stale entries fail) and `test_every_golden_replay_pauses_resumes_and_ends_with_the_games_own_quit`
  - Fixtures re-recorded: PaddleSlap 622 frames, Clockwork Keep 532, Brave Adventurer 472 (each
    edition), Mr. Muncher 2072 (script cut to 1950 frames, death and take 2 still included, to
    stay under 100 KB)
- **Follow-up (TODO): gamepad controls in golden replays**. A supervisor can post JOYBUTTONDOWN
  etc. with `post_input_event`, but the engine drops input events of devices it has not opened
  (`InputDevices.dispatches`) and the dummy driver has none. A probe with the tests' stand-in
  devices (`tests/input/stand_in_devices.py`, installed before `GameEngine.start`) moved the
  player live, but the recording's header held no `devices`/`device_enumeration`
  (`ReplayDeviceRegistry.take_opened_descriptors` returns only descriptors learned from a
  recording), so the replay saw no device and diverged. Needed: a stand-in registry that reports
  what it served (descriptors opened, enumeration answers) the way `LiveDeviceRegistry` does,
  stand-in pads with instance ids 0 and 1 (PaddleSlap binds per instance), gamepad tails
  (buttons, axes past their thresholds, Mr. Muncher's hat), and gamepad matching in the test
  (then shrink `UNEXERCISED_CONTROLS`)

### 42. Mr. Muncher Remade: A Maze Chase at the Movies ✅ COMPLETED
- **Description**: The converted toy was not fun (12 px/s movement, an open field with two
  wall pieces, munchers wandering at random, discs overlapping walls, a catch resetting only the
  player, no end to a won game; a perfect bot cleared 87 of 211 dots in 10 minutes). It is now a
  complete, original maze-chase game with a cinema theme (2026-10-23)
- **Status**: ✅ COMPLETED (2026-10-23)
- **Implementation** (now `src/games/mr-muncher/mr_muncher/`, a workspace member since
  the workspace-packages Part 1; it was the `mr_muncher` folder of the engine's examples package):
  - `maze.py`: a hand-designed 27x24 maze (symmetric, corridors one tile wide, no dead ends,
    connected; tests check all four), tunnels at the top and bottom, a house with a door
  - `actors.py`: tile-to-tile movement (turns on tile centres only; a direction pressed early is
    taken at the first open junction; reversing is immediate); four munchers with their own
    targets (chaser, ambusher, flanker, shy), scatter/chase phases, a frightened random walk on
    the seeded stream, eyes going home and back out
  - `levels.py`: speeds, fright length, mode schedule and bonus per reel, ramping to reel 8
  - `game.py`: the scene (countdown 3-2-1-ACTION!, TAKE n after a death, REEL n, CUT!, THE END),
    sprockets (10), snacks (50, a sugar rush), munchers 200/400/800/1600, the bonus reel twice a
    reel, an extra life at 10,000, high scores through `open_saves`, the engine's pause and a
    game-over screen, a screen shake and rumble on a catch, a projector-flutter live voice,
    `debug_draw` marks muncher targets; `drawing.py` (velvet-and-gold maze, popcorn-bucket
    player, fuzzball munchers, candy snacks), `scenery.py`, `sounds.py` (all original sounds)
  - `autopilot.py`: a player bot (territory-safe BFS) used by the golden script and the tests;
    golden replay re-recorded (then 2250 frames, 2072 since #44: countdown, pause, a snack, two munchers and the
    bonus eaten, a death, take 2); tests `src/games/mr-muncher/tests/test_mr_muncher.py` and
    `src/games/mr-muncher/tests/test_mr_muncher_maze_and_actors.py` (100% lines and branches)

### 41. Mr. Muncher Example Game and Microphone Capture Check ✅ COMPLETED
- **Description**: Two untracked toys brought up to the project's standards (2026-10-23): the
  plain-pygame Pac-Man toy `scripts/mr_muncher.py` became the example game
  `src/games/mr-muncher/mr_muncher/` (`uv run mr-muncher`; it was
  the `mr_muncher` folder of the engine's examples package until the workspace-packages Part 1), and `scripts/audio_test.py` became
  `scripts/microphone_capture_check.py`
- **Status**: ✅ COMPLETED (2026-10-23)
- **Implementation**:
  - Mr. Muncher: a `Scene` run by `GameEngine`; scancode `ActionMap` controls; the maze, its
    sprockets and the munchers' turns from seeded random streams; frame-rate independent speeds;
    sprites (compared by replays) instead of direct drawing; golden replay
    `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz` (600 frames,
    `scripts/record_golden_traces.py: mr_muncher_script`); `src/games/mr-muncher/tests/test_mr_muncher.py`
  - Microphone check: capture `--duration` seconds (default 3) from the default or a named
    (`--device`) capture device with miniaudio, report bytes, frames and peak/RMS levels, exit
    with an `ExitCode`; `tests/test_microphone_capture_check.py`

### 40. Gameplay Replay ✅ COMPLETED (Parts 1-3)
- **Description**: Replay a `--record-trace` recording exactly through the real engine
  (`--replay-trace PATH`), comparing every frame's sprites with the recording and reporting the
  first divergence; audit determinism in two fresh processes (`--audit`); replay tooling (Part 2)
  and in-game playback (Part 3)
- **Use Case**: Bug reproduction from a recording, regression tests from real play, finding
  nondeterminism; watching and stepping through recordings; attract-mode demos, instant replays
  and ghosts in games
- **Status**: ✅ COMPLETED (branch `feature/gameplay-replay`: Part 1 2026-10-19, Parts 2 and 3
  2026-10-20; final whole-branch review clean 2026-10-20; merged 2026-10-22 as PR #95, `bb51239d`)
- **Priority**: High
- **Implementation**:
  - The doors: `src/glitchygames/sources.py` (leaf registry), `LiveSources`, `RecordingSources`,
    `ReplaySources`; `tests/test_engine_doors.py` guards them
  - Clocks (`src/glitchygames/clock.py`, `Scene.game_time`), input snapshots (`current_input()`),
    the devices door with replay stand-ins, saves through `open_saves` (`DiskSaveManager` /
    `MemorySaveManager`), the supervisor hook and control events
  - Trace format 3, `--replay-fps {recorded,real}`, real input blocked at SDL during a replay,
    golden replay fixtures (`tests/fixtures/replays/`, `scripts/record_scripted_session.py`),
    run as pytest items by the replay plugin (`src/glitchygames/testing/replays.py`)
  - Part 2, tooling: `--headless`, the watched-replay viewer (pause, step, speed, step back
    through a restarted process, bookmarks saved to `*.bookmarked.jsonl.gz`), recordings as
    pytest items, `--rebaseline`
  - Part 3, playback: scene starts (`src/glitchygames/scene_start.py`), the playback scope
    (`src/glitchygames/replay/playback.py`), demos (`play_recording`; PaddleSlap's bundled demo on
    its game-over screen), instant replay (`src/glitchygames/instant_replay.py`), ghosts
    (`src/glitchygames/replay/ghosts.py`)
- **Docs**: CLAUDE.md (Clocks, Gameplay Recording and Replay),
  `docs/architecture/gameplay_replay.md`, `plans/2026-10-19-gameplay-replay.md`

### 39. Engine World Space and One End-of-Frame Call ✅ COMPLETED
- **Description**: Sprites declare `CoordinateSpace.WORLD` and the engine positions, snaps and
  culls them from the scene's camera every frame; the camera follows a target on chosen axes;
  every frame ends in one `_finish_frame` that paces and measures the frame once (engine audit
  #6 and #15)
- **Use Case**: Games no longer write per-sprite camera loops or culling; shake, snapping,
  culling and follow have one place in the engine; frame statistics match what the loop did
- **Status**: ✅ COMPLETED (branch `feature/engine-world-space`, 2026-10-18; merged 2026-10-22 as PR #94, `cd5e5f97`)
- **Priority**: High
- **Implementation**:
  - `src/glitchygames/world.py`: `CoordinateSpace`, `WorldPositioned`, `hidden`,
    `position_world_sprites` (`CULL_MARGIN_PIXELS` culling that never lowers `dirty = 2`,
    `draw_offset` added), `aim_camera`
  - `Camera2D.follow(target=, axes=FollowAxes)`, `aim_at`, `begin_frame`; `Scene.camera_target()`,
    `Scene.PIXEL_SNAP_MODE`, `Scene.MAX_FRAME_SECONDS`
  - `SceneManager._finish_frame`: one start-to-start `dt`; pacing re-anchors after a hitch
  - Brave Adventurer, Papyrus, Clockwork Keep and PaddleSlap migrated; the pose rule (draw the
    pose in `dt_tick` before collision) fixes the one-frame wall lag
  - Golden traces of every game (`tests/world/test_golden_traces.py`), each difference proven by
    exactly one rule; gameplay recording (`--record-trace`) and seeded random streams
    (`--random-seed`)
- **Docs**: CLAUDE.md (World Space, Frame Pacing), `plans/2026-10-18-engine-world-space.md`

### 16. ASCII Transparency Contrast Enhancement ✅ COMPLETED
- **Description**: Enhanced ASCII renderer to draw fully transparent pixels as light grey for better contrast visibility
- **Use Case**: Improves visibility of transparent pixels in terminal output, making it easier to see sprite boundaries and structure
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - Modified `_colorize_pixels` method in ASCII renderer
  - Added light grey (192, 192, 192) background for fully transparent pixels (alpha = 0)
  - Enhanced transparency detection for both RGBA and magenta transparency
  - Improved contrast for better terminal visibility
- **Files Modified**:
  - `src/glitchygames/tools/ascii_renderer.py` - Enhanced transparency handling

### 17. TOML Drag-n-Drop Support ✅ COMPLETED
- **Description**: Added drag-n-drop support for .toml files to the canvas, complementing existing PNG drag-n-drop functionality
- **Use Case**: Allows users to directly load TOML sprite files by dragging them onto the canvas, streamlining the workflow
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - Extended `on_drop_file_event` method to detect .toml file extensions
  - Added direct loading of TOML files without conversion
  - Maintained existing PNG conversion workflow
  - Updated error messages to reflect support for both file types
- **Files Modified**:
  - `src/glitchygames/bitmappy/editor.py` - Enhanced drag-n-drop handling

### 18. Flood-Fill Tool ✅ COMPLETED
- **Description**: Implemented flood-fill functionality for the canvas using control-click to fill connected regions of the same color
- **Use Case**: Efficiently fill large areas or backgrounds with a single click, improving productivity for sprite editing
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - Added control-click detection using `pygame.key.get_pressed()`
  - Implemented iterative flood-fill algorithm using stack-based approach
  - Added 4-connected neighbor checking (up, down, left, right)
  - Integrated with existing canvas interface and color system
  - Added comprehensive logging for debugging
- **Files Modified**:
  - `src/glitchygames/bitmappy/editor.py` - Added flood-fill algorithm and control-click handling

### 19. Onion Skinning Initialization Fix ✅ COMPLETED
- **Description**: Fixed onion skinning initialization when loading sprites to ensure proper alpha blending and transparency handling
- **Use Case**: Ensures onion skinning works correctly after loading sprites, with proper semi-transparent overlays
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - Restored `_initialize_onion_skinning_for_sprite` method
  - Added automatic initialization after successful sprite loading
  - Proper frame state management for all animations
  - Global onion skinning toggle support
  - Enhanced alpha blending with transparent pixels
- **Files Modified**:
  - `src/glitchygames/bitmappy/editor.py` - Fixed onion skinning initialization

### 20. Debug Logging Cleanup ✅ COMPLETED
- **Description**: Removed verbose debug logging statements that were cluttering console output
- **Use Case**: Cleaner console output for better development experience and reduced log noise
- **Status**: ✅ COMPLETED
- **Priority**: Low
- **Implementation**:
  - Removed animation update debug logs
  - Removed film strip update debug logs
  - Maintained functionality while reducing console verbosity
- **Files Modified**:
  - `src/glitchygames/bitmappy/editor.py` - Cleaned up debug logging

### 21. Controller Position Undo/Redo System ✅ COMPLETED
- **Description**: Integrated controller position and mode changes into the undo/redo system, allowing users to undo controller movements and mode switches
- **Use Case**: Essential for collaborative editing workflows where controller positions and modes need to be tracked and reversible, improving user experience and workflow efficiency
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - **Controller Position Tracking**: Track controller position changes for undo/redo operations
  - **Controller Mode Tracking**: Track controller mode changes (canvas, film_strip, slider modes)
  - **Smart Continuous Movement Handling**: Skip tracking during continuous movement to prevent undo stack overflow
  - **Final Position Tracking**: Track final positions when continuous movement stops
  - **Undo/Redo Integration**: Full integration with existing undo/redo system
  - **Controller-Specific History**: Each controller maintains its own position and mode history
  - **Performance Optimization**: Efficient tracking that doesn't interfere with continuous movement
- **Technical Requirements**:
  - Controller position operation tracking system
  - Controller mode change operation tracking
  - Continuous movement detection and handling
  - Integration with existing undo/redo manager
  - Performance optimization for real-time tracking
  - Smart operation batching for continuous movements
- **Key Features**:
  - **Position Undo/Redo**: Undo/redo controller position changes
  - **Mode Undo/Redo**: Undo/redo controller mode switches
  - **Continuous Movement Handling**: Smart tracking that doesn't overwhelm undo system
  - **Final Position Tracking**: Track complete movements as single operations
  - **Controller Context**: Maintain controller-specific undo/redo history
  - **Performance Optimized**: Minimal impact on continuous movement performance
- **Files Created/Modified**:
  - `src/glitchygames/bitmappy/history/undo_redo.py` - Added controller position operation types and callbacks
  - `src/glitchygames/bitmappy/history/operations.py` - Added ControllerPositionOperationTracker
  - `src/glitchygames/bitmappy/editor.py` - Integrated controller position tracking with movement system
  - `tests/tools/test_controller_position_undo_redo.py` - Comprehensive test suite
  - `tests/tools/test_slider_continuous_movement_fix.py` - Continuous movement fix tests
- **Known Issues**:
  - Some minor bugs with slider continuous movement stopping (livable but annoying)
  - Controller position tracking may occasionally miss rapid movements
  - Mode switching undo/redo may have edge cases with complex controller interactions
- **Future Improvements**:
  - Enhanced continuous movement detection
  - Improved slider button release handling
  - Better integration with existing undo/redo visualization
  - Performance optimizations for high-frequency controller movements

### 22. Per-Pixel Alpha Support for AI-Generated Sprites ✅ COMPLETED
- **Description**: Enhanced sprite loading and rendering pipeline to support per-pixel alpha transparency in AI-generated sprites, with automatic detection and proper handling
- **Use Case**: Enables AI-generated sprites to use sophisticated transparency effects with per-pixel alpha values, improving visual quality and artistic possibilities
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - **Automatic Alpha Detection**: Detects whether sprites use per-pixel alpha or indexed transparency based on color data
  - **RGBA Surface Creation**: Creates pygame surfaces with SRCALPHA flag when per-pixel alpha is detected
  - **Transparency Key Handling**: Maintains proper handling of magenta (255, 0, 255) transparency key
  - **Canvas Rendering**: Ensures transparency key pixels are skipped during canvas rendering to show background
  - **Film Strip Display**: Converts transparency key to transparent pixels for proper film strip visualization
  - **ASCII Output Enhancement**: Updated ASCII renderer to show all animation frames with dimensions and properties
- **Technical Requirements**:
  - Enhanced sprite loading pipeline with alpha detection
  - Proper RGBA surface creation and pixel conversion
  - Canvas renderer updates to handle transparency correctly
  - Film strip transparency handling
  - ASCII renderer improvements for animation display
- **Key Features**:
  - **Per-Pixel Alpha Support**: Full RGBA color support with alpha channel
  - **Indexed Transparency Fallback**: Maintains compatibility with existing indexed transparency
  - **Automatic Detection**: No manual configuration required - automatically detects alpha usage
  - **Proper Canvas Rendering**: Transparency key pixels show background instead of drawing transparently
  - **Enhanced ASCII Output**: Shows all animation frames with dimensions (e.g., "dimensions: 2x2")
  - **Film Strip Compatibility**: Proper transparency handling in film strip display
- **Files Modified**:
  - `src/glitchygames/sprites/animated.py` - Enhanced RGBA support and transparency key handling
  - `src/glitchygames/bitmappy/editor.py` - Updated canvas rendering and sprite loading
  - `src/glitchygames/bitmappy/canvas_interfaces.py` - Fixed transparency key pixel rendering
  - `src/glitchygames/bitmappy/film_strip.py` - Proper transparency handling for film strip
  - `src/glitchygames/tools/ascii_renderer.py` - Enhanced animation frame display with dimensions
- **Future Improvements**:
  - Update AI sprite generation instructions to include per-pixel alpha examples
  - Add documentation for alpha transparency best practices
  - Consider adding alpha blending modes for advanced effects

## Animation Features

### 66. Onion Skinning ✅ COMPLETED
- **Description**: Animation feature that allows users to see previous/future frames as semi-transparent overlays while editing current frame
- **Use Case**: Helps with smooth animation creation by providing visual reference of motion
- **Status**: ✅ COMPLETED
- **Priority**: TBD
- **Implementation**:
  - **Onion Skinning Manager**: Core data structure to track enabled frames per animation
  - **Visual Indicators**: Film strip shows yellow overlay for frames with onion skinning enabled
  - **Canvas Rendering**: Onion frames rendered first with 50% transparency, then active frame with full opacity
  - **Toggle Controls**: Right-click or Shift+click on film strip frames to toggle onion skinning
  - **Keyboard Shortcuts**: 'O' key toggles global onion skinning on/off
  - **Transparency Control**: Configurable transparency level (default 50%)
- **Files Created/Modified**:
  - `src/glitchygames/bitmappy/onion_skinning.py` - Core onion skinning management
  - `src/glitchygames/tools/onion_skinning_renderer.py` - Canvas rendering with transparency
  - `src/glitchygames/bitmappy/film_strip.py` - Visual indicators and click handling
  - `src/glitchygames/bitmappy/canvas_interfaces.py` - Integration with canvas rendering
  - `src/glitchygames/bitmappy/editor.py` - Keyboard shortcuts
  - `tests/tools/test_onion_skinning.py` - Comprehensive test suite


### 67. Multi-Controller Navigation System (BETTER) ✅ COMPLETED
- **Description**: Multi-controller support system for bitmappy tool allowing up to 4 simultaneous controllers with independent navigation and visual distinction
- **Use Case**: Enables multiple users to navigate and select different frames/animations simultaneously using separate controllers
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - **Controller Assignment**: Automatic detection and assignment of controllers on first button press
  - **Independent Navigation**: Each controller navigates film strips and frames independently
  - **Visual Distinction**: Unique colored triangles for each controller (Red, Green, Blue, Yellow)
  - **Smart Positioning**: Automatic collision avoidance when multiple controllers select same frame
  - **Controller Management**: 
    - Automatic assignment on first button press
    - Controller reconnection handling
    - Status tracking and display
  - **Navigation Features**:
    - Independent frame/animation selection per controller
    - Controller-specific scrolling and navigation
    - Frame preservation when switching between controllers
    - Individual controller selection state management
- **Technical Requirements**:
  - Multi-controller event handling system
  - Visual collision detection and positioning
  - Independent state tracking per controller
  - Efficient rendering of multiple indicators
  - Controller connection/disconnection handling
- **Controller Color Scheme**:
  - Controller 0: Red (255, 0, 0)
  - Controller 1: Green (0, 255, 0)  
  - Controller 2: Blue (0, 0, 255)
  - Controller 3: Yellow (255, 255, 0)
- **User Experience**:
  - **Intuitive Assignment**: Controllers automatically assigned on first use
  - **Clear Visual Feedback**: Distinct colors and indicators for each controller
  - **Smooth Navigation**: Independent scrolling and frame selection
  - **No Conflicts**: Smart positioning prevents visual overlap
- **Files to Create/Modify**:
  - `src/glitchygames/bitmappy/controllers/manager.py` - Core multi-controller system
  - `src/glitchygames/bitmappy/controllers/selection.py` - Individual controller state management
  - `src/glitchygames/bitmappy/indicators/collision.py` - Visual indicator positioning
  - `src/glitchygames/bitmappy/editor.py` - Enhanced with multi-controller support
  - `src/glitchygames/bitmappy/film_strip.py` - Enhanced visual system for multiple indicators
  - `tests/tools/test_multi_controller.py` - Multi-controller system tests
  - `tests/tools/test_visual_collision.py` - Visual system tests
- **Configuration Options**:
  - Maximum controller count (default: 4, easily configurable)
  - Controller color customization
  - Navigation speed per controller
  - Visual indicator styles
- **Future Extensibility**:
  - Easy to increase controller limit (change MAX_CONTROLLERS constant)
  - Modular design allows adding new controller features
  - Foundation for collaborative editing features

### 23. Collaborative Multi-Controller Editing System (BEST) ✅ COMPLETED
- **Description**: Advanced collaborative editing system building on multi-controller navigation, enabling real-time simultaneous editing by multiple users
- **Use Case**: Enables teams to collaboratively edit sprites and animations in real-time, with conflict resolution and advanced workflow management
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Prerequisites**: Multi-Controller Navigation System (Feature #18)
- **Implementation**:
  - **Real-time Collaborative Editing**: Multiple controllers can edit pixels simultaneously
  - **Conflict Resolution**: Intelligent handling of simultaneous pixel editing with priority-based resolution
  - **Advanced Visual Management**:
    - Controller-specific settings and preferences
    - Customizable visual indicators and styles
    - Advanced positioning algorithms for complex scenarios
  - **Collaborative Features**:
    - Shared editing sessions with real-time synchronization
    - Permission management (master/slave controller relationships)
    - Edit history and undo/redo per controller
    - Collaborative session management
  - **Advanced Controller Features**:
    - Controller-specific shortcuts and button mappings
    - Speed control and navigation preferences per controller
    - Focus management and controller switching
    - Performance monitoring per controller
  - **Session Management**:
    - Start/stop collaborative sessions
    - Controller permission levels
    - Edit conflict notifications
    - Session history and playback
- **Technical Requirements**:
  - Real-time synchronization system
  - Conflict detection and resolution algorithms
  - Advanced visual management for complex scenarios
  - Performance optimization for simultaneous editing
  - Session state management
  - Edit history tracking per controller
- **Collaborative Workflow**:
  - **Session Initiation**: Master controller starts collaborative session
  - **Controller Joining**: Additional controllers join with assigned permissions
  - **Real-time Editing**: All controllers can edit simultaneously
  - **Conflict Handling**: Automatic resolution of edit conflicts
  - **Session Management**: Save/load collaborative sessions
- **Permission Levels**:
  - **Master Controller**: Full control, can manage session
  - **Editor Controllers**: Can edit pixels, limited session control
  - **Viewer Controllers**: Can navigate, cannot edit
  - **Guest Controllers**: Limited navigation, no editing
- **Conflict Resolution Strategies**:
  - **First-Come-First-Served**: First controller to edit pixel wins
  - **Priority-Based**: Master controller has priority
  - **Time-Based**: Most recent edit wins
  - **Area-Based**: Controllers assigned to different sprite areas
- **Files to Create/Modify**:
  - `src/glitchygames/tools/collaborative_editing.py` - Collaborative editing system
  - `src/glitchygames/tools/session_manager.py` - Session management
  - `src/glitchygames/tools/conflict_resolver.py` - Conflict resolution
  - `src/glitchygames/tools/permission_manager.py` - Permission system
  - `src/glitchygames/tools/edit_history.py` - Edit history tracking
  - `src/glitchygames/bitmappy/editor.py` - Enhanced with collaborative features
  - `tests/tools/test_collaborative_editing.py` - Collaborative editing tests
  - `tests/tools/test_session_manager.py` - Session management tests
  - `tests/tools/test_conflict_resolver.py` - Conflict resolution tests
- **Advanced Features**:
  - **Edit Broadcasting**: Real-time edit notifications to all controllers
  - **Undo/Redo Per Controller**: Individual edit history for each controller
  - **Edit Locks**: Temporary locks on pixels being edited
  - **Collaborative Cursors**: Show other controllers' cursor positions
  - **Edit Previews**: Show pending edits before confirmation
  - **Session Recording**: Record collaborative sessions for playback
- **Performance Considerations**:
  - **Edit Batching**: Group rapid edits to reduce network overhead
  - **Area-Based Updates**: Only sync relevant sprite areas
  - **Controller Throttling**: Limit edit frequency per controller
  - **Memory Management**: Efficient storage of edit history
- **User Experience**:
  - **Seamless Collaboration**: Natural editing experience with multiple users
  - **Clear Conflict Indication**: Visual feedback for edit conflicts
  - **Session Awareness**: Always know who is editing what
  - **Flexible Permissions**: Adaptable to different workflow needs
- **Future Extensibility**:
  - Network support for remote controllers
  - Cloud-based collaborative sessions
  - Advanced conflict resolution algorithms
  - Integration with version control systems

### 24. Colorized ASCII Output for Bitmappy Sprites ✅ COMPLETED
- **Description**: Enhanced terminal output for bitmappy sprite objects that displays ASCII art with colors matching the sprite's color palette
- **Use Case**: Better visual representation of sprites in terminal/console output, improved debugging and development experience
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - **Color Palette Integration**: Extract colors from sprite's color section and map to terminal colors
  - **ASCII Art Generation**: Convert sprite pixels to ASCII characters with appropriate color mapping
  - **Terminal Color Support**: Detect terminal color capabilities (8-color, 256-color, true color)
  - **Fallback Support**: Graceful degradation for terminals without color support
  - **Performance Optimization**: Efficient color mapping and ASCII conversion
  - **Customization Options**:
    - Configurable ASCII character sets (basic, extended, custom)
    - Color intensity scaling for better terminal visibility
    - Size scaling for different terminal sizes
    - Optional color reduction for compatibility
- **Technical Requirements**:
  - Terminal color detection and support
  - Color palette extraction from sprite data
  - ASCII character mapping algorithms
  - Terminal compatibility testing
  - Performance optimization for large sprites
- **Files to Create/Modify**:
  - `src/glitchygames/tools/ascii_renderer.py` - ASCII rendering system
  - `src/glitchygames/tools/color_mapper.py` - Color palette mapping
  - `src/glitchygames/tools/terminal_utils.py` - Terminal capability detection
  - `tests/tools/test_ascii_renderer.py` - ASCII rendering tests
  - `tests/tools/test_color_mapper.py` - Color mapping tests

## AI and Input Features

### 25. Speech-to-Text AI Sprite Generation
- **Description**: Use microphone input to generate sprites through AI using speech-to-text technology
- **Use Case**: Hands-free sprite creation, accessibility features, creative workflow enhancement
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Speech Recognition**: Real-time speech-to-text conversion for sprite descriptions
  - **AI Integration**: Connect speech input to AI sprite generation systems
  - **Controller Support**: PS5 controller microphone integration for portable sprite creation
  - **Voice Commands**: Natural language commands for sprite generation
  - **Real-time Processing**: Live speech recognition with immediate feedback
  - **Multi-language Support**: Support for multiple languages and accents
- **Technical Requirements**:
  - Speech recognition library integration (e.g., SpeechRecognition, Whisper)
  - AI sprite generation API integration
  - Microphone input handling
  - PS5 controller microphone support
  - Real-time audio processing
  - Voice command parsing and interpretation
- **Controller Integration**:
  - **PS5 Controller Support**: Utilize built-in microphone for portable sprite creation
  - **Voice Activation**: Push-to-talk or voice activation for hands-free operation
  - **Audio Quality**: Optimize for controller microphone limitations
  - **Noise Filtering**: Background noise reduction for better recognition
- **User Experience**:
  - **Natural Language**: "Create a red dragon sprite" or "Make a blue car"
  - **Voice Feedback**: Audio confirmation of recognized commands
  - **Visual Feedback**: Real-time display of recognized speech
  - **Error Handling**: Graceful handling of unclear or unrecognized speech
- **Advanced Features**:
  - **Voice Training**: Personalized voice recognition for better accuracy
  - **Command Shortcuts**: Custom voice shortcuts for common operations
  - **Batch Generation**: Voice commands for creating multiple sprites
  - **Style Transfer**: "Make it look like pixel art" or "Make it anime style"
- **Files to Create/Modify**:
  - `src/glitchygames/ai/speech_sprite_generator.py` - Core speech-to-sprite system
  - `src/glitchygames/ai/voice_processor.py` - Speech recognition and processing
  - `src/glitchygames/ai/controller_mic.py` - PS5 controller microphone support
  - `src/glitchygames/ai/voice_commands.py` - Voice command parsing
  - `src/glitchygames/bitmappy/editor.py` - Integration with bitmappy tool
  - `tests/ai/test_speech_sprite_generator.py` - Speech generation tests
  - `tests/ai/test_voice_processor.py` - Voice processing tests

## Gameplay Features

### 54. Drawing Fire: Everything After the MVP — TODO
- **Goal**: grow Drawing Fire (`src/games/drawing-fire/drawing_fire/`, `uv run drawing-fire`)
  from its MVP into the full vision of its design, plans/2026-10-25-drawing-fire-design.md
  (section 3; the MVP is section 4, docs/games/drawing_fire.md describes it as built)
- **The MVP, built 2026-10-25**: one battlefield that fits the screen, computer against
  computer with pistols, one or two local players joining at any time (START or Enter, a side,
  a soldier), taking over another soldier on death, leaving by holding Back; the debug seats
  view (F3); swatches (#55); a golden replay
- **After the MVP**, each from the design's section 3:
  - **Tunnels** (3.8): diggers tunnel toward the enemy, timber props hold the roof, a
    breakthrough calls in a wall of planes. Holes in the ground arrive with them (4.2)
  - **Air drops** (3.5, 3.6, 3.7): planes bring paratroopers (joining players and computer
    soldiers parachute in) and crates of ammo, guns and props; shooting a chute damages it,
    smashing a crate opens it
  - **Planes and the radio tower** (3.5): each army's tower calls its planes on a seeded
    back-off with an on-screen countdown; a destroyed tower must be repaired; the
    radar-jamming soldier
  - **The weapon ladder** (3.6): pistol, rifle, machine gun, grenades, mortar, bazooka,
    unlocking on the clock and arriving in crates
  - **The camera** (3.9): a battlefield wider than the screen, the view sliding with the
    armies' sizes (a tug of war) and zooming out a little only when sliding is not enough;
    caps on players and soldiers measured in simulations
  - **Network play** (3.11): players join over the internet if there is room; player markings
    shown only to their own side (3.4)
  - **The Twitch TODOs** (3.11): the fifteen chat interactions (enlist, adopt a soldier, vote
    the next crate, hurry the plane, ...), each reaching the game through the host's doors
  - **Roles** (3.4): a soldier's job comes with him (digger, gunner)
  - **A real AI driver** (3.2, 4.4): an outside driver sending a soldier's intent as a control
    event addressed to that soldier
  - **The look** (3.1): the underground cut away beneath the ground, hand-lettered sound
    effects, crayon muzzle flashes
- **Also open from the MVP**:
  - touch controls for the browser build (dual stick; `scripts/build_browser_bundle.py`
    `TOUCH_LAYOUTS`, exempt in `tests/test_browser_touch_controls.py` until its controls
    settle)
  - a pause: the MVP has none (`GAMES_WITHOUT_A_PAUSE` in
    `tests/replay/test_golden_replays.py`)
  - its golden replay compares the battle through the internal events the scene posts (a
    GAMEEVENT per death and seat change): the soldiers are drawn, not sprites, so a soldier's
    position is still never compared, only who dies when and where the players go. Making the
    soldiers sprites would let a replay catch a divergence in where they walk too
  - its golden replay fixture is about 185 KB, over the 100 KB the others keep: the scene start
    records the state of every random stream (19 Mersenne Twisters, twice)
  - its controls in an `ActionMap` (design 4.6): the MVP reads START, BACK, LEFT, RIGHT and fire
    straight from the polled input in `players.py` (ruling R21 accepts that for the MVP). Move
    them into an `ActionMap` bound by scancode and controller button once the engine's
    controller layout work (#47) lands, so the bindings follow the pad's layout
- **Status**: TODO

### 26. Water Physics Level System
- **Description**: Half-water, half-air level with realistic refraction physics and visual effects
- **Use Case**: Enhanced gameplay mechanics, visual variety, physics-based challenges
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Water Boundary Detection**: Detect when paddle/ball enters water zone
  - **Refraction Physics**: Change object velocity based on water entry angle and speed
  - **Visual Effects**:
    - Water surface animation (waves, ripples)
    - Light shimmer effects on water surface
    - Magnification effect (objects appear larger underwater)
    - Splash effects when objects enter water
  - **Audio Effects**:
    - Splash sounds for paddle/ball water entry
    - Different splash intensities based on entry velocity
    - Underwater audio filtering for submerged objects
  - **Physics Considerations**:
    - Reduced speed in water (drag effect)
    - Altered bounce angles due to refraction
    - Buoyancy effects for floating objects
    - Surface tension effects at water boundary
  - **Visual Polish**:
    - Water surface distortion effects
    - Caustic light patterns
    - Particle effects for splashes
    - Dynamic water level (waves affect gameplay)
- **Technical Requirements**:
  - Water zone collision detection
  - Velocity modification algorithms
  - Visual effect rendering system
  - Audio system integration
  - Performance optimization for real-time effects
- **Files to Create/Modify**:
  - `src/glitchygames/levels/water_level.py` - Water level implementation
  - `src/glitchygames/effects/water_effects.py` - Visual effects system
  - `src/glitchygames/physics/refraction.py` - Refraction physics
  - `src/glitchygames/audio/water_sounds.py` - Water audio effects
  - `tests/levels/test_water_level.py` - Water level tests
  - `tests/physics/test_refraction.py` - Refraction physics tests

### 27. Dynamic Audio Intensity System
- **Description**: Programmatic audio modification system for impact-based sound effects
- **Use Case**: Enhanced audio feedback, realistic sound scaling, immersive gameplay
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Audio Scaling**: Modify pitch, volume, and effects based on impact intensity
  - **Velocity-Based Audio**: Different sounds for different collision speeds
  - **Layered Audio**: Combine multiple sound effects for complex interactions
  - **Real-time Processing**: Dynamic audio modification during gameplay
- **Technical Requirements**:
  - Audio processing pipeline
  - Sound effect layering system
  - Performance optimization for real-time audio
  - Integration with existing sound system

## Editing and Workflow Features

### 58. Game Project Workspaces — TODO (a future PR)
- **Description**: A way to manage a game's project space: a **workspace** the tools open, holding
  the game's own files (sprites, levels, sounds, recordings), instead of the tools reaching into
  directories inside the engine or an app. Starting a project means creating a **new workspace**,
  and that is where the starter material is bundled (for example, the sprite library that
  Bitmappy ships today as package data).
- **Use Case**: The user (2026-10-26): "we need a way to manage a game project space, and since
  we're going to be migrating to a much more fully featured tool, we need to add workspace support
  and then we'll just bundle that stuff with a 'new workspace'." The more fully featured tool is
  Glitchy Studio (`plans/2026-10-18-level-tools.md`).
- **Status**: TODO (requested 2026-10-26); not started
- **Priority**: Medium
- **Context**:
  - Workspace packages Part 4 (`plans/2026-10-26-workspace-packages-4-bitmappy.md`) removed the
    engine dialogs' special `examples:` file-name prefix (the user: "We shouldn't treat examples
    specially anymore"). Files are opened by their path, and Bitmappy's sprite library is its own
    package data. A new workspace is where such starter files would come from instead.
- **Later (not now)**: templates for a new workspace (the user: "We could even have templates...
  but for now, this is ok").

### 59. Bitmappy Tests Organized by Input API and by Module — TODO (a future PR)
- **Description**: Reorganize Bitmappy's tests (`src/apps/bitmappy/tests/`, rootless, no
  `__init__.py`) into subdirectories, and decompose them where that reads better:

  ```
  src/apps/bitmappy/tests/
    input/
      controller/   test_bitmappy_pygame_controller_*.py   pygame's game-controller events (CONTROLLER*)
      joystick/     test_bitmappy_pygame_joystick_*.py     pygame's joystick events (JOY*)
    controllers/    test_bitmappy_controller_<module>.py   one file per bitmappy/controllers/ module
  ```

  - Split the input tests by event kind: buttons, axes, hats and balls.
  - Gather the input-handling tests by API. They are spread across about eight files today
    (`test_bitmappy_event_handlers.py`, `test_bitmappy_controller_event_handler.py`,
    `test_bitmappy_bitmap_editor_scene.py`, `test_bitmappy_slider_manager.py`,
    `test_bitmappy_multi_controller_troubleshooting.py`, `test_bitmappy_multi_controller.py`, ...).
  - Merge `test_bitmappy_multi_controller_enhancements.py` (coverage filler; its docstring lists
    source line numbers, which rot) into `test_bitmappy_controller_enhancements.py`: one file for
    `controllers/enhancements.py`, with classes named for the behavior they pin. Drop any test
    that only repeats another, keeping coverage at 100%.
  - Sort the other `test_bitmappy_multi_controller_*` files (stress, performance, edge cases,
    integration) into the module they test, or keep them as cross-module suites under a clear
    name.
- **Use Case**: Readability. The user (2026-10-26): "We could also do a joysticks and separately
  controllers directory under tests, and make the tests a bit more decomposed if it adds to
  readability."
- **Naming**: the `controllers/` test directory mirrors the `bitmappy/controllers/` package, which
  is the multi-controller *system* (players' cursors and modes, fed by either API). pygame's two
  APIs live under `input/`, so "controller" never means both. Test file names keep the
  `test_bitmappy_` prefix in every subdirectory: names must be unique across all test roots
  (`tests/test_suite_collection.py`), and the member's naming guard must cover subdirectories.
- **Status**: TODO (requested 2026-10-26). Deliberately not part of workspace packages Part 4,
  whose commits are pure renames.
- **Priority**: Low

### 69. Bitmappy: White Outline on the Color-Slider Knob — TODO
- **Description**: Give each color slider's draggable knob (`SliderSprite.slider_knob`,
  `src/glitchygames/ui/sliders.py`, created around line 150 and filled `(200, 200, 200)`) a white
  outline, so it contrasts the dark-gray slider track and reads clearly at a glance.
- **Use Case**: The user (2026-10-29): "Wrap the slider knob in a white outline (to contrast the
  dark gray)."
- **Status**: TODO (requested 2026-10-29); not started
- **Priority**: Low
- **Files**: `src/glitchygames/ui/sliders.py`

### 28. Sprite Format Linter
- **Description**: Comprehensive validation and linting tool for TOML sprite files to ensure format compliance and catch common errors
- **Started (2026-10-30)**: the pixel-row core exists. `normalize_pixel_rows` in strict mode and `palette_key_problems` (`src/glitchygames/sprites/pixel_utils.py`) reject ragged rows, blank lines between rows, glyphs missing from the palette and palette keys that aren't one code point; `check_rows_have_equal_lengths` runs them on every repo sprite (`docs/specs/2026-10-30-unified-pixel-rows-design.md`)
- **Use Case**: Essential for maintaining sprite file quality, catching format errors early, and ensuring compatibility across different sprite formats
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - **Format Validation**: Validate TOML syntax and structure compliance
  - **Sprite Structure Validation**: Verify sprite sections, animation structure, and frame data
  - **Color Map Validation**: Validate color definitions and glyph mappings
  - **Transparency Validation**: Check transparency glyph usage and alpha value consistency
  - **Performance Validation**: Detect inefficient color usage and suggest optimizations
  - **Cross-Format Compatibility**: Ensure compatibility between compact and animated formats
- **Validation Rules**:
  - **TOML Syntax**: Valid TOML structure and syntax
  - **Sprite Section**: Required fields (name, pixels) and proper format
  - **Animation Section**: Valid animation structure with proper frame data
  - **Color Section**: Valid color definitions with proper RGB/RGBA values
  - **Transparency Glyph**: Proper usage of `█` glyph (implied constant, not defined in colors)
  - **Frame Consistency**: Consistent frame dimensions and pixel data
  - **Animation Timing**: Valid frame intervals and duration values
- **Linting Features**:
  - **Error Detection**: Identify syntax errors, missing fields, and invalid values
  - **Warning System**: Flag potential issues and suggest improvements
  - **Format Suggestions**: Recommend optimal format (compact vs animated) based on content
  - **Color Optimization**: Suggest color palette optimizations and unused color removal
  - **Performance Analysis**: Analyze sprite efficiency and suggest improvements
- **Output Formats**:
  - **Console Output**: Detailed error/warning messages with line numbers
  - **JSON Report**: Machine-readable validation results for CI/CD integration
  - **HTML Report**: Visual validation report with highlighted issues
  - **Fix Suggestions**: Automatic fix suggestions for common issues
- **Integration Features**:
  - **CLI Tool**: Command-line interface for batch validation
  - **IDE Integration**: Integration with development environments
  - **CI/CD Integration**: Automated validation in build pipelines
  - **Real-time Validation**: Live validation during sprite editing
- **Advanced Features**:
  - **Custom Rules**: User-defined validation rules and constraints
  - **Rule Sets**: Predefined rule sets for different sprite types
  - **Batch Processing**: Validate multiple sprite files simultaneously
  - **Format Migration**: Suggest and perform format migrations
- **Technical Requirements**:
  - TOML parsing and validation engine
  - Sprite format specification compliance checker
  - Color palette analysis and optimization
  - Performance analysis algorithms
  - Integration with existing sprite loading system
- **Files to Create/Modify**:
  - `src/glitchygames/tools/sprite_linter.py` - Core linting engine
  - `src/glitchygames/tools/format_validator.py` - Format validation system
  - `src/glitchygames/tools/color_analyzer.py` - Color palette analysis
  - `src/glitchygames/tools/sprite_optimizer.py` - Performance optimization suggestions
  - `src/glitchygames/tools/cli_linter.py` - Command-line interface
  - `tests/tools/test_sprite_linter.py` - Linter validation tests
  - `tests/tools/test_format_validator.py` - Format validation tests
- **Validation Categories**:
  - **Critical Errors**: Syntax errors, missing required fields, invalid data types
  - **Warnings**: Potential issues, inefficient usage, deprecated patterns
  - **Suggestions**: Optimization opportunities, format improvements, best practices
  - **Info**: Format information, statistics, and analysis results
- **Format Specifications**:
  - **Compact Format**: Single-frame sprites with `[sprite]` section and `pixels` field
    - Uses `[colors."█"]` format (legacy support)
    - Implied `█` glyph for magenta transparency (not defined in colors)
    - Target audience: developers who want simple, readable sprite files
  - **Animated Format**: Multi-frame sprites with `[[animation]]` sections
    - Uses `"█" = { red = 255, green = 0, blue = 255 }` format (legacy support)
    - Implied `█` glyph for magenta transparency (not defined in colors)
    - Target audience: complex animations with multiple frames
- **Future Extensibility**:
  - Support for additional sprite formats (JSON, XML, binary)
  - Custom validation rule engine
  - Integration with sprite generation tools
  - Automated sprite optimization suggestions

### 29. Universal Undo/Redo System
- **Description**: Comprehensive undo/redo system for all editing operations in bitmappy
- **Use Case**: Essential for non-destructive editing, mistake recovery, and professional workflow
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - **Operation History**: Track all editing operations (pixel changes, frame modifications, etc.)
  - **Multi-Level Undo**: Support for multiple undo levels (default: 50 operations)
  - **Keyboard Shortcuts**: Ctrl+Z for undo, Ctrl+Shift+Z for redo
  - **Controller Support**: Circle button (B) for undo, Square button (X) for redo
  - **Visual Feedback**: Clear indication of undo/redo availability
  - **Memory Management**: Efficient storage of operation history
  - **Cross-Frame Undo**: Undo operations across different frames and animations
  - **Canvas Undo/Redo**: Undo/redo pixel-level changes on the canvas
  - **Film Strip Undo/Redo**: Undo/redo frame-level operations (add, delete, reorder frames)
- **Technical Requirements**:
  - Operation serialization and storage
  - Efficient memory management for history
  - Integration with existing editing systems
  - Performance optimization for large histories
  - **Canvas Integration**: Track pixel-level changes, brush strokes, color changes
  - **Film Strip Integration**: Track frame operations, animation changes, frame reordering
  - **Unified History**: Single undo/redo system that works across both areas
  - **Context Awareness**: Undo/redo operations respect current editing context
- **Files to Create/Modify**:
  - `src/glitchygames/bitmappy/history/undo_redo.py` - Core undo/redo system
  - `src/glitchygames/bitmappy/history/operations.py` - Operation tracking
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_undo_redo.py` - Undo/redo system tests

### 30. Pixel-Level Copy/Paste System
- **Description**: Advanced copy/paste functionality for pixel regions within frames
- **Use Case**: Efficient editing of sprite regions, pattern duplication, and detailed sprite work
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - **Selection Tools**: Rectangular selection, freehand selection, magic wand selection
  - **Copy Operations**: Copy selected regions to clipboard
  - **Paste Operations**: Paste with position control and blending options
  - **Multi-Selection**: Support for multiple selected regions
  - **Transform on Paste**: Rotate, flip, scale during paste operations
  - **Blending Modes**: Normal, overlay, multiply, screen blending options
- **Selection Features**:
  - **Rectangular Selection**: Click and drag to select rectangular areas
  - **Freehand Selection**: Lasso tool for irregular selections
  - **Magic Wand**: Select connected pixels of similar color
  - **Selection Modifiers**: Add to selection (Shift), subtract from selection (Ctrl)
- **Paste Features**:
  - **Position Control**: Precise positioning of pasted content
  - **Blending Options**: Various blend modes for natural integration
  - **Transform Tools**: Rotate, flip, scale pasted content
  - **Preview Mode**: See paste result before confirming
- **Files to Create/Modify**:
  - `src/glitchygames/tools/selection_tools.py` - Selection system
  - `src/glitchygames/tools/pixel_clipboard.py` - Pixel-level clipboard
  - `src/glitchygames/tools/transform_tools.py` - Transform operations
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_selection_tools.py` - Selection system tests

### 31. Multi-Frame Copy/Paste System
- **Description**: Copy and paste entire animations or frame sequences
- **Use Case**: Animation workflow efficiency, pattern reuse, and animation composition
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Frame Sequence Copy**: Copy multiple consecutive frames
  - **Animation Copy**: Copy entire animations with all frames
  - **Cross-Animation Paste**: Paste frames between different animations
  - **Frame Insertion**: Insert copied frames at specific positions
  - **Animation Merging**: Combine multiple animations
  - **Timing Preservation**: Maintain original frame timing and duration
- **Workflow Features**:
  - **Frame Range Selection**: Select start and end frames for copying
  - **Animation Browser**: Visual interface for selecting animations to copy
  - **Paste Options**: Insert, replace, or append frames
  - **Timing Control**: Adjust timing when pasting frames
- **Files to Create/Modify**:
  - `src/glitchygames/tools/animation_clipboard.py` - Animation clipboard system
  - `src/glitchygames/tools/frame_sequence_manager.py` - Frame sequence handling
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_animation_clipboard.py` - Animation clipboard tests

### 32. Advanced Clipboard Operations
- **Description**: Enhanced clipboard system with multiple slots and history
- **Use Case**: Professional workflow with multiple clipboard items and advanced operations
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Multiple Clipboard Slots**: Store multiple copied items (default: 10 slots)
  - **Clipboard History**: Access previously copied items
  - **Clipboard Browser**: Visual interface for managing clipboard items
  - **Format Support**: Support for different data formats (pixels, frames, animations)
  - **Clipboard Persistence**: Maintain clipboard across sessions
- **Advanced Features**:
  - **Clipboard Preview**: Thumbnail previews of clipboard items
  - **Clipboard Search**: Search through clipboard history
  - **Clipboard Export**: Save clipboard items to files
  - **Clipboard Import**: Load clipboard items from files
- **Files to Create/Modify**:
  - `src/glitchygames/tools/advanced_clipboard.py` - Advanced clipboard system
  - `src/glitchygames/tools/clipboard_browser.py` - Clipboard management UI
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_advanced_clipboard.py` - Advanced clipboard tests

### 33. Selection and Transform Tools
- **Description**: Comprehensive selection and transformation tools for sprite editing
- **Use Case**: Professional sprite editing with precise selection and transformation capabilities
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Selection Tools**:
    - Rectangular selection with precise positioning
    - Freehand/lasso selection for irregular shapes
    - Magic wand selection for color-based selection
    - Selection modification (add, subtract, intersect)
  - **Transform Tools**:
    - Rotate selected regions (90°, 180°, 270°, custom angles)
    - Flip selected regions (horizontal, vertical)
    - Scale selected regions (uniform and non-uniform scaling)
    - Skew and perspective transforms
  - **Selection Management**:
    - Save and load selections
    - Selection preview and confirmation
    - Selection constraints (aspect ratio, grid alignment)
- **Files to Create/Modify**:
  - `src/glitchygames/tools/selection_tools.py` - Selection system
  - `src/glitchygames/tools/transform_tools.py` - Transform operations
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_transform_tools.py` - Transform tools tests

### 34. System Clipboard Integration
- **Description**: Integration with system clipboard for external tool compatibility
- **Use Case**: Copy/paste between bitmappy and other applications, external tool workflow
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **System Clipboard Support**: Copy/paste to/from system clipboard
  - **Format Conversion**: Convert between bitmappy formats and standard formats
  - **Image Export**: Export selections as standard image formats
  - **External Tool Integration**: Work with external image editors
- **Supported Formats**:
  - PNG export/import for image data
  - JSON export/import for animation data
  - Custom format for bitmappy-specific data
- **Files to Create/Modify**:
  - `src/glitchygames/tools/system_clipboard.py` - System clipboard integration
  - `src/glitchygames/tools/format_converter.py` - Format conversion utilities
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_system_clipboard.py` - System clipboard tests

### 35. Undo/Redo Visualization
- **Description**: Visual representation of undo/redo history for better workflow understanding
- **Use Case**: Advanced users who need to understand their editing history and navigate complex undo stacks
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **History Timeline**: Visual timeline of all operations
  - **Operation Previews**: Thumbnail previews of each operation
  - **Branch Navigation**: Navigate different undo branches
  - **Operation Details**: Detailed information about each operation
  - **History Search**: Search through operation history
- **Visual Features**:
  - **Timeline View**: Horizontal timeline of operations
  - **Thumbnail Grid**: Grid view of operation snapshots
  - **Operation Tree**: Tree view of operation relationships
  - **Filter Options**: Filter operations by type, time, or scope
- **Files to Create/Modify**:
  - `src/glitchygames/tools/undo_visualization.py` - Undo/redo visualization
  - `src/glitchygames/tools/history_browser.py` - History management UI
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_undo_visualization.py` - Undo visualization tests

### 36. Batch Operations
- **Description**: Apply operations to multiple frames, animations, or sprites simultaneously
- **Use Case**: Efficient workflow for repetitive tasks and large-scale sprite operations
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Multi-Frame Operations**: Apply changes to multiple frames at once
  - **Animation-Wide Changes**: Apply operations to entire animations
  - **Batch Processing**: Process multiple sprites or animations
  - **Operation Templates**: Save and reuse operation sequences
  - **Progress Tracking**: Visual progress indicators for long operations
- **Batch Features**:
  - **Frame Range Operations**: Apply operations to frame ranges
  - **Animation Operations**: Apply operations to multiple animations
  - **Sprite Operations**: Apply operations to multiple sprites
  - **Operation Queuing**: Queue multiple operations for batch execution
- **Files to Create/Modify**:
  - `src/glitchygames/tools/batch_operations.py` - Batch operation system
  - `src/glitchygames/tools/operation_templates.py` - Operation template system
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `tests/tools/test_batch_operations.py` - Batch operations tests

### 37. Enhanced Drag-n-Drop Frame Updates
- **Description**: Extend drag-n-drop support to update selected frames or film strips rather than replacing existing content
- **Use Case**: Efficient workflow for updating specific frames, adding frames to animations, and targeted sprite modifications
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Frame-Specific Updates**: Drop files onto specific frames to update them
  - **Film Strip Integration**: Drop files onto film strip positions to insert/update frames
  - **Animation Preservation**: Maintain existing animation structure while updating content
  - **Smart Insertion**: Automatically determine whether to replace, insert, or append frames
  - **Visual Feedback**: Clear indication of drop targets and update operations
- **Update Modes**:
  - **Replace Mode**: Replace selected frame with dropped content
  - **Insert Mode**: Insert new frame at drop position
  - **Append Mode**: Add frame to end of animation
  - **Merge Mode**: Blend dropped content with existing frame
- **Drop Target Detection**:
  - **Frame Drop Zones**: Detect when dropping on specific frames
  - **Film Strip Drop Zones**: Detect when dropping on film strip positions
  - **Animation Drop Zones**: Detect when dropping on animation headers
  - **Smart Positioning**: Automatically position content based on drop location
- **Content Integration**:
  - **Size Matching**: Automatically resize dropped content to match target frame
  - **Format Conversion**: Convert between different sprite formats
  - **Color Palette Integration**: Merge color palettes when combining content
  - **Timing Preservation**: Maintain original frame timing and duration
- **User Experience**:
  - **Visual Drop Indicators**: Show valid drop zones and expected behavior
  - **Preview Mode**: Preview how content will be integrated before confirming
  - **Undo Support**: Full undo/redo support for drag-n-drop operations
  - **Conflict Resolution**: Handle conflicts when dropping incompatible content
- **Advanced Features**:
  - **Batch Frame Updates**: Drop multiple files to update multiple frames
  - **Animation Sequence Import**: Import entire animation sequences
  - **Smart Frame Detection**: Automatically detect frame boundaries in dropped content
  - **Content Validation**: Validate dropped content before integration
- **Technical Requirements**:
  - Enhanced drop zone detection system
  - Content integration and conversion algorithms
  - Visual feedback and preview system
  - Integration with existing undo/redo system
- **Files to Create/Modify**:
  - `src/glitchygames/tools/enhanced_drag_drop.py` - Enhanced drag-n-drop system
  - `src/glitchygames/tools/frame_updater.py` - Frame update operations
  - `src/glitchygames/tools/content_integration.py` - Content integration utilities
  - `src/glitchygames/bitmappy/editor.py` - Integration with main editor
  - `src/glitchygames/bitmappy/film_strip.py` - Enhanced film strip drop handling
  - `tests/tools/test_enhanced_drag_drop.py` - Enhanced drag-n-drop tests

### 38. Frame Alignment Command
- **Description**: A Bitmappy command that permanently re-aligns an animation's frames to a common anchor point, rewriting the pixel data
- **Use Case**: Art drawn top-aligned (like the Papyrus player, whose feet end on rows 24–27 depending on the frame) makes feet drift between frames. The engine can compensate at draw time with `AnimatedSprite.frame_anchor` (`FrameAnchor`), but fixing the art itself makes it correct everywhere, including Bitmappy's own preview, and removes the need for the setting
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Alignment modes**: The nine `FrameAnchor` points: top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right (e.g. bottom for walkers, center for spinners and floaters, top for hanging things)
  - **Reference**: Each frame's hitbox if defined, else its visible-pixel bounds; aligned to the sprite-level hitbox, else the union of all frames' hitboxes
  - **Rewrite**: Shift each frame's pixels within the fixed canvas and shift its per-frame hitbox by the same amount; refuse (with a message) when a shift would push visible pixels off the canvas
  - **Undo**: One undoable operation through the existing undo/redo system
  - **Preview**: Show the aligned animation before applying
  - **After applying**: Clear `frame_anchor` on the sprite if it was set, since the art no longer needs it
- **Files to Create/Modify**:
  - Bitmappy film strip / animation menu (new command)
  - `tests/tools/` - Alignment tests: every mode, hitbox shift, off-canvas refusal, undo

### 45. Sound Effects From a Description
- **Description**: Describe a sound effect in words ("a short wet pop, like a bubble bursting
  underwater", "a heavy mechanical clunk, then a slow hiss") and the engine works out how to make it:
  an LLM (or a rule-based process) plans one or more source sounds, and a chain of audio
  operations shapes them into the sound you asked for
- **Use Case**: Fast, reproducible sound design for games without a sound library or audio tools;
  iterate in plain language ("punchier", "an octave lower", "make the tail longer")
- **Status**: Planned (requested 2026-10-23)
- **Priority**: Medium
- **Implementation**:
  - **Plan from the description**: the LLM (through the existing AI client used for sprite
    generation, `src/glitchygames/ai/`) returns a structured plan (a pydantic model, validated): the
    source sounds and the operations to apply, in order. A rule-based fallback maps common words
    (pop, click, thud, whoosh, zap, chirp) to recipes when no model is available
  - **Source sounds**, any of:
    - synthesized: the existing toolkit (`src/glitchygames/audio/synth.py` oscillators, noise,
      envelopes, pitch curves) and `SoundRecipe`/`Tone` (`src/glitchygames/audio/recipes.py`)
    - spoken: words or syllables rendered with text-to-speech (`src/glitchygames/audio/tts.py`)
    - performed: the engine suggests sounds for you to make yourself ("say 'pop' with your lips
      closed", "click your tongue twice", "say 'tsss'") and records them from the microphone
      (the microphone capture script, `scripts/`), then trims the silence
  - **Operations** (the shaping chain, each with parameters the plan chooses):
    - pitch: shift by octaves or semitones, keeping the length (or resample to change both)
    - time: stretch or compress the length without changing the pitch (phase vocoder or a
      granular method), clip to a range, extend (loop with a crossfade, or a decaying tail)
    - dynamics: gain, compression, limiting, hard or soft clipping (distortion), envelope
      (attack, decay, sustain, release)
    - tone: low-, high- and band-pass filters (the existing FIR filters), EQ
    - layering: mix several sources with offsets (a click on top of a thud)
  - **Iterate**: preview the result, then refine with more words; the plan is updated, not
    regenerated from scratch, so a good result isn't lost
  - **Save it reproducibly**: store the plan (sources and operation chain) as a TOML recipe next to
    the rendered sound, so it can be regenerated and edited by hand; recorded sources are saved
    as files the recipe references. Rendering must be deterministic (seeded noise through the
    engine's random streams) so games and replays sound the same everywhere
- **Technical Requirements**:
  - DSP operations on numpy arrays at the mixer's format (44100 Hz, 16-bit, stereo), unit-tested
    against known signals (a sine's pitch after a shift, a length after a stretch)
  - A schema for the plan the LLM returns, with validation and clear errors for bad plans
  - Microphone capture with a device choice and silence trimming
  - An editor or command-line front end (e.g. a `glitchygames-sfx` console script, or a panel in
    Bitmappy or Glitchy Studio)

### 60. PaddleSlap: A Start Screen With Its Game Options — TODO
- **Description**: PaddleSlap is one game. "Rally" is not a mode: it is the score
  (`rally_count`, paddle hits across all balls), and `rally.jsonl.gz` (`PADDLESLAP_DEMO_PATH`) is
  the attract demo the game-over screen plays after it sits idle (`dt_tick`), recorded with the
  default options (1 ball, `paddle_only`). The game's real options are command-line flags only
  today: `--ball-spawn-mode` (`paddle_only`, the default: a new ball on each paddle hit;
  `wall_only`; `ball_only`; `frequent`; `rare`; `none`) and `--balls N` (balls at the start).
  Add a start screen that offers them as game options (the owner, 2026-10-27: "feels more like a
  game option"), with the flags still setting them (and skipping the screen when given, if that
  reads better).
- **Status**: TODO (requested by the owner 2026-10-27, after the Arcade spike gave the golden and
  the Rally demo a tile each: in the Arcade, PaddleSlap is one tile; the Rally demo stays its
  attract reel). To settle when it is planned: the screen's layout and input (keys, controller,
  mouse), whether the chosen options persist between runs (as the high scores do), that a
  recording keeps the options it was played with so `--replay-trace` starts with them and no
  screen, and that the golden and the Rally demo still replay identically (the screen must not
  shift a recorded frame; rebaseline only deliberately).
- **Priority**: Medium

### 64. Sound Engine: Sequences in Sound Files, and Music and Instrument Formats — DESIGN
- **Description**: A beat-based `[sequences]` table in sound files (the file form of M5's
  `Sequence`), `music = <path>` to read other music formats into it with loaders that work out a
  file's type, and `patch = <path>` for instrument formats. ABC first; then MIDI, Csound scores,
  MML, sfxr, SFZ, trackers and FM patches as the engine gains what each needs
- **Design**: `plans/2026-11-06-music-and-instrument-formats-design.md`
- **Status**: Design (requested by the owner 2026-11-03: ABC import is in scope, and "eventually
  support all of these formats, and wire them into our formats in ways that make sense")
- **Priority**: Medium

### 65. Sprites: Importing Sprite and Spritesheet Formats — DESIGN
- **Description**: A registry of sprite loaders (detected by extension, confirmed by content) and
  a `glitchygames sprite-import` converter that writes sprite TOML and reports what it could not
  carry over; Bitmappy opens the same formats. Aseprite first, then Aseprite JSON sheets,
  animated GIF and APNG, grid sheets, TexturePacker JSON and Tiled tilesets; libGDX, Godot,
  Unity and Piskel as needed. Replaces `LOADER_README.md`'s "Future Format Ideas"
- **Design**: `plans/2026-11-06-spritesheet-formats-design.md`
- **Status**: Design (requested by the owner 2026-11-06)
- **Priority**: Medium

### 70. Sound Engine: Every Musical Instrument Known to Man — BATCH 13 DONE
- **Description**: Grow the instrument catalog from 431 instruments (439 in 21 families after
  batch 1, 448 in 23 after batch 2, 624 after batch 3, 658 after batch 4, 671 after batch 5, 682
  after batch 6, 684 after batch 7, 685 after batch 8, 688 after batch 9, 690 after batch 10, 692 after batch 11, 693 after batch 12, 703 after batch 13) toward every instrument a game might
  want, in one verified batch per family. Adversarial audits (2026-11-07) found 1,303 candidates,
  only 84 with
  source-verified ranges. Adds five families (plucked idiophones, friction instruments, noise
  makers, sound effects, and electromechanical, which takes the electric pianos, Clavinet and
  tonewheel organs from keyboards and organs), makes mechanical instruments a tag, and lists
  the instruments that wait for engine features (sympathetic strings, moving formants, FM,
  samples); every sound effect is usable in music.
  Batch 1 (plucked idiophones, friction instruments, noise makers, tags and aliases) is done:
  of its 79 audited candidates 8 shipped, 4 moved family, 58 wait for engine features, 4 became
  aliases and 5 were dropped.
  Batch 2 (electromechanical and sound effects) is done: of its 62 audited candidates (30
  electromechanical, 32 sound effects) 9 shipped, 10 moved family, 11 wait for engine
  features, 4 became aliases and 28 were dropped.
  Batch 3 (drums and percussion) is done: of its 255 sheet rows 45 shipped (their own builds),
  131 became sound-alikes (entries of their own that share a parent's build, `sounds_like`), 29
  wait for engine features, 27 became aliases and 23 were dropped; the family grew from 61 to
  237 entries. The audit's "Gaps you could not close"
  (`plans/data/instrument-audit/drums-and-percussion.md`: MIMO, the Met, Horniman and Grove
  unconsulted, truncated Wikipedia lists, Korean, Cuban, Oceanian, Indigenous American and
  Eastern European names never searched) are a later pass over this family. `agung`, `tingsha`
  and `teponaztli` also have tuned-percussion audit rows (`merged.tsv`) and shipped here under
  those names, so the tuned percussion batch must not ship them again.
  Batch 4 (plucked strings) is done: of its 284 sheet rows 7 shipped (their own builds), 27
  became sound-alikes (each giving its own sourced range), 215 wait (166 for a sourced range, 21
  for engine features and 28 because their target waits), 19 became aliases and 16 were dropped;
  the family grew from 58 to 92 entries. Most rows wait because the owner ruled the range rule
  stays strict (2026-11-09, asked directly: "Keep it strict"): an instrument with no sourced
  range waits. A later pass can range them from maker or museum sources, since each WAIT row's
  notes record what was searched. The audit's "Gaps you could not close"
  (`plans/data/instrument-audit/plucked-strings.md`) are a later pass too.
  Batch 5 (tuned percussion) is done: of its 164 sheet rows 2 shipped (their own builds,
  `boomwhackers` and `gangsa`), 11 became sound-alikes (each giving its own sourced range), 93
  wait (82 for a sourced range, 4 for engine features and 7 because their target waits), 14
  became aliases and 44 were dropped; the family grew from 23 to 36 entries (671 in all, 68
  aliases and 169 sound-alikes). Most rows wait because the range rule stays strict. The
  audit's "Gaps you could not close" (`plans/data/instrument-audit/tuned-percussion.md`: the
  Chinese, Japanese, Korean, Indian, African, Oceanic and Philippine names it suspected but did
  not confirm) are a later pass over this family.
  Batch 6 (electronic) is done: of its 161 sheet rows 1 shipped (its own build, `nes triangle`),
  10 became sound-alikes (sound chips and drum-machine voices; the chips give their own sourced
  range), 56 wait (13 for a sourced range, 43 for engine features or because their target
  waits), 5 became aliases and 89 were dropped; the family grew from 15 to 26 entries (682 in
  all, 73 aliases and 179 sound-alikes). `Tag.CHIP` is the second tag, on nine entries. The
  audit's "Gaps you could not close" (`plans/data/instrument-audit/electronic.md`: MIMO, the
  Met, Horniman and Grove unconsulted; the SPC700, YM2413, VIC-20, Ensoniq, Waldorf, Nord Lead,
  Korg Wavestation and the rest it suspected but did not list) are a later pass over this family,
  along with ranging the range WAIT rows
  from manuals and datasheets.
  Batch 7 (bowed strings) is done: of its 138 sheet rows (126 candidates and 12 audit alias
  lines) none shipped as a build of its own, 2 became sound-alikes (`viola pomposa` of `viola`,
  `bowed psaltery` of `violin`, each giving its own sourced range), 118 wait (90 for a sourced
  range, 7 for a sourced drone tuning, 7 because their target waits, 7 for sympathetic strings or
  a buzzing bridge, 2 for sub-audio fundamentals, 2 for more than four sources, 2 for a build of
  their own, 1 for a buzzing bridge), 5 became aliases and 13 were dropped; the family grew from
  27 to 29 entries (684 in all, 78 aliases and 181 sound-alikes). Most rows wait because the range
  rule stays strict: a bowed string's audit range is mostly its open strings. The audit's "Gaps
  you could not close" (`plans/data/instrument-audit/bowed-strings.md`: MIMO, the Met and Horniman
  unconsulted; the huqin names it did not row, such as `erquanqin`, `jing erhu`, `datong`,
  `leiqin`; `kontra`, `latfiol` and the Apache fiddle; Ethiopian, Sahel, Malagasy, Oceanian,
  Andean and Caribbean fiddles) are a later pass over this family, along with ranging the 90
  range WAIT rows from maker and museum sources. `viola organista` is decided here (it waits for
  a build of its own), so the keyboards batch must not decide it again.
  Batch 8 (voices and choirs) is done: of its 138 sheet rows (110 candidates and 28 audit alias
  names, on 16 lines) none shipped as a build of its own (the plan's Task 5, the choir vowels'
  build, was skipped by ruling: no choir row shipped), 1 became a sound-alike (`basso buffo ah`
  of `bass ah`, E2-F4, from Wikipedia's Fach page), 64 wait (32 for a sourced range, 14 for
  moving formants, 2 for a buzzing membrane, 1 for a pitch LFO (vibrato), 1 for its own build
  and 14 because their target waits), 2 became aliases (`contralto` of `alto ah`, `boy soprano`
  of `treble ah`) and 71 were dropped (46 voices, 25 choirs); the voices grew from 55 to 56
  entries and the choirs stayed at 13 (685 in all, 80 aliases and 182 sound-alikes). Most rows
  wait or drop because only four kinds of thing are instruments here (voice types, voice
  devices, choir parts and choir vowels) and the range rule stays strict: a hedged, extreme or
  self-contradicting range is no range. The audit's "Gaps you could not close"
  (`plans/data/instrument-audit/voices-and-choirs.md`: Fach ranges no source gave; Kunqu, ca
  trù, Albanian iso-polyphony, Maori karanga and the other traditions it did not research; MIMO,
  the Met, Horniman and Grove unconsulted) are a later pass over these families. `vox humana`
  and `voix celeste` are organ stops: the organs batch decides them. `kazoo` and `swazzle` are
  decided here (each waits for a buzzing membrane).
  Batch 9 (flutes) is done: of its 146 sheet rows (119 candidates and 27 audit alias names) none
  shipped as a build of its own, 3 became sound-alikes (`csakan` of `soprano recorder`,
  Ab4-Eb7; `subcontrabass recorder` of `contrabass recorder`, F1-G3; `ryuteki` of `bansuri`,
  E5-D7, each giving its own sourced range), 131 wait (94 for a sourced range, 18 because their
  target waits, 5 for a build of their own, 3 for a pitch LFO (vibrato), 3 for a pitch LFO
  (portamento between notes), 3 for a buzzing membrane, 2 for a sourced drone tuning, 1 for
  sub-audio fundamentals, 1 for more than four sources, 1 for moving formants), 5 became aliases
  (`penny whistle`, `jula jula`, `julu julu`, `syrinx`, `siyotanka`) and 7 were dropped; the
  family grew from 30 to 33 entries (688 in all, 85 aliases and 185 sound-alikes). `flutes.py`
  now holds the family (moved unchanged from `winds.py`, which keeps the five reed families) and
  `flute_sound_alikes.py` its sound-alikes. Most rows wait because the range rule stays strict:
  a flute's source rarely states both notes as sounding pitch. The audit's "Gaps you could not
  close" (`plans/data/instrument-audit/flutes.md`: MIMO, the Met, Horniman and Grove
  unconsulted; `List_of_flutes` unresolved; the `satara`, `jodi pava`, `pulangkuzhal`, the
  Persian ney sizes, `kiz neyi`, `sring`, `shoor`, `choor`, `shembeko`, `suling degung`, Korean
  `ji`, Chinese `yue`, `koudi`, `pfeife`, `piffero`, `txistu`, `galoubet`, `flabiol`,
  `tubulum`, keyboard-flute hybrids and bamboo flute sizes by key it suspected but did not
  confirm) are a later pass over this family. The hand-offs are decided here: `steam whistle`
  (waits for a sourced range), `boatswains call` (a sourced range), `pea whistle` (a pitch LFO,
  vibrato), `duck call` (a build of its own: its source names reeds), `bird whistle` (a pitch
  LFO, vibrato), `singing bird box` (a pitch LFO, portamento), `hydraulophone` (a sourced
  range; `hs` none) and `pigeon whistle` (more than four sources). `serinette` and `flute clock`
  are barrel organs, so the organs batch decides them.
  Batch 10 (brass) is done: of its 127 sheet rows (104 candidates and 23 audit alias names) none
  shipped as a build of its own, 2 became sound-alikes (`bass wagner tuba` of `wagner tuba`,
  Eb1-F5; `soprano trombone` of `trumpet`, E3-C6, each giving its own sourced range), 99 wait (80
  for a sourced range, 13 because their target waits, 2 for a build of their own, 2 for moving
  formants, 1 for sub-audio fundamentals, 1 for a buzzing membrane), 16 became aliases and 10
  were dropped; the family grew from 42 to 44 entries (690 in all, 101 aliases and 187
  sound-alikes). `brass.py` keeps the family's builds (its table is now `_BRASS_BUILDS`, and
  `BRASS` is `_BRASS_BUILDS + BRASS_SOUND_ALIKES`) and `brass_sound_alikes.py` holds its
  sound-alikes. `didgeridoo` joins `APPROXIMATING_NAMES`, never a parent, and `BRASS_HELD_BACK`
  holds back six names (`bazooka`, `didjeribone`, `subcontrabass tuba`, `sudrophone`, `tenor
  cornett`, `vienna horn`). Most rows wait because the range rule stays strict: a brass source
  rarely states both notes as sounding pitch, and many give a written range with no
  transposition, a hedge, a player's top or one note. The audit's "Gaps you could not close"
  (`plans/data/instrument-audit/brass.md`: the list-of-brass page unread; MIMO, the Met and Grove
  not swept; the African, Pacific, Amazonian, Native American and Southeast Asian horns beyond
  Wikipedia's category, such as Moche clay trumpets and Philippine bamboo trumpets; the marching
  and double-bell variants known only from memory) are a later pass over this family.
  `corrugahorn` is decided (batch 1 waits it for a sourced range, in noise makers), but its
  family question, noise makers or brass, is still open. The mutes are left to the
  articulations design (the spec's Non-goals).
  Batch 11 (double reeds) is done: of its 116 sheet rows (80 candidates and 36 audit alias names)
  none shipped as a build of its own, 2 became sound-alikes (`contraforte` of `contrabassoon`,
  A0-G4; `piccolo heckelphone` of `heckelphone`, E4-A6, each giving its own sourced range), 82 wait
  (61 for a sourced range, 19 because their target waits, 1 for a sourced drone tuning, 1 for its
  own build: `balaban`, a cylindrical bore), 11 became aliases (`cor anglais`, `baritone oboe`, `fagott`, `cervelas`,
  `gyaling`, `zurla`, `bombard`, `surna`, `surnay`, `zournas`, `haidi`) and 21 were dropped; the
  family grew from 23 to 25 entries (692 in all, 112 aliases and 189 sound-alikes).
  `double_reeds.py` now holds the family (moved unchanged from `winds.py`, which keeps the
  clarinets, saxophones, bagpipes and free reeds; its table is `_DOUBLE_REED_BUILDS`, and
  `DOUBLE_REEDS` is `_DOUBLE_REED_BUILDS + DOUBLE_REED_SOUND_ALIKES`) and
  `double_reed_sound_alikes.py` its sound-alikes. `piri` joins `APPROXIMATING_NAMES`, never a
  parent (its page cites a cylindrical bore the catalog's conical build lacks), and
  `DOUBLE_REED_HELD_BACK` holds two names (`aulos`, `balaban`). Most rows wait because the range rule stays
  strict: a double reed's source rarely states both notes as sounding pitch, and many give a
  width, a hedge, a "theoretical" span or a written range with no transposition. The audit's
  "Gaps you could not close" (`plans/data/instrument-audit/double-reeds.md`: the quint and quart
  bassoons, `fagottino` or `octavin`, the subcontrabassoon and the reed contrabass; the dulcian,
  rackett and shawm sizes beyond the candidates; the Korean piri variants, the Okinawan rappa,
  the Philippine, Uzbek and Tajik surnay, the Nepalese sahanai, the Mongolian and Tibetan shawms;
  MIMO, the Met, the Horniman and Grove unconsulted; the Koizumi, Horniman and Edinburgh
  catalogues not reached for the folk shawms) are a later pass over this family. The hand-offs are
  decided here: `zukra` is dropped to the bagpipes batch (its page: "a Libyan bagpipe"),
  `ciaramella` is decided (its fetched page makes the name the mouth-blown shawm, so it waits for
  `piffero`; the bagpipe, `ciaramedda`, is the bagpipes batch's), `musette` (the bagpipe) and
  `dulciana` (the organ stop) are dropped as ambiguous names (the unambiguous `oboe musette`
  waits for `piccolo oboe`), and `piffero` is decided as the shawm (it waits for a sourced range;
  batch 9's flute gap list names the fife sense, which is that batch's).
  Batch 12 (bagpipes) is done: of its 91 sheet rows (66 candidates and 25 audit alias names) 1
  shipped as a build of its own (`sackpipa`, the Swedish bagpipe: Säckpipa in A, E4-E5, one drone
  at E4, and the family's first cylindrical chanter, `CYLINDRICAL_CHANTER_LEVELS`), none became a
  sound-alike, 62 wait (57 for a sourced range and 5 because their target waits), 4 became aliases
  (`irish pipes` of `uilleann pipes`, `lowland pipes` and `half long pipes` of `border pipes`,
  `gaita galega` of `galician gaita`) and 24 were dropped; the family grew from 8 to 9 entries
  (693 in all, 116 aliases and 189 sound-alikes). `bagpipes.py` now holds the family (moved
  unchanged from `winds.py`, which keeps the clarinets, saxophones and free reeds; its table is
  `_BAGPIPE_BUILDS`, and `BAGPIPES` is `_BAGPIPE_BUILDS + BAGPIPE_SOUND_ALIKES`) and
  `bagpipe_sound_alikes.py` its sound-alikes (empty). The retuned sound-alike mechanism is in
  place, a sound-alike whose sourced drones differ from its parent's carrying
  `sound_changes={'drones': ...}` (decision 8's first shipped use, listed in the test table
  `BAGPIPE_RETUNED_DRONES`), but none shipped: the one candidate, the Czech `dudy`, went back to
  waiting for a range. `scottish smallpipes` joins `APPROXIMATING_NAMES`, never a parent (the
  Bagpipe Society's guide: "With its cylindrical bore"), and `BAGPIPE_HELD_BACK`, the guard for
  every wait that is not for a range, holds nothing. Nearly every row waits because the range
  rule stays strict: a bagpipe's source gives a key, a width, note letters with no octave or a
  relation, almost never both sounding notes. The base of the branch is `c0f9e622` (batch 11's
  fix commit). The audit's "Gaps you could not close"
  (`plans/data/instrument-audit/bagpipes.md`: absolute chanter ranges for nearly everything; MIMO
  and Grove unreached, the National Museum of Scotland and Edinburgh (MIMEd) records unread; `karkm`, `shyuvr`,
  `puvama`, `shapar`, `muchosa`, `samponha`, `sourdeline`, `loure`, `pipasso`, `musette bressane`,
  `musette bechonnet`, the Lincolnshire, Yorkshire and Lancashire pipes, `il-qrajna`,
  `sierszenki`, `kozioł biały` and `czarny`; the Central Asian, Tibetan, East and Southeast Asian,
  sub-Saharan and Latin American bagpipes; the Galician gaita's other keys, `grileira`,
  `redonda` and `tumbal`) are a later pass over this family. The hand-offs are decided here:
  `zukra` (a Libyan bagpipe, its bag form this family's) and `ciaramedda` (the Sicilian double
  chanter) wait for a sourced range, `ciaramella` stays batch 11's (the sheet's row drops it,
  naming batch 11's), `electronic bagpipe` is dropped to the electronic family (an electrophone
  that imitates the Highland pipe; the electronic batch is done, so a later electronic pass
  decides it), and no name the sheets found belongs to the organs batch.
  Batch 13 (organs) is done: of its 70 sheet rows (64 candidates and 6 audit alias names) 3
  shipped as builds of their own (`stopped diapason`, with `STOPPED_FLUTE_LEVELS`; `cornet
  organ`, five unbroken ranks summed into one wave by `compound_stop_levels`; and `organ
  clarinet`, with `CLOSED_REED_LEVELS`), 7 became sound-alikes (`bourdon` of `stopped diapason`
  at 16', C2-G4 on the pedal; `salicional` and `voix celeste` of `pipe organ string`; `organ
  oboe`, `organ tuba` and `posthorn` of `pipe organ reed`; `organ krummhorn` of `organ
  clarinet`, each giving its own sourced range), 32 wait (14 for a sourced range, 5 for a sourced
  footage, 5 for a range above C8, 2 for more than four sources, 3 for a build of their own, 1
  for a pitch and amplitude LFO and 2 because their target waits), 4 became aliases (`open
  diapason` of `pipe organ principal`, `organ trompette` of `pipe organ reed`, `air calliope` and
  `calliaphone` of `calliope`) and 24 were dropped; the family grew from 9 to 19 entries (703 in
  all, 120 aliases and 196 sound-alikes). `organs.py` now holds the family (moved unchanged from
  `keyboards.py`, which keeps the keyboards and the electromechanical instruments; its table is
  `_ORGAN_BUILDS`, and `ORGANS` is `_ORGAN_BUILDS + ORGAN_SOUND_ALIKES`) and
  `organ_sound_alikes.py` its sound-alikes. The footage mechanism is new: a stop sounds at its
  footage against its keys (`_pipe_stop`'s `footage`, carried by `blown`'s `semitones`), and a
  sound-alike stop at another footage than its parent carries it as
  `sound_changes={'footage': ...}` (`bourdon`, the only one; the test table is
  `ORGAN_STOP_FOOTAGES`). No self-playing organ shipped (each waits for a sourced range), so
  `Tag.MECHANICAL` is still only on the `music box` and `MECHANICAL_ORGAN_NAMES` is empty.
  `ORGAN_HELD_BACK`, the guard for every wait that is not for a range, holds 16 names
  (`diaphonic diapason`, `gedeckt`, `kinura`, `larigot`, `nasard`, `organ bombarde`, `organ
  mixture`, `organ trombone`, `piccolo organ`, `rohrflote`, `scharff`, `sesquialtera`,
  `spitzflote`, `tierce`, `vox humana` and `bible regal`). The base of the branch is `5cbbf882`
  (batch 12's final review fixes). The audit's "Gaps you could not close"
  (`plans/data/instrument-audit/organs.md`: the hydraulis's Aquincum data; the MIMO and Met regal
  and barrel organ records unopened; the kinura, posthorn and diaphonic diapason needing a theatre
  organ source; Lowrey, Baldwin and the Compton Electrone unread; the Cavaillé-Coll stops (flûte
  harmonique, gambe), the Spanish horizontal reeds (trompeta real, chirimía), the Dutch hoboy,
  schalmei and rankett stops, the Welte Philharmonie organ, Wurlitzer opus lists, Allen, Rodgers
  and digital organs; theatre organ percussion, which is tuned percussion's; the bell organ) are a
  later pass over this family. The hand-offs are decided here: `vox humana` (waits for the
  tremulant, with `kinura`, `regal` and `bible regal` sharing a short-resonator trait),
  `voix celeste` (a sound-alike), `serinette` and `flute clock` (each waits for a sourced
  range), `kinura` (waits for a build of its own) and `band organ` (waits for a sourced range)
  are decided here; `dulciana` and `gemshorn` stay as earlier sheets decided them (batch 11's
  and batch 9's); `orchestrion` and `reed organ` are decided here (`orchestrion` waits for a
  sourced range, `reed organ` is dropped to free reeds), so the keyboards and free reeds batches
  must not decide them again; `orchestrelle` is the free reeds batch's; each electric organ is
  dropped to electronic or electromechanical for a later pass of those families (`lowrey organ`,
  `baldwin organ` and `farfisa` to electronic, `compton electrone` and `choralcelo` to
  electromechanical, `hammond b3` and `telharmonium` already decided there, `vox continental`
  an existing alias of `combo organ`); and `chromelodeon` is dropped to free reeds. No name the
  sheets found belongs to the clarinets batch. Next: clarinets
- **Design**: `plans/2026-11-07-instrument-catalog-expansion-design.md`
- **Plan**: `plans/2026-11-07-instrument-catalog-batch-1-implementation.md`; audit sheet
  `plans/data/instrument-audit/batch-1.tsv`
- **Plan (batch 2)**: `plans/2026-11-08-instrument-catalog-batch-2-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-2.tsv`
- **Plan (batch 3)**: `plans/2026-11-08-instrument-catalog-batch-3-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-3.tsv`
- **Plan (batch 4)**: `plans/2026-11-09-instrument-catalog-batch-4-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-4.tsv`
- **Plan (batch 5)**: `plans/2026-11-11-instrument-catalog-batch-5-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-5.tsv`
- **Plan (batch 6)**: `plans/2026-11-12-instrument-catalog-batch-6-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-6.tsv`
- **Plan (batch 7)**: `plans/2026-11-12-instrument-catalog-batch-7-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-7.tsv`
- **Plan (batch 8)**: `plans/2026-11-12-instrument-catalog-batch-8-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-8.tsv`
- **Plan (batch 9)**: `plans/2026-11-12-instrument-catalog-batch-9-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-9.tsv`
- **Plan (batch 10)**: `plans/2026-11-12-instrument-catalog-batch-10-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-10.tsv`
- **Plan (batch 11)**: `plans/2026-11-12-instrument-catalog-batch-11-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-11.tsv`
- **Plan (batch 12)**: `plans/2026-11-12-instrument-catalog-batch-12-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-12.tsv`
- **Plan (batch 13)**: `plans/2026-11-12-instrument-catalog-batch-13-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-13.tsv`
- **Status**: Batches 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 and 13 done (requested by the owner 2026-11-06)
- **Priority**: Medium

### 71. Sound Engine: The Owner's Checks on Instrument Catalog Batch 2 — TODO
- **Goal**: confirm or overturn the calls made while batch 2 of #70 ran, and listen to its new
  instruments (the owner, 2026-11-08: "make note of those checks")
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and glide below is sound design, not sourced):
  - [ ] `hohner pianet` against `reed electric piano`: distinct enough to be two entries (the
    anti-goal), and does the Pianet's bright strike settle as its source describes?
  - [ ] The eight sound effects (`build/instruments/sound effects/`): thunder sheet, rain
    machine, ocean drum, cannon, crash box, coconut shells, door slam, giants footsteps
  - [ ] `thunder sheet`: `drum`'s one `attack` also swells its 120 Hz metal-ring tone, not
    only the noise
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-2.tsv`):
  - [ ] `thunder run` waits for an amplitude LFO (its separate ball impacts), as fire crackle
    does, rather than shipping as a smooth rumble
  - [ ] `sandpaper blocks` is dropped to drums and percussion (batch 3), like the washboard
    and rain stick
  - [ ] `gunshot`, `snow crunch` and `bone crack` are dropped as Foley tricks, not devices
  - [ ] `rain stick` is a percussion instrument (batch 3), not an alias of `rain machine`
  - [ ] `rumble cart` stays DROP; its note says it would wait for the same feature as the
    thunder run (WAIT instead is one cell)
  - [ ] `thunder sheet` ships although it is shaken slowly then quickly
  - [ ] The Pianet is built with `struck` (harmonics 1–4, higher ones ringing shorter)
  - [ ] Electric guitars, basses, violins and steels stay in their string families rather
    than electromechanical; `combo organ` stays in organs (H-S 53)
  - [ ] The tine electric piano (E1–E7) and tonewheel organ (C2–C7) ranges are kept from the
    catalog: no fetched source gives their ends
- **Follow-ups**:
  - [ ] Brand aliases a game developer would type (`fender rhodes`, `rhodes piano`,
    `hammond organ`), each sourced in the sheet
  - [ ] The tonewheel source comment quotes "near an electromagnetic pickup"; the sheet quotes
    "in front of"; align both with the Hammond organ page
  - [ ] CI: the macOS syft and grype install (`.circleci/config.yml`, `install_release`) makes
    one `curl` attempt, so a GitHub 504 fails the job (PR #162's first run); add
    `--retry 5 --retry-delay 5 --retry-all-errors`
- **Found**: batch 2's reviews and final whole-branch review (2026-11-08)
- **Status**: TODO
- **Priority**: Medium (before batch 3 builds on the family boundaries)

### 73. Sound Engine: The Owner's Checks on Instrument Catalog Batch 3 — TODO
- **Goal**: confirm or overturn the calls made while batch 3 of #70 ran, and listen to its new
  instruments (drums and percussion, 61 to 237 entries; the owner, 2026-11-08: "I want them to
  all show up")
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and glide is sound design, not sourced; the folder is
  `build/instruments/drums and percussion/`). The 45 new builds come first, then the
  sound-alikes; each group below is a parent with the sound-alikes that share its build, which
  must sound alike by design:
  - [ ] The 45 new builds: `bendir`, `bombo leguero`, `chenda`, `daf`, `dhol`, `dholak`,
    `field drum`, `gong bass drum`, `janggu`, `kanjira`, `kebero`, `kendang`, `kendang ageng`,
    `ketipung`, `khol`, `lambeg drum`, `mridangam`, `naqareh`, `otsuzumi`, `pandeiro`,
    `piccolo snare`, `pipe band snare`, `thavil`, `agung`, `anvil`, `bak`, `daluo`,
    `flat ride cymbal`, `garamut`, `ghatam`, `gongue`, `guira`, `jing`, `jingle bells`,
    `karkabou`, `kemanak`, `khartal`, `kkwaenggwari`, `lagerphone`, `sizzle cymbal`,
    `tiger gong`, `tingsha`, `udu`, `washboard`, `xiaoluo`: each distinct from the 61 already
    there and from each other (the anti-goal; the rule-7 test only catches equal builds)
  - [ ] Near pairs to hear side by side: `garamut` and `janggu` and `kendang`, `anvil` and
    `kkwaenggwari`, `bak` and `otsuzumi`, `washboard` and `castanets`
  - [ ] The sound-alikes, 131 in 52 groups (each is its parent's sound):
  - [ ] `paiban`, `sasara` of `bak`
  - [ ] `cultrun`, `damphu`, `parai`, `sakara drum`, `uchiwa daiko` of `bodhran`
  - [ ] `afoxe`, `axatse`, `shekere` of `cabasa`
  - [ ] `chuk`, `gome` of `cajon bass`
  - [ ] `bones`, `spoons` of `castanets`
  - [ ] `bo` of `china cymbal`
  - [ ] `hyoshigi`, `lummi stick` of `claves`
  - [ ] `dabakan` of `conga slap`
  - [ ] `atabaque`, `bamboula`, `bata drum`, `candombe drums`, `kpanlogo`, `kundu`, `makuta`,
    `ngoma`, `tambora`, `timbal` of `conga`
  - [ ] `crash ride cymbal` of `crash cymbal`
  - [ ] `khanjani` of `daf`
  - [ ] `tombak`, `tumbaknari` of `darbuka doum`
  - [ ] `bangu`, `tamborim`, `trong chau` of `darbuka tek`
  - [ ] `davul`, `dhak`, `dohol`, `dollu`, `tabl`, `zabumba` of `dhol`
  - [ ] `bougarabou` of `djembe bass`
  - [ ] `ashiko`, `sabar`, `tifa` of `djembe tone`
  - [ ] `marching snare`, `tabor` of `field drum`
  - [ ] `elathalam`, `kecer`, `manjira` of `finger cymbals`
  - [ ] `dunun` of `floor tom`
  - [ ] `tar drum` of `frame drum`
  - [ ] `ikoro`, `semantron`, `slit drum`, `teponaztli`, `txalaparta` of `garamut`
  - [ ] `ferrinho`, `frottoir`, `guayo` of `guira`
  - [ ] `eo`, `esterilla`, `reco reco` of `guiro`
  - [ ] `puniu`, `tbilat` of `high bongo`
  - [ ] `gudugudu`, `repinique` of `high timbale`
  - [ ] `kakko`, `octoban`, `okedo daiko`, `shime daiko`, `urumi` of `high tom`
  - [ ] `ghungroo`, `turkish crescent` of `jingle bells`
  - [ ] `kendang ciblon`, `kendang wadon`, `klong khaek`, `madal`, `samphor`, `taphon`, `trong
    com` of `kendang`
  - [ ] `chimta`, `triccaballacca` of `khartal`
  - [ ] `stomp box` of `kick drum`
  - [ ] `chengila`, `shoko` of `kkwaenggwari`
  - [ ] `igba` of `low bongo`
  - [ ] `sangban` of `low tom`
  - [ ] `caxirola`, `caxixi`, `hosho` of `maracas`
  - [ ] `concert tom`, `kenkeni`, `tanggu` of `mid tom`
  - [ ] `maddalam`, `pakhavaj` of `mridangam`
  - [ ] `tasha` of `naqareh`
  - [ ] `bedug`, `fontomfrom`, `gbedu`, `thunder drum`, `tsuri daiko` of `orchestral bass drum`
  - [ ] `popcorn snare` of `piccolo snare`
  - [ ] `rainstick` of `rain machine`
  - [ ] `ganza` of `shaker`
  - [ ] `swish cymbal` of `sizzle cymbal`
  - [ ] `sandpaper blocks` of `snare brush`
  - [ ] `caixa malacacheta`, `tarol` of `snare drum`
  - [ ] `dhimay`, `tan tan` of `surdo`
  - [ ] `alfaia`, `buk`, `hira daiko`, `jwago`, `kus`, `nagado daiko` of `taiko`
  - [ ] `pandero jarocho`, `rebana`, `sistrum` of `tambourine`
  - [ ] `ekwe`, `moktak` of `temple block`
  - [ ] `thunder tube` of `thunder sheet`
  - [ ] `atumpan`, `carimbo`, `huehuetl`, `pahu` of `tumba`
  - [ ] `quijada` of `vibraslap`
  - [ ] `cata`, `jam block`, `shishi odoshi` of `woodblock`
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-3.tsv`; the sheet's counts:
  SHIP 45, SOUND_ALIKE 131, WAIT 29, ALIAS 27, DROP 23):
  - [ ] Sound-alikes: each is an entry of its own sharing its parent's build (decision 8). The
    groups under Listen name each parent; confirm none should rather be an alias (`riq` and
    `doira` are ALIAS rows of `daf`, `tavil` of `thavil`) or a drum of its own build
  - [ ] WAIT, amplitude LFO: `damaru`, `lions roar`, `binzasara`, `ratchet`, `bell tree`, `mark
    tree` and `flexatone` (the last three with a stepped or bent pitch)
  - [ ] WAIT, a pitch the sequence moves through a phrase (the squeezed cords): `talking drum`,
    `idakka`, `kotsuzumi`, `udukku`
  - [ ] WAIT, a filter LFO: `water drum`; a pitch LFO: `wobble board`
  - [ ] WAIT because their target waits: `den den daiko` and `pellet drum` (target `damaru`),
    `lion roar` (`lions roar`), `edakka` (`idakka`), and `dundun`, `gangan`, `kalangu`, `dan
    karbi`, `tama`, `tamma`, `tamanin`, `donno`, `lunna`, `odondo`, `doodo`, `obodom` (`talking
    drum`)
  - [ ] Fixed tones: tonic-tuned drums and fixed-pitch gongs ship with one fixed tone (the pitch a
    game gives is ignored): `mridangam` (280 Hz, tuned to the singer, so a fixed tone as the
    catalog tabla bayan is), `agung` (110 Hz), `jing` (205 Hz), `kemanak` (600 Hz), `ghatam` (240
    Hz), `tiger gong` (175 Hz falling), `tingsha` (2350 Hz), `udu` (73 Hz sliding to 137 Hz),
    `daluo` (330 Hz falling) and `xiaoluo` (360 Hz rising)
  - [ ] Strokes shipped: each drum ships one struck sound (a two-headed drum's bass and treble
    heads blended in one hit; no slaps, rolls or open and closed strokes as separate entries), so
    `kendang`, `kendang ageng` and `ketipung` are three drums, not three strokes
  - [ ] The two-half split: membranophones (Hornbostel-Sachs class 2) and everything else (class 1)
    were built in two halves, and the sound-alikes of the second half sit in
    `drum_sound_alikes.py` beside the first half's; confirm the split reads right to a person
    adding the next entry
  - [ ] `bossed gong` is an ALIAS of the tuned percussion family's `tuned gong`, and `chau gong`
    of `tam tam`
- **Follow-ups**:
  - [ ] `candombe drums` (three sizes) is one sound-alike of `conga`; split into three, or keep
    one
  - [ ] `riq` is an ALIAS of `daf` by a redirect; a sound-alike if a source separates them
  - [ ] `kendang ciblon` is the drum `kendang` builds: alias or sound-alike
  - [ ] `zob stick` and `ugly stick` are ALIAS rows of `lagerphone`; SOUND_ALIKE if the
    construction differs
  - [ ] `cata` is parented to `woodblock`, while its source page compares claves
  - [ ] `pandero jarocho` and `rebana` point at `tambourine`; `daf` or `pandeiro` is nearer by the
    sheet's own reasoning
  - [ ] `garamut`'s 1.4 s ring is a weak inference (a sound that carries far is a long hollow
    resonance), and its 330 Hz wood partial's 0.3 s ring is unexplained
  - [ ] `washboard` against `castanets`: thin separation; listen, and merge or tune if they sound
    alike
  - [ ] `jing` is in `LONG_RINGING_ONE_SHOTS` (its ring outlasts the note): the test exempts it
    from the energy-share assertion only; the envelope check (`strikes_again`) and the held
    one-shot test still apply to it
  - [ ] Eight notes and builders disagree where a sourced trait is not built: `jing`, `tiger
    gong`, `sizzle cymbal` (cuts out sharply), `tingsha`, `ghatam`, `washboard`, `lagerphone`,
    `kkwaenggwari`; `bendir`, `dholak` (soft attack) and `bombo leguero` (hollow-log body) too
  - [ ] `LONG_RINGING_ONE_SHOTS` and `NOT_PERIODIC_AT_THE_NOTE` have no guard against going stale
  - [ ] `lions roar` waits for an amplitude LFO by the sheet's reading, not a sourced gap
  - [ ] `drums.py` is about 1,800 lines even with the sound-alikes moved out; split it by class if
    it grows
  - [ ] A sound-alike a source later sets apart (a smaller head's higher tone, a stick's click)
    takes `sound_changes`, citing the source
  - [ ] `sound_changes` cannot change a value a parent's builder fills positionally (e.g. `hertz`
    in `partial(_hand_drum, 215.0, ...)`, `_tom`, `_metal`; 19 parents of 48 sound-alikes, including
    `conga` and `tumba`), so its first real use needs that parent rewritten with keywords
- **Found**: batch 3's reviews (2026-11-08)
- **Status**: TODO
- **Priority**: Medium (before the plucked strings batch builds on the same catalog)

### 74. Sound Engine: The Owner's Checks on Instrument Catalog Batch 4 — TODO
- **Goal**: confirm or overturn the calls made while batch 4 of #70 ran, and listen to its new
  instruments (plucked strings, 58 to 92 entries; the owner, 2026-11-08: "I want them to all
  show up"). Most of the audit's candidates wait, because the owner ruled the range rule stays
  strict (2026-11-09, asked directly: "Keep it strict"): an instrument with no sourced range
  waits. See "Calls to confirm" for what a later pass could do about that
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and pick click is sound design, not sourced; the folder is
  `build/instruments/plucked strings/`). The 7 new builds come first, then the sound-alikes;
  each group below is a parent with the sound-alikes that share its build, which must sound
  alike by design. The ranges differ within a group, since each sound-alike gives its own:
  - [ ] The 7 new builds: `angelique`, `banjolele`, `chapman stick`, `qanun`, `ruan`, `tar`,
    `tiple colombiano`: each distinct from the 58 already there and from each other (the
    anti-goal; the rule-7 test only catches equal builds)
  - [ ] Near pairs to hear side by side: `angelique` and `lute`, `banjolele` and `soprano ukulele`,
    `ruan` and `pipa`
  - [ ] The sound-alikes, 27 in 19 groups (each is its parent's sound):
  - [ ] `bass ukulele`, `contrabass ukulele` of `acoustic bass guitar`
  - [ ] `siter`, `yakumogoto` of `appalachian dulcimer`
  - [ ] `secunda balalaika` of `balalaika`
  - [ ] `sanxian` of `banjo`
  - [ ] `electric bass vi` of `baritone guitar`
  - [ ] `harpejji` of `chapman stick`
  - [ ] `requinto guitar`, `terz guitar` of `classical guitar`
  - [ ] `piccolo domra` of `domra`
  - [ ] `seven string guitar` of `electric guitar`
  - [ ] `trichordo bouzouki` of `greek bouzouki`
  - [ ] `five string kantele`, `gusli`, `concert kankles` of `kantele`
  - [ ] `nigenkin` of `koto`
  - [ ] `bulgarian tambura` of `mandolin`
  - [ ] `liuqin`, `setar` of `pipa`
  - [ ] `gaoyin ruan`, `daruan`, `xiaoruan` of `ruan`
  - [ ] `sopranino ukulele` of `soprano ukulele`
  - [ ] `plectrum banjo` of `tenor banjo`
  - [ ] `viola da terra` of `tiple colombiano`
  - [ ] `alpine zither` of `zither`
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-4.tsv`; the sheet's 284 rows:
  SHIP 7, SOUND_ALIKE 27, WAIT 215, ALIAS 19, DROP 16; the 245 candidates the audits left come
  from the command in Task 3 Step 1 of
  `plans/2026-11-09-instrument-catalog-batch-4-implementation.md`, which regenerates the
  ignored `build/batch-4-candidates.txt`):
  - [ ] The range rule, which is why 215 rows wait. The owner ruled it strict (2026-11-09), so
    the 166 WAIT rows that wait for "a sourced range" stay out until a source gives one; the
    spec accepts fetched text or a maker's or museum's documented span, and a letter tuning
    counts when the source anchors its octave. A later pass can range them from maker pages,
    museum records (MIMO, the Met, Horniman) and organology pages: each such row's notes record
    what was searched. A second research pass over the first 69 such rows was not run, since
    the wider search of the second part turned only 7 of about 65 into rows and several museum
    sites refuse fetches; say if you want it run
  - [ ] WAIT for an engine feature (21 rows): a pitch that moves through a phrase (8: `dan bau`,
    `diddley bow`, `gopichand`, `guqin`, `ichigenkin`, `khamak`, `vong co guitar`, `washtub
    bass`), sympathetic strings (6: `gottuvadhyam`, `mohan veena`, `rabab`, `surbahar`, `ten
    string guitar`, `vichitra veena`), a buzzing bridge or wire or a jawari bridge (5:
    `begena`, `jakhe`, `yueqin`, `electric sitar`, `rudra veena`) and moving formants (2: `ukeke`, `umrhubhe`)
  - [ ] WAIT because their target waits (28 rows): `cavaco` (target `cavaquinho`), `cetera`
    (`citole`), `koboz` (`cobza`), `dotar` (`dutar`), `epinette` (`epinette des vosges`),
    `chitravina` (`gottuvadhyam`), `banjitar` and `banjo guitar` (`guitar banjo`), `kecapi`
    (`kacapi`), `tanbura` (`kissar`), `kopuz` and `qopuz` (`komuz`), `kudlong` (`kudyapi`),
    `laud espanol` (`laud`), `politiko laouto` (`lavta`), `guitarra portuguesa` (`portuguese
    guitar`), `gambus` (`qanbus`), `hommel` and `hummel` (`scheitholt`), `seul` (`se`), `tea
    chest bass`, `babatoni`, `box bass`, `dumdum`, `gutbucket` and `sanduku` (`washtub bass`),
    `hoddu` (`xalam`) and `wolgeum` (`yueqin`)
  - [ ] The pitched sound-alike rule (the plan's call, which you approved with the plan,
    2026-11-09): a sound-alike shares its parent's build but gives its own sourced range, and
    is pitched exactly when its parent is. Decision 8 said a sound-alike has its parent's range;
    that held for drums, which have none. `mandolin` and `mandola` already shared a build with
    their own ranges
  - [ ] The 54 pairs among the 58 existing plucked entries that share a build (`mandolin` and
    `mandola` both use `BRIGHT_LUTE`) were left as they are; the new-entry test never checks them (it
    loops only over `NEW_PLUCKED_NAMES`; `EXISTING_PLUCKED_NAMES` is used only in the
    set-equality test). Confirm, or convert some into sound-alikes
  - [ ] `sitar`, `tanpura` and `veena` are old entries that approximate sympathetic strings and
    a buzzing bridge, which decision 4 now holds back. They stay; new instruments whose
    identifying sound is one of those (`rudra veena`, `surbahar`, `mohan veena`, `ten string
    guitar`) wait and are not sound-alikes of `sitar`. Keep the three, or remove them
  - [ ] The audit's placement notes are not acted on: `lyre`, `kora` and `harp guitar` are in
    harps, `berimbau` is in struck strings. The plucked lyres (`krar`, `kissar`, `kithara`,
    `kinnor`, `barbiton`) stay in plucked strings while `lyre` is in harps, so the family split
    needs a decision before any of them ships
  - [ ] Every derived range: where a source gave a lowest note and a fret count, the highest is
    that note plus the frets (`bulgarian tambura` E4 plus 24 frets is E6); 15 comments in
    `plucked_strings.py` and `plucked_sound_alikes.py` say "derived", each with the source
    quoted
  - [ ] The two-half split: necked lutes (Hornbostel-Sachs 321.3) and then everything else
    (zithers, musical bows, lyres, out-of-family rows) were built in two halves. The halves were
    not exact: leftover necked lutes (`donso ngoni`, `kamele ngoni`, `tanbura`) got their sheet
    rows in the second half. Confirm the split reads right to a person adding the next entry
  - [ ] `angelique` is a SHIP with its own single-strung build (the lute's traits without
    courses, since courses are a sourced trait that sets it apart; its range C2-E4 is the stated
    open-string compass). Keep it, or fold it into a sound-alike once `theorbo`'s build is
    settled
  - [ ] `banjolele` ships without the sheet's unsourced pick click (no fetched source gives a
    plectrum): a slightly softer attack than the sheet's sound design
  - [ ] The sheet's form check reads "a SHIP or SOUND_ALIKE name that is already in the catalog"
    as "other than a batch 4 row already coded", so after the necked lutes it flags exactly
    their 25 coded rows; none collides with an entry of another family
  - [ ] `theorbo` and `archlute` are built with paired courses, but fetched pages call the
    theorbo single-strung (a possible bug in an existing entry)
  - [ ] None of the 58 existing plucked entries cites a source for its range or build
  - [ ] The catalog `zither` tops at C6, but the sourced fingerboard top is D7 (an existing entry
    whose data is off; `alpine zither` carries its own F1-D7)
  - [ ] The cited infobox gives the Greek bouzouki's top as E6, while the catalog `greek
    bouzouki` stops at D6 (C3-D6), so the new `trichordo bouzouki` sound-alike (D3-E6) tops out
    above its parent (the `tetrachordo bouzouki` row's data note)
  - [ ] `bozuk` is an alias of `saz` in `aliases.py`, so it reports the saz's range, but the
    Bağlama page says "Larger saz instruments were known by other names such as: bozuk,
    tambura" and the sheet row admits it "can mean a larger saz": bozuk may be a larger saz (a
    sound-alike with its own range, or a WAIT) rather than another name
  - [ ] `yakumogoto` and `nigenkin` are sound-alikes of other instruments while `ichigenkin`
    waits for a slide, though all three are the same fretless tenkan tube; read as a slide for
    all, both would wait too
  - [ ] `qanun`'s maqam quarter-tones are not in decision 4's list of what the engine cannot do
    yet; it ships with the western semitones
  - [ ] The washtub bass page lists "dan bau" (Vietnam) as a name for the washtub bass, which
    collides with the zither dan bau (`dan bau` waits)
  - [ ] Process calls made on your behalf: the registry's two small code tasks (the pitched
    sound-alike rule and the family's move into `plucked_strings.py`) went to one implementer
    and one review, as separate commits; the batch 4 owner's checks are #74 and refer to batch
    3's as #73 (the PR that renumbered it, #172, merged on 2026-11-10)
- **Follow-ups**:
  - [ ] The audit's "Gaps you could not close" (`plans/data/instrument-audit/plucked-strings.md`)
    are a later pass over this family, along with ranging the 166 range WAIT rows from maker and
    museum sources
  - [ ] The 16 DROP rows (`aeolian harp`, `claviharp`, `divan saz`, `dolceola`, `donso ngoni`,
    `fotdella`, `kacapi suling`, `kamele ngoni`, `laudon`, `marimbula`, `meydan saz`, `nondo`,
    `quijongo`, `shudraga`, `talk box`, `zeze`): each row's notes give the fetched reason
  - [ ] A sound-alike a source later sets apart takes `sound_changes`, citing the source
- **Found**: batch 4's reviews (2026-11-09)
- **Status**: TODO
- **Priority**: Medium (before the electronic batch builds on the same catalog)

### 75. Sound Engine: The Owner's Checks on Instrument Catalog Batch 5 — TODO
- **Goal**: confirm or overturn the calls made while batch 5 of #70 ran, and listen to its new
  instruments (tuned percussion, 23 to 36 entries). Most of the audit's candidates wait, because
  the range rule stays strict: an instrument with no sourced range waits
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and mallet click is sound design unless a source is cited in the
  code; the folder is `build/instruments/tuned percussion/`). The 2 new builds come first, then
  the sound-alikes; each group below is a parent with the sound-alikes that share its build,
  which must sound alike by design. The ranges differ within a group, since each gives its own:
  - [ ] The 2 new builds: `boomwhackers`, `gangsa`: each distinct from the 23 already there and
    from each other (the anti-goal; the rule-7 test only catches equal builds)
  - [ ] `boomwhackers` is the thinnest new build. Its sourced traits are a hollow plastic tube
    struck by hand, with no resonator; every number is sound design, and it sits near `tabla
    dayan`
  - [ ] `gangsa` builds the *ombak* beating pair as a fixed ratio (about 1.036) taken at 220
    Hz. The source gives a beat rate of 8 Hz at 220 Hz, so a fixed ratio beats faster higher
    up, about 38 Hz at C6. Its weakest partial (5.15) was left out because an instrument has at
    most four sources (three partials plus the mallet). Its range (C4-C6) comes from "around
    C7", and the source says "There is no standard pitch in any Balinese music"
  - [ ] Near pairs to hear side by side: `boomwhackers` and `tabla dayan`; `gangsa` against
    `saron` and `gender`. `gangsa` is the GAMELAN_METALLOPHONE family's sound with a 1.036
    *ombak* partial added and the 5.15 partial dropped, so it is the new build most at risk of
    the anti-goal
  - [ ] The sound-alikes, 11 in 3 groups (each is its parent's sound):
  - [ ] `alto glockenspiel`, `alto metallophone`, `bass metallophone`, `soprano glockenspiel`,
    `soprano metallophone`, `tubaphone` of `glockenspiel`
  - [ ] `alto xylophone`, `bass xylophone`, `soprano xylophone` of `xylophone`
  - [ ] `kantilan`, `ugal` of `gangsa`
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-5.tsv`; the sheet's 164 rows:
  SHIP 2, SOUND_ALIKE 11, WAIT 93, ALIAS 14, DROP 44):
  - [ ] Every WAIT (93 rows). 82 wait for "a sourced range" (a later pass can range them from
    maker pages and museum records; each row's notes record what was searched). 4 wait for an
    engine feature: `angklung` and `zimbelstern` and `wind chimes` (repeated strikes, an
    amplitude LFO) and `gyil` (spider-silk mirlitons). 7 wait because their target waits:
    `banghyang`, `hank drum`, `hapi drum`, `pyeongyeong`, `tank drum`, `pyeonjong`, `roto toms`
  - [ ] The four steel pans whose only range source is PAN Magazine (`double guitar`, `double
    tenor`, `quadrophonic`, `tenor bass` steel pan) wait, because a magazine is not a maker or
    museum. The other waiting pans cite it but take no range from it. Their ranges are in the
    sheet's notes, and accepting the source is a one-cell change per row. `soprano steel pan`
    and `lead pan` are aliases resting only on PAN Magazine, as a name source: the same
    publication the strict-range ruling rejects as a range source, so judge the magazine once
    for both uses. `tenor bass`'s parent is a judgment call between `bass steel pan` and `cello steel
    pan`
  - [ ] `lithophone` and `sekkin` wait: the only range found was one stone marimba's photo
    caption
  - [ ] `paigu` waits as a pitched tuned drum; `bonang barung` and `gender barung` wait the same
    way, as sizes of existing entries with no sourced range
  - [ ] Tuned percussion is pitched: an unpitched row goes to drums and percussion.
    `babandil` is dropped from this family and left for drums and percussion, as an unpitched
    timekeeper (no pitch is sourced), the way batch 3 shipped `agung` there
  - [ ] A set's range for a one-pitch body: a `kenong` or `kempul` is a row of single-pitch
    gongs and takes the set's range from a source; without one it waits (both wait)
  - [ ] The one-offs dropped (a one-off instrument, not a type a game would ask for):
    `bamboo marimba boo`, `diamond marimba`, `eucal blossom`, `great stalacpipe organ`, `marble
    machine`, `marimba eroica`, `quadrangularis reversum`, `zymo xyl` (and `gameleste`, which
    is also a keyboard)
  - [ ] The steel pan sizes as sound-alikes: the plan made the sizes the catalog lacks
    sound-alikes of the pan nearest in register, but none shipped, because no maker or museum
    source gave their ranges; all wait except `soprano steel pan`, `lead pan` and
    `ping pong`, which are aliases of `tenor steel pan`
  - [ ] The family's existing shared builds (`marimba` and `bass marimba`; `saron` and
    `gender`; the four steel pans) were left as they are, as batch 4 left its 54 pairs; confirm,
    or convert some into sound-alikes
  - [ ] The audit's range notes on existing entries, unchanged here: `bass marimba` G1-G3 or
    C2-F3 against the catalog's A1-C4, and `timpani` about D2-A3 against D2-C4. `balafon` is
    built without its buzzing mirlitons, which the `gyil` row says are the identifying sound
  - [ ] Aliases may cross families: `verrillon` is an alias of `glass harp`, `sanza` and
    `sansa` of `mbira`. `thumb piano` is dropped as a class name for lamellophones; `sanza` and
    `sansa` alias `mbira`, following batch 1's `zanza`
  - [ ] `rin` is a judgment alias of `singing bowl`; the Standing bell page never equates them
  - [ ] `chime machine` is dropped as a friction device. Its source describes "pine spindles
    worked upon by resined fingers", which corrects batch 2's "bells" reading
  - [ ] Every derived range: where a source gave a set's lowest and highest notes, or a lowest
    note and a count of steps, the range is derived and the sheet's notes show it
  - [ ] The two-half split: bars, plaques, tubes and stones (Hornbostel-Sachs 111.21, 111.22,
    111.23) and then everything else (gongs, bells, pans, drums, out-of-family rows) were built
    in two halves. Confirm the split reads right to a person adding the next entry
- **Follow-ups**:
  - [ ] The audit's "Gaps you could not close" (`plans/data/instrument-audit/tuned-percussion.md`)
    are a later pass over this family, along with ranging the 82 range WAIT rows from maker and
    museum sources
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
  - [ ] Candidate aliases, recorded for the owner and not added: `bell lyre` (the `bell lyra`
    comment in aliases.py quotes a source naming "bell lyre, bell lyra, or lyra-glockenspiel",
    and `instruments.get('bell lyre')` raises KeyError); `single tenor` (quoted in the `lead
    pan` and `ping pong` comments and the sheet); `tubular chimes` (named in the Tubular bells
    infobox but left out without a stated reason)
  - [ ] Name hazard: the Tubular bells infobox lists "orchestral bells", while `orchestra
    bells` is an alias of `glockenspiel`. A developer typing `orchestral bells` gets a KeyError
    whose suggestion is the glockenspiel, a different instrument
  - [ ] A sound-alike a source later sets apart takes `sound_changes`, citing the source
- **Found**: batch 5's reviews (2026-11-11)
- **Status**: TODO
- **Priority**: Medium (before the electronic batch builds on the same catalog)

### 76. Sound Engine: The Owner's Checks on Instrument Catalog Batch 6 — TODO
- **Goal**: confirm or overturn the calls made while batch 6 of #70 ran, and listen to its new
  instruments (electronic, 15 to 26 entries). Most candidates wait, drop or alias: 1 built, 10
  sound-alikes, 56 waits, 5 aliases and 89 drops in the sheet's 161 rows
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and click is sound design unless a source is cited in the code; the
  folder is `build/instruments/electronic/`). The 1 new build comes first, then the
  sound-alikes; each group below is a parent with the sound-alikes that share its build, which
  must sound alike by design. The ranges differ within a group, since a chip gives its own:
  - [ ] The new build, `nes triangle`: a 32-step 4-bit staircase, distinct from the smooth
    `chip triangle`. Its buzz is at harmonics 31 and 33 (about 1/31 of the fundamental each,
    measured), where Wikipedia's Ricoh 2A03 page claims an overtone four octaves higher (see the
    bugs below). Hear it beside `chip triangle` at A2 (the test pins the difference, but only
    the owner hears whether it reads as the NES)
  - [ ] The sound-alikes, 10 in 6 groups (each is its parent's sound):
  - [ ] `ay 3 8910`, `pc speaker`, `sn76489` of `chip square` (sound chips; each a plain square
    with nothing sourced to set it apart)
  - [ ] `sid sawtooth` of `saw lead` (the SID's plain sawtooth waveform, unfiltered; the SID's
    identifying filter, ring modulation and sync wait as `sid voice`)
  - [ ] `electronic conga`, `electronic tom`, `syndrum` of `electronic kick` (drums and
    percussion; see "electronic tom, electronic conga and syndrum" below)
  - [ ] `electronic clave` of `claves`; `electronic cowbell` of `cowbell`; `electronic maracas`
    of `maracas` (all unpitched)
  - [ ] The 5 aliases: `vox continental` (of `combo organ`, in organs), `thereminvox` and
    `etherwave` (of `theremin`), `chip sawtooth` (of `sid sawtooth`), `ym2149` (of `ay 3 8910`)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-6.tsv`; the sheet's 161
  rows: SHIP 1, SOUND_ALIKE 10, WAIT 56, ALIAS 5, DROP 89):
  - [ ] Every WAIT (56 rows), by reason: 13 for a sourced range (`atari punk console`, `casio vl
    tone`, `dynaphone`, `electronde`, `givelet coupleux organ`, `jennings univox`, `lyricon`,
    `moog taurus`, `musical tesla coil`, `omnichord`, `stylophone`, `theremin cello`, `triadex
    muse`); 7 for moving formants (`otamatone`, `sonovox`, `speak and spell`, `talk box`,
    `vocoder`, `voder`, `votrax`); 4 for sample playback (`d 50 la synth`, `electronic cymbal`,
    `linn lm1`, `nes dpcm`); 4 for filter resonance (`minimoog`, `moog modular synthesizer`,
    `trautonium`, `volks trautonium`); 4 for LFSR widths other than 15 and 7 (`atari tia`, `ay 3
    8910 noise`, `pokey`, `sid noise`); 3 for FM synthesis (`dx7 bass`, `dx7 ep`, `ym2612`); 2
    for a chorus's moving delay (`arp string ensemble`, `juno 106`); 2 for FM synthesis and
    wavefolding (`buchla 100`, `buchla music easel`); 2 for wavetable morphing (`ppg wave`,
    `prophet vs`); 2 for a filter envelope and filter resonance (`sh 101`, `tb 303`); 2 for a
    fixed noise clock (`nes noise`, `game boy short noise`); 2 for more than four sources
    (`electronic closed hi hat`, `electronic open hi hat`); 1 each for phase distortion (`casio
    cz`), a pitch LFO for vibrato (`clavioline`), a pitch LFO for portamento between notes
    (`clavivox`), an amplitude LFO for the sawtooth envelope (`electronic clap`), filter
    resonance with ring modulation and oscillator hard sync (`sid voice`), LFSR tap sets other
    than maximal-length (`nes short noise`, the 93-step mode), LFSR tap sets other than
    maximal-length and a 16-stage width (`sn76489 noise`); and 2 because their target waits
    (`suzuki q chord` waits for `omnichord`, `chip dpcm sample` for `nes dpcm`)
  - [ ] The range ruling: a keyboard's keys at the normal setting (8', octave switch at 0, no
    transpose); a chip's hertz at the clock of the machine the entry is named for, the lowest
    note rounded up to the first note at or above the lowest frequency, the highest rounded down,
    and clipped to A0-C8 (the catalog's span). Every derived range, each shown in the sheet's
    notes: `nes triangle` A0-C8 (the NTSC CPU clock 1.789773 MHz over 32 x 2048 is 27.31 Hz, so
    A0; the top 55.9 kHz clipped), `ay 3 8910` B0-C8 (30.6 Hz is B0, 30.87 Hz; 125 kHz
    clipped), `pc speaker` A0-C8 (the PC's 1193180 Hz clock, 18.2 Hz clipped to A0, 596.6 kHz
    clipped to C8), `sid sawtooth` A0-A#7 (0.0596 Hz clipped to A0, 3906.2 Hz is A#7 at 1 MHz),
    `sn76489` A2-C8 (108 Hz is A2 at the NTSC 3.58 MHz clock; 111.6 kHz clipped)
  - [ ] `sid sawtooth`'s top note: the 6581 datasheet's formula (Fout = Fn x Fclk / 16777216, as
    transcribed at bellesondes.fr) at its 1 MHz clock gives 3906.2 Hz, so A#7, not the B7 that
    Wikipedia's 4095.9375 Hz (which implies a 1.048576 MHz clock) gives. Confirm the datasheet's
    clock, or name a machine clock (NTSC C64 1.0227 MHz gives B7).
  - [ ] Confirm `electronic clave` (of `claves`), `electronic maracas` (of `maracas`) and
    `electronic cowbell` (of `cowbell`) as sound-alikes of acoustic parents; the cowbell's pairing
    rests on the unsourced `cowbell` build this entry reports as a bug.
  - [ ] The chip-clock ruling: a chip-named entry (`sn76489`, `ay 3 8910`, `sid sawtooth`)
    takes the clock its own datasheet or page gives, since it is named for the chip and not for a
    machine; three ranges depend on it (the page names Master System, ColecoVision and BBC Micro
    without their clocks)
  - [ ] `sh 101`'s recorded range is C4-G6 (32 keys from middle C at 8' with TRANSPOSE at
    NORMAL, Roland's owner manual), kept on a WAIT row: the entry waits for the filter feature
    its source's quote names, and the range is ready for when it lands
  - [ ] Patches dropped (a patch is not an instrument): `fm bell`, `hoover lead`, `laser zap`,
    `moog bass`, `moog lead`, `noise riser`, `pwm pad`, `reese bass`, `ring modulator`, `sample
    and hold`, `sync lead`, `wobble bass`; the 13 patch entries already in the family (`saw
    lead` to `chip triangle`) predate the rule and stay
  - [ ] Programmable synthesizers as sound-alikes of the patch their source names: only `sid
    sawtooth` (of `saw lead`) shipped. `minimoog` and `sh 101` wait for the filter feature their
    own quotes name, as `tb 303` does (the Task 3 review made the three consistent); `jupiter 8`,
    `prophet 5`, `arp 2600`, `arp odyssey`, `cs 80`, `ems vcs3`, `ms 20`, `oberheim sem`,
    `polymoog`, `synclavier`, `yamaha vl1`, `theremini`, `therevox` are dropped as programmable
    synthesizers whose fetched sources name no voice of their own
  - [ ] The stop and preset DROP reason: `keyboard theremin`, `novachord`, `solovox` and
    `ondioline` are dropped because their fetched sources name a palette of switch-, stop- or
    panel-set imitations of other instruments, not a voice of their own (the programmable-
    synthesizer ruling extended to stop and preset instruments)
  - [ ] Controllers, samplers and programmable channels dropped as having no sound of their
    own: `alphasphere`, `eigenharp`, `ewi`, `fairlight cmi`, `guitar synthesizer`, `haken
    continuum`, `keytar`, `laser harp`, `lightharp`, `radiodrum`, `reactable`, `samchillian`,
    `tenori on`; the programmable channels `amiga paula`, `huc6280`, `konami scc`, `namco wsg`,
    `game boy wave channel`; the biosignal sonifiers `electrocardiophone` and
    `electroencephalophone`
  - [ ] Drum-machine voices in electronic, while `electronic kick` and `electronic snare` stay
    in drums and percussion (unchanged); a drum machine as a product (`rhythm king`, `wurlitzer
    side man`, `drum machine voices`) is dropped as a set of voices, each its own row
  - [ ] `electronic tom`, `electronic conga` and `syndrum` are unpitched sound-alikes of
    `electronic kick`, so they play electronic kick's sound: decision 8's exception (names, not
    builds), though the TR-808's toms and congas and the Syndrum's falling sine are each their
    own circuit or voice in the sources. Confirm, or ask for builds of their own. The audit
    titled `electronic tom` Simmons, but the Simmons page describes no tom circuit, so the
    TR-808's is used
  - [ ] `Tag.CHIP`, its definition (an integrated circuit made to produce a computer's,
    console's or arcade machine's sound: Wikipedia's "Sound chip" page, fetched and quoted in
    the plan), and its addition to the four existing `chip ...` entries (`chip square`, `chip
    pulse 25`, `chip pulse 12`, `chip triangle`). It is on nine entries: those four, `nes
    triangle`, `ay 3 8910`, `pc speaker`, `sid sawtooth` and `sn76489`
  - [ ] `pc speaker` carries `Tag.CHIP`, though the Intel 8253 that drives it is a programmable
    interval timer, not a sound chip by the definition above; the PC speaker is a beeper, not
    a chip. Keep the tag, drop it, or define `Tag.CHIP` more widely (the review noted it)
  - [ ] The existing entries decision 4 would hold back, left alone: `theremin` (no vibrato or
    portamento, C3-C7), the 13 patch entries (no resonance) and their unsourced ranges. The
    existing unsourced ranges: `theremin` C3-C7, the patches, `chip square`, `chip pulse 25` and
    `chip pulse 12` A1-C8, `chip triangle` A0-C7. `ondes martenot`'s C1-C8 is below
  - [ ] The engine features this batch named beyond the spec's table, for the spec's "What the
    engine cannot make yet": oscillator hard sync, ring modulation, filter resonance, a filter
    envelope (a cutoff that moves during a note), wavefolding, phase distortion, wavetable
    morphing, portamento (a glide between successive notes), a chorus's moving delay, a pitch
    LFO (vibrato), an amplitude LFO, LFSR widths other than 15 and 7, a fixed noise clock (the
    engine scales an all-noise instrument's LFSR clock by pitch / 440, so a noise channel at one
    clock cannot be set), and LFSR tap sets other than maximal-length (the NES's 93-step mode,
    the SN76489's feedback from bits 12 and 13). The last two are the names this plan added
    while it ran
  - [ ] The earlier sheets' rows left as decided: batch 2's tape and optical WAITs (`mellotron`,
    `chamberlin`, `optigan`, `vako orchestron`, `welte lichttonorgel`, `telharmonium`) stay
    electromechanical, and `oramics` and `wurlitzer sideman` stay dropped; they are DROP rows
    here naming the sheet and the status. The nine hand-offs decided here: `solovox` (dropped, a
    stop-set palette), `vox continental` (alias of `combo organ`), `dx7 ep` (FM synthesis),
    `chip dpcm sample` (waits for `nes dpcm`), `chip noise` (`nes noise`, a fixed noise clock),
    `drum machine voices` (dropped, a set of voices), `rhythmicon` (dropped as
    electromechanical, H-S 52: its page says electro-mechanical, which outranked the plan's WAIT
    hint), `wurlitzer side man` (dropped, a set of voices), `talk box` (moving formants)
  - [ ] The one-offs dropped (a one-off instrument, not a type a game would ask for): `ans
    synthesizer`, `variophone`, `subharchord`, `hellertion`, `terpsitone`, `sphaerophon`,
    `croix sonore`, `electronic sackbut`, `electro theremin` (and its alias `tannerin`),
    `mixturtrautonium`
  - [ ] The two-half split by kind: the players' instruments (early electronic instruments,
    synthesizers, patches; 79 candidates) and then the machines (sound chips, drum machines,
    tape and sample replay, speech, controllers; 73). Electrophones have no Hornbostel-Sachs
    subclasses the plan could rely on, so the split is an explicit list. Confirm the split reads
    right to a person adding the next entry
  - [ ] Ruling: dae6433c (noise clocks the engine renders) was reverted (00c0647d); the sourced
    clocks stay recorded in the sheet, and the 22050 Hz limit is in the WAIT notes
  - [ ] Ruling: the form check's "taken" rule now accepts a row the code already holds with the
    same target or parent (the check assumed sheet before code; half A was coded first)
  - [ ] Process: pushing and opening the stacked PR without asking, per the owner's "Work on
    every batch in turn and stack them into PRs"; Tasks 1 and 2 done together; the Task 3 and 5
    sheets researched in parallel
- **Bugs to report** (found while building batch 6; none fixed here):
  - [ ] `drums.py`'s acoustic `cowbell` is built as the TR-808 circuit (two squares at 540 and
    800 Hz) with no source: an acoustic cowbell has no reason to sound like that circuit, and
    `electronic cowbell`, the entry the 808 circuit is sourced for, shares this build as a
    sound-alike of it
  - [ ] The engine accepts an LFSR clock up to 44100 Hz, but the pitch check refuses one above
    22050 Hz (the Nyquist frequency): `Noise('lfsr', rate=...)` is resolved as a pitch, so the
    NES noise channel's 27965.2 Hz (period $4) cannot be set. The two limits disagree; a fixed
    noise clock (above) would settle it
  - [ ] `combo organ` (organs) cites no source for its name, build or range (C2-C7); it
    predates the rule, and `vox continental` is now an alias of it
  - [ ] `ondes martenot`'s C1-C8 is the audit's "with the transpose switch" span, which this
    plan's own range ruling (octave switches and transposers do not widen the span) would not
    accept: its range at the normal setting is unsourced
  - [ ] Wikipedia's Ricoh 2A03 page says the triangle's stepping creates "an overtone ... four
    octaves higher at 1/8 the volume"; the NESdev 32-step sequence is half-wave antisymmetric,
    so it has no even harmonics and its 16th measures 0. The buzz is at harmonics 31 and 33
    (this batch's own measurement, not a source), so the code comment and the sheet say so
  - [ ] The subagent commits whose trailer names "Claude Sonnet 5.5" instead of the owner's
    "Claude Opus 5.5": the ledger says three, the branch holds one (`5a237a64`, Task 4's
    implementer); the brief's other two were not found between `origin/main` and the head
- **Follow-ups**:
  - [ ] The audit's "Gaps you could not close" (`plans/data/instrument-audit/electronic.md`) are
    a later pass over this family, along with ranging the 13 range WAIT rows from manuals and
    datasheets
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
  - [ ] The engine changes that unblock the waits above (a fixed noise clock first: two entries,
    `nes noise` and `game boy short noise`, wait only on it)
- **Found**: batch 6's reviews (2026-11-12)
- **Status**: TODO
- **Priority**: Medium (before the bowed strings batch builds on the same catalog)

### 77. Sound Engine: The Owner's Checks on Instrument Catalog Batch 7 — TODO
- **Goal**: confirm or overturn the calls made while batch 7 of #70 ran, and listen to its new
  instruments (bowed strings, 27 to 29 entries). Almost every candidate waits, drops or aliases:
  0 built, 2 sound-alikes, 118 waits, 5 aliases and 13 drops in the sheet's 138 rows
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and click is sound design unless a source is cited in the code; the
  folder is `build/instruments/bowed strings/`). No new build was added, so the listening is the
  sound-alikes under their parents, which must sound alike by design. The ranges differ within a
  group, since each gives its own:
  - [ ] `viola pomposa` (C3-A6) beside its parent `viola`: its source calls it "less resonant than
    a viola", so the entry plays the viola's sound
  - [ ] `bowed psaltery` (F3-F5) beside its parent `violin`: a psaltery's steel strings are
    bowed one at a time with no frets, so the violin's bowed tone stands in for it
  - [ ] The 5 aliases: `lira korbowa` (of `hurdy gurdy`), `soprano viol` (of `treble viol`),
    `behala` (of `violin`), `matouqin` (of `morin khuur`), `kemence` (of `kemenche`)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-7.tsv`; the sheet's 138
  rows: SHIP 0, SOUND_ALIKE 2, WAIT 118, ALIAS 5, DROP 13):
  - [ ] Every WAIT (118 rows), by reason: 90 for a sourced range (`alto viol`, `alto violin`,
    `arpeggione`, `baritone violin`, `byzantine lyra`, `calabrian lira`, `cello da spalla`,
    `contrabass violin`, `division viol`, `electric cello`, `electric violin`, `esseharpa`, `five
    string violin`, `geigenwerk`, `gue`, `gusle`, `kit violin`, `lijerica`, `lira da braccio`,
    `lirone`, `cretan lyra`, `lyra viol`, `mezzo violin`, `neola`, `oktavharpa`, `pardessus de
    viole`, `politiki lyra`, `rabeca`, `rebec`, `silverbasharpa`, `small bass`, `soprano violin`,
    `stroh violin`, `symphonia`, `talharpa`, `tenor violin`, `treble violin`, `ukelin`, `vielle`,
    `violetta`, `violino piccolo`, `violotta`, `yaybahar`, `ajaeng`, `banam`, `banhu`, `black
    sea kemence`, `byzaanchy`, `chikara`, `dan nhi`, `dihu`, `diyingehu`, `endingidi`, `erxian`,
    `gaohu`, `gehu`, `ghijak`, `goje`, `haegeum`, `igil`, `imzad`, `javanese rebab`, `kamancheh`,
    `kezaixian`, `khuuchir`, `kobyz`, `kokyu`, `kongahyan`, `kyl kyyak`, `laruan`, `masenqo`,
    `pena`, `ravanahatha`, `rebab`, `sato`, `saw duang`, `saw sam sai`, `saw u`, `sihu`, `sukong`,
    `tar shehnai`, `tehyan`, `tro ou`, `yazheng`, `yehu`, `zeze`, `zhonghu`, `zhuihu`, `sanjo
    ajaeng`, `jeongak ajaeng`); 7 for a sourced drone tuning (`crwth`, `gudok`, `jouhikko`,
    `langspil`, `moraharpa`, `organistrum`, `sarangi nepali`); 6 for sympathetic strings
    (`baryton`, `gadulka`, `dilruba`, `kamaicha`, `sarinda`, `taus`) and 1 for sympathetic
    strings and a buzzing bridge (`esraj`); 2 for sub-audio fundamentals (`long string
    instrument`, `octobass`); 2 for more than four sources (`phonoliszt violina`, `violano
    virtuoso`); 1 for a buzzing bridge (`tromba marina`); 1 for its own build (a bowed wheel
    without a buzzing bridge: `viola organista`); 1 for its own build (`jinghu`: a bamboo body and
    a tone raspier than the violin, unlike the erhu; its range D4-B6 is recorded from Koizumi no.
    310, reading `b'"` as b'''); and 7 because their target waits (`tagelharpa` and `strakharpa`
    for `talharpa`, `njarka` and `goge` for `goje`, `viola da spalla` for `cello da spalla`, `dan
    co` for `dan nhi`, `zhuiqin` for `zhuihu`)
  - [ ] The new `waits_for` values: `its own build (a bowed wheel without a buzzing bridge)`
    (`viola organista`: its bowed wheel needs a build that is neither the hurdy gurdy's buzzing
    bridge nor a bowed string's); `its own build` (`jinghu`, whose range D4-B6 is recorded from
    Koizumi no. 310, reading `b'"` as b'''; the sheet's cell gives the rule 7 trait); and `a
    sourced drone tuning` (an instrument whose source names drone strings but gives no pitches)
  - [ ] The range ruling (the lowest open string of the standard tuning; a stated highest note,
    compass or exact span; open strings and hedged spans are no range; nothing below A0), and
    every derived range: `viola pomposa` C3-A6 (open strings C3-G3-D4-A4 and "a range from C3
    to A6 (or even higher)"), `bowed psaltery` F3-F5 ("fully chromatic two octave range f -
    f''", read in Helmholtz notation)
  - [ ] `viola pomposa`'s "(or even higher)" is read as extending past A6, not as a hedge on
    A6; the range stays C3-A6. If it is a hedge, the entry waits for a sourced range
  - [ ] The approximating entries (`sarangi`, `hardanger fiddle`, `viola d amore`,
    `nyckelharpa`, `hurdy gurdy`) left unchanged and refused as parents of any sound-alike (so
    `dilruba`, `taus`, `kamaicha` and the other sympathetic-string instruments wait instead),
    and the reading of `hurdy gurdy`'s `drive` as its buzzing bridge
  - [ ] `lira korbowa` is an alias of the approximating `hurdy gurdy`: an alias adds a name, not
    a sound-alike, so the refusal as a parent does not apply. Confirm, or drop the alias
  - [ ] The drone ruling (`with_drones` at sourced pitches, else `a sourced drone tuning`): no
    drone instrument had sourced pitches, so seven wait
  - [ ] The moving-pitch ruling: an instrument whose source names a slide, portamento or
    vibrato as its identifying sound waits for a pitch LFO; the existing `violin`, `erhu` and
    the rest have no vibrato and stay
  - [ ] The mechanical and keyed instruments decided here: `violano virtuoso` and `phonoliszt
    violina` wait for more than four sources, `viola organista` for its own build and
    `geigenwerk` for a sourced range. The keyboards batch must not decide `viola organista`
    again. `Tag.MECHANICAL` is still on the `music box` alone
  - [ ] Sizes as sound-alikes of the nearest existing entry their source relates them to: only
    `viola pomposa` shipped; the violin octet, the viol consort and the huqin sizes wait for a
    sourced range
  - [ ] The one-offs dropped: `adapted viola`, `celloridoo`, `fences`, `kaisatsuko`, `keyolin`,
    `bazantar`. They rest on the sources naming one person's instrument (batch 5's Partch
    precedent), with no count of instruments in the sources. The `bazantar` page also files it
    under "String instruments with sympathetic strings": if it is ever un-dropped, it waits for
    sympathetic strings, not a range. The `adapted viola` has replicas, at least three instruments
    in all, still a handful
  - [ ] The other drops: `viola bastarda` (a style, and altered viols), `tro` and `armenian
    kamancha` (the audit's names for `tro ou` and `kamancheh`), `tihu` (a town, no instrument),
    `tiqin` (a name for several huqin), `rabab` (decided in batch 4: a plucked string)
  - [ ] The earlier sheets' rows left as decided (`electric upright bass`, batch 4's WAIT for a
    sourced range, a DROP row here) and the hand-offs decided here (`zeze`: batch 4's DROP
    "bowed strings", now a WAIT for a sourced range)
  - [ ] The three split pairs, kept as different instruments: `violotta` and `alto violin`
    (Stelzner's tuned an octave below the violin, the octet's alto tuned like the viola),
    `talharpa` and `jouhikko` ("a close relative", not the same), `organistrum` and `symphonia`
    (the symphonia a smaller box-shaped successor)
  - [ ] The `hs` column, assigned by the instrument's body type (`321.322-71` box lutes,
    `321.321-71` bowl lutes, `321.22-71` lyres, `321.322-72` wheel lutes, `314.122-71` and
    `314.122-72` board zithers, and the sheet's other cells: `31`, `311`, `312.22-71`, `321`,
    `321.31-71`, `321.311-71`, `321.312-71`, `321.313-71` and `321.321`) where no fetched page
    gives a Hornbostel-Sachs class, as with `viola pomposa`, `bowed psaltery` and
    `viola organista`. Confirm the classes, or ask for each to be sourced
  - [ ] chinesemusic.co.uk (Chinese Music Online) rejected as a range source for `banhu` and
    `jinghu` on its source type only (an ensemble's education page, not a maker, museum or
    encyclopedia); it also contradicts itself on the gaohu and jinghu spans
  - [ ] `gaohu` waits for a sourced range because its Wesleyan museum record contradicts itself
    (a three-octave compass against two-octave tunings), the flaw that rejected chinesemusic.co.uk
  - [ ] `sarinda` waits for sympathetic strings on the Met's record (503556), read through an
    archive.org snapshot because metmuseum.org answered 429. Confirm that source
  - [ ] The module move (`bowed_strings.py`, `strings.py` keeping harps and struck strings), the
    27 existing entries moved unchanged, and the two-half split by tradition (the European and
    modern bowed strings, 69 candidates, then the bowed strings of Asia and Africa, 57)
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    a bowed wheel without a buzzing bridge (`viola organista`), the one this batch added. The
    rest were already named: sympathetic strings, a buzzing bridge, sub-audio fundamentals, more
    than four sources, a pitch LFO
  - [ ] Process: pushing and opening the stacked PR without asking, per the owner's "Work on
    every batch in turn and stack them into PRs"; the two sheet halves researched in parallel,
    and Tasks 1, 2 and 4 run in parallel; the controller wrote `build/batch-7-names-before.txt`
    (755 names) up front so the sheets could start before the module move
- **Bugs to report** (found while building batch 7; none fixed here):
  - [ ] `erhu`, `morin khuur` and `kemenche` share one `SPIKE_FIDDLE` build, so three named
    instruments sound identical (they predate decision 8 and the sound-alike rule)
  - [ ] The catalog's `kemenche` (A3-A6) does not say which kemençe it is (the classical bowl
    kemençe and the Black Sea box kemençe differ), which blocks `politiki lyra` and the
    `black sea kemence` row
  - [ ] The existing viol tops (treble D6, tenor G5, bass D5, violone G4) are unsourced under
    this batch's range rule: no source comment gives a highest note
- **Follow-ups**:
  - [ ] The audit's "Gaps you could not close" (`plans/data/instrument-audit/bowed-strings.md`)
    are a later pass over this family, along with ranging the 90 range WAIT rows from maker and
    museum sources
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
  - [ ] The engine changes that unblock the waits above: sympathetic strings and a buzzing
    bridge first (seven rows wait only on them, with `sarangi`, `viola d amore` and the others
    waiting to be rebuilt), then a sourced drone tuning for the seven drone rows
- **Found**: batch 7's reviews (2026-11-12)
- **Status**: TODO
- **Priority**: Medium (before the voices and choirs batch builds on the same catalog)

### 78. Sound Engine: The Owner's Checks on Instrument Catalog Batch 8 — TODO
- **Goal**: confirm or overturn the calls made while batch 8 of #70 ran, and listen to its new
  instruments (voices 55 to 56 entries, choirs unchanged at 13). Almost every candidate waits,
  drops or aliases: 0 built, 1 sound-alike, 64 waits, 2 aliases and 71 drops in the sheet's 138
  rows. The plan's Task 5 (the choir vowels' build and its part-range test) was skipped by
  ruling, since no choir row shipped
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and click is sound design unless a source is cited in the code; the
  folders are `build/instruments/voices/` and `build/instruments/choirs/`). No new build was
  added, so there is nothing new to hear in `choirs/`, and the listening is the sound-alike and
  the aliases under their parents, which must sound alike by design:
  - [ ] `basso buffo ah` (E2-F4) beside its parent `bass ah`: the Fach page gives the type's own
    range and no trait that sounds different, so it plays the bass's sound
  - [ ] The 2 aliases: `contralto` (of `alto ah`) and `boy soprano` (of `treble ah`)
  - [ ] The choirs' `childrens choir` and the `choir ... ah` entries, unchanged, for the
    record of what the choirs family sounds like today
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-8.tsv`; the sheet's 138
  rows: SHIP 0, SOUND_ALIKE 1, WAIT 64, ALIAS 2, DROP 71):
  - [ ] Every WAIT (64 rows), by reason: 32 for a sourced range (20 voice types: `baritenor ah`,
    `bass baritone ah`, `basso cantante ah`, `boy alto ah`, `coloratura soprano ah`, `dramatic
    bass ah`, `dramatic contralto ah`, `dramatic mezzo soprano ah`, `dramatic soprano ah`, `haute
    contre ah`, `heldentenor ah`, `lyric soprano ah`, `oktavist ah`, `sopranist ah`, `soubrette
    ah`, `spinto soprano ah`, `spinto tenor ah`, `leggero tenor ah`, and the audit lines
    `soprano sfogato` and `tenore contraltino`; and 12 choir vowels: `choir soprano`, `alto`,
    `tenor` and `bass` on `eh`, `ee` and `hum`); 14 for moving formants (`borbangnadyr`,
    `chylandyk`, `dumchuktaar`, `electrolarynx`, `ezengileer`, `kargyraa`, `katajjaq`, `khoomei`,
    `rekuhkara`, `sygyt`, `tibetan chant`, `umngqokolo`, `yodel`, `tuvan ensemble`); 2 for a
    buzzing membrane (`kazoo`, `swazzle`); 1 for a pitch LFO (vibrato: `byrlang`); 1 for its own
    build (`castrato ah`); and 14 because their target waits (`khoomii`, `xoomei`, `overtone
    singing` and `harmonic singing` for `khoomei`; `khargyraa` for `kargyraa`; `inuit throat
    singing`, `iirngaaq`, `piqqusiraarniq`, `qiarvaaqtuq` and `nipaquhiit` for `katajjaq`;
    `jodel` for `yodel`; `octavist` and `oktavist` for `oktavist ah`; `artificial larynx` for
    `electrolarynx`)
  - [ ] The "what a candidate is" ruling: only four kinds are instruments (voice type, voice
    device, choir part, choir vowel); a technique, style, genre, repertoire or theatre role
    (`falsetto male`, `belt voice`, `scat singing`, `gregorian chant`, `gospel choir`, ...) is
    dropped as "a singing technique, style or genre, sung by any voice; not an instrument". The
    one exception is the spec's own table, whose "overtone and throat singing" and "yodel" WAIT
    for moving formants instead of dropping. 71 rows dropped (46 voices, 25 choirs)
  - [ ] Voice types are `ah` sound-alikes of the type their source names, with no
    `sound_changes` and no other vowels: the Csound manual's five rows are the catalog's only
    formant source, and no source turns "light", "lyric" or "dramatic" into a different static
    formant voice (a number chosen to differ is the anti-goal). Only `basso buffo ah` shipped
  - [ ] The range ruling: a range is stated (both notes with octaves), never hedged
    ("approximately", "about", "typically"), never a type's extremes, and a page that contradicts
    itself gives none; nothing below A0. Under it only `basso buffo ah` has a range (Fach page,
    unhedged "From the E half an octave below low C (E2) to the F above middle C (F4)")
  - [ ] The hedged spans the notes record, in case the owner relaxes the rule (each row's notes
    quote the page; where the Fach page also gives a span it is named). One row per line:
    - `lyric soprano ah` C4-D6 (Fach: B3-C6)
    - `coloratura soprano ah` C4-F6 (lyric) and A3-F6 (dramatic) (Fach: C4-F6)
    - `dramatic soprano ah` A3-C6 (Fach: A3-C6)
    - `soubrette ah` C4-D6 (Fach: C4-C6)
    - `spinto soprano ah` A3-C6 (Fach only)
    - `dramatic mezzo soprano ah` F3-G5 (Fach: G3-B5)
    - `dramatic contralto ah` F3-A5 (Fach only)
    - `sopranist ah` C4-C6
    - `tenore contraltino ah` C3-C5
    - `leggero tenor ah` G2 up to E5, "sometimes" F#5 or G5
    - `heldentenor ah` B2-C5 (Fach only)
    - `spinto tenor ah` C3-C5 (Fach only)
    - `bass baritone ah` F2-F#4 (low lyric) and E2-F4 (high dramatic) (Fach only)
    - `dramatic bass ah` C2-F4 (Fach only; both Fach rows)
    - `choir soprano eh`, `ee` and `hum` C4-A5 (the Soprano page's choral span)
    - `choir alto eh`, `ee` and `hum` F3-F5 (the Alto page's choral span)
    - `choir tenor eh`, `ee` and `hum` B2-G4 and B2-A4 (the Tenor page contradicts itself)
    - `choir bass eh`, `ee` and `hum` E2-E4 (the Bass page's solo span, hedged)
    Relaxing the rule ships the voice rows as `ah` sound-alikes of their parents
  - [ ] `haute contre ah` stays WAIT although the Haute-contre page's solo range C3-D5 is
    unhedged: the page gives it at a French eighteenth-century pitch "as much as a whole tone
    lower than that of today", so the sounding notes are not fixed. The ruling was the
    controller's; ship it at C3-D5 if the owner reads the caveat as no hedge
  - [ ] The choir-vowel ruling: a choir vowel (`eh`, `ee`, `hum`) ships only on a sourced choral
    range equal to its part's `CHOIR_PARTS` row. No source gives one for any part, so all 12
    wait. Open Music Theory's SATB page gives alto G3-D5, the same as the catalog's row, but as a
    part-writing textbook convention, not a choral range; confirm that reading (it costs the
    three alto vowels)
  - [ ] Ensembles of parts dropped for their parts (men's and women's choirs, quartets, `cantu a
    tenore`, `barbershop quartet`, `doo wop group`, `orthodox choir`, `boys choir`, `girls
    choir` and the rest), and choirs of one part as sound-alikes of `childrens choir` (none
    qualified: no source describes one voice type in unison)
  - [ ] The voice devices: `kazoo` and `swazzle`, handed off from round 1 and decided here under
    the spec's boundary call (the kazoo goes in voices), each wait for a buzzing membrane (batch
    5's `gyil` reason) and also lack a sourced range. `electrolarynx` waits for moving formants,
    as batch 6 ruled `talk box`, `sonovox` and `voder`
  - [ ] The moving-formant WAITs (14 rows): the spec's own table names them
  - [ ] `byrlang` waits for a pitch LFO (vibrato), not moving formants: both fetched pages call
    it a vibrato or a lip quiver added to another style
  - [ ] Aliases of a voice type resolve to its `ah` entry (`contralto` of `alto ah`, `boy
    soprano` of `treble ah`); an alias whose target waits waits, and one whose target is dropped
    is dropped
  - [ ] The earlier sheets' rows left as decided (`talk box`, `sonovox`, `vocoder`, `voder`:
    batch 6's WAITs), `vocoder voice` and `speech synth lpc` dropped, and `vox humana` and
    `voix celeste` left for the organs batch (organs.md rows them as stops)
  - [ ] The barbershop lead is mapped to `tenor ah` (the Barbershop quartet page: "the second
    tenor singing the lead"); the row is dropped as an ensemble in any case
  - [ ] The `hs` column is `none` where no fetched source gives a Hornbostel-Sachs class (every
    row but the kazoo's `242`)
  - [ ] One module with two sound-alike tables, no `choirs.py` (`voices.py` shares the formant
    table between the two families; `voice_sound_alikes.py` holds `VOICE_SOUND_ALIKES` and
    `CHOIR_SOUND_ALIKES`, the latter empty)
  - [ ] The split by family (voices, 100 rows; choirs, 38), with the two sheets researched in
    parallel
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make
    yet": none new. Every wait names a feature the spec or an earlier batch already named
    (moving formants, a pitch LFO, a buzzing membrane), or `its own build` (`castrato ah`:
    "boy-bright" with an adult chest, related to no single type)
  - [ ] Task 5 skipped: with no choir row shipping, `ADDED_CHOIR_SOUNDS` and its builder would be
    empty machinery, and the test that pins every choir entry of a part to one range waits for
    the first choir vowel that ships
- **Bugs to report** (found while building batch 8; none fixed here):
  - [ ] `HUM_FORMANTS` (`voices.py`) has no source and no sound-design note
  - [ ] `CHOIR_PARTS`' "usual choral ranges" are unsourced, and no fetched source states three of
    the four rows as choral ranges: the alto row (G3-D5) matches Open Music Theory's part-writing
    convention, but no choral source gives it (the Alto page says "approximately from F3 ... to
    F5"); the tenor row (C3-A4) meets a hedged Grove figure and the Tenor page contradicts itself;
    the bass row (E2-D4) matches no fetched source; the soprano row (C4-A5) matches the Soprano
    page's hedged choral span and two library definitions
  - [ ] `whistling` C5-C7 is unsourced
  - [ ] `countertenor` E3-E5 rests on the Voice type page, which hedges it and gives two tops
    (caption E3-E5, text C4-C6 and D3-D5)
  - [ ] `treble` A3-A5 disagrees with its page (A3-F5), and `treble` uses the adult soprano
    formant row
  - [ ] `basso profundo` C2-C4 has no source; the Fach page's hedged span is about C2-F4
- **Incidents and process**:
  - [ ] An incident: on the first test fetch, a research agent (Task 2's implementer) put the
    owner's email address in a User-Agent header to Wikipedia. Later fetches did not, and every
    dispatch since forbids personal data in any request header, URL or payload
  - [ ] Pushes and stacked PRs happen without asking (the owner, 2026-11-12), and the two sheets
    were researched in parallel, with Tasks 1, 2 and 4 running together
  - [ ] A parked minor from the reviews: `orthodox choir`'s `sound_source` is the Basso profondo
    page, which describes the oktavist, not a choir (the notes' wording was fixed; the drop
    holds either way)
- **Follow-ups**:
  - [ ] The audit's "Gaps you could not close" (`plans/data/instrument-audit/voices-and-choirs.md`)
    are a later pass over these families
  - [ ] Ranging the range WAITs (20 voice types, 12 choir vowels) from conservatory, opera-house
    or choral-society sources
  - [ ] Bare voice-type names (`soprano`, `tenor`) resolve to nothing today
  - [ ] The other vowels (`eh`, `ee`, `oh`, `oo`, humming) for the voice types that shipped as
    `ah` (today only `basso buffo ah`)
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
  - [ ] The engine changes that unblock the waits above: moving formants first (14 rows, and
    the throat-singing aliases behind them), then a pitch LFO, then a buzzing membrane
- **Found**: batch 8's reviews (2026-11-12)
- **Status**: TODO
- **Priority**: Medium (before the flutes batch builds on the same catalog)

### 79. Sound Engine: The Owner's Checks on Instrument Catalog Batch 9 — TODO
- **Goal**: confirm or overturn the calls made while batch 9 of #70 ran, and listen to its new
  instruments (flutes 30 to 33 entries). Almost every candidate waits or drops: 0 built, 3
  sound-alikes, 131 waits, 5 aliases and 7 drops in the sheet's 146 rows. The plan's Task 2 (the
  two recorder retitles) was skipped by ruling: see the recorder naming call below
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and click is sound design unless a source is cited in the code; the
  folder is `build/instruments/flutes/`). No new build was added, so there is nothing new to hear
  as a build, and the listening is the sound-alikes and the aliases under their parents, which
  must sound alike by design:
  - [ ] The new builds: none (0 SHIP rows)
  - [ ] The 3 sound-alikes beside their parents: `csakan` (Ab4-Eb7) beside `soprano recorder`,
    `subcontrabass recorder` (F1-G3) beside `contrabass recorder` (its low end is the lowest
    note of any flute: listen for a quiet or wrong note at F1) and `ryuteki` (E5-D7) beside
    `bansuri`
  - [ ] The 5 aliases: `penny whistle` (of `tin whistle`), `jula jula`, `julu julu` and `syrinx`
    (of `pan flute`) and `siyotanka` (of `native american flute`)
  - [ ] The two recorders whose titles Task 2 would have changed, as they sound and read today:
    `great bass recorder` and `contrabass recorder`
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-9.tsv`; the sheet's 146 rows:
  SHIP 0, SOUND_ALIKE 3, WAIT 131, ALIAS 5, DROP 7):
  - [ ] Every WAIT (131 rows), by reason:
    - 94 for a sourced range: `bird flageolet`, `blown bottle`, `boatswains call`, `classical
      flute`, `double contrabass flute`, `double flageolet`, `double ocarina`, `dvojnica`, `eb
      soprano flute`, `flageolet`, `floyera`, `fluier`, `flute d amour`, `flutophone`, `frula`,
      `fujara`, `garklein recorder`, `gemshorn`, `hydraulophone`, `kalyuka`, `koncovka`,
      `renaissance flute`, `sixth flute`, `sopilka`, `soprano ocarina`, `steam whistle`,
      `subcontrabass flute`, `subgreat bass recorder`, `tabor pipe`, `tenor ocarina`, `tilinca`,
      `tonette`, `voice flute`, `willow flute`, `atenteben`, `blul`, `borrindo`, `chi flute`,
      `chiflo`, `colombian gaita`, `danso`, `dilli kaval`, `embilta`, `firlinfeu`, `gasba`,
      `hitoyogiri`, `hocchiku`, `huilacapitztli`, `junggeum`, `kagurabue`, `kawala`, `khlui`,
      `koauau`, `koauau ponga ihu`, `komabue`, `limbe`, `nguru`, `nohkan`, `nose flute`,
      `paixiao`, `palendag`, `palwei`, `pifano`, `pinkillo`, `quenacho`, `quills`, `rondador`,
      `salamuri`, `saluang`, `sao truc`, `shabbaba`, `shinobue`, `shvi`, `siku`, `sodina`,
      `sogeum`, `solomon panpipes`, `suling`, `sybyzgy`, `tarka`, `tempuku`, `tieu`, `tungso`,
      `umtshingo`, `washint`, `wot`, `xun`, `fangufangu`, `kalaleng`, `bulalri`, `aangun`,
      `nai`, `kuvytsi`, `venu`
    - 18 because their target waits: `swanee whistle`, `lotus flute`, `piston flute` and `jazz
      flute` (for `slide whistle`); `ohe hano ihu`, `ohe hanu ihu` and `pitung ilong` (for
      `nose flute`); `antara` and `zampona` (for `siku`); `hun` and `tsuchibue` (for `xun`);
      `geling` and `geshao` (for `pigeon whistle`); `bosuns call` (for `boatswains call`);
      `police whistle` (for `pea whistle`); `salamiyya` (for `kawala`); `tongali` (for
      `kalaleng`); `xipro` (for `chiflo`)
    - 5 for a build of their own: `duck call`, `aztec death whistle`, `fulani flute`, `porutu`,
      `putorino`
    - 3 for a pitch LFO (vibrato): `bird whistle`, `pea whistle`, `water whistle`
    - 3 for a pitch LFO (portamento between notes): `singing bird box`, `slide whistle`,
      `whistling vessel`
    - 3 for a buzzing membrane: `bangdi`, `daegeum`, `qudi`
    - 2 for a sourced drone tuning: `algoza`, `lalingedan`
    - 1 each for sub-audio fundamentals (`hyperbass flute`, C0), more than four sources
      (`pigeon whistle`) and moving formants (`tsuur`)
  - [ ] The range ruling (the owner kept it strict, 2026-11-09): a range is stated or an exact
    span above the lowest note, in sounding pitch (a written range counts only when the same
    source states the transposition), never hedged ("about", "usually up to"), never an extreme
    ("advanced players", "possible altissimo"), never a width with no pitches (the ocarina
    page's "an octave plus a fourth") or letters with no octaves (the hydraulophone page's "A to
    E"); the key a source calls standard; maker and museum sources count, a retailer, blog or
    forum does not; nothing below A0 (`hyperbass flute`, C0) or above C8 (no row needed it); a
    one-note pipe has no range, and a set shared among players in hocket is dropped
    (`embilta` waits; `nyanga panpipes` and `tshikona pipes` dropped). The ranges derived under
    it: `csakan` Ab4-Eb7 (Wikipedia: written C4-G6, "a transposing instrument in A-flat", so a
    minor sixth up; the parenthesised extended range left out); `subcontrabass recorder` F1-G3
    (Paetzold by Kunath's manual, sounding range printed on a bass staff, read from the PDF at
    1200 dpi); `ryuteki` E5-D7 (Koizumi record 466, `e"-d""`, the same as the Japanese
    Wikipedia corpus; Stanford's wider span is extremes)
  - [ ] The range rule's casualty `garklein recorder`: its page's only range ("C6-A7 (C8)") is
    a sentence the page itself tags "[citation needed]". The controller ruled an uncited claim
    is not a sourced range, so it waits. Ship it at C6-A7 if the owner accepts the uncited
    sentence
  - [ ] `tempuku` waits although the Koizumi record (391 and 392) gives `g-f"`: the record's
    octave marks contradict the pipe length (29 cm), and the catalog's marks are unreliable for
    these entries. The controller's ruling; ship it at G3-F5 if the owner trusts the record
  - [ ] `bangsi` dropped ("no fetched source describes it"): its only source is a field
    recording project's blog (Aural Archipelago), and a blog is not a source under the range
    ruling. It also names a membrane, "almost like in a kazoo"
  - [ ] `tungso` waits for a sourced range, not a buzzing membrane: its page says it "may have"
    a membrane, "especially common in the folk variety" (optional, as for `khlui`, which also
    waits only for a range)
  - [ ] `tonette` waits: its page gives C4-D5, which reads as written pitch (Talk:Tonette says
    the real range is an octave higher, C5-D6) and no source states a transposition, so ruling 2
    leaves no range
  - [ ] The ocarina sizes (`soprano ocarina`, `tenor ocarina`, `double ocarina`): makers' size
    names disagree (STL Ocarina's tenor in C is A4-F6, which overlaps the catalog's "Ocarina
    (alto C)", C5-F6), no source calls a size or key standard, so each waits. Each model page
    gives a range for one key only
  - [ ] The slide whistle waits for a pitch LFO (portamento between notes): its whole identity
    is its glide, so `slide whistle` and its four alias names (`swanee whistle`, `lotus flute`,
    `piston flute`, `jazz flute`) are `PORTAMENTO_NAMES` in the catalog test, refused as a build
    or a sound-alike, and the alias rows wait for their target. Decided by the plan, not per
    row; the engine has one glide per note (`pitch_curve`) but none between notes
  - [ ] The recorder naming: one convention (great bass C3, contrabass F2, subgreat bass C2,
    subcontrabass F1, the Paetzold/Mollenhauer one), and a name from the other convention is
    never an alias because it would read as another size. The plan's Task 2 would have retitled
    `great bass recorder` "Great bass recorder in C" and `contrabass recorder` "Contrabass
    recorder in F" (the spec's finding: "Not a bug, but the titles could state the lowest note").
    It was skipped by ruling, since existing entries change only for a cited bug and the spec says
    this one is not one. Do you want the retitle? New recorder sizes state their key in the
    title (`Subcontrabass recorder in F`)
  - [ ] `dizi` among the approximations (`APPROXIMATING_NAMES`), never a parent: its page names a
    membrane that gives "the final tone a buzzing, nasal quality", and a sound-alike would ship
    the omission under a new name. A flute whose source names that buzz as its sound waits for a
    buzzing membrane (`bangdi`, `daegeum`, `qudi`); one that has none today is built like any
    other (`junggeum`, `sogeum`: they wait only for a range)
  - [ ] The moving-sound ruling: a slide between notes waits for a pitch LFO (portamento); a
    warble or trill that the device itself makes (`pea whistle`, `water whistle`, `bird
    whistle`) waits for a pitch LFO (vibrato), and `singing bird box` and `whistling vessel`
    for the portamento one; a trill or vibrato any player may add is technique, not the sound
  - [ ] Flutes with a voice or a drone: `tsuur` waits for moving formants (throat singing,
    the spec's row); `fulani flute`, `porutu` and `putorino` wait for a build of their own (a
    sung or lip-buzzed voice that is not throat singing); `algoza` and `lalingedan` wait for a
    sourced drone tuning (batch 7's ruling). A double flute whose pipes each play a melody is
    played as two notes of one sequence
  - [ ] Overtone flutes (`fujara`, `koncovka`, `kalyuka`, `willow flute`, `tilinca`) are flutes:
    the harmonic series decides the notes, not the sound. They wait only for a sourced range
  - [ ] No new shape: every flute shipped (3 sound-alikes) reuses the six existing ones, so no
    stopped-pipe trait was added (see the `pan flute` bug below)
  - [ ] Unpitched flutes (`FLUTE_UNPITCHED_NAMES`, empty): `aztec death whistle` waits for a
    build of its own, since a sound-alike is pitched exactly when its parent is and no flute is
    unpitched
  - [ ] The boundary hand-offs: `duck call` stays in flutes (the spec: "duck calls and signal
    whistles go in flutes (they are edge-blown)") but waits for a build of its own. Its page
    names reeds ("Early duck call tools were basic woodwind instruments ... single, double, or
    triple reed call") and also says "a duck call is like a traditional whistle", describing
    whistle-type teal calls. The noise makers audit read it as a reed call. Which family is
    right? `hydraulophone` is in flutes under the spec, with `hs` `none` (its page gives no
    class) and waits for a range (letters with no octaves). `steam whistle` waits for a range;
    its page relates it to no catalog entry, so no cross-family sound-alike of `calliope` was made
  - [ ] Sizes and keys as sound-alikes: the concert flute's and recorders' sizes and the folk
    flutes in other keys ship as a sound-alike of the entry nearest in register that their source
    relates them to, with their own range, or wait. Only `csakan`, `subcontrabass recorder` and
    `ryuteki` qualified
  - [ ] One-offs and unsourced rows dropped: `ringflute` and `clackamore` (one-offs),
    `bangsi` and `gezi shao` (no fetched source describes them), `lingbu` (a term for all
    Tibetan flutes), `nyanga panpipes` and `tshikona pipes` (ensembles of one-note pipes played
    in hocket)
  - [ ] The aliases: `jula jula` and `julu julu` point at `pan flute` (the Pan flute page names
    them as Bolivian panpipe names; the audit's `siku` was not related by any fetched source) and
    `syrinx` too; `penny whistle` at `tin whistle`; `siyotanka` at `native american flute`
  - [ ] The module move: the family moved unchanged from `winds.py` to `flutes.py` (its table is
    `_FLUTE_BUILDS + FLUTE_SOUND_ALIKES`, the sound-alikes in `flute_sound_alikes.py`), and
    `winds.py` keeps the five reed families (clarinets, saxophones, double reeds, bagpipes, free
    reeds); the process-state guard's six build names moved with it
  - [ ] The two-half split by an explicit list (half A, the European, orchestral and modern
    flutes with the whistles and calls, 47 candidates; half B, the traditional flutes of Asia,
    Africa, the Americas and Oceania with every panpipe, 72), the two sheets researched in
    parallel, and Tasks 1, 3 and 5 run together
  - [ ] Task 2 skipped by ruling (the recorder retitles, above), and the pushes and stacked PRs
    made without asking (the owner, 2026-11-12, #78)
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make
    yet": none new. Every wait names a feature the spec or an earlier batch already named (a
    pitch LFO, a buzzing membrane, moving formants, more than four sources, sub-audio
    fundamentals, a sourced drone tuning) or `its own build`
- **Bugs to report** (found while building batch 9; none fixed here):
  - [ ] `dizi` is built as `METAL_FLUTE` (the piccolo's build) with no buzz, although its page
    gives the membrane "the final tone a buzzing, nasal quality". It is in `APPROXIMATING_NAMES`
  - [ ] `pan flute` uses `END_BLOWN`, which keeps the even harmonics at full level, but the Pan
    flute page says "The pan flute's tubes are stopped at one end" and that overblowing gives
    "odd harmonics". The page states the stopped pipe and its odd overblown series, not the
    timbre in so many words, so no change was made here
  - [ ] `sopranino recorder` (F5-G7) has no source comment in `flutes.py`: the audit records the
    Recorder page as "soprano C5-D7 (G7)", so its G7 may be an extreme, as the soprano's
    parenthetical is
  - [ ] `ocarina` is titled "Ocarina (alto C)" with C5-F6 and has no source comment; STL
    Ocarina's maker page puts a C ocarina at A4-F6, and size names differ across makers
  - [ ] Wikipedia's Recorder table showed "Musical scores are temporarily disabled due to a
    security issue", so its written and sounding range images could not be read; several recorder
    sizes might get ranges once they render again
  - [ ] The Koizumi catalog (Geidai) holds object records with stated ranges for many flutes
    (`frula`, `dvojnica` and others in half A) that half A did not use
  - [ ] The 30 earlier flutes were not checked against their pages in this batch: the reviews
    found no other existing range that a fetched source contradicts, but none was looked for
    beyond the entries named above
- **Incidents and process**:
  - [ ] Pushes and stacked PRs happen without asking (the owner, 2026-11-12), and the two sheets
    were researched in parallel
  - [ ] Parked minors from the reviews: the code check's "already" exemption skips a row rather
    than requiring its resolution (`build/batch-9-code-check.py`, cosmetic)
  - [ ] Wikipedia's API rate-limited bursts, and Kunath's product pages and the Met returned
    404 or 429
- **Follow-ups**:
  - [ ] Check the 30 earlier flutes' ranges against their pages (none was checked in this batch)
  - [ ] The sheet's other waits (the buzzing membrane, vibrato, the drone tuning and the
    like) have no catalog guard yet: only `PORTAMENTO_NAMES` holds names back, and the one-off
    code check is the only other guard
  - [ ] The audit's gaps (`plans/data/instrument-audit/flutes.md`, listed in #70) are a later
    pass over this family
  - [ ] Ranging the 94 range WAITs from maker and museum sources (the Koizumi catalog, MIMO, the
    Met, the Horniman, Kunath and Moeck model pages), each row's notes recording what was searched
  - [ ] `serinette` and `flute clock`: the organs batch decides them
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
  - [ ] The engine changes that unblock the waits above, most rows first: the 94 range waits need
    no engine feature, then a pitch LFO (vibrato 3, portamento 3 and the slide whistle's 4
    aliases), a buzzing membrane (3, and `dizi`'s fix), a sourced drone tuning (2), then a build of
    their own (5), moving formants (1), sub-audio fundamentals (1) and more than four sources (1)
- **Found**: batch 9's reviews (2026-11-12)
- **Status**: TODO
- **Priority**: Medium (before the brass batch builds on the same catalog)

### 80. Sound Engine: The Owner's Checks on Instrument Catalog Batch 10 — TODO
- **Goal**: confirm or overturn the calls made while batch 10 of #70 ran, and listen to its new
  instruments (brass 42 to 44 entries). Almost every candidate waits or drops: 0 built, 2
  sound-alikes, 99 waits, 16 aliases and 10 drops in the sheet's 127 rows. The plan's Task 5 had
  no build or sound-alike to code (half B shipped only aliases), so only its alias steps ran
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`;
  every level, filter, ring and click is sound design unless a source is cited in the code; the
  folder is `build/instruments/brass/`). No new build was added, so there is nothing new to hear
  as a build, and the listening is the sound-alikes and the aliases beside their parents, which
  must sound alike by design:
  - [ ] The new builds: none (0 SHIP rows)
  - [ ] The 2 sound-alikes beside their parents: `bass wagner tuba` (Eb1-F5) beside `wagner
    tuba` (its low end is a pedal register: listen for a quiet or wrong note at Eb1) and
    `soprano trombone` (E3-C6) beside `trumpet`
  - [ ] The 16 aliases: `b flat piccolo trumpet` (of `piccolo trumpet`), `tenor tuba` (of
    `euphonium`), `treble cornett` and `zink` (of `cornett`), `cornet a pistons` (of `cornet`),
    `tenor horn` (of `alto horn`), `dung dkar`, `hakgediya`, `pututu`, `shankha` and `fotuto` (of
    `conch`), `waldhorn` (of `french horn`), `inventionshorn` (of `natural horn`), `yidaki` and
    `mako` (of `didgeridoo`) and `alpenhorn` (of `alphorn`)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-10.tsv`; the sheet's 127 rows:
  SHIP 0, SOUND_ALIKE 2, WAIT 99, ALIAS 16, DROP 10):
  - [ ] Every WAIT (99 rows), by reason:
    - 80 for a sourced range: `alto ophicleide`, `alto sackbut`, `baritone bugle`, `bass
      cornett`, `bass flugelhorn`, `bass horn`, `bass sackbut`, `buccin`, `cc tuba`, `contrabass
      bugle`, `contrabass ophicleide`, `contrabass saxhorn`, `cornettino`, `double bell
      euphonium`, `e flat trumpet`, `firebird trumpet`, `flumpet`, `helicon`, `herald trumpet`,
      `jazzophone`, `keyed bugle`, `keyed trumpet`, `kuhlohorn`, `mellophonium`, `mute cornett`,
      `rotary valve trumpet`, `russian bassoon`, `saxotromba`, `saxtuba`, `slide trumpet`,
      `sopranino saxhorn`, `soprano helicon`, `soprano saxhorn`, `superbone`, `valve trombone`,
      `abeng`, `amakondere`, `birch trumpet`, `buccina`, `bucium`, `buisine`, `bukkehorn`,
      `carnyx`, `cavalry trumpet`, `chazozra`, `cornu`, `dord`, `dungchen`, `erke`, `haotong`,
      `holztrompete`, `horagai`, `kakaki`, `kangling`, `karnay`, `kombu`, `lituus`, `lur`,
      `midwinter horn`, `nabal`, `nafir`, `natural trumpet`, `oliphant`, `putatara`, `ram singa`,
      `salpinx`, `siwa`, `sneng`, `sringa`, `steerhorn`, `swedish cowhorn`, `tharai`, `tiba`,
      `tochacatl`, `trembita`, `truba`, `trutruca`, `tuba romana`, `turi`, `waqra phuku`
    - 13 because their target waits: `kent bugle` and `royal kent bugle` (for `keyed bugle`),
      `basson russe` (for `russian bassoon`), `hatzotzerah` (for `chazozra`), `waza` (for
      `kakaki`), `luren` (for `lur`), `kerana`, `karna`, `kernei`, `kurenay` and `kanay` (for
      `karnay`), `trutruka` (for `trutruca`) and `tibetan horn` (for `dungchen`)
    - 2 for a build of their own: `tenor cornett` and `vienna horn`
    - 2 for moving formants: `bazooka` and `didjeribone`
    - 1 each for sub-audio fundamentals (`subcontrabass tuba`) and a buzzing membrane
      (`sudrophone`)
  - [ ] The brass range rule (the owner kept the range rule strict, 2026-11-09): a range is
    stated or an exact span above the lowest note, in sounding pitch; a written range counts only
    with the transposition its own source states (a B-flat instrument sounds a tone below its
    part, a horn in F a fifth below, a brass band's treble-clef part is never read as sounding),
    with the arithmetic shown; no pedal note or player's top beyond the stated compass; harmonic
    numbers only with a stated fundamental or named harmonic, never hedged; the key a source
    calls standard (a key in the row's own name is ranged in that key); maker and museum sources
    count, a retailer, blog or forum does not; nothing below A0 or above C8. The ranges derived
    under it: `bass wagner tuba` Eb1-F5 (VSL's archived Wagner tuba range page, "(no
    transposition)", its notation page writing the part a fifth above the sound; the lowest notes
    are pedals VSL says cannot be played forte, kept because they are inside the stated range);
    `soprano trombone` E3-C6 (Wikipedia: "similar to the B-flat trumpet, E3 to C6", read as stated
    notes because the infobox calls the range sounding and the same as the trumpet's; a reviewer
    may read "similar" as a hedge)
  - [ ] One-note horns and shells, waiting for a range: `nafir`, `nabal`, `sneng`, `tuba romana`
    (one or two pitches), `amakondere` and `cavalry trumpet`, and the shells, which a source says
    "produce only one pitch". The catalog needs a lowest below a highest, so each waits. Should a
    one-note horn or shell ship as a fixed-pitch entry instead?
  - [ ] The shell rule: a shell is an alias of `conch` only when a source presents the name as
    the conch itself (`shankha`, `dung dkar`, `pututu`, `fotuto`, `hakgediya`); a shell the
    source gives its own traits (`horagai`: a fitted mouthpiece, three or five notes; `putatara`:
    a carved wooden mouthpiece) waits for a sourced range. `hakgediya` ("a type of conch shell",
    no trait of its own) is an alias while `shankha` ("known in India as the shankha", a species
    name) is too: the line turns on a small difference in wording, the shakiest of the shell
    decisions. `triton shell` is dropped (a shell species, not an instrument name)
  - [ ] `carnyx` waits for a sourced range, not a build of its own: its page calls the replica's
    resonances inharmonic, but that is which notes it plays, not a non-periodic tone, so it is
    out of `BRASS_HELD_BACK`. An inharmonic build is the other reading
  - [ ] `tenor cornett` and `vienna horn` wait for a build of their own, held in
    `BRASS_HELD_BACK`: the tenor cornett's page says its bore is "more bugle-like" (the sentence
    is cited, to Baines), and the Vienna horn's sources name a narrower, more conical bore and a
    mellower sound. Their ranges are kept in the sheet's notes (`tenor cornett` C3-D5, `vienna
    horn` B1-F5, "sounding" on VSL's archived page). The alternative is a sound-alike of `cornett`
    and `french horn`
  - [ ] `b flat piccolo trumpet` is an alias of `piccolo trumpet`, not a sound-alike: VSL's
    archived page gives "D4 – G6" for the high B-flat piccolo but states neither written nor
    sounding and no transposition, so the brass rule leaves no range, and the Piccolo trumpet
    page says most are built to play in either B-flat or A. If the owner reads VSL's range as
    sounding, it could be a sound-alike (D4-G6); if written, the sounding notes would be a minor
    seventh higher
  - [ ] The "an uncited line is not a source" reading (batch 9's `garklein recorder` ruling)
    stands: the `buccin`'s infobox range E2 to B-flat 4 is on a page tagged as needing citations
    and carries no `<ref>`, so it waits (the audit marked it VERIFIED). Ship it at E2-Bb4 if the
    owner accepts the sentence
  - [ ] `trembita` and `truba` wait on uncited cells: their infobox ranges are
    `c<sup>1</sup>-g<sup>4</sup>` and `c<sup>3</sup>-g<sup>5</sup>`, uncited (the truba page is tagged for missing footnotes)
    and the page does not say which octave convention its superscripts follow. The two readings
    lie four octaves apart (`trembita` C4-G7 as Helmholtz, C1-G4 as scientific; `truba` C6-G8,
    above C8, or C3-G5)
  - [ ] `subcontrabass tuba` waits for sub-audio fundamentals, but the range ruling alone would
    not hold it: its only note below A0 is the pedal Bb-1 (15 Hz), which the ruling excludes, and
    Bb0 (29 Hz) is above A0. The wait rests on decision 4 (the spec's "sub-audio fundamentals"),
    so ship it above A0 if the owner reads the pedal as outside the instrument
  - [ ] `didgeridoo` among the approximations (`APPROXIMATING_NAMES`), never a parent: its page
    says the moving formants "give the instrument its readily recognisable sound" and the
    catalog's build has none, and a sound-alike would ship the omission under a new name. Its
    aliases are allowed (`yidaki`, `mako`): an alias is the same instrument and adds no build. A
    brass row whose source names the vocal tract's formants as its sound waits for moving
    formants (`bazooka`: its "subtle harmonic overtones fluctuate" give it its "characteristic
    warbling"; `didjeribone`); `jazzophone` waits for a range, not formants, because its wah is a
    mute. `dord` waits for a range, not formants: its page gives the didgeridoo-like playing only
    as something "some modern performers" believe
  - [ ] Slides, valves and keys as note choice, not sound: `valve trombone`, `superbone`, `slide
    trumpet`, `soprano trombone`, `bazooka` and the keyed and fingered rows are ranged and built
    like any brass. No row waits for a pitch LFO (portamento between notes)
  - [ ] The inharmonic ruling (`carnyx`, above): the family's builds make only whole harmonics,
    and the harmonic-pitch test checks every brass entry repeats at its note's period; a row whose
    source names inharmonic resonances as its sound would wait for a build of its own
  - [ ] No new shape: no brass row shipped, so none of the nine shapes grew (`mute cornett`
    names a horn-like integral mouthpiece and a flute-like sound, the best candidate for a new
    shape, but waits for a range)
  - [ ] Sizes and keys as sound-alikes, standard sizes as aliases: `bass wagner tuba` (of `wagner
    tuba`) and `soprano trombone` (of `trumpet`, its source giving it the B-flat trumpet's bore,
    bell and mouthpiece) are sound-alikes; `treble cornett` and `tenor horn` are aliases because
    their sources call the catalog's own `cornett` and `alto horn` by those names; `tenor tuba`
    is the euphonium's alias (the Tuba page's first sense; its second, the German Baryton, is not
    in the catalog). The saxhorn sizes all wait: the Saxhorn page gives each name to two or three
    sizes depending on the author. `soprano trombone` joins the trombones' size chain, first
  - [ ] Mutes out of scope (the spec's Non-goals: "Articulations and ensemble patches (pizzicato,
    mutes, string sections)"): the audit's four further mutes (trumpet bucket and plunger,
    trombone straight and harmon) are not rows; the catalog's four mute entries (trumpet straight, cup and harmon mutes, trombone cup
    mute) predate this and stay; the batch 10 plan's "six" was wrong
  - [ ] `corrugahorn`: noise makers or brass, still open from batch 1. It is dropped here as
    already decided (batch-1.tsv waits it in noise makers for a sourced range); its family
    question is the owner's
  - [ ] One-offs, artefacts and unsourced rows dropped: `fluba` and `hosaphone` (one maker's or
    player's design), `brudevaelte lur` (a single hoard; the `lur` row is the type), `savernake
    horn` (a single surviving olifant; the `oliphant` row is the type) and `medieval lituus` (a
    one-off reconstruction of an instrument "of an indeterminate nature"), `corno da tirarsi`
    and `tromba da tirarsi` (no instrument or document survives, or only a hedge: "may have
    been"), `swiss horn` (no fetched source names it: only an uncited fact site) and
    `triton shell` (above). The line between a one-off and a type is a judgment: `firebird
    trumpet`, `flumpet` and `soprano helicon` are in production, so they wait for a range
    instead, as `sudrophone`, `saxtuba` and `saxotromba` do; the plan's literal "one maker's
    design" would drop those too
  - [ ] `turi` waits for a sourced range, not DROP: the Met's API record titled "Two Cast Brass
    Side Blown Horns (Turi)" names the type, but it is a side-blown horn of Bastar, a different
    form from the audit's "S-shaped trumpet" (the Dharohar museum lists "Turri, Turhi" as names
    of the ransingha). It decides the Met's instrument, not the audit's lead; the Met's web page
    returned 429
  - [ ] `sneng` is the end-blown lip-blown horn (hs 423.121.21); the page's commoner side-blown
    sneng is a free reed (422.33), which belongs to the free reeds and is decided nowhere
  - [ ] `waza` waits for `kakaki` (the Kakaki page: 'also known as "Waza"'); the Sudanese `wazza`
    is a different instrument and not a row. `ram singa`, `sringa` and `kombu` are decided each
    on its own page, though the Ransingha and Sringa pages disagree on whether they are one
    group
  - [ ] `waldhorn` is an alias of `french horn` (its infobox lists "Horn, Waldhorn, Ventilhorn"),
    `inventionshorn` of `natural horn` (the Natural horn page gives it as a development of that
    instrument with no sound trait of its own). Modern German usage calls the valved orchestral
    horn Waldhorn too, so the natural horn would be the other reading
  - [ ] `BRASS_HELD_BACK`, the guard for every held name: six (`bazooka`, `didjeribone`,
    `subcontrabass tuba`, `sudrophone`, `tenor cornett`, `vienna horn`), refused as a catalog name
    or an alias by a test, and compared with the sheet by the code check. Every other wait is a
    sourced range or a target that waits for one, so none is held. Unlike batch 9's
    `PORTAMENTO_NAMES`, it holds every held name
  - [ ] The two-half split by Hornbostel-Sachs class as explicit lists (half A, the chromatic
    brass 423.2, 49 candidates; half B, the natural horns and trumpets 423.1 with the shells and
    animal horns, 55), the two sheets researched in parallel, and the shared files written up
    front by a setup agent. Half B shipped no build or sound-alike, so its code task ran only the
    alias steps (Task 5, 10 aliases, by ruling); Task 3 added half A's 2 sound-alikes and 6
    aliases
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make
    yet": none new. Every wait names a feature the spec or an earlier batch already named
    (moving formants, sub-audio fundamentals, a buzzing membrane) or `its own build`
- **Bugs to report** (found while building batch 10; none fixed here):
  - [ ] `didgeridoo` is built as a plain `_brass` build with drive, without the moving formants
    its page names. It is in `APPROXIMATING_NAMES` now. Its C2-E2 also lies below the page's
    "fundamental typically A2 to G3" (hedged, so it gives no range here, but the catalog's whole
    span is below even the lowest typical fundamental)
  - [ ] `conch` (C4-E4): the Conch page gives "Limited, typically only a few notes" and the
    Horagai page says "most shell trumpets from other parts of the world ... produce only one
    pitch". The catalog's four-semitone span would wait under this batch's rule (one note), and
    six aliases now resolve to it
  - [ ] `alphorn` (F#2-F#5) is harmonics 2 to 16 over the page's "most alphorns have a
    fundamental tone of F#1": "most" is a hedge and the 16th partial is what "Accomplished
    alphornists can command", a player's extreme. It would not pass the ruling (low priority)
  - [ ] `cornett` (G3-D6): the Cornett page's infobox gives "The sounding range of the treble
    cornett" as A3-D6 (cited to Herbert, Myers and Wallace 2019, p. 490); G3 is the lipped note
    ("can be lowered a further whole tone to G by slackening the embouchure"), an extreme. The
    page also gives the mute cornett "the same range ... G3 to A5", contradicting itself
  - [ ] `wagner tuba` (tenor, E2-F4): VSL gives the tenor Wagner tuba in B-flat "Eb1 – Bb5 (no
    transposition)", far wider at both ends (the new `bass wagner tuba` takes the same source)
  - [ ] `tuba` (BB-flat, D1-F4): VSL's contrabass tuba range is "A0 – B3", for C and B-flat
    tubas together, so not a clean contradiction, but worth a look
  - [ ] The 42 earlier entries carry no source comment: `brass.py`'s module docstring cites
    Adler and calls the folk instruments' ranges "typical", an unsourced claim. `ophicleide`
    (B1-C5) agrees with its page's score and `alto horn` (A2-Eb5) with the Tenor horn page's
    tessitura, but no other existing range was checked against a source
  - [ ] Wikipedia's range scores render as "Musical scores are temporarily disabled due to a
    security issue", so the audit's VERIFIED ranges can be read only from the wikitext, and the
    audit's `buccin` range turned out to be uncited there
- **Incidents and process**:
  - [ ] One agent used a bare `git stash push` and `pop` once, to compare a type-checker
    baseline (Task 3). No foreign stash was popped, nothing was left in the stash and no damage
    was found; the dispatches now forbid `git stash`
  - [ ] Parallel sheets, pushes and stacked PRs were made without asking (the owner,
    2026-11-12, #78)
  - [ ] Parked minors from the reviews: the code comments' quotes use ASCII for the B-flat sign,
    en dash and "a" with a grave accent (likely for ruff's ambiguous-unicode rules) while the
    sheet keeps the verbatim text; Task 1's `brass_sound_alikes.py` imported `CatalogEntry` under
    `TYPE_CHECKING` for an empty table, and Task 3 moved it back to a runtime import
  - [ ] A source-reading bug in the sheet's own process, caught and fixed: an extractor stripped
    `<ref>`, `<sub>` and `<sup>` from raw wikitext and HTML, which first made the tenor cornett's
    cited sentence look uncited and turned the trembita's and truba's superscript octaves into
    "c-g". The generator now checks every quote against the unparsed page
  - [ ] Pages the fetches could not reach: the Met's object pages (429, a Vercel checkpoint), the
    National Music Museum eMuseum, Britannica and Iranica (403), and the Edinburgh `cornet a
    pistons` record (read through WebFetch, whose extract matches the search listing)
- **Leads** (not sources under the ruling, so no row was ranged from them):
  - [ ] Leven's 2023 paper (Adoranten, `rockartscandinavia.com` `a23leven.pdf`, Tables 1 and 2):
    measured eigenfrequencies of each lur replica (for example Rorlykke 95-938 Hz), which belong
    to individual finds with different tunings, and the kombu's Sa, Pa' and Sa' as 262, 392 and
    523 Hz (C4-C5). A journal paper is not a source type the ruling lists
  - [ ] VSL's sample-library listing gives natural trumpets in Bb, C and D as F3-D6, G3-D6 and
    A3-E6: a product's sampled range, not an instrument page, with no stated written or sounding
    pitch and no standard key
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/brass.md`, listed in #70) are a later pass
    over this family
  - [ ] Ranging the 80 range WAITs from maker and museum sources (Wessex, Egger, Monk, the
    Edinburgh and Horniman records, MIMO, the Met once it answers), each row's notes recording what
    was searched; `post horn`, `hunting horn` and the bugle variants were not searched
  - [ ] Check the 42 earlier entries' ranges against sources (none was checked beyond the entries
    named above)
  - [ ] The engine changes that unblock the waits above, most rows first: the 80 range waits need
    no engine feature, then a build of their own (2), moving formants (2), sub-audio fundamentals
    (1) and a buzzing membrane (1); the 13 target waits follow their targets
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
- **Found**: batch 10's reviews (2026-11-12)
- **Status**: TODO
- **Priority**: Medium (before the double reeds batch builds on the same catalog)

### 81. Sound Engine: The Owner's Checks on Instrument Catalog Batch 11 — TODO
- **Goal**: confirm or overturn the calls made while batch 11 of #70 ran, and listen to its new
  instruments (double reeds 23 to 25 entries). Almost every candidate waits or drops: 0 built, 2
  sound-alikes, 82 waits, 11 aliases and 21 drops in the sheet's 116 rows. The plan's Task 5 added
  only `balaban` and 7 aliases, and the final review's ruling then took `balaban` out (it waits for
  its own build); the contraforte's own build was taken out in Task 3's second fix round
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter, ring and click is sound design unless a source is cited in the code; the folder is
  `build/instruments/double reeds/`). No new build was added, so there is nothing new to hear as a
  build, and the listening is the sound-alikes and the aliases beside their parents, which must
  sound alike by design:
  - [ ] The new builds: none (0 SHIP rows)
  - [ ] The 2 sound-alikes beside their parents: `contraforte` (A0-G4) beside `contrabassoon` (A0 is
    the catalog's floor: listen for a quiet or wrong note there) and `piccolo heckelphone` (E4-A6)
    beside `heckelphone` (the top notes sit well above the parent's register: listen for a thin or
    harsh tone)
  - [ ] The 11 aliases: `cor anglais` (of `english horn`), `baritone oboe` (of `bass oboe`),
    `fagott` (of `bassoon`), `cervelas` (of `rackett`), `gyaling` and `haidi` (of `suona`), `zurla`,
    `surna`, `surnay` and `zournas` (of `zurna`) and `bombard` (of `bombarde`)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-11.tsv`; the sheet's 116 rows:
  SHIP 0, SOUND_ALIKE 2, WAIT 82, ALIAS 11, DROP 21):
  - [ ] Every WAIT (82 rows), by reason:
    - 61 for a sourced range: `alto sarrusophone`, `baritone sarrusophone`, `baroque oboe`, `bass
      sarrusophone`, `bassanelli`, `bassett nicolo`, `contrabass oboe`, `b flat contrabass
      sarrusophone`, `e flat contrabass sarrusophone`, `cornamuse`, `dulcian`, `great bass
      crumhorn`, `great bass shawm`, `hautbois de poitou`, `kortholt`, `lupophone`, `nicolo`, `oboe
      da caccia`, `piccolo oboe`, `rauschpfeife`, `rothphone`, `sopranino sarrusophone`, `sopranino
      shawm`, `soprano sarrusophone`, `sordun`, `tenor sarrusophone`, `tenoroon`, `algaita`,
      `charumera`, `chirimia`, `dolcaina`, `gaita navarra`, `gralla`, `guanzi`, `hirtenschalmei`,
      `hne`, `hne galay`, `hne gyi`, `houguan`, `ken bau`, `kuzhal`, `mey`, `nadaswaram`, `ottu`,
      `pi chanai`, `pi chawa`, `pi mon`, `pi nai`, `piffero`, `rhaita`, `salamiya`, `sarune`,
      `serunai`, `shehnai`, `sopila`, `sralai`, `taepyeongso`, `tarompet`, `tarota`, `tenora`,
      `tible`
    - 19 because their target waits: `schreierpfeife` (for `rauschpfeife`); `oboe musette` (for
      `piccolo oboe`); `curtal`, `courtaud`, `bajon` (for `dulcian`); `bassanello` (for
      `bassanelli`); `ciaramella` (for `piffero`); `nagaswaram`, `nadhaswaram`, `nataswaram` (for
      `nadaswaram`); `shahnai`, `sanayi`, `sahanai` (for `shehnai`); `hojeok`, `hojok`, `nallari`,
      `saenap` (for `taepyeongso`); `ghaita`, `ghayta` (for `rhaita`)
    - 1 for a sourced drone tuning: `aulos`
    - 1 for its own build (a cylindrical bore): `balaban`, see the next item
  - [ ] `balaban` waits for its own build (a cylindrical bore) (the controller's ruling after the
    final review; it was a sound-alike of `duduk` at G3-C5 until then). Its page cites the bore
    ("a double-reed pipe with cylindrical bore", and Encyclopaedia Iranica's "cylindrical-bore"),
    and `_duduk` builds every harmonic (see Bugs to report), so a sound-alike would ship a cited
    trait its build lacks: the reason `piri` is in `APPROXIMATING_NAMES`, and what spec decision 4
    forbids. `duduk` itself stays because the Duduk page's "cylindrical body" is uncited. This call
    is the owner's to confirm. `mey` and `guanzi` will meet the same question if they are ever
    ranged, so the ruling decides all three; the sheet keeps `balaban`'s G3-C5 and the museum
    quote in its notes. The range, once a cylinder build exists, is ready
  - [ ] The double reed range rule (the owner kept the range rule strict, 2026-11-09): a range is
    stated or an exact span above the lowest note, in sounding pitch with the source's own
    transposition (an English horn a fifth below its part, a contrabassoon an octave below), with
    the arithmetic shown; no extension, extreme or player's top beyond the stated compass; capped
    reeds ranged like any other; never hedged ("about", "usually", "typically", "commonly",
    "practically"), never "comfortable" or "theoretical"; the key or size a source calls standard (a
    key in the row's own name is ranged in that key); maker and museum sources count, a retailer,
    blog or forum does not; nothing below A0 or above C8; a one-note instrument has no range; a
    Wikipedia range counts only with a citation in the raw wikitext. Two additions are this batch's,
    so confirm them: a span a source calls "comfortable", "theoretical" or "practically" is no
    range, and a Wikipedia range counts only when its citation is in the raw text (the quote check
    finds every `Range:` passage in the saved raw page). The ranges derived under it: `contraforte`
    A0-G4 (Eppelsheim's maker page: "written range A1 - G 5, sounding A0 - G 4") and `piccolo
    heckelphone` E4-A6 (Wikipedia, cited to Grove: written B3-E6, "pitched in F, a perfect fourth
    above the oboe"; the uncited extension of a third is left out). `balaban`'s G3-C5 (the
    Azerbaijan State Museum of Musical Culture: "from the \"sol\" of the small octave to the \"do\"
    of the second octave"; the next sentence, "The diapason can be expanded, depending upon the
    mastery of the performer", is a player's extreme and is left out) is kept in its WAIT row's notes
  - [ ] The quote ruling and the quote check: every `Range:` passage is quoted between «» from the
    raw page the worker saved (`build/batch-11-pages/`, gitignored), citations included, and
    `build/batch-11-quote-check.py` finds each in its saved page; it covers SHIP and SOUND_ALIKE
    rows only, so the quoted passages of the eight sarrusophone WAIT rows were checked by a script
    of Task 2's. `balaban`'s page is served as Windows-1252 with no declared charset and was
    transcoded to UTF-8 so the check could read it, its text unchanged. The curly quotes in its code
    comment are written straight (ruff's ambiguous-unicode rule)
  - [ ] The sarrusophones wait on hedged "theoretical" scores. Each size page's infobox gives a
    written score, a sounding score and a caption with the transposition, cited to Grove, but the
    scores match note for note the Sarrusophone page's uncited "theoretical ranges" list, and the
    same Grove reference says the keywork "usually allows a practical range to high G6" (a hedge).
    So `soprano sarrusophone`, `alto sarrusophone`, `tenor sarrusophone`, `baritone sarrusophone`,
    `bass sarrusophone` and `e flat contrabass sarrusophone` wait for a sourced range, with the
    arithmetic kept in their notes. If you read the in-cell citation as enough, they ship as
    sound-alikes of `sarrusophone` at Ab3-F6, Db3-Bb5, Ab2-F5, Db2-Bb4, Ab1-F4 and Db1-Bb3. They
    would share the C contrabass's fixed 2500 Hz low pass, which would muffle the soprano's top
    (about 1.4 kHz at F6); no fetched source gives a sound difference
  - [ ] `sopranino sarrusophone` is the eighth sarrusophone WAIT and differs from the six sizes
    above: Wikipedia has no Sopranino sarrusophone page (404), so it has no infobox, only the
    Sarrusophone page's uncited "theoretical ranges" list (E-flat sopranino: B-flat3 to G6, sounding
    D-flat4 to B-flat6) and no transposition from Grove, so there is no cited score to accept
  - [ ] `b flat contrabass sarrusophone` waits for a sourced range like its siblings. Its infobox
    (written B♭3-G6, "three octaves and a second (B♭) lower than written") would sound A♭0-F3, below
    the catalog's A0, so if the siblings ship it waits next for sub-audio fundamentals (the spec's
    name; the sheet's first draft waited it for that)
  - [ ] `contraforte` as a sound-alike of `contrabassoon`, not a build of its own (the sheet first
    had it SHIP, and Task 3's review and fix rounds reversed it). Its sources name a wider bore
    (Eppelsheim: "wide bore for a voluminous tone"), a round tone (Guntram Wolf: "klaren, runden
    Klang") and no rattle (Wikipedia: "lacks the distinct 'rattle'"), but the engine cannot make the
    bore's difference: with the contrabassoon's low pass, lowering the drive to 0.2 changed the
    crest factor by 1.5% (measured: 0.989, 0.978 and 0.970 of the contrabassoon's share of
    high-partial energy, i.e. slightly more, not less), a number chosen only to be different, and a
    brighter low pass (2800) had been read from "remaining quite strong into the high register",
    which is about pitch, not spectrum. The alternative is a build of its own with a sound-design
    drive
  - [ ] `terz heckelphone` is dropped as a one-off, on Heckel's own word: "The extremely rare terz
    heckelphone was only made once in 1915 exclusively for the composer Richard Strauss." The same
    page says "instruments" in its Construction section, the cited Marcuse says "few were made" and
    a `{{cn}}` line says "a handful were built", and it gives only "reaches to a depth of D4", so a
    waiting row was the other reading
  - [ ] `shehnai` (and its aliases `shahnai`, `sanayi` and `sahanai`) wait because the citation does
    not support the range: the page's A3-A5 line is followed by a Met essay that gives no range, and
    Britannica gives only "a two-octave range" (a width). It would be a sound-alike of `zurna` at
    A3-A5 (the nearest by centre; hs 422.112) if you accept the uncited line
  - [ ] The alias reasoning for `sorna`, `surna`, `surnay`, `zournas` and `zurla`: `sorna` is
    dropped as a distinct instrument with no candidate row (the Grove-cited Shawm page calls them
    "the closely related sorna and zurna"; the Sorna page's "also Zurna" is an uncited lead; decided
    like `serunai` and `mey`, which wait on their own because sources that disagree make no alias).
    `surna` is an alias of `zurna` though the Surna page gives the name to both the zurna and the
    sorna (its note says so); `surnay` follows the Zurna page's "Persian: karna/Kornay/surnay", and
    `zournas` and `zurla` its names note. Reversal: if the sorna is the zurna, it is an alias too
  - [ ] `bombard` is an alias of `bombarde` while `pommer` is dropped: the Bombard page makes the
    name the Breton instrument's ("Breton: bombard, talabard, French: bombarde"), where the Pommer
    page applies "pommer" to "the alto, tenor, bass, and contrabass members" of the shawm family, a
    generic term. The two rows share one audit line ("Pommer or bombard"), so the pair is the
    shakiest reading here; dropping `bombard` alike is the other
  - [ ] `tenora` and `tible` wait on hedged ranges with no stated octave numbering: the Gran
    Enciclopedia de la Musica gives written and sounding notes ("d'unes tres octaves del fa#2 al
    sol5 (del mi2 al fa5 en notes reals)" for the tenora, "normalment del la2 al mi5 (del re3 al la5
    en sons reals)" for the tible), but the tible's "normalment" is a hedge, the tenora's "d'unes"
    hedges the width, and neither names its octave numbering. Under the Franco-Belgian numbering
    (do3 is middle C) the tenora would be E3-F6 and the tible D4-A6, an inference of the sheet's,
    not the source's
  - [ ] `ottu` waits for a sourced range because it is a one-note instrument ("designed to produce a
    single constant note while being played"; the page does not name the note) and the catalog needs
    a lowest below a highest. Should a one-note instrument ship as a fixed-pitch entry instead? (the
    same question as #80's one-note horns and shells)
  - [ ] Other uncited or ambiguous ranges that wait, any of which is one row edit if you accept the
    line: `dolcaina` (the Dulzaina page's "range in the concert pitch goes from A3 to E5" is
    uncited; it would be a sound-alike of `bombarde`), `gralla` (a "tesitura" G3-G5 with no octave
    numbering), `sopranino shawm` (the maker's "f' - d''" next to "a little over one and a half
    octaves" contradicts itself, and the corrected reading is a guess), `nicolo` (the Shawm page and
    Britannica 1911 make it a tenor and an alto; a width), `mey` (a width), `taepyeongso` (a width),
    and the `hne`, `guanzi`, `houguan`, `nadaswaram` and `sralai` widths
  - [ ] The boundaries: `zukra` is dropped to the bagpipes batch ("is a Libyan bagpipe"; its bagless
    form is a double clarinet, not a double reed). `ciaramella` is decided here, as an alias name
    waiting for `piffero` (the fetched pages make the name the mouth-blown shawm and send the
    bagpipe to the separate Ciaramedda page); if you read it as the bagpipe, it is that drop.
    `piffero` is decided here as the shawm (it waits for a sourced range). `musette` (the musette de
    cour, a bagpipe) and `dulciana` (an organ stop) are dropped as ambiguous names, the unambiguous
    `oboe musette` carrying the alias (it waits for `piccolo oboe`). `fagott` is an alias of
    `bassoon`, not the audit's `dulcian` (the Fagott page redirects to Bassoon), and `doucaine` is
    dropped (it redirects to the Mary Rose page, which calls it the one surviving still shawm; the
    Dulcian page lists it among equivalents)
  - [ ] Generic and ambiguous names dropped: `pi` and `guan` (generic terms for classes of
    instruments), `kuan` (the Wade-Giles spelling of 管, so generic too), `laba` ("horn; trumpet"
    first), `mizmar` ("any single or double reed wind instrument"), `charamela` (a generic term for
    double- and single-reed instruments), `zamr` (it redirects to the double clarinet), `selompret`
    (the only fetched source says "bugle", so brass), `pommer` (above), `duduki`, `sundari` and
    `mukhaveene` (no fetched source describes the first two, and the third follows `sundari`)
  - [ ] One-offs and unsourced rows dropped: `tromboon` (Schickele's comic hybrid), `serpentine
    bassoon` ("a unique Australian double-reed instrument" built for one player; the audit itself
    found no page) and `doppioni` (no page describes it), and `terz heckelphone` (above). The
    in-production line stands: a maker's current model page or a museum's holding makes a type,
    however few were made
  - [ ] The module move: `double_reeds.py` holds the family (moved unchanged from `winds.py`, the
    way batch 9 moved the flutes), its table is `_DOUBLE_REED_BUILDS` and `DOUBLE_REEDS` is
    `_DOUBLE_REED_BUILDS + DOUBLE_REED_SOUND_ALIKES`; `winds.py` keeps the clarinets, saxophones,
    bagpipes and free reeds. The before-and-after record found `changed: []`
  - [ ] The bore ruling (Hornbostel-Sachs 422.111 a cylindrical single oboe, 422.112 a conical one,
    422.12 a double pipe): a sound-alike's parent is built with the row's bore, `_double_reed` and
    `_folk_shawm` being cones, `_capped_reed` a capped cylinder and `_duduk` a cylinder, and the
    form check refuses a sound-alike whose `hs` bore differs from its parent's. The capped and
    uncapped reeds stay apart (a capped reed's parent is a capped entry; the form check cannot see
    the cap, the review did): `hirtenschalmei` (capped, 422.111) and `kortholt` (capped) wait, so no
    capped row shipped
  - [ ] `piri` is in `APPROXIMATING_NAMES` and `hichiriki` is not, so `piri` can never be a parent
    and `hichiriki` still can: both are built as conical shawms though their pages say cylindrical,
    but the Piri page's "It has a cylindrical bore." is cited (to the Encyclopedia of Korean
    Culture, the batch 9 `dizi` precedent), where the Hichiriki page's line is tagged `{{citation
    needed}}`. Neither is a parent in this batch (the form check refuses both); the Guan page's
    cited "the guan has a cylindrical bore" and the Hichiriki page's "derived from the Chinese guan"
    make the hichiriki's cylinder better sourced than its own line, so you may want it in the set
    too
  - [ ] No new approximation: the hichiriki's embai ("a kind of pitch-gliding technique", cited) and
    the duduk's bent notes are articulations a player applies (the spec's Non-goals), and circular
    breathing (the Zurna, Suona and Duduk pages) is technique, since the engine sustains a note for
    as long as it is held
  - [ ] The pirouette is `_folk_shawm`'s trait already (the Shawm page: "The shawm's conical bore
    and flaring bell, combined with the style of playing dictated by the use of a pirouette, gives
    the instrument a piercing, trumpet-like sound"), and reeds, keys and metal count as a trait only
    when a source names their effect on the sound: the hne's sextuple reed, the sralai's quadruple
    reed, the tenora's keys and the metal bells set no row apart, and none waits for a build of its
    own
  - [ ] Drones, pairs and double pipes: `aulos` (a double pipe, 422.121.2) waits for a sourced drone
    tuning, held in `DOUBLE_REED_HELD_BACK` (its page's only drone sentence is Sachs's analogy to
    "bagpipes with a chanter and (modulated) drone", it gives neither pipe's notes, and a sourced
    range is missing too); `sopila`, "always played in pairs", waits for a range as one instrument
    of its size (the pair is an ensemble); the duduk's second-player dum is not part of the
    instrument
  - [ ] Any new builder and the trait its source names: none. No double reed row shipped as a build,
    so the family has the same four builders (`_double_reed`, `_folk_shawm`, `_capped_reed`,
    `_duduk`)
  - [ ] Sizes and keys as sound-alikes, standard sizes and other names as aliases: `piccolo
    heckelphone` is a sound-alike of `heckelphone` (its source makes the wide bore "the basic
    principle of the heckelphone"), and `contraforte` of `contrabassoon`;
    `balaban` was a sound-alike of `duduk` ("almost identical, except for historical and
    geographical differences"; a relation, which is why `mey` is not an alias and waits on its
    own) until the final review's ruling made it wait for a cylindrical build; `cor anglais`, `baritone oboe` and `cervelas`
    are aliases because their sources call the catalog's own `english horn`, `bass oboe` and
    `rackett` by those names, and `gyaling` and `haidi` are aliases of `suona` (the Gyaling page:
    "it is the Chinese double reed Suona horn"; the Suona page: "also called dida, laba or haidi",
    though it also gives 海笛 hǎidí to a piccolo size the catalog lacks). No new size chain: none of
    the shipped sound-alikes sits beside two or more catalog sizes a source names as one family. The
    `hne` sizes (`hne gyi`, `hne galay`) and `sopranino shawm`, `great bass shawm` and `great bass
    crumhorn` wait for a range
  - [ ] `DOUBLE_REED_HELD_BACK`, the guard for every held name: two (`aulos`, and `balaban` for its
    own build), refused as a catalog
    name or an alias by a test, and compared with the sheet by the code check. Every other wait is a
    sourced range or a target that waits for one (the sarrusophones' `sub-audio fundamentals` was
    dropped from the guard when `b flat contrabass sarrusophone` went to a sourced range)
  - [ ] The two-half split as explicit lists (half A, the orchestral, modern and early European
    double reeds, 34 candidates and 13 alias names, 47 rows; half B, the folk and traditional shawms
    and oboes with the aulos, 46 candidates and 23 alias names, 69 rows), the two sheets researched
    in parallel, and the shared files written up front by a setup agent. No code task was skipped by
    ruling: Task 3 added half A's contraforte and piccolo heckelphone and 4 aliases, Task 5 half B's
    balaban (later held back) and 7 aliases, and each half's rulings were applied after the reviews (the six
    sarrusophones, `terz heckelphone`, `contraforte`, `balaban`, `sorna`)
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    none new. The one feature wait, `aulos`, names batch 7's "a sourced drone tuning", and the
    sarrusophone sub-audio floor is the spec's "sub-audio fundamentals". The cylindrical bore's
    harmonic series (the duduk's, see below) is a build question, not a missing engine feature
- **Bugs to report** (found while building batch 11; none fixed here):
  - [ ] `piri` is built as a conical shawm (`_folk_shawm`) though the Piri page says "It has a
    cylindrical bore." (cited). It is in `APPROXIMATING_NAMES` now (never a parent); the build is
    the bug
  - [ ] `hichiriki` is built the same way, against the Hichiriki page's "has a cylindrical bore and
    thus its sound is similar to that of a clarinet" (tagged `{{citation needed}}`), and the Guan
    page's cited "the guan has a cylindrical bore" with its "derived from the Chinese guan" supports
    it. It is not in `APPROXIMATING_NAMES`
  - [ ] The catalog's `soprano crumhorn` (C4-D5) and `alto crumhorn` (F3-G4) are a tone below the
    Crumhorn page's table, soprano "(C4) D4-E5 (F5)" and alto "(F3) G3-A4 (Bb4)". The table is
    uncited, so this is a lead to check with a maker, not a source: the Renaissance Workshop Company
    gives a soprano of c'-e'' and an F alto of f-a', each with one upward key, which agree with the
    catalog without the keys
  - [ ] `oboe` (A6 at the top) sits above the Oboe page's "B♭3 to about G6" and "usually from B♭3 to
    G6" (cited, but hedged, so a lead). No fetched source supports A6
  - [ ] `_duduk` builds every harmonic (`falling_series(count=10, decibels_per_octave=9.0)`, no
    `odd_only`) though the duduk is modelled as a cylinder (the Duduk page: "The unflattened reed
    and cylindrical body"; the form check treats it as 422.111; `winds.py`'s module docstring says "a
    clarinet (a closed cylinder) favours odd harmonics"; `_capped_reed` does use `odd_only=True`).
    `balaban` would have inherited this, so it waits for its own build (a cylindrical bore) instead
    of shipping as a sound-alike, and `mey` and `guanzi` meet the same question if they are ever
    ranged
  - [ ] `zurna` is built as a cone (`_folk_shawm`) against the Zurna page's "It has a cylindrical
    bore, and a bell opening out in a parabolic curve". The line is uncited, and the same page says
    "a conical brass tube" and sits in "Single oboes with conical bore", so this is a conflict to
    rule on, not a cited bug. Four aliases resolve to it now (`zurla`, `surna`, `surnay`, `zournas`)
  - [ ] `double_reeds.py`'s docstring calls the folk instruments' ranges "typical of the common
    keys" without a source (moved unchanged from `winds.py`)
  - [ ] The 23 earlier entries carry no source comment, and no range or build of theirs was checked
    against a source beyond the entries named above (`sarrusophone` Bb0-G3 agrees with its cited
    infobox)
  - [ ] A warning to understand: `pytest -W error` fails on a DeprecationWarning at import (17 of
    them, from `speech_recognition`, whose `aifc` module Python 3.13 removed). It is third-party,
    present before this batch and shown by a plain `-W default` run, but it means the suite is not
    warning-clean under `-W error`. `ty` also reports 3 diagnostics in the catalog tests (Mapping
    subscript-assignment tests, from before this batch)
- **Incidents and process**:
  - [ ] Parallel sheets, pushes and stacked PRs were made without asking (the owner, 2026-11-12,
    #78)
  - [ ] Task 1's first commit went in with ruff errors (zsh word-splitting made the first lint run a
    no-op); it was fixed and amended before the report. Task 1's docstring line, 101 columns in the
    brief, lost its "and" to fit 100
  - [ ] Task 2's `build/batch-11-half-a.tsv` and Task 3's regenerated copy are gitignored working
    files; the committed sheet is the record. Task 2 moved its own fetched pages inside the session
    scratchpad and copied them back; nothing in `build/batch-11-pages/` was moved
  - [ ] The plan's contraforte (SHIP, then a rounder low pass, then a sound-alike) went through
    three rounds because a trait test measured an unsourced low-pass number. No sourced trait is
    measurable, so the plan's rule 7 ("a number chosen only to be different") decided it
  - [ ] A plan inconsistency caught before coding: "`hichiriki` and `piri` never parents" without
    being in `APPROXIMATING_NAMES` contradicted batch 9's `dizi` precedent. The controller ruled
    `piri` in (a cited cylindrical bore) and `hichiriki` out (an uncited line), above
  - [ ] Pages the fetches could not reach: the Met (429), MFA Boston (403), the National Music
    Museum eMuseum (403), the Grinnell catalogue (403), Britannica and Encyclopaedia Iranica (read
    from archives), the SMB sarunai PDFs (404), the Wikipedia pages for `doppioni` and `sundari`
    (404), Guntram Wolf's dulcian and baroque oboe pages (no text), and Lorée's and Marigaux's
    piccolo oboe pages (no compass). The Koizumi, Horniman and Edinburgh catalogues were not reached
  - [ ] Parked minors from the reviews: the sheet's notes for `surna`, `surnay`, `aulos` and `kuan`
    were extended per the Task 4 review (the name covers two reeds; the drone is by analogy and the
    range is missing too; the Wade-Giles spelling); the `sopranino shawm` row's "f' - d''" is
    probably a typo for d''' but the corrected reading is a guess; the contraforte's drive had read
    the wider bore as smoother where the heckelphone's reads as more drive (moot once it became a
    sound-alike); the code comments write the B-flat sign and curly quotes in ASCII for ruff's
    ambiguous-unicode rules while the sheet keeps the verbatim text
- **Leads** (not sources under the ruling, so no row was ranged from them):
  - [ ] The Grinnell catalogue's taepyeongso snippet ("if, for example, it is approximately
    B-flat4", hedged, 403 on fetch); powerflute.ch's nadaswaram (one octave from G3, a collector
    site); Karahasanoglu's mey paper ("limited to one octave", a width); Moeck's baroque oboe "after
    Denner, c'-d''', a'=415", found only on a retailer's archived list (Moeck's historical line
    closed in 2008); Heckel's terz heckelphone "reaches to a depth of D4"; Wikipedia's uncited
    crumhorn range table and Dulzaina range line
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/double-reeds.md`, listed in #70) are a later
    pass over this family
  - [ ] Ranging the 61 range WAITs from maker and museum sources (MIMO, the Met once it answers, the
    Horniman, the Edinburgh and Bate collections, the Koizumi catalogue, Moeck, Moulder and the
    Renaissance Workshop Company), each row's notes recording what was searched; the six
    sarrusophone sizes with an infobox and `b flat contrabass sarrusophone` are the quickest if you
    accept their infobox scores (the `sopranino sarrusophone` has none)
  - [ ] Check the 23 earlier entries' ranges and builds against sources (the crumhorns, the `oboe`,
    the `piri`, `hichiriki` and `zurna` bores, the `duduk`'s series; none was checked beyond the
    entries named above)
  - [ ] The engine changes that unblock the waits above, most rows first: the 61 range waits need no
    engine feature, then a sourced drone tuning (1) and a cylindrical build (1, `balaban`); the 19 target waits follow their targets
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
- **Found**: batch 11's reviews (2026-11-12)
- **Status**: TODO
- **Priority**: Medium (before the bagpipes batch builds on the same catalog)

### 82. Sound Engine: The Owner's Checks on Instrument Catalog Batch 12 — TODO
- **Goal**: confirm or overturn the calls made while batch 12 of #70 ran, and listen to its new
  instrument (bagpipes 8 to 9 entries). Almost every candidate waits or drops: 1 built, 0
  sound-alikes, 62 waits, 4 aliases and 24 drops in the sheet's 91 rows. Several calls were
  reversed during the batch (see the list below): `dudy` shipped and then went back to waiting,
  `brian boru bagpipes`, `sac de gemecs` and `parkapzuk` wait for a range rather than for an
  engine feature, and `union pipes`, `biniou braz`, `tulug` and `mushak baja` were dropped
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter, drone level and click is sound design unless a source is cited in the code; the
  folder is `build/instruments/bagpipes/`):
  - [ ] The new build: `sackpipa` (Säckpipa in A, E4-E5, one drone at E4), the family's first
    cylindrical chanter (`CYLINDRICAL_CHANTER_LEVELS`: odd harmonics only, sound design marked so
    in its comment). Listen for a hollow, clarinet-like chanter against `scottish smallpipes`
    (whose levels, drone levels, low pass, drive and breath it copies; the sources call the
    säckpipa's tone "quite soft" and "warm, soft"), a quiet single drone, and the same instrument
    at both ends of its octave. The trait test measures the chanter alone: at A#4 (the middle
    note of E4-E5, not the sources' tonic A4) the second and fourth harmonics are 0.0002 of the
    first and the third is 0.387, against the Highland pipe's even harmonics above 0.6
  - [ ] The sound-alikes beside their parents: none shipped (0 SOUND_ALIKE rows), so there are no
    retuned sound-alikes to hear and no drones to compare. The mechanism is in place and tested
    with an empty table (`BAGPIPE_RETUNED_DRONES`)
  - [ ] The 4 aliases beside their parents, which are the same instrument by name: `irish pipes`
    (of `uilleann pipes`), `lowland pipes` and `half long pipes` (of `border pipes`) and `gaita
    galega` (of `galician gaita`)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-12.tsv`; the sheet's 91 rows:
  SHIP 1, SOUND_ALIKE 0, WAIT 62, ALIAS 4, DROP 24):
  - [ ] Every WAIT (62 rows), by reason:
    - 57 for a sourced range: `baghet`, `biniou koz`, `boha`, `bousine`, `brian boru bagpipes`,
      `cabrette`, `caramusa`, `cornemuse du centre`, `cornish bagpipes`, `gaita asturiana`, `gaita
      de boto`, `gaita de saco`, `gaita sanabresa`, `gaita transmontana`, `great irish warpipes`,
      `odrecillo`, `pastoral pipes`, `sac de gemecs`, `scottish smallpipes in d`, `surdelina`,
      `surdullina`, `veuze`, `ciaramedda`, `chabrette`, `cabreiresa`, `askomandoura`, `cimpoi`,
      `dankiyo`, `dudmaisis`, `dudy`, `dzhura gaida`, `gudastviri`, `istarski mih`, `jirba`, `kaba
      gaida`, `latvian dudas`, `macedonian gaida`, `magyar duda`, `marktsackpfeife`, `mashak`,
      `ney anban`, `parkapzuk`, `polish dudy`, `sakkipilli`, `sorbian dudy`, `sruti upanga`, `swiss
      sackpfeife`, `tadghtita`, `titti`, `torupill`, `tsampouna`, `tulum`, `volynka`, `zaqq`,
      `zukra`, `zummarah bi soan`, `schaferpfeife`
    - 5 because their target waits: `chabretta` (for `chabrette`), `gaita mirandesa` (for `gaita
      transmontana`), `masak been` (for `mashak`), `xeremies` (for `sac de gemecs`) and `guda` (for
      `tulum`)
    - 0 for an engine feature, a build of its own, a sourced drone tuning or a sourced chanter
      bore: `BAGPIPE_HELD_BACK` is empty
  - [ ] The range ruling (the owner kept the range rule strict, 2026-11-09): a range is stated or
    an exact span above the lowest note, in sounding pitch, never hedged ("about", "typically",
    "commonly", "usually", "practically", "can reach"); a compass relative to a tonic counts only
    when the same source fixes the tonic's octave; no extension or extreme (a note in parentheses,
    a player's top, an optional key); a width ("nine notes"), a key alone, note letters with no
    octave, a relation to a sibling ("an octave above the bombarde") or a tessitura is no range;
    the key the source calls standard, usual or most common (a key in the row's own name is
    ranged in that key); a maker's, museum's or piping society's page outranks an uncited
    Wikipedia line, and a retailer, blog, forum or tune book is not a source; nothing below A0 or
    above C8; a one-note instrument has no range; a Wikipedia range counts only with a citation
    in the raw wikitext that supports it. The one range derived under it: `sackpipa` E4-E5 (Leif
    Eriksson, a maker writing of his own pipes: "The normal key for the Swedish bagpipe is a', the
    lowest tone being e', and the highest e'', with a', in the middle."). It stands although the
    maker's own page says "I do not make bagpipes for sale anymore": a maker's stated normal key
    counts whether or not he still sells (the controller's ruling; confirm it)
  - [ ] The nominal-pitch ruling (a bagpipe's note names are often its own, not concert pitch): a
    nominal range counts only with the same source's sounding pitch for a named note, the shift
    being the nearest equal-tempered semitone (A4 = 440 Hz) from the stated pitch, a span's
    midpoint, and a pitch within 10 cents of halfway between two semitones decides nothing. It
    shifted no shipped row. It held `gaita asturiana` (its tonic C5 sounds "between concert C and
    C#", within the margin) and the catalog's `highland bagpipe` range (Ab4-Bb5, the page's G4-A5
    nominal range a semitone up) agrees with it. Confirm the rule, in particular the 10-cent
    margin
  - [ ] The drone ruling: a drone is sourced when a source gives its note with an octave, a hertz
    figure, or an interval from a chanter note whose sounding pitch it fixes; a droneless pipe
    says so; unison drones count once; muted drones are left out; at most two distinct pitches
    (`with_drones` keeps room for two beside the chanter's breath); keyed drones are notes of the
    sequence; and every drone sounds its derived note equal-tempered at A4 = 440 Hz like the
    chanter, in hertz to two decimals, a source's hertz figure deciding which note and not the
    drone's pitch. The one derived drone is `sackpipa`'s E4 (329.63 Hz, Eriksson: "The drone is
    normally tuned to the e' of the chanter."). Equal-tempered drones are this plan's call and
    differ from the older entries' (Bugs to report): confirm
  - [ ] The retuned sound-alikes, decision 8's first shipped use of `sound_changes`: a sound-alike
    whose sourced drones differ from its parent's by more than 5 cents (or in number) carries
    `sound_changes={'drones': ((hertz, level), ...)}`, each drone at its derived note with the
    level of the parent's drone of the same rank (the parent's levels copied unchanged), and only
    `drones` may change. The tests changed for it: `CHANGED_SOUND_ALIKE_NAMES` no longer holds
    the bagpipes, the sound-alike test's equality skips the retuned (they must differ from the
    parent) and `test_a_retuned_bagpipe_sounds_its_sourced_drones` pins each one's drones. None
    ships: the table `BAGPIPE_RETUNED_DRONES` is empty. The test first asserted `drone_notes`,
    which fails for a droneless retuned bagpipe (`drones=()`, as the plan allowed); the assert
    was removed in the final review, so the test checks the hertz list alone. Retuned
    sound-alikes were considered for `marktsackpfeife` (a `highland bagpipe` sound-alike at G4-A5 with drones E3 and A2, refused
    below) and `dudy` (a `sackpipa` sound-alike with an E♭1 drone, below)
  - [ ] `dudy` was shipped and then went back to waiting (a sourced range). Pavel Číp & synové (a
    dudy maker, histnastroje.cz/dudy-lidove/) give the bore ("Vrtání píšťal válcové. Tvorba tónu
    pomocí jednoduchého nárazného jazýčku.": cylindrical, a simple beating reed), the most used
    key (Es dur), the tone row «B-d-Es-f-g-a-b-c'», "neúplné nony" and a drone "o dvě oktávy níž
    než základní tón". Fix round 1 read the row as B♭2-C4 with an E♭1 drone (38.89 Hz) as a retuned
    `sackpipa` sound-alike; the re-review found that no source states the sounding octave: the row
    is mixed-case, not strict Helmholtz (a capital Es between a small d and a small f), and the
    pipe lengths point to a nominal row an octave low (a closed cylinder sounding B♭2 needs about
    0.74 m, and one sounding 38.89 Hz about 2.2 m). The Číp page is its lead, and a source that
    fixes the sounding octave (a maker, museum or society) would close it. This call is the
    owner's to confirm, with the octave doubt. `sorbian dudy` and `polish dudy` wait for a range on
    their own pages
  - [ ] The chanter ruling (Hornbostel-Sachs 422.1 a double reed, 422.2 a single reed, then single
    or a set, then 1 cylindrical or 2 conical): the `hs` cell holds the chanter's class from a
    page's infobox, its category, or a source sentence naming the reed and bore, and a ranged row
    with no sourced bore waits for `a sourced chanter bore`, a source wait this plan added (no row
    waits for it in the end). Every existing bagpipe is built with an every-harmonic chanter, that
    is a cone, so a sound-alike of an existing bagpipe has a conical chanter and a cylindrical
    chanter ships as its own build or waits. `CYLINDRICAL_CHANTER_LEVELS` is `SWEET_CHANTER_LEVELS`'s
    odd harmonics with the even ones silent (`(1.0, 0.0, 0.4, 0.0, 0.17, 0.0, 0.06, 0.0)`), sound
    design, and `sackpipa` is its first build. The trait its source names is the bore (Alban
    Faust, a maker: "a single reed which sits on a cylindrically drilled chanter"); the drone
    levels, low pass 4000, drive 0.3 and breath 0.01 are copied from `scottish smallpipes`, and the
    process-state guard asked for no line (a literal tuple of floats). Confirm the rule and
    `sackpipa` as its first build
  - [ ] `scottish smallpipes`, `northumbrian smallpipes` and `musette de cour` are never parents (the
    form check refuses them): each page names a cylindrical chanter, uncited, and each is built
    with an every-harmonic chanter. `scottish smallpipes` joins `APPROXIMATING_NAMES` (like `piri`,
    batch 11): the Bagpipe Society, a piping society, writes "With its cylindrical bore, the sound
    is characteristically lilting" (its guide to the Scottish smallpipes), so the cited trait the
    build lacks is the reason, and `piri` and `dizi` are the precedent. `northumbrian smallpipes`
    and `musette de cour` stay out (their lines are uncited; the ruling that kept the uncited
    `hichiriki` out). Should either join it?
  - [ ] `marktsackpfeife` is refused as a musician's site, not shipped. The Marktsackpfeife page's
    range ("It features a range from one whole tone lower than the tonic (A = 440Hz) to one octave
    above it", g' to a'') sits in an uncited Tuning section, so it is no range (ruling 10), and
    the only other page is Sönke Kraft's personal site ("standard scale range g¹ a¹ b¹ – a² ...
    Long drone sounds on tone A, short drone sounds on tone e⁰"), which is not a maker or society
    (batch 9's `quenacho` precedent). If you accept Kraft's page, the row becomes a retuned
    sound-alike of `highland bagpipe`, G4-A5, `drones=((164.81, 0.45), (110.0, 0.55))` (E3 and A2;
    the saved page is the sheet row's). It would be the batch's only retuned sound-alike
  - [ ] One-note instruments waiting for a range: `sruti upanga`, a drone with no chanter ("It is
    used merely as a drone; the holes ... are wholly or partially stopped with wax so as to tune
    the instrument to the pitch desired"). Should one ship as a fixed-pitch entry? (the same
    question as #80's one-note horns and shells and #81's `ottu`)
  - [ ] Double chanters: two melodic pipes are notes of one sequence (batch 9's double-pipe
    ruling), so the `ciaramedda`, `zukra` and `surdelina` ranges would run from the lower pipe's
    lowest note to the upper's highest. A pair in unison that a source says is "tuned slightly
    apart" to beat has a sourced trait no bagpipe build can make (`with_drones` keeps only the
    chanter's tone and breath sources), so it would wait for `its own build (a detuned double
    chanter)`: `parkapzuk`'s page says so ("the chanters are tuned slightly apart, giving a
    'beat'"), but it waits for a range first (rule 6; its page is unsure even of one or two
    chanters, "Some sources indicate that the parkapzuk is single chantered"), so the engine wait
    is only in its notes. That is a name beyond the spec's table for "What the engine cannot make
    yet": `its own build (a detuned double chanter)`
  - [ ] Three or more drones as an engine limit: `with_drones` has room for two beside the
    chanter's breath, so a source giving three distinct sounding pitches would wait for `more than
    four sources` (the spec's name). `brian boru bagpipes` ("a single tenor drone pitched one
    octave below the chanter, a baritone drone pitched one fifth below the tenor drone, and a bass
    drone pitched two octaves below the chanter") and `sac de gemecs` (three drones, "two octaves
    below the tonic of the chanter", a fifth above that and an octave below the chanter) have
    three pitches, but each waits for a range first (neither source fixes the chanter's pitch),
    so the limit is in their notes and not a wait. Both were first held back for the engine
    limit and reversed to a range wait by the controller, so `BAGPIPE_HELD_BACK` holds nothing
  - [ ] No new approximation: grace notes, closed (staccato) fingering, regulators' chords, flea
    holes and bellows are technique or notes of a sequence (the spec's Non-goals), except where a
    source names a closed chanter as the instrument's own sound
  - [ ] Sizes and keys as sound-alikes, other names as aliases: none of the sizes shipped
    (`scottish smallpipes in d`, `kaba gaida`, `dzhura gaida`, the dudy sizes wait for a range).
    The 4 aliases rest on a cited page naming the catalog's own entry: `irish pipes` (the Uilleann
    pipes page, "also known as Union pipes and sometimes called Irish pipes", cited to UNESCO),
    `lowland pipes` and `half long pipes` ("Other names have been used for the instrument: Lowland
    pipes and reel pipes in Scotland, and half-long pipes in Northumberland and Durham", the Border
    pipes page) and `gaita galega` (the Galician gaita page). `xeremies` is an alias too, of
    `sac de gemecs`, waiting for it (the Xeremia page, cited to Genovart Espinosa: "while in
    Catalonia it is known as sac de gemecs"; its drone difference is uncited and hedged, "often
    dummy drones", a configuration of the same pipe, and the page also gives the name to Ibiza's
    bagless `reclam de xeremies`). No new size chain
  - [ ] `union pipes`, `biniou braz`, `tulug` and `mushak baja` are dropped. `union pipes` is
    ambiguous: the Pastoral pipes page also names it (its infobox, "|names= '''Union pipes'''"),
    and the National Museum of Scotland's record A.1947.105 ("Union or Pastoral bagpipe") is
    named but not quoted (its data request was refused by the permission classifier, and the
    collection page is a script-drawn shell). `biniou braz` ("In Brittany, the great Highland
    bagpipe is known as the binioù braz") rests on uncited lines, the standard that also refused
    `great irish warpipes` ("one and the same as the Scottish great Highland bagpipe", in an
    `{{Unreferenced section}}`, so it waits as its own row). `tulug` rests only on the uncited List
    of bagpipes line, which carries the hidden comment "Isn't the Azerbaijani bagpipe called a
    'tulug'?", and `mushak baja` only on the Mashak page's lead sentence with no reference of its
    own (the cited paragraph says "masak baja"; `masak been` waits for `mashak` on that paragraph).
    Each drop is "no cited source gives it as another name" (union pipes: ambiguous). If you read
    the lines as enough, they are aliases of `highland bagpipe` (biniou braz) and `tulum` and
    `mashak` (the other two)
  - [ ] `zampogna` is dropped as a generic term ("a generic term for a number of Italian double
    chantered bagpipes", "there are dozens"), though it is the name people would most likely type
    for an Italian bagpipe: it resolves to nothing, and `surdullina` and `ciaramedda` lose their
    parent. If you want it typed anyway, it is a WAIT for a sourced range or an alias of a
    chosen type
  - [ ] Generic and ambiguous terms dropped: `doedelzak` (the Dutch and Flemish word for
    bagpipes), `welsh pibgod` (one of several Welsh words for bagpipes), `dudelsack` and
    `sackpfeife` (the German words for any bagpipe; the Schäferpfeife page's "also known as the
    Sackpfeife" arguably meets the exception, and `schaferpfeife` itself waits), `habban` (the Gulf coast's Holi bagpipe and, in Oman, a
    nativized Highland pipe: "While the term itself is generic"), `gajdy`, `gajde` and `gayda` (each given to several bagpipes), `reel pipes`
    (a half-set Highland pipe and the Border pipes' other name), `piva` (also the Istrian
    `istarski mih`'s name), `bock` (the Bohemian bock and the Großer or Praetorius Bock: the
    Met's separate records agree), `mizwad` (the Tunisian mezoued, its own instrument; Baines's
    claim that it is the zukra is uncited and disputed), `coimbra` (a city: the bagpipe is the
    gaita-de-fole coimbrã, with no page) and `mutsianka` (the audit's "(memory)" row; the list gives
    it to the Belarusian duda). `cornemuse du centre` is decided as one instrument, not dropped
    as generic (its page's lead, cited to Grove, names one type in many keys)
  - [ ] One-offs, reconstructions and unsourced rows: `zetland pipes` is dropped as a one-off (one maker's
    design, Royce Lerwick's, out of production since about 2000), `gaita alistana` and `mechawka` for
    no fetched source (the en and es pages are 404; the Wendish Museum's records answered 404 and
    503), `electronic bagpipe` as the electronic family's (below). The in-production line stands:
    a maker's current model page or a museum's holding makes a type
  - [ ] The boundaries: `ciaramella` is dropped, "already decided" by batch 11's WAIT (its target,
    `piffero`, the mouth-blown shawm), and the bagpipe is `ciaramedda`, an instrument row of its
    own (the Ciaramedda page: "a type of zampogna with equal length double chanters", "often only
    the middle drone is reeded while the other two remain muted"; it waits for a range).
    `zukra` waits for a range (a bagpipe in the south and west of Libya, a double clarinet played
    by mouth in the east, so its bag form is this family's) and `mizwad` is a different
    instrument (above). `electronic bagpipe` is dropped to the electronic family (an electrophone
    that emulates the Highland pipe, among others), whose batch is done: #70 lists it for a
    later electronic pass
  - [ ] The naming ruling: a key goes in the title after the name, as the bagpipes' titles have it
    (`scottish smallpipes in d`, "Scottish smallpipes in D"), so `sackpipa` is "Säckpipa in A" and
    the dudy row is "Dudy (Czech bock)"
  - [ ] The module move: `bagpipes.py` holds the family (moved unchanged from `winds.py`, the way
    batches 9 and 11 moved the flutes and double reeds), its table is `_BAGPIPE_BUILDS` and
    `BAGPIPES` is `_BAGPIPE_BUILDS + BAGPIPE_SOUND_ALIKES`; `winds.py` keeps the clarinets,
    saxophones and free reeds. The before-and-after record found `changed: []`. The moved
    code dropped its "# --- Bagpipes ---" banner (harmless in a one-section module)
  - [ ] `BAGPIPE_HELD_BACK`, the guard for every non-range wait: empty, refused as a catalog name
    or an alias by a test and compared with the sheet by the code check. The plan expected it to
    hold `brian boru bagpipes`, `sac de gemecs` and `parkapzuk` (an engine limit, an engine limit
    and a detuned double chanter), and each was ruled back to a range wait, which is checked first
  - [ ] The two-half split as explicit lists (half A, the bagpipes of Western Europe with the
    electronic bagpipe, 31 candidates and 13 alias names, 44 rows; half B, those of Central,
    Northern and Eastern Europe, the Balkans, the Mediterranean islands, the Caucasus, the Middle
    East, North Africa and South Asia, 35 candidates and 12 alias names, 47 rows), the two sheets
    researched in parallel, and the shared files (the names file, the candidate lists and the
    three check scripts) written up front by a setup agent. Tasks 3 and 5 (the two halves' code)
    went to one implementer, since half A had only 4 aliases and half B ships nothing but
    `sackpipa`. No code task was skipped by ruling
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    `its own build (a detuned double chanter)` (above; in `parkapzuk`'s notes, no row waits for
    it) and `a sourced chanter bore` (a source wait this plan added, with no row on it)
- **Bugs to report** (found while building batch 12; none fixed here):
  - [ ] `highland bagpipe`'s drones (240 and 120 Hz) are 51 cents above its chanter's B♭ (233.08
    and 116.54 Hz), though its page says "The drones are tuned to this tonic note" (the sentence is
    in the paragraph cited to Macpherson). Kraft's page ("c. a¹ = 472 Hz") agrees with the offset
    as a pitch, but the engine's chanter is equal-tempered, so the drones beat against it
  - [ ] The drone tunings and counts on three pages do not match their builds, each built with
    two drones: the Northumbrian smallpipes page's "three will usually be tuned to the tonic,
    dominant and octave tonic" against the build's two octave G drones (196 and 98 Hz); the Border
    pipes page's three drones "typically tuned A, a, e'" (or "A, a, a") against its two (220 and
    110 Hz; no source fixes the octave of the page's letters); and the uilleann pipes' three
    drones (the chanter's lowest note, an octave below and two octaves below: D4, D3 and D2 for a
    D4 chanter) against its two (D3 and D2). The two-drone limit of `with_drones` explains them,
    so they are leads, not cited bugs
  - [ ] Every existing bagpipe is built with an every-harmonic chanter (`HIGHLAND_LEVELS` or
    `SWEET_CHANTER_LEVELS`), a cone, though three pages name a cylindrical chanter, uncited:
    `scottish smallpipes` ("The instrument has a cylindrically bored chanter"; now supported by
    the Bagpipe Society's "With its cylindrical bore", so it is in `APPROXIMATING_NAMES`),
    `northumbrian smallpipes` ("The cylindrically bored chanter has a number of metal keys") and
    `musette de cour` ("Both the chanters and the drones have a cylindrical bore and use a double
    reed")
  - [ ] `bulgarian gaida`'s chanter bore: the evidence is mixed, so this is a lead, not a bug. It
    is built with `HIGHLAND_LEVELS`. The Cimpoi page (cited to Sachs) puts the Eastern European
    bagpipes in a "cylindrical chanter bore and the use of single reeds" group and says its Type
    3 is "virtually identical to Bulgarian bagpipes"; Kraft's page lists "Gaide" among
    cylindrical single-reed chanters; against that, the Kaba gaida page gives 422.112
  - [ ] `scottish smallpipes` is now in `APPROXIMATING_NAMES`: its cylindrical bore is the build's
    missing trait (above), and a name is added to the list only for a cited one
  - [ ] `winds.py`'s docstring calls the folk ranges "typical of the common keys" without a
    source (moved with the clarinets and free reeds; `sound.md` repeats the phrase)
  - [ ] The 8 earlier entries carry no source comment, and no range or build of theirs was checked
    against a source beyond the entries named above
  - [ ] A warning to understand: `pytest -W error` fails on a DeprecationWarning at import
    ("aifc was removed in Python 3.13", from the standard-aifc package that
    `speech_recognition` imports). It is third-party and present before this batch (#81 records
    it); a new warning in these runs would be a new finding
- **Leads** (not sources under the ruling, so no row was ranged from them):
  - [ ] The cornemuse du centre's range, from the Lowland and Border Pipers' Society's magazine
    (LBPS Common Stock, December 2012, "Cauld wind in the Massif Central"): "The most common
    nowadays is the 16# in G." and "The range is from lower F to C' (one octave higher)". It
    describes the Béchonnet model and gives letters with no octave and no sounding pitch (ruling
    5), so it only names a standard size
  - [ ] The macedonian gaida's cylindrical bore, from the Bagpipe Society's article on the Macedonian
    gajda: "predominant cylindrical bore (which is responsible, together with the single reed, for
    the sound of the chanter)", with "a range, or ambitus, of an octave" (a width), the key "A" and
    the lowest note "E" (no octaves). It would make the gaida a cylinder like `sackpipa`
  - [ ] `dudy`'s Číp page (above), the drones of `brian boru bagpipes` and `sac de gemecs` (three
    pitches each) and `marktsackpfeife`'s Kraft page (above)
  - [ ] The Met's Binioù kozh (503854) and Scottish small pipe (501860) records (HTTP 429 on the
    first fetch, so unread), and the Met's open-access API, which gave names and classes only
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/bagpipes.md`, listed in #70) are a later
    pass over this family
  - [ ] Ranging the 57 range WAITs from maker, museum and piping-society sources (MIMO, the Met
    once it answers, the Edinburgh (MIMEd) and National Museum of Scotland records, the Horniman,
    Alban Faust's chart, the Czech makers Janovec, Konrady and Číp), each row's notes recording
    what was searched; `dudy`, `cornemuse du centre` and `macedonian gaida` are the best leads
  - [ ] Check the 8 earlier entries' drones, ranges and builds against sources (the Highland pipe's
    drones against its chanter, the three drone counts above, the gaida's bore, the three
    cylindrical chanters); none was checked beyond the entries named above
  - [ ] The engine changes that unblock the waits above, most rows first: the 57 range waits need
    no engine feature, the 5 target waits follow their targets, and a detuned double chanter
    (`parkapzuk`) and a third drone (`brian boru bagpipes`, `sac de gemecs`) are the only engine
    features, both behind a range
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
- **Incidents and process**:
  - [ ] The Pi hook was skipped while the Pis were unreachable (the owner, 2026-11-13)
  - [ ] The syft pin was bumped to 1.57.1 on the stack (the owner's choice)
  - [ ] The two sheet halves were researched in parallel, and pushes and stacked PRs were made
    without asking (the owner, 2026-11-12, #78)
  - [ ] The reversals above (`union pipes`, `biniou braz`, `xeremies`, `brian boru bagpipes`,
    `sac de gemecs`, `parkapzuk`, `tulug`, `mushak baja` and `dudy`) each followed a review round:
    the half A sheet had one fix commit, half B two, so the sheet's own history holds the first
    readings
  - [ ] Parked minors from the reviews: Task 1's banner (above) and the `assert drone_notes`
    (added in Task 3's commit, removed in the final review); the `tulum` row's "(Laz: guda)" quote is a rendering of a
    template, not literal text; the Herri Musika record quoted in `dudy` was fetched and not
    saved (its row is unranged); the `sakkipilli` and `sackpipa` rows apply the generic-term
    exception (each page also makes the word one revived instrument's name); `volynka`'s `hs` is
    `none` (its infobox gives 421.111-12, a flute's class); `tulum`, `zukra` and `dzhura gaida`
    take their `hs` from Kraft's page, cited for the class only
- **Found**: batch 12's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before the organs batch builds on the same catalog)

### 83. Sound Engine: The Owner's Checks on Instrument Catalog Batch 13 — TODO
- **Goal**: confirm or overturn the calls made while batch 13 of #70 ran, and listen to its new
  instruments (organs 9 to 19 entries). Three builds, 7 sound-alikes, 32 waits, 4 aliases and 24
  drops in the sheet's 70 rows (SHIP 3, SOUND_ALIKE 7, WAIT 32, ALIAS 4, DROP 24). Several calls
  were reversed during the batch (the list below): `open diapason` and `organ trompette` became
  aliases (the first was a sound-alike in the plan), `organ bombarde` went from shipping to
  waiting for a footage, the 6 organs held back for an engine feature (`fairground organ`, `dance
  organ`, `orchestrion`, `panharmonicon`, `regal`, `band organ`) wait for a range first, and
  `carousel organ` was dropped
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter, chiff and release is sound design unless a source is cited in the code; the
  folder is `build/instruments/organs/`):
  - [ ] The new builds: `stopped diapason` (`STOPPED_FLUTE_LEVELS`, the flute stop's levels with
    the even harmonics silent: Audsley, a covered pipe's missing even harmonics; listen for a
    hollow, flute-like tone against `pipe organ flute`, whose second harmonic is 0.1 where this
    one's is 0.0003), `cornet organ` (five unbroken ranks, 8', 4', 2 2/3', 2' and 1 3/5', summed
    into one wave by `compound_stop_levels`, C4-C7: listen for a bright, reedy flute chorus, not
    a single pipe, and for the top notes, whose upper ranks sound as high as E9) and `organ
    clarinet` (`CLOSED_REED_LEVELS`, odd harmonics only: Encyclopedia of Organ Stops, half-length
    cylindrical resonators; listen for a hollow reed against `pipe organ reed`, whose second
    harmonic is 0.75 where this one's is 0)
  - [ ] The sound-alikes beside their parents (each sounds as its parent does, except `bourdon`):
    `bourdon` (of `stopped diapason`, at 16': an octave below it, on the pedal keys C2-G4, so it
    sounds C1-G3), `salicional` and `voix celeste` (of `pipe organ string`), `organ oboe`, `organ
    tuba` and `posthorn` (of `pipe organ reed`) and `organ krummhorn` (of `organ clarinet`). The
    stops at another footage than 8' are named here: only `bourdon` (16'); the other six are 8'
  - [ ] The 4 aliases beside their parents, which are the same instrument by name: `open
    diapason` (of `pipe organ principal`), `organ trompette` (of `pipe organ reed`), `air
    calliope` and `calliaphone` (of `calliope`)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-13.tsv`; the sheet's 70 rows:
  SHIP 3, SOUND_ALIKE 7, WAIT 32, ALIAS 4, DROP 24):
  - [ ] Every WAIT (32 rows), by reason:
    - 14 for a sourced range: `band organ`, `chamber organ`, `dance organ`, `fairground organ`,
      `flute clock`, `hydraulis`, `orchestrion`, `panharmonicon`, `perroquette`, `portative
      organ`, `pyrophone`, `regal`, `serinette`, `street organ`. Range first: the six held back
      for an engine limit (the fairground and dance organs, `orchestrion`, `panharmonicon`,
      `regal` and `band organ`) have no sourced range either, so they wait for one, and each
      row's notes keep its engine limit ("Engine limit, once ranged": a fairground organ's drums
      and percussion, which the spec counts as more than four sources; a regal's short
      resonators). `band organ` waits for a range directly, not for its target
    - 5 for a sourced footage: `gedeckt`, `organ bombarde`, `organ trombone`, `rohrflote`,
      `spitzflote`. The sources give the stop at several footages with none usual, or disagree
      (Audsley alone gives the bombarde at 16', against the Encyclopedia's "16', 8'"; the same
      split made the trombone wait)
    - 5 for a range above C8: `larigot` (1 1/3'), `nasard` (2 2/3' on the manual), `piccolo organ` (2'), `sesquialtera` (2 2/3' and 1 3/5') and `tierce` (1 3/5')
    - 2 for more than four sources: `organ mixture` and `scharff`, whose ranks break back across
      the compass (see the compound-stop call below: the blocker is the breaks)
    - 3 for a build of their own: `diaphonic diapason` (the diaphone's beating pallet), `kinura`
      (inharmonic partials) and `bible regal` (beating reeds in tiny pipes, not quite an inch
      long)
    - 1 for a pitch and amplitude LFO (the tremulant): `vox humana`
    - 2 because their target waits: `fire organ` (for `pyrophone`) and `bird organ` (for
      `serinette`)
    - `ORGAN_HELD_BACK` holds the 16 that wait for something other than a range (the 5 + 5 + 2 +
      3 + 1 above), every one a name no test lets into the catalog or the aliases
  - [ ] The stop-or-setting ruling: an organ stop is an entry (it is a rank or a named set of
    ranks of pipes of its own, with its own voicing, and a game asks for it by name: the catalog's
    `pipe organ` stops already are), while a registration (several stops drawn together, as `pipe
    organ plenum` already is), the tremulant, the couplers and the swell are settings, a technique
    the player applies, unless a cited source makes one part of a stop's own sound (the vox
    humana's tremulant, which is why it waits). Confirm, in particular that `pipe organ plenum`
    stays an entry
  - [ ] The footage ruling: a stop sounds at its footage against its keys (8' at the key, 16' an
    octave below, 4' an octave above, 2 2/3' a twelfth above), through `_pipe_stop`'s `footage`,
    carried by `blown`'s new `semitones` (the chiff is not moved). Footage is pitch, never timbre,
    so a footage difference alone is never a SHIP: a stop at another footage than a catalog stop
    is a sound-alike with `sound_changes={'footage': ...}` (`bourdon` is the only one). A source
    that gives a stop at several footages with none usual makes the row wait for `a sourced
    footage`, a source wait this batch added. Confirm footage as pitch, and the footage
    sound-alikes
  - [ ] The sounding span: a stop's sounding span, its keys moved by its first rank's footage,
    must lie between A0 and C8 (range ruling 8), so a 2' stop on C2-C7 sounds C4-C9 and waits for
    a range above C8, which is the one reason `larigot`, `nasard`, `piccolo organ`,
    `sesquialtera` and `tierce` wait. The question: would you relax it (a stop may sound above C8
    when its keys do not), which would ship five stops at once
  - [ ] The cornet's top ranks sound up to E9 while `piccolo organ` waits: the rules judge only
    the first rank's span (rules 4 and 6), so `cornet organ` (C4-C7 on the keys, its 2' and 1 3/5'
    ranks sounding to C9 and E9) ships and the 2' `piccolo organ` waits for the same notes. Either
    the cornet's upper ranks are above the span too, or the span is a pitch-of-the-key rule
    and the piccolo ships; this is the previous call's inconsistency
  - [ ] Compound stop against mixture: a compound stop whose ranks are all unbroken harmonics 1 to
    32 of the key is one wave (as `pipe organ plenum`'s nine drawbars are one wave), a SHIP built
    with `compound_stop_levels` (the cornet: its source calls the five ranks unbroken, "all of
    wide scale"). A mixture whose source says its ranks break back across the compass (`organ
    mixture`, `scharff`) is the spec's "large mixtures" and waits for `more than four sources`,
    but that label hides the real blocker: the breaks, the key at which each rank steps back an
    octave, which one fixed wave per entry cannot make, not the number of ranks. `compound_stop_levels`
    refuses a footage that is not 8/n (stricter than the plan). Confirm both the rule and the
    label (or a new wait name for the breaks)
  - [ ] The range ruling for organs (the owner kept the range rule strict, 2026-11-09): a stop's
    range is its keys at 8' pitch, with the stop's footage from a fetched source; the division's
    standard compass (the AGO's, from a source that calls it standard) is the stop's own range,
    unless the stop's own source states one; a keyless organ's range is its sounding notes; never
    hedged ("about", "usually", "common"), a width ("61 notes", "five octaves"), a pipe or tune
    count, a footage alone ("at 2' pitch"), note letters with no octave, a key or one pitch;
    museum, maker and organ-reference sources over an uncited Wikipedia line; nothing below A0 or
    above C8; a one-note instrument has no range; a cited Wikipedia line counts when its citation
    supports it. The stop range rule: every one-rank stop takes its keys, never a sibling's or the
    parent's, and every derived range and footage is in the sheet's `notes`: `stopped diapason`,
    `organ clarinet`, `organ oboe`, `organ krummhorn`, `organ tuba`, `posthorn`, `salicional` and
    `voix celeste` C2-C7 on the 61-note manual (the Pipe organ page, cited to the AGO's Pipe Organ
    Guide: "sixty-one notes (five octaves, from C to c⁗)", c⁗ read as C7 by the page's own
    Helmholtz notation), all at 8'; `cornet organ` C4-C7 (the Encyclopedia of Organ Stops: "usually
    from middle C upwards") with the five ranks 8' + 4' + 2 2/3' + 2' + 1 3/5';
    `bourdon` C2-G4 on the pedal at 16'. Confirm the rule and each derived range
  - [ ] `bourdon` on the pedal (C2-G4 keys, sounding C1-G3): Audsley says the 16' bourdon "most
    frequently appears, in English and American instruments of moderate dimensions, in the Pedal
    Organ" and the Encyclopedia calls it "possibly the single most common 16' pedal stop"; the
    pedal's compass is the AGO guide's "Some have 30 notes-to F above middle C; others have 32-to
    G above middle C", with low C the lowest written note (the OSI brochure's "CCC to G" is the
    same board read at 16'). The row first took the manual (C2-C7) and was ruled onto the pedal. If
    "CCC to G" is the keys, the range is an octave lower (C1-G3 keys, C0 sounding: sub-audio)
  - [ ] `posthorn` is ranged on the church console (C2-C7, the Pipe organ page's AGO line) though
    it is a theatre stop (the Encyclopedia of Organ Stops: "The English Post Horn was originally
    designed by Hope-Jones as a 16' Reed"): a theatre-compass gap, the same gap the audit left for the kinura and the diaphonic diapason
    (needing a theatre organ source). Is the church compass acceptable for it?
  - [ ] `organ clarinet`'s full-manual range (C2-C7) is borderline: Audsley says English builders
    "very frequently" make it of tenor-C form (a short compass), a competing compass, though his
    "should be carried, in all cases" to the full manual is a recommendation, not a statement of
    what is usual. The full manual stands under ruling 3; confirm or give it the tenor-C range
  - [ ] Celestes: a celeste is "an organ stop consisting of either one or two ranks of pipes
    slightly out of tune" (the Voix céleste page). One rank beats only against another stop drawn
    with it, which is a registration, a setting, so `voix celeste` is a sound-alike of `pipe organ
    string` with no change; two ranks would ship as `_pipe_stop(..., chorus_cents=...)` only with a
    sourced detune in cents, else the row waits for `a sourced detune`, the second source wait this
    batch added. No row used either: `chorus_cents` was not added. Confirm the ruling, and that
    one rank's few cents sharp is no trait
  - [ ] Organ-only parents: a stop's parent is an organ stop chosen by its family from its own
    page or an organ reference (a principal `pipe organ principal`, a flute `pipe organ flute`, a
    string `pipe organ string`, a chorus reed `pipe organ reed`), never another family's entry:
    `organ oboe` is a reed stop, not the double reed, and `organ krummhorn` is not the crumhorn
    (its parent is `organ clarinet`, a closed reed). Confirm
  - [ ] `STOPPED_FLUTE_LEVELS`, `CLOSED_REED_LEVELS` and `compound_stop_levels` (`chorus_cents`
    was not added), each with the trait its source names: `STOPPED_FLUTE_LEVELS` is `(1.0, 0.0,
    0.12, 0.0, 0.02)`, `FLUTE_STOP_LEVELS` with the even harmonics silent (Audsley, The Organ of
    the Twentieth Century, 1919: the covered pipe's missing even harmonics, "Covered pipes cannot
    give the uneven upper partial tones"); `CLOSED_REED_LEVELS` is `falling_series(count=28,
    decibels_per_octave=2.5,
    odd_only=True)` (the Encyclopedia of Organ Stops, Clarinet: cylindrical resonators of half
    length, reinforcing the odd-numbered harmonics), with a line in the process-state guard's
    `CATALOG_SERIES`; `compound_stop_levels` places each rank's levels at harmonic 8/footage and
    normalises. Every level and `chiff` is copied from the parent's table and marked sound design.
    The test `test_a_stopped_or_closed_stop_sounds_odd_harmonics` measures them (stopped
    diapason h2 0.0003, organ clarinet h2 0.0, against 0.10 and 0.75 for the open flute and reed)
  - [ ] The short-resonator trait: `kinura`, `vox humana`, `regal` and `bible regal` share it
    (Encyclopedia of Organ Stops: the kinura "of the Regal class"; Audsley: the vox humana's
    resonators of cylindrical form, covered at the top; the regal and bible regal's tiny pipes,
    "not intended to reinforce the vibrations" in EB1911), but none was built: three wait for a
    build of their own or the tremulant and the regals for a range first. Decide them together
    once one is ranged (a `SHORT_RESONATOR_LEVELS` table, or all four wait)
  - [ ] The mechanical organs: no self-playing organ shipped (each waits for a sourced range:
    `serinette`, `flute clock`, `street organ`, `fairground organ`, `dance organ`, `band organ`,
    `orchestrion`, `panharmonicon`, `perroquette`), so `Tag.MECHANICAL` is still only on the
    `music box` and `MECHANICAL_ORGAN_NAMES` is empty. A keyless organ's sources give a pipe count,
    a tune count or a footage ("ten pipes", "2' pitch") rather than notes, which ruling 5 refuses;
    a fairground organ's or orchestrion's drums and cymbals would count as more than four sources
    (the spec names the orchestrion). Confirm, and say whether a pipe count with a footage should
    ever range a keyless organ
  - [ ] The calliope ruling: `air calliope` and `calliaphone` are aliases of `calliope` (the
    Calliope page: "The air-driven calliope is sometimes called a calliaphone", the name Norman
    Baker gave it; steam and air are the same instrument blown by another gas), and no row made the
    steam's pitch drift with temperature its sound, so none waits for a pitch LFO. The catalog's
    `calliope` (C3-G5) stays, unsourced (Bugs, below)
  - [ ] `open diapason` and `organ trompette` are aliases, not sound-alikes: the Encyclopedia of
    Organ Stops lists "Open Diapason English" among the principal's names and "Trompette French"
    among the trumpet's, and neither cites a trait, so decision 8's "a true alias stays an alias"
    decides them alike. The plan had `open diapason` a sound-alike. Confirm both
  - [ ] The boundary: free-reed organs (`reed organ`, `chromelodeon`) are dropped to free reeds
    (H-S 412.132; the `orchestrelle` is the free reeds batch's); electric organs are dropped to
    electronic or electromechanical (`lowrey organ` and `baldwin organ`, H-S 53; `compton
    electrone`, H-S 52; `choralcelo`, H-S 51: piano strings vibrated by electromagnets), both
    batches done, so #70 lists each for a later pass; `hammond b3`, `telharmonium` and `vox
    continental` were already decided; the pyrophone and the hydraulis are organs, so both wait
    for a range
  - [ ] `farfisa` is dropped as a maker's name, not one instrument (the Farfisa page is the
    company's: "a manufacturer of electronics ... founded in 1946", making many models), as
    `baldwin organ` and `lowrey organ` are. If you want it, it is an electronic organ
    alias
  - [ ] `choralcelo` is dropped to electromechanical on 120years.net (Wikipedia's page is a 404):
    the site was accepted as a source in batch 6, but it is a history site, not a museum, maker or
    organ reference (the range rule's list). Confirm it as the source
  - [ ] The bible regal's Met free-reed ambiguity: the Met's two "Bible Regal" records (502605 and
    505061) are classified "Aerophone-Free Reed-harmonium", so museums give the name to later
    free-reed instruments as well as the Renaissance beating-reed regal. No single source gives
    the name to both, so `bible regal` stays its own row (waiting for a build of its own: EB1911
    sets it apart, "unpleasantly harsh tone, due to their tiny pipes, not quite an inch long";
    Edinburgh MIMEd 4331 gives "Compass 49 notes, C₂ - C₆", the one range any regal has), not an
    alias of `regal`, and `regal organ` is dropped as the audit's name for `regal`. A range from
    MIMEd would still leave the name ambiguous
  - [ ] Generic and ambiguous terms dropped: `barrel organ` (a class: its page covers street,
    chamber and church barrel organs; the page is tagged `{{original research}}`), `limonaire` (the
    generic French term for fairground organs after Gavioli, the Limonaire Frères page), `carousel
    organ` (no fetched page uses the name; reversed from a target alias of `fairground organ`, as
    `regal organ`), and `dulciana` and `gemshorn` as earlier sheets decided them (batch 11's DROP:
    also the dulcian's Italian name; batch 9's WAIT: the vessel flute, whose page says the organ
    stop is modelled on it). Already decided, so decided here: dulciana, gemshorn and
    `hydraulophone` (batch 9's WAIT, flutes: the sheet's row is DROP "Already decided")
  - [ ] One-offs and the in-production line: `componium`, `apollonicon`, `sea organ`, `beer bottle
    organ`, `bubble organ`, `uberorgan` and `sequential resonation machine` are dropped as one-off
    instruments (one maker's or artist's design not in production), `hydraulis` and `portative
    organ` are not (makers build reconstructions today, and museums hold the type). The Audsley
    quotes in the code comments are corrected from the OCR text (".A.merican" to "American",
    "naroes" to "names", "organ- builders" and "depart- ment" unhyphenated): the sheet keeps the
    scan's text, the code comments the reading
  - [ ] The module move: `organs.py` holds the family (moved unchanged from `keyboards.py`, which
    keeps the keyboards and the electromechanical instruments; the way batches 9, 11 and 12 moved
    their families), its table is `_ORGAN_BUILDS` and `ORGANS` is `_ORGAN_BUILDS +
    ORGAN_SOUND_ALIKES`, and the process-state guard's three `falling_series` lines
    (`PRINCIPAL_LEVELS`, `REED_STOP_LEVELS`, `STRING_STOP_LEVELS`) moved with the tables, with a
    fourth for `CLOSED_REED_LEVELS`. The before-and-after record of all 693 builds found `changed:
    []`
  - [ ] `ORGAN_HELD_BACK`, the guard for every non-range wait: 16 names (above), refused as a
    catalog name or an alias by a test and compared with the sheet by the code check. The plan's
    dispatch said `bible regal` only (the half B ruling); the plan's rule, the brief and the code
    check all require every wait that is not for a range, which brings in half A's 15
  - [ ] The two-half split as explicit lists (half A, the organ stops, 29 candidates; half B, the
    organs as instruments and the 6 audit alias names, 41 rows), the two sheets researched in
    parallel, and the shared files (the names file, the candidate lists and the three check
    scripts) written up front by a setup agent. Tasks 3 and 5 (the two halves' code) went to one
    implementer, since half B shipped only two aliases and held back `bible regal`. No code task
    was skipped by ruling
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    `a sourced footage` and `a sourced detune` (source waits this plan added; the first has 5 rows,
    the second none), `its own build (the diaphone's beating pallet)`, `its own build
    (inharmonic partials)`, `its own build (beating reeds in tiny pipes, not quite an inch long)`,
    `a pitch and amplitude LFO (the tremulant)`, and mixtures' breaks (under `more than four
    sources`)
- **Bugs to report** (found while building batch 13; none fixed here):
  - [ ] The 9 earlier entries carry no source comment (`combo organ` is already in #76), and no
    range or build of theirs was checked against a source beyond the entries named here. No
    fetched page contradicts `calliope`'s C3-G5 or `positive organ`'s C2-C6 (the Calliope page
    gives only counts: "25 to 67 whistles, but 32 is traditional"), and nothing contradicted
    `pipe organ plenum`'s drawbars or `theatre organ (tibia)`'s static chorus, though no source
    was fetched for either, so both stay leads
  - [ ] Wikipedia's regal page attaches a trait to all regals that its cited source gives only to
    the bible regal: the page says the resonators are "not intended to reinforce the
    vibrations", but its cited source, EB1911, says it of the bible regal's tiny pipes. The regal
    row's 5 1/2 in. pipe length (EB1911) likewise describes the organ's regal pipes, not the table
    instrument
  - [ ] The cornet's top ranks sound up to E9, over the catalog's C8 limit (see the sounding-span
    call): a check of the span on the first rank only lets a build past it
  - [ ] The audit's "UNVERIFIED" existence rows (`kinura`, `posthorn` and `diaphonic diapason`
    were marked "(existence and range) UNVERIFIED") were all confirmed from the Encyclopedia of
    Organ Stops, but none from a theatre organ source
  - [ ] A warning to understand: `pytest -W error` fails on a DeprecationWarning at import
    ("aifc was removed in Python 3.13", from the standard-aifc package that `speech_recognition`
    imports). It is third-party and present before this batch (#81 records it); a new warning in
    these runs would be a new finding
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/organs.md`, listed in #70) are a later pass
    over this family
  - [ ] Ranging the 14 range WAITs from museum, maker and organ-reference sources (MIMO, the Met
    once it answers, Edinburgh MIMEd, the Museum Speelklok, the Deutsches Musikautomaten-Museum,
    organa.it's `portative` sizes, the Edinburgh, Colonial Williamsburg and Met chamber organs
    (several sizes, none standard), Audsley's and the Encyclopedia of Organ Stops' other stops),
    each row's notes recording what was searched; `regal` (MIMEd 4331's C2-C6, "Compass 49
    notes") and the fairground organs are the best leads
  - [ ] Check the 9 earlier entries against sources (ranges, builds, `theatre organ (tibia)`'s
    static chorus and `pipe organ plenum`'s drawbars)
  - [ ] The engine changes that unblock the waits above, most rows first: the 14 range waits need
    no engine feature, the 5 footage waits need a source that fixes one footage (or the owner's
    pick of the usual one), the 5 above-C8 waits need only the span ruling relaxed, the 2 mixtures
    need breaks (a rank that steps back an octave at a note), a short-resonator build opens
    `kinura`, `vox humana`, `regal` and `bible regal`, the tremulant needs a pitch and amplitude
    LFO, and `diaphonic diapason` needs the diaphone's beating pallet
  - [ ] The sheet's cells contain stray quote characters (some cells are CSV-quoted), so read it
    with Python's csv module rather than splitting on tabs
- **Incidents and process**:
  - [ ] The Pi hook was skipped while the Pis were unreachable (the owner, 2026-11-13)
  - [ ] The syft pin is 1.57.1 on the stack (the owner's choice, batch 12's note)
  - [ ] Batch 11 was squash-merged into batch 10, and batch 12 merged batch 10's tip, batch 13's
    base is batch 12's `5cbbf882`
  - [ ] The controller's code check (`build/batch-13-code-check.py`) had a bug: its DROP and WAIT
    branch asserted that no such name was in `CATALOG` or `ALIASES`, but `vox continental` is an
    "Already decided" DROP that existed before the batch (batch 6's alias of `combo organ`) and
    must still resolve. It was fixed so a DROP whose notes begin "Already decided" and whose name
    was in the catalog before the batch must still be there, and the check prints `matches 70
    rows`
  - [ ] The two sheet halves were researched in parallel, and pushes and stacked PRs were made
    without asking (the owner, 2026-11-12, #78)
  - [ ] The reversals above (`open diapason` and `organ trompette`, `organ bombarde`, the six
    held-back organs, `carousel organ` and the cornet's comparison) each followed a review round:
    the half A sheet had one fix commit and half B one, so the sheet's own history holds the first
    readings
  - [ ] Parked minors from the reviews: the semitones test's -12 case would have passed with
    `semitones` ignored (tightened in Tasks 3 and 5, which now also assert the tone repeats at its
    expected period); `compound_stop_levels` refuses a non-harmonic footage (stricter than the
    plan); the sheet's `organ oboe` row has no Encyclopedia URL, so its comment cites Audsley
    only; `regal`'s 5 1/2 in. pipe inference and the `portative organ` and `chamber organ` rows'
    museum and maker checks (several sizes, none standard) are in their notes; the quote check
    accepts the raw Encyclopedia HTML only for passages without tags or entities (one cornet
    passage quotes `Chemin&eacute;e` verbatim); each ranged row's saved page copy holds the 800 KB
    Audsley text, in the gitignored `build/`
- **Found**: batch 13's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before the clarinets batch builds on the same catalog)

### 72. Live Pacing's Catch-Up After a Late Frame: Does the Player See It? — TODO (decision needed)
- **Description**: An open question about the live pacer (`src/glitchygames/timing.py`,
  `next_frame_deadline_ns`: a frame up to one period late is caught up by the next, so the
  average rate holds; only a frame more than a period behind re-anchors). After a late frame the
  next deadline stays on the original grid, so the next frame is very short: committed
  recordings hold a 28.63 ms frame followed by a 1.51 ms one (PaddleSlap's `rally.jsonl.gz`,
  frame 286) and a 34.02 ms frame followed by a 7.44 ms one (Brave Adventurer's
  `golden-classic.jsonl.gz`, frame 460). A 60 Hz display probably never shows a frame that
  lasts 1.5 ms (it and the next are presented within one refresh), so "the player saw it" may
  not hold. The watched replay now presents every recorded frame at 1x (rule 2 of
  `src/glitchygames/replay/viewer.py`), which assumes the live run showed each; the question is
  whether the live pacer's catch-up is right, or whether it should re-anchor after any late
  frame (or otherwise avoid the very short frame), and what that does to the average rate, the
  recorded frame times and the frame-time statistics.
- **Status**: TODO, decision needed (found 2026-10-30 while triaging why a watched replay hid a
  frame, with scripts/replay_schedule.py)
- **Priority**: Low

## Notes

- All features are currently in planning phase
- Implementation timeline will be determined based on project priorities
- Features may be refined or expanded upon during development
- This document will be updated as features are implemented or new features are added

---
*Moved into plans/ on 2026-10-18.*
