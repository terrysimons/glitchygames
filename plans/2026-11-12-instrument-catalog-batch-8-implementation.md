# Instrument catalog batch 8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the voices and choirs families from the audit's candidates. Voices are the kinds
of singer and the devices a person sings through. Choirs are one part of a choir. Each
instrument gets a cited source and either sounds unlike every other entry or is a listed
sound-alike of the one it sounds like. The rest become aliases, wait for an engine feature or a
sourced range, or are dropped with a reason.

**Architecture:** As in batches 3 to 7, a verification sheet (`batch-8.tsv`) decides every
candidate before any code is written. Both families' 68 entries stay in `voices.py`, which
shares one formant table between them. Its two tables become `_VOICE_BUILDS +
VOICE_SOUND_ALIKES` and `_CHOIR_BUILDS + CHOIR_SOUND_ALIKES`, and the sound-alikes go in a new
`voice_sound_alikes.py`. Both families are wholly pitched, so the batch table's
`unpitched_names` stays empty in both rows. The sheet and the code each come in two halves, one
per family: voices, then choirs. The two sheet halves may be researched at the same time.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`: `blown`, `formant_series`,
`Formant`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md` (decisions 1–8 bind; 4 and 8
above all). Batch 7's plan (`plans/2026-11-12-instrument-catalog-batch-7-implementation.md`) is
this plan's template. Batch 4's (`plans/2026-11-09-instrument-catalog-batch-4-implementation.md`)
holds the pitched sound-alike and strict range rules. This plan's own path is
`plans/2026-11-12-instrument-catalog-batch-8-implementation.md`. The branch is
`feat/instrument-catalog-batch-8`, made from `feat/instrument-catalog-batch-7` (HEAD `29ab4064`).
The candidates come from `plans/data/instrument-audit/`:
- the `merged.tsv` rows whose `family` is `voices` (68) or `choirs` (38), all from the round-2
  audit `voices-and-choirs.md`;
- the `round-1/merged-missing.tsv` rows whose `family` contains `voice` (2: `vocoder`, `voder`;
  batch 6 already decided both);
- two hand-offs that no family has decided: `kazoo` (the spec's boundary call: "the kazoo goes
  in voices (it colours a voice)") and `swazzle`. Both are round-1 rows in a proposed "singing
  membranes / mirlitons" family, which the spec never made.

Together: **110 unique candidate names**: 72 voices and 38 choirs, counted for this plan, and
Task 2 Step 1 recounts them. None is in the catalog or the alias table today. The audit's
"Aliases" section proposes 28 more names on 16 lines. Earlier sheets decided four of the
candidates: `talk box`, `sonovox`, `vocoder` and `voder` are batch 6 WAIT rows (`moving
formants`). `plans/future-features.md` #70–#77 leave nothing else for these families.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`, checked with
  `fullmatch`). A voice entry's name is `<voice type> <sound>`, and a choir entry's is
  `choir <part> <sound>`, as all 68 existing entries are (`soprano ah`, `choir alto oo`). Accents,
  hyphens and parentheses go only in the title (`haute contre ah`, title `Haute-contre (ah)`).
- "A family is defined by how the sound is made" (spec, Families), with "the existing
  player-facing splits kept where they already exist (keyboards and organs; voices and
  choirs)". The boundary call: "the kazoo goes in voices (it colours a voice)".
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1). The owner kept this strict (2026-11-09, "Keep it strict").
  This plan's range ruling for voices and choirs is below, under "Decisions". A row with no
  sourced range is WAIT, `waits_for` `a sourced range`.
- Decision 8: "A verified instrument that sounds like an existing entry is its own entry,
  sharing the parent's build (`CatalogEntry.sounds_like`) … a true alias (another name for the
  same instrument) stays an alias." A sound-alike is pitched exactly when its parent is, and a
  pitched sound-alike gives its own sourced range (batch 4).
- Decision 4: "Instruments the engine cannot make well yet wait for the feature". None ships as
  an approximation, under its real name or a qualified one. The spec's table names this
  family's waits: "moving formants, vowel glides, vibrato | overtone and throat singing, talk
  box, vocoder, yodel". Batch 6 added the other names a WAIT may give: a pitch LFO (vibrato), a
  pitch LFO (portamento between notes), an amplitude LFO, filter resonance, a filter envelope,
  more than four sources and moving formants. Batch 5 added a buzzing membrane (the gyil's
  mirlitons), and batch 7 added its own build. What the engine has: up to four `Source`s, one
  glide per note (`pitch_curve`), and static formants baked into the harmonic levels at one
  fundamental (`formant_series`; the module docstring says "the vowel is truest mid-range (no
  formant filter moves with the note here)"). It also has breath noise, a fixed FIR low or high
  pass, `drive` 0–20, and `blown`'s chorus copy (`chorus_cents`: 3 for a solo voice, 11 for a
  choir).
- `Instrument(profile=...)` stays `hybrid`.
- Anti-goal: "Bulk-adding hundreds of instruments that all sound like the same three timbres."
  (spec, Anti-goals). Sound-alikes are decision 8's exception, because they add names, not
  builds.
- Reuse `voices.py`'s parts (`FORMANT_TABLE`, the Csound manual's five voice types on five
  vowels; `SINGER_FORMANT`; `HUM_FORMANTS`; `_formants`; `_middle_hz`; `_sung`) and the shared
  `blown` and `formant_series`. Add a builder only for a genuinely new sound, and give it its
  own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: "When you use a reference (not just look at it, but use content from
  it) you need to attribute it with a comment pointing to the source."). Every quote in the
  sheet is verbatim from a page the worker fetched.
- The 68 entries already in the families (55 voices, 13 choirs) keep their names, titles,
  ranges, builds and order. New entries come after them. An existing entry changes only for a
  cited bug, reported to the owner.
- Code style: "Make sure to use the code style already present in the project": Google
  docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage. "I don't like short
  abbreviated variables." "explicit is better than implicit." "Whenever you see warnings thrown
  by a test, you should understand why it's happening and be concerned": a warning is a
  finding, and it must be understood before going on.
