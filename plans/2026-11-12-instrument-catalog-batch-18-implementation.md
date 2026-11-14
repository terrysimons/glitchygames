# Instrument catalog batch 18 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the struck strings family from the audits' candidates. The family holds the
instruments whose strings are set sounding by a beater in the player's hand (Hornbostel–Sachs
suffix -4, "Hammers or beaters"): the hammered dulcimers and cimbaloms (struck box zithers,
314.122-4), the struck musical bows (311.12, the catalog's `berimbau`) and the other struck
zithers and string drums. Each instrument gets a cited source for its name, its sound, how it is
struck and its range, and either sounds unlike every other entry or is a listed sound-alike of the
one it sounds like. The rest become aliases, wait for an engine feature or a source, or are dropped
with a reason.

**Architecture:** As in batches 3 to 17, a verification sheet (`batch-18.tsv`) decides every
candidate before any code is written. The family's 5 entries are all that is left in
`strings.py` (82 lines) since batch 17 moved the harps out, and every other family has a module
named for it and a sibling sound-alikes module. So `strings.py` is renamed, unchanged, to
`struck_strings.py` (`git mv`, so its history follows), and no `strings.py` is kept: the moved
table becomes `_STRUCK_BUILDS`, and `STRUCK_STRINGS` becomes `_STRUCK_BUILDS + STRUCK_SOUND_ALIKES`,
with the sound-alikes in a new `struck_sound_alikes.py` (named as `bowed_sound_alikes.py` and
`plucked_sound_alikes.py` are). The catalog's two struck builders, `_hammered(*, ring_seconds,
low_pass)` (a plucked series struck near the string's end, two detuned courses) and `_berimbau()`
(a struck bow), take only sound-design values (no source behind any), so a new dulcimer or bow
with no other cited trait is a sound-alike, `builder` "unchanged". This batch adds no builder, no
keyword and no `sound_changes`: no foreseen struck-string trait has a sourced number a builder
takes, and a trait the builds cannot make (a rattle in the beating hand, a bouncing hammer's
tremolo, a glide from a bent bow) means the row waits. A new guard, `STRUCK_HELD_BACK`, holds every
name the sheet holds back for any reason but a sourced range. The sheet and the code each come in
two halves, as explicit lists: the hammered dulcimers and hammered zithers, then the struck bows,
string drums and the rest. The controller writes the names file, the candidate lists and the three
check scripts before anything is dispatched, so the two sheet halves are researched at the same
time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `plucked`, `plucked_series`,
`struck`, `Course`, `Partial`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all; its audit table counts the struck strings audit's 14 rows, and its batch order,
"One batch per family", reaches struck strings after harps, as #70 names it: "Next: struck strings
(batch 18)"). Batch 17's plan (`plans/2026-11-12-instrument-catalog-batch-17-implementation.md`)
and its owner's checks (`plans/future-features.md` #87) are this plan's template and its ledger:
its controller step, its quote check, its held-back guard, its module move, its two parallel
halves and its code check carry over, with the corrections listed at the end of this plan. Batch
4's plan (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) holds the pitched
sound-alike and strict range rules, the before-and-after build record, and the sheet that handed
`fotdella`, `nondo` and `quijongo` here; batch 11's holds the balaban rule (a cited trait the
build cannot make means the row waits); batch 15's holds the keyed struck strings
(`dolceola`, `dulce melos`: keyboards). This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-18-implementation.md`. The branch is
`feat/instrument-catalog-batch-18`, made from batch 17's tip, `9a8dcfbe` (batch 17's final review
fixes); Task 6 records that SHA in #70. The candidates come from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `struck` (13, every one from the round-2 audit
  `struck-strings.md`: `khim`, `hackbrett`, `santoor`, `yanggeum`, `chang`, `pantaleon`,
  `tambourin a cordes`, `utogardon`, `zhu`, `malunga`, `ground bow`, `marxophone`, `dolceola`;
  the audit's 14th row, `chapman stick`, has family "plucked strings");
- the `round-1/merged-missing.tsv` rows whose `family` contains `struck` (3: `harmonic canon`
  "struck strings (or plucked strings)", `harmonic generator` "struck strings", `marxophone`
  "new family: fretless/box zithers (or struck strings)", taken as batch 17 took `kithara
  (partch)`'s "plucked strings (or harps)");
- five hand-offs that no family has decided, as batch 9 took its hand-offs as candidates:
  `fotdella`, `nondo` and `quijongo` (`batch-4.tsv` DROPs naming this family: «Struck strings.»,
  «Struck, not plucked: struck strings» and «Struck with a stick: struck strings (with the
  catalog's berimbau)»), and `celestaphone` and `pianoharp` (`missing-categories.md`: «marxophone,
  celestaphone, pianoharp -> struck strings»; round-1 rows with family "new family:
  fretless/box zithers", which the spec rejected as a family).

Together: 15 unique audit names (`marxophone` is in both lists) and 5 hand-offs, none of them a
catalog name or alias (checked for this plan at `9a8dcfbe`: the catalog holds 704 entries and 125
aliases, 829 names, and no struck strings alias at all). So there are **20 candidate names**
(counted for this plan, the controller recounts). The struck strings audit's alias lines whose
left-hand names are no catalog name and whose target or note names a candidate or a catalog
struck string propose **47 alias names** (each name as a catalog name: hyphens and slashes become
spaces or separate names):
- "yoochin (Mongolia), yangzi/rgyud-mang (Tibet), dan tam thap luc (Vietnam), santouri/santouri
  (Greece), dulcemele, dultzimar, darushimaa, hakkebord, hakkebraet, hakkebrett, hackbraede,
  hammarharpa, oprekelj, cimbale, cimbule -> hammered dulcimer or cimbalom per same page" (16:
  `yoochin`, `yangzi`, `rgyud mang`, `dan tam thap luc`, `santouri`, `dulcemele`, `dultzimar`,
  `darushimaa`, `hakkebord`, `hakkebraet`, `hakkebrett`, `hackbraede`, `hammarharpa`, `oprekelj`,
  `cimbale`, `cimbule`);
- "cimbal (Czech/Slovak/Croatian), cymbaly (Poland), tsymbaly (Ukraine/Belarus), zymbal, tsimbl
  (Yiddish), tambal (Romania), chimbaly (Russia) -> cimbalom (…)" (7);
- "tympanon (France), tiompan (Ireland), salterio (Iberia/Italy) -> hammered dulcimer family (same
  page); salterio is also a psaltery name, so it is ambiguous" (3);
- "hudie qin -> butterfly dulcimer; yangqin page says it is a related butterfly zither (not an
  alias exactly)" (1: its note names the catalog's `yangqin`);
- "Xinjiang yangqin -> chang (one encyclopedia entry, weak source)" (1: `xinjiang yangqin`);
- "ttun-ttun, salmo, chicoten, toum-toum -> tambourin a cordes" (4: `ttun ttun`, `salmo`,
  `chicoten`, `toum toum`);
- "umbulumbumba (mbulumbumba) -> berimbau (…)" (2); "urucungo, madimba lungungu -> berimbau (same
  page)" (2); "hungu: a Kimbundu name for a gourd bow like the berimbau (…)" (1);
- "kalinga/galinga, gayumba, tumbandera, tingo-talango, angbindi -> ground bow" (6: `kalinga`,
  `galinga`, `gayumba`, `tumbandera`, `tingo talango`, `angbindi`);
- "gunga/berra-boi, medio, viola/violinha: berimbau sizes (three tones); candidates for 3 catalog
  entries" (4: `gunga`, `berra boi`, `medio`, `violinha`; `viola` is the catalog's bowed viola,
  so it is no row, and Task 4 decides the high bow under `violinha`).
The line "santur (Iran), yangqin, cimbalom: already catalog entries" names only catalog names: no
row. No other audit has an alias line naming a struck string (checked with grep over every
`*.md` in the folder and `round-1/`). The round-1 alias tables are not used, as no earlier batch
used them. So the sheet will hold **67 rows** (20 candidates and 47 alias names). An alias row's
`audit_name` is its audit line as written above (its URL, if any, left out).

The hand-offs from earlier sheets (checked: `batch-1.tsv` to `batch-17.tsv` with a csv read for
each candidate, each alias name and `struck strings` in the notes, and `plans/future-features.md`
#70–#87):
- `fotdella`, `nondo`, `quijongo`: candidates (above), each quoting its `batch-4.tsv` DROP. A DROP
  naming a family is a hand-off that family's batch decides (batch 15's `claviharp` and
  `dolceola`, batch 16's `reed organ`, batch 17's two ngonis).
- Already decided, and candidates: each row is DROP, its notes beginning "Already decided:" and
  naming the sheet whose status stands and that status (none is a catalog name or alias, so the
  code check's last branch applies):
  - half A: `chang` (`batch-17.tsv` DROP, harps: «an ambiguous name», a Persian angular harp, the
    Uyghur and Uzbek dulcimers and an Afghan jew's harp; #70: «the struck strings batch treats the
    name as already decided: DROP»); `dolceola` (`batch-15.tsv` WAIT `a sourced range`, keyboards,
    after `batch-4.tsv` dropped it there: its keys strike its strings);
  - half B: `harmonic canon` (`batch-4.tsv` WAIT `a sourced range`, plucked strings: «played with
    fingers or picks, or, in some cases, unique mallets»).
- Decided elsewhere, not candidates, no row: `dulce melos`, `lutheal` and `tangent piano`
  (`batch-15.tsv` WAITs, keyboards: keys strike their strings); `claviharp` (`batch-15.tsv` WAIT);
  `musical bow` (`batch-4.tsv` WAIT `a sourced range`, the generic name); `uhadi` (`batch-4.tsv`
  WAIT), `umrhubhe` (`batch-4.tsv` WAIT `moving formants`), `ukeke` and `washtub bass`
  (`batch-4.tsv` WAITs), the bows batch 4 decided as plucked strings; `ektara` (`batch-4.tsv`
  WAIT, plucked); `chapman stick` and `harpejji` (catalog names in plucked strings; batch 4).
  Task 6 lists the bows in #88 for the owner (whether the struck ones belong here), never
  re-deciding them.
- #70 says of batches 15, 16 and 17 that no row was dropped to struck strings beyond batch 17's
  `chang` ("so the struck strings batch treats the name as already decided"). Batch 15 decided
  `dulce melos` («similar to a hammered dulcimer, but with the strings struck by hammers on keys»)
  as keyboards, not as a hand-off here.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, parentheses and hyphens go only in the title (`tambourin a
  cordes` titled "Tambourin à cordes", `ttun ttun` titled "Ttun-ttun"). A candidate keeps its
  audit name (the naming ruling of batch 12).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families),
  "with the existing player-facing splits kept where they already exist". The struck strings
  family holds the strings a beater in the player's hand sounds; the boundary rulings below
  decide each row.
