# Instrument catalog batch 12 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the bagpipe family from the audits' candidates. The family holds the reed pipes
sounded from a bag: a chanter (single or double, double reed or single reed, conical or
cylindrical) over fixed drones, or with none, from the Great Highland bagpipe and the uilleann
pipes to the gaitas, gaidas, dudy, zampogne and the droneless double chanters of the
Mediterranean, the Middle East and North Africa. Each instrument gets a cited source for its name,
its chanter, its range and its drones, and either sounds unlike every other entry or is a listed
sound-alike of the one it sounds like. The rest become aliases, wait for an engine feature or a
sourced range or drone tuning, or are dropped with a reason.

**Architecture:** As in batches 3 to 11, a verification sheet (`batch-12.tsv`) decides every
candidate before any code is written. The family's 8 entries live in `winds.py` (520 lines, which
also holds the clarinets, saxophones and free reeds), so they move unchanged to a new
`bagpipes.py`, as batches 9 and 11 moved the flutes and the double reeds. Its table is
`_BAGPIPE_BUILDS`, and `BAGPIPES` becomes `_BAGPIPE_BUILDS + BAGPIPE_SOUND_ALIKES`, with the
sound-alikes in a new `bagpipe_sound_alikes.py`. A bagpipe's drones are fixed pitches inside its
build, so a sound-alike in another key would sound its parent's drones under its own chanter: a
sound-alike whose sourced drones differ from its parent's is built with `sound_changes={'drones':
...}` (decision 8's "change their details", used in a shipped entry for the first time), listed in
a new test table `BAGPIPE_RETUNED_DRONES`. A new guard, `BAGPIPE_HELD_BACK`, holds every name the
sheet holds back for any reason but a sourced range. The sheet and the code each come in two
halves, as explicit lists: the bagpipes of Western Europe (Britain and Ireland, France and
Flanders, Iberia, Italy), then those of Central, Northern and Eastern Europe, the Balkans, the
Mediterranean islands, the Caucasus, the Middle East, North Africa and South Asia. The controller
writes the names file, the candidate lists and the three check scripts before anything is
dispatched, so the two sheet halves are researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `with_drones`,
`wave_from_levels`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 2, 4
and 8 above all). Batch 11's plan (`plans/2026-11-12-instrument-catalog-batch-11-implementation.md`)
and its owner's checks (`plans/future-features.md` #81) are this plan's template and its ledger:
its controller step, its quote check on the raw page text, its held-back guard and its two
parallel halves carry over. Batch 4's plan (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`)
holds the pitched sound-alike and strict range rules and the before-and-after build record. Batch
7's plan holds the drone ruling (`with_drones` at sourced pitches, else `a sourced drone
tuning`), and batch 9's the double-pipe ruling (pipes that each play a melody are notes of one
sequence). This plan's own path is `plans/2026-11-12-instrument-catalog-batch-12-implementation.md`.
The branch is `feat/instrument-catalog-batch-12`, made from `feat/instrument-catalog-batch-11` at
its HEAD once batch 11's fix commit has landed (the controller's ruling that `balaban` waits for
its own build, a cylindrical bore; it touches no bagpipe). The controller records that SHA in
Task 6's #70 line. The candidates come from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` contains `bagpipe` (64, every one from the round-2 audit
  `bagpipes.md`, whose `audit_file` cell is `bagpipes.md`);
- the `round-1/merged-missing.tsv` rows whose `family` contains `bagpipe` (6: `zampogna`,
  `tulum`, `biniou koz`, `mashak`, `zukra`, `electronic bagpipe`).

