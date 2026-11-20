# Instrument catalog batch 9 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the flutes family from the audits' candidates. The family holds the edge-blown
aerophones (Hornbostel–Sachs 421: transverse, end-blown, duct, vessel and panpipe flutes) and,
by the spec's boundary calls, duck calls, signal whistles and the hydraulophone. Each instrument
gets a cited source and either sounds unlike every other entry or is a listed sound-alike of the
one it sounds like. The rest become aliases, wait for an engine feature or a sourced range, or
are dropped with a reason.

**Architecture:** As in batches 3 to 8, a verification sheet (`batch-9.tsv`) decides every
candidate before any code is written. The family's 30 entries live in `winds.py` (811 lines,
which also holds clarinets, saxophones, double reeds, bagpipes and free reeds), so they move
unchanged to a new `flutes.py`, as batch 7 moved bowed strings out of `strings.py`. Its table
becomes `_FLUTE_BUILDS + FLUTE_SOUND_ALIKES`, with the sound-alikes in a new
`flute_sound_alikes.py`. The family may gain unpitched entries (a whistle that its source calls
noise), so the batch table's row names them in `FLUTE_UNPITCHED_NAMES`, as batch 6's electronic
row does. The two recorder titles that the spec's audit findings call ambiguous state their key.
The sheet and the code each come in two halves, split by an explicit list: the European,
orchestral and modern flutes with the whistles and calls, then the traditional flutes of Asia,
Africa, the Americas and Oceania with every panpipe. The two sheet halves are researched at the
same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `falling_series`,
`with_drones`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all). Batch 8's plan (`plans/2026-11-12-instrument-catalog-batch-8-implementation.md`)
is this plan's template. Batch 7's (`plans/2026-11-12-instrument-catalog-batch-7-implementation.md`)
holds the module move, `APPROXIMATING_NAMES` and the drone ruling, and batch 4's
(`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) the pitched sound-alike and
strict range rules and the before-and-after build record. This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-9-implementation.md`. The branch is
`feat/instrument-catalog-batch-9`, made from `feat/instrument-catalog-batch-8` (HEAD
`cfa668eb`). The candidates come from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` starts with `flutes` (96): the round-2 audit `flutes.md`'s
  94, and `hydraulophone` and `pigeon whistle` from `new-environmental-instruments.md`;
- the `round-1/merged-missing.tsv` rows whose `family` contains `flute` (19, `hydraulophone`
  among them: `subcontrabass flute`, `double contrabass flute`, `koauau`, `nguru`, `ryuteki`,
  `nohkan`, `shinobue`, `daegeum`, `suling`, `fujara`, `gemshorn`, `slide whistle`, `nose
  flute`, `aztec death whistle`, `blown bottle`, `putorino`, `ringflute`, `clackamore`);
- six hand-offs that no family has decided. `steam whistle`, `boatswains call`, `pea whistle`
  and `duck call` are round-1 rows in the proposed noise makers family, and
  `missing-categories.md` sends them here ("steam whistle, boatswains call, pea whistle, duck
  call -> flutes"), as does the spec ("duck calls and signal whistles go in flutes"). `bird
  whistle` is `batch-2.tsv`'s DROP "Edge-blown, so flutes, not sound effects". `singing bird box`
  is a `merged.tsv` row in the mechanical instruments family, which the spec makes a tag ("Each
  stays in the family it sounds like"): a bird whistle in a box.

Together: **119 unique candidate names** (counted for this plan; Task 3 Step 1 recounts). None
is in the catalog or the alias table today. The flutes audit's "Aliases" section proposes 24
names, one per line, and the environmental audit's proposes 3 for the pigeon whistle (`gezi
shao`, `geling`, `geshao`): **27 alias names**, so the sheet will hold 146 rows.
`plans/future-features.md` #70–#78 leave nothing else for this family. No earlier sheet decided
a candidate: `bird whistle` was dropped to this family, not decided.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, hyphens and parentheses go only in the title (`flute d
  amour`, title `Flûte d'amour`; `jula jula` for the audit's `jula-jula`).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families).
  The boundary calls bind: "duck calls and signal whistles go in flutes (they are edge-blown)
  … the hydraulophone goes in flutes (Hornbostel–Sachs gives it no class)". The kazoo is
  voices', and batch 8 decided it.
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict").
  This plan's range ruling for flutes is below, under "Decisions". A row with no sourced range
  is WAIT, `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the
  same instrument) stays an alias." A sound-alike is pitched exactly when its parent is, and a
  pitched sound-alike gives its own sourced range (batch 4). A parent may be in another family
  (batch 7), when the row's source relates them.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as
  an approximation, under its real name or a qualified one. The spec's table names no flute,
  but its row "moving formants, vowel glides, vibrato | overtone and throat singing" binds a
  flute played with throat singing, and "sub-audio fundamentals" binds a flute pitched below
  A0. Earlier batches added the other names a WAIT may give: a pitch LFO (vibrato), a pitch LFO
  (portamento between notes), an amplitude LFO, filter resonance, a filter envelope, more than
  four sources, moving formants (batch 6); a buzzing membrane (batch 5); a sourced drone tuning
  and its own build (batch 7). What the engine has: up to four `Source`s, each with its own
  semitones, detune and fixed pitch (`with_drones`: fixed-pitch drones under every note,
  keeping only the `tone` and `breath` sources); one glide per note (`pitch_curve`); a fixed FIR
  low or high pass; `drive` 0–20; and the family's `_flute` shape (a falling series of 10
  harmonics, its slope, the even harmonics' level, breath noise and its low pass, the attack, a
  chorus copy). It has no LFO of any kind.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not
  builds.
- Reuse the family's six shapes (`METAL_FLUTE`, `WOODEN_FLUTE`, `RECORDER`, `WHISTLE`,
  `END_BLOWN`, `VESSEL`, all `_flute` partials) and the shared `blown` and `with_drones`. Add a
  shape only for a genuinely new sound, and give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the
  sheet is verbatim from a page the worker fetched. No request carries the owner's email or any
  personal data, in a header, a URL or a payload (#78, "Incidents and process").
- The 30 entries already in the family keep their names, ranges, builds and order, and all but
  two keep their titles. The exception is Task 2's two recorder titles, on the spec's own
  finding. New entries come after the 30. Any other existing entry changes only for a cited
  bug, reported to the owner.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown
  by a test, you should understand why it's happening and be concerned": a warning is a
  finding, and it must be understood before going on.
- Commits as batches 4 to 8: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this
  plan, never from memory. Write no `.md` file beyond those Task 7 names.

## Review Focus

1. **A membrane flute shipped as a copy of the plain `dizi`.** The audit offers `qudi` and
   `bangdi` as "dizi, lower pitch" and "dizi, higher pitch", and `daegeum`, `khlui` and `sao
   truc` have membranes too. The catalog's `dizi` is `METAL_FLUTE`, the piccolo's build, with no
   buzz, though its page says the membrane gives "the final tone a buzzing, nasal quality". A
   sound-alike of it would ship that omission under a new name. Task 1 adds `dizi` to
   `APPROXIMATING_NAMES`, so the test and the form check refuse it as a parent. Rule 4 makes a
   flute whose source names its membrane's buzz WAIT `a buzzing membrane`.
2. **A key-specific, written or letter-only range read as the instrument's range.** Shinobue,
   bansuri, quena and Native American flutes are made in many keys. Recorder music is written an
   octave below its sound. The ocarina page gives widths with no pitches, and the hydraulophone
   page gives letters with no octaves. The range ruling refuses all four. The form check requires
   a `Range:` passage on every pitched row, and the code check compares every range with the
   sheet.
3. **A size beyond the catalog's floor or top.** The hyperbass flute sits four octaves below
   the concert flute, and the subcontrabass recorder (F1) and double contrabass flute (C1) are
   near A0. The garklein recorder and the whistles are near C8. The form check refuses a range
   below A0 or above C8, and the range ruling makes such a row WAIT. The render and pitch tests
   play every range's ends: a quiet or wrong note there is a finding about the range or the
   build, and the range is never trimmed to pass.
4. **A device's moving sound shipped as a static flute.** The slide whistle's glide, the pea
   whistle's trill, the warble of the water whistle, bird whistle and singing bird box, the
   whistling vessel's glide, and the throat-sung tsuur cannot be made without an LFO, a glide
   between notes or moving formants. Task 1's test refuses the slide whistle and its alias
   names in the catalog, and the form check refuses them as SHIP or SOUND_ALIKE. Rule 4 holds the
   rest to their source's words.
5. **A candidate decided in the wrong family or twice.** The duck call is a reed call by the
   noise makers audit and edge-blown by the spec. The steam whistle sounds in the organs'
   `calliope`. `serinette` and `flute clock` are barrel organs that the mechanical audit rows.
   The hand-offs are decided here and nowhere else: the duck call stays in flutes (decision 2),
   with any conflict in #79. A steam whistle may be a sound-alike of `calliope` across families.
   Task 7 tells #70 that the organs batch decides `serinette` and `flute clock`. The form check
   refuses a SHIP, SOUND_ALIKE or ALIAS row whose name the catalog or alias table held before
   this batch.

---

## File Structure

- Create `src/glitchygames/audio/instruments/flutes.py`. It takes the "Flutes" section of
  `winds.py` (`_flute`, the six shapes, the 30 entries), unchanged, as `_FLUTE_BUILDS`. New
  builds go after the 30, and `FLUTES = _FLUTE_BUILDS + FLUTE_SOUND_ALIKES`.
- Create `src/glitchygames/audio/instruments/flute_sound_alikes.py`, holding `FLUTE_SOUND_ALIKES`.
- Modify `winds.py` (the section and its flute sentences leave; it keeps the five reed
  families), `registry.py` (it imports `FLUTES` from `flutes.py`; its first place in
  `FAMILY_TABLES` doesn't change), and `aliases.py` (the batch's ALIAS rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 2, 4 and 6) and
  `tests/test_process_state_guard.py`. In the guard, the six `CATALOG_BUILD` names move from
  `'audio/instruments/winds.py'` to `'audio/instruments/flutes.py'`, any new shape joins them,
  and `FREE_REED_LEVELS` stays under `winds.py`.
- Create `plans/data/instrument-audit/batch-9.tsv` (Tasks 3 and 5).
- Docs (Task 7): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #79), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #79):

- **Flutes get their own module.** `winds.py` holds six families, and later batches grow five of
  them (clarinets, saxophones, double reeds, bagpipes, free reeds). Batches 4, 6 and 7 gave each
  family they grew a module of its own, with a sibling sound-alikes module that names it ("The
  family's builds are in …"). Batch 8 did not split, but only because `voices.py` held exactly
  the two families it grew. Moving the flutes leaves `winds.py` with the five reed families,
  which their own batches can move the same way. No other module imports the flute shapes. The
  move is mechanical, and Task 1's before-and-after record checks it.
- **The recorder sizes keep one naming, and the two ambiguous titles state their key.** The
  spec's audit findings: "The recorder sizes follow one naming (great bass C3, contrabass F2,
  the Paetzold/Mollenhauer convention); a second 'great bass in F' exists elsewhere. Not a bug,
  but the titles could state the lowest note to remove the ambiguity." The other convention's
  great bass is this catalog's contrabass, so neither title alone tells the size. Task 2 retitles
  `great bass recorder` to "Great bass recorder in C" and `contrabass recorder` to "Contrabass
  recorder in F". It changes no name, range or build, and it follows the family's own titles
  ("Alto flute in G", "Tin whistle in D"). The retitle needs a maker's page that names those
  sizes by those keys, cited in a comment. Without one, Task 2 is skipped by ruling and the
  finding goes to #79. A new recorder size is named in the same convention as the recorder
  page's table (`subgreat bass recorder` C2, `subcontrabass recorder` F1), and its title states
  its key. A name from the other convention (a "great bass in F", a "contrabass in C") is never
  an alias, because here it would read as another size: DROP "the other naming convention's
  name for <entry>; it names another size in this catalog". Any recorder or concert-flute size
  that ships joins its chain in `test_sized_families_descend_from_highest_to_lowest`, in
  descending order.
- **Range ruling for flutes.** A sourced range is the lowest and highest sounding notes that a
  fetched source states for the instrument:
  1. *Stated*: the source gives both notes as the range or compass, in note names with octaves
     (scientific `C4`, Helmholtz `c'`, or a named note whose octave the source fixes). Or it
     gives the lowest note and an exact span above it ("two octaves and a tone"), as batch 7
     allowed.
  2. *Sounding*: a range in written pitch counts only when the same source states the
     transposition (a recorder or piccolo sounding an octave above written, a flute in G a
     fourth below). The derivation shows the arithmetic. Otherwise the row WAITs.
  3. *Not a range*: a hedged span ("about", "approximately", "usually up to", "can reach"),
     extremes ("advanced players", "possible altissimo"), a width with no pitches (the ocarina
     page's "an octave plus a fourth"), note letters with no octaves (the hydraulophone page's
     "A to E"), or a tessitura.
  4. *Several keys or sizes*: the key or size that the source calls standard, usual or most
     common, from that source or a maker's model page in that key. With none so called, the row
     WAITs (batch 7's rule for several tunings).
  5. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached);
     a maker's catalogue or model page (Yamaha, Powell, Mollenhauer, Moeck, Kunath/Paetzold,
     Kingma and the like); a museum's object record (MIMO, the Met, the Horniman); or a
     conservatory reference. A retailer's listing, a blog or a forum is not a source. A range is
     never taken from a sibling size, the parent or the audit.
  6. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`, the spec's name) and
     nothing above C8, the piano's top and the form check's (WAIT `a range above C8`, a name
     Task 7 lists in #79 if any row uses it).
  7. *One-note pipes*: a pipe that sounds one note has no range of its own (the catalog needs
     lowest below highest). A set that one player plays is one instrument, ranged by the set's
     stated lowest and highest notes. A set shared among players in hocket (the audit's
     `embilta`, `tshikona pipes`, `nyanga panpipes`) is DROP "an ensemble of one-note pipes
     played in hocket, not one instrument", unless a source describes one player playing the set.
  Every pitched row's `notes` holds `Range:` and the quoted passages, then the derivation.
- **Approximating entries are never parents, and `dizi` is one.** The dizi page (fetched for
  this plan, https://en.wikipedia.org/wiki/Dizi_(instrument)) says the membrane-covered hole
  makes the dizi "brighter and louder, and adding harmonics to give the final tone a buzzing,
  nasal quality". The catalog's `dizi` has no buzz, so it omits the sound its source names, as
  batch 7's `sarangi` imitates sympathetic strings with a detuned copy. It predates decision 4
  and stays, but it joins `APPROXIMATING_NAMES`, and #79 reports it as a bug. A flute whose
  fetched source names a membrane's buzz as its sound WAITs `a buzzing membrane` (batch 5's
  `gyil` reason). One whose source says it has no membrane today (the audit says so of
  `junggeum` and `sogeum`) is ranged and built like any other flute.
- **A moving sound waits, by what makes it move** (batch 4's đàn bầu ruling, batch 7's
  moving-pitch ruling). A slide or glide between notes that the source names as the
  instrument's sound (the slide whistle's piston, a whistling vessel's glide) WAITs `a pitch LFO
  (portamento between notes)`. A warble or trill that the device itself makes (the pea in a pea
  whistle, the water in a water whistle) WAITs `a pitch LFO (vibrato)` or `an amplitude LFO`, as
  the source describes it. A trill or vibrato that any player may add is technique, not the
  instrument's sound. The slide whistle's whole identity is its glide, so this plan decides it
  now: `slide whistle` and its alias names (`swanee whistle`, `lotus flute`, `piston flute`,
  `jazz flute`) are `PORTAMENTO_NAMES`, refused by Task 1's test and the form check. The alias
  rows WAIT `its target, slide whistle`.
- **A flute with a voice or a drone.** A flute whose source names the player's throat or
  overtone singing sounding with it (the audit's `tsuur`, `fulani flute`) WAITs `moving
  formants`, the spec's row for "overtone and throat singing". One with a hummed or sung voice
  that is not throat singing WAITs `its own build`. A double flute whose second pipe is a drone
  is built with `with_drones` at the drone pitch its source gives in a note name with an octave.
  With no sourced pitch it WAITs `a sourced drone tuning` (batch 7's drone ruling), and a drone
  build joins `NOT_PERIODIC_AT_THE_NOTE` with its reason. A double flute whose two pipes each
  play a melody is played as two notes of a sequence. Its sound is one pipe's: it is that pipe's
  SOUND_ALIKE or build, and the notes say so.
- **Overtone flutes are flutes.** Playing on the harmonic series (the audit's "harmonic
  snapping" for `fujara`, `koncovka`, `kalyuka`, `willow flute`, `tilinca`) decides which notes
  are played, not the sound. Such a flute is ranged and built like any other. Its range is the
  stated lowest and highest notes, never a range derived from its length.
- **A new shape only for a sourced acoustic trait.** A shape is new when a fetched source names a
  trait that none of the six shapes has, such as a stopped pipe's odd harmonics. Its own test
  checks that trait, as batch 2's `test_the_pianet_settles_from_a_bright_strike` checks its own.
  Its other numbers are sound design, marked so in the comment. Every stopped-pipe flute in the
  candidates (the panpipes, `koauau`, `nguru`) is in half B, so only half B may add a stopped-pipe
  shape. Half A may add a shape only for a trait that no half-B row names. A shape is a
  module-level `partial` in `flutes.py` beside the six, and the guard gets a `CATALOG_BUILD` line
  for it.
- **Unpitched flutes.** A whistle that its fetched source describes as noise with no pitch (the
  audit says this of the `aztec death whistle`) is an unpitched entry, with no range and its
  `notes` beginning `Unpitched.`, as batch 6 ruled. It ships only with its own build from a
  sourced trait, since a sound-alike is pitched exactly when its parent is and no flute today is
  unpitched. Otherwise it WAITs `its own build`. Its name goes in `FLUTE_UNPITCHED_NAMES`.
- **The boundary hand-offs.** The duck call is decided here under decision 2. If its fetched
  source names a reed as its sound, it WAITs `its own build`, because no flute shape makes a
  reed's buzz, and #79 records the conflict with the spec's reason "(they are edge-blown)". The
  hydraulophone is decided here, with `hs` `none` if its page gives no class. The signal
  whistles (`police whistle` and `pea whistle`, `bosuns call` and `boatswains call`, `steam
  whistle`) and the bird whistles (`bird whistle`, `bird flageolet`, `water whistle`, `singing
  bird box`, `pigeon whistle`) are decided here. A steam whistle may be a sound-alike of the
  organs' `calliope` if its source relates them. `serinette` and `flute clock` (mechanical
  audit rows) are barrel organs, so the organs batch decides them. A SHIP or SOUND_ALIKE row of a
  self-playing instrument (`singing bird box`) carries `Tag.MECHANICAL` (`tags` `mechanical`).
- **Sizes and keys are sound-alikes.** The concert flute's sizes (`eb soprano flute`, `flute d
  amour`, `subcontrabass flute`, `double contrabass flute`), the recorder sizes and the folk
  flutes in another key (`qudi` and `bangdi` aside, which have membranes) will mostly sound like
  an existing entry. Each is a SOUND_ALIKE of the existing entry nearest in register that its
  source relates it to, with its own range under the ruling, or it WAITs.
- **One-offs and unsourced rows are dropped** (batch 5's ruling): DROP "a one-off instrument,
  not a type a game would ask for". The audit suspects `ringflute` and `clackamore`. A row with
  no fetched page describing it is DROP "no fetched source describes it" (rule 6).
- **Two halves by an explicit list.** Half A, the European, orchestral and modern flutes with the
  whistles and calls, is these 47 candidates. Half B, the traditional flutes of Asia, Africa, the
  Americas and Oceania and every panpipe, is the other 72:
  `blown bottle`, `boatswains call`, `bird flageolet`, `bird whistle`, `bosuns call`,
  `clackamore`, `classical flute`, `czakan`, `double contrabass flute`, `double flageolet`,
  `double ocarina`, `duck call`, `dvojnica`, `eb soprano flute`, `flageolet`, `floyera`,
  `fluier`, `flute d amour`, `flutophone`, `frula`, `fujara`, `garklein recorder`, `gemshorn`,
  `hydraulophone`, `hyperbass flute`, `kalyuka`, `koncovka`, `pea whistle`, `police whistle`,
  `renaissance flute`, `ringflute`, `singing bird box`, `sixth flute`, `slide whistle`,
  `sopilka`, `soprano ocarina`, `steam whistle`, `subcontrabass flute`, `subcontrabass
  recorder`, `subgreat bass recorder`, `tabor pipe`, `tenor ocarina`, `tilinca`, `tonette`,
  `voice flute`, `water whistle`, `willow flute`.
  The 27 alias names go with their target's half. Half A has the 5 for the slide whistle and
  the tin whistle (`swanee whistle`, `lotus flute`, `piston flute`, `jazz flute`, `penny
  whistle`). Half B has the other 22: the nose flute's 7, `bulalri`, `hun`, `tsuchibue`, the
  siku's 3, the pan flute's 3 (`nai`, `kuvytsi`, `syrinx`), `xipro`, `siyotanka`, `venu` and the
  pigeon whistle's 3. The candidates' duplicates fall within one half: `police whistle` with
  `pea whistle` and `bosuns call` with `boatswains call` in A, and `nose flute`, `koauau` and
  `koauau ponga ihu` in B.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the
  batch, or a SHIP row of the same half, and never a row of the other half. So Task 5 needs
  nothing from Task 3. Half B drafts to a build file, which is appended to the sheet once half A
  is committed. The form check accepts a row that the code already holds with the same target or
  parent (batch 7's lesson).
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task's Steps 1–3 and 5 are skipped and only its code check
  runs, which must still pass (every WAIT and DROP name absent from the catalog). Task 7 records
  the skip in #79, as batch 8 recorded its Task 5.
- **Out of scope:** the audit's "Gaps you could not close" (MIMO, the Met, the Horniman and Grove
  unconsulted; `List_of_flutes` unresolved; the suspected `satara`, `jodi pava`, `pulangkuzhal`,
  the Persian ney sizes, `kiz neyi`, `sring`, `shoor`, `choor`, `shembeko`, `suling degung`,
  Korean `ji`, Chinese `yue`, `koudi`, `pfeife`, `piffero`, `txistu`, `galoubet`, `flabiol`,
  `tubulum`, keyboard-flute hybrids, and bamboo flute sizes by key). Task 7 lists them in #70 for
  a later pass.

---

### Before the tasks: the controller records the names before the batch

The controller runs this once, before dispatching anything, so that Tasks 1, 3 and 5 can start
together:
```bash
mkdir -p build
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-9-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
Expected: `names before 765` (685 entries and 80 aliases).

