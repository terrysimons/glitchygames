# Instrument catalog batch 11 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the double reed family from the audits' candidates. The family holds the oboes
(Hornbostel–Sachs 422.1: a double reed on a conical or cylindrical pipe, capped or not, and the
double pipes), from the orchestral oboes, bassoons, heckelphones and sarrusophones and the
Renaissance shawms, crumhorns and dulcians to the folk shawms of Europe, the Middle East, Africa
and Asia. Each instrument gets a cited source and either sounds unlike every other entry or is a
listed sound-alike of the one it sounds like. The rest become aliases, wait for an engine feature
or a sourced range, or are dropped with a reason.

**Architecture:** As in batches 3 to 10, a verification sheet (`batch-11.tsv`) decides every
candidate before any code is written. The family's 23 entries live in `winds.py` (743 lines,
which also holds the clarinets, saxophones, bagpipes and free reeds), so they move unchanged to a
new `double_reeds.py`, as batch 9 moved the flutes. Its table is `_DOUBLE_REED_BUILDS`, and
`DOUBLE_REEDS` becomes `_DOUBLE_REED_BUILDS + DOUBLE_REED_SOUND_ALIKES`, with the sound-alikes in
a new `double_reed_sound_alikes.py`, the pattern of `brass_sound_alikes.py`. A new guard,
`DOUBLE_REED_HELD_BACK`, holds every name the sheet holds back for an engine feature or a build
of its own. The sheet and the code each come in two halves, as explicit lists: the orchestral,
modern and early European double reeds (researched mostly from makers, early-instrument makers
and museums), then the folk and traditional shawms and oboes of Europe, the Middle East, Africa
and Asia (researched mostly from encyclopedias and museums). The controller writes the names
file, the candidate lists and the three check scripts before anything is dispatched, so the two
sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `falling_series`,
`with_drones`, `wave_from_levels`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all). Batch 10's plan (`plans/2026-11-12-instrument-catalog-batch-10-implementation.md`)
and its owner's checks (`plans/future-features.md` #80) are this plan's template and its ledger.
Batch 4's plan (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`) holds the
pitched sound-alike and strict range rules and the before-and-after build record. Batch 9's plan
holds the module move. This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-11-implementation.md`. The branch is
`feat/instrument-catalog-batch-11`, made from `feat/instrument-catalog-batch-10` at its HEAD
(`36ecd139`, batch 10's final review fixes, which touch no double reed). The candidates come from
`plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `double reed` (69, every one from the round-2
  audit `double-reeds.md`, whose `audit_file` cell is `double_reeds.md`);
- the `round-1/merged-missing.tsv` rows whose `family` contains `double reed` (12: `aulos`,
  `dulcian`, `nadaswaram`, `shehnai`, `oboe da caccia`, `piccolo oboe`, `kortholt`,
  `rauschpfeife`, `hne`, `bassanelli`, `tromboon`, `serpentine bassoon`).

Together: **80 unique candidate names** (`nadaswaram` is in both; counted for this plan, the
controller recounts). None is in the catalog or the alias table today, and every one is already
a valid catalog name. The audit's "Aliases" section proposes **36 alias names**: `cor anglais`,
`baritone oboe`, `musette`, `oboe musette`, `fagott`, `curtal`, `courtaud`, `bajon`, `doucaine`
(the audit's "douçaine"), `dulciana`, `bassanello`, `pommer`, `bombard`, `nagaswaram`,
`nadhaswaram`, `nataswaram`, `shahnai`, `sanayi`, `sahanai`, `surna`, `sorna`, `surnay`,
`zournas`, `hojeok`, `hojok`, `nallari`, `saenap`, `guan`, `kuan`, `haidi`, `laba`, `cervelas`,
`ghaita`, `ghayta`, `pi` and `mukhaveene`. None is in the catalog or the aliases. That section's
last line, "cornu / tarogato modern -> single reed, not this family", proposes no alias: `cornu`
was decided by batch 10 (brass) and the tárogató is the clarinets batch's. So the sheet will hold
**116 rows**.

No earlier sheet hands a candidate to this family (checked: `batch-1.tsv` to `batch-10.tsv`, and
`plans/future-features.md` #70–#80). Two candidates are also rows of the bagpipes audit, the next
batch's: `zukra` (its page: "a Libyan bagpipe") and `ciaramella` (the bagpipes audit's row is a
zampogna, "ciaramedda"). `dulciana`, an alias name here, is an organ stop in the organs audit.
Batch 9's #70 lists `piffero` among the flutes' unconfirmed names; the candidate here is the
shawm. The plan's boundary ruling below decides each.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, hyphens and parentheses go only in the title (`doucaine`
  for "Douçaine", `hautbois de poitou` for "Hautbois de Poitou"). A key goes before the name, as
  in the catalog (`e flat clarinet`, `e flat tuba`), so the audit's `contrabass sarrusophone eb`
  and `contrabass sarrusophone bb` are `e flat contrabass sarrusophone` and `b flat contrabass
  sarrusophone`, with the audit's names in `audit_name`.
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families).
  Double reeds are the oboes, H-S 422.1: 422.111 a single oboe with a cylindrical bore, 422.112
  with a conical bore, 422.12 a set of oboes (a double pipe), whatever the material (wood, cane,
  metal). A bag makes a bagpipe, the next batch's family.
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict").
  This plan's range ruling for double reeds is below, under "Decisions". A row with no sourced
  range is WAIT, `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the
  same instrument) stays an alias." A sound-alike is pitched exactly when its parent is, and a
  pitched sound-alike gives its own sourced range (batch 4). A parent may be in another family
  (batch 7), when the row's source relates them.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as
  an approximation, under its real name or a qualified one. The spec's table names no double
  reed, but its rows "sub-audio fundamentals" (the B-flat contrabass sarrusophone's A-flat 0) and
  "more than four sources" bind. Earlier batches added the other names a WAIT may give: a pitch
  LFO (vibrato), a pitch LFO (portamento between notes), an amplitude LFO, filter resonance, a
  filter envelope, moving formants (batch 6); a buzzing membrane (batch 5); a sourced drone
  tuning and its own build (batch 7); a range above C8 (batch 10). What the engine has: up to
  four `Source`s, each with its own semitones, detune and fixed pitch; one glide per note
  (`pitch_curve`); a fixed FIR low or high pass; `drive` 0–20; `with_drones` (fixed-pitch drones
  under a chanter, as the bagpipes use); and `blown` (a harmonic series, its attack, release,
  breath noise, low pass, drive and `bite_levels`). `falling_series` makes every harmonic, odd
  harmonics only, or quieter even ones. Its harmonics are whole multiples of the note, and it has
  no LFO of any kind.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not
  builds.
- Reuse the family's builders, which `double_reeds.py` keeps under their current names:
  `_double_reed` with `OBOE_LEVELS` (the oboes, heckelphone) or `BASSOON_LEVELS` (the bassoons,
  sarrusophone), `_folk_shawm` (the shawms, suona, zurna, bombarde, hichiriki, piri),
  `_capped_reed` (the crumhorns, rackett) and `_duduk`. The module writes each entry's build as
  an inline `partial(...)` of one of them. Add a builder only for a genuinely new sound, and
  give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the
  sheet is verbatim from a page the worker fetched, and every `Range:` passage is quoted from the
  raw page text (the plan's quote ruling). No request carries the owner's email or any personal
  data, in a header, a URL or a payload (#78, "Incidents and process").
- Code comments name committed files (`plans/data/instrument-audit/batch-11.tsv`), never the
  gitignored `build/` files (batch 9's fix).
- The 23 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 23. An existing entry changes only for a cited bug, reported to the
  owner; the 23 entries carry no source comment, so a range or a build that a fetched source
  contradicts is reported in #81, not changed here (batch 10's rule).
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown
  by a test, you should understand why it's happening and be concerned": a warning is a
  finding, and it must be understood before going on.
- Commits as batches 4 to 10: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this
  plan, never from memory. Write no `.md` file beyond those Task 6 names. Never use `git stash`:
  the stack is shared with other worktrees and sessions (#80, "Incidents and process"). Set work
  aside with a temporary commit instead.

## Review Focus

1. **A written range read as sounding.** Many double reeds are written transposed: the English
   horn and oboe da caccia sound a fifth below their part, the oboe d'amore a minor third below,
   the heckelphone, contrabassoon and contraforte an octave below, the piccolo oboe a minor third
   or a fourth above, every sarrusophone but the C contrabass from treble clef (the B-flat bass
   two octaves and a tone below), and the Catalan tenora and tible from their own keys. A range
   read off such a part is wrong by up to two octaves and a tone. Range ruling 2 takes a written
   range only with the transposition its own source states, the `Range:` passage shows the
   arithmetic, and the code check compares every range with the sheet.
2. **A width, a hedge or a comfortable span read as a range.** The pages mostly give widths
   ("a range of two and a half octaves" for the nadaswaram, "about two and one-half octaves" for
   the guanzi, "a tonal range of a ninth" for the rauschpfeife, "a range of a perfect twelfth"
   for the nicolo, "capable of producing two full octaves" for the taepyeongso) or hedges ("B♭3
   to about G6" for the oboe; the Baroque oboe's range "comfortably extends from C4 to D6"; the
   sarrusophones' "theoretical ranges"). Range ruling 5 takes none of them. Each SHIP and
   SOUND_ALIKE row's `notes` hold the passage and the derivation, and the form check refuses a
   ranged row without a `Range:` passage.
3. **An uncited range, or a citation a parser hid.** Batch 10's extractor stripped `<ref>`,
   `<sub>` and `<sup>` from the pages, which hid a citation and turned two octaves into letters.
   Wikipedia's sarrusophone size list carries no `<ref>` (the next paragraph, cited to Grove,
   gives only the written compass), nor does its crumhorn range table. Range ruling 10 takes a
   Wikipedia range only with a citation in the raw wikitext, and the quote check finds every
   `Range:` passage in the saved raw page with its citation.
4. **A sound-alike given a parent built with another bore.** A cylindrical double reed sounds
   unlike a conical one (the module's docstring: "a clarinet (a closed cylinder) favours odd
   harmonics, saxophones and double reeds (cones) have every harmonic"). The catalog builds
   `hichiriki` and `piri` as conical shawms (`_folk_shawm`) though the Piri page says "It has a
   cylindrical bore" (cited) and the Hichiriki page says so too (uncited). A guan, a mey or a
   balaban made their sound-alike would ship a cone under a cylinder's name. The form check
   refuses a sound-alike whose `hs` bore class differs from the bore its double reed parent is
   built as, and refuses `hichiriki` and `piri` as parents.
5. **The same instrument shipped twice, or a name decided twice.** `zurla`, `surna`, `sorna`,
   `surnay` and `zournas` may be the catalog's `zurna`; `mey`, `balaban` and `duduki` may be the
   `duduk`; `hne`, `hne gyi` and `hne galay` one instrument in two sizes; `rhaita`, `algaita`,
   `ghaita` and `ghayta`, `charumera` and `charamela`, `rauschpfeife` and `schreierpfeife`,
   `kortholt` and `sordun`, `bassanelli` and `bassanello` are pairs to tell apart. `fagott` is the
   German name of the modern bassoon, not only the dulcian the audit maps it to; `musette` is
   also the bagpipe (musette de cour); `dulciana` is an organ stop; `zukra` and `ciaramella` are
   bagpipes-audit rows too. Rules 3, 5 and 8 and the boundary ruling decide each, the form check
   refuses a name taken before the batch, and the code check finds every name exactly once.

---

## File Structure

- Create `src/glitchygames/audio/instruments/double_reeds.py`. It takes the "Double reeds"
  section of `winds.py` (`OBOE_LEVELS`, `BASSOON_LEVELS`, `_double_reed`, `_folk_shawm`,
  `_capped_reed`, `_duduk`, the 23 entries), unchanged, as `_DOUBLE_REED_BUILDS`. New builds go
  after the 23, a new builder is a module-level function beside the four, and `DOUBLE_REEDS =
  _DOUBLE_REED_BUILDS + DOUBLE_REED_SOUND_ALIKES`.
- Create `src/glitchygames/audio/instruments/double_reed_sound_alikes.py`, holding
  `DOUBLE_REED_SOUND_ALIKES`.
- Modify `winds.py` (the section and its double reed words leave; it keeps the clarinets,
  saxophones, bagpipes and free reeds), `registry.py` (it imports `DOUBLE_REEDS` from
  `double_reeds.py`; its place in `FAMILY_TABLES`, after the saxophones, doesn't change),
  `flutes.py`'s docstring and `instruments/__init__.py`'s sentence that name `winds.py`, and
  `aliases.py` (the batch's ALIAS rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5). The process-state guard
  (`tests/test_process_state_guard.py`) lists nothing from the double reed section today (its
  `winds.py` entry holds only `FREE_REED_LEVELS`), so nothing moves there.
- Create `plans/data/instrument-audit/batch-11.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #81), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #81):

