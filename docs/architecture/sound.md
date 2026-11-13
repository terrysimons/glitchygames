# Sound

The sound engine's first milestone (M1) gives every game one call for sound:
`scene_manager.audio.sound(...)`. It takes a short name, a path or an `Instrument`, compiles the
sound the first time it is asked for, and hands back the same compiled sound on every later
request. Getting a sound never plays it.

The design is in two specifications:

- [Sound engine feature specification](../specs/2026-11-02-sound-engine-feature-spec.md): what
  the engine does, with the requirement ids (`AUD-*`) used below.
- [Sound engine implementation specification](../specs/2026-11-02-sound-engine-implementation-spec.md):
  how each requirement is met, the decision and risk registers, and the measurements.

M2 adds live instruments (sounds that follow game parameters), moves the five games onto this
API and removes the old sound paths (`SoundBank`, `load_sound`, `live_audio`). Until then those
keep working beside it on channels of their own.

## One call

```python
from glitchygames.audio import Instrument
from glitchygames.scenes import Scene


class Game(Scene):
    def setup(self):
        audio = self.scene_manager.audio
        self.coin = audio.sound('coin')                        # a short name
        self.slap = audio.sound('sounds/sfx_slap.wav')         # a path
        self.zap = audio.sound(Instrument(wave='square'), pitch='C5', length=0.1)
        self.jingle = audio.sound('coin', notes='C5:0.1 E5:0.1 G5:0.2')

    def on_key_down_event(self, event):
        self.coin.play(volume=0.8, pan=-0.5)                  # a SoundHandle
```

- `audio.sound(source, *, pitch=None, notes=None, chord=None, length=None, transpose=0.0,
  parameters=None)` returns a compiled `Sound`. What it is (the source and those arguments) is
  its identity: the same identity is compiled once and cached.
- `Sound.play(*, volume, pan, bus, priority, loop, persist, ...)` plays it and returns a
  `SoundHandle`: `stop(fade=...)`, `cancel()`, `release()` (a loop ends after its pass),
  `set_volume(volume, fade=...)`, `set_pan(pan)` and `is_playing`. Every method answers False
  once the voice has ended, and never touches a later voice on the same channel.
- `audio.play(source, ...)` is `audio.sound(source, ...).play(...)` in one call, and
  `audio.beep(pitch='A4', wave='square', length=0.1)` plays a basic wave.
- Pitches may be note names (`'A4'`, `'C#5'`), hertz (`Hz(440.0)` or a float), MIDI numbers
  (`Midi(69)`) or scale steps (`Scale('C', 'major').step(2)`, step 0 being the root in octave
  4), mixed freely. A4 is 440 Hz.
- Waves are named (`sine`, `square`, `saw`, `triangle`, the pulse widths, ...), and new ones can
  be mixed, blended, drawn as points or built from harmonics (`Wave`, `Harmonics`,
  `WavePoint`, with the `CYCLE` and `LEVEL` named positions). Each engine context has its own
  wave registry.

Compile in `setup()`. That is the convention, not a rule: a sound first asked for during gameplay
compiles in that frame, and the engine counts it, logs it and shows it in the Audio panel as a
gameplay compile, so you can move it into `setup()`. A setup whose compiles take more than 50 ms
logs one INFO line naming its slowest sounds. A loading screen can spread compiles across frames
with `audio.sounds.warm(requests, budget_ms=...)`.

## Short names and paths

A short name (`'coin'`) is looked up in the active scene's `SOUND_DIRECTORY` (a class attribute,
`'sounds'` by default), relative to the scene's package directory. Every sound file there
contributes its sounds by name; two files defining the same name are an error naming both. A
recorded file is a short name too: `sounds/sfx_slap.wav` is `'sfx_slap'`.

A path (`'sounds/pickups.toml#coin'`, `'sounds/sfx_slap.wav'`) is relative to the scene's package
directory and always works, whatever the short-name index holds.

A sound file is TOML (version 1):

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

