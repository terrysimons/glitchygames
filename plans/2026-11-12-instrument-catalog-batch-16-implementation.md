# Instrument catalog batch 16 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the free reeds family from the audits' candidates. The family holds the instruments
whose sound is a free reed, a tongue swinging through a closely fitting slot (Hornbostel–Sachs
412.13), and the free-reed pipes whose finger holes set the pitch (422.3): the bellows-blown
accordions, concertinas, harmoniums and reed organs, and the mouth-blown harmonicas, melodicas,
pipe mouth organs (sheng, sho, khaen and their kin) and reed pipes (bawu, hulusi). Each
instrument gets a cited source for its name, its sound, how it is blown, its range and (where it
has them) its drones, its reed sets' detune or its octave reeds, and either sounds unlike every
other entry or is a listed sound-alike of the one it sounds like. The rest become aliases, wait for
an engine feature or a source, or are dropped with a reason.

**Architecture:** As in batches 3 to 15, a verification sheet (`batch-16.tsv`) decides every
candidate before any code is written. The family's 13 entries live in `winds.py` (241 lines),
which also holds the 8 saxophones; batch 14 already moved the clarinets out the same way. So the
free reeds section moves unchanged to a new `free_reeds.py`, and `winds.py` keeps the saxophones:
the moved table becomes `_FREE_REED_BUILDS`, and `FREE_REEDS` becomes `_FREE_REED_BUILDS +
FREE_REED_SOUND_ALIKES`, with the sound-alikes in a new `free_reed_sound_alikes.py`. The catalog's
free reed builders (`_accordion` for bellows-blown reeds, `_mouth_reed` for mouth-blown reed
plates; `sheng` is built with `_accordion`) already make a free reed's buzzing harmonic series and
a second reed set detuned against the first, so a new free reed with no other cited trait is a
sound-alike. Three sourced traits change a sound-alike's sound through `sound_changes` (a reed
set's detune in cents, an octave reed set, a drone's notes), and one trait no catalog free reed
has makes a SHIP: fixed drones under every note (a new `_droned_reed`, as the bagpipes build
theirs). A self-playing free reed carries `Tag.MECHANICAL`. A new guard, `FREE_REED_HELD_BACK`,
holds every name the sheet holds back for any reason but a sourced range. The sheet and the code
each come in two halves, as explicit lists: the bellows-blown free reeds, then the mouth-blown
ones. The controller writes the names file, the candidate lists and the three check scripts
before anything is dispatched, so the two sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `with_drones`,
`wave_from_levels`, `falling_series`; `audio/instruments/organs.py`: `compound_stop_levels`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all, and 7 for `Tag.MECHANICAL`). Batch 15's plan
(`plans/2026-11-12-instrument-catalog-batch-15-implementation.md`) and its owner's checks
(`plans/future-features.md` #85) are this plan's template and its ledger: its controller step, its
quote check, its held-back guard, its two parallel halves and its code check carry over, with the
corrections listed at the end of this plan. Batch 12's plan holds the drone rule (a drone sounds
at its sourced note under every note, `with_drones`, and a drone whose notes no source states
waits for `a sourced drone tuning`); batch 14's holds the drone and detune guards and the module
move this plan repeats; batch 13's holds the footage arithmetic (`compound_stop_levels`) and the
mechanical tag rule; batch 11's holds the balaban rule (a cited trait the build cannot make means
the row waits); batch 4's (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) holds
the pitched sound-alike and strict range rules and the before-and-after build record. This plan's
own path is `plans/2026-11-12-instrument-catalog-batch-16-implementation.md`. The branch is
`feat/instrument-catalog-batch-16`, made from batch 15's tip, `d4c1e3eb` (the merge of
`feat/instrument-catalog-batch-14` into `feat/instrument-catalog-batch-15`, after batch 15's final
review fixes `8173b3ec`); Task 6 records that SHA in #70. The candidates come from
`plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `free reed` (32, every one from the round-2 audit
  `free-reeds.md`);
- the `round-1/merged-missing.tsv` rows whose `family` contains `free reed` (9: `hulusi`, `bawu`,
  `pitch pipe`, `khene`, `sho`, `saenghwang`, `lusheng`, `jaw harp` with family "free reeds", and
  `chromelodeon` with "organs (or free reeds)");
- the mechanical-instruments audit's `orchestrelle` row (`merged.tsv`, `audit_file`
  `new_mechanical_instruments.md`, whose family is a tag: "roll-playing pressure reed organ ...
  free reed, not pipe"). #70 says "`orchestrelle` is the free reeds batch's", as batch 15 took the
  piano rows from the same audit. The audit's other mechanical rows are other families'.

Together: 42 unique names, none of them a catalog name or alias (checked for this plan at
`d4c1e3eb`: the catalog holds 704 entries and 121 aliases, 825 names, and no free reed alias at
all). So there are **42 candidate names** (counted for this plan, the controller recounts). The
audits' alias lines that name a free reed candidate, or a free reed the catalog holds, propose
**25 alias names** that are not candidates, all from `free-reeds.md`'s "Aliases" (no other audit
has an alias line naming a free reed; checked with grep):
- "kaen / khaen / kehn / ken / kheng -> khene (proposed)" (5); "bayan -> chromatic button
  accordion"; "melodeon (button) -> diatonic button accordion" (`melodeon`); "garmoshka / khromka
  -> garmon" (2); "trikiti / eskusoinu txiki -> trikitixa" (2); "pianica, triola -> soprano
  melodica (catalog)" (2); "claviola -> melodica family (listed on Wikipedia free reed template
  only)"; "goofus, queenophone -> couesnophone" (2); "accordina -> melodica-like button instrument
  (Wikipedia melodica page); listed as alias, not catalogued"; "richter harmonica -> harmonica
  (catalog)"; "piano accordion -> accordion (catalog)"; "peti / samvadini -> indian harmonium"
  (2); "keledi / enkulurai / kadedek -> keluri; engkerurai -> keluri" (4).
"standard sheng range -> catalog sheng (unspecified size)" names no instrument and is not a row.
The round-1 alias tables are not used, as no earlier batch used them. So the sheet will hold
**67 rows**. An alias row's `audit_name` is its audit line as written above (its URL left out).

The hand-offs from earlier sheets (checked: `batch-1.tsv` to `batch-15.tsv`, and
`plans/future-features.md` #70–#85):
- `chromelodeon`: `batch-13.tsv` DROP, "belongs to free reeds (H-S 412.132): pump organs retuned
  by Partch", listed in #70 for this batch ("`chromelodeon` is dropped to free reeds"). A half-A
  candidate, decided here.
- `orchestrelle`: #70, "`orchestrelle` is the free reeds batch's". A half-A candidate, decided
  here.
- `reed organ`: `batch-13.tsv` DROP, "belongs to free reeds (H-S 412.132): an organ that uses
  free reeds" (that row: "this sheet decides the name, #70", and the harmonium question "is the
  free reeds batch's to decide"). A half-A candidate, decided here, by the controller's ruling (the
  reed organ ruling, below).
- Already decided, and a candidate: its row is DROP, its notes beginning "Already decided:" and
  naming the earliest sheet that decided it and its status: half B's `jaw harp` (`batch-1.tsv`
  WAIT, plucked idiophones, "moving formants (the mouth cavity sweeps the overtones)";
  `batch-5.tsv` also dropped it, and the earliest sheet is the one named). It was never a catalog
  name or alias, so the code check's "Already decided" branch does not apply to it (it takes the
  last branch).
- Already decided, not candidates, no row: `orchestrion` (`batch-13.tsv` WAIT) and
  `panharmonicon` (`batch-13.tsv` WAIT; `batch-15.tsv` dropped it as already decided); `regal` and
  `bible regal` (`batch-13.tsv` WAITs, organs: beating reeds); `pey pok`, `tarpa` and `pungi`
  (`batch-14.tsv` WAITs, clarinets: "their free reed being unsourced"); `sneng` (`batch-10.tsv`
  WAIT, brass; #80: "the page's commoner side-blown sneng is a free reed (422.33), which belongs
  to the free reeds and is decided nowhere"). The side-blown sneng is a lead for a later pass
  (Task 6 lists it in #70); this batch adds no row for it, since no audit names it as a free reed
  candidate and the name `sneng` is batch 10's.
- #85 says "No row was dropped to struck strings, harps, free reeds or electromechanical", and
  #76–#84 hand nothing here beyond the lines above.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`; the one-letter `u` matches). Accents, macrons, apostrophes and hyphens go only in the
  title (`sho` titled "Shō", `free bass accordion` titled "Free-bass accordion"). A candidate keeps
  its audit name (the naming ruling of batch 12): the row for the Khaen page's instrument is
  `khene`, and `khaen` is decided as its alias name.
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families),
  "with the existing player-facing splits kept where they already exist (keyboards and organs …)".
  The free reeds family holds the instruments a free reed sounds (412.13) and the free-reed pipes
  (422.3). The boundary rulings below decide each row.
