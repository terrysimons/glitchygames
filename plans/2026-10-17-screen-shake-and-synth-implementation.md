# Screen Shake and Sound Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stackable screen shake with rumble and a three-layer sound synthesizer to the
GlitchyGames engine, fix the four bugs they depend on, and use both in Clockwork Keep's elevator
and gameplay.

**Architecture:** Pure-math modules (`effects/shake.py`, `audio/synth.py`, `audio/recipes.py`) sit
under thin engine integrations (`Camera2D`, `SceneManager`, `input/rumble.py`, `audio/live.py`).
`SceneManager` owns everything that must outlive a scene (screen shake, rumble, live voices) and
updates it once per main-loop pass in both the normal and transition branches.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8 (SDL 2.32), numpy, pytest + pytest-mock, uv.

**Spec:** `plans/2026-10-17-screen-shake-and-synth.md` (revision 2). Read it before starting; this
plan implements it and notes the three places where it refines it (Task 9 triangle wave, Task 11
sweep comparison, Task 6 end-of-shake redraw).

## Global Constraints

- Run everything through uv: `uv run pytest ...`, `uv run ruff check ...`, `uv run ruff format ...`,
  `uv run basedpyright ...`, `uv run ty check ...`.
- Lint and type-check the touched files before running tests. Fix the code; never add global lint
  ignores, never change linter/type-checker configuration, never delete or weaken a failing test.
- **Commit per task, never push.** Each task ends with a checkpoint: lint, type checks and the
  task's tests pass, then commit only that task's files (`git add <paths>`, never `git add -A` or
  `.`; the repo root holds many untracked scratch files that must never be committed) with a
  descriptive message ending in the Co-Authored-By line. Never `git push`, never amend or rebase
  existing commits, never restore files from git.
- Tests use the pytest-mock `mocker` fixture (never `unittest.mock` directly), pytest assertions,
  game time, and seeded randomness (`random.Random(seed)` for shake, `numpy.random.default_rng(seed)`
  for audio). No test may depend on chance or wall-clock time.
- Put new tests in an existing test file when one matches; the files named below say which.
- Code style: single quotes, Google-style docstrings, 100-character lines, full descriptive names
  (no abbreviations such as `freq`, `amp`, `idx`, `cb`), keyword arguments at call sites,
  `from __future__ import annotations` where the neighbors use it, `typing.Self` / `override` as
  the neighbors do. Read the comments in any code before changing it.
- Attribute any external reference used with a comment (PolyBLEP, the trauma model).
- Mixer facts (verified 2026-10-17): `pygame.init()` starts the mixer at `(44100, -16, 2)` with a
  512-sample buffer and 8 channels. `set_reserved(n)` reserves channels `0..n-1`.
  `Channel.stop()` and `Channel.fadeout()` start the channel's queued sound; a second `stop()`
  silences it. `set_num_channels(smaller)` stops the sound on removed channels. `Sound.play()`
  returns `None` when no unreserved channel is free.
- Test paths containing `scene` or `game_objects` get a Mock `pygame.mixer` from
  `tests/conftest.py:92-117` (`get_init()` returns `(22050, -16, 2)`).
- Option keys (argparse dests): `screen_shake_intensity`, `rumble_intensity`, `live_voice_pool`.
  Defaults: 1.0, 1.0, 4.

## Review Focus

1. A shake whose `duration` ends between frames (one large `dt` jumps past the end): offset and
   rumble must be exactly zero that frame, never a final jolt. Pinned in Task 4.
2. A game launched with `--live-voice-pool 0` or with no audio device: the elevator must still ride
   silently, never crash. Pinned in Task 13 (`ValueError` caught) and Task 14 (no-mixer ride).
3. Pausing (Esc or focus loss) during an active screen shake and then resuming: the pause screen
   must not shake and the resumed game must not jump. Pinned in Task 6 (`switch_to_scene` clears).
4. A controller unplugged mid-rumble (device list changes): rumble must skip missing devices
   without raising. Pinned in Task 7.
5. A frame hitch longer than a live chunk (loading, window drag): the motor must resume, not stay
   silent or crash. Pinned in Task 13 (underrun recovery).

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `glitchygames/camera.py` | modify | Parallax fix; owns WORLD `ScreenShake`; `shake_intensity` |
| `glitchygames/events/audio.py` | modify | Remove dead `pre_init`; survive no audio device |
| `glitchygames/effects/shake.py` | create | `Shake`, styles, `ScreenShake` math |
| `glitchygames/effects/__init__.py` | modify | Export shake names |
| `glitchygames/input/rumble.py` | create | `RumbleController`, device discovery |
| `glitchygames/scenes/scene.py` | modify | `SceneManager` screen shake, presentation, rumble, live audio, lifecycle; `Scene.camera`, `Scene.shake`, `Scene.apply_camera_to_sprites` |
| `glitchygames/engine/game_engine.py` | modify | Three new arguments; reserve the live voice pool |
| `glitchygames/transitions/base.py` | modify | `on_update`, `add_cue`, `eased_velocity_at` |
| `glitchygames/transitions/elevator.py` | modify | `on_update` pass-through; clamp eased progress |
| `glitchygames/audio/exceptions.py` | create | `AudioUnavailableError`, `SoundRecipeError` |
| `glitchygames/audio/synth.py` | create | Toolkit (layer A) |
| `glitchygames/audio/recipes.py` | create | `Tone`, `SoundRecipe`, TOML loader, `SoundBank` (layer B) |
| `glitchygames/audio/live.py` | create | Pool reservation, `LiveVoice`, `LiveAudio` (layer C) |
| `glitchygames/audio/__init__.py` | modify | Export new names |
| `glitchygames/examples/brave_adventurer/sounds.py` | modify | Port to the toolkit |
| `glitchygames/examples/clockwork_keep/sounds.py` | create | Recipes and bank |
| `glitchygames/examples/clockwork_keep/constants.py` | modify | Elevator tuning constants |
| `glitchygames/examples/clockwork_keep/game.py` | modify | Elevator fix, sounds, motor, shake, land edge |
| `tests/test_camera.py` | modify | Parallax and WORLD shake tests |
| `tests/events/test_audio_events.py` | modify | Mixer init tests |
| `tests/effects/test_shake.py` | create | Shake math + SceneManager presentation (real surfaces; a `tests/scenes` file would get mocked pygame) |
| `tests/input/test_rumble.py` | create | Rumble controller |
| `tests/scenes/test_scene_manager.py` | modify | Lifecycle, frame services, `Scene.shake` |
| `tests/engine/test_game_engine_args.py` or the existing engine argument test file | modify | New arguments |
| `tests/transitions/test_transitions.py` | modify | Hooks, clamp |
| `tests/audio/__init__.py`, `tests/audio/test_synth.py`, `tests/audio/test_recipes.py`, `tests/audio/test_live.py` | create | Audio layers (`tests/audio/` exists but is empty) |
| `tests/examples/test_brave_adventurer_sounds.py` + `tests/examples/brave_adventurer_golden/*.npy` | create | Migration goldens |
| `tests/examples/test_clockwork_keep.py` | create | Clockwork Keep behavior (no existing file) |
| `tests/mocks/test_mock_factory.py` | modify | Mixer mock returns real-shaped channel counts |
| `CLAUDE.md`, `BUGS.md` | modify | Docs |

---

### Task 1: Fix parallax scrolling (BUGS.md #21)

**Files:**
- Modify: `glitchygames/camera.py` (`Camera2D.update`, `Camera2D.snap_to`)
- Test: `tests/test_camera.py`

**Interfaces:**
- Produces: `Camera2D._update_parallax_layers(*, camera_x: float, camera_y: float) -> None`
  (private helper; Task 5 calls it with the shaken position).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_camera.py`; add `import pygame` at
  the top)

```python
class TestCamera2DParallax:
    """Parallax layers follow the camera (regression for BUGS.md #21)."""

    @staticmethod
    def _add_recording_layer(camera, mocker):
        if not pygame.get_init():
            pygame.init()
        layer = camera.add_background_layer(
            scroll_factor=0.5,
            draw_function=lambda surface, offset_x, offset_y: None,
            layer_depth=0,
            groups=pygame.sprite.LayeredDirty(),
        )
        return mocker.patch.object(layer, 'update_scroll')

    def test_update_scrolls_parallax_layers(self, mocker):
        """update() passes the new camera position to every parallax layer."""
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        update_scroll = self._add_recording_layer(camera, mocker)
        camera.update(target_x=300.0, target_y=40.0, dt=1.0 / 60.0)
        update_scroll.assert_called_once_with(
            pytest.approx(camera.world_x), pytest.approx(camera.world_y)
        )

    def test_snap_to_scrolls_parallax_layers_once(self, mocker):
        """snap_to() updates each layer exactly once (the duplicate loop is gone)."""
        camera = Camera2D(screen_width=200, screen_height=100)
        update_scroll = self._add_recording_layer(camera, mocker)
        camera.snap_to(target_x=120.0, target_y=30.0)
        update_scroll.assert_called_once_with(120.0, 30.0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_camera.py::TestCamera2DParallax -v`
Expected: `test_update_scrolls_parallax_layers` FAILS (not called); `test_snap_to...` FAILS (called
twice).

- [ ] **Step 3: Implement.** In `Camera2D.update`, after `self._clamp_to_bounds()`, add
  `self._update_parallax_layers(camera_x=self.world_x, camera_y=self.world_y)`. In `snap_to`,
  replace both parallax loops (and their comments) with one call to the same helper. Add:

```python
    def _update_parallax_layers(self, *, camera_x: float, camera_y: float) -> None:
        """Scroll every parallax layer to the given camera position.

        Args:
            camera_x: Camera X used for the parallax offset.
            camera_y: Camera Y used for the parallax offset.

        """
        for layer in self._parallax_layers:
            layer.update_scroll(camera_x, camera_y)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_camera.py -v` — Expected: all PASS.

- [ ] **Step 5: Checkpoint and commit.** `uv run ruff check glitchygames/camera.py tests/test_camera.py`,
  `uv run basedpyright glitchygames/camera.py`, `uv run ty check glitchygames/camera.py`. Report.

---

### Task 2: Mixer initialization (BUGS.md #22, #23)

**Files:**
- Modify: `glitchygames/events/audio.py:74-76`
- Test: `tests/events/test_audio_events.py` (class `TestAudioEventManager`)

- [ ] **Step 1: Write the failing tests**

```python
    def test_init_does_not_call_pre_init(self, mocker):
        """pre_init after pygame.init() never took effect, so it is not called (BUGS.md #22)."""
        pre_init = mocker.patch('pygame.mixer.pre_init')
        AudioEventManager(game=mocker.Mock())
        pre_init.assert_not_called()

    def test_init_survives_missing_audio_device(self, mocker):
        """No audio device logs a warning and continues silently (BUGS.md #23)."""
        mocker.patch('pygame.mixer.init', side_effect=pygame.error('no audio device'))
        mocker.patch('pygame.mixer.get_init', return_value=None)
        warning = mocker.patch('glitchygames.events.audio.log.warning')
        manager = AudioEventManager(game=mocker.Mock())
        assert len(manager.proxies) == 1
        assert warning.called
```

(Import `pygame` at the top of the test file if it is not already imported.)

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/events/test_audio_events.py::TestAudioEventManager -v`
Expected: both new tests FAIL.

- [ ] **Step 3: Implement.** Replace lines 74-76 with:

```python
        # pygame.init() has already started the mixer at its defaults (44100 Hz, signed
        # 16-bit, stereo, 512-sample buffer); init() only matters if that failed.
        try:
            pygame.mixer.init()
        except pygame.error as error:
            log.warning('Audio unavailable, running silently: %s', error)
```

The existing `get_init() is None` warning below stays.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/events/test_audio_events.py -v` — Expected: all PASS.

- [ ] **Step 5: Checkpoint and commit** (ruff, basedpyright, ty on `glitchygames/events/audio.py`). Report.

---

### Task 3: Clockwork Keep elevator is interact-only (BUGS.md #24) and test scaffolding

**Files:**
- Modify: `glitchygames/examples/clockwork_keep/game.py` (`_check_elevator`)
- Create: `tests/examples/test_clockwork_keep.py`

**Interfaces:**
- Produces fixture `clockwork_scene` (used by Task 14):
  `ClockworkKeepScene(options={'input_mode': 'joystick'})` on a real display.

- [ ] **Step 1: Write the failing test file**

```python
"""Tests for the Clockwork Keep example game."""

import pygame
import pytest

from glitchygames.events.base import HashableEvent
from glitchygames.examples.clockwork_keep.game import ClockworkKeepScene

FRAME_TIME = 1.0 / 60.0


@pytest.fixture
def clockwork_scene(mocker):
    """A floor-0 scene with transition_to recorded instead of performed."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 480))
    scene = ClockworkKeepScene(options={'input_mode': 'joystick'})
    mocker.patch.object(scene, 'transition_to')
    return scene


def _stand_on_first_elevator(scene):
    elevator = scene.elevator_sprites[0]
    scene.player.world_x = elevator.world_x + 5
    scene.player.world_y = elevator.world_y - scene.player.rect.height
    for _ in range(5):
        scene.dt_tick(FRAME_TIME)


def _press_key(scene, key):
    scene.on_key_down_event(
        HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=0)
    )


class TestElevatorActivation:
    """BUGS.md #24: interact rides the elevator, jump always jumps."""

    def test_interact_rides(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_w)
        clockwork_scene.dt_tick(FRAME_TIME)
        clockwork_scene.transition_to.assert_called_once()

    def test_jump_jumps_and_does_not_ride(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_SPACE)
        clockwork_scene.dt_tick(FRAME_TIME)
        assert clockwork_scene.player.velocity_y < 0
        clockwork_scene.transition_to.assert_not_called()

    def test_jump_while_held_never_rides(self, clockwork_scene):
        """Even if on_ground is restored before the check, jump alone never rides."""
        _stand_on_first_elevator(clockwork_scene)
        clockwork_scene.actions.handle_event(
            HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode='', scancode=0)
        )
        clockwork_scene._check_elevator()
        clockwork_scene.transition_to.assert_not_called()
```

- [ ] **Step 2: Run to verify** — `uv run pytest tests/examples/test_clockwork_keep.py -v`.
  Expected: `test_jump_while_held_never_rides` FAILS (rides); the others pass (they document the
  current behavior).

- [ ] **Step 3: Implement.** In `_check_elevator`:

```python
    def _check_elevator(self: Self) -> None:
        """Ride the elevator when the player stands on it and presses interact.

        Jump is deliberately not accepted: jumping clears on_ground before this check runs,
        so it could never ride (BUGS.md #24), and jump should always jump.
        """
        if not self.actions.just_pressed('interact'):
            return
```

Update the `Elevator` docstring in `terrain.py` ("presses up/interact") to "presses interact".

- [ ] **Step 4: Run** — all three PASS.
- [ ] **Step 5: Checkpoint and commit** (ruff, basedpyright, ty on `game.py`, `terrain.py`, the test). Report.

---

### Task 4: Shake math (`effects/shake.py`)

**Files:**
- Create: `glitchygames/effects/shake.py`
- Modify: `glitchygames/effects/__init__.py` (export `RumbleSettings`, `ScreenShake`, `Shake`,
  `ShakeAxis`, `ShakeStyle`, `ShakeTarget`)
- Test: `tests/effects/test_shake.py`

**Interfaces:**
- Produces:
  - `ShakeStyle(Enum)`: `NOISE`, `JITTER`, `BOUNCE`; `ShakeTarget(Flag)`: `WORLD`, `SCREEN`;
    `ShakeAxis(Enum)`: `BOTH`, `HORIZONTAL`, `VERTICAL`.
  - `RumbleSettings(low_frequency: float, high_frequency: float)` frozen dataclass.
  - `Shake(style, strength, duration, frequency, axis=ShakeAxis.BOTH, rumble=None)` frozen.
  - `ScreenShake(*, maximum_offset: float = 32.0, intensity: float = 1.0,
    random_source: random.Random | None = None)` with `add(shake)`, `update(dt)`, `clear()`,
    `is_active: bool`, `offset: tuple[float, float]`, `rumble_levels: tuple[float, float]`,
    `rumble_remaining: float`, settable validated `intensity`, read-only `maximum_offset`.
  - `DEFAULT_MAXIMUM_OFFSET = 32.0`.

- [ ] **Step 1: Write the failing tests** (`tests/effects/test_shake.py`)

```python
"""Tests for screen shake math."""

import math
import random

import pytest

from glitchygames.effects.shake import (
    RumbleSettings,
    ScreenShake,
    Shake,
    ShakeAxis,
    ShakeStyle,
)

SEED = 1234
ALL_STYLES = list(ShakeStyle)


def _shaker(**kwargs):
    return ScreenShake(random_source=random.Random(SEED), **kwargs)


class TestShakeValidation:
    @pytest.mark.parametrize(
        ('field', 'value'),
        [('strength', -1.0), ('duration', 0.0), ('duration', -0.1), ('frequency', 0.0)],
    )
    def test_invalid_values_raise(self, field, value):
        settings = {'style': ShakeStyle.NOISE, 'strength': 5.0, 'duration': 0.5,
                    'frequency': 10.0}
        settings[field] = value
        with pytest.raises(ValueError, match=field):
            Shake(**settings)

    @pytest.mark.parametrize('value', [-0.01, 1.01])
    def test_rumble_settings_range(self, value):
        with pytest.raises(ValueError, match='low_frequency'):
            RumbleSettings(low_frequency=value, high_frequency=0.5)

    @pytest.mark.parametrize('value', [-0.1, 1.1])
    def test_intensity_range(self, value):
        with pytest.raises(ValueError, match='intensity'):
            ScreenShake(intensity=value)


class TestShakeLifetime:
    @pytest.mark.parametrize('style', ALL_STYLES)
    def test_offset_is_zero_at_and_after_duration(self, style):
        shaker = _shaker()
        shaker.add(Shake(style=style, strength=10.0, duration=0.5, frequency=12.0))
        shaker.update(0.5)
        assert shaker.offset == (0.0, 0.0)
        assert not shaker.is_active

    @pytest.mark.parametrize('style', ALL_STYLES)
    def test_one_large_dt_past_the_end_leaves_no_jolt(self, style):
        """Review focus 1: a dt that jumps past the end gives zero, never a final offset."""
        shaker = _shaker()
        shaker.add(Shake(style=style, strength=10.0, duration=0.2, frequency=12.0,
                         rumble=RumbleSettings(low_frequency=1.0, high_frequency=1.0)))
        shaker.update(0.15)
        shaker.update(0.5)
        assert shaker.offset == (0.0, 0.0)
        assert shaker.rumble_levels == (0.0, 0.0)
        assert shaker.rumble_remaining == 0.0

    @pytest.mark.parametrize('style', ALL_STYLES)
    def test_offset_never_exceeds_strength(self, style):
        shaker = _shaker()
        shaker.add(Shake(style=style, strength=10.0, duration=1.0, frequency=9.0))
        for _ in range(60):
            shaker.update(1.0 / 60.0)
            offset_x, offset_y = shaker.offset
            assert abs(offset_x) <= 10.0 + 1e-9
            assert abs(offset_y) <= 10.0 + 1e-9

    def test_clear_stops_everything(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=5.0, duration=1.0, frequency=30.0))
        shaker.clear()
        assert shaker.offset == (0.0, 0.0)
        assert not shaker.is_active


class TestShakeStyles:
    def test_bounce_starts_at_full_strength_and_decays_to_one_percent(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.BOUNCE, strength=10.0, duration=1.0, frequency=5.0,
                         axis=ShakeAxis.VERTICAL))
        assert shaker.offset == pytest.approx((0.0, 10.0))
        shaker.update(0.999999)
        assert abs(shaker.offset[1]) <= 0.1 + 1e-6

    def test_noise_magnitude_follows_remaining_squared(self):
        """Trauma model: the envelope is remaining**2 (offset bounded by it)."""
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.NOISE, strength=10.0, duration=1.0, frequency=20.0))
        shaker.update(0.5)
        bound = 10.0 * 0.5**2
        assert max(abs(value) for value in shaker.offset) <= bound + 1e-9

    def test_noise_is_smooth_between_frames(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.NOISE, strength=10.0, duration=2.0, frequency=4.0))
        previous = shaker.offset
        for _ in range(30):
            shaker.update(1.0 / 240.0)
            current = shaker.offset
            assert math.dist(previous, current) < 2.0
            previous = current

    def test_jitter_holds_value_within_a_step(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=10.0, duration=10.0, frequency=1.0))
        shaker.update(0.1)
        first = shaker.offset
        shaker.update(0.1)
        second = shaker.offset
        # Same step: same direction, magnitude shrinks only by the linear decay
        assert first[0] * second[0] >= 0
        assert first[1] * second[1] >= 0

    @pytest.mark.parametrize(
        ('axis', 'zero_index'), [(ShakeAxis.HORIZONTAL, 1), (ShakeAxis.VERTICAL, 0)]
    )
    def test_axis_restricts_movement(self, axis, zero_index):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=10.0, duration=1.0, frequency=30.0,
                         axis=axis))
        shaker.update(0.01)
        assert shaker.offset[zero_index] == 0.0

    def test_same_seed_same_offsets(self):
        offsets = []
        for _ in range(2):
            shaker = _shaker()
            shaker.add(Shake(style=ShakeStyle.NOISE, strength=8.0, duration=1.0, frequency=10.0))
            shaker.update(0.3)
            offsets.append(shaker.offset)
        assert offsets[0] == offsets[1]


class TestStackingAndLimits:
    def test_offsets_sum(self):
        single = _shaker()
        single.add(Shake(style=ShakeStyle.BOUNCE, strength=5.0, duration=1.0, frequency=2.0))
        double = _shaker()
        for _ in range(2):
            double.add(Shake(style=ShakeStyle.BOUNCE, strength=5.0, duration=1.0, frequency=2.0))
        assert double.offset == pytest.approx(tuple(2 * value for value in single.offset))

    def test_cap_holds_for_any_stack(self):
        shaker = _shaker(maximum_offset=12.0)
        for style in ALL_STYLES:
            for _ in range(5):
                shaker.add(Shake(style=style, strength=30.0, duration=1.0, frequency=7.0))
        for _ in range(30):
            shaker.update(1.0 / 60.0)
            assert all(abs(value) <= 12.0 for value in shaker.offset)

    def test_intensity_scales_and_zero_disables(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.BOUNCE, strength=10.0, duration=1.0, frequency=2.0))
        full = shaker.offset
        shaker.intensity = 0.5
        assert shaker.offset == pytest.approx(tuple(value / 2 for value in full))
        shaker.intensity = 0.0
        assert shaker.offset == (0.0, 0.0)