Version 0 recipe files (`[recipes.*]`) still load and sound exactly as before;
`glitchygames sound-migrate FILE` converts one to version 1.

## Cache modes

`--sound-cache` chooses how compiled sounds are kept (replay-local: a recording replays under any
mode):

| Mode | What happens |
| --- | --- |
| `ram` (default) | Compiled sounds stay in memory. Above `--sound-cache-memory` (256 MB) the least recently played sounds that are not playing are dropped, and compiled again on their next request (counted). |
| `none` | Nothing is kept: every `play()` compiles in its frame. This is the switch that shows what compiling in gameplay costs. Getting a sound renders nothing, and a sound played 5 times compiles 5 times. What a game reads of a sound never depends on the cache (a replay may run under another mode): a synthesized sound's `length` is worked out without rendering, exactly as a compile would size it; whatever only a compile can tell (every `peak`, and a recorded file's `length` and rate) comes from one compile on its first read, counted like any compile, then kept. A play's compile gives them too, so a read after a play compiles nothing more. |
| `disk` | Arrives in M3; refused now (`OPTIONS_REFUSED`). |

## Voices, channels and buses

The mixer's channels are partitioned once at startup: the live voice pool (`--live-voice-pool`,
4), then the sound library's channels (`--sound-channels`, 32), then pygame's 8 for legacy
`Sound.play()` callers. Neither side can take the other's channels.

A play takes the lowest free library channel its bus may use. When none is free it steals a
playing voice of lower or equal priority (releasing voices first, then the lowest priority, the
earliest play): the stolen channel fades with `Channel.fadeout(10)` and the new sound starts on
another free channel, or on the stolen one a frame later (a *delayed play*). A play with nothing
to steal is dropped. Steals, delayed plays and drops are counted.

What a game sees never depends on the audio device: `is_playing` and voice endings follow each
voice's played time, which advances by the frame's served `dt` (the recorded `dt` in a replay),
so a replay sees the same answers. Frames run in silence (a watched replay's step-back rebuild,
an instant replay's fast-forward) only quiet the channels: their voices go on by frame time, so
`is_playing`, voice endings and steals are the same as when those frames were heard.

Buses form a tree under `master`: `music`, `effects`, `ui`, `ambience` and `dialogue` always
exist (`ui` and `music` keep two channels each that a storm of effects cannot take), and
`audio.buses.add(name, parent=...)` adds more. A bus has a `volume`, `mute` and `solo`; changes
reach every playing voice of the bus at the next frame. `audio.stop_all(fade=..., bus=...)` fades
a bus and the buses under it, or everything.

Plays belong to the scene that started them. When a scene is switched away from directly, its
voices fade over 50 ms unless they were played with `persist=True`; behind a pause screen they
pause and resume.

### Fades on the device (measured)

SDL_mixer (2.8.2 with pygame-ce 2.5.8) changes a channel's level only between mixer chunks, 512
frames (11.6 ms) at 44.1 kHz. Measured through SDL's disk audio driver
(`tests/audio/test_channel_fades.py`; the steal's ordering, which depends on when the mixer
thread runs, in `tests/benchmarks/test_channel_fade_relations.py` under `--benchmark-only`):

- `Channel.fadeout(10)` (a steal) is one plateau or an immediate halt, and `Channel.play` straight
  after it replaces the fading sound at the next chunk, so the engine keeps its one-frame wait.
- The wait orders the fade before the stealer only if the mixer thread mixes a chunk during that
  frame. A mixer thread kept off the CPU for longer than a frame mixes the stealer into the fade's
  first chunk, the same cut as playing at once, so the delayed benchmark needs only
  `MINIMUM_DELAYED_STEAL_TRIALS` of its trials to show the wait. Both steal benchmarks report
  every trial, passing or not (the action chunk, both tones' levels in it, and whether the
  stealer is absent from it and sounds after it), to `test-results/channel-fade-steal-delayed.md`
  and `channel-fade-steal-immediate.md`, so a flaky run can be diagnosed afterwards.
- A volume or bus fade stepped once per frame over 50 ms reaches the channel as three gain steps
  of a third, each at a chunk boundary.
- The CRT skip's `Channel.fadeout(20)` is one or two plateaus and then a halt.

None of these is a smooth ramp by the feature spec's discontinuity metric (16.1), so steals,
short fades and the CRT skip can click. Whether they are heard is the owner's listening check;
the fallback, fades rendered into the sound by the engine, is the owner's decision (impl spec
risks R4 and R5).