---

### Task 1: Flutes in their own module, unchanged; the batch table's row; no sound-alike of `dizi`; no slide whistle

**Files:**
- Create: `src/glitchygames/audio/instruments/flutes.py`,
  `src/glitchygames/audio/instruments/flute_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/winds.py`, `registry.py`,
  `tests/test_process_state_guard.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `FLUTES: Final[tuple[CatalogEntry, ...]] = _FLUTE_BUILDS + FLUTE_SOUND_ALIKES` in
  `flutes.py`, with `_flute` and `METAL_FLUTE`, `WOODEN_FLUTE`, `RECORDER`, `WHISTLE`,
  `END_BLOWN` and `VESSEL` there under their current names. `FLUTE_SOUND_ALIKES:
  Final[tuple[CatalogEntry, ...]]` is empty. The test file gains `EXISTING_FLUTE_NAMES:
  frozenset[str]` (the 30); `NEW_FLUTE_NAMES: list[str]`, `FLUTE_SOUND_ALIKE_PARENTS: dict[str,
  str]` and `FLUTE_UNPITCHED_NAMES: frozenset[str]`, all empty here, for Tasks 4 and 6 to fill;
  `PORTAMENTO_NAMES: frozenset[str]`; `'dizi'` in `APPROXIMATING_NAMES`; and the row
  `Family.FLUTES: BatchFamily(EXISTING_FLUTE_NAMES, NEW_FLUTE_NAMES, FLUTE_SOUND_ALIKE_PARENTS,
  FLUTE_UNPITCHED_NAMES)` in `BATCH_FAMILIES`. Also `build/flute-builds-before.txt`.

- [ ] **Step 1: Record the family's builds.** Run batch 4's Task 1 Step 1 command with
  `family='flutes'` and `build/flute-builds-before.txt`. Expected: `recorded 30`.

- [ ] **Step 2: Write the tests.** Above the bowed names, add `EXISTING_FLUTE_NAMES` (the 30
  names, one per line, with the comment "# The 30 flutes that predate batch 9: their shared
  builds predate the anti-goal rule"), then `NEW_FLUTE_NAMES: list[str] = []`,
  `FLUTE_SOUND_ALIKE_PARENTS: dict[str, str] = {}` and `FLUTE_UNPITCHED_NAMES: frozenset[str] =
  frozenset()`, each commented as batch 8's lists are. Put the flutes row first in
  `BATCH_FAMILIES`, which is table order. In `test_a_sound_alike_is_listed_and_builds_its_parents_sound`,
  the closing list begins with `list(FLUTE_SOUND_ALIKE_PARENTS) +`, and its comment begins
  "flutes, bowed strings, …". Add `'dizi'` to `APPROXIMATING_NAMES` on a line of its own, and
  extend its comment: "…, batch 7's for the bowed ones, and batch 9's for the dizi, built without
  the membrane its page names (https://en.wikipedia.org/wiki/Dizi_(instrument): 'adding harmonics
  to give the final tone a buzzing, nasal quality')". After `test_nothing_waiting_for_moving_formants_is_listed`,
  add:
```python
# The slide whistle's sound is its glide between notes, which the engine cannot make (it has one
# glide per note and no LFO): it and its names wait for a pitch LFO (portamento between notes),
# batch 4's dan bau ruling, under its name, a qualified name or an alias (decision 4; batch 9)
PORTAMENTO_NAMES = frozenset({
    'slide whistle',
    'swanee whistle',
    'lotus flute',
    'piston flute',
    'jazz flute',
})


