# Instrument catalog batch 10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the brass family from the audits' candidates. The family holds the lip-vibrated
aerophones (Hornbostel–Sachs 423: the trumpets, horns, trombones and tubas, the keyed and
fingered lip-reeds such as cornetts, serpents and ophicleides, and the natural horns, shells and
animal horns). Each instrument gets a cited source and either sounds unlike every other entry or
is a listed sound-alike of the one it sounds like. The rest become aliases, wait for an engine
feature or a sourced range, or are dropped with a reason.

**Architecture:** As in batches 3 to 9, a verification sheet (`batch-10.tsv`) decides every
candidate before any code is written. The family's 42 entries are already in a module of their
own, `brass.py` (238 lines), so nothing moves. Its table is renamed `_BRASS_BUILDS`, and `BRASS`
becomes `_BRASS_BUILDS + BRASS_SOUND_ALIKES`, with the sound-alikes in a new
`brass_sound_alikes.py`, the pattern of `flute_sound_alikes.py`. `didgeridoo` joins
`APPROXIMATING_NAMES`, because its page says its moving formants give "the instrument its
readily recognisable sound" and the catalog's build has none. A new guard,
`BRASS_HELD_BACK`, holds every name the sheet holds back for an engine feature or a build of its
own. The sheet and the code each come in two halves, split by Hornbostel–Sachs class into
explicit lists: the chromatic brass (423.2: valves, slides, keys or finger holes), then the
natural horns and trumpets (423.1: the lips alone), with the shells and animal horns. The
controller writes the names file, the candidate lists and both check scripts before anything is
dispatched, so the two sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `falling_series`,
`formant_series`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all). Batch 9's plan (`plans/2026-11-12-instrument-catalog-batch-9-implementation.md`)
and its owner's checks (`plans/future-features.md` #79) are this plan's template and its ledger.
Batch 4's plan (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) holds the
pitched sound-alike and strict range rules and the before-and-after build record. This plan's own
path is `plans/2026-11-12-instrument-catalog-batch-10-implementation.md`. The branch is
`feat/instrument-catalog-batch-10`, made from `feat/instrument-catalog-batch-9` at its HEAD once
batch 9's fix commit has landed (that commit reorders batch 9's aliases and touches no brass).
The candidates come from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `brass` (90): the round-2 audit `brass.md`'s 89,
  and `corrugahorn` from `new-noise-makers.md` (family "noise makers (or brass: lip-excited,
  owner question)");
- the `round-1/merged-missing.tsv` rows whose `family` contains `brass` (14: `natural trumpet`,
  `keyed bugle`, `buccin`, `carnyx`, `cornu`, `dungchen`, `karnay`, `trutruca`, `slide trumpet`,
  `subcontrabass tuba`, `bazooka`, `didjeribone`, `hosaphone`, `fluba`).

Together: **104 unique candidate names** (counted for this plan; the controller recounts). None
is in the catalog or the alias table today, and every one is already a valid catalog name. The
brass audit's "Aliases" section proposes **23 alias names**: `kent bugle`, `royal kent bugle`,
`cornet a pistons`, `tenor horn`, `waldhorn`, `inventionshorn`, `yidaki`, `mako`, `alpenhorn`,
`swiss horn`, `luren`, `fotuto`, `triton shell`, `tromba da tirarsi`, `basson russe`, `zink`,
`kerana`, `karna`, `kernei`, `kurenay`, `kanay`, `trutruka` and `tibetan horn` (none is in the
catalog or the aliases; `shankha`, `horagai`, `dung dkar`, `pututu` and `trutruca`, also named in
that section, are candidate rows). So the sheet will hold **127 rows**.

No earlier sheet hands a candidate to this family. Checked for the lip-reed boundary: the noise
makers audit keeps `vuvuzela` in brass ("VERIFIED: keep in brass; the boundary question is
closed"), and it is in the catalog; `alphorn`, `conch`, `didgeridoo`, `shofar` and `natural horn`
are catalog entries, so only their audit alias names are rows here. `corrugahorn` was decided by
`batch-1.tsv` (WAIT, `a sourced range`, in noise makers), which left its brass question to the
owner. Batch 9's `porutu` and `putorino` (a "trumpet" voice) were decided in flutes, batch 7's
`tromba marina` in bowed strings, and batch 6's `sackbut` row (an electronic instrument's alias)
was dropped as the catalog's brass `sackbut`. `plans/future-features.md` #70–#79 leave nothing
else for this family.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, hyphens and parentheses go only in the title
  (`cornet a pistons` for "cornet à pistons", `ram singa` for the audit's "Ram-singa"). A key
  goes before the name, as in the catalog (`c trumpet`, `e flat tuba`), so the audit's `piccolo
  trumpet in b flat` is `b flat piccolo trumpet`, with the audit's name in `audit_name`.
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families).
  Brass is the lip-vibrated aerophones, H-S 423, whatever the material (wood, horn, shell, bone).
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict").
  This plan's range ruling for brass is below, under "Decisions". A row with no sourced range
  is WAIT, `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the
  same instrument) stays an alias." A sound-alike is pitched exactly when its parent is, and a
  pitched sound-alike gives its own sourced range (batch 4). A parent may be in another family
  (batch 7), when the row's source relates them.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as
  an approximation, under its real name or a qualified one. The spec's table names no brass
  instrument, but its row "moving formants, vowel glides, vibrato" binds a didgeridoo-type drone,
  and "sub-audio fundamentals" binds a brass instrument pitched below A0. Earlier batches added
  the other names a WAIT may give: a pitch LFO (vibrato), a pitch LFO (portamento between notes),
  an amplitude LFO, filter resonance, a filter envelope, more than four sources, moving formants
  (batch 6); a buzzing membrane (batch 5); a sourced drone tuning and its own build (batch 7).
  What the engine has: up to four `Source`s, each with its own semitones, detune and fixed pitch;
  one glide per note (`pitch_curve`); a fixed FIR low or high pass; `drive` 0–20; and the
  family's `_brass` shape (a falling series of 24 harmonics, its slope, a low pass, the attack,
  drive, breath noise, and `bite_levels`, a brighter series the note starts on). Its harmonics
  are whole multiples of the note: it makes no inharmonic partial. It has no LFO of any kind.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not
  builds.
