# Sprite QuickLook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A macOS app at `src/quicklook/` whose QuickLook Preview and Thumbnail extensions render GlitchyGames sprite `.toml` files (static and auto-playing animated) exactly as the engine draws them.

**Architecture:** A pure-Swift SwiftPM library, `SpriteCore`, holds the TOML decoding, the engine-exact pixel and color rules, the animation clock and the CGImage rendering. It is tested with `swift test` and checked against golden frames dumped by the engine's own Python loader. A small XcodeGen project builds the host app and two app extensions, the preview and the thumbnail, both linking `SpriteCore`.

**Tech Stack:** Swift 6.4, Swift Testing (`import Testing`), SwiftPM, TOMLDecoder 0.4.5 (`https://github.com/dduan/TOMLDecoder`), AppKit + QuickLookUI + QuickLookThumbnailing, XcodeGen (2.46.0, installed by `src/quicklook/.envrc` through direnv), Xcode 27.1. Python (the repo's `uv` env) only for the golden-dump tool.

**Spec:** `docs/specs/2026-10-29-sprite-quicklook-design.md`. Read it first; this plan argues from it.

## Global Constraints

- `src/quicklook/.envrc` (already written) `source_up`s the repo's `.envrc` and installs xcodegen once with Homebrew; carry it into the worktree with the spec.
- Everything lives under `src/quicklook/`. Don't change the engine (`src/glitchygames/`) or `third_party/`.
- Work on branch `feat/sprite-quicklook` from `main`, in a worktree (`superpowers:using-git-worktrees`).
  The spec and the new `plans/future-work.md` row are currently uncommitted on
  `feat/bitmappy-masterhub-push`; carry both files over (copy them into the worktree, plus this plan).
- **Commits:** the owner never wants automatic commits or pushes. Each "Checkpoint" step means: show
  `git status` and the diff summary, and commit only after the owner OKs it. Never push.
- No Python at preview time. The extensions use only `SpriteCore` + system frameworks.
- Glyphs are Unicode **scalars** (Python code points). Never iterate `String` by `Character` and never
  split on `Character("\n")`: Swift treats `"\r\n"` as one Character. Use `unicodeScalars` throughout.
- Pixel art is never smoothed: `interpolationQuality = .none` / `magnificationFilter = .nearest`.
- Preview scaling uses whole-number factors only, centered. Transparent pixels sit on a checkerboard in the preview and are left transparent in thumbnails.
- Animations auto-play when the preview opens; the first animation in file order plays first.
- Timing is wall-clock: each frame shows for exactly its `frame_interval`. A non-looping animation stops on its last frame.
- Ordinary `.toml` files: the preview shows the file in a scrollable, monospaced, read-only text view; the thumbnail extension fails the request so Finder keeps its default icon.
- Signing is ad-hoc (`CODE_SIGN_IDENTITY = "-"`). There is no team ID. Deployment target macOS 14.0.
- Bundle IDs: `games.glitchy.SpritePreview` (app), `games.glitchy.SpritePreview.PreviewExtension`,
  `games.glitchy.SpritePreview.ThumbnailExtension`.
- Long, explicit names; no abbreviations (owner preference). Attribute any copied reference with a source comment.
- Build products and DerivedData go outside Dropbox: `-derivedDataPath ~/Library/Developer/Xcode/DerivedData/SpritePreview`.
  The repo `.gitignore` already ignores `build/`; also ignore `src/quicklook/.build/` and the generated
  `src/quicklook/App/SpritePreview.xcodeproj/`.

## Engine rules the code must copy (from `src/glitchygames/sprites/animated.py`, `pixel_utils.py`)

These are written out once here; tasks refer back to them.

- **R1 sprite or not:** after parsing, it's a sprite if `animation` is a non-empty array or `sprite.pixels`
  exists. Static if `animation` is missing or empty **and** `sprite.pixels` exists; otherwise animated.
- **R2 colors:** `[colors]` maps a 1-scalar key to `{red, green, blue, alpha?}`. Missing channel → 0. No alpha
  → 255. alpha 0–254 → that value. Anything else → 255. Glyph not in the map → magenta `(255,0,255,255)`.
- **R3 transparent:** `alpha == 0` or `(r,g,b) == (255,0,255) && alpha == 255`.
- **R4 animated rows:** split the string on U+000A only. Python-`strip()` each line and drop the empty ones.
  Width = the most common line length (ties go to the length seen first). Longer lines are truncated;
  shorter ones are padded with their own last scalar. No lines → the frame is skipped.
- **R5 static rows:** Python-`strip()` the whole string, then split on U+000A (lines are **not** stripped). Width =
  the longest row. Shorter rows are padded with the most common scalar across all rows (ties go to the
  first seen).
- **R6 animations:** `namespace` defaults to `"default"`, `frame_interval` to 0.5, `loop` to true. Frames play in
  **file order**: the engine's `frame_index` sort reads an attribute no frame has, so it is a no-op (found by
  the golden tests while building; corrected here and in the spec). A frame's own `frame_interval` overrides
  the animation's. An animation with no non-empty frames is dropped.
