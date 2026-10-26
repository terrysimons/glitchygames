# GlitchyGames Engine

A Python 3.14 game engine built on Pygame with an event-driven architecture. Includes Bitmappy, a full-featured pixel art editor with animation support, AI sprite generation, and voice recognition.

## Getting Started

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/terrysimons/glitchygames.git
cd glitchygames

# Install core dependencies (--all-packages: the workspace members too, src/games/mr-muncher)
uv sync --all-packages

# Install with dev extras (testing, linting, type checking, security scanning)
uv sync --extra dev --all-packages

# Install with documentation extras (MkDocs)
uv sync --extra docs --all-packages

# Install everything
uv sync --all-extras --all-packages
```

### Optional Dependency Groups

| Extra | Purpose |
|-------|---------|
| `dev` | nox, pytest (cov, xdist, mock, benchmark), hypothesis, ruff, basedpyright, ty, bandit, safety, pip-audit, deptry, vulture, wily, pyinstaller |
| `docs` | MkDocs documentation generation |

The sprite API server and client (FastAPI, uvicorn, httpx, apng, pillow) are core dependencies; the `api` extra is empty.

## Script Entrypoints

### `bitmappy` -- Pixel Art Editor

Full-featured pixel art and sprite editor with animation timeline, multi-controller support (up to 4 simultaneous controllers), AI sprite generation, and voice recognition.

```bash
# Run with default settings (32x32 canvas)
uv run bitmappy

# Custom canvas size
uv run bitmappy -s 64x64

# Timer backend without the measured sleep model (the default is auto)
uv run bitmappy --timer-backend=fast

# Custom target FPS
uv run bitmappy --target-fps=120
```

#### Bitmappy Options

| Flag | Description | Default |
|------|-------------|---------|
| `-v`, `--version` | Print the version and exit (parsed but not implemented yet: BUGS.md #178, item 25) | -- |
| `-s`, `--size` | Canvas size (e.g. `32x32`, `64x64`) | `32x32` |

#### Keyboard Controls

| Key | Action |
|-----|--------|
| Control+click | Flood fill |
| O | Toggle onion skinning |
| Control+Shift+Arrow | Move the current frame's pixels one pixel that way (hold to repeat, up to 10 pixels per press-and-hold; pixels moved past the edge are dropped when the keys come up; Control+Z undoes the whole move) |
| B (controller) | Undo |
| X (controller) | Redo |
| Y (controller) | Mode-specific toggle |

#### Controller Modes (L2/R2 switching)

L2 steps forward through the modes (Film Strip -> Canvas -> R, G, B sliders -> Film Strip); R2 steps back (B -> G -> R -> Canvas -> Film Strip; R2 does nothing on the Film Strip).

| Mode | D-pad | A button | L1/R1 |
|------|-------|----------|-------|
| Film Strip | Navigate frames | Select frame | Switch animations |
| Canvas | Move cursor | Paint pixel | 8-pixel jumps |
| R/G/B Slider | Adjust value | -- | Adjust by 8 |

### `glitchygames-server` -- Sprite API Server

FastAPI-based server for AI sprite generation, sprite rendering, and APNG frame extraction.

```bash
# Start the server (default: http://127.0.0.1:8000)
uv run glitchygames-server

# Docs available at http://localhost:8000/docs
```

#### Server Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API information (name, version, docs and health links) |
| GET | `/health` | Health check (status, version, AI provider and model) |
| POST | `/sprites/generate` | Generate a sprite from a text prompt |
| POST | `/sprites/refine` | Refine an existing sprite with a new prompt |
| POST | `/sprites/extract-frames` | Extract individual frames from an APNG |

#### Server Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GLITCHYGAMES_HOST` | Bind address | `127.0.0.1` |
| `GLITCHYGAMES_PORT` | Bind port | `8000` |
| `GLITCHYGAMES_RELOAD` | Enable auto-reload | `false` |

### `glitchygames-client` -- Sprite API Client

CLI client for the sprite API server. Generates sprites from text prompts and extracts APNG frames.

