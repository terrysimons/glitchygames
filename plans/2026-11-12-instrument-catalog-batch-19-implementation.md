# Instrument catalog batch 19 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the saxophones family from the audits' candidates, the last family the expansion's
batch order reaches. The family holds the single reeds on a conical bore (Hornbostel–Sachs 422.212,
"With conical bore", under 422.21 "(Single) clarinets"; the saxophones' infobox class is
422.212-71, "Single-reed aerophone with keys"): every size and key of the saxophone, and the other
conical single reeds batch 14 sent here (the modern tárogató, the octavin, the Heckel instruments,
the sarune etek). Each instrument gets a cited source for its name, its sound, its reed and bore
and its range, and either sounds unlike every other entry or is a listed sound-alike of the one it
sounds like. The rest become aliases, wait for an engine feature or a source, or are dropped with a
reason. Because every other family has had its batch, the docs task also closes the expansion: a
cross-sheet final audit of all 19 sheets against the code, a closing summary in #70 and the
design's status line.

**Architecture:** As in batches 3 to 18, a verification sheet (`batch-19.tsv`) decides every
candidate before any code is written. The family's 8 entries are all that is left in `winds.py`
(106 lines) since batch 16 moved the free reeds out, and every other family has a module named for
it and a sibling sound-alikes module. So `winds.py` is renamed, unchanged, to `saxophones.py`
(`git mv`, so its history follows), and no `winds.py` is kept: the moved table becomes
`_SAXOPHONE_BUILDS`, and `SAXOPHONES` becomes `_SAXOPHONE_BUILDS + SAXOPHONE_SOUND_ALIKES`, with
the sound-alikes in a new `saxophone_sound_alikes.py` (named as `clarinet_sound_alikes.py` and
`harp_sound_alikes.py` are). The catalog's one saxophone builder, `_saxophone(*, low_pass)`, takes
only a sound-design value (no source behind any of the 8 `low_pass` values), so a new saxophone
with no other cited trait is a sound-alike, `builder` "unchanged". This batch adds no builder, no
keyword and no `sound_changes`. A trait the build cannot make (two pipes sounding together, a slide
that is the instrument's way of changing pitch, a bore or bell its source says changes the sound)
means the row waits, and a range below A0 waits for `sub-audio fundamentals`. A new guard,
`SAXOPHONE_HELD_BACK`, holds every name the sheet holds back for any reason but a sourced range.
The sheet and the code each come in two halves, as explicit lists: the saxophones (their sizes,
keys and models), then the other conical single reeds. The controller writes the names file, the
candidate lists and the four check scripts before anything is dispatched, so the two sheet halves
are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `falling_series`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4 and 8
above all; its audit table counts the saxophones audit's 12 rows; its batch order, "One batch per
family", reaches the saxophones last, as #70 names it: "Next: saxophones (batch 19), the family the
audits cover and no batch has grown"). The spec has no saxophones section beyond that table row and
says nothing explicit about the end of the expansion: its status line lists each batch done and
ends "The later batches are not yet planned.", its "Depends on" line carries the catalog's count
after each batch, it is "Tracked as: `plans/future-features.md` #70", and its Goals are "Add the
instruments the audits found, in batches by family", "Settle the family list", "Record, per
instrument, where its name, range and description came from" and "Say plainly which instruments
the engine cannot make yet, and what engine feature each needs". Task 6 folds those four into the
close: the status line and #70 say every family has had its batch, a final audit checks every
sheet's standing decision against the code (goals 1 and 3), and #70's closing summary lists every
wait by reason and the engine features the batches named beyond the spec's table (goal 4), for the
owner to rule on. Nothing in the spec asks the plan to edit its "What the engine cannot make yet"
table or to mark the design done; both are the owner's calls, asked in #89.

Batch 18's plan (`plans/2026-11-12-instrument-catalog-batch-18-implementation.md`) and its owner's
checks (`plans/future-features.md` #88) are this plan's template and its ledger: its controller
step, its quote check, its held-back guard, its module move, its two parallel halves and its code
check carry over, with the corrections listed at the end of this plan. Batch 14's plan
(`plans/2026-11-12-instrument-catalog-batch-14-implementation.md`) holds the bore boundary (a
cylindrical single reed is a clarinet, a conical one a saxophone), the makers' ruling (`xaphoon`,
`venova`) and the sheet that sent `tarogato`, `octavin`, `heckel clarina`, `heckelphone clarinet`
and `sarune etek` here; batch 4's holds the pitched sound-alike and strict range rules and the
before-and-after build record; batch 11's holds the balaban rule (a cited trait the build cannot
make means the row waits). This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-19-implementation.md`. The branch is
`feat/instrument-catalog-batch-19`, made from batch 18's tip, `6503a1e1` (batch 18's final review
fixes); Task 6 records that SHA in #70. The candidates come from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `saxophone` (12, every one from the round-2 audit
  `saxophones.md`: `soprillo saxophone`, `c soprano saxophone`, `f mezzo soprano saxophone`, `g
  mezzo soprano saxophone`, `conn o sax`, `saxello`, `slide saxophone`, `contralto saxophone`,
  `tubax`, `bb tubax`, `subcontrabass saxophone`, `grafton alto saxophone`);
- the `round-1/merged-missing.tsv` rows whose `family` contains `saxophone` (6: `xaphoon`,
  `aulochrome`, `tubax`, `subcontrabass saxophone`, `soprillo`, `maui xaphoon`);
- five hand-offs, as batch 18 took batch 4's: `tarogato`, `octavin`, `heckel clarina`,
  `heckelphone clarinet` and `sarune etek` (`batch-14.tsv` DROPs, each «Belongs to saxophones (H-S
  422.212)» or, for `sarune etek`, «DROP: belongs to saxophones (H-S 422.212)»; #70: «dropped to the
  saxophones, so the saxophones batch decides them»).

Together: 16 unique audit names (`tubax` and `subcontrabass saxophone` are in both lists) and 5
hand-offs, none of them a catalog name or alias (checked for this plan at `6503a1e1`: the catalog
holds 704 entries and 138 aliases, 842 names, and no saxophone alias at all). So there are **21
candidate names** (counted for this plan; the controller recounts). `soprillo` and `soprillo
saxophone` are one instrument under two audit names (the audit's «soprillo: renamed soprillo
saxophone»), decided by rule 8. The saxophones audit's "Aliases" lines whose left-hand names are no
catalog name and no candidate propose **7 alias names**:
- "stritch -> alto saxophone (Kirk's name for a straight Buescher alto; no distinct sound)";
- "manzello -> saxello (Kirk's modified saxello with large upturned bell)";
- "tubax in Eb -> tubax" (`tubax in eb`);
- "curved soprano saxophone -> soprano saxophone (shape only; vendors list both)";
- "sopranissimo saxophone -> soprillo saxophone (Wikipedia title Soprillo redirects to
  Sopranissimo saxophone in mirrors)";
- "pocket sax -> xaphoon (the ABS plastic version, sold since 2000)";
- "xaphoon de catalunya -> xaphoon".
The line "maui xaphoon -> xaphoon" names a candidate (round 1's `maui xaphoon`), so it is that
candidate's row, not an alias row. No other audit has an alias line naming a saxophone (checked
with grep over every `*.md` in the folder and `round-1/`). The round-1 alias tables are not used, as
no earlier batch used them. So the sheet will hold **28 rows** (21 candidates and 7 alias names).
An alias row's `audit_name` is its audit line as written above.

The hand-offs from earlier sheets (checked for this plan: `batch-1.tsv` to `batch-18.tsv`, read
with the csv module, for every candidate, every alias name, `saxophone`, `xaphoon`, `aulochrome`,
`tarogato`, `octavin`, `heckel`, `sarune`, `saxonette`, `venova`, `soprillo`, `tubax`, `stritch`,
`manzello`, `saxello`, `rothphone`, `saxorusofono` and "wind controller" in any cell, and
`plans/future-features.md` #70–#88 for "saxophones"):
- Decided here (batch 14's DROPs naming this family; a DROP naming a family is a hand-off that
  family's batch decides, as batch 18 decided batch 4's `fotdella`, `nondo` and `quijongo`):
  `tarogato`, `octavin`, `heckel clarina`, `heckelphone clarinet`, `sarune etek` (all half B). Each
  row quotes its `batch-14.tsv` DROP in the notes, then is decided under this plan's rulings.
- Already decided, and rows: each is DROP, its notes beginning "Already decided:" and naming the
  sheet whose status stands and that status (none is a catalog name or alias, so the code check's
  last branch applies). All are half B: `xaphoon` (`batch-14.tsv` WAIT `a sourced range`, family
  clarinets, the makers' ruling); `maui xaphoon`, and the alias rows `pocket sax` and `xaphoon de
  catalunya` (each `batch-14.tsv` WAIT `its target, xaphoon`). #70 binds them: «the xaphoon's alias
  names are decided here (`xaphoon` waits for a sourced range, and `maui xaphoon`, `pocket sax` and
  `xaphoon de catalunya` wait for it), so the saxophones batch must not decide them again». The
  audit's own call that the xaphoon has a «cylindrical bore» agrees with batch 14's family.
- Decided elsewhere, not candidates, no row: `saxonette` and `venova` (`batch-14.tsv` WAITs,
  clarinets); the saxhorns, `saxotromba` and `jazzophone` (`batch-10.tsv`, brass: the "sax" in
  their names is Adolphe Sax's, or a shape); the sarrusophones and `rothphone` (`batch-11.tsv`,
  double reeds); `sneng` (`batch-10.tsv` WAIT, brass; #86 notes it is a free reed); `couesnophone`,
  `goofus` and `queenophone` (`batch-16.tsv`, free reeds in a saxophone shape); `ewi` (`batch-6.tsv`
  DROP, «no sound of its own», «a type of wind controller») and `lyricon` (`batch-6.tsv` WAIT),
  electronic. #84 left «the saxophones audit's xaphoon keys (C, B-flat, D, G)» to a later clarinets
  pass: not this batch's. Task 6 lists these for the owner, never re-deciding them.
- #86 asks "Should `winds.py` be renamed now that it holds only the saxophones?": Task 1 answers it.
- Not decided by any batch: `saxorusofono` (the audit's "Gaps": «saxophone keywork with a
  sarrusophone body and double reed; belongs in double reeds»). It is no candidate here (a double
  reed); Task 6 lists it in #70 for a later double reeds pass.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, parentheses, hyphens, flats and sharps go only in the title
  (`tarogato` titled "Tárogató", `conn o sax` titled "Conn-O-Sax", `tubax in eb` titled "Tubax in
  E♭"). A candidate keeps its audit name (the naming ruling of batch 12).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families),
  "with the existing player-facing splits kept where they already exist". The saxophones hold the
  single reeds on a conical bore; the boundary rulings below decide each row.
- Hornbostel–Sachs, every code this plan relies on checked against Wikipedia's raw wikitext on
  2026-11-13 (`List_of_aerophones_by_Hornbostel–Sachs_number`, `Hornbostel–Sachs`,
  `Template:Infobox_saxophone`):
  - 422.1 "Double reed instruments"; 422.2 "Single reed instruments - The pipe has a single 'reed'
    consisting of a percussion lamella."; 422.21 "(Single) clarinets."; 422.211 "With cylindrical
    bore." (422.211.1 "Without fingerholes.", 422.211.2 "With fingerholes."); 422.212 "With conical
    bore." (listing the Octavin, the Saxophone and its sizes from the Soprillo to the Tubax, the
    Sneng and the «Tarogato (modern)»; no subclass is listed); 422.22 "Sets of clarinets."; 422.3
    "Reedpipes with free reeds"; 412.13 free reeds.
  - Suffixes: the main page's «An '''8''' indicates that the instrument has a keyboard attached,
    while a '''9''' indicates the instrument is mechanically driven», and «a number of suffixes
    unique to each of the top-level groups»; the aerophone list gives none. `-71` is taken only from
    `Template:Infobox saxophone`, whose raw text sets «hornbostel_sachs = 422.212-71» and
    «hornbostel_sachs_desc = [[Single-reed instrument|Single-reed]] [[aerophone]] with
    [[key (instrument)|keys]]».
  - **Trap: the saxophone pages' class is in the template, not on the page.** Every page built on
    `{{Infobox Saxophone}}` (Saxophone, Tubax, Soprillo, Aulochrome, Mezzo-soprano saxophone, C
    soprano saxophone, Subcontrabass saxophone; `Template:Infobox_Saxophone` redirects to
    `Template:Infobox_saxophone`) shows 422.212-71 rendered, but its raw wikitext holds no class, so
    the quote check cannot find it there. A row that writes `422.212-71` saves the template's raw
    text as one of its own pages and quotes it there; a row whose page's own words name what sounds
    and how («a single-reed woodwind … with a conical body», «a conical bore and a single reed»)
    writes `422.212` from those words. The template's class is the template's default for every
    page using it (the Aulochrome page uses it for two pipes), so it is no evidence about a row's
    bore by itself: the row's bore comes from its own page's words. The Octavin infobox writes
    «hornbostel_sachs = 422.212» on the page itself.
  - **Trap: batch 14's `sarune etek` row writes `422.212.2`, a subclass the fetched list does not
    hold** (422.212 has no subclasses on it). Its half-B row writes `422.212` unless a fetched list
    gives the subclass; Task 6 reports the batch-14 cell in #89 (not fixed here).
  A worker who finds a code that a fetched list does not hold reports it to the controller before
  any row relies on it. No other code is assumed. A class is written from words naming what sounds
  and how, never from a relation ("based on", "like the", "a type of", "derived from"): that is a
  parent (#87's `gravikord`).
- "Every name, range and description checked against a source cited in the code … A range that no
  source gives is the instrument's documented playable span from a maker or museum, or the entry
  waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict"). This plan's
  range ruling is below. A row with no sourced range is WAIT, `waits_for` `a sourced range`, and
  **the range is checked first**, before any engine limit or other trait (batch 13's reversals): a
  row with neither a range nor a buildable trait waits for the range, its notes keeping "Engine
  limit, once ranged: …".
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry, sharing
  the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the same
  instrument) stays an alias." A sound-alike is pitched exactly when its parent is (every saxophone
  is pitched), and a pitched sound-alike gives its own sourced range (batch 4). This batch's
  sound-alikes carry no `sound_changes` (the sound-alike ruling).
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as an
  approximation. The spec's table binds this family through "sub-audio fundamentals" (the Bb tubax
  and the subcontrabass saxophone reach A♭0, below A0). Earlier batches added the other names a
  WAIT may give: a pitch LFO (vibrato), a pitch LFO (portamento between notes) (batch 9's `slide
  whistle`), an amplitude LFO, a pitch and amplitude LFO (batch 2), filter resonance, a filter
  envelope, moving formants (batch 6); a pitch moving through a phrase (batch 4); a buzzing
  membrane (batch 5); a sourced drone tuning and its own build (batches 7, 12); a range above C8
  (batch 10); a sourced detune and a sourced footage (batch 13); a sourced reed and bore (batch 14);
  a sourced partial series (batch 15); `its own build (rattles)` and `its own build (a drummed
  resonator)` (batch 17). This plan adds no new wait name; `its own build (<the trait>)` names any
  trait no builder makes. What the engine has: `blown` (one harmonic series, an attack and release,
  breath noise with its own low pass, a fixed low pass, drive and a bite series); no LFO, no glide
  between notes in a phrase, no second pipe, no series that changes with the note.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not builds.
- Reuse `_saxophone` under its current name; add no builder or keyword (the sound-alike ruling). A
  row whose source states a trait `blown` could make with a sourced number is reported to the
  controller before its half's code task (the SHIP ruling).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from it)
  you need to attribute it with a comment pointing to the source."). Every quote in the sheet, in
  every row of every status, is verbatim from a page the worker fetched and saved, or from a
  committed file the notes name (an earlier sheet, an audit file, #70 or the spec), and the quote
  check finds each one. No request carries the owner's email or any personal data, in a header, a
  URL or a payload (#78).
- **Quotes in code comments are ASCII where ruff would refuse them** (#88: batch 18's aliases first
  quoted a page's en dash, ruff refused it as an ambiguous character, ten lines got `# ruff:
  ignore[ambiguous-unicode-character-comment]` and ran past 100 columns, and the final review
  removed them). A comment writes a page's en dash or em dash as an ASCII hyphen, and any other
  character ruff flags (RUF001–RUF003) as its ASCII form, with one note in the section's header
  comment saying so, as batch 18's final fix did. The flat and sharp signs become `b` and `#` only
  if ruff flags them. The sheet keeps the page's text verbatim. **Never add a suppression**: no `#
  noqa`, `# ruff: ignore[...]`, `# type: ignore`, `# pyright: ignore` or `# pragma` in this batch's
  diff (Tasks 1, 3 and 5 check the diff for one).