class TestRumbleLevels:
    def test_per_motor_maximum_scaled_by_decay_and_strength(self):
        shaker = _shaker(maximum_offset=20.0)
        shaker.add(Shake(style=ShakeStyle.BOUNCE, strength=10.0, duration=1.0, frequency=2.0,
                         rumble=RumbleSettings(low_frequency=1.0, high_frequency=0.2)))
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=20.0, duration=0.5, frequency=2.0,
                         rumble=RumbleSettings(low_frequency=0.1, high_frequency=0.8)))
        low, high = shaker.rumble_levels
        assert low == pytest.approx(1.0 * 1.0 * (10.0 / 20.0))
        assert high == pytest.approx(0.8 * 1.0 * 1.0)

    def test_remaining_is_longest_rumbling_shake(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.NOISE, strength=5.0, duration=0.3, frequency=5.0,
                         rumble=RumbleSettings(low_frequency=0.5, high_frequency=0.5)))
        shaker.add(Shake(style=ShakeStyle.NOISE, strength=5.0, duration=0.9, frequency=5.0))
        shaker.update(0.1)
        assert shaker.rumble_remaining == pytest.approx(0.2)

    def test_rumble_decays_with_its_shake(self):
        shaker = _shaker(maximum_offset=10.0)
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=10.0, duration=1.0, frequency=5.0,
                         rumble=RumbleSettings(low_frequency=1.0, high_frequency=1.0)))
        shaker.update(0.75)
        assert shaker.rumble_levels == pytest.approx((0.25, 0.25))
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/effects/test_shake.py -v`
  Expected: ImportError (module missing).

- [ ] **Step 3: Implement `glitchygames/effects/shake.py`**

```python
"""Stackable screen shake with optional controller rumble levels.

Pure math: no display or controller code. Camera2D applies a ScreenShake to world sprites;
SceneManager applies another to the whole presented frame.

The NOISE style follows the trauma model from Squirrel Eiserloh, "Juicing Your Cameras With
Math", GDC 2016: the visible magnitude scales with the square of the remaining shake, so big
hits feel much heavier than small ones and every shake eases out smoothly.
"""

from __future__ import annotations

import dataclasses
import enum
import math
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random

DEFAULT_MAXIMUM_OFFSET = 32.0
# BOUNCE amplitude remaining at the end of its duration (1% of strength)
BOUNCE_FINAL_AMPLITUDE_FRACTION = 0.01


class ShakeStyle(enum.Enum):
    """How a shake moves."""

    NOISE = 'noise'  # Smooth, heavy wobble (trauma model)
    JITTER = 'jitter'  # Random snap to a new offset every 1/frequency seconds
    BOUNCE = 'bounce'  # Damped spring that starts with a full-strength push


class ShakeTarget(enum.Flag):
    """What a shake moves. Combine with | to shake both."""

    WORLD = enum.auto()  # Camera-transformed sprites; HUD stays still
    SCREEN = enum.auto()  # The whole presented frame, including HUD and transitions


class ShakeAxis(enum.Enum):
    """Which axes a shake moves along."""

    BOTH = 'both'
    HORIZONTAL = 'horizontal'
    VERTICAL = 'vertical'


@dataclasses.dataclass(frozen=True)
class RumbleSettings:
    """Controller motor intensities (0.0-1.0) at full shake strength."""

    low_frequency: float
    high_frequency: float

    def __post_init__(self) -> None:
        """Validate motor intensities.

        Raises:
            ValueError: If either intensity is outside 0.0-1.0.

        """
        for field_name in ('low_frequency', 'high_frequency'):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                message = f'{field_name} must be between 0.0 and 1.0, got {value}'
                raise ValueError(message)


@dataclasses.dataclass(frozen=True)
class Shake:
    """One shake's settings."""

    style: ShakeStyle
    strength: float  # Peak offset in pixels
    duration: float  # Seconds
    frequency: float  # Hz
    axis: ShakeAxis = ShakeAxis.BOTH
    rumble: RumbleSettings | None = None

    def __post_init__(self) -> None:
        """Validate the settings.

        Raises:
            ValueError: If strength is negative or duration/frequency are not positive.

        """
        if self.strength < 0.0:
            message = f'strength must be >= 0, got {self.strength}'
            raise ValueError(message)
        if self.duration <= 0.0:
            message = f'duration must be > 0, got {self.duration}'
            raise ValueError(message)
        if self.frequency <= 0.0:
            message = f'frequency must be > 0, got {self.frequency}'
            raise ValueError(message)


class _ActiveShake:
    """One running shake: elapsed time plus the style's random state."""

    def __init__(self, *, shake: Shake, random_source: random.Random) -> None:
        self.shake = shake
        self.elapsed = 0.0
        self._random_source = random_source
        self._noise_lattice_horizontal: dict[int, float] = {}
        self._noise_lattice_vertical: dict[int, float] = {}
        self._jitter_step = -1
        self._jitter_horizontal = 0.0
        self._jitter_vertical = 0.0
        self._bounce_damping = -math.log(BOUNCE_FINAL_AMPLITUDE_FRACTION) / shake.duration

    @property
    def finished(self) -> bool:
        """True once elapsed time reaches the duration."""
        return self.elapsed >= self.shake.duration

    @property
    def remaining_time(self) -> float:
        """Seconds left, never negative."""
        return max(0.0, self.shake.duration - self.elapsed)

    def decay(self) -> float:
        """Envelope multiplier for offset and rumble (exactly 0.0 when finished).

        Returns:
            The style's decay factor at the current elapsed time.

        """
        if self.finished:
            return 0.0
        remaining_fraction = 1.0 - self.elapsed / self.shake.duration
        match self.shake.style:
            case ShakeStyle.NOISE:
                return remaining_fraction**2
            case ShakeStyle.JITTER:
                return remaining_fraction
            case ShakeStyle.BOUNCE:
                return math.exp(-self._bounce_damping * self.elapsed)

    def offset(self) -> tuple[float, float]:
        """Current offset in pixels before intensity and the cap.

        Returns:
            The (horizontal, vertical) offset.

        """
        if self.finished:
            return (0.0, 0.0)
        magnitude = self.shake.strength * self.decay()
        unit_horizontal, unit_vertical = self._unit_direction()
        horizontal = unit_horizontal * magnitude
        vertical = unit_vertical * magnitude
        match self.shake.axis:
            case ShakeAxis.HORIZONTAL:
                return (horizontal, 0.0)
            case ShakeAxis.VERTICAL:
                return (0.0, vertical)
            case ShakeAxis.BOTH:
                return (horizontal, vertical)

    def _unit_direction(self) -> tuple[float, float]:
        position = self.elapsed * self.shake.frequency
        match self.shake.style:
            case ShakeStyle.NOISE:
                return (
                    self._value_noise(lattice=self._noise_lattice_horizontal, position=position),
                    self._value_noise(lattice=self._noise_lattice_vertical, position=position),
                )
            case ShakeStyle.JITTER:
                step = math.floor(position)
                if step != self._jitter_step:
                    self._jitter_step = step
                    self._jitter_horizontal = self._random_source.uniform(-1.0, 1.0)
                    self._jitter_vertical = self._random_source.uniform(-1.0, 1.0)
                return (self._jitter_horizontal, self._jitter_vertical)
            case ShakeStyle.BOUNCE:
                wave = math.cos(2.0 * math.pi * position)
                return (wave, wave)

    def _value_noise(self, *, lattice: dict[int, float], position: float) -> float:
        """Smooth 1D value noise in [-1, 1]: random lattice values, smoothstep between them.

        Returns:
            The interpolated noise value.

        """
        left = math.floor(position)
        fraction = position - left
        left_value = self._lattice_value(lattice=lattice, index=left)
        right_value = self._lattice_value(lattice=lattice, index=left + 1)
        smoothed = fraction * fraction * (3.0 - 2.0 * fraction)
        return left_value + (right_value - left_value) * smoothed

    def _lattice_value(self, *, lattice: dict[int, float], index: int) -> float:
        if index not in lattice:
            lattice[index] = self._random_source.uniform(-1.0, 1.0)
        return lattice[index]


class ScreenShake:
    """Sums any number of active shakes into one capped offset."""

    def __init__(
        self,
        *,
        maximum_offset: float = DEFAULT_MAXIMUM_OFFSET,
        intensity: float = 1.0,
        random_source: random.Random | None = None,
    ) -> None:
        """Initialize with no active shakes.

        Args:
            maximum_offset: Per-axis cap on the summed offset, in pixels (> 0).
            intensity: Player setting 0.0-1.0 multiplying every offset (0 disables).
            random_source: Randomness for NOISE and JITTER; seed it in tests.

        Raises:
            ValueError: If maximum_offset is not positive.

        """
        if maximum_offset <= 0.0:
            message = f'maximum_offset must be > 0, got {maximum_offset}'
            raise ValueError(message)
        self._maximum_offset = maximum_offset
        self._intensity = 1.0
        self.intensity = intensity
        self._random_source: random.Random = random_source or secrets.SystemRandom()
        self._active: list[_ActiveShake] = []

    @property
    def maximum_offset(self) -> float:
        """Per-axis cap on the summed offset, in pixels."""
        return self._maximum_offset

    @property
    def intensity(self) -> float:
        """Player setting 0.0-1.0 multiplying every offset."""
        return self._intensity

    @intensity.setter
    def intensity(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            message = f'intensity must be between 0.0 and 1.0, got {value}'
            raise ValueError(message)
        self._intensity = value

    @property
    def is_active(self) -> bool:
        """True while any shake is running."""
        return bool(self._active)

    def add(self, shake: Shake) -> None:
        """Start a shake; it stacks with any already running.

        Args:
            shake: The shake to start.

        """
        self._active.append(_ActiveShake(shake=shake, random_source=self._random_source))

    def update(self, dt: float) -> None:
        """Advance every shake by game time and drop finished ones.

        Args:
            dt: Seconds since the last update.

        """
        for active_shake in self._active:
            active_shake.elapsed += dt
        self._active = [shake for shake in self._active if not shake.finished]

    def clear(self) -> None:
        """Stop every shake immediately."""
        self._active.clear()

    @property
    def offset(self) -> tuple[float, float]:
        """Summed offset times intensity, each axis clamped to +/- maximum_offset."""
        if self._intensity == 0.0 or not self._active:
            return (0.0, 0.0)
        offsets = [shake.offset() for shake in self._active]
        horizontal = sum(offset[0] for offset in offsets) * self._intensity
        vertical = sum(offset[1] for offset in offsets) * self._intensity
        limit = self._maximum_offset
        return (max(-limit, min(limit, horizontal)), max(-limit, min(limit, vertical)))

    @property
    def rumble_levels(self) -> tuple[float, float]:
        """Per-motor maximum over rumbling shakes of value x decay x strength fraction."""
        low = 0.0
        high = 0.0
        for active_shake in self._active:
            rumble = active_shake.shake.rumble
            if rumble is None:
                continue
            scale = active_shake.decay() * min(
                1.0, active_shake.shake.strength / self._maximum_offset
            )
            low = max(low, rumble.low_frequency * scale)
            high = max(high, rumble.high_frequency * scale)
        return (low, high)

    @property
    def rumble_remaining(self) -> float:
        """Longest remaining time among shakes that rumble (0.0 if none)."""
        return max(
            (shake.remaining_time for shake in self._active if shake.shake.rumble is not None),
            default=0.0,
        )
```

Note on `offset()`: `_ActiveShake.offset()` lazily draws JITTER/NOISE random values, but once
drawn they are a pure function of `elapsed`, so reading `ScreenShake.offset` several times in one
frame returns the same value.

- [ ] **Step 4: Run** — `uv run pytest tests/effects/test_shake.py -v` — Expected: all PASS.
  If `test_bounce_starts...` fails on sign, check that BOUNCE at `t=0` returns `cos(0) = 1`.

- [ ] **Step 5: Checkpoint and commit** (ruff, basedpyright, ty on `glitchygames/effects/`). Report.

---

### Task 5: WORLD shake in `Camera2D`

**Files:**
- Modify: `glitchygames/camera.py`
- Test: `tests/test_camera.py`

**Interfaces:**
- Consumes: `ScreenShake`, `_update_parallax_layers` (Tasks 1, 4).
- Produces: `Camera2D(..., shake_intensity: float = 1.0)`, attribute
  `shake_effect: ScreenShake`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_camera.py`)

```python
from glitchygames.effects.shake import Shake, ShakeAxis, ShakeStyle


def _bounce(strength=10.0):
    return Shake(style=ShakeStyle.BOUNCE, strength=strength, duration=1.0, frequency=2.0,
                 axis=ShakeAxis.VERTICAL)


class TestCamera2DShake:
    def test_apply_includes_shake_offset(self):
        camera = Camera2D(screen_width=200, screen_height=100)
        camera.shake_effect.add(_bounce())
        assert camera.apply(50.0, 50.0) == (50, 40)

    def test_update_advances_shake(self):
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        camera.shake_effect.add(_bounce())
        camera.update(target_x=0.0, target_y=0.0, dt=1.0)
        assert not camera.shake_effect.is_active

    def test_world_position_is_unshaken(self):
        """Collision and visibility use world_x/world_y, which shake never changes."""
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        camera.shake_effect.add(_bounce())
        camera.update(target_x=30.0, target_y=0.0, dt=1.0 / 60.0)
        assert camera.world_x == pytest.approx(30.0, abs=0.1)

    def test_shake_intensity_zero_disables(self):
        camera = Camera2D(screen_width=200, screen_height=100, shake_intensity=0.0)
        camera.shake_effect.add(_bounce())
        assert camera.apply(50.0, 50.0) == (50, 50)

    def test_parallax_receives_shaken_position(self, mocker):
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        update_scroll = TestCamera2DParallax._add_recording_layer(camera, mocker)
        camera.shake_effect.add(_bounce())
        camera.update(target_x=0.0, target_y=0.0, dt=0.0)
        update_scroll.assert_called_once_with(pytest.approx(0.0), pytest.approx(10.0))

    def test_snap_to_ignores_shake(self, mocker):
        camera = Camera2D(screen_width=200, screen_height=100)
        update_scroll = TestCamera2DParallax._add_recording_layer(camera, mocker)
        camera.shake_effect.add(_bounce())
        camera.snap_to(target_x=0.0, target_y=0.0)
        update_scroll.assert_called_once_with(0.0, 0.0)
```

- [ ] **Step 2: Run** — FAIL (`shake_effect` missing).

- [ ] **Step 3: Implement.** In `Camera2D.__init__` add the keyword `shake_intensity: float = 1.0`
  (document it in the class docstring Args) and
  `self.shake_effect: ScreenShake = ScreenShake(intensity=shake_intensity)`. In `update`, after
  `_clamp_to_bounds()`:

```python
        self.shake_effect.update(dt)
        shake_x, shake_y = self.shake_effect.offset
        # Layers scroll from the shaken position, so each shakes in proportion to its
        # scroll_factor: a static sky never shakes, distant scenery barely moves.
        self._update_parallax_layers(camera_x=self.world_x + shake_x,
                                     camera_y=self.world_y + shake_y)
```

(This replaces the Task 1 call.) `snap_to` keeps the unshaken call. `apply` becomes:

```python
        shake_x, shake_y = self.shake_effect.offset
        return (
            round(world_x - self.world_x - shake_x),
            round(world_y - self.world_y - shake_y),
        )
```

Note the sign: a positive vertical offset moves sprites up (40 from 50), and the parallax layer
receives `camera_y + offset`, which also moves its drawing up — the two agree.

- [ ] **Step 4: Run** — `uv run pytest tests/test_camera.py -v` — all PASS.
- [ ] **Step 5: Checkpoint and commit.** Report.

---

### Task 6: Engine arguments and SCREEN shake in `SceneManager`

**Files:**
- Modify: `glitchygames/engine/game_engine.py` (Graphics Options group)
- Modify: `glitchygames/scenes/scene.py` (`SceneManager.__init__`, `game_engine` setter, main
  loop, `switch_to_scene`, `_start_transition`; `Scene.__init__`, new
  `Scene.apply_camera_to_sprites`)
- Test: `tests/effects/test_shake.py` (presentation, real surfaces),
  `tests/scenes/test_scene_manager.py` (lifecycle), the existing engine argument tests (find with
  `grep -rln "update_type\|--target-fps" tests/engine`)

**Interfaces:**
- Produces:
  - `glitchygames.engine.game_engine.unit_interval(value: str) -> float` and
    `non_negative_int(value: str) -> int` (argparse types; raise `argparse.ArgumentTypeError`).
  - `SceneManager.screen_shake: ScreenShake`, `SceneManager._present_frame(*, full_update: bool)`,
    `SceneManager._update_frame_services()`.
  - `Scene.camera: Camera2D | None = None`, `Scene.apply_camera_to_sprites() -> None` (default
    no-op; games that position sprites with a camera override it).
  - `SHAKE_BORDER_COLOR = (0, 0, 0)` in `scene.py`.

- [ ] **Step 1: Write the failing argument tests** (in the existing engine argument test file)

```python
import argparse

import pytest

from glitchygames.engine.game_engine import non_negative_int, unit_interval


class TestShakeAndAudioArguments:
    @pytest.mark.parametrize(('text', 'expected'), [('0', 0.0), ('0.5', 0.5), ('1', 1.0)])
    def test_unit_interval_accepts_range(self, text, expected):
        assert unit_interval(text) == expected

    @pytest.mark.parametrize('text', ['-0.01', '1.01', 'abc', 'nan'])
    def test_unit_interval_rejects(self, text):
        with pytest.raises(argparse.ArgumentTypeError):
            unit_interval(text)

    @pytest.mark.parametrize('text', ['-1', '1.5', 'x'])
    def test_non_negative_int_rejects(self, text):
        with pytest.raises(argparse.ArgumentTypeError):
            non_negative_int(text)

    def test_defaults(self):
        parser = argparse.ArgumentParser()
        GameEngine.args(parser)  # use whatever the existing tests call to register arguments
        options = vars(parser.parse_args([]))
        assert options['screen_shake_intensity'] == 1.0
        assert options['rumble_intensity'] == 1.0
        assert options['live_voice_pool'] == 4
```

(Match the existing file's way of building the parser; if it calls a different method than
`GameEngine.args`, use that.)

- [ ] **Step 2: Implement the arguments.** In `game_engine.py` add module-level constants
  `DEFAULT_SCREEN_SHAKE_INTENSITY = 1.0`, `DEFAULT_RUMBLE_INTENSITY = 1.0`,
  `DEFAULT_LIVE_VOICE_POOL = 4`, and:

```python
def unit_interval(value: str) -> float:
    """Argparse type: a float from 0.0 to 1.0 inclusive.

    Args:
        value: The command-line text.

    Returns:
        The parsed float.

    Raises:
        argparse.ArgumentTypeError: If the text is not a number in 0.0-1.0.

    """
    try:
        number = float(value)
    except ValueError as error:
        message = f'{value!r} is not a number'
        raise argparse.ArgumentTypeError(message) from error
    if not 0.0 <= number <= 1.0:  # Also rejects NaN, which fails every comparison
        message = f'{value!r} must be between 0.0 and 1.0'
        raise argparse.ArgumentTypeError(message)
    return number


def non_negative_int(value: str) -> int:
    """Argparse type: an integer >= 0.

    Args:
        value: The command-line text.

    Returns:
        The parsed integer.

    Raises:
        argparse.ArgumentTypeError: If the text is not an integer >= 0.

    """
    try:
        number = int(value)
    except ValueError as error:
        message = f'{value!r} is not an integer'
        raise argparse.ArgumentTypeError(message) from error
    if number < 0:
        message = f'{value!r} must be >= 0'
        raise argparse.ArgumentTypeError(message)
    return number
```

In the Graphics Options group, after `--perf-trim-percent`:

```python
        group.add_argument(
            '--screen-shake-intensity',
            type=unit_interval,
            help='screen shake strength from 0.0 (off) to 1.0 (default: 1.0)',
            default=DEFAULT_SCREEN_SHAKE_INTENSITY,
        )
        group.add_argument(
            '--rumble-intensity',
            type=unit_interval,
            help='controller rumble strength from 0.0 (off) to 1.0 (default: 1.0)',
            default=DEFAULT_RUMBLE_INTENSITY,
        )
        group.add_argument(
            '--live-voice-pool',
            type=non_negative_int,
            help='mixer channels reserved for real-time synth voices (default: 4)',
            default=DEFAULT_LIVE_VOICE_POOL,
        )
```

Run the argument tests: PASS.

- [ ] **Step 3: Write the failing presentation tests** (append to `tests/effects/test_shake.py`;
  this file is outside `tests/scenes`, so surfaces are real)

```python
import pygame

from glitchygames.scenes import SceneManager


@pytest.fixture
def scene_manager_with_screen(mocker):
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 48))
    manager = SceneManager()
    manager.screen = pygame.Surface((64, 48))
    manager.active_scene = mocker.Mock(rects=[])
    flip = mocker.patch('pygame.display.flip')
    update = mocker.patch('pygame.display.update')
    yield manager, flip, update
    manager.screen_shake.clear()


class TestScreenShakePresentation:
    def _paint_marker(self, screen):
        screen.fill((0, 0, 255))
        screen.set_at((10, 10), (255, 0, 0))

    def test_shaken_frame_is_presented_shifted_and_screen_restored(
        self, scene_manager_with_screen, mocker
    ):
        manager, flip, _update = scene_manager_with_screen
        self._paint_marker(manager.screen)
        manager.screen_shake.add(Shake(style=ShakeStyle.BOUNCE, strength=4.0, duration=1.0,
                                       frequency=1.0, axis=ShakeAxis.VERTICAL))
        presented = {}

        def capture_flip():
            presented['marker_moved'] = manager.screen.get_at((10, 14))[:3] == (255, 0, 0)
            presented['top_strip_black'] = manager.screen.get_at((30, 1))[:3] == (0, 0, 0)

        flip.side_effect = capture_flip
        manager._present_frame(full_update=False)
        assert presented == {'marker_moved': True, 'top_strip_black': True}
        # Between presents the display surface holds the unshifted frame
        assert manager.screen.get_at((10, 10))[:3] == (255, 0, 0)
        assert manager.screen.get_at((30, 1))[:3] == (0, 0, 255)

    def test_first_frame_after_shake_is_a_full_flip(self, scene_manager_with_screen):
        manager, flip, update = scene_manager_with_screen
        manager.screen_shake.add(Shake(style=ShakeStyle.BOUNCE, strength=4.0, duration=0.1,
                                       frequency=1.0))
        manager._present_frame(full_update=False)
        manager.screen_shake.update(0.2)
        flip.reset_mock()
        manager._present_frame(full_update=False)
        flip.assert_called_once()
        update.assert_not_called()
        flip.reset_mock()
        manager._present_frame(full_update=False)  # Back to normal dirty-rect updates
        flip.assert_not_called()

    def test_unshaken_frame_uses_existing_update_path(self, scene_manager_with_screen, mocker):
        manager, flip, _update = scene_manager_with_screen
        update_display = mocker.patch.object(manager, '_update_display')
        manager._present_frame(full_update=False)
        update_display.assert_called_once()
        flip.assert_not_called()
```