- Hornbostel–Sachs, every code this plan relies on checked against Wikipedia's raw wikitext on
  2026-11-13 (`List_of_aerophones_by_Hornbostel–Sachs_number` and `Hornbostel–Sachs`):
  - 412.13: "Free-reed instruments feature a reed which vibrates within a closely fitting slot
    (there may be an attached pipe, but it should only vibrate in sympathy with the reed, and not
    have an effect on the pitch - instruments of this class can be distinguished from 422.3 by the
    lack of finger-holes)". 412.131 "Individual free reeds" (the list names the Bawu, the Party
    horn and the Pitch pipe); 412.132 "Sets of free reeds" (the list names the Accordina,
    Accordion, Bandoneon, Concertina, Harmoneon, Harmonica, Harmonium, Melodica, Reed organ,
    Sheng, Martinshorn and others; the main page adds "Accordion, harmonica, and reed pipes of the
    pipe organ"). The Accordion, Concertina, Harmonica, Melodica, Pump organ, Sheng and Shruti box
    infoboxes give 412.132.
  - 422.3 "Reedpipes with free reeds - The reed vibrates through [at] a closely fitted frame.
    There must be fingerholes, otherwise the instrument belongs to the free reeds 412.13."; 422.31
    "Single pipes with free reed"; 422.32 "Double pipes with free reeds".
  - 412.12 "Percussion reeds - A single lamella strikes against a frame" (412.122 "Sets of
    percussion reeds. - Earlier organs"): the beating reeds, not free reeds.
  - Three traps, found while writing this plan. The list files the Bawu under 412.131 although its
    page gives it "Seven or eight finger-holes" and the 422.3 text sends a fingered free reed there:
    the class text decides, and a bawu is 422.31. The Shō infobox gives "441.21", which is no
    Hornbostel–Sachs class (the aerophones are 41 and 42 only): a sho row's `hs` is written from its
    quoted words. The Bawu and Hulusi pages give no code. The round-1 audit's "sho 441.21" and "bawu
    412.131" are leads, not codes.
  - Suffixes: "An 8 indicates that the instrument has a keyboard attached, while a 9 indicates the
    instrument is mechanically driven" (the main page). Any other suffix is written only from a
    quoted source that names it.
  A worker who finds a code that a fetched list does not hold reports it to the controller before
  any row relies on it. No other code is assumed.
- "Every name, range and description checked against a source cited in the code … A range that no
  source gives is the instrument's documented playable span from a maker or museum, or the entry
  waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict"). This plan's
  range ruling is below. A row with no sourced range is WAIT, `waits_for` `a sourced range`, and
  **the range is checked first**, before any engine limit or other trait (batch 13's reversals): a
  row with neither a range nor a buildable trait waits for the range, its notes keeping "Engine
  limit, once ranged: …".
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry, sharing
  the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the same
  instrument) stays an alias." "So `sound_changes` (keyword overrides of the parent's builder,
  empty by default) lets a sound-alike differ by a sourced trait." A sound-alike is pitched exactly
  when its parent is, and a pitched sound-alike gives its own sourced range (batch 4). The only
  `sound_changes` this batch may carry are `cents` (the detune ruling), `footages` (the reed-set
  ruling) and `drones` (the drone ruling), each from a sourced number.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as an
  approximation, under its real name or a qualified one. The spec's table binds this family through
  "more than four sources | orchestrion, violano-virtuoso, large mixtures" and "sub-audio
  fundamentals". Earlier batches added the other names a WAIT may give: a pitch LFO (vibrato), a
  pitch LFO (portamento between notes), an amplitude LFO, a pitch and amplitude LFO (batch 2),
  filter resonance, a filter envelope, moving formants (batch 6); a buzzing membrane (batch 5); a
  sourced drone tuning and its own build (batch 7, 12); a range above C8 (batch 10); a sourced
  detune and a sourced footage (batch 13); a sourced reed and bore (batch 14); a sourced partial
  series (batch 15). This plan adds no new wait name; `its own build (<the trait>)` names any trait
  no builder makes. What the engine has: up to four `Source`s, each with its own semitones, detune
  and fixed pitch; `blown` (one harmonic series, an optional chorus copy detuned sharp by
  `chorus_cents`, a bite, a breath noise, a fixed low or high pass, drive); `with_drones` (a
  chanter's tone and breath kept, at most two drones with breath); `compound_stop_levels` (ranks
  at 8' and 4' summed into one series); one glide per note (`pitch_curve`); no LFO of any kind,
  and a harmonic series that does not change with the note.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not builds.
- Reuse the family's builders under their current names: `_accordion(*, cents, low_pass)` and
  `_mouth_reed(*, low_pass, breath=0.03)`, with `FREE_REED_LEVELS`. Each entry's build is an
  inline `partial(...)`. Add a builder or keyword only for a genuinely new, sourced sound
  (`_droned_reed`, `_mouth_reed`'s `cents`, the `footages` keyword, below), and give it its own
  test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the sheet,
  in every row of every status, is verbatim from a page the worker fetched and saved, or from a
  committed file the notes name (an earlier sheet, an audit file, #70 or the spec), and the quote
  check finds each one (Step 4 below). No request carries the owner's email or any personal data,
  in a header, a URL or a payload (#78, "Incidents and process").
- Sources: an unsaved WebFetch read is a lead, never a source (#85's `nickelodeon`): every cited
  page is saved raw with curl (for Wikipedia, the `action=raw` wikitext). A page that refuses curl
  (403, 429) is fetched from the Internet Archive's copy (`https://web.archive.org/web/<date>id_/<url>`,
  the `id_` form returns the page as archived), saved, and cited by its archive URL. Uncited lines
  (range ruling 10), blogs, forums, retailers' listings and hobbyists' pages are not sources; a
  scholarly article (a journal paper, a conference paper, a museum's or university's publication)
  is.
- Code comments name committed files (`plans/data/instrument-audit/batch-16.tsv`), never the
  gitignored `build/` files (batch 9's fix).
- Data is never evaluated as code: a check script reads a literal with `ast.literal_eval`, never
  `eval` or `exec`.
- The 13 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 13. An existing entry changes only for a cited bug, and not in this batch:
  the 13 carry no source comment, so a range or build that a fetched source contradicts is reported
  in #86 for the owner, not changed here (batches 10 to 15's rule). Leads already seen while
  writing this plan, for the workers who fetch those pages to check under range ruling 10: the
  Sheng page gives the soprano sheng "a soprano range of G3 to F#6" against the catalog's `sheng`
  G3–A6 (the audit: "standard sheng range -> catalog sheng (unspecified size)"); the Melodica
  infobox gives "Usually 2 or 3 octaves" (a hedged width, no range); the catalog's `concertina` is
  titled "English concertina". Task 1's before-and-after record of every entry checks that the
  move changes nothing, and Tasks 3 and 5 repeat it for the 704 earlier entries after adding a
  keyword.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns, a module docstring's first line included: batch 14's first line
  was 123 columns), basedpyright and ty clean, 100% coverage. "I don't like short abbreviated
  variables." "explicit is better than implicit." "Whenever you see warnings thrown by a test, you
  should understand why it's happening and be concerned": a warning is a finding, and it must be
  understood before going on. #85 records 17 DeprecationWarnings under `-W default` from the
  third-party `speech_recognition` (it imports `aifc`), filtered on purpose in `pyproject.toml`; a
  report says "the 17 known speech_recognition warnings, no other" when that is what it saw, never
  "no warnings".
- Commits as batches 4 to 15: `SKIP=replay-metrics git commit`, with the subject `Plans: …`,
  `Instrument catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this plan,
  never from memory. Write no `.md` file beyond those Task 6 names. Never use `git stash`: the
  stack is shared with other worktrees and sessions (#80, "Incidents and process"). Set work aside
  with a temporary commit instead.

## Review Focus

1. **A key, a hole or reed count, or a scale read as a range.** Free reed pages give "Diatonic
   harmonica in C", "10 holes", "37 treble keys", "36-reed", "seven tones per octave", "A minor
   scale", the saenghwang's "from hwangjong (黃: E♭) to cheongnam-ryo (湳: C)" (pitch names with no
   octave), the bawu's "typically has a range of an eleventh ... from B to E" and the Melodica
   infobox's "Usually 2 or 3 octaves". Range ruling 5 makes none of them a range, the form check
   needs `Range:` with a quoted passage the quote check finds on the saved page, and the code check
   compares every shipped range with the sheet.
2. **A model's or one size's range given to the bare name.** Makers sell harmonicas, melodicas and
   accordions in many models and keys, and the sheng in four sizes (one with two ranges: "G2 to
   F♯5 or F2 to E5"). Range ruling 4 ranges a model's row from its maker's model page only, and
   ruling 6 makes a bare name with several sizes and none called standard wait; the form check's
   `Range:` passage and the reviewers check the source names the row's instrument, not a model.
3. **A free-reed pipe or a beating reed built as a reed plate.** The bawu and hulusi melody pipe
   sound through a pipe whose length "not the reed's own frequency, sets the pitch, unlike in the
   accordion or harmonica" (the Hulusi page); the regal and the clarinets' pey pok are beating
   reeds. The reed pipe ruling lets a 422.3 row be a sound-alike only by the parent ruling's rule 1
   (the form check asks for "Parent (rule 1):" on any `422.3` row), and the boundary ruling drops a
   beating reed. No harmonica sound-alike is made of a bawu by the nearest-lowest-note rule.
4. **A drone, a detune or an octave reed set shipped from an unsourced or player-chosen number,
   or a guard that passes only because its table is empty.** "Slightly sharp", "wet", "musette",
   a khaen drone the player picks per mode and an accordion register switched by the player are no
   numbers. The drone, detune and reed-set rulings need the number quoted after `Drones:`,
   `Detune:` or `Reeds:`, which the quote check finds; the 2% rule refuses a detune a hair from the
   parent's; and Task 1 tests every guard's helper on a real build (`musette accordion`'s 15-cent
   chorus, `highland bagpipe`'s two drones, `harmonica`'s tone wave, a real catalog name and alias
   for the held-back check), as batch 15's final review found its guards untested
   (`8173b3ec`).
5. **A name decided twice.** `jaw harp` (`batch-1.tsv`) is already decided, and `orchestrion`
   (#70: "must not decide them again") is no row; `khene` and its five
   spellings, `pitch pipe` and `chromatic pitch pipe`, `trikitixa` and `trikiti`, and the sheng
   sizes and `sheng` are each decided once. Rule 8 decides duplicates, the code check finds every
   name exactly once, and `test_no_new_build_is_another_entrys_instrument` refuses a new build equal
   to an existing one.

---

## File Structure

- Create `src/glitchygames/audio/instruments/free_reeds.py`. It takes the "Free reeds" section of
  `winds.py` (its header comment, `FREE_REED_LEVELS`, `_accordion`, `_mouth_reed` and the
  `FREE_REEDS` table, renamed `_FREE_REED_BUILDS`), unchanged.
- Create `src/glitchygames/audio/instruments/free_reed_sound_alikes.py`, holding
  `FREE_REED_SOUND_ALIKES`.
- Modify `src/glitchygames/audio/instruments/winds.py`: it keeps the "Saxophones" section only.
- Modify `registry.py` (it imports `SAXOPHONES` from `winds.py` and `FREE_REEDS` from
  `free_reeds.py`; their places in `FAMILY_TABLES` don't change), the docstrings that name
  `winds.py` as the free reeds' home (`__init__.py` lines 102, 113 and 124; `bagpipes.py` line 9;
  `clarinets.py` lines 8–9; `double_reeds.py` line 6; `flutes.py` line 8), and `aliases.py` (the
  batch's ALIAS rows).
- Modify `tests/test_process_state_guard.py`: its listing `'audio/instruments/winds.py':
  {'FREE_REED_LEVELS': CATALOG_SERIES}` moves to `'audio/instruments/free_reeds.py'`, between the
  `flutes.py` and `organs.py` listings (the keys are in path order). The guard fails on a listing
  the scan no longer finds, so this moves with the code.
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5).
- Create `plans/data/instrument-audit/batch-16.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #86), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #86):

- **The free reeds get their own module, and `winds.py` keeps the saxophones.** Every family a
  batch has grown since batch 4 has a module of its own and a sibling sound-alikes module that
  names it. The free reeds section is self-contained: only `registry.py` imports `FREE_REEDS`
  (checked with grep), no other module imports `_accordion`, `_mouth_reed` or `FREE_REED_LEVELS`,
  and the process-state guard lists `FREE_REED_LEVELS` under `winds.py`, which moves with it.
  `winds.py` is not renamed (the saxophones batch may decide that; #86 asks). The docstring
  sentence "folk instruments' are typical of the common keys", which #84 reported as unsourced,
  stays verbatim in both modules: removing it is the owner's call (#84 parked it). Task 1's
  before-and-after record of all 704 builds checks the move.
- **The boundary rulings.** A row's family is decided by what sounds and how, from its fetched
  source's words, with the Hornbostel–Sachs class those words imply:
  1. *Free reeds*: a reed swinging through a closely fitting slot, sounded by bellows (the
     accordions, concertinas, bandoneons, the harmonium and reed organ, the shruti box) or by the
     mouth (harmonicas, melodicas, pitch pipes, the pipe mouth organs), with or without keys
     (412.131, 412.132; -8 with a keyboard, -9 mechanically driven).
  2. *Free-reed pipes*: a free reed in a pipe with finger holes, the pipe setting the pitch (the
     bawu; the hulusi's melody pipe), are this family's (422.31, 422.32), under the reed pipe
     ruling.
  3. *The harmonium is free reeds*: the catalog's `harmonium` is already a free reed entry, and
     `batch-13.tsv` sent the reed organ and the chromelodeon here; the harmonium's kin (the Indian
     harmonium, the physharmonica, the orchestrelle, the shruti box) are decided here.
  4. *The pipe organ's reed stops are organs*: a reed stop of a pipe organ, beating or free, stays
     with the organs (the spec keeps the organs' player-facing split, and batch 13 decided the
     catalog's reed stops), whatever 412.132's "reed pipes of the pipe organ" says. A row whose
     source makes it a pipe organ stop is DROP "belongs to organs (a stop of the pipe organ): <its
     words>", listed in #70.
  5. *A beating reed is not a free reed*: a reed that strikes its frame (412.12; the regal, "beating
     reeds"), a clarinet's single reed (422.2) or a double reed (422.1) is DROP "belongs to <the
     family> (a beating reed, H-S <class>): <its words>", listed in #70 for that family's later
     pass.
  6. *Drones*: a mouth organ with drones (the hulusi's drone pipes, the khaen's drones) is a drone
     build as in the bagpipes, under the drone ruling; a bagpipe whose chanter is a free reed would
     be this family's too (none is a candidate).
  7. *Electric and electronic*: a reed read electrically (the Pianet's and Wurlitzer's reeds, H-S
     51 and 52) is electromechanical, a circuit's sound (53) electronic; both batches are done, so
     the row is DROP "belongs to electromechanical" or "belongs to electronic", listed in #70 for a
     later pass.
  8. *Jaw harps*: a lamella plucked by the finger with the mouth as resonator is a plucked
     idiophone (121.2; batch 1 decided `jaw harp`), even when a page groups it with the free reeds.
  9. *The `hs` cell* holds the class a fetched source gives (an infobox, or a sentence naming what
     sounds and how, quoted, with the code it implies, written from the classes and suffixes
     above), else `none`. A SHIP or SOUND_ALIKE row's `hs` fullmatches
     `(412\.13[12]|422\.3[12])(-[0-9]+)*`.
- **A free reed is a sound-alike unless a cited trait sets it apart.** The catalog's free reed
  builds are `_accordion` (a free reed series with a second reed set detuned sharp by `cents`, a
  little breath, a low pass) and `_mouth_reed` (the same series, more breath, drive, no second
  set). A row whose sources name no other trait is a SOUND_ALIKE (the parent ruling). A button or
  keyboard layout, bisonoric or unisonoric action (push and pull sounding other notes or the same),
  a Stradella, free-bass or converter left hand, a register switch the player works, a cassotto, a
  key ("in C", "in G"), a tuning or scale (Richter, solo, just or equal temperament, the shruti),
  a chord or cluster the instrument sounds (the chord harmonica's chords, the sho's *aitake*: the
  notes a sequence asks for with `chord=`), a size, a material (brass, bamboo, silver reeds), a
  maker, a roll or barrel mechanism, or a colour word ("bright", "reedy", "mellow", "warm",
  "plaintive") is no trait (rule 7), unless a fetched source names an effect on the sound with the
  numbers a builder takes. A trait the engine can make with sourced numbers is a sound change under
  the detune, reed-set and drone rulings, or a SHIP (fixed drones, which no catalog free reed has).
  A trait it cannot make (a spectrum that changes with the note, as the Bawu page's "As successively
  higher notes are fingered, the upper harmonics are gradually extinguished"; a reed's bend; a
  tremolo by the player's hand; three or more detuned reed sets; a 16' or 2' reed set) is WAIT
  `its own build (<the trait>)` or the spec's or an earlier batch's feature name, with the source
  quoted. A trait `_accordion` or `_mouth_reed` could imitate by turning an unsourced keyword (a
  darker `low_pass`, more `breath`, a wider `cents`) is not made by the build: batch 11's
  contraforte and the balaban rule.
- **The parent ruling.** A SOUND_ALIKE's parent is a catalog entry from before the batch (never a
  sound-alike) or a SHIP row of its half, never one of `APPROXIMATING_NAMES`:
  1. The entry its own source relates it to ("a type of accordion", "a smaller harmonium", "derived
     from the sheng", "a German concertina system"), quoted in the notes after "Parent (rule 1):".
     Only this rule may name another family's entry, and only this rule may parent a 422.3 reed
     pipe (the reed pipe ruling). `musette accordion` (a colouring) and `accordion bass` (the
     accordion's left hand) are parents only by rule 1.
  2. Otherwise the free reed entry of the same mechanism whose `lowest` note is nearest the row's
     own lowest note in semitones, the earlier catalog entry on a tie, written after "Parent (rule
     2):" with the mechanism and the semitone counts. The mechanisms: bellows-blown reed sets
     (`accordion`, `bandoneon`, `concertina`, `harmonium`); mouth-blown reed plates in a comb or a
     case (`harmonica`, `chromatic harmonica`, `bass harmonica`, `soprano melodica`, `alto
     melodica`, `bass melodica`); mouth-blown pipes, each with its own reed, in a wind chest
     (`sheng` alone, whatever its lowest note).
  3. A sound-alike's drones equal its parent's (none for a catalog parent), unless it carries its
     own sourced drones as `sound_changes` (the drone ruling).
  4. The sizes or models of one type share the type's parent, or are sound-alikes of the type when
     it is a SHIP row: never a sound-alike's sound-alike. The sheng sizes' parent is `sheng`, by
     rule 1 when their page relates them to it, else by rule 2's third mechanism.
- **The detune ruling** (batch 13's and 14's sourced detune). Two reed sets tuned apart beat; the
  catalog builds one detuned set as `blown`'s chorus copy, `cents` sharp. So:
  1. A row whose source states the detune between its reed sets in cents, or in beats per second
     at a stated note (converted: cents = 1200 × log2((hertz + beats) / hertz), the arithmetic
     shown), quoted after `Detune:` in the notes, is a SOUND_ALIKE with `sound_changes={'cents':
     <the number>}`. "Slightly", "wet", "dry", "musette", a range of cents or a hedge is no number,
     and the row is a sound-alike unchanged (or waits, if its source makes the beating the
     instrument's sound and gives no number: WAIT `a sourced detune`).
  2. A detune within 2% of its parent's `cents` is no trait (a 1–2% numeric difference is not a
     trait): the row is a sound-alike unchanged. The catalog's own `cents` (accordion 1.0, musette
     15.0, bandoneon 3.0, concertina 1.0, harmonium 2.0, sheng 4.0) are sound design, as built.
  3. Two detuned sets beside the main one (a three-voice musette: one flat, one sharp) are more
     than the chorus copy: WAIT `its own build (two detuned reed sets)`.
  4. `_mouth_reed` has no `cents` today. The first code task whose row needs it adds `cents: float
     = 0.0`, passed to `blown` as `chorus_cents` (0 adds no chorus, so no existing build changes).
- **The reed-set ruling** (batch 13's footage arithmetic). A reed set an octave above the note
  sounds the note's even harmonics louder. So:
  1. A row whose source states a fixed reed set an octave above its unison set (an octave
     harmonica's "two reeds per note an octave apart", if its source says so), quoted after
     `Reeds:`, is a SOUND_ALIKE with `sound_changes={'footages': (8.0, 4.0)}`. A register the player
     switches is no trait (the techniques ruling). A 16' set (an octave below), a 2' set or a fifth
     is WAIT `its own build (<the reed set>)`.
  2. The row's range is its unison set's; its highest note plus 12 semitones must lie at or below
     C8, else WAIT `a range above C8`.
  3. The first code task whose row needs it adds `footages: tuple[float, ...] = (8.0,)` to the
     parent's builder (`_accordion` or `_mouth_reed`): when `footages != (8.0,)`, the levels are
     `compound_stop_levels(FREE_REED_LEVELS[:16], footages)` (the first 16 levels, so a 4' set
     reaches harmonic 32, `HIGHEST_HARMONIC`), imported from `organs.py`; `(8.0,)` keeps
     `FREE_REED_LEVELS` untouched, so no existing build changes. The cut to 16 levels is sound
     design, marked so.
- **The drone ruling** (batch 12's, for a mouth organ). A drone is a pipe or reed sounding a fixed
  note under every note:
  1. The `drones` cell names the drone notes as a fetched source gives them for this instrument
     (note names with octaves, or a stated interval from a stated note with its octave), highest
     first, at most two; `drone_source` holds the URL, and `notes` quote them after `Drones:` with
     the derivation. A row with no drones has `drones` `none` and needs no source or passage.
  2. A drone whose notes the player chooses (a khaen player holding pipes for a mode, an Indian
     harmonium's drone stops) or that no source states is no drone tuning: WAIT `a sourced drone
     tuning`, once ranged, when the source makes the drone part of the instrument's sound; a drone
     stop the player works is no trait.
  3. A ranged row with sourced drones whose parent mechanism has no drones is a SHIP:
     `_droned_reed(low_pass=<copied>, drones=((<hertz>, 0.3), ...))`, the `low_pass` copied from
     the parent ruling's rule-2 entry (sound design, named), the drones at equal temperament
     (A4 = 440 Hz, two decimals, as the catalog writes hertz). A droned row of another droned SHIP
     row's type is its sound-alike, with `sound_changes={'drones': ...}` when its sourced drones
     differ.
  4. The first code task that ships one adds, in `free_reeds.py`, `_droned_reed(*, low_pass:
     float, drones: tuple[tuple[float, float], ...]) -> Instrument`, returning
     `with_drones(_mouth_reed(low_pass=low_pass), drones=drones,
     drone_wave=wave_from_levels(FREE_REED_LEVELS))`: the chanter is the catalog's mouth-blown
     reed (its tone and breath kept, at most two drones), and the drone level 0.3 is sound design,
     copied from the `uilleann pipes`' bass drone (`bagpipes.py`), marked so. That task lists the
     entry in `FREE_REED_DRONES` and in `NOT_PERIODIC_AT_THE_NOTE` ("drones at <notes> under every
     note").
- **The reed pipe ruling.** A free reed with finger holes sounds through its pipe (422.3): "One
  acoustic study describes copper free reeds, in which pipe length, not the reed's own frequency,
  sets the pitch, unlike in the accordion or harmonica" (the Hulusi page, to be checked under range
  ruling 10 by the worker who fetches it). No catalog build models it. So a 422.3 row is a
  sound-alike only of an entry its source relates it to (rule 1); otherwise, once ranged, it WAITs
  `its own build (a free reed sounding a fingered pipe)`. A reed pipe with drones (the hulusi)
  waits the same way; the drone ruling applies once its own build exists.
- **The mechanical ruling** (batch 13's tag rule). A free reed that plays itself from a roll,
  barrel, book or disc carries `tags` `mechanical` (H-S suffix -9). It is decided as the free reed
  it sounds as (the orchestrelle, a roll-played reed organ: a sound-alike of the catalog free reed
  its source relates it to, with its own sourced range). One whose source adds other instruments
  (the audit's "Solo Orchestrelle (1906) 14 reeds plus triangle") WAITs `more than four sources`
  once ranged. The first code task that ships one adds it to `MECHANICAL_FREE_REED_NAMES` and to
  the list in `test_plucked_idiophones_hold_the_lamellophones_and_music_boxes` (its comment: "This
  lists every mechanical entry, so it grows when another entry is tagged mechanical"), in catalog
  order.
- **The reed organ ruling** (the controller's). `reed organ` is a half-A candidate, decided here,
  not "Already decided". #70 says "`orchestrion` and `reed organ` are decided here (`orchestrion`
  waits for a sourced range, `reed organ` is dropped to free reeds), so the keyboards and free reeds
  batches must not decide them again". A DROP naming a family is a hand-off that family's batch
  decides, as batch 15 decided `claviharp` and `dolceola` after `batch-4.tsv` dropped them to
  keyboards; "must not decide them again" holds for `orchestrion` (batch 13 decided it: it waits for
  a sourced range) and is a slip of the pen for `reed organ`. Its row is decided on its pages like
  any other: an ALIAS of `harmonium` on a cited page giving the name to the harmonium, else a
  sound-alike of `harmonium` (rule 1: the Pump organ page makes the harmonium one of its types)
  once ranged. The reed organ's types (`physharmonica`, the Indian harmonium, `melodeon` in its
  organ sense) are decided on their own pages.
- **Range ruling for free reeds.** A sourced range is the lowest and highest sounding notes that
  one fetched source states for the instrument:
  1. *Stated, by one source*: both notes as the range or compass, from one source (batch 14's
     `xaphoon`: two sources for one range is no range), in note names with octaves (scientific
     `G3`; Helmholtz `c` or `g‴`, whose octave marks fix the octave, as #84 confirms; a named note
     whose octave the source fixes), or the lowest note and an exact span or reed count above it,
     chromatic or diatonic as the source says ("chromatic from C3, 37 notes"), as batch 7 allowed.
  2. *Sounding*: notes the source gives as the instrument's range are taken as given. A range the
     source calls written, notated or in a clef counts only with the transposition its own source
     states ("sounds an octave lower than written"), the derivation showing the arithmetic.
     Otherwise the row WAITs.
  3. *Extensions and extremes*: the stated compass, and nothing beyond it. Extra notes some models
     have, keys or reeds that "can be added", or a note in parentheses are extremes: the range is
     the compass without them, or the row WAITs.
  4. *A maker's or museum's page ranges that model only*: a maker's model page (Hohner, Suzuki,
     Tombo, Seydel, Hering; Pigini, Bugari, Victoria, Castagnari; Wheatstone, Lachenal, Dipper; a
     sheng or harmonium maker) or a museum's object record ranges a row named for that model or
     object only, never the bare type name (#85, the Neupert "harpsichord Hass" page).
  5. *Not a range*: a hedged span ("about", "approximately", "roughly", "typically", "usually",
     "can reach", "up to"); a general or notation rule ("harmonicas are written ...", "accordions
     usually have 41 keys", "concertinas range from ..." of the class); a width or count with no
     pitch ("two or three octaves", "37 keys", "10 holes", "36 reeds"); note letters with no octaves
     ("B to E", "C to C", "F-F pipes"); a key ("in C", "on an instrument in G"); a tuning list or a
     scale called a range (the saenghwang's *yul* names, the khaen's "seven tones per octave", a
     Richter layout); a tessitura; or one pitch. The audit's ranges are leads, not sources (its
     "VERIFIED" soprano and bass sheng, its "DERIVED" alto and tenor sheng and its "octave number is
     memory" pitch pipe included).
  6. *Several sizes, none standard*: a bare type name with several sizes, models or keys is ranged
     only from a source that calls one standard, usual, most common or traditional for the bare
     name. A source giving one instrument two ranges has given none (the tenor sheng's "G2 to F♯5 or
     F2 to E5"). With neither, the row WAITs (batch 7's rule; batch 14's `birbyne`).
  7. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached; a
     national encyclopedia); a maker's catalogue or model page (ruling 4); a museum's object record
     (MIMO, the Met, the Horniman and its Wayne concertina collection, the Smithsonian, the Musée
     de la musique, the Musical Instrument Museum (Phoenix), the Edinburgh University Collection,
     the Koizumi Fumio archive, the National Music Museum); a scholarly article (a journal or
     conference paper, a museum's or university's publication); or a conservatory or orchestration
     reference (the Vienna Symphonic Library). A museum's or maker's page outranks an uncited
     Wikipedia line, and when they disagree the museum or maker decides (batch 11's lesson). A
     retailer's listing, a blog, a forum, an auction listing or a hobbyist's page is not a source.
     A list or category page is a source for a name only. A range is never taken from a sibling, the
     parent, a related instrument ("like a harmonica's"), the audit or memory.
  8. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`) and nothing above C8
     (WAIT `a range above C8`), for the notes and for an octave reed set's sounding span.
  9. *One note*: an instrument whose source gives it one note (the audit's `mangtong`, "one pitch
     each") has no range. It WAITs `a sourced range`, the note quoted.
  10. *Cited*: a range, drone, detune, reed set or trait from Wikipedia counts only when the raw
      wikitext shows a citation (a `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it in its own
      cell or paragraph, with no `{{citation needed}}` first, in a section not tagged
      `{{Unreferenced section}}`. The citation must support the line: where the cited work is
      reachable the worker opens it, and a citation that gives no range (batch 11's `shehnai`) is
      no citation; one to a retailer (the Pitch pipe page's "Musician Madness",
      `{{Unreliable source?}}`) is none either. An uncited line is not a source for a range, a
      drone, a detune, a reed set or a trait that decides a SHIP or a WAIT.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then the
  derivation; then, as the rulings need, `Drones:`, `Detune:` and `Reeds:`, each with its passages
  and derivation, in that order.
- **Registers, stops and techniques.** A register or stop the player works (an accordion's
  switches, a harmonium's stops, a drone stop, a chromatic harmonica's slide, a swell) is no
  instrument and no trait. A technique (bending, the hand tremolo, tongue blocking, overblowing,
  the khaen's circular breathing) is how a player sounds the instrument, not its build.
- **Generic and ambiguous terms.** A name its source gives to a class or to several instruments is
  DROP "a generic term for <the instruments>" or "an ambiguous name: <the instruments>", unless the
  source makes it one instrument's name (then rule 3). `melodeon` is the first case to check: the
  Melodeon disambiguation page (checked for this plan) gives "Melodeon (accordion), a type of
  button accordion" and "Melodeon (organ), a type of 19th-century reed organ". `ken` and `u` are
  short words with other meanings; each is decided on the page that names it as the instrument.
- **Makers' names and products.** A maker's name for an instrument the catalog holds in several
  sizes (`pianica`, Yamaha's, and `triola`, Seydel's, for the melodica: the Melodica page's "The
  melodica is known by various names, often at the whim of the manufacturer") is an ALIAS of one
  size only on a cited page that gives the name to that size; a name for the instrument of every
  size is DROP "a maker's name for the <instrument> of every size, not one entry". A maker's
  product in production is decided on its own page (rule 3, or a row of its own ranged from its
  maker's page, or DROP under the one-off ruling).
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's in-production
  line): DROP "a one-off instrument, not a type a game would ask for" for one maker's or
  artist's design never made as a type (`chromelodeon`, if its pages make it Partch's two
  modified pump organs only); DROP "no fetched source describes it" when no fetched page describes
  the row, applied the same to every such row, candidate or alias name. A reconstruction makers
  offer today, or a type a museum holds, is not a one-off.
- **The size chain.** `test_sized_families_descend_from_highest_to_lowest` gains the sheng sizes
  that ship (soprano to bass, at least three), in Task 5, since their ranges are each sourced; the
  catalog's three melodicas are not chained (their ranges are unsourced), and #86 asks whether to
  add them.
- **Two halves, as explicit lists.** Half A, the bellows-blown free reeds (accordions,
  concertinas, harmoniums, reed organs, the shruti box and the boundary names that are bellows
  instruments), is these 17 candidates:
  `anglo concertina`, `cajun accordion`, `chemnitzer concertina`, `chromatic button accordion`,
  `chromelodeon`, `diatonic button accordion`, `duet concertina`, `flutina`, `free bass accordion`,
  `garmon`, `indian harmonium`, `orchestrelle`, `organetto`, `physharmonica`, `reed organ`, `shruti
  box`, `trikitixa`.
  Half B, the mouth-blown free reeds (harmonicas, the melodica, pitch pipes, the pipe mouth organs,
  the reed pipes and the jaw harp), is the other 25: `alto sheng`, `bass sheng`, `bawu`, `chord
  harmonica`, `chromatic pitch pipe`, `couesnophone`, `horn harmonica`, `hulusi`, `jaw harp`,
  `keluri`, `khene`, `lusheng`, `mangtong`, `octave harmonica`, `pitch pipe`, `qeej`, `saenghwang`,
  `sho`, `sompoton`, `soprano sheng`, `tenor melodica`, `tenor sheng`, `tremolo harmonica`, `u`,
  `yu`.
  The list decides the half. The alias names go with the half whose candidate or target their line
  names: half A's 9 (`bayan`, `melodeon`, `garmoshka`, `khromka`, `trikiti`, `eskusoinu txiki`,
  `piano accordion`, `peti`, `samvadini`) and half B's 16 (`kaen`, `khaen`, `kehn`, `ken`,
  `kheng`, `pianica`, `triola`, `claviola`, `goofus`, `queenophone`, `accordina`, `richter
  harmonica`, `keledi`, `enkulurai`, `kadedek`, `engkerurai`), each half in that order. So half
  A's sheet holds 26 rows and half B's 41.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the batch,
  or a SHIP or SOUND_ALIKE row of the same half, never a row of the other half. So Task 4 needs
  nothing from Task 2. Half B drafts to a build file, appended to the sheet once half A is
  committed. The form check accepts a row the code already holds with the same target or parent
  (batch 7's lesson). If Task 5 finds a half-B build equal to a half-A build, that is a finding for
  the controller, who re-rules the row in a sheet fix commit.
- **A held-back guard.** As batch 15's `KEYBOARD_HELD_BACK`, this batch's guard is
  `FREE_REED_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose
  reason is not `a sourced range` (an engine feature, a build of its own, a sourced drone tuning,
  a sourced detune, sub-audio fundamentals, a range above C8, more than four sources), and every
  alias row that waits for such a row. A test refuses each of its names in the catalog and the
  aliases through a helper that Task 1 tests on a real name and alias, so the guard is exercised
  even while its table is empty, and the code check compares the table with the sheet, in the
  sheet's order.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task still fills `FREE_REED_HELD_BACK` with the half's held
  rows and runs the code check, which must pass; its other steps are skipped, and Task 6 records
  the skip in #86.
- **Out of scope:** the audit's "Gaps you could not close" (`free-reeds.md`: Grove and MIMO not
  searched; the removed names bass, baritone and treble concertina, vocalion, harmoniflute,
  harmonetta, polyphonia, naw, steirische harmonika, schwyzerorgeli and hohner harmonetta; the
  template's unresearched orthotonophonium, harmoneon, panharmonicon, Martinshorn, lap organ,
  Querhammerflügel with Aeoline and sneng; the Aeolian-type orchestral reed organs), the
  side-blown sneng (#80), the seraphine and the melodeon organ (`organs.md`'s reed organ row), and
  the free-reed names a page mentions in passing. Task 6 lists them in #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of the build files is committed.

- [ ] **Step 0: The branch and the plan.** Run `git branch --show-current` and `git rev-parse
  --short HEAD`. Expected: `feat/instrument-catalog-batch-16` and `d4c1e3eb`. Anything else: stop
  and find out why. Copy this plan to `plans/2026-11-12-instrument-catalog-batch-16-implementation.md`
  and commit it:
```bash
git add plans/2026-11-12-instrument-catalog-batch-16-implementation.md
SKIP=replay-metrics git commit -m "Plans: batch 16 of the instrument catalog (free reeds), the implementation plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-16-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-16-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names), len(instruments.CATALOG), len(instruments.ALIASES))
"
```
  Expected (after pygame's banner): `names before 825 704 121` (checked for this plan at
  `d4c1e3eb`). Any other number means the branch is not batch 15's tip: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && tolower($4) ~ /free reed/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /free reed/ {print tolower($1)}' round-1/merged-missing.tsv
  awk -F'\t' 'NR>1 && $1 == "new_mechanical_instruments.md" && tolower($2) == "orchestrelle" {print tolower($2)}' merged.tsv
} | LC_ALL=C sort -u | LC_ALL=C comm -23 - ../../../build/batch-16-names-before.txt > ../../../build/batch-16-candidates.txt
cd ../../..
```
  Write the plan's 17 half-A names, one per line, to `build/batch-16-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-16-candidates.txt build/batch-16-half-a.txt > build/batch-16-half-b.txt`
  and `wc -l build/batch-16-*.txt`.
  Expected: 42 candidates, 17 in half A, 25 in half B, and
  `LC_ALL=C comm -13 build/batch-16-candidates.txt build/batch-16-half-a.txt` prints nothing.
  Check that `build/batch-16-half-b.txt` is exactly the plan's half-B list. The sorted union before
  the `comm` is also 42 names (no candidate is already a catalog name or alias).

- [ ] **Step 3: The form check,** `build/batch-16-form-check.py`. Copy `build/batch-15-form-check.py`
  and change it as follows; `STATUSES`, `pattern`, `held_as_this_row`, `taken`, `in_span`, the
  `bad` list's shape and the output stay.
  - The docstring:
```python
"""Batch 16's sheet form check: uv run python -I build/batch-16-form-check.py SHEET.

Batch 15's form check (build/batch-15-form-check.py) with batch 16's changes (batch 16's plan,
"Before the tasks" Step 3): the free reeds family, a shipped row's free reed class, batch 14's
drones and drone_source columns in place of the footages, a sound-alike's sourced sound changes
(cents, footages, drones), the only SHIP a droned reed, the mechanical tag, and a reed pipe's or
another family's parent only by the parent ruling's rule 1.
"""
```
  - Remove `KEYBOARD_CLASS`, `ALLOWED_FOOTAGES`, `UNISON_FOOTAGE`, `CATALOG_FOOTAGES`,
    `EXISTING_RATIOS`, `NYQUIST_HERTZ`, `RATIOS`, `keyboard_parents`, `harpsichord_parents`,
    `rank_footages`, `footage_of`, `ranged`, `footaged`, `built_ratios`, `near`, `partials_sourced`
    and `alike_allowed`, and the `math` and `fractions` imports; `names_before` reads
    `build/batch-16-names-before.txt`; refresh `APPROXIMATING_NAMES` from the test file's
    (unchanged since batch 13); and add:
```python
# Hornbostel-Sachs classes checked against Wikipedia's lists for batch 16's plan: 412.131 and
# 412.132 (individual and sets of free reeds) and 422.31 and 422.32 (single and double pipes with
# free reeds, which have finger holes), each with any suffixes (-8 keyboard, -9 mechanical drive)
FREE_REED_CLASS = re.compile(r'(412\.13[12]|422\.3[12])(-[0-9]+)*')
REED_PIPE_CLASS = re.compile(r'422\.3')
TAGS = ('', 'mechanical')
# with_drones: "at most two with breath", and _mouth_reed keeps the breath
MOST_DRONES = 2
SOUND_CHANGE_KEYS = {'cents', 'footages', 'drones'}
OCTAVE_REED_SETS = (8.0, 4.0)
# Parents only by the parent ruling's rule 1: a colouring and the accordion's left hand
RULE_ONE_PARENTS = {'musette accordion', 'accordion bass'}
SOUND_CHANGES = re.compile(r'sound_changes=(\{[^}]*\})')
pre_batch_entries = {
    name for name in names_before
    if name in instruments.CATALOG and instruments.entry(name).sounds_like is None
}
free_reed_parents = set(ship_rows) | {
    name for name in pre_batch_entries if instruments.entry(name).family == 'free reeds'
}


def changes(row):
    """A row's sound_changes from its builder cell, as a literal: {} if none, None if malformed."""
    match = SOUND_CHANGES.search(row['builder'])
    if match is None:
        return {}
    try:
        value = ast.literal_eval(match.group(1))
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, dict) else None


def parent_cents(name):
    """A parent's chorus cents as built: a catalog entry's cents keyword, else 0.0."""
    if name in ship_rows or name not in instruments.CATALOG:
        return 0.0
    return float(getattr(instruments.entry(name).build, 'keywords', {}).get('cents', 0.0))


def ranged(row):
    """Both notes, lowest below highest, a source and passage, an octave reed set's span in C8."""
    octave_up = (changes(row) or {}).get('footages') == OCTAVE_REED_SETS
    return (
        in_span(row['lowest']) and in_span(row['highest'])
        and row['range_source'].startswith('http')
        and 'Range:' in row['notes']
        and Note(row['lowest']).midi_number < Note(row['highest']).midi_number
        and (not octave_up or in_span(row['highest'], 12.0))
    )


def droned(row):
    """none, or one or two sourced drone notes, A0 to C8, highest first, with a passage."""
    if row['drones'] == 'none':
        return True
    if not row['drone_source'].startswith('http') or 'Drones:' not in row['notes'].partition('Range:')[2]:
        return False
    drone_notes = row['drones'].split()
    if not 1 <= len(drone_notes) <= MOST_DRONES or not all(in_span(note) for note in drone_notes):
        return False
    numbers = [Note(note).midi_number for note in drone_notes]
    return numbers == sorted(set(numbers), reverse=True)


def changes_sourced(row):
    """Each sound change a sourced number with its passage, and the detune not within 2%."""
    sound_changes = changes(row)
    if sound_changes is None or not set(sound_changes) <= SOUND_CHANGE_KEYS:
        return False
    after_range = row['notes'].partition('Range:')[2]
    if 'cents' in sound_changes:
        cents = sound_changes['cents']
        parent = parent_cents(row['alias_of'])
        if not isinstance(cents, float) or cents <= 0.0 or 'Detune:' not in after_range:
            return False
        if parent and abs(cents - parent) <= 0.02 * parent:
            return False
    if 'footages' in sound_changes and (
        sound_changes['footages'] != OCTAVE_REED_SETS or 'Reeds:' not in after_range
    ):
        return False
    return 'drones' not in sound_changes or row['alias_of'] in ship_rows


def shipped_build(row):
    """The only SHIP: a droned reed with sourced drones and no sound changes."""
    return row['builder'].startswith('_droned_reed') and row['drones'] != 'none' and not changes(row)


def alike_allowed(row):
    """A free reed parent, or a reed pipe's or another family's by rule 1, with its drones."""
    parent = row['alias_of']
    if parent in APPROXIMATING_NAMES or parent not in free_reed_parents | pre_batch_entries:
        return False
    needs_rule_one = (
        parent not in free_reed_parents
        or parent in RULE_ONE_PARENTS
        or REED_PIPE_CLASS.match(row['hs'])
    )
    if needs_rule_one and 'Parent (rule 1):' not in row['notes']:
        return False
    if 'drones' in (changes(row) or {}):
        return row['drones'] != ship_rows[parent]['drones']
    parent_drones = ship_rows[parent]['drones'] if parent in ship_rows else 'none'
    return row['drones'] == parent_drones
```
  - `in_span` takes `shift=0.0` as batch 15's does. The `bad` list's family test is
    `row['family'] != 'free reeds'`; its tag tests are batch 15's; its shipped-row test reads
```python
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)
                or not droned(row) or not FREE_REED_CLASS.fullmatch(row['hs'])
                or not changes_sourced(row)))
       or (row['status'] == 'SHIP' and not shipped_build(row))
```
    and its ALIAS test is `row['alias_of'] not in pre_batch_entries | set(ship_rows) | alikes |
    set(instruments.CATALOG)`.
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: The quote check,** `build/batch-16-quote-check.py`. Copy
  `build/batch-15-quote-check.py` and change it as follows; `CITATION`, `UNCITED_TAG`, `located`,
  `cited` and `quoted` stay. This answers #85's two quote check bugs: it decodes a page that is not
  UTF-8 (Gregg Miner's windows-1252 pages), and it checks every row's quotes, not only the shipped
  rows'.
  - The docstring:
```python
"""Batch 16's quote check: uv run python -I build/batch-16-quote-check.py SHEET.

Batch 15's quote check (build/batch-15-quote-check.py) with batch 16's changes (batch 16's plan,
"Before the tasks" Step 4). Every «passage» in every row's notes, whatever its status, must be in
one of the row's raw pages saved as build/batch-16-pages/<name, spaces as hyphens>--<n>.txt
(whatever its line breaks; for a page with HTML tags, in the raw text or in its visible text, tags
removed and entities unescaped), or else in a committed ledger file the notes may quote (the
spec, plans/future-features.md, an earlier sheet or an audit file). A SHIP or SOUND_ALIKE row's
Range:, Drones:, Detune: and Reeds: passages must be on its saved pages, and one whose source is
Wikipedia must have a citation after it in its own cell or paragraph, before any uncited tag. A
page is read as UTF-8, else as windows-1252 (listed in the output); a page that neither decodes is a
failure, never read lossily.
"""
```
  - The page reading and the ledger:
```python
import html
from pathlib import Path

PAGES = Path('build/batch-16-pages')
LEDGER_FILES = [
    Path('plans/2026-11-07-instrument-catalog-expansion-design.md'),
    Path('plans/future-features.md'),
    *sorted(Path('plans/data/instrument-audit').glob('batch-*.tsv')),
    *sorted(Path('plans/data/instrument-audit').glob('*.md')),
]
decoded_as_windows_1252 = []


def read_page(path):
    """A saved page's text: UTF-8, else windows-1252 (recorded); a UnicodeDecodeError otherwise."""
    raw = path.read_bytes()
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        decoded_as_windows_1252.append(path.name)
        return raw.decode('cp1252')


def visible(page):
    """A page's text with its HTML tags removed and its entities unescaped."""
    return html.unescape(re.sub(r'<[^>]+>', ' ', page))
```
    `LEDGER_FILES` leaves out the sheet being checked (the glob's `batch-16.tsv` is removed from the
    list by comparing with `Path(sys.argv[1])`, and a build file of the sheet is not in the glob).
  - Every row's pages are read with `read_page` (a `UnicodeDecodeError` appends `(name, 'page
    neither UTF-8 nor windows-1252: <file>')` to `bad`). A passage is found in a page when
    `located(page, passage)` or `located(visible(page), passage)` is not None; the citation check
    runs on the raw page only (wikitext).
  - The shipped rows' sections are:
```python
    sections = [('range', quoted(row['notes'], 'Range:', ('Drones:', 'Detune:', 'Reeds:')), row['range_source'])]
    if row['drones'] != 'none':
        sections.append(('drones', quoted(row['notes'], 'Drones:', ('Detune:', 'Reeds:')), row['drone_source']))
    if "'cents'" in row['builder']:
        sections.append(('detune', quoted(row['notes'], 'Detune:', ('Reeds:',)), row['sound_source']))
    if "'footages'" in row['builder']:
        sections.append(('reeds', quoted(row['notes'], 'Reeds:', ()), row['sound_source']))
```
    each checked as batch 15's are, against the row's saved pages only (a shipped row with no
    saved page is `no saved page`).
  - Then, for every row of every status, every `«passage»` in its whole `notes` that is on none of
    its saved pages must be in one of the `LEDGER_FILES` (found with `located`), else `bad` gets
    `(name, 'quote on no saved page or ledger file: ' + passage[:60])`. A row with no passage and
    no page (a DROP "no fetched source describes it") passes.
  - It prints `decoded as windows-1252:` with the list, then `bad:` and exits 1 if `bad`.
  It checks what can be checked mechanically; a worker still applies range ruling 10 in full.

- [ ] **Step 5: The code check,** `build/batch-16-code-check.py`: copy `build/batch-15-code-check.py`
  and change it as follows; `test_table`, `held_back`, `in_catalog_order`, the "Already decided"
  branch and the order checks' shape stay.
  - The docstring:
```python
"""Batch 16's code check: uv run python -I build/batch-16-code-check.py SHEET.

Batch 15's code check (build/batch-15-code-check.py) with batch 16's changes (batch 16's plan,
"Before the tasks" Step 5): the free reeds family, the drones, the sound changes (cents, footages,
drones) and the mechanical tag compared with the sheet, and the builds, sound-alikes and aliases
in the sheet's order. The test file's tables and a builder cell's sound changes are read as
literals (ast.literal_eval), never evaluated. A one-off check may read the private
_FREE_REED_BUILDS; a test may not.
"""
```
  - The imports read `FREE_REED_SOUND_ALIKES` from `free_reed_sound_alikes` and
    `_FREE_REED_BUILDS` from `free_reeds`, add `import math` and `from glitchygames.audio.pitch
    import Note`; `EXISTING_COUNT = 13`; `NAMES_BEFORE` reads `build/batch-16-names-before.txt`;
    `RATIOS`, `effective_keywords`, `sheet_ratios`, `sheet_sixteen_foot` and `sheet_changes` go,
    replaced by batch 14's `built_drones` and `sheet_drones` (unchanged) and:
```python
SOUND_CHANGES = re.compile(r'sound_changes=(\{[^}]*\})')


def sheet_changes(row):
    """The sound changes the row's builder cell names, read as a literal ({} for none)."""
    match = SOUND_CHANGES.search(row['builder'])
    return {} if match is None else ast.literal_eval(match.group(1))


def built_detune(name):
    """The cents of an entry's chorus copy, or 0.0 when it has none."""
    sources = dict(instruments.get(name).sources)
    return float(sources['chorus'].detune_cents) if 'chorus' in sources else 0.0


def sheet_detune(row):
    """A sound-alike's own cents, else its parent's as built (a droned SHIP row's 0.0)."""
    own = sheet_changes(row).get('cents')
    if own is not None:
        return float(own)
    parent = row['alias_of'] if row['status'] == 'SOUND_ALIKE' else None
    if parent is None or parent in rows_by_name:
        return 0.0
    return float(getattr(instruments.entry(parent).build, 'keywords', {}).get('cents', 0.0))
```
    (`rows_by_name` is defined before them, as in batch 15's script).
  - The shipped-row assertions after `assert entry.sounds_like == parent, name` read:
```python
        expected_tags = frozenset({Tag.MECHANICAL}) if row['tags'] == 'mechanical' else frozenset()
        assert entry.tags == expected_tags, name
        assert dict(entry.sound_changes) == sheet_changes(row), name
        assert built_drones(name) == sheet_drones(row), name
        assert math.isclose(built_detune(name), sheet_detune(row)), name
```
  - The table assertions after the loop read:
```python
assert test_table('FREE_REED_DRONES') == {
    name: tuple(rows_by_name[name]['drones'].split())
    for name in in_catalog_order(lambda row: row['drones'] != 'none')
}, 'FREE_REED_DRONES'
assert test_table('FREE_REED_DETUNES') == {
    name: float(sheet_changes(rows_by_name[name])['cents'])
    for name in in_catalog_order(lambda row: 'cents' in sheet_changes(row))
}, 'FREE_REED_DETUNES'
assert test_table('FREE_REED_REED_SETS') == {
    name: tuple(sheet_changes(rows_by_name[name])['footages'])
    for name in in_catalog_order(lambda row: 'footages' in sheet_changes(row))
}, 'FREE_REED_REED_SETS'
assert test_table('MECHANICAL_FREE_REED_NAMES') == in_catalog_order(
    lambda row: row['tags'] == 'mechanical'
), 'MECHANICAL_FREE_REED_NAMES'
assert test_table('FREE_REED_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'FREE_REED_HELD_BACK'
assert list(test_table('FREE_REED_HELD_BACK')) == [
    row['name'] for row in rows if held_back(row)
], 'held-back order'
assert test_table('NEW_FREE_REED_NAMES') == ship_names, 'NEW_FREE_REED_NAMES'
assert list(test_table('FREE_REED_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'FREE_REED_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in _FREE_REED_BUILDS[EXISTING_COUNT:]] == ship_names, 'build order'
assert [entry.name for entry in FREE_REED_SOUND_ALIKES] == alike_names, 'sound-alike order'
```
    followed by batch 15's alias-order assertion and `print('matches', len(rows), 'rows')`. `in_catalog_order`
    must be defined before these assertions (move it above them if the copy has it below).
  It cannot run until Task 1 has created `free_reeds.py`, `free_reed_sound_alikes.py` and the test
  tables. The one "Already decided" DROP row (`jaw harp`) was never a catalog name or alias, so it
  takes the last branch.

---

### Task 1: Free reeds in their own module, unchanged; their sound-alikes module; the batch table's row, the drones, detune, reed-set and mechanical tables, the held-back guard, and every guard's helper tested on a real build

**Files:**
- Create: `src/glitchygames/audio/instruments/free_reeds.py`,
  `src/glitchygames/audio/instruments/free_reed_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/winds.py`, `registry.py`, and the docstrings of
  `__init__.py`, `bagpipes.py`, `clarinets.py`, `double_reeds.py` and `flutes.py`
- Test: `tests/audio/test_instrument_catalog.py`, `tests/test_process_state_guard.py`

**Interfaces:**
- Produces: in `free_reeds.py`, `FREE_REEDS: Final[tuple[CatalogEntry, ...]] = _FREE_REED_BUILDS
  + FREE_REED_SOUND_ALIKES`, `FREE_REED_LEVELS: Final[tuple[float, ...]]`, and `_accordion(*,
  cents: float, low_pass: float) -> Instrument` and `_mouth_reed(*, low_pass: float, breath: float
  = 0.03) -> Instrument` under their current names; in `winds.py`, `SAXOPHONES` and `_saxophone`
  unchanged. `FREE_REED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test file
  gains `EXISTING_FREE_REED_NAMES: frozenset[str]` (the 13); `NEW_FREE_REED_NAMES: list[str]`,
  `FREE_REED_SOUND_ALIKE_PARENTS: dict[str, str]`, `MECHANICAL_FREE_REED_NAMES: list[str]`,
  `FREE_REED_DRONES: dict[str, tuple[str, ...]]`, `FREE_REED_DETUNES: dict[str, float]`,
  `FREE_REED_REED_SETS: dict[str, tuple[float, ...]]` and `FREE_REED_HELD_BACK: dict[str, str]`,
  all empty here, for Tasks 3 and 5 to fill; the helpers `drone_hertz(name: str) -> list[float]`,
  `chorus_detune_cents(name: str) -> float | None`, `effective_free_reed_keywords(catalog_entry:
  CatalogEntry) -> dict[str, object]`, `tone_wave(name: str) -> Wave` and
  `names_listed(names: Iterable[str]) -> set[str]`; the tests below; and the row
  `Family.FREE_REEDS: BatchFamily(EXISTING_FREE_REED_NAMES, NEW_FREE_REED_NAMES,
  FREE_REED_SOUND_ALIKE_PARENTS)` in `BATCH_FAMILIES`. Also `build/catalog-builds-before.txt`.

- [ ] **Step 1: Record every build.**
```bash
uv run python -I -c "
from glitchygames.audio import instruments
with open('build/catalog-builds-before.txt', 'w', encoding='utf-8') as before:
    for name in instruments.names():
        entry = instruments.entry(name)
        before.write(f'{name}\t{entry.title}\t{entry.lowest}\t{entry.highest}\t{instruments.get(name)._identity()!r}\n')
print('recorded', len(instruments.names()))
"
```
  Expected: `recorded 704`. (`_identity` is private. A one-off check may read it, a test may not.)

- [ ] **Step 2: Write the tables and the guards.** After batch 15's keyboard tables
  (`MECHANICAL_KEYBOARD_NAMES`), add `EXISTING_FREE_REED_NAMES` (the 13 names, one per line, in
  catalog order, with the comment "# The 13 free reeds that predate batch 16: their shared builds
  predate the anti-goal rule"), then `NEW_FREE_REED_NAMES: list[str] = []`,
  `FREE_REED_SOUND_ALIKE_PARENTS: dict[str, str] = {}` and `MECHANICAL_FREE_REED_NAMES: list[str]
  = []`, each commented as batch 15's keyboard lists are. Put the free reeds row between the
  bagpipes and brass rows in `BATCH_FAMILIES`, which is table order. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list gains `+
  list(FREE_REED_SOUND_ALIKE_PARENTS)` between the bagpipes' and the brass' lines, its comment
  reading "… double reeds, bagpipes, free reeds, brass, …". At the end of the file, after
  `test_a_keyed_idiophone_sounds_its_sourced_partials` (batch 15's last test), add:
```python
# Batch 16's free reeds with fixed drones (_droned_reed), each with its drone notes as the sheet
# writes them (highest first), sounding at equal temperament under every note, in catalog order:
# the builds, then their sound-alikes (plans/data/instrument-audit/batch-16.tsv)
FREE_REED_DRONES: dict[str, tuple[str, ...]] = {}
# Batch 16's free reed sound-alikes whose sourced detune between reed sets differs from their
# parent's, each with its cents (sound_changes={'cents': ...}), in the sheet's order
# (plans/data/instrument-audit/batch-16.tsv)
FREE_REED_DETUNES: dict[str, float] = {}
# Batch 16's free reed sound-alikes with a sourced reed set an octave above the unison
# (sound_changes={'footages': (8.0, 4.0)}), in the sheet's order
# (plans/data/instrument-audit/batch-16.tsv)
FREE_REED_REED_SETS: dict[str, tuple[float, ...]] = {}
# Every name plans/data/instrument-audit/batch-16.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# drone tuning or detune, sub-audio fundamentals, a range above C8 or more than four sources, and
# the alias rows that wait for one of them, in the sheet's order. None ships under that name or as
# an alias until the reason is met (decision 4; batch 16). The test matches exact names
FREE_REED_HELD_BACK: dict[str, str] = {}
```
  Then the helpers, each with a Google docstring (`Returns:`), and the tests, each with a one-line
  docstring:
  - `names_listed(names)`: the given names that are catalog names or aliases.
  - `drone_hertz(name)`: `[float(source.pitch) for source_name, source in
    instruments.get(name).sources if source_name.startswith('drone_')]`, in build order.
  - `chorus_detune_cents(name)`: the `chorus` source's `detune_cents` as a float, or None.
  - `effective_free_reed_keywords(catalog_entry)`: the parent's (or its own) build keywords, read
    with `getattr(build, 'keywords', {})`, updated with its `sound_changes`.
  - `tone_wave(name)`: the `tone` source's `content` (a `Wave`; checked for this plan:
    `harmonica`'s equals `wave_from_levels(FREE_REED_LEVELS)`).
  - `test_the_free_reed_guards_helpers_read_real_builds`: `names_listed(['harmonica', 'fender
    rhodes', 'not an instrument']) == {'harmonica', 'fender rhodes'}` (a catalog name and an alias
    from before the batch); `drone_hertz('highland bagpipe') == [240.0, 120.0]` and
    `drone_hertz('harmonica') == []`; `chorus_detune_cents('musette accordion') == 15.0` and
    `chorus_detune_cents('harmonica') is None`;
    `effective_free_reed_keywords(instruments.entry('musette accordion')) == {'cents': 15.0,
    'low_pass': 6000.0}`; and `tone_wave('harmonica') == wave_from_levels(FREE_REED_LEVELS)`
    (importing the public `FREE_REED_LEVELS` from `free_reeds` and `wave_from_levels` from
    `timbres`). This is batch 15's final review lesson: each guard below is exercised on a real
    build even while its table is empty.
  - `test_no_free_reed_name_held_back_for_a_feature_is_listed`: `names_listed(FREE_REED_HELD_BACK)
    == set()`.
  - `test_the_mechanical_free_reeds_are_tagged`: `instruments.names(family=Family.FREE_REEDS,
    tag=Tag.MECHANICAL) == tuple(MECHANICAL_FREE_REED_NAMES)`.
  - `test_a_droned_free_reed_sounds_its_sourced_drones`: the free reed entries with a non-empty
    `drone_hertz` are exactly `FREE_REED_DRONES`' keys, in catalog order; each one's
    `drone_hertz` equals `[round(float(Note(note).to_hz()), 2) for note in drone_notes]`, and each
    is in `NOT_PERIODIC_AT_THE_NOTE`.
  - `test_a_detuned_free_reed_beats_at_its_sourced_cents`: the free reed entries whose
    `sound_changes` hold `cents` are exactly `FREE_REED_DETUNES`' keys, in catalog order; each
    one's `chorus_detune_cents` is `pytest.approx` its value.
  - `test_a_free_reed_reed_set_sounds_its_octave`: the free reed entries whose
    `effective_free_reed_keywords` hold a `footages` other than `(8.0,)` are exactly
    `FREE_REED_REED_SETS`' keys, in catalog order; each one's `tone_wave` equals
    `wave_from_levels(compound_stop_levels(FREE_REED_LEVELS[:16], footages))` (importing the
    public `compound_stop_levels` from `organs`).
  All of them hold with the tables empty (no free reed is tagged, droned, re-detuned or given a
  reed set today) and fail if a later task ships one without listing it; the helper test proves
  the reading they rely on.

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or mechanical or droned or detuned or reed_set or helpers_read_real_builds or sound_their_note" -v`
  Expected: PASS, with the ID `[free reeds]` in the parametrised batch tests. They are guards that
  hold the later tasks; the move in Step 4 must keep them passing.

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move `winds.py`'s
  "Free reeds" section (its header comment, `FREE_REED_LEVELS`, `_accordion`, `_mouth_reed` and
  `FREE_REEDS`) into `free_reeds.py` unchanged, comments included, with the imports it uses
  (`partial`, `TYPE_CHECKING`, `Final`, `CatalogEntry`, `Family`, `blown`, `falling_series`, and
  `Instrument` under `TYPE_CHECKING`); `winds.py` keeps only what its section uses. Rename the
  moved tuple `_FREE_REED_BUILDS` and define `FREE_REEDS` after it as the concatenation, importing
  `FREE_REED_SOUND_ALIKES`. The docstrings:
  - `free_reeds.py`'s first line is "Free reeds: accordions, concertinas, bandoneon, harmonium,
    harmonicas, melodicas and sheng." (94 columns with its quotes). It says that a free reed is a
    tongue swinging through a closely fitting slot (Hornbostel-Sachs 412.13), keeps winds.py's
    ranges sentence verbatim (with "folk instruments' are typical of the common keys": #84
    reported it, and the owner has not ruled) and "free reeds are bright and buzzy", says that the
    sound-alikes are in ``free_reed_sound_alikes.py``, and names ``winds.py`` for the saxophones.
  - `winds.py`'s first line becomes "Saxophones: conical single reeds, sopranino to contrabass
    saxophone." (71 columns). It keeps its ranges sentence verbatim, the saxophones' timbre
    sentence ("saxophones (cones) have every harmonic and are brighter"), and names the free reeds'
    module, ``free_reeds.py``, beside the others it names.
  - `free_reed_sound_alikes.py` gets the empty table and `keyboard_sound_alikes.py`'s docstring
    with "Free reeds'" for "Keyboards'", the 16' sentence replaced by "A sound-alike whose source
    gives it a detune between its reed sets, an octave reed set or drones its parent lacks carries
    them as ``sound_changes``, its only changes.", ending "The family's builds are in
    ``free_reeds.py``.". Its first line is "Free reeds' sound-alikes: listed instruments that share
    another entry's build." (81 columns).
  - `__init__.py` lines 102, 113 and 124 say "``winds.py`` keeps the saxophones and
    ``free_reeds.py`` the free reeds"; `bagpipes.py` line 9, `clarinets.py` lines 8–9,
    `double_reeds.py` line 6 and `flutes.py` line 8 name ``winds.py`` for the saxophones and
    ``free_reeds.py`` for the free reeds, rewrapped to 100 columns.
  Point `registry.py` at both modules (`SAXOPHONES` from `winds`, `FREE_REEDS` from
  `free_reeds`). Move the process-state guard's listing (File Structure); read the guard's module
  docstring first, since its listings are an audit (rows R16, `CATALOG_SERIES`), and the moved
  name keeps its reason unchanged.

- [ ] **Step 5: Check nothing changed.**
```bash
uv run python -I -c "
from glitchygames.audio import instruments
before = [line.split('\t') for line in open('build/catalog-builds-before.txt', encoding='utf-8').read().splitlines()]
assert [row[0] for row in before] == list(instruments.names()), 'order'
changed = [row[0] for row in before
           if [instruments.entry(row[0]).title, str(instruments.entry(row[0]).lowest), str(instruments.entry(row[0]).highest), repr(instruments.get(row[0])._identity())] != row[1:]]
print('changed:', changed)
"
awk 'FNR == 1 && length > 100 {print FILENAME": "length}' src/glitchygames/audio/instruments/*.py
uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q
```
  Expected: `changed: []`, nothing from `awk` (every module's first line fits in 100 columns), then
  PASS.

- [ ] **Step 6: Lint and commit.** Run each lint command as its own line (batch 11's Task 1: zsh
  word-splitting once made a combined run a no-op).
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
SKIP=replay-metrics git commit -m "Instrument catalog: free reeds in their own module, unchanged; their sound-alikes module; the drones, detune, reed-set, mechanical and held-back guards, each helper tested on a real build" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The bellows free reeds sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch` for searching, and fetch
every URL you cite with curl, saving it. A WebFetch summary is a lead, never a source (#85's
`nickelodeon`); never cite a page you did not save. Put no personal data in any request, in a
header, a URL or a payload. Save each row's raw pages as `build/batch-16-pages/<name, spaces as
hyphens>--<n>.txt` (for Wikipedia, the `action=raw` wikitext; never a text extracted from it,
which drops `<ref>` and `<sup>`: #81's lesson; for a refused page, the Internet Archive's `id_`
copy). This holds for every row whose notes quote a page, WAIT and DROP rows too, since the quote
check reads them all. A list or category page is a source for a name only. The sound, the
mechanism, the range and any drones, detune or reed sets come from the instrument's own page, a
maker, a museum or a scholarly article under range ruling 7. The audit's rows and "Range checks"
are leads, not sources, so fetch them. Fetch the page of every existing entry you name as a
parent, and record what it says in the row's notes. Never use `git stash`. This task may start
as soon as the controller has written the shared files, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-16.tsv`
- Create (not committed): `build/batch-16-half-a.tsv`, and the raw pages in
  `build/batch-16-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `free-reeds.md` ("Rejected or corrected
  proposed entries", "Aliases", "Range checks", "Gaps you could not close");
  `new-mechanical-instruments.md` (the `orchestrelle` row); `organs.md` (its `reed organ` row);
  `batch-13.tsv` (the `reed organ` and `chromelodeon` rows); `build/batch-16-names-before.txt`,
  `build/batch-16-half-a.txt`, `build/batch-16-half-b.txt`, `build/batch-16-form-check.py` and
  `build/batch-16-quote-check.py`.
- Produces: `batch-16.tsv` with batch 14's seventeen columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	drones	drone_source`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `free reeds` on every row; `tags` is
  `mechanical` or empty; `drones` is `none` or the drone notes. A SHIP or SOUND_ALIKE row has
  `lowest`, `highest` (sounding), `range_source`, an `hs` that fullmatches the free reed classes,
  and `notes` holding `Range:` (and `Drones:`, `Detune:`, `Reeds:` as the rulings need), each with
  its «raw passages» and derivation, and its parent ruling line ("Parent (rule 1):" or "Parent
  (rule 2):") for a sound-alike. Its `builder` cell says "unchanged", or gives
  `sound_changes={...}` as a literal (`{'cents': 12.0}`, `{'footages': (8.0, 4.0)}`), or a SHIP's
  `_droned_reed(...)` call with every keyword, saying which values come from the source and which
  are sound design, copied from which entry. A candidate row's `audit_name` is its name in
  `build/batch-16-candidates.txt`; an alias row's is its audit line as the Spec line gives it.
  Also `build/batch-16-half-a.tsv`, the half as committed, which Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-16-half-a.txt`'s order, then
  one per alias name of this half, in the plan's order.

  The rules are batch 15's, changed for this family:

  1. **SHIP** only with name, title, sound, mechanism, range and drones from fetched sources, as the
     drone ruling gives it: `_droned_reed` is the batch's only SHIP build. Quote in `notes` the
     passage that describes the sound or construction (what sounds and how it is blown) and, after
     `Range:` and `Drones:`, the «raw passages» and the derivations under the rulings.
  2. **SOUND_ALIKE**: a verified instrument that rule 7 finds would sound like an existing entry or
     a SHIP row of this half. `alias_of` is its parent (the parent ruling). The `notes` begin
     "Sound-alike:", quote the source's description and mechanism, and say why that entry is the
     parent ("Parent (rule 1):" with the source's relating words, or "Parent (rule 2):" with the
     mechanism and the semitone counts). It has its own range, and the `builder` cell says
     "unchanged" or gives its sourced `sound_changes` (the detune, reed-set and drone rulings). It
     is never another sound-alike's sound-alike, never one of `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row of this half. If the target waits, the row is WAIT with `waits_for`
     `its target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is
     dropped". An ambiguous name or a generic term is DROP under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `a sourced drone tuning`, `a sourced
     detune`, `sub-audio fundamentals`, `a range above C8`, `more than four sources`, `its own build
     (<the trait>)`, or another name of Global Constraints. **The range is checked first.** The
     feature must be the sound the source describes, not a technique a player applies (a register,
     a stop, a bend, a hand tremolo). A cited trait no builder makes means the row waits. Any other
     name is allowed only with the source quoted, and Task 6 lists it in #86.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     boundary ruling's words), is a one-off, makes no sound, or is already decided: in the catalog
     under that name (name the entry), an alias already (name its target), or a row of an earlier
     sheet (notes beginning "Already decided:", naming the earliest sheet and its status).
  6. A row the audit marks UNVERIFIED for existence, or sourced only by a list or category page,
     has no sourced sound or range yet. Fetch its own page; the audit's URL is a lead. If no page
     can be found, the row is DROP "no fetched source describes it", the same words on every such
     row.
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='free reeds'))"`
     and the builds in `free_reeds.py`) and every SHIP row above it. If no cited trait (fixed
     sourced drones) makes it sound different, it is a SOUND_ALIKE under rule 2. A number chosen
     only to differ does not count, nor a difference of 1 or 2 percent in a value (batch 11's
     contraforte), nor a loudness, a colour word, a range, a key, a size, a layout, a tuning, a
     material or a self-playing mechanism.
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.

  This half's own cases:

  - **Batch 13's hand-offs.** `reed organ` is decided here under the reed organ ruling (batch 13:
    "an organ that uses free reeds"; its row quotes #70's sentence, which the quote check finds in
    `plans/future-features.md`, and the Pump organ page). `chromelodeon` is decided here (batch 13: "pump organs retuned by
    Partch"): a retuning is no trait (the tuning ruling), so it is decided by the one-off ruling on
    its pages (Partch's Chromelodeon I and II), else as a sound-alike of `harmonium` once ranged.
  - **The orchestrelle.** `orchestrelle` (#70: "the free reeds batch's"; the audit: "Aeolian_Orchestrelle
    returned 404") follows the mechanical ruling: `tags` `mechanical` on a shipped row, a
    sound-alike of the catalog free reed its source relates it to, its range from a source for the
    instrument (a maker's catalogue for a named model ranges that model only), WAIT `more than four
    sources` once ranged if its source adds a triangle or other instruments to the reeds.
  - **Accordions.** `chromatic button accordion`, `diatonic button accordion`, `free bass
    accordion`, `cajun accordion`, `organetto`, `trikitixa`, `garmon` and `flutina` are decided by
    the sound-alike, parent and range rulings: the button layout, the free-bass or Stradella left
    hand, bisonoric action, a register switch and the number of rows are no trait; "dry" or "wet"
    tuning is a detune only with its cents sourced (the detune ruling). Their parent is `accordion`
    by rule 1 where the source calls it an accordion, else by rule 2. The audit's "VERIFIED for
    early Tula garmon" C4–C6 is a model's or period's range (range ruling 4), not the bare
    `garmon`'s, unless its source calls that size standard.
  - **Concertinas.** `anglo concertina`, `duet concertina` and `chemnitzer concertina` are concertina
    systems (the Concertina page: systems "which differ in terms of keyboard layout and whether
    individual buttons (keys) produce the same ... [or different notes]"): a layout is no trait,
    so each is a sound-alike once ranged, its parent `concertina` by rule 1 (the catalog's
    `concertina` is titled "English concertina", so a source relating the row to the English one or
    to the concertina in general decides; the Chemnitzer's detuned pair is a detune only with cents
    sourced).
  - **Harmoniums.** `indian harmonium` (the Free reed aerophone page's "the peti or ... samvadini
    (the Indian floor harmonium)" is a lead for its aliases), `physharmonica` and `shruti box` are
    decided on their pages: a hand pump, drone stops and a shruti tuning are no trait; a shruti box
    is decided as the instrument whose reeds sound (its "3 drone notes" are the notes a sequence
    asks for, not drones under a melody); `physharmonica`'s "four octaves" (the audit) is a width.
  - **The alias names.** `bayan` (the audit: "a Russian variant" of the chromatic button accordion)
    is an ALIAS only on a cited page giving it as that instrument's name, else a row of its own
    decided like any other; `melodeon` follows the generic and ambiguous terms ruling (the
    disambiguation page's two instruments); `garmoshka` and `khromka` follow `garmon`, `trikiti`
    and `eskusoinu txiki` follow `trikitixa` (rule 3), `piano accordion` is an ALIAS of `accordion`
    on a cited page giving it as the accordion's name (else a row of its own, the piano accordion
    being one kind among several), and `peti` and `samvadini` follow `indian harmonium`.

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-16-form-check.py plans/data/instrument-audit/batch-16.tsv`
  and `uv run python -I build/batch-16-quote-check.py plans/data/instrument-audit/batch-16.tsv`.
  Expected: `26 rows;` and the counts, then `bad: []`, exit 0; then the windows-1252 list (any
  page named is recorded in the row's notes), `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-16.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-16-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-16-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
"
```
  Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-16.tsv build/batch-16-half-a.tsv
git add plans/data/instrument-audit/batch-16.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 16's verification sheet, the bellows free reeds (accordions, concertinas, harmoniums and reed organs)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The bellows free reeds

**Files:**
- Modify: `free_reeds.py` (new builds after the 13; `_accordion`'s `footages` only if a row needs
  it), `free_reed_sound_alikes.py` (`FREE_REED_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with
  its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-16-half-a.tsv` (half A as committed), Task 1's tables and helpers, and
  `build/batch-16-code-check.py`.
- Produces: `NEW_FREE_REED_NAMES`, `FREE_REED_SOUND_ALIKE_PARENTS`, `MECHANICAL_FREE_REED_NAMES`,
  `FREE_REED_DETUNES`, `FREE_REED_REED_SETS` and `FREE_REED_HELD_BACK` filled with this half's rows,
  which Task 5 extends; and, if a row needs it, `_accordion(*, cents: float, low_pass: float,
  footages: tuple[float, ...] = (8.0,)) -> Instrument` with the reed-set ruling's levels. Half A
  is bellows-blown, so a half-A row that needs `_droned_reed` or `_mouth_reed` is a finding for the
  controller.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills only
`FREE_REED_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_FREE_REED_NAMES` with one name per SHIP row,
  `FREE_REED_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row,
  `MECHANICAL_FREE_REED_NAMES` with every SHIP and then SOUND_ALIKE row whose `tags` is
  `mechanical`, `FREE_REED_DETUNES` and `FREE_REED_REED_SETS` with each sound-alike whose
  `sound_changes` give `cents` or `footages`, and `FREE_REED_HELD_BACK` with one `name: waits_for`
  per held row (every WAIT row whose reason is not `a sourced range`, and every `its target, <name>`
  row whose target is held), each in the sheet's order. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, in the sheet's order, with a docstring sentence
  for batch 16. If a mechanical row ships, add it to the list in
  `test_plucked_idiophones_hold_the_lamellophones_and_music_boxes` after `'music box'`, in catalog
  order. If `footages` is added, add `test_accordion_footages_add_an_octave_reed_set`: through
  `instruments.entry('accordion').build.func` (the builder is private, so the test reaches it
  through the catalog entry, as `eight_foot_relative_harmonics` does), the build with
  `footages=(8.0, 4.0)` has a `tone_wave` equal to
  `wave_from_levels(compound_stop_levels(FREE_REED_LEVELS[:16], (8.0, 4.0)))`, and the build with
  the default equals `instruments.get('accordion')`.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or held_back or mechanical or music_boxes or detuned or reed_set or footages or sound_their_note" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...` (and, before
  the keyword exists, the footages test with a `TypeError` naming it); the held-back test passes.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in `FREE_REED_SOUND_ALIKES`,
  in the sheet's order, under a section comment naming `plans/data/instrument-audit/batch-16.tsv`
  as `organ_sound_alikes.py`'s does ("--- Batch 16's bellows free reeds, in the order of …"), each a
  `CatalogEntry(name, title, Family.FREE_REEDS, lowest, highest, sounds_like=parent)` with
  `sound_changes={...}` as its row gives and `tags=frozenset({Tag.MECHANICAL})` for a mechanical
  row. Above each, put a comment with its `sound_source` and `range_source` URLs, the quoted
  passages (its mechanism, its range, and any detune or reed set) and the derivations. Each ALIAS
  row goes in `aliases.py` under a "Batch 16's free reeds: the bellows free reeds" section, in the
  sheet's order, with its URL and quote. Add `footages` only if a row needs it, with the reed-set
  ruling's levels marked as sound design. Comments name only committed files.

- [ ] **Step 4: Run the suite and check the code against the sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range or the build: check it against the source, and never trim the range to
  pass. A detuned sound-alike that fails the periodicity test goes in `NOT_PERIODIC_AT_THE_NOTE`
  ("two reed sets <cents> cents apart beat") only after the failure is measured, and Task 6 lists
  it in #86. Then run:
  `uv run python -I build/batch-16-code-check.py build/batch-16-half-a.tsv`
  Expected: `matches 26 rows`. Then rerun Task 1 Step 5's first command with its `order`
  assertion replaced by `names = set(instruments.names()); assert all(row[0] in names for row in
  before), 'missing'`. Expected: `changed: []` (no earlier build changed, the `footages` default
  included).

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 16's bellows free reeds, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The mouth-blown free reeds sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-16-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-16-pages/`
- Modify: `plans/data/instrument-audit/batch-16.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-16-form-check.py`,
  `build/batch-16-quote-check.py`, `build/batch-16-half-b.txt`; `free-reeds.md` (its "Rejected
  or corrected" lines for `jaw harp`, `bawu`, `saenghwang`, `pitch pipe`, `khene`, `lusheng`, `sho`
  and `hulusi`; "Aliases"; "Range checks"; "Gaps"); `round-1/merged-missing.tsv` (the round-1
  rows); `batch-1.tsv` (the `jaw harp` row); `batch-12.tsv`'s drone rows and `batch-14.tsv`'s
  `pey pok`, `tarpa` and `pungi` rows as worked examples of the drone and beating-reed rulings.
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-16-half-b.txt`'s order, then one per alias name
of this half, in the plan's order. A parent or alias target is a catalog name or a SHIP or
SOUND_ALIKE row of this half, never a half-A row. These rules apply on top of Task 2's:

- **Already decided.** `jaw harp` is DROP under rule 5, its notes beginning "Already decided:
  batch-1.tsv WAIT" with that row's family and wait (plucked idiophones, moving formants).
- **Harmonicas.** `tremolo harmonica` and `octave harmonica` follow the detune and reed-set rulings
  (the Harmonica page: "two reeds per note, with one slightly sharp and the other slightly flat";
  "slightly" is no number, so the tremolo is a sound-alike of `harmonica` unchanged or WAIT `a
  sourced detune` as the detune ruling decides); `chord harmonica` (its chords are notes a sequence
  asks for) and `horn harmonica` (the Harmonica page's "lowest pitched starting two octaves below
  middle C ... they usually cover a two- or three-octave range" is a hedged width with models) are
  sound-alikes once ranged, their parent by rule 1 or rule 2's reed plates. `couesnophone` (the
  audit: "saxophone-shaped ... between harmonica and accordion") is decided on its page: its shape
  is no trait.
- **The melodica.** `tenor melodica` is a sound-alike once ranged, its parent by rule 2 among the
  melodicas and harmonicas (a maker's model page ranges that model only: the Hohner, Suzuki and
  Hammond pages the Melodica page cites). `pianica` and `triola` follow the makers' ruling;
  `claviola` (the audit: "listed on Wikipedia free reed template only") and `accordina` (the H-S
  list's "Accordina (instrument)") are each decided on their own page, as an ALIAS of a catalog
  entry on a cited page giving the name to it, a row of their own, or DROP; `claviola` is also on
  #85's list of the keyboard category's unfetched names, so this row decides it for both families.
  `richter harmonica` is an ALIAS of `harmonica` on a cited page giving it as the diatonic
  harmonica's name (a Richter layout is a tuning, no trait).
- **Pitch pipes.** `pitch pipe` and `chromatic pitch pipe` are one instrument or two (rule 8,
  decided on the Pitch pipe page); "F-F pipes and C-C pipes" names no octave, and the page's
  sentence is cited to a retailer under `{{Unreliable source?}}` (range ruling 10).
- **The sheng and its kin.** `soprano sheng`, `alto sheng`, `tenor sheng` and `bass sheng` are
  sizes of the catalog's `sheng` (parent ruling 4), each ranged by its own section of a source (the
  tenor's two ranges are none: range ruling 6); the audit's "DERIVED" alto and tenor ranges are not
  sources. `sho`, `u`, `yu`, `saenghwang`, `lusheng` and `qeej` are pipe mouth organs: a
  sound-alike of `sheng` by rule 1 where the source relates them ("derived from the sheng"), else by
  rule 2's third mechanism, once ranged; the sho's *aitake* are chords, and its infobox's "441.21"
  is no class (Global Constraints). `khene` (the Khaen page) follows the drone ruling: a SHIP
  `_droned_reed` only with its drone notes stated by a source for the instrument; drones the player
  holds per mode are WAIT `a sourced drone tuning` once ranged; its alias names `kaen`, `khaen`,
  `kehn`, `ken` and `kheng` follow it (rule 3), each on a cited page giving it as the khaen's name.
  `keluri` and `sompoton` (gourd mouth organs) are decided the same way, and `keledi`,
  `enkulurai`, `kadedek` and `engkerurai` follow `keluri`. `mangtong` ("one pitch each") follows
  range ruling 9.
- **The reed pipes.** `bawu` and `hulusi` follow the reed pipe ruling (422.31, 422.32): once
  ranged, each waits for its own build unless a source relates it to a catalog entry (rule 1). The
  Bawu page's "typically has a range of an eleventh ... from B to E" is hedged and has no octaves;
  its "the upper harmonics are gradually extinguished" is a trait no build makes. The hulusi's
  drones are decided by the drone ruling once its own build exists. `goofus` and `queenophone`
  follow `couesnophone`.

- [ ] **Step 1: Write half B's rows** to `build/batch-16-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-16-form-check.py build/batch-16-half-b.tsv` and
  `uv run python -I build/batch-16-quote-check.py build/batch-16-half-b.tsv`.
  Expected: `41 rows;` and the counts, then `bad: []`, exit 0; then the windows-1252 list,
  `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-16-half-b.tsv >> plans/data/instrument-audit/batch-16.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `67 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-16.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-16-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-16-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted((half_a | half_b) - set(audit_names)))
print('twice:', sorted({name for name in half_a | half_b if audit_names.count(name) > 1}))
print('extra:', sorted(set(audit_names) - half_a - half_b))
"
```
  Expected: `missing: []` and `twice: []`. `extra:` lists only the alias rows' audit lines (13
  distinct lines, the 13 "Aliases" lines of `free-reeds.md` the Spec line names: 6 for half A and
  7 for half B), because an alias row's `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-16.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 16's verification sheet, the mouth-blown free reeds (harmonicas, mouth organs and reed pipes)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The mouth-blown free reeds

**Files:**
- Modify: `free_reeds.py` (new builds after half A's; `_droned_reed`, `_mouth_reed`'s `cents` and
  `footages`, and `_accordion`'s `footages` if Task 3 did not add it, each only if a row needs it),
  `free_reed_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-16.tsv`'s half-B rows, Task 3's tables, and `build/batch-16-code-check.py`.
- Produces: the finished family; and, as rows need them, `_droned_reed(*, low_pass: float, drones:
  tuple[tuple[float, float], ...]) -> Instrument` and `_mouth_reed(*, low_pass: float, breath:
  float = 0.03, cents: float = 0.0, footages: tuple[float, ...] = (8.0,)) -> Instrument` in
  `free_reeds.py`, with the values the drone, detune and reed-set rulings give.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `NEW_FREE_REED_NAMES`,
  `FREE_REED_SOUND_ALIKE_PARENTS`, `MECHANICAL_FREE_REED_NAMES`, `FREE_REED_DETUNES`,
  `FREE_REED_REED_SETS`, `FREE_REED_HELD_BACK` and the alias parameters, after half A's, as in
  Task 3 Step 1; fill `FREE_REED_DRONES` with every SHIP and then SOUND_ALIKE row whose `drones`
  is not `none`, in catalog order, and add each to `NOT_PERIODIC_AT_THE_NOTE` with the drone
  ruling's reason. If three or more sheng sizes ship, add them to
  `test_sized_families_descend_from_highest_to_lowest`'s parameters, highest first. If
  `_droned_reed` is added (only with the row that ships it), add
  `test_a_droned_reed_keeps_its_chanter_and_adds_the_drones`: for each SHIP entry in
  `FREE_REED_DRONES`, the instrument's sources are `tone`, `breath` and one `drone_<n>` per drone,
  each at its sourced hertz and level 0.3, and its `tone_wave` is `harmonica`'s (the chanter is
  `_mouth_reed`). If `cents` or `footages` is added
  to `_mouth_reed`, add `test_mouth_reed_cents_and_footages_change_only_when_given`: through
  `instruments.entry('harmonica').build.func`, `cents=12.0` gives a `chorus` source at 12.0 cents,
  `footages=(8.0, 4.0)` gives the reed-set ruling's `tone_wave`, and the defaults equal
  `instruments.get('harmonica')`.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command with
  `or droned or sized_families or mouth_reed` added to its `-k` expression.
  Expected: the new cases fail with `KeyError: no instrument named ...` (and, before a keyword or
  builder exists, its test with a `TypeError` or `AttributeError` naming it).

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes, aliases after half A's aliases, under second
  section comments naming the sheet ("Batch 16's free reeds: the mouth-blown free reeds"). A
  droned build carries its `Drones:` passage in its comment. Add `_droned_reed`, `cents` or
  `footages` only if a row needs it, with the rulings' values marked as sound design and the entry
  they are copied from.

- [ ] **Step 4: Run the suite and check the code against the whole sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`, then
  `uv run python -I build/batch-16-code-check.py plans/data/instrument-audit/batch-16.tsv`, then
  Task 3 Step 4's earlier-builds command.
  Expected: PASS, then `matches 67 rows`, then `changed: []`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 16's mouth-blown free reeds, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a free reeds
  paragraph with its count, naming `free_reeds.py` and `free_reed_sound_alikes.py`, with examples,
  in the keyboards paragraph's form, saying that a free reed is a tongue swinging through a closely
  fitting slot, blown by bellows or the mouth, that a layout, a key, a tuning, a chord, a register
  or a size is no trait, that a sound-alike gives its own sourced range, and, if any shipped, that
  a sourced detune or octave reed set is a sound change and a droned reed sounds its sourced drones.
  Say that `winds.py` now holds only the saxophones.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `free reeds`
  row's count and examples, the sound-alike modules sentence and its total, and any sentence naming
  `winds.py` as the free reeds' module).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts, and the `Tag.MECHANICAL` sentence if a mechanical free reed shipped).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 16
  done, pointing at this plan and `batch-16.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 16 DONE";
  - batch 16 done, with the sheet's counts by status and the family's growth, the module move
    (`free_reeds.py`; `winds.py` keeping the saxophones), the boundary rulings, any droned reed,
    detune, reed set or mechanical free reed shipped, `FREE_REED_HELD_BACK`'s names, and the
    branch's base SHA (`d4c1e3eb`, batch 15's tip);
  - the audit's unclosed gaps and the out-of-scope names (the side-blown sneng among them), as a
    later pass;
  - the hand-offs: `chromelodeon`, `reed organ` and `orchestrelle` decided here (`reed organ` by
    the controller's ruling that #70's "must not decide them again" binds only `orchestrion`);
    `jaw harp` left as `batch-1.tsv` decided it; the batch 16 paragraph quotes batch 13's "must
    not decide them again" and records that it binds `orchestrion` only (batch 13's own sentence
    is left as written); each row dropped to organs, a beating-reed family,
    plucked idiophones, electromechanical or electronic, for a later pass of that family; the alias
    names decided here (so no later batch decides `khaen` and its spellings, `bayan`, `melodeon`,
    `pianica`, `triola`, `claviola` or `accordina` again);
  - a "Plan (batch 16)" line, the Status line, and the next batch named: harps (batch 17).

  Add #86 (the highest item is #85), "Sound Engine: The Owner's Checks on Instrument Catalog Batch
  16 — TODO". Use #85's form, place it directly after #85, and give it the Priority "(before the
  harps batch builds on the same catalog)". Its **Listen** section (`build/instruments/free
  reeds/`) covers the new builds (each droned reed against `harmonica`, whose chanter it shares),
  then the sound-alikes beside their parents (each with `sound_changes` beside the parent it
  changes), then the aliases. Its **Calls to confirm** are:
  - every WAIT, by reason, with names;
  - the module move (`free_reeds.py` out of `winds.py`, the process-state listing moved with it)
    and its `changed: []` record, and whether `winds.py` should be renamed now that it holds only
    the saxophones;
  - the boundary rulings, each row they moved, and the Hornbostel–Sachs codes this plan checked
    (412.131, 412.132, 422.31, 422.32, 412.12; the Bawu listed under 412.131 against the class
    text, the Shō infobox's 441.21 no class);
  - the reed organ ruling, recorded (no question): the controller ruled `reed organ` a half-A
    candidate decided here, since a DROP naming a family is a hand-off (batch 15's `claviharp` and
    `dolceola`), and #70's "so the keyboards and free reeds batches must not decide them again"
    is right for `orchestrion` and a slip of the pen for `reed organ`, as #70's batch 16
    paragraph records;
  - a free reed as a sound-alike (layouts, keys, tunings, chords, registers, sizes, materials and
    colour words no trait; a SHIP only for sourced drones; the sound changes only for a sourced
    detune, octave reed set or drones);
  - the parent ruling (the source's relation first, the only way to another family's parent or a
    reed pipe's; else the same mechanism's nearest lowest note, the pipe mouth organs to `sheng`),
    and each sound-alike's parent;
  - the range ruling (one source states both ends; a written range only with its stated
    transposition; a key, a count, a width, a scale, a hedge or a general rule no range; a model's
    page ranges that model only; a bare name of several sizes with none standard waits; nothing
    below A0 or above C8), and every derived range;
  - the detune ruling (the 2% rule against unsourced catalog cents, `_mouth_reed`'s `cents` if
    added), the reed-set ruling (`footages`, the 16-level cut as sound design), the drone ruling
    (`_droned_reed` if added, its copied drone level) and the reed pipe ruling (`its own build (a
    free reed sounding a fingered pipe)`);
  - the mechanical ruling and each tagged or waiting self-playing free reed;
  - generic, ambiguous, makers', one-off, technique and unsourced rows, with the words "no fetched
    source describes it" on every row whose page was not found;
  - `FREE_REED_HELD_BACK`, the guard for every non-range wait, and the helper test that exercises
    every guard on a real build;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - the size chain (the sheng sizes if three or more shipped; would you chain the catalog's three
    melodicas, whose ranges are unsourced?);
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): the 13 earlier entries' missing
  source comments; any existing range or build a sheet's source contradicts (the leads in Global
  Constraints: the Sheng page's soprano G3–F♯6 against the catalog's `sheng` G3–A6; the
  `concertina` titled English); the unsourced "typical of the common keys" sentence now in both
  `winds.py` and `free_reeds.py` (#84); the Hornbostel–Sachs list's Bawu under 412.131 and the Shō
  infobox's 441.21 (Wikipedia's, not the catalog's); the 17 third-party `speech_recognition`
  DeprecationWarnings as #85 records them. Then **Follow-ups**: the audit's gaps; ranging the range
  WAITs from maker, museum and scholarly sources; checking the 13 earlier entries against sources;
  the engine changes that unblock the waits, most rows first (a free reed sounding a fingered pipe,
  a spectrum that changes with the note, a second detuned reed set). Then **Incidents and
  process**, as #85 has them.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries())); print(i.names(tag='mechanical'))"`
  and `uv run python -I build/batch-16-form-check.py plans/data/instrument-audit/batch-16.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only -W default tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-16-code-check.py plans/data/instrument-audit/batch-16.tsv
uv run python -I build/batch-16-quote-check.py plans/data/instrument-audit/batch-16.tsv
```
  Expected: everything passes; the only warnings are the 17 known `speech_recognition`
  DeprecationWarnings (#85; any other is a new finding, understood before going on); `matches 67
  rows`; and `bad: []`. The `build/instruments/free reeds` folder is the one to listen to; the
  owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 16 of the instrument catalog (free reeds), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch in
turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78). The
pre-push hooks take about 40 minutes, and nothing in the working tree may change while they run.

**Order:** the controller's shared files (and the plan's commit), then Tasks 1, 2 and 4 in
parallel. Task 3 follows Tasks 1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows
Tasks 3 and 4, and Task 6 comes last.

**Corrections to batch 15's plan carried here:**
- Batch 15's plan quoted #70 as saying "the keyboards and free reeds batches must not decide them
  again" of `orchestrion` and `panharmonicon`. #70 says it of `orchestrion` and `reed organ`
  (`panharmonicon` is a `batch-13.tsv` WAIT that sentence does not name). This plan quotes #70
  word for word; the controller ruled the sentence binds `orchestrion` only, so `reed organ` is a
  hand-off decided here.
- Batch 15's guards (`KEYBOARD_HELD_BACK`, the 16' and partials tables) passed only because their
  tables were empty until the final review (`8173b3ec`) tested two helpers on real builds; this
  plan's Task 1 tests every guard's helper on a real build from the start, the held-back check
  included.
- Batch 15's quote check read pages as UTF-8 only and checked only SHIP and SOUND_ALIKE rows, so it
  passed vacuously on a sheet of waits and drops (#85, "Bugs to report"); this plan's decodes
  windows-1252 when UTF-8 fails (never lossily), matches HTML pages' visible text, and checks every
  quote of every row against the saved pages or a named ledger file.
- Batch 15's range ruling 4 mixed the model-page rule with the several-sizes rule; this plan
  splits them (ruling 4, a model's page ranges that model only; ruling 6, a bare name of several
  sizes with none standard waits), as #85 names them.
- Batch 15's verification steps expected "no warnings" where the runs showed the 17 known
  `speech_recognition` DeprecationWarnings (#85); this plan's steps name them and treat any other
  as a finding.
- Batch 15's research steps let a WebFetch read stand until a review refused it (#85,
  `nickelodeon`); this plan requires every cited page saved raw, a refused page through the
  Internet Archive's copy.
