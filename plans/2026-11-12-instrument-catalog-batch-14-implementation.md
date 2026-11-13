# Instrument catalog batch 14 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the clarinet family from the audits' candidates. The family holds the single-reed
woodwinds with a cylindrical bore: the orchestral clarinets in every key and size, their early and
modern relatives, and the folk single-reed pipes, single, double (the double clarinets) and
horn-belled. Each instrument gets a cited source for its name, its sound, its reed and bore, its
range (with its stated transposition when the range is written) and any drones, and either sounds
unlike every other entry or is a listed sound-alike of the one it sounds like. The rest become
aliases, wait for an engine feature or a source, or are dropped with a reason.

**Architecture:** As in batches 3 to 13, a verification sheet (`batch-14.tsv`) decides every
candidate before any code is written. The family's 9 entries live in `winds.py` (331 lines, which
also holds the saxophones and the free reeds), so they move unchanged to a new `clarinets.py`, as
batches 9, 11, 12 and 13 moved the flutes, double reeds, bagpipes and organs. Its table is
`_CLARINET_BUILDS`, and `CLARINETS` becomes `_CLARINET_BUILDS + CLARINET_SOUND_ALIKES`, with the
sound-alikes in a new `clarinet_sound_alikes.py`. The catalog's `_clarinet` build already favours
odd harmonics ("A closed cylinder: odd harmonics, with only a trace of the even ones"), so a new
cylindrical clarinet needs no new table: with no other cited trait it is a sound-alike. A SHIP is
possible only for a cited trait the engine can make that no clarinet build has yet: drones (a
double clarinet's drone pipe, through `timbres.with_drones`) or two unison pipes at a sourced
detune (`blown`'s `chorus_cents`). A conical single reed is the saxophones' class, not this
family's. A new guard, `CLARINET_HELD_BACK`, holds every name the sheet holds back for any reason
but a sourced range. The sheet and the code each come in two halves, as explicit lists: the
orchestral and modern clarinets, then the folk single-reed pipes. The controller writes the names
file, the candidate lists and the three check scripts before anything is dispatched, so the two
sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `falling_series`,
`wave_from_levels`, `with_drones`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all). Batch 13's plan (`plans/2026-11-12-instrument-catalog-batch-13-implementation.md`)
and its owner's checks (`plans/future-features.md` #83) are this plan's template and its ledger:
its controller step, its quote check on the raw page text, its held-back guard, its two parallel
halves and its code check (as fixed during batch 13: an "Already decided" DROP that was a catalog
name or alias before the batch must still resolve) carry over. Batch 12's plan holds the drone
ruling, the chanter-bore rule (a source wait for an unsourced bore) and the double-chanter ruling;
batch 11's plan holds the transposition rule ("a written range counts only with its stated
transposition") and the balaban rule (a cited trait the build cannot make means the row waits);
batch 4's plan (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) holds the pitched
sound-alike and strict range rules and the before-and-after build record. This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-14-implementation.md`. The branch is
`feat/instrument-catalog-batch-14`, made from `feat/instrument-catalog-batch-13` at its HEAD (batch
13's fix commit, which corrects OCR quotes in comments and changes no build); Task 6 records that
SHA in #70. The candidates come from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `clarinet` (40, every one from the round-2 audit
  `clarinets.md`);
- the `round-1/merged-missing.tsv` rows whose `family` contains `clarinet` (5: `alboka`, `arghul`,
  `launeddas`, `tarogato`, `bohlen pierce clarinet`).

Together: **45 unique candidate names** (counted for this plan, the controller recounts). None is
in the catalog or the alias table today, and every one is already a valid catalog name. The
audits' alias lines that name a clarinet candidate propose **6 alias names** that are not
candidates: `cifte`, `argun` and `argul` (`clarinets.md`: "cifte (argun, argul) -> arghul"), and
`maui xaphoon`, `pocket sax` and `xaphoon de catalunya` (`saxophones.md`: "maui xaphoon ->
xaphoon", "pocket sax -> xaphoon (the ABS plastic version, sold since 2000)", "xaphoon de catalunya
-> xaphoon"; the xaphoon is decided here, as batch 13 took the mechanical audit's organ alias
lines). The other `clarinets.md` alias lines propose none: "hornpipe -> pibgorn / stock and horn
are regional forms of one construction" and "zummara: ... Consider folding into mijwiz" name only
candidates, decided by their own rows (rule 8); "pku -> unknown" names no target, and the audit
lists Pku among its gaps; "octavin -> possibly similar to xaphoon in modeling; separate
instruments" proposes none. The round-1 alias tables (`round-1/aerophones.md`: "sipsi, sneng |
chalumeau", "piccolo clarinet, sopranino clarinet | e flat clarinet" and the rest) are not used, as
no earlier batch used them; every candidate they name is decided by its own row. So the sheet will
hold **51 rows**.

The hand-offs from earlier sheets (checked: `batch-1.tsv` to `batch-13.tsv`, and
`plans/future-features.md` #70–#83):
- `tarogato`: batch 11's plan ("the tárogató is the clarinets batch's"; `double-reeds.md`: "cornu
  / tarogato modern -> single reed, not this family"). A half-A candidate, decided by the bore
  boundary below.
- `sneng`: `batch-10.tsv` WAIT `a sourced range` (brass: the end-blown horn; its page gives the
  common side-blown form "a bamboo single-free-reed mouthpiece", 422.33, a free reed). Already
  decided, so its row is DROP "Already decided: batch-10.tsv WAIT, a sourced range (the end-blown
  horn, brass; its side-blown form a free reed)".
- Already decided, not handed, and not candidates: `zamr` (`batch-11.tsv` DROP, "an ambiguous name:
  also the double clarinet (clarinets)"), `mizmar` (`batch-11.tsv` DROP, a generic term), `zukra`
  (`batch-12.tsv` WAIT, a bagpipe whose bagless form is a double clarinet) and `organ clarinet`
  (`batch-13.tsv` SHIP, the organ stop). No row is added for them.
- The catalog's `chalumeau` (F3-Bb4, no source) is an existing entry, not a candidate. The audit's
  "chalumeau: Wikipedia gives no per-size range ... UNVERIFIED" is a lead for #84's bugs.
- #83 says "No name the sheets found belongs to the clarinets batch", and #76–#82 hand nothing here.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, hyphens and keys' flat signs go only in the title
  (`tarogato` for "Tárogató", `clarinet d amore` for "Clarinet d'amore"). A key goes before the name,
  as in the catalog (`e flat clarinet`, `a clarinet`). A candidate keeps its audit name (the naming
  ruling of batch 12).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families),
  "with the existing player-facing splits kept where they already exist". The clarinet family
  holds the single-reed aerophones with a cylindrical bore, one pipe or a set (H-S 422.211 and
  422.221), mouth-blown; the saxophones hold the conical ones (422.212) and the bagpipes the
  bag-blown ones (the -62 suffix). The bore boundary below decides each row.
- "Every name, range and description checked against a source cited in the code … A range that no
  source gives is the instrument's documented playable span from a maker or museum, or the entry
  waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict"). This
  plan's range ruling is below. A row with no sourced range is WAIT, `waits_for` `a sourced range`,
  and the range is checked before any engine limit (batch 13's reversals: a row with neither a
  range nor a buildable trait waits for the range, its notes keeping "Engine limit, once ranged:
  …").
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry, sharing
  the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the same
  instrument) stays an alias." "So `sound_changes` (keyword overrides of the parent's builder,
  empty by default) lets a sound-alike differ by a sourced trait." A sound-alike is pitched exactly
  when its parent is, and a pitched sound-alike gives its own sourced range (batch 4). No
  sound-alike in this batch carries a `sound_changes`: no clarinet trait is carried that way here.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as an
  approximation, under its real name or a qualified one. The spec's table binds this family
  through "sub-audio fundamentals" and "more than four sources". Earlier batches added the other
  names a WAIT may give: a pitch LFO (vibrato), a pitch LFO (portamento between notes), an
  amplitude LFO, a pitch and amplitude LFO (batch 2), filter resonance, a filter envelope, moving
  formants (batch 6); a buzzing membrane (batch 5); a sourced drone tuning and its own build (batch
  7); a range above C8 (batch 10); a sourced detune (batch 13). This plan adds one source wait, `a
  sourced reed and bore` (below). What the engine has: up to four `Source`s, each with its own
  semitones, detune and fixed pitch; `blown` (a harmonic series of up to 32 harmonics in one wave,
  attack, release, breath noise, low pass, drive, a static `chorus_cents` copy, a `bite`);
  `with_drones` (a chanter's `tone` and `breath` kept, "at most two with breath" fixed-pitch
  drones); one glide per note (`pitch_curve`); a fixed FIR low or high pass; no LFO of any kind.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not builds.
- Reuse the family's builder, which `clarinets.py` keeps under its current name: `_clarinet(*,
  slope, low_pass)`. Each entry's build is an inline `partial(...)`. Add a builder or keyword only
  for a genuinely new, sourced sound (`_drone_clarinet`, `_clarinet`'s `chorus_cents`, below), and
  give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the sheet
  is verbatim from a page the worker fetched, and every `Range:`, `Drones:` and `Detune:` passage
  is quoted from the raw page text (the quote ruling). No request carries the owner's email or any
  personal data, in a header, a URL or a payload (#78, "Incidents and process").
- Code comments name committed files (`plans/data/instrument-audit/batch-14.tsv`), never the
  gitignored `build/` files (batch 9's fix).
- The 9 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 9. An existing entry changes only for a cited bug, and not in this batch:
  the 9 carry no source comment, so a range or build that a fetched source contradicts is reported
  in #84 for the owner, not changed here (batches 10 to 13's rule). The audit's "Range checks"
  give five sounding ranges from the Clarinet family page that differ from the catalog's
  (basset horn F2-F6 against F2-F5, alto G2-Eb6 against Bb5, bass Bb1-Bb5 against F5, contra-alto
  Gb1-C5 against G4, contrabass Bb0-G4 against Bb3): leads, which a worker who fetches that page
  checks under range ruling 10 and records for #84. Task 1's before-and-after record of every entry
  checks that the move changes nothing.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown by
  a test, you should understand why it's happening and be concerned": a warning is a finding, and
  it must be understood before going on.
- Commits as batches 4 to 13: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this plan,
  never from memory. Write no `.md` file beyond those Task 6 names. Never use `git stash`: the
  stack is shared with other worktrees and sessions (#80, "Incidents and process"). Set work aside
  with a temporary commit instead.

## Review Focus

1. **A written range read as sounding.** Every clarinet but the C clarinet transposes, and not
   all one way: a B-flat clarinet sounds a major second below written, an A-flat piccolo clarinet a
   minor sixth above, a bass clarinet a major ninth below, an octocontrabass clarinet more than two
   octaves below. Makers (Buffet Crampon, Selmer, Yamaha, Leblanc, Backun) publish written compasses.
   Range ruling 2 takes a written range only with the transposition its own source states (a key in
   the name is not one), the `Range:` passage shows the arithmetic, and the form check holds every
   range inside A0–C8.
2. **A conical single reed built as a clarinet.** The tárogató, octavin, heckel-clarina and
   heckelphone-clarinet are single reeds with conical bores by the audit, so their tone has every
   harmonic, not the clarinet's odd ones. The bore boundary drops them to the saxophones, the form
   check refuses a shipped row whose `hs` is not `422.2[12]1` (a cylindrical single reed), and the
   reed-and-bore wait holds a ranged row whose bore no source gives.
3. **A double clarinet's drone or beating pair shipped as one plain pipe.** The arghul, launeddas,
   diplica and pungi sound a drone pipe under the melody (the audit), and a pair of unison pipes
   that a source says are tuned apart (if one says so of the mijwiz, zummara or another pair) beats. The drone ruling ships a drone only at sourced
   pitches (`_drone_clarinet`), the detune ruling a beating pair only at a sourced detune, the code
   check compares each built drone and detune with the sheet, and
   `test_a_clarinet_sounds_its_sourced_drones` pins the drones.
4. **A size or key shipped as a new sound.** The piccolo, D, C and B-natural clarinets, the low G
   clarinet, the basset clarinet and the three birbynė sizes are clarinets of other sizes and
   keys: each is a sound-alike with its own range, never a SHIP, unless a cited trait the engine
   can make sets it apart (rule 7). `test_no_new_build_is_another_entrys_instrument` refuses a new
   build equal to an existing one.
5. **The same instrument shipped twice, or a name decided twice.** `hornpipe`, `pibgorn`, `stock
   and horn`, `zhaleika` and `pepa` (the audit: "regional forms of one construction"); `mijwiz`,
   `zummara` and `dozaleh`; `arghul` and the alias names `cifte`, `argun`, `argul`; `xaphoon` and
   `maui xaphoon`, `pocket sax`, `xaphoon de catalunya`; `mock trumpet` and the catalog's
   `chalumeau`; `birbyne` and its sizes; `sneng` (batch 10's). Rules 3, 5 and 8 and the
   generic-term ruling decide each, the form check refuses a name taken before the batch, and the
   code check finds every name exactly once.

---

## File Structure

- Create `src/glitchygames/audio/instruments/clarinets.py`. It takes the "Clarinets" section of
  `winds.py` (`_clarinet` and the 9 entries), unchanged, as `_CLARINET_BUILDS`, and `CLARINETS =
  _CLARINET_BUILDS + CLARINET_SOUND_ALIKES`. New builds go after the 9; a new builder sits beside
  `_clarinet`.
- Create `src/glitchygames/audio/instruments/clarinet_sound_alikes.py`, holding
  `CLARINET_SOUND_ALIKES`.
- Modify `winds.py` (the section and its clarinet sentence leave; it keeps the saxophones and free
  reeds), the sibling docstrings that name `winds.py` as the clarinets' home (`flutes.py`,
  `double_reeds.py`, `bagpipes.py`), `registry.py` (it imports `CLARINETS` from `clarinets.py`; its
  place in `FAMILY_TABLES`, after the flutes, doesn't change), `aliases.py` (the batch's ALIAS
  rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5). `tests/test_process_state_guard.py`
  is not touched: `_clarinet` builds its series inside the function, so no module-level table moves,
  and `winds.py`'s `FREE_REED_LEVELS` line stays.
- Create `plans/data/instrument-audit/batch-14.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #84), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #84):

- **Clarinets get their own module.** `winds.py` holds three families, and every family a batch
  has grown since batch 4 has a module of its own and a sibling sound-alikes module that names it
  ("The family's builds are in …"). The clarinet section is self-contained: only `registry.py`
  imports `CLARINETS`, no other module imports `_clarinet` (checked with grep; the test file names
  only `Family.CLARINETS`), it shares nothing with the saxophones and free reeds but `blown` and
  `falling_series` from `timbres.py`, and the process-state guard lists nothing of it. The move is
  mechanical, and Task 1's before-and-after record checks it.
- **The bore boundary.** A clarinet is a single reed on a cylindrical bore, which favours odd
  harmonics (`winds.py`: "a clarinet (a closed cylinder) favours odd harmonics, saxophones (cones)
  have every harmonic"); the catalog's two families split along Hornbostel–Sachs' own line, 422.211
  (single clarinets, cylindrical bore) and 422.212 (conical bore: the saxophones), with 422.221
  the sets of cylindrical pipes (double clarinets), the digits read as batch 12's form check reads
  them (`CHANTER_CLASS`; a worker who fetches the Hornbostel–Sachs page and finds the numbering
  otherwise reports it to the controller before any row relies on it). So:
  1. A row whose fetched source gives it a single reed and a cylindrical bore (or the class 422.211
     or 422.221) is this family's.
  2. A row whose source gives a conical bore (or 422.212 or 422.222) is DROP "belongs to saxophones
     (H-S 422.212): <its words>". The saxophones batch has not run, so Task 6 lists each in #70 for
     it (expected: `tarogato`, `octavin`, `heckel clarina`, `heckelphone clarinet`, as their pages
     decide).
  3. A row whose source gives a double reed is DROP "belongs to double reeds (H-S 422.1): <its
     words>" (batch 11 is done, so #70 lists it for a later double reeds pass); a free reed, DROP
     "belongs to free reeds (H-S 412.13): <its words>"; a bag, DROP "belongs to bagpipes".
  4. A ranged row whose sources do not give both its single reed and its bore, or give two with
     none called usual (the audit's birbynė: "Single- or double-reed (sources conflict)"), WAITs
     `a sourced reed and bore` (a source wait this plan adds, as batch 12 added `a sourced chanter
     bore`: the builder cannot be chosen without it). An unranged row WAITs `a sourced range` first.
  5. The `hs` cell holds the class a fetched source gives (an infobox, its own H-S category, or a
     sentence naming the reed and bore, quoted, with the code it implies), else `none`. A SHIP or
     SOUND_ALIKE row's `hs` matches `422\.2[12]1`.
- **A cylindrical clarinet is a sound-alike unless a cited trait sets it apart.** Every catalog
  clarinet is built by `_clarinet`, a closed cylinder's odd harmonics with a trace of the even
  ones, differing by `slope` and `low_pass` (sound design, by size). So a cylindrical single reed
  needs no new table (the cylindrical traits that batch 11's balaban and batch 12's säckpipa
  lacked are this family's own build). A row whose sources name no other trait is a SOUND_ALIKE of
  a catalog clarinet. A horn bell, an idioglot or heteroglot reed, the material (cane, bone, wood,
  plastic, metal), keys or keylessness, a fingering system, "shrill", "fruity", "piercing",
  "rustic" or "soft" are no trait (rule 7: a loudness or a colour word names nothing the build
  makes, and a horn bell is batch 13's "bell no buildable trait"), unless a fetched source names an
  effect on the sound that a builder makes. A trait the engine can make (drones, a sourced detune)
  is a SHIP under the next two rulings; a trait it cannot (a branched pipe made to sound conical,
  an inharmonic or buzzing reed, a vibrato its source makes the sound) is WAIT `its own build (<the
  trait>)` or the spec's or an earlier batch's feature name, with the source quoted.
- **The parent ruling.** A SOUND_ALIKE's parent is a catalog clarinet from before the batch or a
  SHIP row of its half, never another family's entry and never one of `APPROXIMATING_NAMES`:
  1. The entry its own source relates it to ("an A clarinet with an extended lower range", the
     basset clarinet; "a smaller E-flat", the piccolo), quoted in the notes.
  2. Otherwise the catalog clarinet, `chalumeau` excluded, whose `lowest` note is nearest the row's
     own lowest note in semitones, the higher-pitched entry on a tie (the builds grow darker with
     size). `chalumeau` is a parent only by rule 1.
  3. The sizes of one type (`birbyne`, `tenor birbyne`, `contrabass birbyne`) share the type's
     parent, or are sound-alikes of the type when it is a SHIP row: never a sound-alike's
     sound-alike.
- **The drone ruling** (batch 12's, for a double clarinet). A pipe that holds one note under the
  melody is a drone and part of the sound (the arghul's "melody pipe plus longer drone pipe", the
  audit), so a row with a drone pipe needs its drones sourced:
  1. Sourced as batch 12's drone ruling rules 1–4: each sounding drone's pitch as a note with its
     octave, a hertz figure, or an interval from a chanter note whose sounding pitch the same
     source fixes; drones at one pitch count once; the configuration the source calls usual; each
     drone at its derived equal-tempered note (A4 = 440 Hz), written in the code as hertz to two
     decimals. The `drones` cell names the notes, highest first (`C3`), or `none`, and
     `drone_source` holds the URL. A droneless row is `none` with its source saying so, or by its
     description naming every pipe as a melody pipe; for a single-pipe clarinet the page that
     describes its one pipe is the `drone_source`, and its `Drones:` passage quotes that
     description (the form check needs both on every shipped row).
  2. At most two distinct drone pitches (`_clarinet` keeps its breath, so `with_drones` has room for
     two); three make the row WAIT `more than four sources`.
  3. A row with a sourced range and a drone whose pitch no source gives WAITs `a sourced drone
     tuning`.
  4. A droned row SHIPs `_drone_clarinet`, never a sound-alike of a droneless catalog clarinet. The
     first code task that ships one adds, in `clarinets.py`,
     `_drone_clarinet(*, slope: float, low_pass: float, drones: tuple[tuple[float, float], ...]) ->
     Instrument`, returning `with_drones(_clarinet(slope=slope, low_pass=low_pass), drones=drones,
     drone_wave=wave_from_levels(falling_series(count=16, decibels_per_octave=slope,
     even_level=0.1)))`: the drone pipe sounds the chanter's own cylinder. Its `slope` and
     `low_pass` are copied from the catalog clarinet the parent ruling would choose, and each drone's
     level is 0.35, copied from `sackpipa`'s drone (the catalog's one cylindrical single-reed drone);
     all three are sound design, marked so. That task adds the entry to `NOT_PERIODIC_AT_THE_NOTE`
     ("its drones sound under every note at fixed pitches, as the bagpipes', which are not a harmonic
     family") and its drone notes to `CLARINET_DRONES`.
  5. A droned row whose only difference from a SHIP drone row of its half is its drone pitches is a
     finding for the controller (batch 12's retuned-drones mechanism would carry it, and this plan
     does not add it).
- **Double pipes** (batch 12's double-chanter ruling). Two melody pipes that play different notes
  (the launeddas's "melody in thirds and sixths", the audit) are notes of one sequence: the range
  runs from the lowest note of the lower pipe to the highest of the upper, each stated. Pipes
  fingered together in unison are one pipe. Unison pipes that the source says are tuned apart to
  beat have a sourced trait `blown`'s `chorus_cents` makes: the row SHIPs `_clarinet(slope=...,
  low_pass=..., chorus_cents=<cents>)` only with the detune its source states in cents (or in beats
  per second at a stated note, converted in the derivation), quoted after `Detune:` in `notes`;
  without a stated detune it WAITs `a sourced detune` (batch 13's name). The first code task that
  ships one adds `chorus_cents: float = 0.0` to `_clarinet`, passed to `blown` (no existing build
  changes: `blown` adds the chorus only above 0), and its cents to `CLARINET_DETUNES`. A detuned
  pair over a drone WAITs `its own build (a detuned double pipe over a drone)`: `with_drones` keeps
  only the `tone` and `breath` sources.
- **Range ruling for clarinets.** A sourced range is the lowest and highest sounding notes that a
  fetched source states for the instrument:
  1. *Stated*: both notes as the range or compass, in note names with octaves (scientific `D3`;
     Helmholtz `d` or `e'''` where the source names the notation or fixes the octave; a named note
     whose octave the source fixes), or the lowest note and an exact span above it, as batch 7
     allowed.
  2. *Sounding*: a range in written pitch counts only when the same source, or the same maker's page
     for that model, states the transposition (a B-flat clarinet "sounds a major second lower than
     written", a bass clarinet a major ninth below, a piccolo in A-flat a minor sixth above). A key
     in the instrument's name ("clarinet in D", "Clarinette Mib") is not a stated transposition: it
     names neither the direction nor the octave (an E-flat clarinet sounds a minor third above, an
     E-flat alto a major sixth below). A range the source calls sounding or concert pitch, or the
     range of an instrument its source calls non-transposing (the C clarinet, "non-transposing" by
     the audit's birbynė line), is sounding as given. The derivation shows the arithmetic.
     Otherwise the row WAITs.
  3. *Extensions and extremes*: the stated compass, and nothing beyond it. A note in parentheses is
     an extension, and the range is the unparenthesised notes. A top the source gives to the player
     ("altissimo", "for advanced players", "or higher"), an optional key or a low-C extension the
     source gives some instruments only, is an extreme: the range is the compass without it, or the
     row WAITs.
  4. *Double pipes*: as the double-pipes ruling.
  5. *Not a range*: a hedged span ("about", "approximately", "typically", "commonly", "usually",
     "can reach"), a span the source calls "comfortable" or "theoretical", a width or count with no
     pitches ("about 1.5 octaves", "an octave plus a note", "seven holes", "a sixth or seventh"),
     note letters with no octaves ("F in first octave to D/E in second", unless the source fixes
     which octave its "first octave" is), a key alone ("usually key of E"), a tessitura, or one
     pitch.
  6. *Several keys or sizes*: the key or size the source calls standard, usual or most common, from
     that source or a maker's model page in that key. A key or size in the row's own name (`d
     clarinet`, `tenor birbyne`) is ranged in that key or size. A source giving one size two ranges
     has given none, unless it calls one standard. With neither, the row WAITs (batch 7's rule).
  7. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached); a
     maker's catalogue or model page (Buffet Crampon, Selmer, Yamaha, Leblanc, Backun, Uebel,
     Wurlitzer, Ripamonti, Hammerschmidt, Leitner & Kraus for the contrabass sizes, Maui Xaphoon,
     and the folk-pipe makers' own sites); a museum's object record (MIMO, the Met, the Horniman,
     the Musée de la musique, the Edinburgh University Collection (MIMEd), the National Music
     Museum, the Bate Collection, the Museu de la Música de Barcelona); or a conservatory or
     orchestration reference (the Vienna Symphonic Library's instrument pages). A museum's or
     maker's page outranks an uncited Wikipedia line, and when they disagree the museum or maker
     decides (batch 11's lesson). A retailer's listing (a maker's model sold on a shop's page
     included), a blog, a forum or a fingering chart is not a source. A maker's page for a model in
     another key ranges only that key. A list page (`Single-reed_instrument`, `Clarinet_family`'s
     list of names) is a source for a name only. A range is never taken from a sibling size, the
     parent, a related instrument ("an octave below the birbynė") or the audit.
  8. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`, the spec's name: the
     octocontrabass clarinet's "Bb-1" by the audit) and nothing above C8 (WAIT `a range above C8`).
  9. *One note*: an instrument whose source gives it one note has no range. It WAITs `a sourced
     range`, the note quoted, and #84 carries #80's to #83's question.
  10. *Cited*: a range, bore or drone pitch from Wikipedia counts only when the raw wikitext shows a
      citation (a `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it in its own cell or
      paragraph, with no `{{citation needed}}` first, in a section not tagged `{{Unreferenced
      section}}`. The citation must support the line: where the cited work is reachable the worker
      opens it, and a citation that gives no range (batch 11's `shehnai`) is no citation. An
      uncited line is not a source, for a range, a bore, a drone or a trait that decides a SHIP or a
      WAIT.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then the
  derivation; then `Drones:`, its passages and their derivation (or the words that make it
  droneless); then, for a detuned pair, `Detune:`, its passages and the cents.
- **The Bohlen–Pierce clarinet's scale.** A scale is the pitches a sequence asks for (the engine
  takes any `Hz`), not the instrument's sound, so the 13-step tritave is no trait and no wait. The
  row is decided like any other: its range from a fetched source in notes or hertz, its maker's
  production under the one-off ruling.
- **Generic and ambiguous terms.** A name its source gives to a class rather than one instrument
  (`hornpipe`, if its page makes it "the generic" name of the horn-belled reed pipes, as the audit
  reads it; `memet` if its source names the ancient Egyptian double pipes as a class) is DROP "a
  generic term for <the instruments>", unless the source makes it one instrument's name. A name a
  source gives to two instruments of different families (the audit's birbynė, if its sources give
  the name to a single-reed and a double-reed pipe as two instruments, rather than one instrument
  of uncertain reed) is DROP "an ambiguous name: <the two>".
- **Makers' names and products.** `xaphoon` ("Xaphoon is his trademark", `saxophones.md`) and
  `venova` (Yamaha's) are names of one maker's product. A maker's product in production is an
  instrument a game may ask for (batch 10's in-production line), decided on its maker's page: its
  reed, bore, sound and range from that page under the rulings. A maker's page that sets its sound
  apart by a trait the build cannot make (the venova's branched pipe, if Yamaha's page says it
  makes a cylinder sound like a cone) is WAIT `its own build (<the trait>)`.
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's in-production
  line): DROP "a one-off instrument, not a type a game would ask for" for one maker's or
  artist's design not in production; DROP "no fetched source describes it" when no fetched page
  describes the row, applied the same to every such row, candidate or alias name (the audit's
  "(memory)" and list-only rows: `pilili`, `ganurags`, `saxonette`, `clarinet d amore`, `sarune
  etek`, `bulban`, `toleat`, `pey pok`, `tarpa`, `dozaleh`, `zummara`, `venova`, if their pages are
  not found). A reconstruction makers offer today, or a type a museum holds, is not a one-off; an
  extinct type is decided like any other and waits if no source ranges it.
- **No unpitched, tagged or retuned clarinet.** Every catalog clarinet is pitched, so a sound-alike
  is pitched; no candidate plays itself or is a chip, so no row has `tags`; no sound-alike carries
  `sound_changes`. The batch table's row needs no unpitched names.
- **No size chain.** The catalog's clarinet sizes have no chain in
  `test_sized_families_descend_from_highest_to_lowest` today, and adding one would test the 9
  existing entries' unsourced ranges, which this batch does not change; #84 asks whether to add one.
- **Two halves, as explicit lists.** Half A, the orchestral and modern clarinets (keyed European
  clarinets in other keys and sizes, the early and makers' single reeds, and the conical single
  reeds at the saxophone boundary), is these 17 candidates:
  `b natural clarinet`, `basset clarinet`, `bohlen pierce clarinet`, `c clarinet`, `clarinet d
  amore`, `d clarinet`, `heckel clarina`, `heckelphone clarinet`, `low g clarinet`, `mock trumpet`,
  `octavin`, `octocontrabass clarinet`, `piccolo clarinet`, `saxonette`, `tarogato`, `venova`,
  `xaphoon`.
  Half B, the folk single-reed pipes (single, double and horn-belled), is the other 28:
  `alboka`, `arghul`, `birbyne`, `bulban`, `contrabass birbyne`, `dilli tuiduk`, `diplica`,
  `dozaleh`, `ganurags`, `hornpipe`, `launeddas`, `memet`, `mijwiz`, `pepa`, `pey pok`, `pibgorn`,
  `pilili`, `pungi`, `reclam de xeremies`, `sarune etek`, `sipsi`, `sneng`, `stock and horn`,
  `tarpa`, `tenor birbyne`, `toleat`, `zhaleika`, `zummara`.
  The list decides the half. The alias names go with the half whose candidate their line names:
  `maui xaphoon`, `pocket sax` and `xaphoon de catalunya` with half A, `cifte`, `argun` and `argul`
  with half B. So half A's sheet holds 20 rows and half B's 31.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the batch,
  or a SHIP or SOUND_ALIKE row of the same half, never a row of the other half. So Task 4 needs
  nothing from Task 2. Half B drafts to a build file, appended to the sheet once half A is
  committed. The form check accepts a row the code already holds with the same target or parent
  (batch 7's lesson). If Task 5 finds a half-B build equal to a half-A build, that is a finding for
  the controller, who re-rules the row in a sheet fix commit.
- **A held-back guard.** As batch 13's `ORGAN_HELD_BACK`, this batch's guard is
  `CLARINET_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose
  reason is not `a sourced range` (an engine feature, a build of its own, a sourced reed and bore, a
  sourced drone tuning, a sourced detune, sub-audio fundamentals), and every alias row that waits
  for such a row. A test refuses each of its names in the catalog and the aliases, and the code
  check compares the table with the sheet, in the sheet's order.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task still fills `CLARINET_HELD_BACK` with the half's held
  rows and runs the code check, which must pass; its other steps are skipped, and Task 6 records the
  skip in #84.
- **Out of scope:** the audit's "Gaps you could not close" (ranges and timbres of the folk pipes;
  Pku and the other names not fetched; the reclam de xeremies page possibly mixed with another;
  the pibgorn disambiguation page; MIMO, the Met, the Horniman and Grove not searched; the African,
  Ethiopian and Berber, Indigenous American, Chinese and Korean, Caucasian and Spanish single-reed
  pipes; the Clarinet family page's tail, the albisiphone and the contrabass clarinets in other
  keys) and the saxophones audit's xaphoon keys (C, B-flat, D, G). Task 6 lists them in #70 for a
  later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of these files is committed.

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-14-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-14-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
  Expected: `names before 823` (703 entries and 120 aliases, at batch 13's HEAD). Any other number
  means the branch is not batch 13's HEAD: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && tolower($4) ~ /clarinet/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /clarinet/ {print tolower($1)}' round-1/merged-missing.tsv
} | LC_ALL=C sort -u > ../../../build/batch-14-candidates.txt
cd ../../..
```
  Write the plan's 17 half-A names, one per line, to `build/batch-14-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-14-candidates.txt build/batch-14-half-a.txt > build/batch-14-half-b.txt`
  and `wc -l build/batch-14-*.txt`.
  Expected: 45 candidates, 17 in half A, 28 in half B, and
  `LC_ALL=C comm -13 build/batch-14-candidates.txt build/batch-14-half-a.txt` prints nothing.
  Check that `build/batch-14-half-b.txt` is exactly the plan's half-B list.

- [ ] **Step 3: The form check,** `build/batch-14-form-check.py`:
```python
"""Batch 14's sheet form check: uv run python -I build/batch-14-form-check.py SHEET.

Batch 12's form check (plans/2026-11-12-instrument-catalog-batch-12-implementation.md, "Before
the tasks" Step 3) with batch 14's changes (batch 14's plan, "Before the tasks"): the clarinets
family, a shipped row's cylindrical single reed, no tags, and a sound-alike's drones equal to its
parent's (none for a clarinet from before the batch).
"""

import csv
import re
import sys

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note

STATUSES = ('SHIP', 'SOUND_ALIKE', 'WAIT', 'ALIAS', 'DROP')
# tests/audio/test_instrument_catalog.py APPROXIMATING_NAMES (after batch 13)
APPROXIMATING_NAMES = {
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
    'dizi', 'didgeridoo', 'piri', 'scottish smallpipes',
}
# Hornbostel-Sachs 422.2bc: a single reed; b is 1 for one pipe, 2 for a set; c is 1 for a
# cylindrical bore, 2 for a conical one (batch 14's plan, "The bore boundary")
CYLINDRICAL_SINGLE_REED = re.compile(r'422\.2[12]1')
# with_drones: "at most two with breath", and _clarinet keeps the breath
MOST_DRONES = 2
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
with open('build/batch-14-names-before.txt', encoding='utf-8') as before_file:
    names_before = set(before_file.read().split('\n')) - {''}
ship_rows = {row['name']: row for row in rows if row['status'] == 'SHIP'}
alikes = {row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'}
clarinet_parents = set(ship_rows) | {
    name for name in names_before
    if name in instruments.CATALOG
    and instruments.entry(name).sounds_like is None
    and instruments.entry(name).family == 'clarinets'
}
```
  Then batch 12's `held_as_this_row`, `taken`, `in_span`, `ranged` and `droned`, copied unchanged,
  and:
```python
def alike_allowed(row):
    """A sound-alike of a clarinet, with its parent's drones: none for one from before the batch."""
    parent = row['alias_of']
    if parent not in clarinet_parents or parent in APPROXIMATING_NAMES:
        return False
    parent_drones = ship_rows[parent]['drones'] if parent in ship_rows else 'none'
    return row['drones'] == parent_drones


names = [row['name'] for row in rows]
bad = [row['name'] for row in rows if not pattern.fullmatch(row['name'])
       or row['status'] not in STATUSES
       or row['family'] != 'clarinets'
       or not row['audit_name']
       or not (row['hs'] == 'none' or row['hs'][:1].isdigit())
       or row['tags'] != ''
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)
                or not droned(row) or not CYLINDRICAL_SINGLE_REED.match(row['hs'])))
       or (row['status'] in {'SHIP', 'SOUND_ALIKE', 'ALIAS'} and taken(row))
       or (row['status'] == 'SOUND_ALIKE' and not alike_allowed(row))
       or (row['status'] == 'WAIT' and not row['waits_for'])
       or (row['status'] == 'ALIAS'
           and row['alias_of'] not in clarinet_parents | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {status: sum(row['status'] == status for row in rows) for status in STATUSES})
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: The quote check,** `build/batch-14-quote-check.py`: batch 13's quote check
  (`build/batch-13-quote-check.py`), copied, with these changes only. Its docstring names batch 14
  and "the Range:, Drones: and Detune: passages", with "A row with no drones needs no Drones:
  passage, and only a detuned pair a Detune: passage"; `PAGES` is `Path('build/batch-14-pages')`;
  and its `sections` are
```python
    sections = [('range', quoted(row['notes'], 'Range:', 'Drones:'), row['range_source'])]
    if row['drones'] != 'none':
        sections.append(('drones', quoted(row['notes'], 'Drones:', 'Detune:'), row['drone_source']))
    if 'chorus_cents' in row['builder']:
        sections.append(('detune', quoted(row['notes'], 'Detune:', None), row['sound_source']))
```
  It checks what can be checked mechanically; a worker still applies range ruling 10 in full.

- [ ] **Step 5: The code check,** `build/batch-14-code-check.py`:
```python
"""Batch 14's code check: uv run python -I build/batch-14-code-check.py SHEET.

Batch 13's code check (build/batch-13-code-check.py as fixed during batch 13: an "Already decided"
DROP whose name was a catalog name or alias before the batch must still resolve) with batch 14's
changes (batch 14's plan, "Before the tasks"): every row is checked, the held-back guard, the drones
and the detunes are compared with the sheet, every built drone and detune is the sheet's, no entry
has tags or sound changes, and the builds, sound-alikes and aliases follow the sheet's order. The
test file's tables are read as literals, without importing the tests. A one-off check may read the
private _CLARINET_BUILDS; a test may not.
"""

import ast
import csv
import math
import re
import sys

from glitchygames.audio import instruments
from glitchygames.audio.instruments.clarinet_sound_alikes import CLARINET_SOUND_ALIKES
from glitchygames.audio.instruments.clarinets import _CLARINET_BUILDS
from glitchygames.audio.pitch import Note

TEST_FILE = 'tests/audio/test_instrument_catalog.py'
EXISTING_COUNT = 9
CHORUS_CENTS = re.compile(r'chorus_cents=([0-9.]+)')
with open('build/batch-14-names-before.txt', encoding='utf-8') as names_file:
    NAMES_BEFORE = {line.strip() for line in names_file if line.strip()}
```
  Then batch 13's `test_table`, copied unchanged, and:
```python
def built_drones(name):
    """The hertz of the fixed-pitch drones an entry's build sounds, highest first."""
    return sorted(
        (float(source.pitch) for source_name, source in instruments.get(name).sources
         if source_name.startswith('drone_')),
        reverse=True,
    )


def sheet_drones(row):
    """The sheet's drone notes as the catalog writes them: hertz to two decimals, highest first."""
    if row['drones'] == 'none':
        return []
    return [round(float(Note(note).to_hz()), 2) for note in row['drones'].split()]


def built_detune(name):
    """The cents of an entry's chorus copy, or 0.0 when it has none."""
    sources = dict(instruments.get(name).sources)
    return float(sources['chorus'].detune_cents) if 'chorus' in sources else 0.0


with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
rows_by_name = {row['name']: row for row in rows}


def sheet_detune(row):
    """The row's chorus_cents, a sound-alike's from its parent's row (0.0 for a catalog parent)."""
    if row['status'] == 'SOUND_ALIKE':
        parent_row = rows_by_name.get(row['alias_of'])
        return 0.0 if parent_row is None else sheet_detune(parent_row)
    match = CHORUS_CENTS.search(row['builder'])
    return float(match.group(1)) if match else 0.0
```
  Then batch 13's `held_back`, copied unchanged, and:
```python
for row in rows:
    name = row['name']
    if row['status'] in {'SHIP', 'SOUND_ALIKE'}:
        entry = instruments.entry(name)
        assert (entry.family, entry.lowest, entry.highest, entry.title) == (
            row['family'], row['lowest'], row['highest'], row['title'],
        ), name
        parent = row['alias_of'] if row['status'] == 'SOUND_ALIKE' else None
        assert entry.sounds_like == parent, name
        assert entry.tags == frozenset(), name
        assert dict(entry.sound_changes) == {}, name
        assert built_drones(name) == sheet_drones(row), name
        assert math.isclose(built_detune(name), sheet_detune(row)), name
    elif row['status'] == 'ALIAS':
        assert instruments.ALIASES[name] == row['alias_of'], name
    elif row['status'] == 'DROP' and row['notes'].startswith('Already decided') and name in NAMES_BEFORE:
        # A name decided by an earlier sheet keeps what that sheet gave it
        assert name in instruments.CATALOG or name in instruments.ALIASES, name
    else:
        assert name not in instruments.CATALOG, name
        assert name not in instruments.ALIASES, name
ship_names = [row['name'] for row in rows if row['status'] == 'SHIP']
alike_names = [row['name'] for row in rows if row['status'] == 'SOUND_ALIKE']
assert test_table('CLARINET_DRONES') == {
    row['name']: tuple(row['drones'].split())
    for status in ('SHIP', 'SOUND_ALIKE') for row in rows
    if row['status'] == status and row['drones'] != 'none'
}, 'CLARINET_DRONES'
assert test_table('CLARINET_DETUNES') == {
    row['name']: sheet_detune(row)
    for status in ('SHIP', 'SOUND_ALIKE') for row in rows
    if row['status'] == status and sheet_detune(row)
}, 'CLARINET_DETUNES'
assert test_table('CLARINET_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'CLARINET_HELD_BACK'
assert list(test_table('CLARINET_HELD_BACK')) == [
    row['name'] for row in rows if held_back(row)
], 'held-back order'
assert test_table('NEW_CLARINET_NAMES') == ship_names, 'NEW_CLARINET_NAMES'
assert list(test_table('CLARINET_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'CLARINET_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in _CLARINET_BUILDS[EXISTING_COUNT:]] == ship_names, 'build order'
assert [entry.name for entry in CLARINET_SOUND_ALIKES] == alike_names, 'sound-alike order'
sheet_aliases = [row['name'] for row in rows if row['status'] == 'ALIAS']
assert [name for name in instruments.ALIASES if name in set(sheet_aliases)] == sheet_aliases, (
    'alias order'
)
print('matches', len(rows), 'rows')
```
  It cannot run until Task 1 has created `clarinets.py`, `clarinet_sound_alikes.py` and the test
  tables. `sneng` is DROP "Already decided" but was never a catalog name or alias, so it takes the
  last branch.

---

### Task 1: Clarinets in their own module, unchanged; their sound-alikes module; the batch table's row, the drones and detune tables and the held-back guard

**Files:**
- Create: `src/glitchygames/audio/instruments/clarinets.py`,
  `src/glitchygames/audio/instruments/clarinet_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/winds.py`, `registry.py`, and the docstrings of
  `flutes.py`, `double_reeds.py` and `bagpipes.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: in `clarinets.py`, `CLARINETS: Final[tuple[CatalogEntry, ...]] = _CLARINET_BUILDS +
  CLARINET_SOUND_ALIKES` and `_clarinet(*, slope: float, low_pass: float) -> Instrument` under its
  current name. `CLARINET_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test file
  gains `EXISTING_CLARINET_NAMES: frozenset[str]` (the 9); `NEW_CLARINET_NAMES: list[str]`,
  `CLARINET_SOUND_ALIKE_PARENTS: dict[str, str]`, `CLARINET_DRONES: dict[str, tuple[str, ...]]`,
  `CLARINET_DETUNES: dict[str, float]` and `CLARINET_HELD_BACK: dict[str, str]`, all empty here, for
  Tasks 3 and 5 to fill; the tests below; and the row `Family.CLARINETS:
  BatchFamily(EXISTING_CLARINET_NAMES, NEW_CLARINET_NAMES, CLARINET_SOUND_ALIKE_PARENTS)` in
  `BATCH_FAMILIES`. Also `build/catalog-builds-before.txt`.

- [ ] **Step 1: Record every build.** Run batch 4's Task 1 Step 1 command with
  `instruments.names()` in place of `instruments.names(family='plucked strings')` and
  `build/catalog-builds-before.txt`.
  Expected: `recorded 703`.

- [ ] **Step 2: Write the tests.** After `EXISTING_FLUTE_NAMES`'s batch tables (`FLUTE_UNPITCHED_NAMES`),
  add `EXISTING_CLARINET_NAMES` (the 9 names, one per line, in catalog order, with the comment "#
  The 9 clarinets that predate batch 14: their shared builds predate the anti-goal rule"), then
  `NEW_CLARINET_NAMES: list[str] = []` and `CLARINET_SOUND_ALIKE_PARENTS: dict[str, str] = {}`,
  each commented as batch 13's lists are. Put the clarinets row between the flutes and double reeds
  rows in `BATCH_FAMILIES`, which is table order. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list gains `+
  list(CLARINET_SOUND_ALIKE_PARENTS)` between the flutes' and the double reeds' lines, its comment
  reading "… flutes, clarinets, double reeds, …". At the end of the file, after
  `test_compound_stop_levels_refuses_empty_levels_and_a_footage_of_zero` (batch 13's last test), add:
```python
# Batch 14's double clarinets with a drone pipe, each with its drone notes as the sheet writes them
# (highest first), sounding at equal temperament under every note, in catalog order: the builds,
# then the sound-alikes that share one's drones (plans/data/instrument-audit/batch-14.tsv)
CLARINET_DRONES: dict[str, tuple[str, ...]] = {}
# Batch 14's double clarinets whose unison pipes are tuned apart, each with its sourced detune in
# cents, the chorus copy of _clarinet, in catalog order: the builds, then their sound-alikes
# (plans/data/instrument-audit/batch-14.tsv)
CLARINET_DETUNES: dict[str, float] = {}
# Every name plans/data/instrument-audit/batch-14.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# reed and bore, a sourced drone tuning or a sourced detune, and the alias rows that wait for one of
# them, in the sheet's order. None ships under that name or as an alias until the reason is met
# (decision 4; batch 14). The test matches exact names
CLARINET_HELD_BACK: dict[str, str] = {}


def test_no_clarinet_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a clarinet the sheet holds back."""
    assert set(CLARINET_HELD_BACK) & set(instruments.names()) == set()
    assert set(CLARINET_HELD_BACK) & set(instruments.ALIASES) == set()
```
  Then:
  - `test_a_clarinet_sounds_its_sourced_drones`: the clarinet entries whose build has a source named
    `drone_…` are exactly `CLARINET_DRONES`'s keys, in catalog order; for each, the drones' hertz
    (`float(source.pitch)`, as `test_a_retuned_bagpipe_sounds_its_sourced_drones` reads them, sorted
    highest first) equal `[round(float(Note(note).to_hz()), 2) for note in drone_notes]`, and every
    name in `CLARINET_DRONES` is in `NOT_PERIODIC_AT_THE_NOTE`.
  - `test_a_detuned_clarinet_beats_at_its_sourced_cents`: the clarinet entries whose build has a
    `chorus` source are exactly `CLARINET_DETUNES`'s keys; for each, the chorus source's
    `detune_cents == pytest.approx(cents)`.
  Both hold with the tables empty (no clarinet has drones or a chorus today), and fail if a later
  task ships one without listing it.

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or drones or detuned or sound_their_note" -v`
  Expected: PASS, with the ID `[clarinets]` second in the parametrised batch tests. They are guards
  that hold the later tasks; the move in Step 4 must keep them passing.

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move `winds.py`'s
  "Clarinets" section into `clarinets.py` unchanged, comments included, with the tuple renamed
  `_CLARINET_BUILDS`, and define `CLARINETS` after it as the concatenation, importing
  `CLARINET_SOUND_ALIKES`. The new module docstring's first line is "Clarinets: single reeds on a
  cylindrical bore, the E-flat to the contrabass clarinet, the basset horn and the chalumeau." It
  takes `winds.py`'s clarinet sentences (sounding pitch, "a B-flat clarinet's written C sounds
  B-flat", the orchestration sources, "a clarinet (a closed cylinder) favours odd harmonics"), and
  says that a conical single reed is a saxophone, that the sound-alikes are in
  `clarinet_sound_alikes.py`, and that the saxophones and free reeds are in `winds.py`.
  `winds.py`'s docstring becomes "Woodwinds: saxophones and free reeds." and names `clarinets.py`
  among the sibling modules, keeping its saxophone and free-reed sentences. In `flutes.py`,
  `double_reeds.py` and `bagpipes.py`, the docstring sentence naming `winds.py` as the reed
  families' home also names `clarinets.py` (`flutes.py`: "the clarinets in ``clarinets.py``, the
  other reed families in ``winds.py``", and the same shape in the other two).
  `clarinet_sound_alikes.py` gets the empty table and `double_reed_sound_alikes.py`'s docstring
  with "Clarinets'" for "Double reeds'", ending "The family's builds are in ``clarinets.py``.".
  Point `registry.py` at the new module. If the process-state guard then asks for an entry for
  `_CLARINET_BUILDS`, `CLARINETS` or `CLARINET_SOUND_ALIKES`, that is a finding: `organ_sound_alikes.py`
  needed none, so read why before writing any reason.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `instruments.names()` and `build/catalog-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
SKIP=replay-metrics git commit -m "Instrument catalog: clarinets in their own module, unchanged; their sound-alikes module; the drones, detune and held-back guards" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
  Run each lint command as its own line (batch 11's Task 1: zsh word-splitting once made a
  combined run a no-op).

---

### Task 2: The orchestral and modern clarinets sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. Put no personal data in any request, in a header, a
URL or a payload. Save each ranged row's raw pages as `build/batch-14-pages/<name, spaces as
hyphens>--<n>.txt` (for Wikipedia, the `action=raw` wikitext) under the quote ruling. A list page
(`Single-reed_instrument`) is a source for a name only. The sound, the reed and bore, the range and
the transposition come from the instrument's own page, a maker or a museum under range ruling 7.
The audit's rows and "Range checks" are leads, not sources, so fetch them. Fetch the page of every
existing entry you name as a parent, and record what it says in the row's notes. Never use `git
stash`. This task may start as soon as the controller has written the shared files, alongside
Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-14.tsv`
- Create (not committed): `build/batch-14-half-a.tsv`, and the raw pages in
  `build/batch-14-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `clarinets.md` ("Rejected or corrected proposed
  entries", "Aliases", "Range checks", "Gaps you could not close"); `saxophones.md` (the xaphoon
  lines: "Rejected or corrected", "Aliases"); `double-reeds.md` (`tarogato`, "Heckelphone-clarinet:
  single reed, wrong family"); `build/batch-14-names-before.txt`, `build/batch-14-half-a.txt`,
  `build/batch-14-half-b.txt`, `build/batch-14-form-check.py` and `build/batch-14-quote-check.py`.
- Produces: `batch-14.tsv` with batch 12's seventeen columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	drones	drone_source`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `clarinets` on every row, and `tags` is
  empty on every row. A SHIP or SOUND_ALIKE row has `lowest`, `highest` (sounding), `range_source`,
  `hs` matching `422.2[12]1`, `drones` (notes or `none`), `drone_source`, and `notes` holding
  `Range:` and `Drones:` (and `Detune:` for a detuned pair), each with its «raw passages» and
  derivation. A candidate row's `audit_name` is its name in `build/batch-14-candidates.txt`; an
  alias row's is its audit line. Also `build/batch-14-half-a.tsv`, the half as committed, which
  Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-14-half-a.txt`'s order, then
  one per alias name of this half (`maui xaphoon`, `pocket sax`, `xaphoon de catalunya`).

  The rules are batch 13's, changed for this family:

  1. **SHIP** only with name, title, sound, reed and bore, range and drones from fetched sources,
     and a cited trait the engine can make that no clarinet build has (drones, a sourced detune).
     Quote in `notes` the passage that describes the sound or construction (the reed, the bore,
     the pipes) and, after `Range:`, `Drones:` and `Detune:`, the «raw passages» and the derivations
     under the rulings. The `builder` cell gives the call (`_drone_clarinet` or `_clarinet` with
     `chorus_cents`, with every keyword) and says which values come from the source and which are
     sound design, copied from which entry.
  2. **SOUND_ALIKE**: a verified instrument that rule 7 finds would sound like an existing clarinet
     or a SHIP row of this half. `alias_of` is its parent (the parent ruling). The `notes` begin
     "Sound-alike:", quote the source's description and its reed and bore, and say why that entry
     is the parent (rule 1 or 2 of the parent ruling). It has its own range, and the `builder` cell
     says "unchanged". It is never another sound-alike's sound-alike, never one of
     `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row of this half. If the target waits, the row is WAIT with `waits_for`
     `its target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is
     dropped". An ambiguous name or a generic term is DROP under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `a sourced reed and bore`, `a sourced
     drone tuning`, `a sourced detune`, `more than four sources`, `sub-audio fundamentals`, `a range
     above C8`, `its own build (<the trait>)`, or another name of Global Constraints. The range is
     checked first. The feature must be the sound the source describes, not a technique a player
     applies (circular breathing, glissando, ornaments, vibrato as a player's choice). A cited trait
     no builder makes means the row waits. Any other name is allowed only with the source quoted,
     and Task 6 lists it in #84.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     bore boundary's words), is a one-off, or is already decided: in the catalog under that name
     (name the entry), an alias already (name its target), or a row of an earlier sheet (notes
     beginning "Already decided:", naming the sheet and its status).
  6. A row the audit marks "(memory)", UNVERIFIED for existence, or sourced only by a list page has
     no sourced sound or range yet. Fetch its own page; the audit's URL is a lead. If no page can be
     found, the row is DROP "no fetched source describes it", the same words on every such row.
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='clarinets'))"`
     and the builds in `clarinets.py`) and every SHIP row above it. If no cited trait (drones, a
     sourced detune) makes it sound different, it is a SOUND_ALIKE under rule 2. A number chosen
     only to differ does not count, nor a difference of 1 or 2 percent in a value (batch 11's
     contraforte), nor a loudness, a colour word, a range, a key, a size, a bell or a material.
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.

  This half's own cases:

  - **Keys and sizes.** `piccolo clarinet`, `d clarinet`, `c clarinet`, `b natural clarinet`, `low
    g clarinet` and `basset clarinet` are clarinets of other keys and sizes: each is a SOUND_ALIKE
    under the parent ruling with its own range, ranged under range ruling 2 (the audit's ranges are
    from the Clarinet family page; fetch its raw wikitext and check that each range is cited and
    sounding, or written with a stated transposition). Makers' model pages (Buffet Crampon's,
    Selmer's, Yamaha's, Leblanc's or Backun's D, C, A-flat or basset models) range a key their own
    page names, with a stated transposition. The low G clarinet's "add pitch ornament/slide" (the
    audit) is a technique, not a trait.
  - **Sub-audio.** `octocontrabass clarinet` (the audit's "Bb-1–G3") WAITs `sub-audio
    fundamentals` once its range is sourced, else `a sourced range`.
  - **The saxophone boundary.** `tarogato` (the audit: "Modern form is single-reed conical bore"),
    `octavin` ("Conical-bore single-reed"), `heckel clarina` ("Metal, conical bore, single reed")
    and `heckelphone clarinet` (`double-reeds.md`: "single reed, wrong family") follow the bore
    boundary on their pages: DROP "belongs to saxophones (H-S 422.212): <its words>" for a conical
    bore. The historical double-reed tárogató is the double reeds' (the audit: "choose single-reed
    modern form"), so the row is decided on the modern instrument.
  - **Makers' products.** `xaphoon` (the saxophones audit: "keyless (nine tone holes), cylindrical
    bore, tenor-sax reed, overblows at the twelfth like a clarinet ... usually in C (also Bb, D, G)")
    and `venova` follow the makers' ruling, on their makers' pages (Maui Xaphoon; Yamaha). The
    xaphoon's parent, if it is a sound-alike, follows the parent ruling (the audit calls it
    "Chalumeau-like", which names the catalog's `chalumeau` under rule 1 only if a fetched source
    says it). `maui xaphoon`, `pocket sax` and `xaphoon de catalunya` follow `xaphoon` (rule 3);
    `maui xaphoon` is also a maker's name, and `pocket sax` an ALIAS only on a cited page giving it
    as the xaphoon's name.
  - **Early clarinets.** `mock trumpet` is ALIAS of the catalog's `chalumeau` only on a cited page
    that gives the name to the chalumeau itself; otherwise it is decided on its page. `clarinet d
    amore` and `saxonette` (the audit's "(memory)") follow rule 6.
  - **The Bohlen–Pierce clarinet** follows its ruling (its scale is no trait).

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-14-form-check.py plans/data/instrument-audit/batch-14.tsv`
  and `uv run python -I build/batch-14-quote-check.py plans/data/instrument-audit/batch-14.tsv`.
  Expected: `20 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 3: Check the half.** Run batch 13's Task 2 Step 3 command (batch 12's) with `batch-14`
  for `batch-12`. Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-14.tsv build/batch-14-half-a.tsv
git add plans/data/instrument-audit/batch-14.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 14's verification sheet, the orchestral and modern clarinets" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The orchestral and modern clarinets

**Files:**
- Modify: `clarinets.py` (new builds after the 9; `_drone_clarinet` or `_clarinet`'s
  `chorus_cents`, each only if a row needs it), `clarinet_sound_alikes.py`
  (`CLARINET_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-14-half-a.tsv` (half A as committed), Task 1's tables and
  `build/batch-14-code-check.py`.
- Produces: `NEW_CLARINET_NAMES`, `CLARINET_SOUND_ALIKE_PARENTS`, `CLARINET_DRONES`,
  `CLARINET_DETUNES` and `CLARINET_HELD_BACK` filled with this half's rows, which Task 5 extends;
  and, as rows need them, `_drone_clarinet(*, slope: float, low_pass: float, drones:
  tuple[tuple[float, float], ...]) -> Instrument` and `_clarinet(*, slope: float, low_pass: float,
  chorus_cents: float = 0.0) -> Instrument` in `clarinets.py`.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills only
`CLARINET_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_CLARINET_NAMES` with one name per SHIP row,
  `CLARINET_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row, `CLARINET_DRONES` with
  one `name: (notes, ...)` per SHIP or SOUND_ALIKE row whose `drones` is not `none` (the builds, then
  the sound-alikes), `CLARINET_DETUNES` with one `name: cents` per SHIP row built with
  `chorus_cents` and per sound-alike of one (its parent's cents), and `CLARINET_HELD_BACK` with one `name:
  waits_for` per held row (every WAIT row whose reason is not `a sourced range`, and every `its
  target, <name>` row whose target is held), each in the sheet's order. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, in the sheet's order, with a docstring sentence for
  batch 14. Every name in `CLARINET_DRONES` also goes in `NOT_PERIODIC_AT_THE_NOTE` with the drone
  ruling's reason.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or held_back or drones or detuned or sound_their_note" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the held-back
  test passes.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in `CLARINET_SOUND_ALIKES`,
  in the sheet's order, under a section comment naming `plans/data/instrument-audit/batch-14.tsv`
  as `double_reed_sound_alikes.py`'s does, each a `CatalogEntry(name, title, Family.CLARINETS,
  lowest, highest, sounds_like=parent)`. Above each, put a comment with its `sound_source` and
  `range_source` URLs, the quoted passages (its reed and bore, its range, its transposition) and
  the range's derivation. A SHIP row is a `CatalogEntry` after the 9 in `_CLARINET_BUILDS`, a
  `partial(_drone_clarinet, ...)` or `partial(_clarinet, ..., chorus_cents=...)`, carrying the same
  comment plus its drone or detune passages, and marking the values that are sound design and the
  entry they are copied from. Add `_drone_clarinet` or `chorus_cents` only if a row needs it, as the
  drone and double-pipes rulings give them. Each ALIAS row goes in `aliases.py` under a "Batch 14's
  clarinets: the orchestral and modern clarinets" section, in the sheet's order, with its URL and
  quote. Comments name only committed files.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range or the build. Check it against the source, and never trim the range to
  pass. Then run:
  `uv run python -I build/batch-14-code-check.py build/batch-14-half-a.tsv`
  Expected: `matches 20 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 14's orchestral and modern clarinets, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The folk single-reed pipes sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-14-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-14-pages/`
- Modify: `plans/data/instrument-audit/batch-14.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-14-form-check.py`,
  `build/batch-14-quote-check.py`, `build/batch-14-half-b.txt`; `clarinets.md` (the "Rejected or
  corrected" lines for `arghul`, `alboka`, `launeddas`; "Aliases"; "Range checks"; "Gaps");
  `batch-10.tsv` (`sneng`); `batch-12.tsv` (its drone and double-chanter rows as worked examples:
  `istarski mih`, `tulum`, `zukra`).
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-14-half-b.txt`'s order, then one per alias name
of this half (`cifte`, `argun`, `argul`), in the plan's order. A parent or alias target is a
catalog name or a SHIP or SOUND_ALIKE row of this half, never a half-A row. These rules apply on
top of Task 2's:

- **Already decided.** `sneng` is DROP under rule 5, its notes beginning "Already decided:
  batch-10.tsv WAIT, a sourced range" (the end-blown horn, brass; the side-blown form a free reed).
- **Double clarinets.** `arghul` (the audit: "melody pipe plus longer drone pipe; small/medium/large
  sizes"), `launeddas` ("three pipes (two five-hole chanters of different length plus a drone),
  melody in thirds and sixths"), `diplica` ("one tube drone"), `pungi` ("two pipes, one drone") and
  `alboka` ("two melody pipes sharing one reed cap and one horn bell") follow the drone and
  double-pipes rulings: each needs its range (both chanters' notes for two melody pipes), its reed
  and bore, and each drone's pitch, else it waits, the range first. Several sizes with none
  standard (the arghul's three) is range ruling 6. `mijwiz`, `zummara`, `dozaleh`, `reclam de
  xeremies` and `memet` (two equal pipes) are one pipe in unison unless a fetched source says they
  are tuned apart, when the detune ruling decides. `cifte`, `argun` and `argul` follow `arghul`
  (rule 3) only on a cited page giving each as the arghul's name (the audit: "Turkish tied double
  pipe, demli type has drone pipe": a type of its own is no alias).
- **The birbynė.** `birbyne` decides the type (the audit's "Birbyne (soprano)", "Single- or
  double-reed (sources conflict)"): the bore boundary's reed-and-bore rule and the ambiguity ruling
  decide it on its page; `tenor birbyne` and `contrabass birbyne` are its sizes under the parent
  ruling's rule 3, each with its own range, or wait with it.
- **Hornpipes.** `hornpipe`, `pibgorn`, `stock and horn`, `zhaleika` and `pepa` are horn-belled
  reed pipes (the audit: "regional forms of one construction (hornpipe is the generic; pibgorn
  Welsh; stock and horn Scots)"). `hornpipe` follows the generic-term ruling on its page (the
  `Hornpipe_(instrument)` page); each regional name is decided on its own page (the pibgorn's
  first fetch was a disambiguation page: fetch the instrument's), and an ALIAS only where a cited
  page gives it as another's name. The horn bell is no trait. The zhaleika's "Single-reed (or
  double in some)" is the reed-and-bore rule.
- **The rest.** `sipsi` ("span ~1.5 octaves only", a width), `dilli tuiduk` ("F in first octave
  to D/E in second", letters whose octave the source must fix), `pilili`, `ganurags`, `bulban`,
  `tarpa`, `pey pok`, `sarune etek` and `toleat` are decided on their pages, under rule 6 when no
  page is found.

- [ ] **Step 1: Write half B's rows** to `build/batch-14-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-14-form-check.py build/batch-14-half-b.tsv` and
  `uv run python -I build/batch-14-quote-check.py build/batch-14-half-b.tsv`.
  Expected: `31 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-14-half-b.tsv >> plans/data/instrument-audit/batch-14.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `51 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 2 Step 3's command with
  `half_a | half_b` in place of `half_a` on its `missing:` and `twice:` lines, and print
  `'extra:', sorted(set(audit_names) - half_a - half_b)` in place of the half-B line.
  Expected: `missing: []` and `twice: []`. `extra:` lists only the alias rows' audit lines (four
  distinct lines: `clarinets.md`'s cifte line, shared by its three names, and `saxophones.md`'s three
  xaphoon lines), because an alias row's `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-14.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 14's verification sheet, the folk single-reed pipes (single, double and horn-belled)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The folk single-reed pipes

**Files:**
- Modify: `clarinets.py`, `clarinet_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-14.tsv`'s half-B rows, Task 3's tables and helpers, and
  `build/batch-14-code-check.py`.
- Produces: the finished family.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `NEW_CLARINET_NAMES`,
  `CLARINET_SOUND_ALIKE_PARENTS`, `CLARINET_DRONES`, `CLARINET_DETUNES`, `CLARINET_HELD_BACK`, the
  alias parameters and (for a droned build) `NOT_PERIODIC_AT_THE_NOTE`, after half A's, as in Task 3
  Step 1.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes, aliases after half A's aliases, under second
  section comments naming the sheet ("Batch 14's clarinets: the folk single-reed pipes").

- [ ] **Step 4: Run the suite and check the code against the whole sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`, then
  `uv run python -I build/batch-14-code-check.py plans/data/instrument-audit/batch-14.tsv`.
  Expected: PASS, then `matches 51 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 14's folk single-reed pipes, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a clarinets
  paragraph with its count, naming `clarinets.py` and `clarinet_sound_alikes.py`, with examples, in
  the organs paragraph's form, saying that a clarinet is a cylindrical single reed (a conical one a
  saxophone), that a sound-alike of another key or size gives its own sourced range, and, if one
  shipped, that a double clarinet's drones are fixed pitches inside its build. Fix the double reeds
  and bagpipes paragraphs' "``winds.py`` keeps the clarinets, saxophones …" lines.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `clarinets` row's
  count and examples, the sound-alike modules sentence and its total, and any sentence naming
  `winds.py` as the clarinets' module).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 14
  done, pointing at this plan and `batch-14.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 14 DONE";
  - batch 14 done, with the sheet's counts by status and the family's growth, the module move
    (`clarinets.py`; `winds.py` keeping the saxophones and free reeds), the bore boundary, any
    drone or detuned double clarinet shipped, `CLARINET_HELD_BACK`'s names, and the branch's base
    SHA (batch 13's HEAD, recorded when the branch was made);
  - the audit's unclosed gaps, as a later pass;
  - the hand-offs: `tarogato` and each conical single reed dropped to the saxophones (so the
    saxophones batch decides them: `tarogato`, `octavin`, `heckel clarina`, `heckelphone
    clarinet`, as the sheet dropped them), the xaphoon's alias names decided here (so the saxophones
    batch must not decide `maui xaphoon`, `pocket sax` or `xaphoon de catalunya` again), any row
    dropped to double reeds, free reeds or bagpipes for a later pass of those families, `sneng` left
    as batch 10 decided it, and any name the sheets found that belongs to the keyboards batch;
  - a "Plan (batch 14)" line, the Status line, and the next batch named: keyboards.

  Add #84 (the highest item is #83), "Sound Engine: The Owner's Checks on Instrument Catalog Batch
  14 — TODO". Use #83's form (as #75 began it), place it directly after #83, and give it the
  Priority "(before the keyboards batch builds on the same catalog)". Its **Listen** section
  (`build/instruments/clarinets/`) covers the new builds (each droned or detuned build against the
  catalog clarinet its values were copied from), then the sound-alikes beside their parents, then
  the aliases. Its **Calls to confirm** are:
  - every WAIT, by reason, with names;
  - the bore boundary (a cylindrical single reed this family's, a conical one the saxophones', each
    row it moved, and the new wait name `a sourced reed and bore`);
  - a cylindrical clarinet as a sound-alike (the catalog's `_clarinet` already favours odd
    harmonics, so no new table; a SHIP only for drones or a sourced detune; bells, materials, keys
    and colour words no trait);
  - the parent ruling (the source's relation first, else the nearest lowest note, `chalumeau` only
    by relation, sizes sharing their type's parent), and each sound-alike's parent;
  - the range ruling (sounding, a written range only with its stated transposition and a key in
    the name not one, never hedged, a width, letters, a key or one pitch, makers' and museums'
    pages over uncited Wikipedia lines, nothing below A0 or above C8, one-note instruments, cited
    Wikipedia lines whose citation supports them), and every derived range;
  - the drone ruling and the double-pipes ruling (`_drone_clarinet` and `chorus_cents` if added,
    with each value's source and the copied sound design: `sackpipa`'s 0.35 drone level, the slope
    and low pass of the clarinet the parent ruling chose);
  - the Bohlen–Pierce clarinet's scale as no trait;
  - the makers' ruling (`xaphoon`, `venova`) and the one-off and unsourced rows, with the words
    "no fetched source describes it" on every row whose page was not found;
  - generic and ambiguous terms dropped (`hornpipe`, `memet`, `birbyne` and the rest, as decided);
  - the module move;
  - `CLARINET_HELD_BACK`, the guard for every non-range wait;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - the size chain left out (would you add the clarinet sizes to
    `test_sized_families_descend_from_highest_to_lowest`?);
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): the 9 earlier entries' missing
  source comments; any existing range or build a sheet's source contradicts (the five Clarinet
  family page ranges in Global Constraints, as the sheets find them cited or uncited; `chalumeau`'s
  F3-Bb4); `winds.py`'s and `clarinets.py`'s docstring sentence on folk ranges ("typical of the
  common keys") if it moved without a source; the third-party `speech_recognition`
  DeprecationWarning under `-W error` as #81 to #83 record it. Then **Follow-ups**: the audit's
  gaps; ranging the range WAITs from maker and museum sources; checking the 9 earlier entries
  against sources; the engine changes that unblock the waits, most rows first. Then **Incidents and
  process**, as #83 has them.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries()))"`
  and `uv run python -I build/batch-14-form-check.py plans/data/instrument-audit/batch-14.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-14-code-check.py plans/data/instrument-audit/batch-14.tsv
uv run python -I build/batch-14-quote-check.py plans/data/instrument-audit/batch-14.tsv
```
  Expected: everything passes with no warnings (a warning is a finding; #81 records the
  third-party `speech_recognition` DeprecationWarning under `-W error`, so a new one is a new
  finding), `matches 51 rows`, and `bad: []`. The `build/instruments/clarinets` folder is the one
  to listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 14 of the instrument catalog (clarinets), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch in
turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78). The
pre-push hooks take about 40 minutes, and nothing in the working tree may change while they run.

**Order:** the controller's shared files, then Tasks 1, 2 and 4 in parallel. Task 3 follows Tasks
1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows Tasks 3 and 4, and Task 6 comes
last.