- Commits as batches 4 to 7: `SKIP=replay-metrics git commit`, with the subject `Instrument
  catalog: …`, `Instrument audit: …` or `Docs: …`. The trailer line must be exactly
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents on other models have
  substituted their own name (#76, "Bugs to report"), so copy each commit message from this
  plan, never from memory. Write no `.md` file beyond those Task 6 names.

## Review Focus

1. **A technique or genre shipped as an instrument.** Thirty-odd voice rows are things any
   singer does (`falsetto male`, `belt voice`, `scat singing`, `whisper voice`, `beatbox
   snare`). Most choir rows are repertoires (`gregorian chant`, `barbershop quartet`, `gospel
   choir`). Shipping them would put a style where a person expects an instrument. The "what a
   candidate is" ruling decides them. The form check requires every SHIP or SOUND_ALIKE row's
   notes to name one of the four instrument kinds (`Kind: voice type`, `Kind: voice device`,
   `Kind: choir part`, `Kind: choir vowel`).
2. **A hedged or extreme range read as a voice type's range.** Voice-type pages hedge
   ("approximately middle C"), give extremes ("some coloratura roles to F6") or contradict
   themselves (the Voice type page's countertenor: caption E3–E5, text C4–C6 and D3–D5). The
   range ruling refuses all three. The form check requires a `Range:` passage on every pitched
   row, and the code check compares every range with the sheet.
3. **An approximation of a spec-listed wait.** The audit offers stand-ins: `sygyt` as "sine
   melody over drone", `vocoder voice` as "a static robot vowel", `yodel` as two formant sets.
   Decision 4 refuses each one, under the real name or a qualified one. Task 1's test refuses
   any catalog name or alias in `MOVING_FORMANT_NAMES`, and the form check refuses a SHIP or
   SOUND_ALIKE row whose `audit_name` is in that set.
4. **A candidate decided twice.** `talk box`, `sonovox`, `vocoder` and `voder` are batch 6
   WAITs. `vox humana` and `voix celeste` are organ stops that the organs audit also rows. The
   form check refuses a SHIP, SOUND_ALIKE or ALIAS row whose name the catalog or alias table
   held before this batch. Rule 5 gives each decided row a DROP that names the sheet and its
   status. Task 6 tells #70 that the organs batch decides the two stops.
5. **A choir vowel whose range is not its part's.** The new `choir … eh`, `ee` and `hum` rows
   join parts whose entries share one range (`CHOIR_PARTS`). A new vowel with another range
   would split a part in two. The choir-vowel ruling ships a vowel only on a sourced range equal
   to its part's. Task 5's test pins every choir entry of a part to one range.

---

## File Structure

- Modify `src/glitchygames/audio/instruments/voices.py`. `VOICES` becomes `_VOICE_BUILDS +
  VOICE_SOUND_ALIKES` and `CHOIRS` becomes `_CHOIR_BUILDS + CHOIR_SOUND_ALIKES`, with each
  existing entry unchanged. New voice builds go after `whistling`. New choir builds go after
  `childrens choir`, from a table `ADDED_CHOIR_SOUNDS`.
- Create `src/glitchygames/audio/instruments/voice_sound_alikes.py`, holding
  `VOICE_SOUND_ALIKES` and `CHOIR_SOUND_ALIKES`.
- Modify `aliases.py`, adding the batch's ALIAS rows.
- Modify `tests/audio/test_instrument_catalog.py` (Tasks 1, 3 and 5) and
  `tests/test_process_state_guard.py`. In the guard, `voices.py`'s two R16 reasons move from
  `VOICES` and `CHOIRS` to `_VOICE_BUILDS` and `_CHOIR_BUILDS`. `VOICES` and `CHOIRS`, now
  concatenations of two read-only tuples, need no entry, as `BOWED_STRINGS` needs none.
- Create `plans/data/instrument-audit/batch-8.tsv` (Tasks 2 and 4).
- Docs (Task 6): the `instruments/__init__.py` docstring, `docs/architecture/sound.md`,
  `CLAUDE.md`, `plans/future-features.md` (#70 and a new #78), and the design's status line and
  "Depends on" counts.

Decisions made in this plan (my calls, for the owner to check in #78):

- **One module, two tables; no split.** `voices.py` is 214 lines and holds exactly these two
  families. They share `FORMANT_TABLE`, `_formants`, `_middle_hz` and `_sung`. A `choirs.py`
  would import four private helpers from `voices.py` and buy nothing. Batches 4, 6 and 7 split
  a family out because its file held families that other batches grow, which is not the case
  here. The sound-alikes still get a module of their own, `voice_sound_alikes.py`, which names
  `voices.py` as the builds' home. It holds one table per family, because `FAMILY_TABLES` holds
  one tuple per family.
- **What a candidate is.** A catalog entry is an instrument. For these families, an instrument
  is one of four kinds, and the `notes` cell names it as `Kind: …`:
  1. *Voice type*: a category of singer by range and weight in a published voice classification
     (the voice-type system, the German Fach). It includes historical, liturgical and child types
     (`castrato`, `oktavist`, `boy alto`, `coloratura soprano`, `heldentenor`).
  2. *Voice device*: a device held to or in the mouth or throat that a person sings or speaks
     through (`kazoo`, `swazzle`, `electrolarynx`; batch 6's `talk box` and `sonovox`).
  3. *Choir part*: a choir of one voice type singing one part (the existing `choir soprano ah`,
     `childrens choir`).
  4. *Choir vowel*: a vowel or the hum of an existing choir part that the catalog lacks (the
     audit's `choir soprano eh`, `ee`, `hum`): the solo voices already sing all five vowels and
     hum, and the choir parts sing three.
  Anything else sung is DROP "a singing technique, style or genre, sung by any voice; not an
  instrument", as batch 6 dropped patches ("a patch, programmed on any synthesizer, not an
  instrument"). This covers a register or technique (`falsetto male`, `whistle register`, `vocal
  fry`, `belt voice`, `growl voice`, `whisper voice`, `sprechstimme`, `scat singing`, `lilting`,
  `ululation`, `kulning`, `silbo whistle`, the beatbox sounds, `tongue click`, `mouth bass`). It
  also covers a genre, repertoire or a role in a theatre tradition (`joik`, `urtiin duu`,
  `pansori voice`, `jingju xiaosheng`, `jingju dan`, `shomyo chant`, `dhrupad alap voice`,
  `qawwali voice`, `adhan voice`, `cantorial voice`, `hawaiian falsetto`) and an ensemble's
  tradition (`gregorian chant`, `gospel choir`, `bulgarian choir`, `kecak chorus` and the rest).
  **The one exception is the spec's own table.** The spec names "overtone and throat singing" and
  "yodel" as waiting for "moving formants, vowel glides, vibrato". The spec decided that, so
  those rows WAIT for the feature rather than drop: `khoomei`, `sygyt`, `kargyraa`,
  `borbangnadyr`, `ezengileer`, `chylandyk`, `dumchuktaar`, `byrlang`, `tibetan chant`,
  `umngqokolo`, `katajjaq`, `rekuhkara`, `yodel`, `tuvan ensemble`. Each WAIT quotes its
  fetched source for the feature. A row the audit marks "(memory)" or "named on page, no
  description" with no fetched page describing it is still DROP "no fetched source describes
  it" (rule 6).
- **Voice types are sound-alikes.** The Csound table, the catalog's only formant source, has
  five voice types. The audit's subtypes reuse one of those rows ("same formant-table row as
  an existing voice, so only range/weight differs"). Their sources' words ("light", "lyric",
  "dramatic", "dark", "heavy", "agile") describe weight and agility. No sourced number turns
  those words into a different static formant voice, and a number chosen to differ is the
  anti-goal (batch 7, rule 7). So a voice type is a SOUND_ALIKE of the `ah` entry of the voice
  type its source names it a kind of, with its own sourced range and no `sound_changes`.
  Examples: a soprano subtype is a sound-alike of `soprano ah`, a sopranist of `countertenor ah`
  if its source calls it a countertenor, an oktavist of `bass ah` or `basso profundo ah` as its
  source says. Only `ah` is added, the audit's vowel and the one every type's row has, and the
  name ends in it (`coloratura soprano ah`). A type its source relates to no existing type
  (`castrato`: "boy-bright … with adult chest") WAITs `its own build`.
- **Range ruling for voices and choirs.** A sourced range is the lowest and highest notes that a
  fetched source states as that voice type's or choir part's range:
  1. *Stated*: the source gives both notes as the range, in note names with octaves
     (scientific `C4`, Helmholtz `c'`, or a named note whose octave the source fixes, such as
     "middle C (C4)"), in prose, a table or a caption. If a source gives both a solo and a
     choral range, a voice type takes the solo one and a choir part the choral one.
  2. *Not a range*: a hedged span ("approximately", "about", "roughly", "typically … up to",
     "can extend to"), a type's extremes ("some roles to F6", "sometimes F1", "extreme C1"), a
     tessitura, or one aria's lowest note (the audit's castrato C3 from a Farinelli aria).
  3. *Conflict*: a page that contradicts itself gives no range (batch 7's `gaohu`). If two
     fetched sources disagree, the type's own page decides; if it gives no range, the row WAITs.
  4. *Sources*: the type's own encyclopedia page (Wikipedia, Britannica, Grove where reached),
     or a conservatory, opera-house or choral-society reference. A teacher's blog or a forum is
     not a source. A range is never taken from a sibling type, the parent voice or the audit.
  5. Nothing below A0, the catalog's floor (a below-A0 claim is WAIT `sub-audio fundamentals`).
  Every row's `notes` holds `Range:` and the quoted passages, then the derivation.
- **Choir vowels keep their part's range.** A part's entries share one `CHOIR_PARTS` row, and
  the existing entries change only for a cited bug. A choir vowel (`choir tenor ee`) is SHIP
  only when a fetched source gives that part's choral range under the ruling and it equals the
  part's `CHOIR_PARTS` row. Its build is `_sung` on the Csound row (`_formants(part, vowel)`) or
  on `HUM_FORMANTS`, with `choir=True`, exactly as the existing choir vowels are built. If the
  source gives another range, the row WAITs `a sourced range`, its notes quote both ranges, and
  the disagreement goes to #78's "Bugs to report". If no source gives the part's range, the row
  WAITs as well. `HUM_FORMANTS` is the catalog's existing sound design (no source comment), and
  the `builder` cell says so.
- **Ensembles of several parts are their parts.** One catalog instrument plays one part at a
  time. A men's (TTBB), women's (SSAA) or full (SATB) choir, a quartet, or `cantu a tenore`'s
  four voices is several parts, so it is DROP "an ensemble of parts, each its own entry:
  <names>", as batch 6 dropped drum machines for their voices. A choir that its source
  describes as one voice type in unison (`boys choir` as trebles, say) is a choir part. It is a
  SOUND_ALIKE of the existing part nearest to it (`childrens choir`, the trebles' build) with
  its own sourced range, or it WAITs.
- **Voice devices.** The kazoo and the swazzle are decided here under the kazoo boundary call:
  each colours the voice of the person using it. If its source names the buzz of a membrane or
  reed as its sound, it WAITs `a buzzing membrane`, as batch 5's `gyil` did. Its range is the
  user's voice, so it needs a source stating the device's own range or it WAITs `a sourced
  range`. A device whose sound is speech shaped by the mouth (`electrolarynx`) WAITs `moving
  formants`, batch 6's ruling for `talk box`, `sonovox` and `voder`.
- **Earlier and other families' rows.** `talk box`, `sonovox`, `vocoder` and `voder` are DROP
  "already decided: batch-6.tsv WAIT". `vocoder voice`, the audit's "static robot vowel", is
  DROP "already decided: batch-6.tsv WAIT vocoder; decision 4 bars a qualified name".
  `speech synth lpc` is DROP: linear predictive coding is a technique, and the named speech
  chips are batch 6's (`speak and spell`, `votrax`). `vox humana` and `voix celeste` are DROP
  "belongs to organs (organs.md rows it as a stop); the organs batch decides it".
- **No new approximating entries.** The existing voices imitate no missing feature, so
  `APPROXIMATING_NAMES` is unchanged. A static vowel that is "truest mid-range" is a stated
  limit, not an imitation. A new voice type may therefore have any existing voice entry as its
  parent.
- **Aliases of a voice type resolve to its `ah` entry.** The alias table maps one name to one
  entry, so a synonym of a voice type (`contralto`, `boy soprano`, `octavist`) is ALIAS of that
  type's `ah` entry when its source says it is the same voice. An alias line whose target WAITs
  is WAIT `its target, <name>`. One whose target is dropped is DROP "its target, <name>, is
  dropped" (`overtone singing` follows `khoomei`, `sprechgesang` follows `sprechstimme`).
- **One-offs are dropped** (batch 5's ruling): DROP "a one-off instrument, not a type a game
  would ask for".
- **Two halves by family.** Half A is the voices: the 72 voice candidates (68 merged rows,
  `vocoder`, `voder`, `kazoo` and `swazzle`) and all 28 alias-line names, whose targets are
  all voices. Half B is the choirs: the 38 choir candidates. No duplicate candidate crosses the
  halves.
- **The halves run in parallel.** A parent or alias target is a catalog name from before the
  batch, or a SHIP row of the same half. It is never a row of the other half. A choir row that
  needs a voice row (`orthodox choir` and `cossack choir` on the oktavist, `tuvan ensemble` on
  khoomei) only names it in a DROP or WAIT note, so Task 4 needs nothing from Task 2. Half B is
  written to a build file and appended to the sheet once half A is committed. The form check
  accepts a row that the code already holds with the same target or parent (batch 7's lesson).
- **Out of scope:** the audit's "Gaps you could not close" (Fach ranges no source gave;
  Kunqu, ca trù, Albanian iso-polyphony, Māori karanga and the other traditions it did not
  research; MIMO, the Met, Horniman and Grove unconsulted). Task 6 lists them in #70 for a later
  pass. Bare voice-type names (`soprano`, `tenor`) resolve to nothing today. That is a #78
  follow-up, not this batch's work.

---

### Before the tasks: the controller records the names before the batch

The controller runs this once, before dispatching anything, so that Tasks 1, 2 and 4 can start
together:
```bash
mkdir -p build
uv run python -I -c "
from glitchygames.audio import instruments
names = sorted(set(instruments.CATALOG) | set(instruments.ALIASES))
open('build/batch-8-names-before.txt', 'w', encoding='utf-8').write('\n'.join(names) + '\n')
print('names before', len(names))
"
```
Expected: `names before 762` (684 entries and 78 aliases).

---

### Task 1: The sound-alike tables, the batch table's rows, and no moving-formant name

**Files:**
- Create: `src/glitchygames/audio/instruments/voice_sound_alikes.py`
- Modify: `src/glitchygames/audio/instruments/voices.py`, `tests/test_process_state_guard.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces: `voices.py` with `VOICES: Final[tuple[CatalogEntry, ...]] = _VOICE_BUILDS +
  VOICE_SOUND_ALIKES` and `CHOIRS: Final[tuple[CatalogEntry, ...]] = _CHOIR_BUILDS +
  CHOIR_SOUND_ALIKES`, where `_VOICE_BUILDS` and `_CHOIR_BUILDS` are today's two tuples,
  unchanged. `voice_sound_alikes.py` holds `VOICE_SOUND_ALIKES` and `CHOIR_SOUND_ALIKES`
  (`Final[tuple[CatalogEntry, ...]]`, both empty). The test file gains
  `EXISTING_VOICE_NAMES` and `EXISTING_CHOIR_NAMES` (`frozenset[str]`, 55 and 13);
  `NEW_VOICE_NAMES` and `NEW_CHOIR_NAMES` (`list[str]`); `VOICE_SOUND_ALIKE_PARENTS` and
  `CHOIR_SOUND_ALIKE_PARENTS` (`dict[str, str]`), all empty here, for Tasks 3 and 5 to fill;
  `MOVING_FORMANT_NAMES: frozenset[str]`; and the `BATCH_FAMILIES` rows `Family.VOICES` and
  `Family.CHOIRS`. Also `build/voice-builds-before.txt`.

- [ ] **Step 1: Record both families' builds.** Run batch 4's Task 1 Step 1 command once per
  family (`family='voices'` into `build/voice-builds-before.txt`, then `family='choirs'`
  appended with mode `'a'`). Expected: `recorded 55`, then `recorded 13`.

- [ ] **Step 2: Write the tests.** Above `BatchFamily`, add:
```python
# The 68 voices and choirs that predate batch 8: their shared builds predate the anti-goal rule
EXISTING_VOICE_NAMES = frozenset(
    {
        f'{voice} {sound}'
        for voice in (
            'soprano', 'mezzo soprano', 'alto', 'treble', 'countertenor',
            'tenor', 'baritone', 'bass', 'basso profundo',
        )
        for sound in ('ah', 'eh', 'ee', 'oh', 'oo', 'hum')
    }
    | {'whistling'}
)
EXISTING_CHOIR_NAMES = frozenset(
    {
        f'choir {part} {sound}'
        for part in ('soprano', 'alto', 'tenor', 'bass')
        for sound in ('ah', 'oh', 'oo')
    }
    | {'childrens choir'}
)
```
  Also add `NEW_VOICE_NAMES: list[str] = []`, `VOICE_SOUND_ALIKE_PARENTS: dict[str, str] = {}`,
  `NEW_CHOIR_NAMES: list[str] = []` and `CHOIR_SOUND_ALIKE_PARENTS: dict[str, str] = {}`, each
  with a comment as batch 7's lists have. Put the two rows last in `BATCH_FAMILIES`, voices then
  choirs, which is catalog order. In `test_a_sound_alike_is_listed_and_builds_its_parents_sound`,
  the closing list gains `+ list(VOICE_SOUND_ALIKE_PARENTS) + list(CHOIR_SOUND_ALIKE_PARENTS)`
  after `SOUND_ALIKE_NAMES`. Its comment then ends "…, then drums, voices and choirs". After
  `test_no_sound_alike_shares_an_approximated_sound`, add:
```python
# The spec's "What the engine cannot make yet": "moving formants, vowel glides, vibrato |
# overtone and throat singing, talk box, vocoder, yodel". Nothing in that row ships under its
# name, a qualified name or an alias until the engine has the feature (decision 4; batch 8)
MOVING_FORMANT_NAMES = frozenset({
    'khoomei', 'sygyt', 'kargyraa', 'borbangnadyr', 'ezengileer', 'chylandyk', 'dumchuktaar',
    'byrlang', 'tibetan chant', 'umngqokolo', 'katajjaq', 'rekuhkara', 'yodel', 'tuvan ensemble',
    'talk box', 'sonovox', 'vocoder', 'vocoder voice', 'voder',
})


def test_nothing_waiting_for_moving_formants_is_listed():
    """No catalog name or alias is an instrument the spec holds back for moving formants."""
    assert MOVING_FORMANT_NAMES & set(instruments.names()) == set()
    assert MOVING_FORMANT_NAMES & set(instruments.ALIASES) == set()
```

- [ ] **Step 3: Run them.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or approximated or moving_formants" -v`
  Expected: PASS, with IDs `[voices]` and `[choirs]` after the four earlier families. These are
  guards: they pass now and hold the later tasks.

- [ ] **Step 4: Split the tables.** Read every comment in `voices.py` first. Rename the module's
  `VOICES` tuple to `_VOICE_BUILDS` and `CHOIRS` to `_CHOIR_BUILDS`, unchanged. Then define
  `VOICES` and `CHOIRS` as the concatenations. The module docstring gains one sentence saying
  that the sound-alikes are in `voice_sound_alikes.py`. `voice_sound_alikes.py` gets the two
  empty tables and a docstring quoting the owner, as `bowed_sound_alikes.py`'s does, ending
  "The families' builds are in ``voices.py``." Move the two R16 reasons in
  `tests/test_process_state_guard.py` to `_VOICE_BUILDS` and `_CHOIR_BUILDS`. If the guard then
  asks for an entry for `VOICES` or `CHOIRS`, that is a finding: read why before writing any
  reason. `registry.py` is unchanged.

- [ ] **Step 5: Check nothing changed.** Run batch 4's Task 1 Step 3 command against
  `build/voice-builds-before.txt`, with the name list `list(instruments.names(family='voices'))
  + list(instruments.names(family='choirs'))`. Then run
  `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py -q`.
  Expected: `changed: []`, then PASS.

- [ ] **Step 6: Lint and commit**
```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py tests/test_process_state_guard.py
SKIP=replay-metrics git commit -m "Instrument catalog: voices' and choirs' sound-alike tables; nothing waiting for moving formants is listed" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The voices sheet (half A)

Research: load the web tools with ToolSearch `select:WebSearch,WebFetch`, and fetch every URL
you cite. Never cite a page you did not fetch. A list page is a source for a name only. The
sound, the title and the range come from the instrument's own page, or from an encyclopedia,
conservatory, opera house, maker or museum. The audit's "VERIFIED" rows and its quotes are
leads, not sources, so fetch them. This task may start as soon as the controller has written
`build/batch-8-names-before.txt`, alongside Tasks 1 and 4.

**Files:**
- Create: `plans/data/instrument-audit/batch-8.tsv`
- Create (not committed): `build/batch-8-candidates.txt`, `build/batch-8-voices.txt`,
  `build/batch-8-choirs.txt`, `build/batch-8-form-check.py`

**Interfaces:**
- Consumes: the candidate sources in the Spec line; `voices-and-choirs.md` ("Rejected or
  corrected proposed entries", "Aliases", "Range checks"); `batch-1.tsv` to `batch-7.tsv`;
  `build/batch-8-names-before.txt`.
- Produces: `batch-8.tsv` with batch 7's header:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	hs	audit_name	range_source	sound_source	notes	tags`.
  `status` is one of `SHIP`, `SOUND_ALIKE`, `WAIT`, `ALIAS` or `DROP`. `alias_of` holds an
  ALIAS row's target or a SOUND_ALIKE row's parent. `family` is `voices` on every half-A row.
  Every SHIP or SOUND_ALIKE row is pitched: it has `lowest`, `highest`, `range_source`, and
  `notes` holding `Range:` and `Kind: <kind>`. `tags` is empty. `hs` is the Hornbostel–Sachs
  class that a fetched source gives (the kazoo's `242`), else `none`: the classification covers
  instruments, not the voice, and batch 7's unsourced classes were an owner's question. The
  task also produces the form check script, `build/batch-8-form-check.py SHEET`, which Task 4
  runs.

- [ ] **Step 1: Write the candidate lists**
```bash
mkdir -p build
cd plans/data/instrument-audit
{ awk -F'\t' 'NR>1 && $4 ~ /^voices/ {print tolower($2)}' merged.tsv
  awk -F'\t' 'NR>1 && tolower($5) ~ /voice|choir/ {print tolower($1)}' round-1/merged-missing.tsv
  printf '%s\n' kazoo swazzle
} | LC_ALL=C sort -u > ../../../build/batch-8-voices.txt
awk -F'\t' 'NR>1 && $4 ~ /^choirs/ {print tolower($2)}' merged.tsv | LC_ALL=C sort -u > ../../../build/batch-8-choirs.txt
cd ../../..
LC_ALL=C sort -u build/batch-8-voices.txt build/batch-8-choirs.txt > build/batch-8-candidates.txt
wc -l build/batch-8-*.txt
```
  Expected: 110 candidates, 72 voices, 38 choirs, and `LC_ALL=C comm -12
  build/batch-8-voices.txt build/batch-8-choirs.txt` prints nothing.

- [ ] **Step 2: Write one row per half-A candidate,** in `build/batch-8-voices.txt`'s order,
  then one per name in the audit's "Aliases" section (28 names; a line with several names gives
  one row each, and the audit's line is the row's `audit_name`).

  The rules are batch 7's, changed for these families:

  1. **SHIP** only with name, title, range and sound from fetched sources. Quote in `notes` the
     `Kind:`, the passage that describes the sound, and, after `Range:`, the passages that give
     the range, then the derivation under the range ruling. The `builder` cell gives the
     `_sung` call (`FORMANT_TABLE` row and vowel, or `HUM_FORMANTS`; `choir=False` for a voice).
     It says which values come from the source and which are sound design.
  2. **SOUND_ALIKE**: a verified instrument that rule 7 finds would sound like an existing
     entry or a SHIP row of this half. `alias_of` is its parent. The `notes` begin
     "Sound-alike:", give the `Kind:`, quote the source's description and say why that entry is
     the nearest (for a voice type: which type the source names it a kind of). It has its own
     range under the ruling. The parent is a catalog name or a SHIP row of this half. It is
     never another sound-alike and never one of `APPROXIMATING_NAMES`.
  3. **ALIAS**: another name for the same instrument, cited. The target is a catalog name, a
     SHIP row or a SOUND_ALIKE row. If the target waits, the row is WAIT with `waits_for` `its
     target, <name>`. If the target is dropped, the row is DROP "its target, <name>, is dropped".
  4. **WAIT** when the identifying sound needs a feature the engine lacks, named in `waits_for`
     with the source quoted. The names are those in Global Constraints (`moving formants`, `a
     pitch LFO (vibrato)`, `a buzzing membrane` and the rest) or `a sourced range`, `its own
     build` or `sub-audio fundamentals`. The feature must be the sound the source describes. The
     rows of `MOVING_FORMANT_NAMES` WAIT `moving formants` (the spec's table) unless rule 5 or 6
     drops them. A name beyond these is allowed only with the source quoted, and Task 6 lists it
     in #78.
  5. **DROP** a row that is not an instrument (the "what a candidate is" ruling: "a singing
     technique, style or genre, sung by any voice; not an instrument"), an ensemble of parts
     (name them), a row that belongs to another family (name it), or a one-off. Also DROP a row
     that is already decided: name the entry if it is in the catalog under that name, the target
     if it is already an alias, or the sheet and status if an earlier sheet decided it (`talk
     box`, "already decided: batch-6.tsv WAIT"). The plan's decisions name `vocoder voice`,
     `speech synth lpc`, `vox humana` and `voix celeste`.
  6. A row the audit marks "(memory)" or "not fetched" has no sourced sound yet. Fetch the
     instrument's own page; the audit's URL is a lead. If no page can be found, the row is DROP
     "no fetched source describes it".
  7. **The anti-goal:** before a row is SHIP, compare its `builder` cell with every entry in
     both families (`uv run python -I -c "from glitchygames.audio import instruments as i;
     print(i.names(family='voices'), i.names(family='choirs'))"` and `voices.py`) and every SHIP
     row above it. If no sourced trait (a formant row of its own, a device's construction) makes
     it sound different, it is a SOUND_ALIKE under rule 2. A number chosen only to differ does
     not count, and a range is not a sound trait.
  8. **Names.** A voice type's row is named `<type> ah` in English word order (the audit's
     `tenore leggero ah`, titled "Leggero tenor (ah)", may be `leggero tenor ah`), and keeps the
     audit's name in `audit_name`. Its title is "<Type> (ah)".

- [ ] **Step 3: Write and run the form check.** Write `build/batch-8-form-check.py`. It is batch
  7's `build/batch-7-form-check.py` (batch 7's plan, Task 2 Step 3) with these changes:
  - It reads `build/batch-8-names-before.txt`.
  - It adds `KINDS = ('voice type', 'voice device', 'choir part', 'choir vowel')` and the
    `MOVING_FORMANT_NAMES` set from Task 1.
  - `held_as_this_row` compares `held.family == row['family']` in place of `'bowed strings'`.
  - Its `bad` conditions change in four places. `row['family'] not in {'voices', 'choirs'}`
    replaces the family check. `not (row['hs'] == 'none' or row['hs'][:1].isdigit())` replaces
    the `hs` check. `row['tags'] != ''` replaces both tag checks. Two conditions are added:
    `(row['status'] in {'SHIP', 'SOUND_ALIKE'} and not any(f'Kind: {kind}' in row['notes'] for
    kind in KINDS))` and `(row['status'] in {'SHIP', 'SOUND_ALIKE'} and
    row['audit_name'].lower() in MOVING_FORMANT_NAMES)`.
  - A SOUND_ALIKE row's parent must be in the same family as the row
    (`instruments.entry(parent).family == row['family']` when the parent is a catalog name).
  The rest (statuses, `ranged`, `taken`, the parent and alias-target sets, duplicate names,
  the counts line, the exit code) is batch 7's.
  Run: `uv run python -I build/batch-8-form-check.py plans/data/instrument-audit/batch-8.tsv`
  Expected: the counts, then `bad: []`, exit 0. Read the sheet with the csv module, never by
  splitting on tabs (batch 7 found CSV-quoted cells).

- [ ] **Step 4: Check the half.** Run batch 7's Task 2 Step 4 command with
  `batch-8.tsv`, `build/batch-8-voices.txt` in place of the Europe list and
  `build/batch-8-choirs.txt` in place of the Asia and Africa list.
  Expected: `missing: []` and `from half B: []`.

- [ ] **Step 5: Commit**
```bash
git add plans/data/instrument-audit/batch-8.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 8's verification sheet, the voices" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The voices

**Files:**
- Modify: `voices.py` (new voice builds after `whistling`, if any), `voice_sound_alikes.py`
  (`VOICE_SOUND_ALIKES`), and `aliases.py` (each ALIAS row, with its source URL in a comment)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-8.tsv` as Task 2 left it (half A only), and Task 1's lists.
- Produces: `NEW_VOICE_NAMES` and `VOICE_SOUND_ALIKE_PARENTS`, filled with this half's rows.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_VOICE_NAMES` with one name per SHIP row,
  in the sheet's order, and `VOICE_SOUND_ALIKE_PARENTS` with one `name: parent` per SOUND_ALIKE
  row. Add the ALIAS rows to `test_the_batch_aliases_resolve`'s parameters.

- [ ] **Step 2: Run them and check they fail.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "new_build or new_entries or sound_alike or batch_aliases" -v`
  Expected: the new names and aliases fail with `KeyError: no instrument named ...`.

- [ ] **Step 3: Write the entries.** Write one entry per SOUND_ALIKE row in
  `VOICE_SOUND_ALIKES`, in the sheet's order, as a `CatalogEntry(name, title, Family.VOICES,
  lowest, highest, sounds_like=parent)`. Above each, put a comment with its `sound_source` and
  `range_source` URLs, the quoted passages and the range's derivation, as
  `bowed_sound_alikes.py`'s entries have. A SHIP row is a `CatalogEntry` after `whistling` in
  `_VOICE_BUILDS`, built with `partial(_sung, ..., choir=False)` and carrying the same comment.
  A builder new to the family (a device's buzz, should one ever SHIP) gets its own test of the
  trait it exists for, as batch 2's `test_the_pianet_settles_from_a_bright_strike` does.

- [ ] **Step 4: Run the suite and check the code against the sheet.**
  Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
  Expected: PASS, including `test_every_instrument_renders_across_its_range` and
  `test_harmonic_instruments_sound_their_note` for every new entry. A failure at a range end is
  a finding about the range or the build. Check it against the source, and never trim the range
  to pass. Then run batch 7's Task 3 Step 4 code check with `batch-8.tsv`, comparing
  `e.family` with `r['family']` in place of `'bowed strings'`.
  Expected: `matches N rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 8's voices, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 4: The choirs sheet (half B)

Research as in Task 2. This task may start as soon as the controller has written
`build/batch-8-names-before.txt`, alongside Tasks 1 and 2, because it needs nothing from half A.

**Files:**
- Create (not committed): `build/batch-8-choirs.tsv`, half B's rows under the sheet's header
- Modify: `plans/data/instrument-audit/batch-8.tsv` (append half B's rows)

**Interfaces:**
- Consumes: Task 2's rules 1–8, header and `build/batch-8-form-check.py`, and
  `build/batch-8-choirs.txt`. If either file is missing, rerun Task 2 Step 1 or write the form
  check from Task 2 Step 3.
- Produces: the sheet's remaining rows, which Task 5 reads.

Every half-B candidate gets a row, in `build/batch-8-choirs.txt`'s order, with `family`
`choirs`. A parent or alias target is a catalog name or a SHIP or SOUND_ALIKE row of this half,
never a half-A row. These rules apply to this half on top of Task 2's:

- **Choir vowels** (`choir soprano eh` to `choir bass hum`, 12 rows): apply the choir-vowel
  ruling. The `Kind:` is `choir vowel`. The title follows the existing entries ("Choir basses
  (eh)", not the audit's "Choir basss"), and a hum's title is "Choir sopranos (humming)", as
  the solo hums' titles are. One fetched choral source may range all four parts. Quote it once
  per row.
- **Ensembles and traditions:** `mens choir`, `womens choir`, `full choir ah`, `barbershop
  quartet`, `doo wop group`, `cantu a tenore` and `corsican paghjella` are ensembles of parts,
  unless a source describes one voice type in unison. The repertoires and traditions (`gregorian
  chant`, `byzantine chant ison`, `orthodox choir`, `gospel choir`, `bulgarian choir`, `georgian
  choir`, `pygmy polyphony`, `sacred harp choir`, `isicathamiya choir`, `kecak chorus`, `gamelan
  gerongan`, `tahitian himene`, `bunun pasibutbut`, `vedic chant`, `cossack choir`, `qawwali
  party`) are styles. Name in the note any voice row the tradition depends on (the oktavist,
  khoomei). `tuvan ensemble` WAITs `moving formants`, as one of `MOVING_FORMANT_NAMES`, unless
  rule 6 drops it.
- **Choirs of one part:** `boys choir` and `girls choir` are decided under "Ensembles of
  several parts are their parts". A choir of one part is a SOUND_ALIKE of `childrens choir`
  with its own sourced range, or it WAITs.

- [ ] **Step 1: Write half B's rows** to `build/batch-8-choirs.tsv`, and check them alone.
  Run: `uv run python -I build/batch-8-form-check.py build/batch-8-choirs.tsv`
  Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 2: Append them to the sheet.** Once Task 2 is committed (wait for it otherwise),
  append the build file's rows without its header:
  `tail -n +2 build/batch-8-choirs.tsv >> plans/data/instrument-audit/batch-8.tsv`.
  Run Task 2 Step 3's form check on the whole sheet.
  Expected: the counts, then `bad: []`, exit 0. If Task 3 has run, half A's coded rows are
  accepted as held.

- [ ] **Step 3: Check that no candidate was left out silently.** Run Task 2 Step 4's command
  with `voices | choirs` on the `missing:` line in place of the voices list, and print
  `'extra:', sorted(audit_names - voices - choirs)` in place of the half-B line.
  Expected: `missing: []`. `extra:` lists only the alias-section lines, because an alias row's
  `audit_name` is its audit line.

- [ ] **Step 4: Commit**
```bash
git add plans/data/instrument-audit/batch-8.tsv
SKIP=replay-metrics git commit -m "Instrument audit: batch 8's verification sheet, the choirs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The choirs

**Files:**
- Modify: `voices.py` (`ADDED_CHOIR_SOUNDS` and `_added_choir_entries`) and
  `voice_sound_alikes.py` (`CHOIR_SOUND_ALIKES`)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-8.tsv`'s half-B rows and Task 3's lists.
- Produces: both families finished.

- [ ] **Step 1: Write the failing tests.** Fill `NEW_CHOIR_NAMES` and
  `CHOIR_SOUND_ALIKE_PARENTS` as in Task 3 Step 1. Then add:
```python
def test_a_choir_parts_entries_share_its_range():
    """Every vowel and hum of a choir part, old or new, keeps the part's one range."""
    for part in ('soprano', 'alto', 'tenor', 'bass'):
        ranges = {
            (catalog_entry.lowest, catalog_entry.highest)
            for catalog_entry in instruments.entries(family=Family.CHOIRS)
            if catalog_entry.name.startswith(f'choir {part} ')
        }
        assert len(ranges) == 1, part
```
  If the sheet ships all twelve choir vowels, also add a test parametrized over the four parts,
  `test_every_choir_part_sings_every_vowel_and_hums`, the choir version of
  `test_every_voice_range_sings_every_vowel_and_hums`, asserting `choir {part} {sound}` is in
  `Family.CHOIRS` for `ah`, `eh`, `ee`, `oh`, `oo` and `hum`. Otherwise do not add it.

- [ ] **Step 2: Run them and check they fail.** Run Task 3 Step 2's command.
  Expected: the new cases fail with `KeyError: no instrument named ...`.
  `test_a_choir_parts_entries_share_its_range` passes, because it is a guard.

- [ ] **Step 3: Write the entries.** In `voices.py`, add `ADDED_CHOIR_SOUNDS: Final[tuple[tuple[str,
  str], ...]]`. It holds one `(part, sound)` pair per choir-vowel SHIP row, in the sheet's order
  (`('soprano', 'eh')`, …, `('bass', 'hum')`), with a comment above it citing each part's range
  source and quote. Add `_added_choir_entries() -> tuple[CatalogEntry, ...]`, which builds each
  pair from the part's `CHOIR_PARTS` row. A vowel sound uses `_formants(part, vowel)`, where
  `vowel` is the `VOWELS` key whose value is the sound. `hum` uses `HUM_FORMANTS`. Both take
  `choir=True` and the part's `_middle_hz`, with names `choir {part} {sound}` and the sheet's
  titles. Then `_CHOIR_BUILDS = (*_choir_entries(), *_added_choir_entries())`, so the existing
  13 keep their order. A choir SOUND_ALIKE row goes in `CHOIR_SOUND_ALIKES` with its source
  comment and its own range.

- [ ] **Step 4: Run the suite and check the code against the sheet.** Run Task 3 Step 4's
  commands; the code check now covers every row. Expected: PASS, then `matches N rows`.

- [ ] **Step 5: Lint and commit.** Run Task 1 Step 6's lint commands, then
  `git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py` and
  `SKIP=replay-metrics git commit -m "Instrument catalog: batch 8's choirs, each from its source" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

### Task 6: Docs, counts, the owner's checks and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py`. In the docstring, add a voices and
  choirs paragraph with both counts, naming `voices.py` and `voice_sound_alikes.py`, with
  examples.
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the total, the `voices` and
  `choirs` rows' counts and examples, the sound-alike modules sentence and its total).
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": the counts).
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md`: the status line (batch 8
  done, pointing at this plan and `batch-8.tsv`) and the "Depends on" counts.
- Modify: `plans/future-features.md`. In #70:
  - the heading becomes "BATCH 8 DONE";
  - batch 8 done, with the sheet's counts by status and both families' growth;
  - the audit's unclosed gaps, as a later pass;
  - `vox humana` and `voix celeste` left for the organs batch to decide;
  - `kazoo` and `swazzle` decided here;
  - a "Plan (batch 8)" line, the Status line, and the next batch named: flutes.

  Add #78 (the highest item is #77), "Sound Engine: The Owner's Checks on Instrument Catalog
  Batch 8 — TODO". Use #77's form, place it after #77, and give it the Priority "(before the
  flutes batch builds on the same catalog)". Its **Listen** section (`build/instruments/voices/`
  and `build/instruments/choirs/`) covers the new builds, then the sound-alikes under their
  parents. Its **Calls to confirm** are:
  - every WAIT, by reason;
  - the "what a candidate is" ruling: the four kinds, techniques, styles and genres dropped,
    and the exception for the spec's moving-formants row;
  - voice types as `ah` sound-alikes of the type their source names, with no `sound_changes`
    and no other vowels;
  - the range ruling (stated, never hedged or extreme, a self-contradicting page gives none,
    nothing below A0), and every derived range;
  - the choir-vowel ruling (a vowel ships only on a sourced range equal to its part's);
  - ensembles of parts dropped for their parts, and choirs of one part as sound-alikes of
    `childrens choir`;
  - the voice devices (`kazoo`, `swazzle`, `electrolarynx`) and the buzzing-membrane wait;
  - aliases of a voice type resolving to its `ah` entry;
  - the earlier sheets' rows left as decided (`talk box`, `sonovox`, `vocoder`, `voder`),
    `vocoder voice` and `speech synth lpc` dropped, and `vox humana` and `voix celeste` left
    for organs;
  - `hs` as `none` where no fetched source gives a class;
  - one module with two sound-alike tables (no `choirs.py`);
  - the split by family, with the two sheets researched in parallel;
  - any engine feature named beyond the spec's table, for its "What the engine cannot make
    yet".

  Then **Bugs to report** (found while building, none fixed here). These are what the sheets
  confirm among the audit's leads: the countertenor's E3–E5 against the Voice type page's
  conflict, `whistling` C5–C7 unsourced, `CHOIR_PARTS`' "usual choral ranges" unsourced,
  `HUM_FORMANTS` with no source or sound-design note, `treble` on the adult soprano row, and
  any choir-vowel range disagreement. Then **Follow-ups**: the audit's gaps; ranging the range
  WAITs; bare voice-type names (`soprano`) resolving to nothing; the other vowels for the voice
  types that shipped as `ah`.
- Fix any doc line the counts make stale, and write no count from memory.

- [ ] **Step 1: Get the counts from the code**
  Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES)); print(sum(e.sounds_like is not None for e in i.entries()))"`
  and `uv run python -I build/batch-8-form-check.py plans/data/instrument-audit/batch-8.tsv`
  for the sheet's counts. Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the files.**

- [ ] **Step 3: Run the full checks**
```bash
uv run pytest --dummy-only tests/audio tests/test_process_state_guard.py
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
```
  Expected: everything passes with no warnings (a warning is a finding). The
  `build/instruments/voices` and `build/instruments/choirs` folders are the ones to listen to;
  the owner judges the sound.

- [ ] **Step 4: Commit**
```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
SKIP=replay-metrics git commit -m "Docs: batch 8 of the instrument catalog (voices and choirs), its counts and the owner's checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Pushing and the stacked PR follow the owner's instruction for this series ("Work on every batch
in turn and stack them into PRs"), never anything else. The pre-push hooks take about 40
minutes, and nothing in the working tree may change while they run.

**Order:** the controller's names file, then Tasks 1, 2 and 4 in parallel. Task 3 follows Tasks 1
and 2. Task 4's append waits for Task 2's commit. Task 5 follows Tasks 3 and 4, and Task 6
comes last.
