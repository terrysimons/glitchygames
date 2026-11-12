# Instrument catalog batch 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the tuned percussion family from the audits' candidates. Each instrument gets a
cited source and either sounds unlike every other entry or is a listed sound-alike of the one
it sounds like. The rest are aliases, wait for an engine feature or a sourced range, or are
dropped with a reason.

**Architecture:** As in batches 3 and 4, a verification sheet (`batch-5.tsv`) decides every
candidate before any code is written. `percussion.py` already holds only this family (341
lines), so nothing moves: its table becomes `_TUNED_BUILDS + TUNED_SOUND_ALIKES`, with the
sound-alikes in a new `tuned_sound_alikes.py`, as `plucked_strings.py` and
`plucked_sound_alikes.py` do. Batch 4's pitched sound-alike rule (a sound-alike is pitched
exactly when its parent is, and a pitched one gives its own sourced range) already covers this
family. Batch 4's two family-specific tests become one test per family over a table, so this
batch adds a row instead of copies. The sheet and the code each come in two halves: bars,
plaques, tubes and stones (Hornbostel–Sachs 111.21–111.23), then gongs, bells, pans, the tuned
drums and the out-of-family rows.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 4 and 8 above
all). Batch 4's plan (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) and its
sheet (`batch-4.tsv`) are the model this batch follows. The candidates come from
`plans/data/instrument-audit/`:
- `merged.tsv` rows whose `family` starts with `tuned percussion` (122: 110 from the round-2
  audit `tuned-percussion.md`, 11 from the drums audit, and `wind chimes` from the
  environmental audit);
- `round-1/merged-missing.tsv` rows whose `family` contains `tuned` (35);
- four rows earlier batches handed to this one: `boobam`, `paigu` and `rototom` (batch 3, DROP
  "Tuned percussion batch") and `chime machine` (batch 2, DROP "Bells, so tuned percussion").

