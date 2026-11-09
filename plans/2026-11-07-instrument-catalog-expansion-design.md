# Instrument catalog expansion — Design

- **Date:** 2026-11-07
- **Status:** DESIGN, requested by the owner (2026-11-06: "I want every musical instrument known
  to man"; 2026-11-07: "do an adversarial audit for each musical category and then for
  potentially missing categories and each of those once they're defined"). Batch 1 (plucked
  idiophones, friction instruments, noise makers, tags and aliases) is done: see
  `plans/2026-11-07-instrument-catalog-batch-1-implementation.md` and its audit sheet
  `plans/data/instrument-audit/batch-1.tsv`. Batch 2 (electromechanical and sound effects) is
  done: see `plans/2026-11-08-instrument-catalog-batch-2-implementation.md` and
  `plans/data/instrument-audit/batch-2.tsv`. The later batches are not yet planned.
- **Depends on:** the instrument catalog (`src/glitchygames/audio/instruments/`, 431 instruments
  in 18 families when this was written, shipped with the sound engine M1; 439 in 21 after batch
  1, 448 in 23 after batch 2), its range audit, and the engine's four sources per instrument
  (`src/glitchygames/audio/instrument.py`).
- **Tracked as:** `plans/future-features.md` #70.

## Intent

The catalog should hold every musical instrument a game might want a voice for, from the
orchestra to the marxophone, the bullroarer and the Game Boy's noise channel, each with a
correct range and a recognisable sound. It is reference data as much as code: a wrong range or a
made-up instrument is a bug, so every addition has to be traceable to a source.

## Goals

1. Add the instruments the audits found, in batches by family, each batch verified against
   sources before it lands.
2. Settle the family list: which new families exist, and where boundary instruments go.
3. Record, per instrument, where its name, range and description came from.
4. Say plainly which instruments the engine cannot make yet, and what engine feature each needs,
   instead of shipping a poor imitation under the real name.

## Non-goals

- Every regional name as its own instrument. A name for the same instrument is an alias
  (resolvable by `instruments.get`), not a catalog entry.
- Articulations and ensemble patches (pizzicato, mutes, string sections): those are instrument
  settings, a separate design.
- Engine features (FM, samples, sympathetic strings, moving formants). This design lists them;
  each is its own work.

## Anti-goals

- An entry whose range or description is from memory with nothing saying so.
- A family boundary that changes with whoever wrote the entry.
- Bulk-adding hundreds of instruments that all sound like the same three timbres.

## What the audits found (2026-11-07)

Two rounds of audits, kept in `plans/data/instrument-audit/` (`merged.tsv`, every candidate
with its audit, family, range, range status and sources; one Markdown file per audit; `round-1/`
for the first round):

- Round 1 (2026-11-06): five agents, one per Hornbostel–Sachs class, 402 candidates.
- Round 2 (2026-11-07): one adversarial agent per catalog family (18 families; voices and choirs
  together), one for missing categories, then one per proposed new family (5). Each attacked
  round 1's list and searched for more, mostly with Wikipedia's list and instrument pages; a few
  reached the Met and MIMO.

Round 2 produced **1,343 candidate rows, 1,303 unique names** after removing 39 names that two
audits both listed. Two are already in the catalog (they are proposed moves). By audit:

| Audit | Rows | Audit | Rows |
|---|---|---|---|
| plucked strings | 171 | bagpipes | 64 |
| drums and percussion | 158 | organs | 50 |
| tuned percussion | 110 | clarinets | 40 |
| voices and choirs | 106 | keyboards | 40 |
| electronic | 103 | plucked idiophones (new) | 38 |
| flutes | 94 | free reeds | 32 |
| brass | 89 | noise makers (new) | 21 |
| bowed strings | 75 | harps | 20 |
| double reeds | 69 | friction instruments (new) | 16 |
| struck strings | 14 | mechanical instruments (new) | 16 |
| saxophones | 12 | environmental (new) | 5 |

**Quality.** Only **84 of 1,343 ranges are verified** against a fetched source. Most
traditional instruments have no published range at all, so the audits mostly marked them
UNVERIFIED rather than guess. About 80 rows are flagged as needing an engine feature the
catalog lacks. The first pass of several round-2 audits was done from memory (the web tools
were not loaded); those were redone with sources. Round 1's ranges were largely unsupported
and round 2 corrected or discarded them.

**Corrections to the current catalog found on the way:**

- `whip` is titled "Whip (slapstick)" and is a slapstick; a real whip crack (H-S 411) is missing.
- `glass harmonica` and `singing bowl` move to friction instruments; `kalimba`, `mbira` and
  `music box` to plucked idiophones; the electromechanical voices to electromechanical.
- The recorder sizes follow one naming (great bass C3, contrabass F2, the Paetzold/Mollenhauer
  convention); a second "great bass in F" exists elsewhere. Not a bug, but the titles could state
  the lowest note to remove the ambiguity.

## Design

### Families

The 18 families stay, and five are added (the owner, 2026-11-07, for every row below):

