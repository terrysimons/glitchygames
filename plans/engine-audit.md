# Engine Audit — Master Plan

- **Date:** 2026-10-17
- **Branch audited:** `game/brave-adventurer`
- **Why this file exists:** the original engine-audit master plan and its sub-plans lived in
  `~/.claude/plans/` and were lost to Claude Code's periodic cleanup (last run 2026-10-15). This
  audit was redone from the code and is kept in the repo so it cannot be cleaned up again.
- **Method:** inventory of every engine package, plus what the four games (Brave Adventurer,
  Brave Adventurer Papyrus, Clockwork Keep, PaddleSlap) each build for themselves. Code that
  several games duplicate marks a missing engine feature.

Each item gets its own design spec and implementation plan in `plans/` when it is picked up; those
documents link back here, and this list links to them.

## Already in the engine

Scenes (pause and game-over built-ins, `transition_to`), transitions (fade, crossfade, slide,
wipe, elevator, plus `on_update`/cues), `Camera2D` (follow, bounds, `snap_to`, visibility,
parallax), physics (`PhysicsBody`, gravity/acceleration/friction, bounds and ground constraints),
`CollisionManager` (layers, hitboxes), `AnimationStateMachine` with an expression language,
`ActionMap` (keyboard/controller bindings, `to_dict`/`from_dict`), `SaveManager` (slots,
JSON/TOML, versions), controller audio and rumble, TTS, voice assistant, frame timing.
Unused by games: tweens and easing (`effects/`) outside transitions.

## Items, ranked by value to game developers

| # | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Solid/terrain collision resolution (ground, walls, one-way platforms) | Open | 7 `_resolve_*_collision` methods across the games; `CollisionManager` detects but does not resolve. `_player_support_span` and `_entered_wall_from_left` are duplicated between Brave Adventurer and Papyrus (candidates for the solid-collision design) |
| 2 | Expressions phase 2: `and` / `or` / `not` / parentheses | Open | Promised in `animation/expressions.py:17`; `_FallingCondition` copied into all three platformer players |
| 3 | Screen shake | **Done** (this branch) | `plans/2026-10-17-screen-shake-and-synth.md` |
| 4 | High-score table | Open | `_save_high_score` copied into 4 games |
| 5 | Sound effect synthesis | **Done** (this branch) | Same spec: toolkit, recipes, live voices |
| 6 | Engine world space (absorbs pixel snapping and camera follow) | Open — next design | See below |
| 7 | Balls on `CollisionManager` | Partly done (feature/debug-overlay): ball–paddle detection moved onto CollisionManager (ball–ball already used it), with an exact circle check in `BallSprite.handle_paddle_collision`; generic resolution waits for #1 | Commit `fa5750f`: "except balls which we'll do later" |
| 8 | Sprite transparency/scaling helpers; masks instead of alpha trimming | Open (visible-pixel trimming is now the default hitbox, feature/debug-overlay; masks still open) | Papyrus `sprite_utils.py` |
| 9 | Particles | Open | None exist |
| 10 | Timers and cooldowns on game time | Open | Ad-hoc cooldown dicts in `ball.py` and PaddleSlap |
| 11 | Level/room data format (and tilemaps) | Open | Each game defines its own `ScreenData`/`FloorData`/`LevelManager` |
| 12 | Debug overlay (hitboxes, velocities, FPS) | **Done** (feature/debug-overlay) | `plans/2026-10-17-debug-overlay.md` |
| 13 | Controller rebinding UI and settings persistence | Open | `ActionMap.to_dict`/`from_dict` exist; nothing saves or edits bindings |
| 14 | Multiplayer input: player slots and targeted rumble | Open | All rumble is broadcast to every device; no engine player-to-device mapping (only Bitmappy's own controller manager). See below |
| 15 | Frame loop: one _finish_frame() that paces with the timer backend and records that frame's measured time | Open | BUGS.md #25: pacing and FPS tracking measured frames differently; the deleted _tick_clock() was an early form of this |

Nice to have, not needed by current games: sprite-sheet import, localization, pathfinding.

## Recommended order (one branch each)

1. **Engine world space** (#6) — touches the coordinate system every later item builds on.
2. **Expressions phase 2** (#2) — small; removes three copies of `_FallingCondition`.
3. **Solid collision** (#1) together with **balls on CollisionManager** (#7) — one collision design.
4. Remaining items as small independent branches.

Process lesson from the screen-shake branch: run full-project basedpyright and ty at least once
mid-branch, not only per touched file. A base-class type change (`Scene.camera`) broke two games
that no per-task check looked at.

---

## #6 Engine world space — design brief (to be brainstormed into a full spec)

**Goal:** sprites live in world coordinates and the engine turns them into screen pixels, so
games stop writing per-sprite camera loops and every engine feature that needs world-to-screen
(shake, snapping, culling, follow) has one place to hook in.

**Origin:** the screen-shake final review (spec revision 3). With a default camera on every
scene, a WORLD shake on a scene whose sprites never go through `camera.apply()` silently does
nothing; it now warns. Positioning sprites automatically fixes that properly.

**Decided so far (2026-10-17, with the user):**
- Every scene already has a camera (`Scene.camera: Camera2D`, an identity camera by default).
- Sprites will declare a coordinate space: world-space (moves with the camera) or screen-space
  (HUD/UI). Screen-space is the default so existing UI widgets and Bitmappy are unaffected.
- Each frame, before rendering, the scene positions every world-space sprite from its camera,
  replacing the games' `apply_camera_to_sprites()` loops (Clockwork Keep) and the camera loops in
  both Brave Adventurer games.

**Absorbs:**
- **Engine pixel snapping** (formerly audit #6): `PixelSnapMode` and `world_x`/`world_y`
  properties exist only on `BallSprite`; world-to-screen conversion is where snapping belongs.
  Open question from earlier: snap the camera first with the same mode; per-genre default (FLOOR
  for retro/top-down, NEAREST_HALF_UP for smooth).
- **Camera follow**: games follow on different axes (Brave Adventurer horizontal only,
  Clockwork Keep both) and must update the camera after physics/collision, not in the base
  `dt_tick` (which games call first, so the camera would lag a frame). Needs a target hook that
  runs after game logic.

**Open design questions:**
- How a sprite declares its space (base-class attribute, mixin, or group membership) and how
  existing `world_x` attributes and the ball's properties migrate.
- Where in the frame positions are computed relative to `dt_tick`, `Scene.update()`, dirty-rect
  rendering, and transition screenshots.
- Dirty-rect cost when the camera moves (every world sprite changes position).
- Interaction with parallax layers (already camera-driven) and `is_visible()` culling.
- Whether `apply_camera_to_sprites()` remains as an override point or disappears.

**Next step:** brainstorm this brief into `plans/<date>-engine-world-space.md` (spec) and its
implementation plan, linking back here.

---

## #14 Multiplayer input: player slots and targeted rumble — design brief

**Origin:** 2026-10-17, while adding Brave Adventurer's death rumble. With more than one player, a
personal event (one player's death) must rumble only that player's controller, while shared events
(the elevator slam) rumble everyone.

**Decided so far (with the user):**
- The game decides targets when it creates an effect (`pulse(..., targets=players(2))`), not the
  scene manager through a callback: only the game knows why a rumble happens, and deciding at
  creation is explicit and testable. `SceneManager`/`RumbleController` only mix and route.
- Until this lands, all rumble is broadcast (correct for the current single-player games). When it
  lands, `RumbleController.pulse`, `set_sustained` and `RumbleSettings` gain a `targets` keyword
  defaulting to all devices, so existing calls keep working.

**Sketch:**
1. **Player slots** (engine input registry, owned by the engine because devices are global): player
   number → joystick/controller instance id; default assignment in connection order, explicit
   `assign(player=..., instance_id=...)`, a defined disconnect/reconnect policy. Per-player input
   follows for free: `ActionMap` bindings already filter by `instance_id`. Could later replace
   Bitmappy's own controller manager.
2. **Targets on every rumble source:** shake rumble, sustained rumble and pulses carry `targets`
   (all devices by default, or specific players).
3. **Per-device mixing:** for each device, find its player and take the per-motor maximum over
   sources aimed at that player or at everyone; unassigned devices receive only broadcast rumble.
   Resend state becomes per device (SDL rumble is per device anyway).
4. **Usage:** `pulse(..., targets=players(self.player.number))`; single-player games use player 0.

**Open questions:** joystick vs controller input modes (instance ids differ), hot-plug policy,
how players join (press-to-join vs connection order), whether screen-shake rumble should ever be
per player (split screen), keyboard players (no rumble).

## #15 Frame loop: one end-of-frame call

**Motivation:** BUGS.md #25. Frame pacing (timer backend or pygame clock) and FPS tracking measured
frames differently: pacing used the timer, tracking used pygame's 10-frame `Clock.get_fps()`, so
the statistics disagreed with what the loop actually did.

**Idea:** a single `_finish_frame()` at the end of each main-loop iteration that paces with the
timer backend and records that same frame's measured time, so pacing and measurement cannot
disagree. `SceneManager._tick_clock()` was an early form of this idea; it was dead code and was
removed in the BUGS.md #25 change (it is in git history).

**Requirements recorded so far:**
- (BUGS.md #26, 2026-10-17) Since #26, paced frame time is measured with `time.perf_counter()` from
  the start of the loop iteration to the end of the pacing sleep. Work done after the sleep
  (`_track_performance`, the FPS-event check, loop overhead) is not counted in that frame's
  tracked time, so reported FPS is marginally high (microseconds per frame). `_finish_frame()`
  must measure the full period: the time from one frame's start to the next frame's start, and
  record that as the frame's FPS sample, so tracked frames sum exactly to wall-clock time.
- Keep pacing deadlines on the timer backend's own clock (`FastTimer` by default since #26);
  measurement always uses the perf counter, and fractional target FPS must stay untruncated.
