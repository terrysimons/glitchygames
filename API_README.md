# GlitchyGames Sprite Generation API

REST API and CLI client for generating pixel art sprites using AI via aisuite.

## Overview

The API consists of two components:

- **`glitchygames-server`** -- A FastAPI server that accepts sprite generation requests, calls an AI provider to produce TOML sprite definitions, and optionally renders them to PNG.
- **`glitchygames-client`** -- A CLI client that talks to the server, saves output files locally, and displays colorized ASCII previews in the terminal.

## Setup

### Install Dependencies

The API requires the `api` extra:

```bash
uv sync --extra api
```

This installs: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `apng`, `pillow`.

For development (running tests):

```bash
uv sync --extra api -E dev
```

### Configure AI Provider

The server uses [aisuite](https://github.com/andrewyng/aisuite) to route to AI providers. Set the appropriate API key for your provider:

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY="your-key"

# OpenAI
export SPRITE_AI_PROVIDER="openai"
export SPRITE_AI_MODEL="gpt-4o"
export OPENAI_API_KEY="your-key"

# Ollama (local)
export SPRITE_AI_PROVIDER="ollama"
export SPRITE_AI_MODEL="llama3"
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SPRITE_AI_PROVIDER` | `anthropic` | AI provider name for aisuite |
| `SPRITE_AI_MODEL` | `claude-sonnet-4-5` | Model identifier for the provider |
| `SPRITE_AI_TIMEOUT` | `120` | API call timeout in seconds |
| `SPRITE_DEFAULT_WIDTH` | `16` | Default sprite width (pixels) |
| `SPRITE_DEFAULT_HEIGHT` | `16` | Default sprite height (pixels) |
| `SPRITE_MAX_SIZE` | `64` | Maximum sprite dimension |
| `SPRITE_PNG_SCALE` | `1` | Default PNG scale factor |
| `GLITCHYGAMES_HOST` | `0.0.0.0` | Server bind address |
| `GLITCHYGAMES_PORT` | `8000` | Server port |
| `GLITCHYGAMES_RELOAD` | `false` | Enable auto-reload for development |

## Server

### Starting the Server

```bash
# Using the entry point
uv run glitchygames-server

# Using uvicorn directly (with auto-reload for development)
uv run uvicorn glitchygames.api.main:app --reload

# Custom host and port
GLITCHYGAMES_HOST=127.0.0.1 GLITCHYGAMES_PORT=9000 uv run glitchygames-server
```

On startup, the server initializes pygame in headless mode (SDL_VIDEODRIVER=dummy) for sprite rendering.

### Interactive Documentation

Once running, the server provides interactive API docs:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Endpoints

#### `GET /` -- API Info

Returns basic API information and links to docs.

```bash
curl http://localhost:8000/
```

```json
{
  "name": "GlitchyGames Sprite Generation API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

#### `GET /health` -- Health Check

Returns service status, version, AI provider configuration, and pygame initialization state.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "ai_provider": "anthropic",
  "ai_model": "claude-sonnet-4-5",
  "pygame_initialized": true
}
```

#### `POST /sprites/generate` -- Generate Sprite

Generate a new sprite from a text prompt.

**Request Body:**

| Field | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | (required) | Text description (1-2000 chars) |
| `width` | int | AI decides | Sprite width (1-64 pixels) |
| `height` | int | AI decides | Sprite height (1-64 pixels) |
| `frame_count` | int | `1` | Frames per animation (1-32) |
| `film_strip_count` | int | none | Number of animations (1-8) |
| `animation_duration` | float | none | Animation duration in seconds (0-60) |
| `output_format` | list | `["toml", "png"]` | Output formats: `"toml"`, `"png"`, or both |
| `png_scale` | int | `1` | PNG scale factor (1-10) |
| `output_path` | string | none | Server-side directory to save files |
| `model` | string | none | AI model override (aisuite format) |

When `frame_count > 1`, all animation frames are automatically rendered to PNG. There is no need for a separate flag.

**Example -- Static sprite:**

```bash
curl -X POST http://localhost:8000/sprites/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "16x16 red heart with golden outline", "output_format": ["toml"]}'
```

**Example -- Animated sprite:**

```bash
curl -X POST http://localhost:8000/sprites/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "16x16 slime bouncing",
    "frame_count": 8,
    "output_format": ["toml", "png"]
  }'
