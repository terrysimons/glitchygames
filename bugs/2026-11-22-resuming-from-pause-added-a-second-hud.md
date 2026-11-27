# Resuming From a Pause Added a Second Set of HUD Labels

- **Description**: On `refactor/engine-hud-labels`, before its first commit, Brave Adventurer and Clockwork Keep added their HUD's `HudLabel` sprites in `setup()` each time it ran. Resuming from a pause runs `setup()` again, so each resume added another full set of labels on top of the first.
- **Status**: Fixed (2026-11-22, `8071621f`, branch `refactor/engine-hud-labels`); it never reached `main`
- **Priority**: Medium (a HUD drawn twice after a pause, and more sprites with every pause)
- **Found by**: the trial re-record of the six HUD recordings, checked by `scripts/check_rebaselined_recordings.py`. Brave's golden-classic failed at frame 372, its first frame after the pause scene: `HudLabel#4` to `HudLabel#7` were present, and the plan allowed only `#0` to `#3`.
- **Root Cause**: `setup()` is not run once per scene: the scene manager runs it again when a paused scene becomes active. The HUD as blits kept no state, so running `setup()` twice was harmless; as sprites it was not.
- **Fix**: each scene adds its labels only when it has none (`if self.score_label is None`).
- **Test gap**: the HUD tests ran `setup()` once.
- **Root fix** (2026-11-25, branch `feature/scene-pause-unpause`): a paused scene stays set up. Pausing runs no `cleanup()` and unpausing no `setup()`, so the guards above are gone.
- **Regression tests**: `TestHud::test_pausing_and_unpausing_keeps_one_set_of_labels` in `src/games/brave-adventurer/tests/core/test_brave_adventurer_both_editions.py` (both editions) and `src/games/clockwork-keep/tests/test_clockwork_keep.py`, through a real pause. They replace the tests of the guards, and fail when the pause screen no longer pauses.
- **Class**: a scene's `setup()` and `cleanup()` run on a pause. `TestAPausedSceneStaysSetUp` in `tests/scenes/builtin_scenes/test_pause_screen.py` holds it for every scene paused behind a `PauseScene`.
- **Not covered**: Bitmappy's dialogs, which switch away from the editor and back without pausing, so each still cleans it up and sets it up again.
- **Reporter**: Claude
- **Date Reported**: 2026-11-22
- **Files**: `src/games/brave-adventurer/src/brave_adventurer_core/scene.py`, `src/games/clockwork-keep/src/clockwork_keep/game.py`
