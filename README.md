# GlitchyGames Engine

A Python 3.13 game engine built on Pygame with an event-driven architecture. Includes Bitmappy, a full-featured pixel art editor with animation support.

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/terrysimons/glitchygames.git
cd glitchygames

# Install dependencies (uv manages the virtual environment automatically)
uv sync

# Install with dev extras (for testing/linting)
uv sync --extra dev

# Install with all extras
uv sync --all-extras
```

### Optional Dependency Groups

| Extra | Purpose |
|-------|---------|
| `dev` | Testing, linting, type checking, security scanning |
| `docs` | MkDocs documentation generation |
| `api` | FastAPI sprite server and client |

## Script Entrypoints

The following commands are available after installation:

### `bitmappy`

Full-featured pixel art and sprite editor with animation timeline, multi-controller support, and AI integration.

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

### `glitchygames-server`

FastAPI-based sprite processing server for APNG extraction and sprite manipulation.

```bash
uv run glitchygames-server
```

### `glitchygames-client`

Client for the glitchygames sprite server API.

```bash
uv run glitchygames-client
```

## Development

### Testing

```bash
# Run all tests with coverage (80% minimum required)
uv run pytest

# Run specific test file
uv run pytest tests/test_specific.py

# Run tests matching pattern
uv run pytest -k "test_pattern"

# Run tests with parallel execution
uv run pytest -n auto

# Run performance benchmarks only
uv run pytest --benchmark-only
```

### Linting and Type Checking

```bash
# Format code with ruff
uv run ruff format glitchygames tests scripts noxfile.py

# Check and fix import ordering
uv run ruff check --select I --fix glitchygames tests scripts noxfile.py

# Run full ruff linting
uv run ruff check glitchygames tests scripts noxfile.py

# Type checking with pyright
uv run pyright
```

### Nox Sessions

Automated pipelines for CI and local development:

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

## High-Resolution Draw-Loop Timers

The engine supports two pacing backends for the render loop:

- `pygame` (default): uses `pygame.time.delay`/`get_ticks`.
- `fast`: uses `time.perf_counter_ns()` with a sleep+spin hybrid for tighter pacing.

CLI options (inherited by all games):

- `--timer-backend=pygame|fast` -- Selects the pacing backend (default: `pygame`).
- `--sleep-granularity-ns=<int>` -- Minimum sleep granularity in nanoseconds for the `fast` backend. Default: `1000000` (1 ms). Set to `0` for spin-only last mile.
- `--windows-timer-1ms` -- On Windows, request 1 ms system timer resolution via WinMM while running.
- `--log-timer-jitter` -- Periodically logs jitter statistics (p50/p95/p99/max) for recent frames.
