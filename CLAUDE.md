# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GlitchyGames is a Python 3.14 game engine built on Pygame with an event-driven architecture. The project includes a full-featured pixel art editor called Bitmappy and supports animation, UI widgets, and physics-based game objects.

The engine's source is `src/glitchygames/` (members: `src/games/`, `src/demos/`, `src/apps/`;
plans/2026-10-24-workspace-packages.md). Nothing at the repository root is importable as our
package: tests and tools import the installed engine (`uv sync`: editable, its `.pth` naming
`src/`; nox: not editable). Repository paths in these docs are written from the repository root
(the engine at `src/glitchygames/`); finished plans and resolved BUGS.md entries name the
locations as they were when written (before #105, the engine was the root-level `glitchygames`
directory). A script that imports `scripts.*` runs as `uv run python -m scripts.<name>` from the
root.

## Development Setup

```bash
# Install dependencies (uv manages the virtual environment automatically); --all-packages
# installs the workspace members too (src/games/mr-muncher). A plain `uv sync` keeps them as
# well: the root's dev dependency group (installed by default) names every member as a
# workspace source (tests/test_workspace_config.py checks it)
uv sync --all-packages

# Install with dev extras (for testing/linting)
uv sync --extra dev --all-packages

# Install with all extras
uv sync --all-extras --all-packages

# Optional: trust the project's .envrc (direnv); on entering the repo it runs
# `uv sync --all-extras --all-groups --all-packages` (the locked versions) and, on macOS,
# installs PulseAudio with Homebrew (sound from the Linux test container, nox -s test-linux-x11)
direnv allow

# Upgrade dependencies deliberately, then review the uv.lock change
uv sync --upgrade --all-extras --all-groups --all-packages
```

## Common Commands

### Testing
```bash
# Run all tests with coverage (100% minimum required). Outside CI this also runs the suite on
# the native SDL driver (macOS cocoa) and fails on any frame that differs (see Testing Guidelines)
pytest

# Fast iteration: the dummy driver only, no native run or comparison
pytest --dummy-only

# Run specific test file
pytest tests/test_specific.py

# Run tests matching pattern
pytest -k "test_pattern"

# Run tests with parallel execution
pytest -n auto

# Run performance benchmarks only
pytest --benchmark-only
```

### Linting and Type Checking
```bash
# Format code with ruff
ruff format src tests scripts noxfile.py

# Check and fix import ordering
ruff check --select I --fix src tests scripts noxfile.py

# Run full ruff linting
ruff check src tests scripts noxfile.py

# Type checking with basedpyright (configured in pyrightconfig.json)
basedpyright
```

### Nox Sessions (Automated Testing Pipeline)
```bash
# --- Aggregate sessions ---
nox -s format              # Run ALL formatters (code + TOML)
nox -s lint                # Run ALL linters (code, docs, YAML, TOML, CI, deps, dead code, CVEs)

# --- Individual format sessions ---
nox -s format-code         # Format Python code (ruff format + import sorting)
nox -s format-toml         # Format TOML files (taplo)

# --- Individual lint sessions ---
nox -s lint-code           # Lint Python code (ruff)
nox -s lint-docs           # Lint documentation (mkdocs strict build)
nox -s lint-yaml           # Lint YAML files (yamllint)
nox -s lint-ci-config      # Validate all CI configs (CircleCI + GitHub Actions)
nox -s lint-circleci       # Validate CircleCI config only
nox -s lint-github-actions # Lint GitHub Actions workflows only
nox -s lint-toml           # Lint TOML files (taplo)
nox -s lint-dependencies   # Check dependency issues (deptry)
nox -s lint-dead-code      # Detect dead code (vulture)
nox -s lint-cves           # Audit dependencies for known CVEs (pip-audit)

# --- Static type analysis ---
nox -s static-analysis              # Run ALL type checkers (basedpyright + ty)
nox -s static-analysis-basedpyright # Run basedpyright only
nox -s static-analysis-ty           # Run ty only

# --- Testing ---
nox -s test                # Run tests with coverage
nox -s performance-test    # Run performance benchmarks
nox -s timer-report        # Report this machine's timer accuracy: VM?, CPU share, sleep wakes (diagnostic)
nox -s replay-metrics      # Rebaseline every golden replay + bundled demo headless; append run-ledger rows to test-results/replay-metrics/pending.jsonl (skips this commit+machine; `-- --force`, `-- --allow-dirty`, `-- --only TEXT`)
nox -s test-linux-x11      # Tests on Linux in Docker: X11 windows on XQuartz, sound on the Mac's PulseAudio (starts it; `pulseaudio --kill` stops it; macOS)
nox -s compare-drivers     # On demand N-way matrix: dummy x2, native, x11-macos, x11-linux (whatever runs here); `-- --drivers a,b`, `-- tests/x`; report test-results/driver-comparison/nox/matrix.md
nox -s build-sdl-x11       # Build SDL with x11 for macOS (cached in ~/Library/Caches/glitchygames/sdl-x11; SDL_DYNAMIC_API loads it) and check it on XQuartz

# --- Code quality ---
nox -s code-complexity     # wily: the working tree's changes against HEAD (history measured in a temporary worktree, never in yours); `-- --graphs` generates docs/quality/graphs/ (gitignored), `-- --rank` ranks files

# --- Security ---
nox -s security-scan       # Run ALL security scans (bandit + safety)
nox -s bandit-scan         # Run bandit only
nox -s safety-scan         # Run safety only

# --- Build / Package ---
nox -s build               # Build binary (PyInstaller) + wheel
nox -s build-binary        # Build standalone Bitmappy binary only
nox -s build-wheel         # Build wheel (.whl) only
# build, build-wheel, build-binary and test stamp the engine's commit into the package first
# (src/glitchygames/_build_info.json, removed after; src/glitchygames/build_info.py): test's installed
# copy is not editable, so the stamp is how it names its commit

# --- Docs ---
nox -s docs-deploy         # Fetch gh-pages, replay-metrics (--skip-dirty), build, publish to https://terrysimons.github.io/glitchygames/ (pushes gh-pages, then clears published pending rows; `-- --build-only`: no push)
# CircleCI runs it after every merge to main (job deploy-docs: once the macOS job passes, one at a time,
# `-- --no-measure`: CI timings would be noise in the run ledger), pushing with a deploy key
# (pipeline parameter DOCS_DEPLOY_KEY_FINGERPRINT)
nox -s docs-serve          # Serve the docs locally (same strict build, graphs included) at http://127.0.0.1:8000/glitchygames/
# Every mkdocs build generates the complexity graphs first when HEAD changed, then the performance
# graphs (published run ledger from origin/gh-pages + pending rows; hook: scripts/mkdocs_hooks.py)
# After every build the hook empties griffe's and mkdocstrings' caches, which kept each
# `mkdocs serve` rebuild alive (about 330 MB each; BUGS.md #213)
```

### Running Bitmappy (Pixel Art Editor)
```bash
# Run with default settings
uv run bitmappy

# Legacy pygame timing backend (the default is auto: the fast backend with this machine's
# measured sleep delay; see Frame Pacing)
uv run bitmappy --timer-backend=pygame

# Custom target FPS
uv run bitmappy --target-fps=120   # default is 60.01; --target-fps 0 for uncapped

# Enable timer jitter logging
uv run bitmappy --timer-backend=fast --log-timer-jitter

# Windows: Enable 1ms timer resolution
uv run bitmappy --timer-backend=fast --windows-timer-1ms
```

### Example Games
`uv run paddleslap`, `brave-adventurer`, `brave-adventurer-papyrus`, `clockwork-keep`,
`mr-muncher` (a maze chase at the movies, its own workspace package `src/games/mr-muncher/`) and
`drawing-fire` (a pencil-on-paper stick-figure battle, `src/glitchygames/examples/drawing_fire/`:
computer battles that one or two local players join with START or Enter; its new mechanic is
swatches, recolouring a sprite by palette swap; docs/games/drawing_fire.md) start the example
games.

## Architecture Overview

### Core Engine Components

**GameEngine** (`src/glitchygames/engine/__init__.py`)
- Singleton orchestrator extending `EventManager`
- Handles pygame initialization, display management, event routing
- Bootstraps command-line arguments for all games
- Pre-computes `EVENT_HANDLERS` dict for O(1) event dispatch

