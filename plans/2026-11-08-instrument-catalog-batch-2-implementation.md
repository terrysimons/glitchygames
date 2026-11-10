# Instrument catalog batch 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the last two new families, electromechanical and sound effects, each entry
verified against a cited source. The electric pianos, the Clavinet and the tonewheel organs move
into electromechanical.

**Architecture:** As in batch 1, a verification sheet (`batch-2.tsv`) decides each candidate
before any code is written. Electromechanical entries live in `keyboards.py` beside
`KEYBOARDS`, `ORGANS` and `ELECTRONIC`, because the moved entries' builders (`_tine_piano`,
`_reed_piano`, `_clavinet`, `_tonewheel_with_percussion`) are already there. Sound effects get
a new module, `sound_effects.py`, built from the existing shapes in `timbres.py` (mostly
`drum`).

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md`. Batch 1's plan
(`plans/2026-11-07-instrument-catalog-batch-1-implementation.md`) and sheet (`batch-1.tsv`)
are the model this batch follows. The candidates come from `plans/data/instrument-audit/`:
`merged.tsv` and the `electronic.md`, `keyboards.md` and `organs.md` audits for
electromechanical. Sound effects have no audit: `missing-categories.md` (item 8) only names
the family. So Task 3 builds that candidate list from sources.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents and punctuation go only in the title.
- Electromechanical: "instruments whose sound is made mechanically and picked up or generated
  electrically (H-S 51, 52): Hammond, Rhodes, Wurlitzer, Clavinet, Telharmonium". Electronic
  "keeps purely electronic sound (H-S 53: synthesizers, sound chips, theremin, ondes
  Martenot)" (spec, Families).
- Sound effects: "theatre and Foley devices that are not instruments: thunder sheet, wind
  machine, rain machine, cannon, and the like", "the one family defined by use" (spec,
  Families).
- "Sound effects must be usable in music … each one is playable as a note in a sequence like
  any other instrument … An unpitched effect ignores the pitch it is given, as the drums
  already do." (spec, Sound effects)
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1)
- "Instruments the engine cannot make well yet wait for the feature": none ships as an
  approximation, under its real name or a qualified one (spec, decision 4). The engine lacks
  sympathetic strings or a buzzing bridge, moving formants, vowel glides, vibrato, pitch and
  filter LFOs, FM synthesis, sample playback, more than four sources, and sub-audio
  fundamentals. It has a pitch glide (`PitchCurve`, `Tone.glide_to`) and a held tone
  (`Tone.sustain`).
- Reuse the timbre shapes in `timbres.py`. Add a builder only for a genuinely new sound, and
  give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: attribute content you use).
- Anti-goal: hundreds of entries that all sound like the same three timbres. Two shipped
  entries that would build the same instrument become one entry plus an alias.
- Moved entries keep their names, titles, ranges and builds. Only the family changes, unless
  a fetched source shows a range is wrong.
- Code style: Google docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage,
  no abbreviated variable names.

## Review Focus

1. **A moved entry keeps its sound.** `instruments.get('clavinet')` must build the same
   instrument after the move, and the name must still resolve. Task 2 records each moved
   entry's build identity before the move and compares it after. Instruments compare by their
   whole build, so the check doesn't depend on the platform the way a sample hash would.
2. **The sixteen-foot organ check silently loses its organs.** `SIXTEEN_FOOT_ORGANS` in the
   test file reads only `Family.ORGANS`. After the move it would hold just `pipe organ
   plenum`, and the two-period check in `test_harmonic_instruments_sound_their_note` would stop
   covering the tonewheels. Task 2 makes it read both families, and its existing test pins the
   full set.
3. **A sound effect in a sequence.** A game writes `notes='A4:0.5 A4:0.5'` with a thunder
   sheet: the second note must strike again, not just continue the first one's ring. Task 4
   adds a test over every sound effect.
4. **A long effect clips or runs on.** A rain machine or thunder run held for a long note must
   stay within full scale and stop sounding after its release, like the horns in batch 1.
   Task 4's test covers the held ones.
5. **An alias spelled in another case** (`instruments.get('Hammond Organ')`, if the sheet
   makes it an alias) resolves like a catalog name. The existing alias tests cover every row in
   `ALIASES`, and Task 2 adds the batch's aliases to the parametrized resolve test.

---

## File Structure

- Create `plans/data/instrument-audit/batch-2.tsv`: the verification sheet (Tasks 1 and 3).
- Modify `src/glitchygames/audio/instruments/catalog.py`: `Family.ELECTROMECHANICAL` (after
  `ORGANS`, before `ELECTRONIC`) and `Family.SOUND_EFFECTS` (after `NOISE_MAKERS`). Each is
  added by the task that adds its entries:
  `test_the_catalog_holds_every_family_with_unique_valid_names` requires every family to have
  entries.
- Modify `src/glitchygames/audio/instruments/keyboards.py`: `ELECTROMECHANICAL`, a section
  between Organs and Electronic. The moved entries leave `KEYBOARDS` and `ORGANS`.
- Create `src/glitchygames/audio/instruments/sound_effects.py`: `SOUND_EFFECTS`.
- Modify `src/glitchygames/audio/instruments/registry.py`: both tables in `FAMILY_TABLES`, in
  `Family` order.
- Modify `src/glitchygames/audio/instruments/aliases.py`: the batch's ALIAS rows.
- Modify `tests/audio/test_instrument_catalog.py`: the tests below.
- Docs (Task 5): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70), and the design's status line.

Decisions made in this plan (my calls, for the owner to check):

- **What moves:** `tine electric piano`, `reed electric piano` and `clavinet` from keyboards,
  and the seven `tonewheel organ …` entries from organs. `combo organ` stays in organs: combo
  organs (Vox Continental, Farfisa) are transistor oscillators, H-S 53. `calliope` and the pipe
  organs stay.
- **Electric guitars, basses, violins and lap and pedal steels stay in their string
  families.** H-S 52 would take them too, but a player looks for an electric guitar beside the
  guitar. This is the same kind of player-facing split the spec keeps for keyboards and organs.
  Audit rows for electric string instruments are DROP with the note "string family batch".
- **Sound effects** are devices that imitate a non-musical sound (weather, gunfire, hooves,
  doors, crashes). Entries already in the catalog stay where they are (`whip`, `vibraslap`,
  `cuica`), and so does `whip crack` (noise makers). Orchestral effects not yet in the catalog
  (thunder sheet, wind machine) go in sound effects, as the spec names them.
- **Drums and percussion is batch 3, with its own plan.** It has 147 candidates, and the spec
  gives one batch per family.

---

### Task 1: The electromechanical sheet

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch.

**Files:**
- Create: `plans/data/instrument-audit/batch-2.tsv`

**Interfaces:**
- Consumes: `merged.tsv` rows whose `audit_file` is `electronic.md`, `keyboards.md` or
  `organs.md`; the catalog's `tine electric piano`, `reed electric piano`, `clavinet` and the
  seven `tonewheel organ …` entries.
- Produces: `batch-2.tsv`, with batch 1's header and columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	range_source	sound_source	notes`.
  `status` is one of `SHIP`, `MOVE`, `WAIT`, `ALIAS` or `DROP`. In this task `family` is
  `electromechanical`.