- **R7 static:** one animation named `sprite.name` (default `"idle"`), one frame, duration 0.5, loop true.
- **R8 duplicate namespace (Claude's call, spec):** one entry per distinct name, at the position the name first
  appears, holding the **last** table's frames, interval and loop.
- Python `str.strip()` strips characters where `str.isspace()` is true. Implement
  `pythonStrip` with `Unicode.Scalar.Properties.isWhitespace` **plus** U+001C–U+001F, which Python also counts
  as whitespace.

## Review Focus

1. **CRLF files** (saved on Windows or by some editors). R4 removes the `\r` with the per-line strip, but R5 keeps it as a glyph, which becomes magenta (transparent).
   TOMLDecoder may normalize newlines differently from `tomllib`. A CRLF golden fixture pins this (Task 4).
2. **`frame_interval = 1`** (a TOML integer, not a float). Python accepts it; a strict `Double` decode would fail
   the whole file. Task 1 tests that an integer interval decodes.
3. **Ties in the "most common" choices** (R4 line length, R5 pad scalar). A different tie-break gives a different width or pad color, and it happens silently. Task 2 tests both ties.
4. **Zero or negative durations.** These could freeze the clock or hang it in an infinite loop. Task 5 tests that an all-zero animation stays on frame 0 and returns.
5. **Frames of different sizes in one animation, and large sprites (e.g. 256×256) in a small thumbnail request.** The preview must scale every frame by the same factor, computed from the largest frame, so the sprite doesn't jump around. A sprite bigger than the thumbnail size must scale down nearest-neighbor, never smoothed. Tasks 5 and 7 test these.

---

### Task 1: SwiftPM package, TOML decoding, sprite/not-sprite classification

**Files:**
- Create: `src/quicklook/Package.swift` (library `SpriteCore`, test target `SpriteCoreTests`, dependency
  `TOMLDecoder` `exact: "0.4.5"`, platforms `.macOS(.v14)`, Swift 6 language mode)
- Create: `src/quicklook/Sources/SpriteCore/SpriteDocument.swift`: `Decodable` mirror of the TOML
- Create: `src/quicklook/Sources/SpriteCore/SpriteLoader.swift`: `load`, classification only for now
- Test: `src/quicklook/Tests/SpriteCoreTests/SpriteDocumentTests.swift`
- Modify: `.gitignore`: add `src/quicklook/.build/`, `src/quicklook/App/SpritePreview.xcodeproj/`

**Interfaces:**
- Produces:
  - `struct SpriteDocument: Decodable { var sprite: SpriteSection?; var colors: [String: ColorEntry]?; var animation: [AnimationSection]? }`
  - `struct SpriteSection: Decodable { var name: String?; var pixels: String? }`
  - `struct ColorEntry: Decodable { var red: Int?; var green: Int?; var blue: Int?; var alpha: Int? }`
  - `struct AnimationSection: Decodable { var namespace: String?; var frameInterval: Double?; var loop: Bool?; var frame: [FrameSection]? }`
  - `struct FrameSection: Decodable { var frameIndex: Int?; var frameInterval: Double?; var pixels: String? }`
  - TOML snake_case keys map through `CodingKeys` (`frame_interval`, `frame_index`). Unknown keys (`hitbox`,
    `transition`, `swatches`, `description`, …) are ignored.
  - `frameInterval` decodes a TOML integer **or** float: write a custom `init(from:)` that tries `Double`, then `Int`.
  - `public enum SpriteLoadResult: Sendable { case sprite(Sprite); case notSprite; case failed(reason: String) }`
  - `public enum SpriteLoader { public static func load(data: Data) -> SpriteLoadResult }`. Task 3 fills in `.sprite`.
    For this task, return `.failed(reason: "not implemented")` for documents that are sprites under R1.
  - Parse failure: if the UTF-8 text contains `"[sprite"` or `"[[animation"` → `.failed(reason: <decoder error>)`;
    otherwise → `.notSprite`. Non-UTF-8 data → `.notSprite`.

- [ ] **Step 1: Write the failing tests** (Swift Testing):
  `decodesSubTableColors` (`[colors."a"]` red 255 green 215 blue 0 → `ColorEntry(255,215,0,nil)`),
  `decodesInlineTableColorsWithUnicodeKey` (`"█" = { red = 255, green = 0, blue = 255 }` → key `"█"`),
  `decodesIntegerFrameInterval` (`frame_interval = 1` → `1.0`), `pyprojectIsNotSprite`
  (a minimal `[project] name = "x"` → `.notSprite`), `brokenSpriteTomlFails` (`"[sprite]\nname = "` →
  `.failed`), `brokenPlainTomlIsNotSprite` (`"[tool\n"` → `.notSprite`), `staticAndAnimatedAreSprites`
  (both forms are not `.notSprite`).
- [ ] **Step 2:** `cd src/quicklook && swift test`. Expected: compile failure / FAIL.
- [ ] **Step 3:** Implement the types and `load` above. Check TOMLDecoder 0.4.5's actual API (`TOMLDecoder().decode(_:from:)`
  taking `String` or `Data`) in its README/source before writing the call.
