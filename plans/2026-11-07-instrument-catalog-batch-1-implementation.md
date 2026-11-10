# Instrument catalog batch 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the catalog's tags and aliases, and the first three new families (plucked
idiophones, friction instruments, noise makers), each entry verified against a cited source.

**Architecture:** `Tag` is a closed `StrEnum` beside `Family`, and `CatalogEntry` gets a
`tags` field. An alias table (`aliases.py`) maps other names to catalog names, and `entry` and
`get` resolve them. A verification sheet decides which audit rows ship, wait, become aliases or
are dropped, before any entry is written. The new families live in two new modules,
`idiophones.py` (plucked and friction) and `noise_makers.py`, built only from the existing
shapes in `timbres.py`.

**Tech Stack:** Python 3.14, numpy, pytest, the engine's audio package
(`glitchygames.audio.instrument`, `audio/instruments/timbres.py`).

**Spec:** `plans/2026-11-07-instrument-catalog-expansion-design.md`. The working list is
`plans/data/instrument-audit/merged.tsv` with `new-plucked-idiophones.md`,
`new-friction-instruments.md` and `new-noise-makers.md`.

## Global Constraints

- Catalog names match `^[a-z][a-z0-9]*( [a-z0-9]+)*$` (`ENTRY_NAME_PATTERN`). Accents and
  punctuation go only in the title.
- A family is defined by how the sound is made. Boundary calls (the owner, 2026-11-07): the
  cuíca and lion's roar stay in drums and percussion; duck calls and signal whistles go in
  flutes; the kazoo goes in voices; the hydraulophone goes in flutes.
- Mechanical instruments are a tag (`Tag.MECHANICAL`), not a family. Each stays in the family
  it sounds like.
- "Every name, range and description checked against a source cited in the code … A range that
  no source gives is the instrument's documented playable span from a maker or museum, or the
  entry waits." (spec, Batches 1)
- "Instruments the engine cannot make well yet wait for the feature": none ships as an
  approximation, under its real name or a qualified one (spec, decision 4). The features the
  engine lacks: sympathetic strings or a buzzing bridge, moving formants, vowel glides,
  vibrato, pitch and filter LFOs, FM synthesis, sample playback, more than four sources, and
  sub-audio fundamentals. It does have a pitch glide (`PitchCurve`, `Tone.glide_to`).
- Reuse the timbre shapes in `timbres.py`. Add a builder only for a genuinely new sound, and
  give it its own test (spec, Batches 3–4).
