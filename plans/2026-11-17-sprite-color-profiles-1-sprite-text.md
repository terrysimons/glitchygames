# Sprite color profiles, part 1: sprites as text — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sprites as text in memory, both directions and built once: a pygame-free module for a
sprite file's text as data (parse, write, split into frames), and the engine's module that turns
that text into sprites and sprites and images into that text.

**Architecture:** `src/glitchygames/sprites/sprite_toml.py` imports nothing outside the standard
library and works on the document as `tomllib` reads it; every engine writer goes through its
`write_sprite_toml`. `src/glitchygames/sprites/sprite_text.py` builds on it with pygame and
`AnimatedSprite`: the file loader reads a file's text and calls `sprite_from_text`, and `save`
writes `sprite_to_text`, so file and text share one path.

**Tech Stack:** Python 3.14 and 3.15, `tomllib`, pygame-ce 2.5.8, pytest with pytest-mock.

**Spec:** `plans/2026-11-17-sprite-color-profiles.md` (master plan), "Part 1: sprites as text".

## Global Constraints

- `sprite_toml.py` imports only the standard library: no pygame, no `AnimatedSprite`, no engine
  module. Another session lifts it into a pygame-free package without changing its signatures
  (`plans/2026-11-17-sprite-generation-in-the-ai-service.md`).
- The signatures are fixed by the master plan and reviewed by the `/sprite` session: do not rename
  or reorder them.