- Reuse the family's nine shapes (`TRUMPET`, `CORNET`, `FLUGELHORN`, `HORN`, `TENOR_BRASS`,
  `TROMBONE`, `TUBA`, `NATURAL`, `WOODEN_LIP_REED`, all `_brass` partials) and `_muted`. Add a
  shape only for a genuinely new sound, and give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the
  sheet is verbatim from a page the worker fetched. No request carries the owner's email or any
  personal data, in a header, a URL or a payload (#78, "Incidents and process").
- Code comments name committed files (`plans/data/instrument-audit/batch-10.tsv`), never the
  gitignored `build/` files (batch 9's fix).
- The 42 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 42. An existing entry changes only for a cited bug, reported to the
  owner; `brass.py`'s entries carry no source comment, so a range that a fetched source
  contradicts is reported in #80, not changed here.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown
  by a test, you should understand why it's happening and be concerned": a warning is a
  finding, and it must be understood before going on.
- Commits as batches 4 to 9: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this
  plan, never from memory. Write no `.md` file beyond those Task 6 names.

## Review Focus

1. **A written range read as sounding.** Most brass is written transposed: a B-flat trumpet
   sounds a tone below its part, a horn in F a fifth below, and a brass band's tenor horn,
   baritone, euphonium and tubas are written in treble clef, an octave or more above their
   sound. A range read off such a part is wrong by up to two octaves and a sixth. Range ruling 2
   takes a written range only with the transposition its own source states, the `Range:`
   passage shows the arithmetic, and the code check compares every range with the sheet.
2. **A player's top or the pedal notes read as the compass.** Brass makers and references give
   a top "for advanced players" and pedal notes "below the range". Range ruling 3 takes neither,
   unless the source puts them in the stated compass. A natural instrument's range in harmonic
   numbers counts only under ruling 4.
3. **A didgeridoo-type drone or a carnyx shipped as plain brass.** The catalog's `didgeridoo`
   has no moving formants, though its page says they give its "readily recognisable sound". A
   sound-alike of it, or a `didjeribone` built as a trombone, would ship that omission under a
   new name. Task 1 adds `didgeridoo` to `APPROXIMATING_NAMES`, so the test and the form check
   refuse it as a parent. The carnyx page calls its replica's resonances inharmonic, which
   `_brass` cannot make. Both kinds WAIT under the decisions, and `BRASS_HELD_BACK` keeps their
   names out of the catalog and the aliases.
4. **A size beyond the catalog's floor or top.** `subcontrabass tuba`, `contrabass ophicleide`,
   `contrabass saxhorn` and `helicon` reach toward A0, and `sopranino saxhorn`, `soprano
   trombone` and `b flat piccolo trumpet` toward the top. The form check refuses a range below A0
   or above C8, and range ruling 8 makes such a row WAIT. The render and pitch tests play every
   range's ends: a quiet or wrong note there is a finding about the range or the build, and the
   range is never trimmed to pass.
5. **The same instrument shipped twice, or a candidate decided twice.** The audit's `treble
   cornett` is the catalog's `cornett`, `tenor horn` the British name of the catalog's `alto
   horn`, and `b flat piccolo trumpet` may be the catalog's piccolo trumpet on its other
   leadpipe. `chazozra` and `hatzotzerah` are one instrument; `buccin` (a trombone) and `buccina`
   (Roman), `lituus` and `medieval lituus`, and `lur` and `brudevaelte lur` are pairs to tell
   apart; `corrugahorn` was decided by batch 1. Rules 3, 5 and 8 decide each, the form check
   refuses a name taken before the batch, and the code check finds every name exactly once.

---

## File Structure

- Modify `src/glitchygames/audio/instruments/brass.py`: the table becomes `_BRASS_BUILDS`
  (unchanged), new builds go after the 42, any new shape is a module-level `partial` beside the
  nine, and `BRASS = _BRASS_BUILDS + BRASS_SOUND_ALIKES`. Its docstring names the sound-alikes
  module.
- Create `src/glitchygames/audio/instruments/brass_sound_alikes.py`, holding `BRASS_SOUND_ALIKES`.
- Modify `aliases.py` (the batch's ALIAS rows, in the sheet's order).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5) and, only for a new shape,
  `tests/test_process_state_guard.py` (a `CATALOG_BUILD` line under
  `'audio/instruments/brass.py'`). `registry.py` does not change: it already imports `BRASS`
  from `brass.py`, in its place in `FAMILY_TABLES` after the free reeds.
- Create `plans/data/instrument-audit/batch-10.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #80), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #80):

- **Brass gets a sound-alikes module, and nothing moves.** `brass.py` holds one family already,
  so there is no move (batch 9 moved the flutes out of `winds.py` because it held six). Batches
  4, 6, 7, 8 and 9 each gave the family they grew a sibling sound-alikes module that names it
  ("The family's builds are in …"), so brass gets `brass_sound_alikes.py`. Renaming the tuple
  and appending an empty table changes no entry, and Task 1's before-and-after record checks it.
- **Range ruling for brass.** A sourced range is the lowest and highest sounding notes that a
  fetched source states for the instrument:
  1. *Stated*: the source gives both notes as the range or compass, in note names with octaves
     (scientific `C4`, Helmholtz `c'`, or a named note whose octave the source fixes), or the
     lowest note and an exact span above it ("three octaves"), as batch 7 allowed.
  2. *Sounding*: a range in written pitch counts only when the same source, or the same maker's
     page for that model, states the transposition (a B-flat instrument sounding a major second
     below written, a horn in F a perfect fifth below, a treble-clef euphonium a major ninth
     below). A range the source calls sounding, concert pitch, or the range of a non-transposing
     instrument is sounding as given. The derivation shows the arithmetic. Otherwise the row
     WAITs. A brass band's treble-clef part is never read as sounding.
  3. *Pedal and top*: the stated compass, and nothing beyond it. Pedal notes count only when the
     source puts them inside the stated range (not "pedal notes are possible below"). A top the
     source gives to the player ("and higher for advanced players", "professionals reach",
     "or beyond") is an extreme: the range is the compass the source states without it, or the
     row WAITs. A compass with an extension in parentheses is the unparenthesised notes (batch
     9's `csakan`).
  4. *Natural instruments*: a range in harmonic numbers counts only when the same source states,
     without a hedge, both the harmonic numbers of the range and the sounding pitch of the
     fundamental or of one named harmonic, with its octave. The derivation names each end's
     harmonic and its equal-tempered note (harmonic n lies 12·log2(n) semitones above the
     fundamental, rounded to the nearest semitone). A key alone ("in D") fixes no octave.
  5. *Not a range*: a hedged span ("about", "approximately", "typically", "commonly",
     "usually up to", "can reach"), an extreme, a width with no pitches, note letters with no
     octaves, a tessitura, or one pitch ("pitched in B-flat", "about 235 Hz"). The didgeridoo
     page's "fundamental typically A2 to G3" is the keys instruments are made in, hedged, not one
     instrument's range.
  6. *Several keys or sizes*: the key or size that the source calls standard, usual or most
     common, from that source or a maker's model page in that key. A key in the row's own name
     (`e flat trumpet`, `cc tuba`) is ranged in that key. With neither, the row WAITs (batch 7's
     rule for several tunings).
  7. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached);
     a maker's catalogue or model page (Yamaha, Vincent Bach and Conn of Conn-Selmer, Besson and
     Courtois of Buffet Crampon, Wessex Tubas, Willson, Miraphone, Meinl Weston, B&S, Thein,
     Egger, Ewald Meinl, Christopher Monk Instruments for cornetts and serpents, and the like); a
     museum's object record (MIMO, the Met, the Horniman, the Edinburgh University Collection of
     Historic Musical Instruments, the National Music Museum, the Bate Collection, the Koizumi
     collection of the Tokyo University of the Arts); or a conservatory or orchestration
     reference (the Vienna Symphonic Library's instrument pages). A retailer's listing (a
     maker's model sold on a shop's page included), a blog or a forum is not a source. A maker's
     page for a model in another key ranges only that key. A range is never taken from a sibling
     size, the parent or the audit.
  8. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`, the spec's name) and
     nothing above C8, the piano's top and the form check's (WAIT `a range above C8`).
  9. *One note*: a horn or shell whose source gives it one note, or only its fundamental, has no
     range (the catalog needs lowest below highest). It WAITs `a sourced range`, with the one
     note quoted in `notes`, and Task 6 asks the owner in #80 whether a one-note horn should ship
     as a fixed-pitch entry instead.
  Every pitched row's `notes` holds `Range:` and the quoted passages, then the derivation.
- **Approximating entries are never parents, and `didgeridoo` is one.** The didgeridoo page
  (fetched for this plan, https://en.wikipedia.org/wiki/Didgeridoo): "Bands of frequencies that
  are not thus inhibited produce formants in the output sound. These formants, and especially
  their variation during the inhalation and exhalation phases of circular breathing, give the
  instrument its readily recognisable sound." The catalog's `didgeridoo` is a plain `_brass`
  build with drive, so it omits the sound its source names, as batch 9's `dizi` omits its
  membrane. It predates decision 4 and stays, but it joins `APPROXIMATING_NAMES`, and #80
  reports it as a bug. An alias of it (the audit's `yidaki`, `mako`) is allowed, because an alias
  is the same instrument and adds no build; a sound-alike is not.
- **A lip-reed with a voice or a moving mouth.** A brass row whose fetched source names the
  vocal tract's formants or vocalisations as its sound (a didgeridoo by another name or with a
  slide, as the audit's `didjeribone`) WAITs `moving formants`, the spec's row. One whose source
  names the player singing or shouting through it, without formants, WAITs `its own build`.
  Technique any player may add (flutter tonguing, growl) is not the instrument's sound.
- **Slides, valves, keys and finger holes choose the notes, not the sound.** The catalog's
  `trombone`, `sackbut` and `cimbasso` have no glide. So `valve trombone`, `superbone`, `slide
  trumpet`, `soprano trombone`, `corno da tirarsi`, `bazooka` and the keyed and fingered rows
  are ranged and built like any brass. A row WAITs `a pitch LFO (portamento between notes)` only
  when its fetched source names the glide between notes as the instrument's identifying sound,
  as batch 9 ruled for the slide whistle.
- **Inharmonic resonances wait.** `_brass` makes only whole harmonics, and the harmonic-pitch
  test checks every brass entry repeats at its note's period. A row whose fetched source names
  inharmonic resonances as its sound (the audit quotes the carnyx page for its replica) WAITs
  `its own build`, with the source quoted.
- **A new shape only for a sourced acoustic trait.** A shape is new when a fetched source names a
  trait that none of the nine shapes has (a bore, a bell, a material, a mouthpiece). Its own test
  checks that trait, as batch 2's `test_the_pianet_settles_from_a_bright_strike` checks its own.
  Its other numbers are sound design, marked so in the comment. A new shape is a module-level
  `partial` of `_brass` in `brass.py` beside the nine, and the guard gets a `CATALOG_BUILD` line
  for it. Half A may add a shape only for a trait that no half-B row names (shells, animal horns
  and bark-wrapped wooden horns are half B's), and half B the reverse, so the two never add the
  same shape.
- **Sizes, keys and the standard size.** A size or key of an existing instrument (`cc tuba`, `e
  flat trumpet`, `alto sackbut`, `bass sackbut`, `cornettino`, `tenor cornett`, `alto
  ophicleide`, `bass wagner tuba`, the saxhorns) is a SOUND_ALIKE of the entry nearest in
  register that its source relates it to, with its own range under the ruling, or it WAITs. A
  candidate that its source makes the catalog entry's own standard instrument (the treble
  cornett, if the source calls the ordinary cornett the treble; the tenor horn, if the source
  calls the E-flat alto horn the tenor horn in Britain) is ALIAS of that entry. A
  `b flat piccolo trumpet` is a SOUND_ALIKE of `piccolo trumpet` with its own range, unless its
  source says the A and B-flat piccolo are one instrument (then ALIAS). Any size that ships joins
  its chain in `test_sized_families_descend_from_highest_to_lowest` (the trombones' chain
  exists), and a new chain is added once two or more sizes that one source names as one family
  are in the catalog (sackbuts, cornetts, ophicleides, Wagner tubas).
- **No unpitched or mechanical brass.** Every brass parent is pitched, so a sound-alike is
  pitched, and no candidate plays itself. The form check refuses an unpitched SHIP or
  SOUND_ALIKE row and any `tags`. The batch table's row needs no unpitched names.
- **Mutes are out of scope.** The spec's Non-goals: "Articulations and ensemble patches
  (pizzicato, mutes, string sections): those are instrument settings, a separate design." The
  audit's prose names four more mutes (trumpet bucket and plunger, trombone straight and harmon);
  they are not candidate rows. The catalog's six mute entries predate this and stay.
- **The boundary hand-offs.** None is sent here (see the Spec line). `corrugahorn` is DROP
  "already decided: batch-1.tsv WAIT (a sourced range), in noise makers", and Task 6 restates its
  open family question in #80. A row whose fetched source makes it a free aerophone or a reed
  (not lip-vibrated) is DROP naming the family it belongs to.
- **One-offs, artefacts and unsourced rows are dropped** (batch 5's ruling): DROP "a one-off
  instrument, not a type a game would ask for" for one maker's or player's design, and DROP "a
  single surviving artefact, not a type a game would ask for" for a named find (the audit's
  `brudevaelte lur` and `savernake horn` are leads to check). A row with no fetched page
  describing it is DROP "no fetched source describes it" (rule 6); the audit itself rejects
  `hosaphone` for that.
- **Two halves by Hornbostel–Sachs class, as explicit lists.** Half A, the chromatic brass
  (423.2: valves, slides, keys or finger holes), is these 49 candidates. Half B, the natural horns
  and trumpets (423.1: the lips alone, including shells, animal horns and the ancient and folk
  horns), is the other 55. The list decides the half: a row whose source shows another class
  stays in its half, and its `hs` cell records the class.
  `alto ophicleide`, `alto sackbut`, `baritone bugle`, `bass cornett`, `bass flugelhorn`, `bass
  horn`, `bass sackbut`, `bass wagner tuba`, `bazooka`, `buccin`, `cc tuba`, `contrabass bugle`,
  `contrabass ophicleide`, `contrabass saxhorn`, `cornettino`, `corno da tirarsi`,
  `didjeribone`, `double bell euphonium`, `e flat trumpet`, `firebird trumpet`, `fluba`,
  `flumpet`, `helicon`, `herald trumpet`, `hosaphone`, `jazzophone`, `keyed bugle`, `keyed
  trumpet`, `kuhlohorn`, `mellophonium`, `mute cornett`, `piccolo trumpet in b flat`, `rotary
  valve trumpet`, `russian bassoon`, `saxotromba`, `saxtuba`, `slide trumpet`, `sopranino
  saxhorn`, `soprano helicon`, `soprano saxhorn`, `soprano trombone`, `subcontrabass tuba`,
  `sudrophone`, `superbone`, `tenor cornett`, `tenor tuba`, `treble cornett`, `valve trombone`,
  `vienna horn`.
  The 23 alias names go with their target's half. Half A has 7: `kent bugle`, `royal kent
  bugle`, `cornet a pistons`, `tenor horn`, `tromba da tirarsi`, `basson russe`, `zink`. Half B
  has 16: `waldhorn`, `inventionshorn`, `yidaki`, `mako`, `alpenhorn`, `swiss horn`, `luren`,
  `fotuto`, `triton shell`, `kerana`, `karna`, `kernei`, `kurenay`, `kanay`, `trutruka`,
  `tibetan horn`. So half A's sheet holds 56 rows and half B's 71. The duplicates and near-pairs
  fall within one half (`chazozra` and `hatzotzerah`, `lituus` and `medieval lituus`, `lur` and
  `brudevaelte lur`, `sringa` and `ram singa` in B; `helicon` and `soprano helicon`, `bass horn`
  and `russian bassoon` in A), except `buccin` (A, a trombone) and `buccina` (B, Roman), which
  are different instruments.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the
  batch, or a SHIP or SOUND_ALIKE row of the same half, never a row of the other half. So Task 4
  needs nothing from Task 2. Half B drafts to a build file, which is appended to the sheet once
  half A is committed. The form check accepts a row that the code already holds with the same
  target or parent (batch 7's lesson).
- **A held-back guard.** #79 found that only `PORTAMENTO_NAMES` held batch 9's names back. This
  batch's guard is `BRASS_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every
  WAIT row whose reason is an engine feature or a build of its own (any reason but `a sourced
  range`), and every alias row that waits for such a row. A test refuses each of its names in the
  catalog and the aliases, and the code check compares the table with the sheet.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task still fills `BRASS_HELD_BACK` with the half's held
  rows and runs the code check, which must pass; its other steps are skipped, and Task 6 records
  the skip in #80.
- **Out of scope:** the audit's "Gaps you could not close" (the list-of-brass page unread; MIMO,
  the Met and Grove not swept; the African, Pacific, Amazonian, Native American and Southeast
  Asian horns beyond Wikipedia's category, such as Moche clay trumpets and Philippine bamboo
  trumpets; the marching and double-bell variants known only from memory). Task 6 lists them in
  #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of these files is committed.

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-10-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
  Expected: `names before 773` (688 entries and 85 aliases).

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /brass/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /brass/ {print tolower($1)}' round-1/merged-missing.tsv
} | LC_ALL=C sort -u > ../../../build/batch-10-candidates.txt
cd ../../..
```
  Write the plan's 49 half-A names, one per line, to `build/batch-10-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-10-candidates.txt build/batch-10-half-a.txt > build/batch-10-half-b.txt`
  and `wc -l build/batch-10-*.txt`.
  Expected: 104 candidates, 49 in half A, 55 in half B, and
  `LC_ALL=C comm -13 build/batch-10-candidates.txt build/batch-10-half-a.txt` prints nothing.

- [ ] **Step 3: The form check,** `build/batch-10-form-check.py`:
```python
"""Batch 10's sheet form check: uv run python -I build/batch-10-form-check.py SHEET.

Batch 9's form check (plans/2026-11-12-instrument-catalog-batch-9-implementation.md, Task 3
Step 3) with batch 10's changes (batch 10's plan, "Before the tasks"): the brass family, no
unpitched or tagged rows, and the didgeridoo among the approximations.
"""

