# Instrument catalog batch 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the drums and percussion family from the audits' 209 candidates. Each entry is
verified against a cited source and sounds unlike every other entry. The rest are aliases, wait
for an engine feature, or are dropped with a reason.

**Architecture:** As in batches 1 and 2, a verification sheet (`batch-3.tsv`) decides every
candidate before any code is written. The family's table moves unchanged from `percussion.py`
(1,036 lines, which also holds tuned percussion) to a new `drums.py`, where the new entries go.
They are built with `drum` and the family's existing helpers. The sheet and the code each come
in two halves: drums with a membrane (Hornbostel–Sachs class 2), then everything else (rattles,
scrapers, clappers, blocks, slit drums, cymbals, gongs, bells: class 1).

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md`. Batch 2's plan
(`plans/2026-11-08-instrument-catalog-batch-2-implementation.md`) and its sheet (`batch-2.tsv`)
are the model this batch follows. The candidates come from `plans/data/instrument-audit/`:
- `merged.tsv` rows whose `family` is `drums and percussion` (147, all from the round-2 audit
  `drums-and-percussion.md`);
- `round-1/merged-missing.tsv` rows whose `family` contains `drums` (56; round 2's audit judged
  them in its "Rejected or corrected proposed entries" section);
- six rows that batch 2 sent here: `sandpaper blocks`, `rain stick`, `washboard`, `lion roar`,
  `thunder drum` and `anvil`.

That is 209 unique names. The audit's "Aliases" section (27 lines) proposes aliases on top.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents and punctuation go only in the title (`cata`, title `Catá`; `lions
  roar`, title `Lion's roar`).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)"; "friction drums
  (cuíca, lion's roar) stay in drums and percussion" (spec, Families and boundary calls).
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1)
- "Prune: merge aliases into the alias table; drop entries that are the same sound under another
  name, unless a game would ask for them by name (then an alias)." (spec, Batches 2). For
  this batch the owner rules that any instrument a person might search for counts as asked
  for by name (2026-11-08), so a verified instrument that sounds like an entry is an alias of
  it, never dropped for that reason.
- "Instruments the engine cannot make well yet wait for the feature": none ships as an
  approximation, under its real name or a qualified one (spec, decision 4). The engine lacks
  sympathetic strings or a buzzing bridge, moving formants, vowel glides, vibrato, pitch and
  filter LFOs, amplitude LFOs, FM synthesis, sample playback, more than four sources, and
  sub-audio fundamentals. It has a pitch glide (`Tone.glide_to`, `glide_seconds`), a held tone
  (`Tone.sustain`) and `drum`'s `attack`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals)
- Reuse the timbre shapes in `timbres.py` and the family's helpers. Add a builder only for a
  genuinely new sound, and give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: attribute content you use).
- The 61 entries already in the family keep their names, titles, builds and order. New entries
  come after them.
- Code style: Google docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage,
  no abbreviated variable names.

## Review Focus

1. **Two drums that are one sound.** The family already has 61 entries, and the audit's
   modelling notes for most candidates are "noise click plus short sine; easy". Shipping them
   as written is the anti-goal: a sound-alike is an alias instead (rule 3). Task 2 adds a test that no two entries in the family build an
   equal instrument. The sheet's rule 7 and the reviewers catch builds that are near-equal.
2. **The table move changes a sound.** Moving `DRUMS_AND_PERCUSSION` to `drums.py` must leave
   all 61 builds and their order as they were. Task 2 records each build's identity before the
   move and compares it afterwards.
3. **A drum in a pattern.** `notes='C4:0.5 C4:0.5'` on a new drum must strike twice, not ring
   one hit on. Task 2 extends the sound effects' strike-again and one-shot tests to every new
   entry. A gong whose ring is longer than the note may fail. That is examined, not loosened
   (Task 4).
4. **An alias of something that is not there.** An ALIAS row whose target waits or is dropped
   would fail at import (`aliases_from`). The form check refuses an `alias_of` that is neither
   a catalog name nor a SHIP row in the sheet. An alias whose target waits waits with it.
