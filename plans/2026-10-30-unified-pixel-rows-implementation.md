# One Rule for Sprite Pixel Rows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every pixel block in the engine, Bitmappy, the AI path, the repo's sprite checks and the
QuickLook preview goes through one rule that never removes a pixel and reports every repair.

**Architecture:** One pure function, `normalize_pixel_rows`, in
`src/glitchygames/sprites/pixel_utils.py`, returns the rectangular rows and the repairs it made;
a strict flag raises instead. Every Python parser calls it. Every pixel writer escapes rows with
one helper. QuickLook's `PixelRows.swift` mirrors the function, and golden frames prove that they
agree.

**Tech Stack:** Python 3.13, pygame-ce, pytest; Swift 6 / SwiftPM (`src/quicklook`), swift-testing.

**Spec:** `docs/specs/2026-10-30-unified-pixel-rows-design.md`

## Global Constraints

- **Worktree and branch:** work in `/Users/terry/Dropbox/dev.glitchygames/glitchygames-pixel-rows`,
  on branch `feat/unified-pixel-rows`, based on `origin/main` 1e42b124.
- **Commits and pushes:** commit per task. Never push; the owner pushes or asks for it.
- **Out of bounds:** don't touch `third_party/` or the pygame-ce submodule.
- **Code style:**
  - Match the surrounding code: single quotes, Google docstrings with `Returns:`/`Raises:`
    sections, `Self` annotations, full words in names (no abbreviations), American spelling.
  - Read the comments attached to code before changing it.
  - Attribute any content taken from a reference.
- **Lengths:** counted in code points (`len(str)`); Swift uses `unicodeScalars`.
- **Padding:** a padded pixel is `PADDING_GLYPH = '\x00'` in the rows. It draws as magenta
  (255, 0, 255), the engine's transparency key.
- **Repair messages:** worded exactly as in Task 1. They must not contain the words that
  `build_retry_prompt` matches for other errors: "empty", "truncated", "incomplete",
  "mixed … format", "comma", "markdown".
- **Warnings:** a warning thrown by a test is a finding to understand, not noise.
- **Test commands:**
  - Python: `uv run pytest <path> -q`.
  - Full suite: `uv run pytest -n auto -q`.
  - Swift: `cd src/quicklook && swift test`.
  - Lint before the branch is done: `nox -s lint` and `nox -s static-analysis`.

## Review Focus

1. **An AI response that won't parse as TOML.** The row check must skip it, and the existing
   handling applies. Pinned in Task 5 (`test_unparseable_response_skips_the_row_check`).
2. **A palette that defines U+0000.** Padding must still draw transparent, not that color.
   Pinned in Task 2 (`test_palette_key_u0000_is_dropped_and_reported`) and Task 7.
3. **Bitmappy's repair notice after an AI load.** It must still be visible once the AI manager
   updates its UI. Pinned in Task 6 (`test_ai_load_with_repairs_shows_the_notice`).
4. **CRLF files and tab indentation.** These are tidied, never reported. Pinned in Task 1
   (`test_crlf_is_tidied_not_reported`, `test_shared_tab_indentation_is_removed`).
5. **A sprite with only blank pixel text.** No frame, and no crash in any caller. Pinned in
   Task 1 (`test_blank_text_has_no_rows`) and Task 2 (`test_blank_frame_is_skipped`).

---

### Task 1: `normalize_pixel_rows` and `palette_key_problems`

**Files:**
- Modify: `src/glitchygames/sprites/pixel_utils.py`
- Test: `tests/sprites/test_pixel_utils.py`

**Interfaces:**
- Produces:
  - `PADDING_GLYPH: str = '\x00'`
  - `@dataclass(frozen=True) class NormalizedPixelRows: rows: tuple[str, ...]; width: int; height: int; repairs: tuple[str, ...]`
  - `normalize_pixel_rows(pixels: str, palette_glyphs: Collection[str], *, strict: bool = False, label: str = 'pixels') -> NormalizedPixelRows`
  - `palette_key_problems(palette_glyphs: Iterable[str]) -> tuple[str, ...]`
  - Strict mode raises `ValueError(f'{label}: ' + '; '.join(repairs))`.