- [ ] **Step 4: Write the failing lifecycle tests** (in `tests/scenes/test_scene_manager.py`,
  inside its existing SceneManager test class, using its `self.scene_manager`)

```python
    def test_switch_to_scene_clears_screen_shake(self, mocker):
        """Review focus 3: pause and game over never inherit a running screen shake."""
        from glitchygames.effects.shake import Shake, ShakeStyle

        self.scene_manager.screen_shake.add(
            Shake(style=ShakeStyle.NOISE, strength=5.0, duration=1.0, frequency=5.0)
        )
        self.scene_manager.switch_to_scene(mocker.Mock())
        assert not self.scene_manager.screen_shake.is_active

    def test_frame_services_advance_screen_shake(self):
        from glitchygames.effects.shake import Shake, ShakeStyle

        self.scene_manager.screen_shake.add(
            Shake(style=ShakeStyle.NOISE, strength=5.0, duration=0.5, frequency=5.0)
        )
        self.scene_manager.dt = 1.0
        self.scene_manager._update_frame_services()
        assert not self.scene_manager.screen_shake.is_active

    def test_game_engine_options_set_shake_intensity(self, mocker):
        engine = mocker.Mock()
        engine.OPTIONS = {'update_type': 'update', 'fps_log_interval_ms': 1000,
                          'screen_shake_intensity': 0.25, 'rumble_intensity': 0.5}
        self.scene_manager.game_engine = engine
        assert self.scene_manager.screen_shake.intensity == 0.25
```

- [ ] **Step 5: Run both test groups** — FAIL (`screen_shake` / `_present_frame` missing).

- [ ] **Step 6: Implement in `scene.py`.**
  - Imports: `from glitchygames.camera import Camera2D` and
    `from glitchygames.effects.shake import ScreenShake` (move to `TYPE_CHECKING` only if an import
    cycle appears; `camera.py` imports `glitchygames.sprites`, not scenes).
  - Constant: `SHAKE_BORDER_COLOR = (0, 0, 0)  # Fills the strips a SCREEN shake uncovers`.
  - `SceneManager.__init__`: `self.screen_shake = ScreenShake()` and
    `self._screen_shake_was_presented = False`.
  - `game_engine` setter, inside `if self._game_engine:`:
    `self.screen_shake.intensity = self.OPTIONS.get('screen_shake_intensity', 1.0)`.
  - `switch_to_scene`, first line inside `if scene != self.active_scene:`:
    `self.screen_shake.clear()  # Pause, game over and direct switches never inherit a shake`.
  - Add:

```python
    def _update_frame_services(self: Self) -> None:
        """Advance services that outlive scenes: screen shake (rumble and live audio join later)."""
        self.screen_shake.update(self.dt)

    def _present_frame(self: Self, *, full_update: bool) -> None:
        """Present the rendered frame, shifted by any active SCREEN shake.

        The display surface always holds the unshifted frame between presents: a shaken frame
        is copied, shifted for the flip, then restored. Dirty-rect rendering, screenshots and
        transition captures therefore never see the shift or the black strips.

        Args:
            full_update: True to flip the whole display (transitions); False to use the
                configured update type.

        """
        offset_x, offset_y = self.screen_shake.offset
        pixel_offset = (round(offset_x), round(offset_y))
        if self.screen is not None and pixel_offset != (0, 0):
            unshifted = self.screen.copy()
            self.screen.fill(SHAKE_BORDER_COLOR)
            self.screen.blit(unshifted, pixel_offset)
            pygame.display.flip()
            self.screen.blit(unshifted, (0, 0))
            self._screen_shake_was_presented = True
            return
        if self._screen_shake_was_presented:
            # The display still shows the last shifted frame; the surface holds the correct
            # unshifted one, so one full flip replaces it (a dirty-rect update would not).
            self._screen_shake_was_presented = False
            pygame.display.flip()
            return
        if full_update:
            pygame.display.flip()
        else:
            self._update_display()
```

  (Spec refinement: the spec says "all sprites dirty and a full display update" after a shake.
  Because the surface is restored after every shaken present, it already holds the full correct
  frame, so the full flip alone is sufficient. Marking sprites dirty would only add work.)

  - Main loop: transition branch becomes `update` → `self._update_frame_services()` → `render` →
    `self._present_frame(full_update=True)` (replacing the direct `pygame.display.flip()`); the
    normal branch becomes `_update_scene()` → `_process_events()` → `_update_frame_services()` →
    `_render_scene()` → `self._present_frame(full_update=False)` (replacing `_update_display()`).
  - `Scene.__init__`: `self.camera: Camera2D | None = None  # Assigned by games that scroll`.
  - `Scene`:

```python
    def apply_camera_to_sprites(self: Self) -> None:
        """Reposition camera-relative sprites from the current camera.

        Default: nothing. Games that place sprites through Camera2D.apply() override this so
        the scene manager can refresh positions (for example, after clearing a WORLD shake
        before a transition screenshot).
        """
```

  - `_start_transition`: before the old-player block, clear a WORLD shake so the old-floor
    screenshot is unshaken:

```python
        old_camera = getattr(self.active_scene, 'camera', None) if self.active_scene else None
        camera_was_shaking = isinstance(old_camera, Camera2D) and old_camera.shake_effect.is_active
        if camera_was_shaking:
            old_camera.shake_effect.clear()
            self.active_scene.apply_camera_to_sprites()
```

    and change the re-render condition from `if old_player is not None:` to re-render when
    `old_player is not None or camera_was_shaking` (keep the player hide/show only for the player
    case).

- [ ] **Step 7: Run** — `uv run pytest tests/effects/test_shake.py tests/scenes tests/engine -v`
  Expected: new tests PASS, no existing test broken. If an existing test asserted that the
  transition branch calls `pygame.display.flip` directly, it still passes (flip is still called).

- [ ] **Step 8: Checkpoint and commit** (ruff, basedpyright, ty on `scene.py`, `game_engine.py`). Report.

---

### Task 7: Rumble controller and `Scene.shake`

**Files:**
- Create: `glitchygames/input/rumble.py`
- Modify: `glitchygames/input/__init__.py` (export `RumbleController`)
- Modify: `glitchygames/scenes/scene.py` (`SceneManager` owns `rumble`; `Scene.shake`)
- Test: `tests/input/test_rumble.py`, `tests/scenes/test_scene_manager.py`

**Interfaces:**
- Consumes: `ScreenShake.rumble_levels`, `ScreenShake.rumble_remaining`.
- Produces:
  - `RumbleDevice` Protocol: `rumble(low_frequency, high_frequency, duration) -> bool`,
    `stop_rumble() -> None`.
  - `connected_rumble_devices(controller_manager: object | None) -> list[RumbleDevice]`.
  - `RumbleController(*, intensity: float = 1.0)` with settable `intensity` and
    `update(*, shakers: Sequence[ScreenShake], dt: float,
    devices: Callable[[], list[RumbleDevice]]) -> None`.
  - `RESEND_LEVEL_THRESHOLD = 0.05`.
  - `SceneManager.rumble: RumbleController`; `Scene.shake(shake, *, targets=ShakeTarget.WORLD)`.

- [ ] **Step 1: Write the failing tests** (`tests/input/test_rumble.py`)

```python
"""Tests for the rumble controller."""

import random

import pytest

from glitchygames.effects.shake import RumbleSettings, ScreenShake, Shake, ShakeStyle
from glitchygames.input.rumble import RumbleController, connected_rumble_devices


def _rumbling_shaker(duration=1.0, low=1.0, high=0.5, strength=32.0):
    shaker = ScreenShake(random_source=random.Random(3))
    shaker.add(Shake(style=ShakeStyle.JITTER, strength=strength, duration=duration,
                     frequency=10.0, rumble=RumbleSettings(low_frequency=low, high_frequency=high)))
    return shaker


@pytest.fixture
def devices(mocker):
    return [mocker.Mock(), mocker.Mock()]


class TestRumbleController:
    def test_sends_levels_to_every_device(self, devices):
        controller = RumbleController()
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
        for device in devices:
            device.rumble.assert_called_once_with(1.0, 0.5, 1000)

    def test_duration_is_never_zero(self, devices):
        """0 ms means rumble forever in SDL, so tiny remainders round up to 1 ms."""
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=0.0001)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        assert devices[0].rumble.call_args.args[2] == 1

    def test_does_not_resend_small_changes(self, devices):
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=10.0)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        shaker.update(0.1)  # JITTER decays linearly: 1% change
        controller.update(shakers=[shaker], dt=0.1, devices=lambda: devices)
        assert devices[0].rumble.call_count == 1

    def test_resends_when_levels_drop(self, devices):
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=1.0)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        shaker.update(0.2)
        controller.update(shakers=[shaker], dt=0.2, devices=lambda: devices)
        assert devices[0].rumble.call_count == 2

    def test_stops_when_shakes_end(self, devices):
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=0.1)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        shaker.update(0.2)
        controller.update(shakers=[shaker], dt=0.2, devices=lambda: devices)
        for device in devices:
            device.stop_rumble.assert_called_once()

    def test_intensity_zero_sends_nothing(self, devices):
        controller = RumbleController(intensity=0.0)
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_not_called()

    def test_combines_shakers_per_motor(self, devices):
        controller = RumbleController()
        controller.update(
            shakers=[_rumbling_shaker(low=0.2, high=0.9), _rumbling_shaker(low=0.7, high=0.1)],
            dt=0.0,
            devices=lambda: devices,
        )
        devices[0].rumble.assert_called_once_with(0.7, 0.9, 1000)

    def test_device_errors_are_skipped(self, mocker):
        """Review focus 4: an unplugged device must not stop rumble on the others."""
        broken = mocker.Mock()
        broken.rumble.side_effect = Exception('device gone')
        working = mocker.Mock()
        controller = RumbleController()
        controller.update(shakers=[_rumbling_shaker()], dt=0.0,
                          devices=lambda: [broken, working])
        working.rumble.assert_called_once()


class TestConnectedRumbleDevices:
    def test_controller_mode_uses_controller_proxies(self, mocker):
        manager = mocker.Mock()
        manager.controllers = {3: 'proxy-a', 7: 'proxy-b'}
        assert connected_rumble_devices(manager) == ['proxy-a', 'proxy-b']

    def test_joystick_mode_opens_every_joystick(self, mocker):
        mocker.patch('pygame.joystick.get_count', return_value=2)
        joystick = mocker.patch('pygame.joystick.Joystick', side_effect=['first', 'second'])
        assert connected_rumble_devices(None) == ['first', 'second']
        assert joystick.call_count == 2
```

- [ ] **Step 2: Run** — FAIL (module missing).

- [ ] **Step 3: Implement `glitchygames/input/rumble.py`**

```python
"""Controller rumble driven by active shakes.

SDL replaces a running rumble whenever a new one starts and treats a duration of 0 as
"forever", so this controller sends one combined level (per-motor maximum over all shakers)
and only re-sends when that level changes noticeably or the sent rumble is about to expire.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Protocol

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glitchygames.effects.shake import ScreenShake

log: logging.Logger = logging.getLogger('game.input.rumble')

RESEND_LEVEL_THRESHOLD = 0.05
MILLISECONDS_PER_SECOND = 1000


class RumbleDevice(Protocol):
    """Anything with SDL-style rumble: controller proxies and pygame joysticks."""

    def rumble(self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        """Start rumble; duration in milliseconds (0 = forever)."""
        ...

    def stop_rumble(self) -> None:
        """Stop rumble."""
        ...


def connected_rumble_devices(controller_manager: object | None) -> list[RumbleDevice]:
    """Return every device that can rumble in the current input mode.

    Args:
        controller_manager: GameEngine.controller_manager; None in joystick mode (the
            pygame-ce default), where joysticks are opened directly.

    Returns:
        The devices.

    """
    if controller_manager is not None:
        controllers: dict[int, RumbleDevice] = controller_manager.controllers  # type: ignore[attr-defined]
        return list(controllers.values())
    return [pygame.joystick.Joystick(index) for index in range(pygame.joystick.get_count())]


class RumbleController:
    """Sends the combined rumble of all shakers to every connected device."""

    def __init__(self, *, intensity: float = 1.0) -> None:
        """Initialize with nothing sent.

        Args:
            intensity: Player setting 0.0-1.0 multiplying both motors (0 disables).

        """
        self._intensity = 1.0
        self.intensity = intensity
        self._sent_levels = (0.0, 0.0)
        self._sent_time_left = 0.0

    @property
    def intensity(self) -> float:
        """Player setting 0.0-1.0 multiplying both motors."""
        return self._intensity

    @intensity.setter
    def intensity(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            message = f'intensity must be between 0.0 and 1.0, got {value}'
            raise ValueError(message)
        self._intensity = value

    def update(
        self,
        *,
        shakers: Sequence[ScreenShake],
        dt: float,
        devices: Callable[[], list[RumbleDevice]],
    ) -> None:
        """Send, re-send or stop rumble to match the shakers.

        Args:
            shakers: Every active ScreenShake (screen and the active scene's camera).
            dt: Seconds since the last update.
            devices: Called only when something must be sent.

        """
        self._sent_time_left -= dt
        low = max((shaker.rumble_levels[0] for shaker in shakers), default=0.0) * self._intensity
        high = max((shaker.rumble_levels[1] for shaker in shakers), default=0.0) * self._intensity
        remaining = max((shaker.rumble_remaining for shaker in shakers), default=0.0)

        if low == 0.0 and high == 0.0:
            if self._sent_levels != (0.0, 0.0):
                self._for_each_device(devices=devices, action='stop')
                self._sent_levels = (0.0, 0.0)
            return

        level_change = max(abs(low - self._sent_levels[0]), abs(high - self._sent_levels[1]))
        if level_change <= RESEND_LEVEL_THRESHOLD and self._sent_time_left > 0.0:
            return

        duration_milliseconds = max(1, math.ceil(remaining * MILLISECONDS_PER_SECOND))
        self._for_each_device(devices=devices, action='rumble',
                              levels=(low, high), duration_milliseconds=duration_milliseconds)
        self._sent_levels = (low, high)
        self._sent_time_left = duration_milliseconds / MILLISECONDS_PER_SECOND

    @staticmethod
    def _for_each_device(
        *,
        devices: Callable[[], list[RumbleDevice]],
        action: str,
        levels: tuple[float, float] = (0.0, 0.0),
        duration_milliseconds: int = 0,
    ) -> None:
        for device in devices():
            try:
                if action == 'stop':
                    device.stop_rumble()
                else:
                    # Positional: pygame's C Joystick.rumble does not take keywords
                    device.rumble(levels[0], levels[1], duration_milliseconds)
            except Exception:  # A device unplugged mid-rumble must not stop the others
                log.debug('Rumble failed on %r', device, exc_info=True)
```

If ruff flags the broad `except Exception` (BLE001), narrow it to `(pygame.error, AttributeError,
OSError)` and change the test's side effect to `pygame.error('device gone')`.

- [ ] **Step 4: Run** — `uv run pytest tests/input/test_rumble.py -v` — PASS.

- [ ] **Step 5: Failing `Scene.shake` tests** (in `tests/scenes/test_scene_manager.py`; these use
  real `ScreenShake`/`Camera2D`, which do not touch the mocked display)

```python
class TestSceneShake:
    @staticmethod
    def _shake():
        from glitchygames.effects.shake import Shake, ShakeStyle
        return Shake(style=ShakeStyle.NOISE, strength=5.0, duration=1.0, frequency=5.0)

    def test_world_requires_camera(self):
        scene = Scene()
        with pytest.raises(ValueError, match='camera'):
            scene.shake(self._shake())

    def test_world_on_inactive_scene_raises(self):
        """Cue callbacks run on a cleaned-up scene; WORLD must fail loudly there."""
        from glitchygames.camera import Camera2D

        scene = Scene()
        scene.camera = Camera2D(screen_width=100, screen_height=100)
        scene.scene_manager.active_scene = None
        with pytest.raises(RuntimeError, match='active'):
            scene.shake(self._shake())

    def test_world_on_active_scene_shakes_camera(self):
        from glitchygames.camera import Camera2D

        scene = Scene()
        scene.camera = Camera2D(screen_width=100, screen_height=100)
        scene.scene_manager.active_scene = scene
        scene.shake(self._shake())
        assert scene.camera.shake_effect.is_active

    def test_screen_works_from_any_scene(self):
        from glitchygames.effects.shake import ShakeTarget

        scene = Scene()
        scene.scene_manager.active_scene = None
        scene.shake(self._shake(), targets=ShakeTarget.SCREEN)
        assert scene.scene_manager.screen_shake.is_active
        scene.scene_manager.screen_shake.clear()

    def test_frame_services_drive_rumble(self, mocker):
        from glitchygames.effects.shake import RumbleSettings, Shake, ShakeStyle

        manager = SceneManager()
        update = mocker.patch.object(manager.rumble, 'update')
        manager.active_scene = Scene()
        manager.dt = 0.0
        manager._update_frame_services()
        assert update.call_args.kwargs['shakers'] == [manager.screen_shake]
```