def test_nothing_waiting_for_a_glide_between_notes_is_listed():
    """No catalog name or alias is an instrument held back for a glide between notes."""
    assert PORTAMENTO_NAMES & set(instruments.names()) == set()
    assert PORTAMENTO_NAMES & set(instruments.ALIASES) == set()
```

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or approximated or moving_formants or glide_between" -v`
  Expected: PASS, with the ID `[flutes]` first. These are guards: they pass now and hold the
  later tasks.

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move `winds.py`'s
  "Flutes" section into `flutes.py` unchanged, with the tuple renamed `_FLUTE_BUILDS`, and define
  `FLUTES` as the concatenation. The new module docstring takes `winds.py`'s flute sentences
  (sounding pitch, Adler and the Vienna Symphonic Library, "a flute is nearly pure with breath").
  It says what the family holds, including the spec's boundary calls, and that the sound-alikes
  are in `flute_sound_alikes.py`. `winds.py`'s docstring keeps the rest, drops "flutes" from its
  first line, and names `flutes.py`. Its imports stay as long as the reed families use them.
  `flute_sound_alikes.py` gets the empty table and a docstring quoting the owner, as
  `bowed_sound_alikes.py`'s does, ending "The family's builds are in ``flutes.py``." Point
  `registry.py` at the new module, and move the six `CATALOG_BUILD` names in
  `tests/test_process_state_guard.py`. If the guard then asks for an entry for `_FLUTE_BUILDS` or
  `FLUTES`, that is a finding: read why before writing any reason.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `family='flutes'` and `build/flute-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
SKIP=replay-metrics git commit -m "Instrument catalog: flutes in their own module, unchanged; no sound-alike of the dizi, no slide whistle" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The two ambiguous recorder titles state their key

Follows Task 1, since it edits the moved table. Research as in Task 3.

**Files:**
- Modify: `src/glitchygames/audio/instruments/flutes.py` (two titles and a source comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: Task 1's `flutes.py`.
- Produces: the titles "Great bass recorder in C" and "Contrabass recorder in F".

- [ ] **Step 1: Find the source.** Fetch a maker's page (Mollenhauer, or Kunath for Paetzold)
  that names a great bass recorder in C and a contrabass recorder in F. If none does, stop: skip
  this task by ruling, and give the controller the pages tried for #79.

- [ ] **Step 2: Write the failing test.** After `test_sized_families_descend_from_highest_to_lowest`:
```python
def test_the_great_bass_and_contrabass_recorders_state_their_key():
    """Two conventions name the recorder sizes, so these two titles say which size is meant."""
    assert instruments.entry('great bass recorder').title == 'Great bass recorder in C'
    assert instruments.entry('contrabass recorder').title == 'Contrabass recorder in F'