**The rule** (spec, "The rule", steps 1–5):
1. Split on `'\n'`.
2. `rstrip(' \t\r')` each line.
3. Drop leading and trailing `''` lines.
4. Remove the longest leading run of spaces and tabs, character for character, that is shared by
   every non-blank line.
5. W = the maximum length; pad each row with `PADDING_GLYPH` to W.

**Repair messages, exact text:**
- **Ragged rows:** `'row widths differ ({widths}); short rows padded with transparent pixels to {width}'`.
  - `widths` is the sorted distinct widths, as `', '.join`.
  - A row counts as short only if its length *before* step 2 (after the step-4 prefix
    removal) is still `< W`.
- **Blank interior lines:** `'blank line between rows (line {numbers}); drawn as transparent rows'`.
  - Line numbers are 1-based within the block after step 3.
- **Unknown glyphs:** `'glyphs not in the palette: {glyphs}; drawn transparent'`.
  - `glyphs` is the sorted distinct glyphs, each as `repr`, joined with `', '`.
  - Spaces are excluded.
- **Bad palette keys** (from `palette_key_problems`):
  `'palette keys that are not one code point: {keys}'`.
  - Covers keys with `len(key) != 1`, and the key `'\x00'`.
  - Keys are `repr`, sorted.

- [x] **Step 1: Write the failing tests** in a new `TestNormalizePixelRows` class:
  - `test_rectangle_is_unchanged_and_unreported`: `'ab\nab'` → rows `('ab', 'ab')`, width 2,
    height 2, repairs `()`.
  - `test_long_row_widens_never_truncates`: `'x\nxxxx\nx\nx'`, palette `'x'` → rows
    `('x\0\0\0', 'xxxx', 'x\0\0\0', 'x\0\0\0')`. The repair text equals
    `'row widths differ (1, 4); short rows padded with transparent pixels to 4'`.
  - `test_mode_cannot_cut_a_row`: `'abcd\nab\nab'` → rows[0] == `'abcd'`.
  - `test_blank_interior_line_is_a_transparent_row`: `'ab\n\nab'` → rows[1] == `'\0\0'`. The
    blank-line repair names line 2.
  - `test_outer_blank_lines_and_trailing_whitespace_are_tidied`: `'\n\nab  \n ab\t\n\n'` →
    rows `('ab\0', ' ab')`, repairs `()`. `'ab'` is not short, because before the trim it was
    `'ab  '`, which has length 4, at least W = 3.
  - `test_shared_indentation_is_removed`: `'    ab\n    ab'` → `('ab', 'ab')`, no repairs.
  - `test_shared_tab_indentation_is_removed`: `'\tab\n\tab'` → `('ab', 'ab')`.
  - `test_unshared_indentation_stays_and_is_not_reported`: `'  x  \n xxx \nxxxxx'` (a pyramid)
    → `('  x\0\0', ' xxx\0', 'xxxxx')`, repairs `()`.
  - `test_mixed_prefix_characters_are_not_shared`: `' \tab\n\t ab'` → rows `(' \tab', '\t ab')`.
    The prefix differs character for character. The only repair is the unknown-glyph one, for
    `'\t'`: only spaces are exempt.
  - `test_crlf_is_tidied_not_reported`: `'ab\r\nab\r\n'` → `('ab', 'ab')`, repairs `()`.
  - `test_unknown_glyph_is_reported_space_is_not`: `'aq \na  a'` with palette `'a'` → the
    repair text equals `"glyphs not in the palette: 'q'; drawn transparent"`.
  - `test_blank_text_has_no_rows`: `''` and `'\n  \n'` → rows `()`, width 0, height 0, repairs
    `()`.
  - `test_each_code_point_is_one_pixel`: `'e\u0301e'` → width 3, and `'\u2764\ufe0f'` →
    width 2.
  - `test_strict_raises_with_every_repair`:
    `pytest.raises(ValueError, match=r"^walk frame 0: row widths differ .*; blank line")` for
    `'ab\n\na'` with `strict=True, label='walk frame 0'`.
  - `test_palette_key_problems`: `palette_key_problems(['a', '\u2764\ufe0f', '\x00', 'b'])` ==
    `("palette keys that are not one code point: '\\x00', '\u2764\ufe0f'",)`. Write the expected value
    with `repr` in the test; `palette_key_problems(['a'])` == `()`.

