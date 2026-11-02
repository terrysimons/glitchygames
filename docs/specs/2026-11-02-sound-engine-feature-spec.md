# GlitchyGames Sound Engine — Feature Specification

- **Date:** 2026-11-02 (revision 2: the one-call `audio.sound(...)` API)
- **Status:** DRAFT for the owner's review. M1 is built on this branch (2026-11-02; user docs:
  `docs/architecture/sound.md`); M2 onwards is not.
- **Companion:** `docs/specs/2026-11-02-sound-engine-implementation-spec.md` (how each requirement
  is met, the traceability table, the decision and risk registers, the measurements).
- **Source brief:** `~/Documents/ChatGPT/GlitchyGames/glitchygames-sound-engine-development-brief.md`
  (the owner's assignment; its vocabulary, workflows and phases are followed here, adapted to the
  repository).
- **Branch:** `docs/sound-engine-specs` (worktree `../glitchygames-sound-engine`).

Labels used throughout:

| Label | Meaning |
| --- | --- |
| **[Owner]** | Decided by the owner in the design conversation (2026-11-02) |
| **[Fact]** | Verified in the repository at `origin/main` 0f1a4b81, with the path cited |
| **[Measured]** | A number from the throwaway experiments in the implementation spec's Appendix A |
| **[Proposal]** | A design choice made in this spec, open to change |
| **[Open]** | Unresolved; the implementation spec names the experiment and the fallback |

---

## 1. Vision

Sound becomes a first-class retro feature of GlitchyGames, alongside the CRT power-on, the
colour bars and the channel 3 screen **[Owner]**: something people notice and play with, not
something that sits quietly underneath. The engine makes a simple beep effortless, a
sophisticated instrument possible, and a sound that reacts continuously to gameplay natural to
express.

It has the immediacy of a classic sound chip and the flexibility of a modern synthesizer. A
developer picks a wave, a pitch, a length and an envelope in one line. A sound designer builds
reusable instruments from named waves, blends, wavetables, envelopes, filters and modulation. A
game connects those instruments to its own values (`rpm`, `charge`, `health`) without ever
building an audio buffer.

Three promises shape everything else:

1. **Games stop "raw-dogging" audio [Owner].** Today each game assembles numpy arrays, mixer
   channels and frequency tables itself. The engine gives them a formal interface instead.
2. **One call gets a sound, and the first call compiles it [Owner].** `audio.sound(...)` returns a
   ready-to-play sound. The first request for a given sound compiles it (renders its audio, or
   prepares a live instrument). Every later request with the same arguments returns it from the
   engine's cache. Getting a sound never plays it; `.play()` does. Calling `audio.sound(...)` in
   `setup` is just the convention for paying the compile cost before gameplay. The code that
   loads a sound is the same code that uses it.
3. **The engine owns compiled sounds [Owner: "the engine tracks the temp files"].** The engine
   keeps the rendered audio and its cache. Games never handle buffers or files.

Example sounds the engine is designed for:

- A coin pickup: two short pulse-wave notes.
- A CRT switching on: a power click, the degauss thump, the flyback whine, static as the picture
  opens, then the colour bars' 1 kHz tone **[Owner: "I would love the CRT power-on to have
  sounds"]**.
- A vehicle: a pitched oscillator plus filtered noise. `rpm` continuously moves its pitch and
  brightness.
- A lead instrument that slides across a wavetable of named waves (sine to ghost to square) as
  a game value rises.
- A seeded procedural explosion that reproduces exactly in a bug report and renders to a WAV
  file without opening an audio device.

### 1.1 What exists today [Fact]

The engine already has a solid base, and this spec builds on it **[Owner: "we can absolutely build
on existing infra"]**:

| Piece | Where | What it does |
| --- | --- | --- |
| Synth toolkit | `src/glitchygames/audio/synth.py` | numpy waveforms (sine, square, sawtooth, triangle, noise; PolyBLEP on square and saw), `frequency_curve`, `Envelope` + `apply_envelope`, FIR `low_pass`/`high_pass`, `distort`, `tremolo`, `mix`, `normalize`, `to_sound()` |
| Recipes | `src/glitchygames/audio/recipes.py` | `Tone`, `SoundRecipe`, TOML `[recipes.<name>]` loading, `SoundBank.play(name)` / `prerender()` |
| Live voices | `src/glitchygames/audio/live.py` | `LiveVoice`: 100 ms chunks rendered from the game loop and queued on reserved mixer channels (`--live-voice-pool`, default 4) |
| Mixer | `pygame.mixer` (pygame-ce 2.5.8, SDL 2.32.10) | 44100 Hz, signed 16-bit, stereo, 512-frame buffer (CLAUDE.md, Sound Synthesis) |
| Replays | `src/glitchygames/replay/silence.py` | `FrameSilencer` stops sounds that silent rebuild/fast-forward frames start |
| Headless | `GameEngine` (`src/glitchygames/engine/game_engine.py`) | `--headless` restarts the mixer on SDL's dummy driver |
| Controller audio | `src/glitchygames/audio/controller_audio.py` | miniaudio capture **and playback** for a controller's own mic and speaker (DualSense) |

How games use it today [Fact]:

- **Brave Adventurer** (`src/games/brave-adventurer/src/brave_adventurer_core/sounds.py`) calls the
  synth functions directly and builds five `pygame.mixer.Sound`s at scene setup.
- **Mr. Muncher** (`src/games/mr-muncher/src/mr_muncher/sounds.py`) and **Clockwork Keep**
  (`src/games/clockwork-keep/src/clockwork_keep/sounds.py`) write `SoundRecipe`s with hand-typed
  `NOTE_FREQUENCIES` tables and `prerender()` a `SoundBank` at setup.
- **Clockwork Keep**'s elevator motor is a `LiveVoice` whose frequency follows the ride.
- **Paddle Slap** loads WAV files through `glitchygames.game_objects.sounds.load_sound`.
- **The CRT power-on** (`src/glitchygames/crt_power_on.py`) is silent. Its sound was already
  listed as a follow-up (`plans/future-features.md` #53).

All sound rendering today runs on the main (game-loop) thread with numpy [Fact]. Today's costs are
small **[Measured]**:

- Mr. Muncher's 11 recipes take 17.8 ms in total. The worst, `film_snap`, takes 8.5 ms.
- Clockwork Keep's 7 recipes take 18.9 ms in total. The worst, `victory`, takes 9.7 ms.
- A live voice's 100 ms chunk takes 0.15 ms.

Both games already pay the larger cost once, at setup. The compile-on-first-request model keeps
compiles out of gameplay frames by convention, and §16.2 says how the gain is measured rather than
assumed.

### 1.2 Vocabulary

These terms are used the same way in both specs and in the public API.

| Term | Definition |
| --- | --- |
| **Wave** | One cycle of a periodic shape, by name (`'square'`, `'ghost'`) or built from points or harmonics |
| **Wavetable** | An ordered row of waves with a continuous *position* that blends between neighbours |
| **Source** | Something that produces a signal: an oscillator playing a wave or wavetable, a noise generator, or a sample player |
| **Operator** | An oscillator plus envelope taking part in an FM arrangement |
| **Instrument** | **How** something sounds: an immutable recipe of up to four sources, their envelopes, filters, modulation, effects and exposed parameters. It has no pitch of its own, like a piano nobody is touching |
| **Sound** | **What** is played on an instrument: an instrument plus a pitch, notes or a chord, and a length. `audio.sound(...)` returns one, compiled and ready to play. A sound is either **baked** or **live** |
| **Compile** | Turning a requested sound into something playable. For a baked sound that means rendering its audio. For a live sound it means validating it and building its wave tables. It happens on the first request, never again for the same arguments |
| **Baked sound** | A sound whose audio was rendered once, at compile time, and is played from memory |
| **Live sound** | A sound rendered while it plays, because exposed parameters change it continuously |
| **Voice** | One playing instance of a sound, with its own state. A chord plays as one voice per note |
| **Sequence** | Timed note events with a tempo and tracks (music; M5) |
| **Bus** | A mixing destination with its own volume: `music`, `effects`, `ui`, `ambience`, `dialogue` |
| **Output channel** | A speaker channel (left, right). Not a pygame mixer `Channel` |
| **Mixer channel** | One of pygame's playback slots (`pygame.mixer.Channel`). Each playing voice uses one |
| **Handle** | What `.play()` returns: a reference to one playing or pending voice |
| **Profile** | A documented set of restrictions or defaults applied to authoring (Chip, Wavetable, FM, Sampler, Hybrid) |

A four-source instrument playing one note is **one voice**. It costs four sources' worth of
rendering, which a baked sound pays once, at compile time. Voices, sources and render cost are
reported separately (§11).

---

## 2. Goals, non-goals and anti-goals

### Goals

1. A formal, small sound API every game can use instead of the mixer and numpy directly **[Owner]**.
2. One call, `audio.sound(...)`, both loads and gets a sound; the first call compiles it, and
   calling it never plays it **[Owner]**.
3. Pitches written as notes **or** frequencies, and both styles feel first-class **[Owner: "Allow both notes and frequency tables"]**.
4. Named waves that can be mixed, blended, morphed in wavetables, drawn as points or built from
   harmonics, in code, in TOML files and later in an editor **[Owner: "All of the above!"]**. The
   numbers in those definitions get explanatory names **[Owner]**.
5. Sounds referred to by short name or by explicit path, both supported **[Owner]**.
6. Continuous game-driven sounds (vehicle, ambience, health) through named instrument parameters.
7. The CRT power-on gets sound as the first thing built on the new interface **[Owner]**.
8. Demos and small games that show the sound system off **[Owner: "build some sound demos - or games"]**.
9. Reproducible, offline rendering to a file, with no audio device.
10. Existing games keep working unchanged until they choose to migrate.

### Non-goals (for this spec's milestones)

- Cycle-accurate or electrically accurate emulation of any real sound chip.
- Transparent time-stretching, or pitch-shifting that keeps duration. Rate-based pitch changes
  also change duration (§4.4).
- Sample-accurate response to arbitrary main-thread calls, or sync across machines.
- An unrestricted modular node graph, or user code running inside rendering.
- 3D/HRTF spatial audio.
- A full instrument editor in the first milestone (§9.4 describes the later tool).

### Anti-goals (would be failures even if they technically work)

- A second, competing audio device or music clock beside `pygame.mixer` that drifts out of sync.
- An API where reading music is required. Frequencies and named steps are always offered.
- Retro character that smears away a wave's intended sharp edges, or clicks and pops that come
  from bad engineering rather than design.
- Gameplay hitches caused by sound work in a frame that the game did not ask for.
- Copying recordings, ROM sound banks or proprietary instrument presets into the engine.
- Breaking replays: a sound must never change game state, a random stream or a clock a replay
  serves.

---

## 3. Public workflows

All examples use the API settled in the implementation spec §8. The engine-owned audio object is
`self.scene_manager.audio` (an `AudioEngine`); examples bind it to `audio`.

### 3.1 The one call **[Owner]**

```python
coin = audio.sound('coin')                         # first time: compiled; afterwards: from the cache
blip = audio.sound('blip', pitch='E5')             # each pitch is its own compiled sound
coin.play()                                        # getting never plays; play() does
audio.sound('blip', pitch='E5').play(volume=0.8)   # the same call inline in gameplay: a cache hit
audio.play('coin')                                 # shorthand for audio.sound('coin').play()
```

`audio.sound(...)` takes two kinds of argument:

- **What the sound is.** The source (a name, a path or an `Instrument`), plus `pitch`, `notes`,
  `chord`, `length`, `transpose` and `parameters`. These identify the compiled sound. Different
  values give a different sound, compiled once each.
- **Nothing about playback.** Volume, pan, bus, loop and priority belong to `.play(...)`. A sound
  file may set defaults for them.

`audio.play(source, ..., volume=..., ...)` accepts both kinds and splits them: the identity
arguments go to `sound()`, the playback arguments to `play()`.

**Where compiling happens is the game's choice.** Calling `audio.sound(...)` in `setup` compiles
before the first frame. The first call during gameplay compiles in that frame. Either way the
engine times and counts every compile, and the diagnostics name any that happened inside a
gameplay frame (§11.1). `setup` is the convention, not a separate API.

### 3.2 Referring to a sound **[Owner: "Could we support both formats"]**

| The game writes | The engine reads it as |
| --- | --- |
| `'coin'` | A **short name**, looked up in the sound files under the scene's `SOUND_DIRECTORY` (a class attribute like `TARGET_FPS`; default `'sounds'`, relative to the game's package) |
| `'sounds/pickups.toml#coin'` | A **path** to a sound file plus the name of a `[sounds.*]` table in it |
| `'sounds/sfx_slap.wav'` | A **path** to a recorded sound |
| `Instrument(...)` | An instrument built in code, used directly |

- A string is a path if it contains `/`, `#` or a file extension. Otherwise it is a short name.
- Short names are indexed the first time one is looked up: every `.toml` sound file in
  `SOUND_DIRECTORY` is read for its `[sounds.*]` table names. Nothing is compiled by indexing.
- If two files define the same short name, the first lookup of that name raises `SoundAssetError`
  naming both files. A short name never silently picks one.
- A WAV or OGG file in the directory is also a short name, by its file stem (`sfx_slap`).
- Paths are relative to the game's package, as sprite files are [Fact: sprites load from package
  paths].