| Family | Holds | Decision |
|---|---|---|
| plucked idiophones | jaw harps (H-S 121.2), lamellophones (mbira, likembe, marimbula), music-box combs (122) | **Add.** A distinct mechanism and sound; ~40 instruments. Kalimba, mbira and music box move in |
| friction instruments | musical saw, nail violin, daxophone, glass harmonica and harp, verrophone, Cristal Baschet, terpodion (H-S 13) | **Add.** ~16 instruments; glass harmonica and singing bowl (when rubbed) move in |
| noise makers | bullroarers, sirens, whirled tubes, klaxons and air horns, party horns, whip cracks (H-S 41) | **Add.** ~21 |
| sound effects | theatre and Foley devices that are not instruments: thunder sheet, wind machine, rain machine, cannon, and the like | **Add.** Their own family; see "Sound effects" below |
| electromechanical | instruments whose sound is made mechanically and picked up or generated electrically (H-S 51, 52): Hammond, Rhodes, Wurlitzer, Clavinet, Telharmonium | **Add,** split from electronic, which keeps purely electronic sound (H-S 53: synthesizers, sound chips, theremin, ondes Martenot); electronic would otherwise pass 100 entries |
| mechanical instruments | music boxes, barrel and fairground organs, orchestrions, player pianos | **A tag, not a family** (`Tag.MECHANICAL`, see "Tags"): each sounds like an existing family; only ~9 have their own timbre |
| environmental instruments | sea and wave organs, aeolian harps, suikinkutsu | **Drop.** Mostly one-off installations; the 5 usable voices go to existing families (aeolian harp: plucked strings; wind chimes: tuned percussion; pyrophone: organs) |

A family is defined by **how the sound is made** (the Hornbostel–Sachs class), with the existing
player-facing splits kept where they already exist (keyboards and organs; voices and choirs),
and sound effects as the one family defined by use.

**Boundary calls** (the owner, 2026-11-07): friction drums (cuíca, lion's roar) stay in drums and
percussion; duck calls and signal whistles go in flutes (they are edge-blown); the kazoo goes in
voices (it colours a voice); the hydraulophone goes in flutes (Hornbostel–Sachs gives it no
class).

### Tags

A grouping that cuts across families is a tag, not a family (the owner, 2026-11-07):

- `CatalogEntry.tags: frozenset[Tag]`, empty by default. `Tag` is a closed `StrEnum` beside
  `Family` in `audio/instruments/catalog.py`, so entries cannot drift into synonyms
  ("mechanical", "automatic", "self playing"); a new tag is a deliberate change to the enum.
- The first tag is `Tag.MECHANICAL`: instruments that play themselves from a pinned cylinder,
  punched disc, roll or book (music boxes, barrel and fairground organs, orchestrions, player
  pianos, serinettes). Each stays in the family it sounds like.
- `instruments.names(tag=Tag.MECHANICAL)` lists them, beside `names(family=...)`; both may be
  given together.
- Later tags (`chip` for the sound-chip voices, `historical`, regions) are added the same way
  when a batch needs one.
- Tests: every entry's tags are members of `Tag`; `names(tag=...)` returns exactly the tagged
  entries.

### Sound effects

The owner's rule (2026-11-07): sound effects must be usable in music. Every catalog entry, sound
effects included, is an `Instrument` built from waveforms and noise, so each one is playable as
a note in a sequence like any other instrument (a thunder sheet on beat 1 of bar 9). An
unpitched effect ignores the pitch it is given, as the drums already do. How a song places any
sound, not only catalog instruments (a game's `[sounds]` entries, effects with notes of their
own), is designed in `plans/2026-11-06-music-and-instrument-formats-design.md`, "Any sound in a
sequence".

### Batches

One batch per family, in this order: the new families first (they fill the biggest
gaps for games), then the largest existing ones (drums and percussion, plucked strings, tuned
percussion, electronic, bowed strings), then the rest. Each batch is one PR:

1. **Verify:** every name, range and description checked against a source cited in the code,
   as the catalog's existing range audit did. A range that no source gives is the instrument's
   documented playable span from a maker or museum, or the entry waits.
2. **Prune:** merge aliases into the alias table; drop entries that are the same sound under
   another name, unless a game would ask for them by name (then an alias).
3. **Build:** reuse the existing timbre builders in `timbres.py`; add a builder only for a
   genuinely new sound.
4. **Test:** the existing catalog tests (names, ranges, every instrument renders) cover each
   entry; a new builder gets its own test.

### Sources recorded per instrument

Each entry cites its source in a comment, as the catalog does now. The audit tables keep the
URL and whether the range was verified; the code comment carries the URL.

### What the engine cannot make yet

| Needs | Instruments |
|---|---|
| sympathetic strings, a buzzing bridge (jawari) | sitar, sarangi, tanpura, rudra veena, hardanger fiddle, viola d'amore |
| moving formants, vowel glides, vibrato | overtone and throat singing, talk box, vocoder, yodel |
| FM synthesis | DX7-style voices, OPL/OPN sound chips (AdLib, Mega Drive) |
| sample playback | Mellotron, Chamberlin, Optigan, sample-based drum machines |
| more than four sources | orchestrion, violano-virtuoso, large mixtures |
| sub-audio fundamentals | octobass lowest notes, bullroarer, some sirens |

The engine already has a pitch glide (`pitch_curve`); it lacks pitch and filter LFOs. These
instruments wait for the feature (the owner, 2026-11-07): none ships as an approximation under
its real name or a qualified one. Each feature's design lists the instruments it unlocks.

## Tests

- The existing catalog tests run on every new entry: names follow the naming rule, ranges are
  valid notes with lowest below highest, every instrument renders without clipping.
- Aliases resolve to exactly one entry; no alias equals a catalog name.
- A family test: every entry's family is one of the declared families.

## Decisions (the owner, 2026-11-07)

1. New families: plucked idiophones, friction instruments, noise makers, sound effects and
   electromechanical; mechanical instruments are a tag; no environmental family.
2. Boundary calls as listed under "Families".
3. Electronic is split into electromechanical (H-S 51, 52) and electronic (H-S 53).
4. Instruments the engine cannot make well yet wait for the feature.
5. Sound effects are a family, and every one is usable in music.
6. The audit tables are kept in `plans/data/instrument-audit/` as the batches' working list.

7. Tags are a `tags: frozenset[Tag]` field on `CatalogEntry`, where `Tag` is a closed enum like
   `Family`; see "Tags".

## Open questions

None at the moment.
