# A Bitmappy Tile Stops Every AI Worker in the Process

- **Description**: Building a Bitmappy inner game (an Arcade tile) inside a live Bitmappy stops the
  live editor's AI worker. The editor plays on, and every later request shows `AI processing not
  available`: nothing starts a worker again in that run.
- **Reproduction**: Reproduced 2026-11-24 at `433fe83a` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in one child process on the dummy drivers, with `HOME` in a scratch folder, no
  sound cache and the AI install root at nowhere. `multiprocessing.Process` and `Queue` were
  stand-ins that record their calls, so no real worker ran.
  - The outer game: a live `BitmapEditorScene` in `golden_game(..., extra_arguments=
    ['--lucid-circuit'])`, whose worker was running and registered. Then
    `reserve_inner_game_channels(games=1)` and `InnerGame.replay(command='bitmappy',
    path=<the bundled demo drawing.jsonl.gz>, name='tile', size=(800, 480))`, not stepped.
  - The tile was `RUNNING` at 0 frames and had started no worker. The outer worker had been sent its
    shutdown message (`None`) and joined, both queues were dropped, and its manager was no longer
    registered. A request in the outer editor then showed `AI processing not available`.
- **Status**: Open
- **Priority**: Low today: nothing in the repository runs a Bitmappy tile inside a live Bitmappy. It
  matters once a host holds a live Bitmappy beside a tile of it (the Arcade's live games).
- **Root Cause**: `InnerGame._build` (`src/glitchygames/inner_game.py`) calls the command's own
  `main()`, and an inner `engine.start()` returns as soon as the game is built, so Bitmappy's
  `main()` (`src/apps/bitmappy/src/bitmappy/editor.py`) runs its `finally` at the tile's build, not
  at its end. That calls `shut_down_running_ai_workers`
  (`src/apps/bitmappy/src/bitmappy/ai_manager.py`), which cleans up every manager in
  `_RUNNING_AI_MANAGERS`: one set for the whole process, whichever context started the worker.
- **Test gap**: `test_an_inner_game_is_what_its_own_engine_is`
  (`src/apps/bitmappy/tests/test_bitmappy_ai_manager.py`) builds a tile inside a live run, but the
  live run has no worker. The set is allowed as shared state (`tests/test_process_state_guard.py`,
  audit row S15), and no test runs the shutdown with a worker of another context.
- **Solution**: Not chosen. Unproven: the registry as a `ContextSlot`, so a context's `main()` shuts
  down only its own workers. Row S15 of plans/2026-10-25-engine-context.md kept it shared as
  shutdown bookkeeping across the process, so a fix must still reach a worker whose own context's
  `main()` never ends.
- **Known limits**: Reproduced with stand-in workers only. A real worker takes the same calls
  (message, join, then terminate if still alive).
- **Sweep**: Covered: the other callers of `shut_down_running_ai_workers` in `src/` (none). Not
  covered: the other commands' `main()` functions, for code after `engine.start()` that acts on the
  whole process.
- **Related**: [Bitmappy starts a real AI
  worker](2026-11-24-bitmappy-starts-an-ai-worker-in-a-replay.md), whose fix keeps a tile from
  starting a worker of its own.
- **Reporter**: Lucid Circuit's switch, Task 3
- **Date Reported**: 2026-11-24
- **Files**: `src/apps/bitmappy/src/bitmappy/ai_manager.py`,
  `src/apps/bitmappy/src/bitmappy/editor.py`, `src/glitchygames/inner_game.py`
