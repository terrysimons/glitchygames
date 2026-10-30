# Sprite QuickLook

QuickLook support on macOS for GlitchyGames sprite `.toml` files:

- **Preview** (select a file in Finder, press space): a static sprite is drawn crisp on a
  checkerboard. Anything with more frames shows a film strip: one row per animation with every
  frame (its number above, its duration below) and the animation playing at the right end, the
  frame on screen outlined in blue. Every row plays straight away; long animations wrap, and many
  rows scroll. A `.toml` file that isn't a sprite (`pyproject.toml`, ...) is
  shown as plain text. A sprite file that can't be drawn shows the reason above its text.
- **Thumbnails** (Finder icon and column view, Get Info): the first frame of the first animation.
  Other `.toml` files keep their normal icon.

Sprites are drawn the way the engine draws them (`src/glitchygames/sprites/animated.py`). The golden
tests check this against frames dumped by the engine's own loader. Design:
`docs/specs/2026-10-29-sprite-quicklook-design.md`.

## Layout

- `Sources/SpriteCore/`: the Swift library that reads sprite TOML (with
  [TOMLDecoder](https://github.com/dduan/TOMLDecoder)) and draws it. Both extensions use it.
- `Tests/SpriteCoreTests/`: unit tests, plus `Golden/`, the engine's frames for real sprites.
- `App/project.yml`: the XcodeGen spec for the host app (`HostApp/`) and the two extensions
  (`PreviewExtension/`, `ThumbnailExtension/`).
- `tools/`: `dump_engine_frames.py` (golden data), `make_thumbnails.swift` (thumbnail check),
  `make_app_icon.py` (the app icon), `fixtures/` (hand-written edge-case sprites).

## Setup

`cd src/quicklook && direnv allow` once. The `.envrc` loads the repo's own `.envrc` and installs
XcodeGen with Homebrew when it's missing.

## Build, test, install

```sh
make test       # swift test
make install    # generate the Xcode project, build Release, copy to /Applications, register
make uninstall
```

`make install` opens `/Applications/GlitchyGames Sprite Preview.app` once, which registers the extensions. If
QuickLook still doesn't use them, turn them on in System Settings → General → Login Items &
Extensions → Quick Look (the app has a button that opens that page).

**Signing:** this Mac has no code-signing identity, so everything is signed ad hoc ("Sign to Run
Locally"). That's enough to run it on this Mac. If macOS ever refuses the extensions, add a free
Apple ID team in Xcode and set `DEVELOPMENT_TEAM` in `App/project.yml`.

## Checking by hand

```sh
qlmanage -r && qlmanage -r cache          # forget cached previews and thumbnails
qlmanage -p path/to/sprite.toml            # the preview window
swift tools/make_thumbnails.swift /tmp/thumbs path/to/sprite.toml pyproject.toml
pluginkit -mv | grep glitchy               # both extensions, from /Applications
```

Don't use `qlmanage -t` to check thumbnails. On current macOS it only uses the old generator
plug-ins, never app-extension thumbnail providers, and it hangs on file types it has no generator
for. `make_thumbnails.swift` asks the same way Finder does.

## Golden frames

When the engine's loader changes, regenerate the golden data from the repo root:

```sh
SDL_VIDEODRIVER=dummy uv run python src/quicklook/tools/dump_engine_frames.py \
    --out src/quicklook/Tests/SpriteCoreTests/Golden \
    src/apps/bitmappy/src/bitmappy/resources/sprites/small_heart.toml \
    src/games/drawing-fire/src/drawing_fire/sprites/soldier.toml \
    src/games/brave-adventurer/src/brave_adventurer_papyrus/sprites/player.toml \
    src/quicklook/tools/fixtures/*.toml \
    <slime-jump.toml> <slime-jump-alpha.toml>
```

The app icon is `shroom4.toml` drawn by the engine's loader on the preview's checkerboard. To
redraw it after the sprite changes (from the repo root), then `make install`:

```sh
SDL_VIDEODRIVER=dummy uv run python src/quicklook/tools/make_app_icon.py \
    src/apps/bitmappy/src/bitmappy/resources/sprites/shroom4.toml \
    src/quicklook/App/HostApp/Assets.xcassets/AppIcon.appiconset
```

The two `slime-jump` sprites live untracked in the main checkout's root. Their copies in `Golden/`
are the fixtures. Never edit a `.json` there by hand: if a golden test fails, the preview and the
engine disagree, and the fix goes in `SpriteCore`.
