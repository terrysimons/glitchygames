# Instrument catalog batch 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the plucked strings family from the audits' 244 candidates. Each instrument gets
a cited source and either sounds unlike every other entry or is a listed sound-alike of the one
it sounds like. The rest are aliases, wait for an engine feature, or are dropped with a reason.

**Architecture:** As in batch 3, a verification sheet (`batch-4.tsv`) decides every candidate
before any code is written. The family's table moves unchanged from `strings.py` (806 lines,
which also holds bowed strings, harps and struck strings) to a new `plucked_strings.py`, where
the new builds go. Sound-alikes go in `plucked_sound_alikes.py`, as `drum_sound_alikes.py` does
for drums. Unlike drums, this family is pitched: every entry, sound-alikes included, needs a
sourced range. So Task 2 lets a pitched sound-alike carry its own range. The sheet and the code
each come in two halves: necked lutes (Hornbostel–Sachs 321.3: guitars, lutes, banjos,
ukuleles), then everything else (zithers 31, musical bows, lyres 321.2, and the out-of-family
rows).

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 4 and 8 above
all). Batch 3's plan (`plans/2026-11-08-instrument-catalog-batch-3-implementation.md`) and its
sheet (`batch-3.tsv`, with its `SOUND_ALIKE` status) are the model this batch follows. The
candidates come from `plans/data/instrument-audit/`:
- `merged.tsv` rows whose `family` starts with `plucked strings` (173, from the round-2 audit
  `plucked-strings.md` and the environmental audit's `aeolian harp`);
- `round-1/merged-missing.tsv` rows whose `family` contains `plucked str` (72);
- five rows the audit moves here from harps: `krar`, `begena`, `nyatiti`, `sasando` and
  `swarmandal` (`plucked-strings.md`, "Rejected or corrected proposed entries").

The first two give 244 unique names. With the five, 249 at most. The audit's "Aliases" section
(25 lines) proposes aliases on top.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents and punctuation go only in the title (`dan bau`, title `Đàn bầu`).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec,
  Families). Harps (322) stay in harps. Bowed lyres (`jouhikko`, `talharpa`) belong to bowed
  strings. Hammered zithers (`marxophone`) belong to struck strings. Quill keyboards belong to
  keyboards. All of those are DROP here, naming where they go.
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). A range can be derived only from sourced facts: the lowest
  open string, plus the fret count or the highest stopped note when the source gives them. The
  derivation goes in `notes`. An instrument with no sourced range is WAIT, with `waits_for` `a
  sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`), listed by `names` and `entries` and
  given a demo like any other; a true alias (another name for the same instrument) stays an
  alias."
- Decision 4: "Instruments the engine cannot make well yet wait for the feature": none ships as
  an approximation, under its real name or a qualified one. The engine lacks sympathetic
  strings or a buzzing bridge (jawari), moving formants, vibrato, pitch and filter LFOs, FM,
  sample playback, more than four sources, and sub-audio fundamentals. It has one pitch glide
  per note (`Tone.glide_to`, `glide_seconds`), paired and octave courses (`Course`), a pick
  click (`pick`), drive, and a held tone (`sustain`).
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception: they add names, not builds.
- Reuse the family's shapes (`_plucked`, `NYLON_GUITAR`, `STEEL_GUITAR`, `LUTE`,
  `BRIGHT_LUTE`, `SHORT_LUTE` and the rest). Add a builder only for a genuinely new sound, and
  give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: attribute content you use).
- The 58 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after them.
- Code style: Google docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage,
  no abbreviated variable names.

## Review Focus