```
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k state_their_key -v`
  Expected: FAIL on the title.

- [ ] **Step 3: Retitle.** Change only the two title strings. Above them, add a comment that
  quotes the maker's page with its URL, and the spec's finding ("the Paetzold/Mollenhauer
  convention"; "a second 'great bass in F' exists elsewhere").

- [ ] **Step 4: Run the suite.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -q`
  Expected: PASS.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: the great bass and contrabass recorder titles state their key" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 3: The European, orchestral and modern flutes, whistles and calls sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. Put no personal data in any request. A list page
is a source for a name only. The sound, the title and the range come from the instrument's own
page, or from an encyclopedia, maker, museum or conservatory. The audit's "VERIFIED" rows and its
quotes are leads, not sources, so fetch them. This task may start as soon as the controller has
written `build/batch-9-names-before.txt`, alongside Tasks 1 and 5.

**Files:**
- Create: `plans/data/instrument-audit/batch-9.tsv`
- Create (not committed): `build/batch-9-candidates.txt`, `build/batch-9-half-a.txt`,
  `build/batch-9-half-b.txt`, `build/batch-9-form-check.py`, `build/batch-9-half-a.tsv`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `flutes.md` ("Rejected or corrected proposed
  entries", "Aliases", "Range checks", the catalog note); `new-environmental-instruments.md` and
  `new-noise-makers.md` for their rows; `batch-1.tsv` to `batch-8.tsv`;
  `build/batch-9-names-before.txt`.
- Produces: `batch-9.tsv` with batch 8's header:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `flutes` on every row. A pitched SHIP
  or SOUND_ALIKE row has `lowest`, `highest`, `range_source`, and `notes` holding `Range:`. An
  unpitched one has none of the three, and its `notes` begin `Unpitched.` (a sound-alike's:
  `Sound-alike: Unpitched.`). `tags` is `mechanical` on a self-playing instrument's SHIP or
  SOUND_ALIKE row, else empty. `hs` is the Hornbostel–Sachs class that a fetched source gives
  (`421.…`), else `none`. Also the form check script, `build/batch-9-form-check.py SHEET`, which
  Task 5 runs, and `build/batch-9-half-a.tsv`, the half as committed, which Task 4's code check
  reads.

- [ ] **Step 1: Write the candidate lists**
```bash
mkdir -p build
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /^flutes/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /flute/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' 'steam whistle' 'boatswains call' 'pea whistle' 'duck call' 'bird whistle' 'singing bird box'
} | LC_ALL=C sort -u > ../../../build/batch-9-candidates.txt
cd ../../..
```
  Then write the plan's 47 half-A names, one per line, to `build/batch-9-half-a.txt`, sorted with
  `LC_ALL=C sort`, and run `LC_ALL=C comm -23 build/batch-9-candidates.txt build/batch-9-half-a.txt > build/batch-9-half-b.txt`
  and `wc -l build/batch-9-*.txt`.
  Expected: 119 candidates, 47 in half A, 72 in half B, and `LC_ALL=C comm -13
  build/batch-9-candidates.txt build/batch-9-half-a.txt` prints nothing.

- [ ] **Step 2: Write one row per half-A candidate,** in `build/batch-9-half-a.txt`'s order, then
  one per half-A alias name (5; the audit's line is the row's `audit_name`).

  The rules are batch 8's, changed for this family:

  1. **SHIP** only with name, title, range and sound from fetched sources. Quote in `notes` the
     passage that describes the sound or construction (bore, material, a duct or an edge, a
     stopped or open pipe, a vessel) and, after `Range:`, the passages that give the range, then
     the derivation under the range ruling. The `builder` cell gives the shape (one of the six, a
     `with_drones` call, or a new shape under the plan's ruling). It says which values come from
     the source and which are sound design.
  2. **SOUND_ALIKE**: a verified instrument that rule 7 finds would sound like an existing entry
     or a SHIP row of this half. `alias_of` is its parent. The `notes` begin "Sound-alike:",
     quote the source's description, and say why that entry is the nearest (for a size: the
     entry its source relates it to, nearest in register). It has its own range under the ruling,
     or is unpitched exactly when its parent is. The parent is a catalog name or a SHIP row of
     this half. It is never another sound-alike, never one of `APPROXIMATING_NAMES` (now with
     `dizi`), and in another family only when the source relates them.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row. If the target waits, the row is WAIT with `waits_for` `its target,
     <name>`. If the target is dropped, the row is DROP "its target, <name>, is dropped".
  4. **WAIT** when the identifying sound needs a feature the engine lacks, named in `waits_for`
     with the source quoted. The names are those in Global Constraints (`a buzzing membrane`, `a
     pitch LFO (vibrato)`, `a pitch LFO (portamento between notes)`, `an amplitude LFO`, `moving
     formants`, `more than four sources`, `a sourced drone tuning`, `its own build` and the rest),
     or `a sourced range`, `sub-audio fundamentals` or `a range above C8`. The feature must be the
     sound the source describes, not one the instrument merely has. The rows of `PORTAMENTO_NAMES`
     WAIT as the plan's decisions say. Any other name is allowed only with the source quoted, and
     Task 7 lists it in #79.
  5. **DROP** a row that does not exist as described, belongs to another family (name it), is a
     one-off, is the other recorder convention's name, or is already decided: in the catalog under
     that name (name the entry), an alias already (name its target), or a row of an earlier sheet
     (name the sheet and its status). The hand-offs (`steam whistle`, `boatswains call`, `pea
     whistle`, `duck call`, `bird whistle`, `singing bird box`) are decided here, not dropped as
     decided.
  6. A row the audit marks "none fetched; existence from memory" has no sourced sound yet. Fetch
     the instrument's own page; the audit's URL is a lead. If no page can be found, the row is DROP
     "no fetched source describes it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='flutes'))"`
     and the builds in `flutes.py`) and every SHIP row above it. If no sourced trait (bore,
     material, a duct, a stopped pipe, a vessel, drones) makes it sound different, it is a
     SOUND_ALIKE under rule 2. A number chosen only to differ does not count, and a range is not
     a sound trait.
  8. **Duplicates in the candidates** (`police whistle` and `pea whistle`, `bosuns call` and
     `boatswains call`): one row decides the instrument. The other is ALIAS when a person would
     type that name, else DROP "the audit's name for <row>". A name with an apostrophe, hyphen or
     reordered word gets a valid `name` and keeps the original in `audit_name`.

