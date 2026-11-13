# CLAUDE.md

Guidance for Claude Code in this repository. This file holds the commands, the layout and the
rules code must follow; the detail lives in `docs/architecture/` and in the module docstrings
named below (many say "whose docstring is the contract": read it before changing that module).

## Project Overview

GlitchyGames is a Python 3.14 game engine on pygame-ce with an event-driven architecture, a
pixel-art editor (Bitmappy), example games, and exact gameplay recording and replay.

- Engine: `src/glitchygames/`. Workspace members (plans/2026-10-24-workspace-packages.md): games
  in `src/games/` (paddleslap, brave-adventurer, clockwork-keep, mr-muncher, drawing-fire), demos
  in `src/demos/` (dt, joystick, sound-board, text-input), apps in `src/apps/` (bitmappy). Each is
  its own package with its own code, tests and golden replay (recipe:
  docs/architecture/game_packages.md).
- Nothing at the repository root is importable as the package: tests and tools import the
  installed engine. A script importing `scripts.*` runs as `uv run python -m scripts.<name>`.
- Paths here are written from the repository root. Finished plans and resolved BUGS.md entries
  name locations as they were then (before #105 the engine was the root-level `glitchygames/`).
- The engine never imports a member, in source or tests, and no engine module or engine test
  reaches `scripts/` (enforced: `tests/test_workspace_config.py`, `tests/test_suite_collection.py`).

## Development Setup

```bash
uv sync --all-extras --all-groups --all-packages   # everything development uses
direnv allow        # optional: .envrc syncs on entry; on macOS installs PulseAudio, syft, grype
uv sync --upgrade --all-extras --all-groups --all-packages   # deliberate upgrade; review uv.lock
```

The packages are not on PyPI yet: outside the repository, `uv build --all-packages` and install
from `dist/` (extras: `games`, `apps`, `templates` for cookiecutter).

## Common Commands

```bash
pytest                      # full suite, 100% coverage; outside CI also on the native SDL driver,
                            # failing on any frame that differs (see Testing Guidelines)
pytest --dummy-only         # fast iteration: dummy driver only
                            # addopts already has -n auto and -p no:randomly (fixed order;
                            # only nox -s test-random shuffles)
ruff format src tests scripts noxfile.py
ruff check src tests scripts noxfile.py     # --select I --fix for import order
basedpyright                # pyrightconfig.json
```

Nox (`nox -l` lists all; each session's docstring explains it):
- `format`, `lint` (aggregates), `static-analysis` (basedpyright + ty), `test`, `test-random`
  (shuffled order, the pre-push hook; `-- SEED` repeats one), `performance-test`
- `compare-drivers` (N-way driver matrix; pre-push runs `-- --drivers native
  --fail-on-difference`), `test-linux-x11`, `test-linux-ci` (CircleCI's Linux job in Docker)
- `replay-metrics` (measure every golden and demo into the pending ledger), `timer-report`
- `security-scan` (bandit, syft SBOM `docs/sbom.cyclonedx.json`, grype, license check; commit
  the regenerated SBOM with any `uv.lock` change; exceptions in `.grype.yaml` and
  `scripts/check_licenses.py` are the owner's)
- `build`, `build-wheel`, `build-binary` (stamp the commit into `_build_info.json` around the build)
- `docs-serve` (isolated env; refuses a taken address), `docs-deploy` (CircleCI runs it after
  every merge to main; refused unless HEAD is on origin/main), `code-complexity`

### Running games and tools
### Nox Sessions (Automated Testing Pipeline)
```bash
# --- Aggregate sessions ---
nox -s format              # Run ALL formatters (code + TOML)
nox -s lint                # Run ALL linters (code, docs, YAML, TOML, CI, deps, dead code)

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

# --- Static type analysis ---
nox -s static-analysis              # Run ALL type checkers (basedpyright + ty)
nox -s static-analysis-basedpyright # Run basedpyright only
nox -s static-analysis-ty           # Run ty only

# --- Testing ---
nox -s test                # Run tests with coverage
nox -s test-random         # The suite in a shuffled order (pytest-randomly, a new seed each run; `-- SEED` repeats one): the pre-push hook. Dummy drivers, no coverage; a failure prints the seed and the one-process command that replays it. Every other run keeps the files' order (addopts: -p no:randomly)
nox -s performance-test    # Run performance benchmarks (every testpath: the engine's and each member's)
# tests/benchmarks/test_logging_cost.py (only under --benchmark-only): every golden and bundled demo at
# --log-level warning, info and debug; the chattiest loggers and the cost per frame (docs/quality/performance.md)
nox -s timer-report        # Report this machine's timer accuracy: VM?, CPU share, sleep wakes (diagnostic)
nox -s replay-metrics      # (the project's editable install) Rebaseline every golden replay + bundled demo headless; append run-ledger rows to test-results/replay-metrics/pending.jsonl (skips this commit+machine; `-- --force`, `-- --allow-dirty`, `-- --only TEXT`)
nox -s test-linux-x11      # Tests on Linux in Docker: X11 windows on XQuartz, sound on the Mac's PulseAudio (starts it; `pulseaudio --kill` stops it; macOS)
nox -s test-linux-ci       # Tests as CircleCI's Linux job runs them, in Docker: its amd64 image, 2 GB without swap, 1 CPU, serial, CI=true, the RSS guard (read from .circleci/config.yml); results in test-results/linux-ci/
nox -s compare-drivers     # N-way matrix: dummy x2, native, x11-macos, x11-linux (whatever runs here), each its own run; `-- --drivers a,b` (`native`: every native driver here), `-- tests/x`; report test-results/driver-comparison/nox/matrix.md. Each run has 4 workers (`-- --workers N`, `-- --workers auto` every core). A pre-push hook runs `-- --drivers native --fail-on-difference --workers auto --skip-when-frames-cannot-change`: a driver difference stops the push (BUGS.md #254), and a push whose every path is under plans/, docs/, quality/, .circleci/ or .github/, or is root Markdown, skips the comparison (no frame can change; `_path_cannot_change_frames`)
nox -s build-sdl-x11       # Build SDL with x11 for macOS (cached in ~/Library/Caches/glitchygames/sdl-x11; SDL_DYNAMIC_API loads it) and check it on XQuartz

# --- Code quality ---
nox -s code-complexity     # wily: the working tree's changes against HEAD (history measured in a temporary worktree, never in yours); `-- --graphs` generates docs/quality/graphs/ (gitignored), `-- --rank` ranks files

```bash
uv run paddleslap            # also brave-adventurer, clockwork-keep, mr-muncher, drawing-fire,
uv run bitmappy              # dt-demo, joystick-demo, sound-board-demo, text-input-demo
uv run glitchygames --help   # every recording/replay/measurement tool, with its options
uv run paddleslap --record-trace run.jsonl.gz
uv run paddleslap --replay-trace run.jsonl.gz --headless
uv run glitchygames verify   # every game's goldens and bundled demos, headless
```

Every tool is described once in `src/glitchygames/replay/tools/registry.py` (`TOOLS`) and is both
a flag on every game and a `glitchygames` subcommand with the same options; project settings come
from `[tool.glitchygames]` in `pyproject.toml`. A game may not define an argument that clashes
with a tool option. Reference: docs/architecture/gameplay_replay.md.

### Local AI service

Installed by Ansible (`ansible/macos_ai_service.yml`; plans/lucid-circuit.md), its own project in
`services/ai-service/` (own tests, lock file, 100% coverage) that shares no code with the engine.
Games reach it only over a socket (127.0.0.1:23231) through `src/glitchygames/ai_link.py` and
`ai_host.py`: on by default (`--ai`/`--no-ai`), never with `--headless`, in a replay or browser.
The test harness points `GLITCHYGAMES_AI_INSTALL_ROOT` at nowhere. The backtick key opens the
read-only AI console (`src/glitchygames/ai_console.py`).

## Architecture Overview

### Core Engine Components

**GameEngine** (`src/glitchygames/engine/__init__.py`): one per running game
(`current_engine()`); pygame setup, display, argument parsing, O(1) event dispatch. Games log at
`--log-level warning` by default; every start logs the options block at CRITICAL (secrets
redacted). Argument rules: docs/architecture/argument_system.md.

**SceneManager** (`src/glitchygames/scenes/__init__.py`): runs the frame loop. Each frame:
begin (camera flags), logic (`Scene.dt_tick(dt)`), events, frame services (shake, rumble), camera
aim (`Scene.camera_target()`), world-sprite positioning and culling, render (`Scene.update()`,
then `LayeredDirty.draw()`), still-camera shake advance, present, `_finish_frame` (pacing). The
active scene is always a `Scene` or None. Docs: docs/architecture/playback/how-a-frame-runs.md.

**Game Host** (`src/glitchygames/host.py`): a transparent outer game on every live run;
`HostSources` sits between the live doors and the recorder, so what the host adds or hides is
recorded. `GameHost.run_async` / `GameEngine.start_async` drive the loop one awaited tick at a
time (the browser).

**Exit Codes** (`src/glitchygames/exit_codes.py`): `ExitCode` IntEnum; never write the number in
code or tests. 0/64-70/73 equal `os.EX_*`; signals are 128 + N.

**Frame Pacing** (`src/glitchygames/timing.py`): `--timer-backend auto` (default) is `FastTimer`
with a measured sleep model; `pygame` is legacy. Default target 60.01 FPS (`--target-fps 0` is
uncapped); a scene may set `TARGET_FPS` and `MAX_FRAME_SECONDS`. `dt` is measured start to start
in `_finish_frame` only.

**World Space** (`src/glitchygames/world.py`, `camera.py`):
- A sprite with `COORDINATE_SPACE = CoordinateSpace.WORLD` keeps float `world_x`/`world_y`; the
  engine is then the only writer of its `rect` and owns its `visible`. Hide one with
  `hidden = True`, never `visible = False`.
- Never read a world sprite's `rect` in game logic (`dt_tick`, handlers): it is where it was last
  drawn. Use `world_x`/`world_y`, `snapped_world_position` or the collision rect.
- The pose rule: draw a sprite's pose (its image, so its hitbox) in `dt_tick`, before collision;
  `update()` runs after collision and does only visual work. Collision resolution also belongs
  in `dt_tick`.
- Camera: `camera.follow(target=..., axes=FollowAxes.X)` in `setup()`, or override
  `camera_target()`. Parallax layer draw functions must depend only on their arguments unless
  `animated=True`.
- Golden traces (`tests/world/test_golden_traces.py`): every difference from the pre-world-space
  baselines must be explained by exactly one `ExpectedDifference`. Never re-record the baselines
  to make a change pass.

**Clocks** (`src/glitchygames/clock.py`): every time read comes from here or `Scene.game_time`,
so replays serve the same values.
- `Scene.game_time` for gameplay timers; `frame_clock_seconds()` for animation and UI timing;
  `wall_clock_time()` for timestamps; `elapsed_seconds()` for throttles and timeouts;
  `measured_seconds()` for diagnostics only (never affects what is drawn, played or recorded);
  `raw_*` are the engine's own.
- Import the module (`from glitchygames import clock`, call `clock.raw_sleep(...)`), never a
  function by name, and never name a local `clock` where the module is imported (SceneManager's
  pygame pacing clock is `pacing_fallback_clock`). `clock.py` is the only file that may use `time` or read `datetime` now.
- A function that waits or measures takes its sleep/counter as a parameter defaulting to None,
  resolved at call time. Tests pass a fake or patch `glitchygames.clock.<function>`, never `time`.

**Gameplay Recording and Replay** (`sources.py`, `live_sources.py`, `recording.py`, `replay/`,
`randomness.py`; docs: docs/architecture/gameplay_replay.md, docs/architecture/playback/):
- Doors: the engine takes events, frame time, polled input, devices, saves, clocks and the seed
  only through the active `EngineSources` (`LiveSources`, `HostSources`, `RecordingSources`,
  `ReplaySources`). `tests/test_engine_doors.py` fails on any bypass outside its allowlists.
- Polled input: `current_input()` returns the frame's immutable `InputSnapshot`. Never poll
  pygame or a device directly; enumerate and open devices only through
  `active_sources().devices()`. Games read `Scene.input_devices`
  (`src/glitchygames/input/input_devices.py`).
- Saves: `glitchygames.state.open_saves(app_name=...)`; replays use an in-memory sandbox.
- Randomness: draw only from named streams (`random_stream('name')`, `numpy_stream('name')`)
  seeded by `--random-seed`. Never `secrets`, `random.SystemRandom`, global `random.*` or an
  unseeded `np.random.default_rng()` in gameplay (`tests/test_unseeded_randomness_guard.py`).
- Engine code posts events with `recording.post_event`; code driving a game from outside its
  logic (supervisor, harness) uses `post_input_event`.
- A game whose state is drawn rather than kept in sprites must post an internal event for what
  matters, or its replay compares nothing of it.
- Golden replays (`<member>/tests/fixtures/replays/*.jsonl.gz`) and bundled demos
  (`<package>/demos/*.jsonl.gz`) are recorded by `scripts/record_scripted_session.py` and
  `scripts/record_bundled_demos.py`. Re-record only deliberately, as a reviewed step. Every golden
  ends with the controls tail (pause, every bound control, the game's own quit): a new game's
  bindings must be listed in `tests/replay/golden_replay_controls.py`.
- Exit codes, refusals and the rules of each mode (`--replay-trace`, `--rebaseline`, `--audit`,
  `--compare-trace`, instant replay, demos, ghosts) are in `replay/driver.py`'s docstring and the
  docs above.

**Engine Context** (`src/glitchygames/engine_context.py`; docs/architecture/engine_context.md):
the state one running game owns, so several games can run in one process (the Arcade). New
per-game state is a `ContextSlot` declared at module level and read with
`current_context().value(slot=...)` at use time, never at import; every slot needs an isolation
check in `tests/test_engine_context.py`. New module- or class-level mutable state fails
`tests/test_process_state_guard.py` unless it is a slot or listed with its audit row. Each context
has its own audio engine, scene manager and performance manager. The old class-level names
(`GameEngine.OPTIONS`, ...) are read-only views engine code never reads. Inner games
(`src/glitchygames/inner_game.py`) draw on a render target and use a private event queue; engine
code uses `display_surface()`, never `pygame.display.get_surface()`.

**Source revision** (`src/glitchygames/build_info.py`): the engine's and the game's commit, from
git, a git archive, or a build stamp; held by every recorded run.

**Screen Shake and Rumble** (`effects/shake.py`, `input/rumble.py`):
`Scene.shake(Shake(...), targets=ShakeTarget.WORLD | ShakeTarget.SCREEN)`.

**Sound Synthesis** (`src/glitchygames/audio/`; docs/architecture/sound.md, specs in
`docs/specs/2026-11-02-sound-engine-*`):
- `scene_manager.audio.sound(source, ...)` returns a compiled `Sound`; `Sound.play(...)` returns
  a `SoundHandle`. Request sounds in `setup()`: a gameplay compile is counted and logged.
- Sources: a short name looked up in the scene's `SOUND_DIRECTORY`, a path (`file.toml#name`) or
  an `Instrument`. Sound files are TOML version 1 (v0 still loads).
- Voice ends follow played time (the served `dt`), never the device, so replays match.
- Mixer: 44100 Hz, signed 16-bit, stereo, 512-sample buffer.
- Instrument catalog (`audio/instruments/`): `instruments.get(name)` returns an `Instrument`
  built once per process; `instruments.entry(name)` gives family and range; `CATALOG` and
  `ALIASES` are read-only. `tests/audio/test_instrument_catalog.py` renders and pitch-checks
  every entry.
- `SoundBank`, `load_sound` and `live_audio` are the older toolkit, kept until M2 moves the games.

**Transitions** (`src/glitchygames/transitions/`): cues run after the old scene's cleanup, so they
may use only SceneManager services.

**Debug Overlay** (`src/glitchygames/debug/`): `--debug-overlay` or F3, F4 cycles panels
(hitboxes, physics, camera, performance, audio, AI). Drawn in `_present_frame`, never in
screenshots or traces. Scenes and sprites may add `debug_draw(surface, camera)`.

**Scene backgrounds** (`src/glitchygames/backgrounds.py`): a scene with no background shows the
default TV test pattern (or channel 3), never black, because black can't be told from "nothing
rendered". Scenes that want black set `background_color` explicitly. The CRT power-on sequence
(`crt_power_on.py`, sound in `crt_power_on_sound.py`) plays before every game, skipped on the
dummy driver and before replays/recordings; its sounds compile once per process
(`ENGINE_SOUND_CACHE`).

**Pixel snapping** (`pixel_snap.py`): `Scene.PIXEL_SNAP_MODE`, per-sprite `pixel_snap_mode`.

**Opaque frames** (`opacity.py`, BUGS.md #142): on macOS the display has per-pixel alpha and
shows alpha 0 as black. Backgrounds must be opaque; the display is made opaque before every
present. Check rendering on the real driver with `SDL_VIDEODRIVER=cocoa uv run pytest`.
**GameEngine** (`src/glitchygames/engine/__init__.py`)
- Orchestrator extending `EventManager`, one per running game (`current_engine()` is the current
  engine context's)
- Handles pygame initialization, display management, event routing
- Bootstraps command-line arguments for all games
- Pre-computes its own `event_handlers` dict (per engine; `GameEngine.EVENT_HANDLERS` is the
  current game's, a read-only view) for O(1) event dispatch
- Logging: a game logs at `--log-level warning` by default (the owner, 2026-10-28; the tools'
  level), so the exit code, whether the seed was rolled or given, and the end-of-run performance
  reports (INFO) show only with `--log-level info`; the seed itself is always in the options
  block below. Each failure a player sees (exit 70 from a run's or a game flag
  tool's crash, a failed teardown, a failed playback) logs `exit_codes.BUG_REPORT_HINT` after
  its traceback ("run the game again with --log-level info and include the output"; not the
  `glitchygames` command's, which has no `--log-level`). Every engine start logs the whole
  options dictionary once at CRITICAL (`startup_options_block`: sorted, aligned, nested values
  indented, path options relative to the project root inside it and absolute outside, any
  option named like a key/token/secret/password/credential `<redacted>`; "for now",
  plans/future-work.md; docs/architecture/argument_system.md)

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
  restarts need a new process, so in a browser they only show a message (`RESTARTS_AVAILABLE`). Both
  starts share everything up to the first frame: `_begin_run()`, the CRT power-on (its sound from
  `_power_on_sound_cues()`, handed back by `_hand_back_power_on`) and `_build_game()`; `_run_game`
  runs them blocking, `start_async` awaiting the power-on's ticks

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
  - `FastTimer`: High-resolution `clock.raw_counter_ns()` (`time.perf_counter_ns()`) with
    sleep+spin hybrid (`clock.raw_sleep`): it sleeps so it wakes `sleep_granularity_ns` (1 ms)
    before the deadline, then spins the rest. It takes its counter and sleep as parameters
    (`FastTimer(read_counter_ns=..., sleep=...)`, also `measure_sleep_model` and
    `sleep_overshoot_ns`), so tests pass a fake clock instead of patching one
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
- Paced frame time (`dt`, FPS tracking) is always measured with `clock.raw_counter_seconds()`
  (`time.perf_counter()`), and
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
  `clock.raw_counter_seconds()` once; that reading ends this frame and starts the next, and `self.dt` is
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
- Golden traces (`scripts/record_golden_traces.py` with our input scripts in
  `scripts/golden_inputs.py`, on the engine's harness
  `src/glitchygames/replay/tools/golden_traces.py`; `tests/world/test_golden_traces.py`) replay
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
- Raw time (the engine's own, never replayed, not for game code): `raw_counter_ns()` /
  `raw_counter_seconds()` (`time.perf_counter_ns()` / `perf_counter()`: frame pacing, the frame
  loop's measurement of each frame, the audio-glitch probe, the performance statistics' log
  interval, a measurement tool's summary), `raw_sleep(seconds)` (`time.sleep`: pacing, the
  replay viewer, the power-on frames, waits for a window manager, microphone, controller speaker
  or AI retry) and `raw_wall_clock_time()` (`datetime.now(tz=UTC)`: the live doors' wall clock,
  a recording's `recorded_at` and each run's `measured_at`)
- `glitchygames.clock` is the one clock (the owner, 2026-10-28): every caller, engine and members,
  imports the module (`from glitchygames import clock`) and calls `clock.elapsed_seconds()`,
  `clock.raw_sleep(...)` and so on, never a function imported by name
  (`tests/test_engine_doors.py` `clock_functions_imported_by_name` fails on one). Every read
  then looks the function up in one place, so one patch on `glitchygames.clock` reaches every
  reader. A local name never says `clock` where the module is imported (`SceneManager`'s pygame
  pacing clock is `pacing_fallback_clock`)
- A function or class that waits or measures takes its sleep or counter as a parameter where
  that is clean (`FastTimer(read_counter_ns=..., sleep=...)`, `play_power_on(sleep=...)`,
  `listen(sleep=...)`, `sleep_coarsely(sleep=...)`, `VoiceEventManager(sleep=...)`, Bitmappy's
  `_create_ai_retry_decorator(sleep=...)`, which hands tenacity its `sleep`). The default is
  None, resolved to `clock.raw_sleep` (or `clock.raw_counter_ns`) when called: a default of
  `clock.raw_sleep` would be bound once, when the function is defined, and a patch on
  `glitchygames.clock` would never reach it. Tests pass a fake; otherwise they patch
  `glitchygames.clock`'s function (`mocker.patch('glitchygames.clock.raw_sleep')`), never a
  module's copy and never the shared `time` module (ruff's preview rule `shared-clock-mock`)
- `clock.py` is the only file in the package (engine and members) that may use the `time` module
  at all or read `datetime`'s now (`tests/test_engine_doors.py`); `pygame.time.set_timer`/`Clock`
  stay fenced as before (by function: `SceneManager.__init__`'s `pacing_fallback_clock`).
  `PygameTimer` (`--timer-backend pygame`) reads `pygame.time` through its own `self._pg`
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
- Guard: `tests/test_engine_doors.py` AST-scans the package. Any use of the `time` module or a
  `datetime` read of now outside `clock.py`, pygame key/mouse polling, `pygame.event.get`/`post` and joystick/controller enumeration or construction outside
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
  only (controller events blocked), `controller` mapped pads only. Stand-in devices
  (`src/glitchygames/input/stand_in_devices.py`: doors and a registry that answer as SDL would
  and hand a recorder what they opened) go through the door: tests use them (their
  descriptors in `tests/input/stand_in_devices.py`), and a scripted session records a game
  played on one (`record_scripted_session(stand_in_devices=[...])`, `GoldenTraceEngine`'s
  `stand_in_devices`; its pad events reach the snapshot with `polled_input`). `stand_in_devices`
  has three cases: None (the default) the machine's real devices, an empty tuple no devices at
  all (stand-in doors around an empty registry: real ones are never seen or opened), a non-empty
  tuple exactly those stand-ins. `--list-input-devices`
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
- The engine's tools (Part 3 Stage D; `src/glitchygames/replay/tools/`): every recording, replay
  and measurement tool is described once in `registry.TOOLS` (`Tool`, `ToolOption`), and both
  front ends are built from it so names and options can't drift: `GameEngine.args` adds each
  tool to every game's command line (`add_game_flags`: `--record-trace` with `--random-seed`
  and `--headless`, `--replay-trace` and its options `--replay-fps`, `--audit`, `--compare-processing`, `--max-processing-slowdown`,
  `--replay-pause-at-frame`, `--rebaseline`, `--replay-digest`, `--headless`, `--compare-trace
  OLD`, `--compare-alpha PERCENT` and the hidden `--replay-frame-stream PORT:TOKEN`
  (`ToolOption.hidden`: parsed on both front ends, in neither's help),
  `--record-golden-trace PATH` with `--input-script MODULE:NAME`, `--frame-count N`,
  `--random-seed` and `--headless`, `--record-session PATH` with those and `--controls-tail
  MODULE:NAME`, `--polled-input`, `--input-only-placements`, `--verify [PATH ...]` with
  `--only TEXT`), and `GameEngine.__init__`
  (`_run_game_flag_tool`, before the engine starts pygame or opens a window) runs a tool with a
  game handler in its place and exits with its code: one that doesn't run the game, or one that
  runs it its own way (record-golden-trace in the golden-trace harness, record-session in the
  scripted-session recorder), so the game's own engine never builds a second one
  (`run_game_flag_tool`). The
  `glitchygames` console script (and `python -m glitchygames`, both via
  `src/glitchygames/__main__.py`, which hides pygame's banner first) has the same tools as subcommands
  (`glitchygames record-trace GAME PATH`, `glitchygames replay-trace PATH [--game GAME]`,
  `glitchygames record-golden-trace GAME PATH --input-script MODULE:NAME --frame-count N`,
  `glitchygames record-session GAME PATH --input-script MODULE:NAME --frame-count N`,
  `glitchygames verify [PATH ...] [--only TEXT] [--game GAME ...]`,
  `glitchygames measure [PATH ...] [--force] [--allow-dirty | --skip-dirty] [--only TEXT]
  [--code-tree TREE] [--rows-directory DIR] [--pending PATH] [--game GAME ...]`,
  `glitchygames unmeasured [--code-tree TREE] [--rows-directory DIR] [--pending PATH] [--game GAME
  ...]`, `glitchygames clear-published [--pending PATH]`,
  `glitchygames report PATH [--threshold PERCENT] [--minimum-ms MS] [--spans N]`,
  `glitchygames performance-pages DIRECTORY [--published]`,
  `glitchygames sound-render SOURCE --sound-output PATH [--sample-format int16|float32]`,
  `glitchygames sound-migrate FILE [--migrated-output PATH]` (`replay/tools/sound_tools.py`:
  offline render through `glitchygames.audio.render_to_file`; v0 recipes to a v1 sound file,
  refusing what v1 cannot say yet), each with
  `--project-root DIR`; arguments after a bare `--` go to the game). `--game` is the one
  command-only option (`COMMAND_ONLY_FLAGS` in `tests/replay/tools/test_registry.py`): a game needs
  none, it is the game. `verify` (`verify.py`) replays each recording headless in a child (no
  seed: it always compares; `--random-seed`, given to it or among the arguments it passes on, is
  refused OPTIONS_REFUSED before anything runs), prints `PASS|FAIL <name>: <why>` per recording and `verify: N of M
  recordings passed`, and exits SUCCESS only when all matched (or none was found, which it says),
  REPLAY_DIVERGED when the only failures diverged, else the first other failure's code. On the
  game it runs from `__init__` (the game is never built) and replays through the game started
  again (`children.running_game_command`); with no PATHs it verifies the game's own recordings
  (`recordings.game_recordings(*, identity, settings, project_root)`: the `golden-globs` goldens
  its console script replays, plus `<package>/demos/*.jsonl.gz`). The command with no PATHs runs
  `GAME --verify` per game (`--game`, else `[tool.glitchygames] games`); with PATHs each is
  replayed by the game its header names (or the one `--game`). Both find the project the same
  way (`--project-root`, else the nearest directory up whose `pyproject.toml` has
  `[tool.glitchygames]`, else the nearest with a `pyproject.toml`, so inside a workspace member
  the root is the project: `settings.find_project_root`, Stage D Task D6; none is said) and pass the game's other arguments to the games they
  start (the command's after `--`; the game's own beside `--verify`, `registry.tool_free_arguments`).
  A replay that crashes before its engine starts exits 1 and counts as a divergence (user, 2026-10-27). It starts the game as a child
  (`children.py`: `resolve_game` reads `GAME` as a script path, `MODULE:CALLABLE`, an installed
  console script or a module; `replay-trace` takes the game from the recording's header and asks
  for `--game` when its module no longer imports). `children.py` also holds the console-script
  lookups and the headless child replay/rebaseline the pytest plugin uses (pytest-free).
  `measure`, `unmeasured` and `clear-published` (`replay/tools/measure.py`, Stage D Task D6, moved
  from the deleted scripts/replay_metrics.py) are the run ledger's tools: `--measure [PATH ...]`
  rebaselines the game's own recordings (or the PATHs) headless through its console script into
  the project's pending ledger (or `--rows-directory`, row files), skipping what this machine
  measured for the game's commit (or `--code-tree`); each recording under its recorded seed, so
  `--random-seed` is refused as verify refuses it. The commit, refusal and rows are the GAME's
  revision (`identity.game_source_revision`, else the engine's): uncommitted changes or an
  unknown commit are refused OPTIONS_REFUSED unless `--allow-dirty` (a trial row) or
  `--skip-dirty` (nothing measured, SUCCESS). `glitchygames measure` runs `GAME --measure` per
  game (`--game`, else `[tool.glitchygames] games`) and exits with the first failure's code
  (`combined_exit_code`); with the settings' games, a golden none of them replays is a failure
  line naming why (`unclaimed_goldens`). `unmeasured` lists, one ledger name per line (summary on
  stderr), what `measure` would measure (`missing_measurements`); the command reads a console
  script's game without starting it (`identity.console_script_identity`). `clear-published` drops
  the pending rows the published ledger holds. A pending ledger under `.glitchygames/` is made
  through `settings.ensure_local_directory`; settings come from the project found, never from a
  module-level read of ours.
  `report` (`replay/tools/report.py`, Stage D Task D7, moved whole from the deleted
  scripts/recording_report.py; output byte-identical) prints a recording's runs, speed changes
  and behaviour-change map. `performance-pages DIRECTORY` (`replay/tools/performance_pages.py`,
  D7: the rendering half of scripts/generate_performance_graphs.py and its source merge) writes a
  local build (default) of the project's ledger and graph pages (`merged_ledger`: row files landed by git,
  published and pending rows, from the settings given; `write_performance_pages`); with
  `--published` it builds what a deploy publishes (trials and unlanded row files left out), through
  the same `build_performance_pages` the docs hook's gh-deploy build uses. Neither runs
  the game; on the game both run from `__init__` (never built). Our docs build reaches it through
  `scripts/mkdocs_hooks.py` -> `scripts/generate_performance_graphs.py` (our docs paths and the
  `performance_graphs.md` snippet only; it passes our settings) -> the engine.
  An option may be listed under several tools but is one game flag (`--random-seed`: every tool
  that runs the game; `--headless`: record-trace, replay-trace, record-golden-trace and
  record-session; `--input-script` and `--frame-count`:
  record-golden-trace and record-session). `--random-seed` (the user's rule, 2026-10-26)
  defaults to None everywhere: a run or recording rolls a seed (the harness tools too; our
  goldens pass `RANDOM_SEED`), a replay uses the recording's; a replay given another seed plays
  the inputs out under it without comparing or writing (headless: the rebaseline's summary, exit
  0), `--rebaseline NEW --random-seed N` records them under N, and `--audit` under another seed is
  refused (rule 19 of `replay/driver.py`). The end-to-end proof is
  `tests/replay/tools/test_an_unseen_game.py` (Task D9): a stand-in game in its own git
  repository in `tmp_path` (package under `src/`, a launcher script, an input-script module, a
  golden, a local bare repository as its published ledger), run through every tool in `TOOLS` on
  both front ends and in all three `GAME` forms, in a project with a `[tool.glitchygames]` and in
  one without; each case checks the exit, exactly the files written, the stand-in's commit in its
  rows and runs, and (an import watch in the children's `sitecustomize`) that no child imported
  `scripts`, `tests` or a member; a tool in `TOOLS` without a case there fails it. The
  golden-trace harness (`golden_traces.py`: `record_trace(*, scene_class, script, frame_count,
  ...)`, `replay_golden_recording(*, scene_class, script, path, ...)`, `golden_game`,
  `GoldenTraceEngine`, `InputScript`, `press`/`release`) runs any game by its scene class and an
  `InputScript`; `load_input_script(*, reference)` reads `--input-script MODULE:NAME`: a callable
  taking no arguments that returns an `InputScript`, its module looked for in the current
  directory first. A trace's `game` is the scene's logical name (our goldens relabel theirs with
  the game key). The scripted-session recorder (`scripted_sessions.py`:
  `record_scripted_session(*, scene_class, script, frame_count, path, controls_tail=None,
  polled_input=False, input_only_placements=False, random_seed=None)`,
  `ScriptedInputSupervisor`, `PostedPolledInput`, `GameDidNotQuitError`) runs any game for real
  with `--record-trace` while a supervisor posts the script. Our five games' scripts and controls
  tails are `scripts/golden_inputs.py`. Two tool flags at once are
  refused, and a tool that runs no game must have a game handler. Every tool's flag and option is
  added to every game's parser, so a game may not define one of those names (`--threshold`,
  `--only`, ...; `test_no_tool_option_clashes_with_any_of_our_games_arguments` checks ours). The general flags no tool
  lists (`--resolution`, ...) stay in `GameEngine.args`. A project's settings for the tools are
  `[tool.glitchygames]` in its `pyproject.toml` (`settings.py`: `load_project_settings(*,
  project_root)` -> `ProjectSettings`, kebab-case keys, unknown keys refused by name, defaults
  for a project without the table); ours, in the root `pyproject.toml`, hold what were the
  constants of `code_tree.py` and `recording_metrics.py` (`ledger-directory`, `measured-paths`,
  `unmeasured-paths`, `landed-ref`, `pending-ledger`, `published-ledger` as `REF:PATH`,
  `recording-renames`), which those modules now take as arguments. A game's identity comes from
  its scene class alone (`identity.py`: `game_identity(*, game)` -> `GameIdentity` with its
  package, package directory, console script and distribution, each None when not found)
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
- Bundled demos (Part 3 Task 4): a workspace member's `<package>/demos/<name>.jsonl.gz` ships in
  its wheel as package data (hatch includes every file in the package; no pyproject change).
  One engine lookup finds them in the installed packages,
  `glitchygames.bundled_demos.bundled_demos(*, packages)` (`BundledDemo`: console script, path,
  install name; `packages` is required, no default since Stage D Task D5: a game passes its own,
  our tests `tests/workspace_expectations.MEMBER_PACKAGES`); the replay plugin's
  `bundled_demo_paths(*, packages)` and `replay/tools/recordings.py` (which measure uses)
  call it. Development installs are editable (`uv sync`; the
  `replay-metrics` nox session runs `uv run --all-packages`), so the ledger names a demo by its
  repository path; outside a repository, by its install name. Every Arcade tile has one (Arcade
  sub-plan 2, plans/2026-11-11-arcade-2-demos.md), ten in all, each under its member's
  `src/<package>/demos/` (`tests/workspace_expectations.py` `EXPECTED_BUNDLED_DEMOS`): PaddleSlap
  `rally`, Clockwork Keep `climb`, Brave Adventurer `classic` and `papyrus` (both in the
  launcher's package, `brave_adventurer_modes/demos/`: its console script is the one that
  replays them), Mr. Muncher `chase`, Drawing Fire `battle`, Bitmappy `drawing`, and the dt,
  text-input and joystick demos' `timing`, `typing` and `pad` (the Sound Board has no tile and
  no demo). One command records them, `scripts/record_bundled_demos.py` (`DEMO_RECIPES`, one
  `DemoRecipe` per demo: scene, input script, frame count, package and name, `polled_input`,
  `input_only_placements`, `stand_in_devices`; `uv run python -m scripts.record_bundled_demos
  --demo KEY` or `--all`): each is `--script-only` (no controls tail, no quit) under the goldens'
  `RANDOM_SEED` at 800x480, with the AI install root pointed at an empty directory, with no
  devices at all unless the recipe names stand-ins (`stand_in_devices=()`, the recipe's default),
  and SDL's real joystick drivers off for the session as defence in depth. The games reuse their golden scripts' frames before the
  controls tail (Mr. Muncher's chase a demo-only script, `scripts/demo_inputs.py`, which also holds
  the dt, text-input, joystick and Bitmappy scripts); the joystick demo's pad is a stand-in
  ('GlitchyGames Demo Pad', `ScriptedSessionOptions.stand_in_devices`), which the recording's
  header holds and its replay opens again. `tests/replay/test_bundled_demos.py` also checks each
  demo is at most `MAXIMUM_DEMO_BYTES` (256 KB) and ends with nothing held: no key, mouse or pad
  button down, every pad axis at rest (exactly 0) and every hat centred, since the Arcade loops
  it. PaddleSlap's (the first) is
  `src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz`. PaddleSlap has no title screen, so its
  game-over screen (`PaddleSlapGameOverScene`) plays
  `PADDLESLAP_DEMO_PATH` after `GAME_OVER_IDLE_SECONDS` (10) of game time without a key or
  button press. `tests/replay/test_bundled_demos.py` replays every demo headless
  (`bundled_demo_paths` in `src/glitchygames/testing/replays.py`, `replay_recording_headless` in
  `src/glitchygames/replay/tools/children.py`) and
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
  `src/glitchygames/replay/driver.py`), and NEW holds the current logical names. A demo is recorded through the
  real engine loop with `--record-trace`, so frame 0 holds the scene start; PaddleSlap's rally is
  450 frames, before the golden script's pause. Re-record a demo only deliberately, as a golden
- `--random-seed INT`: the run's master seed (default: 64 random bits, kept in recordings). All
  randomness draws from named streams seeded from it: `random_stream('name')` (`random.Random`) or
  `numpy_stream('name')` (numpy `Generator`), looked up at draw time; `engine_random()` is
  `random_stream('engine')`, `reset_streams(seed=...)` reseeds (tests, replay). Never use
  `secrets`, `random.SystemRandom`, global `random.*` functions or an unseeded
  `np.random.default_rng()` in gameplay (`tests/test_unseeded_randomness_guard.py` scans for them)
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
  accumulator (real time x speed, consumed by recorded dt, within `INNER_FRAME_BUDGET_SECONDS` per
  tick, the owed time capped at `MAX_OWED_INNER_FRAMES` and a half frames, never below a frame plus
  a 60 Hz tick plus the tick paid for, in inner time; at every speed the work budget is the only
  per-tick limit (no frame count), so an uncapped recording whose frames cost what they did live may
  not keep up on a real machine, and "can't keep up" then means exactly that; up to 1x a tick runs
  at most one unless behind, owing that frame plus a whole tick, so a long live frame and its short
  catch-up frame are each presented, the replay then staying about a tick behind real time (a
  constant lag a pause resets), and a recording faster than 60 FPS still runs several a tick,
  presenting the last; above 1x the same limit follows a frame lasting at least a tick of inner time
  at that speed (shorter frames run several a tick, fast-forward) (rule 2 of `viewer.py`); the
  status bar shows the real speed when it cannot keep up),
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
- `--replay-trace NEW --compare-trace OLD [--compare-alpha PERCENT]` (Stage D Task D11;
  `src/glitchygames/replay/tools/compare.py`, whose docstring is the contract; rule 20 of
  `replay/driver.py`): the onion skin. NEW replays watched as always; `ReplaySources.onion_skin`
  (`OnionSkin`) draws OLD's items from the frame of the same number over the presented copy
  (`draw_overlay`, before the status bar; not while rebuilding) at PERCENT, NEW staying opaque
  (Tasks D13 and D16, rule 10: `GhostCompositor`, each frame on its own: OLD's background
  colors are the exact colors covering at least `BACKGROUND_COLOR_SHARE`, 5%, of OLD's frame;
  an OLD pixel that differs from NEW's in none of those colors is an item, blended with SDL's
  alpha arithmetic, `blend_over`; numpy on RGBX as `uint32`) (default 50;
  `argument_types.percent_from_zero_to_one_hundred`, kind `bounded-percent`). OLD is replayed by a headless
  child (OLD's game from its header, `traces.find_recorded_game`, else
  `children.running_game_command`; started inside the run by `OnionSkin.begin`, on the first
  presented frame or as a restart's rebuild begins, with `process.start_command`, its output in
  a temporary file logged when it fails) with the hidden `--replay-frame-stream PORT:TOKEN`
  (`FrameStreamAddress`; the token, from `secrets` per child, is sent first, and a connection
  without it is closed and logged; `tests/test_unseeded_randomness_guard.py` lists the module):
  `ReplaySources.frame_sink` (`FrameStream`) writes each frame from the display surface in
  `end_frame` to the parent's loopback socket (`FRAME_HEADER` `<III`: frame, width, height; then
  RGB rows), and a write nobody reads stops the child. The parent reads only when it draws
  (lockstep through pause and steps; one frame held as sent, decoded only when drawn); OLD
  ended: its last frame stays, labelled `OLD ended at frame N`; a child silent for
  `CHILD_READ_TIMEOUT_SECONDS` ends OLD the same way and is stopped at once (NEW goes on).
  Refused before anything runs: with `--headless`, `--audit`, `--rebaseline` (64), an OLD of
  another screen size or unreadable (65: not a readable recording, its seed or size missing or
  malformed included; a header without a size is warned about, not refused), missing (66); a frame stream without `--headless` or not `PORT:TOKEN` (64), or with
  nobody listening (69). A step back's restart keeps `--compare-trace`; its child gets the same
  `--replay-pause-at-frame N`, starts as the rebuild begins (the two rebuild at once) and
  streams from `first_streamed_frame` (N - 1). The teardown (`_shutdown`: `_end_the_comparison`,
  then `_shut_down_the_run` even if that failed) always stops and reaps the child. The three
  options are `REPLAY_LOCAL_OPTIONS`
- Stored paths (D15 item 4): every path the tools write into a file (a recording header's path
  options, `rebaselined_from`, a ledger row's recording) is relative to the project root
  (`find_project_root`, the settings' anchor; `--project-root` where a subcommand takes it), a
  path in another checkout of the same project (same `[project] name`) relative to that
  checkout's root, or the file name alone for any other path outside it (`replay/tools/settings.py` `stored_path`;
  `GameEngine` `stored_options`). `tests/test_our_stored_paths.py` fails on an absolute path in
  any tracked recording header or row-shaped JSON; the recording-renames table is refused when a
  path is absolute or a new path is itself an old one, and each new path must exist
- `<game> --compare-trace OLD [--compare-alpha PERCENT]` without `--replay-trace` (Task D12,
  decision 19; rule 9 of `replay/tools/compare.py`): live play against OLD. The same `OnionSkin`
  is the live host's overlay (`HostSources.overlay`, drawn over each presented frame before
  inner doors' overlay). Frames pair by game frame (Task D14, rule 11;
  `src/glitchygames/game_frames.py`: `GameFrameClock`, a context slot restarted by
  `SceneManager.begin_run`; `begin_frame` in `_run_frame_steps` with the scene whose logic the
  frame runs, a pause screen's being one whose `debug_subject` is another scene): live, replay
  and OLD's child's stream (game frames only) read it, so pausing freezes OLD and a recording
  of the run replayed with `--compare-trace OLD` pairs the same frames; a step back carries the
  game frame shown in `ViewerState.compare_first_game_frame` (`ReplayResult.shown_game_frames`). Live play runs under OLD's recorded seed unless `--random-seed N` is given
  (`_live_random_seed`, logged by `_log_the_runs_seed`). Refused before anything runs:
  `--headless` (64), OLD missing (66) or unreadable (65; its seed or size missing or malformed
  included), another size than the opened window (65,
  `_refuse_a_live_display_of_another_size_than_old`). `start_async` (a browser page) refuses
  `--compare-trace`, live or replayed, before anything starts (64,
  `_refuse_a_comparison_in_a_browser`: OLD's child is a process). `--record-trace NEW` may go with it;
  no step back; game flag only (no `play` subcommand)
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
- Golden replays: every game is a workspace member, so each golden lives in
  `<member>/tests/fixtures/replays/<name>.jsonl.gz` (the replay plugin still collects another
  project's `fixtures/replays/<console-script>/<name>.jsonl.gz`; no game's is there) (Mr. Muncher's:
  `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`), replayed through the member's
  console script (`recording_console_script`: its one, or for a member with several, the one
  starting the game the recording's header names). Brave Adventurer has one, its launcher,
  which starts the game each header names: `golden-classic.jsonl.gz` and
  `golden-papyrus.jsonl.gz` (scripts/record_scripted_session.py keys games by game, not console
  script: `GAME_CONSOLE_SCRIPTS`), and its bundled demos in
  `<package>/demos/`.
  They are recorded through the
  real engine loop by `scripts/record_scripted_session.py` (our games' policy over the engine's
  `scripted_sessions.record_scripted_session`: a supervisor posts each game's golden
  input script one frame ahead; never the golden harness, whose recordings have no FPS events).
  Each is a pytest item of its own: the plugin `src/glitchygames/testing/replays.py` (registered
  by the engine's `pytest11` entry point, named after its module, so no conftest loads it;
  `-p no:glitchygames.testing.replays` turns it off; it imports no pygame until it finds a
  recording, so a project that is no game gets no item and no output from it, unless it has a
  `fixtures/replays/<directory>/*.jsonl.gz`, whose non-console-script directory is a collection
  error; a wheel install has pytest rewrite asserts throughout the engine package, harmless, with
  `*-pytest-*.pyc` files in site-packages) collects every `.../fixtures/replays/<console-script>/*.jsonl.gz`,
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
  engine's `source_revision` (see Source revision) and the game's `game_source_revision`, the `machine_state`
  (`src/glitchygames/machine_state.py`: CPU, memory, mains or battery, macOS thermal report, CI),
  a `summary` (`RunSummary`: processing p50/p95/p99/max, worst frame and scene, frames over the
  target FPS budget, the live run's frame times; filled in when the next run stacks, since a
  header is written first; `recording_run_summaries` computes the newest's; since 2026-10-28
  also the mean and the "5% low"/"5% high" slice means of the processing times and of a live
  run's frame times, stored in seconds, never FPS: `slice_frame_count` is the one definition,
  `ceil(5%)` of the frames and at least one, pause frames included, a live run's first frame
  left out of its frame-time mean and slices (its `dt` runs from the clock's start); older
  summaries read them as None and are completed from the frames when the next run stacks),
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
  missing; it keeps only git staging and its refusals, and runs `glitchygames unmeasured` then
  `glitchygames measure --code-tree TREE --rows-directory DIR` in its own process) measures every
  golden replay and bundled demo when this machine has no rows for the
  staged code tree (`src/glitchygames/code_tree.py`: a git tree of only the root
  `pyproject.toml`'s `[tool.glitchygames]` `measured-paths`, `src/` (the engine, games, demos,
  apps; less its `unmeasured-paths`, the members' `tests/` but for their
  `tests/fixtures/replays/`), recordings, `uv.lock`, `pyproject.toml`), so
  code that arrived by
  a merge or rebase is measured by the next commit, and stages the rows, each naming that code
  tree (`LedgerRow.code_tree`), into the same commit, plus the `history-...` row files it wrote
  (a recording's earlier header runs, written only when measured on a commit on `origin/main`
  without uncommitted changes, and never again under a moved recording's new path:
  `measure.rows_to_write`, `LedgerRow.held_key`; none without an `origin/main`) (refused for a partial `git commit <path>`
  or untracked files under the measured paths; `SKIP=replay-metrics` skips it); every docs build reads them and keeps the rows whose tree
  landed (`landed_code_trees`: the tree of each commit that added rows, i.e. main's squash
  merge; `landed_rows`), labelled with that commit, then merges gh-pages' ledger and local
  pending rows (`nox -s replay-metrics`: `glitchygames measure`) and graphs them
  (the engine's `performance-pages`, through `scripts/generate_performance_graphs.py`,
  docs/quality/performance.md); CircleCI's
  `deploy-docs` publishes after each merge (`nox -s docs-deploy` refuses unless HEAD is on
  origin/main). A branch updated from main is measured by its next commit, or by hand: `uv run
  python -m scripts.measure_staged_replays`, then commit what it stages Each measured row carries a `FrameProfile` (about 100 buckets of the run's slowest frame
  per stretch, integer microseconds, scenes run-length encoded; ~0.4-0.6 KB) for the page's frame
  x commit heatmap (time only: the report shows whether the work changed). Rows measured on
  uncommitted changes (`LedgerRow.from_uncommitted_changes`, e.g. `--allow-dirty`) are left out
  of a published build (the hook's `on_startup` sees `gh-deploy`; no startup event counts as
  published) and shown, labelled, in a local `mkdocs build`/`serve`; they stay in the pending
  file after a deploy (`clear-published` removes only rows gh-pages holds). `uv run glitchygames
  report PATH` prints a recording's runs, speed changes and behaviour-change map. FPS is for
  display only, one division from the stored seconds (`recording_metrics.fps_from_seconds`,
  None for missing or zero seconds; `describe_fps`: `avg 222 fps (5% low 168, 5% high 251)`):
  `measure`'s line and `report`'s run summaries show headroom FPS (1 / processing time) and a
  live run's achieved FPS (1 / frame time) beside the milliseconds; the performance pages add
  FPS by commit (`fps_charts`: live runs' achieved FPS solid, replays' headroom FPS dashed,
  each point the average with its 5% low and high as an error bar, log axis, a dotted
  target-FPS line from `budget_seconds`) and a machines view (`machines_chart`: each machine's
  latest replay row as a bar of headroom FPS, replays only, CI machines marked `(CI)`). Rows
  from before the slice means have no FPS
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
  `plans/future-work.md`. User docs: `docs/architecture/gameplay_replay.md` (the command
  reference) and `docs/architecture/playback/` (how it fits together, with diagrams: the overview,
  how a frame runs, speeds and timing, the recording file with its stored and derived fields, and
  how playback is tested)

**Engine Context** (`src/glitchygames/engine_context.py`; design `plans/2026-10-25-engine-context.md`)
- The state one running game owns, so several games can run in one process (the Arcade's demo
  tiles). Ordinary games never create one and run in the default context
  (`default_context()`), exactly as before. Per context today: the slots below, and the
  engine's and scene manager's own attributes (`engine.options`, `game`, `running_game`,
  `event_handlers`, the event bookkeeping; `manager.engine_options`). Still one per process:
  the audit's shared rows (S1-S20: the display, mixer, SDL's queue, joystick subsystem, process
  services, ...), which later sub-plans keep inner contexts off. A game runs in another context
  as an inner game (below; the sound-file loader also switches to a scratch context)
- Per-context state is a `ContextSlot(name=..., factory=...)` declared once at module level in
  the module that owns it; code reads `current_context().value(slot=...)` when it needs it,
  never at import (`tests/test_engine_context.py` scans the engine and every member).
  `ContextSlot` is internal to the engine: engine modules declare slots, games keep state on
  their scenes (the tests' `COUNTER_SLOT` only tests the class)
- `with context.active():` switches (a `contextvars.ContextVar`: per thread and asyncio task;
  nests; restores on exceptions). Slots today: the default snap mode, the default background,
  the polled input, the random streams, the game-frame clock, the doors with the frame clock
  and observers, the `SceneManager` singleton, the wave registry, the audio engine, the current
  engine (`current_engine()`), the internal-post tracker, the performance manager
  (`AdaptiveClamping()`), the shared event managers and `FontManager` (`ResourceManager`), the
  font options, the singleton sprites, the debug-events log set, the sprite counters
  (`sprite_counters()`), the render target with its hosted start and the private event queue
  (the table in
  `docs/architecture/engine_context.md` lists each one's functions); each has an isolation check in `tests/test_engine_context.py`
  (`ISOLATION_CHECKS`), and a slot without one fails the suite
- The old class-level names are read-only views (`src/glitchygames/read_only_views.py`):
  `GameEngine.OPTIONS`, `game`, `EVENT_HANDLERS`, `LAST_EVENT_MISS`, `MISSING_EVENTS`,
  `UNIMPLEMENTED_EVENTS`, `SceneManager.OPTIONS`, `FontManager.OPTIONS`, `Sprite.SPRITE_COUNTERS`,
  `SPRITE_BREAKPOINTS`, `SPRITE_COUNT` and the module view
  `glitchygames.performance.performance_manager`. Each is read-only, the current game's, and
  `None` (or its empty default) outside a game; writing one raises `ReadOnlyViewError` naming
  where to write instead. Engine code never reads a view (it costs about two slot reads): it
  reads the instance (`self.options`), or the owner function (`sprite_counters()`,
  `AdaptiveClamping()`); `current_engine()` is the engine made last in the current context. The
  views table and the measured costs are in `docs/architecture/engine_context.md`
- Guards: `tests/test_read_only_views.py` (every view checked per context, the engine never
  reads one, the page's views table and costs), `tests/test_process_state_guard.py` (the audit
  as an allowlist scan of the engine and every member: new module- or class-level mutable state
  fails unless it is a slot or listed with its audit row), `tests/test_shared_font_cache_guard.py`
  (nothing restyles a cached font in place, R9) and `tests/test_suite_collection.py` (no living
  document writes a view)
- The harness fails a test that leaves another context current
  (`every_test_ends_in_the_default_engine_context`): a switch entered by hand and still held. A
  switch abandoned unexited unwinds itself when collected and is not reported. A new autouse fixture that resets engine
  state must join a group (`per_context_state_resets` or `engine_service_resets` in
  `tests/harness.py`) that the leak check requests, or be listed in
  `PROCESS_STATE_AUTOUSE_FIXTURES` (`tests/test_engine_context.py`) with its reason; a guard
  test enforces it for the autouse fixtures defined in `tests/harness.py`
- Inner contexts (Arcade sub-plan 3, `plans/2026-11-12-arcade-3-inner-game.md`; the rules in
  `docs/architecture/engine_context.md`, "Inner contexts"): a context with a render target
  (`src/glitchygames/render_target.py`, `is_inner_context()`) is inner. Its engine draws on the
  target (`display_surface()`, never `pygame.display.get_surface()` in engine code), never
  opens, resizes, captions, presents or icons the window, never changes SDL's drivers (S1, S2),
  and makes each unpresented frame opaque (BUGS.md #142); no SCREEN shake or overlay is drawn
  in it. Its posts go to its own queue (`recording.private_event_queue()`), which its replay
  doors drain, never SDL's (S5, S6), so a recorded QUIT ends only that game. `start()` in it is
  a hosted start: the game is built to its first frame and the engine handed over
  (`take_started_engine()`), no signal handlers, loop, crash boundary, `_begin_start` or
  `_begin_run`; a `request_hosted_start()` lasts the context's life
- `InnerGame` (`src/glitchygames/inner_game.py`, its docstring the rules) is the host's handle:
  `InnerGame.replay(command=..., path=..., name=..., size=..., arguments=())` calls a game's
  installed command, unchanged, in a fresh context (render target, private queue, `sys.argv`
  swapped for the call), `step()` runs one unpaced frame, `finish()` settles `outcome`
  (`InnerGameOutcome`: `RUNNING`/`ENDED`/`FAILED`, frames, report, error). Only headless
  replays: live play, tool flags, `--rebaseline`, `--audit`, `--compare-trace`, `--profile`,
  `--list-input-devices`, `--help`, `--version` raise `InnerGameRefusedError` before anything is
  built. An `Exception` or `SystemExit` fails only that game; it writes nothing to stdout (the
  report is the outcome's, logged at INFO). SDL's blocked event types are never changed from an
  inner context (`events.set_event_types_allowed`, the one way the engine blocks or allows).
  Still shared (`plans/future-work.md`): the mixer (sub-plan 4), SDL's key repeat, text input
  start/stop, Bitmappy's mouse visibility, `pygame.freetype`'s default resolution (an inner
  `FontManager`'s `--font-dpi`), `SDL_MOUSE_FOCUS_CLICKTHROUGH` when unset and
  `pygame.register_quit`. The proof:
  `tests/test_every_recording_replays_inside_an_inner_game.py` (every golden and bundled demo,
  interleaved beside another inside a window of another size, matches its solo replay's digests
  and pixels; Bitmappy's demo and the text-input demo's key repeat are strict xfails); ten
  stand-in tiles per outer frame: `test_ten_inner_games_per_outer_frame`

**Source revision** (`src/glitchygames/build_info.py`, the contract): `source_revision()` names the
engine's commit and how it is known, first answer wins: a git checkout (git: HEAD, its date,
uncommitted changes to tracked files; only when git tracks the package's files, so a copy
installed in another repository's `.venv` does not count), a git archive
(`src/glitchygames/_git_archival.txt`, `export-subst` in `.gitattributes`: `git archive` and GitHub's
source zips write the commit in), a build stamp (`_build_info.json`, written by
`scripts/write_build_stamp.py` around `nox -s build-wheel`/`build-binary`/`test`, gitignored, packaged
through hatch `artifacts`), else unknown. Every recorded run holds it
(`MeasurementRun.source_revision`; `engine_source_revision()` looks it up once per process), and
the game's beside it (`MeasurementRun.game_source_revision`: the same lookup in the game's package
directory, `glitchygames.replay.tools.identity.game_source_revision`; None when that directory is
not found, or for a run from before the field). A ledger row's commit and uncommitted-changes flag
are the game's (`MeasurementRun.game_or_engine_revision`), the engine's only when there is no game
revision: a game outside this repository names its own commit. Here both are one checkout.

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

**Sound Synthesis** (`src/glitchygames/audio/`; user docs `docs/architecture/sound.md`, specs
`docs/specs/2026-11-02-sound-engine-feature-spec.md` and `...-implementation-spec.md`; M1 built,
M2 next)
- One call: `scene_manager.audio` is the context's `AudioEngine` (`audio/engine.py`, slot
  `AUDIO_ENGINE_SLOT`). `audio.sound(source, *, pitch, notes, chord, length, transpose)` returns
  a compiled `Sound`: the first request for an identity compiles, later ones hit the cache, and
  getting never plays. `Sound.play(volume=, pan=, bus=, priority=, loop=, persist=)` returns a
  `SoundHandle` (`stop`, `cancel`, `release`, `set_volume`, `set_pan`, `is_playing`: False once
  ended, never touching a later voice); `audio.play(...)` and `audio.beep(...)` are shorthands.
  Request sounds in `setup()`: a gameplay compile is counted, logged and shown in red
- Sources: a short name, looked up in the scene's `SOUND_DIRECTORY` (`'sounds'`, relative to the
  scene's package directory; a TOML `[sounds.*]` name or a `.wav`/`.ogg` stem; a name in two
  files raises naming both), a path (`'sounds/pickups.toml#coin'`) or an `Instrument` (waves,
  noise, up to four sources, envelope, filter, drive). Pitches: note names, `Hz`, `Midi`,
  `Scale(root, kind).step(n)` (`audio/pitch.py`); named waves, mixes, blends, points and
  harmonics (`audio/waves.py`, a per-context registry). Sound files are TOML version 1
  (`audio/assets.py`, `audio/spec.py`); version 0 recipe files load and sound as before
- Cache (`--sound-cache`, replay-local): `ram` (default; least recently played idle sounds go
  above `--sound-cache-memory`, 256 MB) or `none` (every play compiles in its frame; the CRT
  power-on's sounds, the engine's own, are compiled once per process and exempt); `disk`
  arrives in M3 and is refused (`OPTIONS_REFUSED`) until then. A sound's `length`, `peak` and
  `sample_rate` never depend on the cache, and eviction keeps them. Under `none` getting a sound
  renders or decodes nothing (5 plays, 5 compiles): a synthesized sound's `length` is derived
  exactly as the compile sizes it (`render.rendered_frame_count`, `SoundRecipe.frame_count`);
  every `peak`, and a recorded file's `length` and rate, come from one counted compile on first
  read (a play's compile counts as that read), then are kept
- Channels: partitioned once at startup: the live pool (`--live-voice-pool`, 4), the library
  (`--sound-channels`, 32), then pygame's 8 for legacy `Sound.play()` callers. The voice table
  (`audio/voices.py`) steals by priority (`Channel.fadeout(10)`; the stealer waits a frame for
  the stolen channel, a delayed play), drops and counts; `is_playing` and voice ends follow
  played time (the served `dt`), never the device, so replays see the same answers.
  `FrameSilencer`'s stops (rebuild, fast-forward) only quiet the channels
  (`AudioEngine.silenced`): the voices, their ends and steals go on by frame time. Owners are
  compared by identity. Buses
  (`audio/buses.py`): `master` over `music`, `effects`, `ui`, `ambience` and `dialogue` (`ui`
  and `music` reserve two channels each). A scene's voices fade over 50 ms when it is switched
  away from (unless `persist=True`) and pause behind a pause screen
- Measured (`tests/audio/test_channel_fades.py`, SDL's disk driver): SDL_mixer changes a
  channel's level only between 512-frame chunks (11.6 ms), so `Channel.fadeout` of 10 or 20 ms
  is a plateau or two and a halt, a per-frame volume or bus fade steps once per chunk, and
  `play` straight after `fadeout` cuts the fade (why steals wait a frame). Short fades can click:
  the owner's listening check and decision (impl spec risks R4 and R5; strict xfails hold the
  unmet criterion)
- Accounting (`audio/accounting.py`): each compile, decode and cache read is timed; a frame's
  work reaches the doors, and so recordings, as `audio_seconds` and `audio_work` (at most 32
  entries); `audio.diagnostics()` totals compiles (setup and gameplay), steals, delayed and
  dropped plays and the cache's hits, misses and bytes; the debug overlay's Audio panel shows
  them per frame
- Offline: `glitchygames.audio.render_to_file(sound, path, ...)` (`audio/offline.py`) writes a
  sound (plus `OfflineEvent`s, loops, stems) to a WAV file with no audio device; alone it is the
  compiled int16 buffer bit for bit (never cut); with `events`, the tail stops 100 ms into
  -90 dBFS after the last nominal end (an instrument sound's last release), or at `tail_seconds`.
  The `glitchygames sound-render` and `sound-migrate` (v0 recipes to v1) tools use it
- The Sound Board (`uv run sound-board-demo`) plays every built-in wave and noise by note, hertz
  and scale step, with the Audio panel open
- Instrument catalog (`audio/instruments/`): `instruments.get('violin')` is an ordinary
  `Instrument` (built once per process), `instruments.entry(name)` its title, family and range
  (`lowest`/`highest`, sounding; None for unpitched drums, whose fixed tones ignore the pitch
  given). 703 entries in 23 `Family`s (every size of each family, voices soprano to basso
  profundo on five vowels; `Tag.MECHANICAL` marks mechanical ones and `Tag.CHIP` sound-chip
  voices, `names(tag=...)` lists them;
  `ALIASES` (read-only, as `CATALOG` is) maps 120 other names to catalog names, resolved by
  `get`/`entry`; a sound-alike is its own entry sharing a parent's build via `sounds_like`, with
  optional sourced `sound_changes`; 196 in all, and a pitched one, as the plucked strings' and bowed strings' are,
  gives its own sourced range), each built by a shape in `timbres.py` (`blown`, `plucked`, `struck`, `rubbed`,
  `drum`, `with_drones`) from overtone series (`falling_series`, `plucked_series`,
  `formant_series`); `tests/audio/test_instrument_catalog.py` renders every entry across its
  range and checks each harmonic one's pitch. `scripts/make_instrument_demos.py` writes WAVs
- The older toolkit, kept until M2 moves the games over and removes `SoundBank`, `load_sound`
  and `live_audio`: oscillators (PolyBLEP square/saw), pitch curves via easing, envelopes, FIR
  filters, mixing and `to_sound()` (`synth.py`, still the renderer's building blocks);
  `Tone`/`SoundRecipe` (TOML-loadable) played through `SoundBank` (`recipes.py`); live voices,
  `scene_manager.live_audio.create_voice(owner=...)`, streamed in 100 ms chunks on the live pool
  (`live.py`)
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
line), and an Audio panel after Performance (cache mode, mixer, voices, an audio-time graph stacked by
kind of work, channel strip, bus meters, compile log; under All only its header; `--sound-diagnostics`
opens on it; built from `AudioEngine.snapshot()` only while the overlay is visible and the engine
already exists), then an AI panel (the link, models and requests, from the AI console). Drawn in `SceneManager._present_frame`, never in screenshots, with the bundled Bitstream
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
driver (`--headless`, every test) and before a replay, audit, rebaseline or recording. Its sound
(`src/glitchygames/crt_power_on_sound.py`, feature spec 12.1) plays with the picture, unless
`--crt-power-on-sound off`: a power click and a 60 Hz degauss thump at the switch, a flyback whine
(`FLYBACK_WHINE_HZ`, owner-tunable) from the dot, static as the picture opens, then the bars' 1 kHz
tone (or channel 3's hiss), all `Instrument`s through `audio.sound(...)`, cued by the frames'
progress through `play_power_on(sound_cues=...)` (`PowerOnSoundCues`: `crt_power_on.py` stays a
leaf with no audio import). They are requested through `audio.engine_sound(...)` and compile once
per process (the owner, 2026-11-02): the engine's process-wide `ENGINE_SOUND_CACHE`
(`audio/library.py`) keeps their read-only samples by identity key (mixer rate and tuning
included), so every later power-on and engine context (the Arcade) compiles nothing; each context
gets its own `Sound` over the shared samples. It is exempt from the memory limit and from
`--sound-cache none`; the first compile is counted where it happens, reuses are cache hits; tests
start empty (`tests/harness.py` `empty_engine_sound_cache`). Its voices are the audio engine's `SYSTEM_OWNER`'s; the engine is made
before the power-on with the game engine's options and partition (`SceneManager.audio_for`), the
one the game's `scene_manager.audio` returns. A skip fades every voice over 20 ms; the tail loops
into the game and fades over 500 ms from frame 0's first audio update
(`AudioEngine.fade_out_at_next_update`)

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

`active_sources().pump_events()` → `GameEngine.process_events()` → `SceneManager.on_*_event()` →
`Scene.on_*_event()` → `Sprite.on_*_event()`. Handlers get immutable `HashableEvent`s
(`events/base.py`; change one with `event.with_fields(...)`). Unhandled events raise under
`--no-unhandled-events` (on in every test). Docs: docs/architecture/event_system.md.

### Sprites, animation and collision

- **Every game object is a sprite** in the scene's groups, never drawn straight to the screen
  (the owner, 2026-11-07): sprites get stable ids, replay comparison, debug hitboxes and the AI's
  introspection. Drawing Fire predates this (conversion is in plans/future-work.md).
- Hierarchy (`sprites/`): `RootSprite` → `Sprite` → `BitmappySprite`, `AnimatedSprite`. Load
  sprites with `SpriteFactory.load_sprite(filename=...)`, not `BitmappySprite` directly.
- Sprite files are TOML only (character-to-colour map, optional per-colour alpha, magenta
  255,0,255 as the transparency key, `[[animation]]` sections); see ANIMATION_README.md.
- Hitboxes (`collision/`) default to the image's visible pixels; TOML hitboxes win. A TOML
  `AnimatedSprite`'s frames keep magenta opaque, so give it a `[sprite.hitbox]`. Use
  `common_hitbox_x_range()` for standing support and `frame_anchor` for frames of different shapes.
- Engine-level patterns must work for other genres (top-down RPG, shooter, puzzle, fighting), not
  just today's games: flag any that lock one out.

### Bitmappy (`src/apps/bitmappy/`)

The pixel-art editor, an app member: canvas editing with undo/redo, animation film strip, up to
four controllers (CONTROLLER_CONTROLS_README.md), onion skinning, flood fill (Ctrl+click), TOML
and PNG drag-and-drop, AI generation through the local AI service (`AI_FEATURES_ENABLED`; off in
WebAssembly). The Load and Save dialogs take the file name as typed (no `example:` prefix), so a
library sprite is opened by its path. Its sprite library is package data in `src/apps/bitmappy/src/bitmappy/resources/
sprites/`. Docs: docs/architecture/bitmappy.md.

### Browser

`nox -s browser -- <game>` builds a browser bundle. The page installs its own clipboard
(`browser/browser_clipboard.py`) and user files (`src/glitchygames/user_files.py`); on-screen
touch buttons (`browser/touch_controls.js`) send ordinary key events, checked by
`tests/test_browser_touch_controls.py`. The shared pause and game-over screens resume with Space
and quit with Esc, so a game's own pause must not be on an Esc button (Mr. Muncher's is P).

## Testing Guidelines

- Real pygame, real display, real files (`tmp_path`); no shared mocks. Patch only what can't run
  in a test (hardware, network, third-party tools, the clock, injected failures) with targeted
  `mocker` calls. Assert on pixels, not draw calls, without assuming the display's pixel format.
- Wall-clock timings never belong in the normal suite; measure time in benchmarks
  (`pytest --benchmark-only`).
- Tests import the installed packages and never edit `sys.path` (`uv sync` installs them
  editable; `nox -s test` installs a non-editable copy, so it tests what a wheel would ship). Member tests live in
  `src/<layer>/<member>/tests/`, are named `test_<distribution with - as _>*.py`, and import
  helpers by qualified path from the root (`src.apps.bitmappy.tests.film_strip_support`).
- An engine test that needs a game uses a stand-in (`tests/stand_in_games.py`) or the workspace
  expectations (`tests/workspace_expectations.py`, edited when a game, golden, demo or console
  script is added). A test of the repository itself goes in its own file, never beside engine
  tests.
- `tests/harness.py` defaults SDL to the dummy drivers; macOS joystick drivers are off, so tests
  see only stand-in devices (`tests/input/stand_in_devices.py`).
- Driver comparison: outside CI, `pytest` also runs on the native driver and fails on any
  differing frame (PNGs in `test-results/driver-comparison/pytest/`). A test whose frames
  legitimately vary carries `@pytest.mark.frames_vary(reason=...)`.
  Docs: docs/quality/driver_comparison.md.
- The display rule (`tests/display_canvas.py`): each test starts on the canvas pattern, and a test
  whose last frame is entirely black fails as a rendering bug (opt-out
  `@pytest.mark.black_frame_expected(reason=...)`). Assert untouched pixels with
  `canvas_color_at(x=..., y=...)`, never as black.
- Sprite-file checks: call `glitchygames.testing.sprite_files`' `check_*` functions; don't copy them.
- Coverage is 100% with no configured exclusions; a deliberate defensive line carries
  `# pragma: no cover` with its reason.
- Run the linters after modifying files.
- A new autouse fixture that resets engine state must join a group in `tests/harness.py` (see
  `tests/test_engine_context.py`).
- Check for real bugs before assuming a test failure is a test issue.

## Code Style

Python 3.14, ruff (100-character lines, import order), Google-style docstrings, basedpyright and
ty. Data classes are pydantic models. Active bugs: BUGS.md.

## Docs

The site is mkdocs 1.x (`mkdocs<2.0`) with the Material theme, configured in `zensical.yml` (`mkdocs.yml` links
to it; code reads `zensical.yml`). Engine API pages are hand-written in `docs/glitchygames/`;
member pages are generated (`scripts/gen_ref_pages.py`) and must be in the nav. Write pages in
Material's conventions (plans/2026-11-09-docs-material-formatting.md); the abbreviations'
glossary is `docs/includes/abbreviations.md`. Roadmaps:
plans/future-work.md, plans/future-features.md.