1. **A plucked string that is a renamed copy.** Most audit notes say "plain pluck". A new
   entry with its own build that equals another entry's build is the anti-goal: it should be a
   sound-alike instead. Task 4 adds a test that no new entry with its own build builds the same
   instrument as any other entry in the family. The family's 54 existing pairs that share a
   build (`mandolin` and `mandola` both use `BRIGHT_LUTE`, for example) predate the rule, and
   the test leaves them out by name (see the plan's decisions).
2. **A range from memory.** The audit says ranges are "estimated from usual tunings from
   memory" for all but about 12 rows. A SHIP or SOUND_ALIKE row's `range_source` must be a
   fetched URL whose text gives the lowest note. The form check refuses an empty one.
3. **A sound-alike whose range is its parent's by copy.** A requinto is not a classical
   guitar's E2 to B5. With Task 2's rule, a pitched sound-alike gives its own sourced range.
   The code-against-sheet check in Tasks 4 and 6 compares every range with the sheet.
4. **The table move changes a sound.** The 58 builds and their order must survive the move to
   `plucked_strings.py`. Task 1 records each build's identity before the move and compares it
   afterwards.
5. **A sound-alike or alias of something that is not there.** An ALIAS or SOUND_ALIKE row whose
   target waits or is dropped would fail at import. The form check refuses a target that is
   neither a catalog name nor a SHIP row in the sheet. A sound-alike of a sound-alike is
   refused too, as `sound_alikes_from` refuses it.

---

## File Structure

- Create `src/glitchygames/audio/instruments/plucked_strings.py`: `PLUCKED_STRINGS`, moved
  from `strings.py` with the plucked section's helpers (`_plucked`, `PAIRED`, `OCTAVE_PAIRED`,
  `SYMPATHETIC`, `NYLON_GUITAR` through `SHORT_LUTE`, and any other helper only that section
  uses), then the new builds. The module's table is `_PLUCKED_BUILDS + PLUCKED_SOUND_ALIKES`, as
  `drums.py` does it.
- Create `src/glitchygames/audio/instruments/plucked_sound_alikes.py`: `PLUCKED_SOUND_ALIKES`.
- Modify `strings.py`: the plucked section leaves, and the module docstring drops its plucked
  sentences, which move to the new module with their sources.
- Modify `registry.py`: import `PLUCKED_STRINGS` from `plucked_strings.py`; the pitched
  sound-alike rule (Task 2).
- Modify `catalog.py`: the `sounds_like` docstring (Task 2).
- Modify `aliases.py`: the batch's ALIAS rows.
- Modify `tests/audio/test_instrument_catalog.py`: the tests below.
- Create `plans/data/instrument-audit/batch-4.tsv`: the verification sheet (Tasks 3 and 5).
- Docs (Task 7): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70, and a new #74 for the owner's checks), and the
  design's status line and decision 8. #74 assumes the loose-ends PR
  (`fix/replay-fps-column`), which renumbers batch 3's checks to #73, has merged first. If it
  hasn't, rebase onto main before Task 7.

Decisions made in this plan (my calls, for the owner to check):

- **A pitched sound-alike has its own range** (Task 2). Decision 8's `sounds_like` docstring
  says a sound-alike "has its parent's range". That held for drums, which have no range. Here a
  terz guitar may sound like a classical guitar a minor third higher. Sharing the build is the
  right call, but copying the range would put wrong data in the catalog. The family already
  works this way: `mandolin` (G3–B6) and `mandola` (C3–E6) share `BRIGHT_LUTE`. The new rule: a
  sound-alike is pitched exactly when its parent is, and a pitched one gives its own sourced
  range. An unpitched one still has none.
- **The existing shared builds stay as they are.** The 54 pairs among the 58 existing entries
  are left alone. Turning them into sound-alikes would change entries this batch must not
  change. Task 7 lists them in the owner's checks as a possible later conversion.
- **Existing entries that decision 4 would now hold back stay.** `sitar`, `tanpura` and `veena`
  approximate sympathetic strings with `SYMPATHETIC` courses and buzz with `drive`
  (`BUZZING_LUTE`). They shipped with M1, before decision 4. They are not removed. New
  instruments whose identifying sound is sympathetic strings or a jawari bridge (rudra veena,
  surbahar, mohan veena, the ten-string guitar) WAIT, and do not become sound-alikes of
  `sitar`. Task 7 puts the three existing entries in the owner's checks.
- **Placement questions stay open.** The audit's placement notes (`lyre`, `kora` and
  `harp guitar` in harps; `berimbau` in struck strings) are not acted on here. They go in the
  owner's checks.
- **Two halves by Hornbostel–Sachs class:** necked lutes (321.3) in Tasks 3–4, everything else
  in Tasks 5–6. The executor may dispatch a half in two parts, in the candidate list's order,
  with one review per half.
- **A moving pitch through a phrase waits.** A đàn bầu's rod bends each note through a melody,
  and a guqin's slides and a diddley bow's slide do too when they are the identifying sound.
  That is a pitch the sequence would control, which one glide per note is not (batch 3's
  talking drum ruling). A single sourced slide into a note may use the glide.
