# Instrument catalog batch 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the electronic family (Hornbostel–Sachs 53: synthesizers, sound chips, the
theremin and ondes Martenot; electromechanical left in batch 2) from the audits' candidates.
Each instrument gets a cited source and either sounds unlike every other entry or is a listed
sound-alike of the one it sounds like. The rest are aliases, wait for an engine feature or a
sourced range, or are dropped with a reason.

**Architecture:** As in batches 3 to 5, a verification sheet (`batch-6.tsv`) decides every
candidate before any code is written. The family's 15 entries live in `keyboards.py` (628
lines, which also holds keyboards, organs and electromechanical), so they move unchanged to a
new `electronic.py`, as batch 4 moved plucked strings out of `strings.py`. Its table becomes
`_ELECTRONIC_BUILDS + ELECTRONIC_SOUND_ALIKES`, with the sound-alikes in a new
`electronic_sound_alikes.py`. This is the first batch whose family has unpitched candidates
(drum-machine voices, noise channels), so the batch-family test table says which new entries
are unpitched. The batch adds `Tag.CHIP`, the second tag. The sheet and the code each come in
two halves: the players' instruments (early electronic instruments, synthesizers, patches),
then the machines (sound chips, drum machines, tape and sample replay, speech, controllers).

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/waves.py`, `audio/instruments/timbres.py`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 3, 4,
7 and 8 above all). Batch 5's plan (`plans/2026-11-11-instrument-catalog-batch-5-implementation.md`)
is this plan's template, and batch 4's (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`)
holds the pitched sound-alike and strict range rules. The candidates come from
`plans/data/instrument-audit/`:
- `merged.tsv` rows whose `family` starts with `electronic` (103, all from the round-2 audit
  `electronic.md`);
- `round-1/merged-missing.tsv` rows whose `family` contains `electronic` (58, of which 45 are not
  in `merged.tsv`: `syndrum`, `clavioline`, `novachord`, `trautonium`, `minimoog`, ...);
- nine rows earlier sheets handed to this family: `solovox`, `vox continental` and `dx7 ep`
  (`batch-2.tsv`, DROP "H-S 53"); `chip dpcm sample`, `chip noise`, `drum machine voices`,
  `rhythmicon` and `wurlitzer side man` (`batch-3.tsv`, DROP "Electronic, H-S 53"); `talk box`
  (`batch-4.tsv`, DROP "electronic").

