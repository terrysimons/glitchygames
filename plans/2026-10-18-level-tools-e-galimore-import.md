# Level Tools E — Translating Galimore Forward

- **Date:** 2026-10-18
- **Status:** Design brief
- **Master plan:** [Level Tools](2026-10-18-level-tools.md) (see "Design for today's constraints")
- **Depends on:** the existing sprite format (now); [A — Tilemap format](2026-10-18-level-tools-a-tilemap-format.md) (maps)
- **Source data:** `../galimore_files/` (read-only), surveyed in `docs/galimore.md`
  (which documents every binary layout). A read-only decoder written during the survey (kept in
  the session scratchpad, not in the repo) renders all of it to PNG; review it before reuse.

## Goal

Bring Galimore's real content into GlitchyGames' formats, the same way the sprite format replaced
older ones: not by reading the 1999 formats at runtime, but by converting them once into the modern
formats. The converted content becomes example assets and test fixtures for sub-plans A–C, and a
check that the new formats can express everything the old tools could.

## What gets translated, and how

| Galimore data | Old encoding (1999 constraint) | New form |
|---|---|---|
| 2000 tiles (`.bg`, `.fg`, `.get`; 2332 B) | 32×32 RGB565, column-major, `0xF81F` key, empty attribute block | Static sprite TOML (RGB888, magenta key, palette legend); one tileset per `.dat` with explicit IDs = the old 1-based indices; empty attributes dropped |
| 2000 sprites (`.spr`; 49,152 B) | 16 fixed 32×48 frames, unused ones grey | Animated sprite TOML using the directional naming from Bitmappy updates D6 (`front`, `back`, `left`, `right`, walk variants); grey frames dropped; `frame_anchor = "bottom"`; mirrored side frames either stored or marked for runtime flip |
| Photoshop raws (`.raw`) | Headerless RGB, size implies dimensions | PNG (for Bitmappy import) or sprite TOML |
| 2000 maps (`.map`; 114,692 B) | 64×64 × 2 floors, `UINT8`/`UINT16` layers, 64-bit mask per cell | Sub-plan A map: tile layers per old floor/layer with `z` order; mask bits → named properties (`unpassable_*` → `solid`, `deep` → `water`, `bridge`, `chasm` → `hazard`, `pushable`, `layer_switch` → a z-transition region); empty cells and unused layers dropped |
| 1999 bitmaps (1312 B) | 256-colour palette indices, per-bitmap transparent slot | Static sprite TOML with the palette resolved to RGB (palette from GTORAW's table or `GALIMORE PALLETE.GIF`) and the transparent slot → magenta |
| 1999 sprites (9262 B) | 8 frames of 32×32 (down/up/left/right × 2) | Animated sprite TOML (`walk_down`, `walk_up`, `walk_left`, `walk_right`) |
| 1999 maps + exits (1458 / 2808 B) | 15×15 × 5 layers (background, wall, object, scenery, door), `Exit{name, X, Y}` | Sub-plan A map: tile layers plus an object layer; walls → `solid`; doors → objects; exits → exit regions pointing at named spawn points in the target map (the best test of the rooms-and-exits design) |
| 1999 tile attributes (`THINGS.H` bits) | WALL, LIQUID, ITEM…, BURNABLE, LOCKABLE… | Entries in the project property schema; per-tile values in the tilesets |
| Sounds | Mac System 7 resource forks only | Out of scope until extracted (needs resource-fork tooling such as `DeRez`) |

## Shape of the converters

- A small read-only `scripts/galimore_import.py` (or a package under `scripts/`), never executed
  against anything but the data files; each format gets a decoder with tests built from the real
  files' exact sizes and known renders (the survey verified `house.map` renders as a cottage and
  `pockets.spr` as Pockets' walk frames).
- Output goes to an examples folder (e.g. `glitchygames/examples/galimore/`) with a README naming
  the source archive and date of each asset.
- Lossy steps are reported, not silent: colour quantisation for tiles with many colours, dropped
  empty attributes, unmapped mask bits.

## Proving the new formats

For each converted map, render it with the sub-plan A runtime and compare against the decoder's PNG
render of the original (pixel-exact for tile layers); check that every old exit resolves to a spawn
and every old mask bit became a property or is listed as unmapped.

## Open questions

Whether to also convert the design documents (story, regions, spells) into readable Markdown for a
future Galimore remake; licensing of third-party reference material in the archives (the FF3 tile
rips and the sound samples should not be redistributed).
