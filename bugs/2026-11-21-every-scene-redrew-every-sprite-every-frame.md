# Every Scene Redrew Every Sprite Every Frame

- **Description**: `Scene.update` ends with `if self.dirty: for sprite in self.all_sprites: sprite.dirty = 1 if not sprite.dirty else sprite.dirty`. `Scene.dirty` is set when a scene is made and by `SceneManager._force_scene_redraw`, and nothing cleared it, so every scene marked every sprite dirty on every frame and `LayeredDirty` redrew them all (from da409711, "Updates to dirty handling", 2021). The overnight profile showed dirty equal to sprites in every game (Brave Adventurer 103 of 103, Zombies 66 of 66, Clockwork Keep 21 of 21, Mr. Muncher 267 of 267); 506,880 of Mr. Muncher's dirty marks in its golden came from that line, against 472 from its own blink.
- **Status**: Fixed (2026-11-21, on `fix/static-sprites-full-screen-update`)
- **Priority**: Medium (drawing cost in every game; it also hid sprites changed without a dirty mark)
- **Reporter**: dev session 53 (Mr. Muncher's dirty-sprite triage); verified and fixed by Claude (dev session c3)
- **Root cause**: the scene's one-time redraw request was never spent.
- **Test gap**: no check compared a frame drawn by dirty rects with a full repaint, and the goldens compare recorded sprite state, not pixels; with every sprite redrawn every frame, a sprite changed without a mark could not show anyway.
- **Solution**: `Scene.update` clears `Scene.dirty` after marking. `glitchygames.testing.full_repaint` compares every rendered frame with its background plus every visible sprite drawn again, and `tests/replay/test_frames_equal_a_full_repaint.py` runs it over every golden and bundled demo (named exclusions for what scenes draw outside sprites).
- **Hidden by it, found by the sweep and fixed with it**:
  - Bitmappy's `AnimatedCanvasSprite.update` rebuilt its picture and then cleared its own dirty flag, so the group never drew it: 846 of the 900 frames of Bitmappy's demo stale on the canvas. It now leaves the mark for the group.
  - `SceneManager._capture_outgoing_scene` and `_capture_arriving_scene` hide the player with `dirty = 0` (so `Scene.update` skips its pose) and relied on the scene-wide marking to erase its old area; they now mark it after the update, before the render.
  - With the flag spent, an unchanged frame's rect list is empty, and `_update_display` turned an empty list into a whole-screen update; a list now presents exactly its rects, None the whole screen.
- **Measured** (dirty sprites at draw per frame, every golden and demo, before and after): Bitmappy 35 to 14, Clockwork Keep 19 to 7, the joystick demo 42 to 26, Zombies' neighborhood 59 to 42; Mr. Muncher 255 and Brave Adventurer about 91 unchanged (their own sprites' marks: plans/future-work.md, "Sprites that still redraw every frame"). Wall-clock time not measured (a loaded machine).
- **Tests**: `tests/scenes/test_scene_rendering.py` `TestASceneRedrawsEverythingOnce` (two failed before the fix), `tests/testing/test_full_repaint.py`, the sweep (Bitmappy failed it before the canvas fix), `src/apps/bitmappy/tests/test_bitmappy_animated_canvas_sprite.py` `test_update_leaves_the_new_picture_marked_for_the_group`. `glitchygames verify` 19 of 19 exact; the driver comparison of the touched tests, 740 tests, no difference.
- **Siblings**: the sweep is the class check (a sprite changed without a mark, anywhere a golden or demo reaches). Mr. Muncher's game-side marks are dev session 53's stacked branch.
- **Date Reported**: 2026-11-21
- **Files**: `src/glitchygames/scenes/scene.py`, `src/glitchygames/testing/full_repaint.py`, `src/apps/bitmappy/src/bitmappy/animated_canvas.py`