- [x] **Step 2: Run them and watch them fail.**
  Run: `uv run pytest tests/sprites/test_pixel_utils.py -q -k "NormalizePixelRows or palette_key"`.
  Expected: FAIL with an ImportError for `normalize_pixel_rows`.

- [x] **Step 3: Implement** the function, the dataclass, the constant and `palette_key_problems`
  in `pixel_utils.py`, in the module's style. The docstring explains the rule and cites the
  spec. No logging here: callers log.

- [x] **Step 4: Run them and watch them pass.** Run the same command. Expected: all pass, no
  warnings.

- [x] **Step 5: Commit**: "Sprites: one rule for pixel rows, normalize_pixel_rows (never
  truncates, reports repairs)".

### Task 2: The engine loader uses it

**Files:**
- Modify: `src/glitchygames/sprites/animated.py`. That is `_convert_static_sprite`,
  `_create_toml_frame`, `build_color_map` and the TOML load entry point, and it removes
  `parse_toml_pixel_lines` and `_validate_toml_frame_dimensions`.
- Test: `tests/sprites/test_animated_sprite.py`. Rewrite `TestConvertStaticSpriteInconsistentWidths`
  (line ~2249) and the `'Inconsistent line lengths'` test (line ~3860) for the new rule; don't
  delete their intent.

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `AnimatedSprite.pixel_row_repairs: list[str]`. It is reset on every load. Each entry is
    `f'{label}: {repair}'`, where `label` is `'sprite'` for a static sprite, or
    `f'{namespace} frame {frame_index}'`, or `'palette'`.
  - One `self.log.warning('%s: pixel rows repaired: %s', filename, '; '.join(block_repairs))`
    per repaired block. Use the file name when known, else `'<data>'`.
  - The palette's problems are logged once per load.

- [x] **Step 1: Write the failing tests**, as full loads from TOML text written to `tmp_path`:
  - `test_static_short_row_pads_transparent`: the static `'ab\na'` → `frame.pixels[3]` is
    magenta (255, 0, 255), and `pixel_row_repairs` has one `'sprite: row widths differ'` entry.
  - `test_animated_sword_keeps_its_crossguard`: the animated frame `'x\nxxxx\nx\nx'` → surface
    4×4, and row 1 is four `x` colors.
  - `test_animated_blank_interior_line_is_kept`: frame height 3, and row 1 is transparent.
  - `test_static_and_animated_agree`: the same ragged text as a static sprite and as a one-frame
    animation gives identical `frame.pixels`.
  - `test_blank_frame_is_skipped`: a frame whose pixels are `'\n  \n'` is skipped, as today.
  - `test_palette_key_u0000_is_dropped_and_reported`: palette `"\u0000"` red, frame `'a\naa'`
    → the padded pixel is magenta, and `pixel_row_repairs` has a `'palette:'` entry.
  - `test_repairs_are_logged_once_per_block`: `caplog` holds exactly one WARNING per repaired
    block, naming the file.
  - `test_clean_sprite_has_no_repairs`: load `small_heart.toml` → `pixel_row_repairs == []`.
  - `test_before_and_after_table`: parametrized over the seven rows of the spec's "Before and
    after" table. Each case loads as a static sprite and as a one-frame animation, and both
    draw the spec's "New" column (`·` = transparent; palette `x a b c d` as in the table).

