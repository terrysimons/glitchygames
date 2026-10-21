# Engine World Space Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The engine positions, snaps and culls world-space sprites after game logic, aims the camera through one precedence order, and ends every frame in one `_finish_frame()` with a single frame time — and all four games migrate onto it with identical behaviour.

**Architecture:** A new `glitchygames/world.py` holds the coordinate-space declaration, the `WorldPositioned` Protocol and the positioning step; `glitchygames/pixel_snap.py` gains the active default snap mode; `Camera2D` gains follow; `Scene` gains `PIXEL_SNAP_MODE` and the `camera_target()` hook; `SceneManager` runs camera aim and positioning in the frame and ends the loop in `_finish_frame()`. Golden traces recorded from the current code before any engine change prove the migrations.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8, pytest + pytest-mock, uv.

**Spec:** `plans/2026-10-18-engine-world-space.md`

## Global Constraints

- uv for everything; lint (`uv run ruff check glitchygames tests scripts noxfile.py`, `uv run ruff format --check glitchygames tests scripts noxfile.py`) and type checks (`uv run basedpyright`, `uv run ty check glitchygames scripts` — 50 pre-existing `unused-ignore-comment` warnings expected) before tests; never change linter/type-checker configuration; no lint suppressions of any kind.
- `uv run mkdocs build --strict` must exit 0 (check the exit status, not the output) when docs change.
- Commit per task with `git add <paths>` only (never `-A`/`.`); messages end with your Co-Authored-By trailer. Never push, amend, rebase, `git stash` or `git restore`. Never `sed -i`.
- Tests use pytest-mock `mocker` (never `unittest.mock`), pytest assertions, no dependence on chance or wall-clock time. Real-surface pygame tests go outside `tests/scenes` and `tests/game_objects` (their conftest mocks pygame) — use `tests/world/` (create `tests/world/__init__.py`).
- Style: single quotes, Google docstrings, 100-char lines, full descriptive names, keyword arguments, `from __future__ import annotations`, explicit `is None`; read comments before modifying code; report any bug you notice.
- Names and values from the spec (exact): `CoordinateSpace.SCREEN` / `CoordinateSpace.WORLD`; `COORDINATE_SPACE`; `WorldPositioned`; `hidden`; `Scene.PIXEL_SNAP_MODE` default `PixelSnapMode.NEAREST_HALF_UP`; `pixel_snap_mode` (per sprite); `Camera2D.follow(*, target, axes=FollowAxes.BOTH)`; `FollowAxes.X` / `Y` / `BOTH`; `follow_target`, `follow_axes`; `Scene.camera_target()`; `position_world_sprites(scene)`; `CULL_MARGIN_PIXELS = 32`; `_finish_frame(*, frame_start_seconds)`.
- Full suite: `time (SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest -n auto -q -p no:cacheprovider)` — all pass, coverage ≥ 80%, no warnings. (zsh's `time` prints `… total`, not `real`; don't wait for a `real` line.)

## Review Focus

