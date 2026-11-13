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

### 70. Sound Engine: Every Musical Instrument Known to Man — EVERY FAMILY BATCHED (BATCH 19 DONE)
- **Description**: Grow the instrument catalog from 431 instruments (439 in 21 families after
  batch 1, 448 in 23 after batch 2, 624 after batch 3, 658 after batch 4, 671 after batch 5, 682
  after batch 6, 684 after batch 7, 685 after batch 8, 688 after batch 9, 690 after batch 10, 692 after batch 11, 693 after batch 12, 703 after batch 13, 704 after batches 14, 15, 16, 17 and 18, 707 after batch 19) toward every instrument a game might
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
  sheets found belongs to the clarinets batch.
  Batch 14 (clarinets) is done: of its 51 sheet rows (45 candidates and 6 audit alias names) 1
  became a sound-alike (`c clarinet`, of `clarinet`, E3-C7 sounding as written: the Vienna
  Symphonic Library's "On the C clarinet this is also the range of sounding pitches"), 40 wait
  (34 for a sourced range, 2 for a sourced reed and bore, 4 because their target waits: `maui
  xaphoon`, `pocket sax` and `xaphoon de catalunya` for `xaphoon`, `argul` for `arghul`) and 10
  were dropped (SOUND_ALIKE 1, WAIT 40, DROP 10); nothing was built and no alias was added. The
  family grew from 9 to 10 entries (704 in all, 120 aliases and 197 sound-alikes). `clarinets.py`
  now holds the family (moved unchanged from `winds.py`, which keeps the saxophones and free
  reeds; its table is `_CLARINET_BUILDS`, and `CLARINETS` is `_CLARINET_BUILDS +
  CLARINET_SOUND_ALIKES`) and `clarinet_sound_alikes.py` its sound-alike. The bore boundary: a
  clarinet is a single reed on a cylindrical bore (the saxophones' is a conical one), and a ranged
  row whose sources give both or neither waits for `a sourced reed and bore`, a source wait this
  batch added (the tenor and contrabass `birbyne`, whose encyclopedia gives the improved type "a
  cylindrical or a conical bore"). No drone or detuned double clarinet shipped (the double
  clarinets all wait for a sourced range), so `_drone_clarinet` and `chorus_cents` were not
  added. `CLARINET_HELD_BACK`, the guard for every wait that is not for a range or a target,
  holds 2 names (`contrabass birbyne` and `tenor birbyne`, each `a sourced reed and bore`). The
  base of the branch is `5bc859c7` (batch 13's HEAD, which merged batch 12's tip).
  Hornbostel-Sachs has no 422.221 or 422.222 (MIMO: 422.22 "Sets of reedpipes with single
  reeds", narrower only by -5 and -62), so the plan's bore split by those digits was dropped and
  the form check reads a set's bore from the quoted source's words. The audit's "Gaps you could
  not close" (`plans/data/instrument-audit/clarinets.md`: the folk pipes' ranges and timbres; Pku
  and the other names not fetched; the reclam de xeremies page possibly mixed with another; the
  pibgorn disambiguation page; MIMO, the Met, the Horniman and Grove not searched; the African,
  Ethiopian and Berber, Indigenous American, Chinese and Korean, Caucasian and Spanish
  single-reed pipes; the Clarinet family page's tail, the albisiphone and the contrabass
  clarinets in other keys) and the saxophones audit's xaphoon keys (C, B-flat, D, G) are a later
  pass over this family. The hand-offs are decided here: `tarogato`, `octavin`, `heckel clarina`
  and `heckelphone clarinet` (each a conical single reed, H-S 422.212) and `sarune etek` (a
  single reed with a conical bore, on a 2017 university journal article) are dropped to the
  saxophones, so the saxophones batch decides them; the xaphoon's alias names are decided here
  (`xaphoon` waits for a sourced range, and `maui xaphoon`, `pocket sax` and `xaphoon de
  catalunya` wait for it), so the saxophones batch must not decide them again; `sneng` stays as
  batch 10 decided it (WAIT, brass); `cifte` and `argun` are dropped (no cited page gives them as
  the arghul's name: the Arghul page gives the cifte a section of its own), the cifte as its own
  double clarinet being a lead for a later pass; no row was dropped to double reeds, free reeds
  or bagpipes for a later pass of those families (`pey pok` and `tarpa` wait for a range, their
  free reed being unsourced); and no name the sheets found belongs to the keyboards batch.
  Batch 15 (keyboards) is done: of its 70 sheet rows (52 candidates and 18 audit alias names)
  none shipped as a build of its own and none became a sound-alike, 47 wait (42 for a sourced
  range and 5 because their target waits: `pianola` and `reproducing piano` for `player piano`,
  `roller piano` for `barrel piano`, `rhombia` for `laterna`, `lautenwerck` for `lautenwerk`), 1
  became an alias (`fender rhodes` of `tine electric piano`) and 22 were dropped (SHIP 0,
  SOUND_ALIKE 0, WAIT 47, ALIAS 1, DROP 22); the family stayed at 11 entries (704 in all, 121
  aliases and 197 sound-alikes). `electromechanical.py` now holds the electromechanical
  instruments (moved unchanged from `keyboards.py`, the before-and-after record of all 704 builds
  finding `changed: []`), `keyboards.py` keeps the keyboards (its table is `_KEYBOARD_BUILDS`, and
  `KEYBOARDS` is `_KEYBOARD_BUILDS + KEYBOARD_SOUND_ALIKES`) and `keyboard_sound_alikes.py` holds
  its sound-alikes (empty). The boundary rulings: a keyboard is an acoustic instrument its keys
  sound (struck or plucked strings, struck bars, forks or glass), and a case, a layout, a tuning, a
  size, a maker or a roll is no trait, so each ranged row would be a sound-alike; the new guards
  and mechanisms are in place but nothing used them: no 16' harpsichord shipped
  (`harpsichord sixteen foot` waits for a sourced range; `_harpsichord`'s `sixteen_foot` was not
  added), no keyed idiophone (`_keyed_idiophone` was not added; the new wait name `a sourced
  partial series` is held for `dulcitone`, `typophone` and `glasschord` once ranged), and no
  mechanical keyboard (every self-playing piano waits, so `Tag.MECHANICAL` is still only on the
  `music box` and `MECHANICAL_KEYBOARD_NAMES` is empty). `KEYBOARD_HELD_BACK`, the guard for every
  wait that is not for a range or a target, holds nothing. The base of the branch is `982a66a7`
  (batch 14's HEAD). The audit's unclosed gaps (`plans/data/instrument-audit/keyboards.md`: MIMO,
  Horniman and Grove not reached; the Wikipedia category's `piganino`, `memotron`, `orpheal`,
  `arcadetar`, `claviola`, `chordboard`, `doppio borgato`, `fotdella`, `gazamba`, `guide-chant`,
  `celestaphone`, `harmoneon`, `bowed clavier` and `contemporary harpsichord`; the Vierling and
  Neo-Bechstein electric pianos, RMI Electra-piano, Baldwin electric harpsichord, Hohner Cembalet,
  Birotron, Pianet and Clavinet Duo, `arpicembalo`, `arpicordo` and `claviorganum`; Asian keyed
  idiophones; and `new-mechanical-instruments.md`'s: the Seeburg and Wurlitzer nickelodeon models,
  `chordephon`, `harmonipan`, the mechanical zithers) are a later pass over this family. The
  hand-offs are decided here: `claviharp` (batch 4's, a plucked keyboard) and `dolceola` (batch 4's,
  its strings struck from a piano keyboard) wait for a sourced range; the earlier sheets' names
  stay as they decided them (`chamberlin`, `mellotron`, `optigan`, `bulbul tarang`, `taishogoto`,
  `geigenwerk`, `viola organista`, `orchestrion` and `panharmonicon`, `rhodes celeste`, `rhodes
  piano bass` and `yamaha cp electric grand`, each DROP "Already decided" naming the earliest
  sheet); `scalatron` and `walking piano` ("an oversized synthesizer") are dropped to electronic
  and `shahi baaja` to plucked strings, for a later pass of those families; no row was dropped to
  struck strings (batch 18), harps (batch 17), free reeds (batch 16) or electromechanical; and
  the alias names are decided here, so no later batch decides `fender rhodes` (an alias), the
  player piano's names (`pianola` and `reproducing piano` wait for their target; `welte mignon`,
  `ampico`, `duo art` and `disklavier` are rows of their own, each waiting for a range), the
  barrel piano's (`roller piano` waits for its target, `rhombia` for `laterna`; `street piano` and
  `piano organ` are dropped as ambiguous names) or `muselar` (a kind of virginal, waiting for a
  sourced range) again. Batch 16 (free reeds) is done: of its 67 sheet rows (42 candidates and 25 audit alias names)
  none shipped as a build of its own and none became a sound-alike, 58 wait (43 for a sourced
  range and 15 because their target waits: `garmoshka` for `garmon`, `trikiti` and `eskusoinu
  txiki` for `trikitixa`, `peti` and `samvadini` for `indian harmonium`, `qeej` for `lusheng`,
  `kaen`, `khaen`, `kehn` and `kheng` for `khene`, `goofus` and `queenophone` for
  `couesnophone`, `keledi`, `enkulurai` and `kadedek` for `keluri`), 1 became an alias
  (`richter harmonica` of `harmonica`) and 8 were dropped (SHIP 0, SOUND_ALIKE 0, WAIT 58, ALIAS
  1, DROP 8; nothing is held back); the family stayed at 13 entries (704 in all, 122 aliases and
  197 sound-alikes). `free_reeds.py` now holds the free reeds (moved unchanged from `winds.py`,
  the before-and-after record of all 704 builds finding `changed: []`, and the process-state
  guard's listing moved with it), `winds.py` keeps only the saxophones, and
  `free_reed_sound_alikes.py` holds the family's sound-alikes (empty; `FREE_REEDS` is
  `_FREE_REED_BUILDS + FREE_REED_SOUND_ALIKES`). The boundary rulings: a free reed is a tongue
  swinging through a closely fitting slot, blown by bellows or the mouth, and a layout, a key, a
  tuning, a chord, a register or a size is no trait, so each ranged row would be a sound-alike; a
  free reed sounding a fingered pipe (`bawu`, `hulusi`) waits for `its own build (a free reed
  sounding a fingered pipe)`, a beating reed (412.12) is no free reed, and a plucked lamella
  (`jaw harp`) stays decided. The new guards and mechanisms are in place but nothing used them:
  no droned reed (`_droned_reed` was not added; the `khene` and `keluri` waits for a sourced
  drone tuning), no detune (`_mouth_reed` has no `cents`; `tremolo harmonica` would wait for a
  sourced detune once ranged), no octave reed set (`footages` was not added) and no mechanical
  free reed (`orchestrelle` waits for a sourced range, so `Tag.MECHANICAL` is still only on the
  `music box`). `FREE_REED_HELD_BACK`, the guard for every wait that is not for a range or a
  target, holds nothing. The base of the branch is `d4c1e3eb` (batch 15's tip). The audit's
  unclosed gaps (`plans/data/instrument-audit/free-reeds.md`: Grove and MIMO not searched; the
  removed names bass, baritone and treble concertina, `vocalion`, `harmoniflute`, `harmonetta`,
  `polyphonia`, `naw`, `steirische harmonika`, `schwyzerorgeli` and `hohner harmonetta`; the
  template's unresearched `orthotonophonium`, `harmoneon`, `panharmonicon`, `martinshorn`, `lap
  organ`, `querhammerfluegel` with Aeoline and `sneng`; the Aeolian-type orchestral reed organs),
  the out-of-scope names (the side-blown `sneng`, #80, a free reed (422.33) that batch 10's WAIT
  left to this family and that no audit names as a candidate; the `seraphine` and the melodeon
  organ, `organs.md`'s reed organ row; the free-reed names a page mentions in passing) are a
  later pass over this family. The hand-offs are decided here: `chromelodeon` (batch 13's
  hand-off, dropped as a one-off), `reed organ` (waits for a sourced range) and `orchestrelle`
  (waits for a sourced range); `reed organ` by the controller's ruling on batch 13's sentence in this item, "`orchestrion` and
  `reed organ` are decided here (... `reed organ` is dropped to free reeds), so the keyboards and
  free reeds batches must not decide them again": it binds `orchestrion` only, since a DROP
  naming a family is a hand-off (batch 15's `claviharp` and `dolceola`) and the sentence is a
  slip of the pen for `reed organ` (batch 13's own sentence is left as written); `orchestrion` and `panharmonicon` stay as `batch-13.tsv` decided them;
  `jaw harp` is left as `batch-1.tsv` decided it (DROP "Already decided"); each row dropped to
  organs, a beating-reed family, plucked idiophones, electromechanical or electronic stays for a
  later pass of that family (none were dropped to harps or struck strings); and the alias names
  are decided here, so no later batch decides `khaen` and its spellings (`kaen`, `kehn`, `kheng`,
  waiting for `khene`; `ken` is dropped as ambiguous), `bayan` (its own row, waiting for a
  sourced range), `melodeon` (dropped as ambiguous), `pianica` (dropped as a maker's name),
  `triola` and `accordina` (rows of their own, waiting for a sourced range), `claviola` (dropped
  as ambiguous) or `richter harmonica` (an alias) again. Batch 17 (harps) is done: of its 47 sheet rows (30 candidates and 17 audit alias names)
  none shipped as a build of its own and none became a sound-alike, 23 wait (18 for a sourced
  range: `andean harp`, `arpa jarocha`, `baroque triple harp`, `cross strung harp`, `gothic harp`,
  `llanera harp`, `paraguayan harp`, `adungu`, `ardin`, `donso ngoni`, `ennanga`, `gravikord`,
  `kamale ngoni`, `kundi`, `ngombi`, `saung gauk`, `seperewa` and `simbi`; and 5 because their
  target waits: `arpa paraguaya` for `paraguayan harp`, `arpa llanera` for `llanera harp`, `saung`
  for `saung gauk`, `ombi` for `ngombi` and `kamele ngoni` for `kamale ngoni`), 3 became aliases
  (`pedal harp` of `concert harp`, `lever harp` and `folk harp` of `celtic harp`) and 21 were
  dropped (SHIP 0, SOUND_ALIKE 0, WAIT 23, ALIAS 3, DROP 21; nothing is held back); the family
  stayed at 7 entries (704 in all, 125 aliases and 197 sound-alikes).
  `harps.py` now holds the harps (moved unchanged from `strings.py`, the before-and-after record
  of all 704 builds finding `changed: []`), `strings.py` keeps only the struck strings
  (`STRUCK_STRINGS`), and `harp_sound_alikes.py` holds the family's sound-alikes (empty; `HARPS`
  is `_HARP_BUILDS + HARP_SOUND_ALIKES`). The boundary rulings: a harp's strings run
  perpendicular to its soundboard (Hornbostel-Sachs 322) and a harp-lute's at right angles to it
  across a notched bridge (323), and a string count, rows, a tuning action, a tuning, a material, a
  size or a body is no trait, so each ranged row would be a sound-alike; harp-lutes are decided
  here (batch 4's hand-off, and the catalog's `kora`), while the lyre (321.2) stays with the
  plucked strings' decisions and the catalog's `lyre` and `harp guitar` stay unchanged and are
  never a parent unless a row's source names them (#74). `HARP_HELD_BACK`, the guard for every
  wait that is not for a range or a target, holds nothing, and no harp carries `sound_changes`.
  The base of the branch is `1ecc25d9` (batch 16's tip). The audit's unclosed gaps (the konghou
  subtypes `wo`, `shu` and `feng shou konghou`, `sogonghu`, `sugonghu`, `wagonghu`, `kudaragoto`
  and `kugo`; the Pokot harp, Bagirmi, the Kotoko galdyama trio, the Tibetan and Ottoman harps
  (`cenk`); the harp guitar variants Dyer Style 8, Gibson Style U, Knutsen and contraguitar) and
  the out-of-scope names (`yazh` and `yaal`, `vajra`, `kafir harp`, `padhar harp`, `bolon`,
  `kinnor`, `hook harp`, `dital harp`, `electric harp`, `double harp` and `arpa doppia`,
  `gonggu`, and the harp names a page mentions in passing) are a later pass over this family. The hand-offs are decided
  here: `donso ngoni` and `kamele ngoni` (batch 4's DROPs to harps: the first waits for a sourced
  range, the second for its target `kamale ngoni`); the seven already-decided rows are left as
  `batch-4.tsv` decided them (`aeolian harp`, `partch kithara`, `sasando`, `swarmandal`, `begena`,
  `krar` and `nyatiti`, each DROP "Already decided" naming that sheet); `chang` is decided here
  once, as an ambiguous name (a Persian angular harp, the Uyghur and Uzbek dulcimers and an Afghan
  jew's harp), so the struck strings batch treats the name as already decided: DROP; each row
  dropped to plucked strings, keyboards or another family stays for a later pass of that family
  (none were dropped to struck strings or keyboards); and the alias names are decided here, so no
  later batch decides `pedal harp`, `lever harp`, `folk harp`, `clarsach` (dropped as ambiguous),
  `telyn` (dropped as a generic term), `wind harp` (dropped with its target `aeolian harp`) or
  `harp lute` (dropped as an ambiguous name) again. Batch 18 (struck strings) is done: of its 67 sheet rows
  (20 candidates and 47 audit alias names) none shipped as a build of its own and none became a
  sound-alike, 27 wait (17 for a sourced range: `khim`, `yanggeum`, `yoochin`, `yangzi`, `rgyud
  mang`, `dan tam thap luc`, `santouri`, `hudie qin`, `ground bow`, `malunga`, `quijongo`, `tambourin a cordes`, `utogardon`,
  `mbulumbumba`, `gunga`, `medio` and `violinha`; and 10 because their target waits: `ttun ttun`,
  `salmo`, `chicoten` and `toum toum` for `tambourin a cordes`, `galinga`, `gayumba`,
  `tumbandera`, `tingo talango` and `angbindi` for `ground bow`, and `berra boi` for `gunga`), 13
  became aliases (`hackbrett`, `dulcemele`, `dultzimar`, `darushimaa`, `hakkebord`, `hakkebraet`,
  `hakkebrett`, `hackbraede`, `hammarharpa`, `oprekelj`, `cimbale`, `cymbaly` and `chimbaly`, all
  of `hammered dulcimer`) and 27 were dropped (SHIP 0, SOUND_ALIKE 0, WAIT 27, ALIAS 13, DROP 27;
  nothing is held back); the family stayed at 5 entries (704 in all, 138 aliases and 197
  sound-alikes). The module move: `strings.py` is now
  `struck_strings.py` (renamed with `git mv`; `strings.py` is gone and nothing re-exports it; every
  other family module is named for its family, which answers #87's question), the before-and-after
  record of all 704 builds finding `changed: []`, and `struck_sound_alikes.py` holds the family's
  sound-alikes (empty; `STRUCK_STRINGS` is `_STRUCK_BUILDS + STRUCK_SOUND_ALIKES`). The boundary
  rulings: a struck string is sounded by a beater in the player's hand (Hornbostel-Sachs suffix 4:
  the hammered dulcimers, 314.122-4, and the struck bows, 311.12), the cimbalom is a dulcimer, a
  keyed or pedal-driven struck string is a keyboard (`fotdella`, `marxophone`) and a plucked
  zither a plucked string, and a string or course count, bridges, a tuning, a material, the
  beaters, a size or a body is no trait, so each ranged row would be a sound-alike. The versions
  ruling moved rows, by sub-list of the Hammered dulcimer page's "Adaptations" list: `yoochin`,
  `yangzi` and `rgyud mang` went from ALIAS to WAIT (the Sinosphere sub-list describes an
  instrument spreading, so its names are versions, as `yanggeum` and `khim` are). The cimbalom
  sub-list's heading is etymology, like the Graeco-Roman and Germanic ones, so its names are
  names: `cimbale`, `oprekelj` and `chimbaly` stayed aliases, `cymbaly` (de:Zymbal calls it
  «Hackbretter») became one, and `tsimbl` and `tambal` (each also redirects to Cimbalom) were
  dropped as ambiguous; `urucungo` and `madimba lungungu` were dropped as generic terms. `STRUCK_HELD_BACK`, the guard for every wait that is not for a
  range or a target, holds nothing (no name), and no struck string carries `sound_changes`. The
  base of the branch is `9a8dcfbe` (batch 17's tip). The audit's unclosed gaps (Hawaiian and
  African struck zithers; the Salzburg hackbrett's 128 strings; the pantaleon's 276; the Uyghur
  chang's courses; MIMO, the Met and the Horniman's 314.122-4 page; and "Not checked: claviharp,
  harp-piano, zither-banjo, tangent piano, orphica, schlagzither, tsimbl/Yiddish vs Romanian
  tambal differences, high/alto/bass yangqin sizes") and the out-of-scope names (`gopichand`,
  `cello col legno`, `luthéal`, `butterfly dulcimer`, `caxixi`, and the struck-string names a page
  mentions in passing) are a later pass over this family. The hand-offs are decided here:
  `fotdella` (batch 4's DROP, sent to keyboards: pedal hammers), `nondo` (dropped: no fetched
  source describes it) and `quijongo` (waits for a sourced range) are batch 4's DROPs; `celestaphone`
  (dropped as an ambiguous name) and `pianoharp` (dropped: no fetched source describes it) are
  `missing-categories.md`'s; the three already-decided rows are left as their sheets decided them
  (`chang`, `dolceola` and `harmonic canon`); each row dropped to keyboards (`fotdella`,
  `marxophone`) stays for a later pass of that family (none were dropped to plucked strings or
  another family); and the alias names are decided here, so no later batch decides the dulcimer
  and cimbalom names (`hackbrett` and its eight kin as aliases; `cimbal`, `cimbule`, `zymbal`,
  `santoor` and `salterio` dropped as ambiguous, `tsymbaly` as generic; `tambal`), `tympanon`,
  the tambourin's names (`ttun ttun`, `salmo`, `chicoten`, `toum toum`), the berimbau's (`urucungo`
  and `madimba lungungu`, dropped as generic; `gunga`, `medio`, `violinha` and `berra boi` as its
  categories) or the ground bow's (`galinga`, `gayumba`, `tumbandera`, `tingo talango`,
  `angbindi`; `kalinga` dropped as ambiguous), or the berimbau's sizes again.
  Batch 19 (saxophones) is done: of its 28 sheet rows (21 candidates and 7 audit alias names)
  none shipped as a build of its own, 3 became sound-alikes (`soprillo saxophone`, of `sopranino saxophone`, Ab4-Db7, and `tubax in eb`, of `contrabass saxophone`,
  Db1-A3, each from Eppelsheim's own page; `heckelphone clarinet`, of `alto saxophone`, D3-C6, from
  the Heckelphone-clarinet page's line cited to Marcuse), 16 wait (15 for a sourced range:
  `aulochrome`, `c soprano saxophone`, `conn o sax`, `contralto saxophone`, `f mezzo soprano
  saxophone`, `g mezzo soprano saxophone`, `grafton alto saxophone`, `saxello`, `slide saxophone`,
  `subcontrabass saxophone`, `tubax`, `curved soprano saxophone`, `heckel clarina`, `octavin` and
  `sarune etek`; and 1 for sub-audio fundamentals: `bb tubax`), 2 became aliases (`soprillo` and
  `sopranissimo saxophone`, of `soprillo saxophone`) and 7 were dropped (SHIP 0, SOUND_ALIKE 3,
  WAIT 16, ALIAS 2, DROP 7); the family grew from 8 to 11 entries (707 in all, 140 aliases and 200
  sound-alikes). The module move: `winds.py` is now `saxophones.py` (renamed with `git mv`;
  `winds.py` is gone and nothing re-exports it), the before-and-after record of all 704 builds
  finding `changed: []`, and `saxophone_sound_alikes.py` holds the family's sound-alikes
  (`SAXOPHONES` is `_SAXOPHONE_BUILDS + SAXOPHONE_SOUND_ALIKES`), so every family module is now
  named for its family. The boundary rulings: a saxophone is a single reed on a conical bore
  (Hornbostel-Sachs 422.212), while a cylindrical one is a clarinet (batch 14's boundary); the
  saxophone pages' 422.212-71 is the default of `Template:Infobox saxophone`, so it is no evidence
  of a row's bore by itself; a key, a size, a shape, a material, keywork, a maker or a colour word
  is no trait, so each ranged row is a sound-alike unless its source gives it two pipes, a slide
  that replaces the keys, or a bore or bell it says changes the sound (each waits for a build of
  its own once ranged: `aulochrome`, `slide saxophone`, `conn o sax`, `contralto saxophone`, and
  the leads in `heckel clarina` and `sarune etek`); a range below A0 waits for sub-audio
  fundamentals. `SAXOPHONE_HELD_BACK`, the guard for every wait that is not for a range or a
  target, holds `bb tubax` (the maker's sounding Ab0-E3); `subcontrabass saxophone` waits for a
  sourced range first (its makers' models disagree, and no source calls one standard), and no
  saxophone carries `sound_changes`. The base of the branch is `6503a1e1` (batch 18's tip). The
  audit's unclosed gaps (`plans/data/instrument-audit/saxophones.md`: the Met article on the
  Conn-O-Sax and rare saxophones; MIMO and the Horniman browsed; Eppelsheim's C tubax and other
  models; the Saxophone page past its first 100,000 characters; Adolphe Sax's patent list of
  sizes, the C bass saxophone, the Buescher and Conn C basses, the vibrato sax and the Selmer
  Varitone) and the out-of-scope names (`piccolo saxophone` on the Soprillo page, the F baritone
  prototypes, the Keilwerth and L.A. Sax straight altos and tenors, and the xaphoon's keys, #84's
  later clarinets pass) are a later pass over this family; the rothphone and `saxorusofono` (a
  double reed with saxophone keywork) are a later double reeds pass's, and so is the historical
  double-reed tárogató, which `batch-14.tsv` calls «batch 11's hand-off» though no sheet has a row
  for it. The hand-offs are decided here: `tarogato` (dropped as an ambiguous name: the page gives
  it to the modern single reed and the historical double reed; a later pass may add `modern
  tarogato`), `octavin`, `heckel clarina` and `sarune etek` (each waits for a sourced range) and
  `heckelphone clarinet` (a sound-alike), batch 14's DROPs; the four xaphoon rows are left as
  `batch-14.tsv` decided them (`xaphoon` waits for a sourced range, and `maui xaphoon`, `pocket
  sax` and `xaphoon de catalunya` wait for it, each DROP "Already decided" here); each row dropped
  to clarinets, double reeds, free reeds, brass or electronic stays for a later pass of that family
  (this batch dropped none to another family; `saxonette` and `venova`, clarinets, the saxhorns,
  `saxotromba` and `jazzophone`, brass, the sarrusophones and `rothphone`, double reeds, `sneng`,
  `couesnophone`, `goofus` and `queenophone`, free reeds, and `ewi` and `lyricon`, electronic, were
  decided by their own batches and have no row here); and the alias names are decided here, so no
  later batch decides `stritch` or `manzello` (dropped as a player's names), `tubax in eb` (a
  sound-alike), `curved soprano saxophone` (a version, waiting for a sourced range) or
  `sopranissimo saxophone` (an alias) again.
  **The expansion's close.** Every family the audits cover has had its batch. The final audit
  (`build/batch-19-final-audit.py`, untracked, run over all 19 sheets against the code on
  2026-11-13) printed `bad: []`: every standing decision agrees with the catalog and its aliases.
  - The catalog grew from 431 instruments in 18 families to 707 in 23 (140 aliases, 200
    sound-alikes).
  - The standing decision of every name across the 19 sheets (2042 names; a name decided again
    by a later sheet counts once, under its standing status): SHIP 76, SOUND_ALIKE 200, MOVE 14,
    ALIAS 140, WAIT 1236, DROP 376. The SOUND_ALIKE and ALIAS counts equal the catalog's. A later
    row replaces an earlier one, except a DROP whose notes begin "Already decided" and a DROP of a
    name an earlier sheet shipped (SHIP, SOUND_ALIKE or ALIAS), which keep the earlier status
    standing: the catalog holds the name, so a later sheet's DROP of it as a candidate does not
    undo the shipping (batch 19's final review; the first run, which let those DROPs replace the
    SHIPs, printed SHIP 73 and DROP 379). The cross-check: 76 SHIP + 200 SOUND_ALIKE = 276 entries
    the sheets shipped, and 707 - 276 = 431, the catalog's pre-expansion entries (every catalog
    entry no sheet shipped; the MOVE rows are pre-expansion entries moved between families)
  - The WAIT rows by reason (goal 4's "which instruments the engine cannot make yet, and what
    engine feature each needs"):
    - a sourced range: 873
    - its target (a row waiting for the row its `alias_of` names): 170
    - every other reason, 193 rows under 73 reasons, each as the audit prints it (the sheets'
      `waits_for` words):
      - FM synthesis (3): `dx7 bass`, `dx7 ep`, `ym2612`
      - FM synthesis and wavefolding (2): `buchla 100`, `buchla music easel`
      - LFSR tap sets other than maximal-length (the 93-step mode) (1): `nes short noise`
      - LFSR tap sets other than maximal-length, and a 16-stage width (1): `sn76489 noise`
      - LFSR widths other than 15 and 7 (4): `atari tia`, `ay 3 8910 noise`, `pokey`, `sid noise`
      - a buzzer (bottle caps on the soundboard); a sourced range (1): `mbira dzavadzimu`
      - a buzzing bridge (3): `begena`, `jakhe`, `tromba marina`
      - a buzzing membrane (6): `bangdi`, `daegeum`, `kazoo`, `qudi`, `sudrophone`, `swazzle`
      - a buzzing membrane whose buzz is the identifying sound (spider-silk mirlitons), and a
        sourced range (1): `gyil`
      - a buzzing resonator wire (1): `yueqin`
      - a chorus's moving delay (2): `arp string ensemble`, `juno 106`
      - a fetchable source; then moving formants (the mouth cavity sweeps the overtones) (1):
        `susap`
      - a filter LFO (the water in constant motion moves the resonance) (1): `water drum`
      - a filter envelope (a cutoff that moves during a note) and filter resonance (2): `sh 101`,
        `tb 303`
      - a fixed noise clock (the engine scales an all-noise instrument's LFSR clock by pitch ÷ 440)
        (2): `game boy short noise`, `nes noise`
      - a jawari bridge (1): `rudra veena`
      - a jawari bridge (the buzz bridge) (1): `electric sitar`
      - a moving filter or pitch LFO (the pitch and loudness follow the changing crank speed) (1):
        `wind machine`
      - a pitch LFO (portamento between notes) (4): `clavivox`, `singing bird box`, `slide whistle`,
        `whistling vessel`
      - a pitch LFO (the flexing board's whoop-whoop: its tone rises and falls with each bounce)
        (1): `wobble board`
      - a pitch LFO (the spin speeds and slows with each pull) (1): `button whirligig`
      - a pitch LFO (vibrato) (5): `bird whistle`, `byrlang`, `clavioline`, `pea whistle`, `water
        whistle`
      - a pitch and amplitude LFO (the Leslie rotating speaker and the scanner vibrato) (1):
        `hammond b3`
      - a pitch and amplitude LFO (the tremulant) (1): `vox humana`
      - a pitch curve that rises and falls (a pitch LFO); one glide per tone only (3): `fog siren`,
        `hand cranked siren`, `siren`
      - a pitch curve that rises and falls (the 'awooga'); one glide per tone only (1): `klaxon`
      - a pitch moving through a phrase (8): `dan bau`, `diddley bow`, `gopichand`, `guqin`,
        `ichigenkin`, `khamak`, `vong co guitar`, `washtub bass`
      - a pitch the sequence moves through a phrase (the squeezed cords) (2): `kotsuzumi`, `talking
        drum`
      - a pitch the sequence moves through a phrase (the squeezed lacing) (1): `idakka`
      - a pitch the sequence moves through a phrase (the squeezed strap) (1): `udukku`
      - a range above C8 (5): `larigot`, `nasard`, `piccolo organ`, `sesquialtera`, `tierce`
      - a sourced description and a sourced range (3): `clavicylinder`, `cricri`, `triolin`
      - a sourced drone tuning (10): `algoza`, `aulos`, `crwth`, `gudok`, `jouhikko`, `lalingedan`,
        `langspil`, `moraharpa`, `organistrum`, `sarangi nepali`
      - a sourced footage (5): `gedeckt`, `organ bombarde`, `organ trombone`, `rohrflote`,
        `spitzflote`
      - a sourced reed and bore (2): `contrabass birbyne`, `tenor birbyne`
      - a sourced sound description (the swish is unsourced; it would need a moving filter) (1):
        `swordblade`
      - an amplitude LFO (its separate impacts) (1): `thunder run`
      - an amplitude LFO (many irregular pops over one note) (1): `fire crackle`
      - an amplitude LFO (repeated strikes of tuned bells as a star turns); a sourced range (1):
        `zimbelstern`
      - an amplitude LFO (repeated strikes: the shaken note) (1): `angklung`
      - an amplitude LFO (the beaters' tremolo) and a pitch the player bends through the note (1):
        `flexatone`
      - an amplitude LFO (the board clicking against each tooth of the turning gearwheel: a run of
        separate clicks) (1): `ratchet`
      - an amplitude LFO (the rhythmic wingbeat hum) (1): `warada`
      - an amplitude LFO (the roar of the resined cord rubbed by a sliding hand) (1): `lions roar`
      - an amplitude LFO (the roaring vibrato from the slat turning on its axis) (1): `bullroarer`
      - an amplitude LFO (the run of slats striking as the wave moves through the stack) (1):
        `binzasara`
      - an amplitude LFO (the sawtooth envelope) (1): `electronic clap`
      - an amplitude LFO (the strikers beating the heads in turn) (1): `damaru`
      - an amplitude LFO with a stepped pitch (many strikes in a run, each a chime tube) (1): `wind
        chimes`
      - an amplitude LFO with a stepped pitch (the glissando: 14 to 28 bowls struck one after
        another) (1): `bell tree`
      - an amplitude LFO with a stepped pitch (the glissando: a finger swept through the chimes,
        each struck one after another) (1): `mark tree`
      - filter resonance (4): `minimoog`, `moog modular synthesizer`, `trautonium`, `volks
        trautonium`
      - filter resonance, ring modulation and oscillator hard sync (1): `sid voice`
      - its own build (8): `aztec death whistle`, `castrato ah`, `duck call`, `fulani flute`,
        `porutu`, `putorino`, `tenor cornett`, `vienna horn`
      - its own build (a bowed wheel without a buzzing bridge) (1): `viola organista`
      - its own build (a cylindrical bore) (1): `balaban`
      - its own build (beating reeds in tiny pipes, not quite an inch long) (1): `bible regal`
      - its own build (inharmonic partials) (1): `kinura`
      - its own build (rule 7: a bamboo body and a tone raspier than the violin, unlike the erhu)
        (1): `jinghu`
      - its own build (the diaphone's beating pallet) (1): `diaphonic diapason`
      - more than four sources (7): `electronic closed hi hat`, `electronic open hi hat`, `organ
        mixture`, `phonoliszt violina`, `pigeon whistle`, `scharff`, `violano virtuoso`
      - more than four sources (the K5LA's five bells) (1): `train horn`
      - moving formants (22): `bazooka`, `borbangnadyr`, `chylandyk`, `didjeribone`, `dumchuktaar`,
        `electrolarynx`, `ezengileer`, `kargyraa`, `katajjaq`, `khoomei`, `otamatone`, `rekuhkara`,
        `speak and spell`, `sygyt`, `tibetan chant`, `tsuur`, `tuvan ensemble`, `ukeke`,
        `umngqokolo`, `umrhubhe`, `votrax`, `yodel`
      - moving formants (the mouth cavity sweeps the overtones) (9): `angkuoch`, `binayo`, `datok`,
        `genggong`, `isitolotolo`, `jaw harp set`, `lubuw`, `pikon`, `temir komuz`
      - moving formants (voice-like timbres) (1): `daxophone`
      - phase distortion (1): `casio cz`
      - sample playback (5): `d 50 la synth`, `electronic cymbal`, `linn lm1`, `mellotron`, `nes
        dpcm`
      - sample playback and a sourced range (4): `chamberlin`, `optigan`, `vako orchestron`, `welte
        lichttonorgel`
      - sub-audio fundamentals (5): `bb tubax`, `hyperbass flute`, `long string instrument`,
        `octobass`, `subcontrabass tuba`
      - sympathetic strings (11): `baryton`, `dilruba`, `gadulka`, `gottuvadhyam`, `kamaicha`,
        `mohan veena`, `sarinda`, `surbahar`, `taus`, `ten string guitar`, `vichitra veena`
      - sympathetic strings and a buzzing bridge (1): `esraj`
      - tones that alternate within one note (a gated LFO) (1): `martinshorn`
      - wavetable morphing (2): `ppg wave`, `prophet vs`
  - The open hand-offs, by the audit's keyword heuristic (a DROP whose notes send the row to another
    family whose batch has passed; a heuristic list, not a count, and some rows on it name another
    family only in passing), each for a later pass of that family: `morsing`, `morchang`,
    `kubing`, `karinding`, `mukkuri`, `kouxian`, `gogona`, `intonarumori` and `chip noise` (batch
    3), `glass violin` (batch 1), `corrugahorn` (batch 10), `wurlitzer sideman`, `gunshot`, `snow
    crunch` and `bone crack` (batch 2), `drum machine voices`, `rhythmicon`, `wurlitzer side man`
    and `cracklebox` (batch 6), `fotdella`, `nondo` and `marxophone` (batch 18), `gameleste`,
    `stamenphone` and `tubulum` (batch 5), `beatbox hihat` (batch 8), `clackamore` (batch 9),
    `pommer` and `selompret` (batch 11), `electronic bagpipe` (batch 12), `baldwin organ`,
    `choralcelo`, `compton electrone`, `farfisa` and `lowrey organ` (batch 13), `chromelodeon`
    (batch 16), `walking piano`, `scalatron` and `shahi baaja` (batch 15), `harp lute` (batch 17)
    and `tarogato` (batch 19, whose historical double reed is the double reeds')
  - The standing DROPs the code holds, for review: 5 names whose standing sheet row is DROP while
    the catalog holds an entry of that name, each a pre-expansion entry. Each row drops the name as
    a candidate because the catalog already had it, so the code is not contradicted: `vibraslap`
    (`batch-2.tsv`: «Already in the catalog (drums and percussion)»), `cuica` (`batch-2.tsv`: the
    same), `whip` (`batch-2.tsv`: the same, «the slapstick is its alias»), `singing bowl`
    (`batch-5.tsv`: «Already decided (rule 5): the catalog has `singing bowl`») and `sackbut`
    (`batch-6.tsv`: the catalog's brass `sackbut` is a different instrument from Le Caine's
    electronic sackbut, so the audit's alias line was dropped)
  - Three names the expansion's own sheets shipped and a later sheet re-listed and dropped (the
    first run of the audit counted them as standing DROPs; their standing status is SHIP):
    - `whip crack`: SHIP in `batch-1.tsv` (line 60, noise makers); DROP in `batch-2.tsv` (line 63,
      sound effects): «Already in the catalog in noise makers (the noise makers row above is its
      entry): a bullwhip crack, not a theatre or Foley device of this family, so not a move.»
    - `thunder sheet`: SHIP in `batch-2.tsv` (line 32, sound effects); DROP in `batch-3.tsv` (line
      225, drums and percussion): «Already shipped in sound effects (rule 4): the catalog thunder
      sheet (sound_effects.py; batch-2.tsv SHIP).»
    - `ocean drum`: SHIP in `batch-2.tsv` (line 40, sound effects); DROP in `batch-3.tsv` (line 75,
      drums and percussion): «Already shipped elsewhere: the catalog ocean drum is in the sound
      effects family (batch 2).»
  - The engine features the WAIT reasons above name (every batch, 1 to 19, gathered from the final
    audit's reasons and deduplicated; a row whose reason names two features counts under each),
    for the owner to rule into the spec's "What the engine cannot make yet". Absent from the
    spec's table, each with its standing WAIT rows:
    - an amplitude LFO (15): `angklung`, `bell tree`, `binzasara`, `bullroarer`, `damaru`,
      `electronic clap`, `fire crackle`, `flexatone`, `lions roar`, `mark tree`, `ratchet`,
      `thunder run`, `warada`, `wind chimes`, `zimbelstern`; 3 of them (`bell tree`, `mark tree`,
      `wind chimes`) also need a stepped pitch
    - a pitch moving through a phrase (8): `dan bau`, `diddley bow`, `gopichand`, `guqin`,
      `ichigenkin`, `khamak`, `vong co guitar`, `washtub bass`
    - a pitch the sequence moves through a phrase, a squeezed drum (4): `idakka`, `kotsuzumi`,
      `talking drum`, `udukku`
    - a buzzing membrane (7): `bangdi`, `daegeum`, `gyil`, `kazoo`, `qudi`, `sudrophone`, `swazzle`
    - filter resonance (7): `minimoog`, `moog modular synthesizer`, `sh 101`, `sid voice`, `tb 303`,
      `trautonium`, `volks trautonium`
    - a pitch LFO other than vibrato (6): portamento between notes (4: `clavivox`, `singing bird
      box`, `slide whistle`, `whistling vessel`), a bounce's rise and fall (`wobble board`) and a
      spin's speeding and slowing (`button whirligig`)
    - a pitch curve that rises and falls, more than one glide per tone (4): `fog siren`, `hand
      cranked siren`, `klaxon`, `siren`
    - LFSR widths other than 15 and 7 (5): `atari tia`, `ay 3 8910 noise`, `pokey`, `sid noise`,
      `sn76489 noise` (a 16-stage width)
    - a range above C8 (5): `larigot`, `nasard`, `piccolo organ`, `sesquialtera`, `tierce`
    - LFSR tap sets other than maximal-length (2): `nes short noise`, `sn76489 noise`
    - a fixed noise clock (2): `game boy short noise`, `nes noise`
    - a filter envelope (2): `sh 101`, `tb 303`
    - a pitch and amplitude LFO (2): `hammond b3` (the Leslie and the scanner vibrato), `vox humana`
      (the tremulant)
    - a chorus's moving delay (2): `arp string ensemble`, `juno 106`
    - wavefolding (2): `buchla 100`, `buchla music easel`
    - wavetable morphing (2): `ppg wave`, `prophet vs`
    - a filter LFO (1): `water drum`
    - a moving filter or pitch LFO (1): `wind machine`
    - a gated LFO, tones that alternate within one note (1): `martinshorn`
    - a pitch the player bends through the note (1): `flexatone`
    - ring modulation (1) and oscillator hard sync (1): `sid voice`
    - phase distortion (1): `casio cz`
    - a buzzing resonator wire (1): `yueqin`
    - a buzzer, bottle caps on the soundboard (1): `mbira dzavadzimu`
    - Already in the spec's table: sympathetic strings (12 rows), a buzzing bridge or jawari (6),
      moving formants (33), vibrato (5), FM synthesis (5), sample playback (9), more than four
      sources (8) and sub-audio fundamentals (5)
    - `its own build` (14 rows) is a catalog build, not an engine feature; its rows' traits are a
      bowed wheel without a buzzing bridge, a cylindrical bore, beating reeds in tiny pipes,
      inharmonic partials, a bamboo body and the diaphone's beating pallet. The source waits (a
      sourced description, drone tuning, footage, reed and bore, or sound description, and a
      fetchable source) are sources, not engine features
    - #76 to #89 also named features that no standing WAIT reason names (their rows wait for a
      sourced range or another reason first): a pitch glide through a note, a detuned double
      chanter, mixtures' breaks, a branched pipe, a free reed sounding a fingered pipe, a spectrum
      that changes with the note, a second detuned reed set, a string buzzing against a bray pin,
      rattles on the instrument, a drummed resonator, a hammer that bounces and restrikes while
      held, a drone chord, and, from batch 19, two pipes sounding together (`aulochrome`), a bell
      that changes the tone (`contralto saxophone`, `conn o sax`, `sarune etek`) and a timbre that
      changes by register (`heckel clarina`)
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
- **Plan (batch 14)**: `plans/2026-11-12-instrument-catalog-batch-14-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-14.tsv`
- **Plan (batch 15)**: `plans/2026-11-12-instrument-catalog-batch-15-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-15.tsv`
- **Plan (batch 16)**: `plans/2026-11-12-instrument-catalog-batch-16-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-16.tsv`
- **Plan (batch 17)**: `plans/2026-11-12-instrument-catalog-batch-17-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-17.tsv`
- **Plan (batch 18)**: `plans/2026-11-12-instrument-catalog-batch-18-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-18.tsv`
- **Plan (batch 19)**: `plans/2026-11-12-instrument-catalog-batch-19-implementation.md`; audit
  sheet `plans/data/instrument-audit/batch-19.tsv`
- **Status**: Batches 1 to 19 done; every family the audits cover has had its batch (requested by
  the owner 2026-11-06). Open: the later passes listed above, and the owner's checks #71 to #89.
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

### 84. Sound Engine: The Owner's Checks on Instrument Catalog Batch 14 — TODO
- **Goal**: confirm or overturn the calls made while batch 14 of #70 ran, and listen to its one
  new instrument (clarinets 9 to 10 entries). Nothing was built, no alias was added, 1
  sound-alike (`c clarinet`), 40 waits and 10 drops in the sheet's 51 rows (SHIP 0,
  SOUND_ALIKE 1, WAIT 40, ALIAS 0, DROP 10). Two rows were reversed during the batch (the list
  below): `d clarinet` went from a sound-alike to a wait, and `xaphoon` from ranged to a wait
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter and release is sound design unless a source is cited in the code; the folder is
  `build/instruments/clarinets/`):
  - [ ] The new builds: none (no row shipped; no drone or detuned build, so `_drone_clarinet` and
    `chorus_cents` were not added, and there is no droned build to compare with the catalog
    clarinet its values would have been copied from)
  - [ ] The sound-alike beside its parent (it sounds as its parent does): `c clarinet` (of
    `clarinet`, E3-C7 sounding as written, against the parent's D3-Bb6)
  - [ ] The aliases: none shipped
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-14.tsv`; the sheet's 51 rows:
  SHIP 0, SOUND_ALIKE 1, WAIT 40, ALIAS 0, DROP 10):
  - [ ] Every WAIT (40 rows), by reason:
    - 34 for a sourced range: `b natural clarinet`, `basset clarinet`, `birbyne`, `bohlen pierce
      clarinet`, `clarinet d amore`, `d clarinet`, `low g clarinet`, `mock trumpet`,
      `octocontrabass clarinet`, `piccolo clarinet`, `saxonette`, `venova`, `xaphoon`, `alboka`,
      `arghul`, `bulban`, `dilli tuiduk`, `diplica`, `dozaleh`, `ganurags`, `launeddas`, `mijwiz`, `pepa`,
      `pey pok`, `pibgorn`, `pilili`, `pungi`, `reclam de xeremies`, `sipsi`, `stock and horn`,
      `tarpa`, `toleat`, `zhaleika` and `zummara`. Range first: a row's notes keep its next
      blocker once ranged (`octocontrabass clarinet`: sub-audio fundamentals; `venova`: its own
      build, a branched pipe; `xaphoon`: a sourced reed and bore; `mijwiz`: a sourced detune; the
      double clarinets `arghul`, `launeddas`, `diplica` and `pungi`: their drones' tuning; `pilili`:
      a sourced reed and bore)
    - 2 for a sourced reed and bore: `tenor birbyne` and `contrabass birbyne`
    - 4 because their target waits: `maui xaphoon`, `pocket sax` and `xaphoon de catalunya` (for
      `xaphoon`) and `argul` (for `arghul`)
  - [ ] The bore boundary: a cylindrical single reed is this family's, a conical one the
    saxophones' (Hornbostel-Sachs 422.211 against 422.212), a double reed, a free reed or a bag
    another family's. Each row it moved: `tarogato`, `octavin`, `heckel clarina`, `heckelphone
    clarinet` and `sarune etek` are dropped to the saxophones (each a single reed with a conical
    bore, quoted in its row). The new wait name `a sourced reed and bore` holds a ranged row whose
    sources give both reed and bore, or give two bores with none called usual: the tenor and
    contrabass `birbyne` (the Visuotine lietuviu enciklopedija gives the improved type "a
    cylindrical or a conical bore"), each ranged from that encyclopedia by its Helmholtz letters
    with octave marks (H-e2 and Fis1-d1, read as B2-E5 and F#1-D4; the soprano's a-f3 reads A3-F6).
    Confirm the boundary, and that Helmholtz letters with octave marks fix the octave (batch 7
    accepted the bowed psaltery's "f - f'''"): if not, the two move to `a sourced range` and
    leave `CLARINET_HELD_BACK`
  - [ ] The bare `birbyne` waits for `a sourced range` although the encyclopedia ranges the
    soprano (A3-F6): neither it nor the English page calls the soprano the standard, usual or most
    common size, and range ruling 6 says that with several sizes and none called standard the row
    waits (the audit's "Birbyne (soprano)" is not a source). Is the soprano the standard size of
    the birbynė? If you have a source that says so, `birbyne` is ranged A3-F6 and then waits for
    a sourced reed and bore like its two sizes (found by the final review; cost: none, it waits
    either way)
  - [ ] A cylindrical clarinet as a sound-alike: the catalog's `_clarinet` already favours odd
    harmonics, so no new table; a SHIP only for drones or a sourced detune; bells, materials,
    keys and colour words are no trait. `c clarinet` is the only one that shipped
  - [ ] The parent ruling (the source's relation first, else the nearest lowest note, `chalumeau`
    only by relation, sizes sharing their type's parent), and each sound-alike's parent:
    `c clarinet` is of `clarinet` (VSL relates the C clarinet to "the other two clarinets", the B
    flat and the A; `clarinet`'s D3 is 2 semitones from the C clarinet's E3, `a clarinet`'s C#3 and
    `e flat clarinet`'s G3 each 3)
  - [ ] The range ruling (sounding, a written range only with its stated transposition and a key
    in the name not one, never hedged, a width, letters, a key or one pitch, makers' and museums'
    pages over uncited Wikipedia lines, nothing below A0 or above C8, one-note instruments, cited
    Wikipedia lines whose citation supports them), and every derived range: `c clarinet` E3-C7
    (VSL: "On all clarinets the written compass ranges from E3 - C7. On the C clarinet this is
    also the range of sounding pitches."). Two rows were reversed by it. `d clarinet` was a
    sound-alike (F#3-D7 from VSL's written E3-C7 plus its "the D clarinet a major second"), but
    VSL's compass line is a statement about notation ("This correlation between notation and
    sound means that the written compass of all clarinets ranges from E3 to C7"), false for the
    basset horn and the bass clarinet, and the E-flat page's cited Gangl line puts that sibling's
    written top at G6, so the row waits (rulings 5 and 7: nothing from a generalisation or a
    sibling); cost: one sound-alike, of `e flat clarinet`. `xaphoon` was ranged C4-C6 from
    Wikipedia's lowest note (cited to Grove, unopened) and the maker's "Two complete octaves", two
    sources for one range, so it waits (range ruling 1: one source). The Clarinet family page's
    range cells are uncited (the contra-alto's and contrabass's written cells alone cite Blatter),
    so they range nothing under ruling 10: `piccolo clarinet` (C4-Eb7), `b natural clarinet`
    (Eb3-Bb6), `low g clarinet` (B2-G6) and `basset clarinet` (A2-A6) wait for it. Confirm the
    rulings, and say whether an uncited family table should range anything
  - [ ] The drone ruling and the double-pipes ruling (`_drone_clarinet` and `chorus_cents` if
    added, with each value's source and the copied sound design: `sackpipa`'s 0.35 drone level,
    the slope and low pass of the clarinet the parent ruling chose): neither was added, because no
    double clarinet has a sourced range. The `mijwiz` is a detuned unison pair by Grove (via the
    Double clarinet page, "often with one pipe tuned slightly higher than the other to produce
    acoustic beats"), with no cents given, so once ranged it waits for `a sourced detune`; the
    Koizumi Fumio archive (Tokyo University of the Arts) gives its specimens' lowest notes, spans
    and drone pitches, each its own key and none called standard, so none is a range
  - [ ] The Bohlen-Pierce clarinet's scale as no trait (the 13-step tritave is the pitches a
    sequence asks for, not the instrument's sound): `bohlen pierce clarinet` waits for a sourced
    range, since one maker (Fox) offers soprano, tenor and contra sizes with none called
    standard. Fox's tuning table's altissimo top (1700.1 Hz) was ruled an extreme (range ruling 3);
    its bore counted as sourced by reference ("the same bore, same mouthpiece" as the B-flat
    clarinet, whose bore VSL gives as cylindrical)
  - [ ] The makers' ruling (`xaphoon`, `venova`) and the one-off and unsourced rows, with the
    words "no fetched source describes it" on every row whose page was not found: `xaphoon` is the
    maker's product (its cylindrical bore only in Wikipedia's uncited lead and infobox, the maker
    naming none, so it also waits for a reed and bore); `venova` (Yamaha: the YVS-100's specs give
    only "fully chromatic 2-octave range", the alto's "F33-F57" and tenor's "C28-C52" use a
    numbering the page does not name; Yamaha says a branched pipe makes the cylindrical bore sound
    conical, which would wait for `its own build (a branched pipe)`). No row carries "no fetched
    source describes it": every row's page was found (`toleat` is West Javanese, from Indonesian
    Wikipedia, not the audit's "Philippines"; `sarune etek` has a journal article, below)
  - [ ] `sarune etek` was dropped to the saxophones on a 2017 university journal article (Danny
    Ivanno Ritonga, "Teknik Permainan Instrumen Musik Tradisional Batak Toba (Gondang Hasapi)",
    Bahas 28(2), Universitas Negeri Medan: "berlidah tunggal", single-reed, bored "seperti bentuk
    kerucut", like a cone). The controller accepted it as scholarship of the same tier as Grove:
    range ruling 7 lists encyclopedias, makers, museums and conservatory references, not
    journals. Batch 9's precedent is weaker than it looks: `nyanga panpipes` (in
    `plans/data/instrument-audit/batch-9.tsv`) cites a journal article (Andrew Tracey, African Music Society
    Journal, 1971) as its source, but is dropped as an ensemble in hocket, not on the article's
    standing, so no earlier batch dropped a row on a journal article alone. Confirm it; cost if
    wrong: only the reason and the #70 hand-off change, to DROP "no
    fetched source describes it" (or WAIT `a sourced range`, its notes being do-re-mi-fa-sol with
    no octave)
  - [ ] Generic and ambiguous terms dropped (`hornpipe`, `memet`, `birbyne` and the rest, as
    decided): `hornpipe` is a generic term (its page makes it "a specific instrument or a class",
    the specific one being the `pibgorn`, which has its own row) and `memet` a generic term for the
    ancient Egyptian single-reed pipes. `birbyne` is not an ambiguous name (its encyclopedia gives
    the improved type a single reed), only one of uncertain bore. `cifte` and `argun` are dropped
    because no cited page gives them as the arghul's name (the Arghul page gives the cifte a
    section of its own, with Koizumi No. 611 and No. 610 "argun" with a drone as separate
    specimens); `argul` is the arghul's alias, as the page spells it. `sneng` stays as batch 10
    decided it (WAIT, brass: "a bamboo single-free-reed mouthpiece" is a free reed)
  - [ ] The module move: `clarinets.py` holds the family (moved unchanged from `winds.py`, which
    keeps the saxophones and free reeds; the way batches 9, 11, 12 and 13 moved their families),
    its table is `_CLARINET_BUILDS` and `CLARINETS` is `_CLARINET_BUILDS +
    CLARINET_SOUND_ALIKES`. The before-and-after record of all 703 builds found `changed: []`.
    The module's first docstring line was 123 columns, closed at first with a `ruff: ignore` and
    then shortened by the controller
  - [ ] `CLARINET_HELD_BACK`, the guard for every non-range wait: 2 names (above), refused as a
    catalog name or an alias by a test and compared with the sheet by the code check. The 4
    target waits (`maui xaphoon`, `pocket sax`, `xaphoon de catalunya`, `argul`) are not held,
    because their targets wait only for a range. `pilili` was held back for a reed and bore until
    the review: its maker's "des1 - c2" tuning list (a seventh) sits on a page that says "a
    diatonic scale of one octave", so it states no compass and the row waits for a range
  - [ ] The two-half split as explicit lists (half A, the orchestral and modern clarinets, 17
    candidates and 3 alias names, 20 rows; half B, the folk single-reed pipes, 28 candidates and 3
    alias names, 31 rows), the sheets researched in parallel, and the shared files (the names
    file, the candidate lists and the three check scripts) written up front by a setup agent. Task
    5 skipped its Steps 2 and 3 by ruling (half B shipped nothing, so it only filled
    `CLARINET_HELD_BACK` and ran the code check); Tasks 3 and 5 went to one implementer, and
    Task 3 shipped only `c clarinet`
  - [ ] The size chain left out: would you add the clarinet sizes to
    `test_sized_families_descend_from_highest_to_lowest`? (It would test the 9 earlier entries'
    unsourced ranges, so this batch did not.)
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    `a sourced reed and bore` (a source wait this plan added; 2 rows held back, plus the
    `birbyne`, `xaphoon` and `pilili` once ranged) and, once ranged, `its own build (a branched pipe)` for
    `venova`, `a sourced detune` for `mijwiz` and `a sourced drone tuning` for the double
    clarinets
- **Bugs to report** (found while building batch 14; none fixed here):
  - [ ] The 9 earlier entries carry no source comment, and no range or build of theirs was checked
    against a source beyond those named here. VSL matches `clarinet` (D3-Bb6) and `a clarinet`
    (C#3-A6) exactly, so both can be sourced as they stand
  - [ ] `e flat clarinet`'s top note: the catalog has C7, but the E-flat clarinet page's cited
    Gangl 2021 line says "Many orchestration and instrumentation books show the highest written
    note for the E-flat clarinet as G6", which sounds Bb6; VSL's "all clarinets E3-C7" written
    plus its "minor third higher" gives Eb7. Two sources, two different tops, neither the catalog's
  - [ ] Five existing clarinet ranges differ from the Clarinet family page's, whose range cells
    are uncited (so they are leads, not contradictions): basset horn F2-F6 against the catalog's
    F2-F5, alto G2-Eb6 against Bb5, bass Bb1-Bb5 against F5, contra-alto Gb1-C5 against G4 and
    contrabass Bb0-G4 against Bb3 (the audit's "Range checks")
  - [ ] `chalumeau`'s F3-Bb4 has no source (the audit: "Wikipedia gives no per-size range ...
    UNVERIFIED"); `mock trumpet` is not an alias of it (Dart calls it the chalumeau's English name
    but Rice says it "predated the chalumeau", and its reed is idioglot)
  - [ ] The docstring sentence on folk ranges ("typical of the common keys") has no source and
    sits in three modules: `winds.py:7-8`, `flutes.py:11-12` and `double_reeds.py:9-10`. It
    predates this batch; `clarinets.py`'s docstring dropped it when the family moved (it holds no
    folk pipe)
  - [ ] English Wikipedia's Tarpa and Pey pok pages cite sources that do not say what they are
    cited for (free reeds: chandrakantha.com says only "a type of a hornpipe of the Pungi class";
    Folkways FE 4082's notes say "single-reed" without saying free). Its Birbyne page gives a G6
    top that the national encyclopedia gives as F6 (the other tenor and contrabass ranges are
    uncited there too)
  - [ ] The audit's "toleat: Philippines" is wrong (West Java), and its "sarune etek: rolled-leaf
    bell? (memory)" is unconfirmed (the journal gives a wooden funnel resonator)
  - [ ] A warning to understand: `pytest -W error` fails on a DeprecationWarning at import ("aifc
    was removed in Python 3.13", from the standard-aifc package that `speech_recognition`
    imports). It is third-party and present before this batch (#81 to #83 record it); a new
    warning in these runs would be a new finding
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/clarinets.md`, listed in #70) are a later
    pass over this family
  - [ ] Ranging the 34 range WAITs from maker and museum sources (Buffet Crampon's Prestige Basset
    page returned 404; MIMEd 16364 returned 403; Backun, Ripamonti, Orsi, Foag, Wurlitzer and
    Leblanc gave only lowest notes), each row's notes recording what was searched
  - [ ] Check the 9 earlier entries against sources (ranges and builds)
  - [ ] The engine changes that unblock the waits above, most rows first: the 34 range waits need
    no engine feature, the tenor and contrabass birbyne need a source that gives one bore, `octocontrabass clarinet`
    needs sub-audio fundamentals, `venova` a build of its own, `mijwiz` a sourced detune and the
    double clarinets their drones' tuning
  - [ ] The cifte as its own double clarinet (Koizumi No. 611: two fingered pipes; No. 610 "argun"
    with a drone), the old folk birbyne (single or double reed) and the modified ganurags in five
    sizes (VLE) are leads, all unranged
- **Incidents and process**:
  - [ ] The Pi hook was skipped while the Pis were unreachable, so pushes skip it (the owner,
    2026-11-13)
  - [ ] Batch 10 now carries batch 12 at the owner's request ("Merge 12 into 10 since 10 needs to
    rerun anyway"). The merge first had to fix a stale `DOUBLE_REEDS` import that broke batch
    10's import (fce13952). This is on branch `feat/instrument-catalog-batch-10` (commit fce13952
    there), not on this branch
  - [ ] The plan had a defect: Hornbostel-Sachs has no 422.221 or 422.222 bore split (MIMO: 422.22
    "Sets of reedpipes with single reeds", narrower only by -5 and -62; the Wikipedia list
    agrees: "422.22 Sets of clarinets." with no split). The controller patched
    `build/batch-14-form-check.py` to accept 422.22 for a set and take its bore from the quoted
    bore words, and half B's `hs` cells were fixed to match
  - [ ] The syft pin is 1.57.1 on the stack (the owner's choice, batch 12's note), and batch 14's
    base is batch 13's HEAD `5bc859c7`, which merged batch 12's tip
  - [ ] The two sheet halves were researched in parallel, and pushes and stacked PRs were made
    without asking (the owner, 2026-11-12, #78)
  - [ ] The reversals above (`d clarinet`, `xaphoon`, `pilili`) each followed a review round: the
    half A sheet had one fix commit and half B one, so the sheet's own history holds the first
    readings. `sarune etek` stayed a drop on the controller's ruling that a journal article is
    scholarship
  - [ ] The first full `uv run pytest` of Task 6 failed one test on the native (cocoa) run, `tests/engine/test_game_engine.py::TestReplayRestartExitStatus::test_a_status_no_exit_code_names_is_passed_through` (a `frames_vary` test: its watched replay shows the live window's mouse focus), while `nox -s lint-docs` ran beside it on the same machine; the test passed alone and the whole suite passed on the rerun (26216 passed, 100% coverage). Likely load or pointer state, not this batch (no engine code changed), but a flaky native-driver test is a finding
  - [ ] Parked minors from the reviews: the `heckelphone clarinet` row now quotes its H-S line;
    `alboka`'s Auñamendi paraphrase is marked as an unsaved lead (the page sits behind a bot wall,
    read only through a fetch tool); `xaphoon de catalunya` counts an uncited Wikipedia paragraph
    as the alias citation (ruling 10 covers ranges, bores, drones and traits, not alias names);
    `test_no_clarinet_name_held_back...` passed vacuously until Task 5 filled the guard; the sheet's
    cells contain stray quote characters (read it with Python's csv module); `c clarinet`'s comment
    in `clarinet_sound_alikes.py` lacked a closing period (fixed by the controller); `pilili`'s
    `hs` is `none` (its infobox's 422.211.2 is uncited); the six double pipes name the fetched
    aerophone list page as their source
- **Found**: batch 14's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before the keyboards batch builds on the same catalog)

### 85. Sound Engine: The Owner's Checks on Instrument Catalog Batch 15 — TODO
- **Goal**: confirm or overturn the calls made while batch 15 of #70 ran, and listen to its one
  alias (`fender rhodes`). Nothing was built and no sound-alike was added: the keyboards stayed at
  11 entries (704 in all, 121 aliases, 197 sound-alikes), with 47 waits, 1 alias and 22 drops in
  the sheet's 70 rows (SHIP 0, SOUND_ALIKE 0, WAIT 47, ALIAS 1, DROP 22). The 5 mechanical-audit
  piano rows were added as candidates, and the electromechanical instruments moved out of
  `keyboards.py` into `electromechanical.py`
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter and release is sound design unless a source is cited in the code; the folder is
  `build/instruments/keyboards/`):
  - [ ] The new builds: none (no 16' harpsichord and no keyed idiophone shipped, so there is no
    build to compare with the catalog entry its values would have been copied from)
  - [ ] The sound-alikes beside their parents: none shipped
  - [ ] The alias: `fender rhodes` (of `tine electric piano`, in
    `build/instruments/electromechanical/`: it is the same instrument under another name, and
    sounds as `tine electric piano` does)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-15.tsv`; the sheet's 70 rows:
  SHIP 0, SOUND_ALIKE 0, WAIT 47, ALIAS 1, DROP 22):
  - [ ] Every WAIT (47 rows), by reason:
    - 42 for a sourced range: `barrel piano`, `dolceola`, `dulce melos`, `giraffe piano`, `janko
      piano`, `laterna`, `lutheal`, `moor double keyboard piano`, `nickelodeon`, `orphica`, `pedal
      piano`, `photoplayer`, `piano melodico`, `player piano`, `quarter tone piano`, `square
      piano`, `tack piano`, `tangent piano`, `welte mignon`, `ampico`, `duo art`, `disklavier`,
      `cabinet piano`, `cottage piano`, `pyramid piano`, `lyre piano`, `pleyel double piano`, `vis
      a vis piano`, `archicembalo`, `clavicymbalum`, `clavicytherium`, `claviharp`, `dulcitone`,
      `glasschord`, `harpsichord buff stop`, `harpsichord sixteen foot`, `keyed glockenspiel`,
      `lautenwerk`, `ottavino`, `pedal clavichord`, `typophone` and `muselar`. Range first: a
      row's notes keep its next blocker once ranged (`laterna`: its bell, more than four sources;
      `photoplayer`: percussion, pipes and effects, more than four sources; `lutheal`: its own build,
      registers `_piano` cannot make; `piano melodico`: its own build, repeated hammer strokes, no
      LFO; `tack piano`: its own build, tacks on the hammers; `vis a vis piano`: its own build, a
      piano and a harpsichord facing one another; `ottavino`: its own build, a 4' choir alone;
      `dulcitone`, `typophone` and `glasschord`: `a sourced partial series`; `harpsichord sixteen
      foot`: sub-audio fundamentals on F1 keys, a sound-alike of `harpsichord` with
      `sound_changes={'sixteen_foot': True}` on keys from A1 up)
    - 5 because their target waits: `pianola` and `reproducing piano` (for `player piano`),
      `roller piano` (for `barrel piano`), `rhombia` (for `laterna`) and `lautenwerck` (for
      `lautenwerk`)
  - [ ] The module move: `electromechanical.py` (the 11 electromechanical entries, out of
    `keyboards.py`, comments included, byte-identical to the removed section) and
    `keyboard_sound_alikes.py` (empty); `keyboards.py` keeps the keyboards, its table is
    `_KEYBOARD_BUILDS` and `KEYBOARDS` is `_KEYBOARD_BUILDS + KEYBOARD_SOUND_ALIKES`. The
    before-and-after record of all 704 builds found `changed: []`. `Instrument` (in
    `keyboards.py`) and `CatalogEntry` (in `keyboard_sound_alikes.py`) moved under `TYPE_CHECKING`,
    as batch 14's modules have them
  - [ ] The boundary rulings, each row they moved, and the Hornbostel-Sachs codes this plan
    checked (314.122, "the piano is part of this subdivision", with the suffixes 4 hammers, 5 bare
    hands and fingers, 6 plectrum, 8 keyboard and 9 mechanical drive; 111.212 and 111.222; 412.132;
    each against Wikipedia's lists on 2026-11-13): `scalatron` and `walking piano` are dropped to
    electronic (an oversized synthesizer), `shahi baaja` to plucked strings (keys stopping the
    strings), `clavier a lumieres` makes no sound, and `octavator` (a keyboard that lights slide
    projectors, a string struck, bowed or strummed) and `chekker` (its source calls its exact
    details "a matter of academic debate") are dropped, `octavator` as a one-off on an enthusiasts'
    gallery page that counts for existence only. No row was dropped to struck strings, harps, free
    reeds or electromechanical
  - [ ] A keyboard as a sound-alike (cases, layouts, tunings, sizes, materials and colour words no
    trait; a SHIP only for a sourced 16' choir or sourced partials): none shipped, so none is a
    sound-alike yet. Each waiting row's "Engine limit, once ranged" note says whether it would be
    one
  - [ ] The parent ruling (the source's relation first, the only way to another family's parent;
    else the same mechanism's nearest lowest note), and each sound-alike's parent: none shipped.
    Once ranged: `pleyel double piano` takes rule 2 (its quote, "two pianos into the same frame",
    names no grand piano), `harpsichord buff stop` is of `harpsichord lute stop` by rule 1 (see the
    bugs below: that parent's build is suspect), `keyed glockenspiel` of `glockenspiel` (a
    cross-family parent, by its source's relation, "a glockenspiel operated by a piano keyboard")
  - [ ] The range ruling (one source states both ends; a string keyboard's 8' compass sounding as
    given, a keyboard idiophone's written range only with its stated transposition; key counts,
    widths, hedges and generalisations no range; makers' and museums' pages over uncited Wikipedia
    lines; nothing below A0 or above C8, for the keys and the choirs), and every derived range:
    none was derived, since every row waits. The rulings that decided it:
    - Range ruling 4 (a maker's or museum's page ranges a row named for that model only) kept
      `tangent piano` (Chris Maene's Spath & Schmahl model, F1-F6, against the page's "given a wide
      6 octave range"), `dulcitone` (the Horniman's AA-a3 at 4' pitch, sounding A2-A7; Yale's
      Machell object gives "A to a'''", and Wikipedia lists 3 1/2-, 4- and 5-octave styles),
      `square piano` (the Met's records give FF-f3, FF-f4 and FF-c4) and `harpsichord sixteen
      foot` waiting for a range
    - the player piano's three roll scales ("A1 to C#7", "A0 to C8", "F1, G1 to E7", an uncited
      paragraph of the Piano roll page, none called standard) range nothing
  - [ ] The keyed glockenspiel and harpsichord sixteen foot rulings: `keyed glockenspiel` waits
    for a sourced range, since the Vienna Symphonic Library's "Keyboard glockenspiel C5 - C8" says
    neither written nor sounding, and its notation says the instrument "generally sounds one
    octave higher than written" (hedged; read as written the range would be C6-C9, above C8).
    Cost if wrong: one cross-family sound-alike of `glockenspiel`, C5-C8, recoverable the moment a
    source says sounding. `harpsichord sixteen foot` waits for a sourced range: Neupert's
    "harpsichord Hass" page gives "keyboard compass: 5 octaves (F1 - f3)" and "lower manual: 8',
    4', 16'", which is one maker's model, not the generic instrument's (range ruling 4, the model-page
    rule: a model's page ranges that model only); its sub-audio point stays in the notes as its next wait, and it left
    `KEYBOARD_HELD_BACK`. Cost if wrong: none, it waits either way. Was a model page enough?
  - [ ] Already decided (12 DROP rows, each naming the earliest sheet that decided it; #70
    forbids deciding them again): `rhodes celeste` and `rhodes piano bass` (batch-2.tsv DROP: the
    tine electric piano covers the register), `yamaha cp electric grand` (batch-2.tsv WAIT, a
    sourced range), `bulbul tarang` and `taishogoto` (batch-4.tsv WAIT, plucked strings),
    `chamberlin`, `mellotron` and `optigan` (batch-2.tsv WAIT, electromechanical tape or optical
    replay; batch-6.tsv also dropped each as already decided, and the earliest sheet is the one
    named), `geigenwerk` and `viola organista` (batch-7.tsv WAIT, bowed strings), `orchestrion` and
    `panharmonicon` (batch-13.tsv WAIT, organs). Cost if wrong: a name that should have been
    researched again stays dropped, recoverable by an owner call on the earlier sheet
  - [ ] The setup's `luthéal` ruling: the candidate lists keep the accent, the sheet's row is named
    `lutheal` and its audit_name is `luthéal`
  - [ ] The choir ruling (`sixteen_foot` if added, its copied level and offset) and the keyed
    idiophone ruling (`_keyed_idiophone` if added, the copied celesta values, the new wait name `a
    sourced partial series`): neither builder was added, because no row shipped. The wait name
    `a sourced partial series` is held for `dulcitone` and `typophone` (a tuning fork's partials
    are stated by no fetched source; the audit's "near-sine" is from no page) and `glasschord`
    ("glass tubes" states no partials), each once ranged. The guards that would pin them
    (`KEYBOARD_SIXTEEN_FOOT_NAMES` and `KEYBOARD_PARTIAL_RATIOS`) are empty
  - [ ] The mechanical ruling and each tagged or waiting self-playing keyboard: none is tagged
    (`MECHANICAL_KEYBOARD_NAMES` is empty); `barrel piano`, `laterna`, `nickelodeon`, `photoplayer`,
    `piano melodico` and `player piano` (and `pianola`, `reproducing piano`, `roller piano`,
    `rhombia`, `welte mignon`, `ampico`, `duo art` and `disklavier`) all wait, so
    `Tag.MECHANICAL` is still only on the `music box`. The 5 mechanical-audit piano rows (`barrel
    piano`, `laterna`, `nickelodeon`, `photoplayer`, `piano melodico`) were added as candidates, as
    batch 13 took `flute clock` from the same audit; no earlier sheet decided them. `nickelodeon`
    rests on the Canadian Encyclopedia through the Wayback Machine's copy (the live page refused
    curl with a 403; the first read was a WebFetch summary, which the review refused as a source),
    all four quotes verbatim. Confirm it as a source, else the row is DROP "no fetched source
    describes it"
  - [ ] The registers ruling (`harpsichord buff stop`) and the catalog's `harpsichord lute stop`
    naming question: `harpsichord buff stop` waits for a sourced range (Grove's entry is titled
    "Buff stop [harp stop and (erroneously) lute stop]"), and once ranged it would be a
    sound-alike of `harpsichord lute stop`. That catalog entry is built muted (a 3.5 kHz low pass),
    which is the buff stop's sound; Grove calls "lute stop" a wrong name for it. The true lute stop
    is "an alternative row of jacks" plucked near the nut, which "emphasizes the higher harmonics,
    and produces a 'nasal' sound quality" (brighter, not muted). Is the catalog's entry a buff
    stop under a wrong name, to be renamed or rebuilt?
  - [ ] Generic, ambiguous, one-off, technique and unsourced rows, with the words "no fetched
    source describes it" on every row whose page was not found: no row carries them (every row's
    page was found). The generic and ambiguous names: `spinet` is DROP, an ambiguous name (a
    harpsichord type, the small upright "spinet piano" from the 1930s, and the "spinet organ" of
    1949, the Spinet page's own three senses), and the Harpsichord page's uncited definition ("A
    spinet is a harpsichord with the strings set at an angle...") is no source (range ruling 9).
    Cost if wrong: one future sound-alike of `harpsichord` (a bentside spinet), recoverable. `street
    piano` ("a piano placed in a public area" on Wikipedia, "Street or barrel piano" at the London
    Museum) and `piano organ` (no fetched page defines it) are dropped as ambiguous, not waiting
    aliases of `barrel piano`. `prepared piano` is dropped (a preparation that differs with each
    piece, the techniques ruling). `muselar` is its own row, not an alias of `virginal` (its page
    sets it apart by its plucking point, one third along the string; no cited page gives it as a
    virginal's name)
  - [ ] `moor double keyboard piano`: the plan's "own build (an octave coupler)" is superseded.
    Only the "special fourth pedal" sounds the octave, a pedal the player works (the techniques
    ruling: "A pedal or a stop the player works ... is no instrument"), and the upper manual is a
    layout, so once ranged it is a sound-alike of a catalog piano by parent ruling 2, not a build
    of its own. It waits for a sourced range either way. Confirm
  - [ ] The other calls that departed from the plan or the audit, each a row that waits for a
    range either way: `vis a vis piano` is no alias of `grand piano` (the only fetched page, on
    Johann Andreas Stein, defines it as "a piano and a harpsichord facing one another in a single
    case", with a harpsichord of 8' 8' 8' 16' (Verona)), `cabinet piano`, `cottage piano`,
    `pyramid piano` and `lyre piano` are rows of their own, not aliases (the pages make them
    distinct uprights, and "cabinet piano" is also a giraffe piano with shelves), `welte mignon`,
    `ampico`, `duo art` and `disklavier` are rows of their own (the makers' ruling: each is a
    maker's system fitted to several pianos; `disklavier` also covers the GranTouch digital
    pianos, so it might be dropped as ambiguous), `reproducing piano` follows `player piano` as a
    waiting alias although the Player piano page calls reproducing pianos "fully automated versions
    of the player piano" (a kind, not another name), `typophone` is decided on its own pages and
    not as an alias of `dulcitone` (the Celesta page: the dulcitone "was developed concurrently in
    Scotland; it is unclear whether their creators were aware of one another's instrument"),
    `lautenwerk` decides the instrument and `lautenwerck` waits for its target, and `clavicymbalum`
    waits rather than being dropped as generic (its page makes it one instrument, cited to
    Kottick)
  - [ ] `KEYBOARD_HELD_BACK`, the guard for every non-range wait: it holds nothing (every wait
    is for a range or for a target that waits only for a range), and the test refusing a held-back
    name as a catalog name or an alias passes vacuously, as batch 12's did
  - [ ] The two-half split as explicit lists (half A, the pianos, 23 candidates and 17 alias
    names, 40 rows; half B, the harpsichords, clavichords, keyboard idiophones and the boundary
    names, 29 candidates and 1 alias name, 30 rows), the sheets researched in parallel, and the
    shared files (the names file, the candidate lists and the three check scripts) written up front
    by a setup agent. Task 5 shipped nothing (no commit: it only ran the code check), and Task 3
    shipped only the `fender rhodes` alias
  - [ ] The size chain left out: would you add the keyboard sizes to
    `test_sized_families_descend_from_highest_to_lowest`? (It would test the 11 earlier entries'
    unsourced ranges, so this batch did not.)
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    `a sourced partial series` (a source wait this plan added; held for `dulcitone`, `typophone`
    and `glasschord` once ranged) and, once ranged, `its own build` for `lutheal`, `piano
    melodico`, `tack piano`, `vis a vis piano` and `ottavino`, more than four sources for
    `laterna` and `photoplayer`, and sub-audio fundamentals for `harpsichord sixteen foot`
- **Bugs to report** (found while building batch 15; none fixed here, except the first):
  - [ ] `electromechanical.py` said "The ten moved entries" where the section holds 11 (the tine and reed
    electric pianos and the Clavinet, 7 tonewheel registrations and the Pianet). A bug that predates the
    batch: the comment moved verbatim in Task 1 and was parked by the review. Fixed in Task 6
    (the only line of existing code changed: "ten" became "eleven")
  - [ ] `harpsichord lute stop` is built muted (`_harpsichord(low_pass=3500.0)`), which is the
    buff stop's sound; Grove calls "lute stop" a wrong name for the buff stop, and the true lute
    stop is brighter and nasal (above). The 11 earlier entries carry no source comment
  - [ ] The Celesta infobox gives C3-F8 against the catalog's C4-C8. The Vienna Symphonic Library
    calls C4-C8 its second-generation four-octave size and says "Modern instruments usually have a
    range of five and a half octaves ... C3 - F8", so the catalog matches a named older size, not
    the usual modern one
  - [ ] The Harpsichord page's compass paragraph ("The traditional pitch range for a 5-octave
    instrument is F1-F6") has no citation in its paragraph, so `harpsichord`'s F1-F6 is uncited
    (a maker's model, Neupert's Hass, agrees for that model only). `virginal`'s C2-C6 is the
    Virginals page's uncited "most virginals was C2/E2 to C6", whose lowest octave is a short
    octave
  - [ ] `glockenspiel` G5-C8: the Vienna Symphonic Library gives G5-C8 as one of two
    two-and-a-half-octave sizes and says "Three-octave mallet-played glockenspiels are usual in
    the symphony orchestra" (F5-F8 or C5-C8), so the catalog's range is not the usual size
  - [ ] The Pleyel et Cie page says "resulting in the double piano in 1890, invented by Hungarian
    composer Emanuel Moor", conflating Pleyel's Duo-Clave with Moor's double keyboard piano, which
    the Emanuel Moor page dates to 1921. A Wikipedia error, not the catalog's. The audit and the
    plan also describe `vis a vis piano` as two pianos facing each other; the only fetched page
    says a piano and a harpsichord
  - [ ] The quote check (`build/batch-15-quote-check.py`) reads saved pages as UTF-8, but Gregg
    Miner's dolceola pages (which batch 4 cited) are windows-1252 HTML, so a SHIP row quoting them
    would fail on decoding. One Miner passage also has `<b>strike</b>` inside the sentence in the
    raw HTML
  - [ ] The quote check verifies only SHIP and SOUND_ALIKE rows, so on a sheet of waits and drops
    it passes vacuously (it did for all 70 rows). The reviews checked the WAIT and DROP quotes by
    hand with scripts (134 quotes in half B, 30 in half A, 4 for the nickelodeon); the check should
    cover every status
  - [ ] The player piano's Piano roll lead: three roll scales in an uncited paragraph, none called
    standard (A1 to C#7, A0 to C8, F1 and G1 to E7); `walking piano`'s "Versions of the piano have
    been installed..." sentence is `{{cn}}` (dropped from the row)
  - [ ] 17 DeprecationWarnings appear under `-W default` (the Task 3 and Task 5 runs, and the full
    runs below): `speech_recognition/__init__.py:7` imports `aifc` (removed in Python 3.13), which
    the `standard-aifc` backport satisfies. It is third-party and present before this batch (#81 to
    #84 record it as a failure under `-W error`); `pyproject.toml` already filters it on purpose, so
    normal runs hide it, and a new warning would be a new finding. The reports said "no warnings"
    where there were these 17
  - [ ] The fetch failures, recorded in the rows' notes: the Met's object page (429; its
    collection API record was saved instead), the National Music Museum's Tangentenflugel record
    (403), the MIM Brussels luthéal page (404), the National Music Centre's Pleyel duoclave (403),
    Britannica's barrel piano and buff stop pages (403), museum-digital's claviharp record (502),
    the Canadian Encyclopedia (403 to curl), and Grove Music Online (a subscription)
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/keyboards.md` and
    `new-mechanical-instruments.md`, listed in #70) are a later pass over this family
  - [ ] Ranging the 42 range WAITs from maker and museum sources (each row's notes record what was
    searched; the compasses found were single objects or models, such as the Met's square pianos,
    the Horniman's and Yale's dulcitones and the Royal College of Music's clavicytherium)
  - [ ] Check the 11 earlier entries against sources (ranges and builds), starting with the
    bugs above
  - [ ] The engine changes that unblock the waits above, most rows first: the 42 range waits need
    no engine feature; `dulcitone`, `typophone` and `glasschord` need a source for their partials;
    `lutheal`, `piano melodico`, `tack piano`, `vis a vis piano` and `ottavino` a build of their
    own; `laterna` and `photoplayer` more than four sources; `harpsichord sixteen foot` (on F1 keys)
    sub-audio fundamentals
  - [ ] Leads for later passes: `scalatron` and `walking piano` (electronic), `shahi baaja`
    (plucked strings), the Landesmuseum Wurttemberg's and the Ringve Museum's claviharp records
    (not reached), and the `octavator` (Ken Butler's hybrid keyboard and string instrument, on the
    Oddmusic gallery)
- **Incidents and process**:
  - [ ] Batch 13 (#191) was squash-merged into batch 10. Batch 14 then merged batch 10's tip
    (`73fd1ecd`), taking its own side, and its PR is #193 on batch 10
  - [ ] The Pi hook was skipped while the Pis were unreachable, so pushes skip it
  - [ ] The two sheet halves were researched in parallel, and pushes and stacked PRs were made
    without asking (the owner, 2026-11-12, #78)
  - [ ] The reversals and re-rulings, each after a review round, so the sheet's own history holds
    the first readings: the sheet's two halves each had one fix commit (`96217693` for half A,
    `020e026d` for half B), and the code task had one fix round for its partials
    guard (`ac4fa351`: the first version passed only because its table was empty and would have
    failed the celesta's and toy piano's real partials, with a tolerance too coarse to tell 2.76
    from 3.0). `nickelodeon` first rested on an unsaved WebFetch read; `spinet`'s first DROP
    ignored the Harpsichord page's definition; `harpsichord sixteen foot` was a wait for sub-audio
    fundamentals until the controller's range-first ruling
  - [ ] Parked minors from the reviews: `octavator` is dropped as a one-off though the plan
    suggested "no fetched source describes it" (only the wording differs); `clavier a lumieres`'s
    page never says "silent" (its keys correspond to colours); `harpsichord buff stop`'s parent
    goes stale if `harpsichord lute stop` is rebuilt; `piano melodico`'s tremolo is a trait no
    engine feature makes
  - [ ] The branch's base is `982a66a7` (batch 14's final review fixes)
- **Found**: batch 15's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before the free reeds batch builds on the same catalog)

### 86. Sound Engine: The Owner's Checks on Instrument Catalog Batch 16 — TODO
- **Goal**: confirm or overturn the calls made while batch 16 of #70 ran, and listen to its one
  alias (`richter harmonica`). Nothing was built and no sound-alike was added: the free reeds
  stayed at 13 entries (704 in all, 122 aliases, 197 sound-alikes), with 58 waits, 1 alias and 8
  drops in the sheet's 67 rows (SHIP 0, SOUND_ALIKE 0, WAIT 58, ALIAS 1, DROP 8). The free reeds
  moved out of `winds.py` into `free_reeds.py` and `free_reed_sound_alikes.py`, and `winds.py`
  now holds only the saxophones
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter and release is sound design unless a source is cited in the code; the folder is
  `build/instruments/free reeds/`):
  - [ ] The new builds: none (no droned reed shipped, so there is no build to compare with
    `harmonica`, whose chanter it would have shared)
  - [ ] The sound-alikes beside their parents: none shipped (so no `sound_changes` beside a parent)
  - [ ] The alias: `richter harmonica` (of `harmonica`: it is the same instrument under another
    name, and sounds as `harmonica` does)
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-16.tsv`; the sheet's 67 rows:
  SHIP 0, SOUND_ALIKE 0, WAIT 58, ALIAS 1, DROP 8):
  - [ ] Every WAIT (58 rows), by reason:
    - 43 for a sourced range: `anglo concertina`, `cajun accordion`, `chemnitzer concertina`,
      `chromatic button accordion`, `diatonic button accordion`, `duet concertina`, `flutina`,
      `free bass accordion`, `garmon`, `indian harmonium`, `orchestrelle`, `organetto`,
      `physharmonica`, `reed organ`, `shruti box`, `trikitixa`, `bayan`, `khromka`, `piano
      accordion`, `alto sheng`, `bass sheng`, `bawu`, `chord harmonica`, `chromatic pitch pipe`,
      `couesnophone`, `horn harmonica`, `hulusi`, `keluri`, `khene`, `lusheng`, `mangtong`,
      `octave harmonica`, `saenghwang`, `sho`, `sompoton`, `soprano sheng`, `tenor melodica`,
      `tenor sheng`, `tremolo harmonica`, `yu`, `triola`, `accordina` and `engkerurai`. Range
      first: a row's notes keep its next blocker once ranged (`tremolo harmonica`: `a sourced
      detune`, since "slightly", "wet" and "dry" give no number; `sho`: `a sourced partial series`,
      CCRMA's "the main energy remains essentially on the 2nd and 4th partials" with levels only in
      a figure; `bawu` and `hulusi`: `its own build (a free reed sounding a fingered pipe)`;
      `khene` and `keluri`: a sourced drone tuning)
    - 15 because their target waits: `garmoshka` (for `garmon`), `trikiti` and `eskusoinu txiki`
      (for `trikitixa`), `peti` and `samvadini` (for `indian harmonium`), `qeej` (for `lusheng`),
      `kaen`, `khaen`, `kehn` and `kheng` (for `khene`), `goofus` and `queenophone` (for
      `couesnophone`) and `keledi`, `enkulurai` and `kadedek` (for `keluri`)
  - [ ] The module move: `free_reeds.py` (the 13 free reed entries, out of `winds.py`, comments
    included, identical to the removed section but for its `_FREE_REED_BUILDS` name and the new
    `FREE_REEDS = _FREE_REED_BUILDS + FREE_REED_SOUND_ALIKES`) and `free_reed_sound_alikes.py`
    (empty); the process-state guard's listing moved with the section (`CATALOG_SERIES`
    unchanged). The before-and-after record of all 704 builds found `changed: []`. Should `winds.py`
    be renamed now that it holds only the saxophones?
  - [ ] The boundary rulings, each row they moved, and the Hornbostel-Sachs codes this plan
    checked (412.131, 412.132, 422.31, 422.32 and 412.12, each against Wikipedia's lists on
    2026-11-13): `bawu` is filed under 422.31 against the Hornbostel-Sachs list's 412.131 (the
    class text, a reed in a pipe, is 422.3), `hulusi` is 422.32, `mangtong` 412.131, `sho` 412.132
    (its infobox's 441.21 is no class), `chromatic pitch pipe` 412.132 (not the list's 412.131: its
    page describes discs with a reed per note), `orchestrelle` 412.132-9 (the -9 suffix for a
    mechanical drive: the half A worker's own call, since the Pianola Institute page says
    "roll-operated" but not that it has a keyboard) and `engkerurai` none (no page says its reed is free).
    `chromelodeon` is dropped as a one-off (batch 13's hand-off) and `pitch pipe` as a generic
    term ("any device used as a pitch reference"; `chromatic pitch pipe` decides the free reed
    instrument). `khromka` went from SOUND_ALIKE back to WAIT (below)
  - [ ] The reed organ ruling, recorded (no question): `batch-13.tsv`'s own row says «The boundary
    ruling sends it to free reeds (also a free_reeds.md row; this sheet decides the name, #70)»,
    and this ruling overrides that "this sheet decides the name, #70". The controller ruled `reed
    organ` a half-A candidate decided here, since a DROP naming a family is a hand-off (batch 15's `claviharp`
    and `dolceola`), and #70's "so the keyboards and free reeds batches must not decide them
    again" is right for `orchestrion` and a slip of the pen for `reed organ`, as #70's batch 16
    paragraph records. It waits for a sourced range; once ranged it is a sound-alike of
    `harmonium` (its page makes the harmonium one of the reed organ's types)
  - [ ] `jaw harp`: already decided (DROP "Already decided", `batch-1.tsv` WAIT, a plucked idiophone,
    121.2, waiting for moving formants; `batch-5.tsv` dropped it too)
  - [ ] A free reed as a sound-alike (layouts, keys, tunings, chords, registers, sizes, materials
    and colour words no trait; a SHIP only for sourced drones; the sound changes only for a sourced
    detune, octave reed set or drones): none shipped, so none is a sound-alike yet. Each waiting
    row's "Engine limit, once ranged" note says whether it would be one
  - [ ] The parent ruling (the source's relation first, the only way to another family's parent
    or a reed pipe's; else the same mechanism's nearest lowest note, the pipe mouth organs to
    `sheng`), and each sound-alike's parent: none shipped. The ruling's cases once ranged:
    `bayan` and `piano accordion` follow their pages' "a type of" relation, `khromka` is of
    `accordion` by rule 1 (its Wikipedia pages call it a diatonic button accordion; rule 2 alone
    would have given `concertina`, 5 semitones from G3), `reed organ` of `harmonium`
  - [ ] The range ruling (one source states both ends; a written range only with its stated
    transposition; a key, a count, a width, a scale, a hedge or a general rule no range; a model's
    page ranges that model only; a bare name of several sizes with none standard waits; nothing
    below A0 or above C8), and every derived range: none was derived, since every row waits. The
    rulings that decided it:
    - `khromka` went from SOUND_ALIKE back to WAIT. The Great Soviet Encyclopedia entry (on
      booksite.ru, saved) gives the right hand «до первой — до четвёртой октавы» (C4-C7, both ends
      in one sentence), but names two forms (21 and 25 keys) and says only that the 25-key form
      «позднее получила распространение» ("later became widespread"), and that the khromka
      «постепенно выходит из обихода» ("is gradually falling out of use"). Becoming widespread is
      not "standard, usual, most common or traditional" (range ruling 6). The notes keep the C4-C7
      reading and the `accordion` parent for when a size is called standard; this is consistent with
      batch 14's bare `birbyne`
    - `chromatic button accordion` and `bayan` wait for a sourced range, with the real reasons: the
      cited work (Llanos and Alberdi, *Accordion for Composers*) gives the right manual's range as
      staff charts, images with no quotable passage (16' E1-G6, 8' E2-G7, 4' E3-C#8, so E1-C#8), and
      only for the C-griff concert accordion (range rulings 4 and 6). A quotable source would make
      them "a range above C8". The infobox's E1-D9 is unsupported
    - `sho` waits though Stanford CCRMA gives A4 to F#6: the text names only the lowest note and
      the penultimate, and the highest is in Figure 4, an image
    - the four `sheng` sizes wait: the Sheng page's size ranges have no citation, the Chinese
      page's one cited range (G3-F#6, Hu 2014) is for "the mainstream modern sheng", and the tenor's
      "G2 to F#5 or F2 to E5" is two ranges, so none
    - `garmon`'s C4-C6 is the Tula garmon's range, not the bare name's (a 25 by 25 standard given
      only as a width), and `orchestrelle`'s "116-note rolls" are the rolls, not the compass
  - [ ] The detune ruling (the 2% rule against unsourced catalog cents, `_mouth_reed`'s `cents`
    if added), the reed-set ruling (`footages`, the 16-level cut as sound design), the drone ruling
    (`_droned_reed` if added, its copied drone level) and the reed pipe ruling (`its own build (a
    free reed sounding a fingered pipe)`): no builder was added, because no row shipped. The
    `hulusi`'s reed pipe line ("pipe length, not the reed's own frequency, sets the pitch") was
    checked against the cited arXiv paper (Xia and Bader), which says so; the guards that would pin
    them are empty. No detune or reed set is taken from a trait: the cajun accordion's "dry" tuning
    is the same pitch, its "wet" one "slightly", the Chemnitzer's gives no number, and the anglo,
    flutina and Indian harmonium drones are stops or buttons the player works
  - [ ] The mechanical ruling and each tagged or waiting self-playing free reed: none is tagged;
    `orchestrelle` (a roll-operated reed organ) waits for a sourced range, so `Tag.MECHANICAL` is
    still only on the `music box`
  - [ ] Generic, ambiguous, makers', one-off, technique and unsourced rows, with the words "no
    fetched source describes it" on every row whose page was not found: no row carries them (every
    row's page was found). The dropped rows: `melodeon` (the diatonic button accordion and the
    19th-century reed organ), `u` (the Japanese u, a larger sho, and the Goryeo-period name of the
    saenghwang: WAIT for a sourced range as a size of `sho` is equally defensible, see the bugs),
    `ken` (the khaen and the Vietnamese ken, a double reed), `claviola` (Hohner's free reed and F.
    Stichel's 1904 self-playing piano trademark; this decides the name for #70's batch 15
    gaps list too), `pianica` (a maker's name for the melodica of every size; Yamaha's P-37E is f-f''' (F3-F6),
    the catalog's alto melodica, but only for that model). Rows of their own rather than aliases:
    `bayan`, `khromka` and `piano accordion` (their pages say "a type of"), `triola` (Seydel's
    single-tone children's harmonica in two models, none standard), `accordina` (a button-layout
    melodica type), `engkerurai` and `kheng` (waiting for `khene` although the Khaen page's
    Vietnamese name has no citation of its own)
  - [ ] `richter harmonica` is an alias of `harmonica`: Richter is a tuning, which is no trait, and
    the catalog `harmonica` ("Diatonic harmonica in C", C4-C7) is the Richter C harp the page
    describes as "the standard diatonic harmonica, labeled C, starting on middle C (C4)". The alias
    name drops the page's "-tuned" (catalog names hold no hyphens). Cost if wrong: one alias too
    many
  - [ ] `FREE_REED_HELD_BACK`, the guard for every non-range wait, and the helper test that
    exercises every guard on a real build: it holds nothing (every wait is for a range or for a
    target that waits only for a range), and Task 1 tested every helper on a real build both ways
    (`drone_hertz('highland bagpipe') == [240.0, 120.0]`, `chorus_detune_cents('musette
    accordion') == 15.0`, a real name and a real alias for the held-back check, and the guards
    refusing a wrong table), as batch 15's final review had found its guards untested
  - [ ] The two-half split as explicit lists (half A, the bellows free reeds, 17 candidates and 9
    alias names, 26 rows; half B, the mouth-blown free reeds, 25 candidates and 16 alias names,
    41 rows), the sheets researched in parallel, and the shared files (the names file, the
    candidate lists and the three check scripts) written up front by a setup agent. Task 3 shipped
    nothing (no commit: half A has no SHIP, SOUND_ALIKE or ALIAS row, so it only ran the code
    check), and Task 5 shipped only the `richter harmonica` alias and two synthetic-entry tests
    for `effective_free_reed_keywords`
  - [ ] The size chain: no `sheng` size shipped (the sheng sizes chain applies if three or more
    do), and would you chain the catalog's three melodicas (`soprano melodica`, `alto melodica`,
    `bass melodica`), whose ranges are unsourced, in
    `test_sized_families_descend_from_highest_to_lowest`? (It would test the earlier entries'
    unsourced ranges, so this batch did not.)
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    a free reed sounding a fingered pipe (`bawu`, `hulusi`), a spectrum that changes with the note
    (`sho`'s second and fourth partials, `a sourced partial series`) and a second detuned reed set
    (the tremolo and musette tunings with a sourced number)
- **Bugs to report** (found while building batch 16; none fixed here):
  - [ ] The 13 earlier free reed entries carry no source comment for their ranges or builds
  - [ ] The catalog `accordion` F3-A6 has no source: the `piano accordion` page's F3-A6 is a
    written range whose sounding notes depend on the stops, and the infobox is uncited (the
    `khromka` and `piano accordion` rows)
  - [ ] The catalog `sheng` is G3-A6 and no fetched source gives A6 for any sheng. The Chinese
    Sheng page's one cited range, Hu 2014, gives G3-F#6 for "today's mainstream modern sheng"
    (目前的主流现代笙), which arguably is "most common" for the bare `sheng` (range ruling 6); the
    uncited Sheng page gives the soprano G3-F#6
  - [ ] `u` could be a `sho` size (the Japanese u, a larger sho), which would make it a WAIT for a
    sourced range rather than a DROP; neither status reaches the code
  - [ ] `keluri`'s 412.132 rests on "Each pipe has a free reed", cited to asza.com, a retailer
    (range ruling 10); the `hs` cell is informational on a WAIT row. The `khene` and `keluri`
    drone lines ("with specific drone pitches", uncited) need re-sourcing before any status relies
    on them
  - [ ] The unsourced "typical of the common keys" sentence now in both `winds.py` and
    `free_reeds.py` (#84)
  - [ ] The Hornbostel-Sachs list's Bawu under 412.131 and the Sho infobox's 441.21 (Wikipedia's,
    not the catalog's)
  - [ ] `.get('footages', (8.0,))` in the footage guard treats an absent keyword as the default 8'
    reed set, so the guard silently follows the old value if the builder's default changes
    (organs, pre-existing)
  - [ ] The quote check (`build/batch-16-quote-check.py`) read pages as UTF-8, else windows-1252,
    so a windows-1251 page (the Great Soviet Encyclopedia's `khromka` and `garmon` entries) read
    as mojibake instead of failing. The controller fixed it: it now reads UTF-8, else the page's
    declared charset (meta charset, http-equiv or XML encoding), else windows-1252, and lists each
    non-UTF-8 read. It decoded `garmon--2`, `khromka--3` and `--5` as windows-1251 and
    `orchestrelle--1` as iso-8859-1.
  - [ ] Parked test minors: the first synthetic test (`test_a_sound_alikes_keywords_start_from_its_parents_build`)
    asserts only `low_pass`, so it would not catch a parent-keyword subset bug on `cents` (the
    second test covers it); a badly wrapped table-order comment near `test_instrument_catalog.py:2154`;
    the footage guard's `.get('footages', (8.0,))` default (above)
  - [ ] 17 DeprecationWarnings appear under `-W default`: `speech_recognition/__init__.py:7`
    imports `aifc` (removed in Python 3.13), which the `standard-aifc` backport satisfies. It is
    third-party and present before this batch (#85 records it), and a new warning would be a new
    finding
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/free-reeds.md`, listed in #70) and the
    out-of-scope names (the side-blown `sneng`, the `seraphine` and the melodeon organ) are a later
    pass over this family
  - [ ] Ranging the 43 range WAITs from maker, museum and scholarly sources (each row's notes
    record what was searched; the compasses found were single models, retailers' pages, charts
    drawn as images, or hedged)
  - [ ] Check the 13 earlier entries against sources (ranges and builds), starting with the
    bugs above
  - [ ] The engine changes that unblock the waits above, most rows first: the 43 range waits need
    no engine feature; `bawu` and `hulusi` a free reed sounding a fingered pipe; `sho` a spectrum
    that changes with the note (`a sourced partial series`); `tremolo harmonica` a second detuned
    reed set with a sourced number; `khene` and `keluri` a sourced drone tuning
  - [ ] The catalog `concertina` is titled English, G3-C7 (a lead from the plan's Global
    Constraints; no defect found: the Concertina page states no compass for any system, and no
    English concertina page was fetched). To check: a source for G3-C7 as the treble English
    compass, and whether the bare name `concertina` should mean one system
  - [ ] Leads for later passes: the side-blown `sneng` (#80), the removed concertina names and the
    template's unresearched names (`orthotonophonium`, `harmoneon`, `lap organ`)
- **Incidents and process**:
  - [ ] Batch 15 is PR #196 on batch 14 (#193)
  - [ ] The Pi hook was skipped while the Pis were unreachable, so pushes skip it
  - [ ] The two sheet halves were researched in parallel, and pushes and stacked PRs were made
    without asking (the owner, 2026-11-12, #78)
  - [ ] The reversals and re-rulings, each after a review round, so the sheet's own history holds
    the first readings: half A had two fix commits (`ef02c9f7`: `khromka` ranged from the Great
    Soviet Encyclopedia and the chromatic button accordion and `bayan` notes corrected to the
    charts' real limits, the cajun accordion's class made 412.132; `bdf1dc09`: `khromka` back to
    WAIT), and half B one (`095d78a8`: `richter harmonica`'s notes named `free_reeds.py` and why
    its type wording is an alias here). `khromka`'s SOUND_ALIKE was the batch's only one
  - [ ] The controller redacted a third party's phone number and email address from a saved page
    (`build/batch-16-pages/engkerurai--1.txt`, the JKKN page: a gitignored folder, and no row quotes
    them)
  - [ ] The brief's Task 1 step 3 expected the guards to pass before the move, but the helper test
    imports `free_reeds`, so they could only go green after it (the RED was an ImportError, an
    honest one)
  - [ ] Parked minors from the reviews: `richter harmonica`'s review asked for the stale
    `winds.py` reference and the type wording to be explained (fixed); the `u` drop rests on the
    saenghwang's historical name and a WAIT is equally defensible; `soprano sheng`'s Hu 2014 line
    is recorded as a lead against the catalog's A6
  - [ ] The branch's base is `d4c1e3eb` (batch 15's tip)
  - [ ] Task 6's full-suite run had one load flake: `test_command_crash_boundary.py`'s signal test,
    case [2], hit its 60 s subprocess timeout under xdist load. It passed alone and on the full
    rerun. A load-flaky test worth a look; batch 14's #84 had a similar native-window flake under
    load
- **Found**: batch 16's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before the harps batch builds on the same catalog)

### 87. Sound Engine: The Owner's Checks on Instrument Catalog Batch 17 — TODO
- **Goal**: confirm or overturn the calls made while batch 17 of #70 ran, and listen to its three
  aliases (`pedal harp`, `lever harp` and `folk harp`). Nothing was built and no
  sound-alike was added: the harps stayed at 7 entries (704 in all, 125 aliases, 197
  sound-alikes), with 23 waits, 3 aliases and 21 drops in the sheet's 47 rows (SHIP 0,
  SOUND_ALIKE 0, WAIT 23, ALIAS 3, DROP 21). The harps moved out of `strings.py` into `harps.py`
  and `harp_sound_alikes.py`, and `strings.py` now holds only the struck strings
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter and release is sound design unless a source is cited in the code; the folder is
  `build/instruments/harps/`):
  - [ ] The sound-alikes beside their parents: none shipped (so no `sound_changes` beside a
    parent)
  - [ ] The aliases, each of the entry it names: `pedal harp` (of
    `concert harp`), `lever harp` and `folk harp` (both of `celtic harp`); each sounds as its
    target does
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-17.tsv`; the sheet's 47 rows:
  SHIP 0, SOUND_ALIKE 0, WAIT 23, ALIAS 3, DROP 21):
  - [ ] Every WAIT (23 rows), by reason, with each row's "Engine limit, once ranged" note:
    - 18 for a sourced range:
      - the frame harps, each a sound-alike of one of the four catalog frame harps by parent rule
        2 once ranged, builder unchanged: `andean harp`, `arpa jarocha`, `cross strung harp`,
        `llanera harp` and `paraguayan harp`
      - the arched or open harps (not frame harps, though the nearest catalog frame harp is their
        parent), each a sound-alike by parent rule 2 once ranged, builder unchanged: `adungu`,
        `ennanga`, `kundi`, `ngombi` and `saung gauk` (the last four have no sourced traits: a
        skin soundboard, a trough body, a deer-hide belly and left-hand stopping are no trait,
        rule 7). The `ennanga` page's «small metallic rattling pieces» are uncited, and the plan
        named that passage as a trait to check: a call for you once the `ennanga` is ranged (if
        it is a trait, the row needs a rattle build of its own, like `ardin` and `simbi`)
      - `baroque triple harp`: a sound-alike of `triple harp` by parent rule 1 once ranged (its
        page says «creating the ''arpa tripla'' or triple harp»)
      - the harp-lutes, each a sound-alike of `kora` once ranged (rule 1: `donso ngoni` and
        `kamale ngoni` «share their basic design», `gravikord` is «based on the West African
        kora», `seperewa` is «similar to» it): `donso ngoni`, `gravikord`, `kamale ngoni` and
        `seperewa` (a pickup is no trait, boundary ruling 8; a box resonator and thumbs are no
        trait)
      - `gothic harp`: `its own build (bray pins)` once ranged, since the Grinnell record states
        the bray buzz for the instrument and no builder buzzes a string against a pin
      - `ardin`: `its own build (rattles)` (a ring plate and strings that act as jingles) and `its
        own build (a drummed resonator)` once ranged; `simbi`: the same two builds (the jingle on
        the neck and a gourd tapped with sticks); neither is a plain sound-alike (rule 7)
    - 5 because their target waits: `arpa paraguaya` (for `paraguayan harp`), `arpa llanera` (for
      `llanera harp`), `saung` (for `saung gauk`), `ombi` (for `ngombi`) and `kamele ngoni` (for
      `kamale ngoni`)
  - [ ] The module move: `harps.py` (the 7 harp entries, out of `strings.py`, comments included,
    identical to the removed section but for its `_HARP_BUILDS` name and the new `HARPS =
    _HARP_BUILDS + HARP_SOUND_ALIKES`) and `harp_sound_alikes.py` (empty). The before-and-after
    record of all 704 builds found `changed: []`. Should `strings.py` be renamed now that it holds
    only the struck strings (`STRUCK_STRINGS`)?
  - [ ] The boundary rulings, each row they moved, and the Hornbostel-Sachs codes this plan
    checked (322 and its subclasses, 323, 321.2, 321.322, 311.112, 314.22 and the suffixes): a
    harp's strings run perpendicular to its soundboard (322) and a harp-lute's at right angles to
    it across a notched bridge (323). `gravikord`'s class is `none` (the controller's ruling: 323
    had been inferred from «based on the West African kora», and no fetched page says harp-lute
    or notched bridge). The Triple harp infobox's "3.2.2" is no class (Wikipedia's, not the
    catalog's), so `baroque triple harp` is 322.212 from its «fully chromatic» text
  - [ ] Harp-lutes in harps (batch 4's hand-off and the catalog's `kora`), and `lyre` (321.2) and
    `harp guitar` (321.322) kept in harps but never a rule-2 parent: #74's question, still open
  - [ ] A harp as a sound-alike (counts, rows, tuning actions, tunings, materials, sizes, bodies
    and colour words no trait; no SHIP and no `sound_changes` in this batch; bray pins, rattles
    and a drummed resonator wait), and any row the SHIP ruling sent to the controller: none
  - [ ] The parent ruling (the source's relation first, the only way to `lyre`, `harp guitar` or
    another family; else the nearest lowest note among the four frame harps, or `kora` for a
    harp-lute), and each sound-alike's parent: none shipped; the cases once ranged are above
  - [ ] The range ruling (one source states both ends; one source's row compasses joined; levers
    and pedals as stated; a count, a width, a tuning, a hedge, an image chart or a general rule no
    range; a model's page ranges that model only; a bare name of several sizes with none standard
    waits, "became widespread" no standard), and every derived range: none was derived, since
    every row waits. The rulings that decided it:
    - `saung gauk` waits though its page says «from C3 to F5»: the Saung page attaches that
      compass to U Sa's 13-string harp, one size among the 13-, 14- and 16-string harps it names,
      with none called standard (range ruling 6), and the Koizumi archive's record 329 («range:
      G-c'''», G2-C6) is one object's (ruling 4). The first reading, that C3-F5 was on no fetched
      page, was false; the review caught it, and the row now quotes the passage and rules on it
    - `gravikord`'s «left side G1 to E5, right side C2 to E5» is solfege degrees (Sol1, Do2) from
      an uncited Tuning section, a tuning list and no compass, and the maker's «3 1/2 octave
      range» is a width
    - `paraguayan harp` and `llanera harp`: Camac's and Salvi's compasses are one model's or one
      object's; the Wikipedia pages give counts and widths («4+ to nearly 8 octaves depending on
      the maker»)
    - `triple harp`'s page gives only «about five octaves» (a width, hedged), and
      `baroque triple harp` is a version of the Welsh one («One common version»)
  - [ ] Generic, ambiguous, one-off and unsourced rows, with the words "no fetched source describes
    it" on every row whose page was not found: `celestial harp` is the one row that carries them.
    The dropped rows (21):
    - already decided (7): `aeolian harp`, `partch kithara`, `sasando`, `swarmandal`, `begena`,
      `krar` and `nyatiti`, each left as `batch-4.tsv` decided it
    - a generic term: `telyn`, `angular harp` (322.12) and `egyptian arched harp` (322.11)
    - an ambiguous name: `konghou` (a zither and two harps; `gonghu` follows it as its Korean
      name), `clarsach`, `clairseach` and `welsh harp` (below), `chang` (a Persian angular harp, the Uyghur and
      Uzbek dulcimers and an Afghan jew's harp: decided here once, for the struck strings batch)
      and `harp lute` (Light's 1795 dital harp, and the class name)
    - a one-off: `queen mary harp`
    - its target is dropped: `gonghu` (for `konghou`) and `wind harp` (for `aeolian harp`)
    - not another name for the target: `domu` (the African harp page names it beside `kundi` as a
      separate harp, and Grove's Domo entry says «Resembles kundi.»)
  - [ ] The reversals and calls in the aliases, each for you to overturn:
    - `baroque triple harp` went from ALIAS to WAIT. Rule 8 needs a source that makes two names
      one instrument, and the Triple harp page calls the Welsh triple harp «One common version»
      of the type, while the catalog's `triple harp` is the "Welsh triple harp". Once ranged it is
      a sound-alike of `triple harp` (rule 1). Cost: one alias
    - `clarsach` and `clairseach` are dropped as ambiguous names, which overturns the brief's
      expected aliases of `wire strung harp`: the Celtic harp page gives both names to the whole
      Celtic harp (old wire-strung and modern lever harps) and the Harp page gives «Celtic harp, or
      Clàrsach, a modern replica», so the sources send the names to two catalog entries. Cost: two
      aliases
    - `folk harp` stays an ALIAS of `celtic harp` but is flagged for you: the Harp page names one
      family three ways («Celtic harps ... or more generically as folk harps ... or as lever
      harps») and the Folk harp redirect goes to a section of the Harp page, not to the Celtic
      harp page as Lever harp's does. The alternative is DROP "a generic term for mid-size harps
      without pedals"
    - `welsh harp` went from ALIAS of `triple harp` to DROP as an ambiguous name, the same ground
      `clarsach` and `clairseach` were dropped on: the Triple harp page gives the name to Talbot's
      1680s large diatonic gothic-style harp with bray pins (this sheet's `gothic harp`) and, by
      the early 18th century, to the triple harp, so the sources send it to two instruments.
      Reading the later use as the name's only current one is an inference from those dates. The
      Welsh Harp disambiguation page lists only one instrument. Cost: one alias (126 to 125). The
      two reversals stand or fall together: confirm both drops or restore both aliases
    - `gothic harp`, `ardin` and `simbi` will need builds of their own once ranged (bray pins,
      rattles and a drummed resonator), but no test stops them shipping as plain sound-alikes then:
      they wait for a sourced range, not for a feature, and `HARP_HELD_BACK` covers only the waits
      other than a range, so they stay out of it. The range comes first, and a reviewer must catch
      the build need at that point
    - `pedal harp` (of `concert harp`: «also known as the concert harp») and `lever harp` (of
      `celtic harp`: the Lever harp page redirects to Celtic harp) stand; both are also
      Hornbostel-Sachs class names (322.222, 322.221), as their targets' classes are
    - `andean harp` is WAIT rather than DROP "no fetched source describes it", a judgment call:
      Wikipedia has no page (Andean_harp, Arpa_andina and Peruvian_harp return 404), and the Penn
      Museum record names its object only «Harp», from «Peru», in the «Andean» culture area
    - the `its target` rows' `alias_of` is filled here (`arpa paraguaya`, `arpa llanera`, `saung`,
      `ombi`, `kamele ngoni`), as batches 3-8 did; batches 9-16 left it empty. The form check
      allows both
  - [ ] `HARP_HELD_BACK` and the sound-change guard, the helper test that exercises them on real
    builds both ways, and the wrong-table runs that showed each failing: `HARP_HELD_BACK`
    holds nothing (every wait is for a range or for a target that waits only for a range). Task 1
    tested the helpers on a real build both ways (`names_listed` finds a real name and a real
    alias and drops a non-name; `entries_with_sound_changes` gives `['bourdon']` over the organs
    and `[]` over the harps) and showed each guard failing on a wrong table (a held-back
    `concert harp`, `lyre` missing from the existing names, a `names_listed` that ignores aliases,
    an `entries_with_sound_changes` that ignores the family, a harp entry forced to report
    `sound_changes`)
  - [ ] The two-half split as explicit lists (half A, the frame harps and the names that are no
    harp, 25 rows; half B, the open harps, harp-lutes and lyres, 22 rows), the sheets researched in
    parallel, and the shared files (the names file, the half lists and the check scripts)
    written up front by a setup agent. Tasks 3 and 5 were one code task: Task 3 shipped the four
    aliases (`aliases.py`), and Task 5 changed nothing (no commit: half B has no SHIP,
    SOUND_ALIKE or ALIAS row, so it only ran the code check, `matches 47 rows`)
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    a string buzzing against a bray pin (`gothic harp`), rattles on the instrument (`ardin`,
    `simbi`) and a drummed resonator (`ardin`, `simbi`)
- **Bugs to report** (found while building batch 17; none fixed here):
  - [ ] The 7 earlier harp entries carry no source comment for their ranges or builds
  - [ ] The catalog `concert harp` tops out at G#7, while the Pedal harp page gives Cb1 to Gb7
    (uncited): the sheet's `pedal harp` row records the lead, and the catalog's top note is
    unsourced either way
  - [ ] The ranges of `triple harp` and `celtic harp` (C2-C7 and C2-A6) have no source: the Triple
    harp page gives only «The compass of the triple harp is about five octaves» (hedged, a width),
    and the Celtic harp pages give only widths («They range from two to six octaves»). The `triple
    harp` is titled "Welsh triple harp", a version of the type its page calls «One common version»
  - [ ] The catalog `kora` is F2-C6: the Kora page's range is an image, and the Grinnell lead
    gives D2-F5 (a lead from the plan's Global Constraints, not checked further this batch)
  - [ ] `lyre` (321.2) and `harp guitar` (321.322) sit in harps, not in plucked strings (#74)
  - [ ] The Triple harp infobox's "3.2.2" is no Hornbostel-Sachs class (Wikipedia's, not the
    catalog's)
  - [ ] The Adungu page is tagged `{{AI-generated` (August 2026); the `adungu` row quotes it only
    for its class and for the sizes and tuning that keep it waiting
  - [ ] 17 DeprecationWarnings appear under `-W default`: `speech_recognition/__init__.py:7`
    imports `aifc` (removed in Python 3.13), which the `standard-aifc` backport satisfies. It is
    third-party and present before this batch (#86 records it), and a new warning would be a new
    finding
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/harps.md`, listed in #70) and the
    out-of-scope names are a later pass over this family
  - [ ] Ranging the 18 range WAITs from maker, museum and scholarly sources (each row's notes
    record what was searched; the compasses found were single models or objects, widths, tuning
    lists or one string count's compass)
  - [ ] Check the 7 earlier entries against sources (ranges and builds), starting with the bugs
    above
  - [ ] The engine changes that unblock the waits above, most rows first: the 15 range waits that
    are plain sound-alikes once ranged need no engine feature (the frame harps and harp-lutes
    above); `gothic harp` needs a string buzzing against a bray pin, and `ardin` and `simbi`
    rattles and a drummed resonator
- **Incidents and process**:
  - [ ] Batch 16 is PR #197 on batch 15 (#196)
  - [ ] The Pi hook was skipped while the Pis were unreachable, so pushes skip it
  - [ ] The two sheet halves were researched in parallel, and pushes and stacked PRs were made
    without asking (the owner, 2026-11-12, #78)
  - [ ] Saved error pages: the controller scanned earlier batches' saved pages and found 4
    Wikimedia 404 pages (batch 12: `mechawka`, `mutsianka`, `tulug`; batch 15: `octavator`). All
    four were genuine 404s saved as evidence, and every row was a DROP noting "returned 404", so no
    decision rests on a failed fetch. Each page held the machine's public IP under "Sensitive
    client information", which the controller redacted; they were in `build/`, which is
    gitignored, and no tracked file held it. New ruling: a 404 goes in the row's notes and is never
    saved. Fetch with `curl -fsS`, because plain curl saves error pages (curl without `-f` wrote
    Wikimedia's "Wikimedia Error" page with exit 0 for 4 of 25 fetches while the plan was written).
    The quote check refuses an error page
  - [ ] The controller redacted the gravikord maker's email address from a saved page
    (`build/batch-17-pages/gravikord--2.txt`: a gitignored folder, and no row quotes it). The Penn
    Museum's institutional contacts (`andean-harp--2.txt`: a digital-media address and a
    switchboard number) were left as they are: an institution's public contacts, not personal
    data
  - [ ] The reversals and re-rulings, each after a review round, so the sheet's own history holds
    the first readings: half A had one fix commit (`16ae47ed`: `baroque triple harp` from ALIAS to
    WAIT, the `arpa` aliases naming their targets, and the notes of `welsh harp`, `folk harp` and
    `andean harp`), and half B one (`b4a85dd8`: `saung gauk`'s C3-F5 quoted and ruled on,
    `gravikord`'s class made `none`, `ennanga`'s trough zither hatnote)
  - [ ] A process bug in half A's fetching: macOS's filesystem is case-insensitive, so the scratch
    copy of the `Welsh_harp` redirect was overwritten by `Welsh_Harp`, the disambiguation page;
    the quote check caught it and the page was fetched again. Anyone saving Wikipedia titles that
    differ only in case into one directory here will hit the same thing
  - [ ] The brief's Task 1 expected the move first and the guards after, each shown failing on a
    wrong table before the commit (batch 16's guards imported the moved module, so their RED was
    an ImportError); this batch did that
  - [ ] Parked minors from the reviews: the comments naming `plans/data/instrument-audit/batch-17.tsv`
    were committed before the sheet (Task 1), and the sheet landed in Task 2's commit, before the
    branch is pushed, as every earlier batch did; the sound-change test
    (`test_no_harp_sound_alike_changes_its_parents_build`) repeats the last assert of the helper
    test; `build/batch-17-code-check.py` is untracked and cited in no comment
  - [ ] The branch's base is `1ecc25d9` (batch 16's tip)
  - [ ] Task 6's full run had no load flake: `uv run pytest` passed (26244 passed, 8 skipped, 6
    xfailed, 100% coverage), the audio subset under `-W default` passed (2745 passed, 3 xfailed,
    the 17 known `speech_recognition` warnings and no other), and `nox -s lint-docs` passed on its
    own afterwards
- **Found**: batch 17's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before the struck strings batch builds on the same catalog)

### 88. Sound Engine: The Owner's Checks on Instrument Catalog Batch 18 — TODO
- **Goal**: confirm or overturn the calls made while batch 18 of #70 ran, and listen to its thirteen
  aliases (`hackbrett`, `dulcemele`, `dultzimar`, `darushimaa`, `hakkebord`, `hakkebraet`,
  `hakkebrett`, `hackbraede`, `hammarharpa`, `oprekelj`, `cimbale`, `cymbaly` and `chimbaly`, all
  of `hammered dulcimer`). Nothing was built and no sound-alike was added: the struck strings
  stayed at 5 entries (704 in all, 138 aliases and 197 sound-alikes), with 27 waits, 13 aliases
  and 27 drops in the sheet's 67 rows (SHIP 0, SOUND_ALIKE 0, WAIT 27, ALIAS 13, DROP 27). The struck strings moved out of `strings.py`, which
  was renamed `struck_strings.py`, and `struck_sound_alikes.py` holds the family's sound-alikes
  (none yet)
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter and release is sound design unless a source is cited in the code; the folder is
  `build/instruments/struck strings/`):
  - [ ] The sound-alikes beside their parents: none shipped (so no `sound_changes` beside a
    parent)
  - [ ] The aliases, each of the entry it names: `hackbrett`, `dulcemele`, `dultzimar`,
    `darushimaa`, `hakkebord`, `hakkebraet`, `hakkebrett`, `hackbraede`, `hammarharpa`, `oprekelj`,
    `cimbale`, `cymbaly` and `chimbaly` (all of `hammered dulcimer`); each sounds as its target
    does
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-18.tsv`; the sheet's 67 rows:
  SHIP 0, SOUND_ALIKE 0, WAIT 27, ALIAS 13, DROP 27):
  - [ ] Every WAIT (27 rows), by reason, with each row's "Engine limit, once ranged" note:
    - 17 for a sourced range:
      - the Sinosphere dulcimers, versions of the hammered dulcimer's spread (one rule for all
        six, the controller's ruling by sub-list: the Sinosphere sub-list's sentence describes an
        instrument spreading): `khim`, `yanggeum`, `dan tam thap luc`, and `yoochin`,
        `yangzi` and `rgyud mang` (the last three went from ALIAS to WAIT; `yangzi` and `rgyud
        mang` name the same Tibetan instrument and wait together). Once ranged each is a
        sound-alike by parent rule 1: `hammered dulcimer` for the first three; the last three sit
        on the Sinosphere list under the sentence «The santur was also spread to the [[Sinosphere]]
        via the Chinese [[yangqin]]», so their parent is `santur` (the first catalog entry that
        sentence names), and `yangqin` is the other reading
      - the versions of the santur and yangqin: `santouri` (`santur`; de:Zymbal: «abgeleitete»)
        and `hudie qin` (`yangqin`: «a form of the instrument»)
      - the struck bows: `ground bow`, `malunga`, `quijongo` and `mbulumbumba` (each a
        sound-alike of `berimbau` once ranged, rule 2 or 1; `mbulumbumba` is Kubik's «variety»,
        «identical in construction and playing technique», a relative and no alias), and the
        berimbau's three categories, `gunga`, `medio` and `violinha` (the page says «These
        categories relate to sound, not to size.»; the same pitch roles, no sizes)
      - `tambourin a cordes` and `utogardon`: range first, then `a sourced drone tuning` once
        ranged (the Marcuse and Szendrei/Grove drone passages are cited); neither has a plain
        parent, and the controller decides it at ranging (the tambourin is a struck box zither
        whose drone chord no dulcimer build makes; the utogardon, 321.322-4, has no rule-2 set)
      - range waits that will need a build of their own once ranged, and so sit outside
        `STRUCK_HELD_BACK`: `malunga` (`its own build (rattles)`, its lead paragraph carries no
        citation, range ruling 10, so a cited source is needed first), `tambourin a cordes` and
        `utogardon` (the drone chord) and `ground bow` (a pitch glide, only if its page makes it
        the instrument's sound; today the page says what a player «can» do). No test stops them
        shipping as plain sound-alikes then, so the reviewer of the ranging must catch it
    - 10 because their target waits: `ttun ttun`, `salmo`, `chicoten` and `toum toum` (for
      `tambourin a cordes`), `galinga`, `gayumba`, `tumbandera`, `tingo talango` and `angbindi`
      (for `ground bow`) and `berra boi` (for `gunga`: «others say Berra-boi», the same category;
      `alias_of` holds the target on every one, as batches 3-8 and 17 did)
  - [ ] The module move: `strings.py` renamed `struck_strings.py` (`git mv`, so its history
    follows, no re-export kept: only `registry.py` imported it, and that import changed) and
    `struck_sound_alikes.py` (empty; `STRUCK_STRINGS = _STRUCK_BUILDS + STRUCK_SOUND_ALIKES`). The
    before-and-after record of all 704 builds found `changed: []`. This answers #87's question
    ("Should `strings.py` be renamed now that it holds only the struck strings"): every other
    family module is named for its family. The earlier plans (batches 7, 9 and 17) still name
    `strings.py`, as the history of those batches
  - [ ] The boundary rulings, each row they moved, and the Hornbostel-Sachs codes this plan
    checked (311.1 and its subclasses, 312, 313, 314.1, 314.122, 314.21, 314.22, 321.322, and the
    suffixes 4, 8 and 9): a struck string is sounded by a beater in the player's hand (suffix 4:
    the hammered dulcimers, 314.122-4, and the struck bows, 311.12), and the cimbalom is a
    dulcimer. The Santur and Cimbalom infoboxes give no class (their range is an image, and no
    class is filled in), so no code is taken from them. The rows moved:
    - `fotdella` to keyboards (321.322-8: «each pedal bringing a padded hammer … like the action of
      a [[piano]]»; batch 4 had dropped it here, and it is not a one-off: the Smithsonian holds
      one and others built more)
    - `marxophone` to keyboards, flagged: the page calls the spring strips «the 15 keys» and says
      they hold «the keys against the strings», so boundary ruling 3's «unless its source calls the
      strips keys» sends it away, but the strips press straight onto the strings with no key lever.
      The other reading makes it WAIT `a sourced range` (and `its own build (a bouncing hammer)`
      once ranged). Nothing ships either way
    - `harmonic canon` was already decided (batch 4's WAIT, plucked strings), and `harmonic
      generator` (a motor-driven keyboard, ruling 7) is dropped under rule 6 because only a Make:
      post describes it
    - the ambiguous names (below) follow ruling 2: a name given to both the cimbalom and a hammered
      dulcimer is ambiguous
  - [ ] The bows batch 4 decided as plucked strings (`musical bow`, `uhadi`, `umrhubhe`, `ukeke`,
    `washtub bass`): whether the struck ones belong here, for a later pass. This batch put the bows
    its sources call struck here (`ground bow`, `malunga`, `quijongo`) and left those rows alone.
    `ground bow` is flagged: its Wikipedia sentence, cited to Kruger, says it «may be struck by a
    stick or plucked», but the Tervuren museum page says «The string is plucked with the index
    finger and the thumb. Sometimes a stick is used as a plectrum.» If plucked wins, it and its
    five alias rows (`galinga`, `gayumba`, `tumbandera`, `tingo talango`, `angbindi`) move to
    plucked strings
  - [ ] A struck string as a sound-alike (counts, courses, bridges, tunings, materials, beaters,
    dampers, sizes, bodies and colour words no trait; no SHIP and no `sound_changes` in this batch;
    rattles, a bouncing hammer, a glide and a drone chord wait), and any row the SHIP ruling sent
    to the controller: none
  - [ ] The parent ruling (the source's relation first, the first named of two; else the nearest
    lowest note among the four dulcimers, or `berimbau` for a struck bow; another mechanism to the
    controller), and each sound-alike's parent: none shipped; the cases once ranged are above
  - [ ] The range ruling (one source states both ends; one source's bridge compasses joined; a
    count, a width, a tuning, a hedge, an image chart or a general rule no range; a model's or
    object's page ranges that model only; a size named in a cited sentence ranges that size only; a
    bare name of several sizes with none standard waits; a version is not the instrument), and
    every derived range: none was derived, since every row waits. The rulings that decided it:
    - `khim`: «Standard size … Lowest note … A2 … Highest note … A4» has no citation (ruling 10),
      and it is one size, so the row waits (if the passage were cited, it would be a
      sound-alike of `hammered dulcimer` A2-A4)
    - the hammered dulcimer's page gives only «can span three [[octave]]s» (a width); Dusty
      Strings' models give D500 D3-E6, D550 G2-E6 and D650 A1-E6, model ranges (ruling 4) that
      range no bare name
    - the `yangqin`'s «slightly over four octaves» is hedged, and the `santur`'s range is an image
    - Kovács's cimbalom «AA-a'''» appears only on Wikipedia-derived and Pianoteq pages, no maker
      page
    - `quijongo`'s only compass leads are dimensions (Met 89.4.2385: 191 cm); `malunga` has no
      range anywhere; `tambourin a cordes` has string counts only («3 sets of 2 (6 total) is the
      common arrangement», uncited: once a cited source gives the six-string instrument's compass
      and calls it common, range ruling 6 lets the bare name take it, and a compass for any other
      count ranges only that version)
    - the berimbau's «122 to 127 cm» bow length is one period's length tied to a technique, no
      compass and no category's size
  - [ ] Generic, ambiguous (past or present senses), one-off and unsourced rows, with the words "no
    fetched source describes it" on every row whose page was not found. The dropped rows (27):
    - already decided (3): `chang` (batch 17), `dolceola` (batch 15) and `harmonic canon`
      (batch 4), each left as its sheet decided it
    - to keyboards (2): `marxophone` (flagged above) and `fotdella`
    - an ambiguous name (13): `celestaphone` (the Phonoharp zither, Weidman's glass-plate
      xylophone and Musser's glockenspiel), `pantaleon` (the square piano too), `santoor` (the
      catalog's `santur`, the Iraqi santur and the Indian instrument; a later pass could add
      `indian santoor`), `cimbule`, `cimbal` and `zymbal` (each given to both the cimbalom and a
      hammered dulcimer), `tsimbl` and `tambal` (one rule: each is on the Hammered dulcimer page's
      cimbalom sub-list, whose names are names of the hammered dulcimer, and each one's own English
      title redirects to Cimbalom, a catalog entry, so each names both; the alternative for either
      is an alias of `hammered dulcimer`), `tympanon` (a Greek frame drum), `tiompan` (a medieval lyre or lute), `salterio` (the
      psaltery), `zhu` (a struck wooden box, 柷, and the zither, 筑) and `kalinga` (the ground bow
      and Rwanda's dynastic drum)
    - a generic term (4): `tsymbaly` (the page lists Hutsul, semi-concert and concert types), and
      `urucungo`, `madimba lungungu` and `hungu` (terms for any musical bow: the controller's
      ruling that the Berimbau page's own text, «terms used for musical bow», outweighs its infobox
      listing; this cost the half's two aliases of `berimbau`, the same rule as batch 15's `spinet`
      and batch 17's folk-harp caution. It overrides two precedents, for you to confirm: batch 7's
      `matouqin`, where a redirect became an alias, and batch 5's `sanza` and `sansa`, where
      infobox names became aliases; `urucungo` redirects to Berimbau and is in its infobox names)
    - no fetched source describes it (5): `pianoharp`, `xinjiang yangqin` (the ambiguous-target
      ruling's row: only a news feature uses the name, in passing, and it held a journalist's email
      address, so it was deleted, below), `harmonic generator` (only a Make: post), `nondo` (also a
      one-off: its title redirects to a place) and `umbulumbumba` (no saved page holds that
      spelling)
  - [ ] The reversals and calls in the aliases, each for you to overturn:
    - The "Adaptations" list is ruled by sub-list (the controller's ruling after the final
      review, which reversed the half-A fix round's ruling that «a name on the "Adaptations" list
      is not shown to be the same instrument»; that wording contradicted the alias basis, since the
      nine shipped aliases rest on the same list). The Sinosphere sub-list («The santur was also
      spread to the [[Sinosphere]] via the Chinese [[yangqin]]») describes an instrument spreading,
      so `yoochin`, `yangzi` and `rgyud mang` stay WAIT versions, with `yanggeum` and `khim`
      (cost: three aliases; restore them as aliases of `hammered dulcimer` if you read the list as
      names). The cimbalom sub-list's heading («variants of the ''[[cimbalom]]'' from Latin
      cymbalum») is etymology, like the Graeco-Roman and Germanic headings, so its names are
      names: `cimbale`, `oprekelj` and `chimbaly` are aliases of `hammered dulcimer` again and
      `cymbaly` is one (de:Zymbal: «Namensverwandte Hackbretter heißen in Polen cymbaly»), while
      `tsimbl` and `tambal` are on the list and each one's own English title redirects to
      Cimbalom, so both DROP as ambiguous by one rule. Cost if you disagree: four aliases (WAIT
      them as sound-alikes of `cimbalom` by parent rule 1) and the two drops (aliases of `hammered
      dulcimer` or of `cimbalom`)
    - `hackbrett` and the eight other original aliases stand: de:Hackbrett says «Im englischen Sprachraum
      heißt das Hackbrett heute noch dulcimer», and the other names are national names on the
      Hammered dulcimer page's list, each on its own line (`hakkebrett` shares a stem with
      `hackbrett`). The Salzburg model is a version of the Hackbrett, and a later pass may want
      `salzburger hackbrett`
    - `santouri` is a row of its own (de:Zymbal: «derived from» the santur), not an alias of
      `santur`
    - `quijongo` is in the family on its uncited «a fourth or sixth» line (its page has no
      `<ref>`), which boundary ruling 5 names
    - `tambourin a cordes` and `utogardon` wait for a range first, then a drone tuning: the plan
      says to check the range first. The controller may want `waits_for` to be `a sourced drone
      tuning`, with the row in `STRUCK_HELD_BACK`
  - [ ] `STRUCK_HELD_BACK` and the sound-change guard, the helper test that exercises them on real
    builds both ways, and the wrong-table runs that showed each failing: `STRUCK_HELD_BACK` holds
    nothing (every wait is for a range or for a target that waits only for a range). The helper
    test is batch 17's (`test_the_harp_guards_helpers_read_real_builds`), not copied (#87's parked
    minor), and Task 1 showed each new guard failing on a wrong table (a held-back `cimbalom`,
    `berimbau` missing from the existing names, a sound-alike parents table naming `cimbalom`),
    and each helper failing when broken (a `names_listed` that returns nothing, an
    `entries_with_sound_changes` with its test inverted: `if not ...`, so `ORGANS` gave 18 names)
  - [ ] The two-half split as explicit lists (half A, the hammered dulcimers and hammered zithers,
    38 rows; half B, the struck bows, string drums and the rest, 29 rows), the sheets researched
    in parallel, and the shared files (the names file, the half lists and the check scripts)
    written up front by a setup agent. Tasks 3 and 5 were one code task: Task 3 shipped the nine
    aliases (`aliases.py`), and Task 5 changed nothing (no commit: half B has no SHIP,
    SOUND_ALIKE or ALIAS row, so it only ran the code check, `matches 67 rows`); Task 5 was
    skipped by ruling
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    rattles on the instrument (`malunga`), a hammer that bounces and restrikes while held
    (`marxophone`, if it returns here), a pitch glide through a note (`ground bow`) and a drone
    chord (`tambourin a cordes`, `utogardon`). None blocks a row today: every wait is for a range
- **Bugs to report** (found while building batch 18; none fixed here):
  - [ ] The 5 earlier struck string entries carry no source comment for their ranges or builds
  - [ ] The catalog `cimbalom` is E2-A6, while the Cimbalom page's cited Schunda tuning system
    gives «a standard pitch range of four [[octave]]s plus a major 3rd; extending from C to e′′′»
    (C2-E6); its «five fully chromatic octaves from AA to a′′′» (A1-A6) has no citation. Neither
    is E2-A6
  - [ ] The ranges of the four dulcimers are unsourced: `hammered dulcimer` D3-E6 (its page gives
    only a three-octave width and «the lowest note (often a G or D)»; Dusty Strings' D500 is D3-E6,
    a model range under ruling 4), `santur` E3-F6 (an image), `yangqin` G2-A6 (hedged: «slightly
    over four octaves»)
  - [ ] The catalog `berimbau` A2-C3 is unsourced: its page gives only letters without an octave
    («Others like to tune the instruments in 4ths (C, F, B flat) or a triad (C, E, G).»), and the
    playing sentence carries `{{citation needed}}`
  - [ ] The struck strings are not in `HARMONIC_FAMILIES`, so `test_harmonic_instruments_sound_their_note`
    does not run on them (the render test across the range does); a new struck string is not
    pitch-checked
  - [ ] Wikipedia's redirects Galinga, Gayumba, Tumbandera, Tingo_talango and Angbindi point to
    `Musical bow#Ground bow`, a section that page no longer has (Wikipedia's, not ours)
  - [ ] 17 DeprecationWarnings appear under `-W default`: `speech_recognition/__init__.py:7`
    imports `aifc` (removed in Python 3.13), which the `standard-aifc` backport satisfies. It is
    third-party and present before this batch (#87 records it), and a new warning would be a new
    finding
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/struck-strings.md`, listed in #70) and the
    out-of-scope names are a later pass over this family
  - [ ] Ranging the 17 range WAITs from maker, museum and scholarly sources (each row's notes
    record what was searched; Grove Online was behind a paywall and not reached)
  - [ ] Check the 5 earlier entries against sources (ranges and builds), starting with the bugs
    above
  - [ ] The engine changes that unblock the waits above, most rows first: the range waits that are
    plain sound-alikes once ranged need no engine feature (the dulcimer versions and the
    berimbau's categories); `malunga` needs rattles, `tambourin a cordes` and `utogardon` a drone
    chord, and `ground bow` a pitch glide if its page makes the glide the instrument's sound
- **Incidents and process**:
  - [ ] Batch 17 is PR #198 on batch 16 (#197)
  - [ ] The Pi hook was skipped while the Pis were unreachable, so pushes skip it
  - [ ] The two sheet halves were researched in parallel, and pushes and stacked PRs were made
    without asking (the owner, 2026-11-12, #78)
  - [ ] Fetches that failed, and how each was handled: Wikipedia 404s (`Hudie_qin`,
    `Butterfly_harp`, `Yoochin`, `Oprekelj`, `Hakkebord`, `Cimbale` and, in half B, `Berra-boi`,
    `Chicotén`, `Toum-toum`, `Violinha`, `Madimba_lungungu`, `Mbulumbumba` and `Umbulumbumba`) were
    noted in the rows and never saved; the redirects (en `Hackbrett`, `Tympanon`, `Tsimbl`, `Țambal`, `Tambal`)
    were fetched as redirects and then replaced by the page they point to; the NMM eMuseum record
    (403, no archive copy), Kubik 1965 on core.ac.uk (403: its text is unread) and `zgmzyq.cn` (400) were not saved. Two more come from the Task 4
    review, not the implementer's report: `magyarmuseum.org` (404) and the quijongo page (429 to
    WebFetch; it was the Met record)
  - [ ] A half-A worker deleted a saved page that held a journalist's email address (a China Daily
    feature that names "Xinjiang yangqin" in passing), rather than keeping or quoting it; no row
    quotes it, so the row's notes carry the lead only as «no fetched source describes it». No saved
    page now holds a private person's address
  - [ ] Make: magazine's press address (`build/batch-18-pages/harmonic-generator--1.txt`) was left
    as it is: a company's public contact, not personal data (the controller's ruling, by batch
    17's rule for institutions). The quote check lists the page for the controller, and no row
    quotes the address
  - [ ] The reversals and re-rulings, each after a review round, so the sheet's own history holds
    the first readings: half A had one fix commit (`40f09c37`: the eight version rows, seven from ALIAS and
    `cymbaly` from DROP, to WAIT, and the notes of `tambal` and `marxophone`; the final review's
    fix returned five of them, four to ALIAS and `tsimbl` to DROP, leaving three version rows:
    `yoochin`, `yangzi` and `rgyud mang`), and half B one (`0d01dd68`:
    notes only, the berimbau categories, the string counts, `hungu` and `harmonic generator`);
    half B's own phase 2 applied the controller's rulings on `urucungo`, `madimba lungungu`,
    `ground bow` and `zhu`
  - [ ] The folded-in fixes of Task 6: `test_the_batch_aliases_resolve`'s docstring gained its
    batch 18 sentence (the review's spec gap); the nine new alias comments in `aliases.py` first
    quoted the page's en dash, which ruff refuses in a comment, so ten lines carried `# ruff:
    ignore[ambiguous-unicode-character-comment]` and ran past 100 columns; the final review's fix
    removed the pragmas and writes each en dash as a hyphen, as every earlier batch does, with a
    note in the batch 18 header comment; and `berra boi`'s notes say «These categories
    relate to sound, not to size.» where they said "the same size"
  - [ ] Parked minors from the reviews: the comments naming `plans/data/instrument-audit/batch-18.tsv`
    were committed before the sheet, and the sheet landed in Task 2's commit, before the branch is
    pushed, as every earlier batch did; the batch-18 check scripts in `build/` are untracked and
    cited in no comment
  - [ ] The controller's brief claimed batch 15 sent dulcimers here; it did not (#70)
  - [ ] The gap: no tracked test stops one of the 27 WAIT names from being added later as an alias;
    only the untracked `build/batch-18-code-check.py` does
  - [ ] The branch's base is `9a8dcfbe` (batch 17's tip)
  - [ ] Task 6's full run had no load flake: `uv run pytest` passed (26256 passed, 8 skipped, 6
    xfailed, 100% coverage, no warnings), the audio subset under `-W default` passed (2757 passed,
    3 xfailed, the 17 known `speech_recognition` warnings and no other), and `nox -s lint-docs`
    passed on its own afterwards
- **Found**: batch 18's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before the next batch builds on the same catalog)

### 89. Sound Engine: The Owner's Checks on Instrument Catalog Batch 19 — TODO
- **Goal**: confirm or overturn the calls made while batch 19 of #70 ran, the last batch, and
  listen to its three sound-alikes (`soprillo saxophone`, of `sopranino saxophone`; `tubax in eb`,
  of `contrabass saxophone`; `heckelphone clarinet`, of `alto saxophone`) and its two aliases
  (`soprillo` and `sopranissimo saxophone`, of `soprillo saxophone`). Nothing new was built: the
  saxophones grew from 8 to 11 entries (707 in all, 140 aliases and 200 sound-alikes), with 3
  sound-alikes, 16 waits, 2 aliases and 7 drops in the sheet's 28 rows (SHIP 0, SOUND_ALIKE 3,
  WAIT 16, ALIAS 2, DROP 7). `winds.py` was renamed `saxophones.py`, and
  `saxophone_sound_alikes.py` holds the family's sound-alikes. The expansion's close (#70's
  closing summary, the design's status line and the final audit) is here for you to rule on too
- **Listen** (render with `uv run python -m scripts.make_instrument_demos build/instruments`; every
  level, filter and release is sound design unless a source is cited in the code; the folder is
  `build/instruments/saxophones/`):
  - [ ] The sound-alikes beside their parents (none carries `sound_changes`, so each is its
    parent's build over its own range): `soprillo saxophone` (Ab4-Db7) beside `sopranino
    saxophone` (Db4-Ab6); `tubax in eb` (Db1-A3) beside `contrabass saxophone` (Db1-Ab3);
    `heckelphone clarinet` (D3-C6) beside `alto saxophone` (Db3-Ab5): its C6 top is above its
    parent's Ab5, which the rules allow (the render test covers its own range)
  - [ ] The aliases, each of the entry it names: `soprillo` and `sopranissimo saxophone` (both of
    `soprillo saxophone`); each sounds as its target does
- **Calls to confirm** (each in `plans/data/instrument-audit/batch-19.tsv`; the sheet's 28 rows:
  SHIP 0, SOUND_ALIKE 3, WAIT 16, ALIAS 2, DROP 7):
  - [ ] Every WAIT (16 rows), by reason, with each row's "Engine limit, once ranged" note:
    - 15 for a sourced range:
      - versions and keys of the saxophone, each a plain sound-alike once ranged: `c soprano
        saxophone` (the page's «standard vintage horn» B♭3 to E♭6 is in a paragraph with no
        citation, range ruling 10; once ranged, of `soprano saxophone`), `f mezzo soprano
        saxophone` (of `alto saxophone`, rule 1: «Its size and [[timbre]] are similar to the
        E{{flat}} alto»), `g mezzo soprano saxophone` (of `soprano saxophone`; not a one-off: Lovano
        «ordered one for himself»), `saxello` and `curved soprano saxophone` (of `soprano
        saxophone`; the curved soprano is a version, the page's «variants», not an alias), and
        `grafton alto saxophone` (an acrylic alto, of `alto saxophone`)
      - `tubax`: two ranged sizes (E♭ and B♭, each its own row) and a C size with no range, none
        called standard (range ruling 6)
      - `subcontrabass saxophone`: a range wait, not `sub-audio fundamentals` (the range is
        checked first): its makers' models disagree (Stainer's compact model A0-E3, and the page
        contradicts itself; Stainer's GWR model Ab0-E3; the B♭ tubax Ab0-E3; Eppelsheim's custom
        instrument a written range with no transposition; the uncited infobox G), and no source
        calls one standard. Once ranged it is held back if its low note is below A0
      - `octavin` (the page's «The (written) range of the octavin is from G♯<sub>3</sub> to
        G<sub>6</sub>.» has no transposition, and its citation, Hartenberger, gives no such range; three keys, none standard; once ranged, of
        `soprano saxophone` by rule 1 from Langwill's «has a tone somewhat like that of the soprano
        saxophone but less pleasant», a hedge you may read as rule 2), `heckel clarina` (both
        sources draw the compass as images, and two sizes, neither standard) and `sarune etek`
        (solfège and note letters with no octaves, and a figure)
      - range waits that will need a build of their own once ranged, and so sit outside
        `SAXOPHONE_HELD_BACK`: `aulochrome` (two pipes sounding together: «a new polyphonic and
        chromatic woodwind instrument»), `slide saxophone` (a pitch LFO, portamento between notes,
        only if a source makes the slide its way of changing pitch; the NMM record says only
        «Pitch names stamped on slide.» and «24 individual holes. 2 octave keys.»), `conn o sax`
        (the Met article: «a pronounced bulb-shaped bell reminiscent of the English horn» and «The
        result was a unique timbre»),
        `contralto saxophone` (Jim Schmidt's «The bell of the contralto has been slightly enlarged
        in proportion to other saxes.» and «I have found that this increases the warmth and
        roundness of tone»), and the leads in `heckel clarina` (EB1911's «The timbre resulting from
        the combination of conical bore and single-reed mouthpiece has in the lowest register
        affinities with the ''cor anglais'', in the middle with the saxophone, and in the highest
        with the clarinet.», a timbre that changes by register) and `sarune etek` (its angar-angar,
        «bentuknya seperti corong dan fungsinya adalah untuk membesarkan suara»: a funnel bell made
        to enlarge the sound). No test stops them shipping as plain sound-alikes then, so the
        reviewer of the ranging must catch it
    - 1 for sub-audio fundamentals: `bb tubax` (the maker's «sounding A b 0-E 3», below A0), held
      back in `SAXOPHONE_HELD_BACK`
  - [ ] The module move: `winds.py` renamed `saxophones.py` (`git mv`, so its history follows, no
    re-export kept: only `registry.py` imported it, and that import changed) and
    `saxophone_sound_alikes.py` (`SAXOPHONES = _SAXOPHONE_BUILDS + SAXOPHONE_SOUND_ALIKES`). The
    before-and-after record of all 704 builds found `changed: []`, and Tasks 3 and 5 repeated it.
    This answers #86's question ("Should `winds.py` be renamed now that it holds only the
    saxophones?"): every family module is now named for its family. The earlier plans and #70 to
    #88 still name `winds.py`, as the history of those batches
  - [ ] The boundary rulings, each row they moved, and the Hornbostel-Sachs codes this plan
    checked (422.2, 422.21, 422.211, 422.212, 422.22, 422.3, 412.13, the suffixes 8 and 9, and -71
    from `Template:Infobox saxophone` only): a saxophone is a single reed on a conical bore
    (422.212), a cylindrical one is a clarinet. The template trap: every page built on `{{Infobox
    Saxophone}}` shows 422.212-71 rendered, but its raw wikitext holds no class, so each row that
    writes 422.212-71 saved the template's raw text and quotes it there; the class is the
    template's default for every page using it (the Aulochrome page uses it for two pipes), so it
    is no evidence of a row's bore. The Grafton page has no infobox and names no class (hs none).
    Batch 14's `sarune etek` writes `422.212.2`, a subclass the fetched list does not hold
    (422.212 has none on it); this batch's row writes 422.212 (below, a bug). No row moved family:
    the four xaphoon names stayed as batch 14 decided them (cylindrical, clarinets)
  - [ ] A saxophone as a sound-alike (keys, sizes, shapes, materials, keywork, makers and colour
    words no trait; no SHIP and no `sound_changes`; two pipes, a slide that replaces the keys and a
    stated bore or bell effect wait), and the rows the SHIP ruling sent to the controller:
    - `tubax in eb` stays a sound-alike (the controller's ruling): its two bore-to-sound lines,
      the Tubax page's «The tubax also has a more focused and compact [[timbre]] than that of the
      full-sized saxophones.» and the Saxophone page's «reedier» tone, are uncited (range ruling
      10), and «reedier» is a colour word; the cited bore passages state no effect on the sound.
      If you count the narrow bore as a trait, the row becomes WAIT `its own build (a narrower
      bore)` and joins the guard
    - `heckelphone clarinet` stays a sound-alike: its page's «wide conical bore» is named, but no
      fetched source states its effect on the sound, so the bore is no trait (as batch 11's
      `contraforte`). Its range rests on Wikipedia's line cited to Marcuse (1975), whose book could
      not be opened (every archive.org copy is access-restricted, and search-inside returned 403);
      range ruling 10 accepts a citation whose work cannot be reached
    - `conn o sax`, `contralto saxophone`, `heckel clarina` and `sarune etek`: the bell, bore and
      register leads above, ruled only once each row is ranged
  - [ ] The parent ruling (the whole instrument's relation first, never a part's or a pitch's;
    else the nearest lowest note among the 8 saxophones, for every conical single reed), and each
    sound-alike's parent: `soprillo saxophone` of `sopranino saxophone` by rule 2 (the page relates
    it to the soprano only by pitch and shape: sopranino Db4 is 7 semitones from Ab4, soprano Ab3
    is 12); `tubax in eb` of `contrabass saxophone` by rule 1 («derived from the contrabass
    saxophone», «a modified [[contrabass saxophone]]»; rule 2 agrees); `heckelphone clarinet` of
    `alto saxophone` by rule 2 (D3 against Db3, 1 semitone; «essentially a wooden [[saxophone]]»
    names no catalog entry, and Heckel's line about the alto is a contrast)
  - [ ] The range ruling (a written range only with its own source's transposition; a general
    rule, an image or a `<score>` chart no range; altissimo and optional keys' extremes left out;
    the makers' ruling; a model's or period's page ranges that one only; a bare name of several
    sizes with none standard waits; below A0 waits), and every derived range, note by note:
    - `soprillo saxophone` Ab4-Db7: Eppelsheim's «written range Bb 3» to «Eb 6, sounding Ab4-Db 7»
      (the maker's own sounding notes; the Soprillo page's «The soprillo in B{{flat}} sounds a [[minor seventh]]
      higher than written.» agrees: Bb3 up 10 semitones is Ab4, Eb6 is Db7). The makers' ruling: «the only
      piccolo-sized saxophone manufactured», built to order, so the model is the instrument
    - `tubax in eb` Db1-A3: Eppelsheim's «range Bb 3-F#6, sounding Db1-A 3» (Bb3, MIDI 58, minus
      33 is Db1; F#6, MIDI 90, minus 33 is A3); the altissimo «written D 7, sounding F 4» is left
      out as an extension; one maker, as batch 11's `contraforte`
    - `heckelphone clarinet` D3-C6: the page's sounding range, cited to Marcuse, for an
      instrument in B♭ «written a whole tone higher»; the row takes the sounding notes
  - [ ] The names-list, player's-name, ambiguous (past or present senses), one-off and unsourced
    rows, with the words "no fetched source describes it" on every row whose page was not found
    (none here: every row's page was found). Versions are not aliases (`curved soprano saxophone`,
    `saxello`). The dropped rows (7):
    - a player's name (2): `stritch` and `manzello`, Kirk's names for his own straight Buescher
      alto and his modified Saxello (the Saxophone page: «The Buescher straight alto was a
      production instrument while the manzello was in fact a ''Saxello'' with a custom-made large
      bell and modified keywork.»). Cost if
      you disagree: `stritch` an alias of a future `straight alto saxophone` row
    - an ambiguous name (1): `tarogato` (the page and its cited maker, Stephen Fox, give the name
      to the modern single reed and to the historical double-reed shawm: «the original
      tárogató», «the historical tárogató»). Batch 14 read it as the modern instrument only to set
      its family; this batch decides the name. A later pass may add `modern tarogato` (Fox: the
      B♭ soprano is «by far the most common type», «roughly described as a soprano saxophone»)
    - already decided (4): `xaphoon` (`batch-14.tsv` WAIT a sourced range), `maui xaphoon`,
      `pocket sax` and `xaphoon de catalunya` (each `batch-14.tsv` WAIT its target, `xaphoon`),
      each DROP "Already decided" here, as #70 binds them
  - [ ] The batch-14 hand-offs decided here (the controller's ruling): batch 14 dropped five
    conical single reeds to the saxophones, and this batch decides each: `tarogato` (DROP, an
    ambiguous name), `octavin`, `heckel clarina` and `sarune etek` (each WAIT a sourced range) and
    `heckelphone clarinet` (a sound-alike of `alto saxophone`)
  - [ ] `saxonette` and `venova` get no row here (the controller's ruling): `batch-14.tsv` decided
    each as a clarinet (both WAIT), so neither is a saxophone candidate and neither is decided
    again
  - [ ] `tubax in eb`'s title is 'Tubax in E-flat' (the final review), spelled as the catalog's
    other titles spell a flat ('E-flat clarinet', 'Soprano trombone in B-flat'), though the plan's
    Global Constraints asked for 'E♭'; `batch-19.tsv`'s title column matches
    - flagged: `sopranissimo saxophone` stays an ALIAS of `soprillo saxophone` (the controller's
      ruling): the page's «or rarely '''sopranissimo saxophone'''» is a names sentence, and van
      Linthout's 1960 «prototype ''sopranissimo''», the same page's «The first playable piccolo
      saxophone» at the same pitch, is an early instance of the same instrument, not a second one
      (unlike batch 17's `welsh harp`, dropped for naming two different harps). Cost if you disagree: under a stricter ambiguous ruling
      it is DROP
    - `aulochrome` waits rather than drops as a one-off: the Aulochrome page says «first prototyped in
      1999» and Playbill (2005) says «Louis is hoping to generate enough interest in the instrument
      to find a sponsor and put the aulochrome into production.», but no
      source says it was never made as a type. Cost if you disagree: a DROP (one-off)
    - `soprillo saxophone`'s bore comes from the family page (the controller's ruling): the
      Soprillo page names no bore, only that it is a [[saxophone]], and the Saxophone page's
      cited «conical body» is the family's, which covers each member it names. Cost if you
      disagree: WAIT `a sourced reed and bore`
  - [ ] `SAXOPHONE_HELD_BACK` and the sound-change guard, the helper test that exercises them on
    real builds both ways, and the wrong-table and broken-helper runs that showed each failing:
    `SAXOPHONE_HELD_BACK` holds `bb tubax` (sub-audio fundamentals) and nothing else (the plan
    expected `subcontrabass saxophone` there too; it waits for a range first, above). The helper
    test is batch 17's (`test_the_harp_guards_helpers_read_real_builds`), not copied. Task 1
    showed each new guard failing on a wrong table (a held-back `alto saxophone`,
    `contrabass saxophone` missing from the existing names, a sound-alike parents table naming
    `tenor saxophone`) and each helper failing when broken (a `names_listed` that returns
    nothing; an `entries_with_sound_changes` with its test inverted, which gave 17 organ names)
  - [ ] The two-half split as explicit lists (half A, the saxophones' 14 candidates and 5 alias
    names, 19 rows; half B, the other conical single reeds and the xaphoon's already-decided names,
    7 candidates and 2 alias names, 9 rows), the sheets researched in parallel (half B drafted to
    `build/` and appended after half A's commit), and the shared files (the names file, the half
    lists and the four check scripts) written up front by a setup agent. Tasks 3 and 5 ran as one
    code task with a commit each (Task 3 half A's two sound-alikes and two aliases, Task 5 half B's
    `heckelphone clarinet`); no code task was skipped by ruling
  - [ ] Engine features named beyond the spec's table, for its "What the engine cannot make yet":
    two pipes sounding together (`aulochrome`), a bell that changes the tone (`conn o sax`,
    `contralto saxophone`, `sarune etek`) and a timbre that changes by register (`heckel
    clarina`). None blocks a row today: each waits for a range first
  - [ ] **The expansion's close** (#70's closing summary):
    - Whether to mark the design's status DONE: its status line now says every family the audits
      cover has had its batch (batches 1 to 19) and points at #70 and #71 to #89, but the status
      word is still DESIGN, the owner's call
    - Whether to add the engine features the batches named to the spec's "What the engine cannot
      make yet" table, which this batch did not edit: #70 gathers them from every batch's WAIT
      reasons (batches 1 to 19), each feature absent from the table with its row count (an
      amplitude LFO 15, a pitch moving through a phrase 8, a buzzing membrane 7, filter resonance
      7, ...), and the features #76 to #89 named for rows that wait for something else first
    - Whether to turn the final audit into a tracked test (#88's gap: no tracked test stops a WAIT
      or DROP name from being added later as an alias or entry; only the untracked
      `build/batch-*-code-check.py` scripts and `build/batch-19-final-audit.py` do)
    - The final audit's standing counts, corrected by the final review: SHIP 76 and DROP 376
      (the first run printed SHIP 73 and DROP 379). The audit now keeps an earlier SHIP,
      SOUND_ALIKE or ALIAS standing when a later sheet drops the same name, as it already did for
      a DROP whose notes begin "Already decided". The cross-check: 76 SHIP + 200 SOUND_ALIKE =
      276, and 707 - 276 = 431, the catalog's pre-expansion entries
    - The final audit's review list: the 5 standing DROPs the code holds, each a pre-expansion
      entry whose row drops the name as a candidate because the catalog already had it
      (`vibraslap`, `cuica` and `whip`, batch 2; `singing bowl`, batch 5; `sackbut`, batch 6, the
      brass sackbut and not Le Caine's electronic sackbut). Each row's words are quoted in #70;
      none contradicts the code, so each stands. The open hand-offs in #70 are the audit's keyword
      heuristic, a list to read, not a count to trust
    - The three names the expansion's own sheets shipped and a later sheet re-listed and dropped,
      whose standing status is SHIP (#70 quotes each later row's DROP note): `whip crack`
      (`batch-1.tsv` SHIP; `batch-2.tsv` DROP «Already in the catalog in noise makers (the noise
      makers row above is its entry)»), `thunder sheet` (`batch-2.tsv` SHIP; `batch-3.tsv` DROP
      «Already shipped in sound effects (rule 4)») and `ocean drum` (`batch-2.tsv` SHIP;
      `batch-3.tsv` DROP «Already shipped elsewhere: the catalog ocean drum is in the sound
      effects family (batch 2).»)
    - [ ] Whether those three later rows (`batch-2.tsv`'s `whip crack`, `batch-3.tsv`'s `thunder
      sheet` and `ocean drum`) should have their notes marked "Already decided", as later
      batches mark a re-listed name, so the sheets themselves say the earlier SHIP stands
- **Bugs to report** (found while building batch 19; none fixed here, except the docstring below):
  - [ ] The 8 earlier saxophone entries carry no per-entry source comment for their ranges or
    builds (the module docstring names Adler and the Vienna Symphonic Library in general), and
    no `low_pass` value has a source
  - [ ] `baritone saxophone` starts at C2, the low-A model's sounding low note, while the B♭-keyed
    instrument sounds D♭2 (the audit's «baritone Eb: Db2-Ab4 (low-A models reach A1)», written)
  - [ ] The catalog's tops are the written F6 top (`soprano saxophone` Eb6, `alto saxophone` Ab5,
    and so on), while makers give F♯6. The Soprano saxophone page gives «a range from concert
    A{{music|flat}}<sub>3</sub> to E<sub>6</sub>» for models with a high F♯ key, cited only to a
    blog (Bandestration), so it is a lead, not a source
  - [ ] `contrabass saxophone` (Db1-Ab3): its page's infobox says «All current models sold extend
    from a low A to a high F{{sharp}}.», written letters with no octaves and uncited; if low A is standard
    on current models, the sounding bottom is C1 rather than Db1. A lead to check
  - [ ] `batch-14.tsv`'s `sarune etek` row writes hs `422.212.2`, a subclass the fetched
    Hornbostel-Sachs list does not hold (batch 19's row writes 422.212)
  - [ ] `batch-14.tsv`'s `tarogato` notes call the historical tárogató «the double reeds' (batch
    11's hand-off)», but no row in `batch-11.tsv` or any other sheet names it: that hand-off was
    never recorded, and it is a lead for a later double reeds pass (#70)
  - [ ] Wikipedia's Octavin range line (G♯3 to G6, cited to Hartenberger) is not supported by
    its citation (Wikipedia's, not ours)
  - [ ] 17 DeprecationWarnings appear under `-W default`: `speech_recognition/__init__.py:7`
    imports `aifc` (removed in Python 3.13), which the `standard-aifc` backport satisfies. It is
    third-party and present before this batch (#87 and #88 record it), and a new warning would be
    a new finding
- **Follow-ups**:
  - [ ] The audit's gaps (`plans/data/instrument-audit/saxophones.md`, listed in #70) and the
    out-of-scope names are a later pass over this family
  - [ ] Ranging the 15 range WAITs from maker, museum and scholarly sources (each row's notes
    record what was searched; the NMM records 7753 and 4094 returned 403 with no archive copy)
  - [ ] Check the 8 earlier entries against sources (ranges and builds), starting with the bugs
    above
  - [ ] The engine changes that unblock the waits, most rows first: sub-audio fundamentals for
    `bb tubax` (and `subcontrabass saxophone` if its sourced range reaches below A0); then, once
    ranged, a second pipe (`aulochrome`), a bell or register-dependent timbre (`conn o sax`,
    `contralto saxophone`, `heckel clarina`, `sarune etek`) and portamento (`slide saxophone`).
    The other range waits are plain sound-alikes once ranged and need no engine feature
- **Incidents and process**:
  - [ ] Batch 18 is PR #199 on batch 17 (#198)
  - [ ] The Pi hook was skipped while the Pis were unreachable, so pushes skip it
  - [ ] The two sheet halves were researched in parallel, and Tasks 1, 2 and 4 ran in parallel;
    pushes and stacked PRs were made without asking (the owner, 2026-11-12, #78)
  - [ ] Fetches that failed, and how each was handled: the Met article on the Conn-O-Sax returned
    429, so its Internet Archive copy was saved and quoted; the NMM records 7753 (Conn-O-Sax) and
    4094 (F mezzo-soprano) returned 403 with no archive copy and were not saved or used; the NMM
    slide saxophone record returned 403 and its archive copy was saved; every archive.org copy of
    Marcuse is access-restricted (search-inside 403), so `heckelphone clarinet`'s cited work was
    not reached; the Albuquerque eMuseum record returned 403 to the Task 2 reviewer. The
    redirects (Conn-O-Sax, Contralto saxophone, Saxello, Slide saxophone, Stritch (saxophone),
    Manzello and Sopranissimo saxophone) were not saved; each row saved and quoted the page they
    point to. The audit's «Wikipedia title Soprillo redirects to Sopranissimo saxophone in
    mirrors» runs the other way on Wikipedia today
  - [ ] Personal data: the controller redacted a sole trader's email address and phone number
    (`contralto-saxophone--2.txt`, Jim Schmidt's archived page for JS Engineering, his one-man
    business: a sole trader's contacts count as a private person's) and the aulochrome maker's
    entity-encoded email addresses (`aulochrome--2`, `--3` and `--5`). The institutions' and
    companies' public contacts were kept (Heckel's `mail@heckel.de`, the Horniman's enquiry
    address, Eppelsheim's `mail@eppelsheim.com`, the record label's address). No row quotes any
    contact, and the saved pages are in the gitignored `build/`
  - [ ] A reviewer wrote its review file at the repository root; the controller moved it into the
    workspace, and nothing of it was committed
  - [ ] The folded-in fixes of Task 6 (parked minors from the reviews): `tarogato`'s notes gained
    a clause saying batch 14 read the row as the modern instrument only to set its family, while
    this batch decides the name and the page gives it to both instruments; `curved soprano
    saxophone`'s once-ranged rule-1 parent quotes the page («All straight and curved variants
    have the same keys and range as the traditional straight soprano») where it paraphrased it.
    The form, quote and code checks were run again after both (`bad: []`, `bad: []`, `matches 28
    rows`)
  - [ ] The stale docstring clause Task 6 removed: `saxophones.py`'s ranges sentence said «folk
    instruments' are typical of the common keys», but no folk instrument has been in the module
    since batch 16 moved the free reeds out
  - [ ] The gap: no tracked test stops one of the 16 WAIT names from being added later as an
    alias; only the untracked `build/batch-19-code-check.py` and the final audit do (#70's close
    asks whether to track it)
  - [ ] The branch's base is `6503a1e1` (batch 18's tip)
  - [ ] Task 6's full run had no load flake: `uv run pytest` passed (26272 passed, 8 skipped, 6
    xfailed, 100% coverage, the cocoa run's driver comparison 0 differences, no warnings), the
    audio subset under `-W default` passed (2773 passed, 3 xfailed, the 17 known
    `speech_recognition` warnings and no other), and `nox -s lint-docs` passed on its own
    afterwards. A first full run was given `-p no:cacheprovider`, which the native child run then
    refused (`Unknown config option: cache_dir`, exit 3, no tests ran there); the plain command was
    run again and passed. The final audit printed `bad: []` both times it ran
- **Found**: batch 19's reviews (2026-11-13)
- **Status**: TODO
- **Priority**: Medium (before any later pass builds on the same catalog)

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