Candidates: every row of the three audits whose instrument makes its sound mechanically and
picks it up or generates it electrically: tines, reeds, strings or tonewheels with pickups,
and tape or optical replay. Seed list from the audits: `telharmonium`, `hohner pianet`,
`wurlitzer electronic piano`, `rhodes piano bass`, `rhodes celeste`, `hohner clavinet`,
`hammond b3`, `chamberlin`, `optigan`, `mellotron`. Add any other such row you find in the
three audits. Purely electronic rows (H-S 53) are not this batch's: leave them out of the sheet.

Rules (batch 1's, applied to every candidate):

1. **SHIP** only with name, title and sound from a fetched source, and, when pitched, the
   lowest and highest notes from a maker's specification, a museum record or a reference page
   that states the compass. Quote the passage in `notes`.
2. **WAIT** when the identifying sound needs a feature the engine lacks, named in `waits_for`.
   Tape and optical replay (Chamberlin, Optigan, Mellotron) need sample playback. A Leslie
   speaker's sound needs a pitch and amplitude LFO. Decide each from its source.
3. **WAIT** a pitched instrument whose range no fetched source gives (`waits_for`:
   `a sourced range`).
4. **ALIAS** another name for the same instrument (same construction and sound). `alias_of` is
   a catalog name or a SHIP or MOVE row. For example, `hohner clavinet` → `clavinet`, if a
   source shows they are one instrument. Cite the source.
5. **DROP** a row that does not exist as described, belongs to another family (electric
   strings: "string family batch"), or would build the same instrument as another SHIP row
   while no game would ask for it by name.
6. **MOVE** the ten catalog entries named in Interfaces. Keep the name, title, range and build,
   unless a fetched source shows the range is wrong. Then give the corrected range and source.
7. Two SHIP rows whose `builder` cells would be the same instrument break the anti-goal.
   Differentiate them from their sources (tine against reed, bell partial, pickup brightness),
   or make one an alias.

- [ ] **Step 1: Build the sheet,** one row per candidate and per move.

- [ ] **Step 2: Check that no candidate was left out silently**

Run:
```bash
cd plans/data/instrument-audit
comm -23 \
  <(awk -F'\t' 'NR>1 && ($1=="electronic.md" || $1=="keyboards.md" || $1=="organs.md") && tolower($0) ~ /electromech|tine|tonewheel|pickup|tape|optical|rhodes|wurlitzer|pianet|clavinet|hammond|telharmon/ {print tolower($2)}' merged.tsv | sort -u) \
  <(awk -F'\t' 'NR>1 {print $1}' batch-2.tsv | sort -u)
```
Expected: no output. A name the sheet spells differently is listed with its audit spelling in
`notes`. A row matched only by a word in passing (a synthesizer whose notes mention "tape")
gets a DROP row saying it is H-S 53.

- [ ] **Step 3: Check the sheet's form**

Run batch 1's Task 3 Step 3 form check with `batch-2.tsv` in place of `batch-1.tsv`. Use
`fullmatch` in place of `match`, so a name with a trailing newline is caught:

```bash
uv run python -I -c "
import csv, re, sys
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-2.tsv'), delimiter='\t'))
bad = [r['name'] for r in rows if not pattern.fullmatch(r['name'])
       or r['status'] not in {'SHIP','MOVE','WAIT','ALIAS','DROP'}
       or r['family'] not in {'electromechanical','sound effects'}
       or (r['status'] in {'SHIP','MOVE'} and not r['sound_source'].startswith('http'))
       or (r['status'] in {'SHIP','MOVE'} and bool(r['lowest']) != bool(r['highest']))
       or (r['status'] == 'SHIP' and r['lowest'] and not r['range_source'].startswith('http'))
       or (r['status'] == 'WAIT' and not r['waits_for'])
       or (r['status'] == 'ALIAS' and not r['alias_of'])]
print(len(rows), 'rows;', {s: sum(r['status']==s for r in rows) for s in ('SHIP','MOVE','WAIT','ALIAS','DROP')})
print('bad:', bad); sys.exit(1 if bad else 0)
"
```
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add plans/data/instrument-audit/batch-2.tsv
git commit -m "Instrument audit: batch 2's verification sheet, electromechanical rows"
```

---

### Task 2: Electromechanical

**Files:**
- Modify: `catalog.py` (`Family.ELECTROMECHANICAL = 'electromechanical'`, after `ORGANS`)
- Modify: `keyboards.py` (an `ELECTROMECHANICAL` section between Organs and Electronic; the
  ten moved entries leave `KEYBOARDS` and `ORGANS`, and their builders move unchanged)
- Modify: `registry.py` (`ELECTROMECHANICAL` in `FAMILY_TABLES`, after `ORGANS`)
- Modify: `aliases.py` (this family's ALIAS rows, each with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-2.tsv` rows with `family` `electromechanical`; `drawbar_organ`, `plucked`,
  `struck` and the other shapes in `timbres.py`.
- Produces: `ELECTROMECHANICAL: Final[tuple[CatalogEntry, ...]]` in `keyboards.py`, exported to
  `registry.py`.

- [ ] **Step 1: Record the moved entries' builds before touching the code**

Run:
```bash
mkdir -p build
uv run python -I -c "
from glitchygames.audio import instruments
moved = ['tine electric piano','reed electric piano','clavinet','tonewheel organ jazz','tonewheel organ full','tonewheel organ ballad','tonewheel organ rock','tonewheel organ gospel','tonewheel organ percussion second','tonewheel organ percussion third']
with open('build/moved-builds-before.txt', 'w', encoding='utf-8') as before:
    for name in moved:
        before.write(f'{name}\t{instruments.get(name)._identity()!r}\n')
print('recorded', len(moved))
"
```
Expected: `recorded 10`. (`_identity` is private. A one-off check may read it, but a test
may not.)

- [ ] **Step 2: Write the failing test**

```python
MOVED_TO_ELECTROMECHANICAL = (
    'tine electric piano',
    'reed electric piano',
    'clavinet',
    'tonewheel organ jazz',
    'tonewheel organ full',
    'tonewheel organ ballad',
    'tonewheel organ rock',
    'tonewheel organ gospel',
    'tonewheel organ percussion second',
    'tonewheel organ percussion third',
)


def test_electromechanical_holds_the_electric_pianos_clavinet_and_tonewheels():
    """The ten moved entries are electromechanical now, under the same names."""
    electromechanical = set(instruments.names(family=Family.ELECTROMECHANICAL))
    assert set(MOVED_TO_ELECTROMECHANICAL) <= electromechanical
    assert not set(MOVED_TO_ELECTROMECHANICAL) & set(instruments.names(family=Family.KEYBOARDS))
    assert not set(MOVED_TO_ELECTROMECHANICAL) & set(instruments.names(family=Family.ORGANS))
    assert 'combo organ' in instruments.names(family=Family.ORGANS)
```

Change `SIXTEEN_FOOT_ORGANS` to read `instruments.entries(family=Family.ORGANS) +
instruments.entries(family=Family.ELECTROMECHANICAL)`. Leave
`test_the_sixteen_foot_organs_are_the_drawbar_settings_that_draw_it` unchanged: it must still
name all eight organs. If the sheet has ALIAS rows, add them to
`test_the_plucked_idiophone_aliases_resolve`'s parameters, renamed
`test_the_batch_aliases_resolve`.

- [ ] **Step 3: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "electromechanical or sixteen" -v`
Expected: the family test fails with `AttributeError: ELECTROMECHANICAL`. The sixteen-foot test
passes, because nothing has moved yet.

- [ ] **Step 4: Write the family**

Start the section with a comment that defines the family (H-S 51 and 52: a mechanical vibration
picked up electrically, or a tone generated electromechanically) and cites the H-S
electrophone list (https://en.wikipedia.org/wiki/Electrophone). Move the ten entries and their
builders unchanged. Then add one entry per SHIP row, in the sheet's order, each preceded by a
comment with its `range_source` and `sound_source` URLs. Use the moved builders where the
sheet's `builder` cell names them (a Rhodes piano bass is `_tine_piano` over a lower range;
its own ratios or ring come from the sheet).

- [ ] **Step 5: Run the suite and check the code against the sheet**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
Expected: PASS, including `test_the_sixteen_foot_organs_are_the_drawbar_settings_that_draw_it`
(all eight organs) and `test_every_instrument_renders_across_its_range` for every new entry.

Then check that the moved builds are unchanged:
```bash
uv run python -I -c "
from glitchygames.audio import instruments
changed = [line.split('\t')[0] for line in open('build/moved-builds-before.txt', encoding='utf-8')
           if repr(instruments.get(line.split('\t')[0])._identity()) != line.rstrip('\n').split('\t')[1]]
print('changed:', changed)
"
```
Expected: `changed: []`.

Then run batch 1's Task 4 Step 5 check over `batch-2.tsv` with `'electromechanical'`:
```bash
uv run python -I -c "
import csv
from glitchygames.audio import instruments
rows = [r for r in csv.DictReader(open('plans/data/instrument-audit/batch-2.tsv'), delimiter='\t')
        if r['family'] == 'electromechanical']
for r in rows:
    if r['status'] in {'SHIP','MOVE'}:
        e = instruments.entry(r['name'])
        assert (e.family, e.lowest or '', e.highest or '') == ('electromechanical', r['lowest'], r['highest']), r['name']
    elif r['status'] == 'ALIAS':
        assert instruments.ALIASES[r['name']] == r['alias_of'], r['name']
    else:
        assert r['name'] not in instruments.CATALOG and r['name'] not in instruments.ALIASES, r['name']
print('matches', len(rows), 'rows')
"
```
Expected: `matches N rows`.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: electromechanical, with the electric pianos, Clavinet and tonewheel organs moved in"
```

---

### Task 3: The sound effects rows

Research, as in Task 1. There is no audit to start from, so this task builds the candidate list
too.

**Files:**
- Modify: `plans/data/instrument-audit/batch-2.tsv` (append rows with `family` `sound effects`)

**Interfaces:**
- Consumes: the sheet from Task 1 and its rules 1–5 and 7.
- Produces: the sheet's sound effects rows, read by Task 4.

Candidates:
- The spec's four: thunder sheet, wind machine (aeoliphone), rain machine, cannon.
- Every theatre or Foley device that a fetched page names and describes. Start from
  https://en.wikipedia.org/wiki/Thunder_sheet, https://en.wikipedia.org/wiki/Wind_machine,
  https://en.wikipedia.org/wiki/Foley_(filmmaking) and
  https://en.wikipedia.org/wiki/Sound_effect. Follow their links (thunder run, crash box,
  coconut shells for hooves, and so on). Record the page each candidate came from.

