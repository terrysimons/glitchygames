# One rule for sprite pixel rows — Design

- **Date:** 2026-10-30
- **Status:** DESIGN, approved (the owner, 2026-10-30: "Go for it"; the builder check's open
  questions were settled the same day, "You go ahead and patch it").
- **Branch:** `feat/unified-pixel-rows`, on its own (the owner, 2026-10-29). Replaces the row in
  `plans/future-work.md` that tracks the two rules.

## Intent

A sprite's `pixels = """…"""` block is text, one glyph per pixel and one line per row. Whatever
the text gets wrong (a short row, a stray space, a blank line), the engine has to turn it into a
rectangle. Today it does that two different ways, and both of them can change the art without
telling anyone:

- **Static sprites** (`AnimatedSprite._convert_static_sprite`, `src/glitchygames/sprites/animated.py`)
  strip the whole block, widen every row to the longest one, and fill with the most common glyph
  in the sprite. That glyph is usually a color, so a short row gets solid pixels the author never
  drew.
- **Animated frames** (`parse_toml_pixel_lines` and `_validate_toml_frame_dimensions`) strip every
  line, drop blank lines, take the most common row length as the width, **cut longer rows off**,
  and pad shorter ones with their own last glyph. Cutting deletes art: a sword drawn
  `x / xxxx / x / x` loads as four single `x` rows, and adding one more short row to `abcd / ab`
  cuts `cd` off the first row.

Bitmappy saves what it loaded, so whatever the repair did is written back into the file.

The goal is **one rule, used everywhere, that never removes a pixel the author wrote, and that
says so whenever it had to repair something.**

## Goals

1. One function decides the rows of every pixel block: static sprites and animation frames, in
   the engine, Bitmappy, the AI path, the repo's sprite checks and scripts, and the QuickLook
   preview (which copies the engine).
2. **Nothing is ever cut off.** A repair only adds transparent pixels.
3. **Repairs are reported.** One log line per repaired block; a strict mode raises instead; the
   repo's sprite checks run strict.
4. Bitmappy tells the person editing when a file it loaded had to be repaired, so that saving
   writes the repaired grid on purpose.
5. The AI path rejects a generated sprite whose rows needed repair, the same way it rejects
   other invalid responses.
6. Saving can't corrupt rows: glyphs that TOML treats specially are escaped.

## Non-goals

- Guessing where a short row's missing pixels belong (lining it up with its neighbors, or
  repeating a glyph). The adversarial review (below) measured this: it rescues some AI mistakes
  and invents pixels in others. The rule adds transparent pixels at the end of the row, nothing
  else.
- Changing any art in the repo. Measured on the branch base (1e42b124): of 98 sprite files and
  377 pixel blocks, the new rule draws exactly the same picture as today for all but the four
  hand-written ragged test fixtures under `src/quicklook/` (repo sprites already pass
  `check_rows_have_equal_lengths`).
