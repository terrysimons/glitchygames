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
| `none` | Nothing is kept: every `play()` compiles in its frame. This is the switch that shows what compiling in gameplay costs. |
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
so a replay sees the same answers.

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
1 kHz tone (or channel 3's hiss). All are `Instrument`s requested through `audio.sound(...)`. The
cues follow the progress that draws the picture, each starting on the frame nearest its point,
so at a steady 60 frames a second or more every onset is within 10 ms of its point (AUD-CRT-001);
a hitch can delay a cue by a frame.

A key or button skips the sequence and fades every CRT voice over 20 ms (on the device: a plateau
or two and a halt, as measured above). Otherwise the tail loops into the game and fades over
500 ms from frame 0's first audio update. `--crt-power-on-sound off` plays the picture silently;
the sound never plays where the picture does not (`--headless`, tests, replays, recordings).

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
