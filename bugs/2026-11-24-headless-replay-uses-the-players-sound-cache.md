# A Headless Replay Uses the Player's Sound Cache, and Waits on Its Locks

- **Description**: A headless replay reads, compiles into, locks and sweeps the player's on-disk
  sound cache. A sound another process holds the write lock of costs up to 5 s, on the main thread,
  and is then compiled without being written. Only what a machine's disk holds changes: the samples
  are the same, so no replay diverges.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - `uv run mr-muncher --headless --replay-trace
    src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz` with an empty cache root: matched
    2072 frames, `main()` in 1.0 s; 11 `.wav` and 11 `.lock` files written to
    `mr_muncher/sounds/1/`.
  - An empty folder of another render version (`mr_muncher/sounds/0/`), planted before a second
    replay, was gone after it.
  - The same replay with the 11 `.wav` files removed and the 11 locks held by the parent process:
    matched, `main()` in 56.2 s (11 waits of 5 s). Staged: one process never holds every lock in
    play.
- **Status**: Open
- **Priority**: High. A mirror beside the live game shares this cache, so either can stall the other
  (the stall is shown on a replay; the live game waiting on a mirror is inferred from the same
  code), and a replay changes the player's files.
- **Root Cause**: `sound_cache` is a replay-local option with default `disk`
  (`src/glitchygames/replay/driver.py:407`, `src/glitchygames/audio/engine.py:158`), so
  `_disk_layer` (`src/glitchygames/audio/engine.py:113`, called at 381) makes the layer, sweeping
  older versions at 134, with no test of the run's mode. A miss takes `write_lock`
  (`src/glitchygames/audio/library.py:1193`), whose `FileLock` waits `WRITE_LOCK_TIMEOUT_SECONDS` =
  5.0 (`src/glitchygames/audio/disk_cache.py:138`, 268-270). `prune` at
  `src/glitchygames/audio/library.py:888`.
- **Test gap**: The harness sets an empty cache root, so no test replays with the disk layer on; the
  disk cache's tests check the lock itself, not that a replay waits on it or whether a replay may
  touch the folder.
- **Solution**: Not chosen. Options, all unproven:
  - A replay uses `none` or `ram` unless the cache is asked for.
  - A read-only layer in a replay: hits are read, nothing is locked, written or swept.
  - Never wait on the main thread: try the lock once and compile unwritten.
- **Known limits**: Measured on macOS only. Sweep and `prune` raced by two processes was read, not
  run. `_disk_layer` sweeps only older render versions.
- **Sweep**: Covered: the engine's disk layer, its sweep, its lock and its prune. The saves, by
  contrast, go to memory in a replay. Not covered: the `sound-cache-*` and `listening-*` tools,
  which are meant to touch the folder.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/audio/engine.py`, `src/glitchygames/audio/library.py`,
  `src/glitchygames/audio/disk_cache.py`, `src/glitchygames/replay/driver.py`
