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
- **Status**: Open
- **Priority**: High. The mirror would run a second worker and ask the service on the live game's
  behalf.
- **Root Cause**: `AIManager.setup` (`src/apps/bitmappy/src/bitmappy/ai_manager.py:168`) tests only
  `AI_FEATURES_ENABLED`, which is `sys.platform != 'emscripten'`
  (`src/apps/bitmappy/src/bitmappy/constants.py:70`); it is called from `BitmapEditorScene.setup`
  (`src/apps/bitmappy/src/bitmappy/editor.py:867`) and the process starts at
  `src/apps/bitmappy/src/bitmappy/ai_manager.py:188`. The worker calls the service through
  `src/glitchygames/ai/local_service.py`, which no door covers.
- **Test gap**: The AI-link guard (`tests/test_ai_service_isolation_guard.py`) covers the engine's
  link, not a member's own worker; `tests/child_process_guard.py` does not see `multiprocessing`
  children.
- **Solution**: Not chosen. Options, all unproven:
  - Being fixed on `feature/lucid-circuit-switch`: Bitmappy follows Lucid Circuit's switch, and
    stays off in headless runs and replays.
  - Beyond that: an AI-answers door, so a recorded generation replays from the recording.
- **Known limits**: The switch's branch does not record the answers, so a replay of a generated
  sprite still cannot match. That a replayed request asks the service was read, not run.
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