- [x] **Step 2: Run them and watch them fail.**
  Run: `uv run pytest tests/sprites/test_animated_sprite.py -q -k "before_and_after or pads_transparent or crossguard or interior_line or agree or blank_frame or u0000 or once_per_block or no_repairs"`.
  Expected: FAIL. The sword test fails with a 1-wide surface, and the others fail on the
  missing attribute.

- [x] **Step 3: Implement.**
  - Both paths call `normalize_pixel_rows(pixels, color_map.keys(), label=...)`.
  - `build_color_map` drops a `'\x00'` key. The load reports `palette_key_problems`.
  - The static path's unknown-glyph handling already draws magenta; keep it.
  - Delete the two old functions. Task 3 moves their callers.

- [x] **Step 4: Run the file**, `uv run pytest tests/sprites -q`. Expected: all pass. Read
  every failure in the old tests, and rewrite only those that pin the old rule.

- [x] **Step 5: Commit**: "Sprites: static sprites and animation frames load through
  normalize_pixel_rows".

### Task 3: The other parsers, the strict repo check, and cobra

**Files:**
- Modify:
  - `src/glitchygames/testing/sprite_files.py` (`check_rows_have_equal_lengths`)
  - `scripts/audit_hitboxes.py` (lines ~145, ~166)
  - `src/glitchygames/sprites/bitmappy_sprite.py` (`_parse_static_toml_data`)
  - `src/apps/bitmappy/src/bitmappy/ai_worker.py` (`_extract_example_size`)
  - `src/glitchygames/tools/ascii_renderer.py` (`colorize_pixels`)
  - `src/games/brave-adventurer/src/brave_adventurer_papyrus/sprites/cobra.toml`
- Test:
  - `tests/testing/test_sprite_files.py`
  - `tests/sprites/test_sprite_bitmappy.py`
  - `src/apps/bitmappy/tests/test_bitmappy_ai_worker.py`
  - `tests/tools/test_ascii_renderer.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `check_rows_have_equal_lengths(*, sprite_file: Path) -> None`, same signature,
  which now raises `AssertionError(f'{sprite_file} {label}: {repairs}')` on any repair in strict
  mode, palette problems included.

- [x] **Step 1: Write the failing tests.**
  - `test_check_fails_on_glyph_missing_from_palette`, `test_check_fails_on_blank_interior_line`,
    `test_check_fails_on_bad_palette_key`: hand-written files in `tmp_path`, each
    `pytest.raises(AssertionError, match=...)`.
  - `test_check_passes_a_space_pyramid`.
  - `test_bitmappy_sprite_fallback_pads_like_the_engine`: `BitmappySprite` loading the static
    `'ab\na'` draws a 2-wide image whose pixel (1, 1) is transparent (magenta). Today the width
    comes from the first row.
  - `test_example_size_uses_the_widest_row`: `_extract_example_size({'pixels': 'a\naaa'})` ==
    `(3, 2)`.
  - `test_colorize_pixels_keeps_unshared_indentation`: rows keep leading spaces that only some
    rows have.
  - `test_cobra_eye_has_a_color`: the cobra's `e` resolves to (180, 30, 30).

- [x] **Step 2: Run them and watch them fail.**
  Run: `uv run pytest tests/testing/test_sprite_files.py tests/sprites/test_sprite_bitmappy.py src/apps/bitmappy/tests/test_bitmappy_ai_worker.py tests/tools/test_ascii_renderer.py -q`.
  Expected: the new tests fail.

- [x] **Step 3: Implement.** Each caller uses `normalize_pixel_rows`. Add to cobra.toml:
  `"e" = { red = 180, green = 30, blue = 30 }` after `"E"`, with a comment:
  `# Second eye: a darker shade of E, like g is of G`.

- [x] **Step 4: Run** the four files, then the workspace checks:
  `uv run pytest tests/test_workspace_sprite_files.py tests/sprites/test_engine_sprite_files.py src/games/brave-adventurer/tests -q`.
  Expected: all pass. If a repo sprite fails strict, stop and report it (spec: no art changes
  except cobra).

