# Screen Shake and Sound Synthesis — Design

- **Date:** 2026-10-17 (revision 3, after the final whole-branch review; see "Revision 3" at the end)
- **Branch:** `game/brave-adventurer`
- **Status:** Implemented (Tasks 1-15); revision 3 fix pass approved 2026-10-17
- **Master plan:** `plans/engine-audit.md` (items #3 and #5)
- **Origin:** Requested while building Clockwork Keep (April 2026): "when the elevator gets to the
  next floor kind of thing and stops... Big clunky shake and some deep sound effects if we can make
  them from scratch." Engine audit items #3 (screen shake) and #5 (sound synthesis).

## Goals

1. Engine-level screen shake that any game can use, stackable, with optional controller rumble.
2. An engine-level sound synthesizer in three layers: toolkit, recipes, and real-time voices.
3. Clockwork Keep uses both: a clunky elevator stop (shake + rumble + clank) with a motor whose
   pitch follows the car's speed, plus steampunk gameplay sounds.
4. Brave Adventurer drops its private synthesizer and uses the engine toolkit.
5. Fix the existing bugs this work depends on or touches (below).

## Non-goals

- Migrating the DualSense haptic generators in `audio/controller_audio.py`.
- Migrating Brave Adventurer to recipes or `SoundBank` (toolkit only).
- Gameplay sounds for Brave Adventurer Papyrus beyond what it already shares.
- Any other engine audit item.

## Decisions (made in conversation)

| Question | Decision |
|---|---|
| Where the elevator stop happens | At the end of the ride, as the car arrives |
| Rumble relationship | Tied to each shake (optional per shake) |
| Shake variants | Two targets (`WORLD`, `SCREEN`) × three styles (`NOISE`, `JITTER`, `BOUNCE`), all stackable |
| Synth layers | All three: toolkit (A), recipes (B), real-time voices (C) |
| Clockwork Keep sounds | Elevator plus gameplay |
| Live voice channels | Fixed pool reserved at startup, default 4, configurable |
| Mixer rate | Accept the 44100 Hz mixer `pygame.init()` already starts; delete the dead 22050 `pre_init` |
| Brave Adventurer pitch | Restore as written (sounds become an octave lower and twice as long as heard today) |
| Elevator activation | Interact only; jump always jumps |

## Existing bugs fixed by this work

Tracked in BUGS.md (#21–#24).

1. **Parallax never scrolls during gameplay** (`camera.py`). Commit `df21435` inserted `snap_to()`
   between `update()`'s clamp and its parallax loop, so the loop moved into `snap_to()` (where it
   now appears twice) and `update()` lost it. Fix: restore the loop in `update()`; keep one loop in
   `snap_to()`. Affects all three platformers.
2. **The engine's mixer settings never take effect** (`events/audio.py:75`). `pygame.init()`
   (`engine/game_engine.py:358`) starts the mixer at (44100, -16, 2) with a 512-sample buffer before
   `AudioEventManager` calls `pre_init(22050, -16, 2, 1024)`. Brave Adventurer generates 22050 Hz
   data, so its sounds play an octave high at half length. Fix: delete the `pre_init` call,
   document 44100/512 as the engine mixer, and generate at the mixer's actual rate.
3. **No audio device crashes the engine** (`events/audio.py:76`). `pygame.mixer.init()` raises
   `pygame.error` uncaught. Fix: catch it, log a warning once, and run silently; every audio API in
   this spec treats an uninitialized mixer as "audio unavailable".
4. **Jump on an elevator never rides it** (`clockwork_keep/game.py:467`). The jump handler clears
   `on_ground` during event processing; `_check_elevator()` requires it the next frame. Fix: remove
   `jump` from `_check_elevator()`; up/interact rides, jump jumps. Update the docstring.

---

## 1. Screen shake

### `glitchygames/effects/shake.py` (new)

Pure math. No display or controller dependencies.

- `ShakeStyle(Enum)`: `NOISE`, `JITTER`, `BOUNCE`.
- `ShakeTarget(Flag)`: `WORLD`, `SCREEN`.
- `ShakeAxis(Enum)`: `BOTH`, `HORIZONTAL`, `VERTICAL`.
- `RumbleSettings` (frozen dataclass): `low_frequency`, `high_frequency`, each 0.0–1.0, the motor
  intensity at full shake strength.
- `Shake` (frozen dataclass): `style`, `strength` (peak offset, pixels, >= 0), `duration`
  (seconds, > 0), `frequency` (Hz, > 0), `axis=ShakeAxis.BOTH`, `rumble: RumbleSettings | None`.
  Invalid values raise `ValueError`.
- `ScreenShake`:
  - `__init__(*, maximum_offset=32.0, intensity=1.0, random_source=None)`.
  - `add(shake)`, `update(dt)` (game time), `clear()`, `is_active`.
  - `offset -> tuple[float, float]`: sum of active offsets × `intensity`, each axis clamped to
    ±`maximum_offset`.
  - `rumble_levels -> tuple[float, float]`: per motor, the maximum over active shakes with rumble
    of `motor value × decay(shake) × min(1, strength / maximum_offset)`, where `decay` is the same
    envelope that shake's offset uses. (0.0, 0.0) when none.
  - `rumble_remaining -> float`: longest remaining duration among active shakes with rumble.

Style behavior (`t` = elapsed seconds, `remaining = 1 - t / duration`):

- `NOISE`: trauma model (Squirrel Eiserloh, "Juicing Your Cameras With Math", GDC 2016).
  Magnitude `strength × remaining²`; direction from smooth 1D value noise sampled at `frequency`,
  one track per axis. Decay = `remaining²`.
- `JITTER`: a uniformly random offset in [-1, 1] per axis, re-drawn every `1 / frequency` seconds,
  scaled by `strength × remaining`. Decay = `remaining`.
- `BOUNCE`: `strength × e^(-damping × t) × cos(2π × frequency × t)` along the axis (`BOTH` = the
  diagonal), with `damping = ln(100) / duration` so the amplitude is 1% of `strength` at
  `duration`. Decay = `e^(-damping × t)`.
- At `t >= duration` a shake contributes exactly zero offset and zero rumble and is removed.

### WORLD target: `Camera2D`

- `Camera2D(..., shake_intensity=1.0)` owns `shake_effect = ScreenShake(intensity=...)`.
- `update(target_x, target_y, dt)` advances the shake, then updates parallax layers (bug 1 fix).
- `apply()` adds the shake offset before rounding.
- Parallax layers scroll from the shaken camera position, so a layer shakes in proportion to its
  `scroll_factor`: a static sky (`0.0`) never shakes, a far layer (`0.1`) barely moves. This is
  intended: distant scenery should not jitter.
- `snap_to()` applies no shake and keeps a single parallax loop.
- Only sprites positioned through `apply()` shake. HUDs drawn directly in `render()` do not.
- Collision and `is_visible()` use the unshaken `world_x`/`world_y`.

### SCREEN target: `SceneManager`

- `SceneManager.screen_shake` is a `ScreenShake` built with the screen-shake intensity option.
- Main loop order, in both the normal and transition branches: update the transition or scene
  first, then `screen_shake.update(dt)`, then live audio (section 3), then render, then present.
- **Presenting a shaken frame:** the scene renders into the display surface unshifted, as today.
  When `screen_shake.offset` rounds to non-zero, the manager copies the display surface, fills the
  display black, blits the copy at the offset, presents with a full `pygame.display.flip()`, then
  blits the copy back at (0, 0). The display therefore always holds the unshifted frame between
  presents, so dirty-rect rendering, `Scene.screenshot`, and transition screenshots never see shift
  or black strips.
- When the shake ends, the manager forces one full redraw (all sprites dirty and a full display
  update, as `_finalize_transition` does) so the last shifted present is fully replaced.
- **Lifecycle:** the screen shake survives `transition_to` (the elevator's shake continues into the
  new floor) and is cleared by `switch_to_scene` (pause and any direct scene switch). A game that
  reaches game over through `transition_to` clears it explicitly before the transition (revision 3:
  Clockwork Keep's game over uses `transition_to(FadeTransition)`).

### Transition screenshots and WORLD shake

`_start_transition` re-renders the old scene with `update()`/`render()` only, so sprite rects keep
their last shaken positions. Before capturing, the manager calls `camera.shake_effect.clear()` on
the old scene's camera (when it has one) and the scene re-applies its camera (the existing
`apply_camera` pass) so the screenshot is unshaken.

### API for games

`Scene.shake(shake, *, targets=ShakeTarget.WORLD)`

- (Revision 3) Every `Scene` has a camera: `Scene.camera: Camera2D`, never `None`. The base
  `__init__` creates a default camera sized to the screen at (0, 0) with no bounds; nothing moves
  it, so `apply(x, y)` returns `(x, y)` (a null-object camera for scenes that do not scroll). The
  three platformers replace it, as before, constructing theirs with
  `shake_intensity=self.options.get('screen_shake_intensity', 1.0)`. Revision 2's
  `Camera2D | None` made every out-of-`__init__` use a type error; re-annotating `camera` in
  subclasses is rejected by basedpyright and ty (mutable attribute invariance).
- (Revision 3) `WORLD` shakes the scene's camera. It moves only sprites positioned through
  `camera.apply()`. `Camera2D` records whether `apply()` has been called; `Scene.shake(..., WORLD)`
  logs a warning once per scene when its camera has never been applied ("WORLD shake on <scene>
  has no effect: no sprites are positioned through its camera; use ShakeTarget.SCREEN").
  Revision 2's `ValueError` for a missing camera no longer applies.
- `SCREEN` routes to `scene_manager.screen_shake`.
- Rumble is owned by a new `RumbleController` held by `SceneManager` (not by the scene, so it
  survives transitions):
  - Each main-loop pass it combines `rumble_levels` from the screen shake and the active scene's
    camera shake (per-motor maximum), scales by the rumble intensity option, and re-sends rumble
    only when the levels change by more than 0.05 or the remaining time is about to run out.
  - Each send uses `duration_ms = max(1, ceil(rumble_remaining × 1000))`. The API takes integer
    milliseconds and treats 0 as infinite, so 0 is never sent. When levels reach (0, 0) it calls
    `stop_rumble`.
  - It sends to every connected device: in controller input mode, every entry in
    `game_engine.controller_manager.controllers` via `rumble(instance_id, ...)`; in joystick input
    mode (the pygame-ce default, where `controller_manager` is `None`), every open
    `pygame.joystick.Joystick` via its `rumble(low, high, duration_ms)`. Devices without rumble
    return False and are ignored.

### Settings

New engine arguments in the Graphics Options group (`engine/game_engine.py`), parsed with a
range-checked float type that rejects values outside 0.0–1.0:

- `--screen-shake-intensity` (default 1.0; 0 disables offsets)
- `--rumble-intensity` (default 1.0; 0 disables rumble)

`SceneManager` reads both from `OPTIONS` at startup.

---

## 2. Synthesizer toolkit (layer A)

### `glitchygames/audio/synth.py` (new)

numpy only. All functions work on mono `float64` arrays in [-1.0, 1.0]; conversion to int16
happens once, in `to_sound`.

- **Sample rate:** every function takes `sample_rate: int | None = None`; `None` is resolved at
  call time by `mixer_sample_rate()`, which returns the mixer's frequency, or 44100 (pygame's
  default and what `pygame.init()` starts) when the mixer is not initialized. Sample counts are
  `round(duration × sample_rate)`.
- **Validation:** `duration` must be > 0 for generators (`ValueError` otherwise); `silence(0)`
  returns an empty array. Any frequency (scalar or array) must be in [0, sample_rate / 2]
  (`ValueError` otherwise).
- `Waveform(Enum)`: `SINE`, `SQUARE`, `SAWTOOTH`, `TRIANGLE`, `NOISE`.
- `oscillator(waveform, frequency, duration, *, sample_rate=None, duty=0.5, phase=0.0,
  random_source=None)`:
  - Phase origin: sample `i` has phase `phase + Σ_{k<i} frequency[k] / sample_rate` (exclusive
    cumulative sum, so sample 0 is at `phase`). For a scalar frequency this equals
    `phase + frequency × i / sample_rate`.
  - Returns `(samples, end_phase)` with `end_phase` wrapped to [0, 1), so live voices can continue
    seamlessly.
  - `SQUARE`, `SAWTOOTH` and `TRIANGLE` are band-limited with PolyBLEP (Välimäki & Huovilainen,
    "Antialiasing Oscillators in Subtractive Synthesis", IEEE Signal Processing Magazine, 2007) so
    high notes do not alias.
  - `NOISE` ignores frequency and draws from `random_source` (a `numpy.random.Generator`).
- `frequency_curve(start_hz, end_hz, duration, *, easing='linear', sample_rate=None)`: sample `i`
  is at time fraction `i / (n - 1)` (both endpoints included); the easing function (scalar-only in
  `effects/easing.py`) is applied with `numpy.vectorize`. The result is validated against
  [0, Nyquist] after easing, so overshooting curves (`*_back`, `*_elastic`) raise if they leave the
  range.
- `Envelope` (frozen dataclass): `attack`, `decay`, `sustain_level`, `release`.
  `apply_envelope(samples, envelope, *, sample_rate=None)`: release is anchored to the end of the
  sound; attack and decay run from the start. When the stages exceed the sound's length, release
  keeps its full length first, then attack, then decay, each truncated in that priority. Ramps are
  linear and include both endpoints (attack starts at 0.0, release ends at 0.0).
- `low_pass(samples, cutoff_hz, *, sample_rate=None, taps=101)` and `high_pass(...)`:
  windowed-sinc FIR (Hamming window), odd `taps` required; `high_pass` uses spectral inversion of
  the low-pass kernel. Filtering uses `np.convolve` on `[zeros(taps - 1), samples]` with
  `mode='valid'`, so the output has the input's length, there is no onset click, and the same code
  continues across chunks when given the previous input tail instead of zeros. Cutoff must be in
  (0, sample_rate / 2).
- `distort(samples, drive)`: `tanh(drive × x) / tanh(drive)`, drive > 0.
- `tremolo(samples, rate_hz, depth, *, sample_rate=None, phase=0.0)`: returns
  `(samples, end_phase)`; depth 0.0–1.0.
- `mix(*layers)`: each layer is an array or `(array, offset_seconds)` with offset >= 0
  (`ValueError` if negative); the result covers the longest layer end; summed, not normalized.
- `concatenate(*arrays)`, `silence(duration, *, sample_rate=None)`.
- `normalize(samples, peak=0.9)`: returns silence unchanged (no division by zero).
- `to_sound(samples, *, volume=0.5) -> pygame.mixer.Sound`: requires the mixer format to be
  signed 16-bit (-16), else raises `AudioUnavailableError` naming the format; clips to [-1, 1],
  scales by 32767, converts to int16, tiles to the mixer's channel count as a C-contiguous 2-D
  array, and wraps with `pygame.sndarray.make_sound`. Raises `AudioUnavailableError` (new, in
  `glitchygames/audio/`) when the mixer is not initialized.

### Brave Adventurer migration (restore as written)

- Before deleting the old code, generate golden samples: run the current private generators with
  `SAMPLE_RATE` patched to 44100 and save each sound's mono samples as `.npy` files under
  `tests/examples/brave_adventurer/golden/`.
- Port the five sounds to toolkit calls with the same frequencies, durations, envelopes and peak
  (24000 / 32767), generated at the mixer rate. Audible result: an octave lower and twice as long
  as what plays today, which is what the code always described.
- The test compares new output to the goldens with a tolerance of ±2 LSB (the old code truncates to
  int16 twice and uses a slightly different sweep grid and phase origin, so bit-exact equality is
  not achievable).

---

## 3. Recipes (B), real-time voices (C), transition hooks

### `glitchygames/audio/recipes.py` (new)

- `Tremolo` (frozen dataclass): `rate_hz`, `depth`.
- `Tone` (frozen dataclass): `waveform`, `start_frequency`, `end_frequency` (defaults to start),
  `easing='linear'`, `duration`, `envelope`, `volume=1.0`, `offset=0.0`, `low_pass_cutoff=None`,
  `high_pass_cutoff=None`, `distortion=None`, `tremolo=None`. Offsets cover layering and
  sequencing.
- `SoundRecipe` (frozen dataclass): `name`, `tones: tuple[Tone, ...]`, `volume=0.5`, `peak=0.9`;
  `render(*, sample_rate=None) -> ndarray` (toolkit only), `to_sound()`, `to_dict()` /
  `from_dict()` (same pattern as `ActionMap`).
- `load_sound_recipes(toml_path) -> dict[str, SoundRecipe]` (tomllib); validation errors name the
  recipe and field.
- `SoundBank(recipes)`: renders on first `play(name)` and caches per sample rate. `play` is a no-op
  (logged once) when audio is unavailable; unknown names raise `KeyError`; when `Sound.play()`
  returns `None` because every unreserved channel is busy, it logs at debug level.

### `glitchygames/audio/live.py` (new)

**Channel pool.** `LiveAudio` is created lazily by `SceneManager` on the first `create_voice` call,
but the pool itself is reserved at engine startup, right after the mixer initializes and before
any sound can play: the engine grows the mixer from its current count `n` to `n + pool_size` and
calls `set_reserved(pool_size)`. `set_reserved` always reserves channels `0..pool_size-1`, and
reserving before anything plays guarantees those channels are idle. The channel count never
changes afterwards, because shrinking stops whatever plays on the removed top channel and
re-reserving can claim a channel that is playing a one-shot. One-shots keep the original `n`
channels. `--live-voice-pool` (engine option, default 4, minimum 0) sets the pool size; requesting
more voices than the pool raises `ValueError`.

**`LiveVoice`** (created by `live_audio.create_voice(owner=scene, ...)`):

- Parameters settable each frame: `frequency`, `volume`, `low_pass_cutoff`, `tremolo`.
- `chunk_duration` default 0.1 s (`round(chunk_duration × sample_rate)` samples).
- `update()`: when `Channel.get_queue()` is `None`, render the next chunk and `queue()` it. pygame
  holds one queued Sound per channel (a second `queue()` replaces the first), so the safety margin
  is the remainder of the playing chunk minus the device buffer already mixed: at 44100 Hz with a
  512-sample buffer and 100 ms chunks, about 88 ms worst case. A frame longer than that underruns:
  the voice falls silent, logs at debug level, and restarts on the next `update()`.
- Latency from a parameter change to hearing it: up to two chunks plus one device buffer plus one
  frame (about 230 ms worst case at the defaults), because the change ramps across the next chunk
  rendered.
- Continuity carried across chunks: oscillator phase (wrapped to [0, 1)), tremolo phase, the noise
  generator, and the low-pass filter's input history (last `taps - 1` samples, see section 2).
  Frequency and volume ramp linearly across a chunk. A cutoff change renders the chunk with both
  the old and new kernels and crossfades between them, because one FIR kernel per chunk cannot
  ramp.
- `stop(*, fade_out=0.1)`: renders the fade into the remaining queued audio (one or two chunks
  ending at zero amplitude), stops queuing, and lets the channel drain. pygame's `Channel.stop()`
  and `fadeout()` start the queued sound, so they are not used for fading.
- `stop_now()`: calls `Channel.stop()` twice (the first starts the queued chunk, the second stops
  it) so the channel is idle immediately.
- `is_playing`: True until the channel has drained.

**`LiveAudio`:**

- `update()` called once per main-loop pass in both branches (see section 1 loop order).
- Every voice has an owner: a `Scene` or a `Transition`. `cleanup()` cannot decide a voice's fate,
  because pausing is `switch_to_scene(PauseScene)`, which calls `cleanup()` on the paused scene,
  and resuming switches back to the same scene object. Instead, each `LiveAudio.update()` applies:
  - Owner is the active scene, or the running transition: the voice plays (resumed if paused).
  - Owner is `SceneManager.previous_scene` (the scene a `PauseScene` returns to): the voice is
    paused with `Channel.pause()`, which keeps its queued chunk.
  - Otherwise (the owner was abandoned, or the owner transition finished): the voice is released
    with `stop_now()` and its pool channel returns to the free list. At most one abandoned scene's
    voices are held at a time.
- `release_voice(voice)` releases explicitly at any time.
- **Transitions:** a voice for a ride is created with the `Transition` as its owner (the
  transition object exists before `transition_to` is called), so it survives the old scene's
  `cleanup()` and is released automatically when the transition finishes.
- Without a mixer, voices are silent no-ops (logged once).

### Transition hooks (`glitchygames/transitions/base.py`)

- `Transition(..., on_update: Callable[[Transition], None] | None = None)`.
- `add_cue(progress, callback)`, progress in [0.0, 1.0].
- Order within `Transition.update(dt)`: advance elapsed time; fire every cue whose progress is
  `<=` the new raw progress and was not yet fired, in ascending order (a cue at 0.0 fires on the
  first update; a cue at 1.0 fires on the completing frame; one large `dt` fires all passed cues);
  then call `on_update`.
- `eased_progress` is clamped to [0, 1] inside `ElevatorTransition`, so overshooting easings
  (`ease_in_back` reaches -0.10, `ease_in_elastic` -0.37, `ease_out_back` exceeds 1) never scroll
  outside the composite surface.
- **Ownership rule:** cue and `on_update` callbacks are closures over the scene that started the
  transition, which has already been cleaned up. They may use `SceneManager`-owned services
  (`screen_shake`, `RumbleController`, `live_audio`, sound playback) but must not touch that
  scene's camera or sprites. `Scene.shake` called with `WORLD` on a scene that is not the active
  scene raises `RuntimeError` (the concrete form of "cleaned up").

### The elevator, end to end

1. `_go_to_next_floor` builds the `ElevatorTransition`, creates the motor voice with the
   transition as its owner (low sawtooth, low-pass filtered, tremolo), starts it, then calls
   `transition_to`.
2. `on_update` computes the car's speed as the change in eased progress over the change in time
   (normalized to 1.0 at peak speed) and sets the motor's frequency and volume from it, so the motor
   spins up and stays high as the car accelerates into the stop.
3. A cue at 1.0 calls `stop_now()` on the motor, plays `elevator_clank`, and adds two `SCREEN`
   shakes through `SceneManager`: a vertical `BOUNCE` (the clunk) and a short `NOISE` (the rattle),
   both with rumble. The shake continues into the new floor.
4. The ride's easing changes from `ease_in_out_quad` to `ease_in_sine` (arrives at speed), tuned by
   eye. There is no spin-down; the slam is the stop.

---

## 4. Clockwork Keep sounds and wiring

### `glitchygames/examples/clockwork_keep/sounds.py` (new)

`SoundRecipe` constants in a `SoundBank`. Steampunk palette: brassy squares and saws, filtered
noise for steam, low booms.

| Sound | Trigger | Character |
|---|---|---|
| `jump` | `Tinker.jump()` actually leaves the ground | Short rising square chirp + steam puff |
| `land` | Airborne on the previous real frame, grounded now | Low thunk |
| `cog_pickup` | Score increase in `_check_collectibles` | Two-note metallic ting |
| `death` | `_player_die` | Falling saw sweep, winding down like a spring |
| `game_over` | Game-over transition | Slow descending three-note chime |
| `elevator_clank` | Elevator arrival cue | Distorted noise hit + low sine boom + short ring |
| motor (live) | Elevator ride | See section 3 |

- **`land` edge detection:** ground collision resets `on_ground` to False and back to True every
  frame, so a level check would fire every frame. The previous-frame state is set from the first
  real collision result (not a default), so the off-screen `dt_tick(0.001)` that
  `_start_transition` runs on the new scene cannot trigger it, and it is suppressed while
  `is_respawning` (respawn sets `on_ground` directly from a tween callback).
- Sounds play from the scene, not from `Tinker`.
- Elevator tuning constants (motor pitch range, bounce strength, rattle duration, easing) go in
  `constants.py`.

---

## Testing

All tests use `mocker`, game time, and a seeded `random_source`; none depend on chance. New tests
go in existing test files where a matching one exists.

**Test environment:** test paths containing "scene" or "game_objects" replace `pygame.mixer` with a
Mock (`tests/conftest.py:92-117`), so code reached from `SceneManager` must not do arithmetic on
mixer calls at construction (`LiveAudio` is lazy; the pool reservation is in the engine's startup
path, tested with explicit mocks). Voice logic is tested against a mocked `Channel`
(`get_queue`, `queue`, `get_busy`, `stop`, `pause`). Real `sndarray` tests run with
`SDL_AUDIODRIVER=dummy`, an explicit `pygame.mixer.init(44100, -16, 2)`, and explicit
`sample_rate`.

- **Existing bugs:** parallax layers scroll on `update()`; `snap_to()` updates layers once; no
  `pre_init` call; no audio device logs and continues; jump on an elevator jumps and does not ride,
  interact rides.
- **Shake:** each style's decay curve; exactly zero offset and rumble at and after `duration`;
  stacking sums; the cap holds for every combination; screen-shake intensity 0 gives no offset
  (rumble is governed only by `--rumble-intensity`, revision 3); every scene has a default
  identity camera; WORLD on a never-applied camera warns once; parallax shake scales with
  `scroll_factor`;
  presenting a shaken frame leaves the display surface unshifted afterwards; one full redraw when
  the shake ends; screen shake survives `transition_to` and is cleared by `switch_to_scene`;
  transition screenshots are unshaken.
- **Rumble:** per-motor maximum with each shake's decay; `duration_ms` never 0 (remaining 0.0001 s
  sends 1); re-send threshold; `stop_rumble` at zero; controller mode loops over all controllers;
  joystick mode loops over all joysticks; intensity 0 sends nothing.