- A round trip keeps the same parsed sprite, not the same bytes.
- Code must run on Python 3.14 (the browser builds'); lint and type checks target it.
- Keyword-only arguments for every new function; full names, no abbreviations; American spelling.
- Tests in pytest style, `mocker` never `unittest.mock`; real files in `tmp_path`.
- Engine change: every game's, the demos' and Bitmappy's sprite tests run with it
  (`uv run pytest --dummy-only src/games src/demos src/apps tests/sprites tests/test_workspace_sprite_files.py`).
- Sprite-file checks live in `glitchygames.testing.sprite_files` as public `check_*` functions;
  tests call them, never copy them.
- Gates in order: `uv run ruff format`, `uv run ruff check`, `uv run basedpyright`,
  `uv run ty check`, then the tests.

## Review Focus

1. **Per-color alpha** (Bitmappy's `toadstool.toml`, colors at alpha 137 and 128): survives text
   load and write exactly. Pinned in Task 3 (every workspace and library sprite file).
2. **Glyphs outside today's 64** (`#`, `é`, `Ŧ`): the loader already accepts any one character;
   text load and write keep them. Pinned in Task 1.
3. **A single-frame sprite written** comes out in the static layout (`pixels` in `[sprite]`), as
   `save` writes it today. Pinned in Task 4.
4. **Per-frame intervals and loop flags** inside an animation survive text load and write. Pinned
   in Task 3 (the existing timing check, run on the text path).
5. **Color order** in `[colors]` is the file's own order after a round trip, not sorted. Pinned in
   Task 1.

---

### Task 1: the pygame-free text module

**Files:**
- Create: `src/glitchygames/sprites/sprite_toml.py`
- Modify: `src/glitchygames/sprites/animated.py` (`_save_toml`, `_save_toml_single_frame` and the
  `_write_toml_*` helpers: the writing moves into `write_sprite_toml`; the building of the document
  from the sprite stays)
- Test: `tests/sprites/test_sprite_toml.py` (new subject)

**Interfaces:**
- Produces: `parse_sprite_toml(*, text: str, source_name: str) -> dict[str, Any]`;
  `write_sprite_toml(*, data: Mapping[str, Any]) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_text_that_is_not_toml_is_refused_naming_its_source():
    with pytest.raises(ValueError, match='dex from the console'):
        parse_sprite_toml(text='[sprite\nname = ', source_name='dex from the console')

def test_a_written_document_parses_back_to_the_same_document():
    text = STATIC_SPRITE_TEXT  # [sprite] pixels, three colors incl. "#", "é", "Ŧ"
    document = parse_sprite_toml(text=text, source_name='test')
    assert parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test') == document

def test_colors_keep_the_files_order():
    document = parse_sprite_toml(text=COLORS_IN_ORDER_Z_A_M, source_name='test')
    written = write_sprite_toml(data=document)
    assert list(parse_sprite_toml(text=written, source_name='test')['colors']) == ['z', 'a', 'm']

def test_an_animated_document_is_written_in_the_animated_layout():
    document = parse_sprite_toml(text=TWO_ANIMATIONS_TEXT, source_name='test')
    written = write_sprite_toml(data=document)
    assert '[[animation]]' in written and 'pixels' not in written.split('[[animation]]')[0]

def test_the_module_imports_only_the_standard_library():
    module = ast.parse(Path(sprite_toml.__file__).read_text(encoding='utf-8'))
    imported = {top_level_name(node) for node in ast.walk(module) if is_import(node)}
    assert imported <= set(sys.stdlib_module_names) | {'__future__'}
```

Define the three text constants in the test file, small (4×4 pixels at most), each written by hand.

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest --dummy-only --no-cov tests/sprites/test_sprite_toml.py -q`
Expected: FAIL, the module does not exist.

- [ ] **Step 3: Implement `parse_sprite_toml` and `write_sprite_toml` in `sprite_toml.py`**

`parse_sprite_toml` is `tomllib.loads`, with its error re-raised as `ValueError` naming
`source_name`. `write_sprite_toml` writes today's layout from the document: the static layout when
`data['sprite']` has `pixels`, otherwise `[sprite]`, each `[[animation]]` with its frames,
`[colors]` in the document's order, `[[transition]]`. Move the string escaping it needs
(`toml_basic_string`, `toml_pixel_block`, `toml_tags_line`, `toml_multiline_basic_string`,
`toml_key`, `toml_scalar`, today in `animated.py`) into `sprite_toml.py`, with `animated.py`
importing them from there; their existing tests keep passing. `AnimatedSprite._save_toml` and
`_save_toml_single_frame` build the document as today and write `write_sprite_toml(data=...)`.

- [ ] **Step 4: Run the new tests and every existing save round-trip check**

Run: `uv run pytest --dummy-only --no-cov tests/sprites tests/test_workspace_sprite_files.py -q`
Expected: PASS, the save round-trip checks unchanged.

- [ ] **Step 5: Commit**

---

### Task 2: splitting a sprite into one file per frame

**Files:**
- Modify: `src/glitchygames/sprites/sprite_toml.py`
- Test: `tests/sprites/test_sprite_toml.py`

**Interfaces:**
- Consumes: Task 1's `parse_sprite_toml`, `write_sprite_toml`.
- Produces: `split_sprite_text(*, text: str) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_each_frame_becomes_its_own_sprite_in_animation_and_frame_order():
    files = split_sprite_text(text=TWO_ANIMATIONS_TEXT)  # "walk": 2 frames, "idle": 1
    names = [parse_sprite_toml(text=each, source_name='test')['sprite']['name'] for each in files]
    assert names == ['kid-walk-0', 'kid-walk-1', 'kid-idle-0']

def test_a_split_frame_keeps_its_pixels_and_only_the_colors_it_uses():
    first = parse_sprite_toml(text=split_sprite_text(text=TWO_ANIMATIONS_TEXT)[0], source_name='t')
    assert first['sprite']['pixels'] == WALK_FRAME_0_PIXELS
    assert set(first['colors']) == set(WALK_FRAME_0_PIXELS.replace('\n', ''))

def test_a_single_frame_sprite_splits_into_itself():
    (only,) = split_sprite_text(text=STATIC_SPRITE_TEXT)
    assert parse_sprite_toml(text=only, source_name='t')['sprite']['pixels'] == STATIC_PIXELS
```

- [ ] **Step 2: Run them and watch them fail** (`split_sprite_text` not defined)

- [ ] **Step 3: Implement `split_sprite_text`**

Each frame becomes a static-layout document: `[sprite]` with `name`
`<sprite>-<animation>-<frame>`, the source's `description`, `tags` and `frame_anchor`, the frame's
`pixels`, and its hitbox (the frame's, else the sprite's) as `[sprite.hitbox]`; `[colors]` keeps
the glyphs the frame uses, in the source's color order. Frames are numbered from 0 within their
animation, animations in file order.

- [ ] **Step 4: Run the tests** — Expected: PASS

- [ ] **Step 5: Commit**

---

### Task 3: loading a sprite from text, one path with files

**Files:**
- Create: `src/glitchygames/sprites/sprite_text.py`
- Modify: `src/glitchygames/sprites/animated.py` (`_load_toml` reads the file's text and calls the
  text loader; the rest of today's `_load_toml` works on the parsed document), `factory.py`
  (`_analyze_toml_file` and `_get_toml_data` analyze the parsed document; `load_sprite_from_text`)
- Modify: `src/glitchygames/testing/sprite_files.py` (a new check),
  `tests/test_workspace_sprite_files.py`
- Test: `tests/sprites/test_sprite_text.py` (new subject)

**Interfaces:**
- Consumes: Task 1's `parse_sprite_toml`.
- Produces: `sprite_from_text(*, text: str, source_name: str) -> AnimatedSprite`;
  `SpriteFactory.load_sprite_from_text(*, text: str, source_name: str) -> AnimatedSprite`;
  `check_text_and_file_loads_agree(*, sprite_file: Path) -> None` in
  `glitchygames.testing.sprite_files`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES + LIBRARY_SPRITE_FILES, ids=sprite_file_id)
def test_text_and_file_loads_agree(sprite_file):
    check_text_and_file_loads_agree(sprite_file=sprite_file)  # same RGBA frames, metadata,
                                                              # timings, hitboxes, transitions

def test_repair_warnings_name_the_text_source(caplog):
    sprite_from_text(text=SHORT_ROW_TEXT, source_name='dex from the console')
    assert 'dex from the console' in caplog.text

def test_text_with_static_and_animated_content_is_refused_as_a_file_is():
    with pytest.raises(ValueError):
        SpriteFactory.load_sprite_from_text(text=MIXED_TEXT, source_name='test')
```

`LIBRARY_SPRITE_FILES` is Bitmappy's library (`src/apps/bitmappy/src/bitmappy/resources/sprites/`,
which holds `toadstool.toml`), added beside `MEMBER_SPRITE_FILES` in
`tests/test_workspace_sprite_files.py`.

- [ ] **Step 2: Run them and watch them fail** (`sprite_text` does not exist)

- [ ] **Step 3: Implement `sprite_from_text` and the shared loader path**

`AnimatedSprite` gains a text load used by both: the file load reads the file's text (keeping
`FileNotFoundError` for a missing file) and calls it; `_pixel_rows_source` is the `source_name`.
`sprite_from_text` builds `AnimatedSprite(groups=None)` and loads the text;
`SpriteFactory.load_sprite_from_text` runs the factory's existing content analysis on the parsed
document, then `sprite_from_text`. No temporary file anywhere.