- [x] **Step 5: Commit**: "Sprites: every row parser uses normalize_pixel_rows; the repo check
  runs strict; cobra's second eye gets a color".

### Task 4: Writers escape pixel rows (and the AI rewrite keeps alpha)

**Files:**
- Modify:
  - `src/glitchygames/sprites/animated.py`: add `toml_pixel_block`, used by the static writer
    (~line 1906) and `_write_toml_animations` (~line 2339).
  - `src/apps/bitmappy/src/bitmappy/ai_manager.py`: `_format_animation_sections` and
    `_construct_toml_with_preserved_formatting`.
  - `src/glitchygames/ai/sprite_generator.py`: the example writers at ~215 and ~282.
- Test:
  - `tests/sprites/test_save_load_pixel_preservation.py`
  - `src/apps/bitmappy/tests/test_bitmappy_ai_manager.py`
  - `tests/ai/test_sprite_generator.py`
  - `src/apps/bitmappy/tests/test_bitmappy_png_loading.py`

**Interfaces:**
- Produces: `toml_pixel_block(pixel_text: str) -> str` in `animated.py`, next to
  `toml_multiline_basic_string`.
  - It returns `'"""\n' + escaped + '\n"""'`, where each row is escaped like
    `toml_multiline_basic_string` (`TOML_SHORT_ESCAPES`, control characters as `\uXXXX`).
  - The newlines between rows stay real. A trailing `'\n'` of the input is removed first.
  - The single-line prompt form uses `toml_basic_string`.

- [x] **Step 1: Write the failing tests.**
  - `test_backslash_glyph_round_trips`: palette glyph `'\\'`, rows `'a\\\nbbb'` → save,
    reload, and the rows are still `['a\\', 'bbb']`, not merged.
  - `test_quote_glyph_round_trips`: rows of `'"""'` survive a save and reload.
  - `test_toml_pixel_block_escapes`: `toml_pixel_block('a\\b\n"c') == '"""\na\\\\b\n\\"c\n"""'`.
  - `test_ai_rewrite_keeps_alpha`: `_construct_toml_with_preserved_formatting` on colors with
    `alpha = 128` writes `alpha = 128`.
  - `test_ai_rewrite_escapes_name_description_and_rows`: a description containing `"""` and
    `\`, and a row with `\`. The output parses with `tomllib` back to the same values.
  - `test_prompt_examples_are_valid_toml`: both example writers, given a `\` glyph, produce
    text that `tomllib.loads` parses to the same pixels.
  - `test_png_import_glyphs_need_no_escaping`: `'\\' not in SPRITE_GLYPHS and '"' not in SPRITE_GLYPHS`.

- [x] **Step 2: Run them and watch them fail.** Expected: the round trips fail
  (`'a\\bbb'`-style merge, or a TOMLDecodeError), and so does the alpha test.

- [x] **Step 3: Implement.** The AI rewrite uses `toml_pixel_block`, `toml_basic_string` and
  `toml_multiline_basic_string`, and writes `alpha` when present.
  - Ruling (from the spec's writer list): `ascii_renderer.py`'s output is a colorized terminal
    view with ANSI codes, not TOML anything reads back, so it isn't escaped. Ledger this.

- [x] **Step 4: Run** the four files. Expected: all pass.

- [x] **Step 5: Commit**: "Sprites: writers escape pixel rows; Bitmappy's AI rewrite keeps
  alpha and escapes text".

### Task 5: The AI path checks rows strictly

**Files:**
- Modify:
  - `src/glitchygames/ai/sprite_generator.py` (`validate_ai_response`, new `pixel_row_problems`)
  - `src/apps/bitmappy/src/bitmappy/ai_worker.py` (`build_retry_prompt`)
  - `src/apps/bitmappy/src/bitmappy/ai_manager.py` (the response handler, around lines
    493–557)
- Test:
  - `tests/ai/test_sprite_generator.py`
  - `src/apps/bitmappy/tests/test_bitmappy_ai_worker.py`
  - `src/apps/bitmappy/tests/test_bitmappy_ai_manager.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `PIXEL_ROWS_ERROR_PREFIX = 'Pixel rows need repair'`.
  - `pixel_row_problems(data: dict[str, Any]) -> str`. It returns `''`, or
    `f'{PIXEL_ROWS_ERROR_PREFIX}: ' + '; '.join(f'{label}: {repair}' ...)`, covering every block
    and the palette.
  - `validate_ai_response(content: str, *, check_pixel_rows: bool = True) -> tuple[bool, str]`.
    The row check runs last, on `tomllib.loads(content)`, and a parse error skips it.

