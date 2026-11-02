# GlitchyGames Sound Engine — Implementation Specification

- **Date:** 2026-11-02 (revision 2: the one-call `audio.sound(...)` API; builder-check fixes)
- **Status:** DRAFT for the owner's review. M1 is built on this branch (2026-11-02; user docs:
  `docs/architecture/sound.md`); M2 onwards is not. The experiments in Appendix A are throwaway
  and are not in the repository.
- **Companion:** `docs/specs/2026-11-02-sound-engine-feature-spec.md` (what the engine does; the
  requirement IDs used below).
- **Branch:** `docs/sound-engine-specs`.

Labels are the feature spec's: **[Owner]**, **[Fact]** (verified at `origin/main` 0f1a4b81),
**[Measured]** (Appendix A, and M1's channel-fade probes in `tests/audio/test_channel_fades.py` and
`tests/benchmarks/test_channel_fade_relations.py`),
**[Proposal]**, **[Open]**, and **[Call]** (a routine choice settled
by the spec's author after the builder check, open to the owner's change).

---

## 1. Repository evidence

| Question from the brief | Answer [Fact] | Where |
| --- | --- | --- |
| Python, pygame | Python ≥ 3.14 (3.14.8 here); pygame-ce 2.5.8 on SDL 2.32.10; numpy 1.26.4 imports and runs on 3.14.8 in the project's `.venv` (checked: the Appendix A runs used it) | `pyproject.toml` `requires-python`; `.venv` |
| Existing audio modules | `synth.py`, `recipes.py`, `live.py`, `controller_audio.py`, `tts.py`, `voice_assistant.py`, `diagnostics.py` | `src/glitchygames/audio/` |
| Output device | `pygame.mixer` only, started by `pygame.init()`: 44100 Hz, s16, stereo, 512-frame buffer | CLAUDE.md "Sound Synthesis"; `synth.mixer_sample_rate` |
| Does anything open a second device? | miniaudio opens a **controller's** speaker and mic only (DualSense), never the main output | `controller_audio.py` |
| Real-time rendering today | `LiveVoice` renders 100 ms numpy chunks **on the main thread** in `SceneManager`'s frame (`_live_audio.update(...)`), queued with `Channel.queue` on reserved channels | `live.py`; `scenes/scene.py:1227-1250` |
| Channel reservation | The live pool is reserved at engine start (`reserve_live_voice_pool`, `game_engine.py:1817`); `LiveAudio` itself is created lazily by the `live_audio` property (`scene.py:1262`) on those channels | both files |
| GIL | The engine sets `sys.setswitchinterval(0.0005)` so the mixer's channel-end callback can queue the next chunk (BUGS.md #27) | `engine/game_engine.py:1303`; `timing.GIL_SWITCH_INTERVAL_SECONDS` |
| Scene lifecycle | `setup()`, `cleanup()`, `load_resources()`; voices owned by scenes, paused behind pause screens and playback scopes | `scenes/scene.py`; `LiveAudio.update(active_scene=..., paused_owners=...)` |
| Replays and silence | Rebuild/fast-forward frames are silenced by stopping channels | `replay/silence.py` `FrameSilencer` |
| Time | One clock module; `raw_counter_seconds` for measurement only; nothing else may import `time`. The frame clock never pauses; `Scene.game_time` stops while a scene is paused | `src/glitchygames/clock.py`; CLAUDE.md "Clocks"; `tests/test_engine_doors.py` |
| Randomness | Named, seeded streams (`numpy_stream('audio.synth')` for synth noise); unseeded randomness is guarded | `randomness.py`; `tests/test_unseeded_randomness_guard.py` |
| Engine contexts | Several games may run in one process (the Arcade); per-game state lives in `ContextSlot`s; nothing in `src/` switches contexts yet | `engine_context.py`; CLAUDE.md "Engine Context" |
| Headless | `--headless` moves SDL video and audio to `dummy`, restarting a running mixer with its format | `GameEngine` (`game_engine.py:2950-2990`) |
| Device events | `AUDIODEVICEADDED/REMOVED` handled by `AudioEventManager` | `events/audio.py` |
| Browser | PyScript/Pyodide with GlitchyGames' own pygame-ce wheel; `mixer.init` + `Sound.play()` verified after a click; SDL's emscripten audio uses the deprecated `ScriptProcessorNode`; games (not demos) get browser builds | `browser/`; `../pygame-ce-wasm/compatibility-matrix.md` A1, `gap-analysis.md` GAP-07; CLAUDE.md "Example Games" |
| Serialization | TOML everywhere (`tomllib` reads, `tomli-w` writes; sprite files, recipes, settings); `.toml` extension, kind told apart by content | CLAUDE.md "File Formats"; `recipes.load_sound_recipes`; `pyproject.toml` |
| Atomic file writes | `output_files.write_aside_then_replace` | `output_files.py` |
| Per-user directories | `state/paths.get_save_directory(app_name)` (no cache-directory helper yet) | `state/paths.py` |
| Demos layer | `src/demos/<name>-demo/`, each its own workspace member and console script; no browser build; not the same thing as a game's bundled demo recordings | CLAUDE.md "Example Games" |
| Processing-time measurement | Every recorded frame holds `processing_seconds`; `--compare-processing` compares a replay with its recording | `replay/processing.py` |
| Tests | pytest, real pygame on the dummy driver, 100% coverage, no wall-clock timings in the normal suite, benchmarks under `--benchmark-only` | CLAUDE.md "Testing Guidelines" |
| Licensing gate | `scripts/check_licenses.py`: permissive allowed; LGPL/MPL/unreviewed fail unless excepted (pygame-ce is excepted) | `scripts/check_licenses.py` |