- Hornbostel–Sachs, every code this plan relies on checked against Wikipedia's raw wikitext on
  2026-11-13 (`Hornbostel–Sachs` and `List_of_chordophones_by_Hornbostel–Sachs_number`):
  - 311.1 "Musical bows – The string bearer is flexible (and curved)"; 311.12 "Heterochord
    musical bows – The string is of separate material from the bearer"; 311.121
    "Mono-heterochord musical bows", 311.121.1 "Without resonator", 311.121.2 "With resonator"
    (311.121.21 "With independent resonator", 311.121.22 "With resonator attached", each with
    .1/.2 "Without/With tuning noose"); 311.122 "Poly-heterochord musical bows"; 311.2 "Stick
    zithers"; 312 tube zithers; 313 raft zithers.
  - 314.1 "True board zithers"; 314.122 "With resonator box – the piano is part of this
    subdivision"; 314.21 "Ground zithers"; 314.22 "Harp zithers".
  - 321.322 "Necked box lutes" (batch 17's check).
  - Suffixes: "An 8 indicates that the instrument has a keyboard attached, while a 9 indicates the
    instrument is mechanically driven" (the main page); the chordophone list's "'''4''': Hammers or
    beaters", "'''5''': Bare hands and fingers", "'''6''': Plectrum", "'''8''': Keyboard". The
    Hammered dulcimer, Yangqin and Santoor infoboxes write «314.122-4» («Simple [[chordophone]]
    sounded by hammers»). A suffix is written when a fetched source for that row gives it or names
    the beater in words ("struck with two sticks": -4).
  - Traps found while writing this plan: the Santur infobox's `hornbostel_sachs` is empty and its
    range is an image («[[File:Santur Range.png|130px|center]]», not quotable); the Cimbalom
    infobox gives no class and «Various (see … below)» as its range; the Berimbau page gives no
    class. The Ground bow page's other names («''kalinga'' or ''galinga''») are cited.
  A worker who finds a code that a fetched list does not hold reports it to the controller before
  any row relies on it. No other code is assumed. A class is written from words naming what
  sounds and how, never from a relation ("based on", "like the", "a type of"): that is a parent
  (#87's `gravikord`, whose 323 was inferred from «based on the West African kora»).
- "Every name, range and description checked against a source cited in the code … A range that no
  source gives is the instrument's documented playable span from a maker or museum, or the entry
  waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict"). This
  plan's range ruling is below. A row with no sourced range is WAIT, `waits_for` `a sourced
  range`, and **the range is checked first**, before any engine limit or other trait (batch 13's
  reversals): a row with neither a range nor a buildable trait waits for the range, its notes
  keeping "Engine limit, once ranged: …".
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry, sharing
  the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the same
  instrument) stays an alias." A sound-alike is pitched exactly when its parent is (every struck
  string entry is pitched), and a pitched sound-alike gives its own sourced range (batch 4). This
  batch's sound-alikes carry no `sound_changes` (the sound-alike ruling).
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as an
  approximation. The spec's table binds this family through "sympathetic strings" and "sub-audio
  fundamentals". Earlier batches added the other names a WAIT may give: a pitch LFO (vibrato), a
  pitch LFO (portamento between notes), an amplitude LFO, a pitch and amplitude LFO (batch 2),
  filter resonance, a filter envelope, moving formants (batch 6); a pitch moving through a phrase
  (batch 4's `washtub bass`); a buzzing membrane (batch 5); a sourced drone tuning and its own
  build (batch 7, 12); a range above C8 (batch 10); a sourced detune and a sourced footage (batch
  13); a sourced reed and bore (batch 14); a sourced partial series (batch 15); `its own build
  (rattles)` and `its own build (a drummed resonator)` (batch 17). This plan adds no new wait
  name; `its own build (<the trait>)` names any trait no builder makes. What the engine has:
  `plucked` (one harmonic series, `ring_seconds` down to `sustain`, up to two more `courses`, a
  pick noise, a fixed low or high pass, drive) and `struck` (fixed partials, each with its own
  ring, a mallet noise with a low pass); no LFO, no rattle, no retriggered strike, no glide, a
  series that does not change with the note.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not builds.
- Reuse `_hammered` and `_berimbau` under their current names; add no builder or keyword (the
  sound-alike ruling). A row whose source states a trait `plucked` or `struck` could make with a
  sourced number is reported to the controller before its half's code task (the SHIP ruling).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the sheet,
  in every row of every status, is verbatim from a page the worker fetched and saved, or from a
  committed file the notes name (an earlier sheet, an audit file, #70 or the spec), and the quote
  check finds each one. No request carries the owner's email or any personal data, in a header, a
  URL or a payload (#78).
- Sources: an unsaved WebFetch read is a lead, never a source (#85's `nickelodeon`): every cited
  page is saved raw with `curl -fsS -L` (for Wikipedia, the `action=raw` wikitext), straight to
  `build/batch-18-pages/<name, spaces as hyphens>--<n>.txt`, never to a scratch copy named by the
  page's title (#87: macOS's filesystem is case-insensitive, and `Welsh_harp` overwrote
  `Welsh_Harp`). `-f` matters: without it curl saves Wikimedia's "Wikimedia Error" page with exit
  0. **A 404 or any other error page is never saved** (#87's ruling): a page that does not exist
  goes in the row's notes ("returned 404"), and the quote check refuses a saved error page. A 429
  ("Too Many Requests": 11 of 24 fetches while writing this plan) is waited out and retried, never
  saved; a page that keeps refusing curl (403, 429) is fetched from the Internet Archive's copy
  (`https://web.archive.org/web/<date>id_/<url>`, the `id_` form returns the page as archived),
  saved, and cited by its archive URL. A saved page holding a private person's contact data (an
  email address, a phone number) is redacted by the controller before any row cites it, and no
  row quotes it (#86's `engkerurai`, #87's gravikord maker); an institution's public contacts (a
  museum's switchboard or department address) are not personal data and stay (#87's Penn Museum
  page). The quote check lists every saved page holding an email address, for the controller to
  judge. Uncited lines (range ruling 10), blogs, forums, retailers' listings, hobbyists' pages
  (the Oddmusic gallery among them) and musicbrainz mirrors are not sources; a scholarly article
  (a journal paper, a conference paper, a museum's or university's publication) is.
- Code comments name committed files (`plans/data/instrument-audit/batch-18.tsv`), never the
  gitignored `build/` files (batch 9's fix), and never describe a builder, keyword or table use
  that does not exist (batch 16's final review).
- Data is never evaluated as code: a check script reads a literal with `ast.literal_eval`, never
  `eval` or `exec`.
- The 5 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 5. An existing entry changes only for a cited bug, and not in this batch:
  the 5 carry no source comment, so a range or build that a fetched source contradicts is reported
  in #88 for the owner (batches 10 to 17's rule). Leads already seen while writing this plan, for
  the workers who fetch those pages to check under range ruling 10: the Cimbalom page gives «The
  Schunda tuning system established a standard pitch range of four [[octave]]s plus a major 3rd;
  extending from C to e′′′» (cited; C2–E6) against the catalog's `cimbalom` E2–A6, and its image
  captions («a range of AA to a′′′», «E2-E6, + D2 string») are single objects; the Santur page's
  range is an image; the audit gives the hammered dulcimer only «three octaves» and the yangqin
  «slightly over four octaves» against `hammered dulcimer` D3–E6 and `yangqin` G2–A6; the berimbau
  page gives tunings, no octaves, against `berimbau` A2–C3. Task 1's before-and-after record of
  every entry checks that the move changes nothing, and Tasks 3 and 5 repeat it.
- The family is not in the catalog test's `HARMONIC_FAMILIES` (checked: harps, keyboards and
  organs are; struck strings are not), so `test_harmonic_instruments_sound_their_note` does not
  run on these entries. A new struck string entry is checked by the render test across its range
  and by the sound-alike test. Task 6 reports the gap in #88; this batch does not change it.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns, a module docstring's first line included: batch 14's first line
  was 123 columns), basedpyright and ty clean, 100% coverage. "I don't like short abbreviated
  variables." "explicit is better than implicit." "Whenever you see warnings thrown by a test, you
  should understand why it's happening and be concerned": a warning is a finding, and it must be
  understood before going on. #86 and #87 record 17 DeprecationWarnings under `-W default` from
  the third-party `speech_recognition` (it imports `aifc`), filtered on purpose in
  `pyproject.toml`; a report says "the 17 known speech_recognition warnings, no other" when that
  is what it saw, never "no warnings".
- Process: run `nox -s lint-docs` on its own, never while a test run is going (#84). Two load
  flakes are known: #84's
  `tests/engine/test_game_engine.py::TestReplayRestartExitStatus::test_a_status_no_exit_code_names_is_passed_through`
  (native run) and #86's `test_command_crash_boundary.py` signal test, case [2]. If one of them
  fails, rerun it alone, then the whole suite once; record it in #88 either way. Any other failure
  is a finding.
- Commits as batches 4 to 17: `SKIP=replay-metrics git commit`, with the subject `Plans: …`,
  `Instrument catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76), so copy each commit message from this plan, never from memory.
  Write no `.md` file beyond those Task 6 names. Never use `git stash`: the stack is shared with
  other worktrees and sessions (#80). Set work aside with a temporary commit instead. A task that
  changes nothing makes no commit, and its report says so.

## Review Focus

1. **A course count, a width, a tuning or an image read as a range.** Dulcimer pages give "25
   bridges, 4 strings each", "about three octaves", "slightly over four octaves", "three
   octaves", "tuned tonic and dominant", "two tones an octave apart", the musical bow's «two
   fundamental notes … about a whole tone», and the Santur infobox's range as an image file. Range
   ruling 5 makes none of them a range; the form check needs `Range:` with a quoted passage the
   quote check finds on the saved page; the code check compares every shipped range with the
   sheet.
2. **One model's, one size's or one object's range given to the bare name.** The khim's page
   gives the «7-note» khim's notes, the berimbau's three sizes are «Gunga», «Médio» and «Viola»
   with the names swapped between sources, the hackbrett is sold in Salzburg chromatic and
   diatonic models, and the Cimbalom page's photo captions each name one maker's instrument. Range
   ruling 4 ranges a model's or object's row only, ruling 4b ranges a size named in a cited sentence
   only that size, ruling 6 makes a bare name with several sizes and none called standard wait.
3. **A keyed or plucked string built as a struck string because of a hammer or a "dulcimer".**
   The dolceola, dulce melos and fotdella strike their strings from keys or pedals (keyboards,
   -8); the harmonic canon and the appalachian dulcimer are plucked; the Chapman Stick is tapped
   under a pickup; a "hammered" word on a page names no beater in the hand. The boundary rulings
   decide them, the form check needs an `hs` matching `(31[1-4]|321)(\.[0-9]+)*-4` on a sound-alike
   (no -8) and "Parent (rule 1):" for any parent outside its mechanism's rule-2 set.
4. **A cited trait the build cannot make shipped as a plain sound-alike, or a guard that passes
   only because its table is empty.** The audit names the malunga's rattle «in the same hand», the
   marxophone's «mandolin-like tremolo» from bouncing hammers, the ground bow's «glissando» from a
   bent stick, and the tambourin's strings sounding together as a drone. The sound-alike ruling
   makes each a WAIT once its source states it; the reviewers read each sound-alike's quoted sound
   passage for such a trait. Task 1 runs the guards' helpers' real-build test (batch 17's, both
   ways) and shows each guard failing on a wrong table.
5. **A name decided twice, or an ambiguous one kept.** `chang` (batch 17's DROP) beside `xinjiang
   yangqin`, `hackbrett` beside `hakkebrett`, `santoor` beside `santur` and `santouri`,
   `cimbal`, `cimbale` and `cimbalom`, `gunga` with `berra boi`, `medio` and `violinha` (whose
   names the Berimbau page swaps: «''Médio'' (others say ''Viola'')»), `salterio` (also a
   psaltery), `tympanon`, and `kalinga` with `galinga` are each decided once. Rule 8 decides
   duplicates, the ambiguous ruling drops a name its sources give to two instruments, past or
   present, the code check finds every name exactly once, and the step checks list every candidate
   once.

---

## File Structure

- Rename `src/glitchygames/audio/instruments/strings.py` to `struck_strings.py` (`git mv`),
  unchanged but for its table's name, `STRUCK_STRINGS` as the concatenation, and its docstring's
  sound-alikes sentence. No `strings.py` remains: only `registry.py` imports it (checked with
  grep), so a re-export would be a module that holds nothing and that nothing needs.
- Create `src/glitchygames/audio/instruments/struck_sound_alikes.py`, holding
  `STRUCK_SOUND_ALIKES`.
- Modify `registry.py` (it imports `STRUCK_STRINGS` from `struck_strings`; its place in
  `FAMILY_TABLES` does not change), and every live docstring naming `strings.py`:
  `bowed_strings.py` lines 5–6, `harps.py` lines 5–6, the `instruments/__init__.py` docstring
  (line 179), and `aliases.py` (the batch's ALIAS rows, Tasks 3 and 5). `docs/architecture/sound.md`
  line 299–300 names `strings.py` too: Task 1 fixes it with the others, so no live file names a
  module that is gone. No process-state guard listing names anything in `strings.py` (checked
  with grep), so `tests/test_process_state_guard.py` does not change; Task 1 runs it.
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5).
- Create `plans/data/instrument-audit/batch-18.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring's family paragraph,
  `docs/architecture/sound.md`, `CLAUDE.md`, `plans/future-features.md` (#70 and a new #88), and
  the design's status line and "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #88):

- **The struck strings get their own module by renaming `strings.py`, with no re-export.** Every
  family a batch has grown since batch 4 has a module named for it (`bowed_strings.py`,
  `plucked_strings.py`, `harps.py`, `free_reeds.py`) and a sibling sound-alikes module that names
  it; `strings.py` holds only `STRUCK_STRINGS` and its two builders, and #87 asks "Should
  `strings.py` be renamed now that it holds only the struck strings". Keeping `strings.py` would
  leave the one family module not named for its family; keeping a re-export would keep a module
  nothing imports. The sound-alikes module is `struck_sound_alikes.py`, as the other string
  families' are `bowed_sound_alikes.py` and `plucked_sound_alikes.py` (not
  `struck_string_sound_alikes.py`), and the private table `_STRUCK_BUILDS`, as `_BOWED_BUILDS`.
  Task 1's before-and-after record of all 704 builds checks the move.
- **The boundary rulings.** A row's family is decided by what sounds and how, from its fetched
  source's words, with the Hornbostel–Sachs class those words imply:
  1. *Struck strings*: strings a beater in the player's hand sounds (suffix -4): the hammered
     dulcimers and cimbaloms (314.122-4), the struck box and board zithers, the string drums
     (the tambourin à cordes, struck with a stick), a struck lute (the utogardon, struck with a
     stick, whatever its body), and the struck musical bows (311.12, with the berimbau).
  2. *The cimbalom is a dulcimer*: the catalog's `cimbalom` is a hammered dulcimer (its page's
     short description: «Hammered dulcimer musical instrument»), in the dulcimers' rule-2 set with
     `hammered dulcimer`, `santur` and `yangqin`. A cimbalom name (`cimbal`, `tsymbaly`, `tambal`)
     is decided by which instrument its source gives it to: the concert cimbalom, the hammered
     dulcimer, or both (then ambiguous).
  3. *Keyed struck strings are keyboards*: a string struck by hammers that keys or pedals drive
     (suffix -8: the piano and the clavichord in the catalog, `dolceola` and `dulce melos` decided
     by batch 15, the fotdella's «each pedal bringing a padded hammer to strike a string … like the
     action of a [[piano]]») is DROP "belongs to keyboards (a keyed struck string): <its words>".
     A hammer the finger presses directly onto the string on a spring strip, with no key lever
     (the marxophone's «depressing spring steel strips that hold small [[lead]] hammers»), is
     struck strings unless its fetched source calls the strips keys or the instrument a keyboard
     zither; the row quotes the words either way.
  4. *Plucked zithers are plucked strings*: a zither plucked by the fingers or a plectrum (the
     harmonic canon, already decided; a chord zither strummed beside its hammers is decided by its
     melody strings) is DROP "belongs to plucked strings (a plucked zither): <its words>" when not
     already decided.
  5. *Musical bows*: a bow whose string the source says is struck (the berimbau's «Baqueta: small
     stick struck against the arame», the quijongo's «striking the string with a stick», the
     malunga, the ground bow's «may be struck by a stick or plucked») is struck strings, with a
     struck bow's parent `berimbau`. A bow its source says is plucked or strummed (the ukeke, the
     mouth bow) is plucked strings: DROP to that family. The bows batch 4 decided stay as it
     decided them (no row here; #88 lists them).
  6. *The tapped Chapman Stick is an electric instrument*: its strings are tapped by the fingers
     (no beater) and sound under a pickup, so it stays the catalog's plucked strings entry (as the
     electric guitars and batch 4's `harpejji`), and no row of this batch is parented on it or
     dropped here for it. An electric struck string whose own strings sound under a pickup is the
     struck string it is; one with no string of its own sounding is electronic.
  7. *Mechanically driven strings*: strings a motor or a mechanism sounds (suffix -9; the
     harmonic generator's «64 strings, 32 motors, keyboard» in the round-1 lead) are no hand
     beater: keyboards if keys drive it, else electromechanical or a one-off, by its fetched words.
  8. *Not struck strings by name*: a "dulcimer" that is plucked (the catalog's `appalachian
     dulcimer`, plucked strings), a "zither" with keys, and a "hammer" word on a page (a
     hammer-on, a "Hammer-Jammer" accessory) are decided by what sounds.
  9. *The `hs` cell* holds the class a fetched source gives (an infobox, or a sentence naming what
     sounds and how, quoted, with the code it implies, written from the classes and suffixes
     above), else `none`. A SOUND_ALIKE row's `hs` fullmatches `(31[1-4]|321)(\.[0-9]+)*-4`.
- **A struck string is a sound-alike unless a cited trait sets it apart.** `_hammered` is
  `plucked` over `plucked_series(count=24, decibels_per_octave=4.0, pluck_position=0.12)` with two
  detuned courses, a ring time and a low pass, every value sound design; `_berimbau` is `struck`
  over three fixed partials. A row whose sources name no other trait is a SOUND_ALIKE (the parent
  ruling), `builder` "unchanged". A string count, a course count (two, three or four strings to a
  course), bridges, crossed or chromatic stringing, a tuning or scale, a string material (brass,
  steel, silk, gut), the beaters (bamboo, leather-tipped, cotton-wound, a stick, a coin or stone
  held against the bow string as the berimbau's «dobrão»), dampers, a size, the body (trapezoid,
  butterfly, gourd, coconut, a hole in the ground), a maker, a region or a colour word ("soft",
  "bright", "delicate", "angelic") is no trait, unless a fetched source names an effect on the
  sound with the numbers a builder keyword takes. A trait the engine cannot make is WAIT `its own
  build (<the trait>)` or the spec's or an earlier batch's feature name, with the source quoted: a
  rattle shaken by the beating hand (`its own build (rattles)`, batch 17's name: the malunga's
  «mai misra», a caxixi the source makes part of the instrument), a hammer that bounces and
  restrikes while held (`its own build (a bouncing hammer)`: the marxophone), a pitch the source
  says glides while the note sounds as the instrument's way of sounding (`a pitch moving through a
  phrase`, batch 4's: the ground bow's bent stick, if its page makes it the instrument's sound
  rather than what a player «can» do), strings that always sound together as a drone chord
  (`a sourced drone tuning`, batch 7's, when its tuning is unsourced; a sourced one goes to the
  SHIP ruling), sympathetic strings (`sympathetic strings`). A technique a player «can» use (a
  roll, damping by hand, a glissando, opening and closing the gourd, pressing the stone against
  the string to raise a note) is how a player sounds the instrument, not its build. A trait a
  builder could imitate by turning an unsourced keyword (a longer `ring_seconds` for a
  three-string course, a darker `low_pass` for leather beaters) is not made by the build: batch
  11's contraforte and the balaban rule.
- **The SHIP ruling.** This batch plans no SHIP and no `sound_changes`. A row whose fetched source
  states a trait in the numbers `plucked` or `struck` takes (a course detune in cents, a stated
  ring time at a stated note, a drone tuning in notes) is reported to the controller before its
  half's code task; the controller rules it, in a sheet fix commit, a WAIT `its own build (<the
  trait>)` or a SHIP with its rule and test added to this plan. The form check refuses a SHIP
  status until then.
- **The parent ruling.** A SOUND_ALIKE's parent is a catalog entry from before the batch (never a
  sound-alike), never one of `APPROXIMATING_NAMES`:
  1. The entry its own source relates it to ("similar to the [[hammered dulcimer]] or
     [[cimbalom]]", "It is a [[hammered dulcimer]]", "a gourd bow like the berimbau"), quoted in
     the notes after "Parent (rule 1):". When the passage names two catalog entries, the first
     named is the parent. Only this rule may name another family's entry.
  2. Otherwise the entry of the same mechanism whose `lowest` note is nearest the row's own lowest
     note in semitones, the earlier catalog entry on a tie, written after "Parent (rule 2):" with
     the mechanism and the semitone counts. The mechanisms: struck board and box zithers (314:
     `hammered dulcimer` D3, `cimbalom` E2, `santur` E3, `yangqin` G2); struck musical bows (311:
     `berimbau` alone). A struck string of another mechanism (a struck lute, 321; a struck tube
     zither, 312) has no rule-2 set: with no rule-1 relation it is reported to the controller
     under the SHIP ruling, and waits `its own build (<the mechanism>)` unless the controller
     rules otherwise.
  3. The sizes or models of one type share the type's parent: never a sound-alike's sound-alike.
- **Range ruling for struck strings.** A sourced range is the lowest and highest sounding notes
  that one fetched source states for the instrument:
  1. *Stated, by one source*: both notes as the range or compass, from one source (batch 14's
     `xaphoon`: two sources for one range is no range), in note names with octaves (scientific
     `C2`; Helmholtz `C` or `e‴`, whose octave marks fix the octave, as #84 confirms: Helmholtz
     `C` is C2, `c` C3, `c′` C4, `e′′′` E6, `AA` A1; a named note whose octave the source fixes,
     "middle C" C4), or the lowest note and an exact span or string count above it, diatonic or
     chromatic as the source says, as batch 7 allowed. One source's compasses for one instrument's
     bridges or sides (a dulcimer's «bass bridge» and «treble bridge») make its range from the
     lowest to the highest, the derivation shown.
  2. *Sounding*: notes the source gives as the instrument's range are taken as given. A range the
     source calls written or notated counts only with the transposition its own source states.
  3. *Extensions and extremes*: the stated compass, and nothing beyond it. A string some models
     add («+ D2 string»), or a note in parentheses, is an extreme: the range is the compass without
     it, or the row WAITs.
  4. *A maker's or museum's page ranges that model only*: a maker's model page (a hackbrett,
     santoor or yangqin maker) or a museum's object record (the Met, MIMO, the Horniman, Grinnell,
     Brooklyn, Tervuren, the Koizumi archive), or a photo caption naming one maker's instrument,
     ranges a row named for that model or object only, never the bare type name (#85, the Neupert
     "harpsichord Hass" page).
     b. *A size named in a cited sentence ranges that size only* (#87's `saung gauk`: «from C3 to
     F5» was U Sa's 13-string harp): a sentence giving a compass to «the 7-note» model, one string
     count or one named size ranges a row for that size, never the bare name, unless the same
     source calls that size standard (ruling 6). The worker quotes every such passage it finds and
     rules on it in the notes; a passage on a saved page that the notes leave out is a review
     finding.
  5. *Not a range*: a hedged span ("about", "approximately", "roughly", "typically", "usually",
     "up to", "slightly over"); a general or notation rule; a width or count with no pitch ("three
     octaves", "25 bridges", "four octaves plus a major 3rd" without notes); note letters with no
     octaves ("C, F, B-flat", "D-D-D-d"); a key or tuning ("in C major", "tonic and dominant",
     "tuned in fourths"); "two tones an octave apart" or a bow's «about a whole tone» with no
     pitch; a tuning list or a scale called a range; a tessitura; one pitch; or a chart drawn as an
     image (the Santur infobox's file, a staff chart: #86's concert accordion charts), however
     readable. The audit's ranges are leads, not sources (its "VERIFIED" khim and marxophone
     included).
  6. *Several sizes, none standard*: a bare type name with several sizes, models or string counts
     is ranged only from a source that calls one standard, usual, most common or traditional for
     the bare name. "Became widespread", "popular" or "modern" is none of these (#86's `khromka`).
     A source giving one instrument two ranges has given none. "One common version" is a version,
     not the instrument (#87's `baroque triple harp`): it ranges that version's row only. With
     neither, the row WAITs (batch 7's rule; batch 14's `birbyne`).
  7. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached; a
     national encyclopedia); a maker's catalogue or model page (ruling 4); a museum's object record
     (ruling 4's, the Smithsonian, the Musée de la musique, the Musical Instrument Museum (Phoenix),
     the Koizumi Fumio archive, the National Music Museum); a scholarly article; or a conservatory
     or orchestration reference (the Vienna Symphonic Library). A museum's or maker's page outranks
     an uncited Wikipedia line, and when they disagree the museum or maker decides (batch 11's
     lesson). A retailer's listing, a blog, a forum, an auction listing, a hobbyist's page or a
     musicbrainz mirror is not a source. A list or category page is a source for a name only. A
     range is never taken from a sibling, the parent, a related instrument, the audit or memory.
  8. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`) and nothing above C8
     (WAIT `a range above C8`).
  9. *One note*: an instrument whose source gives it one note has no range. It WAITs `a sourced
     range`, the note quoted.
  10. *Cited*: a range or trait from Wikipedia counts only when the raw wikitext shows a citation
      (a `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it in its own cell or paragraph, with
      no `{{citation needed}}` first, in a section not tagged `{{Unreferenced section}}` (the
      Khim page carries «{{More citations needed»: each line is still judged by its own
      citation). The citation must support the line: where the cited work is reachable the worker
      opens it, and a citation that gives no range (batch 11's `shehnai`) or points to a retailer is
      none. An uncited line is not a source for a range or for a trait that decides a WAIT.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then the
  derivation.
- **Generic and ambiguous terms.** A name its source gives to a class or to several instruments is
  DROP "a generic term for <the instruments>" or "an ambiguous name: <the instruments>", unless the
  source makes it one instrument's name (then rule 3). **A name is ambiguous when its fetched
  sources give it to two instruments, past or present** (#87's `welsh harp`, `clarsach` and
  `clairseach`: a historical sense counts, and reading the later use as the name's only current
  one is an inference). The cases to check: `salterio` (the audit's own "also a psaltery name"),
  `tympanon` (French for the dulcimer, and a historical name for other instruments if a page says
  so), `cimbal` and `cimbale` (the cimbalom, the dulcimer and the cymbal), `santouri` (the Greek
  santur, or a Greek name for the cimbalom), `medio` and `violinha` (the Berimbau page swaps the
  names between sizes: «''Médio'' (others say ''Viola'')», «''Viola'' (''Violinha'' if the medium
  tone is Viola)»), `kalinga` (also other instruments' names if a page says so), and `hudie qin`
  («butterfly» zithers). A size's name is no alias of its type (the gunga is not the berimbau): it
  is a row of its own under the range rulings.
- **An unambiguous name whose audit target was dropped as ambiguous** is decided on its own
  pages, not dropped with the target: `xinjiang yangqin`'s target, `chang`, was dropped by batch 17
  because the name covers four instruments, while «Xinjiang yangqin» names only the Uyghur
  dulcimer if a fetched source says so. It is then that instrument's row (WAIT `a sourced range`,
  or a SOUND_ALIKE ranged and parented under the rulings above); with no fetched page naming it,
  it is DROP "no fetched source describes it". A name that only translates the dropped target
  (batch 17's `gonghu` for `konghou`) still follows it: DROP "its target, <name>, is dropped".
- **Versions are not aliases.** A source's «a version of», «one common version», «a type of», «a
  variant», «derived from» or «related» makes the row a separate instrument (a sound-alike by
  parent rule 1 once ranged), never an alias (#87's `baroque triple harp`). Rule 8 makes an alias
  only of a name a cited page gives to the same instrument («also called», «also known as», a list
  of other names).
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's in-production
  line): DROP "a one-off instrument, not a type a game would ask for" for one maker's or artist's
  design never made as a type (`nondo`, Neil Feather's, is the first case to check; the fotdella,
  one player's homemade bass, if it is not a keyboard first; Partch's instruments); DROP "no
  fetched source describes it" when no fetched page describes the row, applied the same to every
  such row, candidate or alias name (`harmonic generator`, whose only lead is the Oddmusic
  gallery and which the audit could not find on the Partch pages, and `pianoharp`, whose only lead
  is a forum, are the first cases to check). A reconstruction makers offer today, or a type a
  museum holds (the pantaleon, if a museum holds one), is not a one-off. An ancient instrument
  known only from a tomb find (`zhu`) is not a one-off; it waits for a sourced range like any
  other.
- **Two halves, as explicit lists.** Half A, the hammered dulcimers and the hammered zithers (and
  the keyed names that are no struck string), is these 10 candidates:
  `celestaphone`, `chang`, `dolceola`, `hackbrett`, `khim`, `marxophone`, `pantaleon`,
  `pianoharp`, `santoor`, `yanggeum`.
  Half B, the struck bows, the string drums and the rest, is the other 10:
  `fotdella`, `ground bow`, `harmonic canon`, `harmonic generator`, `malunga`, `nondo`,
  `quijongo`, `tambourin a cordes`, `utogardon`, `zhu`.
  The list decides the half. The alias names go with the half whose candidate or target their line
  names: half A's 28 (the dulcimer and cimbalom lines' 16, 7 and 3, then `hudie qin`, then
  `xinjiang yangqin`, each line's names in the order the Spec line gives them) and half B's 19
  (the tambourin line's 4, the berimbau lines' 2, 2 and 1, the ground bow line's 6, then the
  berimbau sizes' 4), each half in that order. So half A's sheet holds 38 rows and half B's 29.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the batch
  or a SOUND_ALIKE row of the same half, never a row of the other half. So Task 4 needs nothing
  from Task 2. Half B drafts to a build file, appended to the sheet once half A is committed. The
  form check accepts a row the code already holds with the same target or parent (batch 7's
  lesson).
- **Rows that wait for their target name it.** A WAIT whose `waits_for` is `its target, <name>`
  holds `<name>` in `alias_of` too (#87: batches 3–8 and 17 filled it, 9–16 left it empty); the
  form check now refuses one that does not.
- **A held-back guard.** As batch 17's `HARP_HELD_BACK`, this batch's guard is `STRUCK_HELD_BACK`,
  a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose reason is not `a
  sourced range` (an engine feature, a build of its own, a drone tuning, sub-audio fundamentals, a
  range above C8), and every alias row that waits for such a row. A test refuses each of its names
  in the catalog and the aliases through `names_listed`, and the code check compares the table
  with the sheet, in the sheet's order. A row that waits for a range but will need a build of its
  own once ranged (#87's `gothic harp`, `ardin`, `simbi`) is not in the guard: its notes say so,
  and #88 lists it, so the reviewer of a later ranging catches it.
- **The guards' helpers are tested once, on real builds, both ways.** `names_listed` and
  `entries_with_sound_changes` exist (batches 16 and 17), and
  `test_the_harp_guards_helpers_read_real_builds` already tests them on real builds both ways (a
  real name, a real alias and a non-name; the organs' `['bourdon']` and the harps' `[]`). This batch
  adds no second copy of that test (#87's parked minor: batch 17's sound-change guard repeated its
  helper test's last assert); Task 1 runs it, and shows each new guard failing on a wrong table.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no
  SOUND_ALIKE or ALIAS row, its code task still fills `STRUCK_HELD_BACK` with the half's held rows
  and runs the code check, which must pass; its other steps are skipped, it commits only if the
  test file changed, and Task 6 records the skip in #88.
- **Out of scope:** the audit's "Gaps you could not close" (Hawaiian and African struck zithers;
  the Salzburg hackbrett's 128 strings; the pantaleon's 276; the Uyghur chang's courses; MIMO, the
  Met and the Horniman's 314.122-4 page; and "Not checked: claviharp, harp-piano, zither-banjo,
  tangent piano, orphica, schlagzither, tsimbl/Yiddish vs Romanian tambal differences, high/alto/
  bass yangqin sizes"), the names its draft removed (`gopichand`, `cello col legno`), `luthéal`
  (keyboards), `butterfly dulcimer` (no candidate, no catalog name: `hudie qin`'s row decides only
  that name), `caxixi` (a rattle, percussion), and the struck-string names a page mentions in
  passing. Task 6 lists them in #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of the build files is committed.

- [ ] **Step 0: The branch and the plan.** Run `git branch --show-current` and `git rev-parse
  --short HEAD`. Expected: `feat/instrument-catalog-batch-18` and `9a8dcfbe`. Anything else: stop
  and find out why. Copy this plan to `plans/2026-11-12-instrument-catalog-batch-18-implementation.md`
  and commit it:
```bash
git add plans/2026-11-12-instrument-catalog-batch-18-implementation.md
SKIP=replay-metrics git commit -m "Plans: batch 18 of the instrument catalog (struck strings), the implementation plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-18-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-18-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names), len(instruments.CATALOG), len(instruments.ALIASES))
"
```
  Expected (after pygame's banner): `names before 829 704 125` (checked for this plan at
  `9a8dcfbe`). Any other number means the branch is not batch 17's tip: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && tolower($4) ~ /struck/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /struck/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' fotdella nondo quijongo celestaphone pianoharp
} | LC_ALL=C sort -u | LC_ALL=C comm -23 - ../../../build/batch-18-names-before.txt > ../../../build/batch-18-candidates.txt
cd ../../..
```
  Write the plan's 10 half-A names, one per line, to `build/batch-18-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-18-candidates.txt build/batch-18-half-a.txt > build/batch-18-half-b.txt`
  and `wc -l build/batch-18-*.txt`.
  Expected: 20 candidates, 10 in half A, 10 in half B, and
  `LC_ALL=C comm -13 build/batch-18-candidates.txt build/batch-18-half-a.txt` prints nothing.
  Check that `build/batch-18-half-b.txt` is exactly the plan's half-B list. The sorted union before
  the `comm` is also 20 names (no candidate is already a catalog name or alias); without the
  `printf` line it is 15 (`marxophone` is in both audit lists).

- [ ] **Step 3: The form check,** `build/batch-18-form-check.py`. Copy `build/batch-17-form-check.py`
  and change it as follows; `STATUSES`, `pattern`, `held_as_this_row`, `taken`, `in_span`,
  `changes`, `ranged`, the `bad` list's shape and the output stay.
  - The docstring:
```python
"""Batch 18's sheet form check: uv run python -I build/batch-18-form-check.py SHEET.

Batch 17's form check (build/batch-17-form-check.py) with batch 18's changes (batch 18's plan,
"Before the tasks" Step 3): the struck strings family, a sound-alike's struck class (a -4 suffix,
no keyboard), a parent outside its mechanism only by the parent ruling's rule 1, and a row that
waits for its target naming it in alias_of.
"""
```
  - `names_before` reads `build/batch-18-names-before.txt`; `APPROXIMATING_NAMES` is checked
    against the test file's (unchanged since batch 13); `HARP_CLASS` and batch 17's
    `RULE_TWO_PARENTS` are replaced by:
```python
# Hornbostel-Sachs classes checked against Wikipedia's lists for batch 18's plan: a bar, tube,
# raft or board zither (311 to 314) or a lute (321), with any subclass, sounded by hammers or
# beaters (suffix 4); a keyboard (8) makes it a keyboard's
STRUCK_CLASS = re.compile(r'(31[1-4]|321)(\.[0-9]+)*-4')
# The parent ruling's rule 2: each mechanism's catalog entries (batch 18's plan)
RULE_TWO_PARENTS = {
    '311': {'berimbau'},
    '314': {'hammered dulcimer', 'cimbalom', 'santur', 'yangqin'},
}
```
    and `alike_allowed`'s mechanism line reads
    `in_mechanism = parent in RULE_TWO_PARENTS.get(row['hs'][:3], set())` (batch 17's
    `RULE_TWO_PARENTS[row['hs'][:3]]` would raise a KeyError on a 312 or 321 row).
  - The `bad` list's family test is `row['family'] != 'struck strings'`; its sound-alike test
    reads `not STRUCK_CLASS.fullmatch(row['hs'])` for batch 17's `HARP_CLASS`; and it adds two
    tests:
```python
       or (row['status'] == 'WAIT' and row['waits_for'].startswith('its target, ')
           and row['alias_of'] != row['waits_for'].removeprefix('its target, '))
       or (row['status'] == 'DROP' and row['notes'].startswith('Already decided')
           and not re.search(r'batch-[0-9]+\.tsv', row['notes'][:120]))
```
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: The quote check,** `build/batch-18-quote-check.py`. Copy
  `build/batch-17-quote-check.py` and change it as follows; `CITATION`, `UNCITED_TAG`,
  `read_page`, `visible`, `located`, `cited`, `quoted`, `on_page`, the shipped rows' one `range`
  section and the every-row ledger check stay.
  - The docstring: batch 17's, with "Batch 18's" and `build/batch-18-quote-check.py` in its first
    line, "Batch 17's quote check (build/batch-17-quote-check.py) with batch 18's changes (batch
    18's plan, "Before the tasks" Step 4)" in its second paragraph, its error-page sentence
    reading "A saved page that is an HTTP error page (a Wikimedia Error page, a 403, 404, 429 or
    5xx title, or an empty file) is a failure: an error page is never saved (#87).", and a last
    sentence: "Every saved page holding an email address is listed, for the controller to judge
    (a private person's is redacted, an institution's stays)."
  - `PAGES = Path('build/batch-18-pages')`; `ERROR_PAGE`'s alternation gains `|5[0-9][0-9]|Rate
    limited`; a page whose bytes are empty appends `(row['name'], 'saved page is empty: ' +
    path.name)`; and:
```python
# An email address on a saved page: listed for the controller, never a failure by itself
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
pages_with_email = []
```
    with each page read appending `path.name` to `pages_with_email` when `EMAIL.search(text)`
    matches, and `print('pages with an email address:', sorted(set(pages_with_email)))` before the
    `bad:` line.
  It checks what can be checked mechanically; a worker still applies range ruling 10 in full.

- [ ] **Step 5: The code check,** `build/batch-18-code-check.py`: copy `build/batch-17-code-check.py`
  and change it as follows; `test_table`, `held_back`, `in_catalog_order`, the "Already decided"
  branch, the shipped-row assertions and the order checks' shape stay.
  - The docstring:
```python
"""Batch 18's code check: uv run python -I build/batch-18-code-check.py SHEET.

Batch 17's code check (build/batch-17-code-check.py) with batch 18's changes (batch 18's plan,
"Before the tasks" Step 5): the struck strings family, no sound changes and no tags compared with
the sheet, and the builds, sound-alikes and aliases in the sheet's order. The test file's tables
are read as literals (ast.literal_eval), never evaluated. A one-off check may read the private
_STRUCK_BUILDS; a test may not.
"""
```
  - The imports read `STRUCK_SOUND_ALIKES` from `struck_sound_alikes` and `_STRUCK_BUILDS` from
    `struck_strings`; `EXISTING_COUNT = 5`; `NAMES_BEFORE` reads `build/batch-18-names-before.txt`.
  - The table assertions after the loop name `STRUCK_HELD_BACK`, `NEW_STRUCK_NAMES` and
    `STRUCK_SOUND_ALIKE_PARENTS` for batch 17's three, and `_STRUCK_BUILDS` and
    `STRUCK_SOUND_ALIKES` for `_HARP_BUILDS` and `HARP_SOUND_ALIKES`, with the messages renamed to
    match.
  It cannot run until Task 1 has created `struck_strings.py`, `struck_sound_alikes.py` and the test
  tables. The three "Already decided" DROP rows were never catalog names or aliases, so they take
  the last branch.

---

### Task 1: Struck strings in their own module, renamed from strings.py, unchanged; their sound-alikes module; the batch table's row and the held-back and sound-change guards, each shown failing on a wrong table

**Files:**
- Rename: `src/glitchygames/audio/instruments/strings.py` to `struck_strings.py` (`git mv`)
- Create: `src/glitchygames/audio/instruments/struck_sound_alikes.py`
- Modify: `registry.py`, the docstrings of `bowed_strings.py`, `harps.py` and
  `instruments/__init__.py`, and `docs/architecture/sound.md` (the sound-alike modules sentence)
- Test: `tests/audio/test_instrument_catalog.py`; run `tests/test_process_state_guard.py`

**Interfaces:**
- Produces: in `struck_strings.py`, `STRUCK_STRINGS: Final[tuple[CatalogEntry, ...]] =
  _STRUCK_BUILDS + STRUCK_SOUND_ALIKES`, and `_hammered(*, ring_seconds: float, low_pass: float)
  -> Instrument` and `_berimbau() -> Instrument` under their current names.
  `STRUCK_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test file gains
  `EXISTING_STRUCK_NAMES: frozenset[str]` (the 5); `NEW_STRUCK_NAMES: list[str]`,
  `STRUCK_SOUND_ALIKE_PARENTS: dict[str, str]` and `STRUCK_HELD_BACK: dict[str, str]`, all empty
  here, for Tasks 3 and 5 to fill; the two guard tests below; and the row `Family.STRUCK_STRINGS:
  BatchFamily(EXISTING_STRUCK_NAMES, NEW_STRUCK_NAMES, STRUCK_SOUND_ALIKE_PARENTS)` in
  `BATCH_FAMILIES`. Also `build/catalog-builds-before.txt`.
- Consumes: `names_listed(names: Iterable[str]) -> set[str]` and
  `entries_with_sound_changes(family: Family) -> list[str]`, already in the test file.

The move comes first and the guards after, so no step expects a test to pass before the module it
imports exists (batch 16's Task 1 did: #86).

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

- [ ] **Step 2: Rename and split the module.** Read every comment on the moved code first. Run
  `git mv src/glitchygames/audio/instruments/strings.py src/glitchygames/audio/instruments/struck_strings.py`.
  In `struck_strings.py`, rename the tuple `_STRUCK_BUILDS` (its entries, builders and comments
  unchanged), import `STRUCK_SOUND_ALIKES`, and define `STRUCK_STRINGS: Final[tuple[CatalogEntry,
  ...]] = _STRUCK_BUILDS + STRUCK_SOUND_ALIKES` after it. The docstrings:
  - `struck_strings.py` keeps its first line, "Struck strings: hammered dulcimer, cimbalom,
    santur, yangqin and the berimbau." (81 columns with its quotes), its sibling-modules sentence,
    its ranges sentence and its timbre sentence verbatim, and adds after the sibling sentence:
    "The family's sound-alikes, listed instruments that share another entry's build, are in
    ``struck_sound_alikes.py``.", rewrapped to 100 columns.
  - `struck_sound_alikes.py` gets the empty table and `harp_sound_alikes.py`'s docstring with
    "Struck strings'" for "Harps'", ending "The family's builds are in ``struck_strings.py``.".
    Its first line is "Struck strings' sound-alikes: listed instruments that share another entry's
    build." (85 columns). Its imports are `harp_sound_alikes.py`'s (`CatalogEntry` under
    `TYPE_CHECKING`).
  - `bowed_strings.py` lines 5–6 and `harps.py` lines 5–6 name ``struck_strings.py`` for
    ``strings.py``, rewrapped to 100 columns. In the `instruments/__init__.py` docstring, the harps
    paragraph's "``strings.py`` now holds only the struck strings." becomes "The struck strings are
    in ``struck_strings.py``.", and `docs/architecture/sound.md`'s "`strings.py` now holds only the
    struck strings" becomes "the struck strings' builds are in `struck_strings.py`" (Task 6 adds
    their sound-alikes module to that sentence with its count).
  Point `registry.py` at `struck_strings` (`STRUCK_STRINGS`; its place in `FAMILY_TABLES` does not
  change).

- [ ] **Step 3: Check nothing changed.**
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
grep -rn 'strings\.py' src tests scripts docs/architecture CLAUDE.md | grep -v 'bowed_strings\.py\|plucked_strings\.py\|struck_strings\.py'
git status --short
uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q
```
  Expected: `changed: []`; nothing from `awk` (every module's first line fits in 100 columns);
  nothing from `grep` (no live file names `strings.py`); `git status` shows `R` for the rename;
  then PASS.

- [ ] **Step 4: Write the tables and the guards.** After batch 17's harp tables
  (`HARP_SOUND_ALIKE_PARENTS`), add `EXISTING_STRUCK_NAMES` (the 5 names, one per line, in
  catalog order: `hammered dulcimer`, `cimbalom`, `santur`, `yangqin`, `berimbau`), with the comment
  "# The 5 struck strings that predate batch 18: their shared builds predate the anti-goal rule",
  then `NEW_STRUCK_NAMES: list[str] = []` and `STRUCK_SOUND_ALIKE_PARENTS: dict[str, str] = {}`,
  each commented as batch 17's harp lists are. Put the struck strings row between the harps and
  keyboards rows in `BATCH_FAMILIES`, which is table order. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list gains `+
  list(STRUCK_SOUND_ALIKE_PARENTS)` between the harps' and the keyboards' lines, its comment
  reading "… plucked strings, harps, struck strings, keyboards, …". At the end of the file add:
```python
# Every name plans/data/instrument-audit/batch-18.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a drone
# tuning, sub-audio fundamentals or a range above C8, and the alias rows that wait for one of
# them, in the sheet's order. None ships under that name or as an alias until the reason is met
# (decision 4; batch 18). The test matches exact names
STRUCK_HELD_BACK: dict[str, str] = {}
```
  Then the tests, each with a one-line docstring:
  - `test_no_struck_string_name_held_back_for_a_feature_is_listed`:
    `names_listed(STRUCK_HELD_BACK) == set()`.
  - `test_no_struck_string_sound_alike_changes_its_parents_build`:
    `entries_with_sound_changes(Family.STRUCK_STRINGS) == []` (the sound-alike ruling: this batch
    adds no sound change).
  No new helper test: `test_the_harp_guards_helpers_read_real_builds` tests both helpers on real
  builds both ways (the plan's ruling).

- [ ] **Step 5: Run them, then show each guard failing on a wrong table.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or guards_helpers or changes_its_parents" -v`
  Expected: PASS, with the ID `[struck strings]` in the parametrised batch tests. Then, without
  committing, each of these, rerunning the named tests and restoring the table after each:
  - `STRUCK_HELD_BACK = {'cimbalom': 'its own build (a test)'}`, `-k "struck_string_name_held_back"`:
    Expected FAIL naming `cimbalom`.
  - `EXISTING_STRUCK_NAMES` without `'berimbau'`, `-k "new_entries and struck"`: Expected FAIL.
  - `STRUCK_SOUND_ALIKE_PARENTS = {'cimbalom': 'hammered dulcimer'}`, `-k "sound_alike_is_listed"`:
    Expected FAIL (a pre-batch build is no sound-alike).
  Then rerun the first command: PASS. `git diff --stat` shows only the intended edits.

- [ ] **Step 6: Lint and commit.** Run each lint command as its own line (batch 11's Task 1: zsh
  word-splitting once made a combined run a no-op).
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py docs/architecture/sound.md
SKIP=replay-metrics git commit -m "Instrument catalog: struck strings in their own module, renamed from strings.py, unchanged; their sound-alikes module; the held-back and sound-change guards" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The hammered dulcimers and hammered zithers sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch` for searching, and fetch
every URL you cite with `curl -fsS -L`, saving it. A WebFetch summary is a lead, never a source
(#85's `nickelodeon`); never cite a page you did not save. Put no personal data in any request, in
a header, a URL or a payload. Save each row's raw pages straight to
`build/batch-18-pages/<name, spaces as hyphens>--<n>.txt` (for Wikipedia, the `action=raw`
wikitext; never a text extracted from it, which drops `<ref>` and `<sup>`: #81's lesson; never a
scratch copy named by the page title: #87's case-insensitive overwrite; for a page that keeps
refusing curl, the Internet Archive's `id_` copy). A 404 is written in the row's notes ("returned
404") and never saved; a 429 is waited out and fetched again, never saved. After each save, check
the file is the page and not an error page (`grep -l "Wikimedia Error" build/batch-18-pages/*`
prints nothing). If a saved page holds a private person's phone number or email address, tell the
controller, who redacts it before the row cites the page; an institution's public contacts stay.
This holds for every row whose notes quote a page, WAIT and DROP rows too, since the quote check
reads them all. A list or category page is a source for a name only. The sound, the mechanism and
the range come from the instrument's own page, a maker, a museum or a scholarly article under
range ruling 7; a chart drawn as an image is not quotable (range ruling 5). The audit's rows and
"Range checks" are leads, not sources, so fetch them. Fetch the page of every existing entry you
name as a parent, and record what it says in the row's notes. Never use `git stash`. This task may
start as soon as the controller has written the shared files, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-18.tsv`
- Create (not committed): `build/batch-18-half-a.tsv`, and the raw pages in
  `build/batch-18-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `struck-strings.md` (its rows, "Rejected or
  corrected proposed entries", "Aliases", "Range checks", "Gaps you could not close");
  `missing-categories.md` (the reassignment line); `round-1/merged-missing.tsv` and
  `round-1/chordophones.md` (the `celestaphone`, `pianoharp` and `marxophone` rows);
  `batch-15.tsv` (the `dolceola` row) and `batch-17.tsv` (the `chang` row);
  `build/batch-18-names-before.txt`, `build/batch-18-half-a.txt`, `build/batch-18-half-b.txt`,
  `build/batch-18-form-check.py` and `build/batch-18-quote-check.py`.
- Produces: `batch-18.tsv` with batch 17's seventeen columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	drones	drone_source`.
  `status` is one of `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP` (no SHIP: the SHIP ruling).
  `alias_of` holds an ALIAS row's target, a SOUND_ALIKE row's parent, or the target an `its
  target, <name>` WAIT names. `family` is `struck strings` on every row; `tags` is empty, `drones`
  is `none` and `drone_source` empty on every row. A SOUND_ALIKE row has `lowest`, `highest`
  (sounding), `range_source`, an `hs` that fullmatches the struck classes, `builder` "unchanged",
  and `notes` holding `Range:` with its «raw passages» and derivation, and its parent ruling line
  ("Parent (rule 1):" or "Parent (rule 2):"). A candidate row's `audit_name` is its name in
  `build/batch-18-candidates.txt`; an alias row's is its audit line as the Spec line gives it.
  Also `build/batch-18-half-a.tsv`, the half as committed, which Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-18-half-a.txt`'s order, then
  one per alias name of this half, in the plan's order.

  The rules are batch 17's, changed for this family:

  1. **No SHIP** (the SHIP ruling): a row whose source states a trait in numbers `plucked` or
     `struck` takes is reported to the controller with the passage, and waits for the ruling.
  2. **SOUND_ALIKE**: a verified instrument that the sound-alike ruling finds would sound like an
     existing entry. `alias_of` is its parent (the parent ruling). The `notes` begin
     "Sound-alike:", quote the source's description and mechanism (what sounds and what strikes
     it), and say why that entry is the parent ("Parent (rule 1):" with the source's relating
     words, or "Parent (rule 2):" with the mechanism and the semitone counts). It has its own
     range, and the `builder` cell says "unchanged". It is never another sound-alike's
     sound-alike, never one of `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited («also called», «also known as», a
     list of its names), never a version or a relative (the versions ruling). The target is a
     catalog name or a SOUND_ALIKE row of this half. If the target waits, the row is WAIT with
     `waits_for` `its target, <name>` and `alias_of` `<name>`. If the target is dropped, the row
     is DROP "its target, <name>, is dropped", unless the name is unambiguous and its target was
     dropped only as ambiguous (the ruling above). An ambiguous name or a generic term is DROP
     under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `sub-audio fundamentals`, `a range
     above C8`, `sympathetic strings`, `a sourced drone tuning`, `a pitch moving through a
     phrase`, `its own build (<the trait>)`, or another name of Global Constraints. **The range
     is checked first.** The feature must be the sound the source describes, not a technique a
     player «can» apply. A cited trait no builder makes means the row waits. Any other name is
     allowed only with the source quoted, and Task 6 lists it in #88.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     boundary ruling's words), is a one-off, makes no sound, or is already decided: in the catalog
     under that name (name the entry), an alias already (name its target), or a row of an earlier
     sheet (notes beginning "Already decided:", naming the sheet whose status stands and that
     status, and any earlier sheet's hand-off).
  6. A row the audit marks UNVERIFIED or sources only by a list or category page, a musicbrainz
     mirror, a forum, the Oddmusic gallery or the general Hammered dulcimer page has no sourced
     sound or range yet. Fetch its own page; the audit's URL is a lead. If no page can be found,
     the row is DROP "no fetched source describes it", the same words on every such row.
  7. **The anti-goal:** compare each SOUND_ALIKE row's quoted sound with the sound-alike ruling's
     list before writing it: a string or course count, bridges, crossed strings, a tuning, a
     material, the beaters, dampers, a size, a body, a maker, a region or a colour word is no
     trait; a rattle, a bouncing hammer, a glide or a drone chord is a trait the build cannot make
     (WAIT).
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.
  9. **Ranges and sizes:** every passage on a saved page that gives a compass for the row's
     instrument, a size of it or one object of it is quoted in the notes and ruled on (range
     rulings 4, 4b, 5 and 6), so a reviewer never finds one the notes leave out (#87's `saung
     gauk`).

  This half's own cases:

  - **Already decided.** `chang` and `dolceola` are DROP under rule 5, their notes beginning
    "Already decided: batch-17.tsv DROP" (harps, «an ambiguous name», quoting #70's sentence that
    this batch treats the name as decided) and "Already decided: batch-15.tsv WAIT" (keyboards, `a
    sourced range`, after `batch-4.tsv`'s DROP to keyboards), quoting those sheets.
  - **The hammered dulcimers.** `hackbrett`, `khim`, `santoor`, `yanggeum` and `pantaleon` are
    decided by the sound-alike, parent and range rulings: course counts, crossed chromatic
    stringing, brass or steel strings, bamboo or leather-tipped beaters, a trapezoid or butterfly
    body and dampers are no trait. Their parent is the catalog dulcimer their source relates them
    to by rule 1 («similar to the [[hammered dulcimer]] or [[cimbalom]]», «It is a [[hammered
    dulcimer]]»: the first named), else by rule 2 among the four. The khim's «Lowest note … A2 …
    Highest note … A4» is a range only as rulings 4b, 6 and 10 allow (the audit calls it the
    7-note model's). The hackbrett's only audit source is the general Hammered dulcimer page and a
    retailer: rule 6. The pantaleon is Hebenstreit's enlarged dulcimer: a type a museum holds is
    no one-off, its «276 strings» a count.
  - **The hammered zithers.** `marxophone`, `celestaphone` and `pianoharp` are first decided by
    boundary ruling 3 (keys or no keys, in their own pages' words), then by the sound-alike
    ruling: the marxophone's bouncing hammers («A brief stab on a metal strip bounces the hammer»,
    the audit's «mandolin-like tremolo») are `its own build (a bouncing hammer)` once ranged, and
    its «middle C» to «C''» (the Marxophone page) is a range only with a citation; its strummed
    chord strings are a technique beside the struck melody. The celestaphone's Wikipedia page
    returned a musician to the audit: fetch the instrument's page or a museum record, else rule 6.
  - **The alias names.** Each dulcimer and cimbalom name is an ALIAS of the catalog entry a cited
    page gives it to (the Hammered dulcimer page's names list: `hammered dulcimer`; the Cimbalom
    page's: `cimbalom`), decided name by name on the saved page's words, never by the audit's
    grouping; a name a page gives to both, or to the cymbal or psaltery too, is DROP "an
    ambiguous name" (`salterio`, `cimbal`, `cimbale`, `tympanon` and `santouri` checked first). A
    name no saved page holds is DROP "no fetched source describes it". `hudie qin` is decided on
    the Yangqin page: another name for the yangqin (ALIAS), a separate butterfly zither (its own
    row: WAIT `a sourced range` or a sound-alike), or a generic or ambiguous name. `xinjiang
    yangqin` is decided by the ambiguous-target ruling.

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-18-form-check.py plans/data/instrument-audit/batch-18.tsv`
  and `uv run python -I build/batch-18-quote-check.py plans/data/instrument-audit/batch-18.tsv`.
  Expected: `38 rows;` and the counts, then `bad: []`, exit 0; then the declared-charset,
  windows-1252 and email lists (any page named in the first two is recorded in the row's notes;
  any in the third is shown to the controller before the commit), `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-18.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-18-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-18-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
print('alias rows:', sum(row['audit_name'] not in half_a for row in rows))
"
```
  Expected: `missing: []`, `twice: []`, `from half B: []` and `alias rows: 28`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-18.tsv build/batch-18-half-a.tsv
git add plans/data/instrument-audit/batch-18.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 18's verification sheet, the hammered dulcimers and hammered zithers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The hammered dulcimers and hammered zithers

**Files:**
- Modify: `struck_sound_alikes.py` (`STRUCK_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its
  source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-18-half-a.tsv` (half A as committed), Task 1's tables, and
  `build/batch-18-code-check.py`.
- Produces: `STRUCK_SOUND_ALIKE_PARENTS` and `STRUCK_HELD_BACK` filled with this half's rows,
  which Task 5 extends. `NEW_STRUCK_NAMES` stays empty (no SHIP).

If half A has no SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills only
`STRUCK_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file only if it changed
(else no commit, and the report says so).

- [ ] **Step 1: Write the failing tests.** Fill `STRUCK_SOUND_ALIKE_PARENTS` with one `name:
  parent` per SOUND_ALIKE row and `STRUCK_HELD_BACK` with one `name: waits_for` per held row
  (every WAIT row whose reason is not `a sourced range`, and every `its target, <name>` row whose
  target is held), each in the sheet's order. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, in the sheet's order, with a docstring sentence
  for batch 18.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or held_back or changes_its_parents" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the held-back
  and sound-change tests pass.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in
  `STRUCK_SOUND_ALIKES`, in the sheet's order, under a section comment naming
  `plans/data/instrument-audit/batch-18.tsv` as `organ_sound_alikes.py`'s does ("--- Batch 18's
  hammered dulcimers and hammered zithers, in the order of …"), each a `CatalogEntry(name, title,
  Family.STRUCK_STRINGS, lowest, highest, sounds_like=parent)`. Above each, put a comment with its
  `sound_source` and `range_source` URLs, the quoted passages (its mechanism and its range) and
  the derivation. Each ALIAS row goes in `aliases.py` under a "Batch 18's struck strings: the
  hammered dulcimers and hammered zithers" section, in the sheet's order, with its URL and quote.
  Comments name only committed files.

- [ ] **Step 4: Run the suite and check the code against the sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` for every new entry
  (`test_harmonic_instruments_sound_their_note` does not cover this family: Global Constraints). A
  failure at a range end is a finding about the range or the build: check it against the source,
  and never trim the range to pass. Then run:
  `uv run python -I build/batch-18-code-check.py build/batch-18-half-a.tsv`
  Expected: `matches 38 rows`. Then rerun Task 1 Step 3's first command with its `order` assertion
  replaced by `names = set(instruments.names()); assert all(row[0] in names for row in before),
  'missing'`. Expected: `changed: []`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 18's hammered dulcimers and hammered zithers, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The struck bows, string drums and the rest sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-18-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-18-pages/`
- Modify: `plans/data/instrument-audit/batch-18.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–9 and header, `build/batch-18-form-check.py`,
  `build/batch-18-quote-check.py`, `build/batch-18-half-b.txt`; `struck-strings.md` (its rows,
  "Rejected or corrected" lines for `harmonic generator` and `harmonic canon`, "Aliases", "Range
  checks", "Gaps"); `round-1/merged-missing.tsv` and `round-1/electrophones-and-oddities.md` (the
  `harmonic generator` and `harmonic canon` rows); `batch-4.tsv` (the `fotdella`, `nondo`,
  `quijongo`, `harmonic canon` and `musical bow` rows).
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-18-half-b.txt`'s order, then one per alias name
of this half, in the plan's order. A parent or alias target is a catalog name or a SOUND_ALIKE row
of this half, never a half-A row. These rules apply on top of Task 2's:

- **Already decided.** `harmonic canon` is DROP under rule 5, its notes beginning "Already decided:
  batch-4.tsv WAIT" with that row's reason (`a sourced range`) and family (plucked strings).
- **The hand-offs.** `fotdella`, `nondo` and `quijongo` quote their `batch-4.tsv` DROP in the
  notes, then are decided here: the fotdella by boundary ruling 3 first (its pedal hammers, «like
  the action of a [[piano]]»: keyboards) and then the one-off ruling; the nondo by the one-off and
  unsourced rulings (its only source is the Oddmusic gallery); the quijongo as a struck bow
  (boundary ruling 5), parent `berimbau` by rule 1 or 2, its «changing the tone by a fourth or
  sixth» by covering the soundhole a technique and two notes with no pitch (range ruling 5).
- **The struck bows.** `malunga` and `ground bow` are struck bows (311.12, -4 from «struck»),
  parent `berimbau`. The malunga's rattle «in the same hand» is `its own build (rattles)` once
  ranged, when its fetched source states it for the instrument; its «two tones an octave apart»
  has no pitch. The ground bow is a bow, a ground zither (314.21) or both on its page («also known
  as an '''earth-bow''' or '''ground harp'''»): its `hs` is the class its words imply; its bent
  stick's glide is decided by the sound-alike ruling (the instrument's sound, or what a player
  «can» do: «It can be played in a [[glissando]] manner»).
- **The string drums and struck lutes.** `tambourin a cordes` (struck with a stick while the other
  hand plays a pipe; its strings «tuned tonic and dominant» sound together) and `utogardon` (a
  cello-shaped body, «struck and plucked with a 40 cm stick») are decided by boundary ruling 1 and
  the parent ruling's rule 2 (a 321 row has no rule-2 set: the controller rules it); a drone the
  source makes the instrument's sound is `a sourced drone tuning` unless its notes are sourced
  (then the SHIP ruling).
- **The others.** `zhu` is an ancient struck zither («played with a slender stick», «may have
  been plucked» on the audit's reading: quote the page's own words); `harmonic generator` is
  decided by boundary ruling 7 and the unsourced ruling.
- **The alias names.** `ttun ttun`, `salmo`, `chicoten` and `toum toum` follow `tambourin a cordes`
  (rule 3), each on a cited page giving it as that instrument's name (the audit gives them as
  regional instruments: «Basque ttun-ttun, Spanish salmo, Aragonese chicoten»; a regional
  instrument of its own is a row decided on its page, never an alias); `umbulumbumba`,
  `mbulumbumba`, `urucungo`, `madimba lungungu` and `hungu` are ALIASes of `berimbau` only on a
  cited page giving the name to the berimbau («|names=urucungo, madimba lungungu» on the Berimbau
  page), else rows of their own as related bows (the versions ruling: Kubik's «identical
  construction and playing technique» makes a relative, not another name); `kalinga`, `galinga`,
  `gayumba`, `tumbandera`, `tingo talango` and `angbindi` follow `ground bow`, on its page's names
  («Other names include ''kalinga'' or ''galinga''»); `gunga`, `berra boi`, `medio` and `violinha`
  are the berimbau's sizes, each a row of its own (a size is no alias), decided by the ambiguous
  ruling first (the page swaps `medio`'s and `violinha`'s names) and then by the range rulings
  (a sound-alike of `berimbau` only with its own sourced range); `berra boi` is rule 8 with
  `gunga` («''Gunga'' (others say ''Berra-boi'')»).

- [ ] **Step 1: Write half B's rows** to `build/batch-18-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-18-form-check.py build/batch-18-half-b.tsv` and
  `uv run python -I build/batch-18-quote-check.py build/batch-18-half-b.tsv`.
  Expected: `29 rows;` and the counts, then `bad: []`, exit 0; then the charset and email lists,
  `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-18-half-b.tsv >> plans/data/instrument-audit/batch-18.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `67 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-18.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-18-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-18-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted((half_a | half_b) - set(audit_names)))
print('twice:', sorted({name for name in half_a | half_b if audit_names.count(name) > 1}))
print('extra:', len(set(audit_names) - half_a - half_b))
print('names twice:', sorted({row['name'] for row in rows if [r['name'] for r in rows].count(row['name']) > 1}))
"
```
  Expected: `missing: []`, `twice: []`, `extra: 11` and `names twice: []`. The 11 are the alias
  rows' audit lines: half A's 5 (the dulcimer, cimbalom, tympanon, `hudie qin` and `xinjiang
  yangqin` lines) and half B's 6 (the tambourin line, the three berimbau lines, the ground bow line
  and the sizes line).

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-18.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 18's verification sheet, the struck bows, string drums and the rest" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The struck bows, string drums and the rest

**Files:**
- Modify: `struck_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-18.tsv`'s half-B rows, Task 3's tables, and `build/batch-18-code-check.py`.
- Produces: the finished family: `STRUCK_SOUND_ALIKE_PARENTS` and `STRUCK_HELD_BACK` with both
  halves' rows.

If half B has no SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to
  `STRUCK_SOUND_ALIKE_PARENTS`, `STRUCK_HELD_BACK` and the alias parameters, after half A's, as in
  Task 3 Step 1.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: sound-alikes after half
  A's sound-alikes, aliases after half A's aliases, under second section comments naming the sheet
  ("Batch 18's struck strings: the struck bows, string drums and the rest").

- [ ] **Step 4: Run the suite and check the code against the whole sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`, then
  `uv run python -I build/batch-18-code-check.py plans/data/instrument-audit/batch-18.tsv`, then
  Task 3 Step 4's earlier-builds command.
  Expected: PASS, then `matches 67 rows`, then `changed: []`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 18's struck bows, string drums and the rest, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a struck strings
  paragraph with its count, naming `struck_strings.py` and `struck_sound_alikes.py`, with
  examples, in the harps paragraph's form, saying that a struck string is sounded by a beater in
  the player's hand (Hornbostel–Sachs suffix 4: the hammered dulcimers, 314.122-4, and the struck
  bows, 311.12), that keyed struck strings are keyboards, that a string or course count, bridges, a
  tuning, a material, the beaters, a size or a body is no trait, and that a sound-alike gives its
  own sourced range.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `struck strings`
  row's count and examples, the sound-alike modules sentence and its total).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 18
  done, pointing at this plan and `batch-18.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 18 DONE", and the Description's running count gains batch 18;
  - batch 18 done, with the sheet's counts by status and the family's growth, the module move
    (`struck_strings.py`, renamed from `strings.py`, which is gone), the boundary rulings,
    `STRUCK_HELD_BACK`'s names, and the branch's base SHA (`9a8dcfbe`, batch 17's tip);
  - the audit's unclosed gaps and the out-of-scope names (the plan's list), as a later pass;
  - the hand-offs: `fotdella`, `nondo` and `quijongo` decided here (batch 4's DROPs), and
    `celestaphone` and `pianoharp` (`missing-categories.md`'s); the three already-decided rows
    left as their sheets decided them (`chang`, `dolceola`, `harmonic canon`); each row dropped to
    keyboards, plucked strings or another family, for a later pass of that family; the alias
    names decided here (so no later batch decides the dulcimer and cimbalom names, `salterio`,
    `tympanon`, the tambourin's, berimbau's and ground bow's names, or the berimbau's sizes
    again);
  - a "Plan (batch 18)" line, the Status line, and the next batch named, from the spec's order
    and the families no batch has grown.

  Add #88 (the highest item is #87), "Sound Engine: The Owner's Checks on Instrument Catalog Batch
  18 — TODO". Use #87's form, place it directly after #87, and give it the Priority "(before the
  next batch builds on the same catalog)". Its **Listen** section (`build/instruments/struck
  strings/`, the family's value as the folder name) covers the sound-alikes beside their parents,
  then the aliases. Its **Calls to confirm** are:
  - every WAIT, by reason, with names, and each row's "Engine limit, once ranged" note, and the
    range waits that will need a build of their own once ranged (outside `STRUCK_HELD_BACK`);
  - the module move (`strings.py` renamed to `struck_strings.py`, no re-export kept) and its
    `changed: []` record, answering #87's question;
  - the boundary rulings, each row they moved, and the Hornbostel–Sachs codes this plan checked
    (311.1 and its subclasses, 312, 313, 314.1, 314.122, 314.21, 314.22, 321.322, the suffixes
    4, 8 and 9; the Santur and Cimbalom infoboxes' missing classes);
  - the bows batch 4 decided as plucked strings (`musical bow`, `uhadi`, `umrhubhe`, `ukeke`,
    `washtub bass`): whether the struck ones belong here, for a later pass;
  - a struck string as a sound-alike (counts, courses, bridges, tunings, materials, beaters,
    dampers, sizes, bodies and colour words no trait; no SHIP and no `sound_changes` in this
    batch; rattles, a bouncing hammer, a glide and a drone chord wait), and any row the SHIP
    ruling sent to the controller;
  - the parent ruling (the source's relation first, the first named of two; else the nearest
    lowest note among the four dulcimers, or `berimbau` for a struck bow; another mechanism to the
    controller), and each sound-alike's parent;
  - the range ruling (one source states both ends; one source's bridge compasses joined; a count,
    a width, a tuning, a hedge, an image chart or a general rule no range; a model's or object's
    page ranges that model only; a size named in a cited sentence ranges that size only; a bare
    name of several sizes with none standard waits; a version is not the instrument), and every
    derived range;
  - generic, ambiguous (past or present senses), one-off and unsourced rows, with the words "no
    fetched source describes it" on every row whose page was not found; the ambiguous-target
    ruling's `xinjiang yangqin`; versions not aliases;
  - `STRUCK_HELD_BACK` and the sound-change guard, the helper test that exercises them on real
    builds both ways (batch 17's, not copied), and the wrong-table runs that showed each failing;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): the 5 earlier entries' missing
  source comments; any existing range or build a sheet's source contradicts (the leads in Global
  Constraints: the Cimbalom page's cited Schunda compass, C to e′′′ (C2–E6), against `cimbalom`
  E2–A6; the Santur page's image-only range; the hammered dulcimer's and yangqin's widths against
  `hammered dulcimer` D3–E6 and `yangqin` G2–A6; the berimbau's unsourced A2–C3); the family's
  absence from `HARMONIC_FAMILIES`; the 17 third-party `speech_recognition` DeprecationWarnings as
  #87 records them. Then **Follow-ups**: the audit's gaps; ranging the range WAITs from maker,
  museum and scholarly sources; checking the 5 earlier entries against sources; the engine
  changes that unblock the waits, most rows first. Then **Incidents and process**, as #87 has them
  (the fetches that returned 404 or 429 and how each was handled, any redaction and any
  institution's contacts kept, any load flake and its rerun).
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries()))"`
  and `uv run python -I build/batch-18-form-check.py plans/data/instrument-audit/batch-18.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full suite.**
  Run: `uv run pytest --dummy-only -W default tests/audio tests/test_process_state_guard.py`, then
  `uv run pytest`, with nothing else running.
  Expected: PASS, 100% coverage; the only warnings are the 17 known `speech_recognition`
  DeprecationWarnings (#87; any other is a new finding, understood before going on). A failure in
  one of the two known load-flaky tests (Global Constraints) is rerun alone and then the whole
  suite once, and recorded in #88.

- [ ] **Step 4: Run the docs lint, on its own, after the suite has finished.**
  Run: `nox -s lint-docs`. Expected: the strict build passes.

- [ ] **Step 5: Run the remaining checks.**
```bash
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-18-code-check.py plans/data/instrument-audit/batch-18.tsv
uv run python -I build/batch-18-quote-check.py plans/data/instrument-audit/batch-18.tsv
```
  Expected: everything passes; `matches 67 rows`; and `bad: []`. The `build/instruments/struck
  strings` folder is the one to listen to; the owner judges the sound.

- [ ] **Step 6: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 18 of the instrument catalog (struck strings), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch in
turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78). The
pre-push hooks take about 40 minutes, and nothing in the working tree may change while they run.

**Order:** the controller's shared files (and the plan's commit), then Tasks 1, 2 and 4 in
parallel. Task 3 follows Tasks 1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows
Tasks 3 and 4, and Task 6 comes last.

**Corrections to batch 17's plan carried here:**
- Batch 17's plan expected `welsh harp` to be an ALIAS of `triple harp` and `clarsach` and
  `clairseach` of `wire strung harp`, though their sources give each name to two instruments, one
  of them historical; the reviews dropped all three as ambiguous (#87). Here a name its sources give
  to two instruments, past or present, is ambiguous, and the plan names the cases to check first.
- Batch 17's rule 8 let `baroque triple harp` be an alias of `triple harp`, though the page calls
  the Welsh one «One common version» (#87's reversal). Here a version, type, variant or relative
  is a separate row, never an alias (the versions ruling and range ruling 6).
- Batch 17's range ruling had no rule for a compass a cited sentence gives one size, and the first
  reading of `saung gauk` missed «from C3 to F5» on its saved page (#87). Here range ruling 4b
  ranges that size only, and rule 9 has every such passage quoted and ruled on.
- Batch 17's quote check read a saved error page and still checked its quotes; #87 then ruled
  that a 404 is never saved. Here no error page is saved (a 404 goes in the notes, a 429 is waited
  out), and the check refuses one, an empty file and a 5xx page.
- Batch 17's rule for personal data named a third party's data without separating a private
  person's from an institution's (#87: the gravikord maker's address redacted, the Penn Museum's
  contacts kept). Here the rule says so, and the quote check lists every page with an email
  address for the controller.
- Batch 17's plan left the `alias_of` of an `its target, <name>` WAIT unspecified (#87: batches
  3–8 and 17 filled it, 9–16 left it empty). Here it holds the target, and the form check refuses
  one that does not.
- Batch 17's half B inferred `gravikord`'s 323 from «based on the West African kora», a relation,
  and the controller made it `none` (#87). Here a class comes only from words naming the
  mechanism, never from a parent relation.
- Batch 17's fetch rule did not warn that macOS's case-insensitive filesystem lets one page title
  overwrite another's scratch copy (#87's `Welsh_harp`). Here every page is saved straight to its
  row's slug.
- Batch 17's sound-change guard repeated its helper test's last assert (#87's parked minor). Here
  the helper test is not copied, and the new guards test only this family.
- Batch 17's form check indexed `RULE_TWO_PARENTS[row['hs'][:3]]`, which raises a KeyError for a
  class outside the table; this family has classes with no rule-2 set (312, 321), so the lookup
  here is `.get(..., set())`.
- Batch 17's Task 3 expected `test_harmonic_instruments_sound_their_note` on every new entry; that
  test covers only `HARMONIC_FAMILIES`, which does not hold struck strings, so here Tasks 3 and 5
  expect only the render test, and #88 reports the gap.