- Sources: an unsaved WebFetch read is a lead, never a source (#85's `nickelodeon`): every cited
  page is saved raw with `curl -fsS -L` (for Wikipedia, the `action=raw` wikitext), straight to
  `build/batch-19-pages/<name, spaces as hyphens>--<n>.txt`, never to a scratch copy named by the
  page's title (#87's case-insensitive overwrite). `-f` matters: without it curl saves an error
  page with exit 0. **A 404 or any other error page is never saved** (#87): a page that does not
  exist goes in the row's notes ("returned 404"), and the quote check refuses a saved error page. A
  429 is waited out and retried, never saved; a page that keeps refusing curl (403, 429) is fetched
  from the Internet Archive's copy (`https://web.archive.org/web/<date>id_/<url>`), saved, and
  cited by its archive URL. **A Wikipedia redirect is never saved as the row's page**: Conn-O-Sax,
  Saxello, Slide saxophone, Stritch (saxophone) and Manzello redirect to anchors of the Saxophone
  page («#REDIRECT [[Saxophone#Conn-O-Sax]]»), and Sopranissimo saxophone redirects to Soprillo
  (all checked for this plan); the worker notes the redirect in the row and saves the page it
  points to (#88's practice), whose section is the source. The quote check refuses a saved page
  that is only a redirect. **Personal data** (#88): a worker who finds a private person's email
  address or phone number on a saved page deletes that page before any row cites it and notes the
  lead in the row ("held a private person's contact data, deleted"), or hands it to the controller,
  who redacts it; no row quotes it. An institution's or company's public contacts (a museum's
  switchboard, a maker's or magazine's press address) are not personal data and stay (#87's Penn
  Museum page, #88's Make: magazine page). The quote check lists every saved page holding an email
  address, for the controller to judge. Uncited lines (range ruling 10), blogs, forums, retailers'
  listings (sax.co.uk, pmwoodwind.com), hobbyists' pages and musicbrainz mirrors are not sources; a
  scholarly article (a journal paper, a museum's or university's publication) and a maker's page
  are.
- Code comments name committed files (`plans/data/instrument-audit/batch-19.tsv`), never the
  gitignored `build/` files (batch 9's fix), and never describe a builder, keyword or table use that
  does not exist (batch 16's final review).
- Data is never evaluated as code: a check script reads a literal with `ast.literal_eval`, never
  `eval` or `exec`.
- The 8 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 8. An existing entry changes only for a cited bug, and not in this batch:
  the 8 carry no per-entry source comment (the module docstring names Adler and the Vienna
  Symphonic Library in general), so a range or build that a fetched source contradicts is reported
  in #89 for the owner (batches 10 to 18's rule). Leads seen while writing this plan, for the
  workers who fetch those pages to check under range ruling 10: the catalog's `baritone saxophone`
  starts at C2, which is the low-A model's sounding low note (the audit's «baritone Eb: Db2-Ab4
  (low-A models reach A1)», written), while the Bb-keyed instrument sounds D♭2; the catalog's tops
  (`soprano saxophone` Eb6, `alto saxophone` Ab5, and so on) are the written F6 top, while the audit
  quotes makers' F♯6 tops. Task 1's before-and-after record of every entry checks that the move
  changes nothing, and Tasks 3 and 5 repeat it.
- **The family is in the catalog test's `HARMONIC_FAMILIES`** (checked: `Family.SAXOPHONES` is
  listed; batch 18's struck strings were not), so `test_harmonic_instruments_sound_their_note` runs
  on every new saxophone entry, as `test_every_instrument_renders_across_its_range` does. A failure
  at a range end is a finding about the range or the build, never trimmed to pass.
- Code style: "Make sure to use the code style already present in the project": Google docstrings,
  ruff (100 columns, a module docstring's first line included), basedpyright and ty clean, 100%
  coverage. "I don't like short abbreviated variables." "explicit is better than implicit."
  "Whenever you see warnings thrown by a test, you should understand why it's happening and be
  concerned": a warning is a finding, understood before going on. #86 to #88 record 17
  DeprecationWarnings under `-W default` from the third-party `speech_recognition` (it imports
  `aifc`), filtered on purpose in `pyproject.toml`; a report says "the 17 known speech_recognition
  warnings, no other" when that is what it saw, never "no warnings".
- Process: run `nox -s lint-docs` on its own, never while a test run is going (#84). Two load flakes
  are known: #84's
  `tests/engine/test_game_engine.py::TestReplayRestartExitStatus::test_a_status_no_exit_code_names_is_passed_through`
  (native run) and #86's `test_command_crash_boundary.py` signal test, case [2]. If one fails,
  rerun it alone, then the whole suite once; record it in #89 either way. Any other failure is a
  finding.
- Commits as batches 4 to 18: `SKIP=replay-metrics git commit`, with the subject `Plans: …`,
  `Instrument catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76), so copy each commit message from this plan, never from memory.
  Write no `.md` file beyond those Task 6 names. Never use `git stash`: the stack is shared with
  other worktrees and sessions (#80). Set work aside with a temporary commit instead. A task that
  changes nothing makes no commit, and its report says so.

## Review Focus

1. **A written range, a general rule or a chart read as a sounding range.** Saxophones transpose:
   the Saxophone page's «Most saxophones share the same written range», the audit's "Convention"
   (written B♭3–F6, «Bb sizes sound a major 2nd below written, Eb sizes a major 6th below»), the
   infoboxes' ranges drawn as images («[[File:Saxophone range.svg…]]», «[[File:Soprillo
   range.svg…]]») or as LilyPond `<score>` blocks (Tubax, Mezzo-soprano and C soprano: «bes1
   \glissando f'''1»), altissimo notes and optional low A, high F♯ and high G keys. Range rulings 2,
   3 and 5 make none of them a row's range; the form check needs `Range:` with a quoted passage the
   quote check finds on the saved page; the code check compares every shipped range with the sheet.
2. **One model's, one period's or one size's range given to the bare name.** The C soprano page
   gives «the standard vintage horn from 1920–1928» one range and «The 2010 models» another; the
   tubax is made in E♭ and B♭ (and a C size, unranged); Eppelsheim's pages are model pages; the
   Conn F mezzo and Jessen's G mezzo are different instruments. Range rulings 4, 4b and 6 decide
   them, and the makers' ruling decides a one-maker instrument.
3. **A sub-audio size shipped, or a guard that passes only because its table is empty.** The B♭
   tubax and the subcontrabass reach A♭0 (the Tubax page: «the B♭ tubax three octaves and a second
   lower, to A♭0»). Range ruling 8 makes each WAIT `sub-audio fundamentals`, held back by
   `SAXOPHONE_HELD_BACK`; the form check refuses a SOUND_ALIKE outside A0–C8; Task 1 shows each
   guard failing on a wrong table.
4. **A parent from a part, a pitch or another family, or a trait shipped as a plain sound-alike.**
   The Tárogató page's «uses a single reed, like a [[clarinet]] or [[saxophone]]» names `clarinet`
   first, but compares the reed, not the instrument; «pitched one octave above the soprano
   saxophone» compares pitch; «essentially a wooden saxophone» names no catalog entry. Parent rule 1
   needs words relating the instrument as a whole. The aulochrome's two pipes, the slide
   saxophone's slide, and a bore or bell a source says changes the sound wait under the sound-alike
   ruling; the reviewers read each sound-alike's quoted sound passage for such a trait.
5. **A name decided twice, or an ambiguous one kept.** `soprillo`, `soprillo saxophone` and
   `sopranissimo saxophone`; `tubax`, `tubax in eb` and `bb tubax`; `subcontrabass saxophone`
   beside the B♭ tubax that Eppelsheim «described as a "subcontrabass saxophone"»; `saxello` and
   `manzello`; `stritch` (Kirk's name for his own horn); `f mezzo soprano saxophone` (the page's
   «sometimes called the '''F alto saxophone'''»); `tarogato` (the modern single reed and the older
   instrument it «was intended to be a recreation of»); and the xaphoon's four names, already
   decided by batch 14. Rule 8 decides duplicates, the ambiguous ruling drops a name its sources
   give to two instruments, past or present, the code check finds every name exactly once, and the
   step checks list every candidate once.

---

## File Structure

- Rename `src/glitchygames/audio/instruments/winds.py` to `saxophones.py` (`git mv`), unchanged but
  for its table's name, `SAXOPHONES` as the concatenation, and its docstring's sound-alikes
  sentence. No `winds.py` remains: only `registry.py` imports it (checked with grep), and no
  process-state guard listing names it (`tests/test_process_state_guard.py` lists no `winds.py`
  table: `_saxophone` builds its series inside the function), so a re-export would be a module that
  holds nothing and that nothing needs.
- Create `src/glitchygames/audio/instruments/saxophone_sound_alikes.py`, holding
  `SAXOPHONE_SOUND_ALIKES`.
- Modify `registry.py` (it imports `SAXOPHONES` from `saxophones`; its place in `FAMILY_TABLES`, after
  `CLARINETS`, does not change), and every live docstring naming `winds.py`: `flutes.py` line 8,
  `clarinets.py` line 8, `double_reeds.py` line 6, `bagpipes.py` line 9, `free_reeds.py` line 5,
  the `instruments/__init__.py` docstring (lines 102, 113, 124 and 166), and
  `docs/architecture/sound.md` line 298. The only other hit, `docs/quality/graphs/complexity-explorer.json`,
  is generated and gitignored. Task 1 fixes them all, so no live file names a module that is gone.
- Modify `aliases.py` (the batch's ALIAS rows, Tasks 3 and 5).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5).
- Create `plans/data/instrument-audit/batch-19.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring's family paragraph and the stale clause in
  `saxophones.py`'s docstring, `docs/architecture/sound.md`, `CLAUDE.md`, `plans/future-features.md`
  (#70 with the closing summary, and a new #89), and the design's status line and "Depends on"
  counts.

Decisions made in this plan (my calls, for the owner to check in #89):

- **The saxophones get their own module by renaming `winds.py`, with no re-export.** Every family a
  batch has grown since batch 4 has a module named for it and a sibling sound-alikes module that
  names it (`clarinets.py` and `clarinet_sound_alikes.py`, `harps.py` and `harp_sound_alikes.py`,
  `struck_strings.py` and `struck_sound_alikes.py`); `winds.py` holds only `SAXOPHONES` and
  `_saxophone`, and #86 asks "Should `winds.py` be renamed now that it holds only the saxophones?".
  Keeping `winds.py` would leave the one family module not named for its family (batch 18 renamed
  `strings.py` for the same reason); keeping a re-export would keep a module nothing imports. The
  sound-alikes module is `saxophone_sound_alikes.py` (the member's singular, as
  `clarinet_sound_alikes.py`), and the private table `_SAXOPHONE_BUILDS`, as `_CLARINET_BUILDS`.
  Task 1's before-and-after record of all 704 builds checks the move.
- **The boundary rulings.** A row's family is decided by what sounds and how, from its fetched
  source's words, with the Hornbostel–Sachs class those words imply:
  1. *Saxophones*: a single reed on a conical bore (422.212): every saxophone size, key and model,
     and the other conical single reeds (the modern tárogató, the octavin, the heckel-clarina, the
     heckelphone-clarinet, the sarune etek, if their fetched sources say single reed and conical
     bore), **unless batch 14's sheet already decided the name** (`xaphoon`, `maui xaphoon`,
     `pocket sax`, `xaphoon de catalunya`, `saxonette`, `venova`: DROP "Already decided" when a row,
     else no row). A set of single reeds on conical bores (422.22 with conical bores: the
     aulochrome's «two [[Soprano saxophone|soprano saxophones]]») is a saxophone, waiting for its
     own build once ranged (the sound-alike ruling).
  2. *A cylindrical single reed is a clarinet* (batch 14's bore boundary, 422.211): a row whose
     fetched source gives a cylindrical bore is DROP "belongs to clarinets (a cylindrical single
     reed): <its words>". A row whose sources give both bores, or a conical one only for some
     models, is WAIT `a sourced reed and bore` (batch 14's name), not a saxophone by default.
  3. *A plastic or toy saxophone is a sound-alike of its size, or a drop*: a saxophone made of
     plastic, acrylic or another material (the Grafton's acrylic, whose page says «the body
     material having no influence on tone») is a saxophone; the material is no trait, so once
     ranged from its own source it is a sound-alike of the catalog saxophone of its size, by parent
     rule 1 or 2. A toy shaped like a saxophone whose sound is made otherwise (a free reed, a
     kazoo's membrane, a whistle) is DROP to that mechanism's family, naming it (free reeds, voices,
     flutes); one with no sound source of its own is DROP "makes no sound of its own".
  4. *The "sax" in saxhorn and saxotromba is brass* (batch 10): a lip-reed instrument named for
     Adolphe Sax, or a brass instrument in a saxophone's shape (`jazzophone`), is brass, and a
     double or free reed in a saxophone's shape is its reed's family (the sarrusophones, `rothphone`
     and `saxorusofono`: double reeds, batch 11; `couesnophone`: free reeds, batch 16). Such a name
     found here is DROP "belongs to <family>: <its words>" when not already decided, else no row.
  5. *An electronic wind controller is electronic* (batch 6's `ewi`, «a type of wind controller»,
     and `lyricon`): a controller or a "digital saxophone" whose sound is synthesized is DROP
     "belongs to electronic (a wind controller): <its words>". An acoustic saxophone with an
     electronic effect fitted (the audit's Selmer Varitone, out of scope here) is a saxophone, and
     its effect a trait the build cannot make.
  6. *The `hs` cell* holds the class a fetched source gives (an infobox on the page, the saved
     template's text, or a sentence naming what sounds and how, quoted, with the code it implies),
     else `none`. A SOUND_ALIKE row's `hs` fullmatches `422\.212(-71)?`.
- **A saxophone is a sound-alike unless a cited trait sets it apart.** `_saxophone` is `blown` over
  `falling_series(count=18, decibels_per_octave=4.5)` with breath, drive, a bite series and a
  per-size `low_pass` (8000 Hz for the sopranino down to 2500 Hz for the contrabass), every value
  sound design. A row whose sources name no other trait is a SOUND_ALIKE (the parent ruling),
  `builder` "unchanged". A key (B♭, C, E♭, F, G), a size, a shape (straight, curved, a tipped or
  upturned bell, a curved neck), a material (brass, wood, acrylic, ABS), keywork, a fingering
  system, a maker, a period, a player or a colour word ("piercing", "dark", "reedier",
  "cor-anglais-like") is no trait, unless a fetched source names an effect on the sound with the
  numbers a builder keyword takes. A trait the engine cannot make is WAIT `its own build (<the
  trait>)` or the spec's or an earlier batch's feature name, with the source quoted: two pipes
  sounding together as the instrument's way of sounding (`its own build (two pipes sounding
  together)`: the aulochrome, if its source makes the pairing its sound rather than what a player
  «can» do); a slide that is the instrument's way of changing pitch, with no keys (`a pitch LFO
  (portamento between notes)`, batch 9's `slide whistle`; a slide beside full keywork is how a
  player «can» glide, a technique); a bore, bell or body the source says changes the sound, as the
  instrument's sound (the octavin's «smaller taper», the heckelphone-clarinet's «wide conical
  bore», the Conn-O-Sax's spherical bell, if their sources state an effect on the sound): reported
  to the controller under the SHIP ruling, and WAIT `its own build (<the trait>)` unless the
  controller rules otherwise. A technique (altissimo, a growl, a glissando, multiphonics,
  subtone) is how a player sounds the instrument, not its build. A trait a builder could imitate
  by turning an unsourced keyword (a darker `low_pass` for a wooden body) is not made by the build:
  batch 11's balaban rule.
- **The SHIP ruling.** This batch plans no SHIP and no `sound_changes`. A row whose fetched source
  states a trait in the numbers `blown` takes (a stated cutoff, a stated breath level, a harmonic
  series in decibels) or a bore or bell effect is reported to the controller before its half's
  code task; the controller rules it, in a sheet fix commit, a WAIT `its own build (<the trait>)`
  or a SHIP with its rule and test added to this plan. The form check refuses a SHIP status until
  then.
- **The parent ruling.** A SOUND_ALIKE's parent is a catalog entry from before the batch (never a
  sound-alike), never one of `APPROXIMATING_NAMES`:
  1. The entry its own source relates it to as a whole instrument, by kind or sound («closely
     resembles the more common B♭ [[soprano saxophone]]», «resembling a [[soprano saxophone]]»,
     «Its size and [[timbre]] are similar to the …», «derived from the contrabass saxophone»),
     quoted in the notes after "Parent (rule 1):". When the passage names two catalog entries, the
     first named is the parent. **A comparison of a part (the reed, the bore, the mouthpiece:
     «uses a single reed, like a [[clarinet]] or [[saxophone]]») or of pitch or length («pitched one
     octave above the [[soprano saxophone]], and half its length», «one whole tone above the
     [[alto saxophone]]») relates no instrument**, and a name that is no catalog entry («a wooden
     [[saxophone]]»: `saxophone` is neither a catalog name nor an alias) is no parent. Only this
     rule may name another family's entry, and only when its words relate the sound.
  2. Otherwise the saxophone whose `lowest` note is nearest the row's own lowest note in semitones,
     the earlier catalog entry on a tie, written after "Parent (rule 2):" with the semitone counts.
     The rule-2 set is the 8 saxophones (422.212: `sopranino saxophone` D♭4, `soprano saxophone`
     A♭3, `alto saxophone` D♭3, `c melody saxophone` B♭2, `tenor saxophone` A♭2, `baritone
     saxophone` C2, `bass saxophone` A♭1, `contrabass saxophone` D♭1); every conical single reed
     shares that mechanism, so the tárogató, octavin and Heckel rows use it too.
  3. The sizes or models of one type share the type's parent: never a sound-alike's sound-alike
     (the manzello, if a row of its own, takes the saxello's parent, not the saxello).
- **Range ruling for saxophones.** A sourced range is the lowest and highest sounding notes that one
  fetched source states for the instrument:
  1. *Stated, by one source*: both notes as the range or compass, from one source (batch 14's
     `xaphoon`: two sources for one range is no range), in note names with octaves (scientific
     `D♭1`, the wikitext's «D{{flat}}{{sub|1}}» is D♭1; Helmholtz with octave marks, #84; a named
     note whose octave the source fixes), or the lowest note and an exact span above it.
  2. *Sounding, and written with its stated transposition*: notes the source gives as the sounding
     range are taken as given. A written range counts only with the transposition **the same
     source** states for that instrument («The mezzo-soprano saxophone in F sounds a [[perfect
     fifth]] lower than written», «C soprano saxophone sounds as written», «The soprillo in B♭ sounds
     a [[minor seventh]] higher than written»), the derivation shown note by note. A transposition
     from another page, from the Saxophone page's general rule or from the instrument's key alone is
     no transposition.
  3. *Extensions and extremes*: the stated keyed compass, and nothing beyond it. Altissimo notes
     («Most can reach high F♯ or higher using [[altissimo]] fingerings»), a key some models add (low
     A, high F♯, high G), or a note in parentheses is an extreme: the range is the compass without
     it, or the row WAITs. A model page that gives the extra key as standard for that model ranges
     that model's row with it (ruling 4).
  4. *A maker's or museum's page ranges that model only*: a maker's model page (Eppelsheim's
     Soprillo, Tubax E♭ and Tubax B♭ pages; a Conn or King catalogue) or a museum's object record
     (the National Music Museum's eMuseum, the Met, MIMO, the Musical Instrument Museum (Phoenix),
     the Horniman) ranges a row named for that model or object only, never the bare type name
     (#85). **The makers' ruling** (batch 14: «A maker's product in production is an instrument a
     game may ask for … decided on its maker's page»): when the fetched sources say one maker makes
     the type (its inventor's product, under the inventor's name), that maker's page ranges the
     type's row; when the sources name several makers, ruling 6 decides.
     b. *A size named in a cited sentence ranges that size only* (#87's `saung gauk`): a sentence
     giving a compass to one key, one model, one period or one size ranges a row for that one,
     never the bare name, unless the same source calls it standard (ruling 6). The worker quotes
     every such passage it finds and rules on it in the notes; a passage on a saved page that the
     notes leave out is a review finding.
  5. *Not a range*: a hedged span ("about", "approximately", "roughly", "typically", "usually", "up
     to", "just over two and a half octaves"); **a general or notation rule** (the Saxophone page's
     «Most saxophones share the same written range», the audit's "Convention" and "Range checks");
     a width or count with no pitch; note letters with no octaves; a key ("in F", "pitched in B♭");
     a transposition with no notes; a tessitura; one pitch; or **a chart**, whether drawn as an image
     (the infoboxes' `.svg` range files) or written as a LilyPond `<score>` block (Tubax,
     Mezzo-soprano, C soprano: its markup is notation drawn as an image on the page, however
     readable), as #86's concert accordion charts. The text sentence beside a chart (its
     transposition) is quotable; the chart is not. The audit's ranges are leads, not sources (its
     "VERIFIED" soprillo, tubax and F mezzo included: each is derived from a written range and a
     convention, or from a retailer).
  6. *Several sizes, keys or models, none standard*: a bare type name with several sizes, keys or
     models is ranged only from a source that calls one standard, usual, most common or traditional
     for the bare name. "Became widespread", "popular", "modern" or "the 2010 models" is none of
     these (#86's `khromka`). A source giving one instrument two ranges has given none, unless it
     calls one standard (the C soprano page's «standard vintage horn from 1920–1928» is standard for
     that period's horn: it ranges a `c soprano saxophone` row only if the worker shows the page
     makes that horn the instrument's standard, and the controller agrees; else the row WAITs). "One
     common version" is a version (#87's `baroque triple harp`): it ranges that version's row only.
     With neither, the row WAITs (batch 7's rule; batch 14's `birbyne`).
  7. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached); a
     maker's catalogue or model page (ruling 4); a museum's object record; a scholarly article
     (Paul Cohen's «The Saxophone Redefined – Soprillo and Tubax», cited on the Soprillo and Tubax
     pages, if reached); or a conservatory or orchestration reference (the Vienna Symphonic
     Library). A museum's or maker's page outranks an uncited Wikipedia line, and when they disagree
     the museum or maker decides (batch 11). A retailer's listing, a blog (bassic-sax.info), a
     forum, an auction listing, a hobbyist's gallery (jayeaston.com's galleries are a player's
     pages: a lead) or a musicbrainz mirror is not a source. A list or category page is a source for
     a name only. A range is never taken from a sibling, the parent, a related instrument, the
     audit or memory.
  8. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`) and nothing above C8
     (WAIT `a range above C8`). A sourced range reaching below A0 is still quoted in full under
     `Range:`; the row is WAIT `sub-audio fundamentals`, its `lowest` and `highest` left empty.
  9. *One note*: an instrument whose source gives it one note has no range. It WAITs `a sourced
     range`, the note quoted.
  10. *Cited*: a range or trait from Wikipedia counts only when the raw wikitext shows a citation (a
      `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it in its own cell or paragraph, with no
      `{{citation needed}}` first, in a section not tagged `{{Unreferenced section}}`. An infobox
      `range` field with no `<ref>` in it is uncited (the Tubax, Mezzo-soprano, C soprano and
      Subcontrabass infoboxes, as fetched for this plan). The citation must support the line: where
      the cited work is reachable the worker opens it, and a citation that gives no range (batch
      11's `shehnai`) or points to a retailer is none.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then the
  derivation.
- **Names lists are ruled by their sub-list** (#88's final ruling). A list on a page is read by its
  own heading or sentence: a list describing an instrument spreading or changing («was spread to»,
  «derived», «variants of the instrument») gives versions (rows of their own); a list whose heading
  is etymology or naming («also known as», «names», «from Latin …») gives names (aliases). A name
  whose own page redirects to another catalog entry is ambiguous (#88's `tsimbl` and `tambal`).
  **An infobox's `names` do not outweigh the page's own text** (#88's `urucungo`: the Berimbau
  page's «terms used for musical bow» outweighed its infobox `names`). The case to check first: the
  Tárogató infobox's «names = {{hlist|Taragot|töröksíp|torogoata|Turkish pipe}}», which no row
  decides (none is an audit name), beside its text's «The modern tárogató was intended to be a
  recreation of the …».
- **Generic and ambiguous terms.** A name its source gives to a class or to several instruments is
  DROP "a generic term for <the instruments>" or "an ambiguous name: <the instruments>", unless the
  source makes it one instrument's name (then rule 3). **A name is ambiguous when its fetched
  sources give it to two instruments, past or present** (#87, #88). The cases to check first:
  `tarogato` (the modern single-reed tárogató and the older instrument the page says it recreates:
  if the page gives both the name, the row is DROP "an ambiguous name", and a later pass may add
  `modern tarogato`; if the page makes the older one another name's, the row is the modern
  instrument's); `subcontrabass saxophone` (Sax's «saxophone bourdon», J'Élle Stainer's and
  Eppelsheim's instruments, and Eppelsheim's B♭ tubax «he described as a "subcontrabass
  saxophone"»: one instrument type made by several, or two instruments); `stritch` (the
  disambiguation page lists a cardinal and an actress, which are no instruments: only instrument
  senses count). A size's or key's name is no alias of its type (`tubax in eb` is not the tubax):
  it is a row of its own under the range rulings.
- **A player's name for his own instrument is no instrument type.** The Saxophone page: «Rahsaan
  Roland Kirk, who called his straight Buescher alto a "stritch" and his Saxello a "manzello"». A
  name one player gave his own horn is DROP "a player's name for his own instrument: <the words>",
  unless a fetched source gives it as a type others make or a maker's model name (then the versions
  ruling: a row of its own), or as another name for the instrument itself (then rule 8: ALIAS).
- **Versions are not aliases.** A source's «a version of», «a variant», «a type of», «derived
  from», «modified» or «related» makes the row a separate instrument (a sound-alike by parent rule
  1 once ranged), never an alias (#87's `baroque triple harp`). Rule 8 makes an alias only of a
  name a cited page gives to the same instrument («also known as», «sometimes called», a names
  list ruled as names). `curved soprano saxophone` is decided by the Soprano saxophone page's own
  words (a shape of the same instrument, «some have a» curved form: an alias only if the page
  names it so; a model a maker sells as such is a version).
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's in-production
  line and batch 14's makers' ruling): DROP "a one-off instrument, not a type a game would ask for"
  for one maker's or artist's design never made as a type (`g mezzo soprano saxophone`, Peter
  Jessen's horn «most notably played by [[Joe Lovano]]», and `contralto saxophone`, Jim Schmidt's,
  are the first cases to check: a type that maker builds to order or sells is no one-off); DROP "no
  fetched source describes it" when no fetched page describes the row, applied the same to every
  such row, candidate or alias name. A historical production instrument a museum holds (the slide
  saxophone at the National Music Museum, the Conn-O-Sax at the Met and the MIM, Phoenix) is not a
  one-off.
- **Two halves, as explicit lists.** Half A, the saxophones (every size, key and model the audits
  name as a saxophone, and the aulochrome, «two [[Soprano saxophone|soprano saxophones]]»), is
  these 14 candidates:
  `aulochrome`, `bb tubax`, `c soprano saxophone`, `conn o sax`, `contralto saxophone`, `f mezzo
  soprano saxophone`, `g mezzo soprano saxophone`, `grafton alto saxophone`, `saxello`, `slide
  saxophone`, `soprillo`, `soprillo saxophone`, `subcontrabass saxophone`, `tubax`.
  Half B, the other conical single reeds and the xaphoon's already-decided names, is the other 7:
  `heckel clarina`, `heckelphone clarinet`, `maui xaphoon`, `octavin`, `sarune etek`, `tarogato`,
  `xaphoon`.
  The list decides the half. The alias names go with the half whose candidate or target their line
  names: half A's 5 (`stritch`, `manzello`, `tubax in eb`, `curved soprano saxophone`,
  `sopranissimo saxophone`) and half B's 2 (`pocket sax`, `xaphoon de catalunya`), each half in
  the audit's order. So half A's sheet holds 19 rows and half B's 9. Half B is the smaller; its
  rows need the scholarly and maker sources (Dullat, the 2017 sarune etek article, Heckel), and its
  four already-decided rows are quick.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the batch
  or a SOUND_ALIKE row of the same half, never a row of the other half. So Task 4 needs nothing
  from Task 2. Half B drafts to a build file, appended to the sheet once half A is committed. The
  form check accepts a row the code already holds with the same target or parent (batch 7's
  lesson).
- **Rows that wait for their target name it.** A WAIT whose `waits_for` is `its target, <name>`
  holds `<name>` in `alias_of` too (#87); the form check refuses one that does not. An "Already
  decided" row keeps its earlier sheet's status in its notes and is DROP here, its `alias_of`
  empty.
- **A held-back guard.** As batch 18's `STRUCK_HELD_BACK`, this batch's guard is
  `SAXOPHONE_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose
  reason is not `a sourced range` (`sub-audio fundamentals`, a build of its own, a pitch LFO, a
  sourced reed and bore, a range above C8), and every alias row that waits for such a row. A test
  refuses each of its names in the catalog and the aliases through `names_listed`, and the code
  check compares the table with the sheet, in the sheet's order. Unlike batches 15 to 18, this
  guard is expected to hold names: the B♭ tubax and the subcontrabass have stated ranges reaching
  A♭0 (leads: the Tubax infobox sentence and Eppelsheim's B♭ page). A row that waits for a range
  but will need a build of its own once ranged (the aulochrome; the slide saxophone) is not in the
  guard: its notes say so, and #89 lists it.
- **The guards' helpers are tested once, on real builds, both ways.** `names_listed` and
  `entries_with_sound_changes` exist, and `test_the_harp_guards_helpers_read_real_builds` tests
  them on real builds both ways. This batch adds no second copy (#87's parked minor); Task 1 runs
  it, shows each new guard failing on a wrong table, and shows each helper failing when broken (as
  batch 18's Task 1 did, #88).
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SOUND_ALIKE
  or ALIAS row, its code task still fills `SAXOPHONE_HELD_BACK` with the half's held rows and runs
  the code check, which must pass; its other steps are skipped, it commits only if the test file
  changed, and Task 6 records the skip in #89. Half B is likely to (its four xaphoon rows are
  already decided).
- **Out of scope:** the audit's "Gaps you could not close" (the Met article on the Conn-O-Sax and
  rare saxophones; MIMO and the Horniman browsed; the rothphone and `saxorusofono`, double reeds;
  Eppelsheim's C tubax and other models; the Saxophone page past its first 100,000 characters;
  Adolphe Sax's patent list of sizes, the C bass saxophone, the Buescher and Conn C basses, the
  vibrato sax and the Selmer Varitone), the names a page mentions in passing (`piccolo saxophone`
  on the Soprillo page, the F baritone prototypes, the Keilwerth and L.A. Sax straight altos and
  tenors), and the xaphoon's keys (#84's later clarinets pass). Task 6 lists them in #70 for a
  later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of the build files is committed.

- [ ] **Step 0: The branch and the plan.** Run `git branch --show-current` and `git rev-parse
  --short HEAD`. Expected: `feat/instrument-catalog-batch-19` and `6503a1e1`. Anything else: stop
  and find out why. Copy this plan to `plans/2026-11-12-instrument-catalog-batch-19-implementation.md`
  and commit it:
```bash
git add plans/2026-11-12-instrument-catalog-batch-19-implementation.md
SKIP=replay-metrics git commit -m "Plans: batch 19 of the instrument catalog (saxophones), the implementation plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-19-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-19-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names), len(instruments.CATALOG), len(instruments.ALIASES))
"
```
  Expected (after pygame's banner): `names before 842 704 138` (checked for this plan at
  `6503a1e1`). Any other number means the branch is not batch 18's tip: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && tolower($4) ~ /saxophone/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /saxophone/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' tarogato octavin 'heckel clarina' 'heckelphone clarinet' 'sarune etek'
} | LC_ALL=C sort -u | LC_ALL=C comm -23 - ../../../build/batch-19-names-before.txt > ../../../build/batch-19-candidates.txt
cd ../../..
```
  Write the plan's 14 half-A names, one per line, to `build/batch-19-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-19-candidates.txt build/batch-19-half-a.txt > build/batch-19-half-b.txt`
  and `wc -l build/batch-19-*.txt`.
  Expected: 21 candidates, 14 in half A, 7 in half B, and
  `LC_ALL=C comm -13 build/batch-19-candidates.txt build/batch-19-half-a.txt` prints nothing.
  Check that `build/batch-19-half-b.txt` is exactly the plan's half-B list. The sorted union before
  the `comm` is also 21 names (no candidate is already a catalog name or alias); without the
  `printf` line it is 16 (`tubax` and `subcontrabass saxophone` are in both audit lists).

- [ ] **Step 3: The form check,** `build/batch-19-form-check.py`. Copy `build/batch-18-form-check.py`
  and change it as follows; `STATUSES`, `pattern`, `held_as_this_row`, `taken`, `in_span`,
  `changes`, `ranged`, the `bad` list's shape and the output stay.
  - The docstring:
```python
"""Batch 19's sheet form check: uv run python -I build/batch-19-form-check.py SHEET.

Batch 18's form check (build/batch-18-form-check.py) with batch 19's changes (batch 19's plan,
"Before the tasks" Step 3): the saxophones family, a sound-alike's conical single-reed class, the
rule-2 parents keyed by the whole class, and an alias target that is a pre-batch catalog entry or
a sound-alike row of this sheet, never a later catalog entry.
"""
```
  - `names_before` reads `build/batch-19-names-before.txt`; `APPROXIMATING_NAMES` is checked against
    the test file's (unchanged since batch 13); `STRUCK_CLASS` and batch 18's `RULE_TWO_PARENTS`
    are replaced by:
```python
# Hornbostel-Sachs checked against Wikipedia's aerophone list and Template:Infobox_saxophone for
# batch 19's plan: a single reed with a conical bore (422.212), with the template's keys suffix
SAXOPHONE_CLASS = re.compile(r'422\.212(-71)?')
# The parent ruling's rule 2: the catalog saxophones (batch 19's plan)
RULE_TWO_PARENTS = {
    '422.212': {
        'sopranino saxophone', 'soprano saxophone', 'alto saxophone', 'c melody saxophone',
        'tenor saxophone', 'baritone saxophone', 'bass saxophone', 'contrabass saxophone',
    },
}
```
    and `alike_allowed`'s mechanism line reads
    `in_mechanism = parent in RULE_TWO_PARENTS.get(row['hs'].split('-')[0], set())`.
  - The `bad` list's family test is `row['family'] != 'saxophones'`; its sound-alike test reads
    `not SAXOPHONE_CLASS.fullmatch(row['hs'])` for batch 18's `STRUCK_CLASS`; its ALIAS test reads
    `row['alias_of'] not in (names_before & set(instruments.CATALOG)) | alikes` (batch 18's `|
    set(instruments.CATALOG)` accepted any catalog entry the code held at the time, the other
    half's coded sound-alikes included, against the plan's "never a row of the other half"); and it
    adds one test:
```python
       or (row['status'] == 'WAIT' and row['waits_for'] == 'sub-audio fundamentals'
           and (row['lowest'] or row['highest'] or 'Range:' not in row['notes']))
```
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: The quote check,** `build/batch-19-quote-check.py`. Copy
  `build/batch-18-quote-check.py` and change it as follows; `CITATION`, `UNCITED_TAG`, `ERROR_PAGE`,
  `EMAIL`, `read_page`, `visible`, `located`, `cited`, `quoted`, `on_page`, the charset and email
  lists, the shipped rows' one `range` section and the every-row ledger check stay.
  - The docstring: batch 18's, with "Batch 19's" and `build/batch-19-quote-check.py` in its first
    line, "Batch 18's quote check (build/batch-18-quote-check.py) with batch 19's changes (batch
    19's plan, "Before the tasks" Step 4)" in its second paragraph, and a last sentence: "A saved
    page that is only a Wikipedia redirect is a failure: the page it points to is saved instead."
  - `PAGES = Path('build/batch-19-pages')`, and:
```python
# A Wikipedia redirect saved as a row's page (batch 19's plan: the target page is saved instead)
REDIRECT_PAGE = re.compile(r'\A\s*#REDIRECT\s*\[\[', re.IGNORECASE)
```
    with each page read appending `(row['name'], 'saved page is a redirect: ' + path.name)` to the
    failures when `REDIRECT_PAGE.match(text)`.
  It checks what can be checked mechanically; a worker still applies range ruling 10 in full.

- [ ] **Step 5: The code check,** `build/batch-19-code-check.py`: copy `build/batch-18-code-check.py`
  and change it as follows; `test_table`, `held_back`, `in_catalog_order`, the "Already decided"
  branch, the shipped-row assertions and the order checks' shape stay.
  - The docstring:
```python
"""Batch 19's code check: uv run python -I build/batch-19-code-check.py SHEET.

Batch 18's code check (build/batch-18-code-check.py) with batch 19's changes (batch 19's plan,
"Before the tasks" Step 5): the saxophones family, no sound changes and no tags compared with the
sheet, and the builds, sound-alikes and aliases in the sheet's order. The test file's tables are
read as literals (ast.literal_eval), never evaluated. A one-off check may read the private
_SAXOPHONE_BUILDS; a test may not.
"""
```
  - The imports read `SAXOPHONE_SOUND_ALIKES` from `saxophone_sound_alikes` and `_SAXOPHONE_BUILDS`
    from `saxophones`; `EXISTING_COUNT = 8`; `NAMES_BEFORE` reads `build/batch-19-names-before.txt`.
  - The table assertions after the loop name `SAXOPHONE_HELD_BACK`, `NEW_SAXOPHONE_NAMES` and
    `SAXOPHONE_SOUND_ALIKE_PARENTS` for batch 18's three, and `_SAXOPHONE_BUILDS` and
    `SAXOPHONE_SOUND_ALIKES` for `_STRUCK_BUILDS` and `STRUCK_SOUND_ALIKES`, with the messages
    renamed to match.
  It cannot run until Task 1 has created `saxophones.py`, `saxophone_sound_alikes.py` and the test
  tables. The "Already decided" DROP rows (`xaphoon`, `maui xaphoon`, `pocket sax`, `xaphoon de
  catalunya`) were never catalog names or aliases, so they take the last branch.

- [ ] **Step 6: The final audit,** `build/batch-19-final-audit.py`, for Task 6 (the expansion's
  close). New, written from this description:
```python
"""The instrument catalog expansion's final audit: uv run python -I build/batch-19-final-audit.py.

Batch 19's plan, "Before the tasks" Step 6. Reads every plans/data/instrument-audit/batch-N.tsv in
batch order (csv module) and finds each name's standing decision: a later sheet's row replaces an
earlier one, except a DROP whose notes begin "Already decided" (any case), which leaves the earlier
row standing. Fails when a standing SHIP, SOUND_ALIKE or MOVE name is not a catalog entry, a
standing ALIAS is not an alias of its alias_of, or a standing WAIT name is a catalog name or alias;
lists, for the controller, each standing DROP whose name the code holds. Prints the standing
counts, the WAIT reasons (a sourced range, its target, and every other reason with its names) and
the standing DROPs whose notes send the row to another family (open hand-offs).
"""
```
  It reads no `build/` file and imports only `csv`, `collections`, `re`, `sys`, `pathlib` and
  `glitchygames.audio.instruments`. Run it now:
  `uv run python -I build/batch-19-final-audit.py`.
  Expected at `6503a1e1` (18 sheets; checked for this plan with a prototype): `names 2023`, the
  standing counts `SHIP 73, SOUND_ALIKE 197, MOVE 14, ALIAS 138, WAIT 1220, DROP 381`, `bad: []`,
  and 8 standing DROPs the code holds, for review: `whip crack`, `vibraslap`, `cuica` and `whip`
  (`batch-2.tsv`), `thunder sheet` and `ocean drum` (`batch-3.tsv`), `singing bowl`
  (`batch-5.tsv`) and `sackbut` (`batch-6.tsv`). Each is a drop of a name already in the catalog or
  an alias under that name; the controller reads each row's notes and records the ruling for Task
  6. Exit 0. A `bad` entry here is a finding about an earlier batch: stop and report it.

---

### Task 1: Saxophones in their own module, renamed from winds.py, unchanged; their sound-alikes module; the batch table's row and the held-back and sound-change guards, each shown failing on a wrong table

**Files:**
- Rename: `src/glitchygames/audio/instruments/winds.py` to `saxophones.py` (`git mv`)
- Create: `src/glitchygames/audio/instruments/saxophone_sound_alikes.py`
- Modify: `registry.py`, the docstrings of `flutes.py`, `clarinets.py`, `double_reeds.py`,
  `bagpipes.py`, `free_reeds.py` and `instruments/__init__.py`, and `docs/architecture/sound.md`
  (the sound-alike modules sentence)
- Test: `tests/audio/test_instrument_catalog.py`; run `tests/test_process_state_guard.py`

**Interfaces:**
- Produces: in `saxophones.py`, `SAXOPHONES: Final[tuple[CatalogEntry, ...]] = _SAXOPHONE_BUILDS +
  SAXOPHONE_SOUND_ALIKES`, and `_saxophone(*, low_pass: float) -> Instrument` under its current
  name. `SAXOPHONE_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test file gains
  `EXISTING_SAXOPHONE_NAMES: frozenset[str]` (the 8); `NEW_SAXOPHONE_NAMES: list[str]`,
  `SAXOPHONE_SOUND_ALIKE_PARENTS: dict[str, str]` and `SAXOPHONE_HELD_BACK: dict[str, str]`, all
  empty here, for Tasks 3 and 5 to fill; the two guard tests below; and the row
  `Family.SAXOPHONES: BatchFamily(EXISTING_SAXOPHONE_NAMES, NEW_SAXOPHONE_NAMES,
  SAXOPHONE_SOUND_ALIKE_PARENTS)` in `BATCH_FAMILIES`. Also `build/catalog-builds-before.txt`.
- Consumes: `names_listed(names: Iterable[str]) -> set[str]` and
  `entries_with_sound_changes(family: Family) -> list[str]`, already in the test file.

The move comes first and the guards after, so no step expects a test to pass before the module it
imports exists (#86).

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
  `git mv src/glitchygames/audio/instruments/winds.py src/glitchygames/audio/instruments/saxophones.py`.
  In `saxophones.py`, rename the tuple `_SAXOPHONE_BUILDS` (its entries, builder and comments
  unchanged), import `SAXOPHONE_SOUND_ALIKES`, and define `SAXOPHONES: Final[tuple[CatalogEntry,
  ...]] = _SAXOPHONE_BUILDS + SAXOPHONE_SOUND_ALIKES` after it. The docstrings:
  - `saxophones.py` keeps its first line, "Saxophones: conical single reeds, sopranino to
    contrabass saxophone.", its sibling-modules sentence, its ranges sentence and its timbre
    sentence verbatim (the ranges sentence's stale clause is Task 6's), and adds after the sibling
    sentence: "The family's sound-alikes, listed instruments that share another entry's build, are
    in ``saxophone_sound_alikes.py``.", rewrapped to 100 columns.
  - `saxophone_sound_alikes.py` gets the empty table and `struck_sound_alikes.py`'s docstring with
    "Saxophones'" for "Struck strings'", ending "The family's builds are in ``saxophones.py``.". Its
    first line is "Saxophones' sound-alikes: listed instruments that share another entry's
    build." Its imports are `struck_sound_alikes.py`'s (`CatalogEntry` under `TYPE_CHECKING`).
  - Every docstring naming ``winds.py`` names ``saxophones.py``, rewrapped to 100 columns:
    `flutes.py` line 8, `clarinets.py` line 8, `double_reeds.py` line 6, `bagpipes.py` line 9 and
    `free_reeds.py` line 5 ("the saxophones in ``saxophones.py``", "The saxophones are in the
    sibling module ``saxophones.py``"); in the `instruments/__init__.py` docstring, lines 102, 113
    and 124's "``winds.py`` keeps the saxophones" becomes "``saxophones.py`` holds the saxophones",
    and line 166's "``winds.py`` now holds only the saxophones." becomes "The saxophones are in
    ``saxophones.py``."; `docs/architecture/sound.md`'s "`winds.py` now holds only the saxophones"
    becomes "the saxophones' builds are in `saxophones.py`" (Task 6 adds their sound-alikes module
    to that sentence with its count).
  Point `registry.py` at `saxophones` (`from glitchygames.audio.instruments.saxophones import
  SAXOPHONES`, placed in sorted order, after `plucked_strings` and before `sound_effects`; its place
  in `FAMILY_TABLES` does not change).

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
grep -rn 'winds\.py\|instruments\.winds\|winds import' src tests scripts docs/architecture CLAUDE.md
git status --short
uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q
```
  Expected: `changed: []`; nothing from `awk`; nothing from `grep` (no live file names `winds.py`);
  `git status` shows `R` for the rename; then PASS.

- [ ] **Step 4: Write the tables and the guards.** After batch 18's struck tables
  (`STRUCK_SOUND_ALIKE_PARENTS`), add `EXISTING_SAXOPHONE_NAMES` (the 8 names, one per line, in
  catalog order: `sopranino saxophone`, `soprano saxophone`, `alto saxophone`, `c melody
  saxophone`, `tenor saxophone`, `baritone saxophone`, `bass saxophone`, `contrabass saxophone`),
  with the comment "# The 8 saxophones that predate batch 19: their shared builds predate the
  anti-goal rule", then `NEW_SAXOPHONE_NAMES: list[str] = []` and
  `SAXOPHONE_SOUND_ALIKE_PARENTS: dict[str, str] = {}`, each commented as batch 18's struck lists
  are (naming `plans/data/instrument-audit/batch-19.tsv`). Put the saxophones row between the
  clarinets and double reeds rows in `BATCH_FAMILIES`, which is table order. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list gains `+
  list(SAXOPHONE_SOUND_ALIKE_PARENTS)` between the clarinets' and the double reeds' lines, its
  comment reading "… flutes, clarinets, saxophones, double reeds, …". At the end of the file add:
```python
# Every name plans/data/instrument-audit/batch-19.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for sub-audio fundamentals, an engine feature, a build
# of its own, a sourced reed and bore or a range above C8, and the alias rows that wait for one of
# them, in the sheet's order. None ships under that name or as an alias until the reason is met
# (decision 4; batch 19). The test matches exact names
SAXOPHONE_HELD_BACK: dict[str, str] = {}
```
  Then the tests, each with a one-line docstring:
  - `test_no_saxophone_name_held_back_for_a_feature_is_listed`:
    `names_listed(SAXOPHONE_HELD_BACK) == set()`.
  - `test_no_saxophone_sound_alike_changes_its_parents_build`:
    `entries_with_sound_changes(Family.SAXOPHONES) == []` (the sound-alike ruling).
  No new helper test: `test_the_harp_guards_helpers_read_real_builds` tests both helpers on real
  builds both ways (the plan's ruling).

- [ ] **Step 5: Run them, then show each guard and helper failing.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or guards_helpers or changes_its_parents" -v`
  Expected: PASS, with the ID `[saxophones]` in the parametrised batch tests. Then, without
  committing, each of these, rerunning the named tests and restoring the change after each:
  - `SAXOPHONE_HELD_BACK = {'alto saxophone': 'its own build (a test)'}`, `-k
    "saxophone_name_held_back"`: Expected FAIL naming `alto saxophone`.
  - `EXISTING_SAXOPHONE_NAMES` without `'contrabass saxophone'`, `-k "new_entries and
    saxophones"`: Expected FAIL.
  - `SAXOPHONE_SOUND_ALIKE_PARENTS = {'tenor saxophone': 'alto saxophone'}`, `-k
    "sound_alike_is_listed"`: Expected FAIL (a pre-batch build is no sound-alike).
  - `names_listed` returning `set()`, and `entries_with_sound_changes` with its condition inverted
    (`if not catalog_entry.sound_changes`), `-k "guards_helpers"`: Expected FAIL each time.
  Then rerun the first command: PASS. `git diff --stat` shows only the intended edits.

- [ ] **Step 6: Lint, check for suppressions, and commit.** Run each lint command as its own line
  (batch 11: zsh word-splitting once made a combined run a no-op).
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git diff 6503a1e1 -- src tests | grep -n '^+.*\(noqa\|ruff: ignore\|type: ignore\|pyright: ignore\|pragma\)'
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py docs/architecture/sound.md
SKIP=replay-metrics git commit -m "Instrument catalog: saxophones in their own module, renamed from winds.py, unchanged; their sound-alikes module; the held-back and sound-change guards" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
  Expected: the three lint commands pass, and the `grep` prints nothing.

---

### Task 2: The saxophones sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch` for searching, and fetch
every URL you cite with `curl -fsS -L`, saving it. A WebFetch summary is a lead, never a source
(#85); never cite a page you did not save. Put no personal data in any request, in a header, a URL
or a payload. Save each row's raw pages straight to `build/batch-19-pages/<name, spaces as
hyphens>--<n>.txt` (for Wikipedia, the `action=raw` wikitext; never a text extracted from it, which
drops `<ref>` and `<sup>`: #81; never a scratch copy named by the page title: #87; for a page that
keeps refusing curl, the Internet Archive's `id_` copy). **Never save a 404 or other error page**:
`curl -fsS -L` fails on one, and the row's notes say "returned 404"; a 429 is waited out and
fetched again. **Never save a redirect**: note it in the row and save the page it points to. After
each save, check the file is the page (`grep -l "Wikimedia Error" build/batch-19-pages/*` and `grep
-l '^#REDIRECT' build/batch-19-pages/*` print nothing). If a saved page holds a private person's
email address or phone number, delete it before any row cites it and note the lead in the row, or
tell the controller, who redacts it; an institution's or company's public contacts stay. This holds
for every row whose notes quote a page, WAIT and DROP rows too, since the quote check reads them
all. A list or category page is a source for a name only. The sound, the reed and bore and the
range come from the instrument's own page, a maker, a museum or a scholarly article under range
ruling 7; a chart, as an image or a `<score>` block, is not quotable (range ruling 5). A class from
`{{Infobox saxophone}}` needs the template's raw text saved as one of the row's pages (Global
Constraints). The audit's rows and "Range checks" are leads, not sources, so fetch them. Fetch the
page of every existing entry you name as a parent, and record what it says in the row's notes.
Never use `git stash`. This task may start as soon as the controller has written the shared files,
alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-19.tsv`
- Create (not committed): `build/batch-19-half-a.tsv`, and the raw pages in `build/batch-19-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `saxophones.md` (its rows, "Rejected or
  corrected proposed entries", "Aliases", "Range checks", "Gaps you could not close");
  `round-1/merged-missing.tsv` (the `aulochrome`, `tubax`, `subcontrabass saxophone` and
  `soprillo` rows); `build/batch-19-names-before.txt`, `build/batch-19-half-a.txt`,
  `build/batch-19-half-b.txt`, `build/batch-19-form-check.py` and `build/batch-19-quote-check.py`.
- Produces: `batch-19.tsv` with batch 18's seventeen columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	drones	drone_source`.
  `status` is one of `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP` (no SHIP: the SHIP ruling).
  `alias_of` holds an ALIAS row's target, a SOUND_ALIKE row's parent, or the target an `its target,
  <name>` WAIT names. `family` is `saxophones` on every row; `tags` is empty, `drones` is `none` and
  `drone_source` empty on every row. A SOUND_ALIKE row has `lowest`, `highest` (sounding),
  `range_source`, an `hs` that fullmatches `422\.212(-71)?`, `builder` "unchanged", and `notes`
  holding `Range:` with its «raw passages» and derivation (a written range: the source's
  transposition and each note derived), and its parent ruling line ("Parent (rule 1):" or "Parent
  (rule 2):"). A `sub-audio fundamentals` WAIT has `Range:` with its passages and empty `lowest`
  and `highest`. A candidate row's `audit_name` is its name in `build/batch-19-candidates.txt`; an
  alias row's is its audit line as the Spec line gives it.
  Also `build/batch-19-half-a.tsv`, the half as committed, which Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-19-half-a.txt`'s order, then
  one per alias name of this half, in the plan's order.

  The rules are batch 18's, changed for this family:

  1. **No SHIP** (the SHIP ruling): a row whose source states a trait in numbers `blown` takes, or
     a bore, bell or body effect on the sound, is reported to the controller with the passage, and
     waits for the ruling.
  2. **SOUND_ALIKE**: a verified instrument that the sound-alike ruling finds would sound like an
     existing entry. `alias_of` is its parent (the parent ruling). The `notes` begin "Sound-alike:",
     quote the source's description, its reed and bore, and say why that entry is the parent
     ("Parent (rule 1):" with the source's words relating the whole instrument, or "Parent (rule
     2):" with the semitone counts). It has its own range, and the `builder` cell says "unchanged".
     It is never another sound-alike's sound-alike, never one of `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited («also known as», «sometimes called», a
     names list ruled as names), never a version, a size or a relative (the versions ruling). The
     target is a catalog name or a SOUND_ALIKE row of this half. If the target waits, the row is
     WAIT with `waits_for` `its target, <name>` and `alias_of` `<name>`. If the target is dropped,
     the row is DROP "its target, <name>, is dropped". An ambiguous name or a generic term is DROP
     under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `sub-audio fundamentals`, `a range above
     C8`, `a sourced reed and bore`, `a pitch LFO (portamento between notes)`, `its own build (<the
     trait>)`, or another name of Global Constraints. **The range is checked first.** The feature
     must be the sound the source describes, not a technique a player «can» apply. A cited trait no
     builder makes means the row waits. Any other name is allowed only with the source quoted, and
     Task 6 lists it in #89.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     boundary ruling's words), is a one-off, is a player's name for his own instrument, makes no
     sound, or is already decided: in the catalog under that name (name the entry), an alias
     already (name its target), or a row of an earlier sheet (notes beginning "Already decided:",
     naming the sheet whose status stands and that status).
  6. A row the audit marks UNVERIFIED or sources only by a list page, a retailer, a forum, a blog,
     a player's gallery or the general Saxophone page's convention has no sourced sound or range
     yet. Fetch its own page; the audit's URL is a lead. If no page can be found, the row is DROP
     "no fetched source describes it", the same words on every such row.
  7. **The anti-goal:** compare each SOUND_ALIKE row's quoted sound with the sound-alike ruling's
     list before writing it: a key, a size, a shape, a material, keywork, a maker, a period, a
     player or a colour word is no trait; two pipes, a slide that replaces the keys, or a stated
     bore or bell effect is a trait the build cannot make (WAIT).
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.
  9. **Ranges and sizes:** every passage on a saved page that gives a compass, written or sounding,
     for the row's instrument, a key, a model, a period or one object of it is quoted in the notes
     and ruled on (range rulings 2 to 6), so a reviewer never finds one the notes leave out (#87's
     `saung gauk`).

  This half's own cases:

  - **Soprillo.** `soprillo` and `soprillo saxophone` are one instrument (rule 8): `soprillo
    saxophone` is the row that decides it (the round-2 audit's name, in the family's "<size>
    saxophone" form), and `soprillo` is ALIAS of it (the page's title; WAIT `its target, soprillo
    saxophone` if the target waits). `sopranissimo saxophone` follows the Soprillo page's «also known
    as the '''piccolo saxophone''' or rarely '''sopranissimo saxophone'''» (rule 3). Its range:
    Eppelsheim's Soprillo page under the makers' ruling if the sources name Eppelsheim alone as its
    maker, else ruling 4's model row; the infobox's «sounds a [[minor seventh]] higher than written»
    is a transposition with no notes, and its range is an image. Parent: «pitched one octave above
    the [[soprano saxophone]]» is a pitch comparison, so rule 2 (or rule 1 if a source relates the
    instrument as a whole).
  - **The tubax.** `tubax`, `bb tubax` and the alias row `tubax in eb` are decided together. The
    Tubax page makes the tubax two sizes («E♭ tubax … the B♭ tubax»), and a C size is mentioned:
    the bare `tubax` is ranged only by ruling 6 (a source calling one size standard) or WAITs `a
    sourced range`; `tubax in eb` is a size, no alias (the ambiguous ruling's sizes sentence), a row
    of its own ranged by Eppelsheim's E♭ model page; `bb tubax` likewise by the B♭ page, and its
    A♭0 is below A0, so it is WAIT `sub-audio fundamentals` (range ruling 8), held back. The Tubax
    short description, «Musical instrument derived from the contrabass saxophone», is a rule-1
    relation for the E♭ size. The infobox's LilyPond `<score>` is a chart; its sentence («E♭ tubax
    sounds two octaves and a [[major sixth]] lower, to D♭1») has no `<ref>` in the infobox.
  - **The subcontrabass.** `subcontrabass saxophone` is decided by the ambiguous ruling first (Sax's
    «saxophone bourdon», Stainer's and Eppelsheim's instruments, and the B♭ tubax Eppelsheim
    «described as a "subcontrabass saxophone"»), then by the range rulings: its infobox's «sounds
    three octaves and a [[major second]] lower than written» and «extended to a written low B♭
    (sounding A♭)» reach A♭0, so if it is ranged it is WAIT `sub-audio fundamentals`, held back.
  - **The keys and models.** `c soprano saxophone` (the page's two ranges, «the standard vintage
    horn from 1920–1928» and «The 2010 models», under ruling 6), `f mezzo soprano saxophone` (the
    Mezzo-soprano saxophone page; «sometimes called the '''F alto saxophone'''»: a name to note,
    not an audit name), `g mezzo soprano saxophone` (Jessen's: the one-off ruling first),
    `contralto saxophone` (Jim Schmidt's: the one-off ruling first), `conn o sax` (Conn's, F, «extra
    keys for low A and up to high G»; its spherical bell under the sound-alike ruling; museum
    records under ruling 4), `saxello` (King's straight B♭ soprano «with a slightly curved neck and
    tipped bell»: a model, a version of the soprano; a shape is no trait), `slide saxophone`
    (Reiffel & Husted's «slide soprano saxophone», the NMM holding one: the slide under the
    sound-alike ruling), `grafton alto saxophone` (boundary ruling 3: acrylic, «the body material
    having no influence on tone»), and `aulochrome` (two soprano pipes: boundary ruling 1's set, its
    own build once ranged; François Louis's design under the one-off and makers' rulings).
  - **The alias names.** `stritch` and `manzello` are decided by the player's-name ruling (the
    Saxophone page: «who called his straight Buescher alto a "stritch" and his Saxello a
    "manzello"»; «The Buescher straight alto was a production instrument while the …»: quote the
    rest and rule). `curved soprano saxophone` is decided by the versions ruling on the Soprano
    saxophone page's own words. `tubax in eb` and `sopranissimo saxophone` are above.

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-19-form-check.py plans/data/instrument-audit/batch-19.tsv`
  and `uv run python -I build/batch-19-quote-check.py plans/data/instrument-audit/batch-19.tsv`.
  Expected: `19 rows;` and the counts, then `bad: []`, exit 0; then the declared-charset,
  windows-1252 and email lists (any page named in the first two is recorded in the row's notes; any
  in the third is shown to the controller before the commit), `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-19.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-19-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-19-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
print('alias rows:', sum(row['audit_name'] not in half_a for row in rows))
"
```
  Expected: `missing: []`, `twice: []`, `from half B: []` and `alias rows: 5`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-19.tsv build/batch-19-half-a.tsv
git add plans/data/instrument-audit/batch-19.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 19's verification sheet, the saxophones" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The saxophones

**Files:**
- Modify: `saxophone_sound_alikes.py` (`SAXOPHONE_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with
  its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-19-half-a.tsv` (half A as committed), Task 1's tables, and
  `build/batch-19-code-check.py`.
- Produces: `SAXOPHONE_SOUND_ALIKE_PARENTS` and `SAXOPHONE_HELD_BACK` filled with this half's rows,
  which Task 5 extends. `NEW_SAXOPHONE_NAMES` stays empty (no SHIP).

If half A has no SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills only
`SAXOPHONE_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file only if it changed
(else no commit, and the report says so).

- [ ] **Step 1: Write the failing tests.** Fill `SAXOPHONE_SOUND_ALIKE_PARENTS` with one `name:
  parent` per SOUND_ALIKE row and `SAXOPHONE_HELD_BACK` with one `name: waits_for` per held row
  (every WAIT row whose reason is not `a sourced range`, and every `its target, <name>` row whose
  target is held), each in the sheet's order. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, in the sheet's order, with a docstring sentence for
  batch 19 (#88: batch 18 first left it out).

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or held_back or changes_its_parents" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the held-back
  and sound-change tests pass.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in
  `SAXOPHONE_SOUND_ALIKES`, in the sheet's order, under a section comment naming
  `plans/data/instrument-audit/batch-19.tsv` as `struck_sound_alikes.py`'s neighbours do ("---
  Batch 19's saxophones, in the order of …"), each a `CatalogEntry(name, title, Family.SAXOPHONES,
  lowest, highest, sounds_like=parent)`. Above each, put a comment with its `sound_source` and
  `range_source` URLs, the quoted passages (its reed and bore, its range and transposition) and the
  derivation. Each ALIAS row goes in `aliases.py` under a "Batch 19's saxophones" section, in the
  sheet's order, with its URL and quote. Comments name only committed files, and write any
  character ruff flags as its ASCII form, noted once in the section's header comment (Global
  Constraints).

- [ ] **Step 4: Run the suite and check the code against the sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry (the family is harmonic). A
  failure at a range end is a finding about the range or the build: check it against the source,
  and never trim the range to pass. Then run:
  `uv run python -I build/batch-19-code-check.py build/batch-19-half-a.tsv`
  Expected: `matches 19 rows`. Then rerun Task 1 Step 3's first command with its `order` assertion
  replaced by `names = set(instruments.names()); assert all(row[0] in names for row in before),
  'missing'`. Expected: `changed: []`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands and its suppression
  `grep` (which must print nothing), each on its own line, then `git add
  src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 19's saxophones, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The other conical single reeds sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared files,
alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-19-half-b.tsv`, half B's rows under the sheet's header, and
  its raw pages in `build/batch-19-pages/`
- Modify: `plans/data/instrument-audit/batch-19.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–9 and header, `build/batch-19-form-check.py`,
  `build/batch-19-quote-check.py`, `build/batch-19-half-b.txt`; `saxophones.md` (its "Rejected or
  corrected" lines for `maui xaphoon` and `xaphoon`, "Aliases"); `round-1/merged-missing.tsv` (the
  `xaphoon` and `maui xaphoon` rows); `batch-14.tsv` (the `tarogato`, `octavin`, `heckel clarina`,
  `heckelphone clarinet`, `sarune etek`, `xaphoon`, `maui xaphoon`, `pocket sax` and `xaphoon de
  catalunya` rows) and #84 (the `sarune etek` article).
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-19-half-b.txt`'s order, then one per alias name
of this half, in the plan's order. A parent or alias target is a catalog name or a SOUND_ALIKE row
of this half, never a half-A row. These rules apply on top of Task 2's:

- **Already decided.** `xaphoon`, `maui xaphoon`, `pocket sax` and `xaphoon de catalunya` are DROP
  under rule 5, their notes beginning "Already decided: batch-14.tsv WAIT" with that row's
  `waits_for` (`a sourced range` for `xaphoon`, `its target, xaphoon` for the other three) and
  family (clarinets), quoting #70's «so the saxophones batch must not decide them again». No page
  is fetched for them.
- **The hand-offs.** `tarogato`, `octavin`, `heckel clarina`, `heckelphone clarinet` and `sarune
  etek` quote their `batch-14.tsv` DROP in the notes, then are decided here: boundary ruling 1 (a
  single reed on a conical bore, from their own pages' words) or 2 (cylindrical), then the
  ambiguous ruling, then the range and sound-alike rulings.
  - `tarogato`: the ambiguous ruling first (the Tárogató page's modern single-reed instrument and
    the older one it was «intended to be a recreation of»; its infobox `names` do not outweigh the
    text). Its infobox «Written range: B♭3 to C6» has no `<ref>` and no transposition in that field
    (range rulings 2 and 10). Parent: «uses a single reed, like a [[clarinet]] or [[saxophone]]»
    compares the reed (no rule 1); rule 2 among the saxophones once ranged.
  - `octavin`: its infobox writes «hornbostel_sachs = 422.212» on the page; its «its [[conical
    bore]] has a smaller taper than that of a saxophone» is a bore trait for the sound-alike ruling
    only if the page states an effect on the sound.
  - `heckel clarina` («a [[Single-reed instrument|single reed]], conical [[bore (wind
    instruments)|bore]] instrument made of metal, resembling a [[soprano saxophone]]»: rule 1's
    `soprano saxophone`, if «resembling» relates the whole instrument) and `heckelphone clarinet`
    («essentially a wooden [[saxophone]] with wide conical bore … with [[clarinet]] fingering»: a
    material and a fingering are no trait; `saxophone` is no catalog entry, so rule 2), each with
    Heckel's or Dullat's words where reached.
  - `sarune etek`: its 2017 university journal article (#84: Danny Ivanno Ritonga, Bahas 28(2),
    Universitas Negeri Medan), which the controller accepted as scholarship in batch 14; its `hs`
    is `422.212` (Global Constraints' trap on `422.212.2`).
- **The alias names.** `pocket sax` and `xaphoon de catalunya` are above (already decided).

- [ ] **Step 1: Write half B's rows** to `build/batch-19-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-19-form-check.py build/batch-19-half-b.tsv` and
  `uv run python -I build/batch-19-quote-check.py build/batch-19-half-b.tsv`.
  Expected: `9 rows;` and the counts, then `bad: []`, exit 0; then the charset and email lists,
  `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-19-half-b.tsv >> plans/data/instrument-audit/batch-19.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `28 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-19.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-19-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-19-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted((half_a | half_b) - set(audit_names)))
print('twice:', sorted({name for name in half_a | half_b if audit_names.count(name) > 1}))
print('extra:', len(set(audit_names) - half_a - half_b))
print('names twice:', sorted({row['name'] for row in rows if [r['name'] for r in rows].count(row['name']) > 1}))
"
```
  Expected: `missing: []`, `twice: []`, `extra: 7` and `names twice: []`. The 7 are the alias rows'
  audit lines: half A's 5 and half B's 2.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-19.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 19's verification sheet, the other conical single reeds" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The other conical single reeds

**Files:**
- Modify: `saxophone_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-19.tsv`'s half-B rows, Task 3's tables, and `build/batch-19-code-check.py`.
- Produces: the finished family: `SAXOPHONE_SOUND_ALIKE_PARENTS` and `SAXOPHONE_HELD_BACK` with
  both halves' rows.

If half B has no SOUND_ALIKE or ALIAS row (likely: four of its nine rows are already decided),
skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to
  `SAXOPHONE_SOUND_ALIKE_PARENTS`, `SAXOPHONE_HELD_BACK` and the alias parameters, after half A's,
  as in Task 3 Step 1.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: sound-alikes after half
  A's sound-alikes, aliases after half A's aliases, under second section comments naming the sheet
  ("Batch 19's saxophones: the other conical single reeds").

- [ ] **Step 4: Run the suite and check the code against the whole sheet and the earlier builds.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`, then
  `uv run python -I build/batch-19-code-check.py plans/data/instrument-audit/batch-19.tsv`, then
  Task 3 Step 4's earlier-builds command.
  Expected: PASS, then `matches 28 rows`, then `changed: []`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands and its suppression
  `grep`, each on its own line, then `git add src/glitchygames/audio/instruments
  tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 19's other conical single reeds, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks, the expansion's close and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a saxophones
  paragraph with its count, naming `saxophones.py` and `saxophone_sound_alikes.py`, with examples,
  in the struck strings paragraph's form, saying that a saxophone is a single reed on a conical
  bore (Hornbostel–Sachs 422.212) while a cylindrical one is a clarinet, that a key, a size, a
  shape, a material, keywork or a maker is no trait, that a sound-alike gives its own sourced range
  (sounding, a written range only with its own source's transposition), and that a size below A0
  waits.
- Modify: `src/glitchygames/audio/instruments/saxophones.py`'s docstring: remove the ranges
  sentence's stale clause "folk instruments' are typical of the common keys" (no folk instrument has
  been in the module since batch 16 moved the free reeds out), and record the fix in #89.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `saxophones` row's
  count and examples, the sound-alike modules sentence and its total).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 19
  done, pointing at this plan and `batch-19.tsv`; "The later batches are not yet planned." replaced
  by "Every family the audits cover has had its batch (batches 1 to 19); the later passes over each
  family and the owner's checks are tracked in `plans/future-features.md` #70 and #71 to #89.") and
  the "Depends on" counts. The status word (DESIGN), the Goals, the "What the engine cannot make
  yet" table and the Decisions are not changed: they are the owner's (#89 asks).
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "EVERY FAMILY BATCHED (BATCH 19 DONE)", and the Description's running count
    gains batch 19;
  - batch 19 done, with the sheet's counts by status and the family's growth, the module move
    (`saxophones.py`, renamed from `winds.py`, which is gone), the boundary rulings,
    `SAXOPHONE_HELD_BACK`'s names, and the branch's base SHA (`6503a1e1`, batch 18's tip);
  - the audit's unclosed gaps and the out-of-scope names (the plan's list), as a later pass;
  - the hand-offs: `tarogato`, `octavin`, `heckel clarina`, `heckelphone clarinet` and `sarune
    etek` decided here (batch 14's DROPs); the four xaphoon rows left as `batch-14.tsv` decided
    them; each row dropped to clarinets, double reeds, free reeds, brass or electronic, for a later
    pass of that family; the alias names decided here (so no later batch decides `stritch`,
    `manzello`, `tubax in eb`, `curved soprano saxophone` or `sopranissimo saxophone` again);
  - **the closing summary** (the expansion's close), from Step 1's final audit output, never from
    memory: the catalog's growth from 431 instruments in 18 families to the final count in 23; the
    standing decision of every name across the 19 sheets, by status; the WAIT rows by reason, in
    three groups (`a sourced range`; `its target, …`; every other reason, each with its count and
    names), which is goal 4's "which instruments the engine cannot make yet, and what engine
    feature each needs"; the open hand-offs (standing DROPs that send a row to another family whose
    batch has passed), each for a later pass of that family; and the engine features the batches
    named beyond the spec's table (each #7x item's "Engine features named beyond the spec's table"
    line, #76 to #89, gathered and deduplicated), for the owner to rule into the spec's "What the
    engine cannot make yet";
  - a "Plan (batch 19)" line, and the Status line: "Batches 1 to 19 done; every family the audits
    cover has had its batch (requested by the owner 2026-11-06). Open: the later passes listed
    above, and the owner's checks #71 to #89." No "Next" batch is named.

  Add #89 (the highest item is #88), "Sound Engine: The Owner's Checks on Instrument Catalog Batch
  19 — TODO". Use #88's form, place it directly after #88, and give it the Priority "(before any
  later pass builds on the same catalog)". Its **Listen** section (`build/instruments/saxophones/`)
  covers the sound-alikes beside their parents, then the aliases. Its **Calls to confirm** are:
  - every WAIT, by reason, with names, and each row's "Engine limit, once ranged" note, and the
    range waits that will need a build of their own once ranged (outside `SAXOPHONE_HELD_BACK`);
  - the module move (`winds.py` renamed to `saxophones.py`, no re-export kept) and its `changed:
    []` record, answering #86's question;
  - the boundary rulings, each row they moved, and the Hornbostel–Sachs codes this plan checked
    (422.2, 422.21, 422.211, 422.212, 422.22, 422.3, 412.13, the suffixes 8 and 9, and -71 from
    `Template:Infobox saxophone` only), with the template trap and batch 14's `422.212.2`;
  - a saxophone as a sound-alike (keys, sizes, shapes, materials, keywork, makers and colour words
    no trait; no SHIP and no `sound_changes`; two pipes, a slide that replaces the keys and a stated
    bore or bell effect wait), and any row the SHIP ruling sent to the controller;
  - the parent ruling (the whole instrument's relation first, never a part's or a pitch's; else the
    nearest lowest note among the 8 saxophones, for every conical single reed), and each
    sound-alike's parent;
  - the range ruling (a written range only with its own source's transposition; a general rule,
    an image or a `<score>` chart no range; altissimo and optional keys extremes; the makers'
    ruling; a model's or period's page ranges that one only; a bare name of several sizes with none
    standard waits; below A0 waits), and every derived range, note by note;
  - the names-list, player's-name, ambiguous (past or present senses), one-off and unsourced rows,
    with the words "no fetched source describes it" on every row whose page was not found; versions
    not aliases;
  - `SAXOPHONE_HELD_BACK` and the sound-change guard, the helper test that exercises them on real
    builds both ways (batch 17's, not copied), and the wrong-table and broken-helper runs that
    showed each failing;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - any engine feature named beyond the spec's table;
  - **the expansion's close**: whether to mark the design's status DONE, whether to add the
    gathered engine features to the spec's "What the engine cannot make yet" table, whether to turn
    the final audit into a tracked test (#88's gap: no tracked test stops a WAIT or DROP name from
    being added later as an alias; only the untracked check scripts do), and the final audit's
    review list (the standing DROPs the code holds, with the controller's ruling on each).

  Then **Bugs to report** (found while building, none fixed here): the 8 earlier entries' missing
  per-entry source comments; any existing range or build a sheet's source contradicts (the leads in
  Global Constraints: `baritone saxophone`'s C2 against the B♭-keyed D♭2, the written-F6 tops
  against makers' F♯6); batch 14's `sarune etek` `hs` `422.212.2`, a subclass the fetched list does
  not hold; the 17 third-party `speech_recognition` DeprecationWarnings as #88 records them. Then
  **Follow-ups**: the audit's gaps; ranging the range WAITs from maker, museum and scholarly
  sources; checking the 8 earlier entries against sources; the engine changes that unblock the
  waits, most rows first (sub-audio fundamentals for the B♭ tubax and subcontrabass). Then
  **Incidents and process**, as #88 has them (the fetches that returned 404 or 429 and how each was
  handled, the redirects replaced by their targets, any page deleted or redacted for personal data
  and any institution's contacts kept, any load flake and its rerun), and the stale docstring
  clause Task 6 removed.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code and the sheets**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries()))"`,
  then `uv run python -I build/batch-19-form-check.py plans/data/instrument-audit/batch-19.tsv` for
  the sheet's counts, then `uv run python -I build/batch-19-final-audit.py` for the closing summary.
  Expected from the final audit: `bad: []`, exit 0; the standing names are 2023 plus this sheet's
  new names (2042 when every row keeps its planned name: 19 of the 28 names are new, and `tarogato`,
  `octavin`, `heckel clarina`, `heckelphone clarinet`, `sarune etek` and the four xaphoon names
  already stood in `batch-14.tsv`); ALIAS and SOUND_ALIKE equal the catalog's alias and sound-alike
  counts; the review list is the 8 from "Before the tasks" Step 6 plus any batch-19 name the code
  holds as a DROP (none expected). Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full suite.**
  Run: `uv run pytest --dummy-only -W default tests/audio tests/test_process_state_guard.py`, then
  `uv run pytest`, with nothing else running.
  Expected: PASS, 100% coverage; the only warnings are the 17 known `speech_recognition`
  DeprecationWarnings (#88; any other is a new finding, understood before going on). A failure in
  one of the two known load-flaky tests (Global Constraints) is rerun alone and then the whole suite
  once, and recorded in #89.

- [ ] **Step 4: Run the docs lint, on its own, after the suite has finished.**
  Run: `nox -s lint-docs`. Expected: the strict build passes.

- [ ] **Step 5: Run the remaining checks.**
```bash
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-19-code-check.py plans/data/instrument-audit/batch-19.tsv
uv run python -I build/batch-19-quote-check.py plans/data/instrument-audit/batch-19.tsv
uv run python -I build/batch-19-final-audit.py
git diff 6503a1e1 -- src tests | grep -n '^+.*\(noqa\|ruff: ignore\|type: ignore\|pyright: ignore\|pragma\)'
```
  Expected: everything passes; `matches 28 rows`; `bad: []` twice; and the `grep` prints nothing.
  The `build/instruments/saxophones` folder is the one to listen to; the owner judges the sound.

- [ ] **Step 6: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py src/glitchygames/audio/instruments/saxophones.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 19 of the instrument catalog (saxophones), its counts, the owner's checks and the expansion's close" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch in
turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78). The
pre-push hooks take about 40 minutes, and nothing in the working tree may change while they run.

**Order:** the controller's shared files (and the plan's commit), then Tasks 1, 2 and 4 in
parallel. Task 3 follows Tasks 1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows
Tasks 3 and 4, and Task 6 comes last.

**Corrections to batch 18's plan carried here:**
- Batch 18's form check accepted an ALIAS row whose target was any entry the code held when it ran
  (`| set(instruments.CATALOG)`), so a half-B alias of a half-A sound-alike passed once Task 3 had
  run, against the plan's "never a row of the other half". Here the target must be a pre-batch
  catalog entry or a SOUND_ALIKE row of the sheet.
- Batch 18's plan made the dulcimer names aliases from the Hammered dulcimer page's "Adaptations"
  list as a whole; the reviews then ruled it by sub-list (#88: the Sinosphere sub-list describes an
  instrument spreading, so versions; the cimbalom sub-list's heading is etymology, so names), and a
  name whose own page redirects to another catalog entry was dropped as ambiguous. Here the
  names-list ruling says so before any row is written.
- Batch 18's plan pointed its workers at the Berimbau infobox's `names` as the basis for aliases;
  the controller ruled that the page's own text («terms used for musical bow») outweighs them
  (#88's `urucungo`). Here an infobox's names never outweigh the page's text, and the Tárogató
  infobox's names are named as the case to check.
- Batch 18's plan said nothing about quoting in code comments; its aliases first carried ten `#
  ruff: ignore[...]` pragmas for en dashes (#88). Here a comment writes such characters as ASCII,
  noted once, no suppression is ever added, and Tasks 1, 3, 5 and 6 grep the diff for one.
- Batch 18's plan had a worker tell the controller about personal data on a page; a worker deleted
  the page instead (#88). Here either is allowed (the worker deletes it, or the controller redacts
  it), no row quotes it, and an institution's or company's public contacts stay.
- Batch 18's plan replaced redirects by their targets only in practice (#88's incidents). Here the
  rule is written, the redirects this family has are named, and the quote check refuses a saved
  redirect.
- Batch 18's brief to the controller misstated a hand-off («batch 15 sent dulcimers here», #88).
  Here the hand-offs come from the commands and the sheet rows quoted in the Spec line, each with
  its sheet and status.
- Batch 18's #70 bullet named the next batch; this is the last, so no next batch is named, and Task
  6 closes the expansion with a final audit of all 19 sheets against the code, the closing summary
  and the design's status line, leaving the design's status word and tables to the owner.
- Batch 18's family was not in `HARMONIC_FAMILIES`, so its plan expected only the render test; the
  saxophones are, so Tasks 3 and 5 expect the pitch test as well.
