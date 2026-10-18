# Debug Overlay — Design

- **Date:** 2026-10-17
- **Branch:** `feature/debug-overlay`
- **Status:** Implemented on `feature/debug-overlay` (this spec was updated in place to match
  the implementation)
- **Master plan:** `plans/engine-audit.md` (item #12)

## Goal

A toggleable on-screen overlay that shows, for any GlitchyGames game with no game code: collision
hitboxes by layer, physics velocities and ground state, camera bounds and world coordinates, and a
live performance HUD. Games can add their own annotations through an optional hook. It exists to
make position, collision and timing bugs visible (the ball-physics, collision and pacing work in
the previous branches would all have been faster with it) and to support the next roadmap items
(engine world space, solid collision).

## Non-goals

- Editing game state from the overlay (it is strictly read-only).
- Controller bindings for the overlay (keyboard only for now).
- Persisting overlay state between runs.
- Recording or exporting overlay data.

## Decisions (made in conversation)

| Question | Decision |
|---|---|
| Content | All four panels: collision, physics, camera/world, performance |
| Activation | Off by default; `--debug-overlay` starts it on; F3 toggles; F4 cycles panels |
| Discovery | Automatic via typed Protocols, plus an optional `debug_draw(surface, camera)` hook |
| Drawing | Inside `SceneManager._present_frame`, never in screenshots or transition captures |

---

## 1. Structure

New package `glitchygames/debug/`:

- `overlay.py` — `DebugOverlay`: owns `is_visible: bool`, `panel: DebugPanel`, a small font
  (created lazily on first draw), the rolling frame-time history, and the set of disabled hooks.
  - `toggle() -> None`, `cycle_panel() -> None`, `record_frame(*, frame_seconds: float) -> None`,
    `draw(surface, *, scene, screen_offset: tuple[int, int], frame_info: DebugFrameInfo) -> None`.
  - `DebugFrameInfo` (in `panels.py`) carries the per-frame engine readings: target FPS, live voice
    count, rumble levels, SCREEN shake offset, mouse position and the inspected scene's label.
- `DebugPanel(Enum)`: `ALL`, `COLLISION`, `PHYSICS`, `CAMERA`, `PERFORMANCE`; `cycle_panel` advances
  in that order and wraps from `PERFORMANCE` to `ALL`.
- `protocols.py` — runtime-checkable Protocols:
  - `PhysicsState`: `velocity_x: float`, `velocity_y: float`, `world_x: float`, `world_y: float`,
    `on_ground: bool` (matches `glitchygames.physics.body.PhysicsBody`).
  - `HasPhysicsBody`: `physics: PhysicsState`.
  - `DebugDrawable`: `debug_draw(self, surface: pygame.Surface, camera: Camera2D) -> None`.
- `panels.py` — one pure drawing function per panel (`draw_collision_panel`, `draw_physics_panel`,
  `draw_camera_panel`, `draw_performance_panel`), each taking the surface, the data it needs and the
  world-annotation offset; no global state.
- `glitchygames/debug/__init__.py` exports `DebugOverlay`, `DebugPanel`, `DebugDrawable`,
  `DebugFrameInfo`, `HasPhysicsBody` and `PhysicsState`.

### Integration

- `SceneManager` owns one `DebugOverlay` (created inside its `_initialized` guard), visible at start
  when `OPTIONS.get('debug_overlay', False)` (read in the `game_engine` setter, like the shake and
  rumble intensities).
- Each main-loop pass records the frame time (`overlay.record_frame(frame_seconds=self.dt)`) in
  `_update_frame_services`.
- `_present_frame`: when the overlay is visible, it is drawn on the frame about to be presented —
  after any SCREEN shake shift — and the clean frame is restored afterwards (the same copy/restore
  pattern the screen shake uses), so the display surface, `Scene.screenshot` and transition captures
  never contain overlay pixels and the next frame's dirty-rect drawing is not corrupted.
  - World annotations are offset by the SCREEN shake offset so they stay on their sprites; HUD
    elements (legend, mode line, performance panel) are not offset.
  - While visible, presentation uses a full display update (`pygame.display.flip()`), because the
    overlay changes every frame. The performance HUD states that the overlay itself lowers FPS
    slightly.
- When not visible, the cost is one boolean check in `_present_frame` plus `record_frame` (a deque
  append) per frame.

### Keys

- `SceneManager.on_key_down_event` (new explicit method; the class otherwise forwards events to the
  active scene through `__getattr__`) intercepts `K_F3` (toggle) and `K_F4` (cycle panels) on key-down
  only, and only when no sprite in the active scene has keyboard focus (a sprite with `is_active` true,
  the same rule `Scene._handle_focused_sprite_events` uses). Intercepted keys are not forwarded; all
  other key-down events are forwarded to the active scene unchanged.
- Mode line at the top centre while visible: `DEBUG: <Panel> (F3 off, F4 next)`, followed by
  `| paused: <name>` while the overlay inspects a scene other than the active one.
- `Scene.debug_subject` (property, default the scene itself) names the scene the overlay inspects.
  `PauseScene` returns the paused game, so its hitboxes and physics stay visible over the frozen
  screenshot and line up with it.

### Data sources (read-only)

| Source | Panel |
|---|---|
| `scene.collisions` layers and `glitchygames.collision.layers.get_sprite_collision_rect` (exactly what collision tests use) | Collision outlines by layer |
| `scene.all_sprites` | Unlayered sprites (faint outline) |
| objects matching `HasPhysicsBody` among `scene.all_sprites` | Physics arrows, ground marker |
| `scene.camera` | Camera bounds, lead point, shake offsets |
| overlay's own frame history; `scene_manager.live_audio` (only if already created); `scene_manager.rumble` | Performance HUD |

`_get_sprite_collision_rect` was made public as `get_sprite_collision_rect`; nothing imported the
old name, so no alias was kept.

---

## 2. Panels

### Collision (world annotations)
- 1 px hitbox outline per sprite in each collision layer, coloured from a fixed palette in layer
  creation order (`CollisionManager.layer_names()` order), so colours are stable between runs.
- Outlines sit where each sprite is drawn: `sprite.rect` (set from the camera by the game) plus the
  hitbox's offset from the snapped world position (minus `draw_offset` for anchored sprites, whose
  rect already includes it), so the box is never rounded a second time through the camera (which
  put it 1 px off sprites under fractional smooth-follow cameras).