- [ ] **Step 4:** `swift test`. Expected: all pass, **no warnings** (Swift 6 concurrency warnings included).
- [ ] **Step 5: Checkpoint** (see Global Constraints).

### Task 2: Color palette and the two row-normalization rules

**Files:**
- Create: `src/quicklook/Sources/SpriteCore/ColorPalette.swift`
- Create: `src/quicklook/Sources/SpriteCore/PixelRows.swift`
- Test: `src/quicklook/Tests/SpriteCoreTests/ColorPaletteTests.swift`, `PixelRowsTests.swift`

**Interfaces:**
- Consumes: `ColorEntry` (Task 1)
- Produces:
  - `public struct RGBA: Equatable, Hashable, Sendable { public var red, green, blue, alpha: UInt8 }`, `static let magenta = RGBA(255,0,255,255)`, `var isTransparent: Bool` (R3)
  - `struct ColorPalette { init(colors: [String: ColorEntry]); func color(for glyph: Unicode.Scalar) -> RGBA }` (R2;
    keys that are not exactly one scalar are ignored; channels are clamped to 0–255)
  - `enum PixelRows { static func animatedFrameRows(_ pixels: String) -> [[Unicode.Scalar]]` (R4)
    `static func staticSpriteRows(_ pixels: String) -> [[Unicode.Scalar]]` (R5) `static func pythonStrip(_ scalars: some Collection<Unicode.Scalar>) -> [Unicode.Scalar] }`

- [ ] **Step 1: Write the failing tests:**
  - `missingAlphaIsOpaque`, `alpha254Kept`, `alpha255Opaque`, `alpha300BecomesOpaque`, `missingChannelIsZero`,
    `unknownGlyphIsMagenta`
  - `magentaIsTransparent`, `alphaZeroIsTransparent`, `magentaWithAlpha128IsNotTransparent`
  - `animatedStripsEachLineAndDropsEmpty` (`"\n  ab \n\n cd\n"` → `[[a,b],[c,d]]`)
  - `animatedTruncatesAndPadsToModeLength` (`"abc\nabc\nab\nabcd"` → widths all 3; `ab` → `abb`; `abcd` → `abc`)
  - `animatedModeTieGoesToFirstSeenLength` (`"ab\nabc"` → width 2, `abc` → `ab`)
  - `animatedCRLFStripsCarriageReturn` (`"ab\r\ncd\r\n"` → `[[a,b],[c,d]]`)
  - `staticPadsWithMostCommonScalarToLongestRow` (`"abb\nb"` → `b` is most common, so the second row becomes `bbb`)
  - `staticPadTieGoesToFirstSeenScalar` (`"aab\nb"` → `a` and `b` tie at 2 and `a` was seen first, so the second row becomes `baa`)
  - `staticDoesNotStripLines` (`"ab\n cd"` → second row `[" ", c, d]`, width 3)
  - `staticKeepsCarriageReturnAsGlyph` (`"ab\r\ncd"` → first row `[a,b,"\r"]`)
  - `unicodeGlyphIsOneScalar` (`"█o█"` → 3 scalars)
  - `pythonStripRemovesFileSeparator` (U+001C at both ends is removed)
