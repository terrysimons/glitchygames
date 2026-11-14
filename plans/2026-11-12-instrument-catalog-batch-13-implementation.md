# Instrument catalog batch 13 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the organ family from the audits' candidates. The family holds the pipe organ and
its stops (flue and reed ranks, mutations, compound stops), the small and early organs (regal,
portative, positive, chamber organ, hydraulis), the self-playing organs (barrel, street,
fairground, band and dance organs, the serinette and flute clock, the orchestrion), the calliope
and the pyrophone. Each instrument or stop gets a cited source for its name, its sound, its range
and (for a stop) its footage, and either sounds unlike every other entry or is a listed
sound-alike of the one it sounds like. The rest become aliases, wait for an engine feature or a
source, or are dropped with a reason.

**Architecture:** As in batches 3 to 12, a verification sheet (`batch-13.tsv`) decides every
candidate before any code is written. The family's 9 entries live in `keyboards.py` (463 lines,
which also holds the keyboards and the electromechanical instruments), so they move unchanged to
a new `organs.py`, as batches 9, 11 and 12 moved the flutes, the double reeds and the bagpipes.
Its table is `_ORGAN_BUILDS`, and `ORGANS` becomes `_ORGAN_BUILDS + ORGAN_SOUND_ALIKES`, with the
sound-alikes in a new `organ_sound_alikes.py`. An organ stop sounds at its footage relative to the
key (the catalog's convention, which today covers only the 16' drawbar: "a 16' stop or drawbar
sounds an octave lower"), so `_pipe_stop` gains a `footage` keyword, carried by a new `semitones`
keyword on `timbres.blown`; a sound-alike stop at another footage than its parent is built with
`sound_changes={'footage': ...}` (decision 8's "change their details", as batch 12's retuned
drones), listed in a new test table `ORGAN_STOP_FOOTAGES`. A new guard, `ORGAN_HELD_BACK`, holds
every name the sheet holds back for any reason but a sourced range. The sheet and the code each
come in two halves, as explicit lists: the organ stops, then the organs as instruments (early,
portable, self-playing, steam, fire and the electric names at the boundary). The controller writes
the names file, the candidate lists and the three check scripts before anything is dispatched, so
the two sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `drawbar_organ`,
`falling_series`, `wave_from_levels`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all, and 7 for `Tag.MECHANICAL`). Batch 12's plan
(`plans/2026-11-12-instrument-catalog-batch-12-implementation.md`) and its owner's checks
(`plans/future-features.md` #82) are this plan's template and its ledger: its controller step, its
quote check on the raw page text, its held-back guard, its two parallel halves and its
sound-alikes changed by a sourced pitch (the retuned drones) carry over. Batch 4's plan
(`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) holds the pitched sound-alike
and strict range rules and the before-and-after build record. Batch 9's plan holds the
mechanical-tag rule for a self-playing instrument (`tags` `mechanical`). This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-13-implementation.md`. The branch is
`feat/instrument-catalog-batch-13`, made from `feat/instrument-catalog-batch-12` at its HEAD,
`5cbbf882` (batch 12's final review fixes); Task 6 records that SHA in #70. The candidates come
from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `organ` (52: the 50 rows of the round-2 audit
  `organs.md`, `pyrophone` from `new_environmental_instruments.md`, family `organs`, and
  `hydraulophone`, family "flutes (nearest; or organs)");
- the `round-1/merged-missing.tsv` rows whose `family` contains `organ` (11: `regal`,
  `telharmonium`, `choralcelo`, `sea organ`, `pyrophone`, `fire organ`, `chromelodeon`, `beer
  bottle organ`, `bubble organ`, `uberorgan`, `sequential resonation machine`);
- two rows of the mechanical-instruments audit (`new_mechanical_instruments.md`), whose family is
  a tag: `flute clock`, which batch 9 handed here ("`serinette` and `flute clock` are barrel
  organs, so the organs batch decides them", #70 and #79), and `componium` ("automatic organ",
  its audit row; "sound is organ").

Together: **64 unique candidate names** (`pyrophone` is in both filters; `serinette` is already an
`organs.md` row; counted for this plan, the controller recounts). None is in the catalog today;
`vox continental` is already an alias (of `combo organ`, batch 6). Every name is already a valid
catalog name. The audits' alias lines that name organs propose **6 alias names** that are not
candidates: `bible regal` (`organs.md`: "bible regal -> regal"); `carousel organ` and `limonaire`
(`new-mechanical-instruments.md`: "street organ, band organ, dance organ, carousel organ,
limonaire -> fairground organ"); `bird organ` and `perroquette` ("bird organ, perroquette
(similar barrel organ) -> serinette"); and `calliaphone` ("air calliope, calliaphone ->
calliope"). The other names on those lines are candidates, decided by their own rows (rule 8). So
the sheet will hold **70 rows**.

The hand-offs from earlier sheets (checked: `batch-1.tsv` to `batch-12.tsv`, and
`plans/future-features.md` #70–#82):
- `vox humana` and `voix celeste`: `batch-8.tsv` DROP, "belongs to organs (organs.md rows it as a
  stop); the organs batch decides it". Both are half-A candidates.
- `serinette` and `flute clock`: batch 9's plan and #70, #79 ("the organs batch decides them").
  Half-B candidates.
- `kinura`: `batch-2.tsv` DROP, "A pipe-organ stop, so organs, not electromechanical". Half A.
- `band organ`: `batch-2.tsv` DROP, "A pneumatic mechanical organ, not electromechanical …; the
  mechanical-instruments tag covers it with the organs". Half B.
- `dulciana`: `batch-11.tsv` DROP, "an ambiguous name: also the dulciana organ stop (organs)",
  the Dulcian page listing "Italian: dulciana". The name is decided (below).
- Already decided, not handed: `hammond b3` (`batch-2.tsv` WAIT, the Leslie's LFO),
  `telharmonium` (`batch-2.tsv` WAIT; `batch-6.tsv` DROP), `vox continental` (`batch-6.tsv`
  ALIAS of `combo organ`), `hydraulophone` (`batch-9.tsv` WAIT, flutes) and `gemshorn`
  (`batch-9.tsv` WAIT, the vessel flute of that name). Each is DROP "already decided", naming the
  sheet and its status.
- `orchestrion` is also a `keyboards.md` row and `reed organ` a `free_reeds.md` row: this sheet
  decides both names, and #70 tells the keyboards and free reeds batches so.

Not a candidate: the mechanical audit's `orchestrelle` (a roll-playing reed organ, "free reed, not
pipe": the free reeds batch's) and its other rows (music boxes, pianos, the violano), which belong
to other families. Task 6 lists `orchestrelle` in #70 for the free reeds batch.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes and footage marks go only in the title (`rohrflote` titled
  "Rohrflöte 8'"). A stop's title is its name as its source gives it, then its footage as the
  catalog's stop titles have it ("Pipe organ, flute 8'"): "Bourdon 16'", "Organ oboe 8'". A
  candidate keeps its audit name (the naming ruling of batch 12).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families),
  "with the existing player-facing splits kept where they already exist (keyboards and organs …)".
  The organ family holds pipe organs and their stops (H-S 421.22 duct flutes in sets, 422 reed
  pipes, keyboard-played or self-playing), regals, the calliope's whistles, and the pyrophone (the
  spec: "pyrophone: organs"). The boundary ruling below sends free-reed organs to free reeds and
  electric organs to electronic or electromechanical.
- "Every name, range and description checked against a source cited in the code … A range that no
  source gives is the instrument's documented playable span from a maker or museum, or the entry
  waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict"). This
  plan's range ruling for organs is below, under "Decisions". A row with no sourced range is WAIT,
  `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry, sharing
  the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the same
  instrument) stays an alias." "So `sound_changes` (keyword overrides of the parent's builder,
  empty by default) lets a sound-alike differ by a sourced trait." A sound-alike is pitched
  exactly when its parent is, and a pitched sound-alike gives its own sourced range (batch 4). "a
  sound-alike with changes counts as its own build" (decision 8), so it must sound different from
  every other entry.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as an
  approximation, under its real name or a qualified one. The spec's table binds this family
  directly: "more than four sources | orchestrion, violano-virtuoso, large mixtures" and
  "sub-audio fundamentals". Earlier batches added the other names a WAIT may give: a pitch LFO
  (vibrato), a pitch LFO (portamento between notes), an amplitude LFO, a pitch and amplitude LFO
  (batch 2), filter resonance, a filter envelope, moving formants (batch 6); a buzzing membrane
  (batch 5); a sourced drone tuning and its own build (batch 7); a range above C8 (batch 10).
  This plan adds two source waits, `a sourced footage` and `a sourced detune` (below). What the
  engine has: up to four `Source`s, each with its own semitones, detune and fixed pitch; `blown`
  (a harmonic series of up to 32 harmonics in one wave, attack, release, breath noise, low pass,
  drive, a static `chorus_cents` copy); `drawbar_organ` (nine drawbar harmonics in one wave);
  one glide per note (`pitch_curve`); a fixed FIR low or high pass; no LFO of any kind.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not
  builds.
- Reuse the family's builders, which `organs.py` keeps under their current names: `_pipe_stop`
  (`levels`, `chiff`, `release`, and this plan's `footage`) with `PRINCIPAL_LEVELS`,
  `FLUTE_STOP_LEVELS`, `REED_STOP_LEVELS` or `STRING_STOP_LEVELS`; `blown` with `CALLIOPE_LEVELS`;
  `drawbar_organ`. Each entry's build is an inline `partial(...)`. Add a level table or builder
  only for a genuinely new, sourced sound, and give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the sheet
  is verbatim from a page the worker fetched, and every `Range:` and `Footage:` passage is quoted
  from the raw page text (the quote ruling). No request carries the owner's email or any personal
  data, in a header, a URL or a payload (#78, "Incidents and process").
- Code comments name committed files (`plans/data/instrument-audit/batch-13.tsv`), never the
  gitignored `build/` files (batch 9's fix).
- The 9 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 9. An existing entry changes only for a cited bug, reported to the owner;
  the 9 carry no source comment, so a range or build that a fetched source contradicts is
  reported in #83, not changed here (batches 10 to 12's rule). Adding the `footage` and
  `semitones` keywords changes no existing build, and Task 1's before-and-after record of every
  entry in the catalog checks it.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown by
  a test, you should understand why it's happening and be concerned": a warning is a finding, and
  it must be understood before going on.
- Commits as batches 4 to 12: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this plan,
  never from memory. Write no `.md` file beyond those Task 6 names. Never use `git stash`: the
  stack is shared with other worktrees and sessions (#80, "Incidents and process"). Set work aside
  with a temporary commit instead.

## Review Focus

1. **A compass read without the stop's footage.** An organ stop's range in the catalog is its keys
   at 8' pitch, and the stop sounds at its footage: a 16' bourdon on the keys C2–C7 sounds C1–C6,
   a 4' spitzflöte C3–C8, a 2 2/3' nasard G3–G8. A range copied as sounding pitch, or a stop built
   at 8' under a 4' name, is an octave or a twelfth wrong. Range ruling 2 takes a keyed compass
   only with the stop's footage, the form check computes the sounding span, the code check compares
   each built footage with the sheet, and `test_harmonic_instruments_sound_their_note` measures
   each `ORGAN_STOP_FOOTAGES` entry at its footage.
2. **A footage or a registration shipped as a new sound.** A 4' principal is the 8' principal an
   octave up, and "full organ" is several stops drawn at once. The footage ruling makes a footage
   difference a sound-alike's `sound_changes`, never a SHIP (rule 7), and the stop-or-setting
   ruling makes a registration a setting. The anti-goal test refuses any new build equal to another
   entry's.
3. **A cited trait the build cannot make.** A stopped pipe's missing even harmonics, a celeste's
   two ranks beating, the vox humana's tremulant, a mixture's breaks, a fairground organ's drums, a
   regal's short resonators. Each waits for its feature or gets the one table the plan allows for
   it (`STOPPED_FLUTE_LEVELS`, `CLOSED_REED_LEVELS`, only with a cited trait), and
   `test_a_stopped_or_closed_stop_sounds_odd_harmonics` pins the tables.
4. **A self-playing organ's notes read as a range, or its tag forgotten.** A barrel organ has no
   keys; its sources give a pipe count, a tune count or a footage ("one rank of ten metal pipes at
   2' pitch", the serinette) rather than notes. Range ruling 5 takes none of them. A shipped
   self-playing organ carries `Tag.MECHANICAL`; the form check refuses any other tag, the code
   check compares each entry's tags with the sheet, and `test_the_mechanical_organs_are_tagged`
   lists them.
5. **The same instrument shipped twice, or a name decided twice.** `regal`, `regal organ` and
   `bible regal`; `fairground organ`, `street organ`, `band organ`, `dance organ`, `carousel organ`
   and `limonaire`; `barrel organ` and `serinette`, `bird organ`, `perroquette`; `air calliope`,
   `calliaphone` and the catalog's `calliope`; `chamber organ` and the catalog's `positive organ`;
   `pyrophone` and `fire organ`; `orchestrion`, `panharmonicon` and `apollonicon`; `open diapason`
   and `pipe organ principal`; `organ trompette` and `pipe organ reed`; `dulciana` (batch 11's) and
   `gemshorn` (batch 9's). Rules 3, 5 and 8 and the boundary, generic-term and ambiguity rulings
   decide each, the form check refuses a name taken before the batch, and the code check finds
   every name exactly once.

---

## File Structure

- Create `src/glitchygames/audio/instruments/organs.py`. It takes the "Organs" section of
  `keyboards.py` (`_pipe_stop`, `PRINCIPAL_LEVELS`, `FLUTE_STOP_LEVELS`, `REED_STOP_LEVELS`,
  `STRING_STOP_LEVELS`, `CALLIOPE_LEVELS`, the 9 entries), unchanged, as `_ORGAN_BUILDS`, and
  `ORGANS = _ORGAN_BUILDS + ORGAN_SOUND_ALIKES`. New builds go after the 9; a new level table sits
  beside the five.
- Create `src/glitchygames/audio/instruments/organ_sound_alikes.py`, holding
  `ORGAN_SOUND_ALIKES`.
- Modify `timbres.py` (`blown` gains `semitones: float = 0.0`), `keyboards.py` (the section and
  its organ words leave; it keeps the keyboards and electromechanical instruments), `registry.py`
  (it imports `ORGANS` from `organs.py`; its place in `FAMILY_TABLES`, after the keyboards,
  doesn't change), `aliases.py` (the batch's ALIAS rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5) and
  `tests/test_process_state_guard.py` (Task 1: its `audio/instruments/keyboards.py` entry,
  `PRINCIPAL_LEVELS`, `REED_STOP_LEVELS` and `STRING_STOP_LEVELS`, moves to a new
  `audio/instruments/organs.py` entry, since those three `falling_series` calls move).
- Create `plans/data/instrument-audit/batch-13.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #83), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #83):

- **Organs get their own module.** `keyboards.py` holds three families, and every family a batch
  has grown since batch 4 has a module of its own and a sibling sound-alikes module that names it
  ("The family's builds are in …"). The organ section is self-contained: only `registry.py` imports
  `ORGANS`, no other module imports `_pipe_stop` or the five level tables (checked with grep; the
  test file names only `Family.ORGANS`), and the electromechanical builds share nothing with it
  but `timbres.drawbar_organ`, which stays in `timbres.py`. The footage mechanism is the
  organs' own, and the stops and the mechanical tag would otherwise sit beside the pianos. The
  electromechanical section stays in `keyboards.py`: its batch (2) is done and no batch grows it
  here. The move is mechanical, the guard's three lines move with the tables, and Task 1's
  before-and-after record checks it.
- **A stop is an entry; a registration is a setting.** The spec's Non-goals make "Articulations
  and ensemble patches (pizzicato, mutes, string sections)" settings, because each changes how an
  instrument already in the catalog is played. An organ stop is not that: it is a rank of pipes of
  its own (or a named set of ranks voiced as one, a cornet, a sesquialtera, a mixture), with its own
  pipes and voicing, and a game asks for it by name ("a bourdon", "a vox humana"), as the catalog's
  four `pipe organ` stops already are. So a stop is a catalog entry, decided like any instrument. A
  registration, several stops drawn together, is a setting, as a string section is (the existing
  `pipe organ plenum` stays: Global Constraints). The tremulant, couplers, the swell box and the
  expression pedal are settings too, a technique the player applies, unless a cited source makes
  one part of a stop's own sound (the vox humana's tremulant), when the row waits for the feature.
- **The footage ruling.** A stop's footage is the length of its lowest pipe, and it fixes where
  the stop sounds against its keys: 8' at the key, 16' an octave below, 4' an octave above, 2 2/3'
  a twelfth above. The catalog already ranges an organ by "its keys at 8' pitch (a 61-note
  manual, C2-C7)" with "a 16' stop or drawbar" sounding "an octave lower" (`keyboards.py`'s
  docstring); this ruling generalises that to every footage:
  1. The sheet's `footage` cell holds the footage of each rank in feet as the source gives it,
     highest first, separated by ` + `, each an integer or a mixed number (`16`, `8`, `2 2/3`,
     `8 + 4 + 2 2/3 + 2 + 1 3/5`), or `none` for an organ that is not a stop (a regal, a barrel
     organ, the calliope), whose range is its sounding notes. A stop's footage is sourced by a
     fetched passage after `Footage:` in `notes`, its URL in `footage_source`. A source giving the
     stop at several footages gives the one it calls usual or standard; otherwise the row WAITs `a
     sourced footage` (a source wait this plan adds).
  2. A one-rank stop is built with `_pipe_stop(..., footage=<feet>)`, which sounds the tone
     `12 x log2(8 / footage)` semitones from the key (through `blown`'s new `semitones`; the chiff
     noise is not moved), and its range is its keys at 8' pitch.
  3. Footage is pitch, not timbre: a footage difference alone never makes a SHIP (rule 7). A stop
     whose only difference from an organ entry built with `_pipe_stop` is its footage is a
     SOUND_ALIKE of it with `sound_changes={'footage': <feet>}`, as batch 12 carried drone pitches;
     a sound-alike at its parent's footage has no change. Only a `_pipe_stop` parent takes the
     change (the four `pipe organ` stops or a SHIP row of the half built with `_pipe_stop`).
  4. A compound stop (several ranks voiced as one) whose ranks are all at harmonics 1 to 32 of the
     key, and whose source gives no breaks, is one wave of those harmonics (as `pipe organ
     plenum`'s nine drawbars are one wave): a SHIP built with `_pipe_stop(compound_stop_levels(...),
     ...)` at footage 8, ranged by its keys, its lowest rank's harmonic deciding nothing about the
     range. The first code task that ships one adds `compound_stop_levels(levels:
     Sequence[float], footages: Sequence[float]) -> tuple[float, ...]` to `organs.py` (each rank's
     `levels` placed at harmonics n x 8 / footage of the key, summed, normalised to a loudest level
     of 1.0, at most 32 harmonics) and `test_a_compound_stop_sums_its_ranks_as_harmonics`
     (`compound_stop_levels((1.0, 0.5), (8.0, 4.0))` is `(1.0, 1.5, 0.0, 0.5)` divided by 1.5,
     and a rank at 2 2/3' lands on harmonic 3). The rank levels are the parent table's, equal per
     rank, and marked sound design. A compound stop is never a SOUND_ALIKE.
  5. A mixture whose source says its ranks break back across the compass is the spec's "large
     mixtures": WAIT `more than four sources` (the spec's name), and #83 records that the blocker
     is the breaks (one fixed wave per entry), not the source count.
  6. The sounding span, the keys moved by the first rank's footage, must lie between A0 and C8
     (range ruling 8): a 2' stop on C2–C7 sounds C4–C9 and WAITs `a range above C8`; a 32' stop
     WAITs `sub-audio fundamentals`. #83 asks whether a stop may sound above C8 when its keys do
     not.
- **Range ruling for organs.** A sourced range is, for a keyed organ or stop, the lowest and
  highest keys of the compass it plays from, at 8' pitch, and for a keyless organ (barrel,
  fairground, serinette, flute clock) or the calliope, its lowest and highest sounding notes, as a
  fetched source states them:
  1. *Stated*: both notes as the compass or range, in note names with octaves (scientific `C2`;
     Helmholtz `C`–`c''''` or the organ builders' `CC`–`c4` where the source names the notation or
     fixes the octave), or the lowest note and an exact count of keys above it, as batch 7 allowed.
     A short octave (`C/E`) gives its lowest sounding note, and the range is its lowest and highest
     sounding notes.
  2. *Footage is the transposition*: a keyed compass counts for a stop only with the stop's footage
     from a fetched source (batch 11's lesson, "a written range counts only with its stated
     transposition"); the range cell holds the keys, and the footage moves the sound (the footage
     ruling).
  3. *The stop's keys*: a stop plays from the manual or pedalboard its own source places it on, so
     that division's compass is the stop's own range, not a sibling's. It is taken from a source
     that calls one manual (or pedal) compass standard (the American Guild of Organists' standard
     console specification is a lead to fetch, not a source until fetched and quoted), or from the
     stop's own source. A compass the stop's own source states (a treble-only cornet "from middle
     C") outranks the division's. A stop its source places on both, with neither called usual,
     takes the manual. A keyed organ that is not a stop (a regal, a portative) is ranged by its own
     compass, never by a pipe organ's manual.
  4. *Extensions and extremes*: a note in parentheses, an optional extension, a note the source
     gives to some instruments only, is left out, or the row WAITs.
  5. *Not a range*: a hedged span ("about", "approximately", "typically", "commonly", "usually",
     "can reach"), a width or count with no pitches ("61 notes", "five octaves", "about nine
     notes", "25 to 67 whistles"), a tune count, a pipe count, a footage alone ("at 2' pitch", which
     names a register, not notes), note letters with no octaves, a key alone, or one pitch.
  6. *Several sizes*: the size or compass the source calls standard, usual or most common, else the
     row WAITs (batch 7's rule). A source giving one instrument two compasses with neither standard
     has given none.
  7. *Sources*: the instrument's or stop's encyclopedia page (Wikipedia, Britannica, Grove where
     reached); a museum's object record (MIMO, the Met, the Musée de la musique, the Museum
     Speelklok, the Deutsches Musikautomaten-Museum, the Horniman); an organ builder's or a
     mechanical-organ builder's model page; a published organ reference (Audsley's books, public
     domain on archive.org; the Encyclopedia of Organ Stops, organstops.org, where its entry quotes
     a work it cites; the AGO or a national organists' body). A museum's or maker's page outranks an
     uncited Wikipedia line, and when they disagree the museum or maker decides (batch 11's lesson).
     A retailer's listing, a blog, a forum or a hobbyist's page is not a source. A list page
     (`List_of_pipe_organ_stops`) is a source for a name only. A range is never taken from a
     sibling, the parent, a related instrument or the audit.
  8. *The catalog's span*: the range and the sounding span (the footage ruling's rule 6) lie between
     A0 and C8; below, WAIT `sub-audio fundamentals`; above, WAIT `a range above C8`.
  9. *One note*: an instrument whose source gives it one note has no range. It WAITs `a sourced
     range`, the note quoted, and #83 carries #80's to #82's question.
  10. *Cited*: a range or footage from Wikipedia counts only when the raw wikitext shows a citation
      (a `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it in its own cell or paragraph, with no
      `{{citation needed}}` first, in a section not tagged `{{Unreferenced section}}`. The citation
      must support the line: where the cited work is reachable the worker opens it, and a citation
      that gives no range or footage is no citation. An uncited line is not a source, for a range,
      a footage or a trait that decides a SHIP or a WAIT.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then the
  derivation; then, for a stop, `Footage:`, its passages and the footage.
- **A stop's parent is an organ stop.** Every catalog organ entry shares the organ's speech (its
  attack and chiff), so a SOUND_ALIKE's parent is a catalog organ from before the batch or a SHIP
  row of its half, never another family's entry: an organ oboe or krummhorn is a reed stop, not
  the double reed it is named after. The stop's family, from its own page or an organ reference,
  chooses the parent: a principal (diapason) `pipe organ principal`, a flute `pipe organ flute`, a
  string `pipe organ string`, a chorus reed `pipe organ reed`, unless a cited trait makes it a SHIP
  or a WAIT. A keyless or small organ whose source relates its pipes to one of those takes it;
  otherwise it SHIPs a build its traits source, or WAITs.
- **Odd-harmonic tables, only for a cited trait.** A stopped flue pipe and a reed with a closed
  cylindrical resonator favour odd harmonics (as `winds.py` says of the clarinet, "a closed
  cylinder favours odd harmonics"), and no organ build has that. A SHIP row whose cited source names
  a stopped flue pipe's missing even harmonics builds with `STOPPED_FLUTE_LEVELS: Final[tuple[float,
  ...]] = (1.0, 0.0, 0.12, 0.0, 0.02)` (`FLUTE_STOP_LEVELS` with the even harmonics silent), and a
  reed whose cited source names a closed cylindrical resonator with `CLOSED_REED_LEVELS:
  Final[tuple[float, ...]] = falling_series(count=28, decibels_per_octave=2.5, odd_only=True)`
  (`REED_STOP_LEVELS`, odd only). Each is sound design, marked so in its comment, which cites the
  row's trait source. The first code task that ships such a row adds the table and
  `test_a_stopped_or_closed_stop_sounds_odd_harmonics`; `CLOSED_REED_LEVELS` is a `falling_series`
  call, so it gets a `CATALOG_SERIES` line in the process-state guard beside the three moved ones;
  `STOPPED_FLUTE_LEVELS` is a literal tuple and gets none. A stopped flue stop whose source names
  no such trait is a SOUND_ALIKE of `pipe organ flute`. Other values (`chiff`, `release`) are
  copied from the parent table's existing entry and marked as sound design.
- **Celestes.** A celeste is "an organ stop consisting of either one or two ranks of pipes slightly
  out of tune" (the Voix céleste page, quoted in `batch-8.tsv`). One rank beats only against another
  stop drawn with it, a registration and so a setting, and alone it is a string stop a few cents
  off, which is no trait (rule 7): a SOUND_ALIKE of `pipe organ string`. Two ranks beat against each
  other, which `blown`'s `chorus_cents` makes: the row SHIPs `_pipe_stop(STRING_STOP_LEVELS,
  chiff=0.0, chorus_cents=<cents>)` only with the detune its source states in cents (or in beats
  per second at a stated note, converted in the derivation), and the code task adds
  `chorus_cents: float = 0.0` to `_pipe_stop`, passed to `blown`. Without a stated detune it WAITs
  `a sourced detune` (a source wait this plan adds). The source's usual form (one rank or two)
  decides; neither called usual is `a sourced detune`.
- **The boundary.** Free-reed organs (H-S 412.132: the reed organ, harmonium, orchestrelle,
  chromelodeon) belong to free reeds: DROP "belongs to free reeds (H-S 412.132): <its words>".
  Electric organs belong to electronic (H-S 53: an oscillator organ) or electromechanical (H-S 51 or
  52: tonewheels, electrostatic discs): DROP "belongs to <family> (<class>): <its words>"; both
  batches are done, so Task 6 lists each in #70 for a later pass. An alias may still name an existing
  entry across the boundary, as batch 6's `vox continental` names `combo organ`. A maker's name
  (`farfisa`, `lowrey organ`, `baldwin organ` if their pages are the company's) is DROP "a maker's
  name, not one instrument" unless a cited page gives it as one instrument's name. The pyrophone
  and the hydraulis are organs (the spec, and "Hydraulis … is an organ", the mechanical audit).
- **Generic and ambiguous terms.** A name its source gives to a class rather than one instrument
  (`barrel organ` if its page covers street, chamber and church barrel organs; `limonaire`, "the
  generic French term", by the mechanical audit) is DROP "a generic term for <the instruments>",
  unless the source makes it one instrument's name. A name a source gives to two instruments
  (`dulciana`; `gemshorn`) is DROP "an ambiguous name: <the two>". `dulciana` is DROP "already
  decided: batch-11.tsv DROP, an ambiguous name (also the dulcian's Italian name, double reeds)";
  `gemshorn` is DROP "already decided: batch-9.tsv WAIT (the vessel flute); an ambiguous name:
  also the organ stop".
- **Mechanical organs.** A SHIP or SOUND_ALIKE row of an organ that plays itself from a pinned
  barrel, punched book, roll or card (the spec's `Tag.MECHANICAL`: "barrel and fairground organs,
  orchestrions, … serinettes") carries `tags` `mechanical`, which no other row has. Its range is
  its sounding notes (it has no keys). A fairground organ, orchestrion or panharmonicon whose
  source makes drums, cymbals or bells part of the instrument WAITs `more than four sources` (the
  spec names the orchestrion there). A self-playing mechanism is not a sound trait: the build is
  the pipes'. `test_organ_ranges_start_at_their_keys_eight_foot_pitch` assumes keys; a keyless row
  whose sourced range starts below C2 is a finding for the controller before any test changes.
- **The calliope and the steam and air variants.** The catalog's `calliope` (C3-G5, no source)
  stays unchanged. `air calliope` and the alias name `calliaphone` are ALIAS of `calliope` only on
  a cited page that makes them the calliope blown by air; a source that sets the air calliope apart
  in sound makes it a SOUND_ALIKE (its own range) or a SHIP. Steam's pitch drift with temperature
  (the audit) is a moving pitch: a row whose cited source makes it the sound WAITs `a pitch LFO
  (vibrato)`, with the source quoted.
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's
  in-production line): DROP "a one-off instrument, not a type a game would ask for" for one maker's
  or artist's design not in production (`sea organ`, `componium`, `chromelodeon` if not decided by
  the boundary, the round-1 gallery objects `beer bottle organ`, `bubble organ`, `uberorgan`,
  `sequential resonation machine`, each on its page), and DROP "no fetched source describes it"
  when no page describes the row. A reconstruction makers offer today, or a type a museum holds,
  is not a one-off (`hydraulis`, `portative organ`); an extinct type is decided like any other and
  waits if no source ranges it.
- **No unpitched organ.** Every organ in the catalog is pitched, and a sound-alike is pitched
  exactly when its parent is, so the batch row has no unpitched names; a row whose source gives no
  pitch is WAIT `a sourced range` (the pyrophone's "depends on tube" audit cell is no reason to
  call it unpitched).
- **No size chain.** Footages are pitch, and no candidate is a size of a catalog organ by its
  source; a new chain in `test_sized_families_descend_from_highest_to_lowest` is added only if a
  source names three or more shipped organs as sizes of one instrument.
- **Two halves, as explicit lists.** Half A, the organ stops, is these 29 candidates:
  `bourdon`, `cornet organ`, `diaphonic diapason`, `dulciana`, `gedeckt`, `gemshorn`, `kinura`,
  `larigot`, `nasard`, `open diapason`, `organ bombarde`, `organ clarinet`, `organ krummhorn`,
  `organ mixture`, `organ oboe`, `organ trombone`, `organ trompette`, `organ tuba`, `piccolo
  organ`, `posthorn`, `rohrflote`, `salicional`, `scharff`, `sesquialtera`, `spitzflote`, `stopped
  diapason`, `tierce`, `voix celeste`, `vox humana`.
  Half B, the organs as instruments (early and portable, self-playing, steam, fire and the
  electric names at the boundary), is the other 35:
  `air calliope`, `apollonicon`, `baldwin organ`, `band organ`, `barrel organ`, `beer bottle
  organ`, `bubble organ`, `chamber organ`, `choralcelo`, `chromelodeon`, `componium`, `compton
  electrone`, `dance organ`, `fairground organ`, `farfisa`, `fire organ`, `flute clock`, `hammond
  b3`, `hydraulis`, `hydraulophone`, `lowrey organ`, `orchestrion`, `panharmonicon`, `portative
  organ`, `pyrophone`, `reed organ`, `regal`, `regal organ`, `sea organ`, `sequential resonation
  machine`, `serinette`, `street organ`, `telharmonium`, `uberorgan`, `vox continental`.
  The list decides the half. All 6 alias names go with half B, whose candidates their pages decide:
  `bible regal`, `carousel organ`, `limonaire`, `bird organ`, `perroquette`, `calliaphone`. So half
  A's sheet holds 29 rows and half B's 41.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the batch,
  or a SHIP or SOUND_ALIKE row of the same half, never a row of the other half. So Task 4 needs
  nothing from Task 2. Half B drafts to a build file, appended to the sheet once half A is
  committed. The form check accepts a row the code already holds with the same target or parent
  (batch 7's lesson). If Task 5 finds a half-B build equal to a half-A build, that is a finding for
  the controller, who re-rules the row in a sheet fix commit.
- **A held-back guard.** As batch 12's `BAGPIPE_HELD_BACK`, this batch's guard is
  `ORGAN_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose
  reason is not `a sourced range` (an engine feature, a build of its own, a sourced footage, a
  sourced detune), and every alias row that waits for such a row. A test refuses each of its names
  in the catalog and the aliases, and the code check compares the table with the sheet.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task still fills `ORGAN_HELD_BACK` with the half's held rows
  and runs the code check, which must pass; its other steps are skipped, and Task 6 records the
  skip in #83.
- **Out of scope:** the audit's "Gaps you could not close" (the hydraulis's Aquincum data; the MIMO
  and Met regal and barrel organ records unopened; the kinura, posthorn and diaphonic diapason
  needing a theatre organ source; Lowrey, Baldwin and the Compton Electrone unread; the
  Cavaillé-Coll stops (flûte harmonique, gambe), the Spanish horizontal reeds (trompeta real,
  chirimía), the Dutch hoboy, schalmei and rankett stops, the Welte Philharmonie organ, Wurlitzer
  opus lists, Allen, Rodgers and digital organs; theatre organ percussion, which is tuned
  percussion's; the bell organ), and the mechanical audit's Welte philharmonic organ. Task 6 lists
  them in #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of these files is committed.

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-13-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-13-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
  Expected: `names before 809` (693 entries and 116 aliases, at `5cbbf882`). Any other number
  means the branch is not batch 12's HEAD: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && tolower($4) ~ /organ/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /organ/ {print tolower($1)}' round-1/merged-missing.tsv
  printf 'flute clock\ncomponium\n'
} | LC_ALL=C sort -u > ../../../build/batch-13-candidates.txt
cd ../../..
```
  Write the plan's 29 half-A names, one per line, to `build/batch-13-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-13-candidates.txt build/batch-13-half-a.txt > build/batch-13-half-b.txt`
  and `wc -l build/batch-13-*.txt`.
  Expected: 64 candidates, 29 in half A, 35 in half B, and
  `LC_ALL=C comm -13 build/batch-13-candidates.txt build/batch-13-half-a.txt` prints nothing.
  Check that `build/batch-13-half-b.txt` is exactly the plan's half-B list.

- [ ] **Step 3: The form check,** `build/batch-13-form-check.py`:
```python
"""Batch 13's sheet form check: uv run python -I build/batch-13-form-check.py SHEET.

Batch 12's form check (plans/2026-11-12-instrument-catalog-batch-12-implementation.md, "Before
the tasks" Step 3) with batch 13's changes (batch 13's plan, "Before the tasks"): the organs
family, the footage and footage_source columns in place of the drones, the mechanical tag, and a
stop's sounding span inside the catalog's.
"""

import csv
import math
import re
import sys
from fractions import Fraction

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note

STATUSES = ('SHIP', 'SOUND_ALIKE', 'WAIT', 'ALIAS', 'DROP')
# tests/audio/test_instrument_catalog.py APPROXIMATING_NAMES (after batch 12)
APPROXIMATING_NAMES = {
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
    'dizi', 'didgeridoo', 'piri', 'scottish smallpipes',
}
# The organ entries from before the batch built with _pipe_stop, the only builder that takes a
# footage (batch 13's plan, "The footage ruling", rule 3)
PIPE_STOP_ENTRIES = {
    'pipe organ principal', 'pipe organ flute', 'pipe organ reed', 'pipe organ string',
}
UNISON_FOOTAGE = Fraction(8)
# wave_from_levels holds harmonics 1 to 32 of the key
HIGHEST_HARMONIC = 32
TAGS = ('', 'mechanical')
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
with open('build/batch-13-names-before.txt', encoding='utf-8') as before_file:
    names_before = set(before_file.read().split('\n')) - {''}
ship_rows = {row['name']: row for row in rows if row['status'] == 'SHIP'}
alikes = {row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'}
organ_parents = set(ship_rows) | {
    name for name in names_before
    if name in instruments.CATALOG
    and instruments.entry(name).sounds_like is None
    and instruments.entry(name).family == 'organs'
}
pipe_stop_parents = PIPE_STOP_ENTRIES | {
    name for name, row in ship_rows.items() if row['builder'].startswith('_pipe_stop')
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


def rank_footages(cell):
    """Each rank's footage in feet, highest first as written, or None when the cell is none or bad."""
    if cell == 'none':
        return None
    try:
        footages = [sum(Fraction(part) for part in rank.split()) for rank in cell.split(' + ')]
    except (ValueError, ZeroDivisionError):
        return None
    return footages if footages and all(footage > 0 for footage in footages) else None


def sounding_footage(row):
    """The footage the row's first rank sounds at; a row with no footage sounds at its notes."""
    footages = rank_footages(row['footage'])
    return UNISON_FOOTAGE if footages is None else footages[0]


def in_span(note_name, shift=0.0):
    """A note name, moved by shift semitones, that the catalog accepts: A0 to C8."""
    try:
        number = Note(note_name).midi_number
    except Exception:
        return False
    return Note('A0').midi_number <= round(number + shift) <= Note('C8').midi_number


def ranged(row):
    """Both notes, lowest below highest, a range source and passage, a sounding span in A0-C8."""
    if not (in_span(row['lowest']) and in_span(row['highest'])):
        return False
    shift = 12.0 * math.log2(UNISON_FOOTAGE / sounding_footage(row))
    return (
        row['range_source'].startswith('http')
        and 'Range:' in row['notes']
        and Note(row['lowest']).midi_number < Note(row['highest']).midi_number
        and in_span(row['lowest'], shift)
        and in_span(row['highest'], shift)
    )


def footaged(row):
    """none, or a stop's ranks highest first, several only at harmonics 1-32, with a passage."""
    if row['footage'] == 'none':
        return True
    footages = rank_footages(row['footage'])
    if footages is None or footages != sorted(footages, reverse=True):
        return False
    if not row['footage_source'].startswith('http'):
        return False
    if 'Footage:' not in row['notes'].partition('Range:')[2]:
        return False
    if len(footages) == 1:
        return True
    ratios = [UNISON_FOOTAGE / footage for footage in footages]
    return all(ratio.denominator == 1 and 1 <= ratio <= HIGHEST_HARMONIC for ratio in ratios)


def alike_allowed(row):
    """A one-rank sound-alike of an organ; a footage change only on a _pipe_stop parent."""
    parent = row['alias_of']
    if parent not in organ_parents or parent in APPROXIMATING_NAMES:
        return False
    footages = rank_footages(row['footage'])
    if footages is not None and len(footages) > 1:
        return False
    parent_footage = sounding_footage(ship_rows[parent]) if parent in ship_rows else UNISON_FOOTAGE
    return sounding_footage(row) == parent_footage or parent in pipe_stop_parents


names = [row['name'] for row in rows]
bad = [row['name'] for row in rows if not pattern.fullmatch(row['name'])
       or row['status'] not in STATUSES
       or row['family'] != 'organs'
       or not row['audit_name']
       or not (row['hs'] == 'none' or row['hs'][:1].isdigit())
       or row['tags'] not in TAGS
       or (row['tags'] and row['status'] not in {'SHIP', 'SOUND_ALIKE'})
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)
                or not footaged(row)))
       or (row['status'] in {'SHIP', 'SOUND_ALIKE', 'ALIAS'} and taken(row))
       or (row['status'] == 'SOUND_ALIKE' and not alike_allowed(row))
       or (row['status'] == 'WAIT' and not row['waits_for'])
       or (row['status'] == 'ALIAS'
           and row['alias_of'] not in organ_parents | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {status: sum(row['status'] == status for row in rows) for status in STATUSES})
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: The quote check,** `build/batch-13-quote-check.py`: batch 12's quote check
  (batch 12's plan, "Before the tasks" Step 4), copied, with these changes only. Its docstring
  names batch 13 and "the Range: and Footage: passages"; `PAGES` is `Path('build/batch-13-pages')`;
  and its `sections` are
```python
    sections = [('range', quoted(row['notes'], 'Range:', 'Footage:'), row['range_source'])]
    if row['footage'] != 'none':
        sections.append(('footage', quoted(row['notes'], 'Footage:', None), row['footage_source']))
```
  so a row with no footage needs no `Footage:` passage. It checks what can be checked
  mechanically; a worker still applies range ruling 10 in full.

- [ ] **Step 5: The code check,** `build/batch-13-code-check.py`:
```python
"""Batch 13's code check: uv run python -I build/batch-13-code-check.py SHEET.

Batch 12's code check with batch 13's changes (batch 13's plan, "Before the tasks"): every row is
checked, the held-back guard, the footages and the mechanical tag are compared with the sheet,
every built footage is the sheet's, and the builds, sound-alikes and aliases follow the sheet's
order. The test file's tables are read as literals, without importing the tests. A one-off check
may read the private _ORGAN_BUILDS; a test may not.
"""

import ast
import csv
import math
import sys
from fractions import Fraction
from functools import partial

from glitchygames.audio import instruments
from glitchygames.audio.instruments.catalog import Tag
from glitchygames.audio.instruments.organ_sound_alikes import ORGAN_SOUND_ALIKES
from glitchygames.audio.instruments.organs import _ORGAN_BUILDS

TEST_FILE = 'tests/audio/test_instrument_catalog.py'
EXISTING_COUNT = 9
UNISON_FOOTAGE = 8.0


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


def ranks(row):
    return [] if row['footage'] == 'none' else row['footage'].split(' + ')


def expected_footage(row):
    """The footage the build sounds at: a one-rank stop's own; a compound or none, the key's."""
    row_ranks = ranks(row)
    if len(row_ranks) != 1:
        return UNISON_FOOTAGE
    return float(sum(Fraction(part) for part in row_ranks[0].split()))


def built_footage(entry):
    """The footage an entry's build sounds at: its change, its parent's, or its build's keyword."""
    if 'footage' in entry.sound_changes:
        return float(entry.sound_changes['footage'])
    if entry.sounds_like is not None:
        return built_footage(instruments.entry(entry.sounds_like))
    if isinstance(entry.build, partial):
        return float(entry.build.keywords.get('footage', UNISON_FOOTAGE))
    return UNISON_FOOTAGE


with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
rows_by_name = {row['name']: row for row in rows}


def held_back(row):
    """A WAIT for any reason but a sourced range, or an alias waiting for one."""
    if row['status'] != 'WAIT' or row['waits_for'] == 'a sourced range':
        return False
    if row['waits_for'].startswith('its target, '):
        target = rows_by_name.get(row['waits_for'].removeprefix('its target, '))
        return target is not None and held_back(target)
    return True


expected_footages = {}
for row in rows:
    name = row['name']
    if row['status'] in {'SHIP', 'SOUND_ALIKE'}:
        entry = instruments.entry(name)
        assert (entry.family, entry.lowest, entry.highest, entry.title) == (
            row['family'], row['lowest'], row['highest'], row['title'],
        ), name
        parent = row['alias_of'] if row['status'] == 'SOUND_ALIKE' else None
        assert entry.sounds_like == parent, name
        tags = frozenset({Tag.MECHANICAL}) if row['tags'] == 'mechanical' else frozenset()
        assert entry.tags == tags, name
        footage = expected_footage(row)
        assert math.isclose(built_footage(entry), footage), name
        if not math.isclose(footage, UNISON_FOOTAGE):
            expected_footages[name] = ranks(row)[0]
        if parent is not None:
            changes = dict(entry.sound_changes)
            if math.isclose(built_footage(instruments.entry(parent)), footage):
                assert changes == {}, name
            else:
                assert set(changes) == {'footage'}, name
                assert math.isclose(changes['footage'], footage), name
    elif row['status'] == 'ALIAS':
        assert instruments.ALIASES[name] == row['alias_of'], name
    else:
        assert name not in instruments.CATALOG, name
        assert name not in instruments.ALIASES, name
ship_names = [row['name'] for row in rows if row['status'] == 'SHIP']
alike_names = [row['name'] for row in rows if row['status'] == 'SOUND_ALIKE']
mechanical_names = [
    row['name'] for status in ('SHIP', 'SOUND_ALIKE') for row in rows
    if row['status'] == status and row['tags'] == 'mechanical'
]
assert test_table('ORGAN_STOP_FOOTAGES') == expected_footages, 'ORGAN_STOP_FOOTAGES'
assert test_table('MECHANICAL_ORGAN_NAMES') == mechanical_names, 'MECHANICAL_ORGAN_NAMES'
assert test_table('ORGAN_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'ORGAN_HELD_BACK'
assert list(test_table('ORGAN_HELD_BACK')) == [
    row['name'] for row in rows if held_back(row)
], 'held-back order'
assert test_table('NEW_ORGAN_NAMES') == ship_names, 'NEW_ORGAN_NAMES'
assert list(test_table('ORGAN_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'ORGAN_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in _ORGAN_BUILDS[EXISTING_COUNT:]] == ship_names, 'build order'
assert [entry.name for entry in ORGAN_SOUND_ALIKES] == alike_names, 'sound-alike order'
sheet_aliases = [row['name'] for row in rows if row['status'] == 'ALIAS']
assert [name for name in instruments.ALIASES if name in set(sheet_aliases)] == sheet_aliases, (
    'alias order'
)
print('matches', len(rows), 'rows')
```
  It cannot run until Task 1 has created `organs.py`, `organ_sound_alikes.py` and the test
  tables.

---

### Task 1: Organs in their own module, unchanged; their sound-alikes module; a stop's footage; the batch table's row and the held-back guard

**Files:**
- Create: `src/glitchygames/audio/instruments/organs.py`,
  `src/glitchygames/audio/instruments/organ_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/keyboards.py`, `registry.py`, `timbres.py`
  (`blown`)
- Test: `tests/audio/test_instrument_catalog.py`, `tests/test_process_state_guard.py`

**Interfaces:**
- Produces: in `timbres.py`, `blown(..., semitones: float = 0.0)`. In `organs.py`,
  `ORGANS: Final[tuple[CatalogEntry, ...]] = _ORGAN_BUILDS + ORGAN_SOUND_ALIKES`, with
  `PRINCIPAL_LEVELS`, `FLUTE_STOP_LEVELS`, `REED_STOP_LEVELS`, `STRING_STOP_LEVELS` and
  `CALLIOPE_LEVELS` under their current names, `UNISON_FOOTAGE: Final[float] = 8.0` and
  `_pipe_stop(levels: tuple[float, ...], *, chiff: float, release: float = 0.15, footage: float =
  UNISON_FOOTAGE) -> Instrument`. `ORGAN_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty.
  The test file gains `EXISTING_ORGAN_NAMES: frozenset[str]` (the 9); `NEW_ORGAN_NAMES:
  list[str]`, `ORGAN_SOUND_ALIKE_PARENTS: dict[str, str]`, `ORGAN_STOP_FOOTAGES: dict[str, str]`,
  `MECHANICAL_ORGAN_NAMES: list[str]` and `ORGAN_HELD_BACK: dict[str, str]`, all empty here, for
  Tasks 3 and 5 to fill; `footage_feet(footage: str) -> float` and `built_footage(catalog_entry:
  CatalogEntry) -> float`; the tests below; and the row `Family.ORGANS:
  BatchFamily(EXISTING_ORGAN_NAMES, NEW_ORGAN_NAMES, ORGAN_SOUND_ALIKE_PARENTS)` in
  `BATCH_FAMILIES`. Also `build/catalog-builds-before.txt`.

- [ ] **Step 1: Record every build.** `blown` is shared by most of the catalog, so record all of
  it: run batch 4's Task 1 Step 1 command with `instruments.names()` in place of
  `instruments.names(family='plucked strings')` and `build/catalog-builds-before.txt`.
  Expected: `recorded 693`.

- [ ] **Step 2: Write the tests.** After `BAGPIPE_RETUNED_DRONES`, add `EXISTING_ORGAN_NAMES` (the
  9 names, one per line, in catalog order, with the comment "# The 9 organs that predate batch 13:
  their shared builds predate the anti-goal rule"), then `NEW_ORGAN_NAMES: list[str] = []`,
  `ORGAN_SOUND_ALIKE_PARENTS: dict[str, str] = {}`, each commented as batch 12's lists are, and:
```python
# Batch 13's organ entries that sound at a footage other than 8' (a one-rank stop, through
# _pipe_stop's footage), with the footage as the sheet writes it: the range is the keys at 8'
# pitch and the stop sounds 12 x log2(8 / footage) semitones from them
# (plans/data/instrument-audit/batch-13.tsv)
ORGAN_STOP_FOOTAGES: dict[str, str] = {}
# Batch 13's self-playing organs (Tag.MECHANICAL), in catalog order: the builds, then the
# sound-alikes, each in the sheet's order (plans/data/instrument-audit/batch-13.tsv)
MECHANICAL_ORGAN_NAMES: list[str] = []
```
  Put the organs row between the plucked strings and electronic rows in `BATCH_FAMILIES`, which is
  table order. In `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the
  `BATCH_FAMILIES` loop's `if name in BAGPIPE_RETUNED_DRONES:` becomes `if
  instruments.entry(name).sound_changes:` (a retuned bagpipe or a stop at another footage differs
  from its parent; the bagpipe test still pins which bagpipes are retuned), and the closing list
  gains `+ list(ORGAN_SOUND_ALIKE_PARENTS)` between the plucked strings' and the electronic lines,
  its comment reading "… plucked strings, organs, electronic, …". `CHANGED_SOUND_ALIKE_NAMES`'s
  condition becomes `catalog_entry.family not in {Family.BAGPIPES, Family.ORGANS}`, and its comment
  adds "a stop at another footage sustains too; test_an_organ_stop_sounds_at_its_footage checks
  it". In `test_harmonic_instruments_sound_their_note`, `hertz` is also multiplied by `8.0 /
  footage_feet(ORGAN_STOP_FOOTAGES.get(name, '8'))`. After
  `test_a_cylindrical_chanter_sounds_odd_harmonics`, add:
```python
# Every name plans/data/instrument-audit/batch-13.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# footage or a sourced detune, and the alias rows that wait for one of them, in the sheet's order.
# None ships under that name or as an alias until the reason is met (decision 4; batch 13). The
# test matches exact names
ORGAN_HELD_BACK: dict[str, str] = {}


def test_no_organ_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is an organ the sheet holds back."""
    assert set(ORGAN_HELD_BACK) & set(instruments.names()) == set()
    assert set(ORGAN_HELD_BACK) & set(instruments.ALIASES) == set()


def footage_feet(footage: str) -> float:
    """A footage as the sheet writes it ('16', '2 2/3') in feet.

    Returns:
        The footage in feet.
    """
    return float(sum(Fraction(part) for part in footage.split()))


def built_footage(catalog_entry: CatalogEntry) -> float:
    """The footage an organ entry sounds at: its own change, its parent's, or its build's keyword.

    Returns:
        The footage in feet (8.0 for an entry built at its keys' pitch).
    """
```
  `built_footage`'s body follows the code check's `built_footage`, with `8.0` for its constant.
  Then:
  - `test_blown_moves_its_tone_by_its_semitones`: `blown(FLUTE_STOP_LEVELS, attack=0.04,
    release=0.15, semitones=12.0)` and `semitones=-12.0`, each rendered at `A3` with `rendered`,
    held from 0.15 s to 0.35 s; `best_period_near(held, hertz=440.0)` and `hertz=110.0` each lie
    within 30 cents of 440 and 110 Hz; and `blown(FLUTE_STOP_LEVELS, attack=0.04, release=0.15) ==
    blown(FLUTE_STOP_LEVELS, attack=0.04, release=0.15, semitones=0.0)`.
  - `test_an_organ_stop_sounds_at_its_footage`: the organ entries whose `built_footage` is not 8.0
    are exactly `ORGAN_STOP_FOOTAGES`'s keys, each with `built_footage(...) ==
    pytest.approx(footage_feet(footage))`; and every organ entry whose `sound_changes` is not empty
    has `set(catalog_entry.sound_changes) == {'footage'}` (the harmonic test measures the pitch).
  - `test_the_mechanical_organs_are_tagged`: `instruments.names(family=Family.ORGANS,
    tag=Tag.MECHANICAL) == tuple(MECHANICAL_ORGAN_NAMES)`.
  Import `Fraction` from `fractions` and `FLUTE_STOP_LEVELS` from
  `glitchygames.audio.instruments.organs` (a public table, as `FORMANT_TABLE` is imported).

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or footage or mechanical or semitones or one_shot or sound_their_note" -v`
  Expected: `test_blown_moves_its_tone_by_its_semitones` fails (`blown` has no `semitones` yet);
  and the import of `glitchygames.audio.instruments.organs` fails until Step 4. Both pass after
  Step 4; the rest are guards that hold the later tasks, with the ID `[organs]` seventh.

- [ ] **Step 4: Move the section and add the footage.** Read every comment on the moved code
  first. In `timbres.py`, `blown` gains `semitones: float = 0.0`, passed as `semitones=` to the
  tone, chorus and bite `Source`s (never the breath noise), documented as "Moves the tone's
  pitched layers this many semitones from the note (an organ stop of another footage); the breath
  stays." Move `keyboards.py`'s "Organs" section into `organs.py` unchanged, comments included,
  with the tuple renamed `_ORGAN_BUILDS`, and define `ORGANS` after it as the concatenation,
  importing `ORGAN_SOUND_ALIKES`. `_pipe_stop` gains `footage: float = UNISON_FOOTAGE` and passes
  `semitones=12.0 * math.log2(UNISON_FOOTAGE / footage)` to `blown` (no branch: 0.0 at 8'), with
  `UNISON_FOOTAGE: Final[float] = 8.0` commented "a stop of 8' sounds at its key's pitch". The new
  module docstring's first line is "Organs: pipe organ stops, positive, combo and theatre organs,
  and the calliope." It takes `keyboards.py`'s organ sentences (drawbar registrations or pipe
  stops, the principal's, flute's and reed's tones, the keys at 8' pitch), and says that a stop
  sounds at its footage against its keys (16' an octave below, 4' an octave above, 2 2/3' a
  twelfth above, through `_pipe_stop`'s `footage`), that a self-playing organ carries
  `Tag.MECHANICAL`, and that the sound-alikes are in `organ_sound_alikes.py` and the keyboards and
  electromechanical instruments in `keyboards.py`. `keyboards.py`'s docstring becomes "Keyboards
  (pianos, harpsichords, celesta) and electromechanical instruments." without its organ sentences
  except where the tonewheel organs need them, and names `organs.py`; its `blown` import goes if
  nothing left uses it. `organ_sound_alikes.py` gets the empty table and
  `bagpipe_sound_alikes.py`'s docstring with "Organs'" for "Bagpipes'", ending "The family's builds
  are in ``organs.py``.", its drone sentence replaced by "A sound-alike stop whose source gives it
  another footage than its parent carries it as ``sound_changes``, its only change." Point
  `registry.py` at the new module. In `tests/test_process_state_guard.py`, the
  `'audio/instruments/keyboards.py'` entry's three lines move, unchanged, to an
  `'audio/instruments/organs.py'` entry in the dict's alphabetical place. If the guard then asks
  for an entry for `_ORGAN_BUILDS`, `ORGANS` or `ORGAN_SOUND_ALIKES`, that is a finding:
  `bagpipe_sound_alikes.py` needed none, so read why before writing any reason.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `instruments.names()` and `build/catalog-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
SKIP=replay-metrics git commit -m "Instrument catalog: organs in their own module, unchanged; their sound-alikes module; a stop's footage; the held-back guard" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
  Run each lint command as its own line (batch 11's Task 1: zsh word-splitting once made a
  combined run a no-op).

---

### Task 2: The organ stops sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. Put no personal data in any request, in a header, a
URL or a payload. Save each ranged row's raw pages as `build/batch-13-pages/<name, spaces as
hyphens>--<n>.txt` (for Wikipedia, the `action=raw` wikitext) under the quote ruling. A list page
(`List_of_pipe_organ_stops`) is a source for a name only. The sound, the stop's family, the
footage and the range come from the stop's own page or an organ reference under range ruling 7.
The audit's rows and "Range checks" are leads, not sources, so fetch them. Fetch the page of every
existing entry you name as a parent, and record what it says in the row's notes. Never use `git
stash`. This task may start as soon as the controller has written the shared files, alongside
Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-13.tsv`
- Create (not committed): `build/batch-13-half-a.tsv`, and the raw pages in
  `build/batch-13-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `organs.md` ("Rejected or corrected proposed
  entries", "Aliases", "Range checks", "Gaps you could not close"); `batch-2.tsv` (`kinura`),
  `batch-8.tsv` (`vox humana`, `voix celeste`), `batch-9.tsv` (`gemshorn`), `batch-11.tsv`
  (`dulciana`); `build/batch-13-names-before.txt`, `build/batch-13-half-a.txt`,
  `build/batch-13-half-b.txt`, `build/batch-13-form-check.py` and `build/batch-13-quote-check.py`.
- Produces: `batch-13.tsv` with batch 12's first fifteen columns and two more:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	footage	footage_source`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `organs` on every row; `tags` is empty
  or `mechanical`. A SHIP or SOUND_ALIKE row has `lowest`, `highest` (the keys at 8' pitch for a
  stop, the sounding notes otherwise), `range_source`, `footage` (or `none`), `footage_source`
  when the footage is not `none`, and `notes` holding `Range:` and, for a stop, `Footage:`, each
  with its «raw passages» and derivation. `hs` is the Hornbostel–Sachs class a fetched source
  gives, else `none`. A candidate row's `audit_name` is its name in
  `build/batch-13-candidates.txt`; an alias row's is its audit line. Also
  `build/batch-13-half-a.tsv`, the half as committed, which Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-13-half-a.txt`'s order.

  The rules are batch 12's, changed for this family:

  1. **SHIP** only with name, title, sound, range and (for a stop) footage from fetched sources.
     Quote in `notes` the passage that describes the sound or construction (flue or reed, open,
     stopped or half-stopped, its scale, its resonator) and, after `Range:` and `Footage:`, the
     «raw passages» and the derivations under the rulings. The `builder` cell gives the call
     (`_pipe_stop` with its levels and keywords, `STOPPED_FLUTE_LEVELS` or `CLOSED_REED_LEVELS` or
     `compound_stop_levels` under the plan's rulings) and says which values come from the source
     and which are sound design, copied from which entry.
  2. **SOUND_ALIKE**: a verified stop or organ that rule 7 finds would sound like an existing organ
     entry or a SHIP row of this half. `alias_of` is its parent (the plan's parent ruling). The
     `notes` begin "Sound-alike:", quote the source's description, and say why that entry is the
     nearest (the stop's family). It has its own range, and the `builder` cell says "unchanged" or
     "footage <feet>". It is never a compound stop, never another sound-alike's sound-alike, never
     one of `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row of this half. If the target waits, the row is WAIT with `waits_for`
     `its target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is
     dropped". An ambiguous name or a generic term is DROP under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `a sourced footage`, `a sourced
     detune`, `more than four sources`, `a pitch and amplitude LFO (the tremulant)`, `sub-audio
     fundamentals`, `a range above C8`, `its own build (<the trait>)`, or another name of Global
     Constraints. The feature must be the sound the source describes, not a technique or setting a
     player applies (the stop-or-setting ruling). A cited trait no builder makes means the row
     waits. Any other name is allowed only with the source quoted, and Task 6 lists it in #83.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     boundary ruling's words), is a one-off, or is already decided: in the catalog under that name
     (name the entry), an alias already (name its target), or a row of an earlier sheet (name the
     sheet and its status).
  6. A row the audit marks "(memory)", UNVERIFIED for existence, or sourced only by a list page has
     no sourced sound or range yet. Fetch its own page; the audit's URL is a lead. If no page can be
     found, the row is DROP "no fetched source describes it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='organs'))"`
     and the builds in `organs.py`) and every SHIP row above it. If no cited trait (stopped or
     closed pipes' odd harmonics, a two-rank celeste's sourced detune, a compound stop's ranks)
     makes it sound different, it is a SOUND_ALIKE under rule 2. A number chosen only to differ
     does not count, nor a difference of 1 or 2 percent in a value (batch 11's contraforte), nor a
     loudness ("soft", "the softest stop": the builds are normalised), nor a range, a footage, a
     scale or the manual it plays from. A footage is carried as the sound-alike's change (the
     footage ruling).
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.

  This half's own cases:

  - **Principals.** `open diapason` is the principal stop (the audit: "catalog 'pipe organ
    principal' is nearly the same"): a SOUND_ALIKE of `pipe organ principal` with its own range, or
    WAIT. `diaphonic diapason` (a theatre principal) and `kinura` and `posthorn` (theatre reeds,
    "existence and range UNVERIFIED") follow rule 6.
  - **Flutes.** `stopped diapason`, `gedeckt` and `bourdon` are stopped flues: the first whose
    cited source names the missing even harmonics SHIPs with `STOPPED_FLUTE_LEVELS`, and the others
    are its sound-alikes (a 16' bourdon with `footage` 16), or SOUND_ALIKE of `pipe organ flute`
    without that trait. `rohrflote` (half-stopped) and `spitzflote` (conical) are decided under
    rule 7: a trait between two tables is no table, so each is a sound-alike or waits.
    `piccolo organ` (2'), `nasard` (2 2/3'), `tierce` (1 3/5') and `larigot` (1 1/3') on a C2–C7
    manual sound above C8 (the footage ruling's rule 6). `gemshorn` is DROP under the
    ambiguity ruling.
  - **Compound stops.** `sesquialtera` (2 2/3' + 1 3/5') and `cornet organ` (up to five ranks) are
    compound stops under the footage ruling's rule 4, if their sources give no breaks;
    `organ mixture` and `scharff` break back by the audit's lead ("breaks back at octaves") and
    WAIT `more than four sources` only if their sources say so.
  - **Strings and celestes.** `salicional` is a string stop (a SOUND_ALIKE of `pipe organ string`
    unless a cited trait). `voix celeste` follows the celeste ruling. `dulciana` is DROP under the
    ambiguity ruling.
  - **Reeds.** `organ trompette` against `pipe organ reed` (titled "Pipe organ, trumpet 8'"), and
    `organ tuba`, `organ trombone` (16') and `organ bombarde` (16'), are chorus reeds: sound-alikes
    of `pipe organ reed` (with their footage) unless a cited trait. `organ clarinet` and `organ
    krummhorn` have cylindrical resonators by the audit's lead ("cylindrical reed"): with a cited
    closed cylinder, the first SHIPs with `CLOSED_REED_LEVELS` and the other is its sound-alike or
    waits. The audit's "Cromorne" is not a row, and the plan adds no alias for it. `organ oboe` is decided on its page. `vox
    humana` WAITs `a pitch and amplitude LFO (the tremulant)` only if its cited source makes the
    tremulant its sound; its fractional-length resonator is a trait the builds may not make (rule
    4), decided on its page.

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-13-form-check.py plans/data/instrument-audit/batch-13.tsv`
  and `uv run python -I build/batch-13-quote-check.py plans/data/instrument-audit/batch-13.tsv`.
  Expected: `29 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 3: Check the half.** Run batch 12's Task 2 Step 3 command with `batch-13` for
  `batch-12`. Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-13.tsv build/batch-13-half-a.tsv
git add plans/data/instrument-audit/batch-13.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 13's verification sheet, the organ stops" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The organ stops

**Files:**
- Modify: `organs.py` (new builds after the 9; `STOPPED_FLUTE_LEVELS`, `CLOSED_REED_LEVELS`,
  `compound_stop_levels` or `_pipe_stop`'s `chorus_cents`, each only if a row needs it),
  `organ_sound_alikes.py` (`ORGAN_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its source URL
  in a comment)
- Test: `tests/audio/test_instrument_catalog.py`; `tests/test_process_state_guard.py` (only if
  `CLOSED_REED_LEVELS` is added)

**Interfaces:**
- Consumes: `build/batch-13-half-a.tsv` (half A as committed), Task 1's tables and
  `build/batch-13-code-check.py`.
- Produces: `NEW_ORGAN_NAMES`, `ORGAN_SOUND_ALIKE_PARENTS`, `ORGAN_STOP_FOOTAGES` and
  `ORGAN_HELD_BACK` filled with this half's rows, which Task 5 extends; and, as rows need them,
  `STOPPED_FLUTE_LEVELS: Final[tuple[float, ...]]`, `CLOSED_REED_LEVELS: Final[tuple[float, ...]]`,
  `compound_stop_levels(levels: Sequence[float], footages: Sequence[float]) -> tuple[float, ...]`
  and `_pipe_stop(..., chorus_cents: float = 0.0)` in `organs.py`.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills only
`ORGAN_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_ORGAN_NAMES` with one name per SHIP row,
  `ORGAN_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row, `ORGAN_STOP_FOOTAGES`
  with one `name: footage` per one-rank SHIP or SOUND_ALIKE row whose footage is not 8 (the
  sheet's cell, `'16'`), and `ORGAN_HELD_BACK` with one `name: waits_for` per held row (every WAIT
  row whose reason is not `a sourced range`, and every `its target, <name>` row whose target is
  held), each in the sheet's order. Add the ALIAS rows to `test_the_batch_aliases_resolve`'s
  parameters, in the sheet's order, with a docstring sentence for batch 13. If a SHIP row builds
  with `STOPPED_FLUTE_LEVELS` or `CLOSED_REED_LEVELS`, add
  `test_a_stopped_or_closed_stop_sounds_odd_harmonics`: for the first SHIP row built with each
  table, and for `pipe organ flute` or `pipe organ reed` beside it, render the entry with its build
  (`footage` set to 8.0 through `build.func(*build.args, **{**build.keywords, 'footage': 8.0})`) at
  its `middle_note()`, take the spectrum's peaks at harmonics 1 to 4 as
  `test_a_cylindrical_chanter_sounds_odd_harmonics` does, and assert the odd table's harmonics 2
  and 4 are each below a bound and the open one's harmonic 2 above another, the bounds set from the
  measured values with room and the measurements written in the docstring, as batch 12's test
  writes "measured 0.815". If a SHIP row is compound, add
  `test_a_compound_stop_sums_its_ranks_as_harmonics` (the footage ruling's rule 4).

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or held_back or footage or odd_harmonics or compound or sound_their_note" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the held-back
  test passes.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in `ORGAN_SOUND_ALIKES`,
  in the sheet's order, under a section comment naming `plans/data/instrument-audit/batch-13.tsv`
  as `double_reed_sound_alikes.py`'s does, each a `CatalogEntry(name, title, Family.ORGANS,
  lowest, highest, sounds_like=parent)`, a stop at another footage than its parent with
  `sound_changes={'footage': <feet>}` (written `16.0`, or `8.0 / 3.0` for 2 2/3'). Above each, put
  a comment with its `sound_source`, `range_source` and `footage_source` URLs, the quoted passages
  and the derivations of the range and the footage. A SHIP row is a `CatalogEntry` after the 9 in
  `_ORGAN_BUILDS`, a `partial(_pipe_stop, ...)` (or the build its `builder` cell names) carrying the
  same comment and marking the values that are sound design and the entry they are copied from.
  Add a table, the compound helper or `chorus_cents` only if a row needs it, with the value and
  comment of the plan's ruling; `CLOSED_REED_LEVELS` gets its guard line (`CATALOG_SERIES`) in the
  `audio/instruments/organs.py` entry. Each ALIAS row goes in `aliases.py` under a "Batch 13's
  organs" section, in the sheet's order, with its URL and quote. Comments name only committed
  files.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range, the footage or the build. Check it against the source, and never trim
  the range to pass. Then run:
  `uv run python -I build/batch-13-code-check.py build/batch-13-half-a.tsv`
  Expected: `matches 29 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 13's organ stops, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The organs as instruments sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-13-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-13-pages/`
- Modify: `plans/data/instrument-audit/batch-13.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-13-form-check.py`,
  `build/batch-13-quote-check.py`, `build/batch-13-half-b.txt`; `new-mechanical-instruments.md`
  ("Moves", "Aliases", "Range checks"); `batch-2.tsv` (`band organ`, `hammond b3`,
  `telharmonium`), `batch-6.tsv` (`vox continental`, `telharmonium`), `batch-9.tsv`
  (`hydraulophone`).
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-13-half-b.txt`'s order, then one per alias name
(6), in the plan's order. A parent or alias target is a catalog name or a SHIP or SOUND_ALIKE row
of this half, never a half-A row. These rules apply on top of Task 2's:

- **Already decided.** `hammond b3`, `telharmonium`, `vox continental` and `hydraulophone` are
  DROP under rule 5, naming the sheet and status (above).
- **The boundary.** `reed organ` and `chromelodeon` (H-S 412.132 by the audit) are decided by the
  boundary ruling on their pages (free reeds; the chromelodeon may instead be a one-off).
  `lowrey organ`, `baldwin organ`, `compton electrone`, `choralcelo` and `farfisa` are decided by
  the boundary ruling and the maker's-name line; `farfisa` may be ALIAS of `combo organ` only on a
  cited page giving it as that instrument's name.
- **Early and small organs.** `regal` decides the instrument (its page: brass reeds in short
  resonators); `regal organ` (the audit's row titled "Bible regal") is ALIAS or DROP under rule 8,
  and `bible regal` is ALIAS of `regal` only on a cited page calling the bible regal the regal
  itself; a bible regal that its source sets apart (Praetorius's "harsh", if cited) is its own row
  under rule 7. A regal's cited short-resonator sound no organ build makes is `its own build (<the
  trait>)`. The regal's "common compass C/E-c'''" is hedged (range ruling 5) unless a museum
  record or another source states it. `portative organ` ("about nine notes": a hedged width) and
  `hydraulis` (no pitch by the audit) are decided on their pages. `chamber organ` is ALIAS of the
  catalog's `positive organ` only on a cited page giving the name to that instrument.