- The Bitmappy `\n` corruption in `_normalize_escaped_newlines` (`toml_processing.py`): a `\`
  glyph followed by an `n` glyph becomes a line break. Its own later branch (see "Bugs found").
- The full sprite linter (`plans/future-features.md` #28). This branch provides its core check.

## Anti-goals

- Any repair that removes or recolors a pixel the author wrote.
- Any repair nobody hears about.
- QuickLook drawing something different from the game.

## The rule

Every pixel block, static or animated, goes through these steps. Lengths are counted in Unicode
code points (what Python's `str` counts; Swift's `unicodeScalars`), never in grapheme clusters.

1. **Split** the text on U+000A only.
2. **Trim the end of each line**: remove trailing U+0020 (space), U+0009 (tab) and U+000D
   (carriage return, so Windows line endings work).
3. **Drop blank lines at the top and bottom.** A blank line between rows stays.
4. **Remove shared indentation**: the longest run of leading spaces and tabs that every
   non-blank line starts with, character for character. Indentation that only some lines have
   stays, and draws as transparent pixels (a space is never a palette glyph today). This keeps
   indented TOML working without moving art, and keeps a pyramid that uses leading spaces as
   its transparent pixels a pyramid.
5. **Make it a rectangle**: the width is the longest row. Shorter rows are padded at the end with
   transparent pixels, and a blank line between rows becomes a row of transparent pixels.

Accepted costs (the owner agreed, 2026-10-30): one accidentally long row widens the whole frame
by a pixel; a short row in a solid tile shows a see-through notch instead of a guessed fill.
Both are reported, and neither destroys anything.

**Transparent padding** is the engine's transparency key, magenta (255, 0, 255), the color the
engine already draws for a glyph that has no palette entry. On save, the writer finds the
palette's magenta glyph, or adds one if there isn't one (checked on the branch base). *My call,*
revised while planning: an earlier draft preferred the palette's own transparent glyph, but
QuickLook reads the palette as an unordered dictionary, so it couldn't pick the same "first"
glyph. Magenta is one answer that both sides give. A padded pixel is U+0000 in the returned rows
(`PADDING_GLYPH`); a palette that defines U+0000 is reported as a bad palette key.

### What counts as a repair

Steps 2–4 tidy text; they never change the picture, so they are not reported. These change or
might change the picture, and are reported (and raise in strict mode):

- rows of different widths (step 5 padded something), naming each width found;
- a blank line between rows;
- a glyph that isn't in the palette (it draws transparent, which is probably not what the
  author meant; the report names the glyphs). *My call:* a space is the exception. It is the
  format's "no pixel here" glyph (step 4 relies on it), so it is never reported;
- for the width report, a row counts as short only if it is still shorter than the width when
  its trimmed trailing spaces and tabs are counted back in. *My call:* a pyramid padded with
  spaces on both sides is not reported, but a row that really is missing pixels is.
- a palette key that isn't exactly one code point (e.g. `"❤️"` is two: U+2764 and U+FE0F). It
  can never match a pixel, because pixels are single code points.

Animation frames of different sizes are logged at debug level only: they are legal.

### Strict mode

The function takes `strict: bool`. Strict raises one `ValueError` listing every repair in the
block. Loading a sprite is not strict (old and AI-made files must still open). Strict is used
by:

- `check_rows_have_equal_lengths` in `src/glitchygames/testing/sprite_files.py`, which the
  workspace sprite test runs on every repo sprite. *My call:* it keeps running on every pixel
  block, now through the shared function in strict mode, so it also catches blank interior
  lines, missing glyphs and bad palette keys. Renaming it is the builder's call.
- the AI path (Goal 5).

## Before and after: what each layer draws

The record for "what changed", so a later breakage can be traced to the rule. The two old
columns were drawn by the engine itself on the branch base (1e42b124), loading each case as a
static sprite and as a one-frame animation and reading the pixels back as glyphs. `·` is a
transparent pixel. Rows are separated by `/`. The new column is the rule above, and Task 2 of the
plan pins every row of it with a test (`test_before_and_after_table`).

| Case (pixel text) | Old static (`_convert_static_sprite`) | Old animated (`parse_toml_pixel_lines` + `_validate_toml_frame_dimensions`) | New (both) |
|---|---|---|---|
| sword `x / xxxx / x / x` | `xxxx / xxxx / xxxx / xxxx` (filled with the most common glyph) | `x / x / x / x` (crossguard cut) | `x··· / xxxx / x··· / x···` |
| one long row `abcd / ab / ab` | `abcd / abaa / abaa` | `ab / ab / ab` (`cd` cut) | `abcd / ab·· / ab··` |
| short row in a tile `xxxx / xxx / xxxx` | `xxxx / xxxx / xxxx` | `xxxx / xxxx / xxxx` | `xxxx / xxx· / xxxx` (notch, reported) |
| blank line between rows `ab /  / ab` | `ab / aa / ab` | `ab / ab` (row dropped) | `ab / ·· / ab` |
| one indented row `␣␣ab / ab / ab` | `ab / ab / ab` (whole-block strip) | `ab / ab / ab` (per-line strip) | `··ab / ab·· / ab··` (indent kept, reported) |
| space pyramid `␣␣x / ␣xxx / xxxxx` | `xxxxx / ·xxxx / xxxxx` | `x / x / x` | `··x·· / ·xxx· / xxxxx` |
| tie in widths `ab / abc` | `aba / abc` | `ab / ab` (tie goes to the first width) | `ab· / abc` |

Read across a row to see which layer changed and how. Two of the old static results surprised
the review: the whole-block strip also removes the *first row's* indentation, and filling with the
most common glyph turns a short sword into a solid block.

Other records of the old behavior: the QuickLook golden frames at 1e42b124
(`src/quicklook/Tests/SpriteCoreTests/Golden/ragged-*.json`, and the R4 and R5 rules in
`docs/specs/2026-10-29-sprite-quicklook-design.md`), and the old tests that the plan rewrites,
in git history. Each plan task is its own commit, so `git bisect` across the branch names the
task that broke something.

## Where it lives

- **Engine:** one public function in `src/glitchygames/sprites/pixel_utils.py`, taking the pixel
  text, the palette and `strict`, returning the rows, their width and height, and the list of
  repairs. *Builder's call* on names and the result type, following the module's style.
  `_convert_static_sprite` and `_create_toml_frame` both use it.
  `parse_toml_pixel_lines` and `_validate_toml_frame_dimensions` go away; their other callers
  (`sprite_files.py`, `scripts/audit_hitboxes.py`) switch to it. `colorize_pixels` in
  `src/glitchygames/tools/ascii_renderer.py` (a third copy: whole-block strip, no repair) uses it
  for its rows. *My call* on two more copies the builder check found:
  `BitmappySprite._parse_static_toml_data` (`src/glitchygames/sprites/bitmappy_sprite.py`, the
  fallback loader that `_inflate_toml` also uses: it strips each line, drops blank lines, and
  takes the width from the first row) draws in the game, so it uses the function too.
  `_extract_example_size` (`src/apps/bitmappy/src/bitmappy/ai_worker.py`) sizes the AI prompt's
  examples, so it uses it too. Out of scope: the legacy ConfigParser loader
  `scripts/sprite_loader.py`.
- **Reporting:** one `warning` per repaired block, naming the file, the animation and frame (or
  "sprite" for a static one) and each repair. The loaded sprite keeps the list of repairs so
  that Bitmappy (and tests) can read it. *Builder's call* on the attribute name.
- **Bitmappy:** after a load that had repairs, the load message (`_show_load_message` in
  `src/apps/bitmappy/src/bitmappy/animated_canvas.py`, the editor's debug text box) says how many
  blocks were repaired, that the log has the details, and that saving writes the repaired grid.
  *My call* on that wording and place; the owner can change it.
- **AI path:** a strict row check, worded so that `build_retry_prompt`
  (`src/apps/bitmappy/src/bitmappy/ai_worker.py`) can match it, plus a new correction text in
  `build_retry_prompt` telling the model every row must be the same width. There are two AI
  paths:
  - `SpriteGenerationService._validate_and_build_result` (no retries) calls
    `validate_ai_response` (`src/glitchygames/ai/sprite_generator.py`). That function gains the
    check on the cleaned response.
  - Bitmappy's `ai_manager.py` retries a failed check up to `AI_VALIDATION_MAX_RETRIES` (2)
    times. *My call:* there the check runs on the text Bitmappy actually loads, after its own
    clean-up (`normalize_toml_data`), so the rows checked are the rows drawn.

  When Bitmappy's retries run out and the last response still needed repair, it is loaded
  repaired, with the Bitmappy repair notice, instead of being discarded (the owner, 2026-10-30:
  "2. Yes" to my recommendation). Every other validation failure still
  ends with "the sprite was not loaded".

  *My call:* a response that doesn't parse as TOML skips the row check, so this check adds no
  new rejections. The existing checks and the loader handle it as they do today.
- **Writers:** every place that writes pixel rows into TOML escapes each row the way
  `toml_multiline_basic_string` does (`\`, `"` and control characters). Today a row ending in a
  `\` glyph joins the next row (TOML's line continuation), `a\bc` loads as a backspace, and
  `a\a` won't load. The writers are:
  - both writers in `animated.py` (the static writer and `_write_toml_animations`);
  - Bitmappy's AI rewrite (`ai_manager._construct_toml_with_preserved_formatting` and
    `_format_animation_sections`), which feeds the loader;
  - the prompt examples in `sprite_generator.py` (around lines 215 and 282);

  `ascii_renderer.py`'s output isn't on the list. It is a colorized terminal view with ANSI
  codes, and nothing reads it back as TOML (my call, while planning).

  The PNG import (`toml_processing.py`) can't produce either glyph (`SPRITE_GLYPHS`), so it gets
  a test that pins that rather than a change.
- **QuickLook:** `src/quicklook/Sources/SpriteCore/PixelRows.swift`'s two functions become one
  that follows the rule, used for static and animated blocks alike. QuickLook doesn't report or
  go strict: it draws what the game draws. Its golden frames are regenerated from the engine with
  `src/quicklook/tools/dump_engine_frames.py`, and new golden fixtures cover: a long row, a short
  row, a blank interior line, shared and unshared indentation, CRLF, a `\` and a `"` glyph, a
  combining mark, and a VS16 emoji (each code point its own pixel).

