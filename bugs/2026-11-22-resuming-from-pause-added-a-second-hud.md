# Resuming From a Pause Added a Second Set of HUD Labels

- **Description**: On `refactor/engine-hud-labels`, before its first commit, Brave Adventurer and Clockwork Keep added their HUD's `HudLabel` sprites in `setup()` each time it ran. Resuming from a pause runs `setup()` again, so each resume added another full set of labels on top of the first.
- **Status**: Fixed (2026-11-22, `8071621f`, branch `refactor/engine-hud-labels`); it never reached `main`
- **Priority**: Medium (a HUD drawn twice after a pause, and more sprites with every pause)
- **Found by**: the trial re-record of the six HUD recordings, checked by `scripts/check_rebaselined_recordings.py`. Brave's golden-classic failed at frame 372, its first frame after the pause scene: `HudLabel#4` to `HudLabel#7` were present, and the plan allowed only `#0` to `#3`.
- **Root Cause**: `setup()` is not run once per scene: the scene manager runs it again when a paused scene becomes active. The HUD as blits kept no state, so running `setup()` twice was harmless; as sprites it was not.
- **Fix**: each scene adds its labels only when it has none (`if self.score_label is None`).
- **Test gap**: the HUD tests ran `setup()` once.
- **Regression tests**: `TestHud::test_setup_again_on_resuming_from_pause_keeps_one_set_of_labels` in `src/games/brave-adventurer/tests/core/test_brave_adventurer_both_editions.py` (both editions) and `src/games/clockwork-keep/tests/test_clockwork_keep.py`. All three cases failed before the fix.
- **Class**: a pausable scene's `setup()` run again must not add sprites it already added.
- **Sweep** (2026-11-25, by reading: every scene in `src/` that calls `Scene.pause()` and its `setup()`):
  - Guarded: Brave Adventurer, Clockwork Keep (this fix), Zombies' `NeighborhoodScene` (`_yard_drawn`), Mr. Muncher (shows its message only in `Phase.READY`).
  - Adds no sprites in `setup()`: Zombies' `RosterScene`; PaddleSlap has no `setup()` of its own.
  - Not covered: scenes that never call `pause()`, and no test holds the property for every pausable scene.
- **Reporter**: Claude
- **Date Reported**: 2026-11-22
- **Files**: `src/games/brave-adventurer/src/brave_adventurer_core/scene.py`, `src/games/clockwork-keep/src/clockwork_keep/game.py`
