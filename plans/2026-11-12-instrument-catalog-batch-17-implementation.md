# Instrument catalog batch 17 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the harps family from the audits' candidates. The family holds the instruments whose
strings run in a plane perpendicular to the soundboard (Hornbostel–Sachs 322: the open harps,
arched and angular, and the frame harps, with or without levers or pedals) and, by batch 4's
hand-off and the catalog's `kora`, the harp-lutes (323: the kora, the ngonis, the seperewa). Each
instrument gets a cited source for its name, its sound, how it is plucked and its range, and either
sounds unlike every other entry or is a listed sound-alike of the one it sounds like. The rest
become aliases, wait for an engine feature or a source, or are dropped with a reason.

**Architecture:** As in batches 3 to 16, a verification sheet (`batch-17.tsv`) decides every
candidate before any code is written. The family's 7 entries live in `strings.py` (154 lines),
which also holds the 5 struck strings; batches 14 and 16 already moved the clarinets and the free
reeds out the same way. So the harps section moves unchanged to a new `harps.py`, and `strings.py`
keeps the struck strings: the moved table becomes `_HARP_BUILDS`, and `HARPS` becomes
`_HARP_BUILDS + HARP_SOUND_ALIKES`, with the sound-alikes in a new `harp_sound_alikes.py`. The
catalog's one harp builder, `_harp(*, ring_seconds, low_pass, slope=8.0)`, already makes a plucked
string's series ringing down, and its three keywords are sound design (no source behind any
existing value), so a new harp with no other cited trait is a sound-alike, `builder` "unchanged".
This batch adds no builder, no keyword and no `sound_changes`: no foreseen harp trait has a sourced
number a `_harp` keyword takes, and a trait the build cannot make (bray pins, rattles, a drummed
belly) means the row waits. A new guard, `HARP_HELD_BACK`, holds every name the sheet holds back
for any reason but a sourced range. The sheet and the code each come in two halves, as explicit
lists: the frame harps (orchestral, folk and historical) with the boundary names that are no harp,
then the open harps (arched and angular), the harp-lutes and the lyres. The controller writes the
names file, the candidate lists and the three check scripts before anything is dispatched, so the
two sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `plucked`, `plucked_series`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all). Batch 16's plan (`plans/2026-11-12-instrument-catalog-batch-16-implementation.md`)
and its owner's checks (`plans/future-features.md` #86) are this plan's template and its ledger:
its controller step, its quote check (as the controller fixed it), its held-back guard, its module
move, its two parallel halves and its code check carry over, with the corrections listed at the
end of this plan. Batch 4's plan (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`)
holds the pitched sound-alike and strict range rules and the before-and-after build record, and
batch 4's sheet decided the lyres, zithers and the aeolian harp that reach this batch's candidate
list; batch 11's holds the balaban rule (a cited trait the build cannot make means the row waits).
This plan's own path is `plans/2026-11-12-instrument-catalog-batch-17-implementation.md`. The
branch is `feat/instrument-catalog-batch-17`, made from batch 16's tip, `1ecc25d9` (batch 16's
final review fixes); Task 6 records that SHA in #70. The candidates come from
`plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `harp` (20, every one from the round-2 audit
  `harps.md`; no other audit's `merged.tsv` family names harps);
- the `round-1/merged-missing.tsv` rows whose `family` contains `harp` (11: `swarmandal`,
  `sasando`, `konghou`, `krar`, `begena`, `nyatiti`, `seperewa`, `ngombi`, `gravikord` and
  `celestial harp` with family "harps", and `kithara (partch)` with "plucked strings (or harps)",
  taken as batch 16 took `chromelodeon`'s "organs (or free reeds)").

Together: 30 unique names (`ngombi` is in both), none of them a catalog name or alias (checked for
this plan at `1ecc25d9`: the catalog holds 704 entries and 122 aliases, 826 names, and no harp
alias at all). So there are **30 candidate names** (counted for this plan, the controller
recounts). The audits' alias lines whose left-hand names are no catalog name and whose target or
note names a harp candidate or a harp the catalog holds propose **16 alias names**:
- from `harps.md`'s "Aliases" (11 lines, 15 names): "welsh harp, telyn -> triple harp (catalog)"
  (2); "clarsach, clairseach, queen mary harp -> wire strung harp (catalog)" (3); "pedal harp ->
  concert harp (catalog)"; "lever harp, folk harp -> celtic harp (catalog)" (2); "arpa paraguaya
  -> paraguayan harp"; "arpa llanera -> llanera harp"; "gonghu -> gonggu (Korean konghou; alias of
  konghou line, see Held back)" (`gonghu` only: `gonggu` is the line's target, a name for the
  konghou the row decides); "saung -> saung gauk"; "ombi -> ngombi"; "domu -> kundi"; "harp lute
  -> kora (class name, not an instrument)";
- from `new-environmental-instruments.md`'s "Aliases": "wind harp -> aeolian harp (monumental
  versions are the same principle at scale)" (`aeolian harp` is a candidate).
`harps.md`'s "yaal -> yazh" is no row: `yazh` is neither a candidate nor a catalog name (the audit
dropped it "only for lack of range data"); Task 6 lists both in #70 for a later pass. The other
audits' alias lines that say "harp" name another family's instrument (`jaw harp`, `glass harp`,
`talharpa`, the struck strings' `chang` and hammered dulcimer, `ngoni`): not rows (checked with
grep). The round-1 alias tables are not used, as no earlier batch used them. With one hand-off row
(below), the sheet will hold **47 rows**. An alias row's `audit_name` is its audit line as written
above (its URL, if any, left out).

The hand-offs from earlier sheets (checked: `batch-1.tsv` to `batch-16.tsv` with grep for each
candidate and for `harps`, and `plans/future-features.md` #70–#86):
- `donso ngoni`: `batch-4.tsv` DROP, hs 323, «A harp-lute like the kora, which the catalog places
  in harps: harps». A DROP naming a family is a hand-off that family's batch decides (batch 15's
  `claviharp` and `dolceola`, batch 16's `reed organ`). A half-B candidate, decided here.
- `kamele ngoni`: `batch-4.tsv` DROP, hs 323, «A harp-lute like the kora, which the catalog places
  in harps: harps (as donso ngoni)». It is batch 4's spelling (`plucked-strings.md`); `harps.md`
  spells the candidate `kamale ngoni`. Not a candidate, so it gets a **hand-off row** of its own
  in half B, after the alias rows, `audit_name` `kamele ngoni`, decided by rule 8 (duplicates).
- Already decided, and candidates: each row is DROP, its notes beginning "Already decided:" and
  naming the earliest sheet that decided it and its status (each is in `batch-4.tsv` only, never
  a catalog name or alias, so the code check's last branch applies):
  - half A: `aeolian harp` (`batch-4.tsv` DROP: «not a played plucked string»); `kithara
    (partch)` (`batch-4.tsv` WAIT `a sourced range`, under the name `partch kithara`, since the
    parentheses cannot be a catalog name: this row's `name` is `partch kithara`, its
    `audit_name` `kithara (partch)`); `sasando` (WAIT `a sourced range`, a tube zither, hs 312);
    `swarmandal` (WAIT `a sourced range`, a box zither, hs 314.122-5,6);
  - half B: `begena` (WAIT `a buzzing bridge`, a box lyre, hs 321.2); `krar` (WAIT `a sourced
    range`, hs 321.2); `nyatiti` (WAIT `a sourced range`, hs 321.2).
- Decided elsewhere, not candidates, no row: `claviharp` (`batch-15.tsv` WAIT, keyboards, after
  `batch-4.tsv` dropped it there), `jaw harp` (`batch-1.tsv` WAIT), `glass harp` (`batch-1.tsv`
  SHIP), `laser harp` (`batch-6.tsv` DROP), `talharpa` (`batch-7.tsv` WAIT, bowed strings), `harpejji` (`batch-4.tsv` SOUND_ALIKE of `chapman
  stick`), `lyre of ur` (`batch-4.tsv` WAIT), `ngoni` (`batch-4.tsv` WAIT).
- #86 says "none were dropped to harps or struck strings" of batch 16's rows, and #76–#85 hand
  nothing here beyond the two ngonis (#74 parks the question of `lyre`, `kora` and `harp guitar`
  sitting in harps: "the family split needs a decision before any of them ships").

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, parentheses and hyphens go only in the title (`cross strung
  harp` titled "Cross-strung harp"). A candidate keeps its audit name (the naming ruling of batch
  12), except where the name cannot be a catalog name (`kithara (partch)`, decided by batch 4 as
  `partch kithara`).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families),
  "with the existing player-facing splits kept where they already exist". The harps family holds
  the harps (322) and the harp-lutes (323); the boundary rulings below decide each row.
- Hornbostel–Sachs, every code this plan relies on checked against Wikipedia's raw wikitext on
  2026-11-13 (`Hornbostel–Sachs` and `List_of_chordophones_by_Hornbostel–Sachs_number`):
  - 322 Harps: "The plane of the strings lies perpendicular to the resonator's surface."; 322.1
    "Open harps – The harp has no pillar" (322.11 "Arched harps", 322.12 "Angular harps"); 322.2
    "Frame harps – The harp has a pillar"; 322.21 "Without tuning mechanism" (322.211 "Diatonic
    frame harps", 322.212 "Chromatic frame harps", 322.212.2 "With strings in two planes crossing
    each other – Cross-strung harp"); 322.22 "With tuning action." (322.221 "With manual tuning
    action – Lever harp", 322.222 "With pedal action – Pedal harp"), each with .1 (one plane) and
    .2 (two planes crossing).
  - 323 Harp lutes: "The plane of the strings lies at right angles to the sound-table; a line
    joining the lower ends of the strings would be perpendicular to the neck. These have notched
    bridges." (the list names the Kora and the Seperewa).
  - 321.2 "Yoke lutes or lyres – The strings are attached to a yoke which lies in the same plane as
    the sound-table and consists of two arms and a cross-bar" (321.21 bowl lyres, 321.22 box
    lyres); 321.322 "Necked box lutes" (the list names the Harp guitar); 311.112 "Poly-idiochord
    musical bows or harp-bows"; 314.22 "Harp zithers".
  - Suffixes: "An 8 indicates that the instrument has a keyboard attached, while a 9 indicates the
    instrument is mechanically driven" (the main page). The chordophone list adds, under its 33
    heading, "'''4''': Hammers or beaters", "'''5''': Bare hands and fingers", "'''6''':
    Plectrum", "'''7''': Bowing", "'''8''': Keyboard", "'''9''': Using a mechanical drive"; the
    Kora, Seperewa and Simbing infoboxes write "323-5". A suffix is written only when a fetched
    source for that row gives it.
  - Traps found while writing this plan: the Triple harp infobox gives "3.2.2", which is no class
    (a row's `hs` is written from its quoted words); the Ennanga page is a redirect to African
    harp and Arpa llanera to `harp#Venezuelan harps` (cite the target page, and save the redirect
    too); the aeolian harp's class is "31 (wind-excited)" in round 1 and "314.122" (box zithers)
    in the environmental audit: leads, and the row is already decided. The Gravikord, Konghou,
    Adungu and Cross-strung harp pages give no code.
  A worker who finds a code that a fetched list does not hold reports it to the controller before
  any row relies on it. No other code is assumed.
