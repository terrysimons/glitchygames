# Engine World Space — Design

- **Date:** 2026-10-18
- **Branch:** `feature/engine-world-space`
- **Status:** Design approved in conversation; spec awaiting review
- **Master plan:** `plans/engine-audit.md` items #6 (engine world space, absorbing pixel snapping
  and camera follow) and #15 (one end-of-frame call)

## Goal

The engine owns world-to-screen. Sprites declare whether they live in world or screen space, and
once per frame — after game logic — the engine aims the camera and positions every world sprite
from it, with engine-wide pixel snapping and culling. The frame loop ends in one call that paces and
records a single, consistent frame time.

**Success criteria**

- No game contains a camera loop, an `apply_camera` method, or per-sprite camera culling.
- The one-frame pose/wall lag in Brave Adventurer and Clockwork Keep is gone.
- Collision rects and the debug overlay agree exactly with what is drawn.
- Recorded frame times sum exactly to wall-clock time; game logic, FPS statistics and the debug
  overlay all see the same frame time.
- Every game plays as before (golden traces, below).

## Decisions (made in conversation)

| Question | Decision |
|---|---|
| Scope | Engine plus all four games (Brave Adventurer, Papyrus, Clockwork Keep, PaddleSlap) |
| How a sprite declares world space | Class attribute `COORDINATE_SPACE = CoordinateSpace.WORLD` plus a runtime-checkable `WorldPositioned` Protocol (works for `Sprite` and `AnimatedSprite`, which share no base class); `SCREEN` is the default |
| Camera follow | All three modes, with one precedence order: the scene's `camera_target()` hook → the camera's declared follow target → manual (`camera.update` by the game) |
| Pixel snapping | Snap sprite and camera positions separately, one mode per scene (`PIXEL_SNAP_MODE`, default `NEAREST_HALF_UP`), overridable per sprite (`pixel_snap_mode`) |
| Frame order | Logic → events → frame services → camera aim → position world sprites → render → present → `_finish_frame()` |

Already decided in the brief: every scene has a camera (`Scene.camera`, identity by default), and
screen space is the default so UI widgets and Bitmappy are unaffected.

---

## 1. The frame

Today: `dt_tick` (games position sprites here) → events → frame services → render → present →
pacing tail. New order (★ = engine-owned, new):

1. **Scene logic** (`dt_tick`): movement, physics, collision. Games no longer position sprites.
2. **Events.**
3. **Frame services:** screen shake, rumble, live audio (unchanged). They run before positioning so
   sprites are placed with this frame's WORLD shake offset.
4. ★ **Camera aim:** resolve the target (section 2.3), apply the follow axes, and call
   `camera.update(target_x, target_y, dt)` toward it. No target → the camera is left alone.
5. ★ **Position world sprites** (section 2.4).
6. **Render:** `Scene.update()`, then draw.
7. **Present** (debug overlay and SCREEN shake, unchanged).
8. ★ **`_finish_frame()`** (section 3).

Positioning runs only for the active scene, inside the normal frame, so transition captures and the
pause screenshot contain correctly positioned sprites. The transition branch of the loop also ends
in `_finish_frame()`.

**The pose rule (fixes the one-frame lag).** A sprite's image and hitbox for this frame must be
final before collision runs. Brave Adventurer and Clockwork Keep draw the player's pose in
`update()` (render phase, after collision), so collision used the previous frame's pose. Their
migration moves pose drawing into `dt_tick`, after the state is decided and before collision.
Papyrus already does this. The engine documents the rule; per-game tests pin it.

## 2. Components and interfaces

New module `glitchygames/world.py`, plus additions to `Camera2D` and `Scene`.

### 2.1 Declaring world space

- `CoordinateSpace(Enum)`: `SCREEN`, `WORLD`.
- `WorldPositioned` (runtime-checkable Protocol): `COORDINATE_SPACE: CoordinateSpace`,
  `world_x: float`, `world_y: float`, `rect: pygame.Rect`.