Some names repeat across sources; Task 2 Step 1 counts the unique ones. The audit's "Aliases"
section proposes aliases on top.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents and punctuation go only in the title (`gender barung`, title `Gendèr
  barung`).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec,
  Families). Batch 1 took the lamellophones and jaw harps (plucked idiophones) and the rubbed
  glass and metal (friction instruments: musical glasses, Cristal Baschet, verrophone, musical
  saw). The celesta's kin (`gameleste`, tuning-fork keyboards) belong to keyboards. All of
  those are DROP here, naming where they go.
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). A range can be derived only from sourced facts (a set's
  lowest and highest notes, or its lowest note plus a sourced count of chromatic or diatonic
  steps); the derivation goes in `notes`. With no sourced range the row is WAIT, with
  `waits_for` `a sourced range` (the owner kept this strict rule, 2026-11-09).
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`), listed by `names` and `entries` and
  given a demo like any other; a true alias (another name for the same instrument) stays an
  alias." A pitched sound-alike gives its own sourced range; it is pitched exactly when its
  parent is.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature": none ships as
  an approximation, under its real name or a qualified one. The engine lacks amplitude, pitch
  and filter LFOs (a tremolo, a vibraphone's motor), moving formants, FM, sample playback, more
  than four sources, and sub-audio fundamentals. It has up to four partials per note, each with
  its own ratio, level and ring (`Partial`; two partials a few cents apart beat, which is how a
  sourced gamelan *ombak* can be made), a mallet's noise burst (`mallet`, `mallet_low_pass`),
  and one pitch glide per note (`Tone.glide_to`, `glide_seconds`).
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception: they add names, not builds.
- Reuse the family's shapes (`struck_bar`, `GLOCKENSPIEL`, `XYLOPHONE`, `MARIMBA`,
  `VIBRAPHONE`, `GAMELAN_METALLOPHONE`, `KETTLE_GONG`, `HARMONIC_PAN`, `_church_bell`,
  `_tubular_bell`, `_timpani`). Add a builder only for a genuinely new sound, and give it its
  own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: attribute content you use).
- The 23 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after them.
- Code style: Google docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage,
  no abbreviated variable names.

## Review Focus

1. **A gamelan size that is a renamed copy.** The audit lists every size of every gamelan
   instrument (`saron barung`, `demung`, `peking`; `gender barung`, `gender panerus`), and the
   catalog already has `saron`, `gender` and `bonang`. A size differs by range, which is not a
   sound trait: each is a sound-alike of the existing entry unless a sourced trait (the
   material, a resonator, *ombak* beating, the mallet) differs, or an alias when the source
   says it is the same instrument. Task 1's test checks no new build equals another entry's.
2. **A range from memory.** Only four of the audit's ranges are verified (boomwhackers C2–G5,
   angklung G2–C6, musical glasses, cristal baschet). A SHIP or SOUND_ALIKE row's
   `range_source` must be a fetched URL whose text gives the range or the facts it is derived
   from. The form check refuses an empty one.
3. **A candidate an earlier batch already decided.** Batch 1 took the lamellophones, jaw harps
   and friction instruments; batch 3 shipped `agung`, `kemanak`, `anvil`, `tingsha`,
   `teponaztli` and `txalaparta`, made `octoban` a sound-alike and held back `bell tree`,
   `mark tree` and `flexatone`. The form check refuses a SHIP, SOUND_ALIKE or ALIAS row whose
   name is already a catalog name or alias, and Step 2's rule 5 gives each such row a DROP
   naming the earlier decision.
4. **A tremolo shipped as a single strike.** An angklung is shaken (repeated strikes), a wind
   chime or chime tree sounds as many strikes, a vibraphone-style motor is an amplitude LFO. A
   row whose identifying sound is repeated strikes or a tremolo is WAIT, as batch 3's
   `bell tree`, `mark tree` and `flexatone` are.
5. **The test refactor drops a check.** Task 1 turns batch 4's two plucked-string tests into
   tests over a family table. Every plucked string assertion must survive: the plucked rows of
   the table hold exactly batch 4's lists, and the test IDs name the family.

---

## File Structure

- Modify `src/glitchygames/audio/instruments/percussion.py`: rename the table to
  `_TUNED_BUILDS`; new builds after the 23; `TUNED_PERCUSSION = _TUNED_BUILDS +
  TUNED_SOUND_ALIKES`.
- Create `src/glitchygames/audio/instruments/tuned_sound_alikes.py`: `TUNED_SOUND_ALIKES`.
- Modify `aliases.py`: the batch's ALIAS rows.
- Modify `tests/audio/test_instrument_catalog.py`: the family-table tests (Task 1) and the
  batch's lists.
- Create `plans/data/instrument-audit/batch-5.tsv`: the verification sheet (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70, and a new #75 for the owner's checks), and the
  design's status line and "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check):

- **Tuned percussion is pitched.** An instrument with no definite pitch belongs to drums and
  percussion (batch 3 shipped `agung` there as a fixed tone). A row whose source gives no
  definite pitch is DROP "drums and percussion"; a tuned drum with a definite pitch
  (`rototom`, `boobam`, `paigu`, `tabla tarang`) stays here, as `timpani` and `tabla dayan` do.
- **A one-pitch body played as a set takes the set's range.** A `kenong` or `kempul` is a row
  of single-pitch gongs; the entry's range is the set's, from a source. A single body sold in
  sizes takes the span of the sizes a source lists. Otherwise it waits for a sourced range.
- **One-offs are dropped.** The spec dropped the environmental family because its entries are
  "mostly one-off installations". The same goes here for single built instruments (Harry
  Partch's, the Great Stalacpipe Organ, the marble machine): DROP "a one-off instrument, not a
  type a game would ask for". Task 6 lists them in the owner's checks.
- **Existing entries stay as they are.** The family's shared builds (`marimba` and
  `bass marimba`; `saron` and `gender`; the four steel pans) predate the anti-goal rule and are
  left alone, as batch 4 left its 54 pairs. The audit's range notes on existing entries
  (`bass marimba` G1–G3 or C2–F3 against the catalog's A1–C4; `timpani` about D2–A3 against
  D2–C4) go in the owner's checks, unchanged here.
- **The steel pan sizes the catalog lacks** (`soprano`, `double tenor`, `double guitar`,
  `triple guitar`, `quadrophonic`, `tenor bass`, `six bass`, `nine bass`, `twelve bass`) are
  sound-alikes of the steel pan nearest in register, each with its own sourced range, unless a
  source gives a different sound trait.
- **Two halves by Hornbostel–Sachs class:** bars, plaques, tubes and stones (`hs` starting
  `111.21`, `111.22` or `111.23`) in Tasks 2–3, everything else in Tasks 4–5. The executor may
  dispatch a half in two parts, in the candidate list's order, with one review per half.
- **Out of scope:** the audit's "Gaps you could not close" (the Chinese, Japanese, Korean,
  Indian, African, Oceanic and Philippine names it suspected but did not confirm). Task 6 lists
  them in #70 for a later pass.

---

### Task 1: The batch tests read a family table

**Files:**
- Modify: `src/glitchygames/audio/instruments/percussion.py`
- Create: `src/glitchygames/audio/instruments/tuned_sound_alikes.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `TUNED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` (empty in this task);
  `TUNED_PERCUSSION = _TUNED_BUILDS + TUNED_SOUND_ALIKES`. In the test file:
  `EXISTING_TUNED_NAMES` (the 23), `NEW_TUNED_NAMES: list[str]` and
  `TUNED_SOUND_ALIKE_PARENTS: dict[str, str]` (both empty here; Tasks 3 and 5 fill them), and
  `BATCH_FAMILIES: dict[Family, tuple[frozenset[str], list[str], dict[str, str]]]`, mapping a
  family to its existing names, new builds and sound-alike parents.

