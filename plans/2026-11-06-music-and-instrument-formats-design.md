# Sequences in sound files, and music and instrument formats — Design

- **Date:** 2026-11-06
- **Status:** DESIGN, direction set by the owner (2026-11-03): ABC import is in scope; "eventually
  support all of these formats, and wire them into our formats in ways that make sense, if they
  do make sense"; and `music = <path>` with loaders that work out the file type, "would keep the
  config super clean". Not yet planned into milestones.
- **Depends on:** the sound engine M1 (`docs/specs/2026-11-02-sound-engine-feature-spec.md`,
  `docs/specs/2026-11-02-sound-engine-implementation-spec.md`, `docs/architecture/sound.md`) and
  M5's `Sequence`, `Track` and tempo map (feature spec 7.2, 7.3 and example W6).
- **Tracked as:** `plans/future-features.md` #64.

## Intent

A sound file today holds instruments and sounds. A sound's `notes = "B5:0.06 E6:0.18"` gives each
note a length in **seconds**, which suits a two-note coin and does not suit a song: there is no
tempo, no beat, no bar. M5 plans beat-based music as Python (`Sequence(tempo=96, meter=(4, 4),
tracks={...})`), but the spec gives it no form in a sound file.

Meanwhile music already exists in many readable and well-known formats: ABC tunes, MIDI files,
MML, Csound scores, tracker modules. Instruments exist as sfxr parameter sets, SFZ files and FM
patches. The engine should read them, but only by translating them into its own two shapes, so
that every sound still goes through one validated, deterministic path:

- **instruments** (the sound side: `[instruments]` tables and the instrument catalog), and
- **sequences** (the note side: a new `[sequences]` table, the file form of M5's `Sequence`).

## Goals

1. A `[sequences]` table in sound files, written in beats and bars, compiling to M5's `Sequence`.
2. `music = <path>` on a sequence: the engine reads another music format into it, finding the
   file's type itself.
3. ABC first. `scripts/pipe_tunes.py` already reads ABC; its reader becomes the first loader and
   its 20 tunes (`scripts/pipe_tunes_abc/`) become sequences.
4. A registry of loaders, so formats are added one at a time, and a game or plugin can add one
   without changing the engine.
5. The same loaders behind a one-off converter command, `glitchygames sound-import`, beside
   `sound-migrate`.
6. Imports are honest: whatever a format holds that the engine cannot carry over is reported.

## Non-goals

- Supporting every format now. The table below orders them; each is its own piece of work.
- Changing M1's `notes` in `[sounds]`. It stays seconds, the simple form for jingles.
- Playing formats that are programs or register logs (SID, NSF, VGM). That is chip emulation, a
  different project.
- Live-coding languages (Strudel, TidalCycles). They are code, not files.
- Importing LilyPond source. It is a language with Scheme inside; its MIDI output comes in through
  the MIDI loader. Exporting sequences to LilyPond, for sheet music, is in scope later.

## Anti-goals

- A string whose meaning depends on a key somewhere else (the same `"B5:0.06"` meaning seconds in
  one place and beats in another).
- An import that drops something without saying so.
- A loader that guesses a file's type and quietly reads it wrongly.
- A second runtime path: every format becomes our sequences and instruments before it plays.

## Design

### Sequences in a sound file

A sound file that has `[sequences]` declares `version = 2`. Version-1 files load unchanged. A
version-1 reader already rejects an unknown top-level table by name (the
`tests/audio/fixtures/malformed/unknown_top_level_table.toml` fixture), so an old engine fails
clearly on a new file.

```toml
[glitchygames]
kind = "sounds"
version = 2

[sequences.calm]
tempo = 96                 # beats per minute
meter = [4, 4]

[sequences.calm.tracks.lead]
instrument = "chip_lead"
notes = "E4 G4 A4 _ | G4 E4 D4 _ | C4 D4 E4 G4 | E4 _ _ _"

[sequences.calm.tracks.bass]
instrument = "chip_bass"
notes = "C2:2 G2:2 | A1:2 E2:2 | F1:2 C2:2 | G1:4"

[sounds.calm_music]        # a game still asks for a sound by name
sequence = "calm"
bus = "music"
loop = true
```

**Why a new table rather than a `tempo` key on a sound:** `notes` in `[sounds]` is always seconds
and `notes` in a track is always beats, so no string changes meaning with a key elsewhere.

**Track grammar** (the spec's note strings, extended):

| Token | Meaning |
|---|---|
| `E4` | one beat (the spec: "one beat per token") |
| `E4:2`, `E4:1/2`, `E4:1/3` | a length in beats, as an exact fraction, so a triplet stays exact |
| `_` | hold the previous note one beat (the spec's meaning) |
| `\|` | a bar line; every bar is checked against the meter, and a short or long bar is a load error naming the bar |
| `[C4 E4 G4]:2` | a chord |
| `E4@0.8` | an optional velocity |
| `.` | a rest of one beat (`.:2` for two), as in the spec's drum step grid (the owner, 2026-11-07) |
| `x` | play the track's instrument or sound at its own pitch (an unpitched drum's tone; a sound as written); see "Any sound in a sequence" |
| `{coin}` | play another sound at this beat inside a melody; see "Any sound in a sequence" |

**Timing** follows the spec: each note's start is an exact beat, a fraction counted from the start
of the piece, converted through the tempo map to seconds and then to a frame, separately for
every note, so rounding never accumulates. Tempo changes happen only at bar lines:

```toml
tempo_changes = [{ bar = 9, tempo = 120 }]
```

### Any sound in a sequence

The owner's rule (2026-11-07): sound effects must fit into a song, and placing them should be
automatic, because every synthesized sound is already built from waveforms. So a track can play
any sound the engine can name, not only an instrument:

- a catalog instrument (`"thunder sheet"`, from the sound effects family, or `"violin"`);
- an `[instruments]` or `[sounds]` entry, found by the same short-name lookup as `audio.sound`
  (`"coin"`, `"sounds/pickups.toml#coin"`);
- a recorded file (`file =` sounds, `.wav`, `.ogg`).

A whole track of one sound, on a step grid:

```toml
[sequences.storm.tracks.weather]
sound = "thunder"                  # instead of instrument =
notes = ". . x . | x . . . | . x . x | x . . ."
```

One sound dropped into a melody, at the beat it falls on:

```toml
[sequences.level_one.tracks.lead]
instrument = "chip_lead"
notes = "E4 G4 {coin} A4 | G4 E4 {jump}:1/2 D4:1/2 _ | C4 D4 E4 G4 | E4 _ _ _"
```

**How a sound is placed.** A sound with notes of its own (a coin's `"B5:0.06 E6:0.18"`, in
seconds) is placed one of two ways, chosen per track with `fit` (or per token, `{coin|tempo}`):

- `fit = "as written"` (the default): the sound plays whole from its beat with its own timing in
  seconds, the way a sample would. A token's length only says when the next token starts. An
  explosion does not stretch when the tempo changes.
- `fit = "tempo"`: the loader converts the sound into ordinary notes on its own instrument and
  inserts them into the track. Its seconds become beats at its written tempo (`tempo = ...` on
  the `[sounds]` entry, default 120 BPM: one second is two beats), so from then on it follows the
  sequence's tempo map, transposes with `transpose`, is checked against the bar lines, and
  exports to MIDI and LilyPond as notes. This is exact, because a synthesized sound is a recipe
  (an instrument and its notes), not audio.

**Pitch.** `x` plays a sound as written. A pitch token on a sound track transposes a synthesized
sound so its first note lands on that pitch (`G5` plays the coin a third lower than written). An
unpitched sound ignores the pitch, as the catalog's drums do.

**What cannot be converted.** A recorded file has no notes: it plays as written only, and
`fit = "tempo"` on one is a load error naming the file. (Pitching recorded audio waits for sample
playback, which the instrument formats below also need.)

**Exports.** Sounds placed as written have no note form; MIDI and LilyPond exports write them as
markers (a MIDI cue point, a LilyPond text mark) and list them in the export report.

### `music = <path>`: another format as a sequence

```toml
[sequences.amazing_grace]
music = "tunes/amazing_grace.abc"

[sequences.amazing_grace.tracks.melody]
instrument = "great highland bagpipe chanter"

[sequences.battle_theme]
music = "tunes/battle.mid"
tempo = 140                     # optional: overrides the file's own tempo

[sequences.battle_theme.tracks.lead]
part = 1                        # a MIDI channel; an ABC voice is "V:1"
instrument = "square lead"      # optional for MIDI: the General MIDI map picks one otherwise
```

- **On the sequence, not on a track.** One file holds a whole piece (ABC voices, MIDI channels).
  Tracks map its parts to instruments; a one-part file needs a track only to choose its
  instrument.
- **The type comes from the extension and is confirmed by the content** where the format has a
  signature (a MIDI file starts with `MThd`; a ProTracker MOD has its tag at byte 1080; an ABC
  tune starts with an `X:` field). A mismatch is a load error. An unknown extension is an error
  listing the formats that can be read.
- **`format = "..."`** names a type the file cannot show for itself: an MML dialect
  (`format = "mml-ppmck"`), or a `.txt` file. Most files never need it.
- **A file's own settings can be overridden** in the table (`tempo`, and later `transpose`).

### `patch = <path>`: another format as an instrument

The same rule for instrument formats (SFZ, sfxr, FM patches), once the first one is built:

```toml
[instruments.laser]
patch = "sounds/laser.sfxr"
```

Not `instrument = <path>`, which could not tell a catalog name from a path. `file = <path>`
stays recorded audio. So: `music` for notes, `patch` for instrument files, `file` for recorded
audio.

### Loaders

Loaders live in a registry, as the waves and the instrument catalog do. Each registers:

- its format name and file extensions;
- a content check (`can_read(head: bytes) -> bool`);
- a loader that returns sequence events (pitch, start beat, length in beats, velocity, part) and
  the file's tempo map and meter, or an instrument description;
- the list of what it could not carry over, for the import report.

`glitchygames sound-import FILE` runs the same loader and writes TOML for hand editing, with the
import report printed and kept as comments in the output.

**Output layout** (the owner, 2026-11-07): one output file per input file. `battle.mid` becomes
`battle.toml`, holding every sequence the source has (all of an ABC file's `X:` tunes, a
module's songs) and each instrument they use, written once. Re-importing replaces exactly that
file, and the report heads it. `--split` writes one file per sequence instead, with the shared
instruments once in `<name>-instruments.toml`, so no instrument is defined in two files (the
short-name lookup refuses a name found in two files). Games find sequences by short name either
way.

### The formats, and where each fits

In order: what needs only sequences first, then what needs engine features M1 lacks.

| Format | Into | Fits? | Needs first |
|---|---|---|---|
| ABC | sequences | Yes, first (in scope) | `[sequences]` |
| MIDI (`.mid`) | sequences, and instrument choice | Yes. General MIDI's 128 programs map onto the catalog, so a file plays on matching instruments; export too | a GM-to-catalog map |
| Csound score (`.sco`) | sequences | Yes: a score is a table of notes | `[sequences]` |
| MML (NES dialects such as PPMCK; BASIC `PLAY`) | sequences and instruments | Yes. Volume and duty macros are envelopes and pulse duty; one or two dialects | per-step envelopes |
| sfxr, bfxr, jsfxr, ZzFX | one sound | Yes, partly at first: wave, envelope and duty now; slide, vibrato, arpeggio and phaser later | pitch slides, LFOs |
| Csound orchestra (`.orc`) | instruments | A subset in (what our sources can make); export of ours in full, since ours are a subset of Csound | — |
| SFZ | instruments | Yes: its generators (`*sine`, `*saw`, `*square`, `*noise`) now, sample regions later | sample playback |
| MOD, S3M, XM, IT | sequences and sampled instruments | Yes, later; the classic game-music formats | samples, per-note effects |
| AdLib `.sbi`, `.ins`, `.bnk` | instruments | Only with an FM source | an FM source |
| LilyPond | — | Export only (sheet music); import through its MIDI output | `[sequences]` |
| SID, NSF, VGM | — | No: programs and register logs, not descriptions | chip emulation |
| Strudel, TidalCycles | — | No: live-coding languages | — |

The descriptions of the formats here are from memory (2026-11-03 discussion). Each loader's work
starts by reading its format's published specification, cited in the loader's source.

### Prior art

- Csound's split of an orchestra (instruments) from a score (notes) is the same split as
  instruments and sequences. The catalog's voice formants already come from the Csound manual.
- MML put both halves in one readable text file; its NES dialects are the closest old-school
  match for chip sounds.
- SFZ is the closest readable instrument format to our `[instruments]` tables.

## Tests

- Each loader: fixtures of real files in its format, with their expected events; malformed files
  with the error each must give (the pattern of `tests/audio/fixtures/malformed/` and its
  `expected.toml`).
- Sequences: bar checks against the meter; frame-exact onsets after long pieces and tempo changes
  (rounding never accumulates); triplets exact.
- Sounds in sequences: a `[sounds]` entry placed as written renders the same samples as playing
  it alone, starting on its beat's frame; placed with `fit = "tempo"` its notes land on the
  expected beats and follow a tempo change; a recorded file with `fit = "tempo"` is refused by
  name; an unpitched sound ignores pitch tokens.
- Detection: an extension whose content does not match is refused; an unknown extension lists
  the readable formats.
- ABC: `scripts/pipe_tunes_abc/` loads through the loader and renders the same notes as
  `scripts/pipe_tunes.py` today.

## Decisions (the owner, 2026-11-07)

1. The file form ships with M5's `Sequence`, not after it.
2. The rest token is `.`.
3. The General MIDI map gives one catalog instrument per program, overridable per track with
   `instrument =`.
4. Sound effects and every other sound can be placed in a sequence, converted to notes
   automatically where the sound is synthesized ("Any sound in a sequence").
5. `sound-import` writes one file per input file, or one per sequence with `--split` ("Loaders").

## Open questions

None at the moment.