5. **An alias spelled in another case or another spelling** (`instruments.get('Naqareh')`)
   resolves like a catalog name. The existing alias tests cover every row of `ALIASES`, and
   each task adds its aliases to `test_the_batch_aliases_resolve`.

---

## File Structure

- Create `plans/data/instrument-audit/batch-3.tsv`: the verification sheet (Tasks 1 and 3).
- Create `src/glitchygames/audio/instruments/drums.py`: `DRUMS_AND_PERCUSSION`, moved from
  `percussion.py` with the private helpers that follow the tuned table and that only it uses
  (`_tom`, `_hand_drum`, `_metal`, `_cymbal`, `_shaker`), then the new entries.
- Modify `src/glitchygames/audio/instruments/percussion.py`: the table and its helpers leave;
  the module docstring then covers tuned percussion only. A helper that both tables use stays
  in `percussion.py` and `drums.py` imports it.
- Modify `src/glitchygames/audio/instruments/registry.py`: import `DRUMS_AND_PERCUSSION` from
  `drums.py`. Its place in `FAMILY_TABLES` doesn't change.
- Modify `src/glitchygames/audio/instruments/aliases.py`: the batch's ALIAS rows.
- Modify `tests/audio/test_instrument_catalog.py`: the tests below.
- Docs (Task 5): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70, and a new owner's-checks item like #71), and
  the design's status line.

Decisions made in this plan (my calls, for the owner to check):

- **Two halves by Hornbostel–Sachs class:** membranophones (2: drums, friction drums) in Tasks
  1–2, everything else in Tasks 3–4. Each sheet half is about 100 rows. The executor may
  dispatch a half in two parts by the candidate list's order, with one review per half.