**SceneManager** (`src/glitchygames/scenes/__init__.py`)
- Singleton running the main game loop; each frame (`_run_scene_frame`), in order:
  1. **Begin**: `camera.begin_frame()` (clears the camera's manual-update and shake-advance flags)
  2. **Logic**: `Scene.dt_tick(dt)` (game logic, physics and collision)
  3. **Event Processing**: Route pygame events through GameEngine
  4. **Frame services**: shake and rumble (so positioning sees this frame's WORLD shake)
  5. **Aim**: move the camera toward `Scene.camera_target()` (skipped when the scene was switched
     mid-frame, e.g. resuming from pause: that scene ran no logic this frame)
  6. **Position**: place world-space sprites from the camera and cull them (see World Space)
  7. **Render**: `Scene.update()` (visual-only work), then `LayeredDirty.draw()`
  8. **Still-camera shake**: if nothing advanced the camera's WORLD shake this frame (no aim, no
     game `camera.update()`), `camera.advance_shake(dt=...)` advances it with the scene's dt, so it
     decays on a camera that stands still (skipped like the aim when the scene was switched)
  9. **Present**: debug overlay, `pygame.display.update()` or `flip()`
  10. **Finish**: `_finish_frame` (see Frame Pacing)
- Handles scene transitions and lifecycle (`setup()`, `cleanup()`, `load_resources()`)
- The frame loop is four steps: `begin_frames()` (the first frame's start reading and dt),
  `should_run_frames()`, `run_frame_step(frame_start_seconds=..., paced=...)` (one frame, or a
  held frame presented again) and `end_frames()`. `start()` runs them blocking, paced.
  `GameHost.run_async` runs them one per outer tick with `paced=False` (no timer or clock waits:
  the tick is the pacing, measured into the next dt)
- The active scene is always a `Scene` (or subclass), or None: `switch_to_scene` and
  `request_transition`/`transition_to` raise `TypeError` for anything else
  (`scenes.scene.required_scene`), so the manager reads the attributes `Scene` declares
  (`camera`, `scene_start_capture`, `PIXEL_SNAP_MODE`, ...) directly. `SceneInterface`
  (`src/glitchygames/interfaces`) stays as the base both `SceneManager` and `Scene` implement

**Game Host** (`src/glitchygames/host.py`; design `plans/2026-10-23-game-host-and-browser-runner.md`)
- An outer game on top of every live run (`GameEngine.host`; None in a replay, whose viewer is
  its outer game). It is transparent today; later it is where AI input and event/call injection
  go without the game knowing
- `HostSources`: doors forwarding every member to `inner`, installed around the live doors and
  beneath the recorder: `HostSources(inner=LiveSources)`, with `--record-trace`
  `RecordingSources(inner=HostSources(inner=LiveSources))`. Whatever the host adds or hides is
  what a recording holds, so recordings replay exactly without the host
- What the host hides today: a window loss given back within one event batch
  (`without_window_recreation_bursts`: focus lost/gained, hidden/shown, leave/enter, and their
  ACTIVEEVENTs). SDL queues those when it recreates a `SCALED` window for an OpenGL renderer
  (once in the browser, twice on the dummy driver, never on macOS); without this a game pausing
  on focus loss starts paused (BUGS.md #216)
- `GameHost.run` (blocking: `SceneManager.start`) and `GameHost.run_async(scene_manager=...,
  wait_for_tick=...)`: one awaited tick per loop, which returns the tick's timestamp in seconds
  (a browser animation frame), so the host never reads a clock. `TickPacer` runs an inner frame
  when its accumulator holds the frame period less half a tick (the doors' `paced_frame_seconds`,
  else `1 / target_fps`; 0 runs every tick), re-anchors after a stall rather than catching up,
  and measures the median tick interval (the display's refresh, logged once). A 60 FPS game runs
  every second tick at 120 Hz
- `GameEngine.start_async(wait_for_tick=...)` runs a live game that way inside the same crash
  boundary as `start()` (`_crash_boundary`, a context manager both share: the same teardown and
  exit codes). A watched replay runs through `run_watched_replay_async`
  (`src/glitchygames/replay/viewer.py`: one viewer tick per awaited tick, `ticks_externally`, steps
  until `SceneManager.last_step_was_held`); a headless replay raises RuntimeError. Replay
  restarts need a new process, so in a browser they only show a message (`RESTARTS_AVAILABLE`). `_prepare_run()` is everything up to the first
  frame

**Exit Codes** (`src/glitchygames/exit_codes.py`; `ExitCode` IntEnum, re-exported by
`glitchygames.engine`; never write the number in code or tests)
- 0 `SUCCESS` (replay matched, audit deterministic), 1 `REPLAY_DIVERGED`, 2
  `ARGUMENT_PARSER_ERROR` (argparse's own; the engine never exits with it), 3
  `AUDIT_NONDETERMINISTIC`, 4 `GENERATION_REJECTED` / 5 `EXTRACTION_REJECTED` (API client: the
  server refused a generation / a frame extraction; a 503 is `SERVICE_UNAVAILABLE`),
  6 `AUDIO_DROPOUT_RISK` (`scripts/audio_glitch_probe.py` found a risk of audio dropouts),
  7 `REBASELINE_INPUT_LOST` (`--rebaseline` wrote NEW, but the run never got some of OLD's input),
  8 `PROCESSING_SLOWER` (a replay matched, but took more than `--max-processing-slowdown` longer),
  64 `OPTIONS_REFUSED` (option combinations the engine won't run), 65 `UNUSABLE_INPUT` (wrong
  game, unsupported format, corrupt or unreadable file, bad server response), 66 `MISSING_INPUT`
  (the file does not exist), 69 `SERVICE_UNAVAILABLE` (API server unreachable), 70
  `INTERNAL_ERROR` (uncaught exception during a run or its teardown, logged with its traceback
  after teardown; an audit that could not run; an API client bug), 73 `CANNOT_WRITE_OUTPUT` (an
  output file or directory cannot be written), 129 `HANGUP` (SIGHUP, Unix), 130 `INTERRUPTED`
  (SIGINT/Ctrl-C), 143 `TERMINATED` (SIGTERM), 149 `BREAK` (SIGBREAK, Windows)
- 0, 64-70 and 73 equal Python's `os.EX_*` (defined literally: Windows has no `os.EX_*`); signal
  members are 128 + N (`ExitCode.for_signal`). `ExitCode.describe()` gives `'OPTIONS_REFUSED
  (64)'`, the form the engine logs (`Exiting with ...`)
- Signals: `GameEngine.start` installs `exit_on_signal` for SIGTERM/SIGHUP/SIGBREAK (where the
  platform has them and nothing else handles them) for the whole run, and SIGINT ends it through
  KeyboardInterrupt; each exits with its member after teardown (recordings closed). The engine
  sets `SDL_NO_SIGNAL_HANDLERS=1` (unless preset) before `pygame.init()`, so SDL never turns
  SIGINT/SIGTERM into QUIT events. Not wired: SIGKILL/SIGSTOP, SIGPIPE, SIGQUIT. An engine started
  off the main thread can't install handlers, so SIGTERM then kills it without teardown.
  Exceptions before `start()` (in `__init__`) exit with Python's default 1. Tests:
  `tests/signal_handlers.py` (autouse fixture) restores signal handlers after every test

**Frame Pacing** (`src/glitchygames/timing.py`)
- Two timer backends (`--timer-backend auto`, the default, is `FastTimer` with a measured sleep
  model, below):
  - `FastTimer`: High-resolution `time.perf_counter_ns()` with sleep+spin hybrid: it
    sleeps so it wakes `sleep_granularity_ns` (1 ms) before the deadline, then spins the rest
  - `PygameTimer`: Legacy pygame-based timing (whole milliseconds); select with `--timer-backend=pygame`
- A sleep's delay is modelled as a constant plus a fraction of its length (`SleepModel`): macOS
  lets a normal-priority sleep run late by 25% of its length, so `--timer-backend fast` (which
  assumes sleeps wake on time) left most frames 1-2 ms late; at background priority the delay is
  a flat 85-100 ms. `--timer-backend auto` (the default) measures the model
  (`measure_sleep_model`: 10 sleeps each of 1 ms and 8 ms, 90th percentiles, about 0.1 s) as the
  engine starts a paced live game (target FPS > 0, not a replay, not `start_async`, whose outer
  tick is its wait), else at the first paced frame (uncapped runs, replays and async runs never
  measure), and sizes each
  sleep so its predicted wake lands `sleep_granularity_ns` before the deadline; when even no
  sleep would (a delay longer than the wait) it spins the whole wait. Measured on macOS (60 FPS,
  4 ms of work): fast 1.5 ms late per frame at 24% CPU, auto on time at 30%; at background
  priority fast ~90 ms late, auto on time at 92% CPU. The choice is logged (`Timer calibrated:
  fast, final spin 1.0 ms (calibrated: sleeps wake 0.01 ms + 25% of their length late)`) and
  every recorded run names its timer, paced or not (`MeasurementRun.pacing_timer`; `sleep_model`
  null when it never measured; the committed recordings from before it were backfilled with
  `fast`, 1 ms, no model). `nox -s timer-report` shows a
  machine's sleep accuracy
- Paced frame time (`dt`, FPS tracking) is always measured with `time.perf_counter()`, and
  `target_fps` may be fractional (the period is `round(1e9 / target_fps)` ns)
- Default target 60.01 FPS (`DEFAULT_TARGET_FPS` in `src/glitchygames/timing.py`, re-exported by
  `glitchygames.engine`); `--target-fps 0` is uncapped for every game
- A game scene may set `TARGET_FPS` (class attribute, like `NAME`/`VERSION`; `0.0` = uncapped,
  `None` = engine default). Resolution order: explicit `--target-fps` > scene `TARGET_FPS` > 60.01
- A scene may set `MAX_FRAME_SECONDS` (class attribute, default `None` = no cap): its `dt_tick` and
  the camera aim get `min(dt, MAX_FRAME_SECONDS)`, so a hitch advances the game at most the cap.
  The manager's `self.dt` stays the raw frame time (pacing, FPS statistics, overlay, shake), and
  recordings hold the raw dt (Clockwork Keep caps at 0.05 s)
- `_finish_frame(*, frame_start_seconds, ...)` ends every frame: pace, then read
  `time.perf_counter()` once; that reading ends this frame and starts the next, and `self.dt` is
  set only there (start to start, through the doors' `frame_seconds(measured=...)`, which a
  replay answers with the recorded dt), so recorded frames sum exactly to wall-clock time and logic,
  the overlay and the FPS statistics all see the same value. Processing time excludes the
  pacing sleep
- After falling more than one frame behind, pacing re-anchors instead of bursting to catch up
  (`next_frame_deadline_ns`; a slightly late frame is still caught up, so the average rate holds)
- Configurable sleep granularity for tight frame pacing
- Windows timer resolution control via WinMM

**World Space** (`src/glitchygames/world.py`, `src/glitchygames/camera.py`)
- A sprite declares `COORDINATE_SPACE = CoordinateSpace.WORLD` and keeps float `world_x`/`world_y`;
  the engine is then the only writer of its `rect` (it checks only `COORDINATE_SPACE` at runtime;
  `WorldPositioned` is the Protocol for read-only `world_x`/`world_y`, the type of a camera
  follow target). Sprites
  without the attribute (HUD, UI, PaddleSlap's paddles) are screen space and never touched
- Each frame `position_world_sprites` sets `rect.topleft` to `snap(world) - snap(camera) -
  snap(WORLD shake)` plus the sprite's `draw_offset` (frame anchor), each term snapped with the
  sprite's own `pixel_snap_mode` or else the scene's `PIXEL_SNAP_MODE` (class attribute, default
  `PixelSnapMode.NEAREST_HALF_UP`; collision's `snapped_world_position` resolves it the same way).
  It marks the sprite dirty only when it moved (never lowering `dirty = 2`) and owns `visible`:
  on screen within `CULL_MARGIN_PIXELS` (32) and not `hidden`. A game hides a world sprite with
  `hidden = True`, never `visible = False`
- Never read a world sprite's `rect` in game logic (`dt_tick`, event handlers): it holds where
  the sprite was last drawn. Use `world_x`/`world_y`, `snapped_world_position` or the collision
  rect. In the render phase (`update()`, `render()`) rects are this frame's positions
- Camera: `camera.follow(target=player, axes=FollowAxes.X)` in `setup()` (`FollowAxes.X`, `Y` or
  `BOTH`, the default; a target without `world_x`/`world_y` raises `TypeError` there);
  `camera.follow(target=None)` stops it (the example games do at game over, so the world stands
  still). Override `Scene.camera_target()` to aim anywhere else (return `None` for a manual
  camera). The engine aims with `camera.aim_at`; an axis not followed keeps its goal. Camera bounds, lead offsets, smoothing and `snap_to` still apply (without a
  `snap_to` in `setup()` the camera eases in from the origin). A game that also calls
  `camera.update()` while the engine aims gets a one-time warning. `Camera2D.apply()` stays as a
  helper for one-off conversions; to draw against world sprites in the render phase, use their
  positioned rects (Brave Adventurer's pit gaps do)
- Parallax layers (`camera.add_background_layer`): the draw function is called again only when
  the layer's offset (snapped camera position × `scroll_factor`) changes, so it must depend only
  on its arguments; a layer drawing time, randomness or game state passes `animated=True` and
  redraws every frame (Clockwork Keep's clock)
- The pose rule: draw a sprite's pose (image, so its hitbox) in `dt_tick`, after its state is
  decided and before collision; `update()` runs in the render phase, after collision, and may do
  only visual work (fades). Drawing the pose in `update()` makes collision use last frame's pose
  (the old one-frame wall lag). Likewise collision resolution belongs in `dt_tick` (PaddleSlap),
  so its result is positioned before the frame renders
- Transition captures hide a world-space player with `hidden` and restore it afterwards; the
  arriving capture snaps the camera to `camera_target()` on its followed axes only
  (`camera.snap_followed_axes_to`), or to the player on both axes when there is no target
- Golden traces (`scripts/record_golden_traces.py`, `tests/world/test_golden_traces.py`) replay
  every game older than the world-space change (`GOLDEN_TRACE_GAMES`; Mr. Muncher and Drawing
  Fire, newer, have only their golden replays) and compare each sprite's rect and visibility,
  frame by frame, with baselines recorded before the world-space change. Every difference must
  be explained by exactly one `ExpectedDifference` entry whose rule proves it exactly (an entry
  that explains nothing fails too); never re-record the baselines to make a change pass

**Clocks** (`src/glitchygames/clock.py`, a leaf module): every time read in `src/glitchygames/` comes from
here or from `Scene.game_time`, so a replay serves the same values. Pick by purpose:
- `Scene.game_time`: gameplay timers and cooldowns. The sum of the (`MAX_FRAME_SECONDS`-capped) dt
  the scene's `dt_tick` received; it stops while the scene is paused or switched away
- `frame_clock_seconds()` / `frame_clock_milliseconds()`: blinks, animation timing, FPS events,
  "how long since" in UI. The sum of frame times (advanced once per frame in
  `SceneManager._finish_frame`); it never pauses
- `wall_clock_time()` (timezone-aware UTC `datetime`) / `wall_clock_epoch_seconds()`: timestamps
  (undo history, save metadata, logs, ids). In a replay: the recording's `recorded_at` plus the
  frame clock
- `elapsed_seconds()`: throttles, debounces, repeat intervals, timeouts (only differences mean
  anything). It is the frame clock, live and replayed, so these timers have frame granularity
- `measured_seconds()`: real `time.monotonic()` for logs, metrics and diagnostics only. It is never
  replayed, so its readings must never change what is drawn, played or recorded (the one
  exception: each frame's diagnostic `processing_seconds`, recorded but never compared or served)
- Only `ALLOWED_BYPASSES` in `tests/test_engine_doors.py` may read the raw clock (or use
  `pygame.time.set_timer`/`Clock`): pacing (`timing.py`), `performance/`, `debug/`,
  `audio/diagnostics.py` and the live doors' wall clock (`live_sources.py`); by function
  (`ALLOWED_FUNCTION_BYPASSES`): `SceneManager.begin_frames`/`run_frame_step`/`_finish_frame`
  (and its pacing `Clock`),
  the recording's start stamp (`GameEngine.trace_recording_header`), each run's `measured_at`
  (`GameEngine.measurement_run`) and `clock.measured_seconds`
- A recorded run's wall clock (and its replay's) is the header's `recorded_at` plus the frame
  clock (`RecordingSources.wall_clock_time`)

**Gameplay Recording and Replay** (`src/glitchygames/sources.py`, `src/glitchygames/live_sources.py`,
`src/glitchygames/recording.py`, `src/glitchygames/replay/`, `src/glitchygames/randomness.py`; design
`plans/2026-10-19-gameplay-replay.md`, plans `plans/2026-10-19-gameplay-replay-*.md`)
- Doors: the engine takes events, frame time, polled input, devices, saves, the clocks and the
  random seed only through the active `EngineSources`. `src/glitchygames/sources.py` is the leaf
  registry (one per engine context): `active_sources()`, `install_sources(sources=...)` (only
  before the context's first frame,
  else `SourcesAlreadyRunningError`), `reset_sources()` (called by `GameEngine.__init__`), and the
  frame clock. It has no engine imports, which avoids an engine/scenes import cycle. Providers:
  `LiveSources` (`src/glitchygames/live_sources.py`: pygame's queue, the measured dt, pygame polling,
  real devices, `DiskSaveManager`, the real wall clock), `HostSources` (`src/glitchygames/host.py`:
  the game host's forwarding layer around the live doors), `RecordingSources`
  (`src/glitchygames/recording.py`: wraps the host's doors under `--record-trace` and records what
  passes through) and `ReplaySources` (`src/glitchygames/replay/driver.py`: serves the recording)
- Guard: `tests/test_engine_doors.py` AST-scans the package. Raw clock reads, pygame key/mouse
  polling, `pygame.event.get`/`post` and joystick/controller enumeration or construction outside
  the doors fail. The only exceptions are `ALLOWED_BYPASSES` (by file) and
  `ALLOWED_FUNCTION_BYPASSES`, each with its reason. No directory is exempt, Bitmappy included
- Polled input: `glitchygames.input.state.current_input()` (or `GameEngine.input`) returns the
  frame's immutable `InputSnapshot`. It is captured once per frame, right after the frame's first
  pump, so `dt_tick` (which runs before the pump) sees the previous frame's. It offers
  `key_pressed(key)`, `pressed_keys` (like `pygame.key.get_pressed()`; key lookup needs
  `pygame.init()`), `scancode_pressed(scancode=...)` (a physical position: no keymap, the same
  on every layout), `modifiers`, `mouse_position`, `mouse_buttons` and `mouse_focused`. Devices
  are keyed by instance id on two layers: the joystick layer (`axis`/`button`/`hat(device_id=...,
  ...)`, float axes) and the controller layer (`controller_axis`/`controller_button(device_id=...,
  ...)` by `CONTROLLER_AXIS_*`/`CONTROLLER_BUTTON_*` id, on pygame's int scale). Never poll pygame
  or a device directly. Recordings also hold the held keys' key codes (`held_key_codes`), so a
  replay answers `key_pressed(K_*)` as the recording machine's keyboard layout did
- Devices: `active_sources().devices()` (`src/glitchygames/input/devices.py`) is the only way to
  enumerate (`joystick_count`, `controller_count`, `is_controller`, `name_for_index`) and open
  (`open_joystick`, `open_controller`, `joystick_for_instance`, `descriptor_for_instance`)
  devices. Live answers, failures included, and each opened device's descriptor are recorded. A
  replay answers with the recorded answers (a recorded failure is raised again as `pygame.error`)
  and with `ReplayJoystick` / `ReplayController` stand-ins: their positions come from the
  snapshot, rumble is dropped, and the replay never sees real hardware
- Input devices (`src/glitchygames/input/input_devices.py`, its docstring the rules): games read
  `GameEngine.input_devices` / `Scene.input_devices`, one `InputDevice` per physical device by
  instance id (the door's `descriptor`, a `joystick` layer, a `controller` layer for a mapped
  pad, both read from the snapshot; `on_input_device_added/removed(device=...)` on the active
  scene). The registry follows the joystick and controller managers (both keyed by instance id)
  and opens nothing. Each device's input events reach handlers from its `event_layer` only (the
  controller layer if mapped, else the joystick layer): the other layer's are dropped, so each
  press arrives once. `--input-mode` filters: `auto` (default) all, `joystick` joystick layers
  only (controller events blocked), `controller` mapped pads only. Tests use stand-in devices
  through the door (`tests/input/stand_in_devices.py`). `--list-input-devices`
  (`src/glitchygames/input/device_listing.py`) replaces the run: it counts devices before SDL's
  queue is pumped (what the managers' startup count sees), listens a second keeping each
  device added/removed event with its time (macOS reports connected pads as device-added
  events), opens every device through the door and prints each one's index, instance id, name,
  GUID, mapping and controls to stdout, exiting `SUCCESS`; at a terminal, finding none prompts
  and waits for the first device added (Ctrl-C stops); refused (`OPTIONS_REFUSED`) with
  `--replay-trace` or `--record-trace`
- Saves: `glitchygames.state.open_saves(app_name=...)` returns a `SaveManager` (the base class
  holds every rule of the save format): `DiskSaveManager` live, `MemorySaveManager`
  (`src/glitchygames/state/sandbox.py`) in a replay, seeded from the recorded snapshot
  (`save_namespace_snapshot`). Replay writes stay in memory; real saves are never touched.
  `observe_disk_save_changes(observer=...)` (`src/glitchygames/state/manager.py`) calls an observer
  with each slot file's path after a `DiskSaveManager` writes or deletes it (a browser flushes
  IndexedDB there)
- Supervisor hook (`src/glitchygames/supervision.py`): `SceneManager.add_supervisor(supervisor=...)`
  calls `on_frame(frame_number=..., scene=...)` once per frame, after logic and events and before
  frame services, camera aim and positioning. `SceneManager.record_control_event(kind=...,
  data=...)` records a supervisor action in the frame (the frame's `control_events`) and runs the
  handlers from `add_control_event_handler(kind=..., handler=...)`. A replay re-applies recorded
  control events at the same frame's supervisor slot. `GameEngine.__init__` calls
  `SceneManager.begin_run()` (frame 0, `reset_supervision()`, quit/pacing/shake/playback state
  cleared). A future cheat device plugs in here
- `--record-trace PATH`: record the session as a gzip JSON Lines trace (`src/glitchygames/tracing.py`
  format version 3; versions 2 and 3 are readable), off by default. Each frame line holds `dt`,
  the raw `event_batches` read at `GameEngine._pump_events` (the only reader of SDL's queue,
  except a watched replay's viewer ticks, which drain it for the viewer's keys; each event tagged
  `external`/`internal`) and the sprites. Format 3 adds frame fields, written only
  when non-empty: `input_changes` (snapshot diffs), `control_events`, `devices_opened`,
  `saves_opened`, `device_enumeration` and `scene_start` (no format bump: readers pass unknown
  frame fields through). The header holds versions, options, `recorded_at`, the
  random seed and, since format 3, the `saves`, `devices` and `device_enumeration` taken in before
  recording started. Engine code posts events with `glitchygames.recording.post_event` so
  recordings can mark them internal; code driving the game from outside its logic (a
  supervisor, a harness) posts with `post_input_event`, recorded external whatever its type, so
  every replay serves it and drops a copy the replayed code posts (BUGS.md #84). The format is
  described in `src/glitchygames/recording.py`
- Scene starts (`src/glitchygames/scene_start.py`, a leaf: scenes never import the replay package;
  Part 3 Task 1): while the active doors' `captures_scene_starts` is True (`--record-trace` runs
  from their start, `--rebaseline`, the playback scope) or the class sets
  `INSTANT_REPLAY_SECONDS`, and unless it sets `CAPTURES_SCENE_START = False` (`PauseScene`),
  `Scene.__init__` first captures every random stream's state (`capture_stream_states()`) and the
  frame clock, plus the open save stores (stores opened before setup are snapshotted as
  `open_saves` opens them, via `sources.observe_save_store_openings`), and
  `SceneManager._setup_new_scene` completes the frozen pydantic `SceneStart` before the scene's
  FIRST setup only (resume keeps it): `Scene.replay_arguments()` (JSON round-trip exact, default
  `{}`; Clockwork Keep returns its floor, score and lives) and the streams and frame clock again.
  `SceneManager.active_scene_start`, `Scene.scene_start`. At the top of the scene's first logic
  frame (first `dt_tick` on it: frame 0 for the first scene, the frame after a `next_scene`
  switch, the first frame after a transition's ride) `_run_frame` adds `first_logic_frame`
  (streams, frame clock, FPS timer, earlier pending posts, arrived by transition); recordings
  write `scene_start` on that frame (a scene that never runs logic has none). `rebuild_scene(start=..., scene_class=...,
  options=...)` restores the construction streams and clock, constructs, then restores the setup
  ones (no `setup()`); it sets global state the caller must restore. Live play captures nothing
- Playback scope (`src/glitchygames/replay/playback.py`, whose docstring is the contract; Part 3 Task
  2): `start_playback(manager=..., header=..., frames=..., then=..., options=PlaybackOptions(...))`
  (or `start_playback_from_recording(path=...)`) requests a scope from a frame holding a
  `scene_start` with its `first_logic_frame`; `SceneManager._run_frame` enters it at the next
  frame's start (waits out a transition; dropped if the asking scene left that frame): saves the
  streams, frame clock and FPS timer, stashes the live scene (no `cleanup()`), pushes
  `PlaybackSources` (`sources.push_scoped_sources`), records a `playback` marker, rebuilds and
  sets up the scene (repeating a transition's arrival step), then sets the state its first logic
  frame began in and the recording's prior polled input. Real input reaches only the exit check
  (`exit_on_input`), and so does the live game's `post_input_event` of an SDL type (a
  supervisor's press ends a demo, as in a replay without it: BUGS.md #196); a supervisor may
  post any type (`post_input_event`): one SDL never generates (a game event) is held and
  reaches the live game after the scope, live and in a replay without it; the live game's
  own posts and the player's releases, device and window events are held and redelivered after, in pump order (`sources.redeliver_events`; recorded in
  that frame's `redelivered_events`, which a playback starting there serves; a next scope takes
  pending ones over; dropped at `terminate()`); the recording's QUIT ends the scope (not the
  game); saves are a sandbox. It ends after the frame on exit input, the recording's end or
  divergence, and on any error in its part of the frame (logged; installed-door errors
  propagate); `terminate()` ends it first. `last_playback_result` / `last_playback_outcome`
  (frozen pydantic: kind, reason, frames played). A `--record-trace` session records the live
  session through a scope (`recording.py`, Playback scopes) and replays it
- Demos (Part 3 Task 3): `SceneManager.play_recording(path=..., then=scene)` plays a recording
  as an attract-mode demo (`exit_on_input=True`, kind `demo`); a recording that cannot play is
  logged at WARNING ("No demo: ...") and nothing starts; a divergence ends it and logs WARNING
  `demo diverged: <describe()>`; a cut-off file plays to its cut-off and ends `truncated`
  (INFO). Check `last_playback_outcome` for how it ended
- Bundled demos (Part 3 Task 4): `src/glitchygames/examples/<game>_demos/<name>.jsonl.gz` for a
  game still inside the engine; a workspace member's go in the member's import package, e.g.
  `src/games/mr-muncher/mr_muncher/demos/<name>.jsonl.gz`. Each ships in the wheel of the package
  that holds it (the engine's, or the member's; hatch includes every file in the package; no
  pyproject change). PaddleSlap has no
  title screen, so its game-over screen (`PaddleSlapGameOverScene`) plays
  `PADDLESLAP_DEMO_PATH` after `GAME_OVER_IDLE_SECONDS` (10) of game time without a key or
  button press. `tests/replay/test_bundled_demos.py` replays every demo headless
  (`bundled_demo_paths`, `replay_recording_headless` in `src/glitchygames/testing/replays.py`) and
  plays PaddleSlap's through `play_recording` (stepped with `step_finishing`: the golden harness's
  `step` never gives a playback the recording's dt). A recording names its game (header `game`)
  and each scene start (`scene`) by logical names (`src/glitchygames/logical_names.py`: the layer,
  the module path inside the package, `:` and the `__qualname__`, e.g.
  `games.mr_muncher.game:MrMuncherScene`; a module in no layer keeps its path), unchanged when
  a game's code moves; the header check (`check_recorded_game`) and the playback's lookup
  (`find_scene_class`) compare them. A recording without them (made before) is compared by its
  exact `game_module` / `scene_module` and `__qualname__` (bare-name fallback, ambiguity
  refused), except under `--rebaseline`, the backward-compatibility path (no table of former
  locations): there the qualified name alone decides, so a game or scene that moved since is
  accepted (ambiguity still refused; one rule, `modules_not_compared` in
  `src/glitchygames/replay/driver.py`), and NEW holds the current logical names. Record a demo with `scripts/record_scripted_session.py --script-only --output PATH` (it runs
  `--record-trace`, so frame 0 holds the scene start); PaddleSlap's is `--frames 450`, before the
  golden script's pause
- `--random-seed INT`: the run's master seed (default: 64 random bits, kept in recordings). All
  randomness draws from named streams seeded from it: `random_stream('name')` (`random.Random`) or
  `numpy_stream('name')` (numpy `Generator`), looked up at draw time; `engine_random()` is
  `random_stream('engine')`, `reset_streams(seed=...)` reseeds (tests, replay). Never use
  `secrets`, `random.SystemRandom`, global `random.*` functions or an unseeded
  `np.random.default_rng()` in gameplay (`tests/test_randomness.py` scans for them)
- `--replay-trace PATH` (`src/glitchygames/replay/driver.py`; its module docstring lists the rules):
  replay a recording exactly through the real engine. `ReplaySources` serve its events, dt,
  polled input, devices, in-memory saves, clocks and seed, and every frame's sprites are compared
  with the recorded frame. Refusals log the reason and exit with an `ExitCode` (see Exit Codes):
  `UNUSABLE_INPUT` (65) for a recording of another game (by its logical name `game`, or, in a
  recording made before logical names, its exact module: one of a game that moved since is
  refused with a message naming `--replay-trace OLD --rebaseline NEW --headless`, which
  converts it), an unreadable file or an unsupported
  format version, `MISSING_INPUT` (66) for a missing file, and `OPTIONS_REFUSED` (64) for
  `--record-trace` given too (recording over a replay is `--rebaseline`'s job only). A
  different engine version only warns. Recorded options apply except
  `REPLAY_LOCAL_OPTIONS`; the window opens at the header's `screen_size` (the recorded display's
  size, not `--resolution`), and a window that still opens at another size is refused
  `UNUSABLE_INPUT` (a header without one keeps `--resolution`, with a warning). The first
  divergence (kinds `scene`, `sprite`, `event`, `length`) stops a `--headless` replay, as does
  the last recorded frame; closing the window stops any replay. A watched replay (no `--headless`) is a read-only game inside a game
  (`src/glitchygames/replay/viewer.py` documents the contract): the OUTER `ReplayViewer` ticks at
  60 Hz real time (`clock.measured_seconds`), reads the viewer's keys (`ReplayControls`,
  `src/glitchygames/replay/controls.py`: once per press; `.` repeats after 300 ms at 10/s) and
  presents the latest frame with a status bar (`EngineSources.draws_overlay`/`draw_overlay`,
  never in screenshots or traces); the INNER recorded game runs N full frames per tick from an
  accumulator (real time x speed, consumed by recorded dt, at most `MAX_INNER_FRAMES_PER_TICK`
  and `INNER_FRAME_BUDGET_SECONDS` per tick, never owing more than one tick's worth; the status
  bar shows the real speed when it cannot keep up),
  unpresented (`EngineSources.presents_frames` False). It drives the loop through
  `EngineSources.hold_frame` (held = present an outer frame, run nothing, consume no recorded
  batch). It holds at a "Press Spacebar to Start Game Replay" screen after frame 0 (the pause
  screen's `MessageScreen`, `src/glitchygames/ui/message_screen.py`) and pauses at a divergence or
  its end with the debug overlay on; Space pauses, `.` steps, `]`/`[` change speed, Esc quits.
  `,` (paused; held: one frame back per repeat, restarting on release), Home and D (divergence)
  restart the replay process (`src/glitchygames/replay/rebuild.py`) with `--replay-pause-at-frame N`
  and the viewer state (`--replay-viewer-state`: speed, panel, divergence frame): it rebuilds
  frames 0..N-1 unpresented, unpaced and silent (sounds stopped after each frame, music paused),
  then pauses; the first process supervises later restarts through `--replay-restart-handoff`
  (at most two processes, signal handlers reinstalled, a divergence in any run kept in the exit
  status), started with `glitchygames.process.run_command` (the one subprocess launcher, a leaf
  module; no `os.execv`: lint)
  Its real KEYDOWN/KEYUP stay unblocked at SDL and go only to its controls (F3/F4 to the debug
  overlay), never to the game. The report
  (`ReplayResult.report()`: `Replay diverged at frame 6120: sprite Ball#2 rect expected [412,
  300, 16, 16], got [412, 301, 16, 16]`, then that sprite's last 20 frames, expected | got; or
  `Replay matched N frames (end of recording)`) is logged, and every replay that ends normally
  exits with `ReplayResult.exit_code(policy=...)` (the policy and the other replay settings are
  the frozen pydantic `ReplayOptions`): `SUCCESS` (0) matched or quit early (window closed, Esc),
  `REPLAY_DIVERGED` (1), `UNUSABLE_INPUT` (65) for a truncated recording that matched to its
  cut-off. Recorded window references map to None (live events of the display window carry None).
  Version-2 recordings replay with one warning (polled input reads as idle)
- `--replay-fps {recorded,real}` (default `recorded`): FPS events, the performance stats and the
  overlay's performance panel use the recorded frame times (exact, compared) or this machine's
  measured ones (FPS events then not compared); logic always gets the recorded `dt`
- Real input, device and window events are blocked at SDL during a replay
  (`src/glitchygames/replay/input_blocking.py`; never QUIT, the window close event or custom types;
  re-blocked every pump, as event managers made mid-run allow their types; each type's prior
  blocked state is restored exactly when the replay ends, normally or after an error). Caveat:
  posts of a blocked type are refused too, so game code that fakes input by posting e.g. KEYDOWN
  shows a "missing internal event" divergence in a replay
- `--headless` (any run; "Diagnostics Options" group): `SDL_VIDEODRIVER`/`SDL_AUDIODRIVER` set
  to `dummy` right after the options are read (a display or mixer pygame already started on
  another driver is restarted on the dummy one, the mixer with its format and channel count, with
  a warning); when the run ends (`_tear_down_run`, after `_shutdown` quit pygame) both variables
  are put back as they were (an unset one removed), so a process that goes on starts pygame on
  its own drivers again. Live headless runs pace normally and end as the game ends; a
  headless replay is unpaced (`EngineSources.paced_frame_seconds()` returns 0.0: no timer
  deadline, no clock tick) and prints its report to stdout instead of logging it. A replay that a
  crash, Ctrl-C, signal or the game's own exit ends early reports only `Replay stopped at frame
  N: the run ended with ...` (after its result: the result, then `then the run ended with ...`).
  The diagnostic flags (`--headless`, `--list-input-devices`, `--debug-overlay`, `--debug-events`, the trace/replay/audit
  flags, the timer jitter and FPS report flags) are in the "Diagnostics Options" group
- Fabricated key events (scripts, tests) carry their key's US QWERTY position
  (`glitchygames.testing.keys.qwerty_scancode`): the example games bind their own scenes'
  controls by scancode (`ActionMap.bind(scancode=...)`), their pause and quit included; the
  engine's `PauseScene` and `GameOverScene`, and the base `Scene`'s Q/ESC quit (PaddleSlap's),
  check key codes (`event.key`). Both screens answer a gamepad too, on either event layer
  (`scenes/builtin_scenes/gamepad_choice.py`): Start or A goes on (resume, restart) on its
  release after a press there, as SPACE does; B or Back quits on its press, as ESC does
- Golden replays: the engine's own live in `tests/fixtures/replays/<console-script>/golden.jsonl.gz`;
  a workspace member's in `<member>/tests/fixtures/replays/<name>.jsonl.gz` (Mr. Muncher's:
  `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`), replayed through the member's
  console script (`recording_console_script`), and its bundled demos in `<package>/demos/`.
  They are recorded through the
  real engine loop by `scripts/record_scripted_session.py` (a supervisor posts each game's golden
  input script one frame ahead; never the golden harness, whose recordings have no FPS events).
  Each is a pytest item of its own: the plugin `src/glitchygames/testing/replays.py` (root
  `conftest.py` `pytest_plugins`) collects every `.../fixtures/replays/<console-script>/*.jsonl.gz`,
  replays it in a child process through the console script's entry point with
  `--replay-trace PATH --headless`, and fails with the exit code and the printed report unless it
  exits `SUCCESS`; `tests/replay/test_golden_replays.py` keeps the fixture-set and tamper checks.
  Re-record only deliberately (commands in the script's docstring). The controls rule: after the
  script's frames the recorder plays the game's controls tail (`CONTROLS_TAIL_BUILDERS`, never in
  the golden traces' scripts), so every golden replay pauses and resumes (a game with no pause,
  Drawing Fire, is listed in `GAMES_WITHOUT_A_PAUSE` with its reason), presses every keyboard
  control the game binds (each key of an action bound to several), and ends with the game's own
  quit control: the recorded QUIT is internal, so a game that stops quitting diverges ("missing
  internal event"); a tail whose quit does not end the run fails the recording
  (`GameDidNotQuitError`). `test_every_golden_replay_exercises_every_control` maps each
  recording's external input to controls through the game's own ActionMaps (its static
  `_create_action_map(s)`) plus the engine scenes' hard-coded keys (`ENGINE_SCENE_CONTROLS`) and
  fails on an unexercised control unless `UNEXERCISED_CONTROLS` gives its reason (gamepad
  controls: no session has a device; the pause screen's quit: a session quits once); a new game's
  bindings must be listed there. A game that reads its controls from the frame's snapshot
  (`current_input()`) rather than an ActionMap (Drawing Fire) lists them all in
  `ENGINE_SCENE_CONTROLS` (keys by scancode, the mouse as `InputKind.MOUSE`). A posted event
  never changes SDL's polled state, so for such a game (`POLLED_INPUT_GAMES`, opt-in: only
  Drawing Fire) the recorder lays the input it posted over each live snapshot
  (`PostedPolledInput`, `polled_input_follows`), as a real player's input would be; every other
  game's session records the snapshots it always did, so its re-recordings keep their content
  hashes. A game whose state is drawn rather than kept in sprites must post an internal event
  (`post_event`) for what matters, or its replay compares nothing of it: Drawing Fire posts a
  GAMEEVENT per death and seat change. Demos are recorded `--script-only` (no tail, no quit)
- `--replay-trace PATH --audit` (`src/glitchygames/replay/audit.py`): instead of replaying, runs the
  same command twice as child processes (`--no-audit --headless --replay-digest <temp>`,
  `PYTHONHASHSEED` 1 and 2) and compares each run with the recording and the two
  per-frame digest streams (`--replay-digest PATH`: a SHA-256 per replayed frame, then the
  divergence); exits `SUCCESS` (0) when deterministic, `AUDIT_NONDETERMINISTIC` (3) otherwise,
  `INTERNAL_ERROR` (70) when a child could not finish (did not start, hung, crashed, wrote no
  digests); refused with `OPTIONS_REFUSED` (64) under `--replay-fps real` or `python -E`/`-I`,
  which would keep PYTHONHASHSEED from the children, and with `UNUSABLE_INPUT` (65) for a
  truncated recording (an audit needs the whole recording). It compares only
  what the replay samples: the scene class and each sprite's `rect`, `visible` and draw order, not
  pixels, audio or unsampled game state. Children run through `glitchygames.process.run_command`
  (the one launcher; `process.with_options_appended` adds options before a bare `--`), with a
  timeout and the engine's signal handlers installed around the wait
  (`GameEngine._waiting_for_child_processes`, shared with restarts)
- Outputs: an unwritable `--record-trace`, `--rebaseline` partial or `--replay-digest` file is
  refused before the run (`CANNOT_WRITE_OUTPUT`, one line; a recording whose writes fail part
  way, the disk filling, also ends the run `CANNOT_WRITE_OUTPUT` with one line, keeping the
  frames written: `recording.RecordingWriteError`; `src/glitchygames/output_files.py`, which
  also holds the one write-aside-then-replace helper); a game's own `sys.exit(0)` that cuts a
  replay short exits `REPLAY_DIVERGED` (under `--rebaseline` it is the game ending early, as
  `quit_game()` is: NEW is written, exit `REBASELINE_INPUT_LOST`); a malformed header or start frame is `UNUSABLE_INPUT`
- Processing time (`src/glitchygames/replay/processing.py`, whose docstring is the contract): each
  recorded frame holds a diagnostic `processing_seconds` (its work from the top of
  `SceneManager._run_frame_steps`, minus `_present_frame`, without the doors' `end_frame` or
  pacing; `clock.measured_seconds`), passed to the doors as `end_frame(processing_seconds=...)`,
  never compared or served; the header names the `machine`. `--replay-trace PATH --headless
  --compare-processing` prints `Processing: the replay took 14.2% longer than the recording
  (...)` after the report; `--max-processing-slowdown PERCENT` (implies it) exits
  `PROCESSING_SLOWER` (8) for a matched replay that took more than PERCENT longer in total,
  `UNUSABLE_INPUT` when the recording has no times. Refused (`OPTIONS_REFUSED`) without
  `--headless`, with `--audit` or `--rebaseline` (whose NEW records its own times). Paced frames
  process slower (the CPU idles between them), so the fair baseline is a `--rebaseline` made on
  the checking machine (latest run's `processing_paced` False); the report notes a paced baseline
- Frame histories (`src/glitchygames/recording_history.py`, the contract; design
  `plans/2026-10-20-recording-content-hash-and-history.md`): every recorded frame holds
  newest-first `content_hash` (64 bits of SHA-256 of its content fields as JSON decodes them,
  re-encoded compact and key-sorted, scheme 1; each frame field is content or a measurement, enforced) and `processing_seconds`
  lists, and the header `measurement_runs` (each run's provenance: machine, paced and its pacing timer, versions, the
  engine's `source_revision` (see Source revision), the `machine_state`
  (`src/glitchygames/machine_state.py`: CPU, memory, mains or battery, macOS thermal report, CI),
  a `summary` (`RunSummary`: processing p50/p95/p99/max, worst frame and scene, frames over the
  target FPS budget, the live run's frame times; filled in when the next run stacks, since a
  header is written first; `recording_run_summaries` computes the newest's),
  `measured_at` from `GameEngine.measurement_run`, `rebaselined_from`, `hash_scheme`, and
  `frame_count`, filled in when the next run stacks; read leniently, written strictly); index `i`
  is run `i` everywhere, each list capped at its depth constant (10). A rebaseline stacks its run
  in front (same hashes when behaviour is unchanged); `recording_content_hash` derives a
  recording's hash for any run. Never compared by a replay, never served
- Recording metrics (`src/glitchygames/recording_metrics.py`, a leaf; design
  `plans/2026-10-23-recording-metrics.md`, Parts 1 and 2 done): `behaviour_changes` (adjacent
  runs' frames whose `content_hash` differs, as spans with the first frame's scene and both
  commits), `processing_comparisons` (same-work frames only, equal hashes, that got slower or
  faster beyond a ratio and a minimum), and the run ledger (`LedgerRow`, one per recording per
  run, keyed by recording + `measured_at` + machine; `merge_ledgers`, `performance_series`). The
  ledger lives in the repository, one file per row (`quality/replay-ledger/`; design
  `plans/2026-10-25-measured-rows-in-the-repository.md`): the `replay-metrics` pre-commit hook
  (`scripts/measure_staged_replays.py`, its docstring the rules; installed by `.envrc` when
  missing) measures every golden replay and bundled demo when this machine has no rows for the
  staged code tree (`src/glitchygames/code_tree.py`: a git tree of only `MEASURED_PATHS`,
  `src/` (the engine, games, demos, apps; less the members' `tests/` but for their
  `tests/fixtures/replays/`: `is_measured_path`), recordings, `uv.lock`, `pyproject.toml`), so
  code that arrived by
  a merge or rebase is measured by the next commit, and stages the rows, each naming that code
  tree (`LedgerRow.code_tree`), into the same commit, plus the `history-...` row files it wrote
  (a recording's earlier header runs, written only when measured on a commit on `origin/main`
  without uncommitted changes, and never again under a moved recording's new path:
  `replay_metrics.rows_to_write`, `LedgerRow.held_key`; none without an `origin/main`) (refused for a partial `git commit <path>`
  or untracked files under the measured paths; `SKIP=replay-metrics` skips it); every docs build reads them and keeps the rows whose tree
  landed (`landed_code_trees`: the tree of each commit that added rows, i.e. main's squash
  merge; `landed_rows`), labelled with that commit, then merges gh-pages' ledger and local
  pending rows (`nox -s replay-metrics`, `scripts/replay_metrics.py`) and graphs them
  (`scripts/generate_performance_graphs.py`, docs/quality/performance.md); CircleCI's
  `deploy-docs` publishes after each merge (`nox -s docs-deploy` refuses unless HEAD is on
  origin/main). A branch updated from main is measured by its next commit, or by hand: `uv run
  python -m scripts.measure_staged_replays`, then commit what it stages Each measured row carries a `FrameProfile` (about 100 buckets of the run's slowest frame
  per stretch, integer microseconds, scenes run-length encoded; ~0.4-0.6 KB) for the page's frame
  x commit heatmap (time only: the report shows whether the work changed). Rows measured on
  uncommitted changes (`LedgerRow.from_uncommitted_changes`, e.g. `--allow-dirty`) are left out
  of a published build (the hook's `on_startup` sees `gh-deploy`; no startup event counts as
  published) and shown, labelled, in a local `mkdocs build`/`serve`; they stay in the pending
  file after a deploy (`clear-published` removes only rows gh-pages holds). `uv run python
  scripts/recording_report.py PATH` prints a recording's runs, speed changes and
  behaviour-change map
- Bookmarks (watched replay): B bookmarks the frame shown, S saves `x.bookmarked.jsonl.gz`
  (header `bookmarked_copy_of`; only such a file is updated in place) with a
  `{"kind": "breakpoint", "label": "bookmark"}` control event in frame N - 1 per bookmark N; a
  watched replay of the copy pauses at each, and a step back with bookmarks saves and replays the
  copy (rule 16 of `src/glitchygames/replay/driver.py`)
- `--replay-trace OLD --rebaseline NEW --headless` (`src/glitchygames/replay/rebaseline.py`, whose
  docstring is the contract): replays OLD on the current code without stopping at divergences
  (`ReplayOptions.stop_on_divergence=False`; it alone accepts an old-format recording of a game
  that moved, matched by qualified name, and so converts it to logical names), records the run into NEW through
  `RecordingSources(..., replayed=<the ReplaySources>)` (origins from `last_batch_origins()`,
  per-frame saves/device fields from `recording.recorded_frame_fields()`; header = OLD's +
  `rebaselined_from` + current versions + this run's game names (`game_class`, `game_module`,
  `game`), `source_truncated` for a cut-off OLD), written to
  `NEW.partial` and moved into place only on a normal end, prints `Rebaselined N frames to NEW:
  K frames differ (first at F: ...); sprites affected: ...` (or `no frames differ`) and exits
  `SUCCESS` (`ReplayExitPolicy.SUCCESS_AFTER_WRITING`); input OLD has that the run never got
  (unpumped batches' external events, frames after an early game end) is never carried
  elsewhere, only appended to the summary (`; 3 recorded input events not delivered (first at
  frame 812); ended at frame 500 of 9800`), logged as a warning, and the run then exits
  `REBASELINE_INPUT_LOST` (NEW still written; `ReplayResult.has_lost_input`); a failed final move keeps
  `NEW.partial` and exits `CANNOT_WRITE_OUTPUT`. Refused (`OPTIONS_REFUSED`) without
  `--replay-trace` or `--headless`, with NEW or `NEW.partial` == OLD, `--record-trace`,
  `--audit`, `--replay-digest` or `--replay-fps real`. NEW replays clean; a truncated OLD gives a
  `source_truncated` NEW (replays `UNUSABLE_INPUT`, not auditable, not a golden fixture);
  replacing a golden fixture with NEW stays a reviewed step
- Instant replay (contract: `src/glitchygames/instant_replay.py`, a leaf, and rule 7 of
  `replay/playback.py`): `Scene.INSTANT_REPLAY_SECONDS` opts in (an in-memory journal of the
  scene's frames, ~0.5-1.5 MB/min), `MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS` (60) is the
  budget, `scene_manager.instant_replay() -> bool` plays it; end it early only from a
  supervisor with `end_playback()` (reading `playback_player_input`). Supervisors and handlers
  the scope's code adds (not live supervisors' additions) are removed when it ends
  (`SceneManager.in_playback_scope` is the one "in a scope" answer); the scope's code's posts
  still queued at its end are dropped from the next pump (`sources.discard_scope_posts`), while
  live supervisors' and handlers' posts during it (`recording.live_game_posts`, e.g. one made
  right after `end_playback()`) reach the live game after it; inside a scope the installed
  doors' re-applied control events apply, the played recording's never; a playback never
  rumbles real devices, and the voices of the live scene (and of the game behind a pause
  screen it began from) pause behind it
- Ghosts (contract: `src/glitchygames/replay/ghosts.py`): `GhostRecorder(sprite=..., scene=...)`
  (a supervisor; `finish()` -> frozen pydantic `GhostTrack`, `to_json`/`from_json`, store in
  saves), `GhostSprite(track=..., image_for=images_from_animated_sprite(sprite))` with
  `ghost.scene = scene` (a WORLD sprite following `scene.game_time`; no hitbox)
- Part 2 and Part 3 are done; follow-ups (state snapshots, cheat device) are in
  `plans/future-work.md`. User docs: `docs/architecture/gameplay_replay.md`

**Engine Context** (`src/glitchygames/engine_context.py`; design `plans/2026-10-25-engine-context.md`)
- The state one running game owns, so several games can run in one process (the Arcade's demo
  tiles). Ordinary games never create one and run in the default context
  (`default_context()`), exactly as before. Only the slots below are per context today; the rest
  of the process-wide state (`GameEngine` and its `OPTIONS`, `SceneManager.OPTIONS`,
  `FontManager`, `ResourceManager`, the event managers, other audit rows) is later sub-plans,
  and the engine does not switch contexts yet (nothing in `src/` calls `.active()`; tests do)
- Per-context state is a `ContextSlot(name=..., factory=...)` declared once at module level in
  the module that owns it; code reads `current_context().value(slot=...)` when it needs it,
  never at import (`tests/test_engine_context.py` scans the engine and every member).
  `ContextSlot` is internal to the engine: engine modules declare slots, games keep state on
  their scenes (the tests' `COUNTER_SLOT` only tests the class)
- `with context.active():` switches (a `contextvars.ContextVar`: per thread and asyncio task;
  nests; restores on exceptions). Slots today: the default snap mode, the default background,
  the polled input, the random streams, the doors with the frame clock and observers, and the
  `SceneManager` singleton; each has an isolation check in `tests/test_engine_context.py`
  (`ISOLATION_CHECKS`), and a slot without one fails the suite
- The harness fails a test that leaves another context current
  (`every_test_ends_in_the_default_engine_context`). A new autouse fixture that resets engine
  state must join a group (`per_context_state_resets` or `engine_service_resets` in
  `tests/harness.py`) that the leak check requests, or be listed in
  `PROCESS_STATE_AUTOUSE_FIXTURES` (`tests/test_engine_context.py`) with its reason; a guard
  test enforces it

**Source revision** (`src/glitchygames/build_info.py`, the contract): `source_revision()` names the
engine's commit and how it is known, first answer wins: a git checkout (git: HEAD, its date,
uncommitted changes to tracked files; only when git tracks the package's files, so a copy
installed in another repository's `.venv` does not count), a git archive
(`src/glitchygames/_git_archival.txt`, `export-subst` in `.gitattributes`: `git archive` and GitHub's
source zips write the commit in), a build stamp (`_build_info.json`, written by
`scripts/write_build_stamp.py` around `nox -s build-wheel`/`build-binary`/`test`, gitignored, packaged
through hatch `artifacts`), else unknown. Every recorded run holds it
(`MeasurementRun.source_revision`; `engine_source_revision()` looks it up once per process)

**Screen Shake and Rumble** (`src/glitchygames/effects/shake.py`, `src/glitchygames/input/rumble.py`)
- `Scene.shake(Shake(...), targets=ShakeTarget.WORLD | ShakeTarget.SCREEN)`
- Styles: `NOISE` (trauma model), `JITTER`, `BOUNCE`; shakes stack and are capped
- WORLD shakes world-space sprites and parallax layers (HUD stays still); SCREEN shifts the
  presented frame, survives `transition_to`, and is cleared by `switch_to_scene`. A WORLD shake
  advances exactly once per frame whether the engine aims the camera, the game moves it, or
  nothing does (frame step 8), so it decays on a still camera too. A WORLD shake on a scene with
  nothing it could move (no world sprites, parallax or `camera.apply()` use) logs a warning,
  decided at `shake()` time
- Optional `RumbleSettings` per shake; `SceneManager` sends combined rumble in controller and
  joystick modes
- `--screen-shake-intensity`, `--rumble-intensity` (0.0-1.0)

**Sound Synthesis** (`src/glitchygames/audio/synth.py`, `recipes.py`, `live.py`)
- Toolkit: oscillators (PolyBLEP square/saw), pitch curves via easing, envelopes, FIR filters,
  mixing, `to_sound()`
- Recipes: `Tone`/`SoundRecipe` (TOML-loadable) played through `SoundBank`
- Live voices: `scene_manager.live_audio.create_voice(owner=...)`, streamed in 100 ms chunks on
  a channel pool reserved at startup (`--live-voice-pool`, default 4)
- Mixer: 44100 Hz, signed 16-bit, stereo, 512-sample buffer (started by `pygame.init()`)
- GIL: the engine sets `sys.setswitchinterval(GIL_SWITCH_INTERVAL_SECONDS)` (0.5 ms, `timing.py`) so the
  mixer callback can queue the next chunk; check with `uv run python scripts/audio_glitch_probe.py`
- Microphone: `uv run python scripts/microphone_capture_check.py [--duration 3] [--device NAME]`
  captures from it with miniaudio and reports bytes, frames and levels (exit codes in its docstring)

**Transitions** (`src/glitchygames/transitions/`): `on_update` callback, `add_cue(progress, callback)`,
`eased_velocity_at(progress)`; cues run after the old scene's cleanup, so they may use only
SceneManager services

**Debug Overlay** (`src/glitchygames/debug/`): `--debug-overlay` or F3 shows it, F4 cycles panels
(collision hitboxes by layer, physics velocities and ground state, camera panel with world edges
and mouse world position (bounds clamp the camera's top-left, so right/bottom edges are max +
screen size - 1), performance HUD with FPS, frame time, 1% low and a frame-time graph with a target
line). Drawn in `SceneManager._present_frame`, never in screenshots, with the bundled Bitstream
Vera Sans font on translucent cached backings. Scenes or sprites can add annotations with
`debug_draw(surface, camera)`. `Scene.debug_subject` names the scene to inspect (normally the scene
itself; `PauseScene` returns the paused game, so its hitboxes line up with the frozen picture and
the HUD shows `| paused: <name>`).

**Scene backgrounds** (`src/glitchygames/backgrounds.py`): a scene that sets no background shows the
default pattern instead of black (black cannot be told from "nothing rendered"): the SMPTE-style TV
test pattern, or the channel 3 blue screen with `--default-background channel-3`
(`BackgroundPattern`; drawn at any size, cached per size). `Scene.background_color = ...` keeps
working (scenes that want black name it: PaddleSlap, GameOverScene, PauseScene, Bitmappy and its
dialogs); `Scene.background_pattern = BackgroundPattern.CHANNEL_THREE` picks a pattern. A new
engine display is painted with the default before the first frame. Then, before the game is built
(every game started through `GameEngine`, Bitmappy included), the CRT power-on sequence plays on
that canvas (`src/glitchygames/crt_power_on.py`): a dot, a line, the picture opening, warm-up flicker
from fixed tables (no randomness), settling on exactly that default; any key or button skips it, a
window closed during it quits the game. `--crt-power-on auto` (default) skips it on SDL's dummy
driver (`--headless`, every test) and before a replay, audit, rebaseline or recording

**Pixel snapping** (`src/glitchygames/pixel_snap.py`): `PixelSnapMode` and `snap_to_pixel` convert
sub-pixel world positions to drawn whole pixels (NEAREST_HALF_UP for smooth-motion games, FLOOR
for retro/platformer games), shared by sprites, collision and the debug overlay. A scene picks its
mode with `Scene.PIXEL_SNAP_MODE`; a sprite may override it with `pixel_snap_mode` (the ball does).

**Opaque frames** (`src/glitchygames/opacity.py`, BUGS.md #142): on macOS (cocoa) the display has
per-pixel alpha and the window shows alpha 0 as black; a plain `pygame.Surface(size)` there takes
the display's format (alpha mask, no SRCALPHA flag), so blending text onto it leaves alpha 0 and
blitting it copies that alpha. The scene background is opaque (`background_color` refuses alpha
below 255), `Scene.screenshot` is opaque, and `SceneManager._show_frame` runs `make_opaque` on the
display before every present. The test guard judges what the window shows
(`display_looks_entirely_black`); check rendering on the real driver with
`SDL_VIDEODRIVER=cocoa uv run pytest`.

### Event System

**Event Flow**: `active_sources().pump_events()` (live: `pygame.event.get()`) → `GameEngine.process_events()` → `EVENT_HANDLERS[type]()` → `SceneManager.on_*_event()` → `Scene.on_*_event()` → `Sprite.on_*_event()`

**Event Categories**:
- Audio, Controller, Keyboard, Mouse, Window, Touch, Joystick, MIDI
- Custom: `FPSEVENT`, `GAMEEVENT`, `MENUEVENT`

**Event Managers** (`src/glitchygames/events/`):
- Specialized classes: `MouseEventManager`, `KeyboardEventManager`, `ControllerEventManager`
- Scenes override `on_*_event()` methods to handle specific events
- `HashableEvent` (`src/glitchygames/events/base.py`): the hashable, immutable wrapper every handler
  gets (dispatch: `HashableEvent.from_pygame`). `HashableEvent(type, **fields)` builds the type's
  class from `EVENT_CLASSES` (`KeyEvent`, `MouseMotionEvent`, `MouseButtonEvent`, `JoyAxisEvent`,
  `ControllerButtonEvent`, `WindowEvent`, `FpsEvent`, `GameEvent`, ...: field declarations only;
  custom types stay `HashableEvent`, fields `Any`), so handlers name their class (chords get
  `keys: tuple[KeyEvent, ...]`). Equal by type and fields, never by class. Mutators raise
  TypeError: use `event.with_fields(**changes)`; the hash is cached in a slot, never a field.
  `to_json()`/`from_json()` encode values as recordings do, windows as None (recordings still
  store raw pygame events)
- Unhandled events: `GameEngine.unhandled_events` keeps per-type count, first-seen time and attribute names; logged as a table at teardown (`_shutdown`). A scene's stub (`unhandled_event()`) also logs a warning the first time each type arrives under `--debug-events` (off by default) and raises `UnhandledEventError` under `--no-unhandled-events`
- `SYSWMEVENT` (the window system's raw messages) stays blocked, as SDL leaves it (`events.allow_every_event_type`); a game opts in with `NATIVE_WINDOW_MESSAGES = True` on its scene class and gets them in `on_sys_wm_event` as plain `HashableEvent`s (docs/architecture/event_system.md)

### Sprite and Animation System

**Sprite Hierarchy** (`src/glitchygames/sprites/`):
- `RootSprite`: Base with mouse events and `pygame.sprite.DirtySprite`
- `Sprite`: General-purpose with coordinates, name, parent tracking
- `BitmappySprite`: Loaded from TOML files
- `AnimatedSprite`: Multi-frame animation support
- `FocusableSingletonBitmappySprite`: UI widgets with keyboard focus

**Animation** (`src/glitchygames/sprites/animated.py`):
- `FrameManager` (`src/glitchygames/sprites/frame.py`): Centralized frame state with observer pattern
- Multiple named animation sequences per sprite
- Per-frame timing overrides
- TOML format with RGBA/RGB support (magenta key: 255,0,255)

**Hitboxes** (`src/glitchygames/collision/`): default to the image's visible pixels (alpha/colorkey
trimmed, `collision/bounds.py`, measured every query so redrawn images are fine);
`TRIM_TRANSPARENT_HITBOX = False` opts out and TOML hitboxes win (native pixels times
`AnimatedSprite.hitbox_scale`; `hitbox_flip_x = True` mirrors them for a sprite drawn facing
left). `AnimatedSprite.common_hitbox_x_range()` is the x-span every frame shares (use it for
standing support so a wider frame cannot catch a ledge), and
`collision.layers.collision_rect_offset(sprite)` places a sprite so its collision rect is flush
against a wall. Caveat: a TOML `AnimatedSprite`'s visible-pixel default is measured on its
loaded frame images (`SpriteFrame.opaque_bounds()`), which keep magenta as opaque pixels
(`pixel_utils.create_alpha_surface` stores it at alpha 255), so it trims nothing for them, though
the drawn `image` is keyed correctly (#133: SRCALPHA for frames with translucent pixels, a magenta
colorkey otherwise); give them a `[sprite.hitbox]` (e.g. the union of their frames' non-magenta
bounds, as `ghosty.toml` does).
Frames of different shapes: draw walkers bottom-aligned, or set `AnimatedSprite.frame_anchor`
(`FrameAnchor`: edge names align one axis, CENTER/corners both; `[sprite] frame_anchor =
"bottom"`). The engine adds `draw_offset` to `rect` for world-space sprites; a screen-space sprite
adds it to `rect` itself.

**Rendering Optimization**:
- `pygame.sprite.LayeredDirty` for dirty-rect rendering
- Sprites with `dirty=1` force redraw; `dirty=0` skips rendering
- Film strip sprites update every frame for animation preview

### UI Subsystem (`src/glitchygames/ui/`)

Components: `MenuBar`, `MenuItem`, `TextSprite`, `MultiLineTextBox`, `SliderSprite`, `TabControlSprite`, `ColorWellSprite`

Dialogs: `LoadDialogScene`, `SaveDialogScene`, `NewCanvasDialogScene`

**Focus Model**: Focusable sprites intercept keyboard input via `active` attribute

### Bitmappy Pixel Art Editor (`src/glitchygames/bitmappy/`)

Features:
- Canvas-based pixel editing with undo/redo (`UndoRedoManager`)
- Animation timeline (`FilmStripWidget`)
- Multi-controller support (`MultiControllerManager`)
- Collision visualization (`VisualCollisionManager`)
- TOML file format for sprites
- AI integration via aisuite, behind the feature flag `AI_FEATURES_ENABLED`
  (`bitmappy/constants.py`; off in WebAssembly builds for now: the AI worker is a separate
  process, which a browser cannot start). `tenacity` is imported only when an AI request is made
  (`ai_worker._create_ai_retry_decorator`), so Bitmappy imports without it
- Voice recognition support
- PNG drag-and-drop
- Runs in the browser: `nox -s browser -- bitmappy` (its bundle alone includes `bitmappy/`; the builder runs as `python -m scripts.build_browser_bundle`, and a workspace member's game ships its package as its own archive, `mr_muncher.zip` beside `glitchygames.zip`).
  There Load opens the browser's file picker and Save downloads the saved file, through the
  installed user files (`src/glitchygames/user_files.py`; the page's `browser/browser_user_files.py`).
  On the desktop nothing is installed and the dialogs ask for file names as always

**Clipboard and the player's files** (`src/glitchygames/clipboard.py`, `src/glitchygames/user_files.py`)
- Text widgets copy and paste through `system_clipboard()`: the installed clipboard, else
  `create_clipboard()`'s choice (`PyperclipClipboard`, else `InProcessClipboard` without
  pyperclip). A clipboard that cannot be used raises `ClipboardUnavailableError`. Tests get a
  fresh `InProcessClipboard` each (`tests/harness.py` `in_process_clipboard`), never the machine's
- The browser installs `BrowserClipboard` (`browser/browser_clipboard.py`): paste takes the
  page's paste event text (Ctrl/Cmd+V fires it before the game's frame reads the key); copy is
  kept in the game and written with `navigator.clipboard.writeText`, which Safari refuses
  outside the key's own handler (copied text then pastes only inside the game). pyperclip
  installs in Pyodide but cannot work there (it runs clipboard programs)
- `installed_user_files()` is None on the desktop; a browser installs `UserFiles` (`open_file`
  with a file picker, `save_file` as a download). Tests start with none (`desktop_user_files`)

**Touch controls in the browser** (`browser/touch_controls.js`; layouts in
`scripts.build_browser_bundle` `TOUCH_LAYOUTS` (scripts/build_browser_bundle.py), written into boot_config.json)
- On touch devices the page shows on-screen buttons (portrait: below the game; landscape: over
  its bottom corners). A held button holds its key: key events dispatched on the canvas reach
  SDL (on the window they do not), so games, action maps, recordings and replays see ordinary
  key presses and need no changes
- Each button names its key ('Jump · Space'): the shared pause and game-over screens resume with
  Space and quit with Esc, so a second tap on an Esc pause button would quit; their prompts then
  point at the right button. Mr. Muncher's pause is P for that reason
- `tests/test_browser_touch_controls.py` checks every button presses a key its game binds (or the
  shared screens' Space and Esc). Bitmappy has no layout

### Resource Management

**Fonts** (`src/glitchygames/fonts/`): `FontManager` singleton with Bitstream Vera fonts

**Colors** (`src/glitchygames/color/`): Palettes (NES, SYSTEM, VGA) and constants

**Game Objects** (`src/glitchygames/game_objects/`): Physics objects (Ball, Paddle)

**Performance** (`src/glitchygames/performance/`): `AdaptiveClamping` for FPS monitoring

## Design Patterns

- **Singleton**: `SceneManager` (one per engine context), `FontManager`
- **Observer**: `FrameManager` for animation frame changes
- **Strategy**: Timer backends, display update modes, controller modes
- **Proxy**: Event routing through `SceneManager` to `Scene`
- **Factory**: `SpriteFactory` for TOML-based sprite creation

## Testing Guidelines

- Use `pytest` assertions (not unittest style)
- Tests use real pygame, the real display and real files (`tmp_path`); there are no shared mocks. Patch
  only what cannot run in a test (hardware, network, third-party tools such as cookiecutter, the
  clock, injected failures) with targeted pytest-mock `mocker` calls, and assert on what is drawn
  (pixels), not on draw calls. Assertions must not assume the display's pixel format (cocoa's has
  per-pixel alpha)
- Test filenames: Use descriptive names, not generic suffixes like `_simple`
- `tests/harness.py` defaults `SDL_VIDEODRIVER` and `SDL_AUDIODRIVER` to `dummy` for every run (no windows, no sound), so
  plain `uv run pytest` is enough; set either variable yourself only to override (e.g. `SDL_VIDEODRIVER=cocoa`).
- Real pads never reach tests: `tests/sdl_defaults.py` defaults SDL's macOS joystick drivers off
  (`SDL_JOYSTICK_HIDAPI`, `SDL_JOYSTICK_MFI`, `SDL_JOYSTICK_IOKIT` = `0`; each alone finds pads),
  so tests see only their stand-ins (`tests/input/stand_in_devices.py`); set one to `1` yourself
  to test with a real pad. Windows' and Linux's joystick drivers are not covered
- Driver comparison (`tests/driver_comparison.py`; frames recorded by
  `src/glitchygames/testing/frame_fingerprints.py`, compared by `scripts/compare_driver_frames.py`):
  outside CI, `uv run pytest` (and `nox -s test`) also starts the same command on the native
  driver (macOS cocoa + coreaudio, Windows windows, Linux wayland or x11 with dummy audio) as a
  child run, the usual workers split between them (native two thirds), then compares every frame
  each test presented and fails on a difference, re-running the differing tests on both drivers
  to save PNGs and a difference image under `test-results/driver-comparison/pytest/` (the summary
  names the files and the native run's log). Coverage and the 100% gate come from the dummy run.
  Off (dummy only, said in the summary) in CI (`CI=true`), with `--dummy-only`, when you set
  `SDL_VIDEODRIVER`/`SDL_AUDIODRIVER` (that driver alone), and on Linux without a display. A test
  whose frames legitimately differ between runs or drivers (measured frame times, the live
  window's mouse focus) carries `@pytest.mark.frames_vary(reason=...)`: listed, not compared.
  `nox -s compare-drivers` is the on-demand deeper check: an N-way matrix of dummy (run twice to
  find nondeterministic tests), the native driver, `x11-macos` (x11 on XQuartz through an SDL
  built with x11, `scripts/build_sdl_x11.py`) and `x11-linux` (Docker, forwarded to XQuartz);
  it reports every pair in `test-results/driver-comparison/nox/matrix.md` without failing on a
  difference; it fails, keeping the last complete report, when a run recorded no test
  (`docs/quality/driver_comparison.md`)
  After each test the variables, display and mixer a test moved off the run's drivers (a
  constructed `--headless` engine moves them to `dummy`) are put back, the display showing the
  canvas (`tests/sdl_driver_isolation.py`; a few microseconds when nothing changed)
- All tests run with `no_unhandled_events=True` to catch unhandled events as bugs
- The test display rule (`tests/display_canvas.py`): every test starts on the canvas (the default
  pattern; channel 3 with `GLITCHYGAMES_TEST_CANVAS=channel-3`), its display is presented after the
  body, and a test whose last frame is entirely black fails as a rendering bug (opt-out:
  `@pytest.mark.black_frame_expected(reason=...)`, only for a frame black by definition). Assert
  untouched pixels with `canvas_color_at(x=..., y=...)`, never as black
- Coverage minimum: 100% (each remaining miss is audited: dead code is removed, deliberate defensive lines carry a `# pragma: no cover` with the reason)
- Run linting after modifying files
- Check for real bugs before assuming test failures are test issues

## Code Style

- Python 3.14 target
- Ruff for linting/formatting (100 char line length)
- Google-style docstrings
- basedpyright (and ty) for type checking (`pyrightconfig.json`)
- Import ordering enforced by ruff

## Known Bugs

**Active Issues**: see BUGS.md for the current list.

## File Formats and Sprite Loading

**Supported Format**: TOML only (YAML and INI support removed)

**Sprite Loading** (`src/glitchygames/sprites/factory.py`, re-exported by `glitchygames.sprites`):
- `SpriteFactory.load_sprite(filename=...)` - Automatic type detection
- Supports static sprites (single frame) and animated sprites (multi-frame); both load as an
  `AnimatedSprite` (a static one as a single frame)
- TOML format with character-to-color mapping
- Special magenta (255, 0, 255) used as transparency key

**Sprite File Structure**:
```toml
[sprite]
name = "example"
pixels = """
##
##
"""

[colors."#"]
red = 0
green = 0
blue = 0

# Optional alpha for per-pixel transparency
[colors."@"]
red = 255
green = 0
blue = 0
alpha = 127  # 0-254 for transparency, omit for opaque
```

**Animation Format**:
- Multiple `[[animation]]` sections with `namespace` field
- Per-frame timing via `frame_interval` (global or per-frame override)
- Supports RGB (indexed), RGBA (per-pixel alpha), and mixed modes
- See ANIMATION_README.md for complete details

## Bitmappy Editor Features

**Multi-Controller System** (up to 4 simultaneous controllers):
- Colors: Red (0), Green (1), Blue (2), Yellow (3)
- Modes: Film Strip, Canvas, and the R, G and B sliders (`ControllerMode`)
- Mode switching (`ModeSwitcher.handle_trigger_input`): L2 steps forward (film strip -> canvas ->
  R -> G -> B -> film strip), R2 steps back (B -> G -> R -> canvas -> film strip; nothing on the
  film strip); L2 wins when both trigger together
- Independent navigation and editing per controller
- Visual collision avoidance for overlapping indicators
- Comprehensive undo/redo including controller positions

**Key Features**:
- Flood-fill tool (Control+click)
- Onion skinning ('O' key, right-click frames)
- TOML/PNG drag-and-drop support
- Undo/redo system for canvas and film strip operations
- AI sprite generation via aisuite
- Voice recognition support
- ASCII renderer with transparency support

**Controller Controls** (see CONTROLLER_CONTROLS_README.md):
- Film Strip Mode: D-pad navigation, A select, L1/R1 frame switching
- Canvas Mode: D-pad movement, A paint, L1/R1 8-pixel jumps
- Slider Mode: D-pad adjust, L1/R1 adjust by 8
- B button: Undo, X button: Redo, Y button: Mode-specific toggles

## Recent Feature Completions

**Recently Completed** (see `plans/future-features.md` and `plans/engine-audit.md` for the roadmap):
- ✅ Multi-controller navigation and editing (4 controllers, 57+ tests)
- ✅ Controller position undo/redo system
- ✅ Onion skinning for animation
- ✅ Per-pixel alpha support for AI-generated sprites
- ✅ Flood-fill tool (Control-click)
- ✅ TOML drag-and-drop support
- ✅ Enhanced ball boundary physics
- ✅ Colorized ASCII output

**High Priority Features Planned**:
- Memory optimization (100k+ frame FPS buffer)
- Real-time performance monitoring
- Sprite format linter
- Universal undo/redo enhancements
- Pixel-level copy/paste system

## Important Notes

- **Sprite Loading**: Use `SpriteFactory` not direct `BitmappySprite` for new code
- **Coverage**: 100% minimum required (`--cov-fail-under` in pyproject.toml); no exclusions in configuration
- **Documentation**: Architecture details in `docs/architecture/` (the mkdocs site) and root .md files
  (ANIMATION_README.md, LOADER_README.md, etc.). The engine's API reference pages are written by
  hand (`docs/glitchygames/`); each workspace member package's (`mr_muncher/index.md`) is
  generated in the build by `scripts/gen_ref_pages.py` (mkdocs-gen-files), and mkdocs.yml's nav
  names it (`tests/test_workspace_config.py` checks every member's)