## Tests

TDD throughout. Every repair kind, and every step of the rule, gets an engine test, including
the two examples above (the sword keeps its crossguard; `abcd` keeps `cd`). Existing tests that
pin today's behavior (`tests/sprites/test_animated_sprite.py`, e.g.
`TestConvertStaticSpriteInconsistentWidths`, and the `Inconsistent line lengths` log test) are
rewritten for the new rule, not deleted. Round-trip tests save and reload sprites with `\` and
`"` glyphs. The Swift goldens prove engine and preview agree.

## Bugs found (to report in `BUGS.md`)

1. Writer doesn't escape pixel rows (fixed here, Goal 6).
2. `validate_ai_response` never checks row widths (fixed here, Goal 5).
3. `_normalize_escaped_newlines` turns a `\` glyph followed by an `n` glyph into a newline
   (`toml_processing.py`; used by Bitmappy's AI manager and alpha path). Separate branch.
4. `cobra.toml` (`src/games/brave-adventurer/src/brave_adventurer_papyrus/sprites/`) uses glyph
   `e` in 7 rows, but its palette has no `e`, so the cobra's second eye draws transparent. Strict
   mode fails on it. Fixed on this branch (the owner, 2026-10-30: "You go ahead and patch it").
   *My call:* `e` = (180, 30, 30). It follows the palette's own convention, where a lowercase
   glyph is a darker shade of its capital (`g` is `G` minus 20 per channel), so `e` is `E`
   (200, 50, 50) minus 20.
5. `scripts/foo.toml` has pixels and no palette at all; strict mode fails on it too. The owner
   decides whether it's kept.

6. Bitmappy's AI rewrite (`ai_manager._construct_toml_with_preserved_formatting`) writes each
   color's red, green and blue but drops `alpha`, so a generated sprite with see-through colors
   loads opaque. It also writes `name` and `description` unescaped (`description = """{…}"""`),
   so a prompt containing `\` or `"""` breaks the file. Found while planning; fixed on this
   branch with the writer escaping (fixups as we go), since it is the same function.

## Prior work

- The adversarial review (2026-10-30, three reviewers: AI failure modes, the format contract,
  and an adversary), verified by reproduction on the branch base. It measured the alternatives
  over 1,723 frames with injected AI errors, and argued the final shape of the rule above.
- `docs/specs/2026-10-29-sprite-quicklook-design.md` documents today's two rules (its R4 and
  R5); update it to point here.