- **Out of scope:** the audit's "Gaps you could not close" (Siberian and Himalayan lutes,
  Caucasian zithers, kabosy, and others). Task 7 lists them in #70 for a later pass.

---

### Task 1: Plucked strings in their own module, unchanged

**Files:**
- Create: `src/glitchygames/audio/instruments/plucked_strings.py`
- Modify: `src/glitchygames/audio/instruments/strings.py`, `registry.py`

**Interfaces:**
- Produces: `PLUCKED_STRINGS: Final[tuple[CatalogEntry, ...]]` in `plucked_strings.py`, and
  the section's helpers there under their current names.

- [ ] **Step 1: Record the family's builds before touching the code**

Run:
```bash
mkdir -p build
uv run python -I -c "
from glitchygames.audio import instruments
with open('build/plucked-builds-before.txt', 'w', encoding='utf-8') as before:
    for name in instruments.names(family='plucked strings'):
        entry = instruments.entry(name)
        before.write(f'{name}\t{entry.title}\t{entry.lowest}\t{entry.highest}\t{instruments.get(name)._identity()!r}\n')
print('recorded', len(instruments.names(family='plucked strings')))
"
```
Expected: `recorded 58`. (`_identity` is private. A one-off check may read it, but a test may
not.)

- [ ] **Step 2: Move the table**

Move the "Plucked strings" section of `strings.py` into `plucked_strings.py`, unchanged. Read
every comment on the moved code first. The new module docstring keeps the plucked sentences and
sources from `strings.py`'s docstring (the plucking-position series, ringing down, paired
courses, the jawari buzz), and `strings.py`'s docstring keeps the rest. A helper that both
modules use stays in `strings.py`, and `plucked_strings.py` imports it. Point `registry.py` at
the new module. Its place in `FAMILY_TABLES` doesn't change.

- [ ] **Step 3: Check nothing changed**

Run:
```bash
uv run python -I -c "
from glitchygames.audio import instruments
before = [line.split('\t') for line in open('build/plucked-builds-before.txt', encoding='utf-8').read().splitlines()]
assert [row[0] for row in before] == list(instruments.names(family='plucked strings')), 'order'
changed = [row[0] for row in before
           if [instruments.entry(row[0]).title, str(instruments.entry(row[0]).lowest), str(instruments.entry(row[0]).highest), repr(instruments.get(row[0])._identity())] != row[1:]]
print('changed:', changed)
"
uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -q
```
Expected: `changed: []`, then PASS.

- [ ] **Step 4: Commit**

```bash
git add src/glitchygames/audio/instruments
git commit -m "Instrument catalog: plucked strings in their own module, unchanged"
```

---

### Task 2: A pitched sound-alike gives its own range

**Files:**
- Modify: `src/glitchygames/audio/instruments/registry.py` (`sound_alikes_from`)
- Modify: `src/glitchygames/audio/instruments/catalog.py` (the `sounds_like` docstring)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `sound_alikes_from` accepts a sound-alike whose range differs from its parent's
  when both are pitched. It refuses one that is pitched when its parent is not, or the reverse,
  with the message in Step 1.

- [ ] **Step 1: Write the failing tests**