- Legend (bottom-left): layer name, colour swatch, sprite count.
- Sprites in `scene.all_sprites` that are in no collision layer: faint grey outline of the full
  `sprite.rect` (not a trimmed hitbox).
- Overlaps: when two sprites from different layers have overlapping collision rects, both outlines
  are drawn white for that frame (layer pairs are not configured anywhere today, so any cross-layer
  overlap counts).

### Physics (world annotations)
- For each `HasPhysicsBody` sprite: an arrow from the centre of its collision rect to centre +
  velocity × `PHYSICS_ARROW_SECONDS` (0.1 s), length capped at `PHYSICS_ARROW_MAXIMUM_PIXELS` (80), with
  the velocity printed as `(vx, vy)` px/s rounded to integers.
- Ground marker: a 2 px bar under the collision rect, green when `on_ground` is true, red otherwise.

### Camera
- World bounds: each configured bound edge drawn as a dashed line where it falls on screen, via the
  side-effect-free `Camera2D.world_to_screen`. Bounds clamp the camera's top-left, so the left/top
  edges are at `min_x`/`min_y` and the right/bottom edges at `max_x + screen width - 1` /
  `max_y + screen height - 1` (the last world pixel). A read-only `Camera2D.bounds` property returns
  `(min_x, min_y, max_x, max_y)` (each `float | None`) instead of reading private fields.
- Lead point: a crosshair at screen position (`camera.lead_x`, `camera.lead_y`).
- Mouse world position as text at the cursor: `camera.world_x + mouse_x`, `camera.world_y + mouse_y`
  (unshaken), only when the mouse is inside the window.
- Shake: WORLD (`camera.shake_effect.offset`) and SCREEN offsets in px, on separate lines, shown only
  when non-zero.