Together: **152 unique candidate names** (counted for this plan; Task 3 Step 1 recounts). The
audit's "Aliases" section (13 lines) proposes aliases on top. `plans/future-features.md` #70–#75
leave nothing else for this family.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Hyphens, other punctuation and brand capitals go only in the title (`tb 303`,
  title `Roland TB-303`; `ay 3 8910`, title `General Instrument AY-3-8910`).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families).
  Decision 3: "Electronic is split into electromechanical (H-S 51, 52) and electronic (H-S 53)."
  An instrument whose sound starts as a mechanical vibration read electrically (tines, reeds,
  tonewheels, tape, optical discs) is electromechanical, not this batch: DROP, naming it.
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). The owner kept this rule strict (2026-11-09, "Keep it
  strict"). This plan's range ruling for electronic instruments is below ("Decisions"). With no
  sourced range a pitched row is WAIT, `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the
  same instrument) stays an alias." A sound-alike is pitched exactly when its parent is, and a
  pitched one gives its own sourced range (batch 4). A parent may be in another family (the
  registry allows it).
- Decision 4: "Instruments the engine cannot make well yet wait for the feature": none ships as
  an approximation, under its real name or a qualified one. The spec's table names this
  family's waits: "FM synthesis | DX7-style voices, OPL/OPN sound chips (AdLib, Mega Drive)";
  "sample playback | Mellotron, Chamberlin, Optigan, sample-based drum machines"; "moving
  formants, vowel glides, vibrato | … talk box, vocoder"; "more than four sources"; "sub-audio
  fundamentals". The engine also lacks pitch, amplitude and filter LFOs (vibrato, tremolo,
  pulse-width modulation, a chorus's moving delay, a wobble), a cutoff that moves during a note
  (a filter envelope), filter resonance, oscillator hard sync, ring modulation, wavefolding,
  phase distortion, wavetable morphing, a glide between successive notes (portamento), and
  LFSR widths other than 15 and 7 bits. It has: the waves `sine`, `triangle`, `saw`, `square`,
  `pulse_12`, `pulse_25`, `pulse_75` and `Wave('pulse', duty=...)`; drawn waves
  (`Wave.from_points`, shape `steps` for a chip's stepped table), mixes, blends and additive
  waves (`Wave.from_harmonics`); `Noise('white')` and `Noise('lfsr', bits=15 or 7, taps=...,
  rate=...)`; up to four `Source`s, each with its own semitones, detune, fixed pitch, one glide
  per note (`pitch_curve`), envelope and fixed FIR low or high pass; `drive` 0–20; and the
  family's `_synth` shape (wave, attack, decay, sustain, release, low pass, a detuned pair, a
  square an octave below).
- `Instrument(profile=...)` stays `hybrid` (the others "are constrained later, M4"). The
  `chip` profile and `Tag.CHIP` are unrelated: the tag groups entries, the profile constrains
  rendering.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception: they add names, not builds.
- Reuse the family's shape (`_synth`) and the shared shapes (`blown`, `drum`, `struck`). Add a
  builder only for a genuinely new sound, and give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: attribute content you use). Every quote in the sheet is verbatim from
  a page the worker fetched.
- The 15 entries already in the family keep their names, titles, ranges, builds and order (the
  four `chip ...` entries gain `Tag.CHIP`, Task 2; a tag is none of those). New entries come
  after them. An existing entry changes only for a cited bug, reported to the owner.
- Code style: Google docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage,
  no abbreviated variable names. A test warning is a finding: understand it before going on.
- Commits as batches 4 and 5: `SKIP=replay-metrics git commit`, subject `Instrument catalog: …`,
  `Instrument audit: …` or `Docs: …`, and the trailer line
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No `.md` file beyond those Task 7
  names.

## Review Focus

1. **A programmable synthesizer shipped as a guess at "its" sound.** A Prophet-5 or Minimoog
   plays any patch. The audit's notes ("fat brass", "lush pads") are memory. Under the plan's
   ruling a named synthesizer is a SOUND_ALIKE of the existing patch entry its fetched source
   names as its characteristic voice, or WAIT for that voice's feature, or DROP; a new build
   that equals `saw lead` or `synth brass` is the anti-goal. Task 1's family-table test refuses
   a new build equal to another entry's.
2. **A chip's range read wrong.** A datasheet gives hertz at a clock: the wrong machine's clock,
   rounding outward instead of inward, or a top at 111.6 kHz kept as a note all give a range no
   source supports. The form check (Task 3 Step 3) refuses a pitched range outside A0–C8 or
   without a fetched `range_source`, and the code check compares every range with the sheet.
3. **An unpitched voice in a pitched family.** `electronic` is in `HARMONIC_FAMILIES` and its 15
   entries are all pitched. An 808 clap has no note: Task 1 makes the harmonic test skip
   unpitched entries and makes the batch table name the unpitched new entries, so an entry that
   is unpitched by accident (a missing range) fails instead of passing.
4. **A feature-dependent sound shipped as an approximation.** A theremin's vibrato and
   portamento, a TB-303's resonant sweep, a Juno's chorus, PWM pads, an 808 hi-hat's six
   oscillators, a POKEY's 4-, 5- and 9-bit polynomials, the Mega Drive's FM. Rule 4 makes each
   WAIT with the feature named and the source quoted; the existing `theremin` (no vibrato)
   stays, and no new theremin-like becomes its sound-alike (batch 4's sitar ruling).
5. **A candidate an earlier sheet already decided.** Batch 2 kept `mellotron`, `chamberlin`,
   `optigan`, `vako orchestron`, `welte lichttonorgel` and `telharmonium` in electromechanical
   as WAIT and dropped `oramics` and `wurlitzer sideman`. The form check refuses a SHIP,
   SOUND_ALIKE or ALIAS row whose name is taken, and rule 5 gives each decided row a DROP naming
   the sheet and status. Only the nine hand-offs above are decided here.

---

## File Structure

- Create `src/glitchygames/audio/instruments/electronic.py`: the "Electronic" section of
  `keyboards.py` (`_synth`, `_theremin`, `_ondes_martenot`, the 15 entries), unchanged, as
  `_ELECTRONIC_BUILDS`; new builds after the 15; `ELECTRONIC = _ELECTRONIC_BUILDS +
  ELECTRONIC_SOUND_ALIKES`.
- Create `src/glitchygames/audio/instruments/electronic_sound_alikes.py`:
  `ELECTRONIC_SOUND_ALIKES`.
- Modify `keyboards.py` (the section leaves; the docstring drops "and electronic
  instruments"), `registry.py` (imports `ELECTRONIC` from `electronic.py`; its place in
  `FAMILY_TABLES` doesn't change), `catalog.py` (`Tag.CHIP`), `aliases.py` (the batch's ALIAS
  rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 2, 4, 6) and, only if
  `electronic.py` defines module-level shared builds, `tests/test_process_state_guard.py` (list
  each as `CATALOG_BUILD`, as `plucked_strings.py`'s are).
- Create `plans/data/instrument-audit/batch-6.tsv` (Tasks 3 and 5).
- Docs (Task 7): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70, and a new #76), and the design's status line,
  "Depends on" counts and Tags section.

Decisions made in this plan (my calls, for the owner to check in #76):

- **Range ruling for electronic instruments.** A sourced range is one of:
  1. *A keyboard, ribbon or stylus instrument:* the lowest and highest sounding notes in note
     names from the maker's manual or spec sheet, a museum record, or an encyclopedic page
     that states them (batches 2–5 accepted Wikipedia's "61 keys ranging from F1 to F6" for
     the Pianet); or the key count with the lowest key's note. The span is the keys at the
     manual's normal setting (8', octave switch at 0, no transpose), as the catalog's organs
     use their keys at 8' pitch (`keyboards.py`'s docstring); octave switches, transposers and
     pitch bend do not widen it. Keys named without octave numbers need a sourced tuning
     reference (which key sounds A4) or the row waits.
  2. *A sound chip:* a datasheet, or a page quoting one, giving the frequency range or the
     frequency formula with its divider width, at a clock that a source gives for the machine
     the entry is named for (the NES's, not the chip's maximum). The lowest note is the lowest
     equal-tempered note (A4 = 440 Hz) at or above the lowest frequency, the highest the highest
     at or below the top frequency, then clipped to A0–C8, the catalog's span (the piano's;
     below it is the spec's "sub-audio fundamentals", above it nothing in the catalog plays).
     `notes` shows the clock, the formula, the hertz, the notes and any clip.
  3. *A continuous-pitch instrument* (theremin, trautonium, ribbon): only notes a source
     states; "about three octaves" is WAIT `a sourced range`.
  4. *Unpitched voices* (drum-machine voices, a noise channel at a fixed rate): no range.
  A range is never taken from another model's manual (a Micromoog's is not a Minimoog's).
- **A patch is not an instrument.** A sound named for a technique or a genre (`reese bass`,
  `wobble bass`, `hoover lead`, `pwm pad`, `sync lead`, `sample and hold`, `ring modulator`,
  `noise riser`, `laser zap`, `fm bell`, `moog lead`, `moog bass`) has no maker and no range a
  source can give: DROP "a patch, programmed on any synthesizer, not an instrument". The 13
  patch entries already in the family (`saw lead` to `chip triangle`) predate the rule and stay.
- **A programmable synthesizer takes its sourced characteristic voice.** A named synthesizer
  (`minimoog`, `prophet 5`, `jupiter 8`, `sh 101`, `tb 303`) plays any patch. It is a
  SOUND_ALIKE of the existing patch entry whose sound its fetched source names as the
  instrument's characteristic voice (the waves and the low pass, the sub-oscillator), with its
  own keyboard range; WAIT when that voice needs a feature (a resonant sweep, PWM, sync, a
  chorus); DROP "a programmable synthesizer; no fetched source names a voice of its own" when no
  source names one.
- **Controllers and programmable channels have no sound of their own.** A controller,
  sequencer or general sampler (`keytar`, `ewi`, `eigenharp`, `tenori on`, `fairlight cmi`), a
  chip channel that plays whatever a game loads (`amiga paula`, a wavetable channel with no
  sourced standard wave), and a biosignal sonifier: DROP "no sound of its own". An instrument
  whose identifying sound is its own fixed samples (LinnDrum, NES DPCM drums) is WAIT `sample
  playback`, as the spec's table says.
- **Drum-machine voices are electronic.** Batch 3 handed them here (H-S 53), so `electronic
  clap`, `electronic cowbell` and the rest are unpitched entries of this family. The existing
  `electronic kick` and `electronic snare` stay in drums and percussion, unchanged (#76). A drum
  machine as a product (`rhythm king`, `wurlitzer side man`, `drum machine voices`) is a set of
  voices, each its own row: DROP, naming the voice rows. Voices the candidates don't name are
  not added.
- **`Tag.CHIP` is added now.** The spec: "Later tags (`chip` for the sound-chip voices, …) are
  added the same way when a batch needs one." This batch adds named chip voices beside the four
  generic ones, so `names(tag=Tag.CHIP)` is the only way to list them across the generic and
  named entries. A sound chip is an integrated circuit made to produce a computer's, console's
  or arcade machine's sound (Wikipedia's "Sound chip" page, fetched and quoted in Task 2). The
  tag goes on every chip voice, the four existing `chip ...` entries included (a tag is not a
  name, title, range or build). Synthesizers, drum machines and speech chips do not carry it.
- **Existing entries that decision 4 would now hold back stay.** `theremin` has no vibrato or
  portamento, the patches have no resonance. They shipped with M1 and are left alone; a new
  instrument whose identifying sound needs the missing feature waits and does not become their
  sound-alike (batch 4's sitar ruling). Their unsourced ranges (`theremin` C3–C7, the patches,
  `chip square` A1–C8) go in #76.
- **One-offs are dropped** (batch 5's ruling): a single built instrument or a handful of
  prototypes, as its source says (`ans synthesizer`, `variophone`, `subharchord`, `hellertion`):
  DROP "a one-off instrument, not a type a game would ask for".
- **Two halves by kind.** Electrophones have no Hornbostel–Sachs subclasses this plan can rely
  on, so the split is by an explicit list. Half B, the machines, is these 73 candidates; half A,
  the players' instruments, is the other 79:
  `amiga paula`, `atari tia`, `ay 3 8910`, `ay 3 8910 tone and noise`, `chip dpcm sample`,
  `chip noise`, `chip noise short`, `chip pulse 75`, `chip sawtooth`, `chip wave channel`,
  `namco wsg`, `nes dpcm`, `nes triangle`, `pc engine hucs280`, `pc speaker`,
  `pokey distortion`, `scc wavetable`, `sid chip sawtooth`, `sid noise`, `sid voice`,
  `sn76489 voice`, `sound chip beeper`, `yamaha fm family`, `ym2612 fm voice` (sound chips);
  `drum machine voices`, `electronic clap`, `electronic clave`, `electronic closed hi hat`,
  `electronic conga`, `electronic cowbell`, `electronic cymbal`, `electronic maracas`,
  `electronic open hi hat`, `electronic rimshot`, `electronic tom`, `linn lm1`, `rhythm king`,
  `rhythmicon`, `syndrum`, `wurlitzer side man`, `wurlitzer sideman` (drum machines);
  `chamberlin`, `fairlight cmi`, `mellotron`, `optigan`, `oramics`, `synclavier`,
  `vako orchestron`, `welte lichttonorgel` (tape, optical and sample replay); `sonovox`,
  `speak and spell`, `talk box`, `vocoder`, `voder`, `votrax` (speech);
  `alphasphere`, `dermatron`, `eigenharp`, `electrocardiophone`, `electroencephalophone`, `ewi`,
  `guitar synthesizer`, `haken continuum`, `keytar`, `laser harp`, `lightharp`, `optivideotone`,
  `physical modeling synth (vl-1 type)`, `radiodrum`, `reactable`,
  `samchillian tip tip tip cheeepeeeee`, `tenori on`, `triadex muse` (controllers and the rest).
  The executor may dispatch a half in two parts, in the candidate list's order, with one review
  per half.
- **Out of scope:** the audit's "Gaps you could not close" (SPC700, YM2413, VIC-20, Ensoniq,
  Waldorf, Nord Lead, Korg Wavestation and the rest it suspected but did not list). Task 7
  lists them in #70 for a later pass.

---

### Task 1: Electronic in its own module, the batch table names unpitched entries

**Files:**
- Create: `src/glitchygames/audio/instruments/electronic.py`,
  `src/glitchygames/audio/instruments/electronic_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/keyboards.py`, `registry.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `ELECTRONIC: Final[tuple[CatalogEntry, ...]] = _ELECTRONIC_BUILDS +
  ELECTRONIC_SOUND_ALIKES` in `electronic.py`, with `_synth`, `_theremin` and `_ondes_martenot`
  there under their current names; `ELECTRONIC_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]`
  (empty). In the test file: `EXISTING_ELECTRONIC_NAMES` (the 15), `NEW_ELECTRONIC_NAMES:
  list[str]`, `ELECTRONIC_SOUND_ALIKE_PARENTS: dict[str, str]` and `ELECTRONIC_UNPITCHED_NAMES:
  frozenset[str]` (all empty here; Tasks 4 and 6 fill them), and
  `class BatchFamily(NamedTuple)` with fields `existing_names: frozenset[str]`, `new_names:
  list[str]`, `sound_alike_parents: dict[str, str]`, `unpitched_names: frozenset[str] =
  frozenset()`; `BATCH_FAMILIES: dict[Family, BatchFamily]`.

- [ ] **Step 1: Record the family's builds before touching the code.** Run batch 4's Task 1
  Step 1 command with `family='electronic'` and `build/electronic-builds-before.txt`.
  Expected: `recorded 15`.

- [ ] **Step 2: Write the tests over the new table.** Replace the tuples in `BATCH_FAMILIES`
  with `BatchFamily(...)` rows (plucked strings and tuned percussion as now, `unpitched_names`
  left at its default) and add
  `Family.ELECTRONIC: BatchFamily(EXISTING_ELECTRONIC_NAMES, NEW_ELECTRONIC_NAMES,
  ELECTRONIC_SOUND_ALIKE_PARENTS, ELECTRONIC_UNPITCHED_NAMES)`, between the other two in table
  order. Rename `test_the_new_entries_are_pitched_entries_of_their_family` to
  `test_the_new_entries_are_in_their_family_pitched_unless_listed`; its assertions:
```python
row = BATCH_FAMILIES[family]
new_entries = [*row.new_names, *row.sound_alike_parents]
assert row.unpitched_names <= set(new_entries)
for name in new_entries:
    assert instruments.entry(name).family == family, name
    assert instruments.entry(name).pitched == (name not in row.unpitched_names), name
assert set(instruments.names(family=family)) == (
    row.existing_names | set(row.new_names) | set(row.sound_alike_parents)
)
```
  The other two family-table tests read the row's fields by name. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound` the closing list follows the
  catalog's table order: `list(PLUCKED_SOUND_ALIKE_PARENTS) +
  list(ELECTRONIC_SOUND_ALIKE_PARENTS) + list(TUNED_SOUND_ALIKE_PARENTS) + SOUND_ALIKE_NAMES`.
  In `test_harmonic_instruments_sound_their_note`'s parameters add `and entry.pitched`, with
  the comment `# An unpitched entry has no note to repeat at (batch 6's drum-machine voices)`.

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or harmonic" -v`
  Expected: PASS, with IDs `[plucked strings]`, `[electronic]` and `[tuned percussion]`; the
  harmonic test's case count is unchanged (no entry today is unpitched in a harmonic family).

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move
  `keyboards.py`'s "Electronic" section into `electronic.py` unchanged; its module docstring
  says what the family holds (H-S 53, decision 3) and that the sound-alikes are in
  `electronic_sound_alikes.py`. Imports that only the section used leave `keyboards.py`.
  `electronic_sound_alikes.py` gets an empty table and a docstring quoting the owner as
  `tuned_sound_alikes.py`'s does. Point `registry.py` at the new module.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `family='electronic'` and `build/electronic-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
SKIP=replay-metrics git commit -m "Instrument catalog: electronic in its own module, unchanged; the batch table names unpitched entries" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The chip tag

**Files:**
- Modify: `src/glitchygames/audio/instruments/catalog.py` (`Tag`), `electronic.py` (the four
  `chip ...` entries)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `Tag.CHIP = 'chip'`; `CHIP_NAMES: list[str]` in the test file (catalog order),
  which Tasks 4 and 6 extend.

- [ ] **Step 1: Write the failing test**
```python
# Every sound-chip voice, in catalog order (Tag.CHIP; batch 6)
CHIP_NAMES = ['chip square', 'chip pulse 25', 'chip pulse 12', 'chip triangle']


def test_the_chip_tag_marks_exactly_the_sound_chip_voices():
    """names(tag=Tag.CHIP) is every sound-chip voice, each in the electronic family."""
    assert instruments.names(tag=Tag.CHIP) == tuple(CHIP_NAMES)
    assert instruments.names(tag='Chip') == tuple(CHIP_NAMES)
    for name in CHIP_NAMES:
        assert instruments.entry(name).family == Family.ELECTRONIC, name
```

- [ ] **Step 2: Run it.** Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k chip_tag -v`
  Expected: FAIL with `AttributeError: CHIP`.

- [ ] **Step 3: Add the tag.** Fetch https://en.wikipedia.org/wiki/Sound_chip. Add
  `CHIP = 'chip'` to `Tag`, after `MECHANICAL`, with a comment quoting that page's definition
  and its URL. Give the four `chip ...` entries `tags=frozenset({Tag.CHIP})`, nothing else
  changed. Update `catalog.py`'s module docstring (it names `Tag.MECHANICAL`).

- [ ] **Step 4: Run the catalog tests.** Run Task 1 Step 5's commands.
  Expected: `changed: []` (tags are not in the record), then PASS.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `SKIP=replay-metrics git commit -m "Instrument catalog: Tag.CHIP, on the four chiptune voices" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 3: The players' instruments sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. A list page is a source for a name only. The
sound, the title and the range come from the instrument's own page, or from a maker, museum or
datasheet. The audit's "VERIFIED (partly)" rows and its quotes are leads, not sources: fetch them.

**Files:**
- Create: `plans/data/instrument-audit/batch-6.tsv`
- Create (not committed): `build/batch-6-candidates.txt`, `build/batch-6-machines.txt`,
  `build/batch-6-players.txt`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `electronic.md` ("Rejected or corrected
  proposed entries", "Aliases", "Range checks"); `batch-1.tsv` to `batch-5.tsv`.
- Produces: `batch-6.tsv`, with batch 4's header plus a last column `tags`:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an
  ALIAS's target or a SOUND_ALIKE's parent. `family` is `electronic` on every row. A pitched
  SHIP or SOUND_ALIKE row has `lowest`, `highest` and `range_source`; an unpitched one has none
  of the three, and its `notes` begin `Unpitched.` (a sound-alike's: `Sound-alike: Unpitched.`).
  `tags` is `chip` on a sound-chip voice's SHIP or SOUND_ALIKE row, else empty. `hs` is the
  class the source gives (`53` for this family; `51` or `52` for an electromechanical DROP).

- [ ] **Step 1: Write the candidate lists**
```bash
mkdir -p build
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /^electronic/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /electronic/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' solovox 'vox continental' 'dx7 ep' 'chip dpcm sample' 'chip noise' \
    'drum machine voices' rhythmicon 'wurlitzer side man' 'talk box'
} | sort -u > ../../../build/batch-6-candidates.txt
cd ../../..
```
  Then write the plan's 73 half-B names, one per line, sorted, to `build/batch-6-machines.txt`,
  and `comm -23 build/batch-6-candidates.txt build/batch-6-machines.txt >
  build/batch-6-players.txt`. Run `wc -l build/batch-6-*.txt`.
  Expected: 152 candidates, 73 machines, 79 players; `comm -13 build/batch-6-candidates.txt
  build/batch-6-machines.txt` prints nothing.

- [ ] **Step 2: Write one row per player candidate,** in `build/batch-6-players.txt`'s order,
  and one per name in the audit's "Aliases" section whose target is a half-A row.

  Rules (batch 5's, with this family's changes):

  1. **SHIP** only with name, title, range and sound from fetched sources. Quote in `notes` the
     passage that describes the sound or circuit and the passage that gives the range. The
     `builder` cell gives the `_synth`, `blown` or `drum` call (or a new shape's), and says which
     values come from the source (the waves, a sub-oscillator an octave below, the filter
     slope, a fixed pitch drop, the noise kind and LFSR width) and which are sound design.
  2. **SOUND_ALIKE** a verified instrument that rule 7 finds would sound like an existing entry
     or a SHIP row, including a programmable synthesizer under the plan's ruling. `alias_of` is
     its parent. `notes` begin "Sound-alike:", quote the source's description, and say why that
     entry is the nearest. A pitched one has its own sourced range. The parent is a catalog name
     or a SHIP row of this sheet, never another sound-alike.
  3. **ALIAS** another name for the same instrument, cited (`tannerin` for the Electro-Theremin,
     the audit says). The target is a catalog name, a SHIP row or a SOUND_ALIKE row. If the
     target waits, the row is WAIT with `waits_for` `its target, <name>`.
  4. **WAIT** when the identifying sound needs a feature the engine lacks (Global Constraints),
     named in `waits_for` with the source quoted: `FM synthesis`, `sample playback`, `moving
     formants`, `a pitch LFO (vibrato)`, `a pitch LFO (portamento between notes)` and the other
     names listed there, `more than four sources`, `sub-audio fundamentals`; or `a sourced
     range`. The feature must be the sound the source describes, not a feature the instrument
     merely has.
  5. **DROP** a row that does not exist as described, belongs to another family (name it), is a
     patch, a controller, a one-off or has no sound of its own (the plan's decisions), or is
     already decided: in the catalog under that name (name the entry), an alias already (name
     its target), or a row of an earlier sheet (name the sheet and its status). The nine
     hand-offs are decided here, not dropped as decided.
  6. A row the audit marks "(memory)" or "no source fetched" has no sourced sound yet. Fetch
     the instrument's own page. If none can be found, it is DROP "no fetched source describes
     it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i;
     print(i.names(family='electronic'))"` and the builds in `electronic.py`) and every SHIP
     row above it. If no sourced trait (wave, sub-oscillator, filter, noise kind, envelope
     shape) makes it sound different, it is a SOUND_ALIKE under rule 2. A number chosen only to
     be different does not count, and a range is not a sound trait.
  8. **Duplicates in the candidates** (`atari punk` and `atari punk console`, `minimoog` and the
     audit's `moog lead`, `polyphonic analog synth (prophet-5 type)` and `prophet 5`,
     `fm synth electric piano (dx7 type)` and `dx7 ep`): one row decides the instrument; the
     other is ALIAS when a person would type that name, else DROP "the audit's name for
     <row>". A name with parentheses gets a valid `name` (`polyphonic analog synth`) and keeps
     the original in `audit_name`.

- [ ] **Step 3: Check the sheet's form**
```bash
uv run python -I -c "
import csv, re, sys
from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-6.tsv', encoding='utf-8'), delimiter='\t'))
ships = {r['name']: r for r in rows if r['status'] == 'SHIP'}
own = set(ships) | {n for n in instruments.CATALOG if instruments.entry(n).sounds_like is None}
alikes = {r['name'] for r in rows if r['status'] == 'SOUND_ALIKE'}
taken = set(instruments.CATALOG) | set(instruments.ALIASES)
def pitched(r):
    return bool(r['lowest'] or r['highest'] or r['range_source'])
def parent_pitched(name):
    return pitched(ships[name]) if name in ships else instruments.entry(name).pitched
def ranged(r):
    if not pitched(r):
        return 'Unpitched.' in r['notes'][:30]
    try:
        low, high = Note(r['lowest']).midi_number, Note(r['highest']).midi_number
    except Exception:
        return False
    return r['range_source'].startswith('http') and Note('A0').midi_number <= low < high <= Note('C8').midi_number
names = [r['name'] for r in rows]
bad = [r['name'] for r in rows if not pattern.fullmatch(r['name'])
       or r['status'] not in {'SHIP','SOUND_ALIKE','WAIT','ALIAS','DROP'}
       or r['family'] != 'electronic'
       or not r['audit_name'] or not r['hs'][:1].isdigit()
       or r['tags'] not in {'', 'chip'}
       or (r['tags'] and r['status'] not in {'SHIP','SOUND_ALIKE'})
       or (r['status'] in {'SHIP','SOUND_ALIKE'} and (not r['sound_source'].startswith('http') or not ranged(r)))
       or (r['status'] in {'SHIP','SOUND_ALIKE','ALIAS'} and r['name'] in taken)
       or (r['status'] == 'SOUND_ALIKE' and (r['alias_of'] not in own or pitched(r) != parent_pitched(r['alias_of'])))
       or (r['status'] == 'WAIT' and not r['waits_for'])
       or (r['status'] == 'ALIAS' and r['alias_of'] not in own | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {s: sum(r['status']==s for r in rows) for s in ('SHIP','SOUND_ALIKE','WAIT','ALIAS','DROP')})
print('bad:', bad); sys.exit(1 if bad else 0)
"
```
  Expected: the counts, then `bad: []`, exit 0. (Read the sheet with the csv module: batch 5
  found CSV-quoted cells.)

- [ ] **Step 4: Check the half**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-6.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = {r['audit_name'].lower() for r in rows}
players = set(open('build/batch-6-players.txt', encoding='utf-8').read().split('\n')) - {''}
machines = set(open('build/batch-6-machines.txt', encoding='utf-8').read().split('\n')) - {''}
print('missing:', sorted(players - audit_names)); print('from half B:', sorted(machines & audit_names))
"
```
  Expected: `missing: []` and `from half B: []`.

- [ ] **Step 5: Commit**
```bash
git add plans/data/instrument-audit/batch-6.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 6's verification sheet, the players' instruments" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The players' instruments

**Files:**
- Modify: `electronic.py` (new builds after the 15), `electronic_sound_alikes.py`, `aliases.py`
  (each ALIAS row with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-6.tsv` as Task 3 left it (half A only); Task 1's table and lists; Task 2's
  `CHIP_NAMES`.
- Produces: `NEW_ELECTRONIC_NAMES`, `ELECTRONIC_SOUND_ALIKE_PARENTS` and
  `ELECTRONIC_UNPITCHED_NAMES` with this half's rows, which Task 6 extends.

- [ ] **Step 1: Write the failing tests:** fill `NEW_ELECTRONIC_NAMES` with one name per SHIP row,
  in the sheet's order; `ELECTRONIC_SOUND_ALIKE_PARENTS` with one `name: parent` per
  SOUND_ALIKE row; `ELECTRONIC_UNPITCHED_NAMES` with the unpitched ones; append any `chip` row to
  `CHIP_NAMES` in catalog order (builds, then sound-alikes); add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters. A pitched new entry that does not repeat at its
  note's period (an inharmonic or noise build) goes in `NOT_PERIODIC_AT_THE_NOTE` with its
  reason, as `synth bass` does.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or chip_tag" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries.** One per SHIP row, in the sheet's order, after the 15. Above
  each, a comment with its `sound_source` and `range_source` URLs, the quoted traits it is built
  from and the range's derivation, marking the values that are sound design. SOUND_ALIKE rows go
  in `electronic_sound_alikes.py`, each with a source comment and its own range (or none),
  `tags=frozenset({Tag.CHIP})` where the sheet says `chip`. A builder new to the family gets its
  own test of the trait it exists for, as batch 2's `test_the_pianet_settles_from_a_bright_strike`
  does.

- [ ] **Step 4: Run the suite and check the code against the sheet**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` for every new
  entry. A render failure at a range end is a finding about the range or the build: check it
  against the source, never trim the range to pass. Then:
```bash
uv run python -I -c "
import csv
from glitchygames.audio import instruments
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-6.tsv', encoding='utf-8'), delimiter='\t'))
for r in rows:
    if r['status'] in {'SHIP', 'SOUND_ALIKE'}:
        e = instruments.entry(r['name'])
        assert (e.family, e.lowest or '', e.highest or '') == ('electronic', r['lowest'], r['highest']), r['name']
        assert e.sounds_like == (r['alias_of'] if r['status'] == 'SOUND_ALIKE' else None), r['name']
        assert {tag.value for tag in e.tags} == set(r['tags'].split()), r['name']
    elif r['status'] == 'ALIAS':
        assert instruments.ALIASES[r['name']] == r['alias_of'], r['name']
    elif 'already' not in r['notes'].lower():
        assert r['name'] not in instruments.CATALOG and r['name'] not in instruments.ALIASES, r['name']
print('matches', len(rows), 'rows')
"
```
  Expected: `matches N rows`. (A DROP whose note says the name is already in the catalog or an
  alias is the one row allowed to resolve.)

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 6's players' instruments, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 5: The machines sheet (half B)

Research, as in Task 3.

**Files:**
- Modify: `plans/data/instrument-audit/batch-6.tsv` (append the remaining rows)

**Interfaces:**
- Consumes: the sheet from Task 3, its rules 1–8, and `build/batch-6-machines.txt` (if it is
  missing, rerun Task 3 Step 1).
- Produces: the sheet's remaining rows, read by Task 6.

Every half-B candidate gets a row, in `build/batch-6-machines.txt`'s order, plus one per
remaining name in the audit's "Aliases" section. Rules for this half, in addition to Task 3's:

- **Sound chips.** One entry per chip voice a source describes, named for the chip or the
  machine a person knows it by (`sn76489`, `game boy wave` is a name the sheet may choose; the
  audit's name goes in `audit_name`). A chip whose tone channel is a plain square or pulse with
  nothing sourced to set it apart is a SOUND_ALIKE of `chip square` or the matching pulse, with
  its own range under the chip ruling; `tags` `chip`. A chip's noise channel is its own row
  when a source describes it: the engine's LFSR (15 or 7 bits, sourced taps) can make the 2A03's
  and the Game Boy's, not the POKEY's or TIA's 4-, 5- and 9-bit polynomials (WAIT `LFSR widths
  other than 15 and 7`). A noise channel is unpitched unless a source gives its pitched use and
  range. The OPL, OPN and OPM chips WAIT `FM synthesis`; the SID's identifying sound (its
  filter, ring modulation and sync) is WAIT for those features unless a source names a plain
  waveform as the SID's voice.
- **Drum-machine voices** are unpitched unless a source gives a range in notes, and a voice
  that needs more than four oscillators (the 808 hi-hats and cymbal, six squares, if the
  fetched source says so) is WAIT `more than four sources`. Each new drum-machine voice also
  joins the one-shot tests (Task 6 Step 1). Rule 7 compares each voice with the drums'
  `electronic kick` and `electronic snare` too, which the family-table test does not see.
- **Earlier decisions.** `mellotron`, `chamberlin`, `optigan`, `vako orchestron`,
  `welte lichttonorgel` (batch 2 WAIT, electromechanical) and `oramics`, `wurlitzer sideman`
  (batch 2 DROP) are DROP "already decided: batch-2.tsv <status>". `wurlitzer side man` and
  `drum machine voices` (batch 3's hand-offs) are decided here under the drum-machine ruling;
  `rhythmicon`'s pulses are rhythms below audio rate (WAIT `sub-audio fundamentals` if its page
  says so); `talk box` is the spec's moving-formants example.

- [ ] **Step 1: Append the rows.**

- [ ] **Step 2: Check the sheet's form.** Run Task 3 Step 3's command.
  Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 3: Check that no candidate was left out silently**
  Run Task 3 Step 4's command with `players | machines` in place of `players` on the
  `missing:` line, and print `'extra:', sorted(audit_names - players - machines)` instead of
  the half-B line. Expected: `missing: []`; `extra:` lists only the alias-section rows (their
  alias is their `audit_name`).

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-6.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 6's verification sheet, the machines" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The machines

**Files:**
- Modify: `electronic.py`, `electronic_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-6.tsv`'s half-B rows; Task 4's lists.
- Produces: the finished family; `NEW_ELECTRONIC_DRUM_NAMES: list[str]`.

- [ ] **Step 1: Write the failing tests:** append this half's rows to the lists as in Task 4
  Step 1. Add `NEW_ELECTRONIC_DRUM_NAMES` (the drum-machine voices with their own builds, in the
  sheet's order) to the parameters of `test_a_one_shot_strikes_again_on_each_note` and
  `test_a_one_shot_stops_however_long_it_is_held`.

- [ ] **Step 2: Run them and check they fail.** Run Task 4 Step 2's command with `or one_shot`
  added. Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 4 Step 3. Builds new to the family (a chip's
  stepped wave, an LFSR noise channel, a drum-machine voice of square oscillators) each get a
  test of their sourced trait.

- [ ] **Step 4: Run the suite and check the code against the sheet.** Run Task 4 Step 4's
  commands (the second now checks every row). Expected: PASS, then `matches N rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 6's machines, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 7: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py` (the docstring: an electronic
  paragraph with its count, `electronic.py` and `electronic_sound_alikes.py` named, examples;
  `Tag.CHIP` beside `Tag.MECHANICAL`)
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the electronic row's
  count and examples, the `Tag` bullet naming `Tag.CHIP`)
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts, `Tag.CHIP`)
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 6
  done, pointing at this plan and `batch-6.tsv`), the "Depends on" counts, and the Tags
  section's "Later tags (`chip` …)" sentence (`Tag.CHIP` added by batch 6).
- Modify: `plans/future-features.md`. In #70: heading "BATCH 6 DONE"; batch 6 done, with the
  sheet's counts by status and the family's growth; the audit's unclosed gaps as a later pass;
  a "Plan (batch 6)" line; the Status line; and the next batch named: bowed strings, the next
  in the spec's order. Add #76 (the highest item is #75), "Sound Engine: The Owner's Checks on
  Instrument Catalog Batch 6 — TODO", in #75's form, placed after #75. **Listen**
  (`build/instruments/electronic/`): the new builds by group, then the sound-alikes under their
  parents. **Calls to confirm**:
  - every WAIT, by reason;
  - the range ruling (keys at the normal setting; a chip's hertz at its machine's clock,
    rounded inward and clipped to A0–C8), and every derived range;
  - patches dropped, while the 13 existing patch entries stay;
  - programmable synthesizers as sound-alikes of the patch their source names;
  - controllers, samplers and programmable channels dropped as having no sound of their own;
  - drum-machine voices in electronic, while `electronic kick` and `electronic snare` stay in
    drums and percussion;
  - `Tag.CHIP`, its definition, and its addition to the four existing `chip ...` entries;
  - the existing entries decision 4 would hold back (`theremin` without vibrato or portamento)
    and the existing unsourced ranges (`theremin` C3–C7, the patches, `chip square` A1–C8,
    `chip triangle` A0–C7);
  - the engine features this batch named beyond the spec's table (sync, ring modulation,
    resonance, a filter envelope, wavefolding, phase distortion, wavetable morphing,
    portamento, LFSR widths), for the spec's "What the engine cannot make yet";
  - the earlier sheets' rows left as decided (batch 2's tape and optical WAITs stay
    electromechanical) and the nine hand-offs decided here;
  - the one-offs dropped;
  - the two-half split by kind.

  Then **Follow-ups** (the audit's gaps; ranging the range WAITs from manuals and datasheets).
- Fix any doc line the counts make stale; write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(i.names(tag='chip'))"`
  Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
```
  Expected: everything passes with no warnings (a warning is a finding). The
  `build/instruments/electronic` folder is the one to listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 6 of the instrument catalog (electronic), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the PR wait for the owner (CLAUDE.md: never push automatically). The pre-push hooks
take about 40 minutes, and nothing in the working tree may change while they run.
