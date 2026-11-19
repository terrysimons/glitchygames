# Zombies Ain't My Neighbors, Feature 11: The Rest of the Sounds, and the Score — Plan

**Status (2026-11-18):** BUILT, uncommitted, awaiting the owner's ears.

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(decisions 3, 11, 12 and 17; the Game TODO "Sound and music", which this finishes for level 1;
Engine wishlist #3, the music sequencer).

**Revised (2026-11-18, the owner's): the score is mixes.** The first build played each cue as
separate sounds, a layer each, and restarted the loop from game frames. The owner asked for each
cue to be built once and played as the built copy, "same as our other caching layer", and chose
Claude's recommendation: the engine's own `Mix` (decision 17's third exception). The decisions
below say which rows the revision replaced.

## The owner's ask (2026-11-18)

Finish level 1. Its sounds were not done ("Ahhh ok yes the sounds are not done for all of that
yet. continue."). On the music: "Go ahead and stage music creation in the game setup and once
we've landed the game we'll refactor things as needed to pull stuff into the core." So the score's
machinery lives in the game's folder for now (decision 16), shaped so it can move into the engine
later. The owner left the music's feel to Claude; every sound below is Claude's call, to tune by
ear.

## What the engine gives music today (measured 2026-11-18)

- A catalog instrument plays a melody: `audio.sound(instruments.get('theremin'), notes='D5:1 ...')`.
  A 16 s melody compiles in about 80 ms here (theremin, timpani). The disk cache keeps it for
  later launches, and the library shares it across the process.
- **A melody can't loop in time.** Its compiled length drops a trailing rest and adds the
  instrument's release tail: `A3:1 C4:1 E4:1 _:1` (4 s of notes) is 3.25 s on the theremin and
  5.0 s on the timpani. Looped layers would drift apart and stumble at every seam.
- **No play starts at an exact sample** (`at_frame` is reserved for M2), and a sound file cannot
  name a catalog instrument (only its own `[instruments.*]`), so `SOUNDS` cannot declare the score:
  "a pitched sound needs a sound file's entry". The score compiles in the game's own frames.

## Decisions (Claude's calls inside the owner's)

| Decision | Value | Why |
|---|---|---|
| The score's machinery (revised) | A **cue** (`music.py`) is layers, each a catalog instrument playing one melody, compiled into **one sound**: an engine `Mix` (`glitchygames/audio/mix.py`), its parts rendered and added at their volumes, cached as every sound is (memory, then the disk layer, else compiled and written). The loop is a looping mix exactly `LOOP_SECONDS` long, its tails folded onto its start, played once with `loop=True` | The owner's ask: build once, play the built copy. One buffer and one channel per cue instead of one per layer (the score's memory 46 MB to 15 MB), and the mixer repeats the loop sample for sample. *First build, replaced:* layers restarted at each boundary of `game_time`, up to a frame late, later after a hitch (the stage's frame cap holds `game_time` back while the audio plays on) |
| How exactly it keeps time (revised) | Sample-exact, within a pass and across the seam: the loop is one sound the mixer repeats | Nothing for the game to schedule |
| Where the score is compiled (revised twice) | Declared in `SOUNDS` with the effects (`music.SCORE`, on `RosterScene`): the engine builds it while the game starts, in the CRT power-on's spare time, and finishes it before the first scene (at once where the power-on is skipped). A later launch reads the built mixes from the disk cache. A scene's `setup()` still asks for its cues, and finds them built | Decision 11: all heavy work before play. The owner asked (2026-11-18) to take the loop's 188 ms build out of a frame of play; `SOUNDS` is the engine's existing place for it. A scene's `setup()` would not do: it runs inside the frame that asked for the switch, and its time lands in the next scene's first `dt`, which the engine keeps so recorded frames add up to elapsed time. On the first launch the build holds back one frame of the power-on. *Replaced:* the feature card building one cue a frame after the sprite kit |
| The stage's loop (`stage`) | D minor, 120 beats a minute, 8 bars of 4/4: 16 s. Theremin lead (eerie, leaning on the A and C# of the A chord), a theatre organ in two voices (whole-bar chords, lifted a beat early so each change is heard), a pizzicato double bass walking in quarter notes, timpani on the bar-1 and bar-5 downbeats and a three-hit pickup into bars 5 and 1. Chords: Dm Dm Bb A, Dm Gm Bb A | A late-night creature feature: the theremin and the roller-rink organ of a 1950s horror-host show (the concept) |
| The stage clear (`stage-clear`) | 1.5 s, the cheer's length: the organ and theremin land on D major (the minor key's "happy ending"), a timpani hit under it. The loop fades out over 0.3 s first | A B-movie "ta-da" |
| The game over (`game-over`) | The switch-off effect (below) with the picture's collapse, then the organ's "dun dun DUNNN" (D, F, then a low C# under a held D minor) as GAME OVER shows | The genre's own sting |
| Where music sits | The `music` bus, priority 80 (effects keep 50), so a storm of zaps never steals a cue | The music bus keeps two channels of its own; the loop now uses one (it used five, ten across a seam) |
| Music while paused | The engine's owner rules pause it with the scene, and `game_time` stops too, so it resumes in time | Nothing to build |
| The title and the card | Silent for now | The intro and the attract demo (decisions 6 and 15) are their own feature; their music comes with them |
| The new effects | In `sounds/sounds.toml`, written by `sound_rig.py` as feature plan 10's are: `tv-spawn` (a picture-tube thump and a burst of static as a zombie climbs out), `tv-hit` (a glassy tick and a blip of static), `tv-break` (a crunch of glass), `tv-destroyed` (the crunch with a low boom and a fizzle), `rescue` (a bright rising three-note chirp), `loss` (a falling wail and a thud), `knockout` (a cartoon bonk: a pitch drop and a knock), `gate` (an iron gate's creak, about 0.5 s: longer than the 0.24 s swing, which is too short to hear as a creak), `switch-off` (a tube's whine falling away and a click, as long as the collapse) | One sound per moment in the Game TODO; each the length of what it marks |
| Where each effect plays | Panned by its place across the screen (`pan_for`), as plan 10's are: a TV's, a neighbor's, a kid's or the gate's middle. The switch-off is centred | Four players can tell where it happened |
| One sound per event | A TV's zap plays only the strongest of `tv-hit`, `tv-break`, `tv-destroyed`; the gate creaks once, as it begins to open; the stage clear and game over play once | No doubled sounds |
| Volumes | Effects 0.3 to 0.5; music layers 0.15 to 0.35, mixed into each cue's sound, which plays at full volume, so the score sits under play | Starting balance, to tune. The loudest cue peaks at 0.79: nothing clips |

## Engine wishlist additions (decision 12; not built)

- **A melody that loops in time:** a loop length that keeps a trailing rest and folds the release
  tail onto the loop's start. **Built on this branch** as the engine's `Mix` (`loop_seconds`), at
  the owner's choice (decision 17).
- **Catalog instruments in sound files** (`instrument = "catalog:theremin"` or similar), so a
  game can declare its score in `SOUNDS` and the engine compiles it while the game starts.
- **Sample-exact starts** (`at_frame`, M2): layers started in step, wherever the frame lands.

## Tasks

1. **The effects** (`sound_rig.py`, `sounds.py`, the sound file, the sound tests). Each compiles,
   lasts its moment, and has the shape it claims, measured from its render: the spawn's thump is
   low (under 120 Hz) under high static; the rescue's pitch rises, the loss's and the switch-off's
   fall; the knockout's bonk drops; the gate's creak stays in its band for its swing's length;
   no click at any join.
2. **Where they play** (`neighborhood.py`, `game_over.py`). Spies on the compiled sounds show each
   plays once, at its moment, panned by its place; a TV zap plays only its strongest sound; a
   kid already down plays no second knockout.
3. **The score** (`music.py`, its tests). Every loop layer's notes add up to exactly
   `LOOP_SECONDS`, and every sting's layers to its own length; every note is in its instrument's
   playing range (`instruments.entry(name).playing_range`); each cue's mix is its layers at their
   volumes, looping only for the loop; the built loop is exactly `LOOP_SECONDS`; no cue clips.
3a. **The engine's `Mix`** (revision; `src/glitchygames/audio/mix.py`, `library.py`,
   `tests/audio/test_sound_mix.py`). A mix is the sum of its parts at their volumes; a looping
   mix is exactly its loop long, with every frame past its end added onto its start; equal mixes
   are built once; anything that changes a mix changes its identity; the disk layer gives it
   back exactly and a later process compiles nothing; cache `none` knows its length without
   compiling and compiles at each play into ram's samples; a copy at another rate is the loop at
   that rate; a mix takes no pitch or notes, refuses a live part, and refuses no parts, an empty
   loop, no name or a volume outside 0 to 1.
4. **Compiled ahead** (`roster_scene.py`, `neighborhood.py`, `game_over.py`). Every cue's mix is
   declared in `SOUNDS`, so the engine builds it while the game starts (an engine test: a declared
   mix is built by `StartupSounds` and a later request builds nothing); a card shown to its end
   compiles no sound; the stage then compiles nothing during play (the engine's gameplay
   compile count stays 0); a stage or game over set up with nothing compiled compiles what it
   needs in `setup()`.
5. **Played** (`neighborhood.py`, `game_over.py`). The loop starts on the stage's first frame,
   looping, on the music bus, and is never started again; the stage clear fades the loop and plays
   its sting; the game over plays the switch-off at once and its sting as GAME OVER shows.
6. **The goldens, the docs, the master plan.** The goldens replayed (re-recorded only if a
   recorded start changes); `PLAYS_SOUNDS` and the audio golden's entries as the guards demand;
   the docs page; the master plan's Game TODO and wishlist.

Each task: tests first (sounds checked by what plays and when, through spies, and by rendering
offline; nobody can listen in a test), then ruff, the type checkers and the game's tests with its
coverage at 100%; before the commit, the engine's replay, guard and audio golden tests.

## Review Focus

- The loop's seam: the folded tails sound right where the next pass begins, the first pass
  included (its start carries the tails of a pass that never played).
- Four players firing at every TV at once: no layer stolen (priority), no effect dropped.
- A replay repeats every start.

## What only listening can judge

How it sounds, and the balance between the score and play. The tests prove the shapes and the
timing; the owner hears whether it is a creature feature.

## Rulings while building (Claude's, 2026-11-18; the owner may overturn them)

| Ruling | Why | If wrong |
|---|---|---|
| Each effect has at most one chain of swoops; its other layers hold one pitch or are noise | Plan 10's chain test treats every swept tone of an effect as one chain | One test's scope |
| The crossfade-dip test now looks only at swoops (its docstring's subject) | It checked every tone fading in after the start, which flagged deliberate gaps: the rescue's separate notes, the loss's thud after its wail. The groans' joins, its reason, are still checked | Gaps in a chirp would need a different check |
| The stage's score state is one object, `music.StageMusic` (its sounds and the loop playing) | `NeighborhoodScene.__init__` passed ruff's 50-statement limit | None |
| The long music test destroys every TV first (`without_zombies`) | Each test's random streams are unseeded, so whether zombies end the stage within 16 s was luck: one test failed 2 runs in 6 before, 0 in 10 after | None |
| A mix's parts are seeded from `<mix name>-part-<index>`, and its identity digests the parts' own keys | The same seed in every process, and every part change (notes, volume, instrument) builds a new mix | Renaming a cue rebuilds it once |
| `SOUNDS`' element type is one alias, `SoundSource` (`audio/library.py`), used by the library, the engine, startup, `Scene`, the cache inventory and two scripts | The union was written out in eight places, and widening it for `Mix` missed two scripts' copies (both type checkers caught them) | None |
| A looping mix's first pass also carries the folded tails | One buffer, the same every pass: the alternative is a separate first pass, a second sound | The loop's first beat has a faint tail of its last bar |

## Found while building

- **Measured cost, first build (development Mac, 2026-11-18):** the 13 layers compiled in about
  270 ms in all, the slowest 81 ms; the score held about 46 MB, 36 MB of it the stage loop.
- **Measured cost, as mixes (same machine and day):** the stage loop builds in 188 ms, the stings
  in 21 and 43 ms; the score holds 15.1 MB (the loop 9.9 MB: float64, int16 and the mixer's stereo
  copy); peaks 0.78, 0.70 and 0.79. Not yet measured on the Raspberry Pi or in the browser;
  wishlist #14.
- **Proved to fail first (the mix):** the mix tests failed at import before `audio/mix.py`; with
  the loop's fold cut short the fold test failed, and with the part volumes ignored the sum test
  failed. The game's revised tests name what the old code lacked (`loop_sound`, `MUSIC_VOLUME`,
  `cue_mix`), so they could not pass on it.
- **Proved to fail first:** the play tests failed on the scene before this feature (6 of 6, and
  every score test in the neighborhood by import); the card's two "compiles nothing" tests pass
  on old code by nature, so each was proved by planting its defect (compiling while the kit
  builds; compiling after the stage began); the range and length checks by a planted D1 on the
  timpani and a short layer.
