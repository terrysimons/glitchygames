# Debug Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A toggleable debug overlay (collision, physics, camera, performance panels plus a game hook) that works in every GlitchyGames game with no game code.

**Architecture:** A new `glitchygames/debug/` package holds pure state (`DebugOverlay`) and pure drawing functions (`panels.py`). `SceneManager` owns one overlay, intercepts F3/F4, feeds it frame times, and draws it inside `_present_frame` on the frame about to be shown, restoring the clean frame afterwards.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8, pytest + pytest-mock, uv.

**Spec:** `plans/2026-10-17-debug-overlay.md`

## Global Constraints

- uv for everything; lint (`uv run ruff check`, `uv run ruff format --check`) and type checks (`uv run basedpyright`, `uv run ty check glitchygames scripts`) before tests; never change linter/type-checker configuration; never add global ignores.
- Commit per task (only that task's files via `git add <paths>`; never `-A`/`.`), descriptive message ending with your Co-Authored-By trailer. Never push, amend, `git stash` or `git restore`.
- Tests use pytest-mock `mocker` (never `unittest.mock`), pytest assertions, no dependence on chance or wall-clock time.
- Pixel tests use real `pygame.Surface`s and live under `tests/debug/` (create `tests/debug/__init__.py`): `tests/scenes/*` gets a mocked pygame from `tests/conftest.py`. `SceneManager` integration tests that need real surfaces also go in `tests/debug/`.
- Code style: single quotes, Google docstrings, 100-char lines, full descriptive names, keyword arguments, `from __future__ import annotations`, explicit `is None`, read comments before modifying code.
- The overlay is read-only: it never changes positions, velocities, camera state or sprite dirty flags.
- Keys: `pygame.K_F3` toggles, `pygame.K_F4` cycles; flag `--debug-overlay` (store_true, default off; option key `debug_overlay`).
- Constants (spec): `PHYSICS_ARROW_SECONDS = 0.1`, `PHYSICS_ARROW_MAXIMUM_PIXELS = 80`, `PERFORMANCE_WINDOW_SECONDS = 5.0`, `GRAPH_WINDOW_SECONDS = 2.0`, frame history `deque(maxlen=5000)`.
- Run each full suite with `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest -n auto -q -p no:cacheprovider` (all pass, coverage >= 80%, no warnings); ty's 50 pre-existing `unused-ignore-comment` warnings are expected.

## Review Focus

1. A game whose sprites are positioned through the camera while the camera has scrolled: hitbox outlines must sit on the sprites (world rects converted via `camera.apply`), not at world coordinates. Pinned in Task 3.
2. Pressing F3 while typing in a text box (Bitmappy's AI prompt): the keystroke must reach the text box, not toggle the overlay. Pinned in Task 5.
3. Hiding the overlay (F3) mid-game: the next presented frame must not keep stale overlay pixels on screen (one full flip). Pinned in Task 5.
4. A game's `debug_draw` hook that raises every frame: one log line, hook disabled, game keeps running. Pinned in Task 4.
5. Overlay on during a SCREEN shake: world annotations follow the shaken sprites, HUD stays put, and nothing leaks into screenshots. Pinned in Task 5.

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `glitchygames/collision/layers.py` | modify | Public `get_sprite_collision_rect` (+ private alias) |
| `glitchygames/camera.py` | modify | `Camera2D.bounds` read-only property |
| `glitchygames/input/rumble.py` | modify | `RumbleController.sent_levels` read-only property |
| `glitchygames/audio/live.py` | modify | `LiveAudio.playing_voice_count` read-only property |
| `glitchygames/debug/__init__.py` | create | Exports |
| `glitchygames/debug/protocols.py` | create | `PhysicsState`, `HasPhysicsBody`, `DebugDrawable` |
| `glitchygames/debug/overlay.py` | create | `DebugPanel`, `DebugOverlay` state, history, `draw` composition, hook handling |
| `glitchygames/debug/panels.py` | create | Pure drawing functions |
| `glitchygames/scenes/scene.py` | modify | Own overlay, F3/F4, record frames, draw in `_present_frame` |
| `glitchygames/engine/game_engine.py` | modify | `--debug-overlay` flag |
| tests: `tests/test_camera.py`, `tests/input/test_rumble.py`, `tests/audio/test_live.py`, the collision tests (find with `grep -rln "check_overlap" tests`), `tests/debug/*`, engine argument tests | modify/create | |
| `CLAUDE.md`, `plans/engine-audit.md` | modify | Docs |

---

### Task 1: Engine read-outs the overlay needs

**Files:**
- Modify: `glitchygames/collision/layers.py` (`_get_sprite_collision_rect` ~line 207 and its 4 callers)
- Modify: `glitchygames/camera.py`, `glitchygames/input/rumble.py`, `glitchygames/audio/live.py`
- Test: the existing collision test file, `tests/test_camera.py`, `tests/input/test_rumble.py`, `tests/audio/test_live.py`

**Interfaces:**
- Produces: `get_sprite_collision_rect(sprite: Any) -> pygame.Rect` (public; world-space rect for sprites with `world_x`/`world_y`, else `sprite.rect`, else an empty rect); `Camera2D.bounds -> tuple[float | None, float | None, float | None, float | None]` as `(min_x, min_y, max_x, max_y)`; `RumbleController.sent_levels -> tuple[float, float]`; `LiveAudio.playing_voice_count -> int`.

- [ ] **Step 1: Write failing tests**

```python
# collision tests
from glitchygames.collision.layers import get_sprite_collision_rect

def test_get_sprite_collision_rect_is_public_and_uses_world_position(mocker):
    sprite = mocker.Mock(spec=['world_x', 'world_y', 'rect'])
    sprite.world_x, sprite.world_y = 100.0, 50.0
    sprite.rect = pygame.Rect(0, 0, 10, 20)
    rect = get_sprite_collision_rect(sprite)
    assert (rect.x, rect.y) == (100, 50)

# tests/test_camera.py
def test_bounds_property_reports_configured_edges():
    camera = Camera2D(screen_width=200, screen_height=100)
    assert camera.bounds == (None, None, None, None)
    camera.set_bounds(min_x=0.0, max_x=400.0)
    assert camera.bounds == (0.0, None, 400.0, None)

# tests/input/test_rumble.py
def test_sent_levels_reflects_last_send(devices):
    controller = RumbleController()
    assert controller.sent_levels == (0.0, 0.0)
    controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
    assert controller.sent_levels == (1.0, 0.5)

# tests/audio/test_live.py  (inside TestLiveAudio, using its `audio` fixture)
def test_playing_voice_count(self, audio):
    first = self._create(audio, 'scene')
    self._create(audio, 'scene')
    assert audio.playing_voice_count == 0
    first.start()
    assert audio.playing_voice_count == 1
```

(Adapt fixtures/helpers to the files' existing ones; `_rumbling_shaker` and `devices` already exist in test_rumble.py. If `get_collision_rect` needs more attributes on the mock, use a tiny real class instead of a Mock.)

- [ ] **Step 2: Run to verify they fail** — `uv run pytest <files> -q -p no:cacheprovider --no-cov`. Expected: ImportError / AttributeError.

- [ ] **Step 3: Implement**
  - layers.py: rename the function to `get_sprite_collision_rect`, update its four call sites, keep `_get_sprite_collision_rect = get_sprite_collision_rect` with a comment ("kept for existing imports") only if `grep -rn _get_sprite_collision_rect glitchygames tests scripts` finds external users; otherwise drop the alias. Docstring: state that the rect is in world coordinates for sprites with `world_x`/`world_y` and in screen coordinates otherwise.
  - camera.py:

```python
    @property
    def bounds(self) -> tuple[float | None, float | None, float | None, float | None]:
        """World bounds as (min_x, min_y, max_x, max_y); None means unbounded on that edge."""
        return (self._min_x, self._min_y, self._max_x, self._max_y)
```

  - rumble.py: `sent_levels` property returning `self._sent_levels` (docstring: the levels last sent to devices, before device errors).
  - live.py: `playing_voice_count` property: `sum(1 for voice in self._voices if voice.is_playing)`.

- [ ] **Step 4: Run** — same command; PASS. Then `uv run pytest tests/collision tests/test_camera.py tests/input tests/audio -q -p no:cacheprovider --no-cov`.
- [ ] **Step 5: Lint, type-check touched files, commit** (`Add read-only engine accessors for the debug overlay`).

---

### Task 2: Overlay state, protocols and frame history

**Files:**
- Create: `glitchygames/debug/__init__.py`, `glitchygames/debug/protocols.py`, `glitchygames/debug/overlay.py`, `tests/debug/__init__.py`, `tests/debug/test_overlay_state.py`

**Interfaces:**
- Produces:
  - `DebugPanel(Enum)`: `ALL`, `COLLISION`, `PHYSICS`, `CAMERA`, `PERFORMANCE`.
  - `PhysicsState` / `HasPhysicsBody` / `DebugDrawable` runtime-checkable Protocols (spec section 1).
  - `DebugOverlay(*, visible: bool = False)` with `is_visible: bool`, `panel: DebugPanel`, `toggle()`, `cycle_panel()`, `record_frame(*, frame_seconds: float)`, `frame_times() -> list[float]` (oldest first), `current_fps() -> float | None`, `one_percent_low_fps(*, window_seconds: float = PERFORMANCE_WINDOW_SECONDS) -> float | None`, `graph_frame_times(*, window_seconds: float = GRAPH_WINDOW_SECONDS) -> list[float]`, `shows(panel: DebugPanel) -> bool` (True when `self.panel` is `ALL` or equal).
  - Module constants listed in Global Constraints.

- [ ] **Step 1: Failing tests** (`tests/debug/test_overlay_state.py`)

```python
import pytest

from glitchygames.debug import DebugOverlay, DebugPanel
from glitchygames.debug.protocols import DebugDrawable, HasPhysicsBody


class TestToggleAndCycle:
    def test_starts_hidden_by_default_and_toggles(self):
        overlay = DebugOverlay()
        assert overlay.is_visible is False
        overlay.toggle()
        assert overlay.is_visible is True

    def test_cycle_order_wraps(self):
        overlay = DebugOverlay(visible=True)
        seen = []
        for _ in range(6):
            seen.append(overlay.panel)
            overlay.cycle_panel()
        assert seen == [DebugPanel.ALL, DebugPanel.COLLISION, DebugPanel.PHYSICS,
                        DebugPanel.CAMERA, DebugPanel.PERFORMANCE, DebugPanel.ALL]

    def test_shows(self):
        overlay = DebugOverlay()
        assert overlay.shows(DebugPanel.PHYSICS)
        overlay.cycle_panel()  # COLLISION
        assert overlay.shows(DebugPanel.COLLISION)
        assert not overlay.shows(DebugPanel.PHYSICS)


class TestFrameHistory:
    def test_current_fps_from_last_frame(self):
        overlay = DebugOverlay()
        assert overlay.current_fps() is None
        overlay.record_frame(frame_seconds=1 / 50)
        assert overlay.current_fps() == pytest.approx(50.0)

    def test_one_percent_low_uses_window_and_slowest_frames(self):
        overlay = DebugOverlay()
        overlay.record_frame(frame_seconds=1.0)  # older than the 5 s window once followed by 5 s of frames
        for _ in range(500):
            overlay.record_frame(frame_seconds=0.01)  # 5.0 s of 100 FPS frames
        # window keeps the newest frames totalling <= 5 s: the 1.0 s frame is excluded
        assert overlay.one_percent_low_fps() == pytest.approx(100.0)
        overlay.record_frame(frame_seconds=0.05)  # one slow 20 FPS frame inside the window
        # window = the 0.05 s frame + 495 frames of 0.01 s (4.95 s) -> n = 496, ceil(4.96) = 5
        # slowest: one 20 FPS + four 100 FPS
        assert overlay.one_percent_low_fps() == pytest.approx((20 + 4 * 100) / 5)

    def test_graph_window(self):
        overlay = DebugOverlay()
        for _ in range(300):
            overlay.record_frame(frame_seconds=0.01)
        assert len(overlay.graph_frame_times()) == 200  # 2 s of 10 ms frames

    def test_zero_or_negative_frame_times_ignored(self):
        overlay = DebugOverlay()
        overlay.record_frame(frame_seconds=0.0)
        overlay.record_frame(frame_seconds=-1.0)
        assert overlay.frame_times() == []


class TestProtocols:
    def test_has_physics_body(self):
        class Body:
            velocity_x = 1.0; velocity_y = 2.0; world_x = 0.0; world_y = 0.0; on_ground = True
        class Thing:
            physics = Body()
        assert isinstance(Thing(), HasPhysicsBody)
        assert not isinstance(object(), HasPhysicsBody)

    def test_debug_drawable(self):
        class Drawer:
            def debug_draw(self, surface, camera): ...
        assert isinstance(Drawer(), DebugDrawable)
```

Window rule (state it in the docstring): walk frames newest-first, accumulating seconds; include a frame while the running total stays `<= window_seconds`; the 1% low is the mean FPS (1/frame time) of the slowest `max(1, ceil(0.01 * n))` frames among those `n`.

- [ ] **Step 2: Run to verify RED** — `uv run pytest tests/debug -q -p no:cacheprovider --no-cov` (ImportError).

- [ ] **Step 3: Implement** — `protocols.py`:

```python
"""Protocols the debug overlay recognises (structural typing, no inheritance needed)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pygame

    from glitchygames.camera import Camera2D


@runtime_checkable
class PhysicsState(Protocol):
    """Read-only physics state (matches glitchygames.physics.body.PhysicsBody)."""

    velocity_x: float
    velocity_y: float
    world_x: float
    world_y: float
    on_ground: bool


@runtime_checkable
class HasPhysicsBody(Protocol):
    """An object exposing a physics body as `physics`."""

    physics: PhysicsState


@runtime_checkable
class DebugDrawable(Protocol):
    """A scene or sprite that adds its own debug annotations."""

    def debug_draw(self, surface: pygame.Surface, camera: Camera2D) -> None:
        """Draw game-specific debug annotations onto the presented frame."""
        ...
```

`overlay.py` (state part; Task 4 adds `draw`):

```python
"""Debug overlay state: visibility, panel selection and a rolling frame-time history."""

from __future__ import annotations

import collections
import enum
import math

PHYSICS_ARROW_SECONDS = 0.1
PHYSICS_ARROW_MAXIMUM_PIXELS = 80
PERFORMANCE_WINDOW_SECONDS = 5.0
GRAPH_WINDOW_SECONDS = 2.0
FRAME_HISTORY_LENGTH = 5000  # 5 s at up to 1000 FPS
ONE_PERCENT = 0.01


class DebugPanel(enum.Enum):
    """Which panels the overlay draws; F4 cycles in declaration order."""

    ALL = 'all'
    COLLISION = 'collision'
    PHYSICS = 'physics'
    CAMERA = 'camera'
    PERFORMANCE = 'performance'


class DebugOverlay:
    """State for the engine's debug overlay (drawing lives in panels.py)."""

    def __init__(self, *, visible: bool = False) -> None:
        self.is_visible = visible
        self.panel = DebugPanel.ALL
        self._frame_times: collections.deque[float] = collections.deque(maxlen=FRAME_HISTORY_LENGTH)

    def toggle(self) -> None:
        self.is_visible = not self.is_visible

    def cycle_panel(self) -> None:
        panels = list(DebugPanel)
        self.panel = panels[(panels.index(self.panel) + 1) % len(panels)]

    def shows(self, panel: DebugPanel) -> bool:
        return self.panel in {DebugPanel.ALL, panel}

    def record_frame(self, *, frame_seconds: float) -> None:
        if frame_seconds > 0.0:
            self._frame_times.append(frame_seconds)

    def frame_times(self) -> list[float]:
        return list(self._frame_times)

    def current_fps(self) -> float | None:
        return 1.0 / self._frame_times[-1] if self._frame_times else None

    def _window(self, window_seconds: float) -> list[float]:
        selected: list[float] = []
        total = 0.0
        for frame_seconds in reversed(self._frame_times):
            if total + frame_seconds > window_seconds:
                break
            total += frame_seconds
            selected.append(frame_seconds)
        selected.reverse()
        return selected

    def one_percent_low_fps(self, *, window_seconds: float = PERFORMANCE_WINDOW_SECONDS) -> float | None:
        window = self._window(window_seconds)
        if not window:
            return None
        count = max(1, math.ceil(ONE_PERCENT * len(window)))
        slowest = sorted(window, reverse=True)[:count]
        return sum(1.0 / frame_seconds for frame_seconds in slowest) / count

    def graph_frame_times(self, *, window_seconds: float = GRAPH_WINDOW_SECONDS) -> list[float]:
        return self._window(window_seconds)
```

(Add full Google docstrings; ruff will require them.) `__init__.py` exports `DebugOverlay`, `DebugPanel`, `DebugDrawable`.

Note on the 1% low test: with 500 frames of 0.01 s the window total is exactly 5.0 s; floating-point accumulation may land just above 5.0 and drop one frame — if so, compare against a computed expected value from `overlay._window` or use `window_seconds=5.0 + 1e-9` in the implementation's comparison (prefer a tolerance constant `WINDOW_TOLERANCE_SECONDS = 1e-9` with a comment). Make the test deterministic either way.

- [ ] **Step 4: Run** — PASS. **Step 5:** lint/type-check, commit (`Add debug overlay state, protocols and frame history`).

---

### Task 3: Collision and physics panels

**Files:**
- Create: `glitchygames/debug/panels.py`, `tests/debug/test_panels_world.py`

**Interfaces:**
- Consumes: `get_sprite_collision_rect`, `Camera2D.apply`, `HasPhysicsBody`, constants from overlay.py.
- Produces:
  - `screen_rect_for(*, sprite: Any, camera: Camera2D, screen_offset: tuple[int, int]) -> pygame.Rect`: world rect via `get_sprite_collision_rect`; when the sprite has `world_x` and `world_y`, convert its top-left with `camera.apply(rect.x, rect.y)`; otherwise use it as-is (screen space); then add `screen_offset`.
  - `LAYER_PALETTE: tuple[tuple[int, int, int], ...]` (at least 8 distinct, readable colours), `OVERLAP_COLOR = (255, 255, 255)`, `UNLAYERED_COLOR = (90, 90, 90)`, `GROUNDED_COLOR = (60, 220, 60)`, `AIRBORNE_COLOR = (230, 60, 60)`, `ARROW_COLOR = (255, 220, 0)`.
  - `draw_collision_panel(*, surface, scene, camera, screen_offset, font) -> None`.
  - `draw_physics_panel(*, surface, scene, camera, screen_offset, font) -> None`.

- [ ] **Step 1: Failing tests** (real surfaces; build tiny real sprite classes with `world_x`, `world_y`, `rect`, and `physics` where needed; build a real `CollisionManager` with two layers; a `scene` can be a `types.SimpleNamespace(collisions=..., all_sprites=[...], camera=...)`):
  - Outline pixel at the converted position is the layer's palette colour (first layer → `LAYER_PALETTE[0]`), with the camera scrolled (`camera.world_x = 50`) so a sprite at world x=100 is outlined at screen x=50 (Review focus 1).
  - Two sprites in different layers overlapping → both outlines `OVERLAP_COLOR`; same-layer overlap stays the layer colour.
  - A sprite in `all_sprites` but in no layer → `UNLAYERED_COLOR` outline at its `rect`.
  - Legend: the panel writes one legend row per layer (assert via a mocked `font.render` called with text containing each layer name and its count).
  - `screen_offset=(5, 3)` shifts outlines by (5, 3).
  - Physics: velocity (300, 0) → arrow end 30 px right of the rect centre (0.1 s); velocity (5000, 0) → capped at 80 px; ground bar pixel green when `on_ground`, red when not; velocity text `(300, 0)` rendered.
  - A scene without `collisions` draws nothing in the collision panel and raises nothing.

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** `panels.py` with the functions above. Overlap detection uses the world rects (same space collision uses): `rect_a.colliderect(rect_b)` for sprites in different layers. Arrow: line from centre to centre + clamped vector, with a small two-line arrowhead. Use `pygame.draw.rect(surface, color, rect, width=1)`; text with the passed `font` (antialias False is fine) blitted next to the element.
- [ ] **Step 4: Run** — PASS. **Step 5:** lint/type-check, commit (`Add collision and physics debug panels`).

---

### Task 4: Camera and performance panels, hooks, and overlay drawing

**Files:**
- Modify: `glitchygames/debug/panels.py`, `glitchygames/debug/overlay.py`
- Create: `tests/debug/test_panels_hud.py`

**Interfaces:**
- Consumes: Task 2 state, Task 3 functions, `Camera2D.bounds`, `RumbleController.sent_levels`, `LiveAudio.playing_voice_count`.
- Produces:
  - `draw_camera_panel(*, surface, camera, screen_offset, font, mouse_position: tuple[int, int] | None, screen_shake_offset: tuple[float, float]) -> None`.
  - `draw_performance_panel(*, surface, overlay, font, target_fps: float, live_voice_count: int | None, rumble_levels: tuple[float, float]) -> None`.
  - `draw_mode_line(*, surface, font, panel: DebugPanel) -> None` (top centre: `DEBUG: <Panel title> (F3 off, F4 next)`).
  - `DebugOverlay.draw(surface, *, scene, screen_offset: tuple[int, int], target_fps: float, live_voice_count: int | None, rumble_levels: tuple[float, float], screen_shake_offset: tuple[float, float], mouse_position: tuple[int, int] | None) -> None` — creates the font lazily (`pygame.font.Font(None, 16)`, created on first call only), draws the panels it `shows`, the mode line, then hooks (not in `PERFORMANCE`).

- [ ] **Step 1: Failing tests:**
  - Camera: bounds lines drawn only for edges on screen (set `min_x=0` with camera at world_x=0 → a dashed line at screen x=0; `max_x=1000` with a 200 px screen → nothing drawn for it); lead crosshair at (`lead_x`, `lead_y`) + offset; mouse world text `= camera.world + mouse`; shake text only when either offset is non-zero; `mouse_position=None` draws no mouse text.
  - Performance: target 60 → line at 16.67 ms scaled; a 30 ms bar drawn in red, a 10 ms bar not red; target 0 → "uncapped" text and no target line; live voices line only when `live_voice_count` is not None; rumble line only when either level > 0; footnote text `overlay drawing included`.
  - Hooks: a scene implementing `debug_draw` and two sprites (one implementing it) → the scene's and that sprite's hooks are called once each with `(surface, camera)`; in `PERFORMANCE` mode no hook is called; a hook that raises → logged once (`mocker.patch` the module logger, assert one `exception`/`error` call) and not called again on the next draw (Review focus 4).
  - Lazy font: drawing while not visible is never requested by the manager, but `draw` itself creates the font only once across two calls (patch `pygame.font.Font`, assert called once).
  - Read-only: snapshot sprite rects, physics state and camera position, call `draw`, assert unchanged.

- [ ] **Step 2: RED.** **Step 3: Implement.** Disabled hooks are tracked by `id(obj)` in a set on the overlay; log with `log.exception('Debug hook %r failed; disabling it', obj)` once. Built-in panels do not catch errors. **Step 4:** PASS. **Step 5:** lint/type-check, commit (`Add camera and performance debug panels, hooks and overlay drawing`).

---

### Task 5: SceneManager integration, flag, keys, docs

**Files:**
- Modify: `glitchygames/scenes/scene.py` (`SceneManager.__init__` guard, `game_engine` setter, `_update_frame_services`, `_present_frame`, new `on_key_down_event`), `glitchygames/engine/game_engine.py` (Graphics Options: `--debug-overlay`), `CLAUDE.md`, `plans/engine-audit.md`
- Test: `tests/debug/test_scene_manager_overlay.py` (real surfaces; as built: `tests/debug/test_manager_overlay.py`), the engine argument test file

**Interfaces:**
- Consumes: `DebugOverlay`, `DebugOverlay.draw(...)`.
- Produces: `SceneManager.debug_overlay: DebugOverlay`.

- [ ] **Step 1: Failing tests:**
  - Flag: `--debug-overlay` defaults False; passing it sets True; the `game_engine` setter makes `debug_overlay.is_visible` match `OPTIONS.get('debug_overlay', False)`.
  - Keys: F3 key-down toggles and is NOT forwarded to the active scene; F4 cycles and is not forwarded; another key (e.g. `K_a`) is forwarded unchanged to `active_scene.on_key_down_event`; with a sprite whose `is_active` is True in `active_scene.all_sprites`, F3 is forwarded and does not toggle (Review focus 2).
  - Frame history: `_update_frame_services` calls `debug_overlay.record_frame(frame_seconds=self.dt)`.
  - Presentation (real 64×48 surfaces, `pygame.display.flip` patched with a side effect that inspects `manager.screen`):
    - visible overlay: at flip time the screen contains overlay pixels (e.g. the mode-line text area is not the background colour); after `_present_frame` returns, `manager.screen` equals the clean frame pixel-for-pixel;
    - hidden overlay: `DebugOverlay.draw` is not called (patch it, assert not called) and the existing update path is used;
    - after hiding a previously shown overlay, the next present is one full `flip` (Review focus 3);
    - with a SCREEN shake of (0, 4) active: `draw` receives `screen_offset=(0, 4)` and the flip-time frame is shifted; the restored screen is unshifted (Review focus 5);
    - `Scene.screenshot`-style capture (`manager.screen.copy()` after present) has no overlay pixels.
- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement.**
  - `__init__` (inside the `_initialized` guard): `self.debug_overlay = DebugOverlay()` and rename `_screen_shake_was_presented` to `_altered_frame_was_presented` (update its uses and comment: "a shaken or overlaid frame was presented").
  - `game_engine` setter: `self.debug_overlay.is_visible = bool(self.OPTIONS.get('debug_overlay', False))`.
  - `_update_frame_services`: first line `self.debug_overlay.record_frame(frame_seconds=self.dt)`.
  - `_present_frame`:

```python
        offset_x, offset_y = self.screen_shake.offset
        pixel_offset = (round(offset_x), round(offset_y))
        overlay_visible = self.debug_overlay.is_visible
        if self.screen is not None and (pixel_offset != (0, 0) or overlay_visible):
            clean_frame = self.screen.copy()
            if pixel_offset != (0, 0):
                self.screen.fill(SHAKE_BORDER_COLOR)
                self.screen.blit(clean_frame, pixel_offset)
            if overlay_visible and self.active_scene is not None:
                self.debug_overlay.draw(
                    self.screen,
                    scene=self.active_scene,
                    screen_offset=pixel_offset,
                    target_fps=float(self.target_fps),
                    live_voice_count=(
                        self._live_audio.playing_voice_count if self._live_audio is not None else None
                    ),
                    rumble_levels=self.rumble.sent_levels,
                    screen_shake_offset=(offset_x, offset_y),
                    mouse_position=pygame.mouse.get_pos() if pygame.mouse.get_focused() else None,
                )
            pygame.display.flip()
            self.screen.blit(clean_frame, (0, 0))
            self._altered_frame_was_presented = True
            return
        if self._altered_frame_was_presented:
            # The display still shows the last shifted or overlaid frame; the surface holds the
            # clean one, so one full flip replaces it (a dirty-rect update would not).
            self._altered_frame_was_presented = False
            pygame.display.flip()
            return
        ...  # unchanged: full_update flip or _update_display()
```

  - `on_key_down_event`:

```python
    def on_key_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the debug overlay keys, then forward key-down events to the active scene.

        F3 toggles the overlay and F4 cycles its panels, unless a sprite in the active scene has
        keyboard focus (is_active), so typing into text fields is never intercepted.
        """
        overlay_keys = {pygame.K_F3, pygame.K_F4}
        if event.key in overlay_keys and not self._active_scene_has_focused_sprite():
            if event.key == pygame.K_F3:
                self.debug_overlay.toggle()
            else:
                self.debug_overlay.cycle_panel()
            return
        if self.active_scene is not None:
            self.active_scene.on_key_down_event(event)
```

    plus `_active_scene_has_focused_sprite()` returning `any(getattr(sprite, 'is_active', False) is True for sprite in self.active_scene.all_sprites)` (False when there is no active scene). First check how key-down events currently reach the active scene (`SceneManager.__getattr__` ~line 655 forwards `on_*` to the active scene); make sure an explicit method doesn't break any other caller, and keep the forwarding behavior identical for every other key. Run `tests/scenes` and `tests/events` to confirm.
  - game_engine.py (Graphics Options, after `--fps-histogram`):

```python
        group.add_argument(
            '--debug-overlay',
            help='show the debug overlay at startup (F3 toggles, F4 cycles panels)',
            action='store_true',
            default=False,
        )
```

  - CLAUDE.md: add after the Transitions entry:

```markdown
**Debug Overlay** (`glitchygames/debug/`): `--debug-overlay` or F3 shows it, F4 cycles panels
(collision hitboxes by layer, physics velocities and ground state, camera bounds and mouse world
position, performance HUD with a frame-time graph). Drawn in `SceneManager._present_frame`, never in
screenshots. Scenes or sprites can add annotations with `debug_draw(surface, camera)`.
```

  - plans/engine-audit.md: item #12 status → `**Done** (feature/debug-overlay)` with the spec path.
- [ ] **Step 4: Run** the new tests, then `tests/scenes tests/events tests/engine tests/debug`, then lint, type checks and the full suite once.
- [ ] **Step 5: Commit** (`Integrate the debug overlay: F3/F4, --debug-overlay, present-frame drawing`).
- [ ] **Step 6: Manual check for the user** (report it; do not claim it was seen): `uv run clockwork-keep --debug-overlay`, press F4 through each panel, ride the elevator with it on (SCREEN shake), press F3 to hide; `uv run bitmappy`, type F3 into the AI prompt box and confirm it is typed, not toggled.