- [ ] **Step 1: Write the tests over the table**

Replace `test_no_new_plucked_string_builds_another_entrys_instrument` and
`test_the_new_plucked_strings_are_pitched_entries_of_their_family` with:
```python
# Each family a batch grew: (the entries that predate it, its new builds, its sound-alikes)
BATCH_FAMILIES = {
    Family.PLUCKED_STRINGS: (
        EXISTING_PLUCKED_NAMES, NEW_PLUCKED_NAMES, PLUCKED_SOUND_ALIKE_PARENTS
    ),
    Family.TUNED_PERCUSSION: (EXISTING_TUNED_NAMES, NEW_TUNED_NAMES, TUNED_SOUND_ALIKE_PARENTS),
}


@pytest.mark.parametrize('family', list(BATCH_FAMILIES), ids=str)
def test_no_new_build_is_another_entrys_instrument(family):
    """A batch's build is its own sound (the anti-goal), whatever entry it is set against."""
    _, new_names, _ = BATCH_FAMILIES[family]
    names = instruments.names(family=family)
    same = [
        (new_name, other)
        for new_name in new_names
        for other in names
        if other != new_name
        and instruments.entry(other).sounds_like is None
        and instruments.get(new_name) == instruments.get(other)
    ]
    assert same == []


@pytest.mark.parametrize('family', list(BATCH_FAMILIES), ids=str)
def test_the_new_entries_are_pitched_entries_of_their_family(family):
    """Each new entry, sound-alikes included, is in its family with a range."""
    existing_names, new_names, sound_alike_parents = BATCH_FAMILIES[family]
    for name in [*new_names, *sound_alike_parents]:
        assert instruments.entry(name).family == family, name
        assert instruments.entry(name).pitched, name
    assert set(instruments.names(family=family)) == (
        existing_names | set(new_names) | set(sound_alike_parents)
    )
```
In `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, replace the plucked loop with
one over every `BATCH_FAMILIES` row (each sound-alike listed in that row's family, its
`sounds_like` its parent, its build its parent's), and make the closing list follow the table
order (`FAMILY_TABLES`: plucked strings, then tuned percussion, then drums):
`list(PLUCKED_SOUND_ALIKE_PARENTS) + list(TUNED_SOUND_ALIKE_PARENTS) + SOUND_ALIKE_NAMES`.

- [ ] **Step 2: Run them**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike" -v`
Expected: PASS, with IDs `[plucked strings]` and `[tuned percussion]`. The tuned rows pass
trivially here; that is expected until Task 3.