import csv
import re
import sys

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note

STATUSES = ('SHIP', 'SOUND_ALIKE', 'WAIT', 'ALIAS', 'DROP')
# Task 1's set (tests/audio/test_instrument_catalog.py APPROXIMATING_NAMES)
APPROXIMATING_NAMES = {
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
    'dizi', 'didgeridoo',
}
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
with open('build/batch-10-names-before.txt', encoding='utf-8') as before_file:
    names_before = set(before_file.read().split('\n')) - {''}
ship_rows = {row['name'] for row in rows if row['status'] == 'SHIP'}
alikes = {row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'}
parents = ship_rows | {
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
    return held.sounds_like is None and held.family == row['family']


def taken(row):
    """A name the catalog held before the batch, or that the code holds as something else."""
    name = row['name']
    if name in names_before:
        return True
    in_code = name in instruments.CATALOG or name in instruments.ALIASES
    return in_code and not held_as_this_row(row)


def ranged(row):
    """A pitched row with both notes, A0 to C8, its range source and its Range: passage."""
    try:
        lowest, highest = Note(row['lowest']).midi_number, Note(row['highest']).midi_number
    except Exception:
        return False
    return (
        row['range_source'].startswith('http')
        and 'Range:' in row['notes']
        and Note('A0').midi_number <= lowest < highest <= Note('C8').midi_number
    )


def parent_pitched(name):
    return name in ship_rows or instruments.entry(name).pitched


names = [row['name'] for row in rows]
bad = [row['name'] for row in rows if not pattern.fullmatch(row['name'])
       or row['status'] not in STATUSES
       or row['family'] != 'brass'
       or not row['audit_name']
       or not (row['hs'] == 'none' or row['hs'][:1].isdigit())
       or row['tags'] != ''
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)))
       or (row['status'] in {'SHIP', 'SOUND_ALIKE', 'ALIAS'} and taken(row))
       or (row['status'] == 'SOUND_ALIKE'
           and (row['alias_of'] not in parents or row['alias_of'] in APPROXIMATING_NAMES
                or not parent_pitched(row['alias_of'])))
       or (row['status'] == 'WAIT' and not row['waits_for'])
       or (row['status'] == 'ALIAS'
           and row['alias_of'] not in parents | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {status: sum(row['status'] == status for row in rows) for status in STATUSES})
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted
  cells).