### W1. Play a basic waveform with sensible defaults

```python
audio.beep()                                       # A4 square, 0.1 s, pluck envelope, effects bus
audio.beep(pitch='C5', wave='triangle', length=0.25)
audio.beep(pitch=880.0)                            # a float is hertz
```

`beep(...)` is `audio.sound(Instrument(wave=...), pitch=..., length=...).play(...)` in one line.
A short beep compiles in well under a millisecond, and it is cached like any other sound.

### W2. Get sounds and play them

```python
class GameScene(Scene):
    SOUND_DIRECTORY = 'sounds'

    def setup(self) -> None:
        audio = self.scene_manager.audio
        # Convention: get every sound once here, so gameplay never compiles
        self.coin = audio.sound('coin')
        self.slap = audio.sound('sfx_slap')
        self.blips = {note: audio.sound('blip', pitch=note) for note in ('C5', 'E5', 'G5')}

    def on_coin_collected(self) -> None:
        self.coin.play()
        self.blips['E5'].play(volume=0.8, pan=-0.3)
```

A game may equally keep only names and call `audio.play('coin')` in gameplay. The first such call
compiles, and later calls are cache hits.

### W3. Instruments, notes and chords **[Owner]**

```python
pulse = Instrument(wave='pulse_25', envelope='pluck')               # how it sounds

audio.sound(pulse, pitch='C5')                                      # one note
audio.sound(pulse, notes='B5:0.06 E6:0.18')                         # a melody: the coin
audio.sound(pulse, chord=('C4', 'E4', 'G4'), length=0.5)            # notes together

thick = Instrument(sources={
    'a': Wave('saw'),
    'b': Wave('saw').detuned(cents=7),
    'grit': Noise('white', level=0.1),
})
audio.sound(thick, pitch=Hz(110))                                   # all three layers at 110 Hz
```

- `notes` is a string of `pitch:seconds` tokens. `_:seconds` is a rest. It can also be a sequence
  of `(pitch, seconds)` pairs, where a pitch may be a note, `Hz`, `Midi` or scale step (§4.1). The
  notes are baked into one sound, sample-accurately.
- `chord` plays its pitches together. In a baked sound they are rendered together into one
  voice's audio.
- `transpose=semitones` shifts a `notes` or `chord` sound. `pitch` with `notes` or `chord` is a
  `ValueError` (use `transpose`).
- An **unpitched** instrument (noise, the CRT static, an explosion) needs no pitch. If given, its
  pitch scales the instrument's rates (noise rate, filter cutoff) instead of naming a note.
- **Length:** a single note or chord lasts `length` seconds (default 0.25 s) before its release
  begins. The compiled sound ends after the release tail. A `notes` sound ends after the last
  note's release.

### W4. One-shot, looping and streamed audio

```python
audio.play('coin')                                         # one-shot
hum = audio.sound('ambience_hum').play(loop=True)          # loops until stopped
hum.stop(fade=0.5)                                         # graceful: half-second fade
audio.music.play_file('music/title.ogg', loop=True)        # streamed long-form audio (M5)
```

Streamed audio uses pygame's own streaming player (`pygame.mixer.music`) **[Proposal]**. There is
one stream at a time, it is never compiled into memory, and it is not a `sound()`.

### W5. Update a sound from game state (live sounds, M2)

```python
# vehicle.toml marks the instrument live and exposes 'rpm' (600-7000) and 'load' (0-1); §9.2
self.engine_sound = audio.sound('vehicle').start(parameters={'rpm': 800.0})

def update(self) -> None:
    self.engine_sound.set('rpm', self.car.rpm)       # smoothed by the instrument
    self.engine_sound.set('load', self.car.throttle)

def on_crash(self) -> None:
    self.engine_sound.release()                      # envelope release, then it ends
```

- A live sound uses the same `audio.sound(...)` call. Compiling it validates it and builds its
  wave tables; its audio is rendered while it plays.
- `.start(...)` returns a live handle. `.play()` on a live sound starts it with default
  parameters.
- A baked sound may also take **fixed** parameter values, which identify it like a pitch does:
  `audio.sound('thud', parameters={'impact_energy': 0.6})` is its own compiled sound. Values are
  never rounded to a nearest compiled one; a different value is a different sound.

### W6. Melody and a beat-aligned adaptive-music transition (M5)

```python
calm = Sequence(tempo=96, meter=(4, 4), tracks={
    'lead': Track('chip_lead', notes='E4 G4 A4 _ | G4 E4 D4 _ | C4 D4 E4 G4 | E4 _ _ _'),
    'bass': Track('chip_bass', notes='C2 _ G2 _ | A1 _ E2 _ | F1 _ C2 _ | G1 _ _ _'),
})
audio.music.play(audio.sound(calm, loop_length='auto'))
audio.music.switch_to(audio.sound(tense), at='next_bar')
```

A `Sequence` is something you can compile with `audio.sound(...)`. Inside it, tokens are beats,
`_` holds, `|` marks bars, and every note is sample-accurate because the sequence is baked.
Switching between sequences lands on the requested musical boundary to within one game frame plus
one device buffer (§7.3). That is a measured guarantee, not a sample-accurate one.

### W7. Route sounds through buses

```python
audio.buses['music'].volume = 0.4
audio.buses['effects'].mute = True
audio.play('coin', bus='ui')
audio.buses.add('engine', parent='effects', volume=0.8)    # custom bus
audio.buses['music'].duck_under('dialogue', amount_db=-9.0, attack=0.05, release=0.4)   # M5
```

### W8. Inspect voices, compiles and underruns

```python
report = audio.diagnostics()
report.voices_playing, report.voices_limit          # total and per bus, baked and live
report.compiles                                     # count and milliseconds, setup vs gameplay frames
report.compiles_in_gameplay                         # (name, ms, frame) of each compile inside a gameplay frame
report.live_render_milliseconds                     # p50/p99/max over the last second
report.underruns, report.dropped_plays, report.stolen_voices
report.device                                       # 44100 Hz, s16, stereo, 512 frames, driver
```

The same numbers are drawn live by the debug overlay's **Audio** panel (§11.1.1; F3, then F4 to it, or `--sound-diagnostics` to open on it).

### W9. Render a reproducible sound to a file, offline

```python
from glitchygames.audio import render_to_file

render_to_file(audio.sound('explosion'), 'out/explosion.wav')
render_to_file(audio.sound('vehicle'), 'out/vehicle.wav', parameter_timeline={'rpm': [(0.0, 800), (3.0, 7000)]})
```

```bash
uv run glitchygames sound render sounds/vehicle.toml#vehicle --parameter rpm=800:7000:3s -o vehicle.wav
```

Offline rendering opens no audio device and runs faster than real time. With the same engine
version, platform, configuration, assets and seed, it produces the same samples (§10).

### Lifecycle: the four ways a sound ends

| Call | Applies to | What is heard | When the voice is free |
| --- | --- | --- | --- |
| `handle.release()` | live sounds and looping baked sounds | Live: the envelope's release stage. Looping baked: the loop ends after the current pass and its baked tail plays | After the release or tail |
| `handle.stop(fade=0.05)` | any voice | A fade over `fade` seconds (minimum 5 ms) | After the fade |
| `handle.cancel()` | any voice | A 5 ms de-click fade, nothing longer | Within 5 ms |
| `handle.unschedule()` | a play scheduled with `at_frame` that has not started (M2) | Nothing | At once. Returns `False` if it already started |

Calls on a handle whose voice has ended, or was stolen, do nothing and return `False`. Ending a
voice twice is harmless. Handles never control a different voice that later reused the slot
(implementation spec §4.4: generation counters). `release()` on a non-looping baked sound does
nothing and returns `False`, because its release is already part of its audio.

### Errors

| Situation | Behaviour |
| --- | --- |
| Audio device unavailable (no mixer) | `sound()` still compiles (so offline rendering and tests work). `play()` is a silent no-op that returns a handle whose methods return `False`. One warning is logged (today's `SoundBank` behaviour [Fact], kept) |
| Unknown short name | `KeyError` naming the sound directory and close matches |
| Duplicate short name | `SoundAssetError` naming both files |
| Missing file in a path | `SoundAssetError` naming the path and where it was resolved from |
| Malformed sound file | `SoundAssetError` with the file, the TOML field path and the reason |
| Invalid argument (`volume=-1`, `pan=3`, bare integer pitch, `pitch` with `notes`) | `ValueError` naming the parameter and its valid range |
| Unknown parameter on `set` | `KeyError` naming the instrument's exposed parameters |
| Parameter out of range on `set` | Clamped to the declared range and counted in diagnostics |
| Voice limit reached | The lowest-priority voice is stolen (§6.2), or the play is dropped and counted. Never an exception |

---

## 4. Pitch, waves and sources

### 4.1 Pitch: notes and frequencies side by side **[Owner]**

Three explicit types name a pitch. Each is unambiguous:

```python
Note('A4')      # note name; sharps 'F#4' and flats 'Bb3'
Hz(440.0)       # frequency
Midi(69)        # MIDI note number
```

Anywhere a pitch is accepted, a string is a note name and a float is hertz. A bare `int` is
rejected with a message suggesting `Midi(60)` or `Hz(60)`, because `60` could mean middle C or a
60 Hz hum (explicit is better than implicit).

Moving pitches, in both vocabularies:

```python
Note('C4').up(semitones=7)      # musician: up a fifth
Hz(220).times(1.5)              # anyone: one and a half times higher
Hz(220).octave_up()             # Hz(440)
Note('C4').detune(cents=-8)     # slightly flat
```

**Scales as numbered steps: the off-ramp for people who don't read music [Owner].**

```python
scale = Scale('C', 'major_pentatonic')
melody = [(scale.step(n), 0.15) for n in (0, 2, 4, 2, 5)]   # every step is in key
audio.sound(pulse, notes=melody).play()
```

Scales provided: `major`, `minor`, `major_pentatonic`, `minor_pentatonic`, `blues`, `chromatic`,
`whole_tone`, `dorian`, `mixolydian`. A step past the top wraps into the next octave.

**Frequency tables stay valid.** A game's own `NOTE_FREQUENCIES = {'C4': 261.63, ...}` (Mr.
Muncher, Clockwork Keep [Fact]) keeps working, because it is just a table the game owns.
`PitchTable.from_dict(...)` makes such a table first-class (`table['C4']` returns a `Hz`), so a
game can keep thinking in its own names.