- A sprite is positioned by the engine when it matches the Protocol and its `COORDINATE_SPACE` is
  `WORLD`. Sprites without the attribute are screen-space and are never touched.
- `hidden: bool` (default `False`): a world sprite the game wants hidden sets `hidden = True`. The
  engine owns `visible` for world sprites (culling, 2.4); screen-space sprites keep using `visible`
  as today.

### 2.2 Pixel snapping

- `Scene.PIXEL_SNAP_MODE` (class attribute, like `TARGET_FPS`), default
  `PixelSnapMode.NEAREST_HALF_UP` (`glitchygames/pixel_snap.py`). A sprite may override with its
  own `pixel_snap_mode` (the ball does).
- Screen position = `snap(world) − snap(camera) − shake offset`, each snapped with the sprite's
  mode. Snapping the camera separately makes every sprite move by the same whole pixel when the
  camera glides by fractions, so sprites never shimmer against each other or the background.
- Parallax layers use the same snapped camera position.
- Collision (`glitchygames/collision/detection.py` `snapped_world_position`) uses the same mode
  resolution (sprite's mode, else the scene's), replacing its `round()` fallback, so collision rects
  sit exactly where sprites are drawn. Exactly-.5 positions move from round-half-even to
  round-half-up (at most 1 px, only at exact halves).

### 2.3 Camera follow and aim

- `Camera2D.follow(*, target: WorldPositioned | None, axes: FollowAxes = FollowAxes.BOTH)`;
  `FollowAxes(Flag)`: `X`, `Y`, `BOTH`. `follow(target=None)` stops following. Read-only
  `follow_target` and `follow_axes` properties.
- `Scene.camera_target(self) -> tuple[float, float] | None`: overridable hook. The default returns
  the follow target's `(world_x, world_y)`, or `None` without one.
- Precedence each frame: overridden hook → declared follow target (via the default hook) → manual.
  Axes apply to whichever source supplied the point: an axis not followed keeps the camera's
  current target value on that axis (Brave Adventurer follows X only).
- **Double-update guard:** if `camera.update(...)` is called by game code during a frame in which
  the engine will also aim the camera (a target or hook is active), the engine logs a warning once
  per scene, like the WORLD-shake misuse warning.
- Camera bounds, lead offsets, smoothing and `snap_to` are unchanged.

### 2.4 The positioning step

`position_world_sprites(scene)` (in `glitchygames/world.py`, called by the scene manager after camera
aim). For each sprite in `scene.all_sprites` that is world-positioned:

1. Compute the screen position (2.2), adding the sprite's frame-anchor `draw_offset` when it has
   one (Papyrus adds it by hand today).
2. Set `rect.topleft`. Mark the sprite dirty only if its screen position changed.
3. **Cull:** `visible = (rect overlaps the screen inflated by CULL_MARGIN_PIXELS) and not hidden`.
   `CULL_MARGIN_PIXELS` is a named constant (start at 32) so sprites don't pop at the edges.

The step writes only `rect`, `visible` and `dirty`; never world positions, camera state or images.

### 2.5 What changes elsewhere

- Removed from the games: every `apply_camera` method and loop, and every per-sprite
  `camera.is_visible(...)` culling block.
- `BallSprite`'s `world_x`/`world_y` setters stop writing `rect` (the engine is the one writer).
- `Camera2D.apply()` stays as a public helper for one-off conversions (Brave Adventurer's pit-gap
  drawing). `Camera2D.is_visible()` stays.
- The debug overlay needs no change (it reads `rect` plus hitbox offsets); its tests are re-run.

## 3. One end-of-frame call (#15)

Today `self.dt` is written twice per frame: at the top of the loop (time since the previous frame
started; used by logic and the debug overlay) and again inside `_handle_frame_pacing` (this frame's
start to the end of the pacing sleep, excluding the work after it). Two meanings in one variable.

