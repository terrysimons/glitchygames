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
