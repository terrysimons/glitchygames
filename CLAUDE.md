# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GlitchyGames is a Python 3.13 game engine built on Pygame with an event-driven architecture. The project includes a full-featured pixel art editor called Bitmappy and supports animation, UI widgets, and physics-based game objects.

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
# Run full lint and test suite
nox -s lint_and_test

# Run security scanning (bandit + safety)
nox -s security_scan

# Run performance benchmarks
nox -s performance_test

# Generate coverage reports
nox -s coverage_report
```

### Running Bitmappy (Pixel Art Editor)
```bash
# Run with default settings
uv run bitmappy

# High-precision timing backend
uv run bitmappy --timer-backend=fast

# Custom target FPS
uv run bitmappy --target-fps=120

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
- Singleton managing the main game loop with four phases:
  1. **Update**: Accumulate delta time via `Scene.dt_tick(dt)`
  2. **Event Processing**: Route pygame events through GameEngine
  3. **Render**: Update dirty sprites and draw via `LayeredDirty.draw()`
  4. **Display Update**: Call `pygame.display.update()` or `flip()`
- Handles scene transitions and lifecycle (`setup()`, `cleanup()`, `load_resources()`)

**Frame Pacing** (`glitchygames/timing.py`)
- Two timer backends:
  - `PygameTimer`: Legacy pygame-based timing
  - `FastTimer`: High-resolution `time.perf_counter_ns()` with sleep+spin hybrid
- Configurable sleep granularity for tight frame pacing
- Windows timer resolution control via WinMM

### Event System

**Event Flow**: `pygame.event.get()` → `GameEngine.process_events()` → `EVENT_HANDLERS[type]()` → `SceneManager.on_*_event()` → `Scene.on_*_event()` → `Sprite.on_*_event()`

**Event Categories**:
- Audio, Controller, Keyboard, Mouse, Window, Touch, Joystick, MIDI
- Custom: `FPSEVENT`, `GAMEEVENT`, `MENUEVENT`

**Event Managers** (`glitchygames/events/`):
- Specialized classes: `MouseEventManager`, `KeyboardEventManager`, `ControllerEventManager`
- Scenes override `on_*_event()` methods to handle specific events
- `HashableEvent`: Custom wrapper allowing arbitrary attributes

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

**Rendering Optimization**:
- `pygame.sprite.LayeredDirty` for dirty-rect rendering
- Sprites with `dirty=1` force redraw; `dirty=0` skips rendering
- Film strip sprites update every frame for animation preview

### UI Subsystem (`glitchygames/ui/`)

Components: `MenuBar`, `MenuItem`, `TextSprite`, `MultiLineTextBox`, `SliderSprite`, `TabControlSprite`, `ColorWellSprite`

Dialogs: `LoadDialogScene`, `SaveDialogScene`, `NewCanvasDialogScene`

**Focus Model**: Focusable sprites intercept keyboard input via `active` attribute

### Bitmappy Pixel Art Editor (`glitchygames/tools/bitmappy.py`)

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

- Python 3.13 target
- Ruff for linting/formatting (100 char line length)
- Google-style docstrings
- Pyright for type checking (lenient configuration)
- Import ordering enforced by ruff

## Known Bugs

**Active Issues** (see BUGS.md for full details):

1. **First Pasted Frame Alpha Loss** (Film Strip)
   - Location: Film strip per-pixel alpha handling
   - Issue: First frame pasted into new film strip loses transparency
   - Workaround: Paste a second frame, transparency works correctly
   - Files: `glitchygames/tools/film_strip.py`

2. **Ball Collision Trajectory Bug** (Game Physics)
   - Location: `glitchygames/game_objects/ball.py`
   - Issue: Horizontal ball doesn't update trajectory after diagonal collision
   - Priority: High

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

**Recently Completed** (see FUTURE_FEATURES.md for roadmap):
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