- `_finish_frame(*, frame_start_seconds)` replaces the loop tail (`_handle_frame_pacing`,
  `_track_performance`, the FPS-event check). In order:
  1. **Pace:** timer backend → sleep until the next deadline on the timer's own clock (as today);
     no timer backend → `clock.tick(target_fps)` (as today); `--target-fps 0` never sleeps.
  2. **Bookkeeping:** processing-time tracking, jitter logging, the FPS event.
  3. **Close the frame:** read `time.perf_counter()` once; that instant ends this frame and starts
     the next.
- **One frame time:** `self.dt` is set exactly once per frame, as the start-to-start period ending
  at that reading. It feeds the next frame's logic, is recorded as this frame's FPS sample, and is
  recorded by the debug overlay. The second write inside pacing is removed. Recorded frames sum
  exactly to wall-clock time.
- Deadlines stay on the timer backend's clock; measurement stays on the perf counter; fractional
  targets stay untruncated.

## 4. Migrating the games

**Brave Adventurer and Papyrus.** World-space: player, ground segments, walls, enemies, gold
scarabs (ground segments set `world_y = GROUND_Y` once). Remove `apply_camera`, per-sprite culling
and the follow/apply loop; add `camera.follow(target=player, axes=FollowAxes.X)` in setup. Brave
Adventurer's player draws its pose in `dt_tick` before collision. Papyrus drops its manual
`draw_offset` placement. Deliberately hidden sprites use `hidden`. Pit-gap drawing keeps
`camera.apply()`.

**Clockwork Keep.** World-space: player, platforms, elevators, cogs. `camera.follow(target=player,
axes=FollowAxes.BOTH)` with its existing bounds. The tinker's pose moves into `dt_tick`. Elevators,
floor transitions and the elevator ride are unchanged.

**PaddleSlap.** The ball becomes world-space under the identity camera (screen = world, nothing
visible changes); its setters stop writing `rect`; it keeps its own `pixel_snap_mode`. Paddles and
HUD stay screen-space.

## Testing

- **Golden traces (the key test).** A scripted headless run of each game (fixed inputs, fixed frame
  times, seeded randomness) records every sprite's `rect` and `visible` each frame, on `main` and on
  this branch. Traces must match exactly except three expected, enumerated differences: exact-.5
  positions (half-up vs half-even), frames where the pose fix changes a hitbox one frame earlier,
  and culling at the new margin. Each difference is listed and asserted, not ignored.
- **Positioning unit tests:** snapping with camera and sprite at fractional positions moving
  together; WORLD shake; `draw_offset`; dirty only when moved; culling with the margin; `hidden`;
  screen-space sprites untouched; the step never writes world positions.
- **Follow tests:** hook → target → manual precedence; axes (X only keeps Y); `follow(target=None)`;
  the double-update warning (once).
- **Lag tests, per game:** flush against a wall, turn and jump away — the hitbox never enters the
  wall on any frame.
- **Frame tests:** with a fake clock, recorded frame times sum exactly to elapsed time over N frames;
  logic's `dt` equals the previous frame's recorded sample; pacing still hits a fractional target;
  uncapped never sleeps; the debug overlay's history matches the FPS statistics sample for sample;
  the transition branch is paced and measured the same way.
- **Regression:** the ledge and wall fuzzers, the debug-overlay alignment checks (boxes on sprites
  while scrolling), and the full suite.

## Documentation

- CLAUDE.md: a "World Space" entry (declaring world sprites, `camera.follow`, `camera_target()`,
  `PIXEL_SNAP_MODE`, `hidden`, the pose-before-collision rule) and the `_finish_frame` note in Frame
  Pacing.
- `plans/engine-audit.md`: #6 and #15 marked done with this branch; the one-frame-lag row removed
  from `plans/future-work.md`.

## Out of scope

Tilemaps (level tools sub-plan A builds on this), solid collision (#1), multiplayer cameras beyond
what `camera_target()` allows, and dirty-rect optimisation beyond "dirty only when moved".
