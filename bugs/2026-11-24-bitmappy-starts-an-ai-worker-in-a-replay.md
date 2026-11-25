# Bitmappy Starts a Real AI Worker in a Headless Replay and Whatever the AI Switch Says

- **Description**: Bitmappy's `setup()` starts a worker process for its AI features in every mode:
  live, `--headless`, replay and with `--no-ai`. In a replay a recorded request would ask the real
  service (inferred); its answers are not recorded, so the replay of a generated sprite can't match.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - `bitmappy --headless --no-ai --replay-trace
    src/apps/bitmappy/src/bitmappy/demos/drawing.jsonl.gz`, with a start of
    `multiprocessing.Process` logged: a real child was started and alive (matched 900 frames). The
    child then logged `LocalAIServiceNotInstalledError`, as the install root pointed at an empty
    folder.
  - The same without `--no-ai`: the same child.
- **Status**: Fixed on `feature/lucid-circuit-switch` (2026-11-24), but for the answers (Known
  limits)
- **Priority**: High. The mirror would run a second worker and ask the service on the live game's
  behalf.
- **Root Cause**: `AIManager.setup` (`src/apps/bitmappy/src/bitmappy/ai_manager.py:168`) tested only
  `AI_FEATURES_ENABLED`, which was `sys.platform != 'emscripten'`
  (`src/apps/bitmappy/src/bitmappy/constants.py:70`; removed by the fix); it is called from `BitmapEditorScene.setup`
  (`src/apps/bitmappy/src/bitmappy/editor.py:867`) and the process starts at
  `src/apps/bitmappy/src/bitmappy/ai_manager.py:188`. The worker calls the service through
  `src/glitchygames/ai/local_service.py`, which no door covers.
- **Test gap**: The AI-link guard (`tests/test_ai_service_isolation_guard.py`) covers the engine's
  link, not a member's own worker; `tests/child_process_guard.py` does not see `multiprocessing`
  children.
- **Solution**: Bitmappy follows Lucid Circuit's flag, and its AI is off with `--headless`, in a
  replay (in-game playback and a tile's included) and with no engine to ask: `ai_off_reason`
  (`src/apps/bitmappy/src/bitmappy/ai_manager.py`), through the engine link's own gate
  (`reason_lucid_circuit_is_off`, `src/glitchygames/ai_link.py`). It is asked at `setup()`, which
  then starts no process, queue or thread, and at each request, which shows the reason.
- **Tests**: `src/apps/bitmappy/tests/test_bitmappy_ai_manager.py`: `TestRealWorker` (real
  processes, the reproduction above included) and `TestLucidCircuit`, which failed before the fix.
- **Known limits**, all open:
  - The answers are not recorded, so a replay of a generated sprite still cannot match. An
    AI-answers door would let a recorded generation replay from the recording (not chosen).
  - A replayed request shows why the AI is off where the recorded run showed its progress. A
    replay never compares that text, but the pixels differ.
  - The scripted recorder (`src/glitchygames/replay/tools/golden_traces.py`, `_start_game`) runs
    without a window but is not `--headless`: recording Bitmappy's demo still starts a worker. Its
    script points the service nowhere.
- **Sweep**: Covered: every `multiprocessing` start in `src/` (one, above). The engine's AI link is
  not created in a replay (`src/glitchygames/engine/game_engine.py`, `self.replay_sources is None`)
  or under `--headless`. Not covered: `VoiceAssistant`'s own calls
  (bugs/2026-11-24-headless-live-run-opens-controller-audio.md).
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/apps/bitmappy/src/bitmappy/ai_manager.py`,
  `src/apps/bitmappy/src/bitmappy/editor.py`, `src/apps/bitmappy/src/bitmappy/constants.py`