- **Synth toolkit:** FFT peak at the requested frequency for each periodic waveform; PolyBLEP
  alias suppression near Nyquist; phase origin and `end_phase` continuity (two half-length calls
  equal one full call); `frequency_curve` endpoints exact and overshoot rejected; envelope values at
  each stage boundary and the truncation priority; filter attenuation above/below cutoff, output
  length equals input length including inputs shorter than `taps`, no onset click, chunked
  filtering with carried history equals whole-signal filtering; `ValueError` at cutoff 0 and
  Nyquist; `mix` offsets, overhang and negative offset; `normalize` on silence; `to_sound` channel
  tiling, contiguity, format check and `AudioUnavailableError`.
- **Recipes:** render equals the equivalent toolkit composition; `to_dict` / `from_dict` / TOML
  round-trips; validation errors name recipe and field.
- **SoundBank:** lazy render and cache; `KeyError`; no-op without audio; busy-mixer debug log.
- **Live voices:** pool reserved at startup and channel count never changes afterwards; more voices
  than the pool raises; phase, tremolo and filter continuity across chunk boundaries; parameter
  ramps; cutoff crossfade; underrun recovery; `stop()` drains with a fade and never plays a queued
  chunk at full volume; `stop_now()` leaves the channel idle; pause (`switch_to_scene(PauseScene)`)
  pauses the owner's voices and resuming the same scene object resumes them; an abandoned owner's
  voices are released on the next switch and their channels reused; transition-owned voices
  survive the old scene's `cleanup()` and are released when the transition ends.