**Tuning [Proposal]:** 12-tone equal temperament with A4 = 440 Hz, set per engine
(`audio.tuning = Tuning(a4=432.0)`). The tuning is part of a compiled sound's identity, so changing
it recompiles on the next request. Retro pitch quantization (§8) is a profile option, kept
separate from the pitch types.

**Ranges.** The supported fundamental range is 8 Hz to 12 kHz **[Proposal]**. Below that, a
sound is inaudible as pitch. Above that, a periodic wave's harmonics alias even with
band-limiting. `Hz` accepts 0 to Nyquist (22.05 kHz at the 44.1 kHz mixer rate):

- Values outside the supported range but inside that one log a warning once per sound.
- Non-finite values, negatives and values above Nyquist raise `ValueError` (today's
  `_validate_frequencies` rule [Fact], kept).

### 4.2 Named waves, blends, wavetables and custom waves **[Owner]**

Built-in waves by name: `sine`, `triangle`, `saw`, `square`, `pulse_12`, `pulse_25`, `pulse_75`
(the three non-square duty cycles a classic pulse channel offers), and `pulse` with an explicit
`duty` from 0.01 to 0.99.

```python
Wave('square')
Wave('pulse', duty=0.125)

buzzy = Wave.mix(square=0.6, triangle=0.4)          # weights, normalized for you
hollow = Wave('saw').blend('sine', amount=0.3)      # 30% of the way to sine
```

**Blend versus layer** (the API keeps them distinct):

- **Blend** (`Wave.mix`, `blend`, `WaveTable`) produces *one* oscillator with a new shape. It is
  cheap, and it is the classic wavetable sound.
- **Layer** (several sources in an instrument, §5.1) runs separate oscillators that can be
  detuned against each other for a thick, chorused sound.

**Wavetables (M4):**

```python
table = WaveTable(['sine', 'triangle', 'saw', 'square'])
charge = audio.sound(Instrument(wavetable=table, position=Modulated('charge', 0.0, 3.0)),
                     pitch='C4').start()
charge.set('charge', 0.4)
```

A position of 2.5 is half saw, half square. The position moves continuously and is smoothed
(§5.4). Interpolation within a cycle is linear between table samples. Between waves it is a
linear crossfade **[Proposal]**.

**Custom waves with named numbers [Owner: "give those numbers named constants ... to help
explain what's going on"].** Every number in a wave definition is a keyword or a named constant,
never a bare positional list:

```python
from glitchygames.audio import Harmonics, Wave, WavePoint, CYCLE, LEVEL

# "How loud is each overtone", by the overtone's musical name
ORGAN = Harmonics(
    fundamental=1.0,        # the note itself
    octave=0.5,             # 2x the frequency
    octave_and_fifth=0.0,   # 3x
    two_octaves=0.25,       # 4x
)
audio.waves.register('organ', Wave.from_harmonics(ORGAN))

# Points across one cycle: where in the cycle (CYCLE) and how high (LEVEL)
GHOST = (
    WavePoint(at=CYCLE.START,          level=LEVEL.CENTER),
    WavePoint(at=CYCLE.EIGHTH,         level=0.8),            # a sharp rise...
    WavePoint(at=CYCLE.QUARTER,        level=0.3),            # ...that sags
    WavePoint(at=CYCLE.HALF,           level=LEVEL.CENTER),
    WavePoint(at=CYCLE.THREE_QUARTERS, level=-0.6),
    WavePoint(at=CYCLE.END,            level=LEVEL.CENTER),
)
audio.waves.register('ghost', Wave.from_points(GHOST, shape='smooth'))   # or 'linear', 'steps'
Wave.mix(ghost=0.5, square=0.5)
```

- `Harmonics` also takes `harmonic_5=...` through `harmonic_32=...` for higher overtones, and
  `Harmonics.drawbars('888000000')` for the nine-drawbar organ notation (16', 5⅓', 8', 4', 2⅔',
  2', 1⅗', 1⅓', 1'; each digit 0–8). That gives organ players their own names.
- `CYCLE` constants are `START`, `EIGHTH`, `QUARTER`, `THREE_EIGHTHS`, `HALF`, `FIVE_EIGHTHS`,
  `THREE_QUARTERS`, `SEVEN_EIGHTHS` and `END` (0.0–1.0). `LEVEL` constants are `TOP` (1.0), `HIGH`
  (0.5), `CENTER` (0.0), `LOW` (-0.5) and `BOTTOM` (-1.0). Any float in range works as well.
- `Wave.from_samples(levels=..., resolution_bits=4)` takes a fixed-length table, such as the
  32-step, 4-bit wave RAM style of a Game Boy-like wave channel (M4).
- `Wave.from_sprite('waves/ghost.toml')` reads a Bitmappy sprite (M4). Each pixel column is one
  step of the cycle, and the topmost lit pixel in that column is the level. Drawing a wave as
  pixel art is a GlitchyGames-only trick **[Proposal]** (§13).
- Registered waves belong to the engine context. A wave name used in a sound file must be
  registered (in code or in a `[waves.*]` table of any file under `SOUND_DIRECTORY`) before the
  sound is first requested.

**Normalization and import rules:** a custom wave is resampled to the engine's table length
(2048 samples per cycle **[Proposal]**). Its average (DC offset) is removed and it is scaled so
its peak is 1.0; `normalize=False` keeps the author's levels. A wave with no variation (all one
level) is rejected.

The same definitions in a TOML file (§9.2):

```toml
[waves.organ.harmonics]
fundamental = 1.0
octave = 0.5
two_octaves = 0.25

[waves.ghost]
shape = "smooth"
points = [
  { at = "start", level = "center" },
  { at = "eighth", level = 0.8 },
  { at = "quarter", level = 0.3 },
  { at = "half", level = "center" },
  { at = "three_quarters", level = -0.6 },
  { at = "end", level = "center" },
]
```

### 4.3 Noise

| Noise | Description | Milestone |
| --- | --- | --- |
| `white` | Flat-spectrum noise from a seeded stream | M1 |
| `lfsr` | Retro noise from a linear-feedback shift register, with `bits` (7 or 15), `taps` from a validated list, `rate` (Hz or a note) and an explicit `seed`. Short (7-bit) mode gives the metallic, pitched buzz of classic chips | M1 |
| `pink` | -3 dB/octave noise for wind, surf and engines | M2 |

Every noise source has its own seed. The default seed is derived from the sound's identity and
the source's position in it, so a sound's noise is identical on every compile and never draws
from a game's random streams. The engine keeps named, seeded streams in
`src/glitchygames/randomness.py`, and replays require games' streams to be untouched [Fact].

### 4.4 Samples

```toml
[instruments.drum.sources.hit]
sample = "samples/snare.wav"
root = "D3"            # the pitch the recording plays at its own speed
loop = { start = 1200, end = 9800, crossfade = 256 }   # frames
```

- One-shots and forward loops are covered, with an optional loop crossfade. Playback rate follows
  pitch: an octave up plays twice as fast and lasts half as long. **Rate-based pitch changes also
  change duration [Brief].**
- Formats: WAV (PCM 8/16/24-bit, float32) in M4, and OGG through pygame's own loader [Fact:
  `pygame.mixer.Sound` loads it] **[Proposal]**.
- Samples at a different rate from the mixer are resampled at compile time.
- A plain recorded file used as a whole sound (`audio.sound('sfx_slap')`) is available in M1. It
  is loaded as-is, with no instrument.

### 4.5 Hybrid instruments

Up to four sources per instrument (oscillators, wavetables, noise, samples) are mixed with
per-source level, pitch offset and envelope. Layered oscillators and noise are available in M1;
samples and wavetables join in M4. The canonical example is §9.2's hybrid impact.

---

## 5. Instrument behaviour and modulation

### 5.1 Instrument structure

An instrument is:

1. up to 4 **sources**, each with an optional envelope;
2. their **mix**;
3. an optional **filter** with its own envelope;
4. the **amplifier envelope**;
5. **effects**;
6. level and pan.

Exposed **parameters** drive any modulatable value through mapping curves.

### 5.2 Envelopes

ADSR has `attack`, `decay`, `sustain` (level 0–1) and `release`, in seconds. Each stage has a
curve: `linear`, `exponential` or `steps(n)` (stepped, chip-style). Named presets cover the
common cases: `'pluck'`, `'pad'`, `'organ'`, `'percussive'` and `'swell'`. The existing
`Envelope(attack, decay, sustain_level, release)` [Fact] keeps working.

Retrigger rules for live notes: `retrigger = "restart"` (from zero, with a 2 ms de-click),
`"legato"` (keep the current level and glide the pitch) or `"from_current"` (restart the attack
from the current level). The default is `"from_current"` **[Proposal]**.

### 5.3 Modulation

- **LFOs:** wave by name (any registered wave), rate in Hz (or note lengths at a tempo, M5),
  depth, phase and optional per-note retrigger. At most 2 per instrument (M4).
- **Pitch:** tuning, `detune_cents`, pitch bend (in semitones, with the range set per
  instrument), vibrato (an LFO on pitch) and glide (M4).
- **Pitch curves** (M1): a note's pitch can slide to a target over a time with an easing curve.
  This is today's `frequency_curve` with easing [Fact].
- **Velocity:** 0–1, mapped to level and optionally to filter cutoff.
- **Routes** (M2): `source → destination × amount`.
  - Sources: an envelope, an LFO, velocity, note pitch or an exposed parameter.
  - Destinations: pitch, level, pan, filter cutoff, filter resonance, pulse duty, wavetable
    position or FM index.
  - At most 8 routes per instrument. Cycles are rejected at load.
- **FM, ring modulation and hard sync** are three distinct operations (M4):
  - **FM:** 2- and 4-operator arrangements chosen from named algorithms (`stack`, `pair`, `y`,
    `branch`, …), with optional feedback on one operator (0–1, one-sample delay).
  - **Ring modulation:** multiplies two sources, for bell-like and metallic tones.
  - **Hard sync:** one oscillator's cycle restarts another's, for tearing, vocal-like leads.

### 5.4 Exposed game parameters, mapping and smoothing (M2)

```toml
[instruments.vehicle.parameters.rpm]
range = [600.0, 7000.0]
default = 800.0
smoothing_ms = 60          # how quickly a jump is followed
unit = "rpm"

[[instruments.vehicle.routes]]
from = "rpm"
to = "pitch"
curve = "exponential"      # linear | exponential | logarithmic | smoothstep | steps(8)
output = ["A1", "E3"]      # notes, Hz or semitone offsets
```

- Values outside `range` are clamped and counted.
- Smoothing is a one-pole glide in the instrument's own time. A control update can never jump the
  sound in a way that clicks **[Brief]**.
- **Update rates:** the game may call `set` every frame or more often. Only the latest value per
  parameter per render chunk is used. Updates are coalesced, never queued without limit.
- **Late updates:** a value set during a frame affects audio that has not been rendered yet. That
  is after the already-queued chunk, so the delay is at most one chunk (§7.1).
- **Expired handles:** `set` on a released or ended live sound returns `False` and does nothing.

### 5.5 Filters