- [ ] **Step 3: Write and run the form check.** Write `build/batch-9-form-check.py`:
```python
"""Batch 9's sheet form check: python -I build/batch-9-form-check.py SHEET.

Batch 8's build/batch-8-form-check.py with batch 9's changes (batch 9's plan, Task 3 Step 3):
the flutes family, batch 6's unpitched rows, parents in any family, the mechanical tag, the dizi
among the approximations, and the slide whistle's names held back.
"""

import csv
import re
import sys

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note

STATUSES = ('SHIP', 'SOUND_ALIKE', 'WAIT', 'ALIAS', 'DROP')
# Task 1's sets (tests/audio/test_instrument_catalog.py)
APPROXIMATING_NAMES = {
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
    'dizi',
}
PORTAMENTO_NAMES = {'slide whistle', 'swanee whistle', 'lotus flute', 'piston flute', 'jazz flute'}
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
with open('build/batch-9-names-before.txt', encoding='utf-8') as before_file:
    names_before = set(before_file.read().split('\n')) - {''}
ship_rows = {row['name']: row for row in rows if row['status'] == 'SHIP'}
alikes = {row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'}
parents = set(ship_rows) | {
    name for name in names_before
    if name in instruments.CATALOG and instruments.entry(name).sounds_like is None
}


def pitched(row):
    return bool(row['lowest'] or row['highest'] or row['range_source'])


def parent_pitched(name):
    return pitched(ship_rows[name]) if name in ship_rows else instruments.entry(name).pitched


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
    return held.sounds_like is None and held.family == row['family']


def taken(row):
    """A name the catalog held before the batch, or that the code holds as something else."""
    name = row['name']
    if name in names_before:
        return True
    in_code = name in instruments.CATALOG or name in instruments.ALIASES
    return in_code and not held_as_this_row(row)


def ranged(row):
    if not pitched(row):
        return 'Unpitched.' in row['notes'][:40]
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
       or row['family'] != 'flutes'
       or not row['audit_name']
       or not (row['hs'] == 'none' or row['hs'][:1].isdigit())
       or row['tags'] not in {'', 'mechanical'}
       or (row['tags'] and row['status'] not in {'SHIP', 'SOUND_ALIKE'})
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)))
       or (row['status'] in {'SHIP', 'SOUND_ALIKE', 'ALIAS'}
           and (taken(row) or row['name'] in PORTAMENTO_NAMES))
       or (row['status'] == 'SOUND_ALIKE'
           and (row['alias_of'] not in parents or row['alias_of'] in APPROXIMATING_NAMES
                or pitched(row) != parent_pitched(row['alias_of'])))
       or (row['status'] == 'WAIT' and not row['waits_for'])
       or (row['status'] == 'ALIAS'
           and row['alias_of'] not in parents | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {status: sum(row['status'] == status for row in rows) for status in STATUSES})
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  Run: `uv run python -I build/batch-9-form-check.py plans/data/instrument-audit/batch-9.tsv`
  Expected: the counts, then `bad: []`, exit 0. Read the sheet with the csv module, never by
  splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: Check the half.** Run batch 7's Task 2 Step 4 command with `batch-9.tsv`,
  `build/batch-9-half-a.txt` in place of the Europe list and `build/batch-9-half-b.txt` in place
  of the Asia and Africa list.
  Expected: `missing: []` and `from half B: []`.

- [ ] **Step 5: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-9.tsv build/batch-9-half-a.tsv
git add plans/data/instrument-audit/batch-9.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 9's verification sheet, the European, orchestral and modern flutes, whistles and calls" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The European, orchestral and modern flutes, whistles and calls

**Files:**
- Modify: `flutes.py` (new builds after the 30, any new shape beside the six),
  `flute_sound_alikes.py` (`FLUTE_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its source
  URL in a comment), and `tests/test_process_state_guard.py` (a new shape's `CATALOG_BUILD` line)
- Test: `tests/audio/test_instrument_catalog.py`
- Create (not committed): `build/batch-9-code-check.py`

**Interfaces:**
- Consumes: `build/batch-9-half-a.tsv` (half A as committed), and Task 1's lists.
- Produces: `NEW_FLUTE_NAMES`, `FLUTE_SOUND_ALIKE_PARENTS` and `FLUTE_UNPITCHED_NAMES` filled
  with this half's rows, which Task 6 extends; and `build/batch-9-code-check.py SHEET`, which
  Task 6 runs.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 1–3 and 5 by ruling, and run Step 4's
code check alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_FLUTE_NAMES` with one name per SHIP row, in
  the sheet's order, `FLUTE_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row, and
  `FLUTE_UNPITCHED_NAMES` with the unpitched ones. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, with a docstring sentence for batch 9. A
  `mechanical` row's name goes first in the tuple that
  `test_plucked_idiophones_hold_the_lamellophones_and_music_boxes` pins, because flutes come
  first in catalog order. A shipped recorder or concert-flute size joins its chain in
  `test_sized_families_descend_from_highest_to_lowest`, in descending order of lowest note. A
  drone build goes in `NOT_PERIODIC_AT_THE_NOTE` with its reason.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or descend or lamellophones" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in `FLUTE_SOUND_ALIKES`,
  in the sheet's order, as a `CatalogEntry(name, title, Family.FLUTES, lowest, highest,
  sounds_like=parent)` (with `None, None` when unpitched, and `tags=frozenset({Tag.MECHANICAL})`
  where the sheet says `mechanical`). Above each, put a comment with its `sound_source` and
  `range_source` URLs, the quoted passages and the range's derivation, as
  `bowed_sound_alikes.py`'s entries have. A SHIP row is a `CatalogEntry` after the 30 in
  `_FLUTE_BUILDS`, carrying the same comment and marking the values that are sound design. A new
  shape gets its own test of the trait it exists for, as batch 2's
  `test_the_pianet_settles_from_a_bright_strike` does. For a stopped pipe, the test checks that
  the second and fourth harmonics are far below the first and third. For drones, it checks that
  the drone sources sound at their sourced hertz whatever note is played.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range or the build. Check it against the source, and never trim the range to
  pass. Then write `build/batch-9-code-check.py`, batch 7's Task 3 Step 4 code check as a script
  that reads `sys.argv[1]` in place of the fixed sheet path, compares `e.family` with
  `r['family']` in place of `'bowed strings'`, and compares `(e.lowest, e.highest)` with
  `(r['lowest'] or None, r['highest'] or None)` so that an unpitched row matches. It keeps the
  `elif` that checks every WAIT and DROP name is absent from the catalog and the aliases (only a
  DROP whose note says the name is already there may resolve). Run:
  `uv run python -I build/batch-9-code-check.py build/batch-9-half-a.tsv`
  Expected: `matches N rows`, with N half A's row count (52 if every candidate and alias name has
  one row).

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 9's European, orchestral and modern flutes, whistles and calls, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 5: The traditional flutes of Asia, Africa, the Americas and Oceania sheet (half B)

Research as in Task 3. This task may start as soon as the controller has written
`build/batch-9-names-before.txt`, alongside Tasks 1 and 3, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-9-half-b.tsv`, half B's rows under the sheet's header
- Modify: `plans/data/instrument-audit/batch-9.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 3's rules 1–8, header and `build/batch-9-form-check.py`, and
  `build/batch-9-half-b.txt`. If either file is missing, rerun Task 3 Step 1 or write the form
  check from Task 3 Step 3.
- Produces: the sheet's remaining rows, which Task 6 reads.

Every half-B candidate gets a row, in `build/batch-9-half-b.txt`'s order, then one per half-B
alias name (22). A parent or alias target is a catalog name or a SHIP or SOUND_ALIKE row of this
half, never a half-A row. These rules apply to this half on top of Task 3's:

- **Membrane flutes.** `qudi`, `bangdi`, `daegeum`, and any other row whose fetched source names a
  membrane's buzz as its sound (`khlui`, `sao truc` if theirs do), WAIT `a buzzing membrane`. They
  are never a sound-alike of `dizi` (Task 1's test). `junggeum` and `sogeum` are ranged and built
  like any flute if their source says they have no membrane.
- **Panpipes and stopped flutes.** A panpipe that one player plays is one instrument, ranged by its
  stated lowest and highest pipes. A stopped pipe's odd harmonics are a sound trait only when a
  fetched source states them. The first row that needs it adds a stopped-pipe shape under the
  plan's ruling. Later rows that share it are that row's sound-alikes, never new builds. The
  `siku`, `antara`, `rondador`, `paixiao`, `wot`, `nyanga panpipes`, `solomon panpipes`,
  `firlinfeu`, `chiflo` and `quills` are decided this way, and the hocket sets under the range
  ruling's rule 7.
- **Voices and drones.** `tsuur`, `fulani flute`, `sybyzgy` and `umtshingo` follow the "flute with
  a voice or a drone" ruling, by what their fetched source says. `algoza` is a double flute: its
  second pipe's drone needs a sourced pitch, or it WAITs `a sourced drone tuning`.
- **Keys and sizes.** `shinobue`, `nohkan`, `ryuteki`, `kagurabue`, `komabue`, `suling`, `quenacho`
  and the other flutes made in several keys take the key that their source calls standard, under
  the range ruling's rule 4. A size that its source names as another's register (`quenacho` as a
  low quena, `tungso` as a long danso) is a SOUND_ALIKE of the entry nearest in register that its
  source relates it to.
- **Whistles of this half.** `pigeon whistle` (several slits sounding at once), `whistling vessel`
  and `aztec death whistle` follow the moving-sound and unpitched rulings. A whistle with more
  pipes or chambers sounding at once than the build's sources allow WAITs `more than four
  sources`.
- **Aliases.** `venu`'s audit line says "different fingering and tuning", so it is ALIAS of
  `bansuri` only if a fetched source says they are the same instrument. Otherwise it is a row of
  its own (a SOUND_ALIKE with its own range, or a WAIT). `siyotanka` follows the same rule for
  `native american flute`.

- [ ] **Step 1: Write half B's rows** to `build/batch-9-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-9-form-check.py build/batch-9-half-b.tsv`
  Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 3 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-9-half-b.tsv >> plans/data/instrument-audit/batch-9.tsv`.
  Run Task 3 Step 3's form check on the whole sheet.
  Expected: the counts, then `bad: []`, exit 0. If Task 4 has run, half A's coded rows are
  accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 3 Step 4's command with
  `half_a | half_b` on the `missing:` line in place of the half-A list, and print
  `'extra:', sorted(audit_names - half_a - half_b)` in place of the half-B line.
  Expected: `missing: []`. `extra:` lists only the alias lines, because an alias row's
  `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-9.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 9's verification sheet, the traditional flutes of Asia, Africa, the Americas and Oceania" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The traditional flutes of Asia, Africa, the Americas and Oceania

**Files:**
- Modify: `flutes.py`, `flute_sound_alikes.py`, `aliases.py`, `tests/test_process_state_guard.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-9.tsv`'s half-B rows, Task 4's lists and `build/batch-9-code-check.py`.
- Produces: the finished family.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 1–3 and 5 by ruling, and run Step 4's
code check alone. If `build/batch-9-code-check.py` is missing because Task 4 was skipped, write
it from Task 4 Step 4.

- [ ] **Step 1: Write the failing tests:** append this half's rows to the lists as in Task 4
  Step 1.

- [ ] **Step 2: Run them and check they fail.** Run Task 4 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 4 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes.

- [ ] **Step 4: Run the suite and check the code against the whole sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`, then
  `uv run python -I build/batch-9-code-check.py plans/data/instrument-audit/batch-9.tsv`.
  Expected: PASS, then `matches N rows`, with N the sheet's row count (146 if every candidate and
  alias name has one row).

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 9's traditional flutes of Asia, Africa, the Americas and Oceania, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 7: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a flutes
  paragraph with its count, naming `flutes.py` and `flute_sound_alikes.py`, with examples, and
  fix the opening sentence's flute sizes if the sheet added any.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `flutes` row's
  count and examples, the sound-alike modules sentence and its total).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 9
  done, pointing at this plan and `batch-9.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 9 DONE";
  - batch 9 done, with the sheet's counts by status and the family's growth;
  - the audit's unclosed gaps, as a later pass;
  - the hand-offs decided here (`steam whistle`, `boatswains call`, `pea whistle`, `duck call`,
    `bird whistle`, `singing bird box`, `hydraulophone`, `pigeon whistle`);
  - `serinette` and `flute clock` left for the organs batch to decide;
  - a "Plan (batch 9)" line, the Status line, and the next batch named: brass.

  Add #79 (the highest item is #78), "Sound Engine: The Owner's Checks on Instrument Catalog
  Batch 9 — TODO". Use #78's form, place it directly after #78, and give it the Priority "(before
  the brass batch builds on the same catalog)". Its **Listen** section
  (`build/instruments/flutes/`) covers the new builds, then the sound-alikes under their parents,
  then the aliases, and the two retitled recorders. Its **Calls to confirm** are:
  - every WAIT, by reason, with names;
  - the range ruling (stated or an exact span, sounding pitch, never hedged, extreme, a width or
    letters; the standard key; maker and museum sources; nothing below A0 or above C8; one-note
    pipes), and every derived range;
  - the recorder naming: one convention, the two titles retitled (or Task 2 skipped, with the
    pages tried), and other-convention names refused as aliases;
  - `dizi` among the approximations, never a parent, and the membrane flutes' wait;
  - the moving-sound ruling, `PORTAMENTO_NAMES` decided by the plan, and each LFO wait;
  - flutes with a voice or a drone, and double flutes as two notes;
  - overtone flutes as flutes;
  - any new shape and the trait its source names;
  - unpitched flutes (`FLUTE_UNPITCHED_NAMES`);
  - the boundary hand-offs, the duck call's family against its source's reed (if the source says
    so), the hydraulophone's `hs`, and a steam whistle's parent across families, if any;
  - sizes and keys as sound-alikes;
  - one-offs and unsourced rows dropped;
  - the module move (`flutes.py`; `winds.py` keeping the five reed families);
  - the two-half split by an explicit list, the sheets researched in parallel, and any code task
    skipped by ruling;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): `dizi` built as
  `METAL_FLUTE`, without the membrane its page names; any existing range a sheet's source
  contradicts; the `pan flute`'s `END_BLOWN` build, if a fetched source says panpipes are
  stopped. Then **Follow-ups**: the audit's gaps; ranging the range WAITs from maker and museum
  sources; the engine changes that unblock the waits, most rows first.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(i.names(tag='mechanical'))"`
  and `uv run python -I build/batch-9-form-check.py plans/data/instrument-audit/batch-9.tsv`
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
  `build/instruments/flutes` folder is the one to listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 9 of the instrument catalog (flutes), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch
in turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78).
The pre-push hooks take about 40 minutes, and nothing in the working tree may change while they
run.

**Order:** the controller's names file, then Tasks 1, 3 and 5 in parallel. Task 2 follows Task 1.
Task 4 follows Tasks 2 and 3. Task 5's append waits for Task 3's commit. Task 6 follows Tasks 4
and 5, and Task 7 comes last.