- **Self-playing organs.** `barrel organ`, `fairground organ`, `street organ`, `band organ` and
  `dance organ` follow the mechanical-organs and generic-term rulings: one row decides the
  fairground organ, the names a cited page gives it are ALIAS ("band organ is the US name", the
  audit's reading of the Fairground organ page), and a row whose source makes percussion part of it
  WAITs `more than four sources`. `carousel organ` and `limonaire` follow `fairground organ` (rule
  3); `limonaire` is a maker's name too. `serinette` ("one rank of ten metal pipes at 2' pitch": no
  range, range ruling 5) and `flute clock` are decided on their pages; `bird organ` and
  `perroquette` follow `serinette` (rule 3). `orchestrion`, `panharmonicon` and `apollonicon`
  follow the spec's "more than four sources | orchestrion" when their sources make the band part of
  the instrument; `panharmonicon` and `apollonicon` are ALIAS of `orchestrion` only on a cited page
  calling them that instrument. `componium` follows the one-off ruling. Every shipped self-playing
  row carries `tags` `mechanical`.
- **Steam, air and fire.** `air calliope` and `calliaphone` follow the calliope ruling. `pyrophone`
  is an organ (the spec) decided on its page; `fire organ` follows it (rule 3). `sea organ`,
  `beer bottle organ`, `bubble organ`, `uberorgan` and `sequential resonation machine` follow the
  one-off ruling, each on its page.