Together: **66 unique candidate names** (`tulum`, `biniou koz`, `mashak` and `zukra` are in
both; counted for this plan, the controller recounts). None is in the catalog or the alias table
today, and every one is already a valid catalog name. The audit's "Aliases" section proposes **26
alias names** on 14 lines: `union pipes`, `irish pipes`, `lowland pipes`, `reel pipes`, `half long
pipes` (the audit's "half-long pipes"), `biniou braz`, `mushak baja`, `masak been`, `gaita galega`,
`sackpfeife`, `schaferpfeife`, `bock`, `ciaramedda`, `mizwad`, `chabrette`, `chabretta`, `gajdy`,
`gajde`, `gayda`, `tulug`, `guda`, `gaita alistana`, `cabreiresa`, `coimbra`, `gaita mirandesa`
and `mutsianka`. None is in the catalog or the aliases. `reel pipes` is also a candidate, so its
one row decides both senses (rule 8), and the alias names add **25 rows**. So the sheet will hold
**91 rows**.

Two rows come from batch 11's sheet (`batch-11.tsv`), and #70 and #81 name them:
- `zukra` is DROP there, "belongs to bagpipes: 'is a Libyan bagpipe'; the bagpipes batch decides
  it". It is decided here, as a candidate of half B.
- `ciaramella` is WAIT there, "its target, piffero": batch 11's fetched pages made the name the
  mouth-blown shawm and sent the bagpipe to Wikipedia's separate Ciaramedda page (#70: "the
  bagpipe, `ciaramedda`, is the bagpipes batch's"). So the candidate `ciaramella` is already
  decided (DROP, naming batch 11's row), and the bagpipe sense is decided under the audit's alias
  name `ciaramedda`, as an instrument row of its own (the boundary ruling below). The Ciaramedda
  page (fetched for this plan, raw wikitext): "The '''ciaramedda''' or '''ciaramèddha'''
  ([[Sicilian language|Sicilian]]) is a type of [[zampogna]] with equal length double chanters."
  (cited to Sinclair 1908).

Batch 11 also dropped `musette` as an ambiguous name ("also the musette de cour (bagpipes)"); the
catalog's `musette de cour` is one of this family's 8, so nothing is handed back. No other earlier
sheet hands a row to this family (checked: `batch-1.tsv` to `batch-11.tsv`, and
`plans/future-features.md` #70–#81). `electronic bagpipe` is an electrophone, the electronic
family's, whose batch (6) is done; the boundary ruling decides it.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). Accents, apostrophes, hyphens and parentheses go only in the title (`half long
  pipes` for the audit's "half-long pipes", `gaita transmontana` for "Gaita-de-fole
  transmontana"). The bagpipes put a key in the title after the name, as the catalog's do
  ("Scottish smallpipes in A", "Galician gaita in D"), so `scottish smallpipes in d` keeps its
  audit name, titled "Scottish smallpipes in D" (the plan's naming ruling).
- "A family is defined by how the sound is made (the Hornbostel–Sachs class)" (spec, Families).
  A bagpipe is a set of reed pipes sounded from a flexible air reservoir, the bag (Hornbostel–Sachs
  writes it as the suffix -62, "with flexible air reservoir", where a page's class gives it),
  blown by mouth or by bellows. Its chanter is an oboe (422.1, a double reed) or a clarinet
  (422.2, a single reed), single (422.x1x) or a set (422.x2x, a double chanter), with a
  cylindrical (422.xx1) or conical (422.xx2) bore. Batch 11's boundary: "A bag makes a bagpipe".
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict").
  This plan's range ruling for bagpipes is below, under "Decisions". A row with no sourced range
  is WAIT, `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the
  same instrument) stays an alias." "So `sound_changes` (keyword overrides of the parent's
  builder, empty by default) lets a sound-alike differ by a sourced trait." A sound-alike is
  pitched exactly when its parent is, and a pitched sound-alike gives its own sourced range
  (batch 4). "a sound-alike with changes counts as its own build" (decision 8), so it must sound
  different from every other entry.
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as
  an approximation, under its real name or a qualified one. The spec's table names no bagpipe, but
  its rows "more than four sources" and "sub-audio fundamentals" bind. Earlier batches added the
  other names a WAIT may give: a pitch LFO (vibrato), a pitch LFO (portamento between notes), an
  amplitude LFO, filter resonance, a filter envelope, moving formants (batch 6); a buzzing
  membrane (batch 5); a sourced drone tuning and its own build (batch 7); a range above C8
  (batch 10). This plan adds `a sourced chanter bore` (a source wait, below). What the engine has:
  up to four `Source`s, each with its own semitones, detune and fixed pitch; `with_drones`
  ("fixed-pitch drones sounding under every note", keeping only the chanter's `tone` and `breath`
  sources, "at most two with breath, three without"); `blown` (a harmonic series, its attack,
  release, breath noise, low pass and drive); one glide per note (`pitch_curve`); a fixed FIR low
  or high pass; no LFO of any kind.
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not
  builds.
- Reuse the family's builder, which `bagpipes.py` keeps under its current name: `_bagpipe`
  (`chanter_levels`, `drones`, `drone_levels`, `low_pass`, `drive`, `breath`, `attack`,
  `sustain`) with `HIGHLAND_LEVELS` or `SWEET_CHANTER_LEVELS` for the chanter and `DRONE_LEVELS`
  or `SMOOTH_DRONE_LEVELS` for the drones. Each entry's build is an inline `partial(_bagpipe,
  ...)`. Add a level table or builder only for a genuinely new, sourced sound, and give it its own
  test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the
  sheet is verbatim from a page the worker fetched, and every `Range:` and `Drones:` passage is
  quoted from the raw page text (the plan's quote ruling). No request carries the owner's email or
  any personal data, in a header, a URL or a payload (#78, "Incidents and process").
- Code comments name committed files (`plans/data/instrument-audit/batch-12.tsv`), never the
  gitignored `build/` files (batch 9's fix).
- The 8 entries already in the family keep their names, titles, ranges, builds and order. New
  entries come after the 8. An existing entry changes only for a cited bug, reported to the owner;
  the 8 entries carry no source comment and their timbres were "tuned there by ear"
  (`scripts/make_pipes.py`, the comment above `HIGHLAND_LEVELS`), so a range, a drone or a build
  that a fetched source contradicts is reported in #82, not changed here (batches 10 and 11's
  rule).
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown
  by a test, you should understand why it's happening and be concerned": a warning is a
  finding, and it must be understood before going on.
- Commits as batches 4 to 11: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this
  plan, never from memory. Write no `.md` file beyond those Task 6 names. Never use `git stash`:
  the stack is shared with other worktrees and sessions (#80, "Incidents and process"). Set work
  aside with a temporary commit instead.

## Review Focus

1. **A nominal pitch read as sounding.** A bagpipe's note names are often its own, not concert
   pitch. The Great Highland bagpipe page (raw wikitext, fetched for this plan): "It has a range
   from one [[whole tone]] lower than the [[Tonic (music)|tonic]] to one octave above it. The
   drones are tuned to this tonic note, called A (specifically [[scientific pitch
   notation|A<sub>4</sub>]]). … but currently is tuned somewhere around 470–480&nbsp;Hz, or
   slightly above the [[A440 (pitch standard)|standard pitch]] B♭ (466.16&nbsp;Hz)" (cited to
   Macpherson). Its "A" sounds a semitone up, so its nominal G4–A5 sounds A♭4–B♭5 (the catalog's
   `highland bagpipe` range, which agrees). A range copied in nominal names is a semitone (or more)
   wrong. Range ruling 2 takes a nominal range only with the same source's sounding pitch for a
   named note, the derivation shows the shift, and the code check compares every range with the
   sheet.
2. **Drones that are not the source's, or out of tune with the chanter.** A sound-alike builds its
   parent's instrument, drones included, at the parent's fixed hertz. A sound-alike in another
   key would sound its parent's drones under its own chanter, and a drone given in raw hertz sits
   off the engine's equal-tempered chanter: the catalog's `highland bagpipe` drones are 240 and
   120 Hz, a quarter tone (51 cents) above its chanter's B♭ (233.08 and 116.54 Hz), though its page
   says the drones are tuned to the tonic. The drone ruling sounds every drone at its derived
   note, equal-tempered at A4 = 440 Hz, the sheet's `drones` cell names the notes, the code check
   compares every built drone with them, and `test_a_retuned_bagpipe_sounds_its_sourced_drones`
   pins each retuned sound-alike's drones.
3. **A cylindrical chanter given a parent built as a cone.** A closed cylinder favours odd
   harmonics (`winds.py`'s docstring: "a clarinet (a closed cylinder) favours odd harmonics"), and
   every existing bagpipe is built with an every-harmonic chanter (`HIGHLAND_LEVELS`,
   `SWEET_CHANTER_LEVELS`). The Scottish smallpipes, Northumbrian smallpipes and Musette de cour
   pages each name a cylindrical chanter (uncited). Batch 11's balaban and piri rule: a new entry
   with a cited trait its build cannot make waits or gets its own build. The form check refuses a
   sound-alike whose chanter class is not conical when its parent is an existing bagpipe, and
   refuses those three entries as parents.
4. **A width, a key, a relative compass or a sibling's range read as a range.** The pages mostly
   give a key ("most commonly pitched in A", "in E♭"), a width ("nine notes", "one-octave
   scale", "about two octaves"), a compass relative to a tonic whose octave is unstated, or a
   relation ("sounds an octave above the bombarde", the Biniou page). Range ruling 5 takes none of
   them, and ruling 7 never takes a range from a sibling or the parent. Each SHIP and SOUND_ALIKE
   row's `notes` hold the passage and the derivation, and the form check refuses a ranged row
   without a `Range:` passage.
5. **The same instrument shipped twice, or a name decided twice.** `dudy`, `sorbian dudy`,
   `polish dudy`, `mechawka` and `bock`; `macedonian gaida`, `kaba gaida`, `dzhura gaida`, the
   catalog's `bulgarian gaida` and `gajdy`, `gajde`, `gayda`; `dudelsack`, `swiss sackpfeife`,
   `marktsackpfeife`, `sackpfeife` and `schaferpfeife`; `reel pipes` (a half-set Highland pipe and
   the Border pipes' other name); `ciaramella` (batch 11's shawm) and `ciaramedda`; `zukra` and
   `mizwad`; `tulum`, `tulug` and `guda`; `mashak`, `mushak baja` and `masak been`. Rules 3, 5 and
   8 and the boundary, generic-term and ambiguity rulings decide each, the form check refuses a
   name taken before the batch, and the code check finds every name exactly once.

---

## File Structure

- Create `src/glitchygames/audio/instruments/bagpipes.py`. It takes the "Bagpipes" section of
  `winds.py` (`HIGHLAND_LEVELS`, `DRONE_LEVELS`, `SWEET_CHANTER_LEVELS`, `SMOOTH_DRONE_LEVELS`,
  `_bagpipe`, the 8 entries and their comments), unchanged, as `_BAGPIPE_BUILDS`. New builds go
  after the 8, a new level table is a module-level tuple of floats beside the four, and `BAGPIPES
  = _BAGPIPE_BUILDS + BAGPIPE_SOUND_ALIKES`.
- Create `src/glitchygames/audio/instruments/bagpipe_sound_alikes.py`, holding
  `BAGPIPE_SOUND_ALIKES`.
- Modify `winds.py` (the section, its bagpipe words and its `wave_from_levels` and `with_drones`
  imports leave; it keeps the clarinets, saxophones and free reeds), `registry.py` (it imports
  `BAGPIPES` from `bagpipes.py`; its place in `FAMILY_TABLES`, after the double reeds, doesn't
  change), the docstrings of `flutes.py`, `double_reeds.py` and `instruments/__init__.py` that
  name `winds.py`, and `aliases.py` (the batch's ALIAS rows).
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5). The process-state guard
  (`tests/test_process_state_guard.py`) lists nothing from the bagpipe section today (its
  `winds.py` entry holds only `FREE_REED_LEVELS`), so nothing moves there.
- Create `plans/data/instrument-audit/batch-12.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #82), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #82):

- **Bagpipes get their own module.** `winds.py` holds four families, and batch 9 moved the
  flutes out so that the reed families' "own batches can move the same way" (#79); batch 11 moved
  the double reeds. Every family a batch has grown since batch 4 has a module of its own and a
  sibling sound-alikes module that names it ("The family's builds are in …"). No other module
  imports the bagpipe builder or its level tables (only `registry.py` imports `BAGPIPES`; the
  test file names only `Family.BAGPIPES`), and the guard lists none of them, so the move is
  mechanical, and Task 1's before-and-after record checks it. The bagpipes are also the only
  family built with `with_drones`, and the retuned sound-alikes below are their own mechanism;
  leaving them in `winds.py` would put that beside three families no batch has grown yet.
- **Range ruling for bagpipes.** A sourced range is the lowest and highest sounding notes of the
  chanter that a fetched source states for the instrument:
  1. *Stated*: the source gives both notes as the range or compass, in note names with octaves
     (scientific `G4`, Helmholtz `g'` where the source names the notation or fixes the octave,
     or a named note whose octave the source fixes), or the lowest note and an exact span above
     it, as batch 7 allowed. A compass relative to the tonic ("from one whole tone lower than the
     tonic to one octave above it") counts when the same source fixes the tonic's sounding pitch
     with its octave (a hertz figure, or a note with its octave). A key alone ("in A", "pitched
     in E♭") fixes no octave.
  2. *Sounding*: a range in the instrument's nominal names (the Highland "A") counts only when
     the same source states the sounding pitch of a named nominal note, as a hertz figure or a
     concert note. The shift is the nearest equal-tempered semitone (A4 = 440 Hz) from the
     nominal note to that pitch, using a stated span's midpoint (470–480 Hz is 475 Hz, B♭4 plus 32
     cents, so the Highland "A" is B♭4 and the range moves up a semitone). If the pitch lies
     within 10 cents of halfway between two semitones (480 Hz alone is B♭4 plus 51 cents, B4 minus
     49), the source does not decide the note and the row WAITs `a sourced range`. A written
     range in a transposing notation counts only with the transposition its own source states,
     as batch 11's ruling 2. The derivation shows the arithmetic.
  3. *Extensions and extremes*: the stated compass, and nothing beyond it. A note in parentheses
     is an extension, and the range is the unparenthesised notes. A top the source gives to the
     player ("for advanced players", "or higher"), an optional key or extra chanter, and notes
     made by overblowing that the source calls a technique rather than the compass are extremes:
     the range is the compass without them, or the row WAITs. Keys the source counts in the
     compass (a keyed chanter's stated range) are part of it.
  4. *Double chanters*: a chanter of two pipes that each play a melody, or a melody and a
     harmony (the zampogna, the ciaramedda), is played as two notes of one sequence (batch 9's
     double-flute ruling), so its range runs from the lowest note of the lower pipe to the
     highest note of the upper, each stated. Pipes fingered together in unison are one note. A
     pipe that holds one note is a drone (the drone ruling).
  5. *Not a range*: a hedged span ("about", "approximately", "typically", "commonly",
     "usually", "practically", "can reach"), a span the source calls "comfortable" or
     "theoretical", an extreme, a width with no pitches ("nine notes", "a one-octave scale",
     "about two octaves"), note letters with no octaves, a key alone, a tessitura, a scale's
     notes with no octave, or one pitch.
  6. *Several keys or sizes*: the key or size the source calls standard, usual or most common,
     from that source or a maker's model page in that key. A key or size in the row's own name
     (`scottish smallpipes in d`) is ranged in that key. A source giving one size two ranges has
     given none, unless it calls one standard. With neither, the row WAITs (batch 7's rule for
     several tunings).
  7. *Sources*: the instrument's encyclopedia page (Wikipedia, Britannica, Grove where reached);
     a maker's catalogue or model page (the Highland, smallpipe, uilleann, gaita, gaida, dudy and
     zampogna makers' own sites); a museum's object record (MIMO, the National Museum of Scotland,
     the Edinburgh University Collection of Historic Musical Instruments (MIMEd), the Met, the
     Horniman, the Musée de la musique, the Museu de la Música de Barcelona, the Bate Collection);
     or a piping society's or conservatory's published reference (the Lowland and Border Pipers'
     Society, Na Píobairí Uilleann, the Northumbrian Pipers' Society). A museum's or maker's page
     outranks an uncited Wikipedia line, and when they disagree the museum or maker decides (batch
     11's lesson). A retailer's listing, a blog, a forum or a tune book is not a source. A maker's
     page for a model in another key ranges only that key. A range is never taken from a sibling
     size, the parent, a related instrument ("an octave above the bombarde") or the audit.
  8. *The catalog's span*: nothing below A0 (WAIT `sub-audio fundamentals`, the spec's name) and
     nothing above C8 (WAIT `a range above C8`).
  9. *One note*: an instrument whose source gives its pipes one note between them (the sruti
     upanga: a drone with no chanter) has no range, since the catalog needs lowest below highest.
     It WAITs `a sourced range`, with the note quoted in `notes`, and #82 carries #80's and #81's
     question whether a one-note instrument should ship as a fixed-pitch entry instead.
  10. *Cited*: a range from Wikipedia counts only when the raw wikitext shows a citation (a
      `<ref>`, `{{sfn}}`, `{{harvnb}}` or `{{r}}`) after it, in its own infobox or table cell,
      or later in its own paragraph with no `{{citation needed}}` first, and its section is not
      tagged `{{Unreferenced section}}`. The citation must support the line: where the cited work
      is reachable the worker opens it, and a citation that gives no range (batch 11's `shehnai`,
      whose Met essay named none) is no citation.
  Every pitched row's `notes` hold `Range:`, then each quoted passage between `«` and `»`, then
  the derivation; then `Drones:`, its passages and their derivation (the drone ruling).
- **Drone ruling for bagpipes.** A bagpipe's drones are part of its sound (`winds.py`: "a
  bagpipe's chanter sounds over fixed drones"), so a SHIP or SOUND_ALIKE row needs its drones
  sourced, as batch 7 ruled for drone strings:
  1. The drones are sourced when a fetched source gives each sounding drone's pitch as a note with
     its octave, a hertz figure, or an interval from a chanter note whose sounding pitch that
     source fixes (the Galician gaita page: "The bass drone … is pitched two octaves below the key
     note of the chanter", with the key note fixed). A droneless bagpipe is sourced when its
     source says it has none ("droneless", "no drone"); its `drones` cell is `none`.
  2. Drones at one pitch count once (the catalog's `highland bagpipe` sounds its two tenor drones
     as one 240 Hz source). Only drones the source says sound count: a drone the source calls
     muted, decorative or not reeded is left out (the Ciaramedda page: "often only the middle
     drone is reeded while the other two remain muted"), and when the source gives several
     configurations, the one it calls usual or standard, else the row WAITs `a sourced drone
     tuning`.
  3. At most two distinct drone pitches: `_bagpipe` keeps the chanter's breath source, so
     `with_drones` has room for two ("at most two with breath"). A source giving three distinct
     sounding pitches makes the row WAIT `more than four sources` (the spec's name).
  4. Each drone sounds its derived note, equal-tempered at A4 = 440 Hz like the chanter, written
     in the code as hertz to two decimals as the catalog's builds are (146.83, 73.42): a source's
     hertz figure decides which note, not the drone's hertz. So a Highland-pitched drone in "A"
     is B♭3, 233.08 Hz, under a B♭ chanter. The sheet's `drones` cell names the notes, highest
     first, as the catalog's builds list them (`Bb3 Bb2`), and `drone_source` holds the URL.
  5. A drone whose pitch the player changes with keys while playing (the surdelina's
     "key-switched drones") is a pipe played as notes of the sequence (rule 4 of the range
     ruling), not a drone; its fixed drones, if any, follow this ruling.
  6. A row with a sourced range and no sourced drones WAITs `a sourced drone tuning` (batch 7's
     name); a row with neither WAITs `a sourced range`, which is checked first. A row never
     ships with its parent's drones on the assumption that they match.
- **The chanter ruling.** A bagpipe's chanter bore is its sound's main trait beside the drones
  (Review Focus 3), and Hornbostel–Sachs names it. The `hs` cell of a SHIP or SOUND_ALIKE row
  holds the chanter's class, matching `422\.[12][12][12]`: from the page's infobox (for a mixed
  class, the chanter's part), its own Hornbostel–Sachs category, or a source sentence naming the
  chanter's reed and bore (then the code it implies, with the sentence quoted: a conical
  double-reed chanter is 422.112, a cylindrical one 422.111, a cylindrical single-reed chanter
  422.211, and the set codes 422.12x and 422.22x for a double chanter). A ranged row with no
  sourced chanter bore WAITs `a sourced chanter bore` (a source wait this plan adds, since the
  builder cannot be chosen without it). Every existing bagpipe is built with an every-harmonic
  chanter, that is as a cone, so a SOUND_ALIKE of an existing bagpipe has a conical chanter (the
  last digit 2), and a SOUND_ALIKE of a SHIP row of its half has that row's bore. A cylindrical
  chanter (the last digit 1) is no sound-alike of an existing bagpipe: it SHIPs with the
  cylindrical chanter table below, or WAITs. Single and double reeds count as a trait only when a
  fetched source names their effect on the sound (batch 11's "reeds, keys and metal" ruling).
- **Three entries are never parents in this batch.** `scottish smallpipes` ("The instrument has a
  cylindrically bored chanter", its page), `northumbrian smallpipes` ("The cylindrically bored
  chanter has a number of metal keys") and `musette de cour` ("Both the chanters and the drones
  have a cylindrical bore and use a double reed") are built with `SWEET_CHANTER_LEVELS`, every
  harmonic. Each line is uncited in the raw wikitext (fetched for this plan), so, as batch 11's
  final ruling kept the uncited `hichiriki` out of `APPROXIMATING_NAMES`, none joins it; but a
  sound-alike would ship the cone under a cylinder's name, so the form check refuses all three as
  parents, and #82 reports the three builds as leads for the owner. If a sheet worker finds the
  bore line cited by a source that supports it, the entry joins `APPROXIMATING_NAMES` in its
  half's code task, with that source in the comment (batch 11's `piri` precedent), and #82 says
  so.
- **A cylindrical chanter table, only for a sourced cylinder.** A SHIP row whose source names a
  cylindrical chanter builds with `_bagpipe(chanter_levels=CYLINDRICAL_CHANTER_LEVELS, ...)`, a
  new module-level tuple of floats in `bagpipes.py`: `(1.0, 0.0, 0.4, 0.0, 0.17, 0.0, 0.06, 0.0)`,
  `SWEET_CHANTER_LEVELS`'s odd harmonics with the even ones silent (sound design, marked so in its
  comment, which cites the row's bore source). The first code task that ships such a row adds it
  and its test, `test_a_cylindrical_chanter_sounds_odd_harmonics`; the second reuses it. A literal
  tuple of floats is not process state, so the guard gets no line; if it asks for one, that is a
  finding to read before writing any reason. The row's other values (`low_pass`, `drive`,
  `breath`, `attack`, `sustain`, the drone levels) are copied from the existing entry its source
  relates it to, or nearest in kind (a bellows-blown cylinder from `scottish smallpipes`), and
  marked as sound design.
- **Retuned sound-alikes.** A SOUND_ALIKE whose sourced drones are within 5 cents of its parent's
  built drones, in number and pitch, ships unchanged. Otherwise it carries
  `sound_changes={'drones': ((hertz, level), ...)}`: its own drone notes as hertz (drone ruling
  rule 4), each with the level of the parent's drone of the same rank (the lowest takes the
  parent's lowest drone's level, the other the parent's highest's; a parent with one drone gives
  its level to both; a droneless row has `drones=()`). The levels are the parent's sound design,
  copied unchanged. Only `drones` may change: no other keyword has a sourced value here, and a
  number chosen only to differ is no trait (rule 7). Each retuned sound-alike is listed in the
  test table `BAGPIPE_RETUNED_DRONES` (name to drone notes), and
  `test_a_retuned_bagpipe_sounds_its_sourced_drones` checks its drones and that it differs from
  its parent. Two retuned sound-alikes of one parent with the same drones build the same
  instrument, which is allowed, as two unchanged sound-alikes of one parent are. A sound-alike of
  `highland bagpipe` is always retuned, since the parent's drones (240 and 120 Hz) are no
  equal-tempered note (Review Focus 2).
- **A bagpipe's parent is a bagpipe.** Only `_bagpipe` takes `drones`, and a bag with drones is
  the family's sound, so a SOUND_ALIKE's parent is a catalog bagpipe from before the batch or a
  SHIP row of its half, never another family's entry. A droneless bagpipe whose chanter its source
  relates to a shawm is a retuned sound-alike of a bagpipe with `drones=()` only if its source
  relates it to that bagpipe; otherwise it SHIPs its own build or WAITs.
- **Double chanters.** Two melodic pipes are notes of one sequence (range ruling 4). Pipes in
  unison that the source says are tuned apart to beat ("tuned slightly apart") have a sourced trait
  no builder makes: `with_drones` keeps only the chanter's `tone` and `breath` sources, so no
  bagpipe build can sound a second, detuned chanter pipe, and the row WAITs `its own build (a
  detuned double chanter)`. Pipes in unison with no such sentence are one chanter.
- **Nominal pitch and the catalog's own entries.** The existing `highland bagpipe` range
  (`Ab4`-`Bb5`) agrees with its page under range ruling 2, but its drones (240 and 120 Hz) sit 51
  cents above its chanter's B♭ (the page: "The drones are tuned to this tonic note"; the sentence
  is in the paragraph cited to Macpherson). That is a cited bug in an existing entry: #82 reports
  it with the measured cents, and the entry is not changed here (Global Constraints).
- **No new approximation.** No bagpipe joins `APPROXIMATING_NAMES` except under the never-parents
  ruling above. Grace notes, closed (staccato) fingering, regulators' chords and bellows are
  technique or notes of a sequence (the spec's Non-goals: "Articulations and ensemble patches …
  are instrument settings"), except where a fetched source names a closed chanter as the
  instrument's own sound, which `_bagpipe`'s `sustain` carries as `northumbrian smallpipes` does
  (its comment: "Closed-ended: notes are detached, so the chanter drops between them"). A flea
  hole or chanter keys choose notes.
- **No unpitched or mechanical bagpipe.** Every bagpipe parent is pitched, so a sound-alike is
  pitched, and no candidate plays itself. The form check refuses any `tags`, and the batch table's
  row needs no unpitched names.
- **The boundary hand-offs.** `ciaramella` is DROP "already decided: batch-11.tsv WAIT, its
  target, piffero (the shawm); the bagpipe is the ciaramedda row". `ciaramedda` is decided as an
  instrument row (status SHIP, SOUND_ALIKE, WAIT or DROP on its page), not as the audit's alias of
  `ciaramella`, with `audit_name` `ciaramedda -> ciaramella`. `zukra` is decided here on its page
  (batch 11's note: "played by mouth without a bag (as a double clarinet) in the east"; its bag
  form is this family's). A row whose fetched source makes it bagless (a double pipe played by
  mouth) is DROP naming the family (double reeds, clarinets or flutes) and the source's words;
  `electronic bagpipe` is DROP "belongs to electronic (H-S 53): an electrophone that imitates the
  Great Highland bagpipe" if its fetched page says so (the electronic batch is done, so Task 6
  lists it in #70 for a later electronic pass). An alias name that a source gives to an instrument
  of another family is DROP "an ambiguous name: also <the instrument> (<family>)".
- **Generic and ambiguous terms.** A name its source gives to a class of bagpipes rather than one
  (`dudelsack` and `sackpfeife` if their pages make them the German words for any bagpipe, `habban`
  if its page covers "Bedouin types and Highland-style Omani", `cornemuse du centre` if its page
  says "several types") is DROP "a generic term for <the instruments>", unless the source makes it
  one instrument's name. A name a source gives to two instruments of this family (`reel pipes`,
  `gajdy` if its page gives it to more than one bagpipe) is DROP "an ambiguous name: <the two>",
  and the unambiguous names carry the instruments. `coimbra` (a city's name in the audit's alias
  line) is decided on its page like any alias.
- **One-offs, reconstructions and unsourced rows** (batch 5's ruling, with batch 10's
  in-production line): DROP "a one-off instrument, not a type a game would ask for" for one maker's
  or player's design not in production, and DROP "no fetched source describes it" when no page
  describes the row. A reconstruction that makers offer today (a current model page) or a museum
  holds as a type is not a one-off (`zetland pipes`, `marktsackpfeife`); an extinct type
  (`cornish bagpipes`) is decided like any other and waits if no source ranges it. The audit's
  "(memory)" rows (`mutsianka`) follow rule 6.
- **Sizes, keys and the standard size.** A size or key of an existing bagpipe (`scottish
  smallpipes in d`, `kaba gaida`, `dzhura gaida`, the dudy sizes) is a SOUND_ALIKE of the entry
  nearest in register that its source relates it to, with its own range and drones under the
  rulings, or it WAITs. A candidate that its source makes a catalog entry under another name is
  ALIAS of that entry. Any size that ships joins its chain in
  `test_sized_families_descend_from_highest_to_lowest`, and a new chain is added once a size ships
  beside two or more catalog sizes that one source names as one family (the gaidas with `bulgarian
  gaida`), in descending order of lowest note.
- **Two halves, as explicit lists.** Half A, the bagpipes of Western Europe (Britain and Ireland,
  France and Flanders, Iberia, Italy) with `electronic bagpipe`, is these 31 candidates. Half B,
  those of Central, Northern and Eastern Europe, the Balkans, the Mediterranean islands, the
  Caucasus, the Middle East, North Africa and South Asia, is the other 35. The list decides the
  half: a row whose source shows another origin stays in its half.
  `baghet`, `biniou koz`, `boha`, `bousine`, `brian boru bagpipes`, `cabrette`, `caramusa`,
  `ciaramella`, `cornemuse du centre`, `cornish bagpipes`, `doedelzak`, `electronic bagpipe`,
  `gaita asturiana`, `gaita de boto`, `gaita de saco`, `gaita sanabresa`, `gaita transmontana`,
  `great irish warpipes`, `odrecillo`, `pastoral pipes`, `piva`, `reel pipes`, `sac de gemecs`,
  `scottish smallpipes in d`, `surdelina`, `surdullina`, `veuze`, `welsh pibgod`, `xeremies`,
  `zampogna`, `zetland pipes`.
  The 25 alias names go with the candidate or entry whose page decides them. Half A has 13:
  `union pipes`, `irish pipes`, `lowland pipes`, `half long pipes`, `biniou braz`, `gaita galega`,
  `ciaramedda`, `chabrette`, `chabretta`, `gaita alistana`, `cabreiresa`, `coimbra`, `gaita
  mirandesa`. Half B has 12: `mushak baja`, `masak been`, `sackpfeife`, `schaferpfeife`, `bock`,
  `mizwad`, `gajdy`, `gajde`, `gayda`, `tulug`, `guda`, `mutsianka`. So half A's sheet holds 44
  rows and half B's 47. The duplicates and near-pairs fall within one half (`reel pipes`,
  `lowland pipes` and `half long pipes`; `ciaramella`, `ciaramedda`, `zampogna` and `surdullina`;
  the gaitas and their alias names; `cabrette` and its two in A; the dudy, the gaidas, the
  German names, `zukra` and `mizwad`, `tulum` and its two, `mashak` and its two in B).
- **The halves run in parallel.** A parent or alias target is a catalog name from before the
  batch, or a SHIP or SOUND_ALIKE row of the same half, never a row of the other half. So Task 4
  needs nothing from Task 2. Half B drafts to a build file, which is appended to the sheet once
  half A is committed. The form check accepts a row that the code already holds with the same
  target or parent (batch 7's lesson). If Task 5 finds a half-B build equal to a half-A build,
  that is a finding for the controller, who re-rules the row in a sheet fix commit.
- **A held-back guard.** As batch 11's `DOUBLE_REED_HELD_BACK`, this batch's guard is
  `BAGPIPE_HELD_BACK`, a `dict[str, str]` from name to `waits_for`, holding every WAIT row whose
  reason is not `a sourced range` (an engine feature, a build of its own, a sourced drone tuning,
  a sourced chanter bore), and every alias row that waits for such a row. A test refuses each of
  its names in the catalog and the aliases, and the code check compares the table with the sheet.
- **A half that ships nothing skips its code task, by ruling.** If a half's sheet has no SHIP,
  SOUND_ALIKE or ALIAS row, its code task still fills `BAGPIPE_HELD_BACK` with the half's held
  rows and runs the code check, which must pass; its other steps are skipped, and Task 6 records
  the skip in #82.
- **Out of scope:** the audit's "Gaps you could not close" (absolute chanter ranges for nearly
  everything; MIMO and Grove unreached, the NMS and MIMEd records unread; karkm, shyuvr, puvama,
  shapar, muchosa, samponha, sourdeline, loure, pipasso, musette bressane, musette bechonnet, the
  Lincolnshire, Yorkshire and Lancashire pipes, il-qrajna, sierszenki, kozioł biały and czarny;
  Central Asian, Tibetan, East and Southeast Asian, sub-Saharan and Latin American bagpipes; the
  Galician gaita's other keys, grileira, redonda and tumbal, which no candidate rows). Task 6
  lists them in #70 for a later pass.

---

### Before the tasks: the controller writes the shared files

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together. None of these files is committed.

- [ ] **Step 1: The names before the batch**
```bash
mkdir -p build/batch-12-pages
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-12-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
  Expected: `names before 804` (692 entries and 112 aliases, after batch 11's fix commit). Any
  other number means the branch is not batch 11's HEAD: stop and find out why.

- [ ] **Step 2: The candidate lists**
```bash
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /bagpipe/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /bagpipe/ {print tolower($1)}' round-1/merged-missing.tsv
} | LC_ALL=C sort -u > ../../../build/batch-12-candidates.txt
cd ../../..
```
  Write the plan's 31 half-A names, one per line, to `build/batch-12-half-a.txt`, sorted with
  `LC_ALL=C sort`, then run
  `LC_ALL=C comm -23 build/batch-12-candidates.txt build/batch-12-half-a.txt > build/batch-12-half-b.txt`
  and `wc -l build/batch-12-*.txt`.
  Expected: 66 candidates, 31 in half A, 35 in half B, and
  `LC_ALL=C comm -13 build/batch-12-candidates.txt build/batch-12-half-a.txt` prints nothing.

- [ ] **Step 3: The form check,** `build/batch-12-form-check.py`:
```python
"""Batch 12's sheet form check: uv run python -I build/batch-12-form-check.py SHEET.

Batch 11's form check (plans/2026-11-12-instrument-catalog-batch-11-implementation.md, "Before
the tasks" Step 3) with batch 12's changes (batch 12's plan, "Before the tasks"): the bagpipes
family, the drones and drone_source columns, and a sound-alike's chanter bore matching the
chanter its bagpipe parent is built with.
"""

import csv
import re
import sys

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note

STATUSES = ('SHIP', 'SOUND_ALIKE', 'WAIT', 'ALIAS', 'DROP')
# tests/audio/test_instrument_catalog.py APPROXIMATING_NAMES (after batch 11)
APPROXIMATING_NAMES = {
    'sitar', 'tanpura', 'veena', 'sarod',
    'sarangi', 'hardanger fiddle', 'viola d amore', 'nyckelharpa', 'hurdy gurdy',
    'dizi', 'didgeridoo', 'piri',
}
# Built with an every-harmonic chanter though their pages name a cylindrical one: never a parent
# (batch 12's plan, "Three entries are never parents in this batch")
BUILT_AGAINST_THEIR_CHANTER = {'scottish smallpipes', 'northumbrian smallpipes', 'musette de cour'}
# Hornbostel-Sachs 422.abc: a is 1 for a double reed, 2 for a single reed; b is 1 for one pipe,
# 2 for a set; c is 1 for a cylindrical bore, 2 for a conical one
CHANTER_CLASS = re.compile(r'422\.[12][12][12]')
CONICAL = '2'
# with_drones: "at most two with breath", and _bagpipe keeps the breath
MOST_DRONES = 2
pattern = re.compile(r'[a-z][a-z0-9]*( [a-z0-9]+)*')
with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
with open('build/batch-12-names-before.txt', encoding='utf-8') as before_file:
    names_before = set(before_file.read().split('\n')) - {''}
ship_rows = {row['name']: row for row in rows if row['status'] == 'SHIP'}
alikes = {row['name'] for row in rows if row['status'] == 'SOUND_ALIKE'}
bagpipe_parents = set(ship_rows) | {
    name for name in names_before
    if name in instruments.CATALOG
    and instruments.entry(name).sounds_like is None
    and instruments.entry(name).family == 'bagpipes'
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


def in_span(note_name):
    """A note name the catalog accepts, A0 to C8."""
    try:
        number = Note(note_name).midi_number
    except Exception:
        return False
    return Note('A0').midi_number <= number <= Note('C8').midi_number


def ranged(row):
    """A row with both notes, A0 to C8, lowest below highest, its range source and passage."""
    if not (in_span(row['lowest']) and in_span(row['highest'])):
        return False
    return (
        row['range_source'].startswith('http')
        and 'Range:' in row['notes']
        and Note(row['lowest']).midi_number < Note(row['highest']).midi_number
    )


def droned(row):
    """Sourced drones: "none", or one or two distinct notes, A0 to C8, highest first."""
    if not row['drone_source'].startswith('http'):
        return False
    if 'Drones:' not in row['notes'].partition('Range:')[2]:
        return False
    if row['drones'] == 'none':
        return True
    drone_notes = row['drones'].split()
    if not 1 <= len(drone_notes) <= MOST_DRONES or not all(in_span(note) for note in drone_notes):
        return False
    numbers = [Note(note).midi_number for note in drone_notes]
    return numbers == sorted(set(numbers), reverse=True)


def chanter_bore(row):
    """The chanter's bore digit from the hs cell, or None when hs names no chanter class."""
    return row['hs'][6] if CHANTER_CLASS.match(row['hs']) else None


def chanter_matches(row):
    """A sound-alike's chanter has the bore its bagpipe parent is built with."""
    parent = row['alias_of']
    if parent in BUILT_AGAINST_THEIR_CHANTER:
        return False
    if parent in ship_rows:
        return chanter_bore(row) is not None and chanter_bore(row) == chanter_bore(ship_rows[parent])
    # Every bagpipe from before the batch is built with an every-harmonic (conical) chanter
    return chanter_bore(row) == CONICAL


names = [row['name'] for row in rows]
bad = [row['name'] for row in rows if not pattern.fullmatch(row['name'])
       or row['status'] not in STATUSES
       or row['family'] != 'bagpipes'
       or not row['audit_name']
       or not (row['hs'] == 'none' or row['hs'][:1].isdigit())
       or row['tags'] != ''
       or (row['status'] in {'SHIP', 'SOUND_ALIKE'}
           and (not row['sound_source'].startswith('http') or not ranged(row)
                or not droned(row) or chanter_bore(row) is None))
       or (row['status'] in {'SHIP', 'SOUND_ALIKE', 'ALIAS'} and taken(row))
       or (row['status'] == 'SOUND_ALIKE'
           and (row['alias_of'] not in bagpipe_parents
                or row['alias_of'] in APPROXIMATING_NAMES
                or not chanter_matches(row)))
       or (row['status'] == 'WAIT' and not row['waits_for'])
       or (row['status'] == 'ALIAS'
           and row['alias_of'] not in bagpipe_parents | alikes | set(instruments.CATALOG))]
bad += sorted({name for name in names if names.count(name) > 1})
print(len(rows), 'rows;', {status: sum(row['status'] == status for row in rows) for status in STATUSES})
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  Read the sheet with the csv module, never by splitting on tabs (batch 7 found CSV-quoted
  cells).

- [ ] **Step 4: The quote check,** `build/batch-12-quote-check.py`:
```python
"""Batch 12's quote check: uv run python -I build/batch-12-quote-check.py SHEET.

Batch 11's quote check (batch 11's plan, "Before the tasks" Step 4), extended to the drones
(batch 12's plan, "Quotes come from the raw page"): every SHIP and SOUND_ALIKE row's Range: and
Drones: passages are quoted between « and » from the raw text of the pages saved as
build/batch-12-pages/<name, spaces as hyphens>--<n>.txt. Each passage must be in one of them,
whatever its line breaks, and a passage whose source (range_source, drone_source) is Wikipedia
must have a citation after it in its own cell (a passage starting with "|") or its own paragraph,
before any uncited tag.
"""

import csv
import re
import sys
from pathlib import Path

PAGES = Path('build/batch-12-pages')
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


def quoted(notes, label, stop):
    """The «passages» after a label in the notes, up to the next label when one is given."""
    section = notes.partition(label)[2]
    if stop is not None:
        section = section.partition(stop)[0]
    return re.findall(r'«(.+?)»', section, flags=re.DOTALL)


with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
bad = []
for row in rows:
    if row['status'] not in {'SHIP', 'SOUND_ALIKE'}:
        continue
    slug = row['name'].replace(' ', '-')
    pages = [path.read_text(encoding='utf-8') for path in sorted(PAGES.glob(f'{slug}--*.txt'))]
    sections = (
        ('range', quoted(row['notes'], 'Range:', 'Drones:'), row['range_source']),
        ('drones', quoted(row['notes'], 'Drones:', None), row['drone_source']),
    )
    if not pages:
        bad.append((row['name'], 'no saved page'))
        continue
    for label, passages, source in sections:
        if not passages:
            bad.append((row['name'], f'no «passage» for the {label}'))
        for passage in passages:
            spans = [(page, located(page, passage)) for page in pages]
            found = [(page, span) for page, span in spans if span is not None]
            if not found:
                bad.append((row['name'], f'{label} not in the raw page: ' + passage[:60]))
            elif 'wikipedia.org' in source and not any(
                cited(page, span[0], span[1], passage) for page, span in found
            ):
                bad.append((row['name'], f'{label} uncited: ' + passage[:60]))
print('bad:', bad)
sys.exit(1 if bad else 0)
```
  It checks what can be checked mechanically. A worker still applies range ruling 10 in full (an
  `{{Unreferenced section}}` tag, a citation that covers another sentence or gives no range).

- [ ] **Step 5: The code check,** `build/batch-12-code-check.py`:
```python
"""Batch 12's code check: uv run python -I build/batch-12-code-check.py SHEET.

Batch 11's code check with batch 12's changes (batch 12's plan, "Before the tasks"): every row
is checked, the held-back guard and the retuned drones are compared with the sheet, every built
drone sounds the sheet's notes, and the builds, sound-alikes and aliases follow the sheet's
order. The test file's tables are read as literals, without importing the tests. A one-off check
may read the private _BAGPIPE_BUILDS; a test may not.
"""

import ast
import csv
import math
import sys

from glitchygames.audio import instruments
from glitchygames.audio.instruments.bagpipe_sound_alikes import BAGPIPE_SOUND_ALIKES
from glitchygames.audio.instruments.bagpipes import _BAGPIPE_BUILDS
from glitchygames.audio.pitch import Note

TEST_FILE = 'tests/audio/test_instrument_catalog.py'
EXISTING_COUNT = 8
SAME_DRONE_CENTS = 5.0


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


def built_drones(name):
    """The hertz of each drone source in the entry's built instrument, in source order."""
    return [
        float(source.pitch)
        for source_name, source in instruments.get(name).sources
        if source_name.startswith('drone_')
    ]


def sheet_drone_notes(row):
    return () if row['drones'] == 'none' else tuple(row['drones'].split())


def sheet_drones(row):
    """The row's drone notes as the hertz the code writes: equal-tempered, two decimals."""
    return [round(float(Note(note).to_hz()), 2) for note in sheet_drone_notes(row)]


def same_drones(first, second):
    return len(first) == len(second) and all(
        abs(1200.0 * math.log2(one / other)) <= SAME_DRONE_CENTS
        for one, other in zip(first, second, strict=True)
    )


with open(sys.argv[1], encoding='utf-8') as sheet:
    rows = list(csv.DictReader(sheet, delimiter='\t'))
rows_by_name = {row['name']: row for row in rows}
retuned = test_table('BAGPIPE_RETUNED_DRONES')


def held_back(row):
    """A WAIT for any reason but a sourced range, or an alias waiting for one."""
    if row['status'] != 'WAIT' or row['waits_for'] == 'a sourced range':
        return False
    if row['waits_for'].startswith('its target, '):
        target = rows_by_name.get(row['waits_for'].removeprefix('its target, '))
        return target is not None and held_back(target)
    return True


expected_retuned = {}
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
        if parent is not None and same_drones(built_drones(parent), sheet_drones(row)):
            assert dict(entry.sound_changes) == {}, name
        else:
            assert built_drones(name) == sheet_drones(row), name
        if parent is not None and not same_drones(built_drones(parent), sheet_drones(row)):
            expected_retuned[name] = sheet_drone_notes(row)
            assert set(entry.sound_changes) == {'drones'}, name
    elif row['status'] == 'ALIAS':
        assert instruments.ALIASES[name] == row['alias_of'], name
    else:
        assert name not in instruments.CATALOG, name
        assert name not in instruments.ALIASES, name
ship_names = [row['name'] for row in rows if row['status'] == 'SHIP']
alike_names = [row['name'] for row in rows if row['status'] == 'SOUND_ALIKE']
assert retuned == expected_retuned, 'BAGPIPE_RETUNED_DRONES'
assert list(retuned) == [name for name in alike_names if name in retuned], 'retuned order'
assert test_table('BAGPIPE_HELD_BACK') == {
    row['name']: row['waits_for'] for row in rows if held_back(row)
}, 'BAGPIPE_HELD_BACK'
assert test_table('NEW_BAGPIPE_NAMES') == ship_names, 'NEW_BAGPIPE_NAMES'
assert list(test_table('BAGPIPE_SOUND_ALIKE_PARENTS').items()) == [
    (row['name'], row['alias_of']) for row in rows if row['status'] == 'SOUND_ALIKE'
], 'BAGPIPE_SOUND_ALIKE_PARENTS'
assert [entry.name for entry in _BAGPIPE_BUILDS[EXISTING_COUNT:]] == ship_names, 'build order'
assert [entry.name for entry in BAGPIPE_SOUND_ALIKES] == alike_names, 'sound-alike order'
sheet_aliases = [row['name'] for row in rows if row['status'] == 'ALIAS']
assert [name for name in instruments.ALIASES if name in set(sheet_aliases)] == sheet_aliases, (
    'alias order'
)
print('matches', len(rows), 'rows')
```
  It cannot run until Task 1 has created `bagpipes.py`, `bagpipe_sound_alikes.py` and the test
  tables.

---

### Task 1: Bagpipes in their own module, unchanged; their sound-alikes module; the batch table's row; the held-back guard and the retuned-drones test

**Files:**
- Create: `src/glitchygames/audio/instruments/bagpipes.py`,
  `src/glitchygames/audio/instruments/bagpipe_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/winds.py`, `registry.py`, `flutes.py` and
  `double_reeds.py` (docstrings), `__init__.py` (one docstring sentence)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `BAGPIPES: Final[tuple[CatalogEntry, ...]] = _BAGPIPE_BUILDS + BAGPIPE_SOUND_ALIKES`
  in `bagpipes.py`, with `HIGHLAND_LEVELS`, `DRONE_LEVELS`, `SWEET_CHANTER_LEVELS`,
  `SMOOTH_DRONE_LEVELS` and `_bagpipe` there under their current names.
  `BAGPIPE_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]]` is empty. The test file gains
  `EXISTING_BAGPIPE_NAMES: frozenset[str]` (the 8); `NEW_BAGPIPE_NAMES: list[str]`,
  `BAGPIPE_SOUND_ALIKE_PARENTS: dict[str, str]`, `BAGPIPE_RETUNED_DRONES: dict[str, tuple[str,
  ...]]` and `BAGPIPE_HELD_BACK: dict[str, str]`, all empty here, for Tasks 3 and 5 to fill;
  `test_no_bagpipe_name_held_back_for_a_feature_is_listed`;
  `test_a_retuned_bagpipe_sounds_its_sourced_drones`; and the row `Family.BAGPIPES:
  BatchFamily(EXISTING_BAGPIPE_NAMES, NEW_BAGPIPE_NAMES, BAGPIPE_SOUND_ALIKE_PARENTS)` in
  `BATCH_FAMILIES`. Also `build/bagpipe-builds-before.txt`.

- [ ] **Step 1: Record the family's builds.** Run batch 4's Task 1 Step 1 command with
  `family='bagpipes'` and `build/bagpipe-builds-before.txt`. Expected: `recorded 8`.

- [ ] **Step 2: Write the tests.** Between the double reed lists and the brass lists (table
  order), add `EXISTING_BAGPIPE_NAMES` (the 8 names, one per line, in catalog order, with the
  comment "# The 8 bagpipes that predate batch 12: their shared builds predate the anti-goal
  rule"), then `NEW_BAGPIPE_NAMES: list[str] = []`, `BAGPIPE_SOUND_ALIKE_PARENTS: dict[str, str]
  = {}` and
```python
# Batch 12's bagpipe sound-alikes whose sourced drones differ from their parent's, with their
# drone notes (sounding, highest first), in the sheet's order: each is built with
# sound_changes={'drones': ...} (plans/data/instrument-audit/batch-12.tsv)
BAGPIPE_RETUNED_DRONES: dict[str, tuple[str, ...]] = {}
```
  each commented as batch 11's lists are. Put the bagpipes row between the double reeds and
  brass rows in `BATCH_FAMILIES`, which is table order. In
  `test_a_sound_alike_is_listed_and_builds_its_parents_sound`, the `BATCH_FAMILIES` loop's
  equality line becomes "`if name in BAGPIPE_RETUNED_DRONES:` assert the two instruments differ,
  `else:` assert they are equal", and the closing list gains `+ list(BAGPIPE_SOUND_ALIKE_PARENTS)`
  between the double reeds' and the brass lines, its comment reading "flutes, double reeds,
  bagpipes, brass, …". `CHANGED_SOUND_ALIKE_NAMES` gains `and catalog_entry.family !=
  Family.BAGPIPES`, and its comment says why: "a retuned bagpipe sustains, so the one-shot checks
  do not apply; test_a_retuned_bagpipe_sounds_its_sourced_drones checks it". After
  `test_no_double_reed_name_held_back_for_a_feature_is_listed`, add:
```python
# Every name plans/data/instrument-audit/batch-12.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# drone tuning or a sourced chanter bore, and the alias rows that wait for one of them, in the
# sheet's order. None ships under that name or as an alias until the reason is met (decision 4;
# batch 12). The test matches exact names
BAGPIPE_HELD_BACK: dict[str, str] = {}


def test_no_bagpipe_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a bagpipe the sheet holds back."""
    assert set(BAGPIPE_HELD_BACK) & set(instruments.names()) == set()
    assert set(BAGPIPE_HELD_BACK) & set(instruments.ALIASES) == set()


def test_a_retuned_bagpipe_sounds_its_sourced_drones():
    """A bagpipe sound-alike in another tuning sounds its own drones, equal-tempered.

    Decision 8's sound_changes: only the drones change, each at its sourced note (A4 = 440 Hz,
    two decimals, as the catalog's builds write hertz), so it differs from its parent.
    """
    retuned = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.BAGPIPES)
        if catalog_entry.sound_changes
    ]
    assert retuned == list(BAGPIPE_RETUNED_DRONES)
    for name, drone_notes in BAGPIPE_RETUNED_DRONES.items():
        catalog_entry = instruments.entry(name)
        assert set(catalog_entry.sound_changes) == {'drones'}, name
        drone_hertz = [
            float(source.pitch)
            for source_name, source in instruments.get(name).sources
            if source_name.startswith('drone_')
        ]
        assert drone_hertz == [round(float(Note(note).to_hz()), 2) for note in drone_notes], name
        assert instruments.get(name) != instruments.get(catalog_entry.sounds_like or ''), name
```

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or held_back or retuned or one_shot" -v`
  Expected: PASS, with the ID `[bagpipes]` third. These are guards: they pass now and hold the
  later tasks.

- [ ] **Step 4: Move the section.** Read every comment on the moved code first. Move `winds.py`'s
  "Bagpipes" section into `bagpipes.py` unchanged, comments included, with the tuple renamed
  `_BAGPIPE_BUILDS`, and define `BAGPIPES` after it as the concatenation, importing
  `BAGPIPE_SOUND_ALIKES`. The new module docstring's first line is "Bagpipes: reed chanters
  sounded from a bag, over fixed drones or none." It says what the family holds (a chanter of
  one or two pipes, double or single reed, conical or cylindrical, blown from a bag by mouth or
  bellows; Hornbostel–Sachs' -62 suffix, "with flexible air reservoir"), takes `winds.py`'s
  bagpipe words ("a bagpipe's chanter sounds over fixed drones", sounding pitch), and says that
  the sound-alikes are in `bagpipe_sound_alikes.py` and the other reed families in `winds.py`
  and `double_reeds.py`. `winds.py`'s docstring drops "bagpipes" from its first line ("Woodwinds:
  clarinets, saxophones and free reeds.") and its drone sentence, and names `bagpipes.py` beside
  `flutes.py` and `double_reeds.py`; its `wave_from_levels` and `with_drones` imports go if no
  remaining family uses them. `bagpipe_sound_alikes.py` gets the empty table and
  `double_reed_sound_alikes.py`'s docstring with "Bagpipes'" for "Double reeds'" and ending "The
  family's builds are in ``bagpipes.py``.", plus one sentence: "A sound-alike whose source gives
  it other drones carries them as ``sound_changes``, its only change." For the empty table it
  imports only what ruff accepts (`CatalogEntry` under `TYPE_CHECKING`); the task that adds the
  first sound-alike makes `CatalogEntry` and `Family` runtime imports, as
  `double_reed_sound_alikes.py` has them. Point `registry.py` at the new module. In `flutes.py`'s
  docstring, "the other reed families in ``winds.py``." becomes "the bagpipes in ``bagpipes.py``,
  the other reed families in ``winds.py``."; in `double_reeds.py`'s, "The other reed families are
  in the sibling module ``winds.py``." becomes "The bagpipes are in the sibling module
  ``bagpipes.py``, the other reed families in ``winds.py``."; in `__init__.py`'s, "``winds.py``
  keeps the clarinets, saxophones, bagpipes and free reeds." becomes "``winds.py`` keeps the
  clarinets, saxophones and free reeds." If the process-state guard then asks for an entry for
  `_BAGPIPE_BUILDS`, `BAGPIPES` or `BAGPIPE_SOUND_ALIKES`, that is a finding:
  `double_reed_sound_alikes.py` needed none, so read why before writing any reason.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command with
  `family='bagpipes'` and `build/bagpipe-builds-before.txt`, then
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
SKIP=replay-metrics git commit -m "Instrument catalog: bagpipes in their own module, unchanged; their sound-alikes module; the held-back guard and retuned drones" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
  Run each lint command as its own line (batch 11's Task 1: zsh word-splitting once made a
  combined run a no-op).

---

### Task 2: The Western European bagpipes sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. Put no personal data in any request, in a header,
a URL or a payload. Save each ranged row's raw pages under the plan's quote ruling. A list or
category page (`List_of_bagpipes`) is a source for a name only (and a Hornbostel–Sachs category
for the chanter class). The sound, the title, the range and the drones come from the
instrument's own page, or from an encyclopedia, maker, museum or piping society under range
ruling 7. The audit's rows and its "Range checks" are leads, not sources, so fetch them. Fetch the
page of every existing entry you name as a parent, and record its chanter and drones in the row's
notes. Never use `git stash`. This task may start as soon as the controller has written the
shared files, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-12.tsv`
- Create (not committed): `build/batch-12-half-a.tsv`, and the raw pages in
  `build/batch-12-pages/`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `bagpipes.md` ("Rejected or corrected
  proposed entries", "Aliases", "Range checks", "Gaps you could not close"); `batch-11.tsv`
  (`ciaramella`, `musette`); `build/batch-12-names-before.txt`, `build/batch-12-half-a.txt`,
  `build/batch-12-half-b.txt`, `build/batch-12-form-check.py` and
  `build/batch-12-quote-check.py`.
- Produces: `batch-12.tsv` with batch 11's header and two more columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags	drones	drone_source`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an ALIAS
  row's target or a SOUND_ALIKE row's parent. `family` is `bagpipes` on every row, and `tags` is
  empty on every row. A SHIP or SOUND_ALIKE row has `lowest`, `highest`, `range_source`,
  `drones` (sounding notes, highest first, or `none`), `drone_source`, an `hs` chanter class, and
  `notes` holding `Range:` and `Drones:`, each with its «raw passages» and derivation. `hs` is
  the Hornbostel–Sachs class a fetched source gives, else `none`. A candidate row's `audit_name`
  is its name in `build/batch-12-candidates.txt`; an alias row's is its audit line. Also
  `build/batch-12-half-a.tsv`, the half as committed, which Task 3's code check reads.

- [ ] **Step 1: Write one row per half-A candidate,** in `build/batch-12-half-a.txt`'s order,
  then one per half-A alias name (13), in the plan's order.

  The rules are batch 11's, changed for this family:

  1. **SHIP** only with name, title, chanter, range and drones from fetched sources. Quote in
     `notes` the passage that describes the sound or construction (chanter bore and reed, drones,
     bag, bellows or blowpipe, closed or open fingering) and, after `Range:` and `Drones:`, the
     «raw passages» and the derivations under the rulings. The `builder` cell gives the call
     (`_bagpipe` with its level tables and values, `CYLINDRICAL_CHANTER_LEVELS` under the plan's
     ruling) and says which values come from the source and which are sound design, copied from
     which entry.
  2. **SOUND_ALIKE**: a verified bagpipe that rule 7 finds would sound like an existing bagpipe or
     a SHIP row of this half. `alias_of` is its parent. The `notes` begin "Sound-alike:", quote
     the source's description, and say why that entry is the nearest (for a size or key: the
     entry its source relates it to, nearest in register). It has its own range and drones under
     the rulings, and the `builder` cell says "unchanged" or "retuned: drones <notes> at the
     parent's levels <levels>". Its `hs` chanter bore is its parent's built bore (the chanter
     ruling). The parent is a catalog bagpipe or a SHIP row of this half. It is never another
     sound-alike, never one of `APPROXIMATING_NAMES`, and never `scottish smallpipes`,
     `northumbrian smallpipes` or `musette de cour`.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a SHIP
     row or a SOUND_ALIKE row of this half. If the target waits, the row is WAIT with `waits_for`
     `its target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is
     dropped". An ambiguous name or a generic term is DROP under the plan's rulings.
  4. **WAIT** when the identifying sound needs something the engine or the sources lack, named in
     `waits_for` with the source quoted: `a sourced range`, `a sourced drone tuning`, `a sourced
     chanter bore`, `more than four sources`, `its own build (a detuned double chanter)`,
     `sub-audio fundamentals`, `a range above C8`, or another name of Global Constraints. The
     feature must be the sound the source describes, not a technique a player applies (the
     plan's "No new approximation"). Any other name is allowed only with the source quoted, and
     Task 6 lists it in #82.
  5. **DROP** a row that does not exist as described, belongs to another family (name it, and the
     boundary ruling's words), is a one-off, or is already decided: in the catalog under that
     name (name the entry), an alias already (name its target), or a row of an earlier sheet
     (name the sheet and its status).
  6. A row the audit marks "(memory)" or that cites only `List_of_bagpipes` has no sourced sound
     or range yet. Fetch the instrument's own page; the audit's URL is a lead. If no page can be
     found, the row is DROP "no fetched source describes it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every family entry
     (`uv run python -I -c "from glitchygames.audio import instruments as i; print(i.names(family='bagpipes'))"`
     and the builds in `bagpipes.py`) and every SHIP row above it. If no sourced trait (chanter
     bore, drones, a closed chanter) makes it sound different, it is a SOUND_ALIKE under rule 2. A
     number chosen only to differ does not count, and neither does a difference of 1 or 2 percent
     in a value (batch 11's contraforte) nor a range, a key, a scale or the way notes are chosen
     (keys, a flea hole, regulators, a double chanter's second melody). Drone pitches are a
     sourced trait, and the retuned sound-alike carries them.
  8. **Duplicates in the candidates:** one row decides the instrument. The other is ALIAS when a
     person would type that name, else DROP "the audit's name for <row>". Rows that only share a
     word are decided each on its own page.

  This half's own cases:

  - **Britain and Ireland.** `reel pipes` is both a candidate ("Reel pipes (half-set)", a
    scaled-down Highland pipe) and the audit's alias of `border pipes` ("(Border sense)"): one row
    decides it, and if its sources give the name to both, it is DROP under the ambiguity ruling.
    `great irish warpipes` and `brian boru bagpipes` relate to `highland bagpipe` only where their
    source does, each retuned under the ruling; the Brian Boru's keyed chanter is part of its
    compass if its source ranges it, and three distinct drone pitches ("three drones incl
    baritone") make it WAIT `more than four sources`. `pastoral pipes`' regulators and keys are
    notes, not sound. `zetland pipes` and `cornish bagpipes` follow the reconstruction ruling.
    `scottish smallpipes in d` cannot take the catalog's `scottish smallpipes` as parent (the
    never-parents ruling): it SHIPs with the cylindrical chanter table if its source cites the
    bore and ranges the D chanter with its octave, or WAITs. `union pipes` and `irish pipes` are
    ALIAS of `uilleann pipes`, `lowland pipes` and `half long pipes` of `border pipes`, each on a
    cited page that gives the name to that instrument.
  - **France and Flanders.** The Biniou page (Wikipedia now redirects `Biniou` to `Binioù`) gives
    the biniou kozh "an octave above the bombarde": a relation, not a range (ruling 7). `biniou
    braz` is ALIAS of `highland bagpipe` only where a cited page says the biniou braz is the
    Highland pipe itself, not a Breton copy of it (then a size or relation under rule 2, decided on
    its page). `cabrette`'s "drone not necessarily functional" follows drone ruling rule 2;
    `chabrette` and `chabretta` follow `cabrette` (rule 3). `bousine` is droneless by the audit:
    its drones are `none` only on a fetched source. `boha`, `veuze`, `caramusa`, `doedelzak` and
    `cornemuse du centre` are decided on their pages, the last under the generic-term ruling if
    its page gives several types.
  - **Iberia.** `gaita galega` is ALIAS of `galician gaita` on a cited page. `gaita asturiana`,
    `gaita sanabresa`, `gaita transmontana` and `gaita de saco` relate to `galician gaita` only
    where their source does (each retuned under the ruling, with its own key's range).
    `gaita mirandesa` follows `gaita transmontana`. `gaita alistana`, `cabreiresa` and `coimbra`
    are the audit's "gaita de saco family (scale presets)": each is decided on its own page, and
    a scale is no sound trait (rule 7). `gaita de boto`'s "tenor drone parallel to chanter",
    `sac de gemecs`, `xeremies` (a double chanter: range ruling 4) and `odrecillo` are decided on
    their pages.
  - **Italy.** `zampogna` and `ciaramedda` are double chanters ("two chanters which play a melody
    and harmony", the Ciaramedda page): range ruling 4 spans both, each stated, and the drones
    follow drone ruling rule 2 ("The three drones … Some pipes just have two drones. In Sicily,
    often only the middle drone is reeded while the other two remain muted"). The Ciaramedda
    page's reed is "the single blade cane reed mounted in the chanters and drones", so its chanter
    is a single reed (422.2) whose bore a source must give. `surdullina` ("very short single-reed
    chanter") relates to `zampogna` only where its source does. `surdelina`'s "key-switched
    drones" follow drone ruling rule 5. `piva` and `baghet` are decided on their pages.
    `ciaramella` is DROP under the boundary ruling's words.
  - **`electronic bagpipe`** is DROP under the boundary ruling if its fetched page makes it an
    electrophone (the audit: "An electrophone imitating the highland bagpipe (H-S 5)").

- [ ] **Step 2: Run the form check and the quote check.**
  Run: `uv run python -I build/batch-12-form-check.py plans/data/instrument-audit/batch-12.tsv`
  and `uv run python -I build/batch-12-quote-check.py plans/data/instrument-audit/batch-12.tsv`.
  Expected: `44 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 3: Check the half.**
```bash
uv run python -I -c "
import csv
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-12.tsv', encoding='utf-8'), delimiter='\t'))
audit_names = [row['audit_name'] for row in rows]
half_a = {line for line in open('build/batch-12-half-a.txt', encoding='utf-8').read().split('\n') if line}
half_b = {line for line in open('build/batch-12-half-b.txt', encoding='utf-8').read().split('\n') if line}
print('missing:', sorted(half_a - set(audit_names)))
print('twice:', sorted({name for name in half_a if audit_names.count(name) > 1}))
print('from half B:', sorted(half_b & set(audit_names)))
"
```
  Expected: `missing: []`, `twice: []` and `from half B: []`.

- [ ] **Step 4: Keep the half and commit**
```bash
cp plans/data/instrument-audit/batch-12.tsv build/batch-12-half-a.tsv
git add plans/data/instrument-audit/batch-12.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 12's verification sheet, the Western European bagpipes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The Western European bagpipes

**Files:**
- Modify: `bagpipes.py` (new builds after the 8, `CYLINDRICAL_CHANTER_LEVELS` if a row needs it),
  `bagpipe_sound_alikes.py` (`BAGPIPE_SOUND_ALIKES`), `aliases.py` (each ALIAS row, with its
  source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `build/batch-12-half-a.tsv` (half A as committed), Task 1's tables and
  `build/batch-12-code-check.py`.
- Produces: `NEW_BAGPIPE_NAMES`, `BAGPIPE_SOUND_ALIKE_PARENTS`, `BAGPIPE_RETUNED_DRONES` and
  `BAGPIPE_HELD_BACK` filled with this half's rows, which Task 5 extends; and, if a half-A row
  needs it, `CYLINDRICAL_CHANTER_LEVELS: Final[tuple[float, ...]]` in `bagpipes.py`.

If half A has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling: Step 1 fills
only `BAGPIPE_HELD_BACK`, Step 4 runs as written, and Step 5 commits the test file alone.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_BAGPIPE_NAMES` with one name per SHIP row,
  `BAGPIPE_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE row, and
  `BAGPIPE_RETUNED_DRONES` with one `name: (drone notes)` per retuned SOUND_ALIKE row (the plan's
  retuned ruling: drones more than 5 cents from the parent's, or another number of them; `()` for
  a droneless one), each in the sheet's order. Fill `BAGPIPE_HELD_BACK` with one `name:
  waits_for` per held row (every WAIT row whose reason is not `a sourced range`, and every `its
  target, <name>` row whose target is held), in the sheet's order. Add the ALIAS rows to
  `test_the_batch_aliases_resolve`'s parameters, in the sheet's order, with a docstring sentence
  for batch 12. A shipped size joins or starts its chain in
  `test_sized_families_descend_from_highest_to_lowest` under the plan's sizes ruling. If a SHIP
  row builds with `CYLINDRICAL_CHANTER_LEVELS`, add:
```python
def test_a_cylindrical_chanter_sounds_odd_harmonics():
    """A cylindrical chanter's even harmonics are far below its odd ones; a conical one's are not.

    The chanter alone (its drones removed), at its middle note: a closed cylinder favours odd
    harmonics (the bore source in the entry's comment), where every older bagpipe's chanter has
    every harmonic.
    """
```
  Its body renders, for the first SHIP row built with the table and for `highland bagpipe`, the
  entry's own build with `drones=()` (the build is a `functools.partial` of `_bagpipe`: call
  `build.func(**{**build.keywords, 'drones': ()})`) at the entry's `middle_note()`, takes the
  spectrum's peaks at harmonics 1 to 4 as `test_the_nes_triangle_buzzes_from_its_thirty_two_steps`
  does, and asserts the cylinder's harmonics 2 and 4 are each below 0.05 of its harmonic 1 while
  the Highland chanter's harmonic 2 is above 0.3 of its harmonic 1.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases or descend or held_back or retuned or cylindrical" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`; the
  held-back test passes.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in
  `BAGPIPE_SOUND_ALIKES`, in the sheet's order, under a section comment naming
  `plans/data/instrument-audit/batch-12.tsv` as `double_reed_sound_alikes.py`'s does, each a
  `CatalogEntry(name, title, Family.BAGPIPES, lowest, highest, sounds_like=parent)`, a retuned one
  with `sound_changes={'drones': ((hertz, level), ...)}` (hertz to two decimals, the parent's
  levels by rank). Above each, put a comment with its `sound_source`, `range_source` and
  `drone_source` URLs, the quoted passages and the derivations of the range and the drones, as
  `double_reed_sound_alikes.py`'s entries have. A SHIP row is a `CatalogEntry` after the 8 in
  `_BAGPIPE_BUILDS`, a `partial(_bagpipe, ...)` carrying the same comment and marking the values
  that are sound design and the entry they are copied from. Add `CYLINDRICAL_CHANTER_LEVELS` beside
  `SWEET_CHANTER_LEVELS` only if a row needs it, with the value and comment of the plan's ruling.
  Each ALIAS row goes in `aliases.py` under a "Batch 12's bagpipes" section, in the sheet's order,
  with its URL and quote. Comments name only committed files.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` for every new entry.
  A failure at a range end is a finding about the range or the build. Check it against the
  source, and never trim the range to pass. Then run:
  `uv run python -I build/batch-12-code-check.py build/batch-12-half-a.tsv`
  Expected: `matches 44 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 12's Western European bagpipes, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The Central, Northern and Eastern European, Mediterranean, Middle Eastern, African and Asian bagpipes sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written the shared
files, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-12-half-b.tsv`, half B's rows under the sheet's header,
  and its raw pages in `build/batch-12-pages/`
- Modify: `plans/data/instrument-audit/batch-12.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8 and header, `build/batch-12-form-check.py`,
  `build/batch-12-quote-check.py` and `build/batch-12-half-b.txt`.
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-12-half-b.txt`'s order, then one per half-B
alias name (12), in the plan's order. A parent or alias target is a catalog name or a SHIP or
SOUND_ALIKE row of this half, never a half-A row. These rules apply to this half on top of Task
2's:

- **The German and Swiss names.** `dudelsack`, `sackpfeife` and `schaferpfeife` follow the
  generic-term ruling if their pages make them words for any bagpipe; otherwise each is decided
  as an instrument or an alias on its page. `marktsackpfeife` follows the reconstruction ruling,
  and `swiss sackpfeife` ("double reeds, one or two drones") drone ruling rule 2.
- **The dudy.** `dudy` (the Czech bock), `sorbian dudy`, `polish dudy` and `mechawka` are each
  decided on their page; the Gaita page's tonics ("Eb (large), F (dudki), A (mechawka)", the
  audit) are keys, not ranges (ruling 5). `bock` follows `dudy` (rule 3) if a cited page makes it
  that instrument's name.
- **Baltic, Nordic, Hungarian and Russian pipes.** `magyar duda` ("double-bored chanter, single
  reeds", a flea hole: notes, not sound), `latvian dudas`, `dudmaisis`, `torupill`, `sakkipilli`,
  `sackpipa` ("cylindrical bore, single reed") and `volynka` are decided on their pages; a
  single-reed or cylindrical chanter follows the chanter ruling. `mutsianka` is the audit's
  "(memory)" alias of `volynka` (rule 6).
- **The gaidas.** `macedonian gaida`, `kaba gaida` and `dzhura gaida` relate to the catalog's
  `bulgarian gaida` (F#4-A5, one drone at 196 Hz) only where their source does, each with its own
  range and drones (retuned under the ruling); the Kaba gaida's "long low drone" is a drone
  pitch only with its note. `gajdy`, `gajde` and `gayda` are ALIAS of `bulgarian gaida` only on a
  cited page giving the name to that instrument; a name the sources give to several bagpipes
  (the Slovak and Polish gajdy, the Macedonian and Serbian gajde) is DROP under the ambiguity
  ruling. `cimpoi` is decided on its page.
- **Droneless double chanters.** `istarski mih`, `zaqq`, `askomandoura`, `tsampouna`, `tulum`,
  `parkapzuk`, `gudastviri`, `ney anban`, `jirba` and `zummarah bi soan` are double chanters, most
  droneless: range ruling 4 decides how the two pipes are ranged, a pipe that holds a note is a
  drone ("second chanter acts as drone", the audit's tsampouna), and pipes tuned apart to beat wait
  under the double-chanter ruling. The Istrian scale is a scale, not a range. `dankiyo` ("one
  chanter with two reeds") is decided on its page. `tulug` and `guda` follow `tulum` (rule 3);
  `guda` may name a Georgian bag or the gudastviri, in which case the ambiguity ruling decides.
- **North Africa and Arabia.** `zukra` is decided here (batch 11 dropped it to this batch): its
  page's "double-chanter terminating in two cow horns" and "played … by mouth without a bag (as a
  double clarinet) in the east" make it a set of single-reed pipes (422.22x) when bagged, so it is
  no sound-alike of a conical bagpipe (the chanter ruling). `mizwad` is ALIAS of `zukra` only on a
  cited page calling them one instrument; the Zukra page's "similar in construction to the Tunisian
  mizwad" is a relation, so otherwise DROP "a distinct instrument with no candidate row".
  `habban` follows the generic-term ruling if its page gives "Bedouin types and Highland-style
  Omani". `tadghtita` is decided on its page.
- **South Asia.** `mashak` ("single reeds, drone or melody"; "many Indian instruments are
  Highland-style copies", the audit) is decided on its page; `mushak baja` and `masak been` (the
  audit's aliases of `highland bagpipe`) are ALIAS of whichever instrument a cited page names them
  for: `mashak` if it ships, else WAIT `its target, mashak`, or `highland bagpipe`. `titti` is
  decided on its page. `sruti upanga` ("cane drone only, no chanter") is a one-note instrument
  under range ruling 9.

- [ ] **Step 1: Write half B's rows** to `build/batch-12-half-b.tsv`, and check them alone.
  Run: `uv run python -I build/batch-12-form-check.py build/batch-12-half-b.tsv` and
  `uv run python -I build/batch-12-quote-check.py build/batch-12-half-b.tsv`.
  Expected: `47 rows;` and the counts, then `bad: []`, exit 0; then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-12-half-b.tsv >> plans/data/instrument-audit/batch-12.tsv`.
  Run the form check and the quote check on the whole sheet.
  Expected: `91 rows;` and the counts, then `bad: []`, exit 0, twice. If Task 3 has run, half
  A's coded rows are accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 2 Step 3's command
  with `half_a | half_b` in place of `half_a` on its `missing:` and `twice:` lines, and print
  `'extra:', sorted(set(audit_names) - half_a - half_b)` in place of the half-B line.
  Expected: `missing: []` and `twice: []`. `extra:` lists only the alias lines, because an alias
  row's `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-12.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 12's verification sheet, the Central, Northern and Eastern European, Mediterranean, Middle Eastern, African and Asian bagpipes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The Central, Northern and Eastern European, Mediterranean, Middle Eastern, African and Asian bagpipes

**Files:**
- Modify: `bagpipes.py`, `bagpipe_sound_alikes.py`, `aliases.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-12.tsv`'s half-B rows, Task 3's tables (and `CYLINDRICAL_CHANTER_LEVELS` if
  Task 3 added it) and `build/batch-12-code-check.py`.
- Produces: the finished family.

If half B has no SHIP, SOUND_ALIKE or ALIAS row, skip Steps 2 and 3 by ruling, as Task 3 says.

- [ ] **Step 1: Write the failing tests:** append this half's rows to `NEW_BAGPIPE_NAMES`,
  `BAGPIPE_SOUND_ALIKE_PARENTS`, `BAGPIPE_RETUNED_DRONES`, `BAGPIPE_HELD_BACK` and the alias
  parameters, after half A's, as in Task 3 Step 1, with any chain, and
  `test_a_cylindrical_chanter_sounds_odd_harmonics` if Task 3 did not add it and a half-B row
  needs the table.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries,** as in Task 3 Step 3, after half A's: builds after half A's
  builds, sound-alikes after half A's sound-alikes, aliases after half A's aliases, under a
  second section comment naming the sheet.

- [ ] **Step 4: Run the suite and check the code against the whole sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`, then
  `uv run python -I build/batch-12-code-check.py plans/data/instrument-audit/batch-12.tsv`.
  Expected: PASS, then `matches 91 rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 12's Central, Northern and Eastern European, Mediterranean, Middle Eastern, African and Asian bagpipes, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a bagpipes
  paragraph with its count, naming `bagpipes.py` and `bagpipe_sound_alikes.py`, with examples, in
  the double reeds paragraph's form, and saying that a sound-alike in another tuning carries its
  own drones as `sound_changes`.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `bagpipes` row's
  count and examples, the sound-alike modules sentence and its total, and one sentence on the
  retuned drones).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the entry, alias and sound-alike
  counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 12
  done, pointing at this plan and `batch-12.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 12 DONE";
  - batch 12 done, with the sheet's counts by status and the family's growth, the module move
    (`bagpipes.py`; `winds.py` keeping the clarinets, saxophones and free reeds), the retuned
    sound-alikes, and the branch's base SHA;
  - the audit's unclosed gaps, as a later pass;
  - the hand-offs: `zukra` and `ciaramedda` decided here (`ciaramella` stays batch 11's),
    `electronic bagpipe` for a later electronic pass if dropped there, and any name the sheets
    found that belongs to the organs batch;
  - a "Plan (batch 12)" line, the Status line, and the next batch named: organs.

  Add #82 (the highest item is #81), "Sound Engine: The Owner's Checks on Instrument Catalog
  Batch 12 — TODO". Use #81's form (as #75 began it), place it directly after #81, and give it
  the Priority "(before the organs batch builds on the same catalog)". Its **Listen** section
  (`build/instruments/bagpipes/`) covers the new builds, then the sound-alikes beside their
  parents (the retuned ones named, with their drones), then the aliases. Its **Calls to confirm**
  are:
  - every WAIT, by reason, with names;
  - the range ruling (stated or an exact span, sounding pitch, a compass relative to a tonic only
    with the tonic's octave fixed, no extension or extreme, never hedged, a width, a key or a
    relation, the standard key, maker, museum and piping-society sources over uncited Wikipedia
    lines, nothing below A0 or above C8, one-note instruments, cited Wikipedia lines whose
    citation supports them), and every derived range;
  - the nominal-pitch ruling (the nearest semitone from a stated sounding pitch, a span's
    midpoint, the 10-cent margin at a quarter tone) and each row it shifted;
  - the drone ruling (sourced pitches, unison drones once, muted drones out, at most two, drones
    equal-tempered like the chanter, keyed drones as notes) and every derived drone;
  - the retuned sound-alikes: `sound_changes={'drones': ...}` as decision 8's first shipped use,
    the parent's levels by rank, the 5-cent line, and the test changes it needed
    (`CHANGED_SOUND_ALIKE_NAMES` no longer holds bagpipes; the sound-alike test's equality skips
    the retuned);
  - the chanter ruling (H-S 422.abc, conical parents only, `a sourced chanter bore` as a new wait
    name) and `CYLINDRICAL_CHANTER_LEVELS` if added, with the trait its source names;
  - `scottish smallpipes`, `northumbrian smallpipes` and `musette de cour` never parents (uncited
    cylinder lines), and whether any should join `APPROXIMATING_NAMES`;
  - one-note instruments waiting for a range (`sruti upanga`): should they ship as fixed-pitch
    entries?
  - double chanters (two melodies as notes of one sequence; a detuned pair waiting for its own
    build);
  - no new approximation: grace notes, closed fingering, regulators, flea holes and bellows as
    technique or notes;
  - sizes and keys as sound-alikes, other names as aliases, and any new size chain;
  - the boundaries: `ciaramella` (batch 11's) and `ciaramedda`, `zukra` and `mizwad`, `electronic
    bagpipe`;
  - generic and ambiguous terms dropped (`dudelsack`, `sackpfeife`, `habban`, `reel pipes`,
    `gajdy` and the rest, as decided);
  - one-offs, reconstructions and unsourced rows, and the in-production line;
  - the naming ruling (`scottish smallpipes in d`, the key after the name as the bagpipes' titles
    have it);
  - the module move;
  - `BAGPIPE_HELD_BACK`, the guard for every non-range wait;
  - the two-half split as explicit lists, the sheets researched in parallel, the shared files
    written up front, and any code task skipped by ruling;
  - any engine feature named beyond the spec's table (`its own build (a detuned double chanter)`
    if used), for its "What the engine cannot make yet".

  Then **Bugs to report** (found while building, none fixed here): `highland bagpipe`'s drones at
  240 and 120 Hz, 51 cents above its chanter's B♭ (its page: "The drones are tuned to this tonic
  note"); the three cylindrical chanters built with every harmonic (`scottish smallpipes`,
  `northumbrian smallpipes`, `musette de cour`, uncited); and, as leads the sheets confirm or
  not, the Northumbrian page's "three will usually be tuned to the tonic, dominant and octave
  tonic" against the build's two octave G drones (196 and 98 Hz), the Border pipes page's three
  drones "typically tuned A, a, e'" against its build's two (220 and 110 Hz), and the uilleann
  pipes' three drones against its build's two; `winds.py`'s docstring calling the folk ranges
  "typical of the common keys" without a source (moved with the clarinets and free reeds); the 8
  earlier entries' missing source comments; any existing range or build a sheet's source
  contradicts. Then **Follow-ups**: the audit's gaps; ranging the range WAITs from maker, museum
  and piping-society sources; checking the 8 earlier entries against sources; the engine changes
  that unblock the waits, most rows first.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries())); print(sum(bool(e.sound_changes) for e in i.entries()))"`
  and `uv run python -I build/batch-12-form-check.py plans/data/instrument-audit/batch-12.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
uv run python -I build/batch-12-code-check.py plans/data/instrument-audit/batch-12.tsv
uv run python -I build/batch-12-quote-check.py plans/data/instrument-audit/batch-12.tsv
```
  Expected: everything passes with no warnings (a warning is a finding; #81 records the
  third-party `speech_recognition` DeprecationWarning under `-W error`, so a new one is a new
  finding), `matches 91 rows`, and `bad: []`. The `build/instruments/bagpipes` folder is the one
  to listen to; the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 12 of the instrument catalog (bagpipes), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch
in turn and stack them into PRs"; pushes and stacked PRs happen without asking, 2026-11-12, #78).
The pre-push hooks take about 40 minutes, and nothing in the working tree may change while they
run.

**Order:** the controller's shared files, then Tasks 1, 2 and 4 in parallel. Task 3 follows
Tasks 1 and 2. Task 4's append waits for Task 2's commit. Task 5 follows Tasks 3 and 4, and Task
6 comes last.
