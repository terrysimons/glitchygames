# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GlitchyGames is a Python 3.14 game engine built on Pygame with an event-driven architecture. The project includes a full-featured pixel art editor called Bitmappy and supports animation, UI widgets, and physics-based game objects.

## Development Setup

```bash
# Install dependencies (uv manages the virtual environment automatically)
uv sync

# Install with dev extras (for testing/linting)
uv sync --extra dev

# Install with all extras
uv sync --all-extras
```

## Common Commands

### Testing
```bash
# Run all tests with coverage (80% minimum required)
pytest

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
ruff format glitchygames tests scripts noxfile.py

# Check and fix import ordering
ruff check --select I --fix glitchygames tests scripts noxfile.py

# Run full ruff linting
ruff check glitchygames tests scripts noxfile.py

# Type checking with pyright
pyright
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

# --- Security ---
nox -s security-scan       # Run ALL security scans (bandit + safety)
nox -s bandit-scan         # Run bandit only
nox -s safety-scan         # Run safety only

# --- Build / Package ---
nox -s build               # Build binary (PyInstaller) + wheel
nox -s build-binary        # Build standalone Bitmappy binary only
nox -s build-wheel         # Build wheel (.whl) only
```

### Running Bitmappy (Pixel Art Editor)
```bash
# Run with default settings
uv run bitmappy

# Legacy pygame timing backend (the fast backend is the default)
uv run bitmappy --timer-backend=pygame

# Custom target FPS
uv run bitmappy --target-fps=120   # default is 60.01; --target-fps 0 for uncapped

# Enable timer jitter logging
uv run bitmappy --timer-backend=fast --log-timer-jitter

# Windows: Enable 1ms timer resolution
uv run bitmappy --timer-backend=fast --windows-timer-1ms
```

## Architecture Overview

### Core Engine Components

**GameEngine** (`glitchygames/engine/__init__.py`)
- Singleton orchestrator extending `EventManager`
- Handles pygame initialization, display management, event routing
- Bootstraps command-line arguments for all games
- Pre-computes `EVENT_HANDLERS` dict for O(1) event dispatch

**SceneManager** (`glitchygames/scenes/__init__.py`)
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