In `test_the_sound_alikes_are_refused_when_they_are_wrong`, replace the case whose message is
`"test alike: its range must be that of 'test parent'"` with the two cases below. The
helper `sound_alike_table` builds `test parent` unpitched, so the first case is a pitched
sound-alike of an unpitched parent. For the second, add an entry to `sound_alike_table`:
`CatalogEntry('test pitched parent', 'Test pitched parent', Family.PLUCKED_STRINGS, 'C3', 'C5',
plain_drum)`.
```python
(
    CatalogEntry('test alike', 'Test alike', Family.DRUMS_AND_PERCUSSION, 'C4', 'C5',
                 sounds_like='test parent'),
    "test alike: pitched exactly when 'test parent' is",
),
(
    CatalogEntry('test alike', 'Test alike', Family.PLUCKED_STRINGS, None, None,
                 sounds_like='test pitched parent'),
    "test alike: pitched exactly when 'test pitched parent' is",
),
```
Add:
```python
def test_a_pitched_sound_alike_keeps_its_own_range():
    """A sound-alike of a pitched entry builds its parent's sound over its own sourced range."""
    parent = CatalogEntry('test pitched parent', 'Test pitched parent', Family.PLUCKED_STRINGS,
                          'C3', 'C5', plain_drum)
    alike = CatalogEntry('test alike', 'Test alike', Family.PLUCKED_STRINGS, 'E3', 'E5',
                         sounds_like='test pitched parent')

    assembled = sound_alikes_from({parent.name: parent, alike.name: alike})

    assert (assembled['test alike'].lowest, assembled['test alike'].highest) == ('E3', 'E5')
    assert assembled['test alike'].build() == parent.build()
```
(`sound_alikes_from` and `plain_drum` are already in the test file.)

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "sound_alike" -v`
Expected: the new refusal cases fail on the old message, and the new test fails with
`its range must be that of 'test pitched parent'`.

- [ ] **Step 3: Change the rule in `sound_alikes_from`.** Replace the equal-range check with
`catalog_entry.pitched != parent.pitched`, which raises
`ValueError(f'{name}: pitched exactly when {parent_name!r} is')`. Update the Raises line of the
docstring. In `catalog.py`, the `sounds_like` docstring says a sound-alike is pitched exactly
when its parent is, and that a pitched one gives its own sourced range. Cite decision 8 and
this plan.

- [ ] **Step 4: Run the catalog tests**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -q`
Expected: PASS. Every batch 3 sound-alike is unpitched with an unpitched parent, so all of them
still assemble.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: a pitched sound-alike gives its own sourced range"
```

---

### Task 3: The necked lutes sheet

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. A list page ("List of string instruments") is a
source for a name only. The sound, the title and the range come from the instrument's own
page, or from a museum or maker record.

**Files:**
- Create: `plans/data/instrument-audit/batch-4.tsv`
- Create (not committed): `build/batch-4-candidates.txt`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `plucked-strings.md` ("Rejected or
  corrected proposed entries", "Aliases", "Range checks").
- Produces: `batch-4.tsv`, with batch 3's header
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an
  ALIAS's target or a SOUND_ALIKE's parent. `family` is `plucked strings` on every row. SHIP
  and SOUND_ALIKE rows have `lowest`, `highest` and `range_source`. In this task, every row's
  `hs` starts with `321.3`.

- [ ] **Step 1: Write the candidate list**

Run:
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /^plucked strings/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /plucked str/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' krar begena nyatiti sasando swarmandal
} | sort -u > ../../../build/batch-4-candidates.txt
cd ../../..
wc -l < build/batch-4-candidates.txt
```
Expected: between `244` and `249`. Some of the five may already be in the first two sources.
Write the count in the ledger.

- [ ] **Step 2: Build the sheet's necked-lute rows.** Write one row per candidate whose fetched
source shows a neck the strings run along (H-S 321.3: guitars, lutes, banjos, ukuleles,
mandolins, spike lutes), in the candidate list's order. Also add one row per name in the
audit's "Aliases" section whose target is a necked lute.

Rules (batch 3's, with this batch's changes):