- [ ] **Step 4: The code check,** `build/batch-10-code-check.py`:
```python
"""Batch 10's code check: uv run python -I build/batch-10-code-check.py SHEET.

Batch 9's code check with batch 10's changes (batch 10's plan, "Before the tasks"): every row is
checked (no candidate is in the catalog or the aliases, so no row is exempt), the held-back
guard is compared with the sheet, and the builds, sound-alikes and aliases follow the sheet's
order. The test file's tables are read as literals, without importing the tests.
"""

import ast
import csv
import sys

from glitchygames.audio import instruments
from glitchygames.audio.instruments.brass_sound_alikes import BRASS_SOUND_ALIKES

TEST_FILE = 'tests/audio/test_instrument_catalog.py'


def test_table(name):
    """The literal value of a module-level table in the catalog test file."""
    with open(TEST_FILE, encoding='utf-8') as test_source:
        tree = ast.parse(test_source.read())
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target = node.targets[0]
        else:
            continue
        if target.id == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
rows_by_name = {row['name']: row for row in rows}


def held_back(row):
    """A WAIT for an engine feature or a build of its own, or an alias waiting for one."""
    if row['status'] != 'WAIT' or row['waits_for'] == 'a sourced range':
        return False
    if row['waits_for'].startswith('its target, '):
        target = rows_by_name.get(row['waits_for'].removeprefix('its target, '))
        return target is not None and held_back(target)
    return True


for row in rows:
    if row['status'] in {'SHIP', 'SOUND_ALIKE'}:
        entry = instruments.entry(row['name'])
        assert (entry.family, entry.lowest, entry.highest, entry.title) == (
            row['family'], row['lowest'], row['highest'], row['title'],
        ), row['name']
        parent = row['alias_of'] if row['status'] == 'SOUND_ALIKE' else None
        assert entry.sounds_like == parent, row['name']
        assert entry.tags == frozenset(), row['name']
    elif row['status'] == 'ALIAS':
        assert instruments.ALIASES[row['name']] == row['alias_of'], row['name']
    else:
        assert row['name'] not in instruments.CATALOG, row['name']
        assert row['name'] not in instruments.ALIASES, row['name']
assert test_table('BRASS_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'BRASS_HELD_BACK'
assert test_table('NEW_BRASS_NAMES') == [
    row['name'] for row in rows if row['status'] == 'SHIP'
], 'NEW_BRASS_NAMES'
assert list(test_table('BRASS_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'BRASS_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in BRASS_SOUND_ALIKES] == [
    row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'
], 'sound-alike order'
sheet_aliases = [row['name'] for row in rows if row['status'] == 'ALIAS']
assert [name for name in instruments.ALIASES if name in set(sheet_aliases)] == sheet_aliases, (
    'alias order'
)
print('matches', len(rows), 'rows')
```
  It cannot run until Task 1 has created `brass_sound_alikes.py` and the test tables.

