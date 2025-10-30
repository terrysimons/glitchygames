# GlitchyGames Engine

## Development

It's recommended to use pyenv or a venv for development.

To set up a local development environment:

### Linux/macOS Virtual Environment

```
python3 -m venv venv
source venv/scripts/activate
```

### Windows Virtual Environment

```
python3 -m venv venv
venv/Scripts/activate
```

### Install Development Package

Once you have an environment created, link the local source tree with pip.

```
pip install -e .
```

## High-resolution draw-loop timers

The engine supports two pacing backends for the render loop:

- `pygame` (default): uses `pygame.time.delay`/`get_ticks`.
- `fast`: uses `time.perf_counter_ns()` with a sleep+spin hybrid for tighter pacing.

CLI options (inherited by all games):

- `--timer-backend=pygame|fast`
  - Selects the pacing backend (default: `pygame`).
- `--sleep-granularity-ns=<int>`
  - Minimum sleep granularity in nanoseconds for the `fast` backend.
  - Default: `1000000` (1 ms). Set to `0` to uncap (spin-only last mile).
- `--windows-timer-1ms`
  - On Windows, request 1 ms system timer resolution via WinMM while running (power impact; off by default).
- `--log-timer-jitter`
  - Periodically logs jitter statistics (p50/p95/p99/max) for the last frames.

Examples:

```
# Default behavior (pygame backend)
python -m glitchygames.tools.bitmappy --timer-backend=pygame

# High-precision pacing with 1 ms granularity
python -m glitchygames.tools.bitmappy --timer-backend=fast --sleep-granularity-ns=1000000

# Fully uncap (no pacing) – combine with target fps 0
python -m glitchygames.tools.bitmappy --target-fps=0

# Windows: enable 1 ms resolution
python -m glitchygames.tools.bitmappy --timer-backend=fast --windows-timer-1ms

# Debug jitter stats
python -m glitchygames.tools.bitmappy --timer-backend=fast --log-timer-jitter
```