**Exit Codes** (`glitchygames/exit_codes.py`; `ExitCode` IntEnum, re-exported by
`glitchygames.engine`; never write the number in code or tests)
- 0 `SUCCESS` (replay matched, audit deterministic), 1 `REPLAY_DIVERGED`, 2
  `ARGUMENT_PARSER_ERROR` (argparse's own; the engine never exits with it), 3
  `AUDIT_NONDETERMINISTIC`, 4 `GENERATION_REJECTED` / 5 `EXTRACTION_REJECTED` (API client: the
  server refused a generation / a frame extraction; a 503 is `SERVICE_UNAVAILABLE`),
  6 `AUDIO_DROPOUT_RISK` (`scripts/audio_glitch_probe.py` found a risk of audio dropouts),
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

**Frame Pacing** (`glitchygames/timing.py`)
- Two timer backends:
  - `FastTimer` (default): High-resolution `time.perf_counter_ns()` with sleep+spin hybrid
  - `PygameTimer`: Legacy pygame-based timing (whole milliseconds); select with `--timer-backend=pygame`
- Paced frame time (`dt`, FPS tracking) is always measured with `time.perf_counter()`, and
  `target_fps` may be fractional (the period is `round(1e9 / target_fps)` ns)
- Default target 60.01 FPS (`DEFAULT_TARGET_FPS` in `glitchygames/timing.py`, re-exported by
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

**World Space** (`glitchygames/world.py`, `glitchygames/camera.py`)
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
- The pose rule: draw a sprite's pose (image, so its hitbox) in `dt_tick`, after its state is
  decided and before collision; `update()` runs in the render phase, after collision, and may do
  only visual work (fades). Drawing the pose in `update()` makes collision use last frame's pose
  (the old one-frame wall lag). Likewise collision resolution belongs in `dt_tick` (PaddleSlap),
  so its result is positioned before the frame renders
- Transition captures hide a world-space player with `hidden` and restore it afterwards; the
  arriving capture snaps the camera to `camera_target()` on its followed axes only
  (`camera.snap_followed_axes_to`), or to the player on both axes when there is no target
- Golden traces (`scripts/record_golden_traces.py`, `tests/world/test_golden_traces.py`) replay
  every example game and compare each sprite's rect and visibility, frame by frame, with
  baselines recorded before the world-space change. Every difference must be explained by
  exactly one `ExpectedDifference` entry whose rule proves it exactly (an entry that explains
  nothing fails too); never re-record the baselines to make a change pass

**Clocks** (`glitchygames/clock.py`, a leaf module): every time read in `glitchygames/` comes from
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
  replayed, so its readings must never change what is drawn, played or recorded
- Only `ALLOWED_BYPASSES` in `tests/test_engine_doors.py` may read the raw clock: pacing
  (`timing.py`, `SceneManager.start`/`_finish_frame`), `performance/`, `debug/`,
  `audio/diagnostics.py`, the recording's start stamp (`engine/game_engine.py`), `api/client.py`
  (request signing) and the live doors' wall clock (`live_sources.py`). `clock.measured_seconds`
  is also allowed, by function (`ALLOWED_FUNCTION_BYPASSES`)

**Gameplay Recording and Replay** (`glitchygames/sources.py`, `glitchygames/live_sources.py`,
`glitchygames/recording.py`, `glitchygames/replay/`, `glitchygames/randomness.py`; design
`plans/2026-10-19-gameplay-replay.md`, plans `plans/2026-10-19-gameplay-replay-*.md`)
- Doors: the engine takes events, frame time, polled input, devices, saves, the clocks and the
  random seed only through the active `EngineSources`. `glitchygames/sources.py` is the leaf
  registry: `active_sources()`, `install_sources(sources=...)` (only before the first frame,
  else `SourcesAlreadyRunningError`), `reset_sources()` (called by `GameEngine.__init__`), and the
  frame clock. It has no engine imports, which avoids an engine/scenes import cycle. Providers:
  `LiveSources` (`glitchygames/live_sources.py`: pygame's queue, the measured dt, pygame polling,
  real devices, `DiskSaveManager`, the real wall clock), `RecordingSources`
  (`glitchygames/recording.py`: wraps the live doors under `--record-trace` and records what
  passes through) and `ReplaySources` (`glitchygames/replay/driver.py`: serves the recording)
- Guard: `tests/test_engine_doors.py` AST-scans the package. Raw clock reads, pygame key/mouse
  polling, `pygame.event.get`/`post` and joystick/controller enumeration or construction outside
  the doors fail. The only exceptions are `ALLOWED_BYPASSES` (by file) and
  `ALLOWED_FUNCTION_BYPASSES`, each with its reason. No directory is exempt, Bitmappy included
- Polled input: `glitchygames.input.state.current_input()` (or `GameEngine.input`) returns the
  frame's immutable `InputSnapshot`. It is captured once per frame, right after the frame's first
  pump, so `dt_tick` (which runs before the pump) sees the previous frame's. It offers
  `key_pressed(key)`, `pressed_keys` (like `pygame.key.get_pressed()`; key lookup needs
  `pygame.init()`), `modifiers`, `mouse_position`, `mouse_buttons` and `mouse_focused`. Devices
  are keyed by instance id on two layers: the joystick layer (`axis`/`button`/`hat(device_id=...,
  ...)`, float axes) and the controller layer (`controller_axis`/`controller_button(device_id=...,
  ...)` by `CONTROLLER_AXIS_*`/`CONTROLLER_BUTTON_*` id, on pygame's int scale). Never poll pygame
  or a device directly
- Devices: `active_sources().devices()` (`glitchygames/input/devices.py`) is the only way to
  enumerate (`joystick_count`, `controller_count`, `is_controller`, `name_for_index`) and open
  (`open_joystick`, `open_controller`, `joystick_for_instance`) devices. Live answers, failures
  included, and each opened device's descriptor are recorded. A replay answers with the recorded
  answers (a recorded failure is raised again as `pygame.error`) and with `ReplayJoystick` /
  `ReplayController` stand-ins: their positions come from the snapshot, rumble is dropped, and the
  replay never sees real hardware
- Saves: `glitchygames.state.open_saves(app_name=...)` returns a `SaveManager` (the base class
  holds every rule of the save format): `DiskSaveManager` live, `MemorySaveManager`
  (`glitchygames/state/sandbox.py`) in a replay, seeded from the recorded snapshot
  (`save_namespace_snapshot`). Replay writes stay in memory; real saves are never touched
- Supervisor hook (`glitchygames/supervision.py`): `SceneManager.add_supervisor(supervisor=...)`
  calls `on_frame(frame_number=..., scene=...)` once per frame, after logic and events and before
  frame services, camera aim and positioning. `SceneManager.record_control_event(kind=...,
  data=...)` records a supervisor action in the frame (the frame's `control_events`) and runs the
  handlers from `add_control_event_handler(kind=..., handler=...)`. A replay re-applies recorded
  control events at the same frame's supervisor slot. `GameEngine.__init__` calls
  `reset_supervision()`. A future cheat device plugs in here
- `--record-trace PATH`: record the session as a gzip JSON Lines trace (`glitchygames/tracing.py`
  format version 3; versions 2 and 3 are readable), off by default. Each frame line holds `dt`,
  the raw `event_batches` read at `GameEngine._pump_events` (the only reader of SDL's queue; each
  event tagged `external`/`internal`) and the sprites. Format 3 adds frame fields, written only
  when non-empty: `input_changes` (snapshot diffs), `control_events`, `devices_opened`,
  `saves_opened` and `device_enumeration`. The header holds versions, options, `recorded_at`, the
  random seed and, since format 3, the `saves`, `devices` and `device_enumeration` taken in before
  recording started. Engine code posts events with `glitchygames.recording.post_event` so
  recordings can mark them internal. The format is described in `glitchygames/recording.py`
- `--random-seed INT`: the run's master seed (default: 64 random bits, kept in recordings). All
  randomness draws from named streams seeded from it: `random_stream('name')` (`random.Random`) or
  `numpy_stream('name')` (numpy `Generator`), looked up at draw time; `engine_random()` is
  `random_stream('engine')`, `reset_streams(seed=...)` reseeds (tests, replay). Never use
  `secrets`, `random.SystemRandom`, global `random.*` functions or an unseeded
  `np.random.default_rng()` in gameplay (`tests/test_randomness.py` scans for them)
- `--replay-trace PATH` (`glitchygames/replay/driver.py`; its module docstring lists the rules):
  replay a recording exactly through the real engine. `ReplaySources` serve its events, dt,
  polled input, devices, in-memory saves, clocks and seed, and every frame's sprites are compared
  with the recorded frame. Refusals log the reason and exit with an `ExitCode` (see Exit Codes):
  `UNUSABLE_INPUT` (65) for a recording of another game, an unreadable file or an unsupported
  format version, `MISSING_INPUT` (66) for a missing file, and `OPTIONS_REFUSED` (64) for
  `--record-trace` given too (refused until Part 2's `--rebaseline` wires recording over a
  replay). A different engine version only warns. Recorded options apply except
  `REPLAY_LOCAL_OPTIONS`. The first divergence (kinds `scene`, `sprite`, `event`, `length`)
  stops the replay, as do the last recorded frame and closing the window. The report
  (`ReplayResult.report()`: `Replay diverged at frame 6120: sprite Ball#2 rect expected [412,
  300, 16, 16], got [412, 301, 16, 16]`, then that sprite's last 20 frames, expected | got; or
  `Replay matched N frames (end of recording)`) is logged, and every replay that ends normally
  exits with `ReplayResult.exit_code(policy=...)` (the policy and the other replay settings are
  the frozen pydantic `ReplayOptions`): `SUCCESS` (0) matched or window closed,
  `REPLAY_DIVERGED` (1), `UNUSABLE_INPUT` (65) for a truncated recording that matched to its
  cut-off. Recorded window references map to None (live events of the display window carry None).
  Version-2 recordings replay with one warning (polled input reads as idle)
- `--replay-fps {recorded,real}` (default `recorded`): FPS events, the performance stats and the
  overlay's performance panel use the recorded frame times (exact, compared) or this machine's
  measured ones (FPS events then not compared); logic always gets the recorded `dt`
- Real input, device and window events are blocked at SDL during a replay
  (`glitchygames/replay/input_blocking.py`; never QUIT, the window close event or custom types;
  re-blocked every pump, as event managers made mid-run allow their types; each type's prior
  blocked state is restored exactly when the replay ends, normally or after an error). Caveat:
  posts of a blocked type are refused too, so game code that fakes input by posting e.g. KEYDOWN
  shows a "missing internal event" divergence in a replay
- `--headless` (any run; "Diagnostics Options" group): `SDL_VIDEODRIVER`/`SDL_AUDIODRIVER` set
  to `dummy` right after the options are read (a display or mixer pygame already started on
  another driver is restarted on the dummy one, the mixer with its format and channel count, with
  a warning). Live headless runs pace normally and end as the game ends; a
  headless replay is unpaced (`EngineSources.paced_frame_seconds()` returns 0.0: no timer
  deadline, no clock tick) and prints its report to stdout instead of logging it. A replay that a
  crash, Ctrl-C, signal or the game's own exit ends early reports only `Replay stopped at frame
  N: the run ended with ...` (after its result: the result, then `then the run ended with ...`).
  The diagnostic flags (`--headless`, `--debug-overlay`, the trace/replay/audit flags, the timer
  jitter and FPS report flags) are in the "Diagnostics Options" group
- Golden replays: `tests/fixtures/replays/<console-script>/golden.jsonl.gz`, recorded through the
  real engine loop by `scripts/record_scripted_session.py` (a supervisor posts each game's golden
  input script one frame ahead; never the golden harness, whose recordings have no FPS events).
  `tests/replay/test_golden_replays.py` replays each with `--replay-trace PATH --headless` and
  requires exit `SUCCESS` (failing with the printed report); re-record only deliberately (commands
  in the script's docstring)
- `--replay-trace PATH --audit` (`glitchygames/replay/audit.py`): instead of replaying, runs the
  same command twice as child processes (`--no-audit --headless --replay-digest <temp>`,
  `PYTHONHASHSEED` 1 and 2) and compares each run with the recording and the two
  per-frame digest streams (`--replay-digest PATH`: a SHA-256 per replayed frame, then the
  divergence); exits `SUCCESS` (0) when deterministic, `AUDIT_NONDETERMINISTIC` (3) otherwise,
  `INTERNAL_ERROR` (70) when a child could not finish (did not start, hung, crashed, wrote no
  digests); refused with `OPTIONS_REFUSED` (64) under `--replay-fps real` or `python -E`/`-I`,
  which would keep PYTHONHASHSEED from the children, and with `UNUSABLE_INPUT` (65) for a
  truncated recording (an audit needs the whole recording). It compares only
  what the replay samples: the scene class and each sprite's `rect`, `visible` and draw order, not
  pixels, audio or unsampled game state. Children run through `subprocess.run` (argument list, no shell; the
  one authorised subprocess suppression), with a timeout
- Pending: Part 2 (watched replay controls, `--rebaseline`, the pytest plugin; `--headless` is
  done) and
  Part 3 (in-game playback: demos, instant replay, ghosts); see `plans/future-work.md`. User docs:
  `docs/architecture/gameplay_replay.md`

**Screen Shake and Rumble** (`glitchygames/effects/shake.py`, `glitchygames/input/rumble.py`)
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

**Sound Synthesis** (`glitchygames/audio/synth.py`, `recipes.py`, `live.py`)
- Toolkit: oscillators (PolyBLEP square/saw), pitch curves via easing, envelopes, FIR filters,
  mixing, `to_sound()`
- Recipes: `Tone`/`SoundRecipe` (TOML-loadable) played through `SoundBank`
- Live voices: `scene_manager.live_audio.create_voice(owner=...)`, streamed in 100 ms chunks on
  a channel pool reserved at startup (`--live-voice-pool`, default 4)
- Mixer: 44100 Hz, signed 16-bit, stereo, 512-sample buffer (started by `pygame.init()`)
- GIL: the engine sets `sys.setswitchinterval(GIL_SWITCH_INTERVAL_SECONDS)` (0.5 ms, `timing.py`) so the
  mixer callback can queue the next chunk; check with `uv run python scripts/audio_glitch_probe.py`

**Transitions** (`glitchygames/transitions/`): `on_update` callback, `add_cue(progress, callback)`,
`eased_velocity_at(progress)`; cues run after the old scene's cleanup, so they may use only
SceneManager services

**Debug Overlay** (`glitchygames/debug/`): `--debug-overlay` or F3 shows it, F4 cycles panels
(collision hitboxes by layer, physics velocities and ground state, camera panel with world edges
and mouse world position (bounds clamp the camera's top-left, so right/bottom edges are max +
screen size - 1), performance HUD with FPS, frame time, 1% low and a frame-time graph with a target
line). Drawn in `SceneManager._present_frame`, never in screenshots, with the bundled Bitstream
Vera Sans font on translucent cached backings. Scenes or sprites can add annotations with
`debug_draw(surface, camera)`. `Scene.debug_subject` names the scene to inspect (normally the scene
itself; `PauseScene` returns the paused game, so its hitboxes line up with the frozen picture and
the HUD shows `| paused: <name>`).

**Pixel snapping** (`glitchygames/pixel_snap.py`): `PixelSnapMode` and `snap_to_pixel` convert
sub-pixel world positions to drawn whole pixels (NEAREST_HALF_UP for smooth-motion games, FLOOR
for retro/platformer games), shared by sprites, collision and the debug overlay. A scene picks its
mode with `Scene.PIXEL_SNAP_MODE`; a sprite may override it with `pixel_snap_mode` (the ball does).

### Event System

**Event Flow**: `active_sources().pump_events()` (live: `pygame.event.get()`) → `GameEngine.process_events()` → `EVENT_HANDLERS[type]()` → `SceneManager.on_*_event()` → `Scene.on_*_event()` → `Sprite.on_*_event()`

**Event Categories**:
- Audio, Controller, Keyboard, Mouse, Window, Touch, Joystick, MIDI
- Custom: `FPSEVENT`, `GAMEEVENT`, `MENUEVENT`

**Event Managers** (`glitchygames/events/`):
- Specialized classes: `MouseEventManager`, `KeyboardEventManager`, `ControllerEventManager`
- Scenes override `on_*_event()` methods to handle specific events
- `HashableEvent`: Custom wrapper allowing arbitrary attributes
- Unhandled events: `GameEngine.unhandled_events` keeps per-type count, first-seen time and attribute names; logged as a table at teardown (`_shutdown`)

### Sprite and Animation System

**Sprite Hierarchy** (`glitchygames/sprites/`):
- `RootSprite`: Base with mouse events and `pygame.sprite.DirtySprite`
- `Sprite`: General-purpose with coordinates, name, parent tracking
- `BitmappySprite`: Loaded from TOML files
- `AnimatedSprite`: Multi-frame animation support
- `FocusableSingletonBitmappySprite`: UI widgets with keyboard focus

**Animation** (`glitchygames/sprites/animated.py`):
- `FrameManager`: Centralized frame state with observer pattern
- Multiple named animation sequences per sprite
- Per-frame timing overrides
- TOML format with RGBA/RGB support (magenta key: 255,0,255)

**Hitboxes** (`glitchygames/collision/`): default to the image's visible pixels (alpha/colorkey
trimmed, `collision/bounds.py`, measured every query so redrawn images are fine);
`TRIM_TRANSPARENT_HITBOX = False` opts out and TOML hitboxes win (native pixels times
`AnimatedSprite.hitbox_scale`; `hitbox_flip_x = True` mirrors them for a sprite drawn facing
left). `AnimatedSprite.common_hitbox_x_range()` is the x-span every frame shares (use it for
standing support so a wider frame cannot catch a ledge), and
`collision.layers.collision_rect_offset(sprite)` places a sprite so its collision rect is flush
against a wall. Caveat: TOML `AnimatedSprite`s that are not converted to alpha keep magenta as
opaque pixels, so the visible-pixel default trims nothing for them; give them a `[sprite.hitbox]`
(e.g. the union of their frames' non-magenta bounds, as `ghosty.toml` does).
Frames of different shapes: draw walkers bottom-aligned, or set `AnimatedSprite.frame_anchor`
(`FrameAnchor`: edge names align one axis, CENTER/corners both; `[sprite] frame_anchor =
"bottom"`). The engine adds `draw_offset` to `rect` for world-space sprites; a screen-space sprite
adds it to `rect` itself.

**Rendering Optimization**:
- `pygame.sprite.LayeredDirty` for dirty-rect rendering
- Sprites with `dirty=1` force redraw; `dirty=0` skips rendering
- Film strip sprites update every frame for animation preview

### UI Subsystem (`glitchygames/ui/`)

Components: `MenuBar`, `MenuItem`, `TextSprite`, `MultiLineTextBox`, `SliderSprite`, `TabControlSprite`, `ColorWellSprite`

Dialogs: `LoadDialogScene`, `SaveDialogScene`, `NewCanvasDialogScene`

**Focus Model**: Focusable sprites intercept keyboard input via `active` attribute

### Bitmappy Pixel Art Editor (`glitchygames/bitmappy/`)

Features:
- Canvas-based pixel editing with undo/redo (`UndoRedoManager`)
- Animation timeline (`FilmStripWidget`)
- Multi-controller support (`MultiControllerManager`)
- Collision visualization (`VisualCollisionManager`)
- TOML file format for sprites
- AI integration via aisuite
- Voice recognition support
- PNG drag-and-drop

### Resource Management

**Fonts** (`glitchygames/fonts/`): `FontManager` singleton with Bitstream Vera fonts

**Colors** (`glitchygames/color/`): Palettes (NES, SYSTEM, VGA) and constants

**Game Objects** (`glitchygames/game_objects/`): Physics objects (Ball, Paddle)

**Performance** (`glitchygames/performance/`): `AdaptiveClamping` for FPS monitoring

## Design Patterns

- **Singleton**: `SceneManager`, `FontManager`
- **Observer**: `FrameManager` for animation frame changes
- **Strategy**: Timer backends, display update modes, controller modes
- **Proxy**: Event routing through `SceneManager` to `Scene`
- **Factory**: `SpriteFactory` for TOML-based sprite creation

## Testing Guidelines

- Use `pytest` assertions (not unittest style)
- Leverage centralized mocks when available
- Test filenames: Use descriptive names, not generic suffixes like `_simple`
- `tests/conftest.py` defaults `SDL_VIDEODRIVER` and `SDL_AUDIODRIVER` to `dummy` for every run (no windows, no sound), so
  plain `uv run pytest` is enough; set either variable yourself only to override (e.g. `SDL_VIDEODRIVER=cocoa`)
- All tests run with `no_unhandled_events=True` to catch unhandled events as bugs
- Coverage minimum: 80%
- Run linting after modifying files
- Check for real bugs before assuming test failures are test issues

## Code Style

- Python 3.14 target
- Ruff for linting/formatting (100 char line length)
- Google-style docstrings
- Pyright for type checking (lenient configuration)
- Import ordering enforced by ruff

## Known Bugs

**Active Issues**: see BUGS.md for the current list.

## File Formats and Sprite Loading

**Supported Format**: TOML only (YAML and INI support removed)

**Sprite Loading** (`glitchygames/sprites/__init__.py`):
- `SpriteFactory.load_sprite(filename)` - Automatic type detection
- Supports static sprites (single frame) and animated sprites (multi-frame)
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
- Three modes: Film Strip, Canvas, Slider
- Mode switching: L2 (Canvas), R2 (Film Strip), L2+R2 (Slider)
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

- **Test Suite**: Migrating to TOML-only (see TEST_UPDATE_PLAN.md)
- **Sprite Loading**: Use `SpriteFactory` not direct `BitmappySprite` for new code
- **Event Managers**: May be renamed to `*EventManager` convention in future
- **Coverage**: 80% minimum required, exceptions handled via configuration
- **Documentation**: Architecture details in root .md files (ANIMATION_README.md, LOADER_README.md, etc.)