- [ ] **Step 3: Split the table.** Rename `percussion.py`'s table to `_TUNED_BUILDS`, unchanged.
Create `tuned_sound_alikes.py` with an empty `TUNED_SOUND_ALIKES` and a module docstring that
quotes the owner as `plucked_sound_alikes.py`'s does. `TUNED_PERCUSSION = _TUNED_BUILDS +
TUNED_SOUND_ALIKES`. `registry.py` keeps importing `TUNED_PERCUSSION`; its place in
`FAMILY_TABLES` doesn't change.

- [ ] **Step 4: Run the catalog tests**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: the batch tests read a family table; tuned sound-alikes get a module"
```

---

### Task 2: The bars, plaques, tubes and stones sheet

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. A list page is a source for a name only. The
sound, the title and the range come from the instrument's own page, or from a museum or maker
record.

**Files:**
- Create: `plans/data/instrument-audit/batch-5.tsv`
- Create (not committed): `build/batch-5-candidates.txt`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `tuned-percussion.md` ("Rejected or
  corrected proposed entries", "Aliases", "Range checks", "Modeling difficulty"); `batch-1.tsv`
  through `batch-4.tsv` (earlier decisions).
- Produces: `batch-5.tsv`, with batch 4's header
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an
  ALIAS's target or a SOUND_ALIKE's parent. `family` is `tuned percussion` on every row. SHIP
  and SOUND_ALIKE rows have `lowest`, `highest` and `range_source`. In this task, every row's
  `hs` starts with `111.21`, `111.22` or `111.23`.

- [ ] **Step 1: Write the candidate list**

Run:
```bash
mkdir -p build
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /^tuned percussion/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /tuned/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' boobam paigu rototom 'chime machine'
} | sort -u > ../../../build/batch-5-candidates.txt
cd ../../..
wc -l < build/batch-5-candidates.txt
```
Expected: about 150 (the sources overlap). Write the count in the ledger.

- [ ] **Step 2: Build the sheet's bar, plaque, tube and stone rows.** Write one row per
candidate whose fetched source shows struck bars, plaques, tubes or stones (H-S 111.21–111.23:
xylophones, marimbas, metallophones, glockenspiels, lithophones, tube sets such as
boomwhackers and the angklung), in the candidate list's order. Also add one row per name in
the audit's "Aliases" section whose target is one of these.

Rules (batch 4's, with this batch's changes):

1. **SHIP** only with name, title, range and sound from fetched sources. Quote the passage that
   describes the sound or construction in `notes`, and the passage that gives the range. The
   `builder` cell gives the `struck_bar` call (ratios, levels, ring, mallet), or names a family
   shape with its changes. It says which values come from the source (wood or metal bars,
   gourd or tube resonators, a buzzing membrane, the bar's tuning of its overtones, beating
   pairs, hard or padded mallets) and which are sound design.
2. **SOUND_ALIKE** a verified instrument that rule 7 finds would sound like an existing entry or
   a SHIP row. `alias_of` is its parent. `notes` begin "Sound-alike:", quote the source's
   description, and say why that entry is the nearest. It has its own sourced range. The parent
   is a catalog name or a SHIP row of this sheet, never another sound-alike.
3. **ALIAS** another name for the same instrument, cited. The target is a catalog name, a SHIP
   row or a SOUND_ALIKE row. If the target waits, the row is WAIT with `waits_for` `its target,
   <name>`.
4. **WAIT** when the identifying sound needs a feature the engine lacks, named in `waits_for`
   with the source quoted: an amplitude LFO (a tremolo, repeated strikes such as an angklung's
   shaking, a motor), a buzzing membrane whose buzz is the identifying sound and which the
   mallet's noise cannot make (the gyil's and balafon's spider-silk mirlitons: the catalog's
   `balafon` has none, which goes in the owner's checks), or `a sourced range`.
5. **DROP** a row that does not exist as described, belongs to another family (name it:
   "plucked idiophones", "friction instruments", "keyboards", "drums and percussion"), is a
   one-off (the plan's decisions), or is already decided: in the catalog under that name (name
   the entry), an alias already (name its target), or a row of an earlier sheet (name the
   sheet and its status).
6. A row the audit marks "(memory)" has no sourced sound yet. Fetch the instrument's own page.
   If none can be found, it is DROP "no fetched source describes it".
7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
   (`uv run python -I -c "from glitchygames.audio import instruments as i;
   print(i.names(family='tuned percussion'))"`, and the builds in `percussion.py`) and every
   SHIP row above it. If no sourced trait (material, resonator, overtone tuning, beating,
   mallet, ring) makes it sound different, it is a SOUND_ALIKE under rule 2. A different number
   chosen only to be different does not count. A range is not a sound trait: two gamelan sizes
   an octave apart with the same keys are sound-alikes.

- [ ] **Step 3: Check the sheet's form**

Run:
```bash
uv run python -I -c "
import csv, re, sys
from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-5.tsv'), delimiter='\t'))
own = {r['name'] for r in rows if r['status'] == 'SHIP'} | {n for n in instruments.CATALOG if instruments.entry(n).sounds_like is None}
alikes = {r['name'] for r in rows if r['status'] == 'SOUND_ALIKE'}
taken = set(instruments.CATALOG) | set(instruments.ALIASES)
def ranged(r):
    try:
        return r['range_source'].startswith('http') and Note(r['lowest']).midi_number < Note(r['highest']).midi_number
    except Exception:
        return False
names = [r['name'] for r in rows]
bad = [r['name'] for r in rows if not pattern.fullmatch(r['name'])
       or r['status'] not in {'SHIP','SOUND_ALIKE','WAIT','ALIAS','DROP'}
       or r['family'] != 'tuned percussion'
       or not r['audit_name'] or not r['hs'][:1].isdigit()
       or (r['status'] in {'SHIP','SOUND_ALIKE'} and (not r['sound_source'].startswith('http') or not ranged(r)))
       or (r['status'] in {'SHIP','SOUND_ALIKE','ALIAS'} and r['name'] in taken)
       or (r['status'] == 'SOUND_ALIKE' and r['alias_of'] not in own)
       or (r['status'] == 'WAIT' and not r['waits_for'])
       or (r['status'] == 'ALIAS' and r['alias_of'] not in own | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {s: sum(r['status']==s for r in rows) for s in ('SHIP','SOUND_ALIKE','WAIT','ALIAS','DROP')})
print('bad:', bad); sys.exit(1 if bad else 0)
"
```
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 4: Check that every row is a bar, plaque, tube or stone**

Run: `awk -F'\t' 'NR>1 && $10 !~ /^111\.2[123]/ {print $1}' plans/data/instrument-audit/batch-5.tsv`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add plans/data/instrument-audit/batch-5.tsv
git commit -m "Instrument audit: batch 5's verification sheet, bar, plaque, tube and stone rows"
```

---

### Task 3: Bars, plaques, tubes and stones

**Files:**
- Modify: `percussion.py` (the new builds, after the 23), `tuned_sound_alikes.py`, `aliases.py`
  (this half's ALIAS rows, each with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-5.tsv` rows whose `hs` starts `111.21`, `111.22` or `111.23`; Task 1's
  table and lists.
- Produces: `NEW_TUNED_NAMES` and `TUNED_SOUND_ALIKE_PARENTS` with this half's rows, which
  Task 5 extends.

- [ ] **Step 1: Write the failing tests:** fill `NEW_TUNED_NAMES` with one name per SHIP row of
  this half, in the sheet's order, and `TUNED_SOUND_ALIKE_PARENTS` with one `name: parent` per
  SOUND_ALIKE row; add this half's ALIAS rows to `test_the_batch_aliases_resolve`'s parameters.

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases" -v`
Expected: the new-name and alias cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries.** Add one entry per SHIP row, in the sheet's order, after the
existing 23. Precede each with a comment holding its `sound_source` and `range_source` URLs and
the quoted traits it is built from, and mark the values that are sound design. Put the
SOUND_ALIKE rows in `tuned_sound_alikes.py`, each with a source comment and its own range. Put
the ALIAS rows in `aliases.py` with their source comments. A builder new to the family (only if
no existing shape can make the sourced sound) gets its own test of the trait it exists for, as
batch 2's `test_the_pianet_settles_from_a_bright_strike` does.

- [ ] **Step 4: Run the suite and check the code against the sheet**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
Expected: PASS, including `test_every_instrument_renders_across_its_range` for every new
entry. A render failure at a range end is a finding about the range or the build: check it
against the source, never by trimming the range to pass. (A free bar's 5.40x partial passes
the Nyquist limit above about C7; the module's comment on `FREE_BAR_RATIOS` says why.)

Then run:
```bash
uv run python -I -c "
import csv
from glitchygames.audio import instruments
rows = [r for r in csv.DictReader(open('plans/data/instrument-audit/batch-5.tsv'), delimiter='\t')
        if r['hs'][:6] in {'111.21', '111.22', '111.23'}]
for r in rows:
    if r['status'] in {'SHIP', 'SOUND_ALIKE'}:
        e = instruments.entry(r['name'])
        assert (e.family, e.lowest, e.highest) == ('tuned percussion', r['lowest'], r['highest']), r['name']
        assert e.sounds_like == (r['alias_of'] if r['status'] == 'SOUND_ALIKE' else None), r['name']
    elif r['status'] == 'ALIAS':
        assert instruments.ALIASES[r['name']] == r['alias_of'], r['name']
    elif 'already' not in r['notes'].lower():
        assert r['name'] not in instruments.CATALOG and r['name'] not in instruments.ALIASES, r['name']
print('matches', len(rows), 'rows')
"
```
Expected: `matches N rows`. (A DROP whose note says the name is already in the catalog or an
alias is the one row allowed to resolve.)

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: batch 5's bars, plaques, tubes and stones, each from its source"
```

---

### Task 4: The gongs, bells, pans and drums sheet

Research, as in Task 2.

**Files:**
- Modify: `plans/data/instrument-audit/batch-5.tsv` (append the remaining rows)

**Interfaces:**
- Consumes: the sheet from Task 2, its rules 1–7, and `build/batch-5-candidates.txt` (if it is
  missing, rerun Task 2 Step 1).
- Produces: the sheet's remaining rows, read by Task 5.

Every candidate with no row yet gets one: gongs and kettle gongs (`hs` `111.241`: the gamelan's
`kenong`, `kempul`, `gong ageng`, `bonang` sizes, `reyong`, `trompong`, `kulintang`), bells
(`111.242`: `bianzhong`, `almglocken`, `choirchimes`, `chime machine`), steel pans and tongue
drums, the tuned drums (`2`: `rototom`, `boobam`, `paigu`, `tabla tarang`, `piccolo timpani`),
and the out-of-family rows (DROP, with `hs` the class the source gives). Also add one row per
remaining name in the audit's "Aliases" section.

Rules for this half, in addition to Task 2's:

- A gong or bell set takes the set's sourced range (the plan's decisions). A gamelan gong's
  long swell (`gong ageng`, per "Modeling difficulty") is a slow attack, which `struck` cannot
  make if the source makes it the identifying sound: WAIT for it then, naming the feature.
- `bianzhong`: Zhou-era bells give two pitches a third apart, struck at two points; later sets
  give one (the audit). An entry plays one pitch per note, so it is the one-pitch kind or it
  waits; say which in `notes`.
- `chime machine` (batch 2): a theatre device of bells; rule 3 decides whether it is another
  name for `tubular bells` or `church bell`, and rule 7 whether it sounds like one.
- Steel pans: the plan's decision makes each missing size a sound-alike of the nearest steel
  pan in register unless a source gives another sound trait. The audit gives the steelpan
  family A1–G6 overall only, so each size needs its own sourced range or waits.
- `steel tongue drum`: the audit says its C3–C6 is unverified and that `hank drum`, `hapi drum`
  and `tank drum` are brand names for it (rule 3, cited, if it ships).
- `wind chimes`: sounds as many strikes, so rule 4 (an amplitude LFO with a stepped pitch, as
  batch 3's `mark tree`) unless a source gives a single-strike form.
- `rototom`: the drum is retuned by turning it, through a phrase as a glissando; a sourced
  fixed-pitch use may ship, with the glide only for a sourced single slide.

- [ ] **Step 1: Append the rows,** in the candidate list's order.

- [ ] **Step 2: Check the sheet's form.** Run Task 2 Step 3's command.
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 3: Check that no candidate was left out silently**

Run:
```bash
comm -23 build/batch-5-candidates.txt \
  <(awk -F'\t' 'NR>1 {print tolower($11)}' plans/data/instrument-audit/batch-5.tsv | sort -u)
```
Expected: no output. (Alias-section rows have their alias as `audit_name` and are not in the
candidate list. That is expected.)

- [ ] **Step 4: Commit**

```bash
git add plans/data/instrument-audit/batch-5.tsv
git commit -m "Instrument audit: batch 5's verification sheet, gong, bell, pan, drum and out-of-family rows"
```

---

### Task 5: Gongs, bells, pans and drums

**Files:**
- Modify: `percussion.py`, `tuned_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-5.tsv` rows whose `hs` does not start with `111.21`, `111.22` or `111.23`;
  Task 3's lists.
- Produces: the finished family.

- [ ] **Step 1: Write the failing tests:** append this half's SHIP names to `NEW_TUNED_NAMES`,
  its SOUND_ALIKE rows to `TUNED_SOUND_ALIKE_PARENTS`, and its ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3.

- [ ] **Step 4: Run the suite and check the code against the sheet.** Run Task 3 Step 4's
commands with `r['hs'][:6] not in {...}` in place of `r['hs'][:6] in {...}`. Then run the
second command again with `True` as the condition, so that every row is checked.
Expected: PASS, then `matches N rows` twice.

- [ ] **Step 5: Lint and commit.** Run Task 3 Step 5's lint commands, then:
```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: batch 5's gongs, bells, pans and drums, each from its source"
```

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py` (the docstring: the family's count
  and examples; `tuned_sound_alikes.py` named)
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the count, and the tuned
  percussion row's count and examples)
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts)
- Modify: `plans/future-features.md`. In #70: batch 5 done, with the sheet's counts by status;
  the audit's unclosed gaps as a later pass; and the next batch named (electronic, the next
  largest existing family, per the spec's order). Fix #74's stale line that says #172 "is
  still open" (it merged on 2026-11-10). Add #75, "Sound Engine: The Owner's Checks on
  Instrument Catalog Batch 5 — TODO", in #74's form. **Listen**: the new builds by group, and
  the sound-alikes grouped under their parents. **Calls to confirm**:
  - every WAIT;
  - tuned percussion is pitched (unpitched rows go to drums and percussion);
  - a set's range for a one-pitch body;
  - the one-offs dropped;
  - the steel pan sizes as sound-alikes;
  - the family's existing shared builds, as possible sound-alike conversions;
  - the audit's range notes on `bass marimba` and `timpani`, and `balafon` built without its
    buzzing mirlitons;
  - every derived range;
  - the two-half split.

  Then **Follow-ups**.
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 5
  done, pointing at this plan and `batch-5.tsv`) and the "Depends on" counts.

- [ ] **Step 1: Get the counts from the code**

Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries()))"`
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
Expected: everything passes. The `build/instruments/tuned percussion` folder is the one to
listen to. The owner judges the sound.

- [ ] **Step 4: Commit**

```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
git commit -m "Docs: batch 5 of the instrument catalog (tuned percussion), its counts and the owner's checks"
```

Pushing and the PR wait for the owner (CLAUDE.md: never push automatically). The pre-push
hooks take about 40 minutes, and nothing in the working tree may change while they run.