- "Every name, range and description checked against a source cited in the code … A range that no
  source gives is the instrument's documented playable span from a maker or museum, or the entry
  waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict"). This
  plan's range ruling is below. A row with no sourced range is WAIT, `waits_for` `a sourced
  range`, and **the range is checked first**, before any engine limit or other trait (batch 13's
  reversals): a row with neither a range nor a buildable trait waits for the range, its notes
  keeping "Engine limit, once ranged: …".
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry, sharing
  the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the same
  instrument) stays an alias." A sound-alike is pitched exactly when its parent is, and a pitched
  sound-alike gives its own sourced range (batch 4). This batch's sound-alikes carry no
  `sound_changes` (the sound-alike ruling).
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as an
  approximation. The spec's table binds this family through "sympathetic strings, a buzzing bridge
  (jawari)" and "sub-audio fundamentals". Earlier batches added the other names a WAIT may give: a
  pitch LFO (vibrato), a pitch LFO (portamento between notes), an amplitude LFO, a pitch and
  amplitude LFO (batch 2), filter resonance, a filter envelope, moving formants (batch 6); a
  buzzing membrane (batch 5); a sourced drone tuning and its own build (batch 7, 12); a range
  above C8 (batch 10); a sourced detune and a sourced footage (batch 13); a sourced reed and bore
  (batch 14); a sourced partial series (batch 15). This plan adds no new wait name; `its own build
  (<the trait>)` names any trait no builder makes. What the engine has: `plucked` (one harmonic
  series, `ring_seconds` down to `sustain`, up to two more `courses`, a pick noise, a fixed low or
  high pass, drive); no LFO, no buzz against a bridge or pin, no rattle, a series that does not
  change with the note.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not builds.
- Reuse `_harp` under its current name; add no builder or keyword (the sound-alike ruling). A row
  whose source states a trait `plucked` could make with a sourced number is reported to the
  controller before its half's code task (the SHIP ruling).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the sheet,
  in every row of every status, is verbatim from a page the worker fetched and saved, or from a
  committed file the notes name (an earlier sheet, an audit file, #70 or the spec), and the quote
  check finds each one. No request carries the owner's email or any personal data, in a header, a
  URL or a payload (#78).
- Sources: an unsaved WebFetch read is a lead, never a source (#85's `nickelodeon`): every cited
  page is saved raw with `curl -fsS -L` (for Wikipedia, the `action=raw` wikitext). `-f` matters:
  without it curl saves Wikimedia's "Wikimedia Error" page with exit 0 (4 of 25 fetches while
  writing this plan), and the quote check refuses a saved error page. A page that refuses curl
  (403, 429) is fetched from the Internet Archive's copy
  (`https://web.archive.org/web/<date>id_/<url>`, the `id_` form returns the page as archived),
  saved, and cited by its archive URL. A saved page holding a third party's personal data (a phone
  number, an email address) is redacted by the controller before any row cites it, and no row
  quotes it (#86, the `engkerurai` page). Uncited lines (range ruling 10), blogs, forums,
  retailers' listings, hobbyists' pages (the Oddmusic gallery among them) and musicbrainz mirrors
  are not sources; a scholarly article (a journal paper, a conference paper, a museum's or
  university's publication) is.
- Code comments name committed files (`plans/data/instrument-audit/batch-17.tsv`), never the
  gitignored `build/` files (batch 9's fix), and never describe a builder, keyword or table use
  that does not exist (batch 16's final review: "once a builder takes cents" comments).
- Data is never evaluated as code: a check script reads a literal with `ast.literal_eval`, never
  `eval` or `exec`.
- The 7 entries already in the family keep their names, titles, ranges, builds and order, `lyre`
  and `harp guitar` included (#74 asks the owner whether they move). New entries come after the 7.
  An existing entry changes only for a cited bug, and not in this batch: the 7 carry no source
  comment, so a range or build that a fetched source contradicts is reported in #87 for the owner
  (batches 10 to 16's rule). Leads already seen while writing this plan, for the workers who fetch
  those pages to check under range ruling 10: the Pedal harp page gives «the range is
  C{{music|b}}<sub>1</sub> to G{{music|b}}<sub>7</sub>» (and "usually ending on G♭", a hedge)
  against the catalog's `concert harp` Cb1–G#7; the Kora infobox's range is an image ("Traditional
  Range of the Kora.png", not quotable) and the audit's Grinnell record gives D2–F5 for a 21-string
  kora against the catalog's `kora` F2–C6; the Triple harp page gives «about five octaves» against
  `triple harp` C2–C7. Task 1's before-and-after record of every entry checks that the move changes
  nothing, and Tasks 3 and 5 repeat it.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns, a module docstring's first line included: batch 14's first line
  was 123 columns), basedpyright and ty clean, 100% coverage. "I don't like short abbreviated
  variables." "explicit is better than implicit." "Whenever you see warnings thrown by a test, you
  should understand why it's happening and be concerned": a warning is a finding, and it must be
  understood before going on. #85 and #86 record 17 DeprecationWarnings under `-W default` from the
  third-party `speech_recognition` (it imports `aifc`), filtered on purpose in `pyproject.toml`; a
  report says "the 17 known speech_recognition warnings, no other" when that is what it saw, never
  "no warnings".
- Process: run `nox -s lint-docs` on its own, never while a test run is going (#84: a native-driver
  test failed while the docs lint ran beside it). Two load flakes are known: #84's
  `tests/engine/test_game_engine.py::TestReplayRestartExitStatus::test_a_status_no_exit_code_names_is_passed_through`
  (native run) and #86's `test_command_crash_boundary.py` signal test, case [2] (its 60 s
  subprocess timeout under xdist). If one of them fails, rerun it alone, then the whole suite once;
  record it in #87 either way. Any other failure is a finding.
- Commits as batches 4 to 16: `SKIP=replay-metrics git commit`, with the subject `Plans: …`,
  `Instrument catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76), so copy each commit message from this plan, never from memory.
  Write no `.md` file beyond those Task 6 names. Never use `git stash`: the stack is shared with
  other worktrees and sessions (#80). Set work aside with a temporary commit instead. A task that
  changes nothing makes no commit, and its report says so.

## Review Focus

1. **A string count, a width, a tuning or an image read as a range.** Harp pages give "47
   strings", "32 strings", "13 to 16 strings", "about five octaves", "4+ to nearly 8 octaves",
   "roughly two to six octaves", "tuned to a diatonic scale … G major/E minor", "pentatonic", the
   Pedal harp page's "usually ending on G♭", and the Kora infobox's range as an image file. Range
   ruling 5 makes none of them a range; the form check needs `Range:` with a quoted passage the
   quote check finds on the saved page; the code check compares every shipped range with the sheet.
2. **A model's or one size's range given to the bare name.** Lever harps are sold in many sizes,
   the Paraguayan harp with 32 to 46 strings, the saung with 13 to 16, the adungu in soprano to
   bass sizes; the gravikord's page gives each side its own compass. Range ruling 4 ranges a
   model's row from its maker's model page only, ruling 6 makes a bare name with several sizes and
   none called standard wait, and ruling 1 lets one source's stated compasses of one instrument's
   rows make its range (the derivation shown).
3. **A non-harp built as a harp because of its name or a "harp-like".** Lyres (321.2), zithers
   (the sasando's "a harp-like … tube zither", the swarmandal, the aeolian harp), the jaw, mouth
   and blues harps, the harp guitar and keyed harps are not this family's; a harp-lute coded 322
   or a frame harp parented on `kora` mixes the two mechanisms. The boundary rulings decide them,
   the form check needs an `hs` matching `(322(\.[0-9]+)*|323)(-[0-9]+)*` on a sound-alike and
   "Parent (rule 1):" for any parent outside its mechanism's rule-2 set (`lyre` and `harp guitar`
   are in no set).
4. **A cited trait the build cannot make shipped as a plain sound-alike, or a guard that passes
   only because its table is empty.** The audit names bray pins ("a buzzing edge", the gothic
   harp), "small metal rattles on pegs" (the ennanga), strings that "double as jingles" and a belly
   that "can be drummed" (the ardin). The sound-alike ruling makes each a WAIT once its source
   states it; the reviewers read each sound-alike's quoted sound passage for such a trait. Task 1
   tests each guard's helper on a real build both ways (`names_listed` on a real name, a real alias
   and a non-name; `entries_with_sound_changes` on the organs' `bourdon` and on the harps) and shows
   each guard failing on a wrong table.
5. **A name decided twice.** The seven `batch-4.tsv` names, `kamele ngoni` beside `kamale ngoni`,
   `chang` (also the struck strings audit's row, a dulcimer), `wind harp` with `aeolian harp`,
   `telyn` and `welsh harp` beside `triple harp`, `baroque triple harp` beside `triple harp`,
   `saung` beside `saung gauk`, and `gonghu` beside `konghou` are each decided once. Rule 8 decides
   duplicates, the code check finds every name exactly once, and the step checks list every
   candidate once.

---

## File Structure

- Create `src/glitchygames/audio/instruments/harps.py`. It takes the "Harps" section of
  `strings.py` (its header comment, `_harp` and the `HARPS` table, renamed `_HARP_BUILDS`),
  unchanged.
- Create `src/glitchygames/audio/instruments/harp_sound_alikes.py`, holding `HARP_SOUND_ALIKES`.
- Modify `src/glitchygames/audio/instruments/strings.py`: it keeps the "Struck strings" section
  only.
- Modify `registry.py` (it imports `STRUCK_STRINGS` from `strings.py` and `HARPS` from
  `harps.py`; their places in `FAMILY_TABLES` don't change), the docstring that names `strings.py`
  as the harps' home (`bowed_strings.py` lines 4–5), and `aliases.py` (the batch's ALIAS rows).
  No process-state guard listing names anything in `strings.py` (checked with grep), so
  `tests/test_process_state_guard.py` does not change; Task 1 runs it.
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5).
- Create `plans/data/instrument-audit/batch-17.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #87), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #87):

- **The harps get their own module, and `strings.py` keeps the struck strings.** Every family a
  batch has grown since batch 4 has a module of its own and a sibling sound-alikes module that
  names it. The harps section is self-contained: only `registry.py` imports `HARPS` (checked with
  grep), no other module imports `_harp`, and no process-state listing names it. `strings.py` is
  not renamed (the struck strings batch, 18, may decide that; #87 asks). Task 1's before-and-after
  record of all 704 builds checks the move.
- **The boundary rulings.** A row's family is decided by what sounds and how, from its fetched
  source's words, with the Hornbostel–Sachs class those words imply:
  1. *Harps* (322): strings in a plane perpendicular to the soundboard, plucked by the fingers:
     open harps (arched 322.11, angular 322.12) and frame harps (322.2: diatonic, chromatic and
     cross-strung, lever and pedal harps).
  2. *Harp-lutes are decided here, as 323, never 322*: a notched bridge with the strings at right
     angles to the soundboard (the kora, the ngonis, the seperewa, the simbi, the gravikord if its
     page says so). Batch 4 handed `donso ngoni` and `kamele ngoni` here because "the catalog
     places [the kora] in harps"; the catalog's `kora` stays where it is (#74's open question).
     Their `hs` is 323 (with the row's sourced suffix), and their rule-2 parent is `kora`.
  3. *A lyre is plucked strings*: a yoke lute (321.2) is DROP "belongs to plucked strings (a
     lyre, H-S 321.2): <its words>" when no earlier sheet decided it (`krar`, `begena` and
     `nyatiti` are already decided). The catalog's `lyre`, like `harp guitar` (a necked box lute,
     321.322), stays in harps unchanged (#74) and is never a rule-2 parent.
  4. *A zither is plucked strings*: a tube, board or box zither (312, 314: the sasando's "harp-like
     … tube zither", the swarmandal, a harp zither 314.22) or a harp-bow (311.112) is DROP "belongs
     to plucked strings (a zither, H-S <class>)" when not already decided.
  5. *The aeolian harp is wind-sounded*: its strings sound only when the wind drives them into
     overtones (the round-1 audit's "31 (wind-excited)", the environmental audit's 314.122), no
     harp by class, and `batch-4.tsv` already dropped it («not a played plucked string»). Its row is
     DROP "Already decided", and `wind harp` follows its dropped target.
  6. *"Harp" in a name is not a harp*: the jaw harp and mouth harp (plucked idiophones, 121.2,
     `batch-1.tsv`), the blues harp (a harmonica, free reeds, 412.132), the harp guitar (321.322),
     the glass harp (friction instruments) and the laser harp (a controller, `batch-6.tsv`) are
     decided by what sounds. Any such row is DROP to that family, or "Already decided".
  7. *Keyed harps are keyboards*: a harp whose strings keys pluck (the claviharp, `batch-15.tsv`
     WAIT; a "harp piano"; suffix -8) is DROP "belongs to keyboards (a keyed harp): <its words>".
  8. *Electric harps*: a harp whose own strings sound and a pickup amplifies (the gravikord, an
     electric lever harp) is the harp it is, as the catalog's electric guitars and batch 4's
     `harpejji` stay plucked strings; one with no sound of its own is electronic.
  9. *Bowed and struck*: a bowed harp (the talharpa, a bowed lyre) is bowed strings; a struck
     "chang" (a dulcimer) is struck strings (batch 18).
  10. *The `hs` cell* holds the class a fetched source gives (an infobox, or a sentence naming what
      sounds and how, quoted, with the code it implies, written from the classes and suffixes
      above), else `none`. A SOUND_ALIKE row's `hs` fullmatches `(322(\.[0-9]+)*|323)(-[0-9]+)*`.
- **A harp is a sound-alike unless a cited trait sets it apart.** `_harp` is `plucked` over
  `plucked_series(count=20, decibels_per_octave=slope, pluck_position=0.33)` with a ring time and
  a low pass, every value sound design. A row whose sources name no other trait is a SOUND_ALIKE
  (the parent ruling), `builder` "unchanged". A string count, one row or two or three, crossing
  rows, levers, pedals or no tuning action, a tuning or scale, a string material (gut, nylon,
  wire, silk, goat hair), a size, the body (arched, angular, framed, calabash, trough, box), how
  it is plucked (fingers, nails, a plectrum), a maker, a region or a colour word ("bright",
  "soft", "warm", "percussive") is no trait, unless a fetched source names an effect on the sound
  with the numbers a `_harp` keyword takes. A trait the engine cannot make is WAIT `its own build
  (<the trait>)` or the spec's or an earlier batch's feature name, with the source quoted: bray
  pins buzzing against the strings (`its own build (bray pins)`), rattles or jingles on the pegs,
  neck or strings (`its own build (rattles)`), a belly drummed while playing (`its own build (a
  drummed resonator)`), sympathetic strings (`sympathetic strings`), a buzzing bridge (`a buzzing
  bridge`). A technique (a glissando, a string pressed to bend it, harmonics, damping, the
  konghou's vibrato by pressing the second row) is how a player sounds the instrument, not its
  build. A trait `_harp` could imitate by turning an unsourced keyword (a longer `ring_seconds`
  for wire, a darker `low_pass` for gut) is not made by the build: batch 11's contraforte and the
  balaban rule.
- **The SHIP ruling.** This batch plans no SHIP and no `sound_changes`. A row whose fetched source
  states a trait in the numbers `plucked` takes (a doubled course at a stated interval, a stated
  ring time at a stated note) is reported to the controller before its half's code task; the
  controller rules it, in a sheet fix commit, a WAIT `its own build (<the trait>)` or a SHIP with
  its rule and test added to this plan. The form check refuses a SHIP status until then.
- **The parent ruling.** A SOUND_ALIKE's parent is a catalog entry from before the batch (never a
  sound-alike), never one of `APPROXIMATING_NAMES`:
  1. The entry its own source relates it to ("a type of lever harp", "a Welsh triple harp", "like
     the kora", "a wire-strung harp"), quoted in the notes after "Parent (rule 1):". Only this rule
     may name `lyre`, `harp guitar` or another family's entry.
  2. Otherwise the entry of the same mechanism whose `lowest` note is nearest the row's own lowest
     note in semitones, the earlier catalog entry on a tie, written after "Parent (rule 2):" with
     the mechanism and the semitone counts. The mechanisms: harps (322, open or framed: `concert
     harp`, `celtic harp`, `wire strung harp`, `triple harp`); harp-lutes (323: `kora` alone).
  3. The sizes or models of one type share the type's parent: never a sound-alike's sound-alike.
- **Range ruling for harps.** A sourced range is the lowest and highest sounding notes that one
  fetched source states for the instrument:
  1. *Stated, by one source*: both notes as the range or compass, from one source (batch 14's
     `xaphoon`: two sources for one range is no range), in note names with octaves (scientific
     `C2`; Helmholtz `C` or `c‴`, whose octave marks fix the octave, as #84 confirms; a named note
     whose octave the source fixes), or the lowest note and an exact span or string count above
     it, diatonic or chromatic as the source says ("diatonic from C2, 36 strings"), as batch 7
     allowed. One source's compasses for one instrument's rows or sides (the gravikord's "left
     side … right side") make its range from the lowest to the highest, the derivation shown.
  2. *Sounding, levers and pedals as stated*: notes the source gives as the instrument's range are
     taken as given, the lever or pedal settings the source states included (the catalog's
     `concert harp` reads Cb1 with the pedals flat); nothing is added for a lever or pedal the
     source does not state. A range the source calls written or notated counts only with the
     transposition its own source states.
  3. *Extensions and extremes*: the stated compass, and nothing beyond it. Strings some models
     add, or a note in parentheses, are extremes: the range is the compass without them, or the
     row WAITs.
  4. *A maker's or museum's page ranges that model only*: a maker's model page (Lyon & Healy,
     Salvi, Camac, Dusty Strings; a kora, konghou or Paraguayan harp maker) or a museum's object
     record (the Met, MIMO, the Horniman, Grinnell, Brooklyn, Tervuren) ranges a row named for
     that model or object only, never the bare type name (#85, the Neupert "harpsichord Hass" page).
  5. *Not a range*: a hedged span ("about", "approximately", "roughly", "typically", "usually",
     "up to"); a general or notation rule ("harps are written on two staves", "lever harps span two
     to six octaves" of the class); a width or count with no pitch ("five octaves", "47 strings",
     "21 strings", "4+ to nearly 8 octaves"); note letters with no octaves ("C to C"); a key or
     tuning ("in E-flat", "G major/E minor", "pentatonic", "diatonic"); a tuning list or a scale
     called a range; a tessitura; one pitch; or a chart drawn as an image (the Kora infobox's file,
     a staff chart: #86's concert accordion charts), however readable. The audit's ranges are
     leads, not sources (its "VERIFIED" saung gauk and gravikord included).
  6. *Several sizes, none standard*: a bare type name with several sizes, models or string counts
     is ranged only from a source that calls one standard, usual, most common or traditional for
     the bare name. "Became widespread", "popular" or "modern" is none of these (#86's `khromka`:
     «позднее получила распространение», "later became widespread"). A source giving one
     instrument two ranges has given none. With neither, the row WAITs (batch 7's rule; batch 14's
     `birbyne`).
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
      no `{{citation needed}}` first, in a section not tagged `{{Unreferenced section}}`. The
      citation must support the line: where the cited work is reachable the worker opens it, and
      a citation that gives no range (batch 11's `shehnai`) or points to a retailer is none. An
      uncited line is not a source for a range or for a trait that decides a WAIT.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then the
  derivation.
- **Generic and ambiguous terms.** A name its source gives to a class or to several instruments is
  DROP "a generic term for <the instruments>" or "an ambiguous name: <the instruments>", unless the
  source makes it one instrument's name (then rule 3). The cases to check: `angular harp` and
  `egyptian arched harp` (322.12 and 322.11 are classes; a row of its own only if a source makes
  it one instrument with a stated range), `harp lute` (the audit's own "class name, not an
  instrument"), `telyn` (Welsh for harp), `chang` (the Chang (instrument) page's Persian angular
  harp, and the struck strings audit's `chang`, a dulcimer: decided here once; if a fetched page
  gives the name to both, the row is DROP "an ambiguous name", and #70 records it for the struck
  strings batch), `konghou` (ancient angular and modern frame forms: one instrument or a name for
  several, decided on its page) and `andean harp` (the audit's only source is the general Harp
  page).
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's in-production
  line): DROP "a one-off instrument, not a type a game would ask for" for one maker's or artist's
  design never made as a type; DROP "no fetched source describes it" when no fetched page describes
  the row, applied the same to every such row, candidate or alias name (`celestial harp`, whose
  only lead is the Oddmusic gallery, is the first case to check). A reconstruction makers offer
  today (a gothic harp, a baroque triple harp), or a type a museum holds, is not a one-off.
- **Two halves, as explicit lists.** Half A, the frame harps (orchestral, folk and historical)
  and the boundary names that are no harp (a zither, a wind-sounded string, Partch's kithara), is
  these 13 candidates:
  `aeolian harp`, `andean harp`, `arpa jarocha`, `baroque triple harp`, `celestial harp`, `cross
  strung harp`, `gothic harp`, `kithara (partch)`, `konghou`, `llanera harp`, `paraguayan harp`,
  `sasando`, `swarmandal`.
  Half B, the open harps (arched and angular), the harp-lutes and the lyres, is the other 17:
  `adungu`, `angular harp`, `ardin`, `begena`, `chang`, `donso ngoni`, `egyptian arched harp`,
  `ennanga`, `gravikord`, `kamale ngoni`, `krar`, `kundi`, `ngombi`, `nyatiti`, `saung gauk`,
  `seperewa`, `simbi`.
  The list decides the half. The alias names go with the half whose candidate or target their line
  names: half A's 12 (`welsh harp`, `telyn`, `clarsach`, `clairseach`, `queen mary harp`, `pedal
  harp`, `lever harp`, `folk harp`, `arpa paraguaya`, `arpa llanera`, `gonghu`, `wind harp`) and
  half B's 4 (`saung`, `ombi`, `domu`, `harp lute`), each half in that order, then half B's
  hand-off row `kamele ngoni`. So half A's sheet holds 25 rows and half B's 22.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the batch
  or a SOUND_ALIKE row of the same half, never a row of the other half. So Task 4 needs nothing
  from Task 2. Half B drafts to a build file, appended to the sheet once half A is committed. The
  form check accepts a row the code already holds with the same target or parent (batch 7's
  lesson).
- **A held-back guard.** As batch 16's `FREE_REED_HELD_BACK`, this batch's guard is
  `HARP_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose
  reason is not `a sourced range` (an engine feature, a build of its own, sub-audio fundamentals,
  a range above C8), and every alias row that waits for such a row. A test refuses each of its
  names in the catalog and the aliases through `names_listed`, which Task 1 tests on a real name,
  a real alias and a non-name, and the code check compares the table with the sheet, in the
  sheet's order.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no
  SOUND_ALIKE or ALIAS row, its code task still fills `HARP_HELD_BACK` with the half's held rows
  and runs the code check, which must pass; its other steps are skipped, it commits only if the
  test file changed, and Task 6 records the skip in #87.
- **Out of scope:** the audit's "Held back" (the konghou subtypes: wo, shu and feng shou konghou;
  sogonghu, sugonghu, wagonghu; kudaragoto and kugo) and "Gaps you could not close" (the Pokot
  harp, Bagirmi, the Kotoko galdyama trio, Tibetan and Ottoman harps (cenk); the harp guitar
  variants: Dyer Style 8, Gibson Style U, Knutsen, contraguitar); the names its draft dropped
  (`yazh` and `yaal`, `vajra`, `kafir harp`, `padhar harp`, `bolon`, `kinnor`, `hook harp`, `dital
  harp`, `electric harp`, `double harp` / `arpa doppia`); `gonggu`; and the harp names a page
  mentions in passing. Task 6 lists them in #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of the build files is committed.

- [ ] **Step 0: The branch and the plan.** Run `git branch --show-current` and `git rev-parse
  --short HEAD`. Expected: `feat/instrument-catalog-batch-17` and `1ecc25d9`. Anything else: stop
  and find out why. Copy this plan to `plans/2026-11-12-instrument-catalog-batch-17-implementation.md`
  and commit it:
```bash
git add plans/2026-11-12-instrument-catalog-batch-17-implementation.md
SKIP=replay-metrics git commit -m "Plans: batch 17 of the instrument catalog (harps), the implementation plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-17-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-17-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names), len(instruments.CATALOG), len(instruments.ALIASES))
"
```
  Expected (after pygame's banner): `names before 826 704 122` (checked for this plan at
  `1ecc25d9`). Any other number means the branch is not batch 16's tip: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && tolower($4) ~ /harp/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /harp/ {print tolower($1)}' round-1/merged-missing.tsv
} | LC_ALL=C sort -u | LC_ALL=C comm -23 - ../../../build/batch-17-names-before.txt > ../../../build/batch-17-candidates.txt
cd ../../..
```
  Write the plan's 13 half-A names, one per line, to `build/batch-17-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-17-candidates.txt build/batch-17-half-a.txt > build/batch-17-half-b.txt`
  and `wc -l build/batch-17-*.txt`.
  Expected: 30 candidates, 13 in half A, 17 in half B, and
  `LC_ALL=C comm -13 build/batch-17-candidates.txt build/batch-17-half-a.txt` prints nothing.
  Check that `build/batch-17-half-b.txt` is exactly the plan's half-B list. The sorted union before
  the `comm` is also 30 names (no candidate is already a catalog name or alias).

- [ ] **Step 3: The form check,** `build/batch-17-form-check.py`. Copy `build/batch-16-form-check.py`
  and change it as follows; `STATUSES`, `pattern`, `held_as_this_row`, `taken`, `in_span`, the
  `bad` list's shape and the output stay.
  - The docstring:
```python
"""Batch 17's sheet form check: uv run python -I build/batch-17-form-check.py SHEET.

Batch 16's form check (build/batch-16-form-check.py) with batch 17's changes (batch 17's plan,
"Before the tasks" Step 3): the harps family, a sound-alike's harp or harp-lute class, no SHIP and
no sound changes, no drones and no tags, and a parent outside its mechanism only by the parent
ruling's rule 1.
"""
```
  - Remove `FREE_REED_CLASS`, `REED_PIPE_CLASS`, `MOST_DRONES`, `SOUND_CHANGE_KEYS`,
    `OCTAVE_REED_SETS`, `RULE_ONE_PARENTS`, `free_reed_parents`, `parent_cents`, `droned`,
    `changes_sourced` and `shipped_build`; keep `SOUND_CHANGES` and `changes`; `names_before`
    reads `build/batch-17-names-before.txt`; refresh `APPROXIMATING_NAMES` from the test file's
    (unchanged since batch 13); `ranged` drops its octave line; and add:
```python
# Hornbostel-Sachs classes checked against Wikipedia's lists for batch 17's plan: 322 (harps, with
# any subclass) and 323 (harp lutes), each with any suffixes a row's source gives
HARP_CLASS = re.compile(r'(322(\.[0-9]+)*|323)(-[0-9]+)*')
# The parent ruling's rule 2: each mechanism's catalog entries (batch 17's plan)
RULE_TWO_PARENTS = {
    '322': {'concert harp', 'celtic harp', 'wire strung harp', 'triple harp'},
    '323': {'kora'},
}


def alike_allowed(row):
    """A catalog parent from before the batch, outside its mechanism's set only by rule 1."""
    parent = row['alias_of']
    if parent in APPROXIMATING_NAMES or parent not in pre_batch_entries:
        return False
    in_mechanism = parent in RULE_TWO_PARENTS[row['hs'][:3]]
    return in_mechanism or 'Parent (rule 1):' in row['notes']
```
  - The `bad` list's family test is `row['family'] != 'harps'`; its tag test is `row['tags'] !=
    ''`; it adds `row['drones'] != 'none'` and `row['status'] == 'SHIP'` (the SHIP ruling); its
    sound-alike test reads
```python
       or (row['status'] == 'SOUND_ALIKE'
           and (not row['sound_source'].startswith('http') or not ranged(row)
                or not HARP_CLASS.fullmatch(row['hs']) or changes(row) != {}
                or row['builder'] != 'unchanged' or not alike_allowed(row)))
```
    and its ALIAS test is `row['alias_of'] not in pre_batch_entries | alikes |
    set(instruments.CATALOG)`.
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: The quote check,** `build/batch-17-quote-check.py`. Copy
  `build/batch-16-quote-check.py` (as the controller fixed it: UTF-8, else the page's declared
  charset, else windows-1252, each non-UTF-8 read listed; #86) and change it as follows;
  `CITATION`, `UNCITED_TAG`, `read_page`, `visible`, `located`, `cited`, `quoted`, `on_page` and
  the every-row ledger check stay.
  - The docstring: batch 16's, with "Batch 17's" and `build/batch-17-quote-check.py` in its first
    line, "Batch 16's quote check (build/batch-16-quote-check.py) with batch 17's changes (batch
    17's plan, "Before the tasks" Step 4)" in its second paragraph, "A SOUND_ALIKE row's Range:
    passages must be on its saved pages", and a last sentence: "A saved page that is an HTTP error
    page (a Wikimedia Error page, or a 403, 404 or 429 title) is a failure."
  - `PAGES = Path('build/batch-17-pages')`, and:
```python
# A page curl saved without -f: Wikimedia's error page, or a title naming an HTTP error
ERROR_PAGE = re.compile(
    r'<title>[^<]*(Wikimedia Error|403|404|429|Forbidden|Not Found|Too Many Requests)[^<]*</title>',
    re.IGNORECASE,
)
```
    and each page read appends `(row['name'], 'saved page is an error page: ' + path.name)` to
    `bad` when `ERROR_PAGE.search(text)` matches (the page is still read, so its quotes are
    checked too).
  - The shipped rows are the SOUND_ALIKE rows, with one section:
    `sections = [('range', quoted(row['notes'], 'Range:', ()), row['range_source'])]`.
  It checks what can be checked mechanically; a worker still applies range ruling 10 in full.

- [ ] **Step 5: The code check,** `build/batch-17-code-check.py`: copy `build/batch-16-code-check.py`
  and change it as follows; `test_table`, `held_back`, `in_catalog_order`, the "Already decided"
  branch and the order checks' shape stay.
  - The docstring:
```python
"""Batch 17's code check: uv run python -I build/batch-17-code-check.py SHEET.

Batch 16's code check (build/batch-16-code-check.py) with batch 17's changes (batch 17's plan,
"Before the tasks" Step 5): the harps family, no sound changes and no tags compared with the
sheet, and the builds, sound-alikes and aliases in the sheet's order. The test file's tables are
read as literals (ast.literal_eval), never evaluated. A one-off check may read the private
_HARP_BUILDS; a test may not.
"""
```
  - The imports read `HARP_SOUND_ALIKES` from `harp_sound_alikes` and `_HARP_BUILDS` from
    `harps`, and drop `math`, `re`, `Tag` and `Note`; `EXISTING_COUNT = 7`; `NAMES_BEFORE` reads
    `build/batch-17-names-before.txt`; `SOUND_CHANGES`, `built_drones`, `sheet_drones`,
    `sheet_changes`, `built_detune` and `sheet_detune` go.
  - The shipped-row assertions after `assert entry.sounds_like == parent, name` read
    `assert entry.tags == frozenset(), name` and `assert dict(entry.sound_changes) == {}, name`.
  - The table assertions after the loop read:
```python
assert test_table('HARP_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'HARP_HELD_BACK'
assert list(test_table('HARP_HELD_BACK')) == [
    row['name'] for row in rows if held_back(row)
], 'held-back order'
assert test_table('NEW_HARP_NAMES') == ship_names == [], 'NEW_HARP_NAMES'
assert list(test_table('HARP_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'HARP_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in _HARP_BUILDS[EXISTING_COUNT:]] == ship_names, 'build order'
assert [entry.name for entry in HARP_SOUND_ALIKES] == alike_names, 'sound-alike order'
```
    followed by batch 16's alias-order assertion and `print('matches', len(rows), 'rows')`.
  It cannot run until Task 1 has created `harps.py`, `harp_sound_alikes.py` and the test tables.
  The seven "Already decided" DROP rows were never catalog names or aliases, so they take the last
  branch.

---

### Task 1: Harps in their own module, unchanged; their sound-alikes module; the batch table's row, the held-back and sound-change guards, and each guard's helper tested on a real build both ways

**Files:**
- Create: `src/glitchygames/audio/instruments/harps.py`,
  `src/glitchygames/audio/instruments/harp_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/strings.py`, `registry.py`, and the docstring of
  `bowed_strings.py`
- Test: `tests/audio/test_instrument_catalog.py`; run `tests/test_process_state_guard.py`

**Interfaces:**
- Produces: in `harps.py`, `HARPS: Final[tuple[CatalogEntry, ...]] = _HARP_BUILDS +
  HARP_SOUND_ALIKES` and `_harp(*, ring_seconds: float, low_pass: float, slope: float = 8.0) ->
  Instrument` under its current name; in `strings.py`, `STRUCK_STRINGS`, `_hammered` and
  `_berimbau` unchanged. `HARP_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test
  file gains `EXISTING_HARP_NAMES: frozenset[str]` (the 7); `NEW_HARP_NAMES: list[str]`,
  `HARP_SOUND_ALIKE_PARENTS: dict[str, str]` and `HARP_HELD_BACK: dict[str, str]`, all empty here,
  for Tasks 3 and 5 to fill; the helper `entries_with_sound_changes(family: Family) -> list[str]`
  (`names_listed` already exists, batch 16's); the tests below; and the row `Family.HARPS:
  BatchFamily(EXISTING_HARP_NAMES, NEW_HARP_NAMES, HARP_SOUND_ALIKE_PARENTS)` in `BATCH_FAMILIES`.
  Also `build/catalog-builds-before.txt`.

The move comes first and the guards after, so no step expects a test to pass before the module it
imports exists (batch 16's Task 1 did: its RED was an ImportError, #86).

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

- [ ] **Step 2: Move the section.** Read every comment on the moved code first. Move `strings.py`'s
  "Harps" section (its header comment, `_harp` and `HARPS`) into `harps.py` unchanged, comments
  included, with the imports it uses (`partial`, `TYPE_CHECKING`, `Final`, `CatalogEntry`,
  `Family`, `plucked`, `plucked_series`, and `Instrument` under `TYPE_CHECKING`); `strings.py`
  keeps only what its section uses. Rename the moved tuple `_HARP_BUILDS` and define `HARPS` after
  it as the concatenation, importing `HARP_SOUND_ALIKES`. The docstrings:
  - `harps.py`'s first line is "Harps: concert, lever, wire-strung and triple harps, the lyre, kora
    and harp guitar." (87 columns with its quotes). It says that a harp's strings run in a plane
    perpendicular to the soundboard (Hornbostel-Sachs 322) and that the kora is a harp-lute (323),
    keeps `strings.py`'s ranges sentence verbatim ("Ranges are sounding pitch, after the common
    tunings of the instruments.") and its harp timbre clause ("a harp string is plucked and rings
    down (``plucked_series``)"), says that the sound-alikes are in ``harp_sound_alikes.py``, and
    names ``strings.py`` for the struck strings and ``bowed_strings.py`` and ``plucked_strings.py``
    as `strings.py`'s docstring does.
  - `strings.py`'s first line becomes "Struck strings: hammered dulcimer, cimbalom, santur,
    yangqin and the berimbau." (82 columns). It keeps its ranges sentence verbatim; its timbre
    sentence names the plucked series itself, since "the same series" no longer follows a harp
    ("a hammered dulcimer is a plucked string's series (``plucked_series``) plucked near the
    string's end, with two slightly detuned courses; the berimbau is ``struck``"); and it names
    ``harps.py`` beside the sibling modules it names.
  - `harp_sound_alikes.py` gets the empty table and `free_reed_sound_alikes.py`'s docstring with
    "Harps'" for "Free reeds'", its sentence about future sound changes removed (no harp builder
    takes a sourced change: a comment never describes one that does not exist), ending "The
    family's builds are in ``harps.py``.". Its first line is "Harps' sound-alikes: listed
    instruments that share another entry's build." (76 columns).
  - `bowed_strings.py` lines 4–5 say "Harps are in the sibling module ``harps.py`` and struck
    strings (dulcimers) in ``strings.py``", rewrapped to 100 columns.
  Point `registry.py` at both modules (`STRUCK_STRINGS` from `strings`, `HARPS` from `harps`).

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
uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q
```
  Expected: `changed: []`, nothing from `awk` (every module's first line fits in 100 columns), then
  PASS.

- [ ] **Step 4: Write the tables and the guards.** After batch 16's free reed tables
  (`FREE_REED_SOUND_ALIKE_PARENTS`), add `EXISTING_HARP_NAMES` (the 7 names, one per line, in
  catalog order, with the comment "# The 7 harps that predate batch 17: their shared builds predate
  the anti-goal rule"), then `NEW_HARP_NAMES: list[str] = []` and `HARP_SOUND_ALIKE_PARENTS:
  dict[str, str] = {}`, each commented as batch 16's free reed lists are. Put the harps row between
  the plucked strings and keyboards rows in `BATCH_FAMILIES`, which is table order. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list gains `+
  list(HARP_SOUND_ALIKE_PARENTS)` between the plucked strings' and the keyboards' lines, its
  comment reading "… bowed strings, plucked strings, harps, keyboards, …". At the end of the file
  add:
```python
# Every name plans/data/instrument-audit/batch-17.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, sub-audio
# fundamentals or a range above C8, and the alias rows that wait for one of them, in the sheet's
# order. None ships under that name or as an alias until the reason is met (decision 4; batch
# 17). The test matches exact names
HARP_HELD_BACK: dict[str, str] = {}
```
  Then the helper, with a Google docstring (`Returns:`), and the tests, each with a one-line
  docstring:
  - `entries_with_sound_changes(family)`: the names of the family's entries whose
    `sound_changes` are not empty, in catalog order.
  - `test_the_harp_guards_helpers_read_real_builds`: `names_listed(['concert harp', 'fender
    rhodes', 'not an instrument']) == {'concert harp', 'fender rhodes'}` (a catalog name and an
    alias from before the batch, and a non-name); `entries_with_sound_changes(Family.ORGANS) ==
    ['bourdon']` (the catalog's one entry with `sound_changes`, `{'footage': 16.0}`) and
    `entries_with_sound_changes(Family.HARPS) == []`.
  - `test_no_harp_name_held_back_for_a_feature_is_listed`: `names_listed(HARP_HELD_BACK) == set()`.
  - `test_no_harp_sound_alike_changes_its_parents_build`:
    `entries_with_sound_changes(Family.HARPS) == []` (the sound-alike ruling: this batch adds no
    sound change).

- [ ] **Step 5: Run them, then show each guard failing on a wrong table.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or harp_guards or changes_its_parents or sound_their_note" -v`
  Expected: PASS, with the ID `[harps]` in the parametrised batch tests. Then, without committing,
  set `HARP_HELD_BACK = {'concert harp': 'its own build (a test)'}` and rerun
  `-k held_back`: Expected FAIL naming `concert harp`. Restore the empty table. Then set
  `EXISTING_HARP_NAMES` without `'lyre'` and rerun `-k "new_entries and harps"`: Expected FAIL.
  Restore it, rerun the first command: PASS. `git diff --stat` shows only the intended edits.

- [ ] **Step 6: Lint and commit.** Run each lint command as its own line (batch 11's Task 1: zsh
  word-splitting once made a combined run a no-op).
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
SKIP=replay-metrics git commit -m "Instrument catalog: harps in their own module, unchanged; their sound-alikes module; the held-back and sound-change guards, each helper tested on a real build" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The frame harps sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch` for searching, and fetch
every URL you cite with `curl -fsS -L`, saving it. A WebFetch summary is a lead, never a source
(#85's `nickelodeon`); never cite a page you did not save. Put no personal data in any request, in
a header, a URL or a payload. Save each row's raw pages as `build/batch-17-pages/<name, spaces as
hyphens>--<n>.txt` (for Wikipedia, the `action=raw` wikitext; never a text extracted from it,
which drops `<ref>` and `<sup>`: #81's lesson; for a refused page, the Internet Archive's `id_`
copy). After each save, check the file is the page and not an error page (`grep -l "Wikimedia
Error" build/batch-17-pages/*` prints nothing). If a saved page holds a third party's phone number
or email address, tell the controller, who redacts it before the row cites the page. This holds
for every row whose notes quote a page, WAIT and DROP rows too, since the quote check reads them
all. A list or category page is a source for a name only. The sound, the mechanism and the range
come from the instrument's own page, a maker, a museum or a scholarly article under range ruling
7; a chart drawn as an image is not quotable (range ruling 5). The audit's rows and "Range checks"
are leads, not sources, so fetch them. Fetch the page of every existing entry you name as a parent,
and record what it says in the row's notes. Never use `git stash`. This task may start as soon as
the controller has written the shared files, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-17.tsv`
- Create (not committed): `build/batch-17-half-a.tsv`, and the raw pages in
  `build/batch-17-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `harps.md` ("Rejected or corrected proposed
  entries", "Aliases", "Range checks", "Gaps you could not close"); `new-environmental-instruments.md`
  (the `aeolian harp` row and the `wind harp` alias line); `batch-4.tsv` (the `aeolian harp`,
  `partch kithara`, `sasando` and `swarmandal` rows); `build/batch-17-names-before.txt`,
  `build/batch-17-half-a.txt`, `build/batch-17-half-b.txt`, `build/batch-17-form-check.py` and
  `build/batch-17-quote-check.py`.
- Produces: `batch-17.tsv` with batch 16's seventeen columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	drones	drone_source`.
  `status` is one of `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP` (no SHIP: the SHIP ruling).
  `alias_of` holds an ALIAS row's target or a SOUND_ALIKE row's parent. `family` is `harps` on
  every row; `tags` is empty, `drones` is `none` and `drone_source` empty on every row. A
  SOUND_ALIKE row has `lowest`, `highest` (sounding), `range_source`, an `hs` that fullmatches the
  harp classes, `builder` "unchanged", and `notes` holding `Range:` with its «raw passages» and
  derivation, and its parent ruling line ("Parent (rule 1):" or "Parent (rule 2):"). A candidate
  row's `audit_name` is its name in `build/batch-17-candidates.txt`; an alias row's is its audit
  line as the Spec line gives it. Also `build/batch-17-half-a.tsv`, the half as committed, which
  Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-17-half-a.txt`'s order, then
  one per alias name of this half, in the plan's order.

  The rules are batch 16's, changed for this family:

  1. **No SHIP** (the SHIP ruling): a row whose source states a trait in numbers `plucked` takes is
     reported to the controller with the passage, and waits for the ruling.
  2. **SOUND_ALIKE**: a verified instrument that the sound-alike ruling finds would sound like an
     existing entry. `alias_of` is its parent (the parent ruling). The `notes` begin
     "Sound-alike:", quote the source's description and mechanism (what sounds and how it is
     plucked), and say why that entry is the parent ("Parent (rule 1):" with the source's relating
     words, or "Parent (rule 2):" with the mechanism and the semitone counts). It has its own
     range, and the `builder` cell says "unchanged". It is never another sound-alike's
     sound-alike, never one of `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name or a
     SOUND_ALIKE row of this half. If the target waits, the row is WAIT with `waits_for` `its
     target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is dropped".
     An ambiguous name or a generic term is DROP under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `sub-audio fundamentals`, `a range
     above C8`, `sympathetic strings`, `a buzzing bridge`, `its own build (<the trait>)`, or
     another name of Global Constraints. **The range is checked first.** The feature must be the
     sound the source describes, not a technique a player applies. A cited trait no builder makes
     means the row waits. Any other name is allowed only with the source quoted, and Task 6 lists
     it in #87.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     boundary ruling's words), is a one-off, makes no sound, or is already decided: in the catalog
     under that name (name the entry), an alias already (name its target), or a row of an earlier
     sheet (notes beginning "Already decided:", naming the earliest sheet and its status).
  6. A row the audit marks ESTIMATE (memory), or sourced only by a list or category page, a
     musicbrainz mirror or the general Harp page, has no sourced sound or range yet. Fetch its own
     page; the audit's URL is a lead. If no page can be found, the row is DROP "no fetched source
     describes it", the same words on every such row.
  7. **The anti-goal:** compare each SOUND_ALIKE row's quoted sound with the sound-alike ruling's
     list before writing it: a string count, rows, a tuning action, a tuning, a material, a size,
     a body, a way of plucking, a maker, a region or a colour word is no trait; a bray, a rattle, a
     drummed belly or sympathetic strings is a trait the build cannot make (WAIT).
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.

  This half's own cases:

  - **Already decided.** `aeolian harp`, `kithara (partch)` (row `partch kithara`), `sasando` and
    `swarmandal` are DROP under rule 5, their notes beginning "Already decided: batch-4.tsv
    <status>" with that row's family and reason (the Spec line's list), quoting `batch-4.tsv`.
  - **The frame harps.** `cross strung harp`, `paraguayan harp`, `llanera harp`, `arpa jarocha`,
    `andean harp`, `gothic harp` and `baroque triple harp` are decided by the sound-alike, parent
    and range rulings: crossing rows, levers, pedals, nylon strings, nails and a diatonic tuning are
    no trait; the gothic harp's bray pins are a trait only when its fetched source states them for
    the instrument (then WAIT `its own build (bray pins)` once ranged). Their parent is `celtic
    harp`, `concert harp`, `wire strung harp` or `triple harp` by rule 1 where the source relates
    it ("a lever harp", "a Welsh triple harp"), else by rule 2. The Paraguayan harp's "32-46
    strings" and "4+ to nearly 8 octaves" and the llanera's "32 strings" are counts and widths. The
    Arpa llanera page redirects to `harp#Venezuelan harps`: cite the Harp page's section.
    `baroque triple harp` (the Italian arpa tripla) and the catalog's `triple harp` (Welsh) are
    decided on their pages: rule 8 only if a source makes them one instrument.
  - **The konghou.** `konghou` is decided on the Konghou page: one instrument (the modern frame
    harp with two rows, a sound-alike once ranged; pressing one row to bend the other is a
    technique) or a name for several (ancient and modern, DROP "an ambiguous name"); the audit's
    held-back subtypes are out of scope. `gonghu` follows it (rule 3), on a cited page giving it as
    the konghou's Korean name.
  - **The celestial harp.** `celestial harp`'s only lead is the Oddmusic gallery, a hobbyist's page:
    rule 6.
  - **The alias names.** `welsh harp` and `telyn` are ALIASes of `triple harp` only on a cited page
    giving the name to the Welsh triple harp (`telyn` is Welsh for any harp: the generic ruling
    first); `clarsach`, `clairseach` and `queen mary harp` of `wire strung harp` (the Queen Mary
    harp is one surviving instrument: an object's name is no alias of a type, so DROP "a one-off
    instrument, not a type a game would ask for" unless a source makes it a type); `pedal harp` of
    `concert harp` (the Pedal harp page: «also known as the '''concert harp'''»); `lever harp` and
    `folk harp` of `celtic harp`; `arpa paraguaya` and `arpa llanera` follow their candidates (rule
    3); `wind harp` follows `aeolian harp`, which is dropped: DROP "its target, aeolian harp, is
    dropped".

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-17-form-check.py plans/data/instrument-audit/batch-17.tsv`
  and `uv run python -I build/batch-17-quote-check.py plans/data/instrument-audit/batch-17.tsv`.
  Expected: `25 rows;` and the counts, then `bad: []`, exit 0; then the declared-charset and
  windows-1252 lists (any page named is recorded in the row's notes), `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-17.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-17-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-17-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
"
```
  Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-17.tsv build/batch-17-half-a.tsv
git add plans/data/instrument-audit/batch-17.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 17's verification sheet, the frame harps (orchestral, folk and historical harps)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The frame harps

**Files:**
- Modify: `harp_sound_alikes.py` (`HARP_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its
  source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-17-half-a.tsv` (half A as committed), Task 1's tables and helper, and
  `build/batch-17-code-check.py`.
- Produces: `HARP_SOUND_ALIKE_PARENTS` and `HARP_HELD_BACK` filled with this half's rows, which
  Task 5 extends. `NEW_HARP_NAMES` stays empty (no SHIP).

If half A has no SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills only
`HARP_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file only if it changed
(else no commit, and the report says so).

- [ ] **Step 1: Write the failing tests.** Fill `HARP_SOUND_ALIKE_PARENTS` with one `name:
  parent` per SOUND_ALIKE row and `HARP_HELD_BACK` with one `name: waits_for` per held row (every
  WAIT row whose reason is not `a sourced range`, and every `its target, <name>` row whose target
  is held), each in the sheet's order. Add the ALIAS rows to `test_the_batch_aliases_resolve`'s
  parameters, in the sheet's order, with a docstring sentence for batch 17.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or held_back or changes_its_parents or sound_their_note" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the held-back
  and sound-change tests pass.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in `HARP_SOUND_ALIKES`,
  in the sheet's order, under a section comment naming `plans/data/instrument-audit/batch-17.tsv`
  as `organ_sound_alikes.py`'s does ("--- Batch 17's frame harps, in the order of …"), each a
  `CatalogEntry(name, title, Family.HARPS, lowest, highest, sounds_like=parent)`. Above each, put a
  comment with its `sound_source` and `range_source` URLs, the quoted passages (its mechanism and
  its range) and the derivation. Each ALIAS row goes in `aliases.py` under a "Batch 17's harps:
  the frame harps" section, in the sheet's order, with its URL and quote. Comments name only
  committed files.

- [ ] **Step 4: Run the suite and check the code against the sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range or the build: check it against the source, and never trim the range to
  pass. Then run:
  `uv run python -I build/batch-17-code-check.py build/batch-17-half-a.tsv`
  Expected: `matches 25 rows`. Then rerun Task 1 Step 3's first command with its `order` assertion
  replaced by `names = set(instruments.names()); assert all(row[0] in names for row in before),
  'missing'`. Expected: `changed: []`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 17's frame harps, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The open harps, harp-lutes and lyres sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-17-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-17-pages/`
- Modify: `plans/data/instrument-audit/batch-17.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-17-form-check.py`,
  `build/batch-17-quote-check.py`, `build/batch-17-half-b.txt`; `harps.md` (its rows, "Rejected
  or corrected" lines for `krar`, `begena`, `nyatiti`, `seperewa`, `ngombi` and `gravikord`,
  "Aliases", "Range checks", "Gaps"); `round-1/merged-missing.tsv`; `batch-4.tsv` (the `begena`,
  `krar`, `nyatiti`, `donso ngoni` and `kamele ngoni` rows); `struck-strings.md` (its `chang` row).
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-17-half-b.txt`'s order, then one per alias name
of this half, in the plan's order, then the hand-off row `kamele ngoni`. A parent or alias target
is a catalog name or a SOUND_ALIKE row of this half, never a half-A row. These rules apply on top
of Task 2's:

- **Already decided.** `begena`, `krar` and `nyatiti` are DROP under rule 5, their notes beginning
  "Already decided: batch-4.tsv WAIT" with that row's reason (`a buzzing bridge` for `begena`, `a
  sourced range` for the others) and its lyre class (321.2).
- **The harp-lutes.** `donso ngoni` (batch 4's hand-off, quoted in its notes), `kamale ngoni`,
  `seperewa`, `simbi` and `gravikord` are decided under boundary ruling 2: `hs` 323 (the Kora,
  Seperewa and Simbing infoboxes' "323-5", or the source's words), parent `kora` by rule 1 where the
  source relates it ("share their basic design with the Manding kora") or rule 2. The gravikord's
  "left side G1 to E5, right side C2 to E5" (the audit's reading) is a range only as range ruling
  1 allows, from the fetched page's own words with a citation; its "standard scale … G major/E
  minor" and "24 strings" are no range, and its pickup is no trait (boundary ruling 8). A harp-lute
  whose source makes a rattle or buzz its sound waits for its own build.
- **The open harps.** `adungu`, `ennanga` (a redirect to African harp), `ngombi`, `kundi`,
  `ardin`, `saung gauk`, `chang`, `egyptian arched harp` and `angular harp` are harps (322.11 or
  322.12), parent by rule 1 or rule 2 among the four frame harps. The ennanga's rattles and the
  ardin's jingling strings and drummed belly are traits only when their fetched sources state them
  for the instrument (then WAIT `its own build (rattles)` or `its own build (a drummed resonator)`
  once ranged). The adungu's sizes and the saung's 13 to 16 strings fall under range ruling 6 (the
  Saung page's infobox `range=` is empty). `chang` and `angular harp` are checked under the
  generic and ambiguous terms ruling first.
- **The alias names.** `saung` follows `saung gauk`, `ombi` follows `ngombi`, `domu` follows
  `kundi` (rule 3), each on a cited page giving it as that instrument's name; `harp lute` is DROP
  "a generic term for the harp-lutes (H-S 323)" unless a source makes it one instrument's name.
- **The hand-off.** `kamele ngoni` is `kamale ngoni` under batch 4's spelling: rule 8, ALIAS of
  `kamale ngoni` if that row is a SOUND_ALIKE and a cited page gives this spelling, WAIT `its
  target, kamale ngoni` if that row waits, else DROP "the audit's name for kamale ngoni"; its notes
  quote `batch-4.tsv`'s DROP.

- [ ] **Step 1: Write half B's rows** to `build/batch-17-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-17-form-check.py build/batch-17-half-b.tsv` and
  `uv run python -I build/batch-17-quote-check.py build/batch-17-half-b.tsv`.
  Expected: `22 rows;` and the counts, then `bad: []`, exit 0; then the charset lists, `bad: []`,
  exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-17-half-b.tsv >> plans/data/instrument-audit/batch-17.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `47 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-17.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-17-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-17-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted((half_a | half_b) - set(audit_names)))
print('twice:', sorted({name for name in half_a | half_b if audit_names.count(name) > 1}))
print('extra:', sorted(set(audit_names) - half_a - half_b))
print('names twice:', sorted({row['name'] for row in rows if [r['name'] for r in rows].count(row['name']) > 1}))
"
```
  Expected: `missing: []`, `twice: []` and `names twice: []`. `extra:` lists only the alias rows'
  audit lines and the hand-off: 13 distinct entries (12 alias lines: 8 for half A, the 7 `harps.md`
  lines naming `triple harp`, `wire strung harp`, `concert harp`, `celtic harp`, `paraguayan harp`,
  `llanera harp` and `gonggu`, and the `wind harp` line; 4 for half B; and `kamele ngoni`).

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-17.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 17's verification sheet, the open harps, harp-lutes and lyres" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The open harps and harp-lutes

**Files:**
- Modify: `harp_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-17.tsv`'s half-B rows, Task 3's tables, and `build/batch-17-code-check.py`.
- Produces: the finished family: `HARP_SOUND_ALIKE_PARENTS` and `HARP_HELD_BACK` with both halves'
  rows.

If half B has no SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `HARP_SOUND_ALIKE_PARENTS`,
  `HARP_HELD_BACK` and the alias parameters, after half A's, as in Task 3 Step 1.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: sound-alikes after half
  A's sound-alikes, aliases after half A's aliases, under second section comments naming the sheet
  ("Batch 17's harps: the open harps, harp-lutes and lyres").

- [ ] **Step 4: Run the suite and check the code against the whole sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`, then
  `uv run python -I build/batch-17-code-check.py plans/data/instrument-audit/batch-17.tsv`, then
  Task 3 Step 4's earlier-builds command.
  Expected: PASS, then `matches 47 rows`, then `changed: []`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 17's open harps and harp-lutes, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a harps
  paragraph with its count, naming `harps.py` and `harp_sound_alikes.py`, with examples, in the
  free reeds paragraph's form, saying that a harp's strings run perpendicular to its soundboard
  (322) and a harp-lute's at right angles to it across a notched bridge (323), that a string
  count, rows, a tuning action, a tuning, a material, a size or a body is no trait, that a
  sound-alike gives its own sourced range, and that `strings.py` now holds only the struck strings.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `harps` row's
  count and examples, the sound-alike modules sentence and its total).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 17
  done, pointing at this plan and `batch-17.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 17 DONE", and the Description's running count gains batch 17;
  - batch 17 done, with the sheet's counts by status and the family's growth, the module move
    (`harps.py`; `strings.py` keeping the struck strings), the boundary rulings, `HARP_HELD_BACK`'s
    names, and the branch's base SHA (`1ecc25d9`, batch 16's tip);
  - the audit's unclosed gaps and the out-of-scope names (the Spec line's and File Structure's
    lists, `yazh`, `yaal` and `gonggu` among them), as a later pass;
  - the hand-offs: `donso ngoni` and `kamele ngoni` decided here (batch 4's DROPs to harps); the
    seven already-decided rows left as `batch-4.tsv` decided them; `chang` decided here once, so
    the struck strings batch treats the name as already decided (and how); each row dropped to
    plucked strings, keyboards or another family, for a later pass of that family; the alias
    names decided here (so no later batch decides `pedal harp`, `lever harp`, `folk harp`,
    `clarsach`, `telyn`, `wind harp` or `harp lute` again);
  - a "Plan (batch 17)" line, the Status line, and the next batch named: struck strings (batch 18).

  Add #87 (the highest item is #86), "Sound Engine: The Owner's Checks on Instrument Catalog Batch
  17 — TODO". Use #86's form, place it directly after #86, and give it the Priority "(before the
  struck strings batch builds on the same catalog)". Its **Listen** section (`build/instruments/
  harps/`) covers the sound-alikes beside their parents, then the aliases. Its **Calls to confirm**
  are:
  - every WAIT, by reason, with names, and each row's "Engine limit, once ranged" note;
  - the module move (`harps.py` out of `strings.py`) and its `changed: []` record, and whether
    `strings.py` should be renamed now that it holds only the struck strings;
  - the boundary rulings, each row they moved, and the Hornbostel–Sachs codes this plan checked
    (322 and its subclasses, 323, 321.2, 321.322, 311.112, 314.22, the suffixes; the Triple harp
    infobox's "3.2.2" no class);
  - harp-lutes in harps (batch 4's hand-off and the catalog's `kora`), and `lyre` and `harp
    guitar` kept in harps but never a rule-2 parent: #74's question, still open;
  - a harp as a sound-alike (counts, rows, tuning actions, tunings, materials, sizes, bodies and
    colour words no trait; no SHIP and no `sound_changes` in this batch; bray pins, rattles and a
    drummed resonator wait), and any row the SHIP ruling sent to the controller;
  - the parent ruling (the source's relation first, the only way to `lyre`, `harp guitar` or
    another family; else the nearest lowest note among the four frame harps, or `kora` for a
    harp-lute), and each sound-alike's parent;
  - the range ruling (one source states both ends; one source's row compasses joined; levers and
    pedals as stated; a count, a width, a tuning, a hedge, an image chart or a general rule no
    range; a model's page ranges that model only; a bare name of several sizes with none standard
    waits, "became widespread" no standard), and every derived range;
  - generic, ambiguous, one-off and unsourced rows, with the words "no fetched source describes it"
    on every row whose page was not found;
  - `HARP_HELD_BACK` and the sound-change guard, the helper test that exercises them on real builds
    both ways, and the wrong-table runs that showed each failing;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): the 7 earlier entries' missing
  source comments; any existing range or build a sheet's source contradicts (the leads in Global
  Constraints: the Pedal harp page's Cb1–Gb7 against `concert harp` Cb1–G#7; the kora's
  image-only range and Grinnell's D2–F5 against `kora` F2–C6; the Triple harp page's "about five
  octaves" against `triple harp` C2–C7); `lyre` (321.2) and `harp guitar` (321.322) in harps
  (#74); the Triple harp infobox's "3.2.2" (Wikipedia's, not the catalog's); the 17 third-party
  `speech_recognition` DeprecationWarnings as #86 records them. Then **Follow-ups**: the audit's
  gaps; ranging the range WAITs from maker, museum and scholarly sources; checking the 7 earlier
  entries against sources; the engine changes that unblock the waits, most rows first. Then
  **Incidents and process**, as #86 has them (the fetches that returned error pages, any redaction,
  any load flake and its rerun).
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries()))"`
  and `uv run python -I build/batch-17-form-check.py plans/data/instrument-audit/batch-17.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full suite.**
  Run: `uv run pytest --dummy-only -W default tests/audio tests/test_process_state_guard.py`, then
  `uv run pytest`, with nothing else running.
  Expected: PASS, 100% coverage; the only warnings are the 17 known `speech_recognition`
  DeprecationWarnings (#86; any other is a new finding, understood before going on). A failure in
  one of the two known load-flaky tests (Global Constraints) is rerun alone and then the whole
  suite once, and recorded in #87.

- [ ] **Step 4: Run the docs lint, on its own, after the suite has finished.**
  Run: `nox -s lint-docs`. Expected: the strict build passes.

- [ ] **Step 5: Run the remaining checks.**
```bash
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-17-code-check.py plans/data/instrument-audit/batch-17.tsv
uv run python -I build/batch-17-quote-check.py plans/data/instrument-audit/batch-17.tsv
```
  Expected: everything passes; `matches 47 rows`; and `bad: []`. The `build/instruments/harps`
  folder is the one to listen to; the owner judges the sound.

- [ ] **Step 6: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 17 of the instrument catalog (harps), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch in
turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78). The
pre-push hooks take about 40 minutes, and nothing in the working tree may change while they run.

**Order:** the controller's shared files (and the plan's commit), then Tasks 1, 2 and 4 in
parallel. Task 3 follows Tasks 1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows
Tasks 3 and 4, and Task 6 comes last.

**Corrections to batch 16's plan carried here:**
- Batch 16's Task 1 ran its guards "before the move" and expected them to pass, but its helper
  test imported the moved module, so the RED was an ImportError (#86). Here the move and its
  `changed: []` record come first, the guards after, and each guard is shown failing on a wrong
  table before the commit.
- Batch 16's quote check read UTF-8, else windows-1252, and read a windows-1251 page as mojibake
  until the controller fixed it (#86); this plan starts from the fixed script (the declared
  charset before windows-1252).
- Batch 16's fetch rule did not catch a saved HTTP error page: curl without `-f` writes
  Wikimedia's "Wikimedia Error" page with exit 0 (4 of 25 fetches while writing this plan). Here
  every fetch uses `curl -fsS -L`, the research steps grep for error pages, and the quote check
  refuses one.
- Batch 16's range ruling 6 did not say that "became widespread" is not "standard" (the `khromka`
  reversal, `bdf1dc09`), and no ruling named a chart drawn as an image (the concert accordion's
  charts, #86); both are written into this plan's ruling 5 and 6.
- Batch 16's research steps had no rule for personal data on a saved page; the controller redacted
  one by hand (#86, `engkerurai`). Here the controller redacts before any row cites the page.
- Batch 16's Task 3 told a code task with nothing to ship to "commit the test file alone", though
  nothing had changed (#86: "no commit"). Here a task that changes nothing makes no commit and says
  so.
- Batch 16's Task 6 listed `nox -s lint-docs` in the same block as the suite, and named no known
  flake; #84's native-driver failure came from running the two side by side, and #86 met a second
  load flake. Here the docs lint runs on its own after the suite, and both flakes are named with
  their rerun rule.