1. A sprite spawned during `dt_tick` (a new PaddleSlap ball, a respawned player) must be drawn at its correct screen position on its very first rendered frame, not at (0, 0). Pinned in Task 4.
2. A world sprite the game hid (`hidden = True`) that is later un-hidden while on screen must become visible again; one that scrolls back on screen while hidden must stay invisible. Pinned in Task 2.
3. At scene start the camera must begin on its follow target (no swoop from the origin) exactly as each game does today; a game that called `camera.snap_to` in setup keeps doing so. Pinned in Task 3 and by the golden traces.
4. A world sprite in `scene.all_sprites` whose `world_x`/`world_y` are ints, or a sprite that sets `COORDINATE_SPACE = WORLD` but lacks `world_y`, must not crash the frame: ints work; a missing attribute raises a clear `TypeError` naming the sprite class at positioning time. Pinned in Task 2.
5. The first frame after a long hitch (e.g. a window drag, 2 s) must record one long frame — not distort pacing for the following frames — and `--target-fps 0` must never sleep. Pinned in Task 5.

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `scripts/record_golden_traces.py` | create | Deterministic headless runs of each game recording per-frame sprite `rect`/`visible` |
| `tests/world/golden/*.jsonl.gz` | create | Baseline traces recorded from the pre-change code (format version 2: gzip JSON Lines, keyframes + deltas; Task 1c) |
| `glitchygames/tracing.py` | create | Trace format: `TraceWriter` (streaming), `read_trace`/`read_trace_result`, `write_trace`, `encode_frame`/`decode_frame`, `StableSpriteIds`, `sample_scene_frame` (Task 1c) |
| `tests/world/test_golden_traces.py` | create | Re-runs the harness and compares with the baseline (plus enumerated expected differences) |
| `glitchygames/scenes/scene.py` | modify | Extract `_run_scene_frame()`; camera aim + positioning in the frame; active snap mode on activation; `PIXEL_SNAP_MODE`, `camera_target()`; `_finish_frame()` |
| `glitchygames/pixel_snap.py` | modify | `set_active_default_snap_mode`, `active_default_snap_mode`, `resolve_snap_mode(sprite)` |
| `glitchygames/world.py` | create | `CoordinateSpace`, `WorldPositioned`, `is_world_positioned`, `screen_position_for`, `position_world_sprites`, `aim_camera` |
| `glitchygames/camera.py` | modify | `FollowAxes`, `follow`, `follow_target`, `follow_axes`, manual-update tracking, snapped parallax |
| `glitchygames/collision/detection.py` | modify | `snapped_world_position` uses `resolve_snap_mode` |
| `glitchygames/examples/clockwork_keep/*` | modify | Migration (Task 6) |
| `glitchygames/examples/brave_adventurer/*` | modify | Migration (Task 7) |
| `glitchygames/examples/brave_adventurer_papyrus/*` | modify | Migration (Task 8) |
| `glitchygames/game_objects/ball.py`, `glitchygames/examples/paddleslap.py` | modify | Migration (Task 9) |
| `CLAUDE.md`, `plans/engine-audit.md`, `plans/future-work.md` | modify | Docs (Task 9) |

---

### Task 1: Golden trace baseline (before any engine change)

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`SceneManager.start`: extract the non-transition frame body)
- Create: `scripts/record_golden_traces.py`, `tests/world/__init__.py`, `tests/world/golden/{clockwork_keep,brave_adventurer,brave_adventurer_papyrus,paddleslap}.json`, `tests/world/test_golden_traces.py`

**Interfaces:**
- Produces: `SceneManager._run_scene_frame(self) -> None` (the non-transition frame body: `_update_scene()`, `_process_events()`, `_update_frame_services()`, `_render_scene()`, `_present_frame(full_update=False)`, then the pending-transition / requested-switch check — moved verbatim, no behaviour change). Later tasks insert steps into it.
- Produces: `scripts/record_golden_traces.py` with `record_trace(game_key: str, *, frame_count: int) -> dict` and a `main()` that writes `tests/world/golden/<game_key>.json`. Trace format: `{"game": key, "frame_seconds": 1/60, "frames": [{"frame": n, "scene": scene class name, "sprites": [{"id": "<ClassName>#<index among that class in all_sprites order>", "rect": [x, y, w, h], "visible": bool}]}]}`.

- [ ] **Step 1: Extract `_run_scene_frame()`.** Move the `else:` branch body of `SceneManager.start()` into a method with a docstring; `start()` calls it. Run `uv run pytest tests/scenes tests/debug -q -p no:cacheprovider --no-cov` — all pass (pure refactor).