Low-pass, high-pass and band-pass have a cutoff (Hz or a note) and a resonance (0–0.95 of
self-oscillation, clamped to stay stable) **[Proposal]**. Each instrument has one filter, with a
filter envelope (M2). M1 sounds use the existing FIR low- and high-pass filters [Fact] without
resonance.

---

## 6. Voices, buses and mixing

### 6.1 Voice limits and categories

- **Baked voices** each use one mixer channel. The default is 32 mixer channels for the sound
  library **[Proposal]**. Mixing happens in SDL's C mixer, so baked voices are cheap.
- **Live voices** render in Python and keep the reserved live pool [Fact: `--live-voice-pool`,
  default 4]. M3 raises the pool to 8 if its frame-time measurements allow (implementation
  spec §11).
- **Older code** that calls `Sound.play()` directly (`SoundBank`, `load_sound`) keeps its own
  unreserved channels (pygame's default 8), so it never takes a library channel and the library
  never cuts it off.
- **Category reservations:** each bus may reserve a minimum number of mixer channels (`ui`: 2,
  `music`: 2 by default), so a storm of effects can never silence a menu click.

### 6.2 Voice stealing and overload

When a play finds no free channel in its bus's share:

1. Steal the lowest-priority voice, the oldest first among equals, provided its priority is lower
   than or equal to the new play's. `priority` runs 0–100; the defaults are 50 for effects, 80 for
   UI and 90 for music.
2. A stolen voice fades out over 10 ms instead of cutting off.
3. If nothing is stealable, the new play is dropped and counted (`dropped_plays`).

Release tails count toward the limit until they end. A voice in its release stage is preferred
for stealing over one at the same priority that is not releasing.

When live voices exceed their render budget (§11):

1. the engine lowers live-voice quality (filter quality first, then wavetable interpolation);
2. if that is not enough, it releases the lowest-priority live voice.

Both steps are logged. Virtualizing inaudible voices is **deferred**.

### 6.3 Buses

The default buses are `music`, `effects`, `ui`, `ambience` and `dialogue`, under `master`. Games
can add custom buses with a parent. The bus graph is a tree, so it has no cycles.

- **Volume** (0–1, or `volume_db`), **mute** and **solo** per bus. Changes apply to voices already
  playing.
- **Pan** per voice, from -1 (left) to +1 (right), with a constant-power law (-3 dB at centre).
- **Fades:** `bus.fade_to(volume, seconds)`.
- **Ducking:** `bus.duck_under(other_bus, amount_db, attack, release)` (M5).
- **Bus effects:** buses apply volume, pan, ducking and fades in real time. Effects that change the
  sound itself (echo, bit reduction) belong to instruments and are compiled in (§6.4). Real-time
  bus effects need the native-core decision (implementation spec, decision D3).

### 6.4 Effects

| Effect | Where | Milestone |
| --- | --- | --- |
| Distortion / drive (exists [Fact]) | instrument, compiled | M1 |
| Bit reduction (bit depth) and sample-rate reduction | instrument, compiled or live | M2 |
| Delay / echo (bounded feedback ≤ 0.9, delay ≤ 2 s) | instrument, compiled | M4 |
| Wow and flutter (tape pitch wobble) | instrument, compiled or live | M4 |
| Simple reverb (short rooms, tails ≤ 3 s) | instrument, compiled | M5 |
| Ducking | bus, real time (gain only) | M5 |
| Master limiter | master | Deferred (needs a real-time mix path; D3) |

### 6.5 Headroom and clipping

- Compiled sounds keep the author's levels. They are **not** silently normalized.
- Compiling reports each sound's peak. A peak above 0 dBFS is clipped to full scale and logged
  once with the sound's name.
- `normalize = true` in a sound (or `normalize=True` in code) scales the peak to -1 dBFS.
- A **loudness budget** per bus (M2) lowers that bus's volume briefly when exceeded, to keep SDL's
  mixer from hard-clipping during explosion storms. The default budget is a summed peak of at most
  1.5 across the bus's playing voices.
- Meters report each bus's summed peak (an estimate from compiled peaks and volumes; no audio is
  read back) and the clip-protection events.

### 6.6 Positional audio (M4)

`.play(position=(x, y))` uses the active camera: pan comes from horizontal offset and attenuation
from distance, with a cutoff radius. Nothing beyond 2D is planned.

---

## 7. Timing and music

### 7.1 Clock domains

| Domain | Unit | Who uses it | Replayed? |
| --- | --- | --- | --- |
| Frame | integer frame number and the frame time (`dt`) the engine served [Fact: `glitchygames.clock`] | game code, scheduling, voice bookkeeping, replays | Yes |
| Sound frames | integer audio sample frames inside one compiled sound | the renderer | n/a (deterministic) |
| Beats | beats at a sequence's tempo | sequences (M5) | n/a |
| Device | the mixer's playback | nothing in the public API | No |

Rules:

- `play()` starts the sound at the next mixer buffer after the call. With the 512-frame buffer at
  44.1 kHz, that is within about 11.6 ms [Fact: buffer size, CLAUDE.md]. The start is not
  sample-accurate.
- **Inside a compiled sound, timing is sample-accurate.** Every note in `notes` lands on its exact
  sample frame, because the whole sound is rendered at once.
- **Live parameter latency:** a live voice renders ahead in chunks (default 100 ms today [Fact];
  M3 evaluates 50 ms). A parameter change is heard within one chunk plus one device buffer.
- `play(..., at_frame=n)` (M2) schedules a play for the start of frame `n`, deterministically in
  replays, with frame resolution.
- **Late scheduled plays (M2):** a play scheduled for a frame that has already passed starts now
  if it is at most `late_tolerance_frames` late (default 2). Otherwise it is dropped. Either way
  it is counted.

### 7.2 Sequences (M5)

A sequence has a tempo (BPM), a meter, optional tempo changes at bar boundaries, and tracks of
note events: pitch, start beat, length in beats, velocity, and optional parameter changes. It can
be written three ways:

- note strings (`'E4 G4 A4 _ |'`, one beat per token);
- `(pitch, beats)` pairs, where a pitch is a note, `Hz`, `Midi` or scale step;
- a step grid for drums (`'x . . x | x . x .'`).

Beats are converted to seconds through the tempo map, then to sound frames, rounded to the nearest
frame per event. Each event is converted from its absolute beat, so rounding never accumulates.
M1's `notes=` string (seconds per token) is the simple form for jingles.

### 7.3 Music transport (M5)

- The transport offers `audio.music.play(sound)`, `stop(fade)`, `pause()`, `resume()`,
  `switch_to(sound, at='now' | 'next_beat' | 'next_bar' | 'end', crossfade)`, and layer control
  (`audio.music.layer('drums').volume = 0`).
- **Layers** are sequences compiled with identical length and tempo and started in the same
  frame, so they stay aligned. Whether their starts land in the same mixer buffer is verified by
  measurement.
- **Boundary accuracy:** transitions are scheduled from the transport's own count of the current
  music's playback, on the frame clock. They land within one frame plus one device buffer of the
  exact boundary **[Proposal, to be measured in M5]**. Sample-accurate transitions are deferred to
  the native-core decision (D3).
- **Pause:** see §7.4. Already-scheduled plays keep their frame numbers.
- **Time scaling** (slow motion): compiled sounds are not resampled. A bus may be marked
  `follows_time_scale`, and new plays on it then use a pitch- and speed-scaled compiled sound
  (M5, optional).
- **Seeking** within music is supported only for streamed files (`pygame.mixer.music.set_pos`).

### 7.4 Scenes, pause, replays and shutdown

- **Scene switches:** voices belong to the scene that started them, like live voices today [Fact:
  `LiveAudio.update(active_scene=...)`]. A scene's voices stop with a 50 ms fade when it is
  cleaned up, unless played with `persist=True`. Music persists by default. Compiled sounds stay
  cached across scenes.