## Accounting

Every compile, file decode and cache read is timed. Each frame's audio work goes to the
recording doors as `audio_seconds` (the total) and `audio_work` (`(kind, name, microseconds)`
entries, at most 32 a frame, the rest summed as `other`), so a recording holds what audio cost
frame by frame; the times are measurements and never change what is drawn or played.

`audio.diagnostics()` returns the totals: voices playing and the voice limit; compiles and their
milliseconds, split into setup and gameplay; the last 32 gameplay compiles with their frames;
stolen voices, delayed plays and dropped plays; the device format; and the cache's hits, misses,
compiles and bytes held.

## The Audio panel

The debug overlay (`--debug-overlay`, F3; F4 cycles panels) has an Audio panel after
Performance. `--sound-diagnostics` opens the overlay on it. It shows the cache mode, the mixer's
format and the voice counts; an audio-time graph stacked by kind of work (compile red, decode
orange, live blue, cache grey) on the same time axis as the frame-time graph; a strip with one
cell per channel (idle, playing, fading, paused; a stolen channel flashes); the bus meters (a
soloed bus is marked); and the compile log, with gameplay compiles in red. Under the All panel
only its header lines are drawn. The panel is built from `AudioEngine.snapshot()` only while
the overlay is visible, and never appears in screenshots.

## The CRT power-on sound

The CRT power-on sequence (`src/glitchygames/crt_power_on.py`) plays with a sound
(`src/glitchygames/crt_power_on_sound.py`, feature spec 12.1): a power click and a 60 Hz degauss
thump at the switch, the flyback whine from the dot, static as the picture opens, then the bars'
1 kHz tone (or channel 3's hiss). All are `Instrument`s requested through
`audio.engine_sound(...)`, the engine's own sounds' `audio.sound`.

They compile once per process, on the first power-on that plays its sound, and every later
power-on reuses them: a second game run in one process (the Arcade, the test harness's repeated
engines) and every engine context compiles nothing for the CRT. The compiled samples are kept in
the engine's process-wide cache (`glitchygames.audio.library.ENGINE_SOUND_CACHE`), keyed by each
sound's identity key, which holds the mixer's rate and the tuning: a mixer restarted at another
rate compiles them anew. Only the samples are shared, read-only; each context gets its own
`Sound` over them (its own player and pygame sound), and game sounds stay in each context's
library. The cache is exempt from the memory limit's eviction and from `--sound-cache none` (the
CRT is the engine's, not something a game benchmarks): under `none` the CRT's plays compile
nothing. The first compile is counted and attributed like any compile in the context that
triggered it; every reuse is a cache hit. Headless runs, tests that never power on and
`--crt-power-on-sound off` compile nothing.

The cues follow the progress that draws the picture, each starting on the frame nearest its point,
so at a steady 60 frames a second or more every onset is within 10 ms of its point (AUD-CRT-001);
a hitch can delay a cue by a frame.

A key or button skips the sequence and fades every CRT voice over 20 ms (on the device: a plateau
or two and a halt, as measured above). Otherwise the tail loops into the game and fades over
500 ms from frame 0's first audio update. `--crt-power-on-sound off` plays the picture silently;
the sound never plays where the picture does not (`--headless`, tests, replays, recordings).

## The instrument catalog

`glitchygames.audio.instruments` holds 704 ready-made instruments in 23 families. Each is an
ordinary `Instrument`, built from the engine's own parts (waves from overtone series, noise,
layers with their own envelopes and pitches, filters and drive), so it compiles, caches, plays
and renders offline like any other:

