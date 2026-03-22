# GlitchyGames Engine

A Python 3.13 game engine built on Pygame with an event-driven architecture. Includes Bitmappy, a full-featured pixel art editor with animation support, AI sprite generation, and voice recognition.

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/terrysimons/glitchygames.git
cd glitchygames

# Install core dependencies
uv sync

# Install with dev extras (testing, linting, type checking, security scanning)
uv sync --extra dev

# Install with API extras (FastAPI sprite server)
uv sync --extra api

# Install with documentation extras (MkDocs)
uv sync --extra docs

# Install everything
uv sync --all-extras
```

### Optional Dependency Groups

| Extra | Purpose |
|-------|---------|
| `dev` | pytest, ruff, pyright, bandit, safety, coverage, benchmarks |
| `api` | FastAPI sprite server and client (uvicorn, httpx, apng, pillow) |
| `docs` | MkDocs documentation generation |

## Script Entrypoints

### `bitmappy` -- Pixel Art Editor

Full-featured pixel art and sprite editor with animation timeline, multi-controller support (up to 4 simultaneous controllers), AI sprite generation, and voice recognition.

```bash
# Run with default settings (32x32 canvas)
uv run bitmappy

# Custom canvas size
uv run bitmappy -s 64x64

# High-precision timing backend
uv run bitmappy --timer-backend=fast

# Custom target FPS
uv run bitmappy --target-fps=120
```

#### Bitmappy Options

| Flag | Description | Default |
|------|-------------|---------|
| `-v`, `--version` | Print the version and exit | -- |
| `-s`, `--size` | Canvas size (e.g. `32x32`, `64x64`) | `32x32` |

#### Keyboard Controls

| Key | Action |
|-----|--------|
| Control+click | Flood fill |
| O | Toggle onion skinning |
| B (controller) | Undo |
| X (controller) | Redo |
| Y (controller) | Mode-specific toggle |

#### Controller Modes (L2/R2 switching)

| Mode | Trigger | D-pad | A button | L1/R1 |
|------|---------|-------|----------|-------|
| Film Strip | R2 | Navigate frames | Select frame | Switch animations |
| Canvas | L2 | Move cursor | Paint pixel | 8-pixel jumps |
| Slider | L2+R2 | Adjust value | -- | Adjust by 8 |

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
| GET | `/` | Health check |
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
uv run glitchygames-client "blue dragon" --model anthropic:claude-sonnet-4-5
```

#### Client Options

| Flag | Description | Default |
|------|-------------|---------|
| `prompt` | Text description of the sprite to generate | -- |
| `--server` | Server URL | `http://localhost:8000` |
| `-f`, `--output-format` | Output format: `toml`, `png`, or both | both |
| `-o`, `--output-path` | Directory to save output files | -- |
| `--width` | Sprite width in pixels | 16 |
| `--height` | Sprite height in pixels | 16 |
| `--frame-count` | Number of animation frames (1-32) | 1 |
| `--film-strip-count` | Number of film strips (1-8) | 1 |
| `--animation-duration` | Animation duration in seconds (0-60) | -- |
| `--png-scale` | PNG output scale factor (1-10) | 1 |
| `--model` | AI model override (aisuite format) | -- |
| `--extract-frames` | Extract frames from an APNG file | -- |
| `-v` | Verbose output | -- |
| `-q` | Quiet output | -- |

## Engine Options

All games built on GlitchyGames inherit these command-line options from the engine.

### Graphics Options

| Flag | Description | Default |
|------|-------------|---------|
| `-f`, `--target-fps` | Cap the framerate (0 = unlimited) | `0.0` |
| `--fps-log-interval-ms` | How often to log the FPS counter in milliseconds | `1000` |
| `-w`, `--windowed` | Run in windowed mode | `True` |
| `-r`, `--resolution` | Display resolution (e.g. `1024x768`) | `800x480` |
| `--use-gfxdraw` | Use pygame.gfxdraw for rendering | `False` |
| `--update-type` | Display update method: `update` (dirty rects) or `flip` (full screen) | `update` |
| `--video-driver` | SDL video driver override (platform-specific) | auto |

#### Platform-Specific Video Drivers

| Platform | Available Drivers |
|----------|-------------------|
| Linux | `wayland`, `x11`, `dga`, `fbcon`, `directfb`, `ggi`, `vgl`, `svgalib`, `aalib` |
| Windows | `windib`, `directx` |

### Timer / Frame Pacing Options

| Flag | Description | Default |
|------|-------------|---------|
| `--timer-backend` | Timer backend: `pygame` or `fast` | `pygame` |
| `--sleep-granularity-ns` | Minimum sleep granularity in nanoseconds (0 = spin-only) | `1000000` (1 ms) |
| `--windows-timer-1ms` | Request 1 ms system timer resolution via WinMM (Windows only) | `False` |
| `--log-timer-jitter` | Log frame pacing jitter statistics (p50/p95/p99/max) | `False` |
| `--perf-trim-percent` | Percent of frames to trim from FPS reporting (top and bottom) | `5.0` |

The `fast` timer backend uses `time.perf_counter_ns()` with a sleep+spin hybrid for tighter frame pacing than pygame's built-in `pygame.time.delay`.

### Game Options

| Flag | Description | Default |
|------|-------------|---------|
| `-l`, `--log-level` | Logging level: `debug`, `info`, `warning`, `error`, `critical` | `info` |
| `--no-unhandled-events` | Fail on unhandled events (used in testing) | `False` |
| `-p`, `--profile` | Enable cProfile profiling | `False` |

### Controller Options

| Flag | Description | Default |
|------|-------------|---------|
| `--input-mode` | Input event family: `joystick` or `controller` | `controller` |

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

The engine uses pygame's mixer for audio playback, pre-initialized at 22050 Hz, 16-bit stereo with a 1024-byte buffer. Audio device hotplug events (`AUDIO_DEVICE_ADDED`, `AUDIO_DEVICE_REMOVED`) are routed through the event system.

### Voice Recognition

Voice recognition provides hands-free command input in Bitmappy. It uses the `speech_recognition` library with Google's speech API.

#### Microphone Backends (auto-detected, priority order)

1. **Miniaudio** -- preferred backend using the `miniaudio` library. Captures at 16000 Hz mono, SIGNED16 format.
2. **PortAudio** -- fallback, wraps `speech_recognition.Microphone` (requires PyAudio).

The backend registry (`voice_backends/registry.py`) automatically probes available backends and selects the best one. If neither is available, voice recognition is disabled gracefully.

#### Voice Commands in Bitmappy

Commands are registered dynamically. The voice manager runs a listening loop in a daemon thread with:
- 1 second ambient noise calibration at startup
- 10 second phrase time limit
- Exact and partial phrase matching

## Development

### Testing

```bash
# Run all tests with coverage (80% minimum required)
uv run pytest

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
uv run ruff format glitchygames tests scripts noxfile.py

# Fix import ordering
uv run ruff check --select I --fix glitchygames tests scripts noxfile.py

# Lint
uv run ruff check glitchygames tests scripts noxfile.py

# Type check
uv run pyright
```

### Nox Sessions

```bash
# Lint code and docs
nox -s lint

# Format code
nox -s format

# Run tests with coverage reports (HTML, XML, JSON, LCOV)
nox -s test

# Security scanning (bandit + safety)
nox -s security_scan

# Performance benchmarks
nox -s performance_test
```