- [ ] **Step 4: Run the new tests, then every sprite test in the workspace**

Run: `uv run pytest --dummy-only --no-cov tests/sprites tests/test_workspace_sprite_files.py src/games src/demos src/apps -q`
Expected: PASS.

- [ ] **Step 5: Commit**

---

### Task 4: writing a sprite as text

**Files:**
- Modify: `src/glitchygames/sprites/sprite_text.py`, `animated.py` (`save` writes
  `sprite_to_text`), `src/glitchygames/testing/sprite_files.py`, `tests/test_workspace_sprite_files.py`
- Test: `tests/sprites/test_sprite_text.py`

**Interfaces:**
- Consumes: Task 1's `write_sprite_toml`; Task 3's `sprite_from_text`.
- Produces: `sprite_to_text(*, sprite: AnimatedSprite) -> str`;
  `check_save_writes_the_sprites_text(*, sprite_file: Path, directory: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES + LIBRARY_SPRITE_FILES, ids=sprite_file_id)
def test_save_writes_the_sprites_text(sprite_file, tmp_path):
    check_save_writes_the_sprites_text(sprite_file=sprite_file, directory=tmp_path)
    # the saved file's text == sprite_to_text(sprite=the loaded sprite)

def test_a_single_frame_sprite_is_written_in_the_static_layout():
    text = sprite_to_text(sprite=sprite_from_text(text=STATIC_SPRITE_TEXT, source_name='t'))
    assert 'pixels' in parse_sprite_toml(text=text, source_name='t')['sprite']
```

- [ ] **Step 2: Run them and watch them fail** (`sprite_to_text` not defined)

- [ ] **Step 3: Implement `sprite_to_text`**: the document `save` builds today (static layout for a
  single animation with one frame, as `_is_single_frame_sprite` decides), written by
  `write_sprite_toml`; `save` writes that text to the file.

- [ ] **Step 4: Run the Task 3 command** — Expected: PASS

- [ ] **Step 5: Commit**

---

### Task 5: an image's frames as a sprite file

**Files:**
- Modify: `src/glitchygames/sprites/sprite_text.py`
- Modify: `src/apps/bitmappy/src/bitmappy/film_strip_sprite.py` (`_load_image_as_sprite_frame`
  reads pixels through the shared function, after its canvas resize)
- Test: `tests/sprites/test_sprite_text.py`, Bitmappy's existing image-import tests

**Interfaces:**
- Consumes: Task 4's `sprite_to_text`.
- Produces: `sprite_text_from_frames(*, frames: Sequence[pygame.Surface], frame_intervals:
  Sequence[float], name: str) -> str`; `class SpriteColorLimitError(ValueError)` with
  `color_count: int` and `limit: int`; `surface_rgba_pixels(*, surface: pygame.Surface) ->
  list[tuple[int, int, int, int]]` (row-major), shared with Bitmappy.

- [ ] **Step 1: Write the failing tests**

```python
def test_frames_become_one_animation_with_each_frames_own_interval():
    text = sprite_text_from_frames(frames=[red_4x4(), blue_4x4()], frame_intervals=[0.1, 0.25], name='blink')
    sprite = sprite_from_text(text=text, source_name='t')
    assert [frame.duration for frame in only_animation_frames(sprite)] == [0.1, 0.25]

def test_partial_alpha_is_kept():
    text = sprite_text_from_frames(frames=[half_transparent_red_4x4()], frame_intervals=[0.1], name='glass')
    colors = parse_sprite_toml(text=text, source_name='t')['colors'].values()
    assert {'red': 255, 'green': 0, 'blue': 0, 'alpha': 128} in colors

def test_more_colors_than_glyphs_is_refused_with_the_count():
    with pytest.raises(SpriteColorLimitError) as refusal:
        sprite_text_from_frames(frames=[sixty_five_color_frame()], frame_intervals=[0.1], name='photo')
    assert (refusal.value.color_count, refusal.value.limit) == (65, 64)

@pytest.mark.parametrize('intervals', [[], [0.1, 0.1]])
def test_intervals_must_match_the_frames(intervals):
    with pytest.raises(ValueError, match='frame_intervals'):
        sprite_text_from_frames(frames=[red_4x4()], frame_intervals=intervals, name='x')

def test_frames_of_different_sizes_are_refused():
    with pytest.raises(ValueError, match='size'):
        sprite_text_from_frames(frames=[red_4x4(), red_8x8()], frame_intervals=[0.1, 0.1], name='x')
```

The helpers build `pygame.Surface`s with `SRCALPHA` in the test file.

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Implement**: count the frames' distinct RGBA colors first and refuse past
  `len(SPRITE_GLYPHS)`; build an empty `AnimatedSprite`, one animation named `name` with one
  `SpriteFrame` per surface and its interval, then `sprite_to_text`. Bitmappy's import calls
  `surface_rgba_pixels` instead of its own loop; its tests keep passing unchanged.

- [ ] **Step 4: Run the Task 3 command** — Expected: PASS