```python
from glitchygames.audio import instruments

violin = instruments.get('violin')                       # built once, then kept
tune = audio.sound(violin, notes='G3:0.5 D4:0.5 A4:1')
instruments.entry('alto saxophone').playing_range        # (Note('Db3'), Note('Ab5'))
instruments.names(family=instruments.Family.BRASS)       # every brass instrument
instruments.names(tag=instruments.Tag.MECHANICAL)        # every entry carrying a tag
instruments.names(tag=instruments.Tag.CHIP)              # every sound-chip voice
instruments.get('slapstick')                             # an alias: the same instrument as 'whip'
```

| Family | Entries | Examples |
| --- | --- | --- |
| `flutes` | 33 | piccolo to contrabass flute, wooden flutes, sopranino to subcontrabass recorders, whistles, shakuhachi, ocarinas, and 3 sound-alikes (csakan, subcontrabass recorder, ryuteki) |
| `clarinets` | 10 | E-flat to contrabass clarinet, basset horn, chalumeau, and 1 sound-alike (c clarinet) |
| `saxophones` | 8 | sopranino to contrabass, C melody |
| `double reeds` | 25 | oboe family, bassoon and contrabassoon, heckelphone, sarrusophone, shawms, crumhorns, suona, zurna, duduk, and 2 sound-alikes (contraforte, piccolo heckelphone) |
| `bagpipes` | 9 | Highland, uilleann, smallpipes, gaita, gaida, musette, sackpipa (drones built in) |
| `free reeds` | 13 | accordions (dry, musette, bass), bandoneon, concertina, harmonium, harmonicas, melodicas, sheng (no sound-alikes yet) |
| `brass` | 44 | piccolo trumpet to contrabass tuba, alto to contrabass trombone, mutes, historic and folk horns, and 2 sound-alikes (bass wagner tuba, soprano trombone) |
| `bowed strings` | 29 | violin to double bass, sections, pizzicato, viols, erhu, hurdy-gurdy, and 2 sound-alikes (viola pomposa, bowed psaltery) |
| `plucked strings` | 92 | guitars (nylon, steel, twelve-string, electric clean to distortion), basses, ukuleles, banjos, mandolins, lutes (angelique), sitar, koto, qanun, tar, ruan, chapman stick, and 27 sound-alikes |
| `harps` | 7 | concert, celtic (lever), wire-strung, triple harp, lyre, kora, harp guitar (no sound-alikes yet) |
| `struck strings` | 5 | hammered dulcimer, cimbalom, santur, yangqin, berimbau |
| `keyboards` | 11 | pianos, fortepiano, harpsichords, virginal, clavichord, celesta, toy piano (no sound-alikes yet) |
| `organs` | 19 | pipe organ stops and plenum, positive, combo and theatre organs, calliope, stopped diapason, cornet and organ clarinet, and 7 sound-alikes (bourdon, salicional, voix céleste, oboe, krummhorn, tuba, post horn) |
| `electromechanical` | 11 | electric pianos (tine, reed), Clavinet, Pianet, tonewheel organ registrations and percussion |
| `electronic` | 26 | theremin, ondes Martenot, leads, pads, basses, chiptune pulses, sound-chip voices (NES triangle, AY-3-8910, SID sawtooth, SN76489, PC speaker) and drum-machine voices (TR-808 tom, conga, cowbell, clave, maracas; Syndrum); 10 of the 26 are sound-alikes of other entries |
| `tuned percussion` | 36 | glockenspiel, xylophone, marimba, vibraphone, bells, steel pans, timpani, gamelan, boomwhackers, gangsa, and 11 sound-alikes |
| `plucked idiophones` | 4 | kalimba, mbira, music box, sansula |
| `friction instruments` | 3 | glass harmonica, glass harp, terpodion |
| `drums and percussion` | 237 | kits (kicks, snares, toms, hi-hats, cymbals), hand drums (daf, dhol, kendang, mridangam), gongs, shakers, blocks, and 131 sound-alikes |
| `noise makers` | 5 | whip crack, diaphone, air horn, vehicle horn, party horn |
| `sound effects` | 8 | thunder sheet, rain machine, ocean drum, cannon, crash box, coconut shells, door slam |
| `voices` | 56 | soprano, mezzo, alto, treble, countertenor, tenor, baritone, bass and basso profundo on ah, eh, ee, oh, oo and humming; whistling; and 1 sound-alike (basso buffo, of bass ah) |
| `choirs` | 13 | soprano, alto, tenor and bass sections on ah, oh and oo; children's choir |