(Use the file's existing imports for `Scene`/`SceneManager`/`pytest`.)

- [ ] **Step 6: Implement in `scene.py`.**
  - Import `RumbleController, connected_rumble_devices` from `glitchygames.input.rumble` and
    `Shake, ShakeTarget` from `glitchygames.effects.shake`.
  - `SceneManager.__init__`: `self.rumble = RumbleController()`. `game_engine` setter:
    `self.rumble.intensity = self.OPTIONS.get('rumble_intensity', 1.0)`.
  - Extend `_update_frame_services`:

```python
        shakers = [self.screen_shake]
        camera = getattr(self.active_scene, 'camera', None)
        if isinstance(camera, Camera2D):
            shakers.append(camera.shake_effect)
        controller_manager = getattr(self.game_engine, 'controller_manager', None)
        self.rumble.update(
            shakers=shakers,
            dt=self.dt,
            devices=lambda: connected_rumble_devices(controller_manager),
        )
```

  - `Scene`:

```python
    def shake(self: Self, shake: Shake, *, targets: ShakeTarget = ShakeTarget.WORLD) -> None:
        """Start a shake on the world (camera), the whole screen, or both.

        Rumble, if the shake has it, is sent automatically by the scene manager.

        Args:
            shake: The shake to start.
            targets: ShakeTarget.WORLD, ShakeTarget.SCREEN, or both combined with |.

        Raises:
            ValueError: If WORLD is requested and the scene has no camera.
            RuntimeError: If WORLD is requested on a scene that is not active (for example
                from a transition cue, which runs after the scene was cleaned up).

        """
        if ShakeTarget.WORLD in targets:
            if self.camera is None:
                message = f'{self.NAME} has no camera; WORLD shake needs Scene.camera'
                raise ValueError(message)
            if self.scene_manager.active_scene is not self:
                message = f'{self.NAME} is not the active scene; use ShakeTarget.SCREEN'
                raise RuntimeError(message)
            self.camera.shake_effect.add(shake)
        if ShakeTarget.SCREEN in targets:
            self.scene_manager.screen_shake.add(shake)
```

- [ ] **Step 7: Run** — `uv run pytest tests/input tests/scenes -v` — PASS, nothing broken.
- [ ] **Step 8: Checkpoint and commit.** Report.

---

### Task 8: Transition hooks and elevator clamp

**Files:**
- Modify: `glitchygames/transitions/base.py`, `glitchygames/transitions/elevator.py`
- Test: `tests/transitions/test_transitions.py`

**Interfaces:**
- Produces: `Transition(duration=0.5, easing='ease_in_out_quad', on_update=None)`,
  `Transition.add_cue(progress: float, callback: Callable[[], None]) -> None`,
  `Transition.eased_velocity_at(progress: float) -> float`; `ElevatorTransition(...,
  on_update=None)`.

- [ ] **Step 1: Failing tests** (append; import `ElevatorTransition` from
  `glitchygames.transitions.elevator`)

```python
class TestTransitionHooks:
    def test_on_update_called_every_frame_with_transition(self, surfaces, mocker):
        on_update = mocker.Mock()
        transition = Transition(duration=1.0, on_update=on_update)
        transition.start(surfaces[0], surfaces[1])
        transition.update(0.1)
        transition.update(0.1)
        assert on_update.call_count == 2
        on_update.assert_called_with(transition)

    def test_cue_fires_once_when_crossed(self, surfaces, mocker):
        callback = mocker.Mock()
        transition = Transition(duration=1.0)
        transition.add_cue(0.5, callback)
        transition.start(surfaces[0], surfaces[1])
        transition.update(0.4)
        callback.assert_not_called()
        transition.update(0.1)  # progress == 0.5 exactly: "<=" fires
        transition.update(0.1)
        callback.assert_called_once()

    def test_cue_at_zero_fires_on_first_update(self, surfaces, mocker):
        callback = mocker.Mock()
        transition = Transition(duration=1.0)
        transition.add_cue(0.0, callback)
        transition.start(surfaces[0], surfaces[1])
        transition.update(0.0)
        callback.assert_called_once()

    def test_large_dt_fires_all_passed_cues_in_order(self, surfaces):
        order = []
        transition = Transition(duration=1.0)
        transition.add_cue(1.0, lambda: order.append('end'))
        transition.add_cue(0.2, lambda: order.append('early'))
        transition.add_cue(0.6, lambda: order.append('middle'))
        transition.start(surfaces[0], surfaces[1])
        assert transition.update(5.0) is True
        assert order == ['early', 'middle', 'end']

    def test_cues_fire_before_on_update(self, surfaces):
        order = []
        transition = Transition(duration=1.0, on_update=lambda _transition: order.append('update'))
        transition.add_cue(1.0, lambda: order.append('cue'))
        transition.start(surfaces[0], surfaces[1])
        transition.update(1.0)
        assert order == ['cue', 'update']

    @pytest.mark.parametrize('progress', [-0.01, 1.01])
    def test_cue_progress_validated(self, progress):
        with pytest.raises(ValueError, match='progress'):
            Transition().add_cue(progress, lambda: None)

    def test_eased_velocity_of_linear_is_one(self):
        assert Transition(easing='linear').eased_velocity_at(0.5) == pytest.approx(1.0)

    def test_eased_velocity_at_ends_is_one_sided(self):
        transition = Transition(easing='ease_in_sine')
        assert transition.eased_velocity_at(1.0) == pytest.approx(math.pi / 2, rel=1e-2)
        assert transition.eased_velocity_at(0.0) == pytest.approx(0.0, abs=1e-2)


class TestElevatorTransitionClamp:
    @pytest.mark.parametrize('easing', ['ease_in_back', 'ease_in_elastic', 'ease_out_back'])
    def test_overshooting_easing_stays_inside_composite(self, surfaces, easing, mocker):
        old, new, screen = surfaces
        transition = ElevatorTransition(duration=1.0, easing=easing)
        transition.start(old, new)
        blit = mocker.spy(screen, 'blit')
        for _ in range(20):
            transition.update(0.05)
            transition.render(screen)
            area = blit.call_args_list[0].kwargs['area']
            assert 0 <= area.top <= transition._total_scroll
            blit.reset_mock()
```

(`math` import needed at top.)

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement in `base.py`**: add `import bisect` and
  `from collections.abc import Callable` under `TYPE_CHECKING` (plus a runtime-safe annotation via
  `from __future__ import annotations`, already present). Constant
  `EASING_SLOPE_STEP = 1e-3`. In `__init__` add `on_update: Callable[[Transition], None] | None =
  None` and:

```python
        self._on_update = on_update
        # Sorted by progress; equal progresses keep insertion order
        self._cues: list[tuple[float, int, Callable[[], None]]] = []
        self._next_cue_index = 0
```

  Add:

```python
    def add_cue(self, progress: float, callback: Callable[[], None]) -> None:
        """Call callback once when raw progress first reaches progress.

        Cues fire in ascending progress order, before on_update, on the frame that reaches
        them; one large dt fires every cue it passes. A cue at 0.0 fires on the first update
        and a cue at 1.0 on the completing frame.

        Args:
            progress: Raw progress 0.0-1.0 at which to fire.
            callback: Called with no arguments.

        Raises:
            ValueError: If progress is outside 0.0-1.0.

        """
        if not 0.0 <= progress <= 1.0:
            message = f'progress must be between 0.0 and 1.0, got {progress}'
            raise ValueError(message)
        bisect.insort(self._cues, (progress, len(self._cues), callback),
                      key=lambda cue: (cue[0], cue[1]))

    def eased_velocity_at(self, progress: float) -> float:
        """Slope of the easing curve (d eased / d raw progress) at a raw progress.

        Uses a central difference, one-sided at 0.0 and 1.0.

        Args:
            progress: Raw progress 0.0-1.0.

        Returns:
            The slope; 1.0 everywhere for linear easing.

        """
        lower = max(0.0, progress - EASING_SLOPE_STEP)
        upper = min(1.0, progress + EASING_SLOPE_STEP)
        return (self._easing_func(upper) - self._easing_func(lower)) / (upper - lower)
```

  In `update`, after `self._elapsed += dt` and before the completion check:

```python
        current_progress = self.progress
        while (
            self._next_cue_index < len(self._cues)
            and self._cues[self._next_cue_index][0] <= current_progress
        ):
            callback = self._cues[self._next_cue_index][2]
            self._next_cue_index += 1
            callback()
        if self._on_update is not None:
            self._on_update(self)
```

  In `start`, reset `self._next_cue_index = 0`.

  In `elevator.py`: add `on_update` as the last keyword parameter of `ElevatorTransition.__init__`
  and pass it to `super().__init__(duration=duration, easing=easing, on_update=on_update)`. In
  `_render_frame` replace `progress = self.eased_progress` with:

```python
        # Overshooting easings (ease_in_back -0.10, ease_in_elastic -0.37, ease_out_back > 1)
        # would scroll past the composite and show black
        progress = min(1.0, max(0.0, self.eased_progress))
```

- [ ] **Step 4: Run** — `uv run pytest tests/transitions -v` — PASS.
- [ ] **Step 5: Checkpoint and commit.** Report.

---

### Task 9: Synth toolkit, part 1 — sample rate, oscillators, pitch curves

**Files:**
- Create: `glitchygames/audio/exceptions.py`, `glitchygames/audio/synth.py`, `tests/audio/__init__.py`
  (empty), `tests/audio/test_synth.py`

**Interfaces:**
- Produces:
  - `AudioUnavailableError(RuntimeError)`, `SoundRecipeError(ValueError)` in `exceptions.py`.
  - `DEFAULT_SAMPLE_RATE = 44100`, `mixer_sample_rate() -> int`,
    `sample_count(duration: float, sample_rate: int) -> int` (= `round(duration * sample_rate)`).
  - `Waveform(Enum)`: `SINE`, `SQUARE`, `SAWTOOTH`, `TRIANGLE`, `NOISE`.
  - `oscillator(waveform, frequency, duration, *, sample_rate=None, duty=0.5, phase=0.0,
    random_source=None) -> tuple[FloatArray, float]` where `FloatArray =
    numpy.typing.NDArray[numpy.float64]` and `random_source` is a `numpy.random.Generator`.
  - `frequency_curve(start_hz, end_hz, duration, *, easing='linear', sample_rate=None) ->
    FloatArray`.

**Spec refinement:** `TRIANGLE` is generated naively. Its harmonics fall at 12 dB per octave, so
aliasing is far below the square and sawtooth case, and a band-limited triangle (PolyBLAMP or
integrated PolyBLEP square) needs integrator state across chunks. PolyBLEP is applied to `SQUARE`
and `SAWTOOTH` only.

- [ ] **Step 1: Failing tests** (`tests/audio/test_synth.py`)

```python
"""Tests for the synth toolkit (numpy only unless marked)."""

import numpy as np
import pytest

from glitchygames.audio import synth
from glitchygames.audio.synth import Waveform

RATE = 44100


def _peak_frequency(samples, sample_rate=RATE):
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)[np.argmax(spectrum)]


class TestSampleRate:
    def test_mixer_rate_when_initialized(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=(48000, -16, 2))
        assert synth.mixer_sample_rate() == 48000

    def test_default_when_mixer_missing(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        assert synth.mixer_sample_rate() == 44100

    def test_sample_count_rounds(self):
        assert synth.sample_count(0.05, 22050) == 1102  # 1102.5 rounds half to even
        assert synth.sample_count(0.1, 44100) == 4410


class TestOscillator:
    @pytest.mark.parametrize('waveform', [Waveform.SINE, Waveform.SQUARE, Waveform.SAWTOOTH,
                                          Waveform.TRIANGLE])
    def test_peak_at_requested_frequency(self, waveform):
        samples, _ = synth.oscillator(waveform, 440.0, 0.5, sample_rate=RATE)
        assert _peak_frequency(samples) == pytest.approx(440.0, abs=3.0)

    @pytest.mark.parametrize('waveform', list(Waveform))
    def test_range_and_length(self, waveform):
        samples, _ = synth.oscillator(waveform, 220.0, 0.1, sample_rate=RATE,
                                      random_source=np.random.default_rng(1))
        assert len(samples) == 4410
        assert np.max(np.abs(samples)) <= 1.0 + 0.1  # PolyBLEP may overshoot slightly

    def test_sine_phase_origin_is_zero(self):
        samples, _ = synth.oscillator(Waveform.SINE, 1000.0, 0.01, sample_rate=RATE)
        expected = np.sin(2 * np.pi * 1000.0 * np.arange(441) / RATE)
        np.testing.assert_allclose(samples, expected, atol=1e-12)

    @pytest.mark.parametrize('waveform', [Waveform.SINE, Waveform.SQUARE, Waveform.SAWTOOTH])
    def test_end_phase_continues_seamlessly(self, waveform):
        whole, _ = synth.oscillator(waveform, 330.0, 0.2, sample_rate=RATE)
        first, end_phase = synth.oscillator(waveform, 330.0, 0.1, sample_rate=RATE)
        second, _ = synth.oscillator(waveform, 330.0, 0.1, sample_rate=RATE, phase=end_phase)
        np.testing.assert_allclose(np.concatenate((first, second)), whole, atol=1e-9)

    def test_end_phase_wrapped(self):
        _, end_phase = synth.oscillator(Waveform.SINE, 440.0, 1.0, sample_rate=RATE)
        assert 0.0 <= end_phase < 1.0

    @pytest.mark.parametrize('waveform', [Waveform.SQUARE, Waveform.SAWTOOTH])
    def test_polyblep_reduces_aliasing(self, waveform):
        """At 5 kHz the naive waveform aliases heavily; band-limited energy off-harmonic is lower."""
        samples, _ = synth.oscillator(waveform, 5000.0, 0.5, sample_rate=RATE)
        frequencies = np.fft.rfftfreq(len(samples), d=1.0 / RATE)
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples)))) ** 2
        harmonic = np.isclose((frequencies / 5000.0) % 1.0, 0.0, atol=0.01) | np.isclose(
            (frequencies / 5000.0) % 1.0, 1.0, atol=0.01)
        alias_fraction = spectrum[~harmonic].sum() / spectrum.sum()
        assert alias_fraction < 0.05

    def test_frequency_array_length_must_match(self):
        with pytest.raises(ValueError, match='length'):
            synth.oscillator(Waveform.SINE, np.full(10, 440.0), 0.5, sample_rate=RATE)

    @pytest.mark.parametrize('frequency', [-1.0, RATE / 2 + 1])
    def test_frequency_outside_nyquist_raises(self, frequency):
        with pytest.raises(ValueError, match='frequency'):
            synth.oscillator(Waveform.SINE, frequency, 0.1, sample_rate=RATE)

    @pytest.mark.parametrize('duration', [0.0, -0.1])
    def test_duration_must_be_positive(self, duration):
        with pytest.raises(ValueError, match='duration'):
            synth.oscillator(Waveform.SINE, 440.0, duration, sample_rate=RATE)

    def test_noise_is_seeded(self):
        first, _ = synth.oscillator(Waveform.NOISE, 0.0, 0.01, sample_rate=RATE,
                                    random_source=np.random.default_rng(9))
        second, _ = synth.oscillator(Waveform.NOISE, 0.0, 0.01, sample_rate=RATE,
                                     random_source=np.random.default_rng(9))
        np.testing.assert_array_equal(first, second)


class TestFrequencyCurve:
    def test_endpoints_exact(self):
        curve = synth.frequency_curve(220.0, 660.0, 0.12, sample_rate=RATE)
        assert curve[0] == 220.0
        assert curve[-1] == 660.0
        assert len(curve) == synth.sample_count(0.12, RATE)

    def test_easing_shapes_curve(self):
        linear = synth.frequency_curve(100.0, 200.0, 0.1, sample_rate=RATE)
        eased = synth.frequency_curve(100.0, 200.0, 0.1, easing='ease_in_quad', sample_rate=RATE)
        middle = len(linear) // 2
        assert eased[middle] < linear[middle]

    def test_overshoot_outside_range_raises(self):
        with pytest.raises(ValueError, match='frequency'):
            synth.frequency_curve(10.0, 200.0, 0.1, easing='ease_in_back', sample_rate=RATE)
```

- [ ] **Step 2: Run** — FAIL (module missing).

- [ ] **Step 3: Implement.** `exceptions.py`:

```python
"""Audio exceptions."""


class AudioUnavailableError(RuntimeError):
    """The mixer is not initialized or uses a format the synth cannot produce."""


class SoundRecipeError(ValueError):
    """A sound recipe is invalid; the message names the recipe and field."""
```

`synth.py` (part 1; part 2 appends in Task 10):

```python
"""Sound synthesis toolkit: numpy waveforms, envelopes, filters and mixing.

Every function works on mono float64 arrays in [-1.0, 1.0]. Conversion to 16-bit PCM happens
once, in to_pcm16() / to_sound(). Sample rates default to the running mixer's rate, resolved at
call time.
"""

from __future__ import annotations

import enum
import math

import numpy as np
import numpy.typing as npt
import pygame

from glitchygames.effects.easing import get_easing

FloatArray = npt.NDArray[np.float64]

# pygame's default mixer rate, which pygame.init() starts (BUGS.md #22)
DEFAULT_SAMPLE_RATE = 44100


class Waveform(enum.Enum):
    """Oscillator shapes."""

    SINE = 'sine'
    SQUARE = 'square'
    SAWTOOTH = 'sawtooth'
    TRIANGLE = 'triangle'
    NOISE = 'noise'


def mixer_sample_rate() -> int:
    """Return the mixer's sample rate, or 44100 when the mixer is not initialized.

    Returns:
        Samples per second.

    """
    settings = pygame.mixer.get_init()
    if settings is None:
        return DEFAULT_SAMPLE_RATE
    return int(settings[0])


def sample_count(duration: float, sample_rate: int) -> int:
    """Number of samples for a duration (rounded to the nearest sample).

    Returns:
        The sample count.

    """
    return round(duration * sample_rate)


def _resolve_sample_rate(sample_rate: int | None) -> int:
    return mixer_sample_rate() if sample_rate is None else sample_rate


def _validate_frequencies(frequencies: FloatArray, sample_rate: int) -> None:
    nyquist = sample_rate / 2
    if frequencies.size and (np.min(frequencies) < 0.0 or np.max(frequencies) > nyquist):
        message = (
            f'frequency must be within 0-{nyquist} Hz (Nyquist at {sample_rate} Hz), '
            f'got {np.min(frequencies)}-{np.max(frequencies)}'
        )
        raise ValueError(message)


def _polyblep(phases: FloatArray, increments: FloatArray) -> FloatArray:
    """PolyBLEP residual that removes a sawtooth-style discontinuity at phase 0.

    Reference: V. Välimäki and A. Huovilainen, "Antialiasing Oscillators in Subtractive
    Synthesis", IEEE Signal Processing Magazine, 2007.

    Returns:
        The correction to subtract from (sawtooth) or add to (square) the naive waveform.

    """
    correction = np.zeros_like(phases)
    after_edge = (phases < increments) & (increments > 0.0)
    fraction = phases[after_edge] / increments[after_edge]
    correction[after_edge] = fraction + fraction - fraction * fraction - 1.0
    before_edge = (phases > 1.0 - increments) & (increments > 0.0)
    fraction = (phases[before_edge] - 1.0) / increments[before_edge]
    correction[before_edge] = fraction * fraction + fraction + fraction + 1.0
    return correction


def oscillator(  # ruff: ignore[too-many-arguments] - mirrors the spec's signature
    waveform: Waveform,
    frequency: float | FloatArray,
    duration: float,
    *,
    sample_rate: int | None = None,
    duty: float = 0.5,
    phase: float = 0.0,
    random_source: np.random.Generator | None = None,
) -> tuple[FloatArray, float]:
    """Generate a waveform.

    Sample i has phase `phase + sum(frequency[k] / sample_rate for k < i)` (an exclusive
    running sum), so sample 0 sits at `phase` and any pitch curve plays without clicks.

    Args:
        waveform: The shape.
        frequency: Hz, a number or one value per sample (ignored by NOISE).
        duration: Seconds (> 0). With a frequency array, must round to its length.
        sample_rate: Defaults to the mixer's rate.
        duty: SQUARE high fraction (0 < duty < 1).
        phase: Starting phase in cycles.
        random_source: numpy Generator for NOISE.

    Returns:
        (samples, end_phase) with end_phase wrapped to [0, 1) for seamless continuation.

    Raises:
        ValueError: On non-positive duration, a mismatched frequency array, a frequency
            outside 0-Nyquist, or duty outside (0, 1).

    """
    rate = _resolve_sample_rate(sample_rate)
    if duration <= 0.0:
        message = f'duration must be > 0, got {duration}'
        raise ValueError(message)
    if not 0.0 < duty < 1.0:
        message = f'duty must be between 0 and 1, got {duty}'
        raise ValueError(message)
    count = sample_count(duration, rate)
    if np.ndim(frequency) == 0:
        frequencies = np.full(count, float(frequency))
    else:
        frequencies = np.asarray(frequency, dtype=np.float64)
        if len(frequencies) != count:
            message = (
                f'frequency array length {len(frequencies)} does not match duration '
                f'{duration}s ({count} samples)'
            )
            raise ValueError(message)
    _validate_frequencies(frequencies, rate)

    if waveform is Waveform.NOISE:
        generator = random_source if random_source is not None else np.random.default_rng()
        return generator.uniform(-1.0, 1.0, count), phase % 1.0

    increments = frequencies / rate
    running = np.concatenate(([0.0], np.cumsum(increments[:-1])))
    phases = (phase + running) % 1.0
    end_phase = float((phase + increments.sum()) % 1.0)

    match waveform:
        case Waveform.SINE:
            samples = np.sin(2.0 * math.pi * phases)
        case Waveform.SAWTOOTH:
            samples = 2.0 * phases - 1.0 - _polyblep(phases, increments)
        case Waveform.SQUARE:
            samples = np.where(phases < duty, 1.0, -1.0)
            samples = samples + _polyblep(phases, increments)
            samples = samples - _polyblep((phases + (1.0 - duty)) % 1.0, increments)
        case Waveform.TRIANGLE:
            # Naive: harmonics fall at 12 dB/octave, so aliasing stays negligible
            samples = 1.0 - 4.0 * np.abs(phases - 0.5)
        case _:
            message = f'unsupported waveform {waveform}'
            raise ValueError(message)
    return samples, end_phase


def frequency_curve(
    start_hz: float,
    end_hz: float,
    duration: float,
    *,
    easing: str = 'linear',
    sample_rate: int | None = None,
) -> FloatArray:
    """Per-sample frequencies from start_hz to end_hz shaped by an easing curve.

    Sample i sits at time fraction i / (count - 1), so both endpoints are exact.

    Args:
        start_hz: First sample's frequency.
        end_hz: Last sample's frequency.
        duration: Seconds (> 0).
        easing: Name from glitchygames.effects.easing.
        sample_rate: Defaults to the mixer's rate.

    Returns:
        The frequency array.

    Raises:
        ValueError: On non-positive duration or if the eased curve leaves 0-Nyquist
            (overshooting easings such as ease_in_back).

    """
    rate = _resolve_sample_rate(sample_rate)
    if duration <= 0.0:
        message = f'duration must be > 0, got {duration}'
        raise ValueError(message)
    count = sample_count(duration, rate)
    fractions = np.linspace(0.0, 1.0, count) if count > 1 else np.zeros(count)
    easing_function = get_easing(easing)
    # The easing functions are scalar-only (math.*), so apply them element by element
    eased = np.array([easing_function(float(fraction)) for fraction in fractions])
    frequencies = start_hz + (end_hz - start_hz) * eased
    _validate_frequencies(frequencies, rate)
    return frequencies
```

(If `ruff` flags the `too-many-arguments` suppression syntax, use the project's existing
`# ruff: ignore[...]` style shown elsewhere, e.g. `elevator.py:34`.)

- [ ] **Step 4: Run** — `uv run pytest tests/audio/test_synth.py -v` — PASS. If the aliasing test
  fails, print `alias_fraction` for naive vs PolyBLEP and confirm PolyBLEP lowers it; adjust the
  threshold only to a value naive cannot meet (naive square at 5 kHz is well above 0.1).
- [ ] **Step 5: Checkpoint and commit.** Report.

---

### Task 10: Synth toolkit, part 2 — envelope, filters, effects, mixing, output

**Files:**
- Modify: `glitchygames/audio/synth.py`, `glitchygames/audio/__init__.py`
- Test: `tests/audio/test_synth.py`

**Interfaces:**
- Produces: `Envelope(attack, decay, sustain_level, release)`, `apply_envelope(samples, envelope,
  *, sample_rate=None)`, `low_pass(samples, cutoff_hz, *, sample_rate=None, taps=101,
  history=None)`, `high_pass(...)` (same signature), `filter_kernel(cutoff_hz, *, sample_rate,
  taps, high_pass: bool) -> FloatArray`, `apply_kernel(samples, kernel, *, history=None) ->
  FloatArray`, `distort(samples, drive)`, `tremolo(samples, rate_hz, depth, *, sample_rate=None,
  phase=0.0) -> tuple[FloatArray, float]`, `mix(*layers, sample_rate=None)`,
  `concatenate(*arrays)`, `silence(duration, *, sample_rate=None)`, `normalize(samples,
  peak=0.9)`, `to_pcm16(samples) -> NDArray[int16]`, `to_sound(samples, *, volume=0.5) ->
  pygame.mixer.Sound`, `SIGNED_16_BIT_FORMAT = -16`, `DEFAULT_FILTER_TAPS = 101`.

- [ ] **Step 1: Failing tests** (append to `tests/audio/test_synth.py`)

```python
from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.synth import Envelope


class TestEnvelope:
    def test_stage_boundaries(self):
        samples = np.ones(100)
        envelope = Envelope(attack=10 / RATE, decay=10 / RATE, sustain_level=0.5,
                            release=20 / RATE)
        shaped = synth.apply_envelope(samples, envelope, sample_rate=RATE)
        assert shaped[0] == 0.0
        assert shaped[9] == pytest.approx(1.0)
        assert shaped[19] == pytest.approx(0.5)
        assert shaped[50] == pytest.approx(0.5)
        assert shaped[-1] == 0.0

    def test_release_keeps_priority_when_too_long(self):
        samples = np.ones(30)
        envelope = Envelope(attack=20 / RATE, decay=0.0, sustain_level=1.0, release=20 / RATE)
        shaped = synth.apply_envelope(samples, envelope, sample_rate=RATE)
        # Release keeps all 20 samples (ending at 0); attack is cut to the 10 left
        assert shaped[-1] == 0.0
        assert shaped[9] == pytest.approx(1.0)
        assert np.all(np.diff(shaped[10:]) <= 0)

    def test_matches_brave_adventurer_shape(self):
        """attack + release with sustain 1.0 equals the old attack/decay envelope."""
        count = synth.sample_count(0.12, RATE)
        envelope = Envelope(attack=0.005, decay=0.0, sustain_level=1.0, release=0.08)
        shaped = synth.apply_envelope(np.ones(count), envelope, sample_rate=RATE)
        attack = synth.sample_count(0.005, RATE)
        release = synth.sample_count(0.08, RATE)
        np.testing.assert_allclose(shaped[:attack], np.linspace(0, 1, attack))
        np.testing.assert_allclose(shaped[-release:], np.linspace(1, 0, release))


class TestFilters:
    def _tone(self, frequency):
        return synth.oscillator(Waveform.SINE, frequency, 0.2, sample_rate=RATE)[0]

    def test_low_pass_attenuates_above_cutoff(self):
        low = synth.low_pass(self._tone(200.0), 1000.0, sample_rate=RATE)
        high = synth.low_pass(self._tone(8000.0), 1000.0, sample_rate=RATE)
        assert np.max(np.abs(low[500:])) > 0.9
        assert np.max(np.abs(high[500:])) < 0.05

    def test_high_pass_attenuates_below_cutoff(self):
        low = synth.high_pass(self._tone(100.0), 2000.0, sample_rate=RATE)
        high = synth.high_pass(self._tone(8000.0), 2000.0, sample_rate=RATE)
        assert np.max(np.abs(low[500:])) < 0.1
        assert np.max(np.abs(high[500:])) > 0.9

    @pytest.mark.parametrize('length', [0, 10, 5000])
    def test_output_length_equals_input(self, length):
        assert len(synth.low_pass(np.ones(length), 1000.0, sample_rate=RATE)) == length

    def test_no_onset_click(self):
        """A sound starting at full level ramps through the filter instead of jumping."""
        filtered = synth.low_pass(np.ones(500), 500.0, sample_rate=RATE)
        assert abs(filtered[0]) < 0.05

    def test_chunked_with_history_equals_whole(self):
        signal = synth.oscillator(Waveform.SAWTOOTH, 300.0, 0.2, sample_rate=RATE)[0]
        whole = synth.low_pass(signal, 900.0, sample_rate=RATE)
        taps = synth.DEFAULT_FILTER_TAPS
        history = np.zeros(taps - 1)
        pieces = []
        for chunk in np.array_split(signal, 7):
            pieces.append(synth.low_pass(chunk, 900.0, sample_rate=RATE, history=history))
            history = np.concatenate((history, chunk))[-(taps - 1):]
        np.testing.assert_allclose(np.concatenate(pieces), whole, atol=1e-12)

    @pytest.mark.parametrize('cutoff', [0.0, RATE / 2])
    def test_cutoff_bounds(self, cutoff):
        with pytest.raises(ValueError, match='cutoff'):
            synth.low_pass(np.ones(10), cutoff, sample_rate=RATE)

    def test_taps_must_be_odd(self):
        with pytest.raises(ValueError, match='taps'):
            synth.low_pass(np.ones(10), 1000.0, sample_rate=RATE, taps=100)


class TestEffectsAndMixing:
    def test_distort_keeps_peak_at_one(self):
        assert synth.distort(np.array([1.0, -1.0, 0.0]), 4.0) == pytest.approx([1.0, -1.0, 0.0])

    def test_tremolo_depth_and_phase(self):
        shaped, end_phase = synth.tremolo(np.ones(RATE), 1.0, 0.5, sample_rate=RATE)
        assert shaped[0] == pytest.approx(1.0)
        assert shaped[RATE // 2] == pytest.approx(0.5, abs=1e-3)
        assert end_phase == pytest.approx(0.0, abs=1e-9)

    def test_mix_offsets_and_overhang(self):
        mixed = synth.mix(np.ones(4), (np.ones(4), 2 / RATE), sample_rate=RATE)
        np.testing.assert_allclose(mixed, [1, 1, 2, 2, 1, 1])

    def test_mix_negative_offset_raises(self):
        with pytest.raises(ValueError, match='offset'):
            synth.mix((np.ones(4), -0.1), sample_rate=RATE)

    def test_normalize_silence_unchanged(self):
        np.testing.assert_array_equal(synth.normalize(np.zeros(5)), np.zeros(5))

    def test_normalize_peak(self):
        assert np.max(np.abs(synth.normalize(np.array([0.1, -0.5]), peak=0.9))) == 0.9

    def test_silence_zero_is_empty(self):
        assert len(synth.silence(0.0, sample_rate=RATE)) == 0

    def test_to_pcm16_clips_and_scales(self):
        np.testing.assert_array_equal(
            synth.to_pcm16(np.array([2.0, -2.0, 0.5])), np.array([32767, -32767, 16384],
                                                                dtype=np.int16))


class TestToSound:
    def test_raises_without_mixer(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        with pytest.raises(AudioUnavailableError):
            synth.to_sound(np.zeros(10))

    def test_raises_on_other_format(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=(44100, 32784, 2))
        with pytest.raises(AudioUnavailableError, match='format'):
            synth.to_sound(np.zeros(10))

    @pytest.mark.parametrize('channels', [1, 2])
    def test_tiles_to_mixer_channels(self, mocker, channels):
        mocker.patch('pygame.mixer.get_init', return_value=(44100, -16, channels))
        make_sound = mocker.patch('pygame.sndarray.make_sound')
        synth.to_sound(np.zeros(10), volume=0.3)
        frames = make_sound.call_args.args[0]
        assert frames.dtype == np.int16
        assert frames.flags['C_CONTIGUOUS']
        assert frames.shape == ((10,) if channels == 1 else (10, channels))
        make_sound.return_value.set_volume.assert_called_once_with(0.3)
```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement (append to `synth.py`)**

```python
import dataclasses

DEFAULT_FILTER_TAPS = 101
SIGNED_16_BIT_FORMAT = -16
PCM16_SCALE = 32767


@dataclasses.dataclass(frozen=True)
class Envelope:
    """Attack/decay/sustain/release amplitude envelope (seconds; sustain_level 0-1)."""

    attack: float
    decay: float
    sustain_level: float
    release: float


def apply_envelope(
    samples: FloatArray, envelope: Envelope, *, sample_rate: int | None = None
) -> FloatArray:
    """Shape samples with an envelope.

    Release is anchored to the end; attack and decay run from the start. When the stages
    are longer than the sound, release keeps its full length first, then attack, then decay.
    Ramps are linear and include both endpoints (attack starts at 0.0, release ends at 0.0).

    Returns:
        The shaped samples.

    """
    rate = _resolve_sample_rate(sample_rate)
    count = len(samples)
    release_count = min(sample_count(envelope.release, rate), count)
    attack_count = min(sample_count(envelope.attack, rate), count - release_count)
    decay_count = min(sample_count(envelope.decay, rate), count - release_count - attack_count)
    sustain_count = count - release_count - attack_count - decay_count

    # Each stage starts from the level the previous non-empty stage ended at (1.0 if none)
    attack_ramp = np.linspace(0.0, 1.0, attack_count)
    decay_ramp = np.linspace(1.0, envelope.sustain_level, decay_count)
    sustain = np.full(sustain_count, envelope.sustain_level)
    level_before_release = 1.0
    if sustain_count or decay_count:
        level_before_release = envelope.sustain_level
    release_ramp = np.linspace(level_before_release, 0.0, release_count)
    shape = np.concatenate((attack_ramp, decay_ramp, sustain, release_ramp))
    return samples * shape
```

```python
def filter_kernel(cutoff_hz: float, *, sample_rate: int, taps: int, high_pass: bool) -> FloatArray:
    """Hamming-windowed sinc FIR kernel; high-pass by spectral inversion.

    Returns:
        The kernel (taps coefficients).

    Raises:
        ValueError: If taps is not an odd number >= 3 or cutoff is outside (0, Nyquist).

    """
    if taps < 3 or taps % 2 == 0:
        message = f'taps must be an odd number >= 3, got {taps}'
        raise ValueError(message)
    if not 0.0 < cutoff_hz < sample_rate / 2:
        message = f'cutoff must be between 0 and {sample_rate / 2} Hz, got {cutoff_hz}'
        raise ValueError(message)
    normalized_cutoff = cutoff_hz / sample_rate
    positions = np.arange(taps) - (taps - 1) / 2
    kernel = 2 * normalized_cutoff * np.sinc(2 * normalized_cutoff * positions) * np.hamming(taps)
    kernel /= kernel.sum()
    if high_pass:
        kernel = -kernel
        kernel[(taps - 1) // 2] += 1.0
    return kernel


def apply_kernel(
    samples: FloatArray, kernel: FloatArray, *, history: FloatArray | None = None
) -> FloatArray:
    """Filter samples, continuing from `history` (the previous taps-1 input samples).

    Returns:
        Filtered samples, same length as the input.

    Raises:
        ValueError: If history has the wrong length.

    """
    history_length = len(kernel) - 1
    if history is None:
        history = np.zeros(history_length)
    elif len(history) != history_length:
        message = f'history must have {history_length} samples, got {len(history)}'
        raise ValueError(message)
    return np.convolve(np.concatenate((history, samples)), kernel, mode='valid')


def low_pass(  # ruff: ignore[too-many-arguments]
    samples: FloatArray,
    cutoff_hz: float,
    *,
    sample_rate: int | None = None,
    taps: int = DEFAULT_FILTER_TAPS,
    history: FloatArray | None = None,
) -> FloatArray:
    """Remove content above cutoff_hz.

    Returns:
        Filtered samples, same length as the input.

    """
    rate = _resolve_sample_rate(sample_rate)
    kernel = filter_kernel(cutoff_hz, sample_rate=rate, taps=taps, high_pass=False)
    return apply_kernel(samples, kernel, history=history)


def high_pass(  # ruff: ignore[too-many-arguments]
    samples: FloatArray,
    cutoff_hz: float,
    *,
    sample_rate: int | None = None,
    taps: int = DEFAULT_FILTER_TAPS,
    history: FloatArray | None = None,
) -> FloatArray:
    """Remove content below cutoff_hz.

    Returns:
        Filtered samples, same length as the input.

    """
    rate = _resolve_sample_rate(sample_rate)
    kernel = filter_kernel(cutoff_hz, sample_rate=rate, taps=taps, high_pass=True)
    return apply_kernel(samples, kernel, history=history)


def distort(samples: FloatArray, drive: float) -> FloatArray:
    """Soft-clip with tanh; peaks at +/-1 stay at +/-1.

    Returns:
        Distorted samples.

    Raises:
        ValueError: If drive is not positive.

    """
    if drive <= 0.0:
        message = f'drive must be > 0, got {drive}'
        raise ValueError(message)
    return np.tanh(drive * samples) / math.tanh(drive)


def tremolo(
    samples: FloatArray,
    rate_hz: float,
    depth: float,
    *,
    sample_rate: int | None = None,
    phase: float = 0.0,
) -> tuple[FloatArray, float]:
    """Amplitude modulation: gain 1.0 at phase 0, (1 - depth) half a cycle later.

    Returns:
        (samples, end_phase) for seamless continuation.

    Raises:
        ValueError: If depth is outside 0-1 or rate_hz is not positive.

    """
    rate = _resolve_sample_rate(sample_rate)
    if not 0.0 <= depth <= 1.0:
        message = f'depth must be between 0.0 and 1.0, got {depth}'
        raise ValueError(message)
    if rate_hz <= 0.0:
        message = f'rate_hz must be > 0, got {rate_hz}'
        raise ValueError(message)
    phases = phase + np.arange(len(samples)) * rate_hz / rate
    gain = 1.0 - depth * (0.5 - 0.5 * np.cos(2 * math.pi * phases))
    end_phase = float((phase + len(samples) * rate_hz / rate) % 1.0)
    return samples * gain, end_phase


def mix(*layers: FloatArray | tuple[FloatArray, float], sample_rate: int | None = None) -> FloatArray:
    """Sum layers, each optionally starting at an offset in seconds (>= 0).

    Returns:
        The mixed samples, long enough for the last layer to end (not normalized).

    Raises:
        ValueError: If an offset is negative.

    """
    rate = _resolve_sample_rate(sample_rate)
    placements: list[tuple[FloatArray, int]] = []
    for layer in layers:
        samples, offset = layer if isinstance(layer, tuple) else (layer, 0.0)
        if offset < 0.0:
            message = f'offset must be >= 0, got {offset}'
            raise ValueError(message)
        placements.append((samples, sample_count(offset, rate)))
    total = max((start + len(samples) for samples, start in placements), default=0)
    result = np.zeros(total)
    for samples, start in placements:
        result[start : start + len(samples)] += samples
    return result


def concatenate(*arrays: FloatArray) -> FloatArray:
    """Join arrays end to end.

    Returns:
        The joined samples.

    """
    return np.concatenate(arrays) if arrays else np.zeros(0)


def silence(duration: float, *, sample_rate: int | None = None) -> FloatArray:
    """Zeros for a duration (0 gives an empty array).

    Returns:
        The silent samples.

    """
    return np.zeros(sample_count(duration, _resolve_sample_rate(sample_rate)))


def normalize(samples: FloatArray, peak: float = 0.9) -> FloatArray:
    """Scale so the loudest sample is at peak; silence is returned unchanged.

    Returns:
        The scaled samples.

    Raises:
        ValueError: If peak is outside (0, 1].

    """
    if not 0.0 < peak <= 1.0:
        message = f'peak must be in (0, 1], got {peak}'
        raise ValueError(message)
    loudest = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if loudest == 0.0:
        return samples.copy()
    return samples * (peak / loudest)


def to_pcm16(samples: FloatArray) -> npt.NDArray[np.int16]:
    """Clip to [-1, 1], scale by 32767 and round to signed 16-bit.

    Returns:
        PCM samples.

    """
    return np.round(np.clip(samples, -1.0, 1.0) * PCM16_SCALE).astype(np.int16)


def to_sound(samples: FloatArray, *, volume: float = 0.5) -> pygame.mixer.Sound:
    """Turn mono samples into a pygame Sound matching the mixer.

    Returns:
        The sound, with its volume set.

    Raises:
        AudioUnavailableError: If the mixer is not initialized or is not signed 16-bit.

    """
    settings = pygame.mixer.get_init()
    if settings is None:
        message = 'pygame.mixer is not initialized'
        raise AudioUnavailableError(message)
    _rate, sample_format, channel_count = settings
    if sample_format != SIGNED_16_BIT_FORMAT:
        message = f'mixer format {sample_format} is not signed 16-bit'
        raise AudioUnavailableError(message)
    pcm = to_pcm16(samples)
    frames = pcm if channel_count == 1 else np.repeat(pcm[:, np.newaxis], channel_count, axis=1)
    frames = np.ascontiguousarray(frames)
    # pygame.sndarray.make_sound has incomplete type stubs for its ndarray parameter
    sound: pygame.mixer.Sound = pygame.sndarray.make_sound(frames)  # pyright: ignore[reportUnknownMemberType]
    sound.set_volume(volume)
    return sound
```

Import `AudioUnavailableError` from `glitchygames.audio.exceptions` at the top. Add to
`glitchygames/audio/__init__.py` exports: `AudioUnavailableError`, `Envelope`, `Waveform`
(the module-level functions are used as `synth.oscillator(...)`; export `synth` itself is not
needed). Check that importing `glitchygames.audio` stays cheap (numpy is already a dependency).

- [ ] **Step 4: Run** — `uv run pytest tests/audio/test_synth.py -v` — PASS.
- [ ] **Step 5: Real-mixer smoke test** (append; runs only where a dummy audio driver works):

```python
class TestToSoundRealMixer:
    def test_make_sound_accepts_frames(self, monkeypatch):
        import pygame

        monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
        pygame.mixer.quit()
        pygame.mixer.init(44100, -16, 2)
        try:
            sound = synth.to_sound(np.zeros(441))
            assert sound.get_length() == pytest.approx(0.01, abs=1e-3)
        finally:
            pygame.mixer.quit()
```

Run it. If re-initializing the mixer is not possible in the session, mark the reason in the test
with `pytest.skip(reason)` only after confirming why, and report it.
- [ ] **Step 6: Checkpoint and commit.** Report.

---

### Task 11: Brave Adventurer on the toolkit (restore as written)

**Files:**
- Create (once, before changing code): `tests/examples/brave_adventurer_golden/{jump,land,collect,death,game_over}.npy`
- Create: `tests/examples/test_brave_adventurer_sounds.py`
- Modify: `glitchygames/examples/brave_adventurer/sounds.py`

**Spec refinement:** the spec says all five sounds match goldens within ±2 LSB. That holds for
land and collect. It cannot hold for the others:
- The two sweeps (jump, death): the old sweep uses an inclusive running sum, and the toolkit's
  exclusive phase origin shifts the phase by up to `(end_hz - start_hz) / sample_rate` cycles,
  about 1,500 LSB at 44100 Hz.
- game_over: the old code sizes notes with `int()` (truncation) and the toolkit with `round()`,
  so the 0.375 s note is 16537 vs 16538 samples, which shifts its release ramp by one sample.
  The same can happen to any duration whose product with 44100 is not exact in floating point.

Those three are compared by length (±1 sample), envelope (5 ms RMS windows within 2%), and pitch
at the start and end (within 2%) instead. The differences are inaudible; the user chose
"restore as written" for pitch and length.

- [ ] **Step 1: Capture goldens from the current code** (scratch script, run once, from the repo
  root; do not keep the script in the repo):

```python
# /private/tmp/.../scratchpad/capture_brave_goldens.py
import numpy as np
from pathlib import Path
from unittest import mock

import glitchygames.examples.brave_adventurer.sounds as sounds

output = Path('tests/examples/brave_adventurer_golden')
output.mkdir(exist_ok=True)
generators = {
    'jump': sounds._generate_jump_sound,
    'land': sounds._generate_land_sound,
    'collect': sounds._generate_collect_sound,
    'death': sounds._generate_death_sound,
    'game_over': sounds._generate_game_over_sound,
}
with mock.patch.object(sounds, 'SAMPLE_RATE', 44100):
    for name, generator in generators.items():
        with mock.patch.object(sounds, '_make_sound') as make_sound:
            generator()
            np.save(output / f'{name}.npy', make_sound.call_args.args[0])
            print(name, len(make_sound.call_args.args[0]))
```

(This one scratch script may use `unittest.mock` because it is not a test.) Run with
`uv run python <path>`. Expected lengths at 44100 Hz are about: jump 5292, land 2646,
collect 7938, death 13230, game_over 38587 (`int()` truncation can make any of them one sample
shorter than these). Confirm the five files exist and record the printed lengths in the report.

- [ ] **Step 2: Failing tests** (`tests/examples/test_brave_adventurer_sounds.py`)

```python
"""Brave Adventurer sounds after moving to the engine synth (restore as written)."""

from pathlib import Path

import numpy as np
import pytest

import glitchygames.examples.brave_adventurer.sounds as sounds
from glitchygames.audio import synth

GOLDEN = Path(__file__).parent / 'brave_adventurer_golden'
RATE = 44100
GENERATORS = {
    'jump': sounds._generate_jump_sound,
    'land': sounds._generate_land_sound,
    'collect': sounds._generate_collect_sound,
    'death': sounds._generate_death_sound,
    'game_over': sounds._generate_game_over_sound,
}


def _render(mocker, name):
    mocker.patch('glitchygames.audio.synth.mixer_sample_rate', return_value=RATE)
    to_sound = mocker.patch.object(sounds, 'to_sound')
    GENERATORS[name]()
    return synth.to_pcm16(to_sound.call_args.args[0]).astype(np.int32)


def _window_rms(samples, window=int(0.005 * RATE)):
    trimmed = samples[: len(samples) // window * window].astype(np.float64)
    return np.sqrt(np.mean(trimmed.reshape(-1, window) ** 2, axis=1))


def _zero_crossing_frequency(samples):
    crossings = np.count_nonzero(np.diff(np.signbit(samples)))
    return crossings / 2 / (len(samples) / RATE)


@pytest.mark.parametrize('name', ['land', 'collect'])
def test_constant_pitch_sounds_match_goldens(mocker, name):
    golden = np.load(GOLDEN / f'{name}.npy').astype(np.int32)
    rendered = _render(mocker, name)
    assert len(rendered) == len(golden)
    assert np.max(np.abs(rendered - golden)) <= 2


@pytest.mark.parametrize('name', ['jump', 'death', 'game_over'])
def test_match_length_envelope_and_pitch(mocker, name):
    """Sweeps differ in phase origin; game_over in int() vs round() note sizing."""
    golden = np.load(GOLDEN / f'{name}.npy').astype(np.int32)
    rendered = _render(mocker, name)
    assert abs(len(rendered) - len(golden)) <= 1
    shared = min(len(rendered), len(golden))
    rendered, golden = rendered[:shared], golden[:shared]
    np.testing.assert_allclose(_window_rms(rendered), _window_rms(golden), rtol=0.02, atol=60)
    edge = int(0.02 * RATE)
    for portion in (slice(0, edge), slice(-edge, None)):
        assert _zero_crossing_frequency(rendered[portion]) == pytest.approx(
            _zero_crossing_frequency(golden[portion]), rel=0.02, abs=30
        )


def test_game_sounds_initialize_without_mixer(mocker):
    """No audio device: initialize logs and leaves every sound None (no crash)."""
    mocker.patch('pygame.mixer.get_init', return_value=None)
    game_sounds = sounds.GameSounds()
    game_sounds.initialize()
    game_sounds.play_jump()  # No-op, no exception
    assert game_sounds.jump is None
```

- [ ] **Step 3: Run** — FAIL (`to_sound` not in `sounds`).

- [ ] **Step 4: Port `sounds.py`.** Delete `SAMPLE_RATE`, `_sine_wave`, `_frequency_sweep`,
  `_apply_envelope`, `_to_stereo`, `_concat_samples`, `_make_sound`, and the numpy imports they
  needed. Update the module docstring ("generated at the mixer's sample rate by the engine
  synthesizer, glitchygames.audio.synth"). Keep `MAX_AMPLITUDE` as the peak:

```python
from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.synth import (
    Envelope,
    Waveform,
    concatenate,
    frequency_curve,
    oscillator,
    to_sound,
)

# Peak level as a fraction of full scale (the original 24000 of 32767, kept as written)
PEAK = 24000 / 32767


def _sine(frequency: float, duration: float) -> FloatArray:
    return oscillator(Waveform.SINE, frequency, duration)[0] * PEAK


def _sweep(start_frequency: float, end_frequency: float, duration: float) -> FloatArray:
    frequencies = frequency_curve(start_frequency, end_frequency, duration)
    return oscillator(Waveform.SINE, frequencies, duration)[0] * PEAK


def _fade(samples: FloatArray, *, attack: float, release: float) -> FloatArray:
    """The original attack/fade-out envelope: ramp in, full level, ramp out at the end."""
    return apply_envelope(
        samples, Envelope(attack=attack, decay=0.0, sustain_level=1.0, release=release)
    )


def _generate_jump_sound() -> pygame.mixer.Sound:
    shaped = _fade(_sweep(220, 660, 0.12), attack=0.005, release=0.08)
    return to_sound(shaped, volume=0.35)


def _generate_land_sound() -> pygame.mixer.Sound:
    shaped = _fade(_sine(80, 0.06), attack=0.002, release=0.05)
    return to_sound(shaped, volume=0.25)


def _generate_collect_sound() -> pygame.mixer.Sound:
    note_duration = 0.06
    # C5=523, E5=659, G5=784 Hz (major triad)
    notes = [
        _fade(_sine(frequency, note_duration), attack=0.003, release=0.04)
        for frequency in (523, 659, 784)
    ]
    return to_sound(concatenate(*notes), volume=0.3)


def _generate_death_sound() -> pygame.mixer.Sound:
    shaped = _fade(_sweep(500, 80, 0.3), attack=0.005, release=0.2)
    return to_sound(shaped, volume=0.4)


def _generate_game_over_sound() -> pygame.mixer.Sound:
    note_duration = 0.25
    # Descending minor: E4=330, C4=262, A3=220
    note_e = _fade(_sine(330, note_duration), attack=0.01, release=0.15)
    note_c = _fade(_sine(262, note_duration), attack=0.01, release=0.15)
    note_a = _fade(_sine(220, note_duration * 1.5), attack=0.01, release=0.25)
    return to_sound(concatenate(note_e, note_c, note_a), volume=0.4)
```

Keep each generator's existing docstring. In `GameSounds.initialize`, replace the broad
`except Exception` with `except AudioUnavailableError:` logging
`log.warning('Audio unavailable, Brave Adventurer plays without sound')` (any other exception is a
bug and should surface). Import `apply_envelope` and `FloatArray` too.

- [ ] **Step 5: Run** — `uv run pytest tests/examples/test_brave_adventurer_sounds.py -v` — PASS.
  If land or collect differ in length, a duration's product with 44100 truncated differently
  under `int()`; move that sound to the structural test and say so in the report.
- [ ] **Step 6: Checkpoint and commit** (also run `uv run pytest tests/examples -v`). Report, and remind the
  user that Brave Adventurer and Papyrus now sound an octave lower and twice as long, which is
  what the code always described.

---

### Task 12: Recipes, TOML loader and `SoundBank`

**Files:**
- Create: `glitchygames/audio/recipes.py`, `tests/audio/test_recipes.py`
- Modify: `glitchygames/audio/__init__.py` (export `SoundBank`, `SoundRecipe`, `Tone`, `Tremolo`,
  `load_sound_recipes`, `SoundRecipeError`)

**Interfaces:**
- Produces:
  - `Tremolo(rate_hz: float, depth: float)`.
  - `Tone(waveform, start_frequency, duration, envelope, end_frequency=None, easing='linear',
    volume=1.0, offset=0.0, low_pass_cutoff=None, high_pass_cutoff=None, distortion=None,
    tremolo=None)` (note: `duration` and `envelope` precede the optional fields).
  - `SoundRecipe(name, tones, volume=0.5, peak=0.9)` with `render(*, sample_rate=None)`,
    `to_sound()`, `to_dict()`, `from_dict(name, data)` (classmethod).
  - `load_sound_recipes(path: Path) -> dict[str, SoundRecipe]`.
  - `SoundBank(recipes: Iterable[SoundRecipe])` with `play(name) -> None`.
  - `RECIPE_NOISE_SEED = 0` (recipes always sound the same).

- [ ] **Step 1: Failing tests** (`tests/audio/test_recipes.py`)

```python
"""Tests for sound recipes and the sound bank."""

import numpy as np
import pytest

from glitchygames.audio import synth
from glitchygames.audio.exceptions import AudioUnavailableError, SoundRecipeError
from glitchygames.audio.recipes import (
    RECIPE_NOISE_SEED,
    SoundBank,
    SoundRecipe,
    Tone,
    Tremolo,
    load_sound_recipes,
)
from glitchygames.audio.synth import Envelope, Waveform

RATE = 44100
ENVELOPE = Envelope(attack=0.001, decay=0.01, sustain_level=0.7, release=0.02)


def _two_tone_recipe():
    return SoundRecipe(
        name='ting',
        tones=(
            Tone(waveform=Waveform.TRIANGLE, start_frequency=1318.5, duration=0.08,
                 envelope=ENVELOPE),
            Tone(waveform=Waveform.SQUARE, start_frequency=200.0, end_frequency=100.0,
                 easing='ease_out_quad', duration=0.1, envelope=ENVELOPE, offset=0.05,
                 volume=0.5, low_pass_cutoff=2000.0, distortion=2.0,
                 tremolo=Tremolo(rate_hz=12.0, depth=0.3)),
        ),
    )


class TestRender:
    def test_render_equals_toolkit_composition(self):
        recipe = _two_tone_recipe()
        first = synth.apply_envelope(
            synth.oscillator(Waveform.TRIANGLE, 1318.5, 0.08, sample_rate=RATE)[0],
            ENVELOPE, sample_rate=RATE)
        frequencies = synth.frequency_curve(200.0, 100.0, 0.1, easing='ease_out_quad',
                                            sample_rate=RATE)
        second = synth.oscillator(Waveform.SQUARE, frequencies, 0.1, sample_rate=RATE)[0]
        second = synth.distort(second, 2.0)
        second = synth.low_pass(second, 2000.0, sample_rate=RATE)
        second, _ = synth.tremolo(second, 12.0, 0.3, sample_rate=RATE)
        second = synth.apply_envelope(second, ENVELOPE, sample_rate=RATE) * 0.5
        expected = synth.normalize(synth.mix(first, (second, 0.05), sample_rate=RATE), peak=0.9)
        np.testing.assert_allclose(recipe.render(sample_rate=RATE), expected)

    def test_noise_is_repeatable(self):
        recipe = SoundRecipe(name='hiss', tones=(
            Tone(waveform=Waveform.NOISE, start_frequency=0.0, duration=0.05, envelope=ENVELOPE),))
        np.testing.assert_array_equal(recipe.render(sample_rate=RATE),
                                      recipe.render(sample_rate=RATE))
        assert RECIPE_NOISE_SEED == 0


class TestValidationAndSerialization:
    @pytest.mark.parametrize(('field', 'value'), [('duration', -0.1), ('offset', -0.01),
                                                  ('volume', -1.0)])
    def test_tone_validation(self, field, value):
        settings = {'waveform': Waveform.SINE, 'start_frequency': 440.0, 'duration': 0.1,
                    'envelope': ENVELOPE, field: value}
        with pytest.raises(ValueError, match=field):
            Tone(**settings)

    def test_round_trip(self):
        recipe = _two_tone_recipe()
        assert SoundRecipe.from_dict('ting', recipe.to_dict()) == recipe

    def test_from_dict_names_recipe_and_field(self):
        data = _two_tone_recipe().to_dict()
        data['tones'][1]['waveform'] = 'kazoo'
        with pytest.raises(SoundRecipeError, match=r"ting\.tones\[1\]\.waveform"):
            SoundRecipe.from_dict('ting', data)

    def test_cutoff_at_nyquist_rejected_at_render(self):
        recipe = SoundRecipe(name='bad', tones=(
            Tone(waveform=Waveform.SINE, start_frequency=440.0, duration=0.05,
                 envelope=ENVELOPE, low_pass_cutoff=RATE / 2),))
        with pytest.raises(ValueError, match='cutoff'):
            recipe.render(sample_rate=RATE)

    def test_load_toml(self, tmp_path):
        path = tmp_path / 'sounds.toml'
        path.write_text(
            '[recipes.beep]\nvolume = 0.4\n'
            '[[recipes.beep.tones]]\nwaveform = "sine"\nstart_frequency = 880.0\n'
            'duration = 0.1\n'
            '[recipes.beep.tones.envelope]\nattack = 0.001\ndecay = 0.01\n'
            'sustain_level = 0.5\nrelease = 0.05\n',
            encoding='utf-8',
        )
        recipes = load_sound_recipes(path)
        assert recipes['beep'].name == 'beep'
        assert recipes['beep'].volume == 0.4
        assert recipes['beep'].tones[0].waveform is Waveform.SINE


class TestSoundBank:
    def test_renders_once_and_caches(self, mocker):
        mocker.patch('glitchygames.audio.recipes.mixer_sample_rate', return_value=RATE)
        to_sound = mocker.patch('glitchygames.audio.recipes.to_sound')
        bank = SoundBank([_two_tone_recipe()])
        bank.play('ting')
        bank.play('ting')
        assert to_sound.call_count == 1
        assert to_sound.return_value.play.call_count == 2

    def test_unknown_name_raises(self):
        with pytest.raises(KeyError):
            SoundBank([]).play('missing')

    def test_no_audio_is_a_logged_no_op(self, mocker):
        mocker.patch('glitchygames.audio.recipes.to_sound', side_effect=AudioUnavailableError('x'))
        warning = mocker.patch('glitchygames.audio.recipes.log.warning')
        bank = SoundBank([_two_tone_recipe()])
        bank.play('ting')
        bank.play('ting')
        assert warning.call_count == 1

    def test_busy_mixer_logs_debug(self, mocker):
        to_sound = mocker.patch('glitchygames.audio.recipes.to_sound')
        to_sound.return_value.play.return_value = None
        debug = mocker.patch('glitchygames.audio.recipes.log.debug')
        SoundBank([_two_tone_recipe()]).play('ting')
        assert debug.called

    def test_duplicate_names_rejected(self):
        with pytest.raises(ValueError, match='ting'):
            SoundBank([_two_tone_recipe(), _two_tone_recipe()])
```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement `recipes.py`**

```python
"""Sound recipes: sounds described as layered tones, rendered with the synth toolkit.

Recipes are data (to_dict/from_dict and TOML files), so a sound can live next to sprites and
be edited without code. Processing order per tone: oscillator, distortion, filters, tremolo,
envelope, volume. Tones are mixed at their offsets and the result normalized to `peak`.
"""

from __future__ import annotations

import dataclasses
import logging
import tomllib
from typing import TYPE_CHECKING, Any

import numpy as np

from glitchygames.audio.exceptions import AudioUnavailableError, SoundRecipeError
from glitchygames.audio.synth import (
    Envelope,
    FloatArray,
    Waveform,
    apply_envelope,
    distort,
    frequency_curve,
    high_pass,
    low_pass,
    mix,
    mixer_sample_rate,
    normalize,
    oscillator,
    to_sound,
    tremolo,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    import pygame

log: logging.Logger = logging.getLogger('game.audio.recipes')

RECIPE_NOISE_SEED = 0  # Fixed so a recipe sounds identical every time it renders


@dataclasses.dataclass(frozen=True)
class Tremolo:
    """Amplitude modulation settings."""

    rate_hz: float
    depth: float


@dataclasses.dataclass(frozen=True)
class Tone:
    """One layer of a sound."""

    waveform: Waveform
    start_frequency: float
    duration: float
    envelope: Envelope
    end_frequency: float | None = None  # None: constant pitch
    easing: str = 'linear'
    volume: float = 1.0
    offset: float = 0.0
    low_pass_cutoff: float | None = None
    high_pass_cutoff: float | None = None
    distortion: float | None = None
    tremolo: Tremolo | None = None

    def __post_init__(self) -> None:
        """Validate the settings.

        Raises:
            ValueError: If duration is not positive or offset/volume are negative.

        """
        if self.duration <= 0.0:
            message = f'duration must be > 0, got {self.duration}'
            raise ValueError(message)
        if self.offset < 0.0:
            message = f'offset must be >= 0, got {self.offset}'
            raise ValueError(message)
        if self.volume < 0.0:
            message = f'volume must be >= 0, got {self.volume}'
            raise ValueError(message)

    def render(self, *, sample_rate: int) -> FloatArray:
        """Render this tone (without its offset).

        Returns:
            The tone's samples.

        """
        if self.waveform is Waveform.NOISE or self.end_frequency is None:
            frequency: float | FloatArray = self.start_frequency
        else:
            frequency = frequency_curve(
                self.start_frequency, self.end_frequency, self.duration,
                easing=self.easing, sample_rate=sample_rate,
            )
        samples, _ = oscillator(
            self.waveform, frequency, self.duration, sample_rate=sample_rate,
            random_source=np.random.default_rng(RECIPE_NOISE_SEED),
        )
        if self.distortion is not None:
            samples = distort(samples, self.distortion)
        if self.low_pass_cutoff is not None:
            samples = low_pass(samples, self.low_pass_cutoff, sample_rate=sample_rate)
        if self.high_pass_cutoff is not None:
            samples = high_pass(samples, self.high_pass_cutoff, sample_rate=sample_rate)
        if self.tremolo is not None:
            samples, _ = tremolo(samples, self.tremolo.rate_hz, self.tremolo.depth,
                                 sample_rate=sample_rate)
        return apply_envelope(samples, self.envelope, sample_rate=sample_rate) * self.volume


@dataclasses.dataclass(frozen=True)
class SoundRecipe:
    """A named sound made of tones."""

    name: str
    tones: tuple[Tone, ...]
    volume: float = 0.5
    peak: float = 0.9

    def render(self, *, sample_rate: int | None = None) -> FloatArray:
        """Mix every tone at its offset and normalize to peak.

        Returns:
            The sound's samples.

        """
        rate = mixer_sample_rate() if sample_rate is None else sample_rate
        layers = [(tone.render(sample_rate=rate), tone.offset) for tone in self.tones]
        return normalize(mix(*layers, sample_rate=rate), peak=self.peak)

    def to_sound(self) -> pygame.mixer.Sound:
        """Render at the mixer's rate and wrap as a pygame Sound.

        Returns:
            The sound.

        """
        return to_sound(self.render(), volume=self.volume)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain data (TOML/JSON friendly).

        Returns:
            The recipe as a dict (without its name, which is the key it is stored under).

        """
        return {
            'volume': self.volume,
            'peak': self.peak,
            'tones': [_tone_to_dict(tone) for tone in self.tones],
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> SoundRecipe:
        """Build a recipe from to_dict() output.

        Returns:
            The recipe.

        Raises:
            SoundRecipeError: Naming the recipe and field that is invalid.

        """
        tones = []
        for index, tone_data in enumerate(data.get('tones', [])):
            tones.append(_tone_from_dict(name=name, index=index, data=tone_data))
        try:
            return cls(name=name, tones=tuple(tones), volume=float(data.get('volume', 0.5)),
                       peak=float(data.get('peak', 0.9)))
        except (TypeError, ValueError) as error:
            message = f'{name}: {error}'
            raise SoundRecipeError(message) from error


def _tone_to_dict(tone: Tone) -> dict[str, Any]:
    data: dict[str, Any] = {
        'waveform': tone.waveform.value,
        'start_frequency': tone.start_frequency,
        'duration': tone.duration,
        'envelope': dataclasses.asdict(tone.envelope),
        'easing': tone.easing,
        'volume': tone.volume,
        'offset': tone.offset,
    }
    for optional in ('end_frequency', 'low_pass_cutoff', 'high_pass_cutoff', 'distortion'):
        value = getattr(tone, optional)
        if value is not None:
            data[optional] = value
    if tone.tremolo is not None:
        data['tremolo'] = dataclasses.asdict(tone.tremolo)
    return data


def _tone_from_dict(*, name: str, index: int, data: dict[str, Any]) -> Tone:
    location = f'{name}.tones[{index}]'
    try:
        waveform = Waveform(data['waveform'])
    except (KeyError, ValueError) as error:
        message = f'{location}.waveform: {data.get("waveform")!r} is not a waveform'
        raise SoundRecipeError(message) from error
    try:
        envelope = Envelope(**data['envelope'])
    except (KeyError, TypeError) as error:
        message = f'{location}.envelope: {error}'
        raise SoundRecipeError(message) from error
    tremolo_data = data.get('tremolo')
    try:
        return Tone(
            waveform=waveform,
            start_frequency=float(data['start_frequency']),
            duration=float(data['duration']),
            envelope=envelope,
            end_frequency=data.get('end_frequency'),
            easing=data.get('easing', 'linear'),
            volume=float(data.get('volume', 1.0)),
            offset=float(data.get('offset', 0.0)),
            low_pass_cutoff=data.get('low_pass_cutoff'),
            high_pass_cutoff=data.get('high_pass_cutoff'),
            distortion=data.get('distortion'),
            tremolo=Tremolo(**tremolo_data) if tremolo_data is not None else None,
        )
    except (KeyError, TypeError, ValueError) as error:
        message = f'{location}: {error}'
        raise SoundRecipeError(message) from error


def load_sound_recipes(path: Path) -> dict[str, SoundRecipe]:
    """Load every [recipes.<name>] table from a TOML file.

    Returns:
        Recipes by name.

    """
    with path.open('rb') as recipe_file:
        document = tomllib.load(recipe_file)
    return {
        name: SoundRecipe.from_dict(name, data)
        for name, data in document.get('recipes', {}).items()
    }


class SoundBank:
    """Plays recipes by name, rendering each on first use."""

    def __init__(self, recipes: Iterable[SoundRecipe]) -> None:
        """Index the recipes by name.

        Raises:
            ValueError: If two recipes share a name.

        """
        self._recipes: dict[str, SoundRecipe] = {}
        for recipe in recipes:
            if recipe.name in self._recipes:
                message = f'duplicate sound recipe name {recipe.name!r}'
                raise ValueError(message)
            self._recipes[recipe.name] = recipe
        self._sounds: dict[tuple[str, int], pygame.mixer.Sound] = {}
        self._unavailable_logged = False

    def play(self, name: str) -> None:
        """Play a sound; a no-op (logged once) when audio is unavailable.

        Raises:
            KeyError: If no recipe has this name.

        """
        recipe = self._recipes[name]
        cache_key = (name, mixer_sample_rate())
        if cache_key not in self._sounds:
            try:
                self._sounds[cache_key] = to_sound(recipe.render(), volume=recipe.volume)
            except AudioUnavailableError:
                if not self._unavailable_logged:
                    log.warning('Audio unavailable; sound effects are silent')
                    self._unavailable_logged = True
                return
        if self._sounds[cache_key].play() is None:
            log.debug('No free mixer channel for sound %r', name)
```

- [ ] **Step 4: Run** — `uv run pytest tests/audio -v` — PASS.
- [ ] **Step 5: Checkpoint and commit.** Report.

---

### Task 13: Live voices (`audio/live.py`) and engine/manager integration

**Files:**
- Create: `glitchygames/audio/live.py`, `tests/audio/test_live.py`
- Modify: `glitchygames/engine/game_engine.py` (`_initialize_event_managers`: reserve the pool)
- Modify: `glitchygames/scenes/scene.py` (`SceneManager.live_audio`, `_update_frame_services`)
- Modify: `tests/mocks/test_mock_factory.py` (mixer mock returns real-shaped channel values)
- Modify: `glitchygames/audio/__init__.py` (export `LiveAudio`, `LiveVoice`)

**Interfaces:**
- Consumes: `oscillator`, `filter_kernel`, `apply_kernel`, `tremolo`, `to_sound`,
  `mixer_sample_rate`, `sample_count`, `Tremolo` (Tasks 9, 10, 12).
- Produces:
  - `reserve_live_voice_pool(pool_size: int) -> tuple[int, ...]`.
  - `DEFAULT_CHUNK_DURATION = 0.1`, `DEFAULT_FADE_OUT = 0.1`.
  - `VoiceState(Enum)`: `IDLE`, `PLAYING`, `PAUSED`, `FADING`, `DRAINING`, `STOPPED`.
  - `LiveVoice(*, channel: pygame.mixer.Channel | None, owner: object, waveform: Waveform,
    frequency: float, volume: float, low_pass_cutoff: float | None = None,
    tremolo: Tremolo | None = None, chunk_duration: float = 0.1, sample_rate: int,
    random_source: numpy.random.Generator | None = None)` with settable `frequency`, `volume`,
    `low_pass_cutoff`, `tremolo`; `owner`, `state`, `is_playing`; `start()`, `update()`,
    `stop(*, fade_out=0.1)`, `stop_now()`, `pause()`, `resume()`.
  - `LiveAudio(*, channel_indices: Sequence[int])` with `create_voice(*, owner, waveform,
    frequency, volume=0.5, low_pass_cutoff=None, tremolo=None,
    chunk_duration=DEFAULT_CHUNK_DURATION) -> LiveVoice`, `release_voice(voice)`,
    `update(*, active_scene, previous_scene, active_transitions: Sequence[object | None])`.
  - `GameEngine.live_voice_channels: tuple[int, ...]`; `SceneManager.live_audio` (lazy property).

- [ ] **Step 1: Fix the mixer mock first** (so engine/scene tests keep working once the engine
  reserves channels). In `tests/mocks/test_mock_factory.py` after line 1606:

```python
        mixer_mock.get_num_channels.return_value = 8  # pygame-ce's default channel count
        mixer_mock.set_reserved.side_effect = lambda count: count  # Returns the count reserved
```

Run `uv run pytest tests/mocks -q` — PASS.

- [ ] **Step 2: Failing tests** (`tests/audio/test_live.py`; every test uses a mocked `Channel`)

```python
"""Tests for real-time synth voices."""

import numpy as np
import pytest

from glitchygames.audio import live
from glitchygames.audio.live import LiveAudio, LiveVoice, VoiceState, reserve_live_voice_pool
from glitchygames.audio.recipes import Tremolo
from glitchygames.audio.synth import Waveform

RATE = 44100


@pytest.fixture
def rendered_chunks(mocker):
    """Capture every chunk the voice renders (to_sound receives the samples)."""
    chunks = []

    def fake_to_sound(samples, *, volume):
        chunks.append(samples)
        return mocker.Mock(name=f'sound{len(chunks)}')

    mocker.patch.object(live, 'to_sound', side_effect=fake_to_sound)
    return chunks


@pytest.fixture
def channel(mocker):
    channel = mocker.Mock()
    channel.get_queue.return_value = None
    channel.get_busy.return_value = True
    return channel


def _voice(channel, **overrides):
    settings = {'channel': channel, 'owner': 'scene', 'waveform': Waveform.SINE,
                'frequency': 220.0, 'volume': 0.5, 'sample_rate': RATE,
                'random_source': np.random.default_rng(5)}
    settings.update(overrides)
    return LiveVoice(**settings)


class TestPoolReservation:
    def test_grows_mixer_and_reserves_low_channels(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch('pygame.mixer.get_num_channels', return_value=8)
        set_num = mocker.patch('pygame.mixer.set_num_channels')
        mocker.patch('pygame.mixer.set_reserved', side_effect=lambda count: count)
        assert reserve_live_voice_pool(4) == (0, 1, 2, 3)
        set_num.assert_called_once_with(12)

    def test_zero_pool_or_no_mixer_reserves_nothing(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        assert reserve_live_voice_pool(4) == ()


class TestLiveVoiceChunks:
    def test_start_plays_then_update_queues(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        channel.play.assert_called_once()
        voice.update()
        channel.queue.assert_called_once()
        assert len(rendered_chunks[0]) == 4410  # 100 ms at 44100 Hz

    def test_update_waits_while_queue_full(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        channel.get_queue.return_value = object()
        voice.update()
        channel.queue.assert_not_called()

    def test_phase_continuous_across_chunks(self, channel, rendered_chunks):
        voice = _voice(channel, volume=1.0)
        voice.start()
        voice.update()
        joined = np.concatenate(rendered_chunks)
        expected = np.sin(2 * np.pi * 220.0 * np.arange(len(joined)) / RATE)
        np.testing.assert_allclose(joined, expected, atol=1e-9)

    def test_frequency_change_ramps_over_one_chunk(self, channel, rendered_chunks):
        voice = _voice(channel, volume=1.0)  # SINE: a sawtooth reset could land on the boundary
        voice.start()
        voice.frequency = 440.0
        voice.update()
        second = rendered_chunks[1]
        # No discontinuity at the boundary: first sample of chunk 2 continues chunk 1
        assert abs(second[0] - rendered_chunks[0][-1]) < 0.1

    def test_volume_change_ramps(self, channel, rendered_chunks):
        voice = _voice(channel, volume=0.0)
        voice.start()
        voice.volume = 1.0
        voice.update()
        envelope = np.abs(rendered_chunks[1])
        assert envelope[:100].max() < 0.05
        assert envelope[-200:].max() > 0.9

    def test_filter_and_tremolo_continue_across_chunks(self, channel, rendered_chunks):
        # 233 Hz: 23.3 cycles per 100 ms chunk, so no sawtooth reset falls on the boundary
        voice = _voice(channel, volume=1.0, waveform=Waveform.SAWTOOTH, frequency=233.0,
                       low_pass_cutoff=800.0, tremolo=Tremolo(rate_hz=7.0, depth=0.5))
        voice.start()
        voice.update()
        boundary_step = abs(rendered_chunks[1][0] - rendered_chunks[0][-1])
        typical_step = np.median(np.abs(np.diff(rendered_chunks[0])))
        assert boundary_step < typical_step * 4

    def test_cutoff_change_crossfades(self, channel, rendered_chunks):
        voice = _voice(channel, volume=1.0, waveform=Waveform.SAWTOOTH, frequency=233.0,
                       low_pass_cutoff=4000.0)
        voice.start()
        voice.low_pass_cutoff = 300.0
        voice.update()
        assert abs(rendered_chunks[1][0] - rendered_chunks[0][-1]) < 0.2


class TestLiveVoiceStopping:
    def test_stop_fades_then_drains_without_channel_stop(self, channel, rendered_chunks):
        voice = _voice(channel, volume=1.0)
        voice.start()
        voice.stop(fade_out=0.1)
        voice.update()
        assert abs(rendered_chunks[-1][-1]) < 1e-9  # Faded to silence
        assert voice.state is VoiceState.DRAINING
        voice.update()
        assert channel.queue.call_count == 1  # No more chunks after the fade
        channel.stop.assert_not_called()  # stop()/fadeout() would start the queued chunk
        assert voice.is_playing
        channel.get_busy.return_value = False
        assert not voice.is_playing

    def test_stop_now_silences_immediately(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        voice.stop_now()
        assert channel.stop.call_count == 2  # First starts the queued chunk, second stops it
        assert voice.state is VoiceState.STOPPED

    def test_setters_on_stopped_voice_are_ignored(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        voice.stop_now()
        voice.frequency = 999.0
        voice.update()
        assert len(rendered_chunks) == 1

    def test_underrun_recovers(self, channel, rendered_chunks, mocker):
        """Review focus 5: a long hitch drains the channel; the voice restarts."""
        debug = mocker.patch.object(live.log, 'debug')
        voice = _voice(channel)
        voice.start()
        channel.get_busy.return_value = False
        voice.update()
        assert debug.called
        assert channel.queue.call_count + channel.play.call_count >= 2

    def test_pause_and_resume(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        voice.pause()
        channel.pause.assert_called_once()
        voice.update()
        channel.queue.assert_not_called()
        voice.resume()
        channel.unpause.assert_called_once()

    def test_silent_voice_without_channel(self, rendered_chunks):
        voice = _voice(None)
        voice.start()
        voice.update()
        voice.stop_now()
        assert not voice.is_playing
        assert rendered_chunks == []


class TestLiveAudio:
    @pytest.fixture
    def audio(self, mocker, rendered_chunks):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch('pygame.mixer.Channel', side_effect=lambda index: mocker.Mock(
            name=f'channel{index}', get_queue=mocker.Mock(return_value=None),
            get_busy=mocker.Mock(return_value=True)))
        return LiveAudio(channel_indices=(0, 1))

    def _create(self, audio, owner):
        return audio.create_voice(owner=owner, waveform=Waveform.SINE, frequency=100.0)

    def test_pool_exhaustion_raises_at_limit_plus_one(self, audio):
        self._create(audio, 'scene')
        self._create(audio, 'scene')
        with pytest.raises(ValueError, match='live-voice-pool'):
            self._create(audio, 'scene')

    def test_released_channels_are_reused(self, audio):
        first = self._create(audio, 'scene')
        self._create(audio, 'scene')
        audio.release_voice(first)
        assert self._create(audio, 'scene') is not None

    def test_owner_rules(self, audio):
        active = self._create(audio, 'active')
        paused = self._create(audio, 'previous')
        active.start()
        paused.start()
        audio.update(active_scene='active', previous_scene='previous', active_transitions=())
        assert paused.state is VoiceState.PAUSED
        audio.update(active_scene='other', previous_scene='active', active_transitions=())
        assert active.state is VoiceState.PAUSED
        assert paused.state is VoiceState.STOPPED  # Abandoned owner: released
        assert self._create(audio, 'new') is not None  # Its channel was freed

    def test_transition_owner_survives_until_transition_ends(self, audio):
        transition = object()
        voice = self._create(audio, transition)
        voice.start()
        audio.update(active_scene='new', previous_scene='old', active_transitions=(transition,))
        assert voice.state is VoiceState.PLAYING
        audio.update(active_scene='new', previous_scene='old', active_transitions=(None,))
        assert voice.state is VoiceState.STOPPED

    def test_no_mixer_returns_silent_voice(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        voice = LiveAudio(channel_indices=()).create_voice(
            owner='scene', waveform=Waveform.SINE, frequency=100.0)
        voice.start()
        assert not voice.is_playing
```

- [ ] **Step 3: Run** — FAIL (module missing).

- [ ] **Step 4: Implement `glitchygames/audio/live.py`**

```python
"""Real-time synth voices streamed through reserved mixer channels.

pygame has no audio callback, so each voice renders short chunks from the game loop and keeps
one chunk queued behind the one playing (pygame holds one queued Sound per channel). The safety
margin is the rest of the playing chunk minus one device buffer: about 88 ms at 44100 Hz with a
512-sample buffer and 100 ms chunks. A longer frame underruns; the voice restarts next update.

Channel facts this module relies on (pygame-ce 2.5.8): Channel.stop() and Channel.fadeout()
start the queued sound, so fades are rendered into the samples and stop_now() calls stop()
twice; set_reserved(n) reserves channels 0..n-1; set_num_channels(smaller) stops sounds on the
removed channels, so the pool is reserved once at startup and never resized.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

import numpy as np
import pygame

from glitchygames.audio.synth import (
    DEFAULT_FILTER_TAPS,
    FloatArray,
    Waveform,
    apply_kernel,
    filter_kernel,
    mixer_sample_rate,
    oscillator,
    sample_count,
    to_sound,
    tremolo,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.recipes import Tremolo

log: logging.Logger = logging.getLogger('game.audio.live')

DEFAULT_CHUNK_DURATION = 0.1
DEFAULT_FADE_OUT = 0.1


def reserve_live_voice_pool(pool_size: int) -> tuple[int, ...]:
    """Reserve channels for live voices; call once at startup before any sound plays.

    Grows the mixer by pool_size channels, then reserves channels 0..pool_size-1. Nothing is
    playing yet, so those channels are idle, and one-shot sounds keep the original count.

    Returns:
        The reserved channel indices (empty without a mixer or with pool_size 0).

    Raises:
        ValueError: If pool_size is negative.

    """
    if pool_size < 0:
        message = f'pool_size must be >= 0, got {pool_size}'
        raise ValueError(message)
    if pool_size == 0 or pygame.mixer.get_init() is None:
        return ()
    original_count = pygame.mixer.get_num_channels()
    pygame.mixer.set_num_channels(original_count + pool_size)
    reserved_count = pygame.mixer.set_reserved(pool_size)
    return tuple(range(reserved_count))


class VoiceState(enum.Enum):
    """Lifecycle of a live voice."""

    IDLE = 'idle'
    PLAYING = 'playing'
    PAUSED = 'paused'
    FADING = 'fading'
    DRAINING = 'draining'
    STOPPED = 'stopped'


class LiveVoice:
    """An oscillator whose parameters can change every frame."""

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        *,
        channel: pygame.mixer.Channel | None,
        owner: object,
        waveform: Waveform,
        frequency: float,
        volume: float,
        low_pass_cutoff: float | None = None,
        tremolo: Tremolo | None = None,
        chunk_duration: float = DEFAULT_CHUNK_DURATION,
        sample_rate: int,
        random_source: np.random.Generator | None = None,
    ) -> None:
        """Create a stopped voice; channel None makes a silent no-op voice."""
        self._channel = channel
        self.owner = owner
        self._waveform = waveform
        self._sample_rate = sample_rate
        self._chunk_samples = sample_count(chunk_duration, sample_rate)
        self._random_source = random_source or np.random.default_rng()
        self._target_frequency = frequency
        self._rendered_frequency = frequency
        self._target_volume = volume
        self._rendered_volume = volume
        self._target_cutoff = low_pass_cutoff
        self._rendered_cutoff = low_pass_cutoff
        self._tremolo = tremolo
        self._oscillator_phase = 0.0
        self._tremolo_phase = 0.0
        self._filter_history = np.zeros(DEFAULT_FILTER_TAPS - 1)
        self._fade_total_samples = 0
        self._fade_remaining_samples = 0
        self._state = VoiceState.IDLE

    # --- Parameters (ignored once the voice is stopping or stopped) ---

    @property
    def frequency(self) -> float:
        """Target frequency in Hz."""
        return self._target_frequency

    @frequency.setter
    def frequency(self, value: float) -> None:
        if self._accepts_changes:
            self._target_frequency = value

    @property
    def volume(self) -> float:
        """Target volume 0.0-1.0."""
        return self._target_volume

    @volume.setter
    def volume(self, value: float) -> None:
        if self._accepts_changes:
            self._target_volume = value

    @property
    def low_pass_cutoff(self) -> float | None:
        """Target low-pass cutoff in Hz (None: unfiltered)."""
        return self._target_cutoff

    @low_pass_cutoff.setter
    def low_pass_cutoff(self, value: float | None) -> None:
        if self._accepts_changes:
            self._target_cutoff = value

    @property
    def tremolo(self) -> Tremolo | None:
        """Tremolo settings (None: off)."""
        return self._tremolo

    @tremolo.setter
    def tremolo(self, value: Tremolo | None) -> None:
        if self._accepts_changes:
            self._tremolo = value

    @property
    def _accepts_changes(self) -> bool:
        return self._state in {VoiceState.IDLE, VoiceState.PLAYING, VoiceState.PAUSED}

    @property
    def state(self) -> VoiceState:
        """Current lifecycle state."""
        return self._state

    @property
    def is_playing(self) -> bool:
        """True from start() until the channel has drained (paused counts as playing)."""
        if self._channel is None:
            return False
        if self._state in {VoiceState.PLAYING, VoiceState.PAUSED, VoiceState.FADING}:
            return True
        return self._state is VoiceState.DRAINING and bool(self._channel.get_busy())

    # --- Lifecycle ---

    def start(self) -> None:
        """Start playing (renders and plays the first chunk)."""
        if self._channel is None or self._state is not VoiceState.IDLE:
            return
        self._state = VoiceState.PLAYING
        self._channel.play(to_sound(self._render_chunk(), volume=1.0))

    def update(self) -> None:
        """Keep one chunk queued; call once per frame."""
        if self._channel is None or self._state not in {VoiceState.PLAYING, VoiceState.FADING}:
            return
        if not self._channel.get_busy():
            log.debug('Live voice underrun; restarting')
            self._channel.play(to_sound(self._render_chunk(), volume=1.0))
            return
        if self._channel.get_queue() is None:
            self._channel.queue(to_sound(self._render_chunk(), volume=1.0))

    def stop(self, *, fade_out: float = DEFAULT_FADE_OUT) -> None:
        """Fade to silence over fade_out seconds of rendered audio, then drain."""
        if self._channel is None or self._state not in {VoiceState.PLAYING, VoiceState.PAUSED}:
            return
        if self._state is VoiceState.PAUSED:
            self._channel.unpause()
        self._fade_total_samples = max(1, sample_count(fade_out, self._sample_rate))
        self._fade_remaining_samples = self._fade_total_samples
        self._state = VoiceState.FADING

    def stop_now(self) -> None:
        """Silence immediately: the first stop() starts the queued chunk, the second stops it."""
        if self._channel is not None and self._state is not VoiceState.STOPPED:
            self._channel.stop()
            self._channel.stop()
        self._state = VoiceState.STOPPED

    def pause(self) -> None:
        """Pause; the queued chunk is kept."""
        if self._channel is not None and self._state is VoiceState.PLAYING:
            self._channel.pause()
            self._state = VoiceState.PAUSED

    def resume(self) -> None:
        """Resume after pause()."""
        if self._channel is not None and self._state is VoiceState.PAUSED:
            self._channel.unpause()
            self._state = VoiceState.PLAYING

    # --- Rendering ---

    def _render_chunk(self) -> FloatArray:
        count = self._chunk_samples
        ramp = np.arange(1, count + 1) / count  # Reaches the target on the last sample
        frequencies = self._rendered_frequency + (
            self._target_frequency - self._rendered_frequency
        ) * ramp
        volumes = self._rendered_volume + (self._target_volume - self._rendered_volume) * ramp
        self._rendered_frequency = self._target_frequency
        self._rendered_volume = self._target_volume

        raw, self._oscillator_phase = oscillator(
            self._waveform, frequencies, count / self._sample_rate,
            sample_rate=self._sample_rate, phase=self._oscillator_phase,
            random_source=self._random_source,
        )
        samples = self._filtered(raw=raw, ramp=ramp)
        self._filter_history = np.concatenate((self._filter_history, raw))[
            -(DEFAULT_FILTER_TAPS - 1) :
        ]
        if self._tremolo is not None:
            samples, self._tremolo_phase = tremolo(
                samples, self._tremolo.rate_hz, self._tremolo.depth,
                sample_rate=self._sample_rate, phase=self._tremolo_phase,
            )
        samples = samples * volumes
        if self._state is VoiceState.FADING:
            samples = samples * self._fade_gains(count)
        return samples

    def _filtered(self, *, raw: FloatArray, ramp: FloatArray) -> FloatArray:
        """Apply the low-pass, crossfading old and new outputs when the cutoff changes."""
        old_output = self._apply_cutoff(raw=raw, cutoff=self._rendered_cutoff)
        if self._target_cutoff == self._rendered_cutoff:
            return old_output
        new_output = self._apply_cutoff(raw=raw, cutoff=self._target_cutoff)
        self._rendered_cutoff = self._target_cutoff
        return old_output * (1.0 - ramp) + new_output * ramp

    def _apply_cutoff(self, *, raw: FloatArray, cutoff: float | None) -> FloatArray:
        if cutoff is None:
            return raw
        kernel = filter_kernel(cutoff, sample_rate=self._sample_rate,
                               taps=DEFAULT_FILTER_TAPS, high_pass=False)
        return apply_kernel(raw, kernel, history=self._filter_history)

    def _fade_gains(self, count: int) -> FloatArray:
        positions = self._fade_remaining_samples - np.arange(1, count + 1)
        gains = np.clip(positions / self._fade_total_samples, 0.0, 1.0)
        self._fade_remaining_samples -= count
        if self._fade_remaining_samples <= 0:
            self._state = VoiceState.DRAINING
        return gains


class LiveAudio:
    """Owns the live voice pool and applies the owner rules every frame."""

    def __init__(self, *, channel_indices: Sequence[int]) -> None:
        """Use the channels reserved by reserve_live_voice_pool()."""
        self._pool_size = len(channel_indices)
        self._free_channel_indices = list(channel_indices)
        self._voice_channels: dict[int, int] = {}  # id(voice) -> channel index
        self._voices: list[LiveVoice] = []
        self._unavailable_logged = False

    def create_voice(  # ruff: ignore[too-many-arguments]
        self,
        *,
        owner: object,
        waveform: Waveform,
        frequency: float,
        volume: float = 0.5,
        low_pass_cutoff: float | None = None,
        tremolo: Tremolo | None = None,
        chunk_duration: float = DEFAULT_CHUNK_DURATION,
    ) -> LiveVoice:
        """Create a stopped voice on a free pool channel.

        Without a mixer the voice is a silent no-op (logged once).

        Returns:
            The voice; call start() to hear it.

        Raises:
            ValueError: If every pool channel is in use.

        """
        settings = {'owner': owner, 'waveform': waveform, 'frequency': frequency,
                    'volume': volume, 'low_pass_cutoff': low_pass_cutoff, 'tremolo': tremolo,
                    'chunk_duration': chunk_duration}
        if pygame.mixer.get_init() is None:
            if not self._unavailable_logged:
                log.warning('Audio unavailable; live voices are silent')
                self._unavailable_logged = True
            return LiveVoice(channel=None, sample_rate=mixer_sample_rate(), **settings)
        if not self._free_channel_indices:
            message = (
                f'All {self._pool_size} live voice channels are in use; '
                'raise --live-voice-pool'
            )
            raise ValueError(message)
        channel_index = self._free_channel_indices.pop(0)
        voice = LiveVoice(channel=pygame.mixer.Channel(channel_index),
                          sample_rate=mixer_sample_rate(), **settings)
        self._voice_channels[id(voice)] = channel_index
        self._voices.append(voice)
        return voice

    def release_voice(self, voice: LiveVoice) -> None:
        """Silence a voice and return its channel to the pool."""
        voice.stop_now()
        if voice in self._voices:
            self._voices.remove(voice)
            self._free_channel_indices.append(self._voice_channels.pop(id(voice)))

    def update(
        self,
        *,
        active_scene: object | None,
        previous_scene: object | None,
        active_transitions: Sequence[object | None],
    ) -> None:
        """Play voices of active owners, pause the paused scene's, release the rest.

        Args:
            active_scene: SceneManager.active_scene.
            previous_scene: SceneManager.previous_scene (what a PauseScene returns to).
            active_transitions: The running transition and the pending one (either may be
                None); a voice created for a ride is owned by its transition.

        """
        live_transitions = [transition for transition in active_transitions if transition]
        for voice in list(self._voices):
            owner = voice.owner
            if owner is active_scene or any(owner is t for t in live_transitions):
                voice.resume()
                voice.update()
            elif owner is previous_scene:
                voice.pause()
            else:
                self.release_voice(voice)
```

(Name the generator variable `transition` in full in the `any(...)`; it is abbreviated above only
for line length — expand it and wrap the line.)

- [ ] **Step 5: Run** — `uv run pytest tests/audio/test_live.py -v` — PASS. If
  `test_phase_continuous_across_chunks` fails at the boundary, check that `_render_chunk` passes
  `count / sample_rate` and that `oscillator` returns exactly `count` samples.

- [ ] **Step 6: Engine and manager integration.**
  - `game_engine.py` `_initialize_event_managers`, right after `self.audio_manager = ...`:

```python
        # Reserve live synth voice channels now, before anything can play (see audio/live.py)
        from glitchygames.audio.live import reserve_live_voice_pool

        self.live_voice_channels: tuple[int, ...] = reserve_live_voice_pool(
            int(GameEngine.OPTIONS.get('live_voice_pool', DEFAULT_LIVE_VOICE_POOL))
        )
```

  (Use a module-level import instead if the file's import graph allows; follow how the file
  imports `AppEventManager` locally.)
  - `scene.py` `SceneManager.__init__`: `self._live_audio: LiveAudio | None = None`. Add:

```python
    @property
    def live_audio(self: Self) -> LiveAudio:
        """Live synth voices, created on first use from the engine's reserved channels."""
        if self._live_audio is None:
            channels = getattr(self.game_engine, 'live_voice_channels', ())
            self._live_audio = LiveAudio(channel_indices=channels)
        return self._live_audio
```

  - `_update_frame_services`, at the end:

```python
        if self._live_audio is not None:
            pending_transition = (
                self._pending_transition[1] if self._pending_transition is not None else None
            )
            self._live_audio.update(
                active_scene=self.active_scene,
                previous_scene=self.previous_scene,
                active_transitions=(self._active_transition, pending_transition),
            )
```

  (The pending transition counts because Clockwork Keep creates the motor before
  `transition_to` starts it; without it the voice would be released that same frame.)

- [ ] **Step 7: Integration tests** (append to `tests/scenes/test_scene_manager.py`)

```python
    def test_live_audio_is_lazy_and_updated_with_pending_transition(self, mocker):
        manager = self.scene_manager
        manager._live_audio = None
        manager._update_frame_services()  # No LiveAudio created by merely running frames
        assert manager._live_audio is None
        live_audio = mocker.Mock()
        manager._live_audio = live_audio
        pending = mocker.Mock()
        manager._pending_transition = (mocker.Mock(), pending)
        manager._update_frame_services()
        assert live_audio.update.call_args.kwargs['active_transitions'][1] is pending
        manager._pending_transition = None
        manager._live_audio = None
```

- [ ] **Step 8: Run** — `uv run pytest tests/audio tests/scenes tests/engine tests/mocks -q` — PASS.
- [ ] **Step 9: Checkpoint and commit.** Report.

---

### Task 14: Clockwork Keep sounds, motor, shake and land edge

**Files:**
- Create: `glitchygames/examples/clockwork_keep/sounds.py`
- Modify: `glitchygames/examples/clockwork_keep/constants.py`, `.../game.py`
- Test: `tests/examples/test_clockwork_keep.py`

**Interfaces:**
- Consumes: everything above.
- Produces (in `sounds.py`): recipe constants `JUMP`, `LAND`, `COG_PICKUP`, `DEATH`, `GAME_OVER`,
  `ELEVATOR_CLANK` and `ALL_RECIPES`; in `game.py`: `ClockworkKeepScene.sounds: SoundBank`,
  `_try_jump()`, `_update_elevator_motor(transition)`, `_elevator_arrived()`,
  `apply_camera_to_sprites()` override.

- [ ] **Step 1: Constants** (append to `constants.py`)

```python
# --- Elevator ride feel (tuned by eye and ear) ---
ELEVATOR_RIDE_DURATION = 4.0
ELEVATOR_RIDE_EASING = 'ease_in_sine'  # Arrives at speed so the stop reads as a slam
ELEVATOR_SPEED_SAMPLES = 100  # Points used to find the easing's peak slope
ELEVATOR_MOTOR_IDLE_FREQUENCY = 45.0  # Hz, motor at rest
ELEVATOR_MOTOR_PEAK_FREQUENCY = 110.0  # Hz, motor at full speed
ELEVATOR_MOTOR_MINIMUM_VOLUME = 0.15
ELEVATOR_MOTOR_MAXIMUM_VOLUME = 0.6
ELEVATOR_MOTOR_LOW_PASS_CUTOFF = 600.0  # Hz, keeps the sawtooth deep
ELEVATOR_MOTOR_TREMOLO_RATE = 8.0  # Hz, the motor's chug
ELEVATOR_MOTOR_TREMOLO_DEPTH = 0.4
ELEVATOR_BOUNCE_STRENGTH = 14.0  # Pixels
ELEVATOR_BOUNCE_DURATION = 0.6
ELEVATOR_BOUNCE_FREQUENCY = 7.0  # Hz
ELEVATOR_RATTLE_STRENGTH = 5.0
ELEVATOR_RATTLE_DURATION = 0.35
ELEVATOR_RATTLE_FREQUENCY = 25.0
```

- [ ] **Step 2: `sounds.py`**

```python
"""Clockwork Keep's steampunk sound effects as synth recipes.

Brassy squares and saws, filtered noise for steam, low booms. Values are starting points
tuned by ear; edit them freely.
"""

from glitchygames.audio.recipes import SoundRecipe, Tone, Tremolo
from glitchygames.audio.synth import Envelope, Waveform

JUMP = SoundRecipe(
    name='jump',
    volume=0.35,
    tones=(
        Tone(waveform=Waveform.SQUARE, start_frequency=330.0, end_frequency=660.0,
             duration=0.1, envelope=Envelope(attack=0.005, decay=0.03, sustain_level=0.6,
                                             release=0.05), volume=0.6),
        Tone(waveform=Waveform.NOISE, start_frequency=0.0, duration=0.08,
             envelope=Envelope(attack=0.002, decay=0.02, sustain_level=0.3, release=0.05),
             volume=0.25, high_pass_cutoff=2000.0),
    ),
)

LAND = SoundRecipe(
    name='land',
    volume=0.3,
    tones=(
        Tone(waveform=Waveform.SINE, start_frequency=110.0, end_frequency=55.0, duration=0.09,
             envelope=Envelope(attack=0.002, decay=0.03, sustain_level=0.5, release=0.05),
             low_pass_cutoff=400.0),
        Tone(waveform=Waveform.NOISE, start_frequency=0.0, duration=0.04,
             envelope=Envelope(attack=0.001, decay=0.01, sustain_level=0.3, release=0.02),
             volume=0.3, low_pass_cutoff=800.0),
    ),
)

COG_PICKUP = SoundRecipe(
    name='cog_pickup',
    volume=0.3,
    tones=(
        Tone(waveform=Waveform.TRIANGLE, start_frequency=1318.5, duration=0.08,
             envelope=Envelope(attack=0.002, decay=0.02, sustain_level=0.5, release=0.05)),
        Tone(waveform=Waveform.TRIANGLE, start_frequency=1975.5, duration=0.12, offset=0.07,
             envelope=Envelope(attack=0.002, decay=0.03, sustain_level=0.5, release=0.08)),
    ),
)

DEATH = SoundRecipe(
    name='death',
    volume=0.4,
    tones=(
        Tone(waveform=Waveform.SAWTOOTH, start_frequency=440.0, end_frequency=55.0,
             easing='ease_in_quad', duration=0.7,
             envelope=Envelope(attack=0.005, decay=0.1, sustain_level=0.8, release=0.3),
             low_pass_cutoff=2500.0, tremolo=Tremolo(rate_hz=18.0, depth=0.5)),
    ),
)

GAME_OVER = SoundRecipe(
    name='game_over',
    volume=0.4,
    tones=tuple(
        Tone(waveform=Waveform.TRIANGLE, start_frequency=frequency, duration=duration,
             offset=offset,
             envelope=Envelope(attack=0.01, decay=0.05, sustain_level=0.7, release=0.2))
        for frequency, offset, duration in ((659.25, 0.0, 0.35), (523.25, 0.35, 0.35),
                                            (440.0, 0.7, 0.6))
    ),
)

ELEVATOR_CLANK = SoundRecipe(
    name='elevator_clank',
    volume=0.6,
    tones=(
        Tone(waveform=Waveform.NOISE, start_frequency=0.0, duration=0.25,
             envelope=Envelope(attack=0.001, decay=0.05, sustain_level=0.3, release=0.15),
             volume=0.7, distortion=4.0, low_pass_cutoff=3000.0),
        Tone(waveform=Waveform.SINE, start_frequency=70.0, end_frequency=40.0, duration=0.9,
             envelope=Envelope(attack=0.002, decay=0.1, sustain_level=0.6, release=0.6)),
        Tone(waveform=Waveform.SQUARE, start_frequency=880.0, duration=0.3, offset=0.01,
             envelope=Envelope(attack=0.001, decay=0.02, sustain_level=0.2, release=0.25),
             volume=0.25, high_pass_cutoff=600.0),
    ),
)

ALL_RECIPES = (JUMP, LAND, COG_PICKUP, DEATH, GAME_OVER, ELEVATOR_CLANK)
```

- [ ] **Step 3: Failing tests** (append to `tests/examples/test_clockwork_keep.py`)

```python
from glitchygames.audio.live import VoiceState
from glitchygames.effects.shake import ShakeStyle
from glitchygames.examples.clockwork_keep import sounds as clockwork_sounds


@pytest.fixture
def played(clockwork_scene, mocker):
    return mocker.patch.object(clockwork_scene.sounds, 'play')


class TestRecipes:
    @pytest.mark.parametrize('recipe', clockwork_sounds.ALL_RECIPES, ids=lambda r: r.name)
    def test_every_recipe_renders(self, recipe):
        samples = recipe.render(sample_rate=44100)
        assert len(samples) > 0
        assert abs(samples).max() == pytest.approx(recipe.peak)


class TestGameplaySounds:
    def test_jump_plays_once_when_jump_happens(self, clockwork_scene, played):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_SPACE)
        _press_key(clockwork_scene, pygame.K_SPACE)  # Airborne now: no second jump
        assert [call.args[0] for call in played.call_args_list].count('jump') == 1

    def test_land_plays_once_on_landing(self, clockwork_scene, played):
        _stand_on_first_elevator(clockwork_scene)
        played.reset_mock()
        clockwork_scene.player.velocity_y = 0.0
        clockwork_scene.player.world_y -= 40  # Lift into the air
        for _ in range(60):
            clockwork_scene.dt_tick(FRAME_TIME)
        assert [call.args[0] for call in played.call_args_list].count('land') == 1

    def test_first_tick_never_plays_land(self, clockwork_scene, played):
        """_start_transition runs one off-screen dt_tick(0.001) on the new scene."""
        clockwork_scene.dt_tick(0.001)
        assert 'land' not in [call.args[0] for call in played.call_args_list]

    def test_respawn_does_not_play_land(self, clockwork_scene, played):
        _stand_on_first_elevator(clockwork_scene)
        clockwork_scene.player.world_y -= 40
        clockwork_scene.dt_tick(FRAME_TIME)
        clockwork_scene._respawn_player()
        played.reset_mock()
        for _ in range(60):
            clockwork_scene.tweens.update(FRAME_TIME)
            clockwork_scene.dt_tick(FRAME_TIME)
        # Landing after the respawn tween can play once; the tween's direct on_ground=True can't
        assert [call.args[0] for call in played.call_args_list].count('land') <= 1

    def test_cog_pickup(self, clockwork_scene, played):
        cog = clockwork_scene.collectible_sprites[0]
        clockwork_scene.player.world_x = cog.world_x
        clockwork_scene.player.world_y = cog.world_y
        clockwork_scene._check_collectibles()
        played.assert_any_call('cog_pickup')

    def test_death_with_lives_left(self, clockwork_scene, played):
        clockwork_scene.player.lives = 2
        clockwork_scene._player_die()
        played.assert_any_call('death')

    def test_game_over_on_last_life(self, clockwork_scene, played, mocker):
        mocker.patch.object(clockwork_scene, '_save_high_score')
        mocker.patch.object(clockwork_scene, '_load_high_scores', return_value=[])
        clockwork_scene.player.lives = 1
        clockwork_scene._player_die()
        played.assert_any_call('game_over')


class TestElevatorRide:
    def _ride(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_w)
        clockwork_scene.dt_tick(FRAME_TIME)
        return clockwork_scene.transition_to.call_args.args[1]

    def test_motor_follows_car_speed_then_arrival_shakes_and_stops(
        self, clockwork_scene, played, mocker
    ):
        voice = mocker.Mock(state=VoiceState.PLAYING)
        create_voice = mocker.patch.object(
            clockwork_scene.scene_manager.live_audio, 'create_voice', return_value=voice)
        screen_shake = mocker.patch.object(clockwork_scene.scene_manager.screen_shake, 'add')
        transition = self._ride(clockwork_scene)
        assert create_voice.call_args.kwargs['owner'] is transition
        voice.start.assert_called_once()

        old, new = pygame.Surface((800, 480)), pygame.Surface((800, 480))
        transition.start(old, new)
        transition.update(0.5)
        slow_frequency = voice.frequency
        transition.update(3.0)
        assert voice.frequency > slow_frequency  # Accelerating into the stop
        transition.update(1.0)  # Arrives

        voice.stop_now.assert_called_once()
        played.assert_any_call('elevator_clank')
        styles = [call.args[0].style for call in screen_shake.call_args_list]
        assert styles == [ShakeStyle.BOUNCE, ShakeStyle.NOISE]
        assert all(call.args[0].rumble is not None for call in screen_shake.call_args_list)

    def test_ride_without_free_voice_is_silent_not_fatal(self, clockwork_scene, played, mocker):
        """Review focus 2: --live-voice-pool 0 or a full pool still rides."""
        mocker.patch.object(clockwork_scene.scene_manager.live_audio, 'create_voice',
                            side_effect=ValueError('All 0 live voice channels are in use'))
        transition = self._ride(clockwork_scene)
        transition.start(pygame.Surface((800, 480)), pygame.Surface((800, 480)))
        assert transition.update(5.0) is True
        played.assert_any_call('elevator_clank')

    def test_apply_camera_to_sprites_repositions(self, clockwork_scene):
        clockwork_scene.camera.world_y = 37.0
        clockwork_scene.apply_camera_to_sprites()
        platform = clockwork_scene.platform_sprites[0]
        assert platform.rect.y == round(platform.world_y - 37.0)
```

(If `Platform.apply_camera` sets a different rect attribute, assert on what it sets.)

- [ ] **Step 4: Run** — FAIL.

- [ ] **Step 5: Implement in `game.py`.**
  - Imports: `ShakeTarget`, `Shake`, `ShakeStyle`, `ShakeAxis`, `RumbleSettings` from
    `glitchygames.effects.shake`; `SoundBank`, `Tremolo` from `glitchygames.audio.recipes`;
    `Waveform` from `glitchygames.audio.synth`; `ALL_RECIPES` from `.sounds`; the new constants.
  - Module constants for the two arrival shakes:

```python
ELEVATOR_STOP_BOUNCE = Shake(
    style=ShakeStyle.BOUNCE,
    strength=ELEVATOR_BOUNCE_STRENGTH,
    duration=ELEVATOR_BOUNCE_DURATION,
    frequency=ELEVATOR_BOUNCE_FREQUENCY,
    axis=ShakeAxis.VERTICAL,
    rumble=RumbleSettings(low_frequency=0.9, high_frequency=0.3),
)
ELEVATOR_STOP_RATTLE = Shake(
    style=ShakeStyle.NOISE,
    strength=ELEVATOR_RATTLE_STRENGTH,
    duration=ELEVATOR_RATTLE_DURATION,
    frequency=ELEVATOR_RATTLE_FREQUENCY,
    rumble=RumbleSettings(low_frequency=0.3, high_frequency=0.6),
)
```

  - `__init__`: pass `shake_intensity=self.options.get('screen_shake_intensity', 1.0)` to
    `Camera2D(...)`; add `self.sounds = SoundBank(ALL_RECIPES)`,
    `self._was_grounded: bool | None = None  # Set from the first real collision result`,
    `self._elevator_motor: LiveVoice | None = None`, `self._elevator_peak_velocity = 1.0`.
  - Move the camera-apply loop at the end of `dt_tick` into an override and call it there:

```python
    @override
    def apply_camera_to_sprites(self: Self) -> None:
        """Position every world-space sprite from the camera."""
        self.player.apply_camera(self.camera)
        for platform in self.platform_sprites:
            platform.apply_camera(self.camera)
        for elevator in self.elevator_sprites:
            elevator.apply_camera(self.camera)
        for cog in self.collectible_sprites:
            cog.apply_camera(self.camera)
```

  - `dt_tick`, right after `self._resolve_ground_collision()`: `self._play_land_on_touchdown()`:

```python
    def _play_land_on_touchdown(self: Self) -> None:
        """Play land on the frame the player touches down.

        Ground collision resets on_ground to False and back every frame, so this compares
        with the previous frame's result. The first result only initializes the edge (the
        transition's off-screen dt_tick must not play it), and respawning resets it (the
        respawn tween sets on_ground directly).
        """
        if self.player.is_respawning:
            self._was_grounded = None
            return
        grounded = self.player.on_ground
        if self._was_grounded is False and grounded:
            self.sounds.play('land')
        self._was_grounded = grounded
```

  - Replace the three jump branches in `on_key_down_event`, `on_joy_button_down_event`,
    `on_controller_button_down_event` with `if action == 'jump': self._try_jump()` (keep each
    handler's other branches), and add:

```python
    def _try_jump(self: Self) -> None:
        """Jump if standing on something, with its sound."""
        if self.player.on_ground:
            self.player.jump(running=self.actions.is_held('run'))
            self.sounds.play('jump')
```

  - `_check_collectibles`: after `self.player.score += cog.points`, `self.sounds.play('cog_pickup')`.
  - `_player_die`: in the `lives <= 0` branch, `self.sounds.play('game_over')` before the
    transition; in the `else` branch, `self.sounds.play('death')` before `_respawn_player()`.
  - `_go_to_next_floor`:

```python
        transition = ElevatorTransition(
            duration=ELEVATOR_RIDE_DURATION,
            easing=ELEVATOR_RIDE_EASING,
            wall_color=_FLOOR_THEMES[self.floor_index][0],
            wall_accent=_FLOOR_THEMES[self.floor_index][1],
            player_surface=self.player.image,
            on_update=self._update_elevator_motor,
        )
        self._elevator_peak_velocity = max(
            transition.eased_velocity_at(step / ELEVATOR_SPEED_SAMPLES)
            for step in range(ELEVATOR_SPEED_SAMPLES + 1)
        )
        self._elevator_motor = self._start_elevator_motor(owner=transition)
        transition.add_cue(1.0, self._elevator_arrived)
        self.transition_to(next_scene, transition)
```

  and add:

```python
    def _start_elevator_motor(self: Self, *, owner: object) -> LiveVoice | None:
        """Start the motor voice owned by the ride; None (silent ride) if no channel is free.

        Returns:
            The running voice, or None.

        """
        try:
            motor = self.scene_manager.live_audio.create_voice(
                owner=owner,
                waveform=Waveform.SAWTOOTH,
                frequency=ELEVATOR_MOTOR_IDLE_FREQUENCY,
                volume=ELEVATOR_MOTOR_MINIMUM_VOLUME,
                low_pass_cutoff=ELEVATOR_MOTOR_LOW_PASS_CUTOFF,
                tremolo=Tremolo(rate_hz=ELEVATOR_MOTOR_TREMOLO_RATE,
                                depth=ELEVATOR_MOTOR_TREMOLO_DEPTH),
            )
        except ValueError:
            log.warning('No live voice channel free; the elevator rides without its motor')
            return None
        motor.start()
        return motor

    def _update_elevator_motor(self: Self, transition: Transition) -> None:
        """Drive motor pitch and volume from the car's speed (the easing's slope).

        Runs from the transition after this scene was cleaned up, so it only touches the
        motor voice, never sprites or the camera.
        """
        if self._elevator_motor is None:
            return
        speed_fraction = min(
            1.0, transition.eased_velocity_at(transition.progress) / self._elevator_peak_velocity
        )
        self._elevator_motor.frequency = ELEVATOR_MOTOR_IDLE_FREQUENCY + (
            ELEVATOR_MOTOR_PEAK_FREQUENCY - ELEVATOR_MOTOR_IDLE_FREQUENCY
        ) * speed_fraction
        self._elevator_motor.volume = ELEVATOR_MOTOR_MINIMUM_VOLUME + (
            ELEVATOR_MOTOR_MAXIMUM_VOLUME - ELEVATOR_MOTOR_MINIMUM_VOLUME
        ) * speed_fraction

    def _elevator_arrived(self: Self) -> None:
        """The car slams into the floor: stop the motor, clank, shake and rumble.

        Uses only SceneManager-owned services (SCREEN shake), because this scene has been
        cleaned up by the time the ride ends.
        """
        if self._elevator_motor is not None:
            self._elevator_motor.stop_now()
            self._elevator_motor = None
        self.sounds.play('elevator_clank')
        self.shake(ELEVATOR_STOP_BOUNCE, targets=ShakeTarget.SCREEN)
        self.shake(ELEVATOR_STOP_RATTLE, targets=ShakeTarget.SCREEN)
```

  (`Transition` and `LiveVoice` imports go under `TYPE_CHECKING`.)

- [ ] **Step 6: Run** — `uv run pytest tests/examples/test_clockwork_keep.py -v` — PASS. The
  `test_motor_follows...` test patches `live_audio.create_voice`; if `scene_manager.live_audio`
  cannot be created in the test (no engine), it uses `channel_indices=()`, which is fine because
  `create_voice` is patched.
- [ ] **Step 7: Checkpoint and commit** (ruff, basedpyright, ty on the Clockwork Keep package). Report.

---

### Task 15: Documentation and full verification

**Files:**
- Modify: `CLAUDE.md`, `BUGS.md`

- [ ] **Step 1: CLAUDE.md.** In "Architecture Overview", add after **Frame Pacing**:

```markdown
**Screen Shake and Rumble** (`glitchygames/effects/shake.py`, `glitchygames/input/rumble.py`)
- `Scene.shake(Shake(...), targets=ShakeTarget.WORLD | ShakeTarget.SCREEN)`
- Styles: `NOISE` (trauma model), `JITTER`, `BOUNCE`; shakes stack and are capped
- WORLD shakes `Camera2D` sprites (HUD stays still); SCREEN shifts the presented frame,
  survives `transition_to`, and is cleared by `switch_to_scene`
- Optional `RumbleSettings` per shake; `SceneManager` sends combined rumble in controller and
  joystick modes
- `--screen-shake-intensity`, `--rumble-intensity` (0.0-1.0)

**Sound Synthesis** (`glitchygames/audio/synth.py`, `recipes.py`, `live.py`)
- Toolkit: oscillators (PolyBLEP square/saw), pitch curves via easing, envelopes, FIR filters,
  mixing, `to_sound()`
- Recipes: `Tone`/`SoundRecipe` (TOML-loadable) played through `SoundBank`
- Live voices: `scene_manager.live_audio.create_voice(owner=...)`, streamed in 100 ms chunks on
  a channel pool reserved at startup (`--live-voice-pool`, default 4)
- Mixer: 44100 Hz, signed 16-bit, stereo, 512-sample buffer (started by `pygame.init()`)

**Transitions** (`glitchygames/transitions/`): `on_update` callback, `add_cue(progress, callback)`,
`eased_velocity_at(progress)`; cues run after the old scene's cleanup, so they may use only
SceneManager services
```

- [ ] **Step 2: BUGS.md.** Move #21–#24 to Resolved with `Status: Resolved`, `Date Resolved`, a
  `Solution` line each (Task 1, Task 2, Task 2, Task 3), and the test names that pin them.

- [ ] **Step 3: Full verification.**

```bash
uv run ruff format glitchygames tests scripts noxfile.py
uv run ruff check glitchygames tests scripts noxfile.py
uv run basedpyright
uv run ty check glitchygames scripts
uv run pytest -n auto
```

Expected: ruff, basedpyright, ty report 0 errors; pytest all pass, coverage >= 80%, **no
warnings** (investigate any warning before reporting). Compare the pass count with the last full
run (12,944 passed, 22 skipped) plus the new tests.

- [ ] **Step 4: Manual check list for the user** (report it; do not claim these were heard):
  run `uv run clockwork-keep` (or the project's entry point; check `pyproject.toml`
  `[project.scripts]`): walk, jump, land, collect a cog, die, ride the elevator (motor rises,
  clank, bounce and rattle, rumble on a controller), pause during the shake (no shake on the
  pause screen), parallax background moves during play. Run `uv run brave-adventurer` and confirm
  the sounds are an octave lower and longer than before, and that the parallax now scrolls.

- [ ] **Step 5: Checkpoint and commit.** Report results, including anything skipped and why. Never push.