- **Transition hooks:** cue order and `<=` boundary; cue at 0.0 and 1.0; one large `dt` past several
  cues; cues fire before `on_update`; `eased_progress` clamped in `ElevatorTransition`;
  `Scene.shake(WORLD)` on a cleaned-up scene raises `RuntimeError`.
- **Clockwork Keep:** each trigger plays its sound exactly once per event; `land` not triggered by
  the transition's off-screen tick or by respawn; elevator end to end: motor starts, frequency
  follows speed, arrival plays clank, adds both shakes, rumbles, and stops the motor.
- **Brave Adventurer:** the five sounds match the goldens within ±2 LSB.
- **Manual:** the user plays Clockwork Keep (and Brave Adventurer, whose sounds change pitch) to
  judge feel and sound.
- Lint and type checks (ruff, basedpyright, ty) before tests; full suite before any commit; no
  commit without the user's go-ahead.

## Documentation

- CLAUDE.md architecture overview: `effects/shake`, `audio/synth`, `audio/recipes`, `audio/live`,
  the transition hooks, the 44100/512 mixer, and the three new engine arguments
  (`--screen-shake-intensity`, `--rumble-intensity`, `--live-voice-pool`).
- BUGS.md: #21–#24 resolved when their fixes land.

---

## Revision 3 (2026-10-17): final review fix pass

