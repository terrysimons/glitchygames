# Sprite QuickLook preview for macOS — Design

- **Date:** 2026-10-29
- **Status:** BUILT on `feat/sprite-quicklook` (2026-10-29); the owner checked it in the real QuickLook panel and opened a PR.
  Plan: `plans/2026-10-29-sprite-quicklook-implementation.md`. How to build and install: `src/quicklook/README.md`.
- **Repo / location:** `glitchygames` (this repo), under `src/quicklook/` (the owner, 2026-10-29).

## Intent

When the owner selects a GlitchyGames sprite `.toml` in Finder and presses space, QuickLook shows
the sprite itself — rendered as the sprite, not the TOML text (the owner: "I want to see what the
file contents are - rendered as the sprite"). Animated sprites play; static sprites show as one
image.

## Goals

1. **Static sprites** (`[sprite] pixels = """…"""`, no `[[animation]]`, e.g.
   `src/apps/bitmappy/src/bitmappy/resources/sprites/small_heart.toml`) render as a single image.
2. **Animated sprites** (`[[animation]]` + `[[animation.frame]]`, e.g. `slime-jump.toml` at the repo
   root) **auto-play as soon as the preview opens** (the owner, 2026-10-29), honoring each
   animation's `frame_interval`, each frame's own `frame_interval` override, and `loop`.
3. **Pixel art stays crisp**: scaled up with nearest-neighbor to fill the preview, integer scale
   factors only, centered.
4. **Matches what the engine draws** (rules below, taken from
   `src/glitchygames/sprites/animated.py` and `pixel_utils.py`). If the preview and the game
   disagree, the preview is wrong.
5. **Transparency is visible**: transparent pixels show a checkerboard behind them; partial alpha
   blends over it.
6. **Every frame is visible: a film strip per animation** (the owner, 2026-10-29: "we need to show
   all of the frames of the sprite"). Any sprite with more than one frame or more than one
   animation previews as one row per animation, in file order:
   - the animation's name on the left; every frame left to right, each with its number above it
     and its duration below it ("0.50s"), wrapping onto more lines rather than scrolling sideways
     (the owner chose the annotated layout, number on top and timing on the bottom);
   - the live animation playing at the right end of the row on a checkerboard, labeled "playing",
     "playing (once)" for a non-looping animation, or "still" for a one-frame one; the frame on
     screen is outlined in blue in its strip;
   - every row plays at once from the moment the preview opens, which replaces the old picker.
   *Claude's calls (the owner agreed 2026-10-29):* strip frames fit a 64 pt cell and the live view
   a 192 pt box, both at a whole-number scale unless the sprite is bigger than that; the panel
   scrolls vertically when the rows don't fit; a static sprite (one animation, one frame) keeps
   the single large view, since a one-frame strip would only repeat it.
7. **Non-sprite `.toml` files** (`pyproject.toml`, `.taplo.toml`, …) still preview as plain text.
   macOS gives every `.toml` the single type `public.toml`, so the extension is asked for all of
   them; it must fall back gracefully. An extension can't hand a file back to Apple's built-in
   text preview, so the fallback is the extension's own scrollable, monospaced, read-only text
   view with no highlighting. The owner accepted that it will look slightly different from
   Apple's (2026-10-29).
8. **No Python needed** at preview time: parsing and rendering are native Swift.
9. **Finder thumbnails** (the owner, 2026-10-29): icon view, column view, Get Info and the like
   show the sprite instead of a generic TOML icon. A QuickLook *Thumbnail Extension* sits in the
   same host app as the preview extension, and both use one shared parser/renderer.
   - The thumbnail is the first frame of the first animation in file order (the frame that plays
     first in the preview). For a static sprite it is the single image.
   - It is scaled nearest-neighbor to fit the requested size, centered, and transparent pixels stay
     transparent (no checkerboard), so it sits on Finder's own background.
   - A sprite smaller than the requested size is scaled up by a whole-number factor. A sprite that
     doesn't divide evenly may be scaled down nearest-neighbor; it must never be smoothed.
   - **Non-sprite `.toml` files get no custom thumbnail.** The extension fails the request, so Finder
     keeps the normal TOML icon. The builder must confirm that a failed thumbnail request really
     does fall back to the default icon (not a blank one) on this macOS.

## Non-goals (v1)

- No editing; preview only.
- No hitbox / frame-anchor overlays, no `[[transition]]` state-machine playback.
- No swatch (palette-swap) variants: the `[colors]` palette as written is what renders.
- No distribution: no notarization, App Store, or Homebrew cask. It runs on the owner's Mac.

## Anti-goals (would make it a failure even if it works)

- Rendering that disagrees with the engine (wrong colors, transparency, frame order or timing).
- Blurry / smoothed pixels.
- Breaking QuickLook for ordinary `.toml` files.
- Touching the engine or `third_party/` (see the owner's "leave third_party alone" rule).

## The format, as the engine reads it

Source of truth: `AnimatedSprite._load_toml` and helpers in
`src/glitchygames/sprites/animated.py`, plus `src/glitchygames/sprites/pixel_utils.py`.

**Is it a sprite?** It is if the parsed TOML has either a non-empty `animation` array of tables, or
`sprite.pixels`. Anything else → plain-text fallback. A file that *is* a sprite but fails to render
(bad TOML, no frames) shows a short error plus the text, never a blank pane.

**Colors** — `[colors]`, keyed by a one-glyph string. Both forms appear in the repo:
`[colors."a"]` sub-tables and inline tables (`"█" = { red = 255, green = 0, blue = 255 }`).
Missing `red`/`green`/`blue` default to 0. `alpha` is optional:
- absent → opaque RGB;
- 0–254 → that alpha;
- 255 → opaque.

**Glyphs are Unicode code points**, not bytes and not grapheme clusters. Python iterates a `str` by
code point; Swift must iterate `unicodeScalars` to match (e.g. `█` U+2588 is one pixel).

**Transparency** (`is_color_transparent`): a pixel is transparent when its color is magenta
`(255, 0, 255)` with no alpha or alpha 255, or when its alpha is 0. Glyphs missing from `[colors]`
render as magenta, i.e. transparent.

**Pixel rows** (static sprites and animation frames alike, `normalize_pixel_rows`): one rule since
2026-10-30, described in `docs/specs/2026-10-30-unified-pixel-rows-design.md`. Nothing is cut off;
short rows are padded with transparent pixels to the longest. That design's "Before and after"
table records the two rules this preview first copied (R4, animated: per-line strip, most common
length, truncate, pad with the row's last glyph; R5, static: whole-string strip, longest row, pad
with the most common glyph).

**Animations**: each `[[animation]]` has `namespace` (default `"default"`), `frame_interval`
(seconds, default 0.5), `loop` (default true), and `frame` entries. Frames play in **file order**: the engine means to sort by `frame_index`, but its sort
key is never set, so it changes nothing (found by the golden tests while building, 2026-10-29;
tracked in `plans/future-work.md`). Frames whose pixels are empty are skipped. A frame's own `frame_interval` overrides the animation's. A non-looping animation stops on
its last frame.

**Static sprite name**: the single animation is named after `sprite.name` (default `"idle"`).

## Decided "how" (the owner agreed in conversation; marked where it was Claude's call)

- **A QuickLook Preview Extension inside a tiny host app** — the only mechanism current macOS
  loads (the old `.qlgenerator` plugins are gone). Swift, AppKit/SwiftUI, Xcode 27.1 (installed).
  *(Claude's call, agreed.)*
- **Location:** `src/quicklook/` in this repo (the owner).
- **Auto-play** on open (the owner).
- **Signing:** this Mac has no code-signing identity, so the build uses ad-hoc "Sign to Run
  Locally". Install = copy the app to `/Applications`, open it once, enable the extension in
  System Settings if macOS asks. If macOS refuses an ad-hoc-signed extension, the fallback is the
  owner adding a free Apple ID team in Xcode — that is a step the owner does, not the builder.

## Claude's calls (from the builder check; the owner can override)

- **Timing is wall-clock**: each frame shows for exactly its `frame_interval`. The engine's
  per-tick rounding is not simulated.
- **Engine-exact for well-formed files.** Malformed files may differ from the engine but must
  still render something sensible. Ragged rows are common in AI-generated sprites, so the preview
  copies both row-normalization rules. Duplicate `namespace` values show one label per distinct
  name, using the later table (which is where the engine reads its frames from).
- **No other `.toml` QuickLook extension is installed** (checked with `pluginkit`, 2026-10-29), so
  there is nothing to compete with.

## Left to the builder

- TOML parsing: a vetted TOML 1.0 Swift package via SwiftPM (preferred, must handle inline tables,
  multi-line basic strings, quoted keys like `"."`) or a hand-written parser with tests. Results
  must match `tomllib` on every sprite in the repo.
- How the Xcode project is generated/checked in (plain `.xcodeproj`, or XcodeGen if installed).
- Preview UI details: label row styling, background, checkerboard size, maximum scale, dark mode.
- A `Makefile`/script for build + install, and a short `src/quicklook/README.md` on installing,
  enabling, and resetting QuickLook (`qlmanage -r`, `qlmanage -p <file>` to test).
- Animation timing mechanism (timer / display link), as long as per-frame durations are honored.

## How we know it works

- Swift unit tests for the parser + renderer: color forms, alpha rules, Unicode glyphs, both row
  normalization rules, frame sort order, per-frame intervals, static vs animated detection,
  non-sprite fallback.
- A golden check: for a set of repo sprites (at least `small_heart.toml`, `slime-jump.toml`,
  `slime-jump-alpha.toml`, `drawing_fire/sprites/soldier.toml`, and one with `[[transition]]`),
  the frames the Swift renderer produces match RGBA frames dumped by the engine's own loader
  (a small Python script in `src/quicklook/` that loads with `AnimatedSprite` and writes the
  frames out).
- Manual: `qlmanage -p` on a static sprite, an animated one, and `pyproject.toml`; then space-bar
  in Finder.
- Thumbnails: a unit test that the thumbnail image equals frame 0 scaled; then manually
  `qlmanage -t -s 256 <file>` on a static sprite, an animated one and `pyproject.toml`, and a look at
  a sprite folder in Finder icon view. Finder caches thumbnails, so reset first (`qlmanage -r cache`).

## Engine quirks noticed (reported, not fixed here)

- `frame_index` never orders frames: the engine's sort key reads an attribute no frame has, so frames
  play in file order. The preview copies that; tracked in `plans/future-work.md`.

- ~~Static and animated sprites normalize ragged rows differently (longest row + most-common-glyph
  pad vs most-common length + last-glyph pad + truncation), and static rows are not stripped per
  line. The preview copies both behaviors so it matches the engine. The owner wants the engine
  unified later, on its own branch.~~ Done 2026-10-30 (`feat/unified-pixel-rows`,
  `docs/specs/2026-10-30-unified-pixel-rows-design.md`); the preview follows the one rule. That is tracked in `plans/future-work.md` under "Bugs found and
  not fixed yet"; when it lands, the QuickLook parser and its golden frames change with it.

## Changed while building (2026-10-29)

- Frames play in file order, not `frame_index` order: the engine's sort is a no-op (see above).
- CRLF files: `tomllib` turns CRLF into LF inside multi-line strings and TOMLDecoder doesn't, so
  SpriteCore turns every CRLF into LF before decoding.
- The preview pre-scales each frame with nearest neighbor (offscreen renders blurred without it),
  capped at 512 px on the long side so a full-screen preview stays small; the layer's
  nearest-neighbor filter scales the rest. A sprite bigger than the preview shrinks to fit.
- Thumbnails fit the pixels a Retina display really gives them (`request.scale`), and are drawn
  as a canvas of the whole requested size with the sprite centered on both axes (the owner,
  2026-10-29: they were bottom-left anchored). QuickLook's thumbnail context is in pixels, so
  the image is drawn over the context's real bounds, not its point size.
- Float color channels (`red = 255.0`) draw, truncated like pygame-ce does, instead of failing.
- Film strip (goal 6, the owner, 2026-10-29) replaced the animation picker: every animation shows
  every frame at once. Layout is `Sources/SpriteCore/FilmStripLayout.swift` (unit-tested); the
  view is `App/PreviewExtension/FilmStripView.swift`. Checked offscreen with the render harness
  on `player.toml` (4 animations), `slime-jump.toml` (20 frames, wraps) and `small_heart.toml`
  (static, single view unchanged).
- The app is named "GlitchyGames Sprite Preview" (the owner, 2026-10-29); the extensions are
  "GlitchyGames Sprite Preview" and "GlitchyGames Sprite Thumbnails". Bundle identifiers keep
  `games.glitchy.SpritePreview`. `make install` deletes the build copy after installing, because
  left on disk it registered again and showed in System Settings as a second app with no
  extensions.
- App icon: `shroom4.toml` (the owner's pick), drawn by `src/quicklook/tools/make_app_icon.py`
  with the engine's loader, nearest neighbor on the preview's checkerboard in Apple's rounded
  square. macOS shows it as is (no gray backing plate).
- `qlmanage -t` can't check thumbnail extensions on this macOS: it only uses old generators and
  hangs. Thumbnails are checked with `src/quicklook/tools/make_thumbnails.swift`, which uses
  Finder's API. Non-sprite `.toml` files keep the plain document icon they had before (checked
  with the extension switched off).
