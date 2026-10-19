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
  set only there (start to start), so recorded frames sum exactly to wall-clock time and logic,
  the overlay and the FPS statistics all see the same value. Processing time excludes the
  pacing sleep
- After falling more than one frame behind, pacing re-anchors instead of bursting to catch up
  (`next_frame_deadline_ns`; a slightly late frame is still caught up, so the average rate holds)
- Configurable sleep granularity for tight frame pacing
- Windows timer resolution control via WinMM

**World Space** (`glitchygames/world.py`, `glitchygames/camera.py`)
- A sprite declares `COORDINATE_SPACE = CoordinateSpace.WORLD` and keeps float `world_x`/`world_y`
  (the `WorldPositioned` Protocol); the engine is then the only writer of its `rect`. Sprites
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
  `BOTH`, the default); override `Scene.camera_target()` to aim anywhere else (return `None` for a
  manual camera, e.g. after game over). The engine aims with `camera.aim_at`; an axis not followed
  keeps its goal. Camera bounds, lead offsets, smoothing and `snap_to` still apply (without a
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

**Gameplay Recording** (`glitchygames/recording.py`, `glitchygames/randomness.py`)
- `--record-trace PATH`: record the session as a gzip JSON Lines trace (`glitchygames/tracing.py`
  format), one line per frame, with `dt`, the raw `event_batches` read at `GameEngine._pump_events`
  (the only reader of SDL's queue; each event tagged `external`/`internal`), sprites, and a header
  with versions, options and the random seed; off by default. Engine code posts events with
  `glitchygames.recording.post_event` so recordings can mark them internal
- `--random-seed INT`: the run's master seed (default: 64 random bits, kept in recordings). All
  randomness draws from named streams seeded from it: `random_stream('name')` (`random.Random`) or
  `numpy_stream('name')` (numpy `Generator`), looked up at draw time; `engine_random()` is
  `random_stream('engine')`, `reset_streams(seed=...)` reseeds (tests, replay). Never use
  `secrets`, `random.SystemRandom`, global `random.*` functions or an unseeded
  `np.random.default_rng()` in gameplay (`tests/test_randomness.py` scans for them). Replay
  (`--replay-trace`) is planned (`plans/future-work.md`)

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

**Event Flow**: `pygame.event.get()` → `GameEngine.process_events()` → `EVENT_HANDLERS[type]()` → `SceneManager.on_*_event()` → `Scene.on_*_event()` → `Sprite.on_*_event()`

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