- [ ] **Step 2: Write the harness.** For each game key, construct the game's scene headless (`SDL_VIDEODRIVER=dummy`, `pygame.display.set_mode` at the game's size), install it on a fresh `SceneManager` the way the existing example tests do (find them: `grep -rln "PapyrusBraveAdventurerScene(\|ClockworkKeep\|BraveAdventurerScene(\|paddleslap" tests/examples`), and for N frames: set `manager.dt = 1/60`, post that frame's scripted key events with `pygame.event.post`, call `manager._run_scene_frame()`, then record every sprite in `active_scene.all_sprites`. Determinism: patch randomness with a seeded `random.Random(seed)` — `secrets.randbelow` and `glitchygames.game_objects.ball._SERVE_RANDOM` in PaddleSlap, and any `random`/`secrets` use in the other games (grep them) — and patch `time.perf_counter` with a counter advancing exactly 1/60 per frame where game code reads it. Scripts (keep them free of wall-turning moments; the pose fix is tested separately in Tasks 6–7):
  - Clockwork Keep (900 frames): walk right 120 frames, jump, walk left, ride the elevator once (use the interact key), collect a cog, pause and resume.
  - Brave Adventurer and Papyrus (900 frames each): walk right across the first screens with jumps over walls and a pit, collect scarabs, pause and resume.
  - PaddleSlap (900 frames): paddles track the nearest ball's y (as the review harness did), one pause/resume.

- [ ] **Step 3: Record the baseline** with `uv run python scripts/record_golden_traces.py` and commit the four JSON files. Run it twice and confirm identical output (determinism).