The final whole-branch review found the branch tip failing basedpyright (12 errors) and ty (12)
because of `Scene.camera: Camera2D | None`, plus a missing spec-listed test. Decisions, made with
the user:

1. **Default camera on every scene** (the user's proposal): `Scene.camera` is always a
   `Camera2D`; non-scrolling scenes get an identity camera. Removes all `None` guards in the three
   platformers; no `require_camera()` helper is needed.
2. **WORLD shake on a scene whose sprites never use the camera** warns once instead of raising
   (see "API for games"). Automatic camera positioning, which would make WORLD shake work for any
   scene, is deferred to the "Engine world space" plan (`plans/engine-audit.md`), designed
   together with engine pixel snapping and camera follow.
3. **Following a target stays in each game** for now: games follow on different axes and after
   physics; a base-class follow would lag a frame. Also deferred to "Engine world space".
4. **Rumble is independent of screen-shake intensity.** Separate `--screen-shake-intensity` and
   `--rumble-intensity` exist so players can turn off on-screen motion and keep rumble; revision 2's
   test line "intensity 0 gives no offset and no rumble" is amended.
5. **Clockwork Keep's game over clears the screen shake** before its fade transition.
6. **Pre-rendered sounds:** `SoundBank.prerender()` renders every recipe up front (a no-op without
   audio); Clockwork Keep calls it during floor setup so the elevator clank does not render on the
   slam frame.
7. **Small fixes:** Brave Adventurer and Papyrus pass the shake intensity option to their cameras;
   `_start_elevator_motor` also catches `AudioUnavailableError`; the frame-services ordering comment
   states that `Scene.update()` runs inside rendering, after frame services.
8. **Test added:** transition screenshots are unshaken (WORLD shake cleared and sprites
   re-positioned before the old-scene capture).


---

## Iteration 1 (2026-10-17): ascent rumble, stronger stop, floor-3 clock

Requested after playtesting ("better, definitely better"):

- **Sustained rumble source:** `RumbleController.set_sustained(low_frequency=, high_frequency=)` /
  `clear_sustained()`, combined per motor (maximum) with shake rumble and sent in 0.25 s slices
  refreshed by the time-left margin; `switch_to_scene` clears it. The slice sets only the send
  duration, not the "shakes outlast the sent rumble" check (otherwise it re-sends every frame).
- **Absolute rumble:** `RumbleSettings(scale_with_strength=False)` makes motor values independent of
  the shake's strength (still fading with its decay). The elevator stop uses it: bounce 1.0 / 0.5,
  rattle 0.4 / 0.8, on-screen shake unchanged. Previously the 14 px bounce scaled 0.9 down to ~0.39.
- **Clockwork Keep ascent:** sustained rumble follows the car's speed up to 0.25 low / 0.05 high,
  even without a free motor voice; the arrival cue clears it. `_update_elevator_motor` ignores the
  arrival frame (progress >= 1.0) because `on_update` runs after the 1.0 cue and would re-arm it.
- **Floor-3 clock:** hands driven by game time from 11:58:00 (two minutes to midnight), smooth
  sweep; seconds hand 100 px with tail and cap, minute 85 px, hour 55 px; freezes while paused.

---

## Iteration 2: rumble pulse and Brave Adventurer death rumble

- **Pulse API:** `RumbleController.pulse(low_frequency=, high_frequency=, duration=)` adds a finite
  rumble fading linearly to exactly 0.0 at `duration` (levels validated 0.0-1.0, duration > 0).
  Pulses advance by `dt` inside `update`, are dropped once finished, combine per motor (maximum)
  with shakes and sustained rumble, and their remaining time sets the send duration.
- **Scene switches:** `switch_to_scene` still clears sustained rumble but keeps pulses (they are
  finite), so the game-over pulse is felt on the game-over screen. `clear_pulses()` exists but is
  not called by the switch.
- **Brave Adventurer and Papyrus:** `_player_die` pulses `DEATH_RUMBLE_*` (0.7 / 0.4, 0.35 s) when a
  life is lost and `GAME_OVER_RUMBLE_*` (1.0 / 0.6, 0.8 s) on the last life; constants live in
  `brave_adventurer/constants.py` (tuned by feel). No on-screen shake.
- **Targeting (planned, not implemented):** pulses, like all rumble today, go to every connected
  device. Per-player targeting is a planned engine item; when it lands, `pulse`, `set_sustained`
  and `RumbleSettings` will gain a `targets` keyword defaulting to all devices, so existing calls
  stay valid.

---

## Known follow-ups (deferred review minors)

Minor findings from the per-task reviews, triaged by the final review as not blocking merge.
Kept here because the review ledger was a temporary workspace.

- Task 1: test_update_scrolls_parallax_layers compares against post-call world_x/y; add an explicit expected value
- Task 1: _add_recording_layer helper lacks a docstring
- Task 2: missing-device test asserts warning.called, not the new message text
- Task 2: missing device logs two warnings (new + existing get_init None)
- Task 3: test_jump_while_held_never_rides docstring says "Even if on_ground is restored" but restores nothing (brief wording)
- Task 3: controller Y (interact) riding untested
- Task 4: noise envelope test only asserts an upper bound
- Task 4: jitter hold test uses sign checks; could pin the decay ratio
- Task 4: update() does not guard negative dt (cap still clamps)
- Task 4: no test for maximum_offset <= 0 raising
- Task 5: new camera shake tests/helper lack docstrings
- Task 5: Camera2D has no random_source seam for NOISE/JITTER tests (set camera.shake_effect directly if needed)
- Task 6: no loop-level test pins main-loop order (update → frame services → render → present) in both branches
- Task 6: camera-only re-render runs one extra old-scene update() before the screenshot (same as existing player path)
- Task 6: redundant type-narrowing guards scene.py:236; unused mocker param in presentation test
- Task 7: getattr(controller_manager, 'controllers', {}) silently means no devices
- Task 7: _sent_levels recorded even with no devices; newly connected controller waits for a level change
- Task 7: devices() still outside the per-device try (only get_count() can raise now)
- Task 8: add_cue during a running transition can misfire (insert before _next_cue_index); document "add before start()" or guard
- Task 8: no test that start() resets the cue index; new tests lack type annotations; on_update docstring wording ("including the completing frame")
- Task 9: frequency_curve count==1 returns start_hz only; NOISE validates an ignored frequency; tests don't cover sample_rate=None resolution through oscillator/frequency_curve, duty validation, frequency_curve duration validation
- Task 10: one-sample envelope stages (linspace(a,b,1) == [a]) break the endpoint invariant; matches the old Brave behavior
- Task 10: Envelope values not validated (negative durations, sustain outside 0-1)
- Task 10: apply_kernel empty-input return precedes the history-length check
- Task 10: real-mixer smoke test quits the mixer without restoring prior state; test gaps (tremolo continuity, high_pass history, validation errors)
- Task 11: no-mixer test asserts only jump is None (docstring says every sound)
- Task 12: SoundBank.play uses `not play()` (Channel truthy, verified) — explicit `is None` preferred
- Task 12: loader does not coerce/validate optional numeric fields, malformed shapes, empty tones, volume/peak ranges; play docstring omits render ValueError
- Task 13: stop() fade starts after the already-queued chunk (up to ~200 ms late); document
- Task 13: continuity tests are heuristics; could compare to an uninterrupted render (atol 1e-9)
- Task 13: `random_source or default_rng()` truthiness; integration test cleanup not exception-safe; underrun test assertion loose
- Task 13: never-started IDLE voices hold their channel until the owner is abandoned; abandoned owner cuts off a FADING voice
- Task 14: respawn land test asserts <= 1, would not catch a spurious tween-triggered play
- Task 14: jump allowed (now with sound) while respawning if the tween set on_ground