```bash
# Generate a sprite from a prompt
uv run glitchygames-client "Create a 16x16 jumping frog"

# Generate with specific dimensions and animation
uv run glitchygames-client "walking knight" --width 32 --height 32 --frame-count 4

# Save output to a directory
uv run glitchygames-client "idle slime" -o ./sprites/

# Extract frames from an APNG file
uv run glitchygames-client --extract-frames animation.apng

# Output as TOML only
uv run glitchygames-client "red mushroom" -f toml

# Use a specific AI model
uv run glitchygames-client "blue dragon" --animation-language-model anthropic:claude-sonnet-4-5
```

#### Client Options

| Flag | Description | Default |
|------|-------------|---------|
| `prompt` | Text description of the sprite to generate | -- |
| `--server-url` | Server URL | `http://localhost:8000` |
| `-f`, `--output-format` | Output format: `toml` or `png` (repeat for both) | both |
| `-o`, `--output-path` | Directory to save output files | -- |
| `--width` | Sprite width in pixels (1-64) | the AI chooses |
| `--height` | Sprite height in pixels (1-64) | the AI chooses |
| `--frame-count` | Number of animation frames (1-32) | 1 |
| `--film-strip-count` | Number of film strips (1-8) | 1 |
| `--animation-duration` | Animation duration in seconds (0-60) | -- |
| `--png-scale` | PNG output scale factor (1-10) | 1 |
| `--extract-scale` | Nearest-neighbor scale factor for extracted PNG frames | 8 |
| `--animation-language-model` | AI model override (aisuite format) | -- |
| `--extract-frames` | Extract frames from an APNG file | -- |
| `-v`, `--verbose` | Verbose output | -- |
| `-q`, `--quiet` | Quiet output | -- |

### Example Games

`uv run paddleslap`, `uv run brave-adventurer`, `uv run clockwork-keep`, `uv run mr-muncher` and `uv run drawing-fire` start the example games: Mr. Muncher and Clockwork Keep are each their own package (`src/games/mr-muncher/`, `src/games/clockwork-keep/`), both Brave Adventurer editions are one package in `src/games/brave-adventurer/` (its title screen offers Classic and Papyrus; `--game classic` or `--game papyrus` starts one at once), the others are still in `src/glitchygames/examples/`.

## Engine Options

All games built on GlitchyGames inherit these command-line options from the engine.

### Graphics Options