Observations made while reading (reported per the owner's instructions; not bugs):

- `synth.oscillator`'s NOISE draws from the engine stream `audio.synth`, which is seeded from the
  run's master seed. The same recipe's noise therefore differs per run and depends on render
  order. That is harmless today, because nothing caches across runs, but it is incompatible with a
  content-keyed disk cache. §6.3 gives each sound its own seed, and v0 recipes keep today's
  behaviour (§10.4).
- `SoundBank.play` renders on first use unless `prerender()` was called. Both users call
  `prerender()` at setup [Fact: `mr_muncher/game.py:515`, `clockwork_keep/game.py:473`]. That is
  the same "first request compiles" model the owner chose; the library generalizes it.

---

## 2. Architecture

### 2.1 Layers

```
 Game code ──► AudioEngine facade  (scene_manager.audio; one per engine context)
                 │
                 ├─ Asset layer      TOML → validated model → resolved SoundSpec (pure data)
                 ├─ Library          sound(...) → name/path resolution → compile once → cache
                 ├─ Renderer (DSP)   SoundSpec → float64 buffer   (pure numpy, no I/O)
                 ├─ Voices           channel table, priorities, stealing, handles, buses, live voices
                 └─ Output           pygame.mixer (SDL's C mixer thread)  |  OfflineMixer (files)
```

| Layer | Module [Proposal] | Owns | Thread |
| --- | --- | --- | --- |
| Pitch and waves | `audio/pitch.py`, `audio/waves.py` | `Note/Hz/Midi/Scale/PitchTable/Tuning`; `Wave`, `WaveTable`, `Harmonics`, `WavePoint`, `CYCLE`, `LEVEL`, the wave registry | main |
| Asset | `audio/assets.py` (pydantic v2 models [Fact: an engine dependency]) | parsing, validation, migration, path resolution, the short-name index | main |
| Renderer | `audio/render.py` (sources, envelopes, routes, filters, effects), built on `synth.py` | pure functions of a `SoundSpec`, its seeds and the sample rate | main |
| Library | `audio/library.py` | `SoundLibrary`: `sound(...)`, identity hashing, compiled sounds, memory and disk cache, compile accounting | main |
| Voices and buses | `audio/voices.py`, `audio/buses.py` | channel table, `SoundHandle`, generation counters, bus tree, stealing, pause bookkeeping | main |
| Live voices | `audio/live.py` (extended) | `LiveVoice` rendering chunks from a compiled live instrument | main |
| Facade | `audio/engine.py` | `AudioEngine` | main |
| Offline | `audio/offline.py` | `OfflineMixer`, `render_to_file` | any (no device) |
| Tool | `glitchygames sound` subcommands (`render`, `migrate`, `check`) | the CLI | CLI |

### 2.2 Data flow

1. **Request**: `audio.sound(source, pitch=..., notes=..., chord=..., length=..., transpose=...,
   parameters=...)`.
   - Strings are resolved per feature spec §3.2. A short name goes through the `SOUND_DIRECTORY`
     index, which is built on the first short-name lookup by reading only the table names of
     each `.toml` file. A path goes to that file's `[sounds.<name>]`, or to the recorded file.
   - Each sound file is parsed and validated once, when first touched, into frozen models.
   - The source and identity arguments resolve to an immutable `SoundSpec`: the instrument,
     concrete `Hz` pitches, note events in seconds, fixed parameter values, seeds, tuning, and
     whether it is live.
   - The **identity key** is the SHA-256 of the spec's canonical JSON (§6.2).
2. **Cache lookup**: the key is looked up in the memory cache (then the disk cache, from M3). A
   hit returns the existing `Sound` object, so equal requests return the same object
   (AUD-FUNC-002).
3. **Compile** (on a miss):
   - **Baked:** render a float64 buffer and check it is finite. Report its peak; clip and warn if
     it is above full scale, or scale it to -1 dBFS if `normalize`. Convert to int16 at the mixer
     rate with `synth.to_pcm16` [Fact], and make a `pygame.mixer.Sound` from it when a mixer
     exists.
   - **Live:** build wave tables and filter coefficients; no audio.
   - **Recorded file:** load it with `pygame.mixer.Sound(path)` (no mixer: decode it with the
     `wave` module for offline use, WAV only).
   - In every case the time is recorded with `clock.raw_counter_seconds` [Fact], attributed to
     "setup" (before the scene's first logic frame) or to the current frame number.
4. **Play**: `sound.play(...)` allocates a channel (§7.1), calls `Channel.play(sound, loops)`
   and then `Channel.set_volume(left, right)`. The mixer (C, SDL's audio thread) does the rest.
5. **Live**: `sound.start(...)` creates a `LiveVoice` on a reserved live channel. Each frame,
   `AudioEngine.update` renders the next chunk when the queue has room (today's mechanism
   [Fact]), reading the latest coalesced parameter values.
6. **Offline**: `OfflineMixer` takes compiled float buffers (or steps live renderers with a
   parameter timeline) and sums them at exact sample offsets into a file.

There is no second clock and no second output device. The mixer is the only device owner
**[Proposal; decisions D3/D4]**.

---

## 3. Backend decision (D3) and evidence

### 3.1 Options considered

| Option | Description | Verdict |
| --- | --- | --- |
| **A. pygame.mixer + compiled (baked) sounds + main-loop live chunks** | Extend what exists. Baked sounds mix in SDL's C mixer; live voices render on the main thread in chunks | **Recommended** |
| B. A Python render callback on a device thread (`pygame._sdl2.audio.AudioDevice(callback=...)` or `miniaudio.PlaybackDevice` with a generator) | The classic "audio callback" architecture, with DSP in numpy on the audio thread | **Rejected: measured to miss deadlines under GIL contention** (A.2) |
| C. A Python render-ahead worker thread + copy-only device callback | Render blocks on a worker thread into a ring buffer; the callback only copies | **Rejected for M1–M5:** needs about 85 ms of lookahead to survive a busy game loop (A.3), no better than A's 100 ms chunks, while adding a second device and threads |
| D. A native DSP core (C via cffi, or Rust) owning its own callback without the GIL | The only route to low-latency, sample-accurate real-time mixing, real-time bus effects and a master limiter | **Deferred to an M6 gate [Open]:** adds native builds for every platform plus a separate WebAssembly build, for features not yet asked for |
| E. Free-threaded CPython (3.14t) running B or C without the GIL | Removes the contention that sinks B and C | **Deferred [Open]:** pygame-ce, numpy and the engine would all need free-threaded builds and audits |

### 3.2 Why A

- **[Owner]** "the first time you call for a sound, it gets compiled ... the way you load it is
  the same as the way you'd use it in the game - one API." Option A compiles on request and
  plays compiled audio from memory, which is exactly that model.
- A Python callback cannot reliably meet a 5.33 ms (256-frame) deadline while the game loop runs
  Python. **[Measured A.2]** With a pure-Python busy main thread, a numpy render in a miniaudio
  callback took 256 ms (p99) at the default 5 ms switch interval, 58 ms at 1 ms and 12.7 ms at
  0.2 ms.
- The same numpy render is cheap when uncontended **[Measured A.1]**: 64 voices of
  oscillator + envelope + pan take 0.40 ms (p99 0.47 ms) per 256 frames. On the main thread there
  is no contention.
- Today's main-thread costs are small **[Measured A.4]**: a 100 ms live chunk with a low-pass
  takes 0.15 ms, and the worst existing recipe takes 9.7 ms, compiled once.
- One device means no competing mixer, no second clock, and nothing new for the replay silencer,
  headless runs or the browser to learn.
- There are no new dependencies (AUD-PORT-001).

### 3.3 What A gives up (recorded honestly)

- **Trigger latency:** `play()` starts at the next mixer buffer, about ≤ 11.6 ms after the frame
  that called it. It is not sample-accurate.
- **Live-parameter latency:** up to one chunk (100 ms today; M3 evaluates 50 ms) plus one buffer.
- **Real-time bus effects and a master limiter** are not possible, because SDL's mixer sums in C
  with saturation. Effects are compiled into sounds instead.
- **Sample-accurate transitions between music pieces** are not possible. Inside a compiled sound,
  timing is sample-accurate.
- **Pitch at play time** cannot change a compiled sound, because pygame plays at a fixed rate.
  Each pitch is its own sound, requested by identity.

### 3.4 The native-core gate (M6) **[Open]**

Option D is reopened only if the owner asks for one of:

- real-time bus effects (a reverb send, a master limiter);
- sample-accurate music transitions;
- more than 8 simultaneous live voices;
- trigger latency under 10 ms.

The experiment would be a C core built with cffi (the toolchain pyminiaudio already uses [Fact])
for macOS arm64/x86_64, Linux and Windows, plus an Emscripten build, measured with the Appendix A
harness. If it fails, the fallback is A as specified. The Renderer layer is pure functions over
`SoundSpec`s, so a native core would replace only the Output and Live layers.

---

## 4. Execution model

### 4.1 Threads

| Thread | Runs | Owner |
| --- | --- | --- |
| Main (game loop) | all API calls, compiles, live chunk rendering, channel allocation, bus volume updates, diagnostics | engine |
| SDL audio thread | pygame's C mixer: sums playing channels, and calls the channel-finished callback that queues a live voice's next chunk [Fact] | SDL |

No new thread is created **[Proposal]**. The brief's command-queue and memory-ordering
requirements apply only to the deferred native core (§3.4). With one thread there is nothing to
queue: an API call takes effect through pygame's own thread-safe mixer calls.

### 4.2 Bounded work per frame

`AudioEngine.update(dt=...)` runs once per frame, in the slot where `LiveAudio.update` runs today
[Fact: `scene.py:1227`], with the same scene and pause arguments. It:

1. advances scheduled plays whose frame has arrived (M2; feature spec §7.1, late rule);
2. advances each unpaused voice's played time by `dt` and reaps voices whose sound has ended
   (§7.3);
3. for each live voice whose queue has room, renders one chunk with the latest parameter values;
4. applies bus fades and ducking (one gain step per bus per frame; M5);
5. records diagnostics: counters and `clock.raw_counter_seconds` deltas, kept in fixed-size ring
   arrays.

The work is bounded: at most `live_pool` chunks, at most one reap per channel and one operation
per bus. The only compiles in a frame are the ones the game requested in it. They are timed,
counted and listed with their frame (AUD-FUNC-003).

### 4.3 Parameter updates (coalescing)

`LiveSoundHandle.set(name, value)` writes `latest[name] = clamp(value)` into a small dict owned by
the voice, and rendering reads the dict once per chunk. A thousand calls per frame cost a thousand
dict writes and render nothing extra (AUD-GAME-003). Smoothing runs inside the chunk as a one-pole
glide from the previous chunk's end value toward the new target, with time constant
`smoothing_ms`, in closed form per sample: `target + (start − target)·exp(−n/τ)`.

### 4.4 Handles and stale-handle protection

```python
@dataclass(frozen=True, slots=True)
class SoundHandle:
    slot: int          # index into the voice table
    generation: int    # the slot's generation when this handle was issued
```

Each voice-table slot has a `generation` counter, incremented whenever the slot is reused. Every
handle method first checks `table[slot].generation == handle.generation`. On a mismatch it does
nothing and returns `False`. Handles hold no reference to the `Sound`, so a dropped handle
releases nothing, and a kept one keeps nothing alive.

### 4.5 Resource release

`pygame.mixer.Sound` objects are released when the library drops them. That happens only through
LRU eviction (memory limit) or engine shutdown. Eviction never removes a sound that is playing,
because the voice table holds a reference while the voice plays. Compiled sounds outlive scenes:
a second scene requesting `'coin'` gets the same compiled sound.

---

## 5. DSP decisions

All rendering is float64 numpy on whole buffers (baked) or chunks (live). Conversion to int16
happens once, at the end (`synth.to_pcm16` [Fact]).

| Stage | Algorithm | State | Ranges | Cost class | Verification |
| --- | --- | --- | --- | --- | --- |
| Phase | Exclusive running sum of `f/fs` in cycles, wrapped `% 1.0` (today's `oscillator` [Fact]); float64 keeps sub-cent accuracy for minutes | `phase` float | f ∈ [0, fs/2] | O(n) | AUD-PITCH-006 FFT measurement |
| Phase reset | `phase_reset = "note"` (restart at 0 for each note of `notes`/`chord`) or `"free"` (continue across notes) | per source | — | — | onset waveform check |
| Saw, square, pulse | Naive shape + PolyBLEP residual at each discontinuity (today's [Fact]); pulse is square with `duty`. Compiled, they render at 2× and are filtered down (a 101-tap Hamming-windowed sinc at 0.45 fs, applied centred): PolyBLEP alone measured aliases only 26.8 dB under a 3520 Hz fundamental, 2× gives 51 dB. **Headroom (every periodic source):** the output is divided by the wave's worst band-limited peak over the supported pitches (8 Hz–12 kHz), so a level-1 source never clips and the same shape is equally loud by either route. Table waves use the peak of the band tables those pitches read (`Wave.band_limited_peak`, computed once and cached). PolyBLEP shapes use measured values (the 2× output at level 1, 300 pitches, duties 0.01–0.99): saw 1.143; square and pulse max(\|2d − 1\| + (4/π)·sin(πd), 1.296), the first term being DC plus the lone fundamental of a high note and the second the Gibbs overshoot of narrow pulses; these are divided out with 1% to spare. Live voices (M2, `draft` tier) do not oversample | — | duty 0.01–0.99 | 2× O(n) + 101-tap convolution at 2× | alias floor test (AUD-WAVE-006); no-clip test at level 1 |
| Triangle | Naive (harmonics fall at 12 dB/oct [Fact: comment in `synth.py`]); the Chip profile's 4-bit stepped triangle is quantized and *intentionally* unsmoothed | — | — | O(n) | shape + spectrum |
| Custom waves and wavetables | **Band-limited mip tables.** For each octave band, the wave's FFT is truncated to the harmonics below Nyquist at that band's highest frequency, then inverse-transformed into a 2048-sample table. Reading is linear interpolation within the table, with the band chosen per chunk from the highest frequency in it. Wavetable position crossfades two neighbouring waves' tables | tables per wave, built at registration (≈ 11 bands × 2048 × 8 B ≈ 180 KB per wave) | position ∈ [0, n−1] | O(n) per source | spectral alias test; morph discontinuity test |
| `Harmonics` | Direct additive synthesis into the 2048-sample table, then the mip tables above | — | up to 32 harmonics | build time only | harmonic level check (AUD-WAVE-004) |
| `WavePoint` | `linear`: piecewise linear. `smooth`: monotone cubic (Fritsch–Carlson), so it never overshoots between points — *reference: F. N. Fritsch and R. E. Carlson, "Monotone Piecewise Cubic Interpolation", SIAM J. Numer. Anal. 17(2), 1980*. `steps`: sample-and-hold. Then DC removal and normalization | — | — | build time | point reproduction |
| White noise | `numpy.random.Generator(PCG64(seed)).uniform(-1, 1)` per source; seed per §6.3 | generator | — | O(n) | identical recompile |
| LFSR noise | Galois LFSR stepped at `rate`; output ±1, held between steps. 15-bit taps (14, 13) and a 7-bit "short" mode with taps (6, 5); a table of maximal-length tap sets (Xilinx XAPP 052) is the only allowed input, and `taps=None` takes the width's entry | register int | rate up to fs (at most one step per sample; the public `Noise(rate=...)` is a pitch, so at most Nyquist) | One full period (≤ 32,767 values) is precomputed once per tap set and bit width; output is an indexed gather at the step positions, O(n) | period test |
| Pink noise (M2) | Paul Kellett's "refined" filter of white noise (seven one-pole sections) — *reference: P. Kellett, "Filter to make pink noise from white", musicdsp.org (2000)*. Each section is a first-order IIR; it is computed per section with `scipy`-free numpy by chunked recursion. Cost measured in M2 against the live budget | 7 floats | — | O(n) per section | slope test |
| Envelopes | Piecewise segments in closed form per sample index: linear; exponential (a time constant that reaches 99% of the stage's target in its stated time); `steps(n)` quantized | stage, level | stage times ≥ 0.5 ms | O(n) | stage timing test |
| Pitch curves | `synth.frequency_curve` with the engine's easings [Fact: `glitchygames.effects.easing`] | — | — | O(n) | AUD-INST-008 |
| Filters (M2) | **Trapezoidal-integrated state-variable filter**, stable under fast modulation — *reference: A. Simper, "Linear Trap SVF" (Cytomic technical paper, 2013)*. LP/HP/BP from one structure; resonance `k = 2 − 2·res`, with res clamped to [0, 0.95] | 2 floats per filter | cutoff 20 Hz–0.45 fs | Per-sample recursion: a Python loop over samples with numpy across live voices (A.1 case B: 0.9 ms per 256 frames for 64 voices; live voices are ≤ 8). Compiled sounds run it once | finite-output sweep at maximum resonance (AUD-INST-005) |
| Existing FIR filters (M1) | Hamming-windowed sinc, kept as the M1 filter [Fact] | — | — | O(n·taps) via `np.convolve` | existing tests |
| FM (M4) | **Phase modulation**, as in the DX-style chips the profile is inspired by: `out = sin(2π(φc + I·m))`, where `m` is the modulator's output and `I` (the *index*) is in **cycles** (public name `index`, 0–8). Feedback on one operator uses the average of its last two outputs × `feedback` (0–1) — *reference: J. Chowning, "The Synthesis of Complex Audio Spectra by Means of Frequency Modulation", JAES 21(7), 1973*. Operators evaluate in algorithm order, and feedback is the only allowed loop (one-sample delay). Algorithms are a fixed table of 2-op and 4-op graphs | operator phases, 2 feedback samples | index 0–8, ratio 0.5–16 | per-sample loop only for the feedback operator; others vectorized | sideband test vs Bessel predictions (AUD-INST-006) |
| Ring modulation (M4) | Sample-wise product of two sources | — | — | O(n) | spectrum |
| Hard sync (M4) | The slave's phase resets at each master wrap, with PolyBLEP on the reset step | slave phase | — | O(n), vectorized via wrap indices | spectrum + shape |
| Samples (M4) | Fractional read position; **cubic Hermite** interpolation (quality `full`, compiled) or **linear** (quality `draft`, live); loops get an equal-power crossfade of `crossfade` frames rendered at compile time | read position | rate 1/16–16 | O(n) | rate/duration test; loop boundary test |
| Drive (exists) | `tanh` waveshaper [Fact: `synth.distort`]; compiled at 2× oversampling when drive > 2: zero-stuffed, then the same 101-tap windowed-sinc kernel as the discontinuous waves, applied directly and centred (latency 0; a polyphase form would halve the work) | — | — | 2× O(n·taps) | finite, bounded, zero-latency test |
| Bit / rate reduction (M2) | Quantize to 2^bits levels; sample-and-hold at the reduced rate. These *intentionally* alias | — | bits 1–16; rate 500 Hz–fs | O(n) | level count |
| Delay (M4) | Circular buffer, feedback ≤ 0.9, optional one-pole damping | buffer ≤ 2 s | — | O(n) | tail bound |
| Wow/flutter (M4) | A delay-line read modulated by two LFOs (≈ 0.5 Hz, ≈ 7 Hz), with cubic read | buffer ≤ 50 ms | depth ≤ 30 cents | O(n) | modulation depth |
| Reverb (M5) | A small Schroeder-style comb + all-pass network, tail ≤ 3 s — *reference: M. R. Schroeder, "Natural Sounding Artificial Reverberation", JAES 10(3), 1962* | buffers | — | compile only | tail bound, finite |

**Denormals and non-finite values:** every stateful recursion flushes values with a magnitude
below 1e-30 to zero at chunk boundaries. Every compiled buffer and live chunk is checked with
`np.isfinite`. A compile that fails the check raises `SoundRenderError` naming the sound (a bug,
surfaced at the request). A live chunk that fails it is replaced by silence, the voice is
released, and the event is counted (AUD-RT-004).

**Oversampling:** only for compiled saw, square and pulse (PolyBLEP alone measured 26.8 dB at
3520 Hz, short of AUD-WAVE-006's 40), for drive above 2 and for FM with `index > 4` (2×,
compile-time only, so it is bounded by the sound's length). Live voices (M2, `draft` tier) never
oversample. **Quality tiers:** `full`
(compiled: cubic interpolation and oversampling where listed) and `draft` (live: linear
interpolation, no oversampling). Neither tier is described as hardware emulation.

**De-clicking without smoothing the waves [Call]:** only *boundaries* get ramps, and only where
needed:

- A v1 sound whose first sample's magnitude is above 1/1024 gets a 1 ms fade-in. One whose last
  sample is above that gets a 2 ms fade-out. `hard_edges = true` turns both off, for intentional
  clicks.
- Stops, steals and skips use `Channel.fadeout` (≥ 5 ms).
- Live voices get rendered fades [Fact: today's `_fade_gains`].
- Waveform edges inside a sound are never smoothed.
- v0 recipes get none of this; they compile through today's renderer unchanged (§10.4).

**Level [Call]:** compiled sounds keep the author's levels; there is no automatic normalization
(feature spec §6.5). `normalize = true` scales to -1 dBFS. A peak above full scale is clipped and
logged once.

---

## 6. Assets, library and cache

### 6.1 Schema (v1)

The models are pydantic v2 [Fact: an engine dependency] with `extra='forbid'`. Error messages
render pydantic's `loc` tuple as a TOML path (`instruments.vehicle.routes[1].output`), with a "did
you mean" from `difflib.get_close_matches`. A field that exists in the schema but belongs to a
later milestone is rejected with "`routes` arrives in M2" until its milestone lands
(AUD-ASSET-003). Defaults are listed; a field without one is required.

**`[glitchygames]`**: `kind = "sounds"` (required), `version = 1` (required).

**`[waves.<name>]`** — exactly one of:

| Field | Type | Default | MS |
| --- | --- | --- | --- |
| `mix` | table of wave name → weight | — | M1 |
| `blend` | `{ from = name, to = name, amount = 0–1 }` | — | M1 |
| `harmonics` | table: `fundamental`, `octave`, `octave_and_fifth`, `two_octaves`, `harmonic_5`…`harmonic_32` (each 0–1, default 0), or `drawbars = "888000000"` | — | M1 |
| `points` + `shape` | array of `{ at, level }` (numbers or `CYCLE`/`LEVEL` names in lower case); `shape` ∈ `linear`/`smooth`/`steps` | `shape = "linear"` | M1 |
| `samples` + `resolution_bits` | array of levels; 1–16 bits | no quantization | M4 |
| `sprite` | path to a sprite TOML | — | M4 |

Plus, for every kind: `normalize` (bool, default true).

**`[instruments.<name>]`**:

| Field | Type | Default | MS |
| --- | --- | --- | --- |
| `profile` | `hybrid`/`chip`/`wavetable`/`fm`/`sampler` | `hybrid` | M1 (field); M4 (constraints beyond `hybrid`) |
| `envelope` | preset name, or a table `{ attack, decay, sustain, release, curve }` with `curve` ∈ `linear`/`exponential`/`steps(n)` | `"pluck"` | M1 |
| `live` | bool | false | M2 |
| `seed` | int | derived (§6.3) | M1 |
| `normalize` | bool | false | M1 |
| `hard_edges` | bool | false | M1 |
| `filter` | `{ type = low_pass/high_pass, cutoff }` (FIR) | none | M1 |
| `filter` with `band_pass`, `resonance`, `envelope` | as above + `resonance` 0–0.95, `envelope` table with `amount_octaves` | none | M2 |
| `drive` | 0–20 | 0 | M1 |
| `bits`, `sample_rate_reduction` | 1–16; Hz | none | M2 |
| `parameters.<name>` | `{ range = [lo, hi], default, smoothing_ms = 30, unit = "" }` | none | M2 |
| `routes` | array of `{ from, to, curve = "linear", output = [a, b] }` | none | M2 |
| `vibrato`, `lfos`, `glide`, `bend_range` | tables | none | M4 |
| `algorithm`, `operators`, `feedback` | FM | none | M4 |
| `delay`, `wow_flutter` | tables | none | M4 |
| `reverb` | table | none | M5 |

**`[instruments.<name>.sources.<source>]`** (1–4 sources; table order is the mix order):

| Field | Type | Default | MS |
| --- | --- | --- | --- |
| exactly one of `wave` (name) / `noise` (`white`/`lfsr`/`pink`) / `wavetable` (array of names) / `sample` (path) | — | — | `wave`, `noise` (white, lfsr) M1; `pink` M2; `wavetable`, `sample` M4 |
| `duty` | 0.01–0.99, for `pulse` | 0.5 | M1 |
| `lfsr` | `{ bits = 15 or 7, taps = [a, b], rate }` | `{ bits = 15, taps = [14, 13], rate = "pitch" }` | M1 |
| `level` | 0–1 | 1.0 | M1 |
| `octave`, `semitones`, `detune_cents` | ints/floats | 0 | M1 |
| `pitch` | a pitch (fixed for this source, overriding the note) | none | M1 |
| `pitch_curve` | `{ to = pitch, seconds, easing = "linear" }` | none | M1 |
| `envelope` | as the instrument's | the instrument's | M1 |
| `filter` | as the instrument's (FIR in M1) | none | M1 |
| `position` | `{ from = parameter }` or a number | 0 | M4 |
| `root`, `loop` | sample root pitch; `{ start, end, crossfade }` | — | M4 |

**`[sounds.<name>]`** — the short name `<name>`:

| Field | Type | Default | MS |
| --- | --- | --- | --- |
| `instrument` | an instrument name from any file in the sound directory, or `"path#name"` | required unless `file` | M1 |
| `file` | path to a WAV/OGG recorded sound | — | M1 |
| `pitch` / `notes` / `chord` (at most one) | pitch; `"B5:0.06 E6:0.18"` string or array of `[pitch, seconds]`; array of pitches | none (unpitched instruments allowed) | M1 |
| `length` | seconds per note or chord before release | 0.25 | M1 |
| `transpose` | semitones | 0 | M1 |
| `parameters` | table of fixed parameter values | the instrument's defaults | M2 |
| `bus`, `volume`, `pan`, `priority`, `loop` | playback defaults, overridable in `.play()` | `effects`, 1.0, 0.0, 50, false | M1 |

**Bounds** enforced when a file is read (AUD-RT, AUD-ASSET):

| Item | Limit |
| --- | --- |
| Sources per instrument | 4 |
| Routes per instrument | 8, with no cycles (FM feedback is not a route) |
| LFOs | 2 |
| Wave table length | 2048 internally; imported tables 8–65,536 samples |
| Sample file | 30 s and 32 MB decoded per file (longer → stream it with `music.play_file`) |
| Delay / reverb tail | 2 s / 3 s |
| Compiled sound length | 60 s |
| Notes per `notes` | 256 |
| Pitches per `chord` | 8 |
| Live pool | 4 by default, at most 8 in M2 (D2) |

### 6.2 Identity and cache keys

The `SoundSpec` is serialized to canonical JSON: sorted keys, and floats written with `repr`,
which round-trips exactly. The JSON also includes:

- the mixer sample rate (44100 when no mixer is running);
- the tuning;
- `AUDIO_RENDER_VERSION`, an integer bumped whenever the renderer's output changes;
- the numpy version;
- the platform tag.

The key is the first 128 bits of the SHA-256 of that JSON. Any change to any of these is a miss
(AUD-ASSET-006). A cheaper first-level lookup avoids re-resolving on every call: the library
memoizes `(source string or Instrument id, frozen identity arguments) → key`. That makes a
repeated `audio.sound('coin')` a dict hit.

### 6.3 Seeds

Each source's seed is the instrument's `seed` if given; otherwise it is derived from the sound's
name with `int.from_bytes(sha256(sound name)[:8])`. Either way it is combined with the source's
index through `numpy.random.SeedSequence`. Compiles never touch `glitchygames.randomness` streams,
which respects both the CRT power-on's "no randomness" rule and replays [Fact: the power-on rules
in `crt_power_on.py`]. Version 0 recipes are the exception (§10.4).

### 6.4 The cache: `None`, `'ram'` or `'disk'` **[Owner]**

`AudioEngine(cache=...)` takes the `--sound-cache` option, which is replay-local (§10.2):

- **`None`:** `sound()` resolves and validates, but keeps no audio. The returned `Sound` holds only
  its spec, and every `play()` compiles it in that frame. The compile is timed and accounted like
  any other (§11.0). This is the switch that forces mid-frame rendering.
- **`'ram'`** and **`'disk'`:** as below.

Today's code does not read the mode. It is migrated and removed first (M2, §10.4), and the
benchmarks then run in the owner's order: `None`, then `'ram'`, then `'disk'` (M3, §11.0)
**[Owner]**. `None` and `'ram'` exist from M1, so every test of the new engine can run under
both.

- **Memory (`'ram'`):** a `dict[key, Sound]` plus an LRU order on last play. Total int16 bytes are tracked.
  Above `--sound-cache-memory` (default 256 MB), the least recently played sounds that are not
  playing are dropped. They are recompiled on their next request, which is counted.
- **Disk (`'disk'`, M3):** memory first, then disk.
  - Layout: `<cache>/sounds/<render_version>/<key[:2]>/<key>.wav` (16-bit PCM WAV at the mixer
    rate), written with `output_files.write_aside_then_replace` [Fact].
  - The cache root is a new `state/paths.get_cache_directory(app_name)` beside
    `get_save_directory` [Fact]: macOS `~/Library/Caches/<app>/`, Linux `$XDG_CACHE_HOME/<app>/`
    (default `~/.cache/<app>/`), Windows `%LOCALAPPDATA%\<app>\Cache\`.
  - The size limit is 64 MB, and the oldest-accessed files are pruned at startup.
  - Reads verify the WAV header's rate and length. A bad file is deleted and recompiled.
  - In the browser and in tests, `'disk'` falls back to `'ram'` with one log line. Under
    `--headless` outside tests it is honoured, so the M2 startup benchmark can measure it.
  - **[Call]** The disk layer persists across runs and the engine prunes it, rather than using
    per-run temp files, because the identity hash makes re-use safe and that is what lets a
    second launch skip compiling.

### 6.5 Where compiles happen

There is one rule: **the first request with a given identity compiles**. The places it happens are
conventions, not separate APIs.

1. **Setup (the convention):** games call `audio.sound(...)` in `setup()`. Those compiles run
   before the scene's first logic frame and are attributed to setup. A setup whose compiles exceed
   50 ms logs one INFO line naming the slowest sounds.
2. **Loading screens:** `audio.sounds.warm(requests, budget_ms=...)` takes a list of `sound(...)`
   argument sets and compiles as many as fit in the budget each time it is called, returning
   progress from 0 to 1. It exists only so a loading scene can spread work across frames; it calls
   the same compile path.
3. **Gameplay:** a first request inside a gameplay frame compiles there. It is timed, counted and
   listed with its frame (AUD-FUNC-003).
4. **The engine's own sounds** (CRT) compile before the power-on, in
   `GameEngine._power_on_sound_cues`, which `_run_game` (the blocking start) and `start_async`
   (the browser's) call when the power-on plays (§10.1).
5. **Recompiles:** after eviction, a tuning change or (M4) a hot reload, the next request compiles
   again and is counted.

### 6.6 Hot reload (M4)

With `--sound-hot-reload`, the library records each sound file's mtime. At most once per second,
measured with `clock.elapsed_seconds` [Fact], `AudioEngine.update` checks them. Hot reload is
refused with `--record-trace` and `--replay-trace` (`OPTIONS_REFUSED`), so it never touches a
replay. For each changed file:

1. the file is re-parsed and the short-name index refreshed;
2. memo entries that came from it are dropped, so the next request resolves again and compiles if
   its identity changed;
3. playing voices finish the old audio.

---

## 7. Voices, buses and the mixer

### 7.1 Channel table and the legacy partition

At engine start, where the live pool is reserved today [Fact: `game_engine.py:1817`]:

```
set_num_channels(live_pool + library_channels + legacy_channels)   # default 4 + 32 + 8
set_reserved(live_pool + library_channels)                         # 0 .. 35 reserved
```

| Channels | Used by | How chosen |
| --- | --- | --- |
| `0 .. live_pool-1` | live voices (today's pool, unchanged [Fact]) | `LiveAudio` |
| `live_pool .. live_pool+library-1` | the sound library | the library's own table (`Channel(i).play`) |
| the rest (8, pygame's default count) | legacy `Sound.play()` callers: `SoundBank`, `load_sound`, any game code | SDL picks among unreserved channels |

The library never calls `Sound.play()`, and legacy callers can never reach reserved channels, so
neither cuts the other off (AUD-MIX-008). The one-time reservation keeps today's rule that the
pool is never resized [Fact: BUGS.md #145; `reserve_live_voice_pool` already handles a second
engine in one process].

Allocation for a library play on bus *b* with priority *p*:

1. Take a channel that is free in the table. Whether a channel is free, and so whether a play
   steals, is decided by the table alone, so it is the same in a replay: a channel is free when
   its voice ended by played time (§7.3), or a stop's fade has run out in frame time. The device
   check (`Channel.get_busy()`) only chooses among the free channels: the lowest-numbered one
   not busy on the device, else the lowest-numbered free one anyway, accepting a cut tail of at
   most one device buffer. It never changes what the game sees (§7.3). A free channel counts
   against *b*'s reservation if *b* is under its reservation. Otherwise only channels not needed
   by other buses' unmet reservations are eligible.
2. Otherwise steal: among playing voices with priority ≤ *p*, choose by releasing first, then
   lowest priority, earliest start, lowest channel. Fade it with `Channel.fadeout(10)` and mark
   its channel *fading*. The new sound starts this frame on another free or fading-complete
   channel if one exists. Otherwise it starts on the stolen channel next frame, counted as a
   one-frame delayed play. **[Measured]** (M1, 2026-11-02, `tests/benchmarks/test_channel_fade_relations.py`,
   run under `--benchmark-only` because it depends on the mixer thread's timing, and
   `tests/audio/test_channel_fades.py`
   on SDL's disk driver; pygame-ce 2.5.8, SDL 2.32.10, SDL_mixer 2.8.2): `Channel.play` straight
   after `Channel.fadeout(10)` on the same channel replaces the fading sound at the next mixer
   chunk, so the fade is never heard (worst step 10.3 times a 440 Hz tone's own largest, over
   six steals), and the delay is kept. **[Open]** The delay does not make a steal smooth either:
   SDL_mixer sets a fading channel's volume once per chunk (512 frames, 11.6 ms), so a 10 ms
   fade is one plateau or an immediate halt (worst step 8.3 to 9.7 times the tone's own in two
   recordings of six steals). A smooth steal needs a fade of several chunks or an
   engine-rendered fade tail (risks R4 and R5); the owner decides.
3. Otherwise drop and count.

Which voice is stolen is decided from the table alone, so it is deterministic (AUD-MIX-003). Which
channel index a play lands on may vary with device timing; that is not visible to the game.

### 7.2 Volume and pan

`Channel.set_volume(left, right)` is called after `Channel.play`, because pygame resets channel
volume on play [Fact: noted in `replay/silence.py`]. The gains are:

- left = v·g_bus·g_master·cos(θ)
- right = v·g_bus·g_master·sin(θ)
- with θ = (pan + 1)·π/4, a constant-power law at -3 dB centre.

Bus changes re-apply to every playing channel of that bus. A bus fade is applied as one
`set_volume` per frame (60 steps/s). **[Measured]** (M1, 2026-11-02,
`tests/audio/test_channel_fades.py` on SDL's disk driver): each frame's gain reaches the channel
whole at the next mixer chunk, so a 50 ms fade from full to silence is three steps of a third
(levels 1, 2/3, 1/3, 0, each held for one or two chunks), with a worst step 5.2 to 5.3 times a
440 Hz tone's own largest. **[Open]** Whether those steps are heard as zipper noise for the gain
ranges involved is the owner's listening check; the fallback is to render the fade into a short
tail sound. Voice stops, steals and skips use `Channel.fadeout`, which SDL_mixer also steps once
per chunk rather than ramping (§7.1, §10.1), so a fade shorter than a few chunks is a plateau or
two and a halt.

### 7.3 Voice time without asking the device (fixes the builder check's first finding)

Each voice keeps `played_seconds`. `AudioEngine.update(dt=...)` adds the frame's served `dt` (the
recorded `dt` in a replay [Fact]) only while the voice is **not paused**:

- **Ending:** a baked voice ends when `played_seconds ≥ length`. A looping voice ends only when
  stopped (or released, at the end of its pass). A stopped, cancelled or stolen voice ends at
  once: its handle reports `is_playing` False immediately, while its channel stays *fading*
  for allocation until the fade has run out in frame time.
- **Pause:** pausing (a pause screen over the owner scene, a playback scope [Fact: today's
  `paused_owners`]) calls `Channel.pause()` and stops advancing `played_seconds`. Resuming calls
  `Channel.unpause()`. A paused voice is never reaped, and its channel is never reused while it
  is held.
- **What the game sees:** `handle.is_playing` and reaping use only `played_seconds`, never
  `Channel.get_busy()`. A game reading `is_playing` therefore gets the same answer in a replay
  (`replay/silence.py` warns that device-busy answers are not replay-safe [Fact]).
- **Silenced frames:** `FrameSilencer` stops channels [Fact]. It also calls
  `audio.silenced(channel)` (one new call), which ends the corresponding voices in the table.
- **Before frame 0:** voices started by the engine itself (the CRT) belong to the engine's
  *system owner*, not a scene. During the power-on, the power-on's frame loop calls
  `audio.update(dt=frame_seconds)` with its own measured frame time. Those voices are never
  game-visible, so measured time is acceptable for them. After the power-on they persist into the
  first scene (§10.1).

### 7.4 Buses

The buses are a tree of `Bus(name, parent, volume, mute, solo, reserved_channels,
loudness_budget)`:

- The effective gain is the product of the volumes along the path.
- Solo mutes the subtrees of non-soloed siblings.
- `duck_under` (M5) registers a rule. Each frame, if the trigger bus has a playing voice, the
  ducked bus's gain moves toward `10^(amount_db/20)` at the attack rate. Otherwise it moves back
  at the release rate.
- **Loudness budget (M2):** the sum over a bus's playing voices of `peak × channel gain`. When it
  is above the budget, the bus gain is multiplied by budget/sum, with a 30 ms recovery. This is an
  estimate from compiled peaks and never reads audio back.

### 7.5 Live voices (M2)

The existing `LiveVoice`/`LiveAudio` [Fact] is generalized. A `LiveVoice` renders chunks from a
compiled live instrument (sources, routes, filter state, smoothed parameters) instead of a single
waveform with a cutoff:

- The chunk length is configurable with `--live-chunk-ms` (default 100). M3 measures 50 ms against
  the underrun probe (`scripts/audio_glitch_probe.py` [Fact]). The safety margin is the chunk
  minus the device buffer [Fact: module docstring], so 50 ms leaves about 38 ms.
- The pool grows from 4 to 8 only if AUD-RT-002 holds on the CI Linux container profile (1 CPU
  [Fact: `nox -s test-linux-ci`]).
- `scene_manager.live_audio.create_voice(...)` stays, implemented on the new voice table.

### 7.6 Streams (M5)

`audio.music.play_file` wraps `pygame.mixer.music`: one stream, decoded by SDL_mixer. Its volume
follows the `music` bus. `FrameSilencer` already follows `mixer.music.pause/unpause` [Fact].

---

## 8. API (settled signatures)

Units: seconds (float), hertz (`Hz`), linear gain 0–1, pan −1…1, frames (int). All arguments
after the first are keyword-only. Thread affinity: the main thread only.

```python
# --- pitch.py ---
PitchLike = Note | Hz | Midi | ScaleStep | str | float   # str → Note, float → Hz, int → ValueError

class Note:
    def __init__(self, name: str) -> None: ...      # 'C4', 'F#4', 'Bb3'; ValueError otherwise
    def up(self, *, semitones: float = 0.0, cents: float = 0.0) -> Note | Hz: ...
    def down(self, *, semitones: float = 0.0, cents: float = 0.0) -> Note | Hz: ...
    def detune(self, *, cents: float) -> Hz: ...
    def to_hz(self, *, tuning: Tuning | None = None) -> Hz: ...

class Hz(float):
    def times(self, ratio: float) -> Hz: ...
    def octave_up(self, octaves: int = 1) -> Hz: ...
    def octave_down(self, octaves: int = 1) -> Hz: ...

class Midi(int): ...                                 # 0-127

class Scale:
    def __init__(self, root: str, kind: str) -> None: ...
    def step(self, number: int) -> Note: ...

class PitchTable(Mapping[str, Hz]):
    @classmethod
    def from_dict(cls, table: Mapping[str, float]) -> PitchTable: ...

@dataclass(frozen=True)
class Tuning:
    a4: float = 440.0

def resolve_pitch(pitch: PitchLike, *, tuning: Tuning,
                  sample_rate: int = 44100) -> Hz: ...   # the one conversion point

# --- waves.py ---
class CYCLE:
    START = 0.0; EIGHTH = 0.125; QUARTER = 0.25; THREE_EIGHTHS = 0.375; HALF = 0.5
    FIVE_EIGHTHS = 0.625; THREE_QUARTERS = 0.75; SEVEN_EIGHTHS = 0.875; END = 1.0

class LEVEL:
    TOP = 1.0; HIGH = 0.5; CENTER = 0.0; LOW = -0.5; BOTTOM = -1.0

@dataclass(frozen=True)
class WavePoint:
    at: float            # position in the cycle, 0-1
    level: float         # -1 to 1

@dataclass(frozen=True)
class Harmonics:
    fundamental: float = 1.0
    octave: float = 0.0              # harmonic 2
    octave_and_fifth: float = 0.0    # harmonic 3
    two_octaves: float = 0.0         # harmonic 4
    # harmonic_5 ... harmonic_32: float = 0.0
    @classmethod
    def drawbars(cls, setting: str) -> Harmonics: ...   # nine digits 0-8

class Wave:
    def __init__(self, name: str, *, duty: float | None = None) -> None: ...
    @classmethod
    def mix(cls, **weights: float) -> Wave: ...
    def blend(self, other: str | Wave, *, amount: float) -> Wave: ...
    def detuned(self, *, cents: float) -> Source: ...           # a source, for layering
    @classmethod
    def from_harmonics(cls, harmonics: Harmonics) -> Wave: ...
    @classmethod
    def from_points(cls, points: Sequence[WavePoint], *, shape: str = 'linear',
                    normalize: bool = True) -> Wave: ...
    @classmethod
    def from_samples(cls, *, levels: Sequence[float], resolution_bits: int | None = None,
                     normalize: bool = True) -> Wave: ...       # M4
    @classmethod
    def from_sprite(cls, path: Path | str) -> Wave: ...         # M4

class Noise:
    def __init__(self, kind: str = 'white', *, level: float = 1.0, seed: int | None = None,
                 bits: int = 15, taps: tuple[int, int] | None = None,
                 rate: PitchLike | None = None) -> None: ...

class WaveTable:                                                 # M4
    def __init__(self, waves: Sequence[str | Wave]) -> None: ...

class WaveRegistry:
    def register(self, name: str, wave: Wave) -> None: ...   # ValueError on a built-in name

# --- instruments ---
class Instrument:                                            # immutable; hashable by content
    def __init__(self, *, wave: str | Wave | None = None, noise: str | Noise | None = None,
                 sources: Mapping[str, Wave | Noise | Source] | None = None,
                 envelope: Envelope | str = 'pluck', filter: Filter | None = None,
                 drive: float = 0.0, profile: str = 'hybrid', live: bool = False,
                 seed: int | None = None, normalize: bool = False,
                 hard_edges: bool = False) -> None: ...      # exactly one of wave/noise/sources
    @classmethod
    def load(cls, path: Path | str) -> Instrument: ...       # 'file.toml#name'

# --- engine.py ---
SoundSource = str | Instrument | Sequence_          # name, path, instrument, (M5) sequence

class AudioEngine:
    waves: WaveRegistry
    buses: BusTree
    music: MusicTransport            # M5
    tuning: Tuning
    sounds: SoundLibrary             # warm(), names(), cache statistics

    def sound(self, source: SoundSource, *, pitch: PitchLike | None = None,
              notes: str | Sequence[tuple[PitchLike, float]] | None = None,
              chord: Sequence[PitchLike] | None = None, length: float | None = None,
              transpose: float = 0.0,
              parameters: Mapping[str, float] | None = None) -> Sound: ...
    def play(self, source: SoundSource, *, pitch: PitchLike | None = None,
             notes: str | Sequence[tuple[PitchLike, float]] | None = None,
             chord: Sequence[PitchLike] | None = None, length: float | None = None,
             transpose: float = 0.0, parameters: Mapping[str, float] | None = None,
             volume: float | None = None, pan: float | None = None, bus: str | None = None,
             priority: int | None = None, loop: bool | None = None,
             at_frame: int | None = None, persist: bool = False,
             position: tuple[float, float] | None = None) -> SoundHandle: ...
             # = self.sound(identity...).play(playback...)
    def beep(self, *, pitch: PitchLike = 'A4', wave: str = 'square', length: float = 0.1,
             volume: float = 0.5, bus: str = 'effects') -> SoundHandle: ...
    def diagnostics(self) -> AudioDiagnostics: ...
    def stop_all(self, *, fade: float = 0.05, bus: str | None = None) -> None: ...

class Sound:                         # compiled, immutable, shared; returned by sound()
    name: str                        # the short name, the path, or a generated name
    length: float                    # seconds, including the release tail (baked)
    peak: float
    is_live: bool
    def play(self, *, volume: float | None = None, pan: float | None = None,
             bus: str | None = None, priority: int | None = None, loop: bool | None = None,
             at_frame: int | None = None, persist: bool = False,
             position: tuple[float, float] | None = None) -> SoundHandle: ...
             # None = the sound file's default, else the engine default
    def start(self, *, parameters: Mapping[str, float] | None = None,
              volume: float | None = None, pan: float | None = None, bus: str | None = None,
              priority: int | None = None, persist: bool = False) -> LiveSoundHandle: ...
              # live sounds only; TypeError on a baked sound

class SoundHandle:   # frozen (slot, generation); methods consult the engine's voice table
    def stop(self, *, fade: float = 0.05) -> bool: ...
    def cancel(self) -> bool: ...
    def release(self) -> bool: ...            # live: envelope release; looping baked: end loop
    def unschedule(self) -> bool: ...         # M2
    @property
    def is_playing(self) -> bool: ...
    def set_volume(self, volume: float, *, fade: float = 0.0) -> bool: ...
    def set_pan(self, pan: float) -> bool: ...

class LiveSoundHandle(SoundHandle):
    def set(self, parameter: str, value: float) -> bool: ...   # KeyError for an unknown name
    def note_on(self, pitch: PitchLike, *, velocity: float = 1.0) -> bool: ...
    def note_off(self) -> bool: ...

class SoundLibrary:
    def warm(self, requests: Sequence[Mapping[str, object]], *,
             budget_ms: float | None = None) -> float: ...       # progress 0-1
    def names(self) -> tuple[str, ...]: ...                      # the short names indexed
    def statistics(self) -> CacheStatistics: ...

def render_to_file(sound: Sound, path: Path | str, *, sample_rate: int | None = None,
                   sample_format: str = 'int16', loops: int = 1,
                   tail_seconds: float | None = None, stems: bool = False,
                   parameter_timeline: Mapping[str, Sequence[tuple[float, float]]] | None = None,
                   events: Sequence[OfflineEvent] = ()) -> RenderReport: ...
```

**Rules:**

- Identity arguments: `pitch`, `notes` and `chord` are mutually exclusive (`ValueError`).
  `transpose` applies to `notes` and `chord`. `parameters` is a dict, so parameter names can
  never collide with keyword arguments.
- Playback arguments left as `None` take the sound file's `[sounds.*]` defaults, then the
  engine's defaults.
- **Errors:** `SoundAssetError` (file problems, duplicate names), `SoundRenderError` (a compile
  bug), `KeyError` (unknown short name or parameter) and `ValueError` (invalid argument). The new
  errors derive from the existing `glitchygames.audio.exceptions` hierarchy [Fact:
  `AudioUnavailableError`, `SoundRecipeError`].
- **No mixer:** `sound()` compiles to float buffers (no `pygame.mixer.Sound`), so offline
  rendering and tests work. `play()` returns a handle whose methods return `False`, and a warning
  is logged once (AUD-FUNC-006).
- **Access point:** `SceneManager.audio`, a property creating the `AudioEngine` on first use, as
  `live_audio` does today [Fact: `scene.py:1262`]. It is a `ContextSlot` value, so each engine
  context has its own library, voices and short-name index. **[Call]** M1 adds only the slot.
  Muting all but the audible context is Arcade work, done with the Arcade.
- `Scene.SOUND_DIRECTORY` is a class attribute (default `'sounds'`), resolved relative to the
  scene's package directory (`identity.game_identity(...).package_directory` [Fact]). The index
  is per directory, so scenes sharing a directory share it.
- **Compatibility:** `scene_manager.live_audio` stays. In M2 it is implemented on the new voice
  table.

---

## 9. Determinism and offline rendering

- **Scope (D8):** bit-identical output for a fixed `AUDIO_RENDER_VERSION`, Python, numpy, platform
  tag, sample rate, configuration, asset set, seeds and parameter timeline. Across platforms,
  comparisons use a tolerance of max |Δ| ≤ 2⁻¹⁴ (about −84 dBFS) on float buffers before int16
  conversion, because numpy's `sin`/`exp` may differ in the last ULPs.
- **Offline mixer:**
  - It sums the float buffers of compiled sounds at `round(event_seconds × rate)`, applying the
    same volume and pan law as §7.2, with bus stems if asked.
  - Live sounds are rendered offline by stepping their chunk renderer through a scripted
    parameter timeline. That is the same code as the device path, with the same chunking.
- **Parity:** device-path parity is tested on the pre-device buffers. The buffer that feeds
  `pygame.mixer.Sound` must equal, bit for bit, the buffer `OfflineMixer` uses for a single event
  at offset 0. The device's own mixing (SDL, int16 saturation) is out of scope.
- **Tail termination:** rendering stops when the output stays under −90 dBFS for 100 ms after the
  last event's nominal end, or at `tail_seconds`. The stop is reported in `RenderReport` with the
  peak and the clip count.
- **Recording soundtracks (M5, feature spec §13.3):**
  - Each frame logs its plays (`audio_events`: sound identity, playback arguments) as a
    *measurement* field. It is never compared or served, like `processing_seconds` [Fact].
  - `glitchygames sound render-recording run.jsonl.gz` mixes them offline.

---

## 10. Integration

### 10.1 CRT power-on sound (M1)

- **The sounds:** a new leaf module, `src/glitchygames/crt_power_on_sound.py`, holds the CRT
  instruments and their tunable named constants (`FLYBACK_WHINE_HZ`, `DEGAUSS_HUM_HZ = 60.0`,
  `BARS_TONE_HZ = 1000.0`, `STATIC_SEED`). It requests them through
  `audio.sound(Instrument(...), ...)`, the same API games use.
- **The cue hook:** `crt_power_on.play_power_on` and `play_power_on_async` get one new keyword
  argument, `sound_cues: PowerOnSoundCues | None = None`. It is a small protocol:
  - `at_progress(progress)`, called every power-on frame with the same progress value that drives
    the picture (§12.1 cues are progress fractions); each cue starts on the frame nearest its
    point, the next frame's progress predicted from the last step (ruling R42), so at a steady
    frame rate a sound is at most half a frame off;
  - `skip()`, which fades every CRT voice with `Channel.fadeout(20)`. **[Open]** (AUD-CRT-003,
    ruling R41): SDL_mixer 2.8 recomputes a fading channel's volume once per mixing callback
    (`mix_channels` in src/mixer.c, from `SDL_GetTicks`) and applies it to the whole chunk
    (512 frames, about 11.6 ms), so the 20 ms fade is a plateau or two and then a halt, not a
    ramp. The voices end within 20 ms plus one chunk; the step on a pure tone is measured
    against the model in `tests/test_crt_power_on_sound.py` (a strict xfail holds the "no step
    above threshold" criterion). **[Measured]** (M1, 2026-11-02,
    `tests/audio/test_channel_fades.py` on SDL's disk driver): the model holds on the device:
    `Channel.fadeout(20)` on a 1 kHz tone is one or two plateaus then a halt, every level change
    on a chunk boundary, with a worst step 4.5 to 4.9 times the tone's own largest (from 1.0 to
    4.9 across twelve skips; the model's worst over eight phases is 3.4). The criterion stays
    unmet (strict xfails in both test files). **[Open]** The owner's listening check decides
    whether the skip is heard as a click; the fallback, engine-rendered fade tails (risk R5),
    awaits the owner's decision;
  - `frame(dt)`, which drives `audio.update(dt=...)` for the system owner (§7.3).

  This keeps `crt_power_on.py` a leaf with no audio import [Fact: it is a leaf today], and tests
  pass a recording fake.
- **Wiring:** `GameEngine._power_on_sound_cues` compiles the CRT sounds (a few ms) and makes the
  cues when `--crt-power-on-sound` is not `off`; `_run_game` (the blocking start) and
  `start_async` (the browser's) call it, and pass the cues to the power-on, when
  `_power_on_plays()` (`should_play`) is true. The headless, replay,
  recording, audit and rebaseline rules are inherited from `should_play` [Fact].
- **Carrying into the game:** the bars tone (or channel 3 hiss) is a system-owned, persisting
  voice. `AudioEngine` holds a pending "fade the CRT tail" action, which the first
  `AudioEngine.update` of frame 0 performs (`fadeout(500)`). No scene owns the voice, so scene
  cleanup never stops it early.
- **Browser:** `boot.py` waits for a click before the game starts [Fact], so the audio context is
  running when the power-on plays. **[Open]** This needs a real-browser listening check
  (AUD-PORT-003), the owner's: `nox -s browser -- mr-muncher`, then click the page in Chrome and
  in Safari. Not yet done (2026-11-02).

### 10.2 Engine options (added to `GameEngine.args`)

| Option | Default | Notes |
| --- | --- | --- |
| `--sound-channels N` | 32 | library channels |
| `--live-voice-pool N` | 4 | exists [Fact] |
| `--live-chunk-ms` | 100 | M2 |
| `--sound-cache {none,ram,disk}` | ram | `none` and `ram` from M1; `disk` is refused (`OPTIONS_REFUSED`, "arrives in M3") until M3. Replay-local (added to `REPLAY_LOCAL_OPTIONS` [Fact: `replay/driver.py`]), so a recording replays under any mode |
| `--sound-cache-memory MB` | 256 | |
| `--crt-power-on-sound {on,off}` | on | |
| `--sound-diagnostics` | off | starts with the debug overlay on, showing the Audio panel (§10.5) |
| `--sound-hot-reload` | off | M4; refused with `--record-trace`/`--replay-trace` |

### 10.3 Replays, silence, scenes, shutdown

- **Silence:** `FrameSilencer` stops channels [Fact] and calls `audio.silenced(...)` (§7.3).
- **Scenes:** scene ownership and pausing behind a playback scope follow today's
  `LiveAudio.update` arguments [Fact]. `AudioEngine.update` takes the same ones.
- **Shutdown:** `GameEngine._shutdown` calls `audio.close()` before `pygame.quit()`. That fades
  everything over 50 ms and waits at most 100 ms with `clock.raw_sleep` [Fact: the only allowed
  sleep].

### 10.4 Migration and clean-up (M2), and legacy parity (fixes the builder check's third finding)

**Version 0 recipes compile through today's renderer.** A `[recipes.*]` table (version 0)
resolves to a `LegacyRecipeSpec`, and its compile calls `SoundRecipe.render()` unchanged [Fact:
`recipes.py`]. That means no de-click ramps, no normalization changes and the same noise source
as today, so the audio is bit-identical (AUD-FUNC-010). `glitchygames sound migrate` converts a
file to version 1 when an author wants the new features; migrated sounds then follow the v1 rules
and are checked by listening.

| Today | After |
| --- | --- |
| `SoundBank(ALL_RECIPES)` + `prerender()` + `play(name)` | `audio.sound(name)` in setup + `.play()`. `SoundBank` is removed |
| Brave Adventurer's `_generate_*_sound()` functions | `Instrument(...)` requests; `GameSounds` and its generator functions are removed |
| `scene_manager.live_audio.create_voice(waveform=..., frequency=..., low_pass_cutoff=...)` | `audio.sound(Instrument(..., live=True)).start(parameters={'speed': ...})`; `live_audio` and `create_voice` are removed |
| `game_objects.sounds.load_sound(file)` | `audio.sound('sfx_slap')` (a recorded file by short name); `load_sound` and the `SFX` constants are removed |
| `NOTE_FREQUENCIES` tables | unchanged, or `PitchTable.from_dict(NOTE_FREQUENCIES)` |

Mr. Muncher and Clockwork Keep define their recipes in Python (`ALL_RECIPES` [Fact]), not TOML.
`audio.sounds.add_recipes(ALL_RECIPES)` registers them as short names, a thin adapter that exists
only for migration and compiles nothing. Brave Adventurer's re-authored sounds are compared within
1 LSB, or by RMS spectrum within 0.5 dB plus listening for noise.

**Clean-up [Owner: "complete the API migration to clean everything up"; Call: removal, not
deprecation].** Once all five games are migrated, the old paths are deleted from the engine in
the same milestone: `SoundBank`, `load_sound`/`SFX`, the `live_audio` property and
`LiveAudio.create_voice` (its chunk machinery lives on inside the new live voices), and each
game's own generator code. The synth functions stay as the renderer's building blocks.
`add_recipes` goes too, once the recipes are TOML (`glitchygames sound migrate`). Removal rather
than a deprecation period is safe because neither the engine nor any game is published on PyPI
yet [Fact: CLAUDE.md, Development Setup], so nothing outside this repository depends on them.
Tests of removed code are removed with it; the 100% coverage gate holds.

---

### 10.5 The Audio debug panel (M1; live section M2; replay comparison M3)

The overlay's structure is kept [Fact: `src/glitchygames/debug/overlay.py` `DebugPanel` (F4
cycles in declaration order), `panels.py` with one `draw_*_panel` function per panel,
`DebugFrameInfo` handed in each frame]:

- `DebugPanel.AUDIO = 'audio'` is added after `PERFORMANCE`.
- `DebugFrameInfo` gains `audio: AudioDiagnosticsSnapshot | None`. It replaces today's
  `live_voice_count` field, whose one line moves into the snapshot.
- `AudioEngine.update` builds the snapshot once per frame. It is an immutable dataclass:
  - the cache mode, device format and voice counts;
  - the frame's accounting by kind;
  - the channel states (from the voice table, plus `Channel.get_busy()` for *fading*; display
    only);
  - bus levels;
  - the compile log ring (8 entries);
  - (M2) live voices' parameter values and queue state.
- `DebugOverlay` keeps a rolling `deque` of per-frame audio work by kind, beside its frame-time
  history and over the same `GRAPH_WINDOW_SECONDS` [Fact]. The audio-time graph and the frame-time
  graph therefore share an x-axis.
- `draw_audio_panel(surface=..., overlay=..., font=..., frame_info=...)` follows
  `draw_performance_panel`'s conventions [Fact]: the cached translucent backings, the bundled font
  and `HUD_*` constants. Its new colour constants (compile red, decode orange, live blue, cache
  grey; channel idle, playing, fading, paused) sit beside the existing HUD colours.
- **The All panel** draws only the header lines, through a `draw_audio_header` helper.
- **Watched replays (M3):** the replay viewer already draws the overlay [Fact: rule list in
  `replay/viewer.py`]. When the recording's frames carry `audio_seconds`, the snapshot includes
  the recorded value for the frame being shown, drawn as a second, outlined bar per column.
- **Cost:** overlay drawing is inside the measured frame time, as the Performance panel's
  footnote already says [Fact]. The benchmarks run with the overlay off, and the panel's own draw
  cost is measured once and noted on the *Sound Performance* page.
- **Tests:** pixel assertions on the presented surface, per the repo's rule of asserting on drawn
  pixels rather than draw calls [Fact: CLAUDE.md, Testing Guidelines]:
  - a synthetic history with a gameplay compile at a known frame puts the compile colour in that
    frame's graph column;
  - each channel state's cell colour;
  - the compile log's red entry;
  - the panel's absence from `Scene.screenshot`.

## 11. Performance plan

### 11.0 Measurement design (M3; accounting from M1) **[Owner]**

**Order.** Migration and clean-up first (M2). Then the benchmarks run with the cache off
(`none`), then `ram`, then `disk` (the disk layer is built at the start of M3, after the `none`
and `ram` rows exist).

**The "before" baseline** is the replay ledger's rows at the commit before the migration [Fact:
`quality/replay-ledger/`, one row per recording per commit and machine]. The *Sound Performance*
page reads those rows for the games with sound and plots them beside the post-migration rows
(AUD-MEAS-007). Nothing is added to code that M2 deletes.

**Per-frame accounting (built in M1):**

- `audio/accounting.py` keeps a frame accumulator. A context manager,
  `audio_work(kind, name)`, adds the elapsed `clock.raw_counter_ns()` to it. The kinds are
  `compile`, `decode`, `live_chunk` and `cache_read`.
- At the end of each frame, `SceneManager` hands the accumulator to the doors with
  `processing_seconds` [Fact: `end_frame(processing_seconds=...)`] and resets it.
- `RecordingSources` writes `audio_seconds` (float) and `audio_work` (a list of `[kind, name,
  microseconds]`, at most 32 entries, the rest summed into one `["other", "", µs]` entry). Both
  are added to `MEASUREMENT_FRAME_FIELDS` [Fact: `recording_history.py`], so they never enter a
  content hash and are never compared or served.
- The cost of accounting itself (two counter reads per piece of work) is measured in the storm
  at k = 0 and reported.

**Result rows.**

- A `glitchygames sound-benchmark` tool, registered in `registry.TOOLS` like `measure` [Fact],
  runs the three A/B tests under a chosen mode. It writes one JSON row per benchmark, mode and
  machine to `quality/sound-ledger/`, carrying the same provenance fields as `LedgerRow`
  (`MeasurementRun`: machine, versions, source revision, machine state [Fact]).
- Rows are committed by hand after a run (`nox -s sound-benchmark`), not by the pre-commit hook:
  a full run takes minutes, not the hook's seconds.

**The page.** `docs/quality/sound_performance.md` is rendered by the docs hook through the same
path as the replay performance page [Fact: `scripts/mkdocs_hooks.py` →
`performance_pages`], with bokeh (an existing dependency [Fact: `pyproject.toml`]). Its charts:

| Chart | Data | Reads |
| --- | --- | --- |
| Compile cost per sound | the per-sound benchmark | horizontal bars grouped by game, log ms axis, 1 ms and 16.7 ms lines |
| The storm | storm rows per mode | p99 frame processing (and frames over budget) against *k*, one line per mode, in the order none → ram → disk; `audio_seconds` as a band under the `none` line |
| Frame timelines | real-game rebaselines | per recording, `none` and `ram` frame processing overlaid, audio work shaded, a rug of frames that played a sound; zoomable |
| Distributions | real-game rebaselines | ECDF of frame processing per mode |
| Live chunks | Clockwork Keep's elevator under each mode | chunk cost histogram and its per-frame pattern |
| Startup | `disk` cold vs warm | time from launch to the first frame |
| Before and after the migration | replay ledger rows | p50/p99 per golden replay at the two commits |
| By commit | all rows | each benchmark's p99 per mode by commit |

The page opens with the findings in words, and each chart carries a one-line reading of it.

### 11.1 Benchmark matrix (`tests/benchmarks/test_sound_*.py`, `--benchmark-only`)

| Workload | Measure | Gate (M) |
| --- | --- | --- |
| Compile each feature spec §9.2 example × 8 pitches | ms per sound, ms total | Report only (M1); the disk cache is required if a game's total exceeds 250 ms (M3) |
| Compile today's 18 recipes (Muncher + Keep) | total ms | ≤ 40 ms on the M4 Max (today 36.7 ms [Measured A.4]); the Pi 4 limit is set from its first measurement |
| Repeated `audio.sound('coin')` (cache hit) | µs per call | ≤ 5 µs |
| Live: 1/4/8 vehicle voices, 100 and 50 ms chunks | ms per frame p50/p99/max | p99 ≤ 1.0 ms for the adopted pool (AUD-RT-002) |
| Live: fast control updates (1000 `set`/frame) | ms per frame | ≤ +0.05 ms over no updates |
| Storm: 200 plays in 10 frames with stealing | ms per frame; steal determinism | p99 ≤ 0.5 ms; identical steal log on 3 runs |
| A/B real games (feature spec §16.2): each golden replay and bundled demo with sound under `none`, `ram`, `disk` | `--compare-processing` p99 and frames over budget | `ram` no slower than the pre-migration commit's ledger rows (AUD-RT-001); `none`'s cost reported |
| Underruns: 10-minute live run under the CI Linux profile | `audio_glitch_probe` exit code | `SUCCESS`, not `AUDIO_DROPOUT_RISK` [Fact: exit code 6] |

The A/B works without any sprite difference between the modes. `--rebaseline` records each run's
`processing_seconds` whatever the frames compare, and `--compare-processing` reads only those
[Fact: `replay/processing.py`]. Each record includes:

- the reference hardware **[Owner]**:

  | Tier | Machine | Role |
  | --- | --- | --- |
  | Worst case | Raspberry Pi 4 (RAM TBD), booting from an SD card, passively cooled, stock clocks | **every gate is set from this tier, from the slower of its two OSes** |
  | Mid | Raspberry Pi 5 (RAM TBD), booting from an SD card, the official case with its fan, stock clocks | the typical Pi |
  | High | Raspberry Pi 5 16 GB, booting from an NVMe SSD, in a Thrml Neo 5 NVMe PCIe case (direct-contact heatsink and fan), overclocked within the warranty | the best a Pi does |
  | Desktop | Apple M4 Max | the high end (the Appendix A machine) |
  | Stand-in | The CI Linux container (1 CPU, 2 GB [Fact: `nox -s test-linux-ci`]) | automated, between Pi runs |

  - **Pi operating systems:** each Pi tier runs on Ubuntu 26.04 and on the latest Raspberry Pi
    OS. The owner has two boards per tier, so one per OS. Python 3.14 comes from uv on both.
  - **Pi provenance:** each row records the board, RAM, OS and kernel, boot storage, cooling,
    overclock settings, temperatures and clocks, and whether the run throttled. Timed runs follow
    a thermal warm-up.
  - **Runners:** the Pis are measured by hand until self-hosted Pi runners exist (a separate
    branch, `plans/future-work.md` "Raspberry Pi hardware runners", which details the provenance
    and thermal protocol).
  - Each machine and OS is its own line on the charts;
- the OS, driver, rate and buffer;
- the workload;
- percentiles, maximum, underruns and memory.

The thresholds above are proposals, to be fixed after the M1 measurements (the brief requires
measured gates).

### 11.2 Deployment

Nothing new to install: numpy and pygame-ce are already runtime dependencies [Fact]. The engine
wheel gains only the CRT module. CI runs every sound test on the dummy driver. Browser bundles
ship the same modules.

---

## 12. Roadmap and tasks

### M1 — One-call sound API + CRT (first implementable milestone)

1. `pitch.py` (types, scales, `PitchTable`, `Tuning`, `resolve_pitch`) + tests.
2. `waves.py` (built-ins, `mix`/`blend`, registry, `Harmonics`, `WavePoint`/`CYCLE`/`LEVEL`, mip
   tables) + spectral tests.
3. `render.py` for M1: oscillators, white and LFSR noise, ADSR curves and presets, pitch curves,
   up to 4 layered sources, FIR filter, drive, `notes`/`chord`/`transpose`/`length`, boundary
   de-click, peak report.
4. `assets.py`: v1 models for the M1 fields (§6.1), "arrives in Mx" rejection, v0 recipes as
   `LegacyRecipeSpec`, error formatting, the malformed corpus (≥ 20 cases), the short-name index.
5. `library.py`: `sound()` resolution, identity hashing and memoization, compile accounting
   (setup vs gameplay frames), the memory cache with its LRU limit, `warm`, `add_recipes`.
6. `voices.py`/`buses.py`: the channel partition (§7.1), table allocation and stealing, handles
   with generations, `played_seconds` with pause, constant-power pan, bus volume/mute/solo.
7. `engine.py`: the facade, the `SceneManager.audio` slot, `update(dt)` in the frame, the
   `FrameSilencer` hook, shutdown, `beep`, `play` shorthand.
8. `offline.py`: `render_to_file`; the `glitchygames sound render` and `migrate` subcommands.
9. Diagnostics, the M1 `--sound-*` options (§10.2) including `--sound-cache none|ram`, and the
   per-frame accounting fields (§11.0).
10. The Audio debug panel (§10.5): header, audio-time graph, channel strip, bus meters and the
    compile log; `--sound-diagnostics`.
11. CRT power-on sound (§10.1), with the owner's listening sign-off.
12. Sound Board demo (`src/demos/sound-board-demo/`, console script `sound-board-demo`).
13. Verify the open M1 items: `fadeout` then `play` on a channel (§7.1), frame-stepped bus fades
    (§7.2), and the CRT sound in a browser bundle (§10.1).
14. Docs: `docs/architecture/sound.md` (with an mkdocs nav entry), the CLAUDE.md "Sound Synthesis"
    section, and `plans/future-features.md` #53 marked built for the sound.

### M2 — Live, migration and clean-up

- Live instruments with parameters, routes, curves and smoothing.
- State-variable filter, pink noise, bit and rate reduction.
- `at_frame`, `unschedule` and the late rule.
- Loudness budget, device-loss handling, the Audio panel's live-voices section.
- Migration of all five games, then removal of the old sound paths (§10.4).
- Rev It Up demo; rumble from envelopes; the frame-time Geiger counter (optional).

### M3 — Measurement (in the owner's order)

1. The `glitchygames sound-benchmark` tool, the stand-in storm scene and the per-sound benchmark.
2. **Cache off:** run every benchmark under `none`; commit the rows.
3. **RAM:** run every benchmark under `ram`; commit the rows.
4. The `'disk'` layer and `state/paths.get_cache_directory` (§6.4).
5. **Disk:** run every benchmark under `disk`, plus cold and warm startup; commit the rows.
6. Live-pool and chunk-size measurements (§7.5), the glitch probe under each mode.
7. The *Sound Performance* page with its charts and written findings (§11.0).
8. The Audio panel's replay comparison (§10.5).
9. Set the §11.1 gates from the measured numbers.

### M4 — Instrument depth

- Wavetables; `from_samples`/`from_sprite`.
- WAV samples with loops; samples in hybrid instruments.
- FM, ring modulation and sync; LFOs, vibrato, glide, pitch bend.
- Profiles and pitch quantization.
- Delay and wow/flutter; positional plays; hot reload.
- Wave Lab and Chip Jukebox demos; the random SFX generator.

### M5 — Music and production

- Sequences in all notations, compiled through `audio.sound(sequence)`.
- `MusicTransport` with layers and boundary switches (measured).
- Streamed files; ducking; reverb; stems.
- Recording soundtracks; the controller-speaker bus.
- Night Shift (a game, with a golden replay and a browser build).

### M6 — Authoring and targets

- Sound editor (Bitmappy-style).
- Browser live-voice assessment.
- The native-core gate (§3.4).

---

## 13. Decision register

| # | Decision | Resolution |
| --- | --- | --- |
| D1 | Voices vs sources/operators | A voice is one playing instance. Baked voices cost a mixer channel and no Python time. Live voices cost render time by sources × stages. Diagnostics report voices, live sources and live render time separately |
| D2 | Default limits and quality tiers | 32 library channels, 8 legacy channels, 4 live voices (8 if measured OK). Quality is `full` for compiled sounds and `draft` for live ones. The brief's 64-voice target applies to baked voices only (SDL's C mixer); 64 *live* voices in Python is rejected (A.2/A.3) |
| D3 | DSP and backend | Option A (§3). The native core is gated in M6 **[Open, with the experiment and fallback in §3.4]** |
| D4 | Integration with pygame/SDL | A shared device. The library is a layer over `pygame.mixer`, which stays the only owner. The channel partition keeps the library and legacy callers apart (§7.1) |
| D5 | Clock, queue, ordering, late events | The frame clock and served `dt` for voice bookkeeping and scheduling; sample frames inside compiled sounds. No queue (single thread). Plays issue in call order within a frame. Late scheduled plays (M2) have a 2-frame tolerance, then drop, counted |
| D6 | Schema, versioning, extension | TOML, `.toml`, `[glitchygames] kind = "sounds", version = 1`; v0 recipes compile through today's renderer. The owner was offered `.sound.toml` and has not asked for it; the default stands unless changed |
| D6b | The cache | **[Owner]** A tri-state: `None` (nothing kept; every play compiles), `'ram'`, `'disk'` (§6.4). The disk layer is persistent and pruned by the engine **[Call]**, from M3 |
| D12 | Order of work **[Owner]** | Build the API (M1), migrate every game and remove the old paths (M2), then benchmark: cache off, then `ram`, then `disk` (M3). The pre-migration replay-ledger rows are the baseline |
| D7 | Modulation and feedback limits, processing order | ≤ 8 routes, acyclic. FM feedback 0–1 with a one-sample averaged delay. Order: sources → source envelopes → mix → filter (+env) → amp env → effects → gain/pan → bus → master |
| D8 | Determinism and parity | §9: bit-identical within a fixed environment, a tolerance across platforms, parity on pre-device buffers |
| D9 | Platform, packaging, licensing | No new dependencies. Native (including Linux ARM64 on Raspberry Pi 4/5, the low-end reference), headless and browser (compiled sounds) are supported; browser live sound is an open item; the Pi install path is risk R12 (Appendix B) |
| D10 | Milestones, gates, deferred scope | §12, with the §11 gates set after the M1 measurements. Deferred: real-time bus effects, a master limiter, sample-accurate transitions, voice virtualization, hardware emulation |
| D11 | The one API **[Owner]** | `audio.sound(...)` compiles on first request and returns the cached sound afterwards; getting never plays; setup is a convention. Short names and paths are both accepted (feature spec §3.2) |

### Signal flow

```
 per voice ─────────────────────────────────────────────────────────────────  per bus ────── master
 [src1]─env─┐
 [src2]─env─┼─ mix ─ filter(+env) ─ amp env ─ effects ─ gain ─ pan ─► channel ─► bus gain/duck ─► SDL mix ─► device
 [src3]─env─┤        ▲                ▲                    ▲
 [src4]─env─┘        └──── routes (envelopes, LFOs, velocity, game parameters, smoothed) ────┘
 (left of "channel": compiled once, or rendered in live chunks; right of it: SDL's C mixer)
```

---

## 14. Requirement traceability

Tests live in `tests/audio/` unless noted; benchmarks are in `tests/benchmarks/`.

| Requirement | Impl § | Milestone | Tests |
| --- | --- | --- | --- |
| AUD-MEAS-001 | 6.4, 10.2 | M1/M3 | `test_sound_cache.py::modes_*` |
| AUD-MEAS-002 | 11.0 | M1 | `test_audio_accounting.py`, `tests/test_recording_history.py` (field classification) |
| AUD-MEAS-003…008 | 11.0, 11.1 | M3 | `tests/benchmarks/test_sound_*.py`, the `sound-benchmark` tool's tests, the strict docs build |
| AUD-FUNC-001, 002 | 2.2, 6.2, 8 | M1 | `test_sound_library.py` |
| AUD-FUNC-003 | 4.2, 6.5 | M1 | `test_sound_library.py::compile_accounting_*` |
| AUD-FUNC-004 | 2.2, 8 | M1 | `test_sound_names.py` |
| AUD-FUNC-005 | 4.4, 7.1, 7.3 | M1 | `test_sound_handles.py` |
| AUD-FUNC-006 | 8 | M1 | `test_audio_engine.py::without_mixer_*` |
| AUD-FUNC-007 | 7.1, 10.4 | M1 | existing `test_synth.py`, `test_live.py`, recipe tests unchanged; `test_channel_partition.py` |
| AUD-FUNC-008 | 9 | M1 | `test_offline.py` |
| AUD-FUNC-009 | 7.6 | M5 | `test_music_transport.py` |
| AUD-FUNC-010 | 10.4 | M2 | each member's `test_<game>_sound_migration.py` |
| AUD-FUNC-011 | 5, 6.1 | M1 | `test_render_notes_and_chords.py` |
| AUD-PITCH-001…005 | 8 (pitch.py) | M1 | `test_pitch.py` |
| AUD-PITCH-006 | 5 (phase) | M1 | `test_render_pitch_accuracy.py` |
| AUD-PITCH-007 | 5, 8 | M1 | `test_pitch.py::ranges_*` |
| AUD-WAVE-001…005 | 5, 8 (waves.py) | M1 | `test_waves.py` |
| AUD-WAVE-006 | 5 | M1 | `test_render_aliasing.py` |
| AUD-WAVE-007 | 5 | M4 | `test_wavetables.py` |
| AUD-WAVE-008 | 5, 8 | M4 | `test_waves_from_samples_and_sprites.py` |
| AUD-SRC-001 | 5, 6.3 | M1 | `test_render_noise.py` |
| AUD-SRC-002 | 5 | M2 | `test_render_noise.py::pink_*` |
| AUD-SRC-003 | 5 | M4 | `test_render_samples.py` |
| AUD-SRC-004 | 5, 6.1 | M1/M4 | `test_render_layers.py` |
| AUD-SRC-005 | 2.2 | M1 | `test_sound_names.py::recorded_files_*` |
| AUD-INST-001 | 5 | M1 | `test_render_envelopes.py` |
| AUD-INST-002 | 5 | M2 | `test_render_envelopes.py::retrigger_*` |
| AUD-INST-003 | 5 | M4 | `test_render_modulation.py` |
| AUD-INST-004 | 6.1 | M2 | `test_assets.py::routes_*` |
| AUD-INST-005 | 5 | M2 | `test_render_filters.py` |
| AUD-INST-006 | 5 | M4 | `test_render_fm.py` |
| AUD-INST-007 | 5 | M1–M5 | `test_render_effects.py` |
| AUD-INST-008 | 5 | M1 | `test_render_pitch_curves.py` |
| AUD-GAME-001…006 | 4.3, 7.5 | M2 | `test_live_instruments.py`, demo tests |
| AUD-TIME-001 | 4.2, 9 | M1 | `test_timing.py` |
| AUD-TIME-002 | 4.2 | M2 | `test_timing.py::scheduled_*` |
| AUD-TIME-003 | 5, 9 | M1 | `test_render_notes_and_chords.py::onsets_*` |
| AUD-TIME-004 | 8 | M5 | `test_sequences.py` |
| AUD-TIME-005 | 7.6 | M5 | `test_music_transport.py`, benchmark |
| AUD-TIME-006 | 7.3, 10.3 | M1 | `test_audio_engine_integration.py` (including a pause held longer than the sound) |
| AUD-MIX-001…004 | 7.1, 7.2, 7.4 | M1 | `test_voices.py`, `test_buses.py` |
| AUD-MIX-005 | 7.4 | M2 | `test_buses.py::loudness_*` |
| AUD-MIX-006 | 7.4 | M5 | `test_buses.py::ducking_*` |
| AUD-MIX-007 | 8 | M4 | `test_voices.py::positional_*` |
| AUD-MIX-008 | 7.1 | M1 | `test_channel_partition.py` |
| AUD-RETRO-001…004 | 5, 6.1 | M1 (steps) / M4 | `test_profiles.py`, review checklist |
| AUD-ASSET-001…005 | 6.1 | M1 | `test_assets.py`, `tests/audio/fixtures/malformed/` |
| AUD-ASSET-006 | 6.2, 6.4 | M1/M3 | `test_sound_cache.py` |
| AUD-ASSET-007 | 6.6 | M4 | `test_hot_reload.py` |
| AUD-RT-001 | 4.2, 6.5, 11.0 | M3 | the real-game A/B against the pre-migration ledger rows |
| AUD-RT-002 | 7.5, 11 | M3 | `tests/benchmarks/test_sound_live.py`, the probe |
| AUD-RT-003 | 6.4 | M3 | `test_sound_cache.py::disk_*` |
| AUD-RT-004 | 5 | M1 | `test_render_fuzz.py` |
| AUD-RT-005 | 6.4 | M1 | `test_sound_cache.py::memory_limit_*` |
| AUD-DIAG-001 | 4.2 | M1 | `test_audio_diagnostics.py` |
| AUD-DIAG-002…004 | 10.5 | M1/M2/M3 | `tests/debug/test_audio_panel.py` (pixel assertions) |
| AUD-PORT-001 | 11.2 | M1 | `tests/test_workspace_config.py` dependency check (extended) |
| AUD-PORT-002 | — | M1 | the whole suite on the dummy driver |
| AUD-PORT-003/004 | 10.1 | M1/M6 | a browser probe (the `../pygame-ce-wasm` harness) plus a manual check |
| AUD-PORT-005 | 10.3 | M2 | `test_audio_engine_integration.py::device_*` |
| AUD-CRT-001…003 | 10.1 | M1 | `tests/test_crt_power_on_sound.py` + listening |
| AUD-DEMO-001…004 | 12 | M1–M5 | each demo member's tests |

---

## 15. Risk register (most severe first)

| # | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | Live voices underrun on slow machines (the Raspberry Pi 4 especially) or in the browser (main-thread chunks miss the margin) | Medium–High | Audible gaps in engines and ambience | Keep the pool small; measure on the CI Linux profile and in the browser; restart-on-underrun exists [Fact]; prefer compiled loops where a sound need not follow a parameter |
| R2 | The owner later wants real-time bus effects or sample-accurate music, which option A cannot deliver | Medium | Rework of the output layer | The renderer is pure and backend-agnostic; the native-core gate is defined (§3.4) |
| R3 | Games request sounds first in gameplay and hitch on big instruments | Medium | Frame spikes | Diagnostics name every gameplay compile with its frame; the docs and the Sound Board model the setup convention; the A/B benchmark shows the cost |
| R4 | `Channel.fadeout` then `play` on the same channel cuts the steal fade | Measured: it does (M1, §7.1) | Clicks on stealing | The §7.1 one-frame delay, kept. It is not enough: SDL_mixer steps the 10 ms fade per chunk, so a steal is a plateau or a halt (§7.1, measured); a longer steal fade or rendered fade tails, the owner's decision |
| R5 | Frame-rate volume steps cause zipper noise on bus fades and ducking | Measured: steps of a third at chunk boundaries for a 50 ms fade (§7.2) | Audible stepping | Listening check; `Channel.fadeout` is stepped per chunk too (§10.1, measured); fallback of rendered fade tails |
| R6 | Variant counts (pitches × parameters) grow compile time and memory | Medium | Slow scene starts, memory pressure (44.1 kHz s16 stereo ≈ 10 MB/min) | Diagnostics, `warm` with a budget, the disk cache (M2), mono compiles panned by channel volume (halves memory), the LRU limit |
| R7 | Browser audio differs (ScriptProcessorNode deprecation, autoplay, queue/end callbacks) | Medium | The browser is silent or glitchy | The compiled path is verified for basic play [Fact]; explicit browser checks per milestone |
| R8 | Floating-point differences make cross-platform golden audio flaky | Medium | Flaky tests | Tolerances (§9); golden comparisons per platform tag only |
| R9 | Scope creep (FM, music, editor) delays the visible win | Medium | The owner sees nothing for weeks | M1 is small and ends with the CRT sound and the Sound Board |
| R10 | Short-name ambiguity across files surprises authors | Low | Confusing errors | Duplicates raise naming both files; paths are always available |
| R12 | The Pi install path: numpy resolves to 1.26.4, which has no Python 3.14 wheel on any platform, and miniaudio 1.71 has no Linux ARM64 wheel, so both build from source on a Pi [Fact: `uv.lock`] | High (for the Pi) | No Pi measurements until it installs | Settle on the Pi runners branch (`plans/future-work.md`) before M3's Pi runs |
| R11 | Copyright or likeness concerns with "inspired by" presets | Low | Legal or reputational | Original presets only; a review checklist item (AUD-RETRO-004) |

---

## 16. Summary

**Recommended architecture:**

- `pygame.mixer` stays the only device owner.
- One call, `audio.sound(...)`, takes a short name, a path or an `Instrument`. The first request
  compiles the sound into memory, later requests return it from the engine-owned cache, and
  `.play()` plays it.
- The surrounding API covers pitch types (notes, hertz, MIDI and scale steps side by side), named
  and blendable waves whose numbers are named, and TOML instruments.
- Continuously controlled sounds render in live chunks on the main thread, extending today's
  `LiveVoice`.
- There are no new dependencies and no new threads, and nothing new for replays, headless runs or
  the browser's compiled-sound path to learn.

**Demonstrated by experiment** (Appendix A, throwaway):

- a numpy renderer is fast when uncontended (64 voices at about 9% of a 256-frame budget);
- the same renderer on an audio thread misses deadlines badly under GIL contention;
- render-ahead on a worker needs about 85 ms of lookahead under a busy loop;
- today's recipe and live-chunk costs are small.

**Still proposals:**

- every API shape and default, and the schema;
- the cache and disk layout;
- the DSP algorithm choices (from cited literature);
- the stealing, fading and bus behaviours on pygame's channels (R4 and R5 need M1 checks);
- all performance gates.

**Main risks:** live-voice underruns on slow targets (R1), a future need for real-time effects
that option A cannot meet (R2), and gameplay-time compiles (R3, made visible by diagnostics).

**Order of work [Owner]:** API (M1), then migration and clean-up (M2), then measurement with the
cache off, `ram`, then `disk` (M3), then the deeper features.

**First implementable milestone (M1):** the pitch, wave and instrument API; `audio.sound(...)`
with compile-on-first-request, short names and paths; notes and chords; buses and voice
management with the legacy channel partition; offline render to WAV; the CRT power-on sound; the
Sound Board demo; and the A/B benchmark that measures the smoothness claim.

---

## Appendix A — Feasibility measurements (throwaway; not in the repository)

Machine: Apple M4 Max, macOS (Darwin 27.0), Python 3.14.8, numpy 1.26.4, pygame-ce 2.5.8 (SDL
2.32.10), miniaudio 1.71, on 2026-11-02. The scripts were kept in the session scratchpad and are
disposable. The method is described here so it can be repeated.

### A.1 Uncontended block render (64 voices, 48 kHz, numpy vectorized across voices)

- **Workload A:** phase accumulation + PolyBLEP square + linear envelope + constant-power pan to
  stereo.
- **Workload B:** A + a state-variable filter as a Python loop over samples (numpy across voices).
- **Workload C:** A + a scipy `lfilter` biquad. scipy is present only transitively, through
  aisuite, and is not a proposed dependency.

| Block | Budget | A p50 / p99 / max | B p50 / p99 | C p50 / p99 |
| --- | --- | --- | --- | --- |
| 128 | 2.67 ms | 0.23 / 0.28 / 0.41 ms | 0.46 / 0.53 ms | 0.27 / 0.64 ms |
| 256 | 5.33 ms | 0.40 / 0.47 / 0.50 ms | 0.88 / 0.94 ms | 0.48 / 0.56 ms |
| 512 | 10.67 ms | 0.78 / 0.94 / 1.96 ms | 1.77 / 1.88 ms | 0.92 / 1.03 ms |

### A.2 Python render in a device callback under GIL contention

A `miniaudio.PlaybackDevice` (float32, stereo, 48 kHz) rendered workload A in its generator on
each callback. Meanwhile another thread ran pure-Python arithmetic continuously, a worst-case busy
game loop.

| Switch interval | Render time in callback, p99 | Callback period p50 |
| --- | --- | --- |
| 5 ms (Python default) | 256.6 ms | 230 ms |
| 1 ms | 58.4 ms | 50 ms |
| 0.2 ms | 12.7 ms | 15 ms |

Each numpy call releases and reacquires the GIL, and every reacquisition waits behind the busy
thread. Even at 0.2 ms the render takes more than twice the 5.33 ms budget. Conclusion: option B
is rejected.

### A.3 Render-ahead worker + copy-only callback under the same contention

A worker thread rendered 256-frame blocks into a ring, and the miniaudio callback only copied
bytes. The switch interval was 0.5 ms, the engine's own [Fact]. Each run lasted 5 seconds.

| Ring (lookahead) | Workload | Underrun blocks / callbacks | Callback copy p99 | Render p50 / p99 |
| --- | --- | --- | --- | --- |
| 4 (21 ms) | C | 145 / 980 | 0.017 ms | 3.10 / 18.4 ms |
| 8 (43 ms) | A | 68 / 973 | 0.018 ms | 1.89 / 19.7 ms |
| 8 (43 ms) | B | 156 / 995 | 0.016 ms | 4.10 / 18.2 ms |
| 16 (85 ms) | B | 18 / 991 | 0.015 ms | 3.87 / 15.7 ms |
| 16 (85 ms) | C | 0 / 967 | 0.015 ms | 2.30 / 20.2 ms |
| 8 × 512 (85 ms) | C | 291 / 450 | 0.025 ms | 5.56 / 28.1 ms |

The copy-only callback is cheap, but the worker inherits the contention: render p99 is 15–28 ms.
Underruns stop only at about 85 ms of lookahead, which is today's live-chunk margin [Fact: ≈ 88
ms]. Conclusion: option C buys nothing over A, so it is rejected for M1–M5. A real game loop
sleeps for part of each frame, so these numbers are pessimistic. A is still preferred because it
has no contention at all.

The `pygame._sdl2.audio.AudioDevice` variant of this test hung on start in this environment and
was abandoned without investigation, since the miniaudio variant answered the question.

### A.4 Today's main-thread sound costs

| Item | Time |
| --- | --- |
| Clockwork Keep, 7 recipes rendered at 44.1 kHz | 18.9 ms total (median 0.77; `victory` 9.7, `elevator_clank` 4.1, `death` 3.0) |
| Mr. Muncher, 11 recipes | 17.8 ms total (median 0.61; `film_snap` 8.5, `level_clear` 2.3) |
| One `LiveVoice` 100 ms chunk, sawtooth + low-pass | p50 0.15 ms, p99 0.18 ms, max 0.29 ms |

---

## Appendix B — Dependencies and licensing

| Package | Role | License | Status |
| --- | --- | --- | --- |
| numpy | all rendering | BSD-3-Clause | existing runtime dependency [Fact] |
| pygame-ce | output (mixer), WAV/OGG loading | LGPL-2.1 | existing; excepted by the project's license gate [Fact: `scripts/check_licenses.py`] |
| pydantic | asset models | MIT | existing runtime dependency [Fact: `pyproject.toml`] |
| tomllib | TOML parsing | PSF (stdlib) | existing |
| tomli-w | TOML writing (`glitchygames sound migrate`, later the editor) | MIT | existing runtime dependency [Fact: `pyproject.toml`] |
| miniaudio (pyminiaudio) | controller audio only; not used by this design | MIT (miniaudio itself: public domain / MIT-0) | existing; role unchanged |
| scipy | not used | BSD-3-Clause | present only transitively (aisuite); deliberately not depended on |

No new wheels, native builds or platform constraints are introduced. The native-core gate (§3.4)
would change this set, and would go through the license check and the SBOM at that point.