- [ ] **Step 1: Write half B's rows** to `build/batch-13-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-13-form-check.py build/batch-13-half-b.tsv` and
  `uv run python -I build/batch-13-quote-check.py build/batch-13-half-b.tsv`.
  Expected: `41 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-13-half-b.tsv >> plans/data/instrument-audit/batch-13.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `70 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 2 Step 3's command with
  `half_a | half_b` in place of `half_a` on its `missing:` and `twice:` lines, and print
  `'extra:', sorted(set(audit_names) - half_a - half_b)` in place of the half-B line.
  Expected: `missing: []` and `twice: []`. `extra:` lists only the 6 alias lines, because an alias
  row's `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-13.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 13's verification sheet, the organs as instruments (early, self-playing, steam, fire and electric)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The organs as instruments

**Files:**
- Modify: `organs.py`, `organ_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`; `tests/test_process_state_guard.py` (only if
  this task adds `CLOSED_REED_LEVELS`)

**Interfaces:**
- Consumes: `batch-13.tsv`'s half-B rows, Task 3's tables and helpers, and
  `build/batch-13-code-check.py`.
- Produces: the finished family.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `NEW_ORGAN_NAMES`,
  `ORGAN_SOUND_ALIKE_PARENTS`, `ORGAN_STOP_FOOTAGES`, `ORGAN_HELD_BACK` and the alias parameters,
  after half A's, as in Task 3 Step 1; fill `MECHANICAL_ORGAN_NAMES` with every shipped row tagged
  `mechanical` (half A has none), the builds then the sound-alikes, each in the sheet's order; and
  add a Task 3 test this half needs that Task 3 did not add.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command with `or mechanical`
  added to its `-k`.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes, aliases after half A's aliases, under a second
  section comment naming the sheet. A self-playing entry has `tags=frozenset({Tag.MECHANICAL})`,
  as the `music box` entry has it.

