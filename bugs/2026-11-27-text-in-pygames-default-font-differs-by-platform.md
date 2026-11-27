# Text in pygame's Default Font Was Sized Differently on Windows

- **Description**: Shipped code still drew text in pygame's default font (`pygame.font.Font(None,
  size)`), the font that made PR #328's recordings diverge on Windows. The game-over screen's
  `TextSprite` (`scenes/builtin_scenes/game_over_scene.py`, used by every game's game-over and
  victory screens and Brave Adventurer's title) sizes and centers its rect from the text, so a
  recording holding one replays only on the platform it was made on. Also: Brave Adventurer's
  title cards, Bitmappy's slider tabs and `FontManager`'s fallback when a system font fails.
- **Status**: Fixed (2026-11-27, `fix/default-font-users-use-bundled-vera`).
- **Priority**: Medium. Latent: no golden or bundled demo reaches a game-over screen today, so CI
  stayed green; the first golden that did would have failed on Windows (or on macOS and Linux,
  if recorded on Windows).
- **Root Cause**: SDL_ttf lays pygame's default font (freesansbold) out differently per platform:
  Windows' SDL2_ttf.dll carries its own FreeType and HarfBuzz, and draws `Score: 10` at 28 points
  87 pixels wide where macOS draws 88 (#328; `glitchygames.testing.text_metrics`). The bundled
  Vera fonts lay out the same on all three (#328's CI). #328 moved the HUDs; nothing stopped the
  other users or new ones.
- **Evidence**: `scripts/ai_behaviour/recordings/paddleslap-no-input.jsonl.gz` holds the game-over
  `TextSprite#0` at `[299, 102, 202, 36]`, a width from the default font. The new guard, run on main
  `eb7deb256`, reports exactly the five calls fixed here.
- **Fix**: Every one draws in the bundled Vera Bold (`font_manager.bundled_font`). Sizes are matched
  by line height, as #328 did (default 28 became Vera Bold 16): a default-font size draws at
  0.6875 of itself (pygame-ce), and Vera Bold is taller per point, so 72, 48, 40, 32, 30, 28, 26,
  24 and 16 became 42, 28, 23, 18, 17, 16, 14, 13 and 9. `TextSprite`'s `font_size` is now Vera
  Bold's point size (its callers: the game-over scene, Clockwork Keep's victory, Mr. Muncher's
  game over, Brave Adventurer's title). `FontManager` falls back to the bundled Vera.
- **Re-recorded (rebaselined, inputs unchanged)**: the two AI behaviour recordings, the only
  recordings holding these rects. `paddleslap-no-input`: the five game-over `TextSprite`s from
  frame 70. `brave-adventurer-hazards`: the same, and its four `HudLabel`s, which #328 added and
  did not rebaseline here (the recording diverged at frame 0 on main). No other sprite changed;
  both replay all 2400 frames. Every golden and bundled demo still passes `glitchygames verify`.
- **Test gap**: Nothing named the font a text sprite may use; #328 fixed the instances it saw.
  And nothing replays the AI behaviour recordings (`glitchygames verify` covers goldens and bundled
  demos; their tests use generated snapshots), so #328's change to the Brave HUD broke one
  unnoticed.
- **Invariant**: `tests/test_text_uses_bundled_fonts.py` scans the engine's and every member's
  shipped source and fails on any `Font(None, ...)` or `SysFont(...)` outside its allowlist
  (`FontManager`'s system fonts a player names; the `text_metrics` triage tool), and on an
  allowlist entry no longer needed.
- **Files**: `src/glitchygames/scenes/builtin_scenes/game_over_scene.py`,
  `src/glitchygames/ui/sliders.py`, `src/glitchygames/fonts/font_manager.py`,
  `src/games/brave-adventurer/src/brave_adventurer_modes/title.py`,
  `src/games/clockwork-keep/src/clockwork_keep/game.py`, `src/games/mr-muncher/src/mr_muncher/game.py`,
  `scripts/ai_behaviour/recordings/*.jsonl.gz`, `tests/test_text_uses_bundled_fonts.py`,
  `tests/fonts/test_font_manager.py`, `src/games/clockwork-keep/tests/test_clockwork_keep.py`.
- **Siblings (swept)**: `pygame.freetype` fonts come only from `FontManager` (bundled by default)
  and the shared helpers; tests may use the default font (not scanned, not shipped). Covered: all
  shipped code. Not covered: recordings outside goldens and demos are still replayed by nothing.