- **The sheet gains two columns,** `hs` (the Hornbostel–Sachs number from the fetched source,
  e.g. `211.212.1`, or the class alone, `2`, when the source gives only that) and `audit_name`
  (the candidate's spelling in its audit). `hs` says which half a row belongs to. `audit_name`
  lets the completeness check match a renamed row (`pellet drum (bolang gu / tao)` →
  `pellet drum`).
- **A distinct drum that would sound the same is an alias of the entry it sounds like** (the
  owner, 2026-11-08: "cultural knowledge could change the instrument name they search for -
  humans won't all necessarily know which instruments are identical or know all of their
  names"). If no source gives a trait that would build a dhak differently from the orchestral
  bass drum, `dhak` is an ALIAS of `orchestral bass drum`, and `notes` say it is a sound-alike,
  not the same instrument. If a later source gives such a trait, the alias becomes its own
  entry. A name that no fetched source shows exists is still dropped.
- **No drum is pitched in this family.** A drum whose source gives a definite pitch and a
  compass is DROP "tuned percussion batch" (timpani are already there). A drum tuned to the
  singer's tonic with no fixed compass (mridangam, tabla dayan) ships unpitched at a fixed tone,
  as the catalog's `tabla bayan` does. Its `notes` say the tone is sound design.
- **Strokes are entries when a source names them,** as the catalog already has `djembe bass`,
  `djembe tone` and `djembe slap`. The plain name is the main stroke, and other strokes are
  `<drum> <stroke>`. There are at most three per drum, each a stroke a fetched source names and
  describes.
- **Out of scope:** the audit's "Gaps you could not close" (powwow drum, bomba barrels, to'ere
  and others). Task 5 lists them in #70 for a later pass. The 11 `merged.tsv` rows that the
  audit itself put in `tuned percussion` wait for that batch, and the sheet leaves them out.

---

### Task 1: The membranophones sheet

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. A list page ("List of drums") is a source for a
name only. The sound and the title come from the instrument's own page, or from a museum or
maker record.

**Files:**
- Create: `plans/data/instrument-audit/batch-3.tsv`
- Create (not committed): `build/batch-3-candidates.txt`

**Interfaces:**
- Consumes: the three candidate sources named in the plan's Spec line; the audit
  `drums-and-percussion.md` (its "Rejected or corrected proposed entries" and "Aliases"
  sections); `batch-2.tsv`'s six rows that name this batch.
- Produces: `batch-3.tsv` with the header
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes`.
  `status` is one of `SHIP`, `WAIT`, `ALIAS` or `DROP`. `family` is `drums and percussion` on
  every row. `lowest` and `highest` are always empty. In this task, every row's `hs` starts with
  `2`.

- [ ] **Step 1: Write the candidate list**

Run:
```bash
mkdir -p build
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4=="drums and percussion" {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && $5 ~ /drums/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' 'sandpaper blocks' 'rain stick' 'washboard' 'lion roar' 'thunder drum' 'anvil'
} | sort -u > ../../../build/batch-3-candidates.txt
wc -l < ../../../build/batch-3-candidates.txt
```
Expected: `209`.

- [ ] **Step 2: Build the sheet's membranophone rows,** one row per candidate whose fetched
source shows a membrane (a drum head, including friction drums), in the candidate list's
order. Also add one row per name in the audit's "Aliases" section whose target is a
membranophone.

Rules (batch 2's, with this batch's changes):

1. **SHIP** only with name, title and sound from a fetched source. Quote the passage that
   describes the sound or construction in `notes`. The `builder` cell gives the `drum` call
   (tones with hertz, glide and ring; noise level, ring and filter; tail; attack). It says
   which values come from the source (a head's diameter, "deep", "sharp crack", a named
   stroke) and which are sound design.
2. **WAIT** when the identifying sound needs a feature the engine lacks, named in
   `waits_for`. A talking drum's pitch follows the player's squeeze through a phrase: a
   moving pitch the sequence would control, which one glide per hit is not. Quote the source.
   A drum whose source gives a buzzing snare, rattle or jingle that the noise layer can carry
   doesn't wait.
3. **ALIAS** another name for the same instrument (same construction and sound), cited
   (`gran cassa` → `orchestral bass drum`, if a source shows they are one instrument). Also
   ALIAS a verified instrument that rule 7 finds would sound like an existing entry or SHIP
   row: `alias_of` is the entry it sounds most like, and `notes` begin "Sound-alike:", quote
   the source's description, and say why that entry is the nearest. `alias_of` is a catalog
   name or a SHIP row of this sheet. If the target waits, the alias row is WAIT with
   `waits_for` `its target, <name>`.
4. **DROP** a row that does not exist as described, or belongs to another family (pitched with
   a compass: "tuned percussion batch"; drum machines and chip voices: "electronic, H-S 53";
   an instrument already shipped elsewhere, such as `thunder sheet` or `ocean drum` in sound
   effects or `wind machine`, which waits in `batch-2.tsv`: name where it is).
5. A row the audit marks "(listed; memory)" or "(memory)" has no sourced sound yet. Fetch the
   instrument's own page. If none can be found, it is DROP "no fetched source describes it".
6. Strokes: as in the plan's decisions. The plain name is the main stroke, with at most two
   more `<drum> <stroke>` rows, each a stroke the source names and describes.
7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every catalog entry
   in the family (`uv run python -I -c "from glitchygames.audio import instruments as i;
   print(i.names(family='drums and percussion'))"`, and the builds in `percussion.py`) and every
   SHIP row above it. If no sourced trait (size, head, shell, how it is struck, a named stroke)
   makes it sound different, it is a sound-alike ALIAS under rule 3. A different number chosen
   only to be different does not count.

- [ ] **Step 3: Check the sheet's form**

Run:
```bash
uv run python -I -c "
import csv, re, sys
from glitchygames.audio import instruments
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-3.tsv'), delimiter='\t'))
shipped = {r['name'] for r in rows if r['status'] == 'SHIP'} | set(instruments.CATALOG)
names = [r['name'] for r in rows]
bad = [r['name'] for r in rows if not pattern.fullmatch(r['name'])
       or r['status'] not in {'SHIP','WAIT','ALIAS','DROP'}
       or r['family'] != 'drums and percussion'
       or r['lowest'] or r['highest']
       or not r['audit_name'] or not r['hs'][:1].isdigit()
       or (r['status'] == 'SHIP' and not r['sound_source'].startswith('http'))
       or (r['status'] == 'SHIP' and r['name'] in instruments.CATALOG)
       or (r['status'] == 'WAIT' and not r['waits_for'])
       or (r['status'] == 'ALIAS' and r['alias_of'] not in shipped)]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {s: sum(r['status']==s for r in rows) for s in ('SHIP','WAIT','ALIAS','DROP')})
print('bad:', bad); sys.exit(1 if bad else 0)
"
```
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 4: Check that every row is a membranophone's**

Run: `awk -F'\t' 'NR>1 && substr($10,1,1) != "2" {print $1}' plans/data/instrument-audit/batch-3.tsv`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add plans/data/instrument-audit/batch-3.tsv
git commit -m "Instrument audit: batch 3's verification sheet, membranophone rows"
```

---

### Task 2: Drums (membranophones)

**Files:**
- Create: `src/glitchygames/audio/instruments/drums.py`
- Modify: `percussion.py` (the table and its helpers leave), `registry.py` (the import),
  `aliases.py` (this half's ALIAS rows, each with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-3.tsv` rows with `hs` starting `2`; `drum`, `Tone` and the family's
  helpers.
- Produces: `DRUMS_AND_PERCUSSION: Final[tuple[CatalogEntry, ...]]` in `drums.py`;
  `NEW_DRUM_NAMES` in the test file, which Task 4 extends.

- [ ] **Step 1: Record the family's builds before touching the code**

Run:
```bash
uv run python -I -c "
from glitchygames.audio import instruments
with open('build/drum-builds-before.txt', 'w', encoding='utf-8') as before:
    for name in instruments.names(family='drums and percussion'):
        before.write(f'{name}\t{instruments.get(name)._identity()!r}\n')
print('recorded', len(instruments.names(family='drums and percussion')))
"
```
Expected: `recorded 61`. (`_identity` is private. A one-off check may read it, but a test
may not.)

- [ ] **Step 2: Move the table**

Move `DRUMS_AND_PERCUSSION` and the private helpers only it uses into `drums.py`, unchanged.
Read every comment on the moved code first. The module docstring describes the family (H-S 1
and 2, unpitched; fixed tones ignore the pitch given) and keeps the sources that the moved
comments cite. Point `registry.py` at it, and trim `percussion.py`'s docstring to tuned
percussion. Then run:
```bash
uv run python -I -c "
from glitchygames.audio import instruments
lines = open('build/drum-builds-before.txt', encoding='utf-8').read().splitlines()
before = [line.split('\t') for line in lines]
assert [name for name, _ in before] == list(instruments.names(family='drums and percussion')), 'order'
changed = [name for name, identity in before if repr(instruments.get(name)._identity()) != identity]
print('changed:', changed)
"
uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -q
```
Expected: `changed: []`, then PASS. Commit:
```bash
git add src/glitchygames/audio/instruments
git commit -m "Instrument catalog: drums and percussion in their own module, unchanged"
```

- [ ] **Step 3: Write the failing tests**

```python
# Batch 3's new entries, in the sheet's order (Task 4 appends the idiophones)
NEW_DRUM_NAMES = [
    # one name per SHIP row of batch-3.tsv whose hs starts with 2
]


def test_no_two_drums_build_the_same_instrument():
    """Every entry in the family is its own sound (the anti-goal: no renamed copies)."""
    names = instruments.names(family=Family.DRUMS_AND_PERCUSSION)
    same = [
        (first, second)
        for index, first in enumerate(names)
        for second in names[index + 1 :]
        if instruments.get(first) == instruments.get(second)
    ]
    assert same == []


def test_the_new_drums_are_in_their_family():
    """Each new drum is a drums and percussion entry, unpitched."""
    for name in NEW_DRUM_NAMES:
        assert instruments.entry(name).family == Family.DRUMS_AND_PERCUSSION, name
        assert not instruments.entry(name).pitched, name
```

Parametrize `test_a_sound_effect_strikes_again_on_each_note` and
`test_a_sound_effect_is_a_one_shot_however_long_it_is_held` over `SOUND_EFFECT_NAMES +
NEW_DRUM_NAMES`, renamed `test_a_one_shot_strikes_again_on_each_note` and
`test_a_one_shot_stops_however_long_it_is_held`. Add this half's ALIAS rows to
`test_the_batch_aliases_resolve`'s parameters.

- [ ] **Step 4: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "drum or one_shot or batch_aliases" -v`
Expected: `test_no_two_drums_build_the_same_instrument` passes (the existing 61 differ). The
new-name and alias cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 5: Write the entries**

Add one entry per SHIP row, in the sheet's order, after the existing 61. Precede each with a
comment holding its `sound_source` URL and the quoted trait it is built from, and mark the
values that are sound design. Use the existing helpers where the `builder` cell names them.
ALIAS rows go in `aliases.py` with their source comments.

- [ ] **Step 6: Run the suite and check the code against the sheet**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
Expected: PASS, including `test_every_instrument_renders_across_its_range` and
`test_unpitched_entries_sound_the_same_at_any_pitch` for every new entry.

If a new entry fails the strike-again or one-shot test, measure why first. A gong-like ring
longer than the half-second note is a finding for the sheet (should it ship as a one-shot?),
not a reason to lower `SECOND_STRIKE_FACTOR`.

Then run:
```bash
uv run python -I -c "
import csv
from glitchygames.audio import instruments
rows = [r for r in csv.DictReader(open('plans/data/instrument-audit/batch-3.tsv'), delimiter='\t')
        if r['hs'].startswith('2')]
for r in rows:
    if r['status'] == 'SHIP':
        e = instruments.entry(r['name'])
        assert (e.family, e.lowest, e.highest) == ('drums and percussion', None, None), r['name']
    elif r['status'] == 'ALIAS':
        assert instruments.ALIASES[r['name']] == r['alias_of'], r['name']
    else:
        assert r['name'] not in instruments.CATALOG and r['name'] not in instruments.ALIASES, r['name']
print('matches', len(rows), 'rows')
"
```
Expected: `matches N rows`.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: batch 3's drums (membranophones), each from its source"
```

---

### Task 3: The idiophones sheet

Research, as in Task 1.

**Files:**
- Modify: `plans/data/instrument-audit/batch-3.tsv` (append the remaining rows)

**Interfaces:**
- Consumes: the sheet from Task 1, its rules 1–7, and `build/batch-3-candidates.txt` (if it is
  missing, rerun Task 1 Step 1).
- Produces: the sheet's remaining rows, read by Task 4.

Every candidate with no row yet gets one: idiophones (`hs` starting `1`: rattles, shakers,
scrapers, clappers, concussion sticks, blocks, slit drums, pot drums such as the ghatam,
cymbals, gongs, bells) and the out-of-family rows (DROP, with `hs` the class the source gives:
`5` for electronic, `4` for an aerophone). Also add one row per remaining name in the audit's
"Aliases" section.

Rules for this half, in addition to Task 1's:

- Cymbals and gongs: the catalog has eleven (`crash cymbal` through `wind gong`). A new one
  ships only with a sourced trait that sets it apart: a sizzle cymbal's rivets, a china's
  upturned edge, a bossed gong's definite pitch (then "tuned percussion batch" if the source
  gives a compass).
