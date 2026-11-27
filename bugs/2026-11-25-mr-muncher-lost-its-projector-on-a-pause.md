# Mr. Muncher Lost Its Projector Sound on a Pause

- **Description**: Pausing during play and unpausing left Mr. Muncher without its projector sound until play next started.
- **Status**: Fixed (2026-11-25, `448015d18`, branch `feature/scene-pause-unpause`)
- **Priority**: Low (a background sound missing)
- **Reproduction**: `TestStartingALevel::test_the_projector_is_kept_through_a_pause` in `src/games/mr-muncher/tests/test_mr_muncher.py` pauses with P and unpauses with Space through the frame loop. Before the fix, `projector` was None afterwards.
- **Root Cause**: pausing ran the scene's `cleanup()`, which releases the projector, and the `setup()` on resuming restarts it in no phase; only `_start_playing` does.
- **Fix**: a paused scene is not cleaned up (`plans/2026-11-25-scene-pause-unpause.md`). The live voices already pause for the scene behind a pause screen.
- **Test gap**: no test played Mr. Muncher through a pause; the tests called `setup()` and `cleanup()` directly.
- **Reporter**: Claude
- **Date Reported**: 2026-11-25
- **Files**: `src/glitchygames/scenes/scene.py`, `src/glitchygames/scenes/builtin_scenes/pause_scene.py`