- [ ] **Step 4: Write `tests/world/test_golden_traces.py`:** parametrized over the four games, re-run `record_trace` and compare frame by frame with the baseline. On mismatch, fail with the first differing frame, sprite id and both values. Support an `EXPECTED_DIFFERENCES: dict[str, list[ExpectedDifference]]` (dataclass: `frame`, `sprite_id`, `field`, `reason`) that later tasks fill in, each entry justified; any unlisted difference fails, and any listed difference that no longer occurs also fails (so the list can't go stale). It passes now with an empty list.

- [ ] **Step 5:** lint/type-check, run `tests/world tests/scenes tests/examples`, commit (`Record golden traces of every game before the world-space change`).

---

### Task 2: Coordinate space, snapping resolution and the positioning step

**Files:**
- Modify: `glitchygames/pixel_snap.py`
- Create: `glitchygames/world.py`, `tests/world/test_positioning.py`

**Interfaces:**
- Produces (pixel_snap): `set_active_default_snap_mode(mode: PixelSnapMode) -> None`, `active_default_snap_mode() -> PixelSnapMode` (initially `NEAREST_HALF_UP`), `resolve_snap_mode(sprite: object) -> PixelSnapMode` (the sprite's `pixel_snap_mode` if it is a `PixelSnapMode`, else the active default).
- Produces (world): `CoordinateSpace(Enum)` (`SCREEN`, `WORLD`); `WorldPositioned` runtime-checkable Protocol (`COORDINATE_SPACE`, `world_x`, `world_y`, `rect`); `is_world_positioned(sprite: object) -> bool` (`getattr(sprite, 'COORDINATE_SPACE', CoordinateSpace.SCREEN) is CoordinateSpace.WORLD`); `CULL_MARGIN_PIXELS = 32`; `screen_position_for(*, sprite, camera: Camera2D) -> tuple[int, int]`; `position_world_sprites(*, sprites: Iterable[object], camera: Camera2D, screen_size: tuple[int, int]) -> None`.

```python
"""World space: sprites that live in world coordinates and are positioned by the engine."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import pygame

from glitchygames.pixel_snap import resolve_snap_mode, snap_to_pixel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from glitchygames.camera import Camera2D

# Sprites this far outside the screen still count as visible, so they never pop in at the edge
CULL_MARGIN_PIXELS = 32


class CoordinateSpace(enum.Enum):
    """Where a sprite's position lives: on the screen (HUD, UI) or in the world (moves with the camera)."""

    SCREEN = 'screen'
    WORLD = 'world'


@runtime_checkable
class WorldPositioned(Protocol):
    """A sprite the engine positions from the camera each frame."""

    COORDINATE_SPACE: CoordinateSpace
    world_x: float
    world_y: float
    rect: pygame.Rect


def is_world_positioned(sprite: object) -> bool:
    """Report whether the engine positions this sprite (it declared CoordinateSpace.WORLD)."""
    return getattr(sprite, 'COORDINATE_SPACE', CoordinateSpace.SCREEN) is CoordinateSpace.WORLD


def screen_position_for(*, sprite: object, camera: Camera2D) -> tuple[int, int]:
    """Screen top-left for a world sprite: snap(world) - snap(camera) - shake, plus draw_offset.

    Raises:
        TypeError: If the sprite declares world space but lacks world_x or world_y.
    """
    ...
```

`screen_position_for`: resolve the mode with `resolve_snap_mode(sprite)`; `x = snap_to_pixel(world_x, mode) - snap_to_pixel(camera.world_x, mode) - round_shake_x` where the shake offset is `camera.shake_effect.offset` snapped with the same mode; same for y; add `getattr(sprite, 'draw_offset', (0, 0))`. A missing `world_x`/`world_y` raises `TypeError(f'{type(sprite).__name__} declares CoordinateSpace.WORLD but has no world_x/world_y')`.

`position_world_sprites`: for each sprite where `is_world_positioned(sprite)`: compute the position; if it differs from `rect.topleft`, set it and `dirty = 1` (leave `dirty` alone when unchanged, so `dirty = 2` sprites keep their mode); `visible = rect.colliderect(screen_rect.inflate(2 * CULL_MARGIN_PIXELS, 2 * CULL_MARGIN_PIXELS)) and not getattr(sprite, 'hidden', False)`. Never write anything else.

- [ ] **Step 1: Failing tests** (`tests/world/test_positioning.py`, real `Camera2D` and tiny real sprite classes):
  - snapping: camera at world_x 10.5 and a sprite at 100.5 with `NEAREST_HALF_UP` → x = 101 − 11 = 90; moving both by +0.25 per step for 8 steps, the sprite's screen x never changes relative to a second sprite (no shimmer);
  - a sprite with its own `pixel_snap_mode = FLOOR` uses FLOOR; others use the active default; `set_active_default_snap_mode` changes the default;
  - WORLD shake offset `(3.0, -2.0)` shifts the screen position by (−3, +2);
  - `draw_offset = (0, 6)` adds 6 to y;
  - dirty set only when the position changes; a `dirty = 2` sprite stays 2;
  - culling: on screen → visible; 31 px off the right edge → visible (margin); 40 px off → not visible; `hidden = True` on screen → not visible; un-hidden → visible again; hidden sprite scrolling on screen stays invisible (Review focus 2);
  - screen-space sprites (no attribute, or `SCREEN`) are untouched (rect, visible, dirty);
  - int `world_x`/`world_y` work; a WORLD sprite without `world_y` raises `TypeError` naming the class (Review focus 4);
  - the step never changes `world_x`, `world_y`, camera position or `image`.
- [ ] **Step 2: RED.** `uv run pytest tests/world/test_positioning.py -q -p no:cacheprovider --no-cov`.
- [ ] **Step 3: Implement** the pixel_snap additions and `world.py` as above.
- [ ] **Step 4: GREEN**, then `tests/world` and the golden test (must still pass: nothing uses this yet).
- [ ] **Step 5:** lint/type-check, commit (`Add world-space declaration and the engine positioning step`).

---

### Task 3: Camera follow, the scene hook and camera aim

**Files:**
- Modify: `glitchygames/camera.py`, `glitchygames/scenes/scene.py` (`Scene`), `glitchygames/world.py`
- Test: `tests/world/test_camera_follow.py`

**Interfaces:**
- Produces (camera): `FollowAxes(enum.Flag)` with `X`, `Y`, `BOTH = X | Y`; `Camera2D.follow(self, *, target: object | None, axes: FollowAxes = FollowAxes.BOTH) -> None`; read-only `follow_target` and `follow_axes`; internal manual-update tracking: `update()` called by game code sets `self._updated_by_game_this_frame = True`; the engine calls a new `_engine_update(target_x, target_y, dt)` that runs the same smoothing/clamp/shake/parallax but does not set that flag; `begin_frame()` clears the flag.
- Produces (scene): `Scene.PIXEL_SNAP_MODE: PixelSnapMode = PixelSnapMode.NEAREST_HALF_UP` (class attribute); `Scene.camera_target(self) -> tuple[float, float] | None` (default: the follow target's `(float(world_x), float(world_y))` or `None`).
- Produces (world): `aim_camera(*, scene: object, camera: Camera2D, dt: float) -> None`: `target = scene.camera_target()`; `None` → return (manual mode); apply axes (an unfollowed axis uses the camera's current goal on that axis: `camera.world_x + camera.lead_x` for X, likewise Y); if `camera._updated_by_game_this_frame` → log a warning once per scene ("camera.update() called by the game while the engine is also aiming the camera; remove the manual call or stop following") and still aim; call `camera._engine_update(target_x, target_y, dt)`.
- Parallax uses the snapped camera position: `_update_parallax_layers(camera_x=snap(world_x + shake_x), …)` with `active_default_snap_mode()`.

- [ ] **Step 1: Failing tests:** follow X keeps the camera's Y; BOTH follows both; `follow(target=None)` → `camera_target()` returns None and `aim_camera` doesn't move the camera; an overridden `camera_target` wins over a follow target; axes apply to a hook-supplied point; the warning logs once (mocker on the module logger) when `camera.update` was called by the game in the same frame and an engine target exists, and never in manual mode; `_engine_update` advances shake and parallax exactly like `update`; parallax layer positions are whole pixels with the active snap mode; `snap_to` unchanged (Review focus 3: a camera snapped to the target in setup stays there on the first aimed frame when the target hasn't moved).
- [ ] **Step 2: RED. Step 3: Implement. Step 4: GREEN** + golden test still passes (no game uses follow yet).
- [ ] **Step 5:** lint/type-check, commit (`Add camera follow, the camera_target hook and engine camera aim`).

---

### Task 4: Run camera aim and positioning in the frame; one snap mode for collision

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`_run_scene_frame`, scene activation), `glitchygames/collision/detection.py`
- Test: `tests/world/test_frame_integration.py`; update `tests/world/test_golden_traces.py` expected differences

**Interfaces:**
- Consumes: `aim_camera`, `position_world_sprites`, `set_active_default_snap_mode`, `resolve_snap_mode`.
- `_run_scene_frame` order becomes:
  1. `active_scene.camera.begin_frame()` (clears the manual-update flag)
  2. `_update_scene()`
  3. `_process_events()`
  4. `_update_frame_services()`
  5. `aim_camera(scene=active_scene, camera=active_scene.camera, dt=self.dt)`
  6. `position_world_sprites(sprites=active_scene.all_sprites, camera=active_scene.camera, screen_size=self.screen.get_size())`
  7. `_render_scene()`
  8. `_present_frame(full_update=False)`
  9. the existing pending-transition / requested-switch check.
- On scene activation (`_configure_active_scene`), call `set_active_default_snap_mode(scene.PIXEL_SNAP_MODE)`.
- `snapped_world_position` uses `resolve_snap_mode(sprite)` instead of `round()` for sprites without their own mode.

- [ ] **Step 1: Failing tests:** a world sprite in the active scene is positioned before render (its rect at render time equals `screen_position_for`); a sprite spawned during `dt_tick` is at its correct position in the first rendered frame (Review focus 1); screen-space sprites untouched; activation sets the active snap mode; `snapped_world_position` follows the scene mode for a sprite without `pixel_snap_mode` (exact .5 → half-up).
- [ ] **Step 2: RED. Step 3: Implement.**
- [ ] **Step 4:** run the golden test. The collision snap change may alter traces at exact .5 positions: for each difference, confirm it is a .5 rounding case, then add it to `EXPECTED_DIFFERENCES` with `reason='round-half-up at an exact .5 position (collision snap mode)'`. Any other difference is a bug — fix it.
- [ ] **Step 5:** lint/type-check, `tests/world tests/scenes tests/collision tests/debug tests/examples`, commit (`Aim the camera and position world sprites in the frame`).

---

### Task 5: `_finish_frame()` — one frame time (#15)

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`start`, `_handle_frame_pacing`, `_track_performance`, `_post_fps_event` call site)
- Test: `tests/world/test_finish_frame.py`

**Interfaces:**
- Produces: `SceneManager._finish_frame(self, *, frame_start_seconds: float, timer: object | None, period_ns: int, previous_deadline_ns: int | None, processing_seconds: float) -> float` returning the closing `time.perf_counter()` reading (the next frame's start). It paces (the existing timer/clock code, minus the `self.dt = …` write), does the bookkeeping (`_track_performance`, jitter logging, FPS event), then reads the clock once, sets `self.dt = closing_reading - frame_start_seconds` — the full start-to-start period — and records it as the FPS sample (`_track_performance` uses this `dt`).
- `start()` loop: `frame_start = previous_closing_reading` (initially `time.perf_counter()` once before the loop); the top-of-loop `self.dt = now - previous_time` write is removed, so logic in frame N sees the `dt` closed at the end of frame N−1. The first frame keeps today's behaviour: its `dt` is the short time between the reading taken in `start()` before the loop and the first iteration (set `self.dt` from that once, before the first frame body, exactly as the current top-of-loop line does on its first pass). Both branches (transition and normal) end in `_finish_frame`.
- The debug overlay's `record_frame(frame_seconds=self.dt)` in `_update_frame_services` therefore records the same value the FPS statistics recorded for the previous frame.

- [ ] **Step 1: Failing tests** (fake `time.perf_counter` via mocker returning scripted values; a fake timer with `start_frame`, `compute_deadline`, `sleep_until_next`): over 10 frames recorded samples sum exactly to the elapsed fake time; logic's `dt` in frame N equals frame N−1's recorded sample; `self.dt` is written exactly once per frame (spy on the attribute via a property shim or by counting); pacing with target 60.01 computes deadlines with the fractional period (`round(1e9 / 60.01)` ns); target 0 never calls `sleep_until_next`; the transition branch is paced and recorded the same way; a 2 s hitch frame records one 2.0 s sample and the following frame's deadline is computed from the timer's `compute_deadline` as today (Review focus 5); the debug overlay history matches the performance manager's samples.
- [ ] **Step 2: RED. Step 3: Implement. Step 4: GREEN**, then the golden test (dt is fixed in the harness, so traces are unaffected) and `tests/scenes tests/performance tests/debug tests/engine`.
- [ ] **Step 5:** lint/type-check, commit (`End every frame in _finish_frame with one start-to-start frame time`).

---

### Task 6: Migrate Clockwork Keep

**Files:** `glitchygames/examples/clockwork_keep/{game.py,player.py,terrain.py}`; tests in the existing Clockwork Keep test file and `tests/world/test_golden_traces.py`.

- [ ] **Step 1: Failing tests:** every Clockwork Keep world sprite class declares `COORDINATE_SPACE = CoordinateSpace.WORLD`; no class defines `apply_camera`; the scene calls `camera.follow(target=player, axes=FollowAxes.BOTH)` in setup; **lag test:** standing flush against a side wall, turning to face away and jumping, the player's collision rect never overlaps the wall on any frame (it does today, for one frame).
- [ ] **Step 2: RED. Step 3: Implement:**
  - add `COORDINATE_SPACE = CoordinateSpace.WORLD` to the player, platforms, elevators and cogs; remove their `apply_camera` methods and the loop that calls them; remove manual `camera.update(...)` (game.py ~437) — replaced by `self.camera.follow(target=self.player, axes=FollowAxes.BOTH)` in setup, keeping `set_bounds` and any `snap_to`;
  - any per-sprite `visible` assignment for culling goes; a sprite the game hides deliberately sets `hidden`;
  - move the tinker's pose drawing from `update()` into `dt_tick`, after its state is decided and before the collision/terrain resolution (read the existing comments; keep `update()` for anything purely visual that doesn't affect the hitbox).
- [ ] **Step 4: GREEN.** Golden test: differences only from the pose fix near walls (none expected — the script avoids wall turns) and culling margin; list each justified difference or fix the code.
- [ ] **Step 5:** lint/type-check, `tests/examples tests/world`, commit (`Move Clockwork Keep onto engine world space`).

---

### Task 7: Migrate Brave Adventurer

**Files:** `glitchygames/examples/brave_adventurer/{game.py,player.py,terrain.py,enemies.py}`; tests in `tests/examples/test_brave_adventurer_game.py` and the golden test.

- [ ] **Step 1: Failing tests:** world classes declare WORLD (player, `GroundSegment`, `StoneWall`, enemies, gold scarabs); no `apply_camera`; no `camera.is_visible` calls in the game package (pit-gap drawing may still use `camera.apply`); `camera.follow(target=player, axes=FollowAxes.X)`; **lag test** as in Task 6 against a `StoneWall`.
- [ ] **Step 2: RED. Step 3: Implement:** declare WORLD; `GroundSegment` sets `self.world_y = GROUND_Y` in `__init__`; remove `apply_camera`, the culling blocks and `_follow_player_with_camera`'s loop (keep the score update); `camera.follow(...)` in setup; move the player's pose drawing (`draw_player(...)` in `update()`) into `dt_tick` before collision; collected/removed sprites keep using `kill()` where they do; deliberately hidden ones use `hidden`.
- [ ] **Step 4: GREEN** + golden test with justified differences only.
- [ ] **Step 5:** lint/type-check, `tests/examples tests/world`, commit (`Move Brave Adventurer onto engine world space`).

---

### Task 8: Migrate Papyrus

**Files:** `glitchygames/examples/brave_adventurer_papyrus/{game.py,player.py,terrain.py,enemies.py}`; tests in `tests/examples/test_brave_adventurer_game.py` and the golden test.

- [ ] **Step 1: Failing tests:** as Task 7 for Papyrus classes; the player's rect equals `screen_position_for` (which includes `draw_offset`) with no manual `draw_offset` addition left in Papyrus; the feet-on-ground test (lowest visible row == ground line − 1 on every on-ground frame) still passes.
- [ ] **Step 2: RED. Step 3: Implement:** declare WORLD; remove `apply_camera`, culling and the follow loop; remove Papyrus's manual `draw_offset` placement (the engine adds it); `camera.follow(target=player, axes=FollowAxes.X)`.
- [ ] **Step 4: GREEN** + golden test.
- [ ] **Step 5:** lint/type-check, commit (`Move Papyrus onto engine world space`).

---

### Task 9: Migrate PaddleSlap; docs

**Files:** `glitchygames/game_objects/ball.py`, `glitchygames/examples/paddleslap.py`, `CLAUDE.md`, `plans/engine-audit.md`, `plans/future-work.md`; ball tests; the golden test.

- [ ] **Step 1: Failing tests:** `BallSprite.COORDINATE_SPACE is CoordinateSpace.WORLD`; setting `world_x` no longer writes `rect` (the engine positions it); under PaddleSlap's identity camera the ball's rect after positioning equals its snapped world position with its own `pixel_snap_mode`; ball physics tests that read `rect` after moving now position first (update those tests to call `position_world_sprites` or read the collision rect, per what they assert — do not weaken them).
- [ ] **Step 2: RED. Step 3: Implement.** Paddles and HUD stay screen-space.
- [ ] **Step 4: GREEN** + golden test (PaddleSlap trace must match exactly: identity camera, same snap mode).
- [ ] **Step 5: Docs:** CLAUDE.md "World Space" entry (declaring world sprites, `camera.follow`, `camera_target()`, `PIXEL_SNAP_MODE`, `hidden`, the pose-before-collision rule) and a `_finish_frame` sentence under Frame Pacing; `plans/engine-audit.md` #6 and #15 → Done (feature/engine-world-space); remove the one-frame-lag row from `plans/future-work.md`. `uv run mkdocs build --strict` exit 0.
- [ ] **Step 6:** full checks + one timed full suite; commit (`Move PaddleSlap's ball onto engine world space; document world space`).