- **Double reeds get their own module.** `winds.py` holds five families, and batch 9 moved the
  flutes out so that "the five reed families … their own batches can move the same way" (#79).
  Every family a batch has grown since batch 4 has a module of its own and a sibling sound-alikes
  module that names it ("The family's builds are in …"). No other module imports the double reed
  builders or level tables (only `registry.py` imports `DOUBLE_REEDS`), and the guard lists none
  of them, so the move is mechanical, and Task 1's before-and-after record checks it. Leaving
  them in `winds.py` would put a sixth batch's sound-alikes beside four families that no batch
  has grown yet.
- **Range ruling for double reeds.** A sourced range is the lowest and highest sounding notes
  that a fetched source states for the instrument:
  1. *Stated*: the source gives both notes as the range or compass, in note names with octaves
     (scientific `C4`, Helmholtz `c'` where the source names the notation or fixes the octave,
     or a named note whose octave the source fixes, as the Shehnai page's "from the A below
     middle C to the A one line above the treble clef"), or the lowest note and an exact span
     above it ("three octaves"), as batch 7 allowed.
  2. *Sounding*: a range in written pitch counts only when the same source, or the same maker's
     page for that model, states the transposition (an instrument in F sounding a perfect fifth
     below written, a contrabassoon an octave below). A range the source calls sounding, concert
     pitch, or the range of a non-transposing instrument is sounding as given. The derivation
     shows the arithmetic. Otherwise the row WAITs.
  3. *Extensions and extremes*: the stated compass, and nothing beyond it. A note in parentheses
     (the Bassoon infobox's "(A1) B♭1–E5 (A♭5)", the crumhorn table's modern extensions) is an
     extension: the range is the unparenthesised notes (batch 9's `csakan`). A top the source
     gives to the player ("for advanced players", "or higher"), an optional key or extension
     (a low-A bell), and notes made by underblowing or lipping ("lowered a perfect fourth by
     dropping the breath pressure") are extremes: the range is the compass without them, or the
     row WAITs.
  4. *Capped reeds*: a capped reed overblows little or not at all, so its source's compass is
     usually a ninth or so. It counts as any range does, under rules 1–3; a width alone ("a
     tonal range of a ninth") is not one.
  5. *Not a range*: a hedged span ("about", "approximately", "typically", "commonly", "usually",
     "practically", "can reach"), a span the source calls "comfortable" or "theoretical" (not the
     documented playable span the spec asks for), an extreme, a width with no pitches ("two and a
     half octaves", "a perfect twelfth"), note letters with no octaves, a key alone ("in C"), a
     tessitura, or one pitch.
  6. *Several keys or sizes*: the key or size that the source calls standard, usual or most
     common, from that source or a maker's model page in that key. A key or size in the row's own
     name (`e flat contrabass sarrusophone`, `great bass crumhorn`) is ranged in that key or size.
     A source giving one size two ranges ("Bb1–C3 or C2–D3", by maker) has given none, unless it
     calls one standard. With neither, the row WAITs (batch 7's rule for several tunings).
  7. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached,
     Encyclopaedia Iranica); a maker's catalogue or model page (Fox, Lorée, Marigaux, Rigoutat,
     Howarth, Yamaha, Buffet Crampon, Heckel, Mollenhauer, Moosmann, Püchner, Guntram Wolf,
     Eppelsheim, and the early-instrument makers such as Moeck and Eric Moulder, and the like); a
     museum's object record (MIMO, the Met, the Horniman, the Edinburgh University Collection of
     Historic Musical Instruments, the National Music Museum, the Bate Collection, the Museu de la
     Música de Barcelona, the Musée de la musique); or a conservatory or orchestration reference
     (the Vienna Symphonic Library's instrument pages). A retailer's listing (a maker's model sold
     on a shop's page included), a blog, a forum or a fingering chart sold by a shop is not a
     source. A maker's page for a model in another key ranges only that key. A range is never
     taken from a sibling size, the parent or the audit.
  8. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`, the spec's name) and
     nothing above C8, the piano's top and the form check's (WAIT `a range above C8`).
  9. *One note*: an instrument whose source gives it one note (the ottu: "designed to produce a
     single constant note") has no range, since the catalog needs lowest below highest. It WAITs
     `a sourced range`, with the note quoted in `notes`, and #81 carries #80's question whether a
     one-note instrument should ship as a fixed-pitch entry instead.
  10. *Cited*: a range from Wikipedia counts only when the raw wikitext shows a citation (a
      `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it, in its own infobox or table cell,
      or later in its own paragraph with no `{{citation needed}}` first, and its section is not
      tagged `{{Unreferenced section}}`. An uncited line is not a source (batch 9's `garklein
      recorder` and batch 10's `buccin`, both in #79 and #80).
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then
  the derivation.
- **Quotes come from the raw page.** Batch 10 found that an extractor that stripped `<ref>`,
  `<sub>` and `<sup>` hid a citation and two octaves (#80, "Incidents and process"). So no HTML
  or wikitext parser decides whether a passage is cited or which octave a mark names. Each worker
  saves the raw text of every page a ranged row's `Range:` passages come from as
  `build/batch-11-pages/<name, spaces as hyphens>--<n>.txt` (`n` from 1): for Wikipedia, the
  wikitext from `https://en.wikipedia.org/w/index.php?title=<Title>&action=raw`, fetched with
  `curl -s -A "glitchygames-instrument-audit/1.0"` (no other header, and nothing personal in it);
  for any other page, its HTML source. The `Range:` passages are copied from that raw text,
  markup and citations included. The sound passages may be the rendered text. The controller's
  quote check finds each `Range:` passage in the row's saved pages and, for a Wikipedia range
  source, its citation under rule 10.
- **A sound-alike's parent is built with the row's bore.** A double reed's bore is its sound's
  main trait (the module's docstring, Review Focus 4), and Hornbostel–Sachs names it (422.111
  cylindrical, 422.112 conical, 422.12 a double pipe). The `hs` cell of a SOUND_ALIKE row whose
  parent is a double reed must start with the bore class its parent is built as: `_double_reed`
  and `_folk_shawm` build cones (422.112), `_capped_reed` a capped cylinder (422.111), and the
  duduk's page names "The unflattened reed and cylindrical body" (422.111). A row with `hs` none
  is no double reed's sound-alike. `hs` comes from the instrument page's infobox or its own
  Hornbostel–Sachs category ("Single oboes with conical bore" is 422.112), or from a source
  sentence naming the bore of a single pipe. A capped reed's parent is a capped entry, and an
  uncapped reed's parent an uncapped one (the form check cannot see the cap; the review does).
- **The hichiriki and piri are never parents in this batch.** The catalog builds both as conical
  shawms (`_folk_shawm`), but the Piri page says "It has a cylindrical bore." (cited to the
  Encyclopedia of Korean Culture) and the Hichiriki page "has a cylindrical bore and thus its
  sound is similar to that of a clarinet" (tagged `{{citation needed}}`). A sound-alike would ship
  the cone under a new name. They are not approximations (no engine feature is missing: a
  cylindrical build exists), so they stay out of `APPROXIMATING_NAMES`, but the form check
  refuses them as parents, and #81 reports both builds as bugs for the owner to rule on. A row
  its source relates to them (a guan) SHIPs its own build, is a sound-alike of an entry built
  with its bore that its source also relates it to, or WAITs.
- **No new approximation.** No double reed joins `APPROXIMATING_NAMES`. The Hichiriki page says
  "The instrument is particularly noted for the embai ("salted plum seasoning"), a kind of
  pitch-gliding technique." (cited), and the Duduk page that players "bend" notes; a glide into a
  note is one `pitch_curve`, and a technique a player applies is an articulation (the spec's
  Non-goals: "Articulations and ensemble patches … are instrument settings"), not the
  instrument's sound. Circular breathing (the Zurna, Suona and Duduk pages) is a technique too:
  the engine sustains a note for as long as it is held. #81 asks the owner to confirm the
  hichiriki reading.
- **The pirouette is the shawm's trait already.** The Shawm page: "The shawm's conical bore and
  flaring bell, combined with the style of playing dictated by the use of a pirouette, gives the
  instrument a piercing, trumpet-like sound". `_folk_shawm` is that build ("loud, bright,
  hard-driven reeds"), so a pirouette is no reason for a new builder. A conical shawm with a
  pirouette is a sound-alike of the catalog shawm, `suona`, `zurna` or `bombarde` its source
  relates it to, nearest in register, unless another sourced trait sets it apart.
- **Reeds, keys and metal choose notes or carry the reed, not a new sound.** The number of reed
  blades (the Hne page's sextuple reed, the sralai's quadruple), keywork (the tenora's and tible's
  keys) and a metal body or bell count as sound traits only when a fetched source names their
  effect on the sound. A row whose source does WAITs `its own build` only if no builder can
  carry it (below); otherwise it may add a builder.
- **Drones, pairs and double pipes.** A double reed that sounds one note (the ottu) waits under
  range ruling 9. A double pipe (H-S 422.12, the aulos) is one instrument of two pipes: the
  engine can sound a second pipe as a source a fixed interval away or as a drone (`with_drones`),
  so it ships only when its source states both pipes' notes or the drone's tuning, and WAITs `a
  sourced drone tuning` (batch 7's name) when the source says one pipe drones without its tuning.
  Instruments its source says are "always played in pairs" by two players (the sopila) are each
  an instrument of their own, decided by its size's range; the pair is an ensemble. A second
  player's drone (the duduk's dum) is not part of the instrument.
- **A new builder only for a sourced acoustic trait.** A builder is new when a fetched source
  names a trait none of the family's builds has (a bore, a cap, a bell, a material, a reed). Its
  own test checks that trait, as batch 2's `test_the_pianet_settles_from_a_bright_strike` checks
  its own. Its other numbers are sound design, marked so in the comment. It is a module-level
  function in `double_reeds.py` beside the four, in their style (`def _name(*, …) -> Instrument:
  return blown(...)`), and each entry calls it as an inline `partial(...)`. A module-level level
  table is a tuple of floats, as `OBOE_LEVELS` is. Neither is process state, so the guard gets
  no line; if it asks for one, that is a finding to read before writing any reason. Half A may
  add a builder only for a trait that no half-B row names (capped reeds, metal bodies, the
  heckelphone's and Baroque oboe's bores are half A's), and half B the reverse (uncapped
  cylindrical folk reeds, metal bells, multiple reeds, double pipes), so the two never add the
  same builder.
- **Sizes, keys and the standard size.** A size or key of an existing instrument (the
  sarrusophones, `piccolo heckelphone`, `terz heckelphone`, `sopranino shawm`, `great bass
  shawm`, `great bass crumhorn`, `hne gyi`, `hne galay`) is a SOUND_ALIKE of the entry nearest in
  register that its source relates it to, with its own range under the ruling, or it WAITs. The
  catalog's `sarrusophone` is the C contrabass ("Contrabass sarrusophone in C"), so the other
  sarrusophone sizes relate to it. A candidate that its source makes a catalog entry's own
  instrument under another name (the musette, if the source calls the piccolo oboe the musette;
  the pommer, if the source calls the bass shawm the bass pommer) is ALIAS of that entry. Any
  size that ships joins its chain in `test_sized_families_descend_from_highest_to_lowest`, and a
  new chain is added once a size ships beside two or more catalog sizes that one source names as
  one family (the shawms, the crumhorns, the oboes, the heckelphones, the sarrusophones with
  `sarrusophone`), in descending order of lowest note.
- **No unpitched or mechanical double reed.** Every double reed parent is pitched, so a
  sound-alike is pitched, and no candidate plays itself. The form check refuses an unpitched SHIP
  or SOUND_ALIKE row and any `tags`. The batch table's row needs no unpitched names.
- **The boundary hand-offs.** A row whose fetched source makes it a bagpipe (a bag, as the Zukra
  page's "is a Libyan bagpipe") is DROP "belongs to bagpipes: <the source's words>; the bagpipes
  batch decides it". `ciaramella` is decided here only if its fetched page makes it a shawm
  played by mouth; if the page makes the name the bagpipe, it is that DROP. A row whose source
  makes it a single reed (a clarinet or saxophone) or a lip reed is DROP naming that family. An
  alias name that a source also gives to an instrument of another family (`musette`, the
  bagpipe; `dulciana`, the organ stop) is DROP "an ambiguous name: also <the instrument>
  (<family>)", and the unambiguous name (`oboe musette`) carries the alias. Task 6 tells the
  bagpipes and organs batches, in #70, which of their names this batch decided.
- **Generic terms.** An alias name that its source gives to a class of instruments rather than
  one (the audit marks `pi` "generic term"; `guan` may name the northern and Cantonese guan
  together) is DROP "a generic term for <the instruments>", unless the source makes it one
  instrument's name.
- **One-offs, artefacts and unsourced rows are dropped** (batch 5's ruling): DROP "a one-off
  instrument, not a type a game would ask for" for one maker's or player's design that is not in
  production (a single prototype, a comic invention such as the tromboon, if its page says so),
  and DROP "no fetched source describes it" when no page describes the row (the audit itself
  found no page for `serpentine bassoon`). An instrument a maker's current model page offers, or
  a museum holds as a type, is not a one-off, however few were made (#80's `firebird trumpet`
  reading).
- **Two halves, as explicit lists.** Half A, the orchestral, modern and early European double
  reeds, is these 34 candidates. Half B, the folk and traditional shawms and oboes of Europe, the
  Middle East, Africa and Asia, with the ancient aulos, is the other 46. The list decides the
  half: a row whose source shows another kind stays in its half.
  `alto sarrusophone`, `baritone sarrusophone`, `baroque oboe`, `bass sarrusophone`,
  `bassanelli`, `bassett nicolo`, `contrabass oboe`, `contrabass sarrusophone bb`, `contrabass
  sarrusophone eb`, `contraforte`, `cornamuse`, `doppioni`, `dulcian`, `great bass crumhorn`,
  `great bass shawm`, `hautbois de poitou`, `kortholt`, `lupophone`, `nicolo`, `oboe da caccia`,
  `piccolo heckelphone`, `piccolo oboe`, `rauschpfeife`, `rothphone`, `schreierpfeife`,
  `serpentine bassoon`, `sopranino sarrusophone`, `sopranino shawm`, `soprano sarrusophone`,
  `sordun`, `tenor sarrusophone`, `tenoroon`, `terz heckelphone`, `tromboon`.
  The 36 alias names go with their target's half. Half A has 13: `cor anglais`, `baritone oboe`,
  `musette`, `oboe musette`, `fagott`, `curtal`, `courtaud`, `bajon`, `doucaine`, `dulciana`,
  `bassanello`, `pommer`, `cervelas`. Half B has 23: `bombard`, `nagaswaram`, `nadhaswaram`,
  `nataswaram`, `shahnai`, `sanayi`, `sahanai`, `surna`, `sorna`, `surnay`, `zournas`, `hojeok`,
  `hojok`, `nallari`, `saenap`, `guan`, `kuan`, `haidi`, `laba`, `ghaita`, `ghayta`, `pi`,
  `mukhaveene`. So half A's sheet holds 47 rows and half B's 69. The duplicates and near-pairs
  fall within one half (`rauschpfeife` and `schreierpfeife`, `kortholt` and `sordun`,
  `bassanelli` and `bassanello`, `piccolo oboe` and the two musette names in A; `hne` and its
  sizes, `mey`, `balaban` and `duduki`, `rhaita`, `algaita` and the two ghaita names, `guanzi`,
  `houguan`, `guan` and `kuan`, `nadaswaram` and `ottu` in B).
- **The halves run in parallel.** A parent or alias target is a catalog name from before the
  batch, or a SHIP or SOUND_ALIKE row of the same half, never a row of the other half. So Task 4
  needs nothing from Task 2. Half B drafts to a build file, which is appended to the sheet once
  half A is committed. The form check accepts a row that the code already holds with the same
  target or parent (batch 7's lesson).
- **A held-back guard.** As batch 10's `BRASS_HELD_BACK`, this batch's guard is
  `DOUBLE_REED_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row
  whose reason is an engine feature or a build of its own (any reason but `a sourced range`), and
  every alias row that waits for such a row. A test refuses each of its names in the catalog and
  the aliases, and the code check compares the table with the sheet.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task still fills `DOUBLE_REED_HELD_BACK` with the half's
  held rows and runs the code check, which must pass; its other steps are skipped, and Task 6
  records the skip in #81.
- **Out of scope:** the audit's "Gaps you could not close" (the quint and quart bassoons,
  fagottino or octavin, subcontrabassoon and reed contrabass; the dulcian, rackett and shawm sizes
  beyond the candidates; the Korean piri variants, Okinawan rappa, Philippine and Uzbek and Tajik
  surnay, Nepalese sahanai, Mongolian and Tibetan shawms; MIMO, the Met, the Horniman and Grove
  unconsulted). Task 6 lists them in #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of these files is committed.

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-11-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-11-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
  Expected: `names before 791` (690 entries and 101 aliases).

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /double reed/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /double reed/ {print tolower($1)}' round-1/merged-missing.tsv
} | LC_ALL=C sort -u > ../../../build/batch-11-candidates.txt
cd ../../..
```
  Write the plan's 34 half-A names, one per line, to `build/batch-11-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-11-candidates.txt build/batch-11-half-a.txt > build/batch-11-half-b.txt`
  and `wc -l build/batch-11-*.txt`.
  Expected: 80 candidates, 34 in half A, 46 in half B, and
  `LC_ALL=C comm -13 build/batch-11-candidates.txt build/batch-11-half-a.txt` prints nothing.

- [ ] **Step 3: The form check,** `build/batch-11-form-check.py`:
```python
"""Batch 11's sheet form check: uv run python -I build/batch-11-form-check.py SHEET.

Batch 10's form check (plans/2026-11-12-instrument-catalog-batch-10-implementation.md, "Before
the tasks" Step 3) with batch 11's changes (batch 11's plan, "Before the tasks"): the double reed
family, and a sound-alike's bore class matching the bore its double reed parent is built as.
"""

import csv
import re
import sys

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note

STATUSES = ('SHIP', 'SOUND_ALIKE', 'WAIT', 'ALIAS', 'DROP')
# tests/audio/test_instrument_catalog.py APPROXIMATING_NAMES (unchanged by batch 11)
APPROXIMATING_NAMES = {
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
    'dizi', 'didgeridoo',
}
# The bore each double reed entry is built as (Hornbostel-Sachs 422.112, a single oboe with a
# conical bore; 422.111, with a cylindrical bore): _double_reed and _folk_shawm build cones,
# _capped_reed a capped cylinder, and the duduk's page names its cylindrical body
CONE, CYLINDER = '422.112', '422.111'
BUILT_BORE = {
    name: CONE
    for name in (
        'oboe', 'oboe d amore', 'english horn', 'bass oboe', 'heckelphone', 'bassoon',
        'contrabassoon', 'sarrusophone', 'soprano shawm', 'alto shawm', 'tenor shawm',
        'bass shawm', 'suona', 'zurna', 'bombarde', 'hichiriki', 'piri',
    )
} | {
    name: CYLINDER
    for name in (
        'soprano crumhorn', 'alto crumhorn', 'tenor crumhorn', 'bass crumhorn', 'rackett',
        'duduk',
    )
}
# Built as cones though their pages name a cylindrical bore: never a parent (batch 11's plan)
BUILT_AGAINST_THEIR_BORE = {'hichiriki', 'piri'}
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
with open('build/batch-11-names-before.txt', encoding='utf-8') as before_file:
    names_before = set(before_file.read().split('\n')) - {''}
ship_rows = {row['name']: row for row in rows if row['status'] == 'SHIP'}
alikes = {row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'}
parents = set(ship_rows) | {
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


def bore_matches(row):
    """A sound-alike of a double reed has the bore class its parent is built as."""
    parent = row['alias_of']
    if parent in BUILT_AGAINST_THEIR_BORE:
        return False
    if parent in ship_rows:
        parent_bore = ship_rows[parent]['hs'][:7]
        return parent_bore[:1].isdigit() and row['hs'].startswith(parent_bore)
    if parent in BUILT_BORE:
        return row['hs'].startswith(BUILT_BORE[parent])
    # A parent in another family: its source relates them, and the review checks it
    return True


names = [row['name'] for row in rows]
bad = [row['name'] for row in rows if not pattern.fullmatch(row['name'])
       or row['status'] not in STATUSES
       or row['family'] != 'double reeds'
       or not row['audit_name']
       or not (row['hs'] == 'none' or row['hs'][:1].isdigit())
       or row['tags'] != ''
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)))
       or (row['status'] in {'SHIP', 'SOUND_ALIKE', 'ALIAS'} and taken(row))
       or (row['status'] == 'SOUND_ALIKE'
           and (row['alias_of'] not in parents or row['alias_of'] in APPROXIMATING_NAMES
                or not parent_pitched(row['alias_of']) or not bore_matches(row)))
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

- [ ] **Step 4: The quote check,** `build/batch-11-quote-check.py`:
```python
"""Batch 11's quote check: uv run python -I build/batch-11-quote-check.py SHEET.

Batch 11's plan, "Quotes come from the raw page": every SHIP and SOUND_ALIKE row's Range:
passages are quoted between « and » from the raw text of the pages saved as
build/batch-11-pages/<name, spaces as hyphens>--<n>.txt. Each passage must be in one of them,
whatever its line breaks, and a Wikipedia range source's passage must have a citation after it
in its own cell (a passage starting with "|") or its own paragraph, before any uncited tag.
"""

import csv
import re
import sys
from pathlib import Path

PAGES = Path('build/batch-11-pages')
CITATION = re.compile(r'<ref[ >/]|\{\{\s*(sfn|harvnb|r)\s*\|', re.IGNORECASE)
UNCITED_TAG = re.compile(r'\{\{\s*(citation needed|cn|fact)\s*[|}]', re.IGNORECASE)


def located(page, passage):
    """The passage's start and end in the raw page, whatever its line breaks, or None."""
    words = passage.split()
    match = re.search(r'\s+'.join(re.escape(word) for word in words), page) if words else None
    return None if match is None else (match.start(), match.end())


def cited(page, start, end, passage):
    """A citation follows the passage in its cell or paragraph, before any uncited tag."""
    stop = page.find('\n' if passage.lstrip().startswith('|') else '\n\n', end)
    following = page[start:] if stop == -1 else page[start:stop]
    citation = CITATION.search(following)
    uncited = UNCITED_TAG.search(following)
    return citation is not None and (uncited is None or uncited.start() > citation.start())


with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
bad = []
for row in rows:
    if row['status'] not in {'SHIP', 'SOUND_ALIKE'}:
        continue
    slug = row['name'].replace(' ', '-')
    pages = [path.read_text(encoding='utf-8') for path in sorted(PAGES.glob(f'{slug}--*.txt'))]
    passages = re.findall(r'«(.+?)»', row['notes'].partition('Range:')[2], flags=re.DOTALL)
    if not pages or not passages:
        bad.append((row['name'], 'no saved page or no «passage»'))
        continue
    for passage in passages:
        spans = [(page, located(page, passage)) for page in pages]
        found = [(page, span) for page, span in spans if span is not None]
        if not found:
            bad.append((row['name'], 'not in the raw page: ' + passage[:60]))
        elif 'wikipedia.org' in row['range_source'] and not any(
            cited(page, span[0], span[1], passage) for page, span in found
        ):
            bad.append((row['name'], 'uncited: ' + passage[:60]))
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  It checks what can be checked mechanically. A worker still applies range ruling 10 in full (an
  `{{Unreferenced section}}` tag, a citation that covers another sentence).

- [ ] **Step 5: The code check,** `build/batch-11-code-check.py`:
```python
"""Batch 11's code check: uv run python -I build/batch-11-code-check.py SHEET.

Batch 10's code check with batch 11's changes (batch 11's plan, "Before the tasks"): every row is
checked (no candidate or alias name is in the catalog or the aliases before the batch, so no row
is exempt), the held-back guard is compared with the sheet, and the builds, sound-alikes and
aliases follow the sheet's order. The test file's tables are read as literals, without importing
the tests. A one-off check may read the private _DOUBLE_REED_BUILDS; a test may not.
"""

import ast
import csv
import sys

from glitchygames.audio import instruments
from glitchygames.audio.instruments.double_reed_sound_alikes import DOUBLE_REED_SOUND_ALIKES
from glitchygames.audio.instruments.double_reeds import _DOUBLE_REED_BUILDS

TEST_FILE = 'tests/audio/test_instrument_catalog.py'
EXISTING_COUNT = 23


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
ship_names = [row['name'] for row in rows if row['status'] == 'SHIP']
alike_names = [row['name'] for row in rows if row['status'] == 'SOUND_ALIKE']
assert test_table('DOUBLE_REED_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'DOUBLE_REED_HELD_BACK'
assert test_table('NEW_DOUBLE_REED_NAMES') == ship_names, 'NEW_DOUBLE_REED_NAMES'
assert list(test_table('DOUBLE_REED_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'DOUBLE_REED_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in _DOUBLE_REED_BUILDS[EXISTING_COUNT:]] == ship_names, 'build order'
assert [entry.name for entry in DOUBLE_REED_SOUND_ALIKES] == alike_names, 'sound-alike order'
sheet_aliases = [row['name'] for row in rows if row['status'] == 'ALIAS']
assert [name for name in instruments.ALIASES if name in set(sheet_aliases)] == sheet_aliases, (
    'alias order'
)
print('matches', len(rows), 'rows')
```
  It cannot run until Task 1 has created `double_reeds.py`, `double_reed_sound_alikes.py` and
  the test tables.

---

### Task 1: Double reeds in their own module, unchanged; their sound-alikes module; the batch table's row; the held-back guard

**Files:**
- Create: `src/glitchygames/audio/instruments/double_reeds.py`,
  `src/glitchygames/audio/instruments/double_reed_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/winds.py`, `registry.py`, `flutes.py` (docstring),
  `__init__.py` (one docstring sentence)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `DOUBLE_REEDS: Final[tuple[CatalogEntry, ...]] = _DOUBLE_REED_BUILDS +
  DOUBLE_REED_SOUND_ALIKES` in `double_reeds.py`, with `OBOE_LEVELS`, `BASSOON_LEVELS`,
  `_double_reed`, `_folk_shawm`, `_capped_reed` and `_duduk` there under their current names.
  `DOUBLE_REED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test file gains
  `EXISTING_DOUBLE_REED_NAMES: frozenset[str]` (the 23); `NEW_DOUBLE_REED_NAMES: list[str]`,
  `DOUBLE_REED_SOUND_ALIKE_PARENTS: dict[str, str]` and `DOUBLE_REED_HELD_BACK: dict[str, str]`,
  all empty here, for Tasks 3 and 5 to fill; `test_no_double_reed_name_held_back_for_a_feature_is_listed`;
  and the row `Family.DOUBLE_REEDS: BatchFamily(EXISTING_DOUBLE_REED_NAMES,
  NEW_DOUBLE_REED_NAMES, DOUBLE_REED_SOUND_ALIKE_PARENTS)` in `BATCH_FAMILIES`. Also
  `build/double-reed-builds-before.txt`.

- [ ] **Step 1: Record the family's builds.** Run batch 4's Task 1 Step 1 command with
  `family='double reeds'` and `build/double-reed-builds-before.txt`. Expected: `recorded 23`.

- [ ] **Step 2: Write the tests.** Between the flute lists and the brass lists (table order), add
  `EXISTING_DOUBLE_REED_NAMES` (the 23 names, one per line, in catalog order, with the comment
  "# The 23 double reeds that predate batch 11: their shared builds predate the anti-goal rule"),
  then `NEW_DOUBLE_REED_NAMES: list[str] = []` and `DOUBLE_REED_SOUND_ALIKE_PARENTS: dict[str,
  str] = {}`, each commented as batch 10's lists are. Put the double reeds row between the flutes
  and brass rows in `BATCH_FAMILIES`, which is table order. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the closing list gains
  `+ list(DOUBLE_REED_SOUND_ALIKE_PARENTS)` between the flutes' and the brass lines, and its
  comment reads "flutes, double reeds, brass, …". After
  `test_no_brass_name_held_back_for_a_feature_is_listed`, add:
```python
# Every name plans/data/instrument-audit/batch-11.tsv holds back for an engine feature or a build
# of its own, with its waits_for: the WAIT rows whose reason is not "a sourced range", and the
# alias rows that wait for one of them, in the sheet's order. None ships under that name or as an
# alias until the engine or the build exists (decision 4; batch 11). The test matches exact names
DOUBLE_REED_HELD_BACK: dict[str, str] = {}


def test_no_double_reed_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a double reed the sheet holds back for a feature."""
    assert set(DOUBLE_REED_HELD_BACK) & set(instruments.names()) == set()
    assert set(DOUBLE_REED_HELD_BACK) & set(instruments.ALIASES) == set()
```

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back" -v`
  Expected: PASS, with the ID `[double reeds]` second. These are guards: they pass now and hold
  the later tasks.

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move `winds.py`'s
  "Double reeds" section into `double_reeds.py` unchanged, with the tuple renamed
  `_DOUBLE_REED_BUILDS`, and define `DOUBLE_REEDS` after it as the concatenation, importing
  `DOUBLE_REED_SOUND_ALIKES`. The new module docstring's first line is "Double reeds: oboes,
  bassoons, heckelphones and sarrusophones, shawms, capped reeds and the duduk." It says what the
  family holds (H-S 422.1, a double reed on a conical or cylindrical pipe), takes `winds.py`'s
  double reed words (sounding pitch, Adler and the Vienna Symphonic Library, "double reeds
  (cones) have every harmonic and are brighter"), and says that the sound-alikes are in
  `double_reed_sound_alikes.py` and the other reed families in `winds.py`. `winds.py`'s docstring
  drops "double reeds" from its first line and its cone sentence ("saxophones … (cones) have
  every harmonic"), and names `double_reeds.py` beside `flutes.py`. Its imports stay as long as
  its families use them. `double_reed_sound_alikes.py` gets the empty table and
  `brass_sound_alikes.py`'s docstring with "Double reeds'" for "Brass's" and ending "The family's
  builds are in ``double_reeds.py``." For the empty table it imports only what ruff accepts
  (batch 10's Task 1 put `CatalogEntry` under `TYPE_CHECKING`); the task that adds the first
  sound-alike makes `CatalogEntry` and `Family` runtime imports, as `brass_sound_alikes.py` has
  them (#80's parked minor). Point `registry.py` at the new module. In `flutes.py`'s
  docstring, "The reed families are in the sibling module ``winds.py``." becomes "The double reeds
  are in the sibling module ``double_reeds.py``, the other reed families in ``winds.py``."; in
  `__init__.py`'s docstring, "``winds.py`` keeps the five reed families." becomes "``winds.py``
  keeps the clarinets, saxophones, bagpipes and free reeds." If the process-state guard then asks
  for an entry for `_DOUBLE_REED_BUILDS`, `DOUBLE_REEDS` or `DOUBLE_REED_SOUND_ALIKES`, that is a
  finding: `flute_sound_alikes.py` and `brass_sound_alikes.py` needed none, so read why before
  writing any reason.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `family='double reeds'` and `build/double-reed-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
SKIP=replay-metrics git commit -m "Instrument catalog: double reeds in their own module, unchanged; their sound-alikes module; the held-back guard" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The orchestral, modern and early European double reeds sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. Put no personal data in any request, in a header,
a URL or a payload. Save each ranged row's raw pages under the plan's quote ruling. A list or
category page is a source for a name only (and a Hornbostel–Sachs category for the bore class).
The sound, the title and the range come from the instrument's own page, or from an encyclopedia,
maker, museum or conservatory under range ruling 7. The audit's "VERIFIED" rows and its quotes
are leads, not sources, so fetch them. Never use `git stash`. This task may start as soon as the
controller has written the shared files, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-11.tsv`
- Create (not committed): `build/batch-11-half-a.tsv`, and the raw pages in
  `build/batch-11-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `double-reeds.md` ("Rejected or corrected
  proposed entries", "Aliases", "Range checks", "Gaps you could not close"); `bagpipes.md` and
  `organs.md` for the boundary names; `batch-1.tsv` to `batch-10.tsv`;
  `build/batch-11-names-before.txt`, `build/batch-11-half-a.txt`, `build/batch-11-half-b.txt`,
  `build/batch-11-form-check.py` and `build/batch-11-quote-check.py`.
- Produces: `batch-11.tsv` with batch 10's header:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `double reeds` on every row, and
  `tags` is empty on every row. A SHIP or SOUND_ALIKE row has `lowest`, `highest`,
  `range_source`, and `notes` holding `Range:` with its «raw passages». `hs` is the
  Hornbostel–Sachs class a fetched source gives (`422.1…`), else `none`. A candidate row's
  `audit_name` is its name in `build/batch-11-candidates.txt`; an alias row's is its audit line.
  Also `build/batch-11-half-a.tsv`, the half as committed, which Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-11-half-a.txt`'s order,
  then one per half-A alias name (13), in the plan's order.

  The rules are batch 10's, changed for this family:

  1. **SHIP** only with name, title, range and sound from fetched sources. Quote in `notes` the
     passage that describes the sound or construction (bore, cap, reed, bell, material, keys)
     and, after `Range:`, the «raw passages» that give the range, then the derivation under the
     range ruling. The `builder` cell gives the builder (one of the family's four with its
     levels, or a new builder under the plan's ruling). It says which values come from the source
     and which are sound design.
  2. **SOUND_ALIKE**: a verified instrument that rule 7 finds would sound like an existing entry
     or a SHIP row of this half. `alias_of` is its parent. The `notes` begin "Sound-alike:",
     quote the source's description, and say why that entry is the nearest (for a size or key:
     the entry its source relates it to, nearest in register). It has its own range under the
     ruling, and its `hs` bore class is its parent's built bore (the plan's bore ruling). The
     parent is a catalog name or a SHIP row of this half. It is never another sound-alike, never
     one of `APPROXIMATING_NAMES`, never `hichiriki` or `piri`, and in another family only when
     the source relates them.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row of this half. If the target waits, the row is WAIT with `waits_for`
     `its target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is
     dropped". An ambiguous name or a generic term is DROP under the plan's rulings.
  4. **WAIT** when the identifying sound needs a feature the engine lacks, named in `waits_for`
     with the source quoted, under the plan's decisions (`sub-audio fundamentals`, `a range above
     C8`, `a sourced drone tuning`, `more than four sources`, `its own build` and the rest named
     in Global Constraints), or `a sourced range`. The feature must be the sound the source
     describes, not a technique a player applies (the plan's "No new approximation"). Any other
     name is allowed only with the source quoted, and Task 6 lists it in #81.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and for
     a bagpipe use the boundary ruling's words), is a one-off, or is already decided: in the
     catalog under that name (name the entry), an alias already (name its target), or a row of an
     earlier sheet (name the sheet and its status).
  6. A row the audit marks "(memory)" or "pointer only, not fetched" has no sourced sound or
     range yet. Fetch the instrument's own page; the audit's URL is a lead. If no page can be
     found, the row is DROP "no fetched source describes it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='double reeds'))"`
     and the builds in `double_reeds.py`) and every SHIP row above it. If no sourced trait (bore,
     cap, reed, bell, material) makes it sound different, it is a SOUND_ALIKE under rule 2. A
     number chosen only to differ does not count, and neither a range nor the way notes are
     chosen (keys, finger holes, a pirouette) is a sound trait.
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.

  This half's own cases:

  - **Oboes.** The Oboe page: "the musette (also called oboe musette or piccolo oboe), the
    sopranino member of the family (it is usually pitched in E♭ or F above the oboe)": `piccolo oboe` is the row, `oboe musette` its ALIAS if the source
    says so, and `musette` DROP under the ambiguity ruling. `baritone oboe` and `cor anglais` are
    ALIAS of `bass oboe` and `english horn` on a cited page. `oboe da caccia` relates to
    `english horn` only if its source says so. `baroque oboe`'s page range is "comfortably"
    stated and uncited, so it needs a maker or museum range. `contrabass oboe` is not a one-off
    if a maker's page offers it.
  - **Bassoons.** `tenoroon` and `contraforte` relate to `bassoon` and `contrabassoon` only
    where their source does; a source's sound difference ("louder, more even", a wider bore) is a
    trait under rule 7. A contraforte's written range sounds an octave below.
  - **Heckelphones.** `piccolo heckelphone`, `terz heckelphone` and `lupophone` relate to
    `heckelphone` where their source does, each with its own range.
  - **Sarrusophones.** Each size relates to the catalog's `sarrusophone` (the C contrabass) and
    is named with its key first where it has one. The Sarrusophone page's size list ("the
    following theoretical ranges", with sounding notes in parentheses) carries no citation, and
    "theoretical" is not a range, so a size ships only with a cited sentence, a maker or a museum
    giving its sounding range. The B-flat contrabass's "A{{flat}}{{sub|0}}, one semitone below
    A{{sub|0}}" is below the catalog's floor: WAIT `sub-audio fundamentals` if its range is
    otherwise sourced, else `a sourced range`. `rothphone` relates to `sarrusophone` only if its
    source says so.
  - **Renaissance shawms.** `sopranino shawm` and `great bass shawm` relate to the nearest
    catalog shawm. The Shawm page's `nicolo` ("A tenor shawm in C … with a range of a perfect
    twelfth") gives a key and a width, not a range. `bassett nicolo` "conceals a mostly
    cylindrical bore", so it is no shawm's sound-alike. `hautbois de poitou` and `pommer` are
    decided on their pages.
  - **Capped reeds.** `great bass crumhorn` relates to the catalog crumhorns, but the Crumhorn
    page's table gives it two ranges, uncited ("B{{Music|flat}}<sub>1</sub>–C<sub>3</sub> … or
    C<sub>2</sub>–D<sub>3</sub>"): it needs a maker's range. `cornamuse`, `kortholt` and `sordun`
    are capped cylinders where their source says so; `rauschpfeife` and `schreierpfeife` are
    capped cones ("their conical-bore relatives the rauschpfeife and shawm", the Crumhorn page),
    so neither is a crumhorn's sound-alike. A capped cone that no builder makes may add one under
    the plan's ruling (this half's trait).
  - **Dulcians.** `dulcian`, `doppioni` and `bassanelli` are decided on their pages, and their
    alias names each on its own: `fagott` is the German name of the bassoon (a cited page decides
    its target, `bassoon` or `dulcian`), `doucaine` may be its own instrument (then DROP "a
    distinct instrument with no candidate row"), and `dulciana` is DROP under the ambiguity ruling
    if its page is the organ stop. `cervelas` relates to `rackett` on a cited page.
  - **Novelties.** `tromboon` (Wikipedia redirects it to P. D. Q. Bach's page) and `serpentine
    bassoon` follow the one-off and unsourced rulings.

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-11-form-check.py plans/data/instrument-audit/batch-11.tsv`
  and `uv run python -I build/batch-11-quote-check.py plans/data/instrument-audit/batch-11.tsv`.
  Expected: `47 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-11.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-11-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-11-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
"
```
  Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-11.tsv build/batch-11-half-a.tsv
git add plans/data/instrument-audit/batch-11.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 11's verification sheet, the orchestral, modern and early European double reeds" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The orchestral, modern and early European double reeds

**Files:**
- Modify: `double_reeds.py` (new builds after the 23, any new builder beside the four),
  `double_reed_sound_alikes.py` (`DOUBLE_REED_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with
  its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-11-half-a.tsv` (half A as committed), Task 1's tables and
  `build/batch-11-code-check.py`.
- Produces: `NEW_DOUBLE_REED_NAMES`, `DOUBLE_REED_SOUND_ALIKE_PARENTS` and
  `DOUBLE_REED_HELD_BACK` filled with this half's rows, which Task 5 extends.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills
only `DOUBLE_REED_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_DOUBLE_REED_NAMES` with one name per SHIP row
  and `DOUBLE_REED_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row, each in the
  sheet's order. Fill `DOUBLE_REED_HELD_BACK` with one `name: waits_for` per held row (the plan's
  held-back decision: every WAIT row whose reason is not `a sourced range`, and every `its
  target, <name>` row whose target is held), in the sheet's order. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, in the sheet's order, with a docstring sentence
  for batch 11. A shipped size joins or starts its chain in
  `test_sized_families_descend_from_highest_to_lowest` under the plan's sizes ruling, in
  descending order of lowest note (a shipped `great bass shawm` starts `('soprano shawm', 'alto
  shawm', 'tenor shawm', 'bass shawm', 'great bass shawm')`). A new builder gets its own test of
  the trait it exists for, named for the trait (as batch 2's
  `test_the_pianet_settles_from_a_bright_strike`).

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or descend or held_back" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the
  held-back test passes.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in
  `DOUBLE_REED_SOUND_ALIKES`, in the sheet's order, under a section comment naming
  `plans/data/instrument-audit/batch-11.tsv` as `brass_sound_alikes.py`'s does, each a
  `CatalogEntry(name, title, Family.DOUBLE_REEDS, lowest, highest, sounds_like=parent)`. Above
  each, put a comment with its `sound_source` and `range_source` URLs, the quoted passages and
  the range's derivation, as `brass_sound_alikes.py`'s entries have. A SHIP row is a
  `CatalogEntry` after the 23 in `_DOUBLE_REED_BUILDS`, carrying the same comment and marking the
  values that are sound design. Each ALIAS row goes in `aliases.py` under a "Batch 11's double
  reeds" section, in the sheet's order, with its URL and quote. Comments name only committed
  files.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is a
  finding about the range or the build. Check it against the source, and never trim the range to
  pass. Then run:
  `uv run python -I build/batch-11-code-check.py build/batch-11-half-a.tsv`
  Expected: `matches 47 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 11's orchestral, modern and early European double reeds, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The folk and traditional shawms and oboes sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-11-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-11-pages/`
- Modify: `plans/data/instrument-audit/batch-11.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-11-form-check.py`,
  `build/batch-11-quote-check.py` and `build/batch-11-half-b.txt`.
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-11-half-b.txt`'s order, then one per half-B
alias name (23), in the plan's order. A parent or alias target is a catalog name or a SHIP or
SOUND_ALIKE row of this half, never a half-A row. These rules apply to this half on top of Task
2's:

- **Pirouette shawms.** A conical shawm (`gralla`, `dolcaina`, `chirimia`, `charamela`, `gaita
  navarra`, `piffero`, `ciaramella`, `hirtenschalmei`, `sopila`, `zurla`, `mizmar`, `zamr`,
  `salamiya`, `rhaita`, `algaita`, `charumera`, `ken bau`, `serunai`, `selompret`, `tarompet`,
  `sarune`, `sralai`, the `pi` sizes, the `hne` sizes, `gyaling`, `taepyeongso`, `shehnai`,
  `nadaswaram`, `kuzhal`, `sundari`) is a SOUND_ALIKE of the catalog shawm, `suona`, `zurna` or
  `bombarde` that its source relates it to, nearest in register, when its source gives a range
  (the plan's pirouette ruling), an ALIAS when its source calls it another name for that entry,
  and otherwise WAIT. The Shehnai page's "range of two octaves, from the A below middle C to the
  A one line above the treble clef (A3 to A5 …)" is in a paragraph cited to the Met: check it
  under range ruling 10 in the raw wikitext.
- **Other names of catalog entries.** `zurla`, `surna`, `sorna`, `surnay` and `zournas` are ALIAS
  of `zurna`, `haidi` and `laba` of `suona` ("also called … laba or haidi", the Suona page), and
  `bombard` of `bombarde`, each on a cited page that gives it as that instrument's name (`laba`
  also means a trumpet or horn in Chinese: if its page says so, the ambiguity ruling decides it).
- **Cylindrical reeds.** `mey`, `balaban` and `duduki` relate to `duduk` where their source does
  (sound-alikes with their own range, or aliases if the source calls them the same instrument).
  `guanzi` and `houguan` (and the alias names `guan`, `kuan`) are cylindrical by their source and
  related to the hichiriki and piri, which are never parents here: each SHIPs its own build, is a
  sound-alike of `duduk` if its source relates them, or WAITs. An uncapped cylindrical builder
  is this half's trait to add, under the plan's ruling.
- **Drones, pairs and double pipes.** `ottu` ("designed to produce a single constant note") waits
  under range ruling 9. `aulos` follows the double-pipe ruling. `sopila` is one instrument per
  size; the pair's "Istrian scale" is not a range.
- **The bagpipe boundary.** `zukra` (the Zukra page: "is a Libyan bagpipe") is DROP "belongs to
  bagpipes: 'is a Libyan bagpipe'; the bagpipes batch decides it". `ciaramella` follows the
  boundary ruling on its fetched page.
- **Transposing folk shawms.** The tenora and tible are keyed shawms of the cobla (Wikipedia's
  "Catalan shawm" page): a range read from their parts follows range ruling 2. `tarota` is
  decided on its page.
- **Sizes and generic names.** `pi nai`, `pi chanai`, `pi chawa` and `pi mon` are each decided
  on their page, and `pi` follows the generic-term ruling. `hne` is the type and `hne gyi` and
  `hne galay` its sizes (the Hne page: "has a sextuple reed"; "There are two distinct forms:
  the smaller form is called the hne galay …, while the larger is called the hne gyi"): the type ships or waits
  on its own range, and each size is a sound-alike of it (a SHIP row of this half) or of the
  catalog entry its source relates it to, with its own range, or waits. `nagaswaram`,
  `nadhaswaram` and `nataswaram` follow `nadaswaram`; `shahnai`, `sanayi` and `sahanai` follow
  `shehnai`; `hojeok`, `hojok`, `nallari` and `saenap` follow `taepyeongso`; `ghaita` and
  `ghayta` follow `rhaita`; `mukhaveene` follows `sundari` (rule 3).

- [ ] **Step 1: Write half B's rows** to `build/batch-11-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-11-form-check.py build/batch-11-half-b.tsv` and
  `uv run python -I build/batch-11-quote-check.py build/batch-11-half-b.tsv`.
  Expected: `69 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-11-half-b.tsv >> plans/data/instrument-audit/batch-11.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `116 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half
  A's coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 2 Step 3's command
  with `half_a | half_b` in place of `half_a` on its `missing:` and `twice:` lines, and print
  `'extra:', sorted(set(audit_names) - half_a - half_b)` in place of the half-B line.
  Expected: `missing: []` and `twice: []`. `extra:` lists only the alias lines, because an alias
  row's `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-11.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 11's verification sheet, the folk and traditional shawms and oboes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The folk and traditional shawms and oboes

**Files:**
- Modify: `double_reeds.py`, `double_reed_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-11.tsv`'s half-B rows, Task 3's tables and `build/batch-11-code-check.py`.
- Produces: the finished family.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `NEW_DOUBLE_REED_NAMES`,
  `DOUBLE_REED_SOUND_ALIKE_PARENTS`, `DOUBLE_REED_HELD_BACK` and the alias parameters, after half
  A's, as in Task 3 Step 1, with any chain and new-builder test.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes, aliases after half A's aliases, under a
  second section comment naming the sheet.

- [ ] **Step 4: Run the suite and check the code against the whole sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`, then
  `uv run python -I build/batch-11-code-check.py plans/data/instrument-audit/batch-11.tsv`.
  Expected: PASS, then `matches 116 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 11's folk and traditional shawms and oboes, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a double reeds
  paragraph with its count, naming `double_reeds.py` and `double_reed_sound_alikes.py`, with
  examples, in the brass paragraph's form.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `double reeds`
  row's count and examples, the sound-alike modules sentence and its total).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 11
  done, pointing at this plan and `batch-11.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 11 DONE";
  - batch 11 done, with the sheet's counts by status and the family's growth, and the module
    move (`double_reeds.py`; `winds.py` keeping four reed families);
  - the audit's unclosed gaps, as a later pass;
  - the hand-offs: `zukra` (and `ciaramella`, if dropped) for the bagpipes batch, `musette` and
    `dulciana` decided here as ambiguous names, `piffero` decided here as a shawm (batch 9's
    flute gap list names it);
  - a "Plan (batch 11)" line, the Status line, and the next batch named: bagpipes.

  Add #81 (the highest item is #80), "Sound Engine: The Owner's Checks on Instrument Catalog
  Batch 11 — TODO". Use #80's form (as #75 began it), place it directly after #80, and give it
  the Priority "(before the bagpipes batch builds on the same catalog)". Its **Listen** section
  (`build/instruments/double reeds/`) covers the new builds, then the sound-alikes beside their
  parents, then the aliases. Its **Calls to confirm** are:
  - every WAIT, by reason, with names;
  - the range ruling (stated or an exact span, sounding pitch with the source's own
    transposition, no extension or extreme beyond the stated compass, capped reeds ranged like any
    other, never hedged, "comfortable" or "theoretical", the standard key or size, maker and
    museum sources, nothing below A0 or above C8, one-note instruments, cited Wikipedia lines
    only), and every derived range;
  - the quote ruling and the quote check (raw pages, «passages», citations found in the raw text);
  - one-note instruments waiting for a range (`ottu`): should they ship as fixed-pitch entries?
  - the module move (`double_reeds.py`; `winds.py` keeping the clarinets, saxophones, bagpipes
    and free reeds);
  - the bore ruling (H-S 422.111 and 422.112, the form check's built bores) and the capped and
    uncapped reeds;
  - `hichiriki` and `piri` never parents (built as cones, their pages naming a cylinder);
  - no new approximation: the hichiriki's embai and the duduk's bent notes as articulations,
    circular breathing as technique;
  - the pirouette as `_folk_shawm`'s trait, and reeds, keys and metal as no trait unless sourced;
  - drones, pairs and double pipes (`aulos`, `sopila`, the duduk's dum);
  - any new builder and the trait its source names;
  - sizes and keys as sound-alikes (the sarrusophones of `sarrusophone`, the heckelphones, the
    shawms), standard sizes and other names as aliases, and any new size chain;
  - the B-flat contrabass sarrusophone below A0;
  - the boundaries: `zukra` and `ciaramella` (bagpipes), `musette` (the bagpipe) and `dulciana`
    (the organ stop) as ambiguous names, `fagott`'s target;
  - generic terms (`pi`, `guan`) dropped;
  - one-offs and unsourced rows dropped (`tromboon`, `serpentine bassoon`), and the in-production
    line;
  - `DOUBLE_REED_HELD_BACK`, the guard for every held name;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): `piri` built as a conical
  shawm though its page says "It has a cylindrical bore." (cited); `hichiriki` likewise (its
  page's sentence is tagged `{{citation needed}}`); the catalog's `soprano crumhorn` (C4-D5) and
  `alto crumhorn` (F3-G4) against the Crumhorn page's table, soprano "(C4) D4–E5 (F5)" and alto
  "(F3) G3–A4 (Bb4)" (uncited, so a lead to check with a maker, not a source); the `oboe`'s A6
  against its page's "B♭3 to about G6" (hedged, so a lead); `double_reeds.py`'s docstring
  calling the folk ranges "typical" without a source; the 23 earlier entries' missing source
  comments; any existing range or build a sheet's source contradicts. Then **Follow-ups**: the
  audit's gaps; ranging the range WAITs from maker and museum sources; checking the 23 earlier
  entries against sources; the engine changes that unblock the waits, most rows first.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries()))"`
  and `uv run python -I build/batch-11-form-check.py plans/data/instrument-audit/batch-11.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-11-code-check.py plans/data/instrument-audit/batch-11.tsv
uv run python -I build/batch-11-quote-check.py plans/data/instrument-audit/batch-11.tsv
```
  Expected: everything passes with no warnings (a warning is a finding), `matches 116 rows`, and
  `bad: []`. The `build/instruments/double reeds` folder is the one to listen to; the owner
  judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 11 of the instrument catalog (double reeds), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch
in turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78).
The pre-push hooks take about 40 minutes, and nothing in the working tree may change while they
run.

**Order:** the controller's shared files, then Tasks 1, 2 and 4 in parallel. Task 3 follows
Tasks 1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows Tasks 3 and 4, and Task
6 comes last.