- Rattles and shakers: `_shaker` (noise ring and high pass) is the shared shape. A rattle
  whose source gives nothing beyond "gourd rattle" is a sound-alike alias of the nearest
  rattle (rules 3 and 7).
- A scraper or ratchet whose sound is a run of separate clicks needs an amplitude LFO, as
  batch 2's `thunder run` does. WAIT it for that, unless one noise burst per note is a faithful
  stroke quoted from its source (a guiro's single scrape is already in the catalog).
- `sandpaper blocks` and the audit's `sand blocks`: rule 3 decides whether they are one
  instrument. `washboard`, `frottoir` and their audit aliases: likewise.

- [ ] **Step 1: Append the rows,** in the candidate list's order.

- [ ] **Step 2: Check the sheet's form**

Run Task 1 Step 3's command.
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 3: Check that no candidate was left out silently**

Run:
```bash
comm -23 build/batch-3-candidates.txt \
  <(awk -F'\t' 'NR>1 {print tolower($11)}' plans/data/instrument-audit/batch-3.tsv | sort -u)
```
Expected: no output. (Alias-section rows have their alias as `audit_name` and are not in the
candidate list. That is expected.)

- [ ] **Step 4: Commit**

```bash
git add plans/data/instrument-audit/batch-3.tsv
git commit -m "Instrument audit: batch 3's verification sheet, idiophone and out-of-family rows"
```

---

### Task 4: Percussion (idiophones)

**Files:**
- Modify: `drums.py` (the new idiophone entries, after Task 2's)
- Modify: `aliases.py` (this half's ALIAS rows)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-3.tsv` rows with `hs` starting `1`; Task 2's `drums.py`, `NEW_DRUM_NAMES`,
  `test_no_two_drums_build_the_same_instrument` and the renamed one-shot tests.
- Produces: the finished family.

- [ ] **Step 1: Write the failing tests:** append this half's SHIP names to `NEW_DRUM_NAMES`,
  and its ALIAS rows to `test_the_batch_aliases_resolve`'s parameters.

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "drum or one_shot or batch_aliases" -v`
Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 2 Step 5. A builder new to the family (only
  if no existing shape can make the sourced sound) gets its own test of the trait it exists
  for, as batch 2's `test_the_pianet_settles_from_a_bright_strike` does.

- [ ] **Step 4: Run the suite and check the code against the sheet**

Run Task 2 Step 6's commands, with `r['hs'].startswith('1')` in place of
`r['hs'].startswith('2')`. Then rerun the second command with `True` in place of the `hs`
condition, so that all rows are checked.
Expected: PASS, then `matches N rows` twice. A strike-again or one-shot failure gets the same
treatment as in Task 2. A long-ringing gong that the sheet keeps as SHIP goes in a
`LONG_RINGING_ONE_SHOTS` set in the test file. The set gives its measured ring, and the test
skips it by name with that reason, as `NOT_PERIODIC_AT_THE_NOTE` does.

- [ ] **Step 5: Lint and commit**

Run Task 2 Step 7's lint commands, then:
```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: batch 3's percussion (idiophones), each from its source"
```

---

### Task 5: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py` (the docstring: the family's count
  and examples; `drums.py` named)
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the count, and the drums and
  percussion row's count and examples)
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts)
- Modify: `plans/future-features.md`. In #70: batch 3 done, with the sheet's counts by status;
  the audit's unclosed gaps as a later pass; and the next batch named (plucked strings). Add a
  new item after #71, "Sound Engine: The Owner's Checks on Instrument Catalog Batch 3 — TODO",
  in #71's form: **Listen** (the new entries by group, each group a checkbox), **Calls to
  confirm** (every sound-alike alias and the entry it points at, every WAIT, the fixed
  tones of tonic-tuned drums, the strokes shipped, the two-half split), **Follow-ups**.
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md` (the status line: batch 3
  done, pointing at this plan and `batch-3.tsv`; the "Depends on" counts; and decision 8, the
  owner's 2026-11-08 ruling that a verified instrument that sounds like an entry is an alias of
  it, quoted as in the plan's decisions, with the Non-goals' alias line pointing at it)

- [ ] **Step 1: Get the counts from the code**

Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES))"`
Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.** Write no counts from memory.

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
`build/instruments/<family>/<name>.wav`. The `drums and percussion` folder is the one to
listen to. The owner judges the sound.

- [ ] **Step 4: Commit**

```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
git commit -m "Docs: batch 3 of the instrument catalog (drums and percussion), its counts and the owner's checks"
```

Pushing and the PR wait for the owner (CLAUDE.md: never push automatically). The pre-push
hooks take about 40 minutes, and nothing in the working tree may change while they run.