- [x] **Step 1: Write the failing tests.**
  - `test_ragged_rows_fail_validation`: the error starts with `PIXEL_ROWS_ERROR_PREFIX` and
    names the frame.
  - `test_unparseable_response_skips_the_row_check`: a response with a TOML syntax error gives
    the same result as with `check_pixel_rows=False`.
  - `test_space_pyramid_passes`.
  - `test_retry_prompt_asks_for_equal_widths`: `build_retry_prompt('p', 'Pixel rows need repair: walk frame 0: row widths differ (3, 4); …')`
    contains `'every row of a frame must have the same number of characters'`, and no other
    correction text.
  - `test_bitmappy_retries_ragged_rows`: a ragged response with retries left queues a retry.
  - `test_bitmappy_loads_ragged_rows_after_last_retry`: with `retry_count == AI_VALIDATION_MAX_RETRIES`,
    `_load_ai_sprite` is called, and the sprite loads repaired.
  - `test_bitmappy_still_discards_other_failures`: a missing-`[colors]` response after the last
    retry is not loaded, as today.

- [x] **Step 2: Run them and watch them fail.**

- [x] **Step 3: Implement.**
  - `build_retry_prompt` gets a first branch for `PIXEL_ROWS_ERROR_PREFIX.lower()` with the text:
    `'CRITICAL: every row of a frame must have the same number of characters, one palette glyph per pixel. Count each row.'`
  - Bitmappy's `_validate_ai_content` calls `validate_ai_response(..., check_pixel_rows=False)`,
    so `_is_ai_error_message` never rejects for rows.
  - The handler then runs `pixel_row_problems` on the content Bitmappy loads:
    `parse_toml_robustly` and `normalize_toml_data` of the cleaned response.
  - It retries while retries remain. On the last attempt it calls `_load_ai_sprite`.

- [x] **Step 4: Run** the three files. Expected: all pass.

- [x] **Step 5: Commit**: "AI: ragged pixel rows fail validation; Bitmappy retries them, then
  loads repaired".

### Task 6: Bitmappy's repair notice

**Files:**
- Modify: `src/apps/bitmappy/src/bitmappy/animated_canvas.py` (`_load_file_into_canvas`).
- Test: `src/apps/bitmappy/tests/test_bitmappy_editor_scene.py`, or the canvas load tests that
  already exercise `_show_load_message`.

**Interfaces:**
- Consumes: `AnimatedSprite.pixel_row_repairs` (Task 2).
- Produces: after a load with repairs, `debug_text.text` ends with:
  `f'\nRepaired the pixel rows of {count} block(s) while loading (details in the log). Saving writes the repaired rows.'`.
  Here `count` is the number of distinct labels other than `'palette'`, and a palette problem
  counts as one.

- [x] **Step 1: Write the failing tests.**
  - `test_load_with_repairs_shows_the_notice`.
  - `test_clean_load_shows_no_notice`.
  - `test_ai_load_with_repairs_shows_the_notice`: it goes through `_load_ai_sprite`, and the
    notice is still there after `_update_ui_after_ai_load`.

- [x] **Step 2: Run them and watch them fail.**