- **Pause screens:** a scene behind a pause scene has its voices paused (`Channel.pause`) and
  resumed later (today's live-voice rule [Fact]). A paused voice keeps its channel and its place
  in the sound.
- **Replays and instant replay:** sounds started in silent rebuild or fast-forward frames are
  stopped (the existing `FrameSilencer` [Fact]). Baked and live voices go through the same mixer
  channels, so the silencer covers them.
- **Recordings:** plays are not recorded as input. They are reproduced because the game's logic
  reproduces them.
- **Shutdown:** all voices fade within 50 ms. The engine waits at most 100 ms, then quits the
  mixer.

---

## 8. Retro profiles (M4)

Profiles constrain or configure the one engine. They are authoring presets and validation rules,
not separate playback systems **[Brief]**.

| Profile | What it constrains | Feels like |
| --- | --- | --- |
| **Chip** | Waves limited to pulse (12.5/25/50/75% duty), triangle (4-bit stepped) and LFSR noise; envelopes in `steps(16)`; pitch quantized to a period register (see below); at most 4 simultaneous voices per sound family | 8-bit consoles |
| **Wavetable** | 32-sample, 4-bit custom waves; no filter; volume in 4 steps | handheld wave channels |
| **FM** | 2- or 4-operator algorithms only; sine operators; feedback on one operator | 16-bit FM consoles and arcade boards |
| **Sampler** | Samples resampled at compile time to a reduced rate (e.g. 16 kHz) with an 8-bit option, optional gaussian-like smoothing and echo | 16-bit sample-based consoles |
| **Hybrid** | No restrictions; any of the above together | modern "retro-inspired" |

**Pitch quantization (Chip profile):** the frequency snaps to what an integer period divider of a
reference clock can produce (`frequency = clock / (16 × (period + 1))`, with the clock and period
bits as profile parameters). This makes high notes slightly out of tune in the authentic way.

**The classic palettes as authoring inspiration** (descriptions of character, not emulation
targets):

- **C64-style (SID):** three voices, each a saw, triangle, pulse or noise wave, with ring
  modulation, hard sync and one shared resonant multimode filter. Buzzy, filter-swept leads and
  basses.
- **NES-style:** two pulse channels with four duty cycles, a stepped triangle (bass, no volume
  control), and LFSR noise in long and short modes. Crisp, clean, rhythmic.
- **Game Boy-style:** two pulses (one with a pitch sweep), a 32-step 4-bit wave channel and LFSR
  noise, hard-panned in stereo. Thin and characterful.
- **Genesis-style:** 4-operator FM with feedback (6 channels) plus a simple square-wave PSG.
  Metallic basses, brassy stabs, punchy drums.
- **SNES-style:** 8 sampled voices with compressed samples, soft gaussian interpolation and a long
  echo. Lush, slightly muffled, reverberant.

The engine does not advertise cycle-accurate emulation; hardware emulation would be a separate
project. No recordings, ROM-extracted samples or proprietary instrument banks are included. Every
preset in the engine is authored from scratch.

---

## 9. Assets and authoring

### 9.1 File format and extension [Proposal; decision D6]

- Sound files are TOML with the `.toml` extension, like the engine's sprite files and today's
  recipe files [Fact: `slime-jump.toml`; `load_sound_recipes` reads `[recipes.<name>]`].
- Each file starts with a header table:

  ```toml
  [glitchygames]
  kind = "sounds"         # tells it apart from sprite and level files
  version = 1
  ```

- A file holds any number of `[waves.*]`, `[instruments.*]` and `[sounds.*]` tables. A
  `[sounds.<name>]` table defines the short name `<name>` (§3.2) as an instrument plus its pitch,
  notes or chord and its playback defaults.
- **Today's recipe files** (`[recipes.<name>]`, no header) load as `version = 0`. Each recipe is
  a short name. `glitchygames sound migrate FILE` rewrites a file as version 1.

### 9.2 Complete examples

The implementation spec §6.1 lists every field and its milestone.

**A short pulse-wave pickup (M1)**

```toml
[glitchygames]
kind = "sounds"
version = 1

[instruments.pickup]
profile = "chip"
envelope = { attack = 0.002, decay = 0.04, sustain = 0.0, release = 0.02, curve = "steps(16)" }

[instruments.pickup.sources.tone]
wave = "pulse_25"

[sounds.coin]
instrument = "pickup"
notes = "B5:0.06 E6:0.18"
bus = "effects"
volume = 0.6
```

**A programmable-waveform lead (M4)**

```toml
[glitchygames]
kind = "sounds"
version = 1

[waves.ghost]
shape = "smooth"
points = [
  { at = "start", level = "center" }, { at = "eighth", level = 0.8 },
  { at = "quarter", level = 0.3 },   { at = "half", level = "center" },
  { at = "three_quarters", level = -0.6 }, { at = "end", level = "center" },
]

[instruments.ghost_lead]
profile = "wavetable"
live = true
envelope = "pad"
vibrato = { rate_hz = 5.5, depth_cents = 18, delay = 0.25 }

[instruments.ghost_lead.sources.main]
wavetable = ["sine", "ghost", "square"]
position = { from = "brightness" }

[instruments.ghost_lead.parameters.brightness]
range = [0.0, 2.0]
default = 0.5
smoothing_ms = 30

[instruments.ghost_lead.filter]
type = "low_pass"
cutoff = "C7"
resonance = 0.2
envelope = { attack = 0.01, decay = 0.4, sustain = 0.3, release = 0.3, amount_octaves = 3.0 }
```

**A hybrid impact (M4; without the sample source it is M2)**

```toml
[glitchygames]
kind = "sounds"
version = 1

[instruments.impact]
profile = "hybrid"
seed = 7

[instruments.impact.sources.crack]          # sampled attack
sample = "samples/crack.wav"
root = "C4"
envelope = "percussive"

[instruments.impact.sources.body]           # synthesized body
wave = "sine"
pitch_curve = { to = "A1", seconds = 0.3, easing = "ease_out_quad" }
envelope = { attack = 0.001, decay = 0.35, sustain = 0.0, release = 0.05 }
level = 0.8

[instruments.impact.sources.tail]           # noise tail
noise = "white"
envelope = { attack = 0.005, decay = 0.6, sustain = 0.0, release = 0.1 }
level = 0.4
filter = { type = "low_pass", cutoff = 1800.0 }

[instruments.impact.parameters.impact_energy]
range = [0.0, 1.0]
default = 0.6

[[instruments.impact.routes]]
from = "impact_energy"
to = "level"
curve = "logarithmic"
output = [0.3, 1.0]

[[instruments.impact.routes]]
from = "impact_energy"
to = "sources.tail.filter.cutoff"
curve = "exponential"
output = [600.0, 5000.0]

[sounds.thud]
instrument = "impact"
pitch = "E2"
length = 0.6
```

In code, `audio.sound('thud', parameters={'impact_energy': 0.9})` compiles a harder thud than the
default 0.6. Each value is its own compiled sound, so a game that wants three strengths gets those
three once in `setup`.

**A vehicle instrument controlled by RPM (M2)**

```toml
[glitchygames]
kind = "sounds"
version = 1

[instruments.vehicle]
profile = "hybrid"
live = true                       # rendered while it plays
seed = 42

[instruments.vehicle.parameters.rpm]
range = [600.0, 7000.0]
default = 800.0
smoothing_ms = 80

[instruments.vehicle.parameters.load]
range = [0.0, 1.0]
default = 0.2
smoothing_ms = 120

[instruments.vehicle.sources.engine]
wave = "saw"
level = 0.7

[instruments.vehicle.sources.rumble]
wave = "pulse_25"
octave = -1
level = 0.5

[instruments.vehicle.sources.air]
noise = "pink"
level = 0.25

[instruments.vehicle.filter]
type = "low_pass"
resonance = 0.3

[[instruments.vehicle.routes]]
from = "rpm"
to = "pitch"
curve = "exponential"
output = [32.0, 220.0]            # Hz: the firing frequency of a small engine

[[instruments.vehicle.routes]]
from = "rpm"
to = "filter.cutoff"
curve = "exponential"
output = [400.0, 4000.0]

[[instruments.vehicle.routes]]
from = "load"
to = "sources.air.level"
output = [0.1, 0.5]

[sounds.vehicle]
instrument = "vehicle"
bus = "effects"
```

### 9.3 Validation, versions, paths and the cache

- **Validation** happens when a file is first read, never during play. Each error names the file,
  the TOML path (`instruments.vehicle.routes[1].output`), the value and what was expected.
- **Unknown fields** are errors in files with a header, so typos are caught. In version 0 recipe
  files they are warnings.
- **Versions:** a file with a newer `version` than the engine understands is refused, naming the
  engine version needed. Older versions are migrated in memory, in order (0→1→…), each step a
  tested function.
- **Paths** (samples, sprites, other sound files) are relative to the file that names them. Paths
  that escape the game's package (`../../`) are refused.
- **Missing assets** raise when the sound that needs them is first requested, naming the file and
  the referring field.
- **Authoritative data:** the TOML files, WAV samples and sprites. **Generated, disposable data:**
  compiled audio in memory and the optional disk cache.
- **The engine-owned cache is a tri-state [Owner: "cache=None, cache='disk', cache='ram'"]:**

  | Mode | `--sound-cache` | What happens |
  | --- | --- | --- |
  | `None` | `none` | Nothing is kept. Every `play()` compiles its sound again, in the frame that plays it. This is the switch that forces mid-frame rendering, for measurement and A/B tests |
  | `'ram'` | `ram` (default) | Compiled audio is kept in memory, keyed by a hash of everything that identifies the sound: the resolved instrument, pitch or notes, parameters, tuning, sample rate, seed, the engine's audio render version and the numpy version |
  | `'disk'` | `disk` (M3) | The `'ram'` behaviour, plus a disk layer in the user cache directory (`~/Library/Caches/glitchygames/sounds/` on macOS), so repeat launches skip compiling. The disk layer is size-limited (default 64 MB), safe to delete and never shipped |

  - Today's code does not get the flag. The games move to the new API and the old paths are
    removed first (M2), and then the benchmarks run in order: cache off, then `ram`, then `disk`
    (M3) **[Owner: "complete the API migration to clean everything up, then we benchmark with the
    cache off, then the others"]**.
  - In code: `AudioEngine(cache=None | 'ram' | 'disk')`, taken from the option.
  - In the browser and in tests, `'disk'` falls back to `'ram'` with one log line.
  - The option is local to a run, so a recording replays under any mode.
- **Hot reload** (development; `--sound-hot-reload`, M4): editing a file recompiles the affected
  sounds on their next request. Voices already playing finish with the old audio.
- Sound files cannot run code.

### 9.4 Later: the sound editor (M6)

A Bitmappy-style tool **[Owner: "All of the above!"]** would:

- draw a wave on a pixel grid, with snapping to the `CYCLE`/`LEVEL` constants;
- build harmonics with drawbars;
- arrange a wavetable and scrub its position;
- show envelope curves, and audition notes from the keyboard and a controller;
- scrub exposed game parameters with sliders, to hear `rpm` sweep;
- save TOML that round-trips exactly.

It is kept out of the first runtime milestones.

---

## 10. Determinism and offline rendering

- **Guarantee:** a compiled sound or an offline render produces bit-identical samples for a fixed
  engine version, Python and numpy version, platform, configuration, asset set, seed and parameter
  timeline. Bit identity across platforms is **not** promised; cross-platform comparisons use a
  tolerance (implementation spec §9).
- Noise and any randomness in a sound come from the sound's own seed (§4.3), never from game
  streams.
- **Offline rendering** uses the same compile path:
  - An offline mix of an event list (`[(seconds, sound, pan, volume), ...]`) places each sound at
    its exact sample offset, which is more precise than the device path.
  - Output is WAV, 16-bit or float32, at a chosen rate, with an optional stem per bus.
  - Tails end when the output stays below -90 dBFS for 100 ms, or at `tail_seconds`, whichever
    comes first.
  - Clipping in offline output is reported, never silently saturated (float32 output keeps it).

---

## 11. Diagnostics, portability and reliability

### 11.1 Diagnostics

Collected without blocking:

- voices playing and their limits (total, per bus, baked and live);
- compiles: count and milliseconds, split into compiles before the first frame or in `setup` and
  compiles inside gameplay frames (each named, with its frame);
- live-voice render time (p50/p99/max per second) and live chunk underruns (today's
  restart-on-underrun [Fact]);
- dropped and stolen plays, and clamped parameters;
- the device format and driver;
- the disk-cache hit rate.

The numbers are available from `audio.diagnostics()`, in the run's performance statistics log and
on the debug overlay's Audio panel.

#### 11.1.1 The Audio debug panel **[Owner: "wire up a debug mode visualizer for the audio measurements"]**

The engine's debug overlay [Fact: `src/glitchygames/debug/`; F3 shows it, F4 cycles its panels,
`--debug-overlay` starts with it on] gets a new **Audio** panel, after Performance in the F4 cycle.
`--sound-diagnostics` starts a run with the overlay on and showing the Audio panel. Like every
overlay panel, it is drawn only on the presented frame: never in screenshots, recordings or
traces [Fact: CLAUDE.md, Debug Overlay].

What it shows, top to bottom:

| Part | What it shows | MS |
| --- | --- | --- |
| **Header** | The cache mode in large type (`CACHE: NONE` in red, `RAM`, `DISK`); the mixer format and driver; voices playing (live / library / legacy); compiles in the last second; cache hit rate | M1 |
| **Audio-time graph** | One bar per frame over the same time window as the Performance panel's frame-time graph, stacked by kind of audio work: compiles (red), file decodes (orange), live chunks (blue), cache reads (grey). Each frame's total processing time is a faint outline behind its bar, and the frame budget is a line, so the audio share of every frame is visible at a glance. With `--sound-cache none`, each play shows as a red spike | M1 |
| **Channel strip** | One cell per mixer channel in three labelled groups (live, library, legacy, §6.1), coloured idle, playing, fading or paused. A stolen voice's cell flashes | M1 |
| **Bus meters** | One bar per bus: its estimated level (compiled peaks × gains; no audio is read back), with mute and solo marks, and a flash when clip protection acts (M2) | M1 |
| **Compile log** | The last 8 compiles: frame number, sound, milliseconds, and *setup* or *gameplay*. Gameplay compiles are red | M1 |
| **Live voices** | Each live voice's sound, current parameter values (`rpm 4200`), last chunk time, queue state and underrun count | M2 |
| **Replay comparison** | In a watched replay, each frame's recorded `audio_seconds` drawn beside this run's, so a replay under another cache mode shows the difference live | M3 |

When the overlay shows **All** panels, the Audio panel contributes only its header lines, to keep
the screen readable.

### 11.2 Platforms

| Capability | macOS / Windows / Linux (native) | Headless (`--headless`, tests, CI) | Browser (PyScript/Pyodide) |
| --- | --- | --- | --- |
| Compiled (baked) sounds | Yes | Yes (dummy driver; plays nothing) | Yes [Fact: `mixer.init` + `Sound.play()` verified in Chromium and WebKit, `pygame-ce-wasm/compatibility-matrix.md`] |
| Live sounds | Yes | Yes (renders, plays nothing) | **[Open]** Depends on `Channel.queue` and channel-end callbacks in the wasm build; measured in M2 |
| Streamed music | Yes | Yes | **[Open]** |
| Offline render to file | Yes | Yes | No file output (in-memory only) |
| Disk cache | Yes | Off by default in tests | No |

No new native dependency is added. Everything is numpy plus pygame-ce, both already required
[Fact: `pyproject.toml`]. miniaudio stays for controller audio only (D3).

**Reference hardware [Owner]:** three Raspberry Pi tiers, two boards each, every tier on both
Ubuntu 26.04 and the latest Raspberry Pi OS:

- **Worst case:** a Raspberry Pi 4 booting from an SD card, passively cooled, at stock clocks.
  The performance gates are set from this tier.
- **Mid:** a Raspberry Pi 5 booting from an SD card, in the official case with its fan.
- **High:** a Raspberry Pi 5 16 GB booting from an NVMe SSD, in a Thrml Neo 5 NVMe PCIe case,
  overclocked within the warranty.

The Apple M4 Max is measured beside them. The Pis are measured by hand until self-hosted Pi
runners exist (planned on a separate branch). The Pi 5 has no 3.5 mm jack, so its audio goes out
over HDMI, USB or I2S.

### 11.3 Device and failure behaviour

- **Unavailable audio:** the game runs silent, with one warning, and `play()` is a no-op [Fact:
  current behaviour, kept].
- **Device removed or added:** the engine already receives `AUDIODEVICEADDED/REMOVED` [Fact:
  `src/glitchygames/events/audio.py`]. When the output device is removed, voices stop. If SDL
  moves to the new default device, play continues. Otherwise the engine reopens the mixer with the
  same format on the next play. Compiled audio is kept in Python memory, so nothing is recompiled
  unless the rate changed (M2).
- **Suspend/resume:** live voices that underrun restart on the next update [Fact: today's rule].
- **Shutdown:** see §7.4.

---

## 12. Showing it off: demos, games and the CRT

### 12.1 CRT power-on sound (Milestone 1) **[Owner]**

The sound follows the existing 1.2 s sequence [Fact: `SEQUENCE_SECONDS = 1.2` in
`crt_power_on.py`]. The cue times are fractions of the sequence's own progress, the same progress
that drives the picture:

| Progress | Picture [Fact] | Sound [Proposal] |
| --- | --- | --- |
| 0.00 | black | The mechanical click of the power switch, then the low *thoom* of the degauss coil: a 60 Hz hum with its harmonics, swelling and fading over ~0.5 s |
| dot → line | the beam dot stretches | The flyback whine fades in: a thin, high tone, pitched lower than a real set's 15.7 kHz so more people hear it. A constant sets the pitch |
| picture opens | the picture opens from the line | A burst of static crackle that thins out through the warm-up flicker |
| background settles | test pattern or channel 3 | **Test pattern:** the classic 1 kHz bars tone. **Channel 3:** a soft hiss. Either is quiet, and fades out over 0.5 s once the game's first frame is shown |
| any key | the sequence skips | Everything fades out over 20 ms, with no click |

Rules (the power-on's existing rules [Fact: module docstring], extended to sound):

- It plays only when the picture does (`should_play`).
- It never plays under `--headless`, in tests, or before replays, audits, rebaselines or
  recordings.
- It uses no game random stream; the static has its own fixed seed.
- It changes no game state or clock.
- `--crt-power-on-sound off` silences it without removing the picture **[Proposal]**.
- The engine compiles these sounds before the sequence starts. They are short and compile in a few
  milliseconds.
- **CRT power-off:** a falling whine and a soft thump, for when the collapse animation is built
  (`plans/future-features.md` #53). It is specified with that feature.

### 12.2 Demos

Each demo is a member of the demos layer with its own console script [Fact:
`src/demos/<name>-demo/`; demos get no browser build].

| Demo | Shows | Milestone |
| --- | --- | --- |
| **Sound Board** | Every built-in wave, noise and envelope on a keyboard grid; notes, Hz and scale steps side by side; chords; live diagnostics | M1 |
| **Rev It Up** | A top-down car whose engine sound follows throttle and RPM, with gear shifts, skids (filtered noise) and collisions sized by impact energy | M2 |
| **Wave Lab** | Draw a wave with the mouse or as pixel art, blend named waves, sweep a wavetable, and hear it on a keyboard | M4 |
| **Chip Jukebox** | One original tune played through each profile (Chip, Wavetable, FM, Sampler, Hybrid), switchable live | M4 |
| **Night Shift** | A small original game with an adaptive score: calm and tense layers, bar-aligned transitions and a health-driven heartbeat | M5 (a game in `src/games/`, with a browser build) |

### 12.3 Migrating the existing games (M2)

- **Mr. Muncher and Clockwork Keep** call `audio.sound(name)` on their recipe names. Their recipe
  files load unchanged as version 0, and each recipe compiles through today's renderer, so the
  audio is bit-identical.
- **Brave Adventurer** moves its five generator functions to instruments.
- **Clockwork Keep's elevator motor** becomes a live instrument with an exposed `speed`
  parameter.
- **Paddle Slap** moves to `audio.sound('sfx_slap')`.

Until a game migrates, the old APIs keep working.

---

## 13. More interesting applications **[Proposal; the owner asked to keep exploring]**

These are ideas to evaluate, not commitments. Each names the milestone that would make it
possible.

1. **VCR sounds for the channel 3 screen and instant replay.** Tape whir and a head click when the
   channel 3 screen appears, a rewind squeal while instant replay rewinds
   (`src/glitchygames/instant_replay.py` [Fact]), and wow-and-flutter on audio during replay
   playback (M4).
2. **The arcade's chime over the colour bars.** `plans/future-features.md` #43 [Fact] asks for "an
   original chime over the bars". It becomes a sound in the engine's own sound file (M1).
3. **A recording's soundtrack.** Plays are deterministic consequences of game logic, so the engine
   can log them per frame and render a recording's audio offline. That is the `audio.raw` capture
   that `plans/future-work.md` §"Headless capture" asks for [Fact: it notes the mixer cannot be
   tapped], and it gives video exports sound (M5).
4. **Sprites that sing.** `Wave.from_sprite` turns any pixel art into a wave, so a game's own
   sprites can become its instruments. The ghost sprite's outline *is* the ghost's voice (M4).
5. **The controller speaker as a bus.** A `controller` bus routes chosen sounds to a DualSense's
   own speaker through the existing `ControllerAudio` [Fact], for a radio voice in your hands (M5;
   miniaudio stays scoped to controller audio).
6. **Rumble that matches the sound.** The same envelope drives controller rumble, so a thud's
   impact and its vibration share one curve (M2; the engine has rumble devices [Fact: `scene.py`
   `_rumble_devices`]).
7. **A Geiger counter for frame time** (a developer tool). Each slow frame clicks, GC pauses buzz,
   and the frame-time p99 becomes a pitch. Debugging performance by ear (M2).
8. **A random sound-effect generator.** A "make me a pickup / laser / explosion / jump" button in
   the Sound Board, with seeded randomization and export to TOML. Every result is reproducible
   from its seed (M4).
9. **A robot voice for text-to-speech.** Bit reduction and ring modulation on TTS output
   (`src/glitchygames/audio/tts.py` [Fact]) for in-game announcers (M4).
10. **Music from game state.** In Drawing Fire or Paddle Slap, rally length drives the beat's
    intensity layer, so the score follows the game (M5).

---

## 14. Milestones (summary; the implementation spec has the detail)

| Milestone | Delivers | Demo |
| --- | --- | --- |
| **M0 Evidence** | This spec pair and the measurements in Appendix A | — |
| **M1 One-call sound API + CRT** | Pitch types and scales; named waves, `Wave.mix`/`blend`, `Harmonics`, `WavePoint` with `CYCLE`/`LEVEL`; white and LFSR noise; ADSR with curves and presets; pitch curves; up to 4 layered oscillator/noise sources; `notes` and `chord`; v1 TOML for those fields and v0 recipes; `audio.sound(...)` with compile-on-first-request, short names and paths, recorded files; the cache as `None` or `'ram'`; per-frame audio accounting in recordings; the Audio debug panel; buses (volume, mute, solo, pan); voice limits and stealing; lifecycle handles; diagnostics; offline render to WAV; CRT power-on sound | Sound Board |
| **M2 Live, migration and clean-up** | Live instruments with exposed parameters, routes, curves and smoothing; state-variable filter; pink noise; bit and rate reduction; scheduled plays (`at_frame`) and the late rule; loudness budget; device-loss handling; the Audio panel's live-voices section; migration of all five games; removal of the old sound paths (`SoundBank`, `load_sound`, `live_audio.create_voice`, games' own generator code) | Rev It Up |
| **M3 Measurement** | The benchmarks, in order: cache off (`None`), then `'ram'`, then the `'disk'` layer (built here); live-pool and chunk-size measurements; result rows; the *Sound Performance* docs page and its plots (§16.2); the Audio panel's replay comparison | — |
| **M4 Instrument depth** | Wavetables; waves from samples and sprites; WAV samples with loops; FM (2/4-op), ring modulation, hard sync; LFOs, vibrato, glide, pitch bend; profiles; delay and wow/flutter; positional audio; hot reload | Wave Lab, Chip Jukebox |
| **M5 Music and production** | Sequences and the music transport, layers, bar-aligned transitions, streamed music, ducking, reverb, stems, recording soundtracks, the controller bus | Night Shift |
| **M6 Authoring and targets** | Sound editor; browser live-audio support; the native-core decision (D3) if real-time bus effects or sample-accurate transitions are needed | — |

The requirements follow, by area, with IDs, priorities, milestones and acceptance criteria.

---

## 15. Requirements

Priorities: **P0** (the milestone fails without it), **P1** (expected), **P2** (desirable).
Each requirement's implementation section and tests are in the implementation spec's
traceability table (§14 there).

### Measurement (AUD-MEAS)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-MEAS-001 | `--sound-cache {none,ram,disk}` and `AudioEngine(cache=None \| 'ram' \| 'disk')` | P0 | M1 (`none`, `ram`); M3 (`disk`) | Under `none`, a sound played 5 times compiles 5 times; under `ram`, once. Before M3, `disk` is refused (`OPTIONS_REFUSED`, "arrives in M3"). The option is replay-local: one recording replays under each mode |
| AUD-MEAS-002 | Per-frame audio accounting as measurement fields | P0 | M1 | Recorded frames carry `audio_seconds` and `audio_work`; both are in `MEASUREMENT_FRAME_FIELDS`; golden replays still match under every mode |
| AUD-MEAS-003 | Benchmarks run in the owner's order: cache off, then `ram`, then `disk` | P0 | M3 | Each of the three A/B tests (§16.2) has a `none` result before its `ram` and `disk` results are taken; the page shows them in that order |
| AUD-MEAS-004 | The storm explains itself | P0 | M3 | In the storm, the `none − ram` frame-time difference matches the recorded `audio_seconds` within 10% for each *k* |
| AUD-MEAS-005 | Result rows with provenance | P0 | M3 | One JSON row per benchmark, mode and machine under `quality/sound-ledger/`, naming the commit, machine and versions, like the replay ledger's rows |
| AUD-MEAS-006 | The *Sound Performance* docs page and its plots (§16.2) | P0 | M3 | The strict mkdocs build renders every chart from the committed rows; the page states the findings in words |
| AUD-MEAS-007 | Before and after the migration | P1 | M3 | The page links the Replay Performance rows of the commit before the migration and the commit after it for the golden replays of games with sound, so the migration's own effect is visible |
| AUD-MEAS-008 | The audio glitch probe under each mode | P1 | M3 | The probe's exit codes for `none`, `ram` and `disk` are on the page |

### Formal interface (AUD-FUNC)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-FUNC-001 | `audio.sound(source, ...)` returns a playable sound; getting never plays | P0 | M1 | A scene gets 3 sounds and none is heard until `.play()`; no game code touches `pygame.mixer` or numpy |
| AUD-FUNC-002 | The first request compiles; repeated requests with equal identity arguments return the same compiled sound without compiling | P0 | M1 | Compile counter rises by 1 for the first call and 0 for 100 more; the returned objects are the same object |
| AUD-FUNC-003 | Compiles are timed and attributed to setup or a gameplay frame | P0 | M1 | A scripted run that first requests a sound in frame 30 reports one gameplay compile named with frame 30 |
| AUD-FUNC-004 | Short names and paths both resolve per §3.2; duplicates raise | P0 | M1 | Tests for each row of the §3.2 table; a duplicate name raises `SoundAssetError` naming both files |
| AUD-FUNC-005 | Handles support `release`, `stop(fade)` and `cancel` (and `unschedule` in M2) with the §3 semantics; stale handles return `False` | P0 | M1 | A test per row of the lifecycle table, including a handle used after its channel was reused |
| AUD-FUNC-006 | Unavailable audio: `sound()` still compiles, `play()` is a logged-once no-op | P0 | M1 | With the mixer uninitialized, a full workflow run raises nothing and logs one warning |
| AUD-FUNC-007 | Existing `SoundBank`, `SoundRecipe`, synth functions, `LiveVoice` and `load_sound` keep working beside the library | P0 | M1 | Existing tests pass unchanged; a scene using both `SoundBank.play` and `audio.play` hears both (no channel taken from the other) |
| AUD-FUNC-008 | Offline render of any sound (and parameter timeline) to WAV with no device | P0 | M1 | Runs with no mixer initialized; the output matches the compiled buffer bit for bit |
| AUD-FUNC-009 | Streamed music files play through one stream player | P2 | M5 | A 3-minute OGG plays and loops; memory stays under 10 MB above baseline |
| AUD-FUNC-010 | Every existing game migrated with its sounds unchanged | P1 | M2 | Recipe sounds: bit-identical buffers between `SoundRecipe.render` and `audio.sound`. Re-authored sounds (Brave Adventurer): max difference ≤ 1 LSB at 16 bit, or for noise, RMS spectrum within 0.5 dB plus a listening check |
| AUD-FUNC-011 | `notes`, `chord`, `transpose` and `length` per W3 | P0 | M1 | Note onsets at their exact frames; a chord's spectrum holds each pitch; `pitch` with `notes` raises |

### Pitch (AUD-PITCH)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-PITCH-001 | `Note`, `Hz` and `Midi` types; strings are notes, floats are Hz, bare ints are rejected | P0 | M1 | An equivalence table (A4 = 440, C4 = 261.6256, …) holds within 0.01 cents; `sound(..., pitch=60)` raises `ValueError` mentioning `Midi(60)` |
| AUD-PITCH-002 | Interval operations in semitones, cents and ratios | P0 | M1 | `Note('C4').up(semitones=12)` equals `Hz(261.6256 * 2)` within 0.01 cents |
| AUD-PITCH-003 | Scales as numbered steps, wrapping octaves | P1 | M1 | `Scale('C', 'major').step(7) == Note('C5')`; every listed scale is tested |
| AUD-PITCH-004 | Game frequency tables accepted (`PitchTable`) | P1 | M1 | Mr. Muncher's table loads, and lookups equal its floats |
| AUD-PITCH-005 | Configurable tuning reference, part of sound identity | P2 | M1 | `Tuning(a4=432)` shifts every note by the same ratio; a request after the change compiles anew |
| AUD-PITCH-006 | Rendered pitch accuracy | P0 | M1 | The measured fundamental of sine, square, saw and triangle at 55, 440 and 3520 Hz is within ±0.5 cents (FFT with interpolation over 1 s) |
| AUD-PITCH-007 | Out-of-range handling per §4.1 | P0 | M1 | NaN, inf, negatives and > Nyquist raise; 8 Hz to Nyquist is accepted; outside 8 Hz–12 kHz warns once |

### Waves and sources (AUD-WAVE, AUD-SRC)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-WAVE-001 | Built-in named waves, including pulse duties | P0 | M1 | Each renders; pulse duty measured from zero crossings is within 1% |
| AUD-WAVE-002 | `Wave.mix` / `blend` by name, with weights normalized | P0 | M1 | `mix(square=1, triangle=1)` equals the normalized 0.5·square + 0.5·triangle tables within 1e-9 |
| AUD-WAVE-003 | `audio.waves.register(name, wave)`; registered waves usable everywhere a name is | P0 | M1 | A registered wave is used in `mix`, a sound file and an instrument |
| AUD-WAVE-004 | `Wave.from_harmonics(Harmonics(...))` with musical names and drawbar notation | P1 | M1 | The result's spectrum has the declared harmonic levels within 0.1 dB |
| AUD-WAVE-005 | `Wave.from_points` with `CYCLE`/`LEVEL` constants and `linear`/`smooth`/`steps` shapes | P1 | M1 | Points reproduce at their positions; DC removed; peak 1.0 unless `normalize=False` |
| AUD-WAVE-006 | Aliasing control for discontinuous waves | P0 | M1 | At 3520 Hz, the aliased components of square and saw are ≥ 40 dB below the fundamental |
| AUD-WAVE-007 | Wavetables with a continuous, smoothed position | P1 | M4 | A position sweep from 0 to 3 over 1 s has no step larger than the smoothing allows, and no clicks (§16 discontinuity test) |
| AUD-WAVE-008 | `Wave.from_samples` with resolution bits; `Wave.from_sprite` | P2 | M4 | A 32 × 4-bit table round-trips; a sprite's column profile becomes the expected table |
| AUD-SRC-001 | White and LFSR noise with explicit seeds and valid tap sets | P0 | M1 | The same seed gives identical output; the 15-bit LFSR period is 32767; invalid taps are rejected when the file is read |
| AUD-SRC-002 | Pink noise | P1 | M2 | Spectrum slope −3 ± 0.5 dB/octave over 50 Hz–10 kHz |
| AUD-SRC-003 | Samples with root pitch, one-shot and looping, with crossfaded loops | P1 | M4 | The loop boundary discontinuity is below threshold; rate × 2 gives duration ÷ 2 and pitch +12 semitones |
| AUD-SRC-004 | Up to 4 layered sources (oscillators and noise in M1; samples and wavetables in M4) | P0 | M1/M4 | A three-source instrument's sources are each measurable in the output |
| AUD-SRC-005 | Recorded sound files as whole sounds | P0 | M1 | Paddle Slap's WAVs play through `audio.sound('sfx_slap')` |

### Instruments and modulation (AUD-INST)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-INST-001 | ADSR with curves and named presets | P0 | M1 | Measured stage times are within 1 ms (or one step for `steps(n)`) |
| AUD-INST-002 | Retrigger modes | P1 | M2 | Each mode's level continuity is measured at retrigger |
| AUD-INST-003 | LFOs, detune, vibrato, glide, pitch bend | P1 | M4 | Modulation depth and rate are measured within 2% |
| AUD-INST-004 | Bounded routes (≤ 8), no cycles | P0 | M2 | A cyclic route file is rejected with the cycle named |
| AUD-INST-005 | Low-, high- and band-pass filters with stable resonance | P0 | M2 | Sweeps at resonance 0.95 over 20 Hz–20 kHz produce only finite output |
| AUD-INST-006 | FM with 2/4-op named algorithms and bounded feedback; ring modulation; hard sync | P1 | M4 | Spectra of known settings match the analytic sidebands within 1 dB |
| AUD-INST-007 | Effects: drive (M1); bit and rate reduction (M2); delay, wow/flutter (M4); reverb (M5) | P1 | M1–M5 | Each: finite output, a bounded tail, documented latency of 0 |
| AUD-INST-008 | Pitch curves with easing | P1 | M1 | The measured pitch follows the curve within 1% at 10 points |

### Game-driven sound (AUD-GAME)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-GAME-001 | Live sounds from `audio.sound(...)`, started with `.start()`, parameters set by name | P0 | M2 | Vehicle example: `set('rpm', …)` changes the measured pitch per the route |
| AUD-GAME-002 | Smoothing, clamping and curves | P0 | M2 | A step change from 800 to 7000 rpm shows no discontinuity above the threshold; out-of-range values are clamped and counted |
| AUD-GAME-003 | Coalescing of rapid updates | P0 | M2 | 1000 `set` calls in one frame: one value applied, no growth in memory |
| AUD-GAME-004 | Fixed parameter values as part of a compiled sound's identity | P1 | M2 | `sound('thud', parameters={'impact_energy': 0.9})` compiles a distinct sound; equal values hit the cache |
| AUD-GAME-005 | Examples: vehicle, collision, ambience, health heartbeat | P1 | M2 | Each ships in a demo, with a test that drives its parameters headless |
| AUD-GAME-006 | Live latency bounded by chunk + device buffer | P0 | M2 | Measured parameter-to-output latency ≤ chunk + 12 ms in offline simulation |

### Timing and music (AUD-TIME)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-TIME-001 | Documented clock domains and conversions | P0 | M1 | Conversion functions tested at boundaries (frame 0, rounding) |
| AUD-TIME-002 | Frame-scheduled plays with a deterministic late policy | P1 | M2 | Scheduled at frame n fires on frame n; late by 1 plays and late by 3 drops (default), both counted |
| AUD-TIME-003 | Sample-accurate notes inside compiled sounds | P0 | M1 | Each `notes` onset is at its exact computed frame |
| AUD-TIME-004 | Sequences from note strings, pairs and step grids | P1 | M5 | Each notation produces the same events for the same melody |
| AUD-TIME-005 | Music transport with bar-aligned transitions | P1 | M5 | Measured transition error ≤ one frame + one device buffer on the Raspberry Pi 4, the low-end reference hardware |
| AUD-TIME-006 | Pause, scene switch and shutdown behaviour per §7.4 | P0 | M1 | Integration tests for each, including a pause screen held longer than the sound and a replay rebuild |

### Mixing and voices (AUD-MIX)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-MIX-001 | Default buses, custom buses, and volume/mute/solo applied to playing voices | P0 | M1 | Channel volumes reflect bus × sound × master after each change |
| AUD-MIX-002 | Constant-power panning | P0 | M1 | L² + R² is constant within 0.1 dB across pan −1…1 |
| AUD-MIX-003 | Voice limits, reservations, priorities, deterministic voice choice | P0 | M1 | A scripted storm of 200 plays steals the same voices on every run; the UI reservation is never starved |
| AUD-MIX-004 | Stealing with a 10 ms fade | P0 | M1 | A stolen voice fades (no step above threshold); dropped plays are counted. **[Open]** Measured on SDL's disk driver (`tests/audio/test_channel_fades.py`, 2026-11-02): SDL_mixer applies a fade once per mixer chunk (512 frames, 11.6 ms), so the 10 ms steal fade is one plateau or a halt, with a worst step 8 to 10 times a 440 Hz tone's own largest (two recordings of six steals); `play` straight after the fadeout replaces the voice at the next chunk (worst 10.3 times), so the voice table keeps its one-frame wait (impl spec 7.1). Dropped plays are counted. The fallback (a longer steal fade, or engine-rendered fade tails: impl spec risks R4 and R5) awaits the owner's decision |
| AUD-MIX-005 | Loudness budget per bus | P2 | M2 | A storm of 20 explosions: the summed estimated peak is ≤ the budget after protection |
| AUD-MIX-006 | Ducking | P2 | M5 | The music bus is measured at −9 dB within the attack time when dialogue plays |
| AUD-MIX-007 | 2D positional plays | P2 | M4 | Pan and gain follow position per the stated law |
| AUD-MIX-008 | Legacy `Sound.play()` callers keep their own channels | P0 | M1 | 40 library plays and 8 `SoundBank` plays at once: neither cuts the other |

### Retro profiles (AUD-RETRO)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-RETRO-001 | Five profiles as validation and defaults on one engine | P1 | M4 | An instrument violating its profile is rejected, naming the rule; one renderer serves all five |
| AUD-RETRO-002 | Chip pitch quantization | P2 | M4 | The rendered frequency equals `clock / (16(p + 1))` for the chosen period |
| AUD-RETRO-003 | Stepped envelopes and reduced-resolution waves | P1 | M1 (steps) / M4 (waves) | A `steps(n)` envelope has exactly n levels above silence (n + 1 values counting 0); a wave has 2^bits levels |
| AUD-RETRO-004 | Original presets only | P0 | M4 | Review checklist: every preset authored in the repo, no sampled ROM data |

### Assets (AUD-ASSET)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-ASSET-001 | Versioned TOML sound files with the `[glitchygames]` header | P0 | M1 | The pickup example loads in M1; the others load in their milestones |
| AUD-ASSET-002 | Errors with the file, field path and expectation | P0 | M1 | A malformed-file corpus (≥ 20 cases over the M1 fields) each yields the expected message |
| AUD-ASSET-003 | Unknown fields rejected (v1+) and warned (v0); fields from a later milestone rejected with "not yet supported" | P0 | M1 | A typo field `envelpoe` is rejected with the suggestion `envelope`; `routes` in M1 gives "routes arrive in M2" |
| AUD-ASSET-004 | Version migration v0 → v1; newer versions refused | P0 | M1 | Both games' recipe files migrate; `migrate` round-trips; version 99 is refused |
| AUD-ASSET-005 | Relative paths, escape refusal, missing assets at first request | P0 | M1 (samples M4) | A test per rule |
| AUD-ASSET-006 | Engine-owned cache keyed by sound identity | P0 | M1 (disk M3) | The same identity is a cache hit; any identifying change is a miss; the disk cache can be deleted at any time |
| AUD-ASSET-007 | Hot reload recompiles on the next request; playing voices finish | P2 | M4 | An edited file: the next request compiles the new version; a playing voice finishes the old audio |

### Runtime safety and performance (AUD-RT)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-RT-001 | No sound work in gameplay frames except live voices and compiles the game requested there | P0 | M3 | On the §16.2 charts, each migrated game's golden replays under `ram` are no slower per frame than at the commit before the migration; diagnostics list every gameplay compile |
| AUD-RT-002 | Live voice budget | P0 | M3 | 4 live voices (8 if adopted): p99 per-frame live render ≤ 1.0 ms on the Raspberry Pi 4 (the budget is confirmed or reset from its first M3 measurements); zero underruns in a 10-minute run |
| AUD-RT-003 | Compile time reported; disk cache when large | P1 | M3 | Compile time is in diagnostics; a second launch with the disk cache compiles 0 baked sounds |
| AUD-RT-004 | No non-finite output anywhere | P0 | M1 | Fuzzed instrument parameters within valid ranges never yield NaN or inf |
| AUD-RT-005 | Bounded memory | P1 | M1 | In-memory cache size is reported; a limit (default 256 MB) evicts the least recently played sounds that are not playing |

### Diagnostics and portability (AUD-DIAG, AUD-PORT)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-DIAG-001 | `audio.diagnostics()` fields per §11.1 | P0 | M1 | All fields are present and plausible in the Sound Board run |
| AUD-DIAG-002 | The Audio debug panel: header, audio-time graph, channel strip, bus meters and compile log (§11.1.1) | P1 | M1 | Pixel tests on a synthetic history: a gameplay compile draws a red bar in its frame's column; channel cells take the stated colours; a gameplay compile appears red in the log. `--sound-diagnostics` opens on the panel. Nothing of it appears in a screenshot |
| AUD-DIAG-003 | Live voices section | P2 | M2 | A live voice's parameter values and underrun count appear and update |
| AUD-DIAG-004 | Replay comparison in a watched replay | P2 | M3 | Replaying a `ram` recording under `none` draws both runs' audio time per frame |
| AUD-PORT-001 | No new runtime dependencies | P0 | M1 | `uv.lock` adds no package for the sound engine |
| AUD-PORT-002 | Headless and tests need no sound hardware | P0 | M1 | The full suite passes on the dummy driver |
| AUD-PORT-003 | Browser: compiled sounds play | P1 | M1 | A game's browser bundle (Mr. Muncher's) plays the CRT power-on sound after the click; manual check in Chrome and Safari |
| AUD-PORT-004 | Browser live sounds assessed | P2 | M6 | A written result in the wasm compatibility matrix |
| AUD-PORT-005 | Device loss and reconnection per §11.3 | P1 | M2 | Simulated removed/added events raise nothing; play resumes |

### CRT and demos (AUD-CRT, AUD-DEMO)

| ID | Requirement | Pri | MS | Acceptance |
| --- | --- | --- | --- | --- |
| AUD-CRT-001 | Power-on sound per the §12.1 timeline | P0 | M1 | An offline render of the sequence's sound matches the timeline's cues (onsets within 10 ms of their progress points); listening check signed off by the owner |
| AUD-CRT-002 | Power-on sound obeys the power-on rules and its own off switch | P0 | M1 | Not played in headless runs, tests, replays or recordings; `--crt-power-on-sound off` works |
| AUD-CRT-003 | A skip fades in 20 ms | P0 | M1 | A simulated key at 0.4 s ramps the output to silence within 20 ms, with no step above threshold. **[Open]** SDL_mixer steps a channel fade once per mixer chunk (512 frames, about 11.6 ms), so a 20 ms fade is a plateau or two and a halt: the CRT is silent within 20 ms plus one chunk, but a pure tone shows a step about 3.4 times its own largest (modelled). Measured on SDL's disk driver (`tests/audio/test_channel_fades.py`, 2026-11-02), the model holds: one or two plateaus, then a halt, every step on a chunk boundary, the worst step 4.5 to 4.9 times a 1 kHz tone's own (from 1.0 to 4.9 across twelve skips). Pending the owner's listening check; the fallback (engine-rendered fade tails, impl spec 10.1, risk R5) awaits the owner's decision |
| AUD-DEMO-001 | Sound Board demo | P0 | M1 | A demos-layer member with its console script (`uv run sound-board-demo`); plays every built-in wave and noise; its tests drive it headless |
| AUD-DEMO-002 | Rev It Up demo | P1 | M2 | Runs; its engine sound follows RPM |
| AUD-DEMO-003 | Wave Lab and Chip Jukebox | P1 | M4 | Run |
| AUD-DEMO-004 | Night Shift | P2 | M5 | Runs with its adaptive score; has a golden replay like every game |

---

## 16. Verification

### 16.1 Kinds of evidence

| Area | Evidence |
| --- | --- |
| Pitch | FFT-measured fundamentals across the supported range, with a declared tolerance (AUD-PITCH-006) |
| Waveforms | Shape checks (zero crossings, duty, peak), spectra, and the alias floor at high pitch |
| Envelopes | Stage-time measurements from the rendered envelope |
| Timing | Exact onset frames in compiled `notes` sounds; frame-scheduled plays in a scripted run (M2) |
| Click prevention | A discontinuity metric (the largest sample-to-sample step relative to the local signal slope) on every stop, steal, skip and parameter jump, plus a listening checklist |
| Determinism | Bit-identical recompiles on one platform; a tolerance across platforms |
| Integration | Scene switches, pause, replay-rebuild silence, headless runs, device events, and coexistence with existing `SoundBank`/`LiveVoice` users |
| Assets | Every §9.2 example in its milestone; the malformed corpus; migration |
| Listening | A short checklist per milestone, signed off by the owner: the CRT timeline, the Sound Board's waves, no clicks on stop or steal, the vehicle sweep |

Automated numbers alone do not establish sound quality. The listening checklist is part of each
milestone's acceptance.

### 16.2 Does caching make gameplay smoother? Measured, after the migration **[Owner]**

The owner asked for the sound to be "fully benchmarked and measured" with plots in the docs, for
A/B tests that show the cache's effect "in a really clear way", and for the cache to be a
feature flag "so we can test with it on and off to force mid-frame audio rendering". The order is
the owner's: **finish the API and migrate every game onto it, removing the old paths (M1–M2);
then benchmark with the cache off; then `ram`; then `disk` (M3).**

**The "before" numbers already exist.** The replay ledger measures every golden replay and
bundled demo at every commit [Fact: `docs/quality/performance.md`, `quality/replay-ledger/`]. The
commit before the migration is therefore the baseline of today's code, and the commit after it
shows the migration's own effect, with no flag added to code that is about to be removed
(AUD-MEAS-007).

**The switch.** `--sound-cache none | ram | disk` (§9.3). With `none`, every play compiles its
sound in the frame that plays it. Nothing else differs between runs.

**Per-frame audio accounting (M1).** Every compile, file decode and live chunk is timed with the
engine's raw counter [Fact: `clock.raw_counter_ns`, measurement only]. Each recorded frame gets
two *measurement* fields, which like `processing_seconds` are never compared or served [Fact:
`recording_history.MEASUREMENT_FRAME_FIELDS`]:

- `audio_seconds`: the frame's total audio work;
- `audio_work`: what that work was (kind, sound, microseconds).

A frame's slowdown under `none` can then be explained exactly, not just observed.

**Three A/B tests, from clearest to most realistic (M3):**

1. **Each sound's cost.** Every sound the five migrated games use, compiled under
   pytest-benchmark, plus one live-voice chunk. That gives one bar per sound.
2. **The sound storm.** A stand-in scene does a fixed amount of work per frame and plays *k*
   sounds per frame from a scripted schedule (k = 0, 1, 2, 4, 8, plus bursts), for 600 headless
   unpaced frames under each mode. The frames are identical except for the cache, so the
   difference in frame time is the audio work. The chart shows the cost rising with *k* under
   `none` and staying flat under `ram` and `disk`.
3. **The real games.** Every golden replay and bundled demo of a game with sound is rebaselined
   under each mode on the same machine and commit [Fact: `--rebaseline` records per-frame
   `processing_seconds`; `--compare-processing` compares]. The plots overlay the runs frame by
   frame and mark the frames that played a sound.

`disk` adds a fourth measurement: time from launch to the first frame, cold (empty cache) versus
warm. The audio glitch probe [Fact: `scripts/audio_glitch_probe.py`] runs under each mode too.

**The plots** go on a new docs page, *Sound Performance* (`docs/quality/sound_performance.md`),
built like the replay performance page [Fact: `docs/quality/performance.md`, bokeh charts from
committed result rows]:

- what each sound costs to compile (bars, grouped by game, with 1 ms and 16.7 ms reference lines);
- frame time against sounds per frame, per mode (the storm), with frames over budget;
- per-recording frame timelines, `none` against `ram`, with audio work shaded and sound frames
  marked;
- frame-time distributions (ECDF) per mode;
- live-voice chunk cost;
- startup time, cold against warm `disk`;
- before and after the migration (from the replay ledger);
- each benchmark's p99 by commit, so later milestones show up as regressions or gains.

Today's numbers set expectations **[Measured]**. The worst existing recipe takes 9.7 ms, over half
a 60 fps frame if rendered mid-game, and both recipe games prerender at setup today. The `none`
runs will show exactly what that work costs in a frame, and the `ram` and `disk` runs what
caching saves.