- Names and families are lowercase words separated by spaces (`'tenor saxophone'`, `'double
  reeds'`). `get`, `entry`, `names` and `entries` lowercase what they are given, so
  `instruments.get('Tenor Saxophone')` is the same instrument.
- A `Tag` marks a quality that cuts across families (the set is closed): `Tag.MECHANICAL`, on
  the music box, and `Tag.CHIP`, on the voices of sound chips (an integrated circuit made to
  produce a computer's, console's or arcade machine's sound: the four generic `chip ...` entries
  and `nes triangle`, `ay 3 8910`, `pc speaker`, `sid sawtooth`, `sn76489`; nine in all), each
  stays in the family the instrument sounds like.
  `instruments.names(tag=...)` and `entries(tag=...)` list the entries carrying it, and combine
  with `family=`.
- `instruments.ALIASES` (read-only, as `instruments.CATALOG` is) maps another name to its catalog
  name: `slapstick` to `whip`, `contralto` to `alto ah`, `boy soprano` to `treble ah`, `zanza` to
  `mbira`, `cylinder music box` and `disc music box` to `music box`, `wurlitzer electronic piano`
  to `reed electric piano`, `fender rhodes` to `tine electric piano`, `hohner clavinet` to
  `clavinet`, `rain box` to `rain machine`, `horse hooves` to `coconut shells`, `tavil` to `thavil` and `riq` to `daf`, `richter harmonica` to `harmonica`, `pedal harp` to `concert harp` and `lever harp` to `celtic harp` (125 in all, among them
  `kanun` to `qanun`, `ud` to `oud` and `neapolitan mandolin` to `mandolin`). `get` and `entry`
  resolve an alias, while `names` and `entries` list catalog names only.
- A sound-alike is not an alias: it is a verified instrument that sounds like an existing entry
  (`bamboula` and `conga`, `tombak` and `darbuka doum`), so it is an entry of its own, listed by
  `names` and `entries`, whose `CatalogEntry.sounds_like` names the parent whose build it
  shares (`instruments.get('bamboula') == instruments.get('conga')`; the parent may be in
  another family). A pitched sound-alike (the plucked strings' `requinto guitar`, `liuqin`)
  gives its own sourced range, since it may play another span than its parent; it is pitched
  exactly when its parent is, and an unpitched one has none. `sound_changes` (set on one entry so
  far, the organ stop `bourdon`: its footage) holds keyword overrides of the parent's builder,
  for a sound-alike that a source sets apart by one trait; each needs a cited source.
  Assembly refuses a `sounds_like` that names no entry, itself or another sound-alike. The 131
  drum ones are in `drum_sound_alikes.py`, the family's builds in `drums.py`; the 27 plucked
  string ones are in `plucked_sound_alikes.py`, the builds in `plucked_strings.py`; the 11
  tuned percussion ones are in `tuned_sound_alikes.py`, the 10 electronic ones in
  `electronic_sound_alikes.py` and the 2 bowed string ones (`viola pomposa`, `bowed psaltery`) in
  `bowed_sound_alikes.py`, the builds in `bowed_strings.py`; the voices' one (`basso buffo ah`, of
  `bass ah`) is in `voice_sound_alikes.py`, the builds in `voices.py`; the flutes' 3 (`csakan`, `subcontrabass recorder`, `ryuteki`) are
  in `flute_sound_alikes.py`, the builds in `flutes.py`; and the brass's 2 (`bass wagner tuba`, of
  `wagner tuba`, and `soprano trombone`, of `trumpet`) are in `brass_sound_alikes.py`, the builds in
  `brass.py`; and the double reeds' 2 (`contraforte`, of `contrabassoon`, and `piccolo heckelphone`,
  of `heckelphone`) are in `double_reed_sound_alikes.py`, the builds in
  `double_reeds.py`; the clarinets' 1 (`c clarinet`, of `clarinet`) is in `clarinet_sound_alikes.py`, the builds in `clarinets.py`; the organs' 7 (`bourdon`, `salicional`, `voix celeste`, `organ oboe`, `organ
  krummhorn`, `organ tuba`, `posthorn`) are in `organ_sound_alikes.py`, the builds in `organs.py`;
  the bagpipes' table (`bagpipe_sound_alikes.py`) is empty so far, and so are the keyboards'
  (`keyboard_sound_alikes.py`, the builds in `keyboards.py`) and the free reeds'
  (`free_reed_sound_alikes.py`, the builds in `free_reeds.py`; `winds.py` now holds only the
  saxophones) and the harps' (`harp_sound_alikes.py`, the builds in `harps.py`; the struck strings'
  builds are in `struck_strings.py`). `electromechanical.py` holds the
  electromechanical instruments that shared that module. There are 197 sound-alikes in all. A bagpipe's drones are fixed pitches inside its build, so a bagpipe
  sound-alike in another tuning would carry its own drones as `sound_changes` (each at the pitch
  its source gives, equal-tempered like the chanter).