- [ ] **Step 5: Commit**, then tell the `/sprite` session (`dev-glitchygames-ea`) part 1 is in.

---

---

### Task 6: saving keeps the loaded palette

Added after the final review (the owner, 2026-11-17: "Keep the palette"). Measured then: loading a
sprite and saving it again dropped unused palette entries in 16 of the 92 member sprite files
(toadstool's unused `█`, laser_dot's 11, saved's 9) and merged duplicate colors (slime-jump's B and
D, b and d, which share a color but not a glyph). The drawn pixels were identical, but the spec says
a round trip keeps the same parsed data, and Part 2's converter reasons over palettes.

**Files:**
- Modify: `src/glitchygames/sprites/animated.py` (what the sprite remembers on load; how
  `to_text` builds `[colors]` and the pixel rows)
- Modify: `src/glitchygames/testing/sprite_files.py`, `tests/test_workspace_sprite_files.py`
- Test: `tests/sprites/test_sprite_text.py`, Bitmappy's save tests

**Interfaces:**
- Consumes: Task 4's `sprite_to_text` / `AnimatedSprite.to_text`.
- Produces: `check_save_keeps_the_parsed_document(*, sprite_file: Path) -> None` in
  `glitchygames.testing.sprite_files`.

**The rules:**
- A loaded sprite remembers its `[colors]` table: every glyph, its color and alpha, in file order.
  Saving writes every remembered entry, used or not.
- A frame whose pixels haven't changed since it was loaded keeps its loaded rows exactly, glyph for
  glyph, so two glyphs sharing a color both survive.
- A frame whose pixels changed (an edit, as in Bitmappy) writes each pixel with the first
  remembered glyph of its color; a color the palette doesn't have gets a new glyph, as today.
- A sprite built in code (no loaded palette) is written as today.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_save_keeps_the_parsed_document(sprite_file):
    check_save_keeps_the_parsed_document(sprite_file=sprite_file)
    # parse_sprite_toml(sprite_to_text(load(file))) == parse_sprite_toml(file's text)

def test_two_glyphs_sharing_a_color_both_survive_a_save():
    text = sprite_to_text(sprite=sprite_from_text(text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='t'))
    assert parse_sprite_toml(text=text, source_name='t') == parse_sprite_toml(text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='t')

def test_an_unused_color_survives_a_save(): ...  # same shape, a [colors] entry no pixel uses