- [ ] **Step 2:** `swift test`. Expected: FAIL.
- [ ] **Step 3:** Implement. For the "most common" choices, count in first-seen order and pick the first with the max count. That matches `Counter.most_common(1)`.
- [ ] **Step 4:** `swift test`. Expected: all pass, no warnings.
- [ ] **Step 5: Checkpoint.**

### Task 3: Resolve documents into sprites

**Files:**
- Create: `src/quicklook/Sources/SpriteCore/Sprite.swift`
- Modify: `src/quicklook/Sources/SpriteCore/SpriteLoader.swift` (return `.sprite`)
- Test: `src/quicklook/Tests/SpriteCoreTests/SpriteLoaderTests.swift`

**Interfaces:**
- Consumes: Task 1 and Task 2 types
- Produces:
  - `public struct SpriteFrame: Equatable, Sendable { public let width: Int; public let height: Int; public let pixels: [RGBA] /* row-major, count == width*height */; public let duration: Double }`
  - `public struct SpriteAnimation: Equatable, Sendable { public let name: String; public let loop: Bool; public let frames: [SpriteFrame] /* non-empty */ }`
  - `public struct Sprite: Equatable, Sendable { public let name: String; public let animations: [SpriteAnimation] /* non-empty, file order */ }`
  - `SpriteLoader.load(data:)` returns `.sprite` for R1 sprites. It returns `.failed(reason: "no frames")` when every animation is dropped,
    or when a static sprite has width 0.