| Flag | Description | Default |
|------|-------------|---------|
| `-f`, `--target-fps` | Cap the framerate (0 = uncapped) | the game's `TARGET_FPS`, else `60.01` |
| `--fps-log-interval-ms` | How often to log the FPS counter in milliseconds | `1000` |
| `-w`, `--windowed`, `--no-windowed` | Run in a window; `--no-windowed` runs fullscreen | windowed |
| `-r`, `--resolution` | Display resolution (e.g. `1024x768`) | `800x480` |
| `--use-gfxdraw` | Not used yet: stored, but nothing draws with pygame.gfxdraw because of it | `False` |
| `--update-type` | Display update method: `update` (dirty rects) or `flip` (full screen) | `update` |
| `--video-driver` | Not applied yet: stored, but SDL picks its video driver from `SDL_VIDEODRIVER` (or `--headless`) | none |
| `--random-seed` | Master seed for every engine random stream | a random 64-bit seed |
| `--screen-shake-intensity` | Screen shake strength, 0.0 (off) to 1.0 | `1.0` |
| `--rumble-intensity` | Controller rumble strength, 0.0 (off) to 1.0 | `1.0` |
| `--live-voice-pool` | Mixer channels reserved for real-time synth voices | `4` |
| `--crt-power-on` | Show the canvas switching on like a CRT before the game starts: `auto` (when someone can see it: not on SDL's dummy driver or before a replay, audit, rebaseline or recording), `on` (refused with a replay or recording) or `off` | `auto` |
| `--default-background` | Background of a scene that sets none: `test-pattern` or `channel-3` | `test-pattern` |

#### Platform-Specific Video Drivers

| Platform | Available Drivers |
|----------|-------------------|
| macOS | `cocoa`, `offscreen`, `dummy` |
| Windows | `windows`, `offscreen`, `dummy` |
| Linux | `x11`, `wayland`, `kmsdrm`, `offscreen`, `dummy` |
| any other | `offscreen`, `dummy` |

### Timer / Frame Pacing Options

| Flag | Description | Default |
|------|-------------|---------|
| `--timer-backend` | Timer backend: `auto` (fast, with this machine's sleep delay measured so each sleep wakes in time), `fast` (assumes sleeps wake on time) or `pygame` | `auto` |
| `--sleep-granularity-ns` | How long before each frame deadline the fast backend is to wake from its sleep and spin, in nanoseconds (0 = spin-only) | `1000000` (1 ms) |
| `--windows-timer-1ms` | Request 1 ms system timer resolution via WinMM (Windows only) | `False` |

The `fast` timer backend uses `time.perf_counter_ns()` with a sleep+spin hybrid for tighter frame pacing than pygame's built-in timing; `auto` also sizes each sleep with this machine's measured sleep delay.

### Diagnostics Options

| Flag | Description | Default |
|------|-------------|---------|
| `--log-timer-jitter` | Log frame pacing jitter statistics periodically | `False` |
| `--perf-trim-percent` | Percent of frames to trim from FPS reporting (top and bottom) | `5.0` |
| `--fps-histogram` | FPS histogram buckets in the shutdown report: `equal-range` or `target-relative` | `equal-range` |
| `--debug-overlay` | Show the debug overlay at startup (F3 toggles, F4 cycles panels) | `False` |
| `--debug-events` | Log a warning the first time each unhandled event type arrives | `False` |
| `--headless` | Run on SDL's dummy video and audio drivers (no window, no sound) | `False` |
| `--list-input-devices` | Print every joystick and game controller the game would see (index, instance id, name, GUID, whether SDL maps it as a game controller, its axes, buttons, hats and balls; how many SDL counted before its queue was pumped, and each device added or removed while listening, with when), then exit without running the game. At a terminal, when none is found it asks you to plug one in and waits (Ctrl-C stops). Refused with `--replay-trace` or `--record-trace` | `False` |
| `--record-trace PATH` | Record the session to a gzip JSON Lines trace for later replay | off |
| `--replay-trace PATH` | Replay a recording through the engine, comparing every frame | off |

The other replay options (`--replay-fps`, `--audit`, `--compare-processing`, `--max-processing-slowdown`, `--replay-pause-at-frame`, `--rebaseline`, `--replay-digest`) are described in [Gameplay Recording and Replay](docs/architecture/gameplay_replay.md).

### Game Options

| Flag | Description | Default |
|------|-------------|---------|
| `-l`, `--log-level` | Logging level: `debug`, `info`, `warning`, `error`, `critical` | `info` |
| `--no-unhandled-events` | Fail on unhandled events (used in testing) | `False` |
| `-p`, `--profile` | Enable cProfile profiling | `False` |

### Font Options

| Flag | Description | Default |
|------|-------------|---------|
| `--font-name` | Font to use: the bundled `Vera`, `VeraBd`, `VeraIt`, `VeraBI`, or a system font | `Vera` |
| `--font-size` | Size of the default font (text that asks for no font of its own) | `14` |
| `--font-dpi` | Resolution freetype font sizes are scaled at (the pygame font system ignores it) | `72` |
| `--font-bold`, `--font-italic`, `--font-antialias` | Not used yet: stored, but no font reads them | `False` |
| `--font-system` | `freetype` or `pygame` | `freetype` |

### Controller Options

| Flag | Description | Default |
|------|-------------|---------|
| `--input-mode` | Which gamepads the game sees: `auto` (every device; a mapped pad sends controller events, any other device joystick events, each press once), `joystick` (every device sends joystick events) or `controller` (mapped pads only) | `auto` |

## AI Sprite Generation

GlitchyGames integrates with AI providers via [aisuite](https://github.com/andrewyng/aisuite) for text-to-sprite generation. AI generation is available in both Bitmappy (interactive) and the API server (programmatic).

### Supported Providers

Any provider supported by aisuite, including:

- **Anthropic** (Claude models) -- default
- **OpenAI** (GPT models)
- **Ollama** (local models)

### Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `SPRITE_AI_PROVIDER` | AI provider name | `anthropic` |
| `SPRITE_AI_MODEL` | Model identifier | `claude-sonnet-4-5` |
| `SPRITE_AI_TIMEOUT` | Request timeout in seconds | `120` |
| `SPRITE_DEFAULT_WIDTH` | Default sprite width | `16` |
| `SPRITE_DEFAULT_HEIGHT` | Default sprite height | `16` |
| `SPRITE_MAX_SIZE` | Maximum sprite dimension | `64` |
| `SPRITE_PNG_SCALE` | PNG output scale factor | `1` |

The model string is formatted as `{provider}:{model}` for aisuite (e.g. `anthropic:claude-sonnet-4-5`, `ollama:llama3`).

### How It Works

- **In Bitmappy**: AI requests run in a separate worker process via multiprocessing queues, keeping the editor responsive. Type a sprite description in the AI text box to generate sprites.
- **Via API**: The `/sprites/generate` and `/sprites/refine` endpoints accept text prompts and return TOML sprite data with optional PNG rendering.
- **Prompt System**: Prompts include training examples of the TOML sprite format, automatic size/animation detection, and response validation.

## Audio and Voice Recognition

### Audio Backend

The engine uses pygame's mixer for audio playback, started by `pygame.init()` at 44100 Hz, signed 16-bit stereo with a 512-sample buffer. Live synth voices (`glitchygames/audio/`) stream on a channel pool reserved at startup (`--live-voice-pool`). Audio device hotplug events (`AUDIO_DEVICE_ADDED`, `AUDIO_DEVICE_REMOVED`) are routed through the event system.

### Voice Recognition

Voice recognition provides hands-free command input in Bitmappy. It uses the `speech_recognition` library with Google's speech API.

#### Microphone Backends (auto-detected, priority order)

1. **Miniaudio** -- preferred backend using the `miniaudio` library (`glitchygames/events/voice_miniaudio.py`). Captures at 16000 Hz mono, SIGNED16 format.
2. **PortAudio** -- fallback, wraps `speech_recognition.Microphone` (requires PyAudio).

The backend registry (`glitchygames/events/voice_backends/registry.py`) automatically probes available backends and selects the best one. If neither is available, voice recognition is disabled gracefully.

#### Voice Commands in Bitmappy

Commands are registered dynamically. The voice manager runs a listening loop in a daemon thread with:
- 1 second ambient noise calibration at startup
- 10 second phrase time limit
- Exact and partial phrase matching

## Development

### Testing

```bash
# Run all tests with coverage (the minimum is --cov-fail-under in pyproject.toml). Outside CI this
# also runs the suite on the native SDL driver and fails on any frame that differs
uv run pytest

# Fast iteration: the dummy driver only
uv run pytest --dummy-only

# Run specific test file
uv run pytest tests/test_specific.py

# Run tests matching a pattern
uv run pytest -k "test_pattern"

# Run with parallel execution
uv run pytest -n auto

# Run performance benchmarks only
uv run pytest --benchmark-only
```

### Linting and Type Checking

```bash
# Format code
uv run ruff format src tests scripts noxfile.py

# Fix import ordering
uv run ruff check --select I --fix src tests scripts noxfile.py

# Lint
uv run ruff check src tests scripts noxfile.py

# Type check
uv run basedpyright
```

### Nox Sessions

```bash
# Lint code and docs
nox -s lint

# Format code
nox -s format

# Run tests with coverage reports (HTML, XML, JSON, LCOV)
nox -s test

# Type checkers (basedpyright + ty)
nox -s static-analysis

# Security scanning (bandit + safety)
nox -s security-scan

# Performance benchmarks
nox -s performance-test
```