def test_an_edited_pixel_takes_the_first_glyph_of_its_color(): ...  # edit a pixel to an existing color
def test_an_edited_pixel_of_a_new_color_gets_a_new_glyph(): ...
```

The parametrized check goes in `tests/test_workspace_sprite_files.py` (a repository test), the
rest in `tests/sprites/test_sprite_text.py` on hand-written fixtures.

- [ ] **Step 2: Run them and watch them fail** (16 member files and slime-jump fail today)

- [ ] **Step 3: Implement the rules above** in `animated.py`; Bitmappy's saves go through the same
  `to_text`, so its tests run too.

- [ ] **Step 4: Run** `uv run pytest --dummy-only --no-cov tests/sprites tests/test_workspace_sprite_files.py tests/test_suite_collection.py src/games src/demos src/apps -q`, then
  `uv run nox -s test-3.14` (the whole suite, non-editable, 100% coverage) — Expected: PASS

- [ ] **Step 5: Commit**

## Done when

- Every task's tests pass; the gates pass in order; the whole suite passes on 3.14 and 3.15
  (`uv run nox -s test`).
- `sprite_toml.py` imports only the standard library (Task 1's test).
- The `/sprite` session has been told part 1 is committed, with the commit.

## Execution record

The executor's ledger, kept as written: the rulings made while building, the task reviews' fixes and deferred minors, the whole-branch review's fixes and the minors it deferred, and Task 6, added by the owner's palette decision.

Spec: plans/2026-11-17-sprite-color-profiles.md (master plan, Part 1). Worktree:
/Users/terry/Dropbox/dev.glitchygames/glitchygames-sprite-color-profiles, branch
feature/sprite-color-profiles (stacked on feature/zombies-aint-my-neighbors, PR #215).
Execution: subagent-driven (the owner, 2026-11-17: "subagent").

**Pre-flight scan**

| Tasks | Shared file or interface | Produces vs consumes | Found |
|---|---|---|---|
| 1 → 2 | `sprite_toml.py` | 1 produces `parse_sprite_toml`, `write_sprite_toml`; 2 consumes both | agree |
| 1 → 3 | `parse_sprite_toml`; `animated.py` | 3 consumes `parse_sprite_toml`; 1 edits the writers, 3 the loader, in the same file | agree (different methods) |
| 1 → 4 | `write_sprite_toml`; `animated.py` | 4 consumes it; 4 edits `save` | agree |
| 3 → 4 | `sprite_from_text`; `testing/sprite_files.py`; `tests/test_workspace_sprite_files.py` | 3 adds `LIBRARY_SPRITE_FILES` and a check; 4 uses the list and adds a check | agree |
| 4 → 5 | `sprite_to_text` | 5 consumes it | agree |
| 1 (self) | moving `toml_*` helpers out of `animated.py` | other modules import them from `animated` (e.g. `ai/sprite_generator.py`) | see ruling 1 |
| 1 (self) | the stdlib-only test uses helper names it doesn't define (`top_level_name`, `is_import`) | the implementer writes them in the test file | agree |
| 2 (self) | split keeps only the frame's glyphs | its test checks that | agree |
| 3 (self) | text and file loads share one path | its check compares both loads | agree |
| 4 (self) | the save check compares save's file with `sprite_to_text` | it checks save goes through the text path | agree |
| 5 (self) | tests name `only_animation_frames`, surface helpers | the implementer writes them in the test file | agree |
| all | documentation | no task updates docs; a new public module needs its page | see ruling 2 |

- Ruling 1: `animated.py` keeps the `toml_*` names importable (it imports them from
  `sprite_toml.py` and uses them), so existing importers don't change — the plan says "with
  `animated.py` importing them from there" — cost if wrong: an importer breaks, caught by its tests.
- Ruling 2: Task 5's commit also documents both modules on the hand-written sprites page in
  `docs/glitchygames/sprites/` — CLAUDE.md: engine API pages are hand-written; a new public API
  without its page is undocumented — cost if wrong: one small docs edit to move.

**Tasks**
- Task 1: dispatched (BASE 001f8aa8, implementer on sonnet).
- Task 1: implementer DONE_WITH_CONCERNS (35badc4b). Concern 5, a coverage-mode failure of test_an_animated_sprite_joins_only_the_group_it_is_given: not reproduced with the project's coverage settings, alone or with its whole file, on 35badc4b (370 passed) or the base 001f8aa8 (369 passed); likely the implementer's narrower --cov run under the push gate's load. Concerns 1-4 are observations, passed to the review.
- Task 1: review (sonnet): spec ✅; quality needs fixes, 3 Important. ⚠️ coverage item: already checked above (not reproduced).
- Task 1: minor (deferred): static-layout test asserts on a string split, not the parsed pixels (folded into fix round 1 as a one-line change).
- Task 1: minor (deferred): no tests for a document with both `pixels` and `animation`, or a color missing red/green/blue.
- Task 1: minor (deferred): the documents are loose `Any`; a TypedDict would document their shape.
- Task 1: minor (deferred): animated.py imports sprite_toml in two forms (module and one name).
- Task 1: minor (deferred): the stdlib-only test's helper narrows with assert (fine in tests).
- Task 1: Ruling: write_sprite_toml refuses keys it doesn't know (ValueError naming each, by path) rather than dropping them silently; the known keys are exactly what the loader reads (the [alpha] table included if the format has it) — the spec promises a round trip keeps the parsed sprite, so silent loss is the one outcome not allowed, and writing unknown tables back would guess at an undefined format — cost if wrong: a document with an extra key is refused instead of written, visible and easy to relax later.
- Task 1: fix round 1/5 (3 addressed, 1 open — new breakage: the writer refuses shipped sprites the loader accepts: 41 frames without frame_index, e.g. brave-adventurer papyrus; animations without loop or frame_interval; Drawing Fire's top-level `swatches`; commits 35badc4b..4a95573b)
- Task 1: Ruling (supersedes the round-1 ruling on unknown keys): in the engine's own tables ([sprite], its hitbox, [[animation]], frames and their hitboxes, [colors]) every key the loader reads is accepted, keys the loader treats as optional stay optional on write (written when present, omitted when absent), and unknown keys stay refused by path; top-level tables the engine doesn't own (Drawing Fire's `swatches`, read by its own swatches.py; `[alpha]` where a file has one) are written back as they are — games extend sprite files with their own tables, and the round trip must keep them — cost if wrong: a game's table written where it should have been refused, harmless.
- Task 1: fix round 2 implemented (894b1685): every loader-optional key written only when present, the missing-key refusals removed (the loader defaults every key), other top-level tables written back by a generic writer; 10449 workspace sprite tests passed; scoped re-review dispatched.
- Task 1: fix round 2/5 (2 addressed, 0 open — the writer accepts every document the loader accepts; missing keys write cleanly; commits 4a95573b..894b1685)
- Task 1: minor (deferred): TOML dates/datetimes in a game's own table raise TypeError (sprite_toml.py ~564-583, toml_scalar ~172), where the module otherwise raises named ValueErrors; no shipped sprite has one.
- Task 1: minor (deferred): the shipped-sprite round trip imports MEMBER_SPRITE_FILES from tests/test_workspace_sprite_files.py; the list belongs in a shared helper (glitchygames.testing.sprite_files or a tests/ support module). Pointed at Task 3, which edits that file.
- Task 1: minor (deferred): _sprite_section writes name/description/frame_anchor through toml_basic_string unconditionally; a hand-built non-string value raises deep inside (not reachable from a parsed document).
- Task 1: minor (deferred): NaN in a game's table writes as nan (round-trips, but nan != nan in equality tests); game tables write arrays of tables inline, not as [[headers]].
- Task 1: complete (commits 001f8aa8..894b1685, review clean after 2 fix rounds)
- Task 2: Ruling: frame names use the loader's defaults where the source omits a key (sprite name 'animated_sprite', animation namespace 'default'), so every split file is named `<sprite>-<animation>-<frame>` — Task 1 made every key optional — cost if wrong: an unusual name for a file with no name, visible.
- Task 2: Ruling: a game's own top-level tables (e.g. Drawing Fire's `swatches`) are not carried into split frames, and split_sprite_text's docstring says so — a split frame is a new single-image sprite, not a round trip, and those tables name glyphs the frame may not keep — cost if wrong: a frame without its game's table, easy to add.
- Task 2: dispatched (BASE 894b1685, implementer on sonnet).
- Task 2: implementer DONE_WITH_CONCERNS (a05b77b9): observations (static name <sprite>-default-0, fixture names, extra edge cases incl. a pixel-less frame refused); task review dispatched with the pixel-less refusal named as a point to judge.
- Task 2: review (sonnet): spec ✅; quality needs fixes, 1 Important (a frame with no pixels refused, though the loader accepts it as empty).
- Task 2: Ruling: a static sprite's single frame is named `<sprite>-default-0` — it follows ruling 1's defaults; the brief was silent — cost if wrong: a rename.
- Task 2: minor (deferred): frame-level keys other than pixels and hitbox (a per-frame frame_interval) aren't carried and the docstring doesn't list them.
- Task 2: minor (deferred): sprite_toml.py mixes the literals 'description'/'frame_anchor' with the TAGS_KEY constant.
- Task 2: minor (deferred): the invalid-TOML ValueError path of split_sprite_text is documented but not tested.
- Task 2: minors folded into fix round 1 (cheap, same lines): the shipped-sprite test's parametrization could silently become empty; duplicate frame names when two animations share a namespace, to be stated in the docstring.
- Task 2: fix round 1 implemented (021ae84a, 02b66421 lint fixes); implementer concerns: tests not written failing-first; an empty pixels value may not round-trip (written as a blank row, read back as a newline), with tests stripping it. Scoped re-review dispatched with both as named risks.
- Task 2: fix round 1/5 (3 addressed, 1 open — new: toml_pixel_block writes pixels '' as a blank row (reads back '\n'), and any pixels without a trailing newline gain one ('a' → 'a\n'), so round trips aren't exact; the new tests strip the difference; commits a05b77b9..02b66421)
- Task 2: Ruling: toml_pixel_block writes the opening """, a newline, the text exactly as given (escaped as today), and the closing """ — every pixels value then round-trips exactly, and text ending in a newline (every shipped file) keeps today's layout — cost if wrong: a pixel block's closing quotes on the last row's line for hand-built text without a final newline, valid TOML.
- Task 2: TDD note: the round-1 tests weren't shown failing first; the re-review judged from the diff that the pixel-less frame and pixel-less static tests would have failed on a05b77b9 (raised / returned []). Round 2 must show its strict round-trip tests failing first.
- Task 2: fix round 2 implemented (39d06e78): exact pixel blocks; RED shown; five call sites (animated.py x2, sprite_generator, bitmappy ai_manager x2) now add the final newline the writer used to add. Re-review dispatched.
- Task 2: fix round 2/5 (1 addressed, 0 open — exact pixel blocks; five call sites byte-identical to before; commits 02b66421..39d06e78)
- Task 2: minor (deferred): the five pixel-block callers add the final newline in two idioms (removesuffix + newline; plain + newline).
- Task 2: complete (commits 894b1685..39d06e78, review clean after 2 fix rounds)
- Task 3: Ruling: if MEMBER_SPRITE_FILES already includes Bitmappy's library (Task 1 reported it does), use it rather than adding a duplicate LIBRARY_SPRITE_FILES list; move the sprite-file lists into a shared helper (glitchygames.testing.sprite_files or a tests/ support module) and import it from both test modules — the plan names LIBRARY_SPRITE_FILES only to cover the library, and Task 1's review deferred the cross-test-module import to this task — cost if wrong: one list to split again.
- Task 3: dispatched (BASE 39d06e78, implementer on sonnet).
- Task 3: implementer DONE_WITH_CONCERNS (2bcf4c76): lists moved to tests/workspace_sprite_files.py; two engine test files added to REPOSITORY_TEST_FILES to pass the engine-reaches-scripts guard (named for review against CLAUDE.md); invalid-TOML message changed. Review dispatched.
- Task 3: review (sonnet): spec ❌ on one item (engine tests reclassified as repository tests to pass the scripts/ guard, against CLAUDE.md), else met; quality needs fixes.
- Task 3: minors folded into fix round 1 (the one-path promise): the factory's file route parses with tomllib itself, so a bad-TOML file and bad-TOML text give different errors; pin the file route's message with a test.
- Task 3: minor (deferred): check_text_and_file_loads_agree shares the loader's code, so it guards regressions rather than finding differences (a mutation test shows it can fail).
- Task 3: minor (deferred): testing/sprite_files.py module docstring wraps oddly near line 5.
- Task 3: fix round 1 implemented (a1eac4fc): member-file tests moved to tests/test_workspace_sprite_files.py, REPOSITORY_TEST_FILES entries removed, factory file reads through parse_sprite_toml (red first). Concern: a file is still parsed twice on load (analysis, then load), as before this task. Re-review dispatched.
- Task 3: fix round 1/5 (3 addressed, 0 open — member-file tests moved to the repository test file; factory reads through parse_sprite_toml; pinned; commits 2bcf4c76..a1eac4fc)
- Task 3: minor (deferred): load_sprite parses a file twice (analysis, then load), as before this task; avoiding it means restructuring _analyze_file, which tests patch.
- Task 3: minor (deferred): a sprite file with invalid UTF-8 now raises UnicodeDecodeError (a ValueError) from the factory instead of TOMLDecodeError.
- Task 3: complete (commits 39d06e78..a1eac4fc, review clean after 1 fix round)
- Task 4: dispatched (BASE a1eac4fc, implementer on sonnet), carrying: workspace-wide checks go in tests/test_workspace_sprite_files.py, never engine test files; the shared list is tests/workspace_sprite_files.py's MEMBER_SPRITE_FILES (Bitmappy's library included).
- Task 4: implementer DONE_WITH_CONCERNS (fb0465a3): new public AnimatedSprite.to_text() (sprite_to_text delegates; circular import), _save_as_static_sprite removed as dead, _save_toml/_save_toml_single_frame kept as thin writers for tests, docs updated. Review dispatched.
- Task 4: review (sonnet): spec ✅; 2 Important (production-dead _save_toml/_save_toml_single_frame wrappers kept for tests; new public AnimatedSprite.to_text without a direct test or docs).
- Task 4: Ruling: keep AnimatedSprite.to_text() public, as the method form of the interface, with a direct test and a docs mention; sprite_to_text stays the interface the plan names — making it private would mean a cross-module private call, a lint rule the owner's rules say needs asking before suppression — cost if wrong: one rename later.
- Task 4: minors folded into fix round 1 (same lines): the single-frame log line moves from to_text into save; the animated sprite_to_text test's docstring claims a load-back the test doesn't do.
- Task 4: minor (deferred): check_save_writes_the_sprites_text compares save's output with to_text, which save calls (near-tautological; reloading is covered by the earlier save round-trip checks).
- Task 4: fix round 1 implemented (93f8b970): wrappers removed and tests repointed; to_text tested directly; log moved to save; animated test reloads. Re-review dispatched.
- Task 4: fix round 1/5 (4 addressed, 0 open — wrappers removed, to_text tested and documented, log in save, reload compared; commits fb0465a3..93f8b970)
- Task 4: complete (commits a1eac4fc..93f8b970, review clean after 1 fix round)
- Task 5: dispatched (BASE 93f8b970, implementer on sonnet), carrying ruling 2 (document both modules on docs/glitchygames/sprites/index.md), the workspace-test rule, and the interface the /sprite session reviewed.
- Task 5: implementer DONE (843e8e89): sprite_text_from_frames, SpriteColorLimitError, surface_rgba_pixels shared with Bitmappy, docs section on the sprites page; lint-docs passed. Review dispatched.
- Task 5: review (sonnet): spec ❌ on transparency, else met; 2 Important (alpha-0 pixels not canonicalized, each RGB under alpha 0 a glyph, false color-limit refusals; opaque magenta in an image meets the transparency key, unpinned).
- Task 5: Ruling: every alpha-0 pixel becomes one color, the transparency key made explicit: (255, 0, 255) with alpha 0 — it reads as transparent whether a loader keys magenta or reads alpha, and an image's invisible pixels can't trip the limit — cost if wrong: the canonical transparent entry changes, one constant.
- Task 5: Ruling: an opaque magenta pixel's fate is the loader's: check what the loader does with it, pin it with a test, and document it on the docs page as a limit of the format (if it turns transparent, the image loses that color, which is said, not hidden) — cost if wrong: a documented limit later lifted.
- Task 5: minors folded into fix round 1: the test helper sixty_five_color_surface takes color_count (rename); the duplicate literal assertion at test_sprite_text.py:577 needs a comment saying it pins today's 64.
- Task 5: minor (deferred): surface_rgba_pixels builds its list with a Python double loop (as Bitmappy did); numpy would be faster for large images.
- Task 5: fix round 1 implemented (ce9803f9): alpha-0 pixels canonicalized to the key (its glyph outside the 64, so it is outside the limit); opaque magenta probed (loads as the key, draws transparent), pinned and documented; RED 3 failed. Re-review dispatched.
- Task 5: fix round 1/5 (4 addressed, 0 open — transparent pixels one key color outside the 64; opaque magenta pinned and documented; helper renamed; literal commented; commits 843e8e89..ce9803f9)
- Task 5: complete (commits 93f8b970..ce9803f9, review clean after 1 fix round)
- Final: whole-branch review dispatched (opus, 001f8aa8..ce9803f9); controller running ruff, basedpyright, ty, nox -s lint and nox -s test (both Pythons) in parallel.
- Final review (opus): with fixes. 5 Important: (1) write_sprite_toml writes wrong-typed values wrongly (bool → invalid TOML; tags string → list of characters; string numbers → ints; list pixels → repr); (2) malformed shapes raise AttributeError/TypeError, not ValueError, and Raises undocumented; (3) split numbers frames in file order, the loader by frame_index; (4) a loaded and re-saved sprite drops unused palette entries (16 of 92 files) and merges duplicate colors (slime-jump): owner's decision; (5) SPRITE_KEYS lacks Part 2's profile and color_space.
- Final: Ruling: fix wave for 1, 2, 3, 5 now: every document parse_sprite_toml accepts is either written back equal or refused with a ValueError naming each path (dates written via isoformat); one shared frame ordering (frame_tables_in_load_order moves into sprite_toml); add profile and color_space to SPRITE_KEYS now, as the spec fixes them — the other session lifts this module unchanged — cost if wrong: a stricter writer than a caller expected, visible.
- Final: correction to the Task 5 ruling text: the transparency key is written as [colors."█"] red=255 green=0 blue=255 with no alpha key (the docs page states it correctly); an alpha-reading consumer sees opaque magenta. Whether to write alpha = 0 goes to the fix wave as a check.
- Final: minors folded into the fix wave (from the reviewer's triage): deferred 46, 48, 59 (inside 1 and 2); 57 (a docstring line: split drops per-frame frame_interval); the stale docstring in tests/workspace_sprite_files.py:7-9; surface_rgba_pixels missing from the docs page.
- Final: fix wave implemented (4ae9cbc3): findings 1-4 and the small items; finding 5 not done (alpha = 0 on the key changes the loader's data, so left, per the ruling).
- Final: the controller's full gate (ruff, basedpyright, ty, nox lint all 0; nox -s test failed on both Pythons) found two failures no task subset covers: (a) test_every_shipped_sprite_file_round_trips errors on its parameter ids under nox's non-editable install (the engine's own sprites live in site-packages, not under the repository); (b) on 3.15, after 4ae9cbc3 landed mid-run, test_process_state_guard refuses the new module-level HITBOX_VALUE_KINDS and COLOR_VALUE_KINDS. Both sent back to the fix-wave implementer.
- Final: the owner decided the palette question: saving keeps the loaded palette and glyph assignments (unused and duplicate colors included), so a round trip keeps the same parsed data. Added as Task 6 after the fix wave's re-review.
- Final: fix wave follow-up (d718df11): installed-engine sprite ids; MappingProxyType constants; a test for check_save_writes_the_sprites_text's failure branch (coverage gap). nox -s test-3.14 passes (28461, 100%). Scoped re-review of ce9803f9..d718df11 dispatched; controller runs nox -s test-3.15.
- Final: scoped re-review of the fix wave (ce9803f9..d718df11): all 9 addressed, no new Critical/Important.
- Final: minor (deferred): the write-or-refuse invariant test doesn't assert that its "should write" cases are written (dates and Part 2 keys have positive tests; empty containers don't).
- Task 6 (added by the owner's decision, 2026-11-17: "Keep the palette"): planned in the plan file and dispatched after the fix wave.
- Final: controller's nox -s test-3.15 at d718df11: dummy run 28461 passed, 100% coverage; the native rerun failed one test, test_a_games_revision_is_its_own_else_the_engines (HEAD da565d5c vs the session's stamp d718df11): the controller committed Task 6's plan mid-run. An artifact, not a defect; the whole gate reruns after Task 6 with nothing committing during it.
- Task 6: dispatched (BASE da565d5c, implementer on opus: judgment-heavy glyph tracking).
- Task 6: implementer NEEDS_CONTEXT (uncommitted): palette and glyph rows kept for all 92 files; "unchanged frame" = its pixels still decode from its loaded rows (Bitmappy changes pixels by four routes that never mark a frame); 7 failing pending decisions; found a pre-existing bug.
- Task 6: Ruling: an animation loaded without frame_index is saved without it (each animation remembers it, carried through renames as _loop_flags is) — the owner's "same parsed data" — cost if wrong: a key that could be added later.
- Task 6: Ruling: a game's own top-level tables (soldier.toml's swatches) are written back unchanged on save — Task 1's ruling for write_sprite_toml, applied to save — cost if wrong: harmless extra table.
- Task 6: Ruling: keep BUGS.md #200 item 4 (alpha written only for 0-254; an explicit 255 loads as plain RGB); check_save_keeps_the_parsed_document treats an explicit alpha = 255 as equal to no alpha — "keep the palette" protects colors and glyphs, and an explicit 255 carries no information under #200's one-shape rule — cost if wrong: toadstool's redundant alpha = 255 key isn't kept, one rule to relax.
- Task 6: Ruling: fix in this task, test-first, the pre-existing bug the implementer found: magenta falls back to the █ glyph even when the palette uses █ for another color, so those pixels reload as the wrong color — this task reworks that glyph assignment — cost if wrong: none (a bug fix with a regression test).
- Task 6: implementer DONE_WITH_CONCERNS (06f82b68): rulings applied; █ collision: the key takes █ if free, else the first unused glyph, else 'Too many colors'. nox -s test-3.14 passed (28572, 100%). Concerns: Bitmappy's undo of an animation removal brings frame_index back (public signature); a zombies groan seed 1270429352 fails on HEAD's engine too (PR #215's game; controller reproduces there). Task review dispatched.
- Task 6: review (da565d5c..06f82b68): spec ✅; Changes requested: 1 Important (a frame's loaded rows kept in a sprite whose palette lacks their glyphs: an undefined glyph decodes as magenta, so a moved frame's transparent pixel saves as a new color; reproduced by probe_move.py).
- Task 6: minor (deferred): remembered rows cost ~+31% over frame.pixels per loaded instance (largest sprite 370 KB vs 1.20 MB); kept rows decoded twice per save (72 ms for the largest).
- Task 6: minor (deferred): Bitmappy's undo of an animation removal (restore_animation_settings) brings frame_index back; pixels unaffected. Goes to TODO.
- Task 6: minor (deferred): an unused transparency key glyph can be added when transparent pixels sit only in kept frames (_any_pixel_is_magenta scans kept frames too).
- Task 6: fix round 1 dispatched (resume implementer): the Important finding, with its cross-sprite test.
- Task 6: fix round 1/5 (3 addressed, 0 open; commits 06f82b68..e216633e)
- Task 6: complete (commits da565d5c..e216633e, review clean after 1 round)