- [x] **Step 3: Implement.** Append the notice after the success message is set. If the AI
  manager overwrites `debug_text`, add the notice there too, from the canvas sprite's
  `pixel_row_repairs`.

- [x] **Step 4: Run** `uv run pytest src/apps/bitmappy/tests -q`. Expected: all pass.

- [x] **Step 5: Commit**: "Bitmappy: say when a loaded file's pixel rows were repaired".

### Task 7: QuickLook follows the rule

**Files:**
- Modify:
  - `src/quicklook/Sources/SpriteCore/PixelRows.swift`
  - `SpriteLoader.swift`, both call sites
  - `ColorPalette.swift`, which drops a U+0000 key
- Fixtures:
  - Rewrite the header comments of `src/quicklook/tools/fixtures/ragged-animated.toml` and
    `ragged-static.toml` for the new rule.
  - Add `src/quicklook/tools/fixtures/rows-edge-cases.toml`, an animated file with one frame
    per case:
    - a long row and a short row;
    - a blank interior line;
    - shared and unshared indentation;
    - `\` and `"` glyphs, written escaped;
    - `e\u0301` (a combining mark);
    - `\u2764\ufe0f` (a VS16 emoji);
    - a palette key `"\u0000"`.
  - Add `rows-static-pyramid.toml`, a static space pyramid.
- Test: `src/quicklook/Tests/SpriteCoreTests/PixelRowsTests.swift`, rewritten; the goldens
  under `Golden/` are regenerated.

**Interfaces:**
- Produces: `static func rows(_ pixels: String) -> [[Unicode.Scalar]]`, the one function. It
  pads with `Unicode.Scalar(0)`. `staticSpriteRows`, `animatedFrameRows` and `mostCommon` are
  removed; `pythonStrip` is removed if unused.

- [x] **Step 1: Rewrite `PixelRowsTests.swift`** to mirror Task 1's rule tests: the same inputs
  and the same expected rows, written with `"\u{0}"`.

- [x] **Step 2: Watch them fail.** Run `swift test`. Expected: compile errors, then failures.

- [x] **Step 3: Implement `rows(_:)`** and switch both loader call sites to it.

- [x] **Step 4: Regenerate the goldens** with the README command, plus the two new fixtures. The
  slime-jump sprites are `/Users/terry/Dropbox/dev.glitchygames/glitchygames/slime-jump.toml`
  and `slime-jump-alpha.toml`. Then run `swift test`. Expected: all pass.
  - `git diff --stat src/quicklook/Tests/SpriteCoreTests/Golden` shows only the ragged and new
    fixtures changed. Any other golden that changed is a finding: stop.

- [x] **Step 5: Commit**: "QuickLook: one pixel-row rule, matching the engine".

### Task 8: Docs and tracking

**Files:**
- Modify:
  - `BUGS.md`: new entries, numbered after the current highest, for spec "Bugs found" 1, 2, 4,
    6 (resolved here) and 3 and 5 (open).
  - `plans/future-work.md`: the row-unification entry at line ~101 is resolved, pointing to
    the spec. Add an entry for `_normalize_escaped_newlines` and one for `scripts/foo.toml`.
  - `docs/specs/2026-10-29-sprite-quicklook-design.md`: R4 and R5 point to the new spec.
  - `docs/specs/2026-10-30-unified-pixel-rows-design.md`: Status set to BUILT.
  - `src/quicklook/README.md`: the fixture list.
  - `plans/future-features.md` #28: a note that the core check exists.
- Test: `nox -s lint` (mkdocs strict, yamllint) and `nox -s static-analysis`.

- [x] **Step 1: Make the edits.**
- [x] **Step 2: Run** `nox -s lint` and `nox -s static-analysis`, then the full suite
  `uv run pytest -n auto -q` and `swift test`. Expected: all green and no new warnings.
- [x] **Step 3: Commit**: "Docs: one rule for sprite pixel rows; bugs found on the way".
