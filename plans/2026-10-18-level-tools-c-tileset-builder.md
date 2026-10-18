# Level Tools C — Tilesmith (tileset builder)

- **Date:** 2026-10-18
- **Status:** Design brief
- **Master plan:** [Level Tools](2026-10-18-level-tools.md)
- **Depends on:** [A — Tilemap format and runtime](2026-10-18-level-tools-a-tilemap-format.md)
- **Ancestors:** Galimore Galimake (2000), MAKEDAT and GATTRIB (1999)

## Goal

Build and maintain sub-plan A tilesets from a folder of sprite TOML files, keeping tile IDs stable
forever, and give each tile its game data (properties) without editing code.

## Features

- **The tileset file is the source of truth** (audit in the master plan): Tilesmith edits and lints
  it; it never regenerates it from scratch, so hand edits are never lost.
- **Build / update** (Galimake's job, now an assistant): scan a folder of tile sprites, add new ones
  with the next free ID, keep existing IDs, and mark tiles whose sprite file disappeared as
  `retired = true` (Galimake's "blank, don't delete" rule, but explicit). Never renumber.
- **Identity by file, not pixels:** Galimake matched tiles by pixel equality, so two identical tiles
  collapsed into one and editing a tile's art looked like delete + add. Match by sprite path
  instead (rename-aware via a stored content hash as a fallback hint).
- **Lint:** sizes match the tileset's tile size; no duplicate IDs; no retired ID referenced by any
  map in the project; every map legend entry resolves; ragged sprite rows (the gold scarab bug);
  report unused tiles.
- **Attributes** (GATTRIB's job): a small UI, or a Bitmappy panel, to edit each tile's name and
  properties (unpassable, deep, light level, damage…), with a project-wide property schema so typos
  are caught.
- **CLI first:** `uv run tilesmith build tiles/`, `uv run tilesmith lint`; a UI panel later.
- **Import:** a converter for Galimore `.dat` tilesets (via the survey's decoder) as the first real
  test data.

## Testing

Build twice with no changes → identical file; remove a tile → retired, IDs unchanged; add a tile →
next free ID; lint error cases; Galimore import round trip.

## Open questions

The property schema format (shared with sub-plan A and Mapsmith). Recommendation for where tile
game data lives: in the **tileset** (how a tile is *used* — solid, hazard, item), not in the sprite
file, which keeps only art-intrinsic data (pixels, timing, hitbox, frame anchor). The same sprite
can then be solid in one tileset and decorative in another. Bitmappy's metadata panel (sub-plan D)
edits only the sprite side.
