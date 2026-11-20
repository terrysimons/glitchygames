# Sprite color profiles, part 2: profiles, color spaces and the converter — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

- **Date:** 2026-11-20
- **Status:** APPROVED by the owner (2026-11-20). The master plan is approved (2026-11-17); the owner
  decided all seven open questions on 2026-11-20 (see "Decided by the owner (2026-11-20)" under
  "Open questions"). Nothing built yet. Audited 2026-11-20 against origin/main
  b7c2abd3 (after #235, #237, #238, #239): see "Audit 2026-11-20" at the end.
- **Dependency, in flight:** the bug that `AnimatedSprite` drops `profile` and `color_space`
  (item 1 below) is being fixed separately tonight on `fix/bug-sweep-2026-11-20`
  (`bugs/2026-11-20-animated-sprite-dropped-profile-and-color-space.md`; staged in
  `glitchygames-bug-sweep`, not committed when audited). **If it lands first, Task 3 shrinks**
  to the validation, the split, Bitmappy's warning and the docs; the sprite's two fields, the
  load, both document builders, the copy, `SHARED_SPRITE_FIELDS` and `CompiledSprite` are then
  done, with their regression tests. Task 3 below says which steps drop.
- **Master plan:** [plans/2026-11-17-sprite-color-profiles.md](2026-11-17-sprite-color-profiles.md),
  "Part 2: profiles, color spaces and the converter" (the part its "Answered after the builder
  check" item 1 narrowed to the pure-math spaces and the NES palette). Part 1:
  [sprites as text](2026-11-17-sprite-color-profiles-1-sprite-text.md), shipped in #220, its
  record kept by #234.
- **Branch:** a new branch from main, `feature/sprite-color-profiles-2-converter` (part 1's branch
  merged as #220, so nothing is stacked).

**Goal:** Profiles (how many colors one sprite may use) and color spaces (which colors exist) as
engine data; a sprite file's `profile` and `color_space` kept by the sprite; and a converter, sprite
file text in, converted sprite file text and a report out, exact and the same every time.

**Architecture:** Three pygame-free modules beside `sprite_toml.py`, so the AI service's package
can lift them as it lifts that one (`plans/2026-11-17-sprite-generation-in-the-ai-service.md`,
decision 8): `color_profiles.py` (the data), `color_math.py` (OKLab and its distance) and
`sprite_converter.py` (measure, snap, merge, rewrite, report), working on the parsed document
(`parse_sprite_toml`, `write_sprite_toml`), never on a sprite or a surface. The engine side is
small: `AnimatedSprite` keeps the two keys through load, save, copy, the shared compile and split.

**Tech Stack:** Python 3.15 (everything runs and tests on it; the code must still parse and
type-check as 3.14, the browser builds' Pyodide, so use only what 3.14 has), pydantic,
`configparser` for the palette file, pytest with pytest-mock.

## Global Constraints

- The three new modules import only the standard library and pydantic: no pygame, no
  `AnimatedSprite`, no `glitchygames.color` (that package imports pygame). A test proves it, as
  part 1's does for `sprite_toml.py`.
- The converter never reads a sprite object, a frame's `image` or `pixels`, or a surface: its input
  is text. (#226: engine code reads frames only through `read_only_image` and `read_only_pixels`;
  a converter on text has no reason to.)
- The converter runs in a tool's async step (part 3) and must never be what makes a frame late:
  a sprite of Dex's size converts in a measured time the builder records (the cost guard in the
  master's part 4 is built on that number). The time is measured with `measured_seconds()`, in a
  benchmark, never asserted in the normal suite.
- No new module-level mutable state: registries are `MappingProxyType` over frozen models, as
  part 1 did for its key tables (`tests/test_process_state_guard.py`).
- Keyword-only arguments for every new function; full names, no abbreviations; frozen pydantic
  models with `extra='forbid'`.
- Tests in pytest style, `mocker` never `unittest.mock`; real files in `tmp_path`; sprite-file
  checks are public `check_*` functions in `glitchygames.testing.sprite_files`, tests call them.
- Gates in order: `uv run ruff format`, `uv run ruff check`, `uv run basedpyright`,
  `uv run ty check`, then the tests. Engine change: every game's, the demos' and Bitmappy's sprite
  tests run with it (`uv run pytest --dummy-only src/games src/demos src/apps tests/sprites
  tests/test_workspace_sprite_files.py`).
- No file in the repository changes unless a task names it: no shipped sprite gains a `profile`
  or `color_space` key in this part (open question 3).

## What part 1 and the work since settled, and the master against today's code

Read 2026-11-20 on `origin/main` (4e6c7144; line numbers re-checked on b7c2abd3 in the audit). Where the master's text no longer fits, it is said
here with the evidence; the master is not edited beyond the link.

1. **The sprite does not keep `profile` or `color_space`.** Part 1 made the writer and the schema
   accept them (`sprite_toml.py:30-56`, `sprite_file_schema.py:99-102`), and the master says "the
   writer already carries them". Only `write_sprite_toml` does. `AnimatedSprite` reads neither key
   (`animated.py:1492`, `_load_text_uncached`, reads `name`, `description`, `tags`, `frame_anchor`) and
   writes neither (`animated.py:2070-2096`, `to_text` and `_static_document`, and
   `_build_toml_data_structure` at 2415, build the sprite section from the sprite's own fields), so a load and a save drops them. Reproduced: a text with
   `profile = "8-bit"` and `color_space = "NES palette"` loaded by `sprite_from_text` and written by
   `sprite_to_text` came back with neither key. Since Bitmappy saves through `to_text`, opening a
   converted sprite in Bitmappy and saving it would silently strip its profile. This part must
   fix that (Task 3); it is not optional. **A separate branch is fixing it tonight** (the
   Dependency line above); this part then only verifies it.
2. **The round-trip rule stays, and decides the output layout.** Part 1's rule (a single animation
   with one frame saves in the static layout, `to_text`) belongs to the sprite's writer. The
   converter works on the document and keeps the layout it was given: a static sprite comes out
   static, a one-frame animation stays one animation. #232 made zombies' `art.build` write
   one-frame rigs in the static layout, so those files are unchanged in shape. Loading the
   converted text and saving it again gives the same parsed sprite (Task 5's round-trip test).
3. **Budgets count used colors, not `[colors]` entries.** Part 1's owner decision ("keep the
   palette", Task 6) means a loaded sprite saves its unused and duplicate entries. Measured on
   120 shipped sprite files with a `[colors]` table: 25 declare entries no pixel uses, and 2
   (Bitmappy's `slime-jump.toml` and `slime_jump.toml`) hold two glyphs of one color. A profile
   budget that counted entries would refuse files whose pixels fit. The converter counts the
   distinct colors (with alpha) that pixels use, the glyph-free definition of the master's
   decision 1, and writes only those.
4. **The master's step 1 says "nearest in a perceptual color space" for every space.** For the
   bit-depth grids that is slower than it sounds and not what hardware did. See open question 5.
5. **The 9-bit space.** `plans/future-work.md` says the Genesis's levels were not evenly spaced and
   9-bit RGB should snap to a published, credited table; the master's "Answered after the builder
   check" lists 9-bit among the pure-math spaces. These conflict. See open question 6.
6. **The NES palette.** The master and `future-work.md` say "the NES's 54"; the file holds 55
   entries, all distinct, black included (`color/resources/nes.palette`, its header says
   `colors = 55`). Its description names the console but no source for the values; the owner's
   rule is that each palette's source is recorded and credited, so Task 1 records the source
   before the palette ships as a color space (the builder finds and checks it; nothing is invented).
7. **Stale evidence in the notes.** `future-work.md` and part 1's review focus say Bitmappy's
   `toadstool.toml` has 14 colors at alpha 137 or 128. Today `toadstool.toml` has no partial alpha
   (only the key, written `alpha = 255`). Partial alpha is in `slime-jump.toml` and
   `slime_jump.toml` (alpha 137), `save-sparkle.toml` (alpha 128) and `flame.toml` (one color at
   alpha 0). This plan uses those.
8. **`#226` (shared compiled frames).** Nothing in part 2 conflicts, with one addition: a compile
   copies the fields in `SHARED_SPRITE_FIELDS` (`compiled_sprites.py:48-64`), and its conservation
   test compares a cached load with the loader's own on each. The two new fields join that tuple
   and `CompiledSprite` (Task 3). A converted text compiles as any text, keyed by its hash
   (`sprite_key`, `compiled_sprites.py:72`), so the console's "latest result" reloads share.
9. **`#221` (`/sprite`).** It makes files through the AI service; those files carry no profile.
   Nothing here changes it. Once the converter exists, a generated sprite can be held to a profile
   by calling it: a later step, not this part.
10. **Left over from part 1 that this part decides.** The master's follow-up "split doesn't carry
   `profile` or `color_space`": it carries both (decision 9).
11. **The branch plan.** The master names `feature/sprite-color-profiles` stacked on the zombies
    PR; both merged (#220 and its base), so this part is branched from main.

## Review Focus

1. **Alpha** (`save-sparkle.toml`: the whole background and the sparkle at alpha 128;
   `flame.toml`: a black at alpha 0 that is not the magenta key; `slime-jump.toml`: alpha 137):
   the on/off rule, the key counted once, one transparent entry.
2. **The key is not a color.** Dex declares it as `"." = magenta`, Bitmappy's `toadstool.toml` as
   `"█"`; the converter finds it by color, never by glyph.
3. **Determinism across machines.** Floating-point distances must not change a merge from one
   platform to another (macOS, Linux, Windows and the Pi all run the suite): Task 2 and Task 5
   pin it.
4. **Hints that cannot be kept** are reported, never silently dropped.
5. **A conversion never makes a sprite worse than it said:** no more colors, same pixel grid,
   transparent pixels stay transparent.

## Decisions

The owner's decisions of the master (1 to 9) stand. These are the part's own, the designer's
unless marked; the owner's are in "Open questions".

1. **Profiles** (frozen `Profile`): `name` (the file's value), `label` (the notation),
   `colors_per_sprite` (None for no budget), `description`. The six, as `future-work.md` records
   them: `8-bit` (4), `16-bit` (16), `8-bit+` (64), `16-bit+` (256), `high-color` (32,768),
   `true-color` (None). The labels are `8-bit`, `16-bit`, `8-bit+`, `16-bit+`, `High Color`,
   `True Color`. Console names appear only in descriptions ("like the Genesis"), never as names.
2. **Color spaces** (frozen `ColorSpace`): `name`, `label`, `partial_alpha` (true only for
   `rgba32`), `description`, `source` (the credit; empty for pure math), and exactly one of two
   shapes. A **grid** has the allowed levels of each channel (N-bit RGB, web-safe); a **list** has
   explicit colors (the NES, the mono ramps). The ones this part ships are the master's answered
   set: `rgba32` (the default), `rgb24`, `rgb15`, `rgb12`, `rgb9`, `rgb6`, `web-safe`,
   `mono1`, `mono2`, `mono4` (even grays), and `nes`. Hardware palettes and tints stay a later
   part of the branch. Level math: a channel of k bits has 2^k levels, level i at
   round(i x 255 / (2^k - 1)); web-safe has the six levels 0, 51, 102, 153, 204, 255.
3. **The budget** of a conversion is the profile's `colors_per_sprite`, counting each distinct
   color with its alpha, the key included when the sprite uses transparency (master decision 1;
   a sprite with no transparency spends nothing on it, the master's design). The profile and the
   space are independent: `8-bit+ · mono2` is legal, and its effective budget is whatever the space
   leaves (4 grays and the key is 5, so one gray merges). Nothing special-cases the pairs the
   future-work notes call pointless.
4. **A color is measured by what pixels use** (`measure_sprite_colors`): each distinct
   (red, green, blue, alpha), its pixel count over every frame, whether the sprite uses
   transparency, and the glyphs pixels use that `[colors]` does not declare (the loader decodes
   them as the key; the converter reports them and leaves them in the rows).
5. **One transparent entry.** The key (255, 0, 255, opaque in the file, as part 1 writes it) and
   every color with alpha 0 are the same entry: invisible. In `rgba32` the entry keeps the form of
   its first member in file order (flame's black at alpha 0 stays as it is); in every other space
   the entry is the key. Reason: merging invisible colors costs no pixel, and flame would
   otherwise spend two entries on nothing.
6. **Alpha in on/off spaces.** Partial alpha below 128 becomes the transparent entry, 128 and
   above the color made opaque. 128 is `ALPHA_TRANSPARENCY_THRESHOLD`
   (`color/constants.py:23`), the engine's own "more transparent than not" (`ascii_renderer.py:150`,
   Bitmappy's import `file_io.py:309`), so the three agree. The master's wording "at or below half
   opacity" is the same cut at 8 bits, where half is 127.5. Visible consequence the owner should
   know: `save-sparkle.toml`'s teal background (alpha 128) becomes solid teal under any on/off
   space. That is the owner's rule 2 of 2026-11-16 applied honestly; dithering is not offered.
7. **The perceptual space is OKLab** (Bottosson, 2020, https://bottosson.github.io/posts/oklab/,
   credited in the module): a closed form of two matrices and a cube root, no illuminant tables, and
   distances that follow what the eye sees well enough for merging. CIELAB would need the D65
   constants and is no better here. Distance is Euclidean in OKLab (squared, as order is all the
   merge needs). The master left the choice to the builder.
8. **Merging** (master step 3): repeatedly merge the closest pair until the budget holds, where the
   merged-away color becomes the survivor's. The survivor is a color the hints protect, else the
   one with more pixels, else the one that sorts first by (red, green, blue, alpha). The survivor's
   own value is kept: a merge never averages, so the result stays inside the color space.
   Ties in distance are broken by the pair's color values, never by file order or glyph, so the
   result does not depend on how the file was written. A protected color is never the merged-away
   one; a pair of two protected colors is skipped. The key is never merged.
   *Alternative the builder may weigh:* weighting a merge by pixel counts (Ward's method) keeps
   big areas truer; the master says "closest pairs first" and the report is simplest with that, so
   it is the rule unless the builder's measurements on Dex say otherwise.
9. **The sprite keeps the two keys.** `AnimatedSprite` gains `profile` and `color_space`
   (`str | None`, None when the file has none, so a file with neither key still saves with neither,
   as the round-trip rule needs). They are read in `load_text`, written by both document builders,
   copied by `copy_sprite_metadata_from` (`animated.py:1120`), and in `SHARED_SPRITE_FIELDS` and
   `CompiledSprite`. `split_sprite_text` carries both into each frame: a frame is a still of the
   same sprite, its colors are a subset of the source's, so it conforms wherever the source did
   (an invariant, Task 3).
10. **Values are checked at load** against the registries: an unknown `profile` or `color_space`
    is a `SpriteFileError` naming the value and the valid ones (open question 1 holds the
    alternative). The schema stays pygame-free by importing `color_profiles.py`, which the package
    lift takes along.
11. **Hints** are `#rrggbb` or `#rrggbbaa` (case-insensitive; no alpha means opaque), the colors
    as the file has them before snapping. They are protected in the order given. Not in the sprite,
    malformed, the key itself, snapped onto another hint's color, or more than the budget leaves:
    each is reported with its reason, the conversion goes on, and the first hints that fit are
    kept (the master's rule).
12. **The result** is the input document with only these changes: `[colors]` rewritten to the
    colors pixels use, in the input's order, each with its glyph (a merge keeps the survivor's
    glyph); merged glyphs replaced in every pixel block; `profile` and `color_space` written
    explicitly into `[sprite]` (explicit is better, even for `true-color` and `rgba32`). Nothing
    else: names, sizes, frames, animations, intervals, hitboxes, tags, transitions and a game's
    own tables are as given. A snap-only conversion leaves every pixel block byte for byte as it
    was.
13. **Game tables are carried, and the report says so.** Drawing Fire's `soldier.toml` keeps a
    `[swatches]` table naming glyphs and matched by exact RGB. The converter leaves such tables
    untouched (part 1's ruling) and adds a report note naming each such table when a glyph or a
    color it could mean changed. A sprite meant for swatches is converted with that in mind, or
    not at all; the converter cannot know a game's table.
14. **Errors.** Text that is not a sprite file raises as the loader does (`ValueError` from
    `parse_sprite_toml`, `SpriteFileError` from the schema), naming `source_name`. Everything about
    colors (hints, merges, alpha) is reported, never raised: a tool round (part 3) gets a result
    either way.
15. **Same code path.** `check_*` functions and the converter use `measure_sprite_colors`; the
    conformance check is the converter's "is a conversion needed" test, not a second counter
    (the owner's rule against mirrored copies).

## Relation to swatches (`plans/future-features.md` #61)

Swatches recolor a sprite by palette swap at draw time: its `recolor_surface` maps exact RGBs on
surfaces and a `shade_map` scales shades per channel, so a swapped color generally leaves any
color space. Profiles convert a sprite's palette once, in text. They are two uses of one fact the
indexed format makes cheap, that a sprite is pixels plus a color map. This part keeps them
separate and does not block either way:

- Nothing here touches a surface, so #61's move of `swatches.py` into the engine is independent.
- The converter's core step is a function from color to color applied to a color map and the rows
  of merged glyphs. When #61 lands, a scheme can be seen as the same step with a different mapping;
  the builder keeps that function (`remap`) a public, tested, pure function so #61 can share it
  rather than copy it. Nothing more is promised.
- The interaction to remember: a swatched sprite recolored into a profile's colors leaves the
  profile (a scaled shade is not an NES color); re-snapping a recolored frame is #61's follow-up,
  recorded there, not built here. Decision 13 is this part's side of it.
- The palette features the master leaves out (swaps, cycling, fades) are #61 and the backlog.

## Open questions (the owner's)

### Decided by the owner (2026-11-20)

These answers win over the question text below wherever they differ.

1. **Checked at load:** (a) an unknown `profile` or `color_space` id is refused, naming the valid
   ids; (b) a file holding more than its profile allows loads, and the converter, the
   conformance check and Bitmappy's save warning report it. Refusing (b) at load waits for
   Bitmappy to enforce the profile while painting.
2. **The file holds short ids** (`profile = "8-bit+"`, `color_space = "rgb9"`), and the ids are
   the keys of the profile and color-space registry. Each registry entry carries its
   human-readable label, derived from the id ("8-bit+ · 9-bit RGB" on screen and in the docs);
   no label is ever stored in a file, so rewording one changes no file.
3. **No labels on shipped sprites in this part.** `art.build` labels the Zombies sprites in the
   step that holds the game to its profile.
4. **Bitmappy: a warning only.** It keeps both keys through save and logs when a save no longer
   conforms. A palette-limited canvas is a later part.
5. **Snapping:** grid spaces (`rgb24`, `rgb15`, `rgb12`, `rgb9`, `rgb6`, `web-safe`) snap each
   channel to its nearest level, ties up; the perceptual (OKLab) search is only for list
   palettes (`nes`, the mono ramps).
6. **One `rgb9`, the even grid** (0, 36, 73, 109, 146, 182, 219, 255), shipped in this part.
   There is no `rgb9-measured`: a space's levels never change once files conform to them. A
   console's authentic colors are a hardware palette named for the console (for example
   `mega-drive`), a measured list from a credited source beside `nes`. The rule: grid spaces are
   pure math, snapped per channel; hardware palettes are measured lists, searched perceptually.
7. **Yes, the `convert-sprite` tool** (Task 7).

### The questions as asked

Each has a concrete case, a recommendation and the alternative. Tasks 1, 3 and 7 are written to the
recommendation; a different answer changes the named task only.

1. **Does a file's `profile` get checked when the sprite loads?** Two parts. (a) A value the
   engine does not know (`profile = "8-bit-plus"`, a typo for `"8-bit+"`; or a name a newer engine
   added): *Recommend refuse*, naming the valid values, like every other misspelling in the strict
   schema (rule 3 of `sprite_file_schema.py`). The cost: an older engine refuses a newer file's
   new palette name even though it could draw it. *Alternative:* load, keep the string and log a
   warning. (b) A file that declares more than it holds: Dex declares `profile = "8-bit"` and
   uses 16 colors. *Recommend do not refuse:* the load records the label; the converter, the
   `check_conforms_to_declared_profile` test function and Bitmappy's save-time warning (question 4)
   report it. Reason: Bitmappy cannot yet stop an artist painting a fifth color, so refusing at
   load would let Bitmappy save a file the game then cannot load. *Alternative:* refuse (the owner
   called profiles "strict"), which is right once Bitmappy enforces the profile while painting.
2. **The file's values.** *Recommend* the ids `future-work.md` already shows, plain ASCII with no
   spaces: `profile = "8-bit+"`, `color_space = "rgb9"` (also `rgba32`, `rgb24`, `rgb15`, `rgb12`,
   `rgb6`, `web-safe`, `mono1`, `mono2`, `mono4`, `nes`; profiles `8-bit`, `16-bit`, `16-bit+`,
   `high-color`, `true-color`). *Alternative:* the labels people read (`"8-bit+ · 9-bit RGB"`),
   which put spaces and a middle dot in a file and make the notation the format.
3. **Do shipped sprites get labels now?** All 24 of Zombies' sprites fit 16-bit (the most colors
   any uses is 16, key included; Dex uses 15 and the key) and the `future-work.md` table calls
   that "every Zombies sprite today". *Recommend no labels in this part:* the files are written by
   `art.build` ("edit the rig and rebuild, never this file"), so labeling means changing the
   builder and regenerating 24 files, to be done in the step that holds the game to its profile
   with the check. *Alternative:* have `art.build` write `profile = "16-bit"` now, which makes the
   conformance check real on shipped art immediately, at the cost of that regeneration inside a
   part about the converter.
4. **What Bitmappy shows.** *Recommend nothing new on screen in this part:* Bitmappy keeps the two
   keys through save (Task 3's fix of item 1 above) and logs a warning when a save no longer
   conforms (open it, paint a fifth color in a converted `8-bit · nes` Dex, save: the file says
   `8-bit` and holds five). *Alternative:* show the profile in the title or status line and refuse
   painting outside it; that is an editor feature (a palette-limited canvas) with its own design,
   the natural next part after the AI tools.
5. **Snapping to a grid space** (a change to the master's step 1 wording). For `rgb9`, `rgb12`,
   `rgb15`, `rgb24`, `rgb6` and `web-safe` the master snaps to "the nearest color in a perceptual
   space". Searching all 512 to 32,768 colors for each of up to 64 colors is roughly two million
   OKLab evaluations in Python for `rgb15`, an estimate, not measured, but plainly slow in pure Python,
   and a console did not search: its
   hardware dropped low bits of each channel. *Recommend:* per channel to the nearest level,
   ties up (exact, instant, what hardware did); the perceptual search only for list spaces (the
   NES's 55, the mono ramps), where the perceptual distance is what chooses between very
   different colors. Worked case: Dex's skin `"a" = (252, 212, 172)` in `rgb9` goes to the nearest
   of 8 levels per channel directly. *Alternative:* the master as written, perceptual everywhere,
   deterministic but slow and with no hardware precedent.
6. **9-bit levels.** *Recommend:* ship `rgb9` with even levels (0, 36, 73, 109, 146, 182, 219, 255),
   its description saying so, as the master's pure-math list says, and add the Genesis's measured
   table later as its own named space (`rgb9-measured`, from a credited source) when a source is
   checked, like the other hardware palettes. *Alternative:* hold `rgb9` out of this part until the
   measured table is sourced, as `future-work.md` says. The difference is at most a few levels per
   channel, and an even grid is what a color space called "9-bit RGB" most plainly means.
7. **A tool for it in this part?** *Recommend yes, small and last (Task 7):* `glitchygames
   convert-sprite FILE --target-profile 8-bit --target-color-space nes [--keep-color '#e23e3e']`
   in the tools registry (option names chosen by the audit: `--profile` is already the engine's
   profiler flag, `-p`, `events/game.py:298`, and every tool option is also a flag on every
   game, so `--profile` would clash) (`replay/tools/registry.py`, each tool described once), writing text to stdout and
   the report to stderr. It lets the owner see Dex in the NES palette, open the result in Bitmappy
   and judge the merge rule before the AI is involved, and it gives part 4's `convert_sprite` a
   proven entry point. *Alternative:* no tool until part 4, one fewer registry entry, documented
   page and test to carry, but the converter is then first seen through the model.

## Approaches

- **Where the converter works:** on the document (chosen: text in, text out, layout and every
  untouched key exactly as given, no surfaces, pygame-free, liftable) or on a loaded sprite and
  `to_text` (rejected: it would pass through a loader that drops the keys and re-lays-out the file,
  and needs pygame).
- **What a merge keeps:** the survivor's color (chosen: stays inside the space, report is "a into
  b") or the pixel-weighted mean (rejected: leaves the space, then needs a second snap).
- **What a snap-then-merge order does:** snap first (the master's order), so colors that collapse
  into one space color cost nothing.

## File structure

| File | New or changed | Holds |
|---|---|---|
| `src/glitchygames/sprites/color_profiles.py` | new | `Profile`, `ColorSpace`, the registries, lookups, the NES list |
| `src/glitchygames/sprites/color_math.py` | new | sRGB to OKLab, squared distance, fixed-point rounding |
| `src/glitchygames/sprites/sprite_converter.py` | new | `measure_sprite_colors`, `convert_sprite_text`, report models, `remap`, `profile_problems` |
| `src/glitchygames/color/resources/nes.palette` | changed | the source of its values recorded |
| `src/glitchygames/sprites/sprite_file_schema.py` | changed | `profile` and `color_space` values checked (`:99-102`) |
| `src/glitchygames/sprites/animated.py` | changed | the two fields: load, both document builders, copy |
| `src/glitchygames/sprites/compiled_sprites.py` | changed | the two fields in `SHARED_SPRITE_FIELDS` and `CompiledSprite` |
| `src/glitchygames/sprites/sprite_toml.py` | changed | `split_sprite_text` carries both keys |
| `src/glitchygames/testing/sprite_files.py` | changed | `check_conforms_to_declared_profile`, `check_conversion_invariants` |
| `src/apps/bitmappy/src/bitmappy/` (the save path) | changed | warning at a non-conforming save |
| `src/glitchygames/replay/tools/registry.py` | changed (Task 7) | `convert-sprite` |
| `ANIMATION_README.md`, `docs/glitchygames/sprites/index.md`, `CLAUDE.md` (the sprite-file line) | changed | the keys, the converter |
| tests | new and changed | `tests/sprites/test_color_profiles.py`, `test_color_math.py`, `test_sprite_converter.py` (each a new subject); `test_animated_sprite.py`, `test_sprite_toml.py`, `test_workspace_sprite_files.py` (existing) |

---

### Task 1: profiles and color spaces as data

**Files:** create `color_profiles.py`; change `nes.palette` (source recorded);
test `tests/sprites/test_color_profiles.py`.

**Interfaces:**
- `Profile`, `ColorSpace` (frozen pydantic, `extra='forbid'`; a validator holds that a color
  space is exactly a grid or a list); `PROFILES` and `COLOR_SPACES` (`MappingProxyType`, in the
  order of decision 1 and 2); `profile_named(*, name)` and `color_space_named(*, name)` raising
  `UnknownProfileError` and `UnknownColorSpaceError` (both `ValueError`, naming the valid
  names); `DEFAULT_PROFILE_NAME = 'true-color'`, `DEFAULT_COLOR_SPACE_NAME = 'rgba32'`;
  `effective_profile(*, name)` and `effective_color_space(*, name)` (None reads as the default, as
  every file does today); `color_space_members(*, color_space)` (the colors of a list, or the grid's
  size) for the checks.
- The NES list is read from `color/resources/nes.palette` with `configparser` alone (that file's
  format is documented in `color/resources/README.md`; `glitchygames.color.palette` imports pygame,
  so it is not used here). The read happens once, at first use, held in the registry's immutable
  value, not at import. A lazy read held at module level is process state: either give it an audit
  row in `tests/test_process_state_guard.py` (immutable, same value every run, the guard's own
  allowlist form, which also names `functools.cache`) or read per call; the builder picks, and a
  test names which. The palette file must ship as package data (it does for Bitmappy's palette
  loader; check the wheel's and the browser bundle's file lists contain `nes.palette`).

**Behaviours (tests):**
- Every profile and space in the registries has a description; every non-math space has a
  non-empty `source`; names are unique and ASCII without spaces.
- The budgets are exactly 4, 16, 64, 256, 32,768 and None, in that order of increasing size.
- Grid levels: for every k in {1..8}, a k-bit channel has 2^k levels, strictly increasing, from
  0 to 255 inclusive; `rgb9` has 512 members, `rgb15` 32,768, `web-safe` 216.
- The mono ramps have 2, 4 and 16 distinct grays, from black to white, evenly spaced.
- The NES list equals the palette file's entries in file order (55, all distinct), and is not
  hand-copied into code.
- A color space cannot be built with both or neither shape; both models refuse unknown fields.
- `profile_named` and `color_space_named` refuse an unknown name with the valid ones in the
  message; `None` through `effective_*` gives `true-color` and `rgba32`.
- The module imports only the standard library and pydantic; the NES read works from an
  installed (non-editable) copy.

- [ ] Write the failing tests; verify they fail.
- [ ] Implement; run the gates in order.
- [ ] **Do this first, before the tests:** find and record the NES palette's source in the palette file's description and
      `color/resources/README.md` (the builder reports what it checked; if no source can be
      confirmed, the plan stops here and asks the owner, never shipping an uncredited palette).
- [ ] Commit.

### Task 2: color math

**Files:** create `color_math.py`; test `tests/sprites/test_color_math.py` (new subject).

**Interfaces:** `to_oklab(*, red, green, blue) -> tuple[float, float, float]` (sRGB 0 to 255 in,
the inverse transfer function, Bottosson's matrices); `squared_distance(*, first, second) -> int`
(Euclidean in OKLab, rounded to an integer in millionths, so equal-looking distances compare equal
across platforms).

**Behaviours (tests):**
- Reference points from the source: white is (1, 0, 0) and black (0, 0, 0) within 1e-6; the
  published test values for pure red, green and blue within the published precision.
- Distance is symmetric, zero exactly for equal colors, and satisfies the triangle inequality on a
  sampled grid of colors (an invariant over many triples, seeded through `random_stream` or a fixed
  list, not wall time).
- Lightness is monotonic along the gray ramp, so the mono snap (a nearest search) picks by
  lightness: a property over the ramp.
- The same call twice gives the same integer; the module imports only `math`.
- A golden table of ten colors and their integer distances is stored in the test; it fails on a
  platform whose libm moves a digit, which is the cross-platform pin of Review Focus 3. (Run by the
  macOS, Linux and Windows CI jobs; local macOS and the Pi are the builder's check. What this does
  not prove: platforms nobody runs.)

- [ ] Tests first, then implement, gates, commit.

### Task 3: the sprite keeps `profile` and `color_space`

**Files:** `sprite_file_schema.py`, `sprite_toml.py` (`split_sprite_text`: its `_frame_text` copies
only `description`, `tags` and `frame_anchor`, `sprite_toml.py` ~490), Bitmappy's save path
(`animated_canvas.py:1296` through `sprite_serializer.save`, and `:1763`), `ANIMATION_README.md`;
`animated.py` and `compiled_sprites.py` **only if the bug-sweep fix has not landed**; tests in
`tests/sprites/test_animated_sprite.py`, `test_sprite_toml.py`, `test_sprite_file_schema.py`,
the existing workspace test.

**Interfaces:** `AnimatedSprite.profile` and `AnimatedSprite.color_space` (`str | None`); both in
`SHARED_SPRITE_FIELDS` and `CompiledSprite`; the schema's `Sprite.profile` and `Sprite.color_space`
validated through Task 1's lookups.

**Behaviours (tests):**
- **Regression, shown failing first on today's code:** text with `profile` and `color_space`
  loaded by `sprite_from_text` and written by `sprite_to_text` has both keys with the same values
  (today it has neither: the gap that let this exist is that part 1's round-trip checks use shipped
  files, and no shipped file has either key).
- A file with neither key saves with neither (the keys are never added by a save), for every
  shipped sprite file: the existing `check_save_keeps_the_parsed_document` on the shared list
  already pins this once the fields exist; the test asserts the list is non-empty.
- A file with only one key keeps only that one.
- The key's value survives the copy of a sprite and a shared-compile load (the conservation test
  over `SHARED_SPRITE_FIELDS` covers the new names; a cached load and the loader's own agree).
- Static layout and animated layout both write the keys in `[sprite]`; a single-frame animation
  still saves static, with the keys.
- An unknown `profile` or `color_space` value is refused at load naming the file, the field and
  the valid values; a value of the wrong type is refused as today.
- `split_sprite_text` carries both keys into every frame, and a frame's colors, measured by Task
  4's `measure_sprite_colors`, never exceed the source's budget or leave its space when the source
  conformed (an invariant over a converted fixture).
- Bitmappy: opening a text with the keys and saving keeps them; a save of a sprite whose colors no
  longer conform logs one warning naming the profile and the count; a conforming one logs none.
- The master's "left over" item (split) is recorded as closed.

- [ ] If the bug-sweep fix is in the base: skip the sprite-field steps; confirm its
      `TestColorProfileKeysRoundTrip` and the `SHARED_SPRITE_FIELDS` conservation entries exist
      and pass, and say in the commit that the fields came from that fix. Otherwise:
- [ ] Write the failing regression test against current code first; show it red.
- [ ] Implement; run every game's, demo's and Bitmappy's sprite tests; gates; commit.

### Task 4: measuring a sprite's colors

**Files:** create `sprite_converter.py` (its first half); test
`tests/sprites/test_sprite_converter.py`.

**Interfaces:** `measure_sprite_colors(*, text, source_name) -> SpriteColors` (frozen model:
the distinct colors pixels use in first-seen order, each as (red, green, blue, alpha) with its pixel
count, `uses_transparency`, `undeclared_glyphs`); `format_color(*, color)` and
`parse_color(*, text)` for the `#rrggbb[aa]` notation.

**Behaviours (tests):**
- Counts add up: the pixel counts of a sprite's colors sum to its frames' total pixels (frames x
  width x height), minus none (conservation), for every shipped sprite file.
- Unused `[colors]` entries are not counted; two glyphs of one color are one color
  (`slime-jump.toml`'s pair); an alpha-0 color and the key are one transparent entry (decision 5,
  `flame.toml`).
- A sprite with no transparent pixel reports `uses_transparency` false and the key is not counted.
- The result is independent of glyph naming and `[colors]` order (rename every glyph, permute the
  table: the same colors and counts).
- Static and animated layouts measure the same sprite the same.
- A glyph pixels use but `[colors]` does not declare is listed, not an error.
- `parse_color` and `format_color` round-trip for every 8-bit value and refuse non-hex, wrong
  length and out-of-range text with a `ValueError`.
- Dex: 16 colors (15 and the key), and `parse` -> `format` of each equals the file's.

- [ ] Tests, implement, gates, commit.

### Task 5: the converter

**Files:** `sprite_converter.py` (the second half); same test file, plus a golden fixture
`tests/fixtures/sprite_conversions/` (Dex at `8-bit` · `nes` and one other, recorded
deliberately, the project's rule on goldens).

**Interfaces:**
- `convert_sprite_text(*, text, source_name, profile, color_space, keep_colors=()) ->
  SpriteConversion` with `profile: Profile`, `color_space: ColorSpace`,
  `keep_colors: Sequence[str]`.
- `SpriteConversion` (frozen: `text`, `report`); `ConversionReport` (frozen: the profile and
  space names, color counts before and after, `snapped`, `merged`, `alpha_changes`, `kept_hints`,
  `hint_problems`, `game_tables_note`); `ColorChange` (`from_color`, `to_color`, `pixel_count`,
  as `#rrggbb[aa]` text, the form the model reads and hints use); `HintProblem` (`hint`, `reason`
  a `StrEnum`: `NOT_IN_SPRITE`, `MALFORMED`, `IS_THE_KEY`, `SNAPPED_TOGETHER`, `OVER_BUDGET`).
- `remap(*, color_map, mapping)`: the pure color-to-color step, public and tested alone (the
  swatches relation).
- `profile_problems(*, text, source_name, profile, color_space) -> tuple[str, ...]`: what the
  text holds that its profile and space do not allow, empty when it conforms; the conversion's
  "is a change needed", and the test function's check.

**Behaviours (tests), invariants first:**
- **Budget:** for every shipped sprite file and every profile and color space combination, the
  converted text's distinct colors (alpha included, key when used) never exceed the profile's
  budget.
- **Membership:** every non-transparent color of the output is in the color space; in every space
  but `rgba32` every pixel is opaque or the transparent entry.
- **Conformance is a fixed point:** converting a converted text with the same arguments gives the
  same text and an empty report (idempotent), and `profile_problems` of the output is empty.
- **Deterministic and order-free:** two runs give the same text; renaming every glyph and permuting
  `[colors]` before conversion gives the same decoded pixels (compared as colors per position).
- **Never more colors than the input; a sprite within budget keeps every color:** a sprite already
  within the budget and in the space comes out with identical decoded pixels and identical rows;
  one within the budget but off the space has only its colors snapped, so each distinct input color
  maps to exactly one output color and no new color appears.
- **The grid is untouched:** the converted text, parsed, equals the input with only `[colors]`,
  the merged glyphs in pixel blocks, and the two profile keys different; sizes, frame counts,
  animation names, intervals, loops, hitboxes, tags, transitions and game tables are equal. A
  snap-only conversion leaves every pixel block byte-identical.
- **Transparency:** the pixels that were transparent are exactly those that are transparent after;
  an opaque pixel never becomes transparent, except through the on/off rule, tested at alpha 127,
  128 and 255 (`save-sparkle.toml`'s 128 becomes opaque, flame's alpha 0 becomes the key in
  `rgb24`, stays as written in `rgba32`).
- **The key is not a color:** never snapped (a key stays magenta in `nes`, which has no magenta),
  never merged, counted once; a sprite with none spends no entry (8-bit on a keyless two-color
  sprite keeps up to 4 colors, not 3).
- **Hints:** a protected color is never the merged-away one while the hints fit; two hints that
  cannot both be kept give the first kept and the second reported `OVER_BUDGET` or
  `SNAPPED_TOGETHER`; a hint naming a color the sprite lacks is `NOT_IN_SPRITE` and the
  conversion still completes; hint order changes the result only as the rule says (earlier wins).
  Worked case: a zombie's red eyes `#e23e3e` beside green skin in `8-bit`: with the hint the red
  survives and a green merges, without it the merge is by closeness.
- **Merge rule:** a hand-built sprite whose closest pair, survivor and tie are known by hand
  merges as the rule says; a distance tie is broken by color values, not by glyph.
- **Round trip:** the output loads (`sprite_from_text`), passes `check_values_match_the_schema`
  and `check_text_and_file_loads_agree`, and loads then saves to the same parsed sprite,
  keys included (Task 3).
- **Layouts:** a static sprite converts static; a one-frame animation stays an animation; Dex (32
  animations, 94 frames) converts with every frame's glyph grid the same size.
- **Errors:** invalid TOML raises naming `source_name`; a bad schema value raises `SpriteFileError`;
  neither hint problems nor alpha ever raise.
- **Report accuracy:** replaying the report's `snapped` and `merged` against the input colors gives
  exactly the output colors (the report is a complete account, checked by an independent replay).
- **Golden:** Dex at `8-bit · nes` and at `16-bit · rgb12` equals the stored fixtures on every
  CI platform (the cross-platform pin of Review Focus 3). The recorded real report for Dex goes in
  this plan's execution record, with the converter's measured time.
- **Game tables:** a document with a `[swatches]` table converts with the table unchanged and the
  report note naming it when a glyph it lists was merged.
- Imports only the standard library, pydantic and the sibling pygame-free modules.

- [ ] Land it as two commits so each is green and reviewable. **5a:** measure-based budget
      check, snap, alpha, rewrite, keys, `remap`, `profile_problems`, a conversion that needs no
      merge (the fixed-point, membership, transparency, key, grid-untouched, layouts, round-trip
      and error behaviours). **5b:** the merge rule, hints, the report and its replay check, the
      golden fixtures and the game-tables note. Tests first for each; show red; gates; commit.
- [ ] Record the golden fixtures deliberately; commit them with their provenance line.

### Task 6: conformance checks and the workspace sweep

**Files:** `src/glitchygames/testing/sprite_files.py`, `tests/test_workspace_sprite_files.py`,
`tests/workspace_sprite_files.py` (the shared list).

**Interfaces:** `check_conforms_to_declared_profile(*, sprite_file)` (passes a file with no keys;
fails a file whose colors exceed its profile or leave its space, naming how);
`check_conversion_invariants(*, sprite_file)` (Task 5's invariants for one file over a fixed small
matrix of profiles and spaces, so the whole repository is swept without 120 x 66 conversions
if the builder's measurement says that is too slow; the full matrix runs in Task 5 on a handful
of representative sprites).

**Behaviours (tests):**
- Every shipped sprite file passes `check_conforms_to_declared_profile` (none declares one, so
  trivially today; the test asserts the list is non-empty so it cannot pass on nothing) and
  `check_conversion_invariants`.
- A planted defect fails each check: a fixture declaring `8-bit` with 5 colors; a fixture declaring
  `nes` with a non-NES color (the gate is proven to be able to fail).
- A converted shipped sprite (Dex, `8-bit · nes`) passes `check_conforms_to_declared_profile`.

- [ ] Tests, implement, gates, commit.

### Task 7: the `convert-sprite` tool (agreed by the owner, 2026-11-20: open question 7)

**Files:** `replay/tools/registry.py` (one `TOOLS` entry; the tool is also a flag/subcommand under
the registry's one-description rule), its docs page, the registry-driven tests.

**Behaviours (tests):** `glitchygames convert-sprite FILE --target-profile P --target-color-space S`
writes the converted text to stdout and the report to stderr; `--keep-color` is repeatable; no
option name equals an existing game argument (`--profile` is taken: the registry's clash check
and a test over the generated game parser); an unknown profile or
space exits with the project's usage exit code naming the valid names (`ExitCode`, never a
number); a missing file or invalid TOML exits with the data-error code; nothing is written to the
source file, and the output loads. The tool's options clash with no game argument (the engine's
existing check).

- [ ] Tests, implement, gates, commit.

### Task 8: docs and bookkeeping

- [ ] `ANIMATION_README.md`: the two keys, the ids, what each means, the notation, that a file
      without them reads as `true-color · rgba32`.
- [ ] `docs/glitchygames/sprites/index.md`: the new modules (hand-written page; CLAUDE.md names
      engine API pages as hand-written), the abbreviation glossary if a new term needs one.
- [ ] `CLAUDE.md`: the sprite-file line names `profile` and `color_space` and the converter's
      module; grep every `.md` for stale statements ("the writer already carries them" in the
      master and `future-work.md`; the toadstool evidence in `future-work.md` and part 1's review
      focus is left as history, with a note in the master's Follow-ups).
- [ ] `plans/future-work.md` entry and the master: part 2 done; part 3's text keeps its
      `convert_sprite` row, now with the real function name. The project's FEATURE.md and TODO.md
      (or equivalents) updated.
- [ ] Whole gate session once more after the last edit (`uv run nox -s lint`,
      `uv run nox -s static-analysis`, `uv run nox -s test`), nothing committing during it.

## Done when

- Every task's tests pass; the gates pass in order; the whole suite passes on 3.15 (nothing tests on 3.14; the new code parses and type-checks as 3.14).
- A sprite's `profile` and `color_space` survive load, save, copy, compile, split and Bitmappy's
  save (the regression of item 1 is green and was seen red).
- The converter's invariants hold for every shipped sprite file; the golden conversions hold on
  every CI platform.
- The three new modules import no pygame (tests, in a subprocess that checks `sys.modules`).
- The part-3 and part-4 authors have: `convert_sprite_text`'s signature, the report's fields as the
  text the tool returns to the model, and the measured conversion time for the cost guard.

## Not in this part

- The named hardware palettes (C64, CGA, ZX Spectrum, Game Boy and phosphor tints), community
  palettes, the measured 9-bit table: the later part of this branch, each with its credited source.
- The glyph generator (the master's non-goal): converting down never needs more than 64 glyphs.
- Wiring a converted sprite into a game, palette swaps, cycling, fades, #61's engine swatches.
- The AI service's route and the tools (parts 3 and 4); the console (part 5).
- A Bitmappy profile display or a palette-limited canvas (open question 4).

## Left to the builder

- The measurement of conversion time and, from it, whether Task 6 sweeps the full matrix.
- Whether Ward weighting beats closest-pair on Dex (decision 8), decided by looking at the output,
  recorded either way.
- Names of private helpers and the order of commits within a task.

## Audit 2026-11-20

Checked against origin/main b7c2abd3. What held: the schema keys (`sprite_file_schema.py:99-102`),
the writer's keys (`sprite_toml.py:30-56`), `SHARED_SPRITE_FIELDS` (`compiled_sprites.py:48`),
`sprite_key` (:72), `ALPHA_TRANSPARENCY_THRESHOLD` (`color/constants.py:23`), the NES file (55
entries, `colors = 55`, no source named), the test files the plan names, and the
existing `check_*` functions. Corrected in place:

- Line references into `animated.py` (the load is `_load_text_uncached` at 1492, the writers at
  2070-2096 and 2415, the copy is `copy_sprite_metadata_from` at 1120; `_copy_from` does not
  exist).
- Task 7's option names: `--profile` is the engine's profiler flag (`-p`, `events/game.py:298`),
  and every registry option is also a flag on every game, so the tool would have refused to
  register. Renamed to `--target-profile`, `--target-color-space`, `--keep-color`.
- The Python statement (everything tests on 3.15, nothing on 3.14) in the Tech Stack and Done
  when.
- Task 3 against the in-flight bug-sweep fix (Dependency line): it stages exactly the sprite
  fields this task would add (`profile`, `color_space` on `AnimatedSprite`, load, both builders,
  `copy_sprite_metadata_from`, `CompiledSprite`, `SHARED_SPRITE_FIELDS`), deliberately without
  validating values and without `split_sprite_text`, which stay here. Two builders would collide
  on the same lines, so whichever lands second rebases onto the other; this plan defers to it.
- Task 1: the NES source is found first (a stop condition belongs before any work), and the lazy
  palette read must pass `tests/test_process_state_guard.py` (it flags `functools.cache` and
  module-level state) and ship as package data to the wheel and the browser bundle.
- Task 5 is split into 5a and 5b: as one commit it holds the snap, the alpha rule, the merge, the
  hints, the report and two goldens, which is not reviewable and cannot land green in pieces.

What I would reconsider, with my recommendation (nothing changed in the design):

1. **Decision 12's "write the keys explicitly, even `true-color`/`rgba32`".** It is consistent
   with "explicit is better", but a conversion to the defaults then adds two lines to a file that
   was fine without them. Worked example: converting Dex to `16-bit` writes `profile = "16-bit"`
   (useful) while converting a sprite to `true-color` writes a label that carries no budget.
   Recommend keeping it: a converted file says what was done to it. It is a format choice, so the
   owner may prefer to omit defaults.
2. **Open question 1(b), a file that declares more than it holds, is not refused.** Right for now,
   but it means `check_conforms_to_declared_profile` is the only enforcement until Bitmappy stops
   the painter. Keep, and record the follow-up in `future-work.md` in Task 8.
3. **The measured conversion time** (the cost guard's number) will come from an M4 Max. Record
   the Raspberry Pi's too if a Pi is reachable, or say it is unmeasured: the Pi runs the AI
   tool rounds, and an unmeasured Pi is the case the guard exists for.
4. **Browser build.** The converter is a tool step, not a frame step, so it needs no browser
   work except that the new modules and `nes.palette` stay importable under Pyodide (stdlib and
   pydantic only, as written). Say so in Task 8 rather than leaving it implied.
5. **Replay and golden traces.** No recording should change: sprites only gain two `None`
   attributes. Run the goldens after Task 3 and, if a sprite-state digest includes every
   attribute, that is a change to explain (not a re-record). The part states no golden of its own
   for the game side; Task 5's fixtures are text goldens, recorded deliberately.
6. **Owner decisions the plan made quietly:** none found beyond the existing Open questions;
   decisions 6 (alpha 128 becomes solid in on/off spaces) and 10 (refuse unknown values) are
   already tied to the owner's rule and question 1.

## Execution record

Empty until the part is built.