Rules for this family, in addition to Task 1's:

- A device belongs here when it imitates a non-musical sound. One already in the catalog
  (`whip`, `vibraslap`, `cuica`, `whip crack`) gets a DROP row naming its family, not a move.
  A whistle imitating a bird is edge-blown, so it is flutes. DROP it with that note.
- Most effects are unpitched. Their noise bands, ring times and glides are sound design, so
  say so in `notes`, unless a source gives a frequency. Then cite it.
- A device whose sound depends on a speed that changes while it plays (a wind machine's pitch
  follows the crank) needs a moving filter or a pitch LFO. WAIT it for that feature, unless a
  single `Tone` glide over one note is a faithful sound, quoted from its source.
- A cannon's or explosion's identifying low end may be sub-audio. If the source puts it below
  20 Hz, WAIT it for `sub-audio fundamentals`.
- Two effects that would build the same `drum` call are one entry and an alias, unless the
  sources give them different sounds (rule 7).

- [ ] **Step 1: Append the rows,** one per candidate.

- [ ] **Step 2: Check the sheet's form**

Run Task 1 Step 3's command.
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 3: Check the four named effects have rows**

Run: `awk -F'\t' '$3=="sound effects" {print $1}' plans/data/instrument-audit/batch-2.tsv | grep -c -x -E 'thunder sheet|wind machine|rain machine|cannon'`
Expected: `4`.