- [ ] **Step 4: Run the suite and check the code against the whole sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`, then
  `uv run python -I build/batch-13-code-check.py plans/data/instrument-audit/batch-13.tsv`.
  Expected: PASS, then `matches 70 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 13's organs as instruments (early, self-playing, steam, fire), each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add an organs
  paragraph with its count, naming `organs.py` and `organ_sound_alikes.py`, with examples, in the
  bagpipes paragraph's form, saying that a stop sounds at its footage against its keys and that a
  sound-alike stop at another footage carries it as `sound_changes`; and, if a self-playing organ
  shipped, name it beside the `music box` under `Tag.MECHANICAL`.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `organs` row's
  count and examples, the sound-alike modules sentence and its total, and the 8' sentence: "An
  organ's range is its keys at 8' pitch (C2-C7; a stop sounds at its footage, a 16' an octave
  lower, a 4' an octave higher)").
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 13
  done, pointing at this plan and `batch-13.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 13 DONE";
  - batch 13 done, with the sheet's counts by status and the family's growth, the module move
    (`organs.py`; `keyboards.py` keeping the keyboards and electromechanical instruments), the
    footage mechanism, any mechanical organ tagged, and the branch's base SHA (`5cbbf882`);
  - the audit's unclosed gaps, as a later pass;
  - the hand-offs: `vox humana`, `voix celeste`, `serinette`, `flute clock`, `kinura` and `band
    organ` decided here; `dulciana` and `gemshorn` left as earlier sheets decided them;
    `orchestrion` and `reed organ` decided here (so the keyboards and free reeds batches must not
    decide them again); `orchestrelle` for the free reeds batch; each electric organ dropped to
    electronic or electromechanical for a later pass of those families; and any name the sheets
    found that belongs to the clarinets batch;
  - a "Plan (batch 13)" line, the Status line, and the next batch named: clarinets.

  Add #83 (the highest item is #82), "Sound Engine: The Owner's Checks on Instrument Catalog Batch
  13 — TODO". Use #82's form (as #75 began it), place it directly after #82, and give it the
  Priority "(before the clarinets batch builds on the same catalog)". Its **Listen** section
  (`build/instruments/organs/`) covers the new builds, then the sound-alikes beside their parents
  (the stops at another footage named, with their footages), then the aliases. Its **Calls to
  confirm** are:
  - every WAIT, by reason, with names;
  - the stop-or-setting ruling (a stop an entry, a registration, the tremulant, couplers and the
    swell a setting);
  - the footage ruling (a stop sounds at its footage against its keys; footage is pitch, so a
    footage difference is a sound-alike's change, never a SHIP; `blown`'s `semitones` and
    `_pipe_stop`'s `footage`; compound stops as one wave; mixtures with breaks under "more than four
    sources" though the blocker is the breaks; and whether a stop may sound above C8 when its keys
    do not, which made the high mutations and 2' stops wait);
  - the range ruling (keys at 8' pitch with the stop's footage, the division's standard compass as
    the stop's own, a keyless organ's sounding notes, never hedged, a width, a count, a footage
    alone or a key, the museum, maker and organ-reference sources over uncited Wikipedia lines,
    nothing below A0 or above C8, one-note instruments, cited Wikipedia lines whose citation
    supports them), and every derived range and footage;
  - the parent ruling (a stop's parent an organ stop, chosen by the stop's family);
  - `STOPPED_FLUTE_LEVELS`, `CLOSED_REED_LEVELS`, `compound_stop_levels` and `chorus_cents` if
    added, each with the trait its source names;
  - the celeste ruling (one rank a setting's beating, two ranks only with a sourced detune) and the
    new wait names `a sourced footage` and `a sourced detune`;
  - the mechanical organs (`Tag.MECHANICAL`, sounding ranges, percussion as more than four
    sources);
  - the calliope ruling (air and steam, the steam pitch drift);
  - the boundary (free-reed organs, electric organs, makers' names, the pyrophone and hydraulis
    as organs);
  - generic and ambiguous terms dropped (`dulciana`, `gemshorn`, `barrel organ` and the rest, as
    decided);
  - one-offs, reconstructions and unsourced rows, and the in-production line;
  - the module move, and the process-state guard's three lines moving with the tables;
  - `ORGAN_HELD_BACK`, the guard for every non-range wait;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): the 9 earlier entries' missing
  source comments (`combo organ` is already in #76); any existing range or build a sheet's source
  contradicts (`calliope`'s C3-G5, `positive organ`'s C2-C6, `pipe organ plenum`'s drawbars,
  `theatre organ (tibia)`'s static chorus, as the sheets find them). Then **Follow-ups**: the
  audit's gaps; ranging the range WAITs from museum, maker and organ-reference sources; checking the
  9 earlier entries against sources; the engine changes that unblock the waits, most rows first.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries())); print(i.names(tag='mechanical'))"`
  and `uv run python -I build/batch-13-form-check.py plans/data/instrument-audit/batch-13.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-13-code-check.py plans/data/instrument-audit/batch-13.tsv
uv run python -I build/batch-13-quote-check.py plans/data/instrument-audit/batch-13.tsv
```
  Expected: everything passes with no warnings (a warning is a finding; #81 records the
  third-party `speech_recognition` DeprecationWarning under `-W error`, so a new one is a new
  finding), `matches 70 rows`, and `bad: []`. The `build/instruments/organs` folder is the one to
  listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 13 of the instrument catalog (organs), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch in
turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78). The
pre-push hooks take about 40 minutes, and nothing in the working tree may change while they run.

**Order:** the controller's shared files, then Tasks 1, 2 and 4 in parallel. Task 3 follows Tasks
1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows Tasks 3 and 4, and Task 6 comes
last.
