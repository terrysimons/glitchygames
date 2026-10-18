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
| 1 | Solid/terrain collision resolution (ground, walls, one-way platforms) | Open | 7 `_resolve_*_collision` methods across the games; `CollisionManager` detects but does not resolve |
| 2 | Expressions phase 2: `and` / `or` / `not` / parentheses | Open | Promised in `animation/expressions.py:17`; `_FallingCondition` copied into all three platformer players |
| 3 | Screen shake | **Done** (this branch) | `plans/2026-10-17-screen-shake-and-synth.md` |
| 4 | High-score table | Open | `_save_high_score` copied into 4 games |
| 5 | Sound effect synthesis | **Done** (this branch) | Same spec: toolkit, recipes, live voices |
| 6 | Engine world space (absorbs pixel snapping and camera follow) | Open — next design | See below |
| 7 | Balls on `CollisionManager` | Open | Commit `fa5750f`: "except balls which we'll do later" |
| 8 | Sprite transparency/scaling helpers; masks instead of alpha trimming | Open | Papyrus `sprite_utils.py` |
| 9 | Particles | Open | None exist |
| 10 | Timers and cooldowns on game time | Open | Ad-hoc cooldown dicts in `ball.py` and PaddleSlap |
| 11 | Level/room data format (and tilemaps) | Open | Each game defines its own `ScreenData`/`FloorData`/`LevelManager` |
| 12 | Debug overlay (hitboxes, velocities, FPS) | Open | None exists |
| 13 | Controller rebinding UI and settings persistence | Open | `ActionMap.to_dict`/`from_dict` exist; nothing saves or edits bindings |

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