- [ ] **Step 1: Write the failing tests:**
  - `staticSpriteBecomesOneFrameIdle` (no `sprite.name` → animation `"idle"`, 1 frame, duration 0.5, loop true)
  - `staticSpriteUsesSpriteName`
  - `animationsWinOverSpritePixels` (both present → animated)
  - `defaultsNamespaceIntervalLoop` (`"default"`, 0.5, true)
  - `perFrameIntervalOverrides` (animation 0.5, frame 2 has `frame_interval = 0.1` → durations `[0.5, 0.5, 0.1]`)
  - `framesSortedByFrameIndexStably` (indices `[2, 0, 2]` → order: original #1, #0, #2)
  - `emptyFrameSkippedButCountsForDefaultIndex` (frames: empty, `X` (no index), `Y` with index 0 → order `Y`, `X`)
  - `animationWithOnlyEmptyFramesDropped`
  - `allAnimationsEmptyFails`
  - `duplicateNamespaceKeepsFirstPositionLastData` (R8: `walk`, `run`, `walk`(frames Z) → names `[walk, run]`, walk's frame is Z)
  - `loopFalseKept`
- [ ] **Step 2:** `swift test`. Expected: FAIL.
- [ ] **Step 3:** Implement the resolution in `SpriteLoader` (R6–R8), building each frame's `pixels` through `ColorPalette`.
- [ ] **Step 4:** `swift test`. Expected: all pass, no warnings.
- [ ] **Step 5: Checkpoint.**

### Task 4: Golden frames from the engine's own loader

**Files:**
- Create: `src/quicklook/tools/dump_engine_frames.py`
- Create: `src/quicklook/Tests/SpriteCoreTests/Golden/<name>.toml` + `<name>.json` (generated; committed)
- Create: `src/quicklook/Tests/SpriteCoreTests/Golden/ragged-static.toml`, `ragged-animated.toml`, `crlf-static.toml`,
  `crlf-animated.toml` (hand-written inputs; the `.json` files are generated). Write the CRLF files with real `\r\n` bytes and mark them
  `-text` in `src/quicklook/.gitattributes` so git doesn't rewrite them.
- Test: `src/quicklook/Tests/SpriteCoreTests/GoldenFrameTests.swift`
- Modify: `src/quicklook/Package.swift` (`resources: [.copy("Golden")]` on the test target)

**Interfaces:**
- Consumes: `SpriteLoader.load(data:)`, `Sprite` (Task 3)
- Produces: `python src/quicklook/tools/dump_engine_frames.py --out <dir> <toml>...`. For each input it copies the TOML to
  `<dir>/<stem>.toml` and writes `<dir>/<stem>.json`:
  `{"animations": [{"name": str, "loop": bool|null, "frames": [{"width": int, "height": int, "duration": float, "pixels": [[r,g,b,a], ...]}]}]}`.
  The data comes from `AnimatedSprite` (`_animation_order`, `_animations`, `_loop_flags`, `frame.pixels`, `frame.duration`, `frame.image.get_size()`);
  comment that these are private attributes and that the tool is test-only. RGB tuples get alpha 255. Set `SDL_VIDEODRIVER=dummy`
  and call `pygame.display.set_mode((1, 1))` before loading, because the static path calls `Surface.convert()`.

- [ ] **Step 1:** Write the dump tool, then run it (from the repo root):
  `SDL_VIDEODRIVER=dummy uv run python src/quicklook/tools/dump_engine_frames.py --out src/quicklook/Tests/SpriteCoreTests/Golden
  src/apps/bitmappy/src/bitmappy/resources/sprites/small_heart.toml slime-jump.toml slime-jump-alpha.toml
  src/games/drawing-fire/src/drawing_fire/sprites/soldier.toml src/games/brave-adventurer/src/brave_adventurer_papyrus/sprites/player.toml
  <the four hand-written fixtures>`.
  Expected: one `.json` per input, no warnings. Any warning the engine logs about ragged rows is expected **only** for the ragged fixtures.
  Read and understand any other warning before going on.
- [ ] **Step 2: Write the failing test** `everyGoldenFixtureMatchesTheEngine`, parameterized over the `Golden/*.toml` files.
  It asserts animation names and order, frame count, width, height, durations (within 1e-9) and every pixel's RGBA.
  It skips the `loop` assertion when the JSON value is `null`.
- [ ] **Step 3:** `swift test`. Expected: PASS. If any fixture fails, it's a real disagreement. The CRLF fixtures
  are the likely ones (Review Focus 1). Fix the Swift side to match `tomllib` (e.g. normalize how TOMLDecoder hands back
  newlines) and add a unit test in Task 2's file for whatever the cause was. Never edit a `.json` by hand.
- [ ] **Step 4:** `swift test`. Expected: all pass, no warnings.
- [ ] **Step 5: Checkpoint.**

### Task 5: Rendering and the animation clock

**Files:**
- Create: `src/quicklook/Sources/SpriteCore/SpriteRenderer.swift`
- Create: `src/quicklook/Sources/SpriteCore/AnimationClock.swift`
- Test: `src/quicklook/Tests/SpriteCoreTests/SpriteRendererTests.swift`, `AnimationClockTests.swift`

**Interfaces:**
- Consumes: `Sprite`, `SpriteFrame`, `RGBA.isTransparent`
- Produces:
  - `public enum SpriteRenderer`:
    - `static func image(for frame: SpriteFrame) -> CGImage`: native size, sRGB, premultiplied alpha; transparent (R3) → `(0,0,0,0)`
    - `static func largestFrameSize(of animation: SpriteAnimation) -> CGSize`
    - `static func integerScale(contentSize: CGSize, fitting available: CGSize) -> Int`: `max(1, floor(min(aw/w, ah/h)))`
    - `static func thumbnailImage(for sprite: Sprite, maximumSize: CGSize) -> CGImage`: first frame of the first animation, scaled
      by `integerScale` when it fits. Otherwise it is scaled down to fit (aspect kept, `interpolationQuality = .none`) and centered on a transparent canvas of
      the scaled size.
    - `static func checkerboardImage(cellSize: Int) -> CGImage`: a 2×2-cell pattern tile for the preview background
  - `public struct AnimationClock: Sendable { public init(durations: [Double], loop: Bool); public func frameIndex(at elapsed: Double) -> Int; public func nextChange(after elapsed: Double) -> Double? }`.
    Durations ≤ 0 count as 0. If the total is 0, the index is always 0 and `nextChange` is `nil`. A non-looping clock returns the last index
    once the elapsed time passes the total, and `nextChange` is `nil`.

- [ ] **Step 1: Write the failing tests:**
  - `opaquePixelKeepsColor`, `magentaPixelIsClear`, `halfAlphaIsPremultiplied` (read the CGImage's bytes back)
  - `integerScaleFloors` (16×16 in 100×60 → 3), `integerScaleNeverBelowOne` (64×64 in 10×10 → 1)
  - `largestFrameSizeUsesWidestAndTallest` (frames 8×16 and 16×8 → 16×16)
  - `thumbnailIsFirstFrameScaled` (2×2 sprite, max 64×64 → 64×64 image, pixel (0,0) equals the source's top-left)
  - `thumbnailOfLargeSpriteScalesDownWithoutBlending` (256×256 checker of two colors, max 100×100 → every output pixel is one of the
    two source colors)
  - `clockLoops` (durations `[0.5, 0.25]`, loop: at 0 → 0, 0.6 → 1, 0.76 → 0), `clockStopsWithoutLoop` (at 10 → 1, `nextChange` nil),
    `clockAllZeroStaysOnFirstFrame` (returns quickly, index 0), `clockNextChange` (at 0.1 → 0.5)
- [ ] **Step 2:** `swift test`. Expected: FAIL.
- [ ] **Step 3:** Implement with CoreGraphics (`CGContext`, `CGImage`); no AppKit in `SpriteCore`.
- [ ] **Step 4:** `swift test`. Expected: all pass, no warnings.
- [ ] **Step 5: Checkpoint.**

### Task 6: Xcode project, host app, preview extension

**Files:**
- Create: `src/quicklook/App/project.yml` (XcodeGen). Targets:
  - `SpritePreview` (application). A one-window app explaining how to enable the extensions, with a button that opens
    `x-apple.systempreferences:com.apple.ExtensionsPreferences`.
  - `SpritePreviewExtension` (app-extension, `com.apple.quicklook.preview`).
  - `SpriteThumbnailExtension`, which Task 7 adds.
  - The extensions are embedded in the app, and both link the local package `..` product `SpriteCore`. App Sandbox is on for the extensions. `CODE_SIGN_IDENTITY: "-"`, no team.
- Create: `src/quicklook/App/HostApp/SpritePreviewApp.swift`
- Create: `src/quicklook/App/PreviewExtension/PreviewViewController.swift`, `SpritePlayerView.swift`, `PlainTextView.swift`, `Info.plist`,
  `PreviewExtension.entitlements`
- Create: `src/quicklook/Makefile`, with targets `test` (`swift test`), `project` (`xcodegen --spec App/project.yml`),
  `build` (`xcodebuild -project App/SpritePreview.xcodeproj -scheme SpritePreview -configuration Release -derivedDataPath ~/Library/Developer/Xcode/DerivedData/SpritePreview build`),
  `install` (copy the built `SpritePreview.app` to `/Applications`, `open` it once, `qlmanage -r`, `qlmanage -r cache`) and `uninstall`.

**Interfaces:**
- Consumes: `SpriteLoader`, `SpriteRenderer`, `AnimationClock`
- Produces:
  - `PreviewViewController: NSViewController, QLPreviewingController`, using the async `preparePreviewOfFile(at:)`. On `.sprite`
    it shows `SpritePlayerView`. On `.notSprite` it shows `PlainTextView` (an `NSScrollView` + read-only `NSTextView`, monospaced system font,
    UTF-8 with a Latin-1 fallback). On `.failed(reason)` it shows a one-line red banner with the reason, above `PlainTextView`.
  - Info.plist `NSExtensionAttributes`: `QLSupportedContentTypes = [public.toml]`, `QLSupportsSearchableItems = false`.
  - `SpritePlayerView: NSView` draws the checkerboard background and a layer holding the current frame.
    - The layer uses `magnificationFilter = .nearest` and is sized to `largestFrameSize × integerScale`, centered.
    - (Superseded 2026-10-29 by the film strip, spec goal 6.) When there is more than one animation, it shows a label row along the bottom (an `NSSegmentedControl` of names). Choosing one restarts its clock.
    - It starts playing the first animation as soon as it's in a window, driven by `NSView.displayLink(target:selector:)` or a `Timer` scheduled at `nextChange`, and stops when removed from the window.
    - It recomputes the scale on resize.

- [ ] **Step 1:** `cd src/quicklook && direnv allow` (the owner trusts it once). `src/quicklook/.envrc` installs xcodegen with Homebrew when it is missing. Check that `xcodegen --version` prints 2.46.0 or later, then run `make project`. Expected: `App/SpritePreview.xcodeproj`
  is generated, with no warnings.
- [ ] **Step 2:** Implement the app and extension above. Then run `make build`. Expected: `** BUILD SUCCEEDED **`, with no warnings.
- [ ] **Step 3:** Run `make install`. Then check the extension is registered: `pluginkit -mAvvv -p com.apple.quicklook.preview | grep -A3 games.glitchy`
  should list the extension's path under `/Applications/SpritePreview.app`. If it's missing, enable it in System Settings
  → Login Items & Extensions → Quick Look. If macOS rejects the ad-hoc signature, **stop and tell the owner**. The fallback,
  adding a free Apple ID team, is the owner's step.
- [ ] **Step 4: Verify by hand** with `qlmanage -p` on each file below and **look at a screenshot** of each:
  - `small_heart.toml`: one crisp image on a checkerboard
  - `slime-jump.toml`: plays straight away and loops
  - `player.toml` (Papyrus, several animations): a label row; switching works
  - `soldier.toml`: the `█` glyph is transparent
  - `pyproject.toml`: monospaced text
  - a copy of a sprite with its last line cut off: the error banner and the text

  Then press space in Finder on the same files.
- [ ] **Step 5: Checkpoint.**

### Task 7: Thumbnail extension

**Files:**
- Modify: `src/quicklook/App/project.yml`. Add the `SpriteThumbnailExtension` app-extension (`com.apple.quicklook.thumbnail`), embedded in the app,
  linking `SpriteCore`, sandboxed.
- Create: `src/quicklook/App/ThumbnailExtension/ThumbnailProvider.swift`, `Info.plist`, `ThumbnailExtension.entitlements`

**Interfaces:**
- Consumes: `SpriteLoader.load(data:)`, `SpriteRenderer.thumbnailImage(for:maximumSize:)`
- Produces: `ThumbnailProvider: QLThumbnailProvider`. `provideThumbnail(for:_:)`:
  - On `.sprite` it replies with `QLThumbnailReply(contextSize:currentContextDrawing:)`, drawing the thumbnail image with `interpolationQuality = .none`.
  - On anything else it calls the handler with `nil` and an error.
  - Info.plist: `QLSupportedContentTypes = [public.toml]`, `QLThumbnailMinimumDimension = 0`.

- [ ] **Step 1:** Implement, then run `make project build install`. Expected: `** BUILD SUCCEEDED **`, with no warnings.
  `pluginkit -mAvvv -p com.apple.quicklook.thumbnail | grep -A3 games.glitchy` should list the extension.
- [ ] **Step 2: Verify by hand.** First run `qlmanage -r cache`. Then run `qlmanage -t -s 256 -o <scratch dir>` on `small_heart.toml`,
  `slime-jump.toml`, a large sprite and `pyproject.toml`, and look at the PNGs:
  - the sprites are crisp, and their transparent areas are transparent
  - `pyproject.toml` produces no custom thumbnail
- [ ] **Step 3: Check the fallback icon** (spec goal 9). Open `src/apps/bitmappy/src/bitmappy/resources/sprites/` and the repo root in Finder
  icon view, then look at the thumbnails. The sprites must show their art. `pyproject.toml` and `.taplo.toml` must show the normal TOML
  document icon, **not** a blank tile. If they come out blank, stop and report it to the owner with a screenshot before trying alternatives.
- [ ] **Step 4: Checkpoint.**

### Task 8: Docs and backlog

**Files:**
- Create: `src/quicklook/README.md`, covering:
  - what it does
  - `make test`, `make project build install`, `make uninstall`
  - enabling the extensions in System Settings
  - `qlmanage -r` / `qlmanage -r cache` / `qlmanage -p` / `qlmanage -t`
  - regenerating golden frames with `dump_engine_frames.py`
  - the ad-hoc signing caveat
- Modify: `docs/specs/2026-10-29-sprite-quicklook-design.md`. Change the status to built and note anything that changed while building.
- Modify: `plans/future-work.md`. Add a "QuickLook" section for anything left over, such as hitbox overlays, swatch variants, or a TOML syntax-highlighted
  fallback, and record any bugs found while building.

- [ ] **Step 1:** Write and update the files above.
- [ ] **Step 2:** Run `cd src/quicklook && make test build`. Expected: all tests pass, `** BUILD SUCCEEDED **`, and there are no warnings in either.
- [ ] **Step 3: Checkpoint.**