---

### Task 1: Brass sound-alikes in their own module; the batch table's row; no sound-alike of `didgeridoo`; the held-back guard

**Files:**
- Create: `src/glitchygames/audio/instruments/brass_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/brass.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `BRASS: Final[tuple[CatalogEntry, ...]] = _BRASS_BUILDS + BRASS_SOUND_ALIKES` in
  `brass.py`, with `_brass`, `_muted`, the three level series and the nine shapes there under
  their current names. `BRASS_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test
  file gains `EXISTING_BRASS_NAMES: frozenset[str]` (the 42); `NEW_BRASS_NAMES: list[str]` and
  `BRASS_SOUND_ALIKE_PARENTS: dict[str, str]`, empty here, for Tasks 3 and 5 to fill;
  `BRASS_HELD_BACK: dict[str, str]`, empty here, for Tasks 3 and 5 to fill;
  `test_no_brass_name_held_back_for_a_feature_is_listed`; `'didgeridoo'` in
  `APPROXIMATING_NAMES`; and the row `Family.BRASS: BatchFamily(EXISTING_BRASS_NAMES,
  NEW_BRASS_NAMES, BRASS_SOUND_ALIKE_PARENTS)` in `BATCH_FAMILIES`. Also
  `build/brass-builds-before.txt`.

