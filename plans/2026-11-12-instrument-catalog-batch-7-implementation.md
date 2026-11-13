# Instrument catalog batch 7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the bowed strings family (Hornbostel–Sachs 321 and 31 sounded by a bow or a
wheel: violins, viols, fiddles, bowed lyres, spike fiddles, bowed zithers, hurdy-gurdies) from
the audits' candidates. Each instrument gets a cited source and either sounds unlike every other
entry or is a listed sound-alike of the one it sounds like. The rest are aliases, wait for an
engine feature or a sourced range, or are dropped with a reason.

**Architecture:** As in batches 3 to 6, a verification sheet (`batch-7.tsv`) decides every
candidate before any code is written. The family's 27 entries live in `strings.py` (340 lines,
which also holds harps and struck strings), so they move unchanged to a new `bowed_strings.py`,
as batch 4 moved plucked strings out of the same file. Its table becomes `_BOWED_BUILDS +
BOWED_SOUND_ALIKES`, with the sound-alikes in a new `bowed_sound_alikes.py`. The family is
wholly pitched, so the batch table's `unpitched_names` stays empty. The sheet and the code each
come in two halves, split by an explicit list: the European and modern bowed strings, then the
bowed strings of Asia and Africa. The two sheet halves may be researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/waves.py`, `audio/instruments/timbres.py`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 4 and 8
above all). Batch 6's plan (`plans/2026-11-12-instrument-catalog-batch-6-implementation.md`) is
this plan's template, and batch 4's (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`)
holds the pitched sound-alike and strict range rules. This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-7-implementation.md`. The branch is
`feat/instrument-catalog-batch-7`, made from `feat/instrument-catalog-batch-6`. The candidates
come from `plans/data/instrument-audit/`:
- `merged.tsv` rows whose `family` starts with `bowed` (75, all from the round-2 audit
  `bowed-strings.md`);
- `round-1/merged-missing.tsv` rows whose `family` contains `bowed` (48, none of them in
  `merged.tsv`: `crwth`, `jouhikko`, `octobass`, `baryton`, `tromba marina`, `yaybahar`, ...);
- three rows no family has decided: `zeze` (`batch-4.tsv`, DROP "bowed strings"), and the
  self-playing violins `violano virtuoso` and `phonoliszt violina` (`merged.tsv`, family
  `mechanical instruments`, which the spec makes a tag: "Each stays in the family it sounds
  like").

Together: **126 unique candidate names** (counted for this plan; Task 2 Step 1 recounts). None
is in the catalog or the alias table today. The audit's "Aliases" section (13 lines) proposes
aliases on top. `plans/future-features.md` #70–#76 leave nothing else for this family.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, hyphens and parentheses go only in the title (`viola d
  amore`, title `Viola d'amore`; `cretan lyra` for the audit's `lyra cretan`).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families).
  A string sounded by a bow or a rosined wheel is this family, whatever the body (lute, lyre,
  zither) or the player's interface (keys, a wheel). Friction idiophones (nail violin, musical
  saw: H-S 13) are friction instruments, and electric violins and cellos stay here (batch 2's
  call, #71: "Electric guitars, basses, violins and steels stay in their string families").
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict").
  This plan's range ruling for bowed strings is below ("Decisions"). With no sourced range a row
  is WAIT, `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the
  same instrument) stays an alias." A sound-alike is pitched exactly when its parent is, and a
  pitched one gives its own sourced range (batch 4). A parent may be in another family.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature": none ships as
  an approximation, under its real name or a qualified one. The spec's table names this
  family's waits: "sympathetic strings, a buzzing bridge (jawari) | … sarangi, … hardanger
  fiddle, viola d'amore" and "sub-audio fundamentals | octobass lowest notes". Batch 6 added the
  rest of the names a WAIT may give: a pitch LFO (vibrato), a pitch LFO (portamento between
  notes), an amplitude LFO, filter resonance, a filter envelope, more than four sources, moving
  formants. The engine has: up to four `Source`s, each with its own semitones, detune, fixed
  pitch (`with_drones`: fixed-pitch drones under every note, keeping only the `tone` and
  `breath` sources, so a drone build loses `section_cents`'s chorus), one glide per note
  (`pitch_curve`), its own envelope; fixed FIR low or high pass; `drive` 0–20; static formants
  in the harmonic levels (`formant_series`); and the family's `_bowed` shape (falling series,
  attack, slope, bow noise, a low pass, a detuned second copy, drive) and `_pizzicato`.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception: they add names, not builds.
- Reuse the family's shapes (`_bowed`, `_pizzicato`, `VIOLIN`, `VIOLA`, `CELLO`, `DOUBLE_BASS`,
  `VIOL`, `FOLK_FIDDLE`, `SPIKE_FIDDLE`) and the shared ones (`blown`, `with_drones`,
  `formant_series`). Add a builder only for a genuinely new sound, and give it its own test
  (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the
  sheet is verbatim from a page the worker fetched.
- The 27 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after them. An existing entry changes only for a cited bug, reported to the
  owner.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown
  by a test, you should understand why it's happening and be concerned": a warning is a
  finding, understood before going on.
- Commits as batches 4 to 6: `SKIP=replay-metrics git commit`, subject `Instrument catalog: …`,
  `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`: subagents running on other models
  have substituted their own name (#76, "Bugs to report"), so each commit message is copied
  from this plan, never written from memory. No `.md` file beyond those Task 6 names.

## Review Focus

1. **A sympathetic-string or buzzing-bridge instrument shipped as a copy of an old
   approximation.** `sarangi`, `hardanger fiddle`, `viola d amore` and `nyckelharpa` imitate
   sympathetic strings with a detuned copy (`section_cents`), and `hurdy gurdy` imitates its
   buzzing bridge with `drive`. A new `dilruba` or `moraharpa` as their sound-alike would ship
   the imitation under a new name. Task 1's test refuses any sound-alike of them (and of batch
   4's `sitar`, `tanpura`, `veena` and `sarod`), and the form check refuses such a parent.
2. **An open-string span read as a range.** The audit's "VERIFIED" ranges are mostly open
   strings ("Verified ranges are OPEN-STRING ranges … not full playable compass"). A bowed
   string plays far above its top string, so taking that string as the highest note puts wrong
   data in the catalog. The range ruling refuses it; the form check requires a `Range:` passage
   in every pitched row's notes, and the code check compares every range with the sheet.
3. **A note below the catalog's floor.** The octobass and the contrabass members (the Phoenix
   octobass's C0, a contrabass violin's C1) go below or near A0. The form check refuses a range
   below A0 (the piano's lowest, the catalog's span), and the spec makes the octobass WAIT
   `sub-audio fundamentals`. Nothing is clipped: clipping was batch 6's ruling for a chip's
   divider range, not for an acoustic instrument's lowest string.
4. **A renamed copy.** Most audit rows say "as erhu", "as violin", "as rebec". A new build that
   equals `SPIKE_FIDDLE` or `VIOL` with a number nudged is the anti-goal; it should be a
   sound-alike. Task 1's family-table row makes the existing test refuse a new build equal to
   another entry's.
5. **A candidate decided twice.** `electric upright bass` is batch 4's WAIT (plucked strings),
   and `viola organista` is also a keyboards-audit row. The form check refuses a SHIP,
   SOUND_ALIKE or ALIAS row whose name the catalog or alias table held before this batch, and
   rule 5 gives each decided row a DROP naming the sheet and status; Task 6 tells #70 that the
   keyboards batch must not decide `viola organista` again.

---

## File Structure

- Create `src/glitchygames/audio/instruments/bowed_strings.py`: the "Bowed strings" section of
  `strings.py` (`_bowed`, `_pizzicato`, `VIOLIN` to `SPIKE_FIDDLE`, the 27 entries), unchanged,
  as `_BOWED_BUILDS`; new builds after the 27; `BOWED_STRINGS = _BOWED_BUILDS +
  BOWED_SOUND_ALIKES`.
- Create `src/glitchygames/audio/instruments/bowed_sound_alikes.py`: `BOWED_SOUND_ALIKES`.
- Modify `strings.py` (the section and its bowed docstring sentences leave; it keeps harps and
  struck strings), `registry.py` (imports `BOWED_STRINGS` from `bowed_strings.py`; its place in
  `FAMILY_TABLES` doesn't change), `aliases.py` (the batch's ALIAS rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3, 5) and
  `tests/test_process_state_guard.py` (the seven `CATALOG_BUILD` names move from
  `'audio/instruments/strings.py'` to `'audio/instruments/bowed_strings.py'`, plus any new
  module-level shared build).
- Create `plans/data/instrument-audit/batch-7.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70, and a new #77), and the design's status line
  and "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #77):

- **Bowed strings get their own module.** `strings.py` is not large (340 lines), but batch 4
  and batch 6 each gave the family they grew a module of its own, with a sibling sound-alikes
  module that names it ("The family's builds are in …"). Keeping the bowed builds in
  `strings.py` would make that file hold three families, one of them growing by batch; moving
  them leaves `strings.py` with harps (7) and struck strings (5), which later batches can move
  the same way. The move is mechanical, checked by Task 1's before-and-after record.
- **Range ruling for bowed strings.** A sourced range is the lowest and highest sounding notes,
  each from a fetched source:
  1. *Lowest:* the lowest open string of the standard tuning a source gives in note names with
     octaves (or with a tuning reference that fixes the octave). Several sourced tunings: the
     one the source calls standard or usual; none called so: WAIT `a sourced range`.
  2. *Highest:* a note the source states as the instrument's highest, its compass ("from C3 to
     A6"), or an exact span above the lowest string ("three octaves"). An open-string span
     ("tuned G-D-A-E") gives no highest note. A hedged span ("about", "roughly", "usually up
     to") is not exact. Neither is a range: WAIT `a sourced range`.
  3. A range below A0 (27.5 Hz, the catalog's floor) is WAIT `sub-audio fundamentals`; the spec
     names the octobass. A scordatura instrument (lyra viol) needs a source giving its compass.
  4. A range is never taken from another instrument's page, a size's sibling or the audit.
  `notes` holds `Range:` and the quoted passages, then the derivation.
- **Approximating entries are never parents.** `sarangi`, `hardanger fiddle`, `viola d amore`
  and `nyckelharpa` (sympathetic strings by a detuned copy) and `hurdy gurdy` (its buzzing
  bridge by `drive`, as this plan reads the build) shipped with M1 and stay unchanged. A new
  instrument whose source names sympathetic strings or a buzzing bridge as its sound WAITs
  (`sympathetic strings`, `a buzzing bridge`) and does not become their sound-alike: batch 4's
  sitar ruling. A wheel instrument without a buzzing bridge needs its own build or waits.
  `with_drones` gives fixed drone strings, but not resonating ones.
- **Drone strings are buildable at sourced pitches.** A bowed instrument whose source names
  drone strings as its sound (vielle, crwth, moraharpa) is built with `with_drones` at the
  drone pitches its source gives in note names with octaves (at most two, since the bow noise
  keeps a source). With no sourced drone tuning it WAITs `a sourced drone tuning`, not built
  without its drones. A drone build is not periodic at the note: it joins
  `NOT_PERIODIC_AT_THE_NOTE` with its reason.
- **A moving pitch through a phrase waits** (batch 4's đàn bầu ruling): when a source names a
  slide, portamento or vibrato as the instrument's identifying sound (not a technique any
  player may use), the row WAITs `a pitch LFO (vibrato)` or `a pitch LFO (portamento between
  notes)`. The existing `violin`, `erhu` and the rest have no vibrato and stay.
- **Mechanical and keyed bowed instruments.** `violano virtuoso` and `phonoliszt violina` are
  decided here (a violin with a piano, the spec's "more than four sources" example). `viola
  organista` and `geigenwerk` are decided here too: their strings are bowed, and the keyboards
  batch must not decide `viola organista` again. A SHIP or SOUND_ALIKE row of a self-playing
  instrument carries `Tag.MECHANICAL` (`tags` `mechanical`).
- **Sizes.** The violin octet, the viol consort and the huqin sizes are distinct instruments
  (sourced) that will mostly sound like an existing size: a SOUND_ALIKE of the nearest existing
  entry the source relates them to, each with its own range under the ruling, or WAIT.
- **One-offs are dropped** (batch 5's ruling): a single built instrument or a handful of
  prototypes, as its source says (the audit suspects `fences`, `keyolin`, `kaisatsuko`,
  `celloridoo`, `long string instrument`, `adapted viola`, `neola`): DROP "a one-off
  instrument, not a type a game would ask for".
- **Two halves by an explicit list.** Bowed strings cross the Hornbostel–Sachs subclasses in
  ways the sheet must find out (a spike lute, a necked box or bowl lute, a lyre, a zither), so
  the split is by tradition. Half B, the bowed strings of Asia and Africa, is these 57
  candidates; half A, the European and modern bowed strings, is the other 69:
  `ajaeng`, `armenian kamancha`, `banam`, `banhu`, `behala`, `black sea kemence`, `byzaanchy`,
  `chikara`, `dan co`, `dan nhi`, `dihu`, `dilruba`, `diyingehu`, `endingidi`, `erxian`,
  `esraj`, `gaohu`, `gehu`, `ghijak`, `goje`, `haegeum`, `igil`, `imzad`, `javanese rebab`,
  `jinghu`, `kamaicha`, `kamancheh`, `kezaixian`, `khuuchir`, `kobyz`, `kokyu`, `kongahyan`,
  `kyl kyyak`, `laruan`, `masenqo`, `njarka`, `pena`, `ravanahatha`, `rebab`, `sarangi
  nepali`, `sarinda`, `sato`, `saw duang`, `saw sam sai`, `saw u`, `sihu`, `sukong`, `tar
  shehnai`, `taus`, `tehyan`, `tro`, `tro ou`, `yazheng`, `yehu`, `zeze`, `zhonghu`, `zhuihu`.
  The audit's alias lines go with their target's half: `matouqin`, `zhuiqin`, `tihu`/`tiqin`,
  `rabab`, `goge`, the kemenche spellings and the ajaeng variants in B, the rest in A. The
  candidates' duplicates fall within one half (`talharpa` and `jouhikko`, `violotta` and `alto
  violin`, `tro` and `tro ou`, `organistrum` and `symphonia`).
- **The halves run in parallel.** Each half's parents and alias targets are catalog names
  from before the batch or SHIP rows of the same half, never a row of the other half, so
  Task 4's research needs nothing from Task 2's. Half B is written to a build file and appended
  to the sheet once half A is committed; the form check accepts a row the code already holds
  with the same target or parent (batch 6's lesson: its check called such names "taken").
- **Out of scope:** the audit's "Gaps you could not close" (MIMO, the Met, Horniman and Grove
  unconsulted; the huqin names it did not row, such as `erquanqin`, `jing erhu`, `datong`,
  `leiqin`; `kontra`, `latfiol`, the Apache fiddle; Ethiopian, Sahel, Malagasy, Oceanian,
  Andean and Caribbean fiddles). Task 6 lists them in #70 for a later pass.

---

### Task 1: Bowed strings in their own module, unchanged; the batch table's row

**Files:**
- Create: `src/glitchygames/audio/instruments/bowed_strings.py`,
  `src/glitchygames/audio/instruments/bowed_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/strings.py`, `registry.py`,
  `tests/test_process_state_guard.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `BOWED_STRINGS: Final[tuple[CatalogEntry, ...]] = _BOWED_BUILDS +
  BOWED_SOUND_ALIKES` in `bowed_strings.py`, with `_bowed`, `_pizzicato` and `VIOLIN` to
  `SPIKE_FIDDLE` there under their current names; `BOWED_SOUND_ALIKES: Final[tuple[CatalogEntry,
  ...]]` (empty). In the test file: `EXISTING_BOWED_NAMES: frozenset[str]` (the 27),
  `NEW_BOWED_NAMES: list[str]` and `BOWED_SOUND_ALIKE_PARENTS: dict[str, str]` (empty here;
  Tasks 3 and 5 fill them), `APPROXIMATING_NAMES: frozenset[str]`, and the row
  `Family.BOWED_STRINGS: BatchFamily(EXISTING_BOWED_NAMES, NEW_BOWED_NAMES,
  BOWED_SOUND_ALIKE_PARENTS)` in `BATCH_FAMILIES`. Also `build/bowed-builds-before.txt` and
  `build/batch-7-names-before.txt` (every catalog name and alias before the batch, one per
  line), which Tasks 2 and 4 read.

- [ ] **Step 1: Record the family's builds and the names before touching the code.** Run batch
  4's Task 1 Step 1 command with `family='bowed strings'` and `build/bowed-builds-before.txt`.
  Expected: `recorded 27`. Then:
```bash
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-7-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
  Expected: `names before 755` (682 entries and 73 aliases).

- [ ] **Step 2: Write the tests.** Add `EXISTING_BOWED_NAMES`, `NEW_BOWED_NAMES = []` and
  `BOWED_SOUND_ALIKE_PARENTS = {}` above `BatchFamily`, and the bowed row first in
  `BATCH_FAMILIES` (table order: bowed strings, plucked strings, electronic, tuned percussion).
  In `test_a_sound_alike_is_listed_and_builds_its_parents_sound` the closing list becomes
  `list(BOWED_SOUND_ALIKE_PARENTS) + list(PLUCKED_SOUND_ALIKE_PARENTS) + …`, and its comment
  names bowed strings first. Add:
```python
# Entries that imitate a feature the engine lacks (sympathetic strings by a detuned copy, a
# buzzing bridge by drive). They predate decision 4 and stay, but nothing new shares their
# sound: batch 4's sitar ruling, and batch 7's for the bowed ones
APPROXIMATING_NAMES = frozenset({
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
})


def test_no_sound_alike_shares_an_approximated_sound():
    """No sound-alike takes the build of an entry that imitates a missing engine feature."""
    parents = {catalog_entry.sounds_like for catalog_entry in instruments.entries()}
    assert parents & APPROXIMATING_NAMES == set()
    assert APPROXIMATING_NAMES <= set(instruments.names())
```

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or approximated" -v`
  Expected: PASS, with IDs `[bowed strings]`, `[plucked strings]`, `[electronic]` and
  `[tuned percussion]`. (These are guards: they pass now and hold the later tasks.)

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move
  `strings.py`'s "Bowed strings" section into `bowed_strings.py` unchanged; its module docstring
  takes `strings.py`'s bowed sentences (the Helmholtz sawtooth, bow noise, Adler's ranges),
  says what the family holds and that the sound-alikes are in `bowed_sound_alikes.py`.
  `strings.py`'s docstring keeps the rest and names both sibling modules. Imports only the
  section used leave `strings.py`. `bowed_sound_alikes.py` gets an empty table and a docstring
  quoting the owner as `tuned_sound_alikes.py`'s does. Point `registry.py` at the new module and
  move the seven `CATALOG_BUILD` names in `tests/test_process_state_guard.py`.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `family='bowed strings'` and `build/bowed-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
SKIP=replay-metrics git commit -m "Instrument catalog: bowed strings in their own module, unchanged; no sound-alike of an approximation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The European and modern bowed strings sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. A list page is a source for a name only. The
sound, the title and the range come from the instrument's own page, or from a maker, museum or
encyclopedia. The audit's "VERIFIED" rows and its quotes are leads, not sources: fetch them.

**Files:**
- Create: `plans/data/instrument-audit/batch-7.tsv`
- Create (not committed): `build/batch-7-candidates.txt`, `build/batch-7-asia-africa.txt`,
  `build/batch-7-europe.txt`, `build/batch-7-form-check.py`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `bowed-strings.md` ("Rejected or corrected
  proposed entries", "Aliases", "Range checks"); `batch-1.tsv` to `batch-6.tsv`;
  `build/batch-7-names-before.txt` (Task 1).
- Produces: `batch-7.tsv` with batch 6's header:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an
  ALIAS's target or a SOUND_ALIKE's parent. `family` is `bowed strings` on every row. Every SHIP
  or SOUND_ALIKE row is pitched: `lowest`, `highest`, `range_source`, and `notes` holding
  `Range:`. `tags` is `mechanical` on a self-playing instrument's SHIP or SOUND_ALIKE row, else
  empty. `hs` is the class the source gives (`321.…` or `31…`). Also the form check script,
  `build/batch-7-form-check.py SHEET`, which Task 4 runs.

- [ ] **Step 1: Write the candidate lists**
```bash
mkdir -p build
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /^bowed/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /bowed/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' zeze 'violano virtuoso' 'phonoliszt violina'
} | LC_ALL=C sort -u > ../../../build/batch-7-candidates.txt
cd ../../..
```
  Then write the plan's 57 half-B names, one per line, to `build/batch-7-asia-africa.txt`,
  sorted with `LC_ALL=C sort`, and `LC_ALL=C comm -23 build/batch-7-candidates.txt
  build/batch-7-asia-africa.txt > build/batch-7-europe.txt`. Run `wc -l build/batch-7-*.txt`.
  Expected: 126 candidates, 57 Asia and Africa, 69 Europe; `LC_ALL=C comm -13
  build/batch-7-candidates.txt build/batch-7-asia-africa.txt` prints nothing.

- [ ] **Step 2: Write one row per half-A candidate,** in `build/batch-7-europe.txt`'s order,
  and one per name in the audit's "Aliases" section whose target is a half-A row.

  Rules (batch 6's, with this family's changes):

  1. **SHIP** only with name, title, range and sound from fetched sources. Quote in `notes` the
     passage that describes the sound or construction and, after `Range:`, the passages that
     give the range, then its derivation under the range ruling. The `builder` cell gives the
     `_bowed`, `with_drones` or `formant_series` call, and says which values come from the
     source (strings of gut or metal, a horn, drones and their notes, a body's size relative
     to the violin's) and which are sound design.
  2. **SOUND_ALIKE** a verified instrument that rule 7 finds would sound like an existing entry
     or a SHIP row of this half. `alias_of` is its parent. `notes` begin "Sound-alike:", quote
     the source's description, and say why that entry is the nearest. It has its own range
     under the ruling. The parent is a catalog name or a SHIP row of this half, never another
     sound-alike and never one of `APPROXIMATING_NAMES` (Task 1).
  3. **ALIAS** another name for the same instrument, cited (the audit's `talharpa` and
     `jouhikko`, `viola da spalla` and `cello da spalla`). The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row. If the target waits, the row is WAIT with `waits_for` `its
     target, <name>`.
  4. **WAIT** when the identifying sound needs a feature the engine lacks (Global Constraints),
     named in `waits_for` with the source quoted: `sympathetic strings`, `a buzzing bridge`,
     `sub-audio fundamentals`, `more than four sources`, `a pitch LFO (vibrato)`, `a pitch LFO
     (portamento between notes)` and the other names listed there; or `a sourced range`, or `a
     sourced drone tuning`. The feature must be the sound the source describes, not one the
     instrument merely has. `octobass` WAITs `sub-audio fundamentals` (the spec's table).
  5. **DROP** a row that does not exist as described, belongs to another family (name it), is
     a one-off (the plan's decisions), or is already decided: in the catalog under that name
     (name the entry), an alias already (name its target), or a row of an earlier sheet (name
     the sheet and its status: `electric upright bass`, "already decided: batch-4.tsv WAIT").
     The hand-offs (`zeze`, `violano virtuoso`, `phonoliszt violina`) are decided here, not
     dropped as decided.
  6. A row the audit marks "(memory)" or "none fetched" has no sourced sound yet. Fetch the
     instrument's own page (the audit's "candidate page" is a lead). If none can be found, it
     is DROP "no fetched source describes it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family
     entry (`uv run python -I -c "from glitchygames.audio import instruments as i;
     print(i.names(family='bowed strings'))"` and the builds in `bowed_strings.py`) and every
     SHIP row above it. If no sourced trait (strings, body, drones, a horn, a bow or a wheel)
     makes it sound different, it is a SOUND_ALIKE under rule 2. A number chosen only to be
     different does not count, and a range is not a sound trait.
  8. **Duplicates in the candidates** (`talharpa` and `jouhikko`, `violotta` and `alto
     violin`, `organistrum` and `symphonia`): one row decides the instrument; the other is ALIAS
     when a person would type that name, else DROP "the audit's name for <row>". A name with
     parentheses or a reordered word gets a valid `name` (`fences`, `cretan lyra`) and keeps the
     original in `audit_name`.

- [ ] **Step 3: Write and run the form check.** Write `build/batch-7-form-check.py`:
```python
"""Batch 7's sheet form check: python -I build/batch-7-form-check.py SHEET."""

import csv
import re
import sys

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note

STATUSES = ('SHIP', 'SOUND_ALIKE', 'WAIT', 'ALIAS', 'DROP')
APPROXIMATING_NAMES = {
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
}
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
with open('build/batch-7-names-before.txt', encoding='utf-8') as before_file:
    names_before = set(before_file.read().split('\n')) - {''}
ships = {row['name'] for row in rows if row['status'] == 'SHIP'}
alikes = {row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'}
parents = ships | {
    name for name in names_before
    if name in instruments.CATALOG and instruments.entry(name).sounds_like is None
}


def held_as_this_row(row):
    """The code already holds this row (its half was coded first) as the same kind and target."""
    name = row['name']
    if row['status'] == 'ALIAS':
        return instruments.ALIASES.get(name) == row['alias_of']
    if name not in instruments.CATALOG:
        return False
    held = instruments.entry(name)
    if row['status'] == 'SOUND_ALIKE':
        return held.sounds_like == row['alias_of']
    return held.sounds_like is None and held.family == 'bowed strings'


def taken(row):
    """A name the catalog held before the batch, or that the code holds as something else."""
    name = row['name']
    if name in names_before:
        return True
    in_code = name in instruments.CATALOG or name in instruments.ALIASES
    return in_code and not held_as_this_row(row)


def ranged(row):
    try:
        lowest, highest = Note(row['lowest']).midi_number, Note(row['highest']).midi_number
    except Exception:
        return False
    return (
        row['range_source'].startswith('http')
        and 'Range:' in row['notes']
        and Note('A0').midi_number <= lowest < highest <= Note('C8').midi_number
    )


names = [row['name'] for row in rows]
bad = [row['name'] for row in rows if not pattern.fullmatch(row['name'])
       or row['status'] not in STATUSES
       or row['family'] != 'bowed strings'
       or not row['audit_name'] or not row['hs'][:1].isdigit()
       or row['tags'] not in {'', 'mechanical'}
       or (row['tags'] and row['status'] not in {'SHIP', 'SOUND_ALIKE'})
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)))
       or (row['status'] in {'SHIP', 'SOUND_ALIKE', 'ALIAS'} and taken(row))
       or (row['status'] == 'SOUND_ALIKE'
           and (row['alias_of'] not in parents or row['alias_of'] in APPROXIMATING_NAMES))
       or (row['status'] == 'WAIT' and not row['waits_for'])
       or (row['status'] == 'ALIAS'
           and row['alias_of'] not in parents | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {status: sum(row['status'] == status for row in rows) for status in STATUSES})
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  Run: `uv run python -I build/batch-7-form-check.py plans/data/instrument-audit/batch-7.tsv`
  Expected: the counts, then `bad: []`, exit 0. (Read the sheet with the csv module: batch 5
  found CSV-quoted cells.)

- [ ] **Step 4: Check the half**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-7.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = {r['audit_name'].lower() for r in rows}
europe = set(open('build/batch-7-europe.txt', encoding='utf-8').read().split('\n')) - {''}
asia_africa = set(open('build/batch-7-asia-africa.txt', encoding='utf-8').read().split('\n')) - {''}
print('missing:', sorted(europe - audit_names)); print('from half B:', sorted(asia_africa & audit_names))
"
```
  Expected: `missing: []` and `from half B: []`.

- [ ] **Step 5: Commit**
```bash
git add plans/data/instrument-audit/batch-7.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 7's verification sheet, the European and modern bowed strings" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The European and modern bowed strings

**Files:**
- Modify: `bowed_strings.py` (new builds after the 27), `bowed_sound_alikes.py`, `aliases.py`
  (each ALIAS row with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-7.tsv` as Task 2 left it (half A only); Task 1's lists.
- Produces: `NEW_BOWED_NAMES` and `BOWED_SOUND_ALIKE_PARENTS` with this half's rows, which
  Task 5 extends.

- [ ] **Step 1: Write the failing tests:** fill `NEW_BOWED_NAMES` with one name per SHIP row,
  in the sheet's order; `BOWED_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row;
  add the ALIAS rows to `test_the_batch_aliases_resolve`'s parameters; a `mechanical` row's
  name joins the tuple `test_plucked_idiophones_hold_the_lamellophones_and_music_boxes` pins
  (`instruments.names(tag=Tag.MECHANICAL) == ('music box',)`), in catalog order (bowed strings
  come before plucked idiophones). A new entry that does not repeat at its note's period (a
  drone build) goes in `NOT_PERIODIC_AT_THE_NOTE` with its reason, as `synth bass` does.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or tag" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries.** One per SHIP row, in the sheet's order, after the 27.
  Above each, a comment with its `sound_source` and `range_source` URLs, the quoted traits it is
  built from and the range's derivation, marking the values that are sound design. SOUND_ALIKE
  rows go in `bowed_sound_alikes.py`, each with a source comment and its own range,
  `tags=frozenset({Tag.MECHANICAL})` where the sheet says `mechanical`. A builder new to the
  family (a drone build, a horn's formants) gets its own test of the trait it exists for, as
  batch 2's `test_the_pianet_settles_from_a_bright_strike` does: for drones, that the drone
  sources sound at their sourced hertz whatever note is played.

- [ ] **Step 4: Run the suite and check the code against the sheet**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` for every new
  entry. A render failure at a range end is a finding about the range or the build: check it
  against the source, never trim the range to pass. Then:
```bash
uv run python -I -c "
import csv
from glitchygames.audio import instruments
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-7.tsv', encoding='utf-8'), delimiter='\t'))
for r in rows:
    if r['status'] in {'SHIP', 'SOUND_ALIKE'}:
        e = instruments.entry(r['name'])
        assert (e.family, e.lowest, e.highest) == ('bowed strings', r['lowest'], r['highest']), r['name']
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
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 7's European and modern bowed strings, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The bowed strings of Asia and Africa sheet (half B)

Research, as in Task 2. This task may start as soon as Task 1 is committed, alongside Task 2:
it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-7-asia-africa.tsv` (half B's rows, with the sheet's
  header)
- Modify: `plans/data/instrument-audit/batch-7.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8, header and `build/batch-7-form-check.py`;
  `build/batch-7-asia-africa.txt` (if missing, rerun Task 2 Step 1; if the form check is
  missing, write it from Task 2 Step 3).
- Produces: the sheet's remaining rows, read by Task 5.

Every half-B candidate gets a row, in `build/batch-7-asia-africa.txt`'s order, plus one per
remaining name in the audit's "Aliases" section. A parent or alias target is a catalog name or
a SHIP or SOUND_ALIKE row of this half, never a half-A row. Rules for this half, in addition to
Task 2's:

- **Huqins and spike fiddles.** A two-string spike fiddle that a source relates to an existing
  entry (`erhu`, `kemenche`, `morin khuur`) and sets apart by nothing sourced is that entry's
  SOUND_ALIKE, with its own range under the ruling. A size the source names as a register of
  another (`gaohu`, `zhonghu`, `dihu`, `diyingehu`) is a SOUND_ALIKE of the entry nearest in
  register that its source relates it to. A metal resonator or a horn (`zhuihu`, `tar
  shehnai`) is a sound trait only when the source describes it.
- **Sympathetic strings.** `dilruba`, `esraj`, `taus`, `kamaicha`, `sarangi nepali` and the
  other Indian fiddles WAIT `sympathetic strings` where their fetched source names them; never
  a sound-alike of `sarangi` (Task 1's test).
- **Earlier decisions.** `zeze` is batch 4's DROP "bowed strings": decided here. The audit's
  "Range checks" quote the Indonesian tunings without octaves (`sukong`, `tehyan`,
  `kongahyan`): WAIT `a sourced range` unless a fetched source gives the octave.

- [ ] **Step 1: Write half B's rows** to `build/batch-7-asia-africa.tsv`, and check them alone.
  Run: `uv run python -I build/batch-7-form-check.py build/batch-7-asia-africa.tsv`
  Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-7-asia-africa.tsv >> plans/data/instrument-audit/batch-7.tsv`.
  Run Task 2 Step 3's form check on the whole sheet.
  Expected: the counts, then `bad: []`, exit 0, with half A's coded rows (if Task 3 has run)
  accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 2 Step 4's command
  with `europe | asia_africa` in place of `europe` on the `missing:` line, and print
  `'extra:', sorted(audit_names - europe - asia_africa)` instead of the half-B line.
  Expected: `missing: []`; `extra:` lists only the alias-section rows (their alias is their
  `audit_name`).

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-7.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 7's verification sheet, the bowed strings of Asia and Africa" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The bowed strings of Asia and Africa

**Files:**
- Modify: `bowed_strings.py`, `bowed_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-7.tsv`'s half-B rows; Task 3's lists.
- Produces: the finished family.

- [ ] **Step 1: Write the failing tests:** append this half's rows to the lists as in Task 3
  Step 1.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes.

- [ ] **Step 4: Run the suite and check the code against the sheet.** Run Task 3 Step 4's
  commands (the second now checks every row). Expected: PASS, then `matches N rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 7's bowed strings of Asia and Africa, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py` (the docstring: a bowed strings
  paragraph with its count, `bowed_strings.py` and `bowed_sound_alikes.py` named, examples)
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the bowed strings
  row's count and examples, the sound-alike modules sentence and total)
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts)
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 7
  done, pointing at this plan and `batch-7.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70: heading "BATCH 7 DONE"; batch 7 done, with the
  sheet's counts by status and the family's growth; the audit's unclosed gaps as a later pass;
  `viola organista` decided here (the keyboards batch must not decide it again); a "Plan (batch
  7)" line; the Status line; and the next batch named: voices and choirs. Add #77 (the highest
  item is #76), "Sound Engine: The Owner's Checks on Instrument Catalog Batch 7 — TODO", in
  #76's form, placed after #76, its Priority "(before the voices and choirs batch builds on the
  same catalog)". **Listen** (`build/instruments/bowed strings/`): the new builds, then the
  sound-alikes under their parents. **Calls to confirm**:
  - every WAIT, by reason;
  - the range ruling (lowest open string of the standard tuning; a stated highest note,
    compass or exact span; open strings and hedged spans are no range; nothing below A0), and
    every derived range;
  - the approximating entries (`sarangi`, `hardanger fiddle`, `viola d amore`, `nyckelharpa`,
    `hurdy gurdy`) left unchanged and refused as parents, and the reading of `hurdy gurdy`'s
    `drive` as its buzzing bridge;
  - the drone ruling (`with_drones` at sourced pitches, else `a sourced drone tuning`);
  - the moving-pitch ruling;
  - the mechanical and keyed instruments decided here (`violano virtuoso`, `phonoliszt
    violina`, `viola organista`, `geigenwerk`);
  - sizes as sound-alikes of the nearest existing entry their source relates them to;
  - the one-offs dropped;
  - the earlier sheets' rows left as decided (`electric upright bass`) and the hand-offs
    decided here (`zeze`);
  - the module move (`bowed_strings.py`, `strings.py` keeping harps and struck strings);
  - the two-half split by tradition, and the two sheets researched in parallel;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make
    yet".

  Then **Bugs to report** (anything found while building, none fixed here) and **Follow-ups**
  (the audit's gaps; ranging the range WAITs from maker and museum sources; the stray CSV
  quoting, if the sheet has it).
- Fix any doc line the counts make stale; write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(i.names(tag='mechanical'))"`
  and `uv run python -I build/batch-7-form-check.py plans/data/instrument-audit/batch-7.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

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
  `build/instruments/bowed strings` folder is the one to listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 7 of the instrument catalog (bowed strings), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch
in turn and stack them into PRs"), never without it. The pre-push hooks take about 40 minutes,
and nothing in the working tree may change while they run.