### Performance HUD (top-right, not offset)
- Current FPS (1 / last frame time), target FPS (`scene_manager.target_fps`, "uncapped" when 0),
  frame time in ms, 1% low over the last `PERFORMANCE_WINDOW_SECONDS` (5 s) of recorded frames
  (mean FPS of the slowest `max(1, ceil(0.01 × n))` frames in the window).
- Rolling frame-time graph of the last `GRAPH_WINDOW_SECONDS` (2 s) on a time axis spanning the
  graph's full width: each frame's width is proportional to its duration, and a column shows the
  slowest frame that covers it, scaled to a fixed height. A horizontal line marks the target frame
  time when a target is set (none when uncapped); bars more than `SLOW_FRAME_TOLERANCE_MILLISECONDS`
  (1 ms) above it are drawn red, so timer jitter (at 60.01 FPS many frames land a hair over the
  target) does not turn on-target frames red. The line itself marks the exact target.
- Live voices playing (only if `live_audio` exists) and rumble levels (low/high) while non-zero.
- The overlay keeps its own `collections.deque` of frame times (sized for the 5 s window at a generous
  maximum rate, e.g. 5000 entries) so the HUD does not depend on the shutdown statistics.
- Footnote: `overlay drawing included`.

### Hook
- After the built-in panels, when the panel is not `PERFORMANCE`: call `debug_draw(surface, camera)`
  on the active scene if it implements `DebugDrawable`, then on each sprite in `scene.all_sprites`
  that does. World annotations by hooks are the hook's responsibility (it receives the camera).
- A hook that raises is caught: the exception is logged once (with traceback) and that object's
  hook is disabled for the rest of the session. Built-in panels do not catch their own errors.

---

## 3. Robustness and invariants

- Missing data skips the panel quietly: no `collisions` attribute or no layers → no collision panel;
  `camera` is always present (default identity camera since spec revision 3 of the screen shake
  work) but bounds may all be `None`; no physics bodies → no arrows.
- The overlay never mutates game state (positions, velocities, camera, sprite dirty flags).
- Text uses the engine's bundled Bitstream Vera Sans (`glitchygames/fonts/bitstream_vera/Vera.ttf`)
  on translucent backing surfaces cached by size; the font is created on the first visible draw so
  headless/test paths that never show the overlay never create fonts.

## Testing

Real surfaces where pixels matter (put those tests outside `tests/scenes`, whose conftest mocks
pygame — e.g. `tests/debug/`); `mocker` for input and timing.

- Toggle/cycle: F3 toggles; F4 cycles in order and wraps; both ignored while a sprite has focus; other
  keys forwarded to the scene unchanged; `--debug-overlay` sets the initial state (flag default off).
- No leaks: after `_present_frame` with the overlay visible, the display surface holds the clean
  frame; `Scene.screenshot` has no overlay pixels; with a SCREEN shake active, a world annotation is
  drawn at the shifted sprite position while the HUD is not shifted.
- Collision: hitbox outline pixels in the layer's palette colour; overlapping cross-layer sprites
  white; unlayered sprite grey; legend lists layers with counts.
- Physics: arrow end point for a known velocity; the 80 px cap; ground marker green vs red.
- Camera: bound lines drawn only when on screen; mouse world position text; shake text only when
  non-zero; `Camera2D.bounds` property.
- Performance: graph bars red only above the target frame time plus the 1 ms tolerance (at 60 FPS
  17 ms and exactly target + 1 ms are not red, 18 ms is); 1% low over the window, including the window
  boundary (a frame just older than 5 s is excluded); "uncapped" when target is 0.
- Hook: called on scene and sprites; a raising hook logs once and is not called again; not called in
  `PERFORMANCE` mode.
- Read-only: drawing a frame leaves sprite rects, physics state and camera unchanged.
- Off cost: with the overlay hidden, `_present_frame` makes no overlay draw call.

## Documentation

- CLAUDE.md: a "Debug Overlay" entry in the architecture overview (flag, F3/F4, panels, hook).
- `plans/engine-audit.md`: item #12 marked done with the branch name when it lands.