```

**Response Fields:**

| Field | Type | Description |
|---|---|---|
| `success` | bool | Whether generation succeeded |
| `sprite_name` | string | Name extracted from TOML |
| `is_animated` | bool | Whether the sprite has animation |
| `frame_count` | int | Number of frames |
| `width` | int | Sprite width (pixels) |
| `height` | int | Sprite height (pixels) |
| `toml_content` | string | Generated TOML definition |
| `png_base64` | string | Base64-encoded PNG of first frame |
| `all_frames_png_base64` | list[string] | Base64-encoded PNGs for all frames |
| `rendered_frames` | list[RenderedFrameInfo] | Frames with animation/frame indices |
| `saved_files` | list[string] | Paths of saved files (if `output_path` set) |
| `error` | string | Error message (if `success` is false) |

Each `RenderedFrameInfo` contains:

| Field | Type | Description |
|---|---|---|
| `animation_index` | int | Which animation (film strip) this frame belongs to (0-indexed) |
| `frame_index` | int | Frame position within its animation (0-indexed) |
| `png_base64` | string | Base64-encoded PNG data |

**Error Responses:**

| Status | Cause |
|---|---|
| 422 | Validation error (empty prompt, invalid dimensions, etc.) |
| 503 | AI provider unavailable |
| 500 | Internal server error |

#### `POST /sprites/refine` -- Refine Sprite

Modify an existing sprite based on instructions. Returns the same response format as `/sprites/generate`.

```bash
curl -X POST http://localhost:8000/sprites/refine \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Make the heart blue instead of red",
    "current_toml": "<existing TOML content>",
    "output_format": ["toml", "png"]
  }'
```

**Additional Request Fields:**

| Field | Type | Description |
|---|---|---|
| `current_toml` | string | (required) Existing sprite TOML to refine |

#### `POST /sprites/extract-frames` -- Extract APNG Frames

Extract individual frames and timing metadata from an APNG file.

```bash
curl -X POST http://localhost:8000/sprites/extract-frames \
  -H "Content-Type: application/json" \
  -d '{"apng_base64": "<base64-encoded APNG>"}'
```

**Response Fields:**

| Field | Type | Description |
|---|---|---|
| `success` | bool | Whether extraction succeeded |
| `frame_count` | int | Number of frames extracted |
| `width` | int | Canvas width (pixels) |
| `height` | int | Canvas height (pixels) |
| `loop_count` | int | Loop count (0 = infinite) |
| `total_duration_ms` | int | Total animation duration |
| `frames` | list[ApngFrameInfo] | Per-frame data |

Each `ApngFrameInfo` contains:

| Field | Type | Description |
|---|---|---|
| `index` | int | Frame index (0-based) |
| `png_base64` | string | Base64-encoded PNG |
| `delay_ms` | int | Frame delay in milliseconds |
| `width` | int | Frame width (pixels) |
| `height` | int | Frame height (pixels) |
| `x_offset` | int | X offset within canvas |
| `y_offset` | int | Y offset within canvas |

## Client CLI

### Basic Usage

```bash
# Generate a static sprite (prints TOML to stdout)
uv run glitchygames-client "16x16 red heart"

# Generate and save to a directory
uv run glitchygames-client "16x16 red heart" -o ./sprites

# Generate with specific output formats
uv run glitchygames-client "16x16 red heart" -f toml -f png -o ./sprites
```

### All Options

```
glitchygames-client [OPTIONS] PROMPT

Positional Arguments:
  PROMPT                    Text description of the sprite to generate
                            (optional when using --extract-frames)

