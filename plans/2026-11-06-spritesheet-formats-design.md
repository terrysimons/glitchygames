# Sprite and spritesheet formats — Design

- **Date:** 2026-11-06
- **Status:** DESIGN, requested by the owner (2026-11-06: "do something similar to plan for
  spritesheet formats", alongside `plans/2026-11-06-music-and-instrument-formats-design.md`). Not
  yet planned into milestones.
- **Depends on:** the sprite file format (`ANIMATION_README.md`, `src/glitchygames/sprites/animated.py`),
  the one rule for pixel rows (`docs/specs/2026-10-30-unified-pixel-rows-design.md`), and
  `src/glitchygames/sprites/file_format.py`, which today accepts only TOML.
- **Overlaps:** the tileset builder and tilemap format (`plans/2026-10-18-level-tools-a-tilemap-format.md`,
  `plans/2026-10-18-level-tools-c-tileset-builder.md`); the sprite format linter
  (`plans/future-features.md` #28); `LOADER_README.md`'s "Future Format Ideas" list, which this
  design replaces.
- **Tracked as:** `plans/future-features.md` #65.

## Intent

GlitchyGames sprites are TOML: a `[colors]` table maps one glyph to one color, and pixels are
rows of glyphs, so a sprite is readable, diffable and easy for an LLM to write. Pixel artists
work in other tools, though: Aseprite above all, and sheet packers (TexturePacker), engines
(Godot, Phaser, libGDX, Unity), map editors (Tiled), web editors (Piskel), and plain animated
GIFs and grid sheets.

The engine should read those formats by translating them into its own sprite TOML, the same
principle as the music formats: one validated path, every format converted into our shape, and
nothing dropped without saying so.

## Goals

1. A registry of sprite loaders, each detecting its format by extension and confirming by
   content, as the music loaders do.
2. A converter, `glitchygames sprite-import FILE`, that writes sprite TOML and reports what it
   could not carry over. Bitmappy's File > Open uses the same loaders.
3. Aseprite first: it maps most cleanly (frames with millisecond durations, named tags with a
   direction, slices with pivots, a palette in indexed mode).
4. Honest palette handling: a source with more colors than the format has glyphs is refused with
   the count, or reduced only when asked, never silently.
5. Exact timing conversion from each format's units into seconds.

## Non-goals

- Skeletal animation (Spine, DragonBones): bones and meshes, not pixel frames.
- Tilemaps (`.tmx`): the level-tools plans own maps. A Tiled **tileset** is in scope for its
  tile animations.
- Formats without a published or reverse-engineered specification as first-class loaders
  (Pyxel Edit, GraphicsGale): export from the tool to GIF or a PNG sheet instead.
- CSS sprites: not a file format.
- Lossy sources as pixel art (lossy WebP): readable, but colors are not exact.

## Anti-goals

- Silent color reduction. A quantized palette changes the art.
- Guessing frame size, timing or animation names without saying so: an importer that has to
  assume asks for the value (a command-line option or a Bitmappy dialog) or reports the default
  it used.
- A second runtime path: every format becomes sprite TOML before the engine draws it.

## Design

### How a format comes in

Two ways, one loader:

- **Convert once (the main path):** `glitchygames sprite-import hero.aseprite -o hero.toml` writes
  sprite TOML, with the import report printed and kept as comments at the top of the file. The
  TOML is what the game ships and what people edit.
- **Open in Bitmappy:** File > Open accepts any registered format; saving writes TOML.

Games do not load foreign files at run time (the owner, 2026-11-07): `sprite-import` is the
one way in, so the TOML is always what ships, what is reviewed and what Bitmappy edits, and the
import report is never hidden. `sprite-import --watch` re-converts whenever the source file
changes, so an artist saving in Aseprite sees the game's sprite update. (The music design does
load `music = <path>` directly; sprites differ because the TOML is the editable artifact.)

### Detection

By extension, confirmed by content (signatures from each format's specification, listed under
"The formats, and their order"):

| Format | Extension | Content check |
|---|---|---|
| Aseprite | `.aseprite`, `.ase` | bytes 4–5 are `E0 A5` (WORD 0xA5E0); each frame has magic 0xF1FA |
| Aseprite JSON sheet | `.json` (+ PNG) | `frames` and `meta.app` naming aseprite.org |
| TexturePacker / Phaser / PixiJS JSON | `.json` (+ PNG) | `frames` (an object for Hash, an array for Array) and `meta.image` |
| libGDX atlas | `.atlas` (+ PNG) | text; an image filename line, then `size:`; `bounds:` (new) or `xy:` (legacy) |
| Godot SpriteFrames | `.tres` | a `[gd_resource type="SpriteFrames"` header (to verify) |
| Tiled tileset | `.tsx`, `.tsj` | XML `<tileset`, or JSON `"type": "tileset"` |
| Animated GIF | `.gif` | `GIF87a` / `GIF89a`; animated if more than one image descriptor |
| APNG | `.png`, `.apng` | PNG signature and an `acTL` chunk before the first `IDAT` |
| Animated WebP | `.webp` | `RIFF`…`WEBP` with the VP8X animation flag |
| Piskel | `.piskel` | JSON with `modelVersion` and `piskel` |
| Grid sheet | `.png` | none: the frame size comes from the caller |

A `.json` or `.png` can be several formats, so the content check decides; a file that matches
none is refused with the list of formats that can be read. A `--format` option names it outright.

### What maps, and what has no equivalent

| Concept | Sprite TOML | How |
|---|---|---|
| Frames | `[[animation.frame]]` | sheet formats cut each frame from the PNG; trimmed frames are re-padded to the full canvas (`spriteSourceSize`/`sourceSize`, libGDX `offsets`, Godot `margin`); rotated frames are un-rotated |
| Frame timing | `frame_interval` (seconds) | Aseprite and Tiled: ms ÷ 1000; GIF: hundredths ÷ 100; APNG: `delay_num`/`delay_den` (den 0 means 100); WebP: ms; Godot: `duration` ÷ `speed` (duration is a multiplier); Phaser: 1 ÷ `frameRate`; Piskel: 1 ÷ `fps`; libGDX and PixiJS: none (the caller gives it). Equal durations become the animation's interval; others per-frame overrides |
| Named animations | `[[animation]]` `namespace` | Aseprite tags; Phaser and PixiJS `animations`; libGDX repeated region names ordered by `index`; Godot animations; Tiled tile animations; GIF, APNG and Piskel are one animation |
| Looping | `loop` | infinite or unspecified → `true`; once → `false` |
| Reverse direction | frame order | reordered at import |
| Anchor / pivot | `frame_anchor` | Aseprite slice pivots, TexturePacker `pivot`/`anchor`, Unity pivots, where the pivot is one of the format's nine anchors; otherwise reported |
| Hitbox | `[sprite.hitbox]` / per-frame `hitbox` | Aseprite slice named `hitbox` (the convention, the owner, 2026-11-07), Tiled tile collision rectangles |
| Palette | `[colors]` | Aseprite indexed, GIF and indexed PNG carry one; RGBA sources count unique colors (see below) |
| Text and properties | `description`, `tags` | Aseprite user data, Tiled properties, where they are plain words |

No equivalent, so reported (and handled as listed):

- **Ping-pong** (Aseprite, Phaser `yoyo`, Godot `LOOP_PINGPONG`): baked into frames at import
  (A B C D becomes A B C D C B; the owner, 2026-11-07), and noted in the report.
- **Repeat counts above one:** `loop` is a boolean; reported.
- **Layers and blend modes** (Aseprite, Piskel): visible layers are flattened, honoring opacity,
  cel offsets and z-order; blend modes other than Normal are reported.
- **9-slice borders**, polygon trims and meshes, multiple collision shapes, tile flips: reported.
- **Per-frame palettes** (GIF local color tables): merged into one palette.

### Palette

The sprite format maps one glyph to one color, and the writer's glyph set is 64 characters
(`SPRITE_GLYPHS`, `src/glitchygames/sprites/constants.py`; Bitmappy refuses more colors,
`bitmappy_sprite.py`). Indexed sources fit when they use 64 colors or fewer; a GIF may use 256,
and RGBA sources (TexturePacker sheets, Aseprite RGBA, Piskel) have no palette at all. So:

1. Count the colors actually used across every frame.
2. At or under the budget: assign glyphs, transparent pixels to the transparent glyph.
3. Over it: refuse, naming the count and the budget. `--reduce-colors N` quantizes on request,
   and the report lists the colors merged.

The budget stays at 64 glyphs (the owner, 2026-11-07). A sprite file's rows stay readable and
align in every editor. If imports keep hitting the limit, a later option is two characters per
pixel for sprites over 64 colors (4,096 colors in plain ASCII), not more Unicode glyphs.

### Loaders

As the music loaders: each registers a format name, extensions, a content check, and a loader
that returns frames (RGBA arrays), animations, timing, anchors, hitboxes and the list of what it
could not carry over. Sheet formats need a PNG decoder and the companion image resolved
relative to the data file (`meta.image`, the atlas page line, the `.tres` external resource).

### The formats, and their order

1. **Aseprite native** (`.aseprite`): the fullest mapping (tags with direction, durations,
   slices, palette). Spec: https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md
2. **Aseprite JSON + PNG**: the same metadata without chunk and zlib parsing. Keys from
   https://github.com/aseprite/aseprite/blob/main/src/app/doc_exporter.cpp
3. **Animated GIF and APNG**: universal, and GIF is indexed. Specs:
   https://www.w3.org/Graphics/GIF/spec-gif89a.txt, https://wiki.mozilla.org/APNG_Specification
4. **Grid sheets** (frame size, margin, spacing, as Phaser's
   https://github.com/phaserjs/phaser/blob/master/src/textures/parsers/SpriteSheet.js and Tiled
   describe them), **TexturePacker JSON**, and **Tiled tilesets** (https://doc.mapeditor.org/en/stable/reference/tmx-map-format/).
5. **libGDX, Godot, Unity, Piskel** as needed. Skip Spine and DragonBones.

A natural extra, not yet researched: PICO-8 and TIC-80 cartridge sprite sheets, 8×8 sprites in a
16-color palette, which fit glyph-indexed sprites exactly.

Export (sprite TOML to an Aseprite file, GIF or PNG sheet) is the reverse direction and is not
designed here; Bitmappy already renders frames.

### Sources and what still needs checking

The format research (2026-11-06) read primary sources for Aseprite, Phaser, PixiJS, libGDX,
Godot, Tiled, GIF, APNG, WebP and Piskel. Still to verify before each loader is built:

- Godot's exact `.tres` header and syntax; Unity's `.meta` keys and rect origin.
- libGDX's legacy y-axis convention (the legacy writer flips y and `offset.y`).
- The GIF `NETSCAPE2.0` loop extension, which the GIF89a spec does not define.
- Pyxel Edit's archive layout (secondary sources only); GraphicsGale (reverse-engineered).
- Licenses: Aseprite's spec document (Aseprite itself is under a proprietary EULA; writing an
  independent parser from the public spec is the usual route), and Phaser, PixiJS and Godot.

Each loader cites its format's specification in its source.

## Tests

- Per format: small fixture files with their expected TOML; malformed files with the error each
  must give.
- Timing: each unit converts exactly (a 100 ms Aseprite frame is `0.1`; a GIF delay of 7 is
  `0.07`; a Godot duration of 2.0 at speed 10 is `0.2`).
- Trimmed and rotated sheet frames come back to the full canvas, pixel for pixel.
- Palette: a 65-color source is refused with the count; `--reduce-colors` reports its merges.
- Detection: a `.png` that is an APNG, a grid sheet and a plain image each take the right path.

## Decisions (the owner, 2026-11-07)

1. Import only, through `sprite-import` and Bitmappy, plus `sprite-import --watch`; no run-time
   loading of foreign files.
2. Ping-pong animations are baked into frames at import.
3. The palette budget stays at 64 glyphs; over it, refuse with the count, or `--reduce-colors N`.
4. An Aseprite slice named `hitbox` is the sprite's hitbox.
