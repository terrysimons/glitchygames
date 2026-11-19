# Instrument catalog batch 15 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the keyboard family from the audits' candidates. The family holds the acoustic
instruments sounded from a keyboard: the pianos (struck strings, hand-played or self-playing), the
harpsichords, spinets and virginals (plucked strings), the clavichords (strings struck by
tangents), and the keyboard idiophones (the celesta, the toy piano and their kin: bars, forks or
glass struck through a key action). Each instrument gets a cited source for its name, its sound,
how its keys sound it, its range and (for a harpsichord register) its choirs, and either sounds
unlike every other entry or is a listed sound-alike of the one it sounds like. The rest become
aliases, wait for an engine feature or a source, or are dropped with a reason.

**Architecture:** As in batches 3 to 14, a verification sheet (`batch-15.tsv`) decides every
candidate before any code is written. The family's 11 entries live in `keyboards.py` (365 lines),
which also holds the 11 electromechanical entries; batch 13 already moved the organs out. So the
electromechanical section moves unchanged to a new `electromechanical.py`, and `keyboards.py`
keeps the keyboards: its table becomes `_KEYBOARD_BUILDS`, and `KEYBOARDS` becomes
`_KEYBOARD_BUILDS + KEYBOARD_SOUND_ALIKES`, with the sound-alikes in a new
`keyboard_sound_alikes.py`. The catalog's keyboard builders (`_piano`, `_harpsichord`,
`_celesta`, `_toy_piano`) already make struck and plucked strings and struck bars, so a new
keyboard with no other cited trait is a sound-alike. A SHIP is possible only for a cited trait the
engine can make that no keyboard build has, with its numbers sourced: a 16' choir on a harpsichord
(`_harpsichord`'s new `sixteen_foot`, a `Course` an octave down) or a struck body's sourced
partial ratios (a new `_keyed_idiophone`). A self-playing keyboard carries `Tag.MECHANICAL` (batch
13's tag rule). A new guard, `KEYBOARD_HELD_BACK`, holds every name the sheet holds back for any
reason but a sourced range. The sheet and the code each come in two halves, as explicit lists:
the pianos (struck-string keyboards), then the harpsichords, clavichords, keyboard idiophones and
the boundary names. The controller writes the names file, the candidate lists and the three check
scripts before anything is dispatched, so the two sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `plucked`, `plucked_series`,
`Course`, `struck`, `Partial`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all, and 7 for `Tag.MECHANICAL`). Batch 14's plan
(`plans/2026-11-12-instrument-catalog-batch-14-implementation.md`) and its owner's checks
(`plans/future-features.md` #84) are this plan's template and its ledger: its controller step, its
quote check on the raw page text, its held-back guard, its two parallel halves and its code check
carry over, with the controller's fix to its form check (#84, "Incidents and process":
Hornbostel–Sachs has no 422.221 or 422.222). Batch 13's plan holds the footage ruling (a choir
sounds at its footage against its keys, and its sounding span must lie in A0–C8) and the
mechanical tag rule; batch 11's plan holds the transposition rule and the balaban rule (a cited
trait the build cannot make means the row waits); batch 4's plan
(`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) holds the pitched sound-alike
and strict range rules and the before-and-after build record. This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-15-implementation.md`. The branch is
`feat/instrument-catalog-batch-15`, made from `feat/instrument-catalog-batch-14` at its HEAD,
`982a66a7` (batch 14's final review fixes); Task 6 records that SHA in #70. The candidates come
from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `keyboard` (40, every one from the round-2 audit
  `keyboards.md`);
- the `round-1/merged-missing.tsv` rows whose `family` contains `keyboard` (17: 14 with family
  `keyboards` or "keyboards (or new family: tape keyboards)", and `shahi baaja`, `bulbul tarang`
  and `taishogoto` with "new family: keyboard zithers");
- the five piano rows of the mechanical-instruments audit (`merged.tsv`, `audit_file`
  `new_mechanical_instruments.md`, whose family is a tag): `barrel piano`, `laterna`,
  `nickelodeon`, `photoplayer` and `piano melodico`. Each "sounds like an existing family"
  (spec, Families), the piano's, and no earlier sheet decided them, as batch 7 took the violano
  rows and batch 13 the `flute clock` and `componium`. The audit's other mechanical rows are other
  families' (the music boxes plucked idiophones', the `singing bird box` a whistle's, the
  `mechanical carillon` tuned percussion's, the `orchestrelle` free reeds') and are not rows here.

Together: 55 unique names (`orphica`, `pedal piano`, `clavicymbalum`, `mellotron`, `chamberlin`,
`optigan` and `luthéal` are in both audits). Three are already catalog names or aliases from
batch 2 (`hohner pianet`, an entry; `hohner clavinet` and `wurlitzer electronic piano`, aliases)
and are not candidates. That leaves **52 candidate names** (counted for this plan, the controller
recounts). One is not a valid catalog name as written: `luthéal`, whose row is named `lutheal`
(its `audit_name` keeps the accent). The audits' alias lines that name a keyboard candidate, or a
keyboard the catalog holds, propose **18 alias names** that are not candidates:
- `keyboards.md`: "pianola, reproducing piano -> player piano"; "cabinet/cottage/pyramid/lyre
  piano -> upright piano or giraffe piano (memory, not verified)" (`cabinet piano`, `cottage
  piano`, `pyramid piano`, `lyre piano`); "janko piano, pleyel double piano, vis a vis piano ->
  grand piano" (`pleyel double piano`, `vis a vis piano`); "fender rhodes -> tine electric piano
  (catalog)"; "muselar -> virginal (page names it only in passing)".
- `new-mechanical-instruments.md`: "pianola, reproducing piano, Welte-Mignon, Ampico, Duo-Art,
  Disklavier -> player piano" (`welte mignon`, `ampico`, `duo art`, `disklavier`; `pianola` and
  `reproducing piano` are already on the `keyboards.md` line); "roller piano, street piano, piano
  organ(?) -> barrel piano" (`roller piano`, `street piano`, `piano organ`); "laterna, rhombia ->
  barrel piano" (`rhombia`).
The other `keyboards.md` alias lines name only candidates (`spinet`, `clavicymbalum`,
`lautenwerck`, `geigenwerk`, `janko piano`, `chekker`), decided by their own rows (rule 8), or
names the catalog already holds (`hohner pianet`, `hohner clavinet`, `wurlitzer electronic
piano`). The round-1 alias tables are not used, as no earlier batch used them. So the sheet will
hold **70 rows**. An alias row's `audit_name` is the first audit line naming it, `keyboards.md`
before `new-mechanical-instruments.md`.

The hand-offs from earlier sheets (checked: `batch-1.tsv` to `batch-14.tsv`, and
`plans/future-features.md` #70–#84):
- `claviharp`: `batch-4.tsv` DROP, "A quill-plucked keyboard instrument: keyboards (Global
  Constraints: quill keyboards belong to keyboards)". A half-B candidate, decided here.
- `dolceola`: `batch-4.tsv` DROP, "Its strings are struck from a piano keyboard: keyboards, with
  the piano". A half-A candidate, decided here.
- Already decided, and each a candidate: its row is DROP, its notes beginning "Already decided:"
  and naming the sheet and status that decided it (the earliest sheet that decided it, not a later
  sheet's "already decided" drop):
  - half A: `rhodes celeste` and `rhodes piano bass` (`batch-2.tsv` DROP, the tine electric
    piano's register), `yamaha cp electric grand` (`batch-2.tsv` WAIT, a sourced range);
  - half B: `chamberlin` (`batch-2.tsv` WAIT, sample playback and a sourced range), `mellotron`
    (`batch-2.tsv` WAIT, sample playback), `optigan` (`batch-2.tsv` WAIT, sample playback and a
    sourced range), `bulbul tarang` and `taishogoto` (`batch-4.tsv` WAIT, a sourced range, plucked
    strings), `geigenwerk` (`batch-7.tsv` WAIT, a sourced range) and `viola organista`
    (`batch-7.tsv` WAIT, its own build: #70 "the keyboards batch must not decide it again"),
    `orchestrion` and `panharmonicon` (`batch-13.tsv` WAIT, a sourced range: #70 "the keyboards
    and free reeds batches must not decide them again").
  None was a catalog name or alias before the batch, so the code check's "Already decided" branch
  does not apply to them (they take its last branch: neither a catalog name nor an alias).
- Already decided, not handed, and not candidates: `gameleste` (`batch-5.tsv` DROP, "Keyboards
  and a one-off"; the one-off stands), `zimbelstern` (`batch-5.tsv` WAIT, an organ accessory),
  `reed organ` (`batch-13.tsv` DROP to free reeds). No row is added for them.
- #84 says "no name the sheets found belongs to the keyboards batch", and #76–#83 hand nothing
  here beyond the lines above.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, hyphens and footage marks go only in the title (`lutheal`
  titled "Luthéal", `harpsichord sixteen foot` titled with "16'" as its source writes it). A
  candidate keeps its audit name (the naming ruling of batch 12), accents removed.
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families),
  "with the existing player-facing splits kept where they already exist (keyboards and organs …)".
  The keyboard family holds acoustic instruments whose keyboard sounds them: chordophones whose
  strings a key action strikes or plucks, and idiophones whose bars, forks or glass a key action
  strikes (the catalog's `celesta` and `toy piano`). The boundary rulings below decide each row.
- Hornbostel–Sachs, every code this plan relies on checked against Wikipedia's lists on
  2026-11-13 (raw wikitext of `List_of_chordophones_by_Hornbostel–Sachs_number`,
  `List_of_idiophones_by_Hornbostel–Sachs_number` and `Hornbostel–Sachs`):
  - 314.122 is a real class, "With resonator box - the piano is part of this subdivision"; the
    chordophone suffixes are "4: Hammers or beaters", "5: Bare hands and fingers", "6: Plectrum",
    "7: Bowing", "8: Keyboard", "9: Using a mechanical drive"; the main page: "An 8 indicates
    that the instrument has a keyboard attached, while a 9 indicates the instrument is
    mechanically driven". The Piano infobox gives 314.122-4-8 ("Simple chordophone with keyboard
    sounded by hammers"), the Clavichord infobox 314.122-4-8 ("sounded by tangents"); the
    Harpsichord page gives no code, so a harpsichord's 314.122-6-8 is written from a quoted
    sentence naming its plectra and keyboard. The Hammered dulcimer infobox gives 314.122-4: no
    keyboard.
  - 111.212 "Sets of percussion sticks" (the list names the Glasschord there) and 111.222 "Sets of
    percussion plaques" are real classes; the Celesta and Glockenspiel infoboxes give 111.222.
  - 412.132 "Sets of free reeds – Accordion, harmonica, and reed pipes of the pipe organ" is real;
    the Accordion infobox gives it.
  A worker who finds a code that a fetched list does not hold reports it to the controller before
  any row relies on it. No other code is assumed.
- "Every name, range and description checked against a source cited in the code … A range that no
  source gives is the instrument's documented playable span from a maker or museum, or the entry
  waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict"). This
  plan's range ruling is below. A row with no sourced range is WAIT, `waits_for` `a sourced range`,
  and the range is checked first, before any engine limit or other trait (batch 13's reversals: a
  row with neither a range nor a buildable trait waits for the range, its notes keeping "Engine
  limit, once ranged: …").
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry, sharing
  the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the same
  instrument) stays an alias." "So `sound_changes` (keyword overrides of the parent's builder,
  empty by default) lets a sound-alike differ by a sourced trait." A sound-alike is pitched exactly
  when its parent is, and a pitched sound-alike gives its own sourced range (batch 4). The only
  `sound_changes` this batch may carry is `{'sixteen_foot': True}` (the choir ruling).
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as an
  approximation, under its real name or a qualified one. The spec's table binds this family through
  "sample playback | Mellotron, Chamberlin, Optigan" (decided by batch 2), "more than four
  sources | orchestrion, violano-virtuoso" and "sub-audio fundamentals". Earlier batches added the
  other names a WAIT may give: a pitch LFO (vibrato), a pitch LFO (portamento between notes), an
  amplitude LFO, a pitch and amplitude LFO (batch 2), filter resonance, a filter envelope, moving
  formants (batch 6); a buzzing membrane (batch 5); a sourced drone tuning and its own build (batch
  7); a range above C8 (batch 10); a sourced detune and a sourced footage (batch 13); a sourced
  reed and bore (batch 14). This plan adds one source wait, `a sourced partial series` (the keyed
  idiophone ruling). What the engine has: up to four `Source`s, each with its own semitones,
  detune and fixed pitch; `plucked` (a harmonic series, a ring, `Course`s at their own semitones,
  cents and level, a pick noise, a low pass); `struck` (one to four `Partial`s at their own ratios,
  three with a mallet noise, each ringing down); one glide per note (`pitch_curve`); a fixed FIR
  low or high pass; no LFO of any kind.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not builds.
- Reuse the family's builders under their current names: `_piano(*, ring_seconds, low_pass,
  cents, slope=6.0, hammer=0.03)`, `_harpsichord(*, low_pass, octave_rank)`, `_celesta(*,
  ring_seconds)`, `_toy_piano()`. Each entry's build is an inline `partial(...)`. Add a builder or
  keyword only for a genuinely new, sourced sound (`_harpsichord`'s `sixteen_foot`,
  `_keyed_idiophone`, below), and give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the sheet
  is verbatim from a page the worker fetched and saved, and every `Range:`, `Footage:` and
  `Partials:` passage is checked against the raw saved page (the quote check). No request carries
  the owner's email or any personal data, in a header, a URL or a payload (#78, "Incidents and
  process").
- Code comments name committed files (`plans/data/instrument-audit/batch-15.tsv`), never the
  gitignored `build/` files (batch 9's fix).
- Data is never evaluated as code: a check script reads a literal with `ast.literal_eval`, never
  `eval` or `exec`.
- The 11 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 11. An existing entry changes only for a cited bug, and not in this batch:
  the 11 carry no source comment, so a range or build that a fetched source contradicts is reported
  in #85 for the owner, not changed here (batches 10 to 14's rule). Leads already seen while
  writing this plan, for the workers who fetch those pages to check under range ruling 10: the
  Harpsichord page's compass paragraph ("The traditional pitch range for a 5-octave instrument is
  F1–F6 (FF–f‴)") carries no citation in its paragraph; the Celesta infobox's range is "C3 – F8"
  against the catalog's C4–C8; the Harpsichord page's cited Grove entry is titled "Buff stop [harp
  stop and (erroneously) lute stop]", while the catalog's `harpsichord lute stop` is built muted
  (a 3.5 kHz low pass). Task 1's before-and-after record of every entry checks that the move
  changes nothing.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns, a module docstring's first line included: batch 14's first line
  was 123 columns), basedpyright and ty clean, 100% coverage. "I don't like short abbreviated
  variables." "explicit is better than implicit." "Whenever you see warnings thrown by a test, you
  should understand why it's happening and be concerned": a warning is a finding, and it must be
  understood before going on.
- Commits as batches 4 to 14: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this plan,
  never from memory. Write no `.md` file beyond those Task 6 names. Never use `git stash`: the
  stack is shared with other worktrees and sessions (#80, "Incidents and process"). Set work aside
  with a temporary commit instead.

## Review Focus

1. **A key count or a width read as a range.** Keyboard pages give "88 keys", "61 notes", "five
   octaves", "~6 octaves by the 1820s", "36 keys per octave" or "a range of just over five
   octaves", and the audit filled `A0`–`C8` "from memory" for five pianos. Range ruling 5 makes a
   count or width no range (unless a stated lowest note fixes it, ruling 1), the form check needs
   `Range:` with a quoted passage the quote check finds on the saved page, and the code check
   compares every shipped range with the sheet.
2. **A written range read as sounding.** The celesta "sounds one octave higher than the written
   pitch" (its page), and the audit's dulcitone is "written AA-a3, sounds octave higher". Range
   ruling 2 takes a keyboard idiophone's written range only with its stated transposition and
   shows the arithmetic; a string keyboard's compass at 8' is sounding as given.
3. **A choir pushed out of the catalog's span.** A 16' choir sounds an octave below its keys (the
   Harpsichord page), so on the five-octave F1–F6 keys it would sound F0, below A0; a 4' choir on
   a high compass can pass C8. The choir ruling ranges a register by its keys, the form check
   shifts the lowest key by the lowest choir and the highest key by the highest before holding
   both inside A0–C8, and `test_a_sixteen_foot_harpsichord_sounds_its_lower_choir` pins the built
   choir.
4. **A construction, a layout or a tuning shipped as a new sound, or one instrument shipped
   twice.** A square, giraffe, upright or grand case, a Jankó keyboard, a second manual, pedals,
   a quarter-tone or 36-to-the-octave tuning, a shoulder strap or a roll player are no trait
   (rule 7, the scale ruling); `janko piano`, `quarter tone piano`, `archicembalo`, `pedal
   piano`, `orphica`, `player piano` and their kin are sound-alikes or waits, never SHIPs;
   `lautenwerk` and `lautenwerck`, `player piano` and its six alias names, `barrel piano`, `laterna`
   and their alias names are decided once each. `test_no_new_build_is_another_entrys_instrument`
   refuses a new build equal to an existing one, and the code check finds every name exactly once.
5. **A keyboard idiophone built from made-up partials, or a self-playing keyboard left
   untagged.** A tuning fork's or a glass bar's partials are not the celesta's: the keyed
   idiophone ruling ships `_keyed_idiophone` only with ratios its source states, the form check
   refuses ratios within 2% of an existing build's, and `test_a_keyed_idiophone_sounds_its_sourced_partials`
   pins them. A self-playing piano carries `Tag.MECHANICAL` (`test_the_mechanical_keyboards_are_tagged`),
   and one that also plays drums or a mandolin attachment waits for more than four sources.

---

## File Structure

- Create `src/glitchygames/audio/instruments/electromechanical.py`. It takes the
  "Electromechanical" section of `keyboards.py` (its header comment, `_tine_piano`,
  `_reed_piano`, `_pianet`, `_clavinet`, `_tonewheel_with_percussion` and `ELECTROMECHANICAL`),
  unchanged.
- Modify `src/glitchygames/audio/instruments/keyboards.py`: it keeps the "Keyboards" section, its
  tuple renamed `_KEYBOARD_BUILDS`, and `KEYBOARDS = _KEYBOARD_BUILDS + KEYBOARD_SOUND_ALIKES`.
  New builds go after the 11; `_keyed_idiophone` and `_harpsichord`'s `sixteen_foot` are added
  only when a row needs them.
- Create `src/glitchygames/audio/instruments/keyboard_sound_alikes.py`, holding
  `KEYBOARD_SOUND_ALIKES`.
- Modify `registry.py` (it imports `KEYBOARDS` from `keyboards.py` and `ELECTROMECHANICAL` from
  `electromechanical.py`; their places in `FAMILY_TABLES` don't change), the docstrings that name
  `keyboards.py` as the electromechanical instruments' home (`organs.py` line 9, `electronic.py`
  line 5, `__init__.py` line 137), and `aliases.py` (the batch's ALIAS rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5). `tests/test_process_state_guard.py`
  lists nothing of `keyboards.py` today, so it is not touched.
- Create `plans/data/instrument-audit/batch-15.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #85), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #85):

- **The electromechanical instruments get their own module, and the keyboards keep theirs.**
  `keyboards.py` holds two families; every family a batch has grown since batch 4 has a module of
  its own and a sibling sound-alikes module that names it ("The family's builds are in …"). The
  family being grown here is the keyboards, so the other family leaves, as batches 9 to 14 moved
  theirs out of a shared module. The electromechanical section is self-contained: only
  `registry.py` imports `ELECTROMECHANICAL` (checked with grep), no other module imports its
  builders, and the process-state guard lists nothing of it. The two sections share imports only
  (`partial`, `Final`, `CatalogEntry`, `Family`, `Instrument`); each module takes the ones it
  uses. Task 1's before-and-after record of all 704 builds checks the move.
- **The boundary rulings.** A row's family is decided by what sounds and what sounds it, from its
  fetched source's words, with the Hornbostel–Sachs class those words imply:
  1. *Pianos*: strings struck by hammers from a keyboard (314.122-4-8; -9 for a self-playing one,
     which also carries `tags` `mechanical`) are this family's, whatever the case (grand,
     upright, square, giraffe, pyramid), the keyboard's layout (Jankó, double manual) or the
     tuning. `dolceola` (batch 4's hand-off) and `dulce melos`, keyed zithers whose strings the
     keys strike, are pianos by this rule.
  2. *Harpsichords*: strings plucked by plectra or quills from a keyboard (314.122-6-8) are this
     family's: harpsichords, spinets, virginals, the clavicytherium, the lautenwerk, the
     archicembalo and `claviharp` (batch 4: "quill keyboards belong to keyboards").
  3. *Clavichords*: strings struck by tangents from a keyboard (314.122-4-8, the Clavichord
     infobox) are this family's.
  4. *Keyboard idiophones*: bars, plates, forks or glass struck by hammers from a keyboard
     (111.212 or 111.222 with a keyboard) are this family's, as the `celesta` and `toy piano` are:
     `dulcitone`, `typophone`, `glasschord`, `keyed glockenspiel`.
  5. *Struck strings without a keyboard*: the dulcimers (314.122-4, beaters in the player's hands)
     are struck strings, batch 18's. A row whose source gives hand-held beaters is DROP "belongs to
     struck strings (H-S 314.122-4): <its words>", listed in #70 for that batch.
  6. *Plucked strings and harps without a keyboard*: keys that only stop the strings while the
     player plucks them by hand or plectrum (the keyboard zithers: `shahi baaja`, and `bulbul
     tarang` and `taishogoto`, which batch 4 decided) are plucked strings; a harp is batch 17's.
     DROP "belongs to plucked strings (H-S 314.122-5 or -6, keys stopping the strings): <its
     words>" or "belongs to harps (H-S 322): <its words>", listed in #70.
  7. *Free reeds*: a keyboard sounding free reeds (the accordion, the harmonium, the reed organ;
     412.132) is DROP "belongs to free reeds (H-S 412.132): <its words>", batch 16's, listed in #70.
  8. *Electric and electronic*: a mechanical vibration read electrically (H-S 51 and 52) is
     electromechanical, a circuit's sound (H-S 53) electronic; both batches are done, so the row is
     DROP "belongs to electromechanical" or "belongs to electronic", listed in #70 for a later pass
     (`scalatron`, as its page decides). Tape and optical replay keyboards were decided by batch 2.
  9. *Bowed and self-playing ensembles*: bowed keyboards were decided by batch 7, the orchestrion
     and panharmonicon by batch 13 ("Already decided").
  10. *Silent*: a keyboard whose source says it makes no sound (the audit's `clavier a lumieres`,
      "projected colored lights") is DROP "makes no sound: <its words>".
  11. *The `hs` cell* holds the class a fetched source gives (an infobox, or a sentence naming what
      the keys sound and how, quoted, with the code it implies, written from the classes and
      suffixes above), else `none`. A SHIP or SOUND_ALIKE row's `hs` fullmatches
      `(314\.122|111\.2[12]2)(-[0-9]+)*`.
- **A keyboard is a sound-alike unless a cited trait sets it apart.** The catalog's keyboard builds
  are `_piano` (hammered strings: ring, low pass, unison detune in cents, slope, hammer noise),
  `_harpsichord` (plucked strings, an optional 4' choir), `_celesta` (a struck bar's fundamental
  and 4x partial) and `_toy_piano` (struck rods). A row whose sources name no other trait is a
  SOUND_ALIKE (the parent ruling). A case, a keyboard layout, a second manual, pedals, a tuning or
  scale, a size, a material, a maker, a roll or barrel mechanism, or a colour word ("bright",
  "tinny", "mellow", "plucky", "jangly") is no trait (rule 7), unless a fetched source names an
  effect on the sound with the numbers a builder takes. A trait the engine can make with sourced
  numbers (a 16' choir, a struck body's partial ratios) is a SHIP under the next two rulings; a
  trait it cannot (metal tacks striking the strings, objects between the strings, a luthéal's
  cimbalom register, an octave coupler sounding a second piano note, a mandolin attachment, a
  hammer's buzz) is WAIT `its own build (<the trait>)` or the spec's or an earlier batch's feature
  name, with the source quoted. A trait `_piano` could imitate by turning an unsourced keyword
  (a brighter `low_pass`, a louder `hammer`, a wider `cents`) is not made by the build: batch 11's
  contraforte and the balaban rule.
- **The parent ruling.** A SOUND_ALIKE's parent is a catalog entry from before the batch (never a
  sound-alike) or a SHIP row of its half, never one of `APPROXIMATING_NAMES`:
  1. The entry its own source relates it to ("a smaller type of harpsichord", "an upright
     fortepiano", "a glockenspiel with a keyboard"), quoted in the notes after "Parent (rule 1):".
     Only this rule may name another family's entry (the catalog holds eight cross-family
     sound-alikes from batches 3 and 6, such as `electronic cowbell` of `cowbell`).
  2. Otherwise the keyboard entry of the same mechanism (hammered strings: `grand piano`,
     `upright piano`, `fortepiano`, `clavichord` for tangents; plucked: `harpsichord`,
     `harpsichord lute stop`, `virginal`; struck bars: `celesta`, `toy piano`) whose `lowest` note
     is nearest the row's own lowest note in semitones, the earlier catalog entry on a tie, written
     after "Parent (rule 2):". `bright grand piano` and `honky tonk piano` (a colouring and a
     detuned tuning, both sound design) are parents only by rule 1.
  3. A sound-alike's choirs follow the choir ruling (its footage equals its parent's, or adds a
     16' choir to a `_harpsichord` parent).
  4. The sizes or models of one type share the type's parent, or are sound-alikes of the type when
     it is a SHIP row: never a sound-alike's sound-alike.
- **The choir ruling** (batch 13's footage ruling, for a harpsichord). A harpsichord's choirs
  sound at their footage against its keys: "Strings at eight-foot pitch (8') sound at the normal
  expected pitch; strings at four-foot pitch (4') sound an octave higher. Harpsichords occasionally
  include a sixteen-foot (16') choir (one octave lower than eight-foot) or a two-foot (2') choir"
  (the Harpsichord page, its paragraph to be checked for a citation under ruling 10). So:
  1. The `footage` cell names the row's choirs as a fetched source gives them, lowest-pitched first
     (`16 + 8`, `8 + 4`, `8`), or `none` when its source names none (every piano, clavichord and
     keyboard idiophone, and a plucked keyboard whose source names none). `footage_source` holds the
     URL, and `notes` quote it after `Footage:`. The catalog's own choirs, as built: `harpsichord`
     `8 + 4` (`octave_rank=True`), `harpsichord lute stop` and `virginal` `8`.
  2. A row's range is its keys (its 8' compass). Its sounding span runs from its lowest key shifted
     by its lowest choir (16': down 12 semitones) to its highest key shifted by its highest (4': up
     12), and must lie inside A0–C8: below, WAIT `sub-audio fundamentals`; above, WAIT `a range
     above C8`.
  3. Choirs `_harpsichord` cannot add (a 2' choir, a 16' choir without the 8') make the row WAIT
     `its own build (<the choirs>)`. Three choirs (16' + 8' + 4') are three `Course`-sounded
     strings plus the pick: within four sources.
  4. A row whose choirs add a 16' to a `_harpsichord` parent's choirs is a SOUND_ALIKE with
     `sound_changes={'sixteen_foot': True}` (decision 8's "change their details", as batch 13's
     `bourdon`); a row whose choirs add a 16' to no catalog harpsichord's is a SHIP. The first code
     task that needs it adds `sixteen_foot: bool = False` to `_harpsichord`, giving `Course(
     semitones=-12.0, cents=-1.0, level=0.45)` when true: the 4' choir's level and the mirror of its
     1-cent offset, sound design copied from `_harpsichord`'s octave rank, marked so. No existing
     build changes (the default adds nothing). That task adds the entry to
     `KEYBOARD_SIXTEEN_FOOT_NAMES`, whose notes repeat every two periods of the key, as
     `SIXTEEN_FOOT_ORGANS`' do.
  5. A sound-alike whose choirs differ from its parent's in any other way has the wrong parent:
     the parent ruling picks the catalog entry with its choirs, or the row waits.
- **The keyed idiophone ruling.** A keyboard idiophone's sound is its struck body's partials,
  which differ by body (a bar's, a fork's, a glass bar's). So:
  1. A row whose source states its body's partial ratios (as multiples of the fundamental, or as
     pitches whose interval to the fundamental the source fixes) SHIPs
     `_keyed_idiophone(ratios=(1.0, …))` with those ratios, quoted after `Partials:` in `notes`.
     At most three ratios, the fundamental first and ascending (`struck` takes three partials with
     a mallet), in the order the source lists them; a source giving more keeps its first three.
  2. A body whose source says it sounds only its fundamental ("a pure tone", "nearly a sine") ships
     `ratios=(1.0,)` only when the source says so in those terms.
  3. Ratios within 2% of an existing build's, one by one (`celesta` 1.0 and 4.0; `toy piano` 1.0,
     2.76 and 5.40; a SHIP row above it), are no trait (a 1–2% numeric difference is not a trait):
     the row is a SOUND_ALIKE of that build.
  4. A body whose partials no source states WAITs `a sourced partial series` (a source wait this
     plan adds), once ranged. A body the source calls by its material alone ("glass", "steel
     forks") states no partials.
  5. The highest ratio times the row's highest note stays under 22050 Hz (the celesta's "under
     Nyquist at C8" comment), else WAIT `a range above C8`.
  6. The first code task that ships one adds, in `keyboards.py`,
     `_keyed_idiophone(*, ratios: tuple[float, ...]) -> Instrument`, returning
     `struck(tuple(Partial(ratio=ratio, level=1.0 if ratio == 1.0 else 0.2, ring_seconds=1.5 / ratio) for ratio in ratios), release=0.75, mallet=0.02)`:
     the levels, the 1.5 s ring divided by the ratio, the 0.75 s release and the 0.02 mallet copied
     from `_celesta(ring_seconds=1.5)`, sound design, marked so. That task adds the entry to
     `KEYBOARD_PARTIAL_RATIOS` and, for an inharmonic ratio, to `NOT_PERIODIC_AT_THE_NOTE` ("a
     struck <body>: partials at <ratios>").
- **The mechanical ruling** (batch 13's tag rule). A keyboard that plays itself from a roll,
  barrel, book or disc carries `tags` `mechanical` (H-S suffix -9). It is decided as the keyboard it
  sounds as: a self-playing piano is a sound-alike of a catalog piano under the parent ruling, with
  its own sourced range. One whose source adds other instruments to the piano (drums, effects, a
  mandolin attachment, pipes) WAITs `more than four sources` once ranged (the spec's table:
  "orchestrion"). The first code task that ships one adds it to `MECHANICAL_KEYBOARD_NAMES` and to
  the list in `test_plucked_idiophones_hold_the_lamellophones_and_music_boxes` (its comment: "This
  lists every mechanical entry, so it grows when another entry is tagged mechanical"), in catalog
  order.
- **Range ruling for keyboards.** A sourced range is the lowest and highest sounding notes that
  one fetched source states for the instrument:
  1. *Stated, by one source*: both notes as the range or compass, from one source (batch 14's
     `xaphoon`: two sources for one range is no range), in note names with octaves (scientific
     `F1`; Helmholtz `FF` or `f‴`, whose octave marks fix the octave, as #84 confirms; a named note
     whose octave the source fixes), or the lowest note and an exact span or key count above it
     ("61 keys from F1"), as batch 7 allowed.
  2. *Sounding*: a string keyboard's compass at 8' is sounding as given (its keys sound the notes
     they name; its choirs follow the choir ruling). A keyboard idiophone's compass counts only
     with the transposition its own source states ("sounds one octave higher than the written
     pitch"), the derivation showing the arithmetic; a range the source calls sounding counts as
     given. Otherwise the row WAITs.
  3. *Extensions and extremes*: the stated compass, and nothing beyond it. Extra keys some models
     have ("later models had 60 keys", "some instruments extend to"), a short octave's notes, or a
     note in parentheses are extremes: the range is the compass without them, or the row WAITs.
  4. *Several sizes, models or periods*: the one its source calls standard, usual, most common or
     traditional for the bare name, from that source; or a maker's or museum's page for one model
     or object, which ranges a row named for that model only. A bare type name is not ranged from
     one of its sizes unless a source calls that size the standard (batch 14's `birbyne`). A source
     giving one instrument two ranges has given none. With neither, the row WAITs (batch 7's rule).
  5. *Not a range*: a hedged span ("about", "approximately", "roughly", "typically", "usually",
     "can reach", "up to"), a generalisation about a class ("all harpsichords", "most pianos"), a
     width or count with no pitch ("88 keys", "five octaves", "~6 octaves", "just over five
     octaves", "36 keys per octave", "41 notes"), note letters with no octaves ("low E to high B"),
     a tessitura, or one pitch. The audit's ranges are leads, not sources (five of them are "from
     memory").
  6. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached); a
     maker's catalogue or model page (Steinway, Yamaha, Bösendorfer, Fazioli, Schiedmayer and
     Mustel for celestas, the modern harpsichord and clavichord makers' own sites); a museum's
     object record (MIMO, the Met, the Smithsonian, the Musée de la musique, the Edinburgh
     University Collection (MIMEd) and its Russell Collection, the Royal College of Music Museum,
     the Musikinstrumenten-Museum Berlin, the Germanisches Nationalmuseum, the Cobbe Collection,
     the National Music Museum); or a conservatory or orchestration reference (the Vienna Symphonic
     Library's instrument pages). A museum's or maker's page outranks an uncited Wikipedia line, and
     when they disagree the museum or maker decides (batch 11's lesson). A retailer's listing, a
     blog, a forum, an auction listing or a hobbyist's page is not a source. A list or category
     page is a source for a name only. A range is never taken from a sibling, the parent, a related
     instrument ("like a piano's"), the audit or memory.
  7. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`) and nothing above C8
     (WAIT `a range above C8`), for the keys and for the choirs' sounding span (the choir ruling).
  8. *One note*: an instrument whose source gives it one note has no range. It WAITs `a sourced
     range`, the note quoted.
  9. *Cited*: a range, choir, partial or trait from Wikipedia counts only when the raw wikitext
     shows a citation (a `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it in its own cell or
     paragraph, with no `{{citation needed}}` first, in a section not tagged `{{Unreferenced
     section}}`. The citation must support the line: where the cited work is reachable the worker
     opens it, and a citation that gives no range (batch 11's `shehnai`) is no citation. An uncited
     line is not a source for a range, a choir, a partial or a trait that decides a SHIP or a WAIT.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then the
  derivation; then, for a row with choirs, `Footage:`, its passages and their derivation; then, for
  a keyed idiophone built with its partials, `Partials:`, its passages and the ratios.
- **A tuning or a layout is no trait.** A scale is the pitches a sequence asks for (the engine
  takes any `Hz`), not the instrument's sound, as batch 14 ruled for the Bohlen–Pierce clarinet:
  `quarter tone piano` and `archicembalo` are decided like any other row (a sound-alike once
  ranged, its parent by the parent ruling). A keyboard's layout (Jankó, Moór's two manuals as
  keys) is how notes are reached, not how they sound.
- **Registers and stops.** A register of a keyboard (a harpsichord's buff, lute or 16' stop) is a
  catalog entry, as the catalog's `harpsichord lute stop` and batch 13's organ stops are. Its range
  is its instrument's keys, from a source that ranges the instrument; its sound is the register's,
  from a source that describes it. `harpsichord buff stop` is decided on its page and the cited
  Grove entry the Harpsichord page names ("Buff stop [harp stop and (erroneously) lute stop]"): a
  felt or buff damping the build makes only by an unsourced number is no SHIP, so the row is a
  sound-alike of the catalog entry its source relates it to, or waits. Whether the catalog's
  `harpsichord lute stop` is the true lute stop is a finding for #85, not a change here.
- **Generic and ambiguous terms.** A name its source gives to a class or to several instruments
  (`spinet`, if its page makes it "a smaller type of harpsichord or other keyboard instrument, such
  as a piano or organ"; `clavicymbalum`, if its sources use it for the harpsichord and the virginal
  alike; `piano organ`, if no page gives it one meaning) is DROP "a generic term for <the
  instruments>" or "an ambiguous name: <the instruments>", unless the source makes it one
  instrument's name (then rule 3: an ALIAS of that entry). A name whose sources dispute what
  instrument it was (the audit's `chekker`: "nature disputed: perhaps clavichord") is DROP "no
  source says what instrument it was: <its words>".
- **Techniques and preparations.** A sound the player makes by altering the instrument for a piece
  (the `prepared piano`'s objects between the strings, which differ with each work) is decided on
  its page: if its source describes one standard preparation with its sound, the row waits for
  `its own build (objects between the strings)` once ranged; otherwise DROP "a preparation of the
  piano that differs with each piece, not one instrument: <its words>". A pedal or a stop the
  player works (a moderator, una corda) is no instrument.
- **Makers' names and products.** A maker's product in production, or a system a maker sold under
  its name (`welte mignon`, `ampico`, `duo art`, `disklavier`, `fender rhodes`), is decided on its
  page under rule 3: an ALIAS when a cited page gives the name to the instrument the target entry
  builds, else a row of its own (decided like any other, its range from its maker's page) or DROP
  under the one-off ruling.
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's in-production
  line): DROP "a one-off instrument, not a type a game would ask for" for one maker's or
  artist's design never made as a type (the audit's `walking piano`, if its page makes it one
  floor keyboard built for one film; `moor double keyboard piano`, if no maker built it as a type);
  DROP "no fetched source describes it" when no fetched page describes the row, applied the same to
  every such row, candidate or alias name (the audit's "(memory)", category-only and "no source
  found" rows: `giraffe piano`, `tack piano`, `quarter tone piano`, `clavicymbalum`,
  `keyed glockenspiel`, `octavator`, the four case names, if their pages are not found). A
  reconstruction makers offer today, or a type a museum holds, is not a one-off.
- **No size chain.** The catalog's keyboards have no chain in
  `test_sized_families_descend_from_highest_to_lowest`, and adding one would test the 11 existing
  entries' unsourced ranges, which this batch does not change; #85 asks whether to add one.
- **Two halves, as explicit lists.** Half A, the pianos (hammered-string keyboards: acoustic,
  self-playing and the electric names), is these 23 candidates:
  `barrel piano`, `dolceola`, `dulce melos`, `giraffe piano`, `janko piano`, `laterna`, `luthéal`,
  `moor double keyboard piano`, `nickelodeon`, `orphica`, `pedal piano`, `photoplayer`, `piano
  melodico`, `player piano`, `prepared piano`, `quarter tone piano`, `rhodes celeste`, `rhodes
  piano bass`, `square piano`, `tack piano`, `tangent piano`, `walking piano`, `yamaha cp electric
  grand`.
  Half B, the harpsichords, clavichords, keyboard idiophones and the boundary names, is the other
  29: `archicembalo`, `bulbul tarang`, `chamberlin`, `chekker`, `claviharp`, `clavicymbalum`,
  `clavicytherium`, `clavier a lumieres`, `dulcitone`, `geigenwerk`, `glasschord`, `harpsichord
  buff stop`, `harpsichord sixteen foot`, `keyed glockenspiel`, `lautenwerck`, `lautenwerk`,
  `mellotron`, `octavator`, `optigan`, `orchestrion`, `ottavino`, `panharmonicon`, `pedal
  clavichord`, `scalatron`, `shahi baaja`, `spinet`, `taishogoto`, `typophone`, `viola organista`.
  The list decides the half. The alias names go with the half whose candidate or target their line
  names: the 17 piano names (`pianola`, `reproducing piano`, `welte mignon`, `ampico`, `duo art`,
  `disklavier`, `roller piano`, `street piano`, `piano organ`, `rhombia`, `cabinet piano`,
  `cottage piano`, `pyramid piano`, `lyre piano`, `pleyel double piano`, `vis a vis piano`,
  `fender rhodes`) with half A, in that order, and `muselar` with half B. So half A's sheet holds
  40 rows and half B's 30.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the batch,
  or a SHIP or SOUND_ALIKE row of the same half, never a row of the other half. So Task 4 needs
  nothing from Task 2. Half B drafts to a build file, appended to the sheet once half A is
  committed. The form check accepts a row the code already holds with the same target or parent
  (batch 7's lesson). If Task 5 finds a half-B build equal to a half-A build, that is a finding for
  the controller, who re-rules the row in a sheet fix commit.
- **A held-back guard.** As batch 14's `CLARINET_HELD_BACK`, this batch's guard is
  `KEYBOARD_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose
  reason is not `a sourced range` (an engine feature, a build of its own, a sourced partial series,
  sub-audio fundamentals, a range above C8, more than four sources), and every alias row that waits
  for such a row. A test refuses each of its names in the catalog and the aliases, and the code
  check compares the table with the sheet, in the sheet's order. The test passes vacuously while
  the table is empty (#84's parked minor), so the code check is what holds it to the sheet.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task still fills `KEYBOARD_HELD_BACK` with the half's held
  rows and runs the code check, which must pass; its other steps are skipped, and Task 6 records
  the skip in #85.
- **Out of scope:** the audit's "Gaps you could not close" (`keyboards.md`: MIMO, the Horniman and
  Grove not reached; the category's unfetched names, `piganino`, `memotron`, `orpheal`,
  `arcadetar`, `claviola`, `chordboard`, `doppio borgato`, `fotdella`, `gazamba`, `guide chant`,
  `celestaphone`, `harmoneon`, `contemporary harpsichord`; the reproducing pianos, Disklavier,
  Vierling and Neo-Bechstein, RMI Electra-piano, Baldwin electric harpsichord, Hohner Cembalet,
  Birotron, Pleyel double piano, arpicembalo, arpicordo and claviorganum not searched; Asian keyed
  idiophones), the `keyboards.md` rejected names that are no candidate (`apollonicon`, an organ),
  and the mechanical audit's non-piano rows. Task 6 lists them in #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of these files is committed.

- [ ] **Step 0: The branch.** Run `git branch --show-current` and `git rev-parse --short HEAD`.
  Expected: `feat/instrument-catalog-batch-15` and `982a66a7`. Anything else: stop and find out why.

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-15-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-15-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names), len(instruments.CATALOG), len(instruments.ALIASES))
"
```
  Expected: `names before 824 704 120` (checked for this plan at `982a66a7`). Any other number
  means the branch is not batch 14's HEAD: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && tolower($4) ~ /keyboard/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /keyboard/ {print tolower($1)}' round-1/merged-missing.tsv
  awk -F'\t' 'NR>1 && $1 == "new_mechanical_instruments.md" && tolower($2) ~ /piano|laterna|nickelodeon|photoplayer/ {print tolower($2)}' merged.tsv
} | LC_ALL=C sort -u | LC_ALL=C comm -23 - ../../../build/batch-15-names-before.txt > ../../../build/batch-15-candidates.txt
cd ../../..
```
  Write the plan's 23 half-A names, one per line (`luthéal` with its accent, as the audit writes
  it), to `build/batch-15-half-a.txt`, sorted with `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-15-candidates.txt build/batch-15-half-a.txt > build/batch-15-half-b.txt`
  and `wc -l build/batch-15-*.txt`.
  Expected: 52 candidates, 23 in half A, 29 in half B, and
  `LC_ALL=C comm -13 build/batch-15-candidates.txt build/batch-15-half-a.txt` prints nothing.
  Check that `build/batch-15-half-b.txt` is exactly the plan's half-B list, and that
  `LC_ALL=C comm -12 build/batch-15-candidates.txt build/batch-15-names-before.txt` prints nothing
  (the three batch-2 names are gone).

- [ ] **Step 3: The form check,** `build/batch-15-form-check.py`. Copy `build/batch-14-form-check.py`
  (as the controller fixed it during batch 14) and change it as follows; the rest (`STATUSES`,
  `APPROXIMATING_NAMES`, `pattern`, `held_as_this_row`, `taken`, the `bad` list's shape and the
  output) stays.
  - The docstring:
```python
"""Batch 15's sheet form check: uv run python -I build/batch-15-form-check.py SHEET.

Batch 14's form check (build/batch-14-form-check.py, as the controller fixed it during batch 14)
with batch 15's changes (batch 15's plan, "Before the tasks" Step 3): the keyboards family, a
shipped row's keyboard class, batch 13's footage and footage_source columns in place of the drones
(a choir's sounding span inside the catalog's), the mechanical tag, a keyed idiophone's sourced
partials, and a parent outside the family only by the parent ruling's rule 1.
"""
```
  - Remove `SINGLE_CYLINDRICAL_PIPE`, `SINGLE_REED_SET`, `cylindrical`, `MOST_DRONES`, `droned`
    and `alike_allowed`; `names_before` reads `build/batch-15-names-before.txt`; `clarinet_parents`
    becomes:
```python
import ast
import math
from fractions import Fraction

# Hornbostel-Sachs classes checked against Wikipedia's lists for batch 15's plan: 314.122 (board
# zithers with a resonator box: the piano's subdivision), 111.212 (sets of percussion sticks) and
# 111.222 (sets of percussion plaques), each with any suffixes (-4 hammers, -6 plectrum,
# -8 keyboard, -9 mechanical drive)
KEYBOARD_CLASS = re.compile(r'(314\.122|111\.2[12]2)(-[0-9]+)*')
TAGS = ('', 'mechanical')
ALLOWED_FOOTAGES = {Fraction(16), Fraction(8), Fraction(4)}
UNISON_FOOTAGE = Fraction(8)
# The catalog's harpsichord choirs as built (_harpsichord's octave_rank), the only footages before
# the batch
CATALOG_FOOTAGES = {'harpsichord': '8 + 4', 'harpsichord lute stop': '8', 'virginal': '8'}
# The existing keyboard idiophones' partial ratios (keyboards.py: _celesta, _toy_piano)
EXISTING_RATIOS = [(1.0, 4.0), (1.0, 2.76, 5.40)]
NYQUIST_HERTZ = 22050.0
RATIOS = re.compile(r'ratios=(\([^)]*\))')
pre_batch_entries = {
    name for name in names_before
    if name in instruments.CATALOG and instruments.entry(name).sounds_like is None
}
keyboard_parents = set(ship_rows) | {
    name for name in pre_batch_entries if instruments.entry(name).family == 'keyboards'
}
harpsichord_parents = set(CATALOG_FOOTAGES) | {
    name for name, row in ship_rows.items() if row['builder'].startswith('_harpsichord')
}
```
  - Batch 13's `rank_footages`, adapted, and the span and choir checks:
```python
def rank_footages(cell):
    """Each choir's footage, lowest-pitched first as written, or None when none or malformed."""
    if cell == 'none':
        return None
    try:
        footages = [Fraction(rank.strip()) for rank in cell.split(' + ')]
    except ValueError:
        return None
    if footages != sorted(footages, reverse=True) or not set(footages) <= ALLOWED_FOOTAGES:
        return None
    return footages


def footage_of(name):
    """A parent's choirs: a SHIP row's footage cell, or the catalog's as built, else none."""
    return ship_rows[name]['footage'] if name in ship_rows else CATALOG_FOOTAGES.get(name, 'none')


def in_span(note_name, shift=0.0):
    """A note name whose sound, shifted by whole semitones, lies in A0 to C8."""
    try:
        number = Note(note_name).midi_number
    except Exception:
        return False
    return Note('A0').midi_number <= round(number + shift) <= Note('C8').midi_number


def ranged(row):
    """Both keys, lowest below highest, a source and passage, and the choirs' span in A0-C8."""
    footages = rank_footages(row['footage']) or [UNISON_FOOTAGE]
    low_shift = 12.0 * math.log2(UNISON_FOOTAGE / footages[0])
    high_shift = 12.0 * math.log2(UNISON_FOOTAGE / footages[-1])
    return (
        in_span(row['lowest']) and in_span(row['highest'])
        and row['range_source'].startswith('http')
        and 'Range:' in row['notes']
        and Note(row['lowest']).midi_number < Note(row['highest']).midi_number
        and in_span(row['lowest'], low_shift)
        and in_span(row['highest'], high_shift)
    )


def footaged(row):
    """none, or sourced choirs (16, 8 and 4 only, lowest-pitched first) with a passage."""
    if row['footage'] == 'none':
        return True
    return (
        rank_footages(row['footage']) is not None
        and row['footage_source'].startswith('http')
        and 'Footage:' in row['notes'].partition('Range:')[2]
    )


def built_ratios(row):
    """A keyed idiophone's ratios from its builder cell, read as a literal, or None."""
    match = RATIOS.search(row['builder'])
    if match is None:
        return None
    try:
        ratios = ast.literal_eval(match.group(1))
    except (ValueError, SyntaxError):
        return None
    return tuple(float(ratio) for ratio in ratios) if isinstance(ratios, tuple) else None


def near(first, second):
    """Two ratio sets of one length whose ratios are each within 2% (no trait)."""
    return len(first) == len(second) and all(
        abs(one - other) <= 0.02 * other for one, other in zip(first, second, strict=True)
    )


def partials_sourced(row):
    """A keyed idiophone's ratios: 1.0 first, ascending, one to three, under Nyquist, not near."""
    if not row['builder'].startswith('_keyed_idiophone'):
        return True
    ratios = built_ratios(row)
    if ratios is None or not 1 <= len(ratios) <= 3 or ratios[0] != 1.0:
        return False
    if list(ratios) != sorted(set(ratios)) or 'Partials:' not in row['notes']:
        return False
    if float(Note(row['highest']).to_hz()) * ratios[-1] >= NYQUIST_HERTZ:
        return False
    earlier = [built_ratios(other) for other in ship_rows.values() if other is not row]
    return not any(near(ratios, other) for other in EXISTING_RATIOS + earlier if other)


def alike_allowed(row):
    """A keyboard parent, or another family's by rule 1, with its choirs or a 16' added."""
    parent = row['alias_of']
    if parent in APPROXIMATING_NAMES or parent not in keyboard_parents | pre_batch_entries:
        return False
    if parent not in keyboard_parents and 'Parent (rule 1):' not in row['notes']:
        return False
    if row['footage'] in {'none', footage_of(parent)}:
        return True
    return parent in harpsichord_parents and row['footage'] == f'16 + {footage_of(parent)}'
```
  - The `bad` list's family test is `row['family'] != 'keyboards'`; its tag tests are batch 13's
    (`row['tags'] not in TAGS`, and `(row['tags'] and row['status'] not in {'SHIP',
    'SOUND_ALIKE'})`); its shipped-row test reads
```python
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)
                or not footaged(row) or not KEYBOARD_CLASS.fullmatch(row['hs'])
                or not partials_sourced(row)))
```
    and its ALIAS test is `row['alias_of'] not in pre_batch_entries | set(ship_rows) | alikes |
    set(instruments.CATALOG)`.
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: The quote check,** `build/batch-15-quote-check.py`: copy
  `build/batch-14-quote-check.py` and change only these. Its docstring names batch 15 and "the
  Range:, Footage: and Partials: passages", with "A row with no choirs needs no Footage: passage,
  and only a keyed idiophone built with its partials a Partials: passage"; `PAGES` is
  `Path('build/batch-15-pages')`; `quoted` cuts its section at the earliest of several labels:
```python
def quoted(notes, label, stops):
    """The «passages» after a label in the notes, up to the first of the later labels present."""
    section = notes.partition(label)[2]
    ends = [section.find(stop) for stop in stops if stop in section]
    if ends:
        section = section[: min(ends)]
    return re.findall(r'«(.+?)»', section, flags=re.DOTALL)
```
  and its `sections` are
```python
    sections = [('range', quoted(row['notes'], 'Range:', ('Footage:', 'Partials:')), row['range_source'])]
    if row['footage'] != 'none':
        sections.append(('footage', quoted(row['notes'], 'Footage:', ('Partials:',)), row['footage_source']))
    if row['builder'].startswith('_keyed_idiophone'):
        sections.append(('partials', quoted(row['notes'], 'Partials:', ()), row['sound_source']))
```
  A page is found by the row's name with spaces as hyphens (`lutheal--1.txt`). It checks what can
  be checked mechanically; a worker still applies range ruling 9 in full.

- [ ] **Step 5: The code check,** `build/batch-15-code-check.py`: copy `build/batch-14-code-check.py`
  and change it as follows; `test_table`, `held_back`, the "Already decided" branch and the
  order checks' shape stay.
  - The docstring:
```python
"""Batch 15's code check: uv run python -I build/batch-15-code-check.py SHEET.

Batch 14's code check (build/batch-14-code-check.py) with batch 15's changes (batch 15's plan,
"Before the tasks" Step 5): the keyboards family, the 16' choirs, the keyed idiophones' partial
ratios and the mechanical tag compared with the sheet, the only sound change a 16' choir, and the
builds, sound-alikes and aliases in the sheet's order. The test file's tables and a builder cell's
ratios are read as literals (ast.literal_eval), never evaluated. A one-off check may read the
private _KEYBOARD_BUILDS; a test may not.
"""
```
  - The imports read `KEYBOARD_SOUND_ALIKES` from `keyboard_sound_alikes` and `_KEYBOARD_BUILDS`
    from `keyboards`, add `from glitchygames.audio.instruments.catalog import Tag`, and drop
    `math` and `Note`; `EXISTING_COUNT = 11`; `NAMES_BEFORE` reads
    `build/batch-15-names-before.txt`; `CHORUS_CENTS`, `built_drones`, `sheet_drones`,
    `built_detune` and `sheet_detune` go, replaced by:
```python
RATIOS = re.compile(r'ratios=(\([^)]*\))')


def effective_keywords(name):
    """The keywords an entry builds with: its parent's build's, then its own sound changes."""
    entry = instruments.entry(name)
    parent = instruments.entry(entry.sounds_like or name)
    return {**getattr(parent.build, 'keywords', {}), **dict(entry.sound_changes)}


def sheet_ratios(row):
    """A row's partial ratios: its builder cell's, a sound-alike's from its parent's row."""
    if row['status'] == 'SOUND_ALIKE':
        parent_row = rows_by_name.get(row['alias_of'])
        return None if parent_row is None else sheet_ratios(parent_row)
    match = RATIOS.search(row['builder'])
    return None if match is None else tuple(float(ratio) for ratio in ast.literal_eval(match.group(1)))


def sheet_sixteen_foot(row):
    """The row sounds a 16' choir."""
    return row['footage'].startswith('16')


def sheet_changes(row):
    """The sound changes the row's entry carries: a 16' its parent lacks, else none."""
    if row['status'] != 'SOUND_ALIKE' or not sheet_sixteen_foot(row):
        return {}
    parent_row = rows_by_name.get(row['alias_of'])
    parent_footage = parent_row['footage'] if parent_row else {
        'harpsichord': '8 + 4', 'harpsichord lute stop': '8', 'virginal': '8',
    }.get(row['alias_of'], 'none')
    return {} if parent_footage.startswith('16') else {'sixteen_foot': True}
```
    (`rows_by_name` is defined before them, as in batch 14's script.)
  - The shipped-row assertions after `assert entry.sounds_like == parent, name` read:
```python
        expected_tags = frozenset({Tag.MECHANICAL}) if row['tags'] == 'mechanical' else frozenset()
        assert entry.tags == expected_tags, name
        assert dict(entry.sound_changes) == sheet_changes(row), name
        keywords = effective_keywords(name)
        assert bool(keywords.get('sixteen_foot', False)) == sheet_sixteen_foot(row), name
        assert keywords.get('ratios') == sheet_ratios(row), name
```
  - The table assertions after the loop read:
```python
def in_catalog_order(predicate):
    """The SHIP rows, then the SOUND_ALIKE rows, each in the sheet's order, that match."""
    return [
        row['name'] for status in ('SHIP', 'SOUND_ALIKE') for row in rows
        if row['status'] == status and predicate(row)
    ]


assert test_table('KEYBOARD_SIXTEEN_FOOT_NAMES') == in_catalog_order(sheet_sixteen_foot), '16 foot'
assert test_table('KEYBOARD_PARTIAL_RATIOS') == {
    name: sheet_ratios(rows_by_name[name])
    for name in in_catalog_order(lambda row: sheet_ratios(row) is not None)
}, 'KEYBOARD_PARTIAL_RATIOS'
assert test_table('MECHANICAL_KEYBOARD_NAMES') == in_catalog_order(
    lambda row: row['tags'] == 'mechanical'
), 'MECHANICAL_KEYBOARD_NAMES'
assert test_table('KEYBOARD_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'KEYBOARD_HELD_BACK'
assert list(test_table('KEYBOARD_HELD_BACK')) == [
    row['name'] for row in rows if held_back(row)
], 'held-back order'
assert test_table('NEW_KEYBOARD_NAMES') == ship_names, 'NEW_KEYBOARD_NAMES'
assert list(test_table('KEYBOARD_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'KEYBOARD_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in _KEYBOARD_BUILDS[EXISTING_COUNT:]] == ship_names, 'build order'
assert [entry.name for entry in KEYBOARD_SOUND_ALIKES] == alike_names, 'sound-alike order'
```
    followed by batch 14's alias-order assertion and `print('matches', len(rows), 'rows')`.
  It cannot run until Task 1 has created `electromechanical.py`, `keyboard_sound_alikes.py` and
  the test tables. The twelve "Already decided" DROP rows were never catalog names or aliases, so
  they take the last branch.

---

### Task 1: Electromechanical instruments in their own module, unchanged; the keyboards' sound-alikes module; the batch table's row, the choir, partials and mechanical tables and the held-back guard

**Files:**
- Create: `src/glitchygames/audio/instruments/electromechanical.py`,
  `src/glitchygames/audio/instruments/keyboard_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/keyboards.py`, `registry.py`, and the docstrings of
  `organs.py`, `electronic.py` and `__init__.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: in `keyboards.py`, `KEYBOARDS: Final[tuple[CatalogEntry, ...]] = _KEYBOARD_BUILDS +
  KEYBOARD_SOUND_ALIKES`, and `_piano`, `_harpsichord`, `_celesta`, `_toy_piano` under their
  current names; in `electromechanical.py`, `ELECTROMECHANICAL: Final[tuple[CatalogEntry, ...]]`
  and its builders under their current names. `KEYBOARD_SOUND_ALIKES: Final[tuple[CatalogEntry,
  ...]]` is empty. The test file gains `EXISTING_KEYBOARD_NAMES: frozenset[str]` (the 11);
  `NEW_KEYBOARD_NAMES: list[str]`, `KEYBOARD_SOUND_ALIKE_PARENTS: dict[str, str]`,
  `MECHANICAL_KEYBOARD_NAMES: list[str]`, `KEYBOARD_SIXTEEN_FOOT_NAMES: list[str]`,
  `KEYBOARD_PARTIAL_RATIOS: dict[str, tuple[float, ...]]` and `KEYBOARD_HELD_BACK: dict[str,
  str]`, all empty here, for Tasks 3 and 5 to fill; the tests below; and the row
  `Family.KEYBOARDS: BatchFamily(EXISTING_KEYBOARD_NAMES, NEW_KEYBOARD_NAMES,
  KEYBOARD_SOUND_ALIKE_PARENTS)` in `BATCH_FAMILIES`. Also `build/catalog-builds-before.txt`.

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

- [ ] **Step 2: Write the tests.** After batch 13's organ tables (`MECHANICAL_ORGAN_NAMES`), add
  `EXISTING_KEYBOARD_NAMES` (the 11 names, one per line, in catalog order, with the comment "# The
  11 keyboards that predate batch 15: their shared builds predate the anti-goal rule"), then
  `NEW_KEYBOARD_NAMES: list[str] = []`, `KEYBOARD_SOUND_ALIKE_PARENTS: dict[str, str] = {}` and
  `MECHANICAL_KEYBOARD_NAMES: list[str] = []`, each commented as batch 13's organ lists are. Put
  the keyboards row between the plucked strings and organs rows in `BATCH_FAMILIES`, which is
  table order. In `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list
  gains `+ list(KEYBOARD_SOUND_ALIKE_PARENTS)` before the organs' line, its comment naming the
  keyboards before the organs. In `test_harmonic_instruments_sound_their_note`, the halving reads
  `name in SIXTEEN_FOOT_ORGANS or name in KEYBOARD_SIXTEEN_FOOT_NAMES` (a 16' choir repeats every
  two periods of the key). At the end of the file, after
  `test_a_detuned_clarinet_beats_at_its_sourced_cents` (batch 14's last test), add:
```python
# Batch 15's harpsichords that sound a 16' choir an octave below their keys (_harpsichord's
# sixteen_foot), in catalog order: the builds, then the sound-alikes that add one through
# sound_changes (plans/data/instrument-audit/batch-15.tsv)
KEYBOARD_SIXTEEN_FOOT_NAMES: list[str] = []
# Batch 15's keyboard idiophones built from their sourced partial ratios (_keyed_idiophone), in
# catalog order: the builds, then their sound-alikes (plans/data/instrument-audit/batch-15.tsv)
KEYBOARD_PARTIAL_RATIOS: dict[str, tuple[float, ...]] = {}
# Every name plans/data/instrument-audit/batch-15.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# partial series, sub-audio fundamentals, a range above C8 or more than four sources, and the alias
# rows that wait for one of them, in the sheet's order. None ships under that name or as an alias
# until the reason is met (decision 4; batch 15). The test matches exact names
KEYBOARD_HELD_BACK: dict[str, str] = {}


def test_no_keyboard_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a keyboard the sheet holds back."""
    assert set(KEYBOARD_HELD_BACK) & set(instruments.names()) == set()
    assert set(KEYBOARD_HELD_BACK) & set(instruments.ALIASES) == set()
```
  Then, each with a one-line docstring:
  - `test_the_mechanical_keyboards_are_tagged`: `instruments.names(family=Family.KEYBOARDS,
    tag=Tag.MECHANICAL) == tuple(MECHANICAL_KEYBOARD_NAMES)`.
  - `test_a_sixteen_foot_harpsichord_sounds_its_lower_choir`: the keyboard entries whose effective
    keywords (the parent's `build.keywords`, read with `getattr(build, 'keywords', {})` since
    `toy piano`'s build is a plain function, updated with the entry's own `sound_changes`) hold
    `sixteen_foot=True` are exactly `KEYBOARD_SIXTEEN_FOOT_NAMES`, in catalog order; for each, the
    built instrument has a source whose semitones are -12.0 (`plucked`'s course, read from
    `instruments.get(name).sources` as `test_a_retuned_bagpipe_sounds_its_sourced_drones` reads its
    sources).
  - `test_a_keyed_idiophone_sounds_its_sourced_partials`: the keyboard entries whose effective
    keywords hold `ratios` are exactly `KEYBOARD_PARTIAL_RATIOS`' keys, in catalog order, each
    equal to its value; and for each, an FFT of its middle note (as `eight_foot_relative_harmonics`
    measures) peaks within a quarter of the fundamental's hertz of every ratio times the
    fundamental.
  All three hold with the tables empty (no keyboard is tagged, has a 16' choir or a `ratios`
  keyword today), and fail if a later task ships one without listing it.

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or mechanical or sixteen_foot or keyed_idiophone or sound_their_note" -v`
  Expected: PASS, with the ID `[keyboards]` in the parametrised batch tests. They are guards that
  hold the later tasks; the move in Step 4 must keep them passing.

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move
  `keyboards.py`'s "Electromechanical" section (its header comment, its five builders and
  `ELECTROMECHANICAL`) into `electromechanical.py` unchanged, comments included, with the imports
  it uses (`math`, `partial`, `Final`, `Instrument`, `Source`, `CatalogEntry`, `Family`, and from
  `timbres` and `waves` those its builders call); `keyboards.py` keeps only what its section uses.
  Rename `keyboards.py`'s tuple `_KEYBOARD_BUILDS` and define `KEYBOARDS` after it as the
  concatenation, importing `KEYBOARD_SOUND_ALIKES`. The docstrings:
  - `keyboards.py`'s first line becomes "Keyboards: pianos, harpsichords, clavichord, celesta and
    toy piano." It keeps the piano and harpsichord sentences and "Ranges are each instrument's
    keyboard", says that the sound-alikes are in ``keyboard_sound_alikes.py``, and that the
    electromechanical instruments are in ``electromechanical.py`` and the pipe organ in
    ``organs.py``.
  - `electromechanical.py`'s first line is "Electromechanical instruments: electric pianos,
    Clavinet, Pianet and tonewheel organs." It takes the tonewheel organ sentence ("The tonewheel
    organ's drawbar registrations (``Harmonics.drawbars``) and percussion, a decaying second or
    third harmonic …") and "which read a mechanical vibration electrically", and names
    ``keyboards.py`` for the keyboards.
  - `keyboard_sound_alikes.py` gets the empty table and `organ_sound_alikes.py`'s docstring with
    "Keyboards'" for "Organs'", the footage sentence replaced by "A sound-alike harpsichord whose
    source gives it a 16' choir its parent lacks carries it as ``sound_changes``, its only
    change.", ending "The family's builds are in ``keyboards.py``.".
  - `organs.py` line 9, `electronic.py` line 5 and `__init__.py` line 137 name
    ``electromechanical.py`` for the electromechanical instruments (and `organs.py` ``keyboards.py``
    for the keyboards).
  Point `registry.py` at both modules (`KEYBOARDS` from `keyboards`, `ELECTROMECHANICAL` from
  `electromechanical`). If the process-state guard then asks for an entry for any moved name, that
  is a finding: `clarinets.py` needed none, so read why before writing any reason.

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
uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q
```
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit.** Run each lint command as its own line (batch 11's Task 1: zsh
  word-splitting once made a combined run a no-op).
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
SKIP=replay-metrics git commit -m "Instrument catalog: electromechanical instruments in their own module, unchanged; the keyboards' sound-alikes module; the choir, partials, mechanical and held-back guards" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The pianos sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. Put no personal data in any request, in a header, a
URL or a payload. Save each ranged row's raw pages as `build/batch-15-pages/<name, spaces as
hyphens>--<n>.txt` (for Wikipedia, the `action=raw` wikitext; never a text extracted from it,
which drops `<ref>` and `<sup>`: #81's lesson). A list or category page is a source for a name
only. The sound, the mechanism, the range and any choirs come from the instrument's own page, a
maker or a museum under range ruling 6. The audit's rows and "Range checks" are leads, not
sources, so fetch them. Fetch the page of every existing entry you name as a parent, and record
what it says in the row's notes. Never use `git stash`. This task may start as soon as the
controller has written the shared files, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-15.tsv`
- Create (not committed): `build/batch-15-half-a.tsv`, and the raw pages in
  `build/batch-15-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `keyboards.md` ("Rejected or corrected
  proposed entries", "Aliases", "Range checks", "Gaps you could not close");
  `new-mechanical-instruments.md` (the piano rows and their alias lines); `batch-2.tsv` and
  `batch-4.tsv` (the rows named in the hand-offs); `build/batch-15-names-before.txt`,
  `build/batch-15-half-a.txt`, `build/batch-15-half-b.txt`, `build/batch-15-form-check.py` and
  `build/batch-15-quote-check.py`.
- Produces: `batch-15.tsv` with batch 13's seventeen columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	footage	footage_source`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `keyboards` on every row; `tags` is
  `mechanical` or empty. A SHIP or SOUND_ALIKE row has `lowest`, `highest` (sounding at 8'),
  `range_source`, an `hs` that fullmatches the keyboard classes, `footage` (choirs or `none`), and
  `notes` holding `Range:` (and `Footage:`, `Partials:` as the rulings need), each with its «raw
  passages» and derivation, and its parent ruling line ("Parent (rule 1):" or "Parent (rule 2):")
  for a sound-alike. A candidate row's `audit_name` is its name in
  `build/batch-15-candidates.txt` (`luthéal` with its accent); an alias row's is its audit line.
  Also `build/batch-15-half-a.tsv`, the half as committed, which Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-15-half-a.txt`'s order, then
  one per alias name of this half, in the plan's order.

  The rules are batch 14's, changed for this family:

  1. **SHIP** only with name, title, sound, mechanism, range and (as the rulings need) choirs or
     partials from fetched sources, and a cited trait the engine can make that no keyboard build
     has (a 16' choir, a struck body's partial ratios). Quote in `notes` the passage that describes
     the sound or construction (what the keys sound and how) and, after `Range:`, `Footage:` and
     `Partials:`, the «raw passages» and the derivations under the rulings. The `builder` cell gives
     the call with every keyword and says which values come from the source and which are sound
     design, copied from which entry.
  2. **SOUND_ALIKE**: a verified instrument that rule 7 finds would sound like an existing entry or
     a SHIP row of this half. `alias_of` is its parent (the parent ruling). The `notes` begin
     "Sound-alike:", quote the source's description and mechanism, and say why that entry is the
     parent ("Parent (rule 1):" with the source's relating words, or "Parent (rule 2):" with the
     mechanism and the semitone counts). It has its own range, and the `builder` cell says
     "unchanged" (or "sound_changes={'sixteen_foot': True}" under the choir ruling). It is never
     another sound-alike's sound-alike, never one of `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row of this half. If the target waits, the row is WAIT with `waits_for`
     `its target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is
     dropped". An ambiguous name or a generic term is DROP under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `a sourced partial series`,
     `sub-audio fundamentals`, `a range above C8`, `more than four sources`, `its own build (<the
     trait>)`, or another name of Global Constraints. The range is checked first. The feature must
     be the sound the source describes, not a technique a player applies (a pedal, a stop the
     player works, a preparation for one piece). A cited trait no builder makes means the row
     waits. Any other name is allowed only with the source quoted, and Task 6 lists it in #85.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     boundary ruling's words), is a one-off, makes no sound, or is already decided: in the catalog
     under that name (name the entry), an alias already (name its target), or a row of an earlier
     sheet (notes beginning "Already decided:", naming the sheet and its status).
  6. A row the audit marks "(memory)", UNVERIFIED for existence, or sourced only by a list or
     category page has no sourced sound or range yet. Fetch its own page; the audit's URL is a
     lead. If no page can be found, the row is DROP "no fetched source describes it", the same
     words on every such row.
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='keyboards'))"`
     and the builds in `keyboards.py`) and every SHIP row above it. If no cited trait (a 16'
     choir, sourced partials) makes it sound different, it is a SOUND_ALIKE under rule 2. A number
     chosen only to differ does not count, nor a difference of 1 or 2 percent in a value (batch
     11's contraforte), nor a loudness, a colour word, a range, a key, a size, a case, a layout, a
     tuning, a material or a self-playing mechanism.
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.

  This half's own cases:

  - **Already decided.** `rhodes celeste`, `rhodes piano bass` and `yamaha cp electric grand` are
    DROP under rule 5, their notes beginning "Already decided: batch-2.tsv" and its status.
  - **Batch 4's hand-off.** `dolceola` is decided here under the boundary rulings (batch 4: "Its
    strings are struck from a piano keyboard: keyboards, with the piano"); its page's
    "music-box sound" is a colour word.
  - **Piano forms and layouts.** `square piano`, `giraffe piano`, `orphica` (a portable piano),
    `pedal piano`, `janko piano`, `moor double keyboard piano`, `tangent piano` and `quarter tone
    piano` are decided by the boundary, sound-alike, parent and range rulings, and the tuning and
    layout ruling: each is a sound-alike once ranged, unless its source names a trait the build
    cannot make (Moór's coupler sounding the octave: WAIT `its own build (an octave coupler)`; a
    tangent piano's tangents: decided on its page, the clavichord being a parent only by rule 1).
    The early pianos' compasses vary by period and maker: range ruling 4 (a museum's object record
    ranges a named model only).
  - **The tack piano and the prepared piano.** `tack piano`'s tacks and `prepared piano`'s objects
    follow the sound-alike ruling (a trait `_piano` cannot make: WAIT `its own build (<it>)`) and
    the techniques ruling; `lutheal`'s registers (the audit: "cimbalom-like, harmonics, objects
    over strings, harpsichord/harp-lute") are traits the build cannot make, so once ranged it waits
    for its own build.
  - **Self-playing pianos.** `player piano`, `barrel piano`, `laterna`, `piano melodico`,
    `nickelodeon` and `photoplayer` follow the mechanical ruling: `tags` `mechanical` on a shipped
    row; a piano with drums, effects or a mandolin attachment (the audit's `nickelodeon` and
    `photoplayer`) waits for more than four sources once ranged. A barrel piano's "often tuned
    slightly sharp and jangly" (the audit) is a detune only with its cents sourced, and `_piano`'s
    `cents` is then a SHIP's sourced keyword; without cents it is a colour.
  - **Struck zithers with keys.** `dulce melos` (the audit: "hammered-dulcimer-like keyboard
    zither") is a piano by boundary ruling 1 when its source gives the keys striking the strings,
    struck strings by ruling 5 when it gives beaters.
  - **One-offs.** `walking piano` follows the one-off ruling on its page.
  - **The alias names.** `pianola` and `reproducing piano` follow `player piano` (rule 3), and
    `welte mignon`, `ampico`, `duo art` and `disklavier` the makers' ruling (each a system a maker
    sold; an ALIAS only on a cited page that gives it as the player piano's name). `roller piano`,
    `street piano`, `piano organ` and `rhombia` follow `barrel piano`. `cabinet piano`, `cottage
    piano`, `pyramid piano` and `lyre piano` (the audit's "memory, not verified" line) are each
    decided on a page that names it: an ALIAS of `upright piano` or a SOUND_ALIKE row, a row of its
    own, or DROP "no fetched source describes it". `pleyel double piano` and `vis a vis piano`
    (two pianos in one case, facing) are decided on their pages: an instrument of two grand pianos
    is no new sound, and an ALIAS of `grand piano` only on a cited page giving it as a grand
    piano's name. `fender rhodes` is an ALIAS of `tine electric piano` on a cited page giving it
    as the name of the instrument that entry builds (the entry's own comment cites the Fender
    Rhodes page).

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-15-form-check.py plans/data/instrument-audit/batch-15.tsv`
  and `uv run python -I build/batch-15-quote-check.py plans/data/instrument-audit/batch-15.tsv`.
  Expected: `40 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-15.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-15-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-15-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
"
```
  Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-15.tsv build/batch-15-half-a.tsv
git add plans/data/instrument-audit/batch-15.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 15's verification sheet, the pianos (struck-string keyboards)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The pianos

**Files:**
- Modify: `keyboards.py` (new builds after the 11), `keyboard_sound_alikes.py`
  (`KEYBOARD_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-15-half-a.tsv` (half A as committed), Task 1's tables and
  `build/batch-15-code-check.py`.
- Produces: `NEW_KEYBOARD_NAMES`, `KEYBOARD_SOUND_ALIKE_PARENTS`, `MECHANICAL_KEYBOARD_NAMES` and
  `KEYBOARD_HELD_BACK` filled with this half's rows, which Task 5 extends. Half A holds no
  harpsichord or keyboard idiophone, so it adds neither `sixteen_foot` nor `_keyed_idiophone`; a
  half-A row that needs one is a finding for the controller.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills only
`KEYBOARD_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_KEYBOARD_NAMES` with one name per SHIP row,
  `KEYBOARD_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row,
  `MECHANICAL_KEYBOARD_NAMES` with every SHIP and then SOUND_ALIKE row whose `tags` is
  `mechanical`, and `KEYBOARD_HELD_BACK` with one `name: waits_for` per held row (every WAIT row
  whose reason is not `a sourced range`, and every `its target, <name>` row whose target is held),
  each in the sheet's order. Add the ALIAS rows to `test_the_batch_aliases_resolve`'s parameters,
  in the sheet's order, with a docstring sentence for batch 15. If a mechanical row ships, add it
  to the list in `test_plucked_idiophones_hold_the_lamellophones_and_music_boxes` after `'music
  box'`, in catalog order.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or held_back or mechanical or music_boxes or sound_their_note" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the held-back
  test passes.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in `KEYBOARD_SOUND_ALIKES`,
  in the sheet's order, under a section comment naming `plans/data/instrument-audit/batch-15.tsv`
  as `organ_sound_alikes.py`'s does ("--- Batch 15's pianos, in the order of …"), each a
  `CatalogEntry(name, title, Family.KEYBOARDS, lowest, highest, sounds_like=parent)` with
  `tags=frozenset({Tag.MECHANICAL})` for a mechanical row. Above each, put a comment with its
  `sound_source` and `range_source` URLs, the quoted passages (its mechanism, its range) and the
  range's derivation. A SHIP row is a `CatalogEntry` after the 11 in `_KEYBOARD_BUILDS`, carrying
  the same comment and marking the values that are sound design and the entry they are copied from.
  Each ALIAS row goes in `aliases.py` under a "Batch 15's keyboards: the pianos" section, in the
  sheet's order, with its URL and quote. Comments name only committed files.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range or the build. Check it against the source, and never trim the range to
  pass. Then run:
  `uv run python -I build/batch-15-code-check.py build/batch-15-half-a.tsv`
  Expected: `matches 40 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 15's pianos, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The harpsichords, clavichords and keyboard idiophones sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-15-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-15-pages/`
- Modify: `plans/data/instrument-audit/batch-15.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-15-form-check.py`,
  `build/batch-15-quote-check.py`, `build/batch-15-half-b.txt`; `keyboards.md` (the "Rejected or
  corrected" lines for `spinet`, `clavicymbalum`, `lautenwerck`, `scalatron`, `octavator`;
  "Aliases"; "Range checks"; "Gaps"); `batch-2.tsv`, `batch-4.tsv`, `batch-7.tsv` and
  `batch-13.tsv` (the rows named in the hand-offs); `batch-13.tsv`'s footage rows (`bourdon`,
  `stopped diapason`) as worked examples of the choir ruling.
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-15-half-b.txt`'s order, then one for `muselar`.
A parent or alias target is a catalog name or a SHIP or SOUND_ALIKE row of this half, never a
half-A row. These rules apply on top of Task 2's:

- **Already decided.** `bulbul tarang`, `chamberlin`, `geigenwerk`, `mellotron`, `optigan`,
  `orchestrion`, `panharmonicon`, `taishogoto` and `viola organista` are DROP under rule 5, their
  notes beginning "Already decided:" with the sheet and status the Spec line gives each.
- **Batch 4's hand-off.** `claviharp` is decided here (batch 4: "A quill-plucked keyboard
  instrument: keyboards"); its page's "Special Strings to emulate the sound of a Harp" is a trait
  only with what the build would change sourced.
- **Harpsichords and registers.** `harpsichord sixteen foot` and `harpsichord buff stop` follow
  the registers and choir rulings: the 16' choir's sounding span on the instrument's keys decides
  between a SHIP or sound-alike and `sub-audio fundamentals`; the buff stop's felt or leather damping
  is no SHIP (an unsourced number), and its parent is by relation. `ottavino` (the audit: "small
  spinet/virginal at 4 foot pitch") is a 4' instrument: its keys sound an octave up, so its range is
  its sounding compass from a source, and `footage` `4` only when the source names its choir that
  way (else its sounding range, footage `none`). `clavicytherium`, `lautenwerk` (gut strings: a
  material, unless its source names an effect the build makes with numbers) and `archicembalo`
  (the tuning ruling) are sound-alikes once ranged. `lautenwerck` and `lautenwerk` are one
  instrument (rule 8). `spinet`, `clavicymbalum` and `chekker` follow the generic and ambiguous
  terms ruling. `muselar` is an ALIAS of `virginal` only on a cited page giving it as a virginal's
  name (the Harpsichord page lists "virginals, muselar, and spinet" as similar instruments: a list
  is a source for a name only, and the muselar is a kind of virginal, which is decided on its page,
  as a sound-alike when its source sets it apart only by construction).
- **Clavichords.** `pedal clavichord` is a clavichord with a pedalboard: a sound-alike of
  `clavichord` once ranged (pedals are no trait), with its own sourced range.
- **Keyboard idiophones.** `dulcitone` and `typophone` (tuning forks), `glasschord` (glass bars)
  and `keyed glockenspiel` follow the keyed idiophone ruling: a SHIP only with sourced partial
  ratios, a sound-alike within 2% of an existing build's, else WAIT `a sourced partial series` once
  ranged. The dulcitone's range is written with its stated transposition (the audit: "written
  AA-a3, sounds octave higher", Helmholtz with octave marks): range rulings 1 and 2. `typophone`
  redirects to the Celesta page's history (checked for this plan); it is decided on what a fetched
  source says of it. `keyed glockenspiel`'s parent may be `glockenspiel` by rule 1 only.
- **The boundary names.** `shahi baaja` follows boundary ruling 6 (keys stopping strings plucked by
  hand: plucked strings); `scalatron` boundary ruling 8; `clavier a lumieres` ruling 10;
  `octavator` rule 6 (the audit: "no source found").

- [ ] **Step 1: Write half B's rows** to `build/batch-15-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-15-form-check.py build/batch-15-half-b.tsv` and
  `uv run python -I build/batch-15-quote-check.py build/batch-15-half-b.tsv`.
  Expected: `30 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-15-half-b.tsv >> plans/data/instrument-audit/batch-15.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `70 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half A's
  coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-15.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-15-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-15-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted((half_a | half_b) - set(audit_names)))
print('twice:', sorted({name for name in half_a | half_b if audit_names.count(name) > 1}))
print('extra:', sorted(set(audit_names) - half_a - half_b))
"
```
  Expected: `missing: []` and `twice: []`. `extra:` lists only the alias rows' audit lines (eight
  distinct lines: `keyboards.md`'s pianola, case-names, Jankó, fender rhodes and muselar lines,
  and `new-mechanical-instruments.md`'s Welte-Mignon, roller piano and rhombia lines), because an
  alias row's `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-15.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 15's verification sheet, the harpsichords, clavichords, keyboard idiophones and boundary names" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The harpsichords, clavichords and keyboard idiophones

**Files:**
- Modify: `keyboards.py` (new builds after half A's; `_harpsichord`'s `sixteen_foot` and
  `_keyed_idiophone`, each only if a row needs it), `keyboard_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-15.tsv`'s half-B rows, Task 3's tables, and `build/batch-15-code-check.py`.
- Produces: the finished family; and, as rows need them, `_harpsichord(*, low_pass: float,
  octave_rank: bool, sixteen_foot: bool = False) -> Instrument` and `_keyed_idiophone(*, ratios:
  tuple[float, ...]) -> Instrument` in `keyboards.py`, with the values the choir and keyed
  idiophone rulings give.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `NEW_KEYBOARD_NAMES`,
  `KEYBOARD_SOUND_ALIKE_PARENTS`, `MECHANICAL_KEYBOARD_NAMES`, `KEYBOARD_HELD_BACK` and the alias
  parameters, after half A's, as in Task 3 Step 1; fill `KEYBOARD_SIXTEEN_FOOT_NAMES` with every
  SHIP and then SOUND_ALIKE row whose `footage` begins with 16, and `KEYBOARD_PARTIAL_RATIOS` with
  one `name: ratios` per SHIP row built with `_keyed_idiophone` and per sound-alike of one (its
  parent's ratios), in catalog order. A `_keyed_idiophone` entry with an inharmonic ratio goes in
  `NOT_PERIODIC_AT_THE_NOTE` with the keyed idiophone ruling's reason. If `sixteen_foot` is added,
  add `test_harpsichord_sixteen_foot_adds_a_choir_an_octave_down`: `_harpsichord` imported in the
  test is not allowed (it is private), so build through a catalog entry's `build.func` with
  `sixteen_foot=True` and `False`, as `eight_foot_relative_harmonics` reads `build.func`, and
  assert the true build's sources hold one more than the false one's, at -12.0 semitones.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command with
  `or sixteen_foot or keyed_idiophone` added to its `-k` expression.
  Expected: the new cases fail with `KeyError: no instrument named ...` (and, before the keyword
  exists, the `sixteen_foot` test with a `TypeError` naming the unexpected keyword).

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes, aliases after half A's aliases, under second
  section comments naming the sheet ("Batch 15's keyboards: the harpsichords, clavichords and
  keyboard idiophones"). A 16' sound-alike carries `sound_changes={'sixteen_foot': True}` and its
  `Footage:` passage in its comment. Add `sixteen_foot` or `_keyed_idiophone` only if a row needs
  it, with the rulings' values marked as sound design and the entry they are copied from.

- [ ] **Step 4: Run the suite and check the code against the whole sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -v`, then
  `uv run python -I build/batch-15-code-check.py plans/data/instrument-audit/batch-15.tsv`.
  Expected: PASS, then `matches 70 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's three lint commands, each on its own line,
  then `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 15's harpsichords, clavichords and keyboard idiophones, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a keyboards
  paragraph with its count, naming `keyboards.py` and `keyboard_sound_alikes.py`, with examples,
  in the clarinets paragraph's form, saying that a keyboard is an acoustic instrument its keys
  sound (struck or plucked strings, struck bars, forks or glass), that a sound-alike of another
  form or size gives its own sourced range, and, if one shipped, that a 16' choir sounds an octave
  below the keys and a keyed idiophone sounds its sourced partials. Say that `electromechanical.py`
  now holds the electromechanical instruments.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `keyboards` row's
  count and examples, the sound-alike modules sentence and its total, and any sentence naming
  `keyboards.py` as the electromechanical instruments' module).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts, and the `Tag.MECHANICAL` sentence if a mechanical keyboard shipped).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 15
  done, pointing at this plan and `batch-15.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 15 DONE";
  - batch 15 done, with the sheet's counts by status and the family's growth, the module move
    (`electromechanical.py`; `keyboards.py` keeping the keyboards), the boundary rulings, any 16'
    harpsichord, keyed idiophone or mechanical keyboard shipped, `KEYBOARD_HELD_BACK`'s names, and
    the branch's base SHA (`982a66a7`, batch 14's HEAD);
  - the audit's unclosed gaps, as a later pass;
  - the hand-offs: `claviharp` and `dolceola` decided here; the earlier sheets' names left as they
    decided them; each row dropped to struck strings (batch 18), harps (batch 17), free reeds
    (batch 16), plucked strings, electromechanical or electronic for a later pass of those
    families; the alias names decided here (so no later batch decides `fender rhodes`, the player
    piano's and barrel piano's names, or `muselar` again);
  - a "Plan (batch 15)" line, the Status line, and the next batch named: free reeds (batch 16).

  Add #85 (the highest item is #84), "Sound Engine: The Owner's Checks on Instrument Catalog Batch
  15 — TODO". Use #84's form, place it directly after #84, and give it the Priority "(before the
  free reeds batch builds on the same catalog)". Its **Listen** section
  (`build/instruments/keyboards/`) covers the new builds (each 16' or keyed idiophone build against
  the catalog entry its values were copied from), then the sound-alikes beside their parents, then
  the aliases. Its **Calls to confirm** are:
  - every WAIT, by reason, with names;
  - the module move (`electromechanical.py` out of `keyboards.py`) and its `changed: []` record;
  - the boundary rulings, each row they moved, and the Hornbostel–Sachs codes this plan checked;
  - a keyboard as a sound-alike (cases, layouts, tunings, sizes, materials and colour words no
    trait; a SHIP only for a sourced 16' choir or sourced partials);
  - the parent ruling (the source's relation first, the only way to another family's parent; else
    the same mechanism's nearest lowest note), and each sound-alike's parent;
  - the range ruling (one source states both ends; a string keyboard's 8' compass sounding as
    given, a keyboard idiophone's written range only with its stated transposition; key counts,
    widths, hedges and generalisations no range; makers' and museums' pages over uncited Wikipedia
    lines; nothing below A0 or above C8, for the keys and the choirs), and every derived range;
  - the choir ruling (`sixteen_foot` if added, its copied level and offset), and the keyed
    idiophone ruling (`_keyed_idiophone` if added, the copied celesta values, the new wait name
    `a sourced partial series`);
  - the mechanical ruling and each tagged or waiting self-playing keyboard;
  - the registers ruling (`harpsichord buff stop`) and the catalog's `harpsichord lute stop` naming
    question;
  - generic, ambiguous, one-off, technique and unsourced rows, with the words "no fetched source
    describes it" on every row whose page was not found;
  - `KEYBOARD_HELD_BACK`, the guard for every non-range wait;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - the size chain left out (would you add the keyboard sizes to
    `test_sized_families_descend_from_highest_to_lowest`?);
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): the 11 earlier entries' missing
  source comments; any existing range or build a sheet's source contradicts (the leads in Global
  Constraints: the Harpsichord page's uncited compass paragraph, the Celesta infobox's C3–F8, the
  catalog's lute stop built as a muted register); the third-party `speech_recognition`
  DeprecationWarning under `-W error` as #81 to #84 record it. Then **Follow-ups**: the audit's
  gaps; ranging the range WAITs from maker and museum sources; checking the 11 earlier entries
  against sources; the engine changes that unblock the waits, most rows first. Then **Incidents
  and process**, as #84 has them.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries())); print(i.names(tag='mechanical'))"`
  and `uv run python -I build/batch-15-form-check.py plans/data/instrument-audit/batch-15.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-15-code-check.py plans/data/instrument-audit/batch-15.tsv
uv run python -I build/batch-15-quote-check.py plans/data/instrument-audit/batch-15.tsv
```
  Expected: everything passes with no warnings (a warning is a finding; #81 records the
  third-party `speech_recognition` DeprecationWarning under `-W error`, so a new one is a new
  finding), `matches 70 rows`, and `bad: []`. The `build/instruments/keyboards` folder is the one
  to listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 15 of the instrument catalog (keyboards), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch in
turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78). The
pre-push hooks take about 40 minutes, and nothing in the working tree may change while they run.

**Order:** the controller's shared files, then Tasks 1, 2 and 4 in parallel. Task 3 follows Tasks
1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows Tasks 3 and 4, and Task 6 comes
last.

**Corrections to batch 14's plan carried here:** batch 14's form check assumed a Hornbostel–Sachs
bore split (422.221 and 422.222) that does not exist (#84); every code this plan relies on was
checked against Wikipedia's lists before writing it, and its `cylindrical` test is not carried.
Batch 14's steps named commands by chains of reference ("batch 13's Task 2 Step 3 command (batch
12's)", "batch 4's Task 1 Step 1 command"); this plan writes each command out. Batch 14's range
ruling 1 did not say that one source states both ends, which its `xaphoon` reversal needed; this
plan's does. Batch 14's parent ruling forbade any parent outside the family, while the catalog
holds eight cross-family sound-alikes; this plan allows one by the source's relation only, and its
form check asks for the "Parent (rule 1):" line.