Options:
  --server-url URL          Server URL (default: http://localhost:8000)
  -f, --output-format FMT   Output format: "toml" or "png" (repeatable,
                            default: both)
  -o, --output-path DIR     Directory to save output files
  --width N                 Sprite width in pixels (1-64)
  --height N                Sprite height in pixels (1-64)
  --frame-count N           Number of frames per animation (1-32)
  --film-strip-count N      Number of film strips/animations (1-8)
  --animation-duration SEC  Animation duration in seconds
  --png-scale N             Scale factor for PNG output (1-10, default: 1)
  --extract-scale N         Scale factor for extracted frame PNGs using
                            nearest-neighbor (default: 8)
  --animation-language-model MODEL
                            AI model override (aisuite format,
                            e.g., "anthropic:claude-sonnet-4-5")
  --extract-frames PATH     Extract frames from an APNG file instead
                            of generating a sprite
  -v, --verbose             Enable verbose output
  -q, --quiet               Suppress output except errors
```

### Examples

**Static sprite with custom dimensions:**

```bash
uv run glitchygames-client "sword with a blue gem in the hilt" \
  --width 16 --height 32 -o ./sprites
```

**Animated sprite:**

```bash
uv run glitchygames-client "16x16 slime bouncing" \
  --frame-count 8 --animation-duration 1.0 -o ./sprites
```

**Multi-animation sprite:**

```bash
uv run glitchygames-client "16x16 character" \
  --frame-count 4 --film-strip-count 3 -o ./sprites
```

**Using a different AI model:**

```bash
uv run glitchygames-client "16x16 treasure chest" \
  --animation-language-model "openai:gpt-4o" -o ./sprites
```

**Extract frames from an existing APNG:**

```bash
uv run glitchygames-client --extract-frames sprite.apng -o ./extracted
```

**Lower extract scale for smaller files:**

```bash
uv run glitchygames-client "16x16 mushroom" \
  --frame-count 4 -o ./sprites --extract-scale 2
```

### Terminal Preview

When the response includes TOML content, the client automatically displays a colorized ASCII preview of the sprite in the terminal. Static sprites show a single preview; animated sprites show all frames grouped by animation sequence.

## Output Directory Structure

When saving with `-o`, the client creates a numbered directory per sprite to avoid overwrites:

```
sprites/
  mushroom-001/
    mushroom.toml           # Sprite TOML definition
    mushroom.apng           # Animated PNG (if animated)
    extracted/
      animation-0-frame-0.png  # Individual frames (upscaled)
      animation-0-frame-1.png
      animation-0-frame-2.png
      animation-1-frame-0.png  # Second animation sequence
      animation-1-frame-1.png
```

### Frame Naming Convention

Extracted frames follow the pattern: `animation-{N}-frame-{M}.png`

- `N` = animation index (0-indexed, corresponds to film strip)
- `M` = frame index within that animation (0-indexed)

### PNG Metadata

Each extracted frame PNG embeds metadata in its text chunks:

| Key | Value |
|---|---|
| `FrameName` | `animation-{N}-frame-{M}` |
| `AnimationIndex` | Animation index (0-indexed) |
| `FrameIndex` | Frame index (0-indexed) |
| `FrameCount` | Total number of frames |
| `DelayMs` | Frame delay in milliseconds |
| `ExtractScale` | Scale factor applied |
| `AIModel` | AI model used (if `--animation-language-model` was set) |

Read metadata with PIL:

```python
from PIL import Image
img = Image.open("animation-0-frame-0.png")
print(img.info["AIModel"])      # anthropic:claude-sonnet-4-5
print(img.info["ExtractScale"]) # 8
```

## Architecture

```
glitchygames/api/
  __init__.py              # Package exports, usage docstring
  main.py                  # FastAPI app factory, lifespan, uvicorn entry point
  client.py                # CLI client, file saving, ASCII preview
  dependencies.py          # @lru_cache dependency injection
  models/
    __init__.py            # Re-exports all models
    sprite_models.py       # Pydantic request/response models
  routes/
    __init__.py            # Re-exports routers
    health.py              # GET / and GET /health
    sprites.py             # POST /sprites/generate, /refine, /extract-frames

glitchygames/services/
  __init__.py              # Re-exports all services and exceptions
  config.py                # ServiceConfig (env vars, defaults)
  exceptions.py            # SpriteServiceError, AIProviderError,
                           #   ValidationError, RenderingError
  renderer_service.py      # RendererService (pygame headless rendering)
  sprite_generation_service.py  # SpriteGenerationService (aisuite AI calls)
```

### Request Flow

1. Client sends HTTP request to a route endpoint
2. Route creates service instances via `_get_services()`
3. `SpriteGenerationService` calls the AI provider via aisuite to generate TOML
4. `RendererService` parses the TOML and renders it to PNG using pygame (headless)
5. Route returns the response with TOML, PNG, or both
6. Client saves files locally and displays ASCII preview

### Key Design Decisions

- **Server-side rendering**: PNG rendering happens on the server using pygame in headless mode, not on the client. This keeps the client lightweight.
- **Auto-render animation frames**: When `frame_count > 1`, all frames are automatically rendered. No separate flag needed.
- **Client-side file organization**: The client handles directory creation, de-duplication (numbered suffixes), APNG assembly, and frame extraction with upscaling. The server just returns data.
- **Nearest-neighbor upscaling**: Extracted frames are upscaled with nearest-neighbor interpolation to keep pixel art crisp. Default scale is 8x.

## Running Tests

```bash
# All API and service tests
uv run python -m pytest tests/api/ tests/services/ -v --no-cov

# Just API route tests
uv run python -m pytest tests/api/ -v --no-cov

# Just service tests
uv run python -m pytest tests/services/ -v --no-cov
```