1. **SHIP** only with name, title, range and sound from fetched sources. Quote the passage that
   describes the sound or construction in `notes`, and the passage that gives the range. The
   `builder` cell gives the `_plucked` call, or names a family shape, with its changes. It says
   which values come from the source (nylon, steel, gut or wire strings; paired or octave
   courses; plectrum or fingers; scale length; a skin soundboard such as a banjo's) and which
   are sound design.
2. **SOUND_ALIKE** a verified instrument that rule 7 finds would sound like an existing entry or
   a SHIP row. `alias_of` is its parent. `notes` begin "Sound-alike:", quote the source's
   description, and say why that entry is the nearest. It has its own sourced range (Task 2).
   The parent is a catalog name or a SHIP row of this sheet, never another sound-alike.
3. **ALIAS** another name for the same instrument, cited (`outi` → `oud`, if a source shows
   they are one instrument). The target is a catalog name, a SHIP row or a SOUND_ALIKE row. If
   the target waits, the row is WAIT with `waits_for` `its target, <name>`.
4. **WAIT** when the identifying sound needs a feature the engine lacks, named in `waits_for`
   with the source quoted: sympathetic strings, a jawari bridge, a pitch moving through a
   phrase (the plan's decisions), or `a sourced range`.
5. **DROP** a row that does not exist as described, or belongs to another family (name where
   it goes: "harps", "bowed strings", "struck strings", "keyboards", "plucked idiophones"), or
   is already in the catalog under that name (name the entry).
6. A row the audit marks "(memory)" has no sourced sound yet. Fetch the instrument's own page.
   If none can be found, it is DROP "no fetched source describes it".
7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
   (`uv run python -I -c "from glitchygames.audio import instruments as i;
   print(i.names(family='plucked strings'))"`, and the builds in `plucked_strings.py`) and every
   SHIP row above it. If no sourced trait (string material, courses, plucking, body or
   soundboard, scale) makes it sound different, it is a SOUND_ALIKE under rule 2. A different
   number chosen only to be different does not count. A range is not a sound trait: two
   guitars a fourth apart with the same strings and body are sound-alikes.

- [ ] **Step 3: Check the sheet's form**

Run:
```bash
uv run python -I -c "
import csv, re, sys
from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-4.tsv'), delimiter='\t'))
own = {r['name'] for r in rows if r['status'] == 'SHIP'} | {n for n in instruments.CATALOG if instruments.entry(n).sounds_like is None}
alikes = {r['name'] for r in rows if r['status'] == 'SOUND_ALIKE'}
def ranged(r):
    try:
        return r['range_source'].startswith('http') and Note(r['lowest']).midi_number <= Note(r['highest']).midi_number
    except Exception:
        return False
names = [r['name'] for r in rows]
bad = [r['name'] for r in rows if not pattern.fullmatch(r['name'])
       or r['status'] not in {'SHIP','SOUND_ALIKE','WAIT','ALIAS','DROP'}
       or r['family'] != 'plucked strings'
       or not r['audit_name'] or not r['hs'][:1].isdigit()
       or (r['status'] in {'SHIP','SOUND_ALIKE'} and (not r['sound_source'].startswith('http') or not ranged(r)))
       or (r['status'] in {'SHIP','SOUND_ALIKE'} and r['name'] in instruments.CATALOG)
       or (r['status'] == 'SOUND_ALIKE' and r['alias_of'] not in own)
       or (r['status'] == 'WAIT' and not r['waits_for'])
       or (r['status'] == 'ALIAS' and r['alias_of'] not in own | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {s: sum(r['status']==s for r in rows) for s in ('SHIP','SOUND_ALIKE','WAIT','ALIAS','DROP')})
print('bad:', bad); sys.exit(1 if bad else 0)
"
```
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 4: Check that every row is a necked lute's**

Run: `awk -F'\t' 'NR>1 && $10 !~ /^321\.3/ {print $1}' plans/data/instrument-audit/batch-4.tsv`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add plans/data/instrument-audit/batch-4.tsv
git commit -m "Instrument audit: batch 4's verification sheet, necked lute rows"
```

---

### Task 4: Necked lutes

**Files:**
- Modify: `plucked_strings.py` (the new builds, after the 58), `plucked_sound_alikes.py`
  (create it), `aliases.py` (this half's ALIAS rows, each with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-4.tsv` rows with `hs` starting `321.3`; Task 1's module and helpers; Task 2's
  rule.
- Produces: `PLUCKED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]`; `PLUCKED_STRINGS =
  _PLUCKED_BUILDS + PLUCKED_SOUND_ALIKES`. In the test file, `NEW_PLUCKED_NAMES`,
  `PLUCKED_SOUND_ALIKE_PARENTS` and `EXISTING_PLUCKED_NAMES`, which Task 6 extends.

- [ ] **Step 1: Write the failing tests**

```python
# The 58 plucked strings that predate batch 4: their shared builds predate the anti-goal rule
EXISTING_PLUCKED_NAMES = frozenset({
    # the 58 names from build/plucked-builds-before.txt
})
# Batch 4's entries with their own build, in the sheet's order (Task 6 appends the rest)
NEW_PLUCKED_NAMES = [
    # one name per SHIP row of batch-4.tsv whose hs starts with 321.3
]
# Batch 4's sound-alikes and the entry each sounds like, in the sheet's order
PLUCKED_SOUND_ALIKE_PARENTS = {
    # one name: parent per SOUND_ALIKE row whose hs starts with 321.3
}


def test_no_new_plucked_string_builds_another_entrys_instrument():
    """A batch 4 build is its own sound (the anti-goal), whatever entry it is set against."""
    names = instruments.names(family=Family.PLUCKED_STRINGS)
    same = [
        (new_name, other)
        for new_name in NEW_PLUCKED_NAMES
        for other in names
        if other != new_name
        and instruments.entry(other).sounds_like is None
        and instruments.get(new_name) == instruments.get(other)
    ]
    assert same == []


def test_the_new_plucked_strings_are_pitched_entries_of_their_family():
    """Each new entry, sound-alikes included, is a plucked string with a range."""
    for name in [*NEW_PLUCKED_NAMES, *PLUCKED_SOUND_ALIKE_PARENTS]:
        assert instruments.entry(name).family == Family.PLUCKED_STRINGS, name
        assert instruments.entry(name).pitched, name
    assert set(instruments.names(family=Family.PLUCKED_STRINGS)) == (
        EXISTING_PLUCKED_NAMES | set(NEW_PLUCKED_NAMES) | set(PLUCKED_SOUND_ALIKE_PARENTS)
    )
```
Extend `test_a_sound_alike_is_listed_and_builds_its_parents_sound` to check
`PLUCKED_SOUND_ALIKE_PARENTS` too, in its family, and make its catalog-wide list
`SOUND_ALIKE_NAMES + list(PLUCKED_SOUND_ALIKE_PARENTS)`. Add this half's ALIAS rows to
`test_the_batch_aliases_resolve`'s parameters.

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "plucked or sound_alike or batch_aliases" -v`
Expected: the new-name and alias cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries.** Add one entry per SHIP row, in the sheet's order, after the
existing 58. Precede each with a comment holding its `sound_source` and `range_source` URLs and
the quoted traits it is built from, and mark the values that are sound design. Put the
SOUND_ALIKE rows in `plucked_sound_alikes.py`, as `drum_sound_alikes.py` does: the module
docstring quotes the owner, each entry gets a source comment, and each has its own range. Put
the ALIAS rows in `aliases.py` with their source comments. A builder new to the family (only
if no existing shape can make the sourced sound) gets its own test of the trait it exists for,
as batch 2's `test_the_pianet_settles_from_a_bright_strike` does.

- [ ] **Step 4: Run the suite and check the code against the sheet**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
Expected: PASS, including `test_every_instrument_renders_across_its_range` for every new
entry. A render failure at a range end is a finding about the range or the build: check it
against the source, never by trimming the range to pass.

Then run:
```bash
uv run python -I -c "
import csv
from glitchygames.audio import instruments
rows = [r for r in csv.DictReader(open('plans/data/instrument-audit/batch-4.tsv'), delimiter='\t')
        if r['hs'].startswith('321.3')]
for r in rows:
    if r['status'] in {'SHIP', 'SOUND_ALIKE'}:
        e = instruments.entry(r['name'])
        assert (e.family, e.lowest, e.highest) == ('plucked strings', r['lowest'], r['highest']), r['name']
        assert e.sounds_like == (r['alias_of'] if r['status'] == 'SOUND_ALIKE' else None), r['name']
    elif r['status'] == 'ALIAS':
        assert instruments.ALIASES[r['name']] == r['alias_of'], r['name']
    else:
        assert r['name'] not in instruments.CATALOG and r['name'] not in instruments.ALIASES, r['name']
print('matches', len(rows), 'rows')
"
```
Expected: `matches N rows`.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: batch 4's necked lutes, each from its source"
```

---

### Task 5: The zithers, bows and lyres sheet

Research, as in Task 3.

**Files:**
- Modify: `plans/data/instrument-audit/batch-4.tsv` (append the remaining rows)

**Interfaces:**
- Consumes: the sheet from Task 3, its rules 1–7, and `build/batch-4-candidates.txt` (if it is
  missing, rerun Task 3 Step 1).
- Produces: the sheet's remaining rows, read by Task 6.

Every candidate with no row yet gets one: zithers (`hs` starting `31`: board, tube, raft and
bar zithers, the qanun, koto and guzheng kin, the psaltery and dulcimer kin, musical bows), bow
and yoke lutes (`321.1`, `321.2`: the krar, begena and other lyres, the ngoni's harp-lute
cousins), and the out-of-family rows (DROP, with `hs` the class the source gives: `322` harps,
`311` struck, and so on). Also add one row per remaining name in the audit's "Aliases"
section.

Rules for this half, in addition to Task 3's:

- `aeolian harp`: the wind sounds it, with no player (the audit). It is DROP "sound effects or
  an ambient texture, not a played plucked string", unless a fetched source gives it a played
  form.
- `musical bow`: the source gives types (uhadi, umrhubhe) and two notes a tone apart, not one
  instrument's range. A type whose own page gives its notes may ship. The generic name is WAIT
  `a sourced range` unless a source gives one.
- Drone zithers (`epinette des vosges`, `langeleik`, `scheitholt`, `hummel`): rule 3 decides
  which are one instrument, and rule 7 which sound alike.
- `begena` and the `nyatiti`: the audit says their buzz comes from the bridge. If the source
  makes that buzz the identifying sound, they WAIT for a buzzing bridge (decision 4).
- `washtub bass` and `tea chest bass`: one instrument class per the audit's source; rule 3.
  The pitch changes with the pole's tension through a phrase (rule 4).

- [ ] **Step 1: Append the rows,** in the candidate list's order.

- [ ] **Step 2: Check the sheet's form.** Run Task 3 Step 3's command.
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 3: Check that no candidate was left out silently**

Run:
```bash
comm -23 build/batch-4-candidates.txt \
  <(awk -F'\t' 'NR>1 {print tolower($11)}' plans/data/instrument-audit/batch-4.tsv | sort -u)
```
Expected: no output. (Alias-section rows have their alias as `audit_name` and are not in the
candidate list. That is expected.)

- [ ] **Step 4: Commit**

```bash
git add plans/data/instrument-audit/batch-4.tsv
git commit -m "Instrument audit: batch 4's verification sheet, zither, bow, lyre and out-of-family rows"
```

---

### Task 6: Zithers, bows and lyres

**Files:**
- Modify: `plucked_strings.py`, `plucked_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-4.tsv` rows whose `hs` does not start with `321.3`; Task 4's lists and tests.
- Produces: the finished family.

- [ ] **Step 1: Write the failing tests:** append this half's SHIP names to `NEW_PLUCKED_NAMES`,
  its SOUND_ALIKE rows to `PLUCKED_SOUND_ALIKE_PARENTS`, and its ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters.

- [ ] **Step 2: Run them and check they fail.** Run Task 4 Step 2's command.
Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 4 Step 3.

- [ ] **Step 4: Run the suite and check the code against the sheet.** Run Task 4 Step 4's
commands with `not r['hs'].startswith('321.3')` in place of `r['hs'].startswith('321.3')`.
Then run the second command again with `True` as the condition, so that every row is checked.
Expected: PASS, then `matches N rows` twice.

- [ ] **Step 5: Lint and commit.** Run Task 4 Step 5's lint commands, then:
```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: batch 4's zithers, bows and lyres, each from its source"
```

---

### Task 7: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py` (the docstring: the family's count
  and examples; `plucked_strings.py` and `plucked_sound_alikes.py` named)
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the count, and the plucked
  strings row's count and examples)
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts)
- Modify: `plans/future-features.md`. In #70: batch 4 done, with the sheet's counts by status;
  the audit's unclosed gaps as a later pass; and the next batch named (tuned percussion,
  reminding it not to ship `agung`, `tingsha` and `teponaztli` again). Add #74, "Sound Engine:
  The Owner's Checks on Instrument Catalog Batch 4 — TODO", in #73's form. **Listen**: the
  new builds by group, and the sound-alikes grouped under their parents. **Calls to confirm**:
  - every WAIT;
  - the pitched sound-alike rule (Task 2);
  - the 54 existing shared-build pairs, as possible sound-alike conversions;
  - `sitar`, `tanpura` and `veena`, which approximate what decision 4 now holds back;
  - the audit's placement notes (`lyre`, `kora`, `harp guitar`, `berimbau`);
  - every derived range;
  - the two-half split.
  
  Then **Follow-ups**.
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 4
  done, pointing at this plan and `batch-4.tsv`); the "Depends on" counts; decision 8, with a
  sentence on the pitched sound-alike rule marked as the plan's call for the owner to confirm.

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
Expected: everything passes. The `build/instruments/plucked strings` folder is the one to
listen to. The owner judges the sound.

- [ ] **Step 4: Commit**

```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
git commit -m "Docs: batch 4 of the instrument catalog (plucked strings), its counts and the owner's checks"
```

Pushing and the PR wait for the owner (CLAUDE.md: never push automatically). The pre-push
hooks take about 40 minutes, and nothing in the working tree may change while they run.