- [ ] **Step 1: Record the family's builds.** Run batch 4's Task 1 Step 1 command with
  `family='brass'` and `build/brass-builds-before.txt`. Expected: `recorded 42`.

- [ ] **Step 2: Write the tests.** After the flute lists, add `EXISTING_BRASS_NAMES` (the 42
  names, one per line, in catalog order, with the comment "# The 42 brass instruments that
  predate batch 10: their shared builds predate the anti-goal rule"), then `NEW_BRASS_NAMES:
  list[str] = []` and `BRASS_SOUND_ALIKE_PARENTS: dict[str, str] = {}`, each commented as batch
  9's lists are. Put the brass row after the flutes row in `BATCH_FAMILIES`, which is table
  order. In `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list gains
  `+ list(BRASS_SOUND_ALIKE_PARENTS)` after the flutes' line, and its comment reads "flutes,
  brass, bowed strings, …". Add `'didgeridoo'` to `APPROXIMATING_NAMES` on a line of its own,
  and extend its comment: "…, and batch 10's for the didgeridoo, built without the moving
  formants its page names (https://en.wikipedia.org/wiki/Didgeridoo: 'These formants, and
  especially their variation during the inhalation and exhalation phases of circular breathing,
  give the instrument its readily recognisable sound.')". After
  `test_nothing_waiting_for_a_glide_between_notes_is_listed`, add:
```python
# Every name plans/data/instrument-audit/batch-10.tsv holds back for an engine feature or a build
# of its own, with its waits_for: the WAIT rows whose reason is not "a sourced range", and the
# alias rows that wait for one of them, in the sheet's order. None ships under that name or as an
# alias until the engine or the build exists (decision 4; batch 10). The test matches exact names
BRASS_HELD_BACK: dict[str, str] = {}


def test_no_brass_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a brass instrument the sheet holds back for a feature."""
    assert set(BRASS_HELD_BACK) & set(instruments.names()) == set()
    assert set(BRASS_HELD_BACK) & set(instruments.ALIASES) == set()
```

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or approximated or held_back" -v`
  Expected: PASS, with the ID `[brass]` second. These are guards: they pass now and hold the
  later tasks.

- [ ] **Step 4: Split the table.** Read every comment in `brass.py` first. Rename its tuple
  `_BRASS_BUILDS`, unchanged, and define `BRASS` after it as the concatenation, importing
  `BRASS_SOUND_ALIKES`. Add a sentence to the module docstring, after the first line's
  paragraph: "The family's sound-alikes, listed instruments that share another entry's build,
  are in ``brass_sound_alikes.py``." Create `brass_sound_alikes.py` with the empty table and
  `flute_sound_alikes.py`'s docstring with "Brass" for "Flutes" and ending "The family's builds
  are in ``brass.py``." If the process-state guard then asks for an entry for `_BRASS_BUILDS`,
  `BRASS` or `BRASS_SOUND_ALIKES`, that is a finding: `flute_sound_alikes.py` needed none, so read
  why before writing any reason.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `family='brass'` and `build/brass-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
SKIP=replay-metrics git commit -m "Instrument catalog: brass sound-alikes in their own module; no sound-alike of the didgeridoo; the held-back guard" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The chromatic brass sheet: valved, slide, keyed and fingered (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. Put no personal data in any request, in a header,
a URL or a payload. A list or category page is a source for a name only. The sound, the title
and the range come from the instrument's own page, or from an encyclopedia, maker, museum or
conservatory under range ruling 7. The audit's "VERIFIED" rows and its quotes are leads, not
sources, so fetch them. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-10.tsv`
- Create (not committed): `build/batch-10-half-a.tsv`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `brass.md` ("Rejected or corrected proposed
  entries", "Aliases", "Range checks", "Modeling notes"); `new-noise-makers.md` for
  `corrugahorn`; `batch-1.tsv` to `batch-9.tsv`; `build/batch-10-names-before.txt`,
  `build/batch-10-half-a.txt`, `build/batch-10-half-b.txt` and `build/batch-10-form-check.py`.
- Produces: `batch-10.tsv` with batch 9's header:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `brass` on every row, and `tags` is
  empty on every row. A SHIP or SOUND_ALIKE row has `lowest`, `highest`, `range_source`, and
  `notes` holding `Range:`. `hs` is the Hornbostel–Sachs class a fetched source gives (`423.…`),
  else `none`. A candidate row's `audit_name` is its name in `build/batch-10-candidates.txt`; an
  alias row's is its audit line. Also `build/batch-10-half-a.tsv`, the half as committed, which
  Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-10-half-a.txt`'s order,
  then one per half-A alias name (7), in the plan's order.

  The rules are batch 9's, changed for this family:

  1. **SHIP** only with name, title, range and sound from fetched sources. Quote in `notes` the
     passage that describes the sound or construction (bore, bell, material, mouthpiece, valves,
     slide, keys or finger holes) and, after `Range:`, the passages that give the range, then the
     derivation under the range ruling. The `builder` cell gives the shape (one of the nine, or a
     new shape under the plan's ruling). It says which values come from the source and which are
     sound design.
  2. **SOUND_ALIKE**: a verified instrument that rule 7 finds would sound like an existing entry
     or a SHIP row of this half. `alias_of` is its parent. The `notes` begin "Sound-alike:",
     quote the source's description, and say why that entry is the nearest (for a size or key:
     the entry its source relates it to, nearest in register). It has its own range under the
     ruling. The parent is a catalog name or a SHIP row of this half. It is never another
     sound-alike, never one of `APPROXIMATING_NAMES` (now with `didgeridoo`), and in another
     family only when the source relates them.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row of this half. A size the source makes the catalog entry's own
     standard instrument is ALIAS of it (the plan's sizes ruling). If the target waits, the row is
     WAIT with `waits_for` `its target, <name>`. If the target is dropped, the row is DROP "its
     target, <name>, is dropped".
  4. **WAIT** when the identifying sound needs a feature the engine lacks, named in `waits_for`
     with the source quoted, under the plan's decisions (`moving formants`, `its own build`, `a
     pitch LFO (portamento between notes)`, `a pitch LFO (vibrato)`, `an amplitude LFO`, `more
     than four sources`, `sub-audio fundamentals`, `a range above C8` and the rest named in
     Global Constraints), or `a sourced range`. The feature must be the sound the source
     describes, not one the instrument merely has: a slide or valves is not a glide (the plan's
     ruling). Any other name is allowed only with the source quoted, and Task 6 lists it in #80.
  5. **DROP** a row that does not exist as described, belongs to another family (name it), is a
     one-off or a single artefact, or is already decided: in the catalog under that name (name
     the entry), an alias already (name its target), or a row of an earlier sheet (name the sheet
     and its status).
  6. A row the audit marks "(memory)" has no sourced sound or range yet. Fetch the instrument's
     own page; the audit's URL is a lead, and its caveat says some are guessed titles. If no page
     can be found, the row is DROP "no fetched source describes it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='brass'))"`
     and the builds in `brass.py`) and every SHIP row above it. If no sourced trait (bore, bell,
     material, mouthpiece) makes it sound different, it is a SOUND_ALIKE under rule 2. A number
     chosen only to differ does not count, and neither a range nor the way notes are chosen
     (valves, slide, keys) is a sound trait.
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word (`buccin` and `buccina`) are decided each on its own page.

- [ ] **Step 2: Run the form check.**
  Run: `uv run python -I build/batch-10-form-check.py plans/data/instrument-audit/batch-10.tsv`
  Expected: `56 rows;` and the counts, then `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-10.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-10-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-10-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
"
```
  Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-10.tsv build/batch-10-half-a.tsv
git add plans/data/instrument-audit/batch-10.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 10's verification sheet, the valved, slide, keyed and fingered brass" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The valved, slide, keyed and fingered brass

**Files:**
- Modify: `brass.py` (new builds after the 42, any new shape beside the nine),
  `brass_sound_alikes.py` (`BRASS_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its source
  URL in a comment), and `tests/test_process_state_guard.py` (a new shape's `CATALOG_BUILD`
  line)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-10-half-a.tsv` (half A as committed), Task 1's lists and
  `build/batch-10-code-check.py`.
- Produces: `NEW_BRASS_NAMES`, `BRASS_SOUND_ALIKE_PARENTS` and `BRASS_HELD_BACK` filled with
  this half's rows, which Task 5 extends.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills
only `BRASS_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_BRASS_NAMES` with one name per SHIP row and
  `BRASS_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row, each in the sheet's
  order. Fill `BRASS_HELD_BACK` with one `name: waits_for` per held row (the plan's held-back
  decision: every WAIT row whose reason is not `a sourced range`, and every `its target, <name>`
  row whose target is held), in the sheet's order. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, in the sheet's order, with a docstring sentence
  for batch 10. A shipped size joins its chain in
  `test_sized_families_descend_from_highest_to_lowest` (a `soprano trombone` goes first in the
  trombones'), or starts one under the plan's sizes ruling, in descending order of lowest note.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or descend or held_back" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the
  held-back test passes.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in `BRASS_SOUND_ALIKES`,
  in the sheet's order, under a section comment naming `plans/data/instrument-audit/batch-10.tsv`
  as `flute_sound_alikes.py`'s does, each a `CatalogEntry(name, title, Family.BRASS, lowest,
  highest, sounds_like=parent)`. Above each, put a comment with its `sound_source` and
  `range_source` URLs, the quoted passages and the range's derivation, as
  `flute_sound_alikes.py`'s entries have. A SHIP row is a `CatalogEntry` after the 42 in
  `_BRASS_BUILDS`, carrying the same comment and marking the values that are sound design. Each
  ALIAS row goes in `aliases.py` under a "Batch 10's brass" section, in the sheet's order, with
  its URL and quote. A new shape gets its own test of the trait it exists for, as batch 2's
  `test_the_pianet_settles_from_a_bright_strike` does.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range or the build. Check it against the source, and never trim the range to
  pass. Then run:
  `uv run python -I build/batch-10-code-check.py build/batch-10-half-a.tsv`
  Expected: `matches 56 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 10's valved, slide, keyed and fingered brass, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The natural horns and trumpets sheet, with the shells and animal horns (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-10-half-b.tsv`, half B's rows under the sheet's header
- Modify: `plans/data/instrument-audit/batch-10.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-10-form-check.py` and
  `build/batch-10-half-b.txt`.
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-10-half-b.txt`'s order, then one per half-B
alias name (16), in the plan's order. A parent or alias target is a catalog name or a SHIP or
SOUND_ALIKE row of this half, never a half-A row. These rules apply to this half on top of Task
2's:

- **Natural ranges.** A natural horn's or trumpet's range is its stated lowest and highest notes,
  or harmonic numbers under range ruling 4, never a range derived from its length or key. The
  audit's natural trumpet note ("commonly used range from 3rd to 16th harmonic … roughly C3 to C6
  … plausible") is hedged twice, so it is not a range. A horn or shell with one stated note waits
  under ruling 9.
- **Shells and animal horns.** `shankha`, `horagai`, `dung dkar`, `pututu`, `putatara`,
  `fotuto` and `triton shell` are SOUND_ALIKE rows of `conch` (C4-E4) when their source relates
  them to the conch shell trumpet and gives a range, ALIAS of `conch` when their source calls
  them another name for it, and otherwise WAIT. `abeng`, `bukkehorn`, `steerhorn`, `swedish
  cowhorn` and the other animal horns relate to `shofar` (A3-E4) or `natural horn` only when
  their source says so.
- **Wooden and bark horns.** `bucium`, `trembita`, `birch trumpet`, `midwinter horn`,
  `holztrompete` and the like relate to `alphorn` when their source does; the audit's `alpenhorn`
  and `swiss horn` are ALIAS rows of `alphorn` on a cited page.
- **Didgeridoo-type and voiced horns.** `yidaki` and `mako` are ALIAS of `didgeridoo` if a fetched
  source calls them its names (an alias of an approximating entry is allowed). A drone horn whose
  source names the vocal tract's formants as its sound WAITs `moving formants`; one played with
  the singing or shouting voice WAITs `its own build`.
- **Inharmonic and long horns.** `carnyx` follows the inharmonic ruling by what its fetched page
  says. The very long horns (`dungchen`, `karnay`, `nafir`, `kakaki`, `haotong`) are ranged like
  any other, waiting `sub-audio fundamentals` only for a stated note below A0, and `a sourced
  range` otherwise.
- **Ancient instruments.** A Roman, Greek, Bronze Age or biblical instrument (`cornu`, `tuba
  romana`, `buccina`, `lituus`, `salpinx`, `lur`, `chazozra`, `hatzotzerah`) ships only with a
  range a source states for a replica or a surviving instrument, as a museum record does. A range
  reconstructed by conjecture ("may have", "is thought to") is hedged under ruling 5. `chazozra`
  and `hatzotzerah` are one instrument: rule 8 decides them.
- **Artefacts.** `brudevaelte lur` and `savernake horn` are DROP "a single surviving artefact, not
  a type a game would ask for" when their page describes one find. `luren` follows rule 3 with
  `lur` as its target.
- **`corrugahorn`** is DROP "already decided: batch-1.tsv WAIT (a sourced range), in noise
  makers" (the plan's hand-offs ruling).

- [ ] **Step 1: Write half B's rows** to `build/batch-10-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-10-form-check.py build/batch-10-half-b.tsv`
  Expected: `71 rows;` and the counts, then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-10-half-b.tsv >> plans/data/instrument-audit/batch-10.tsv`.
  Run the form check on the whole sheet.
  Expected: `127 rows;` and the counts, then `bad: []`, exit 0. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 2 Step 3's command
  with `half_a | half_b` in place of `half_a` on its `missing:` and `twice:` lines, and print
  `'extra:', sorted(set(audit_names) - half_a - half_b)` in place of the half-B line.
  Expected: `missing: []` and `twice: []`. `extra:` lists only the alias lines, because an alias
  row's `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-10.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 10's verification sheet, the natural horns and trumpets, shells and animal horns" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The natural horns and trumpets, shells and animal horns

**Files:**
- Modify: `brass.py`, `brass_sound_alikes.py`, `aliases.py`, `tests/test_process_state_guard.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-10.tsv`'s half-B rows, Task 3's lists and `build/batch-10-code-check.py`.
- Produces: the finished family.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `NEW_BRASS_NAMES`,
  `BRASS_SOUND_ALIKE_PARENTS`, `BRASS_HELD_BACK` and the alias parameters, after half A's, as in
  Task 3 Step 1.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes, aliases after half A's aliases, under a
  second section comment naming the sheet.

- [ ] **Step 4: Run the suite and check the code against the whole sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`, then
  `uv run python -I build/batch-10-code-check.py plans/data/instrument-audit/batch-10.tsv`.
  Expected: PASS, then `matches 127 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 10's natural horns and trumpets, shells and animal horns, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a brass
  paragraph with its count, naming `brass.py` and `brass_sound_alikes.py`, with examples.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `brass` row's
  count and examples, the sound-alike modules sentence and its total).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 10
  done, pointing at this plan and `batch-10.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 10 DONE";
  - batch 10 done, with the sheet's counts by status and the family's growth;
  - the audit's unclosed gaps, as a later pass;
  - `corrugahorn`'s family question still open, and the mutes left to the articulations design;
  - a "Plan (batch 10)" line, the Status line, and the next batch named: double reeds.

  Add #80 (the highest item is #79), "Sound Engine: The Owner's Checks on Instrument Catalog
  Batch 10 — TODO". Use #79's form, place it directly after #79, and give it the Priority
  "(before the double reeds batch builds on the same catalog)". Its **Listen** section
  (`build/instruments/brass/`) covers the new builds, then the sound-alikes beside their parents,
  then the aliases. Its **Calls to confirm** are:
  - every WAIT, by reason, with names;
  - the range ruling (stated or an exact span, sounding pitch with the source's own
    transposition, no pedal or player's top beyond the stated compass, harmonic numbers only
    with a stated fundamental, never hedged, the standard key, maker and museum sources, nothing
    below A0 or above C8, one-note horns), and every derived range;
  - one-note horns and shells waiting for a range: should they ship as fixed-pitch entries?
  - `didgeridoo` among the approximations, never a parent, its aliases allowed, and the
    moving-formant waits;
  - slides, valves and keys as note choice, not sound, and any portamento wait;
  - the inharmonic ruling (`carnyx`) and any build-of-its-own wait;
  - any new shape and the trait its source names;
  - sizes and keys as sound-alikes, standard sizes as aliases (`treble cornett`, `tenor horn`),
    and the piccolo trumpet's B-flat row;
  - mutes out of scope (the spec's Non-goals);
  - `corrugahorn`: noise makers or brass, still open from batch 1;
  - one-offs, artefacts and unsourced rows dropped;
  - `BRASS_HELD_BACK`, the guard for every held name;
  - the two-half split by Hornbostel–Sachs class as explicit lists, the sheets researched in
    parallel, the shared files written up front, and any code task skipped by ruling;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): `didgeridoo` built without
  the moving formants its page names; its range C2-E2 lies below the page's "fundamental
  typically A2 to G3" (hedged, so no range here, but the catalog's span is outside it); the 42
  earlier entries carry no source comment (the module docstring cites Adler and calls the folk
  ranges "typical"); any existing range a sheet's source contradicts. Then **Follow-ups**: the
  audit's gaps; ranging the range WAITs from maker and museum sources; checking the 42 earlier
  entries against sources; the engine changes that unblock the waits, most rows first.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries()))"`
  and `uv run python -I build/batch-10-form-check.py plans/data/instrument-audit/batch-10.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-10-code-check.py plans/data/instrument-audit/batch-10.tsv
```
  Expected: everything passes with no warnings (a warning is a finding), and `matches 127 rows`.
  The `build/instruments/brass` folder is the one to listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 10 of the instrument catalog (brass), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch
in turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78).
The pre-push hooks take about 40 minutes, and nothing in the working tree may change while they
run.

**Order:** the controller's shared files, then Tasks 1, 2 and 4 in parallel. Task 3 follows
Tasks 1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows Tasks 3 and 4, and Task
6 comes last.