- [ ] **Step 4: Commit**

```bash
git add plans/data/instrument-audit/batch-2.tsv
git commit -m "Instrument audit: batch 2's verification sheet, sound effects rows"
```

---

### Task 4: Sound effects

**Files:**
- Modify: `catalog.py` (`Family.SOUND_EFFECTS = 'sound effects'`, after `NOISE_MAKERS`)
- Create: `src/glitchygames/audio/instruments/sound_effects.py`
- Modify: `registry.py` (`SOUND_EFFECTS` after `NOISE_MAKERS`)
- Modify: `aliases.py` (this family's ALIAS rows)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-2.tsv` rows with `family` `sound effects`; `drum`, `Tone` (with `sustain`,
  `glide_to`, `glide_seconds`), `noise_layer` and `blown` from `timbres.py`.
- Produces: `SOUND_EFFECTS: Final[tuple[CatalogEntry, ...]]` in `sound_effects.py`.

- [ ] **Step 1: Write the failing tests**

```python
# Compared as a string, so the list is simply empty (no cases) before the family exists
SOUND_EFFECTS = [entry.name for entry in instruments.entries() if entry.family == 'sound effects']


def test_sound_effects_hold_the_thunder_sheet():
    """The thunder sheet is a sound effect, and plays as a note at any pitch."""
    assert instruments.entry('thunder sheet').family == Family.SOUND_EFFECTS
    assert not instruments.entry('thunder sheet').pitched


@pytest.mark.parametrize('name', SOUND_EFFECTS)
def test_a_sound_effect_strikes_again_on_each_note(name):
    """Two notes in a sequence are two hits, not one hit ringing on (usable in music)."""
    instrument = instruments.get(name)
    pitch = instruments.entry(name).middle_note().name
    twice = render_sound(spec_for(instrument, name=name, notes=f'{pitch}:0.5 {pitch}:0.5')).samples
    once = render_sound(spec_for(instrument, name=name, notes=f'{pitch}:1')).samples
    half = round(0.5 * SAMPLE_RATE)
    window = slice(half, half + round(0.05 * SAMPLE_RATE))
    assert np.max(np.abs(twice)) <= 1.0, name
    assert not np.allclose(twice[window], once[window]), name
```