- Each entry cites its source in a code comment with the URL (spec, "Sources recorded per
  instrument"; CLAUDE.md: attribute content you use).
- Anti-goal: hundreds of entries that all sound like the same three timbres. Two shipped
  entries that would build the same instrument become one entry plus an alias.
- Every catalog entry, sound effects included, is playable as a note. An unpitched entry
  ignores the pitch it is given (spec, "Sound effects").
- Code style: Google docstrings, ruff (100 columns), basedpyright and ty clean, 100% coverage,
  no abbreviated variable names.

## Review Focus

1. **An alias spelled in another case** (`instruments.get('Slapstick')`) should resolve like a
   catalog name does. Task 2's test pins it.
2. **An alias that shadows or targets nothing** (an alias equal to a catalog name, or pointing
   at a missing or moved name) should be refused when the catalog is assembled, not when a
   game calls `get`. Task 2's test pins it.
3. **A string tag** (`tags=frozenset({'mechanical'})`) should be refused: a `StrEnum` compares
   equal to its string, so a plain set check would let a synonym-prone string in. Task 1's
   test pins it.
4. **A moved entry keeps its name**: `instruments.get('kalimba')` must still work after the move
   to plucked idiophones. Only its family changes. Tasks 4 and 5 assert it.
5. **An unpitched noise maker given any pitch** should sound the same at every pitch, as the
   drums do. Task 6 adds a test over every unpitched entry in the catalog.

---

## File Structure

- Modify `src/glitchygames/audio/instruments/catalog.py`: `Tag`, the `CatalogEntry.tags`
  field and its check, and the three new `Family` members (each added by the task that adds
  that family's entries, because `test_the_catalog_holds_every_family_with_unique_valid_names`
  requires every family to have entries).
- Create `src/glitchygames/audio/instruments/aliases.py`: `ALIASES`, the alias table, each
  alias with its source.
- Modify `src/glitchygames/audio/instruments/registry.py`: `aliases_from`, alias resolution in
  `entry` and `get`, `tag=` on `names` and `entries`, and the new family tables in
  `FAMILY_TABLES`.
- Modify `src/glitchygames/audio/instruments/__init__.py`: export `Tag` and `ALIASES`, and
  update the docstring.
- Modify `src/glitchygames/audio/instruments/percussion.py`: rename `_bar` to `struck_bar` (it
  becomes shared), and remove the moved entries.
- Create `src/glitchygames/audio/instruments/idiophones.py`: `PLUCKED_IDIOPHONES` and
  `FRICTION_INSTRUMENTS`.
- Create `src/glitchygames/audio/instruments/noise_makers.py`: `NOISE_MAKERS`.
- Create `plans/data/instrument-audit/batch-1.tsv`: the verification sheet.
- Modify `tests/audio/test_instrument_catalog.py`: the tests below.
- Docs: `docs/architecture/sound.md`, `CLAUDE.md`, `plans/future-features.md` (#70) and the
  design's status line.

Decisions made in this plan (my calls, for the owner to check):

- The order of `Family` (which is the catalog order): `PLUCKED_IDIOPHONES` and
  `FRICTION_INSTRUMENTS` go right after `TUNED_PERCUSSION`, and `NOISE_MAKERS` right after
  `DRUMS_AND_PERCUSSION`.
- `singing bowl` (struck) stays in tuned percussion, and `rubbed singing bowl` is a new
  friction entry: the spec moves the bowl only "when rubbed".
- `whip` keeps its name and its title "Whip (slapstick)". `slapstick` becomes an alias of it,
  and `whip crack` is a new noise maker (spec, corrections to the current catalog).
- `music box` moves to plucked idiophones and gets `Tag.MECHANICAL`. `calliope` stays untagged
  because it is played from a keyboard.

---

### Task 1: Tags

**Files:**
- Modify: `src/glitchygames/audio/instruments/catalog.py`
- Modify: `src/glitchygames/audio/instruments/registry.py` (`names`, `entries`)
- Modify: `src/glitchygames/audio/instruments/__init__.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Produces:
  - `class Tag(StrEnum)` in `catalog.py` with one member, `MECHANICAL = 'mechanical'`.
  - `CatalogEntry.tags: frozenset[Tag] = field(default=frozenset())`, the last field, given by
    keyword.
  - `names(*, family: Family | str | None = None, tag: Tag | str | None = None) -> tuple[str, ...]`
    and `entries(...)` with the same two keywords. A string is lowercased and converted;
    an unknown tag raises Tag's `ValueError`.
  - `instruments.Tag`, exported.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_tag_lists_exactly_its_tagged_entries():
    """names(tag=...) is every entry carrying that tag, in catalog order, alone or with family."""
    tagged = instruments.names(tag=Tag.MECHANICAL)
    assert tagged == tuple(
        entry.name for entry in instruments.entries() if Tag.MECHANICAL in entry.tags
    )
    assert instruments.names(tag='Mechanical') == tagged
    assert instruments.names(family=Family.BRASS, tag=Tag.MECHANICAL) == ()
    assert instruments.entries(tag=Tag.MECHANICAL) == tuple(
        instruments.entry(name) for name in tagged
    )
    with pytest.raises(ValueError, match='self playing'):
        instruments.names(tag='self playing')


def test_every_entry_tag_is_a_tag_member():
    """Tags are members of the closed Tag enum, never bare strings."""
    for entry in instruments.entries():
        assert all(type(tag) is Tag for tag in entry.tags), entry.name


def test_an_entry_refuses_a_string_tag():
    """A string equal to a tag's value is still refused: tags cannot drift into synonyms."""
    flute = instruments.entry('flute')
    with pytest.raises(TypeError, match="tag 'mechanical' must be a Tag"):
        CatalogEntry(
            'test flute', 'Test flute', Family.FLUTES, 'C4', 'C7', flute.build,
            tags=frozenset({'mechanical'}),  # pyright: ignore[reportArgumentType] - the refusal
        )
    assert CatalogEntry('test flute', 'Test flute', Family.FLUTES, 'C4', 'C7', flute.build).tags == frozenset()
```

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "tag" -v`
Expected: FAIL with `ImportError: cannot import name 'Tag'`.

- [ ] **Step 3: Implement `Tag`, the `tags` field and its check in `CatalogEntry.__post_init__`, and `tag=` on `names` and `entries`**

The check raises `TypeError(f'{self.name}: tag {tag!r} must be a Tag')` for any tag whose
`type` is not `Tag`. Put a `_tag(tag: Tag | str | None) -> Tag | None` helper beside
`_family`. Add `Tag` to the module docstrings and to `__all__`. No entry carries a tag yet:
`music box` gets one in Task 4. Until then, `names(tag=Tag.MECHANICAL) == ()` satisfies the
first test.

- [ ] **Step 4: Run them and check they pass**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
Expected: PASS (every catalog test).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run ruff check src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
uv run basedpyright src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: tags, a closed Tag enum on each entry, and names(tag=...)"
```

---

### Task 2: Aliases

**Files:**
- Create: `src/glitchygames/audio/instruments/aliases.py`
- Modify: `src/glitchygames/audio/instruments/registry.py`
- Modify: `src/glitchygames/audio/instruments/__init__.py`
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `CATALOG`, `entry`, `get` (registry).
- Produces:
  - `ALIASES: Final[Mapping[str, str]]` in `aliases.py`, mapping an alias to a catalog name.
    Its first entry is `'slapstick': 'whip'`, with a comment citing
    https://en.wikipedia.org/wiki/Slapstick_(instrument), whose page names the instrument
    "whip" or "slapstick".
  - `aliases_from(table: Mapping[str, str], catalog: Mapping[str, CatalogEntry]) -> dict[str, str]`
    in `registry.py`. It raises `ValueError` when an alias does not match `ENTRY_NAME_PATTERN`,
    when it equals a catalog name, or when its target is not a catalog name.
  - The registry's module constant `ALIAS_TABLE = aliases_from(ALIASES, CATALOG)`.
  - `entry(name)` returns `CATALOG[ALIAS_TABLE.get(lowered, lowered)]`. `get(alias)` is the
    same object as `get(target)`. An unknown name still gets close-name suggestions, drawn
    from catalog names and aliases together.
  - `names()` and `entries()` never list aliases.
  - `instruments.ALIASES`, exported (it is `ALIAS_TABLE`).

- [ ] **Step 1: Write the failing tests**

```python
def test_an_alias_finds_its_instrument_in_any_case():
    """An alias resolves to its catalog entry, and get shares the one build."""
    assert instruments.ALIASES['slapstick'] == 'whip'
    assert instruments.entry('Slapstick') is instruments.entry('whip')
    assert instruments.get('SLAPSTICK') is instruments.get('whip')
    assert 'slapstick' not in instruments.names()


def test_every_alias_names_one_entry_and_shadows_none():
    """No alias is a catalog name; every alias names an entry; aliases follow the naming rule."""
    for alias, target in instruments.ALIASES.items():
        assert alias not in instruments.CATALOG, alias
        assert target in instruments.CATALOG, (alias, target)


def test_the_alias_table_is_refused_when_it_is_wrong():
    """A bad alias table fails when the catalog is assembled, naming the alias."""
    with pytest.raises(ValueError, match="alias 'flute' is a catalog name"):
        aliases_from({'flute': 'piccolo'}, instruments.CATALOG)
    with pytest.raises(ValueError, match="alias 'fife of doom' names no instrument: 'fyfe'"):
        aliases_from({'fife of doom': 'fyfe'}, instruments.CATALOG)
    with pytest.raises(ValueError, match="alias 'Bad Alias' must be lower-case words"):
        aliases_from({'Bad Alias': 'flute'}, instruments.CATALOG)


def test_an_unknown_name_suggests_aliases_too():
    """A near miss of an alias suggests it."""
    with pytest.raises(KeyError, match='did you mean slapstick'):
        instruments.entry('slapstik')
```

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "alias" -v`
Expected: FAIL with `AttributeError: module 'glitchygames.audio.instruments' has no attribute 'ALIASES'`.

- [ ] **Step 3: Implement `aliases.py`, `aliases_from`, `ALIAS_TABLE` and alias resolution in `entry` and `get`**

`get` already calls `entry(name)` first. Make `_built` take the resolved catalog name
(`entry(name).name`), so an alias and its target share one cache slot.

- [ ] **Step 4: Run them and check they pass**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

Run the same format, check and basedpyright commands as in Task 1, then:

```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: aliases resolve to their entry (slapstick is the whip)"
```

---

### Task 3: The verification sheet

The audits' rows are candidates, not entries. This task decides each one against a source
before any code is written. It is research: load the web tools with ToolSearch
`select:WebSearch,WebFetch`, and fetch every URL you cite. Never cite a page you did not fetch.

**Files:**
- Create: `plans/data/instrument-audit/batch-1.tsv`

**Interfaces:**
- Consumes: `plans/data/instrument-audit/merged.tsv` (the rows whose `family` starts with
  `plucked idiophones`, `friction instruments` or `noise makers`), the three `new-*.md` audits,
  and the moves they list (`kalimba`, `mbira`, `music box`, `glass harmonica`, and a rubbed
  mode of `singing bowl`).
- Produces: `batch-1.tsv`, read by Tasks 4–6. It has one header line and these tab-separated
  columns:
  `name	title	family	status	alias_of	lowest	highest	waits_for	builder	range_source	sound_source	notes`
  - `status` is one of `SHIP`, `MOVE`, `WAIT`, `ALIAS` or `DROP`.
  - `family` is `plucked idiophones`, `friction instruments` or `noise makers`. A row that
    belongs elsewhere is `DROP`, with the right family in `notes`.
  - `lowest` and `highest` are note names (`C4`), or empty for an unpitched entry.
  - `builder` names the `timbres.py` shape (`struck_bar` with ratios, `blown`, `drum`,
    `plucked`) and its key parameters, in a few words.
  - `range_source` and `sound_source` are fetched URLs. `range_source` is empty for an
    unpitched entry.

Rules, applied to every row (none is left out silently):

1. **SHIP** an entry only if its name, title and sound description come from a fetched source,
   and, when it is pitched, its lowest and highest notes do too: a maker's specification, a
   museum record, or a reference page that states the compass. Quote the passage in `notes`.
   An entry is unpitched when its sources describe no playable pitch (a whip crack, a ratchet).
   An unpitched entry's fixed frequencies are sound design. Say so in `notes`, unless a source
   gives them (the vehicle horn's pair, about 410 and 500 Hz). Then cite it.
2. **WAIT** if the instrument's identifying sound needs a feature the engine lacks (Global
   Constraints). Name the feature in `waits_for`. Examples from the audits: jaw harps need a
   moving formant (the mouth cavity sweeps the overtones); the musical saw needs vibrato; the
   daxophone needs moving formants; the bullroarer needs a sub-audio fundamental and a slow
   amplitude swing; the whirly tube jumps between harmonics with speed. Decide each one from
   its source, not from this list.
3. **WAIT** a pitched instrument whose range no fetched source gives (`waits_for`:
   `a sourced range`).
4. **ALIAS** another name for the same instrument (same construction and sound). Put its
   canonical name in `alias_of`, which must be a catalog name or a SHIP or MOVE row of this
   sheet. Cite the source that says they are the same.
5. **DROP** a row that does not exist as described, belongs to another family, or would build
   the same instrument as another SHIP row while no game would ask for it by name. Give the
   reason and the source in `notes`.
6. **MOVE** the catalog's `kalimba`, `mbira`, `music box` and `glass harmonica` to their new
   family. Keep the name, title, range and build unless a fetched source shows the current
   range is wrong; then give the corrected range and the source.
7. Two SHIP rows whose `builder` cells would be the same instrument violate the anti-goal.
   Differentiate them from their sources (tine ratios, ring time, buzz, register), or make one
   an alias.
8. Mark SHIP rows that play themselves (cylinder and disc music boxes) `mechanical` in `notes`.
   Task 4 tags them.

- [ ] **Step 1: Build the sheet, one row per candidate.** Start with every candidate row of
  the audits for the three families, plus the moves and `rubbed singing bowl`, `whip crack`,
  and `slapstick` (ALIAS of the catalog's `whip`, decided in Task 2).

- [ ] **Step 2: Check that no candidate was dropped silently**

Run:
```bash
cd plans/data/instrument-audit
comm -23 \
  <(awk -F'\t' 'NR>1 && $4 ~ /^(plucked idiophones|friction instruments|noise makers)/ {print tolower($2)}' merged.tsv | sort -u) \
  <(awk -F'\t' 'NR>1 {print $1}' batch-1.tsv | sort -u)
```
Expected: no output. A name the sheet spells differently, without punctuation, is listed with
its audit spelling in `notes`. Fix the sheet until the command prints nothing.

- [ ] **Step 3: Check the sheet's form**

Run:
```bash
uv run python -I -c "
import csv, re, sys
pattern = re.compile(r'^[a-z][a-z0-9]*( [a-z0-9]+)*$')
rows = list(csv.DictReader(open('plans/data/instrument-audit/batch-1.tsv'), delimiter='\t'))
bad = [r['name'] for r in rows if not pattern.match(r['name'])
       or r['status'] not in {'SHIP','MOVE','WAIT','ALIAS','DROP'}
       or (r['status'] in {'SHIP','MOVE'} and not r['sound_source'].startswith('http'))
       or (r['status'] in {'SHIP','MOVE'} and bool(r['lowest']) != bool(r['highest']))
       or (r['status'] == 'SHIP' and r['lowest'] and not r['range_source'].startswith('http'))
       or (r['status'] == 'WAIT' and not r['waits_for'])
       or (r['status'] == 'ALIAS' and not r['alias_of'])]
print(len(rows), 'rows;', {s: sum(r['status']==s for r in rows) for s in ('SHIP','MOVE','WAIT','ALIAS','DROP')})
print('bad:', bad); sys.exit(1 if bad else 0)
"
```
Expected: the counts, then `bad: []`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add plans/data/instrument-audit/batch-1.tsv
git commit -m "Instrument audit: batch 1's verification sheet (plucked idiophones, friction, noise makers)"
```

---

### Task 4: Plucked idiophones

**Files:**
- Modify: `src/glitchygames/audio/instruments/catalog.py` (`Family.PLUCKED_IDIOPHONES = 'plucked idiophones'`, after `TUNED_PERCUSSION`)
- Modify: `src/glitchygames/audio/instruments/percussion.py` (rename `_bar` to `struck_bar` everywhere; remove the `kalimba`, `mbira` and `music box` entries)
- Create: `src/glitchygames/audio/instruments/idiophones.py`
- Modify: `src/glitchygames/audio/instruments/registry.py` (`PLUCKED_IDIOPHONES` in `FAMILY_TABLES`, after `TUNED_PERCUSSION`)
- Modify: `src/glitchygames/audio/instruments/aliases.py` (this family's ALIAS rows)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-1.tsv` rows with `family` `plucked idiophones`; `Tag.MECHANICAL` (Task 1);
  `ALIASES` (Task 2).
- Produces: `PLUCKED_IDIOPHONES: Final[tuple[CatalogEntry, ...]]` in `idiophones.py`, and
  `struck_bar(ratios, levels, *, ring_seconds, mallet=0.05, mallet_low_pass=3000.0,
  overtone_ring=0.25) -> Instrument` in `percussion.py` (the renamed `_bar`, unchanged).
  `TINE_RATIOS` and `SINGING_METAL_SECOND_PARTIAL` stay in `percussion.py`, and
  `idiophones.py` imports them.

- [ ] **Step 1: Write the failing test**

```python
def test_plucked_idiophones_hold_the_lamellophones_and_music_boxes():
    """Kalimba, mbira and music box moved here by name; the music box plays itself."""
    plucked = instruments.names(family=Family.PLUCKED_IDIOPHONES)
    assert {'kalimba', 'mbira', 'music box'} <= set(plucked)
    assert not {'kalimba', 'mbira', 'music box'} & set(instruments.names(family=Family.TUNED_PERCUSSION))
    assert instruments.entry('kalimba').playing_range == (Note('C4'), Note('E6'))
    assert 'music box' in instruments.names(tag=Tag.MECHANICAL)
```

Use the range the sheet gives if it corrected `kalimba` (rule 6).

- [ ] **Step 2: Run it and check it fails**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k plucked_idiophones -v`
Expected: FAIL with `AttributeError: PLUCKED_IDIOPHONES`.

- [ ] **Step 3: Write the family**

The module docstring states what makes a plucked idiophone (Hornbostel–Sachs 12: a lamella
plucked and left to ring) and cites the H-S list
(https://en.wikipedia.org/wiki/List_of_idiophones_by_Hornbostel%E2%80%93Sachs_number), as
`percussion.py`'s docstring cites Rossing.

Add one entry per SHIP and MOVE row, in the sheet's order, each preceded by a comment with its
`range_source` and `sound_source` URLs. Moved entries keep their builds exactly (the
`partial(struck_bar, TINE_RATIOS, ...)` calls move unchanged) and get
`tags=frozenset({Tag.MECHANICAL})` where the sheet says `mechanical`. Add this family's ALIAS
rows to `ALIASES`, each with its source URL in a comment.

- [ ] **Step 4: Run the whole catalog suite**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -v`
Expected: PASS, including `test_every_instrument_renders_across_its_range` for every new entry.

- [ ] **Step 5: Check that the code matches the sheet**

Run:
```bash
uv run python -I -c "
import csv
from glitchygames.audio import instruments
rows = [r for r in csv.DictReader(open('plans/data/instrument-audit/batch-1.tsv'), delimiter='\t')
        if r['family'] == 'plucked idiophones']
for r in rows:
    if r['status'] in {'SHIP','MOVE'}:
        e = instruments.entry(r['name'])
        assert (e.family, e.lowest or '', e.highest or '') == ('plucked idiophones', r['lowest'], r['highest']), r['name']
    elif r['status'] == 'ALIAS':
        assert instruments.ALIASES[r['name']] == r['alias_of'], r['name']
    else:
        assert r['name'] not in instruments.CATALOG and r['name'] not in instruments.ALIASES, r['name']
print('matches', len(rows), 'rows')
"
```
Expected: `matches N rows`.

- [ ] **Step 6: Lint and commit**

Run Task 1's lint commands, then:

```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: plucked idiophones, with the kalimba, mbira and music box moved in"
```

---

### Task 5: Friction instruments

**Files:**
- Modify: `catalog.py` (`Family.FRICTION_INSTRUMENTS = 'friction instruments'`, after `PLUCKED_IDIOPHONES`)
- Modify: `percussion.py` (remove `glass harmonica` and `_sustained_glass`)
- Modify: `idiophones.py` (`FRICTION_INSTRUMENTS`; `_sustained_glass` moves here unchanged)
- Modify: `timbres.py` (`rubbed`, Step 4)
- Modify: `registry.py` (`FRICTION_INSTRUMENTS` after `PLUCKED_IDIOPHONES`)
- Modify: `aliases.py` (this family's ALIAS rows)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-1.tsv` rows with `family` `friction instruments`; `blown`, `struck_bar`,
  `SINGING_METAL_SECOND_PARTIAL`.
- Produces: `FRICTION_INSTRUMENTS: Final[tuple[CatalogEntry, ...]]` in `idiophones.py`.

- [ ] **Step 1: Write the failing test**

```python
def test_friction_instruments_hold_the_rubbed_glass_and_bowl():
    """The glass harmonica moved here by name; the struck singing bowl stayed, the rubbed one is new."""
    friction = set(instruments.names(family=Family.FRICTION_INSTRUMENTS))
    assert {'glass harmonica', 'rubbed singing bowl'} <= friction
    assert instruments.entry('singing bowl').family == Family.TUNED_PERCUSSION
    assert instruments.entry('glass harmonica').playing_range == (Note('G3'), Note('C6'))
    # Rubbed, not struck: it swells, so its first 50 ms are quieter than its next 150 ms
    samples = rendered(instruments.get('rubbed singing bowl'), pitch=instruments.entry('rubbed singing bowl').middle_note().name)
    onset = np.max(np.abs(samples[: round(0.05 * SAMPLE_RATE)]))
    held = np.max(np.abs(samples[round(0.05 * SAMPLE_RATE) : round(0.2 * SAMPLE_RATE)]))
    assert onset < held
```

If the sheet makes `rubbed singing bowl` unpitched, use `pitch='A4'` instead of the middle
note. If the sheet changed `glass harmonica`'s range, use its range.

- [ ] **Step 2: Run it and check it fails**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k friction -v`
Expected: FAIL with `AttributeError: FRICTION_INSTRUMENTS`.

- [ ] **Step 3: Write the family**

As in Task 4: the docstring names H-S 13 (friction idiophones) and cites the list; each SHIP
and MOVE row is preceded by its source comment; and ALIAS rows go in `aliases.py`. A rubbed
sound swells (a `blown` attack of 0.2 s or more, as `_sustained_glass` has) rather than
striking. `rubbed singing bowl` keeps the struck bowl's inharmonic partials
(`1.0, SINGING_METAL_SECOND_PARTIAL, 5.15`), which `blown` (harmonic series only) can't
make, and `struck` has no attack. So it needs the new builder in Step 4, the one genuinely new
sound in this batch. Write Step 4 before this entry.

- [ ] **Step 4: a `rubbed` builder in `timbres.py`**

`rubbed(partials: Sequence[Partial], *, attack: float, release: float, low_pass: float | None = None) -> Instrument`:
inharmonic partials, as `struck` has, but swelling over `attack` and sustaining while held.
Its own test, `test_rubbed_partials_swell_and_hold`, renders 0.4 s and asserts the level at
0.35 s is at least 0.5 of the peak (sustained) and the first 20 ms are below 0.3 of the peak
(swelling). It also asserts that more than four partials raise `ValueError`, like
`test_timbre_shapes_refuse_more_layers_than_four_sources`.

- [ ] **Step 5: Run the suite and check the code against the sheet**

Run the Task 4 Step 4 command, then Task 4 Step 5's command with `'friction instruments'`
in place of `'plucked idiophones'` (in both places).
Expected: PASS, then `matches N rows`.

- [ ] **Step 6: Lint and commit**

```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: friction instruments, the glass harmonica moved in, the rubbed singing bowl"
```

---

### Task 6: Noise makers

**Files:**
- Modify: `catalog.py` (`Family.NOISE_MAKERS = 'noise makers'`, after `DRUMS_AND_PERCUSSION`)
- Create: `src/glitchygames/audio/instruments/noise_makers.py`
- Modify: `registry.py` (`NOISE_MAKERS` after `DRUMS_AND_PERCUSSION`)
- Modify: `aliases.py` (this family's ALIAS rows)
- Test: `tests/audio/test_instrument_catalog.py`

**Interfaces:**
- Consumes: `batch-1.tsv` rows with `family` `noise makers`; `drum`, `Tone` (with
  `glide_to`/`glide_seconds` for sirens and horns), and `blown`.
- Produces: `NOISE_MAKERS: Final[tuple[CatalogEntry, ...]]` in `noise_makers.py`.

- [ ] **Step 1: Write the failing tests**

```python
def test_noise_makers_crack_the_whip():
    """The whip crack is a noise maker; the slapstick whip stayed in drums and percussion."""
    assert instruments.entry('whip crack').family == Family.NOISE_MAKERS
    assert instruments.entry('whip').family == Family.DRUMS_AND_PERCUSSION
    assert not instruments.entry('whip crack').pitched


@pytest.mark.parametrize('name', [entry.name for entry in instruments.entries() if not entry.pitched])
def test_unpitched_entries_sound_the_same_at_any_pitch(name):
    """An unpitched entry (a drum, an effect) ignores the pitch it is given."""
    instrument = instruments.get(name)
    assert np.array_equal(rendered(instrument, pitch='A4', name=name), rendered(instrument, pitch='C2', name=name))
```

If an existing (pre-batch) unpitched entry fails the second test, that is a bug. Stop and
report it; don't exempt it.

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest --dummy-only tests/audio/test_instrument_catalog.py -k "noise_makers or any_pitch" -v`
Expected: `test_noise_makers_crack_the_whip` fails with `KeyError: no instrument named 'whip crack'`,
and the any-pitch cases pass (they are the existing unpitched entries).

- [ ] **Step 3: Write the family**

The docstring names H-S 41 (free aerophones: whips, bullroarers, sirens) and 412 (interruptive
and reed free aerophones: horns, party horns), and cites the H-S aerophone list
(https://en.wikipedia.org/wiki/List_of_aerophones_by_Hornbostel%E2%80%93Sachs_number). Each
SHIP row is preceded by its source comment, and ALIAS rows go in `aliases.py`. A siren's
rise or fall is a `Tone` glide in `drum` (the engine's `PitchCurve`); its sustain is a long
`ring_seconds`. Pitched noise makers (a hornophone with a sourced range) use `blown`.

- [ ] **Step 4: Run the suite and check the code against the sheet**

As in Task 5 Step 5, with `'noise makers'`.
Expected: PASS, then `matches N rows`.

- [ ] **Step 5: Lint and commit**

```bash
git add src/glitchygames/audio/instruments tests/audio/test_instrument_catalog.py
git commit -m "Instrument catalog: noise makers (the whip crack, sirens, horns), every one playable as a note"
```

---

### Task 7: Docs, counts and the full checks

**Files:**
- Modify: `src/glitchygames/audio/instruments/__init__.py` (the docstring: the new families,
  tags with `names(tag=...)`, and aliases)
- Modify: `docs/architecture/sound.md` ("The instrument catalog": the count, the family table
  rows for the three new families and tuned percussion's new count and examples, and a bullet
  each on tags and aliases)
- Modify: `CLAUDE.md` (Sound Synthesis, "Instrument catalog": `431 entries in 18 Family`s`
  becomes the new counts, and tags and aliases get one clause each)
- Modify: `plans/future-features.md` (#70: batch 1 done, with the counts by status from the
  sheet, and the next batch named: sound effects and electromechanical, then drums and
  percussion)
- Modify: `plans/2026-11-07-instrument-catalog-expansion-design.md` (the status line: batch 1
  in progress or done, pointing at this plan and `batch-1.tsv`)

- [ ] **Step 1: Get the counts from the code**

Run: `uv run python -I -c "from glitchygames.audio import instruments as i; print(len(i.names()), len(i.families())); [print(f, len(i.names(family=f))) for f in i.families()]; print(len(i.ALIASES), i.names(tag='mechanical'))"`
Use exactly these numbers in the docs.

- [ ] **Step 2: Edit the five files.** Write no counts from memory.

- [ ] **Step 3: Run the full checks**

Run:
```bash
uv run pytest --dummy-only tests/audio
nox -s lint-docs
uv run ruff check src tests scripts noxfile.py
uv run basedpyright
uv run python -m scripts.make_instrument_demos build/instruments
```
Expected: everything passes. The demos write a WAV per instrument to
`build/instruments/<family>/<name>.wav`. The three new families' folders are the ones to listen
to; the owner judges the sound.

- [ ] **Step 4: Commit**

```bash
git add src/glitchygames/audio/instruments/__init__.py docs/architecture/sound.md CLAUDE.md plans/future-features.md plans/2026-11-07-instrument-catalog-expansion-design.md
git commit -m "Docs: batch 1 of the instrument catalog (three families, tags, aliases) and its counts"
```

Pushing and the PR wait for the owner (CLAUDE.md: never push automatically). The pre-push
hooks take about 40 minutes, and nothing in the working tree may change while they run.
