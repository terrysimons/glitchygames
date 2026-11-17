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