If the sheet does not ship `thunder sheet` (it waits or drops), use the first SHIP row's
name in the first test, and say why in its docstring.

A held effect (one with `Tone.sustain` above 0) also goes into the `HORNS` parametrization's
pattern. Add a `HELD_SOUND_EFFECTS` list from the sheet, and parametrize
`test_a_horn_sounds_for_as_long_as_it_is_held` over `HORNS + HELD_SOUND_EFFECTS`, renamed
`test_a_held_entry_sounds_for_as_long_as_it_is_held`.

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "sound_effect" -v`
Expected: FAIL with `KeyError: no instrument named 'thunder sheet'`.

- [ ] **Step 3: Write the family**

The docstring states the family is defined by use (theatre and Foley devices that imitate a
non-musical sound; spec, Families). It says every effect plays as a note, and an unpitched one
ignores the pitch. It cites the Foley page. Add one entry per SHIP row, in the sheet's order,
each preceded by its source comment. ALIAS rows go in `aliases.py`. Most entries are `drum`
calls: a noise band with a ring for a one-shot (a thunder sheet's crash), and `Tone.sustain`
for a sound that lasts while held (a rain machine turning). The existing
`test_unpitched_entries_sound_the_same_at_any_pitch` covers every unpitched effect
automatically.

- [ ] **Step 4: Run the suite and check the code against the sheet**

Run Task 2 Step 5's two commands, with `'sound effects'` in place of `'electromechanical'` (in
both places in the second).
Expected: PASS, then `matches N rows`.

- [ ] **Step 5: Lint and commit**

Run Task 2 Step 6's lint commands, then:
```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: sound effects (the thunder sheet and its kin), each playable as a note"
```

---

### Task 5: Docs, counts and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py` (the docstring: the two new
  families, with examples from the shipped entries)
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the count, the family table
  rows for electromechanical and sound effects, and keyboards' and organs' new counts and
  examples)
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts)
- Modify: `plans/future-features.md` (#70: batch 2 done, with the sheet's counts by status,
  and batch 3 named: drums and percussion)
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md` (the status line: batch 2
  done, pointing at this plan and `batch-2.tsv`)

- [ ] **Step 1: Get the counts from the code**

Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES), i.names(tag='mechanical'))"`
Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the five files.** Write no counts from memory.

- [ ] **Step 3: Run the full checks**

Run:
```bash
uv run pytest --dummy-only tests/audio
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
```
Expected: everything passes. The demos write a WAV per instrument to
`build/instruments/<family>/<name>.wav`. The `electromechanical` and `sound effects` folders
are the ones to listen to. The owner judges the sound.

- [ ] **Step 4: Commit**

```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
git commit -m "Docs: batch 2 of the instrument catalog (electromechanical and sound effects) and its counts"
```

Pushing and the PR wait for the owner (CLAUDE.md: never push automatically). The pre-push
hooks take about 40 minutes, and nothing in the working tree may change while they run.