- Each entry has a `title`, a `family` and its playing range, `lowest` and `highest` (sounding
  pitch; folk instruments' are typical of the common keys). Drums and other unpitched entries
  have no range: their tones are fixed, so give any pitch (`pitch='A4'`); it does not change
  the sound.
- They are synthesized approximations. The engine has no recorded samples, vibrato or moving
  filters yet, so sustained tones are steady, and a voice's vowel is truest in the middle of its
  range (its formants are placed for that pitch and move with the note elsewhere).
- The ranges and models were audited against published references (orchestration texts, the
  Vienna Symphonic Library, makers' specifications, Fletcher and Rossing, the Csound formant
  table) on 2026-11-03 and corrected. An organ's range is its keys at 8' pitch (C2-C7; a stop sounds at its
  footage, a 16' an octave lower, a 4' an octave higher). Paired strings double every note, though a twelve-string
  guitar's or a bouzouki's octave pairs are only on its lower courses, and a church bell leaves
  out its weak quint, as an instrument has at most four sources.
- `uv run python -m scripts.make_instrument_demos [DIRECTORY] [--only TEXT]` renders every
  instrument climbing its range (or four hits) to `build/instruments/<family>/<name>.wav`.
- `uv run python scripts/make_pipes.py [DIRECTORY]` renders a Highland bagpipe and uilleann
  pipes (chanter, drones and regulators) and *Sí Bheag, Sí Mhór* to `build/pipes/`;
  `uv run python -m scripts.pipe_tunes scripts/pipe_tunes_abc [DIRECTORY]` plays the 20
  public-domain tunes in `scripts/pipe_tunes_abc/` (ABC notation, sources in its
  `index.json`) on them, to `build/pipes/tunes/`.

## The Sound Board

`uv run sound-board-demo` (`src/demos/sound-board-demo/`) plays every built-in wave and noise:
one row per wave, the eight notes of C major on keys 1-8, Up and Down to pick a row, L to switch
the labels between note names, hertz and scale steps (the same pitches play), and C for a C major
chord. It starts with the Audio panel open; every sound is requested in `setup()`, so playing a
key never compiles anything.

## Offline rendering

`glitchygames.audio.render_to_file(sound, path, ...)` writes a sound to a WAV file with no audio
device; `glitchygames sound-render SOURCE --sound-output PATH` does the same from the command
line. A sound rendered alone is its compiled buffer, bit for bit.
