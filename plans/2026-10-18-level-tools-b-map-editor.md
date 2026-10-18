# Level Tools B — Mapsmith (map editor)

- **Date:** 2026-10-18
- **Status:** Design brief
- **Master plan:** [Level Tools](2026-10-18-level-tools.md)
- **Depends on:** [A — Tilemap format and runtime](2026-10-18-level-tools-a-tilemap-format.md)
- **Ancestors:** Galimore Mapedit (2000), GMAP (1999)

## Goal

An editor for the sub-plan A map format, built on the same engine UI as Bitmappy (scenes, sliders,
dialogs, undo/redo, controller support), so it runs anywhere GlitchyGames runs.

## Features (from Mapedit, plus what Bitmappy already does well)

- **Map view** with scrolling and zoom, drawn by the sub-plan A runtime (what you see is what the
  game draws).
- **Tileset palette:** pick tiles from one or more tilesets; tooltips with tile name and properties.
- **Layers:** any number of tile and object layers in z-order around the actor layer, each with
  visibility and lock toggles (generalises Mapedit's fixed background/foreground/object tabs and
  1F/2F floors; see the audit in the master plan).
- **Object tools (first priority, since today's games are object-based):** place, move, resize and
  delete typed objects (ground, wall, platform, elevator, spawn, enemy, pickup, exit, trigger) with a
  properties panel driven by the project schema; snap to pixel or grid; duplicate.
- **Brushes:** sizes 1–4 (Mapedit), eraser (tile 0), flood fill and rectangle fill (from Bitmappy),
  eyedropper (right-click picks a cell's tile, as in Bitmappy).
- **Property paint mode:** stamp named properties from the schema (solid, one_way, hazard,
  climbable, water, game-defined…) onto tile cells; right-click picks up a cell's properties;
  overlays drawn in the debug overlay's palette (not Mapedit's magenta, which is our transparency
  key).
- **Exits and spawns:** draw an exit region (or pick a map edge), choose the target map and one of
  its named spawn points and a transition; follow an exit to open the target map (GMAP's F7).
- **Auto-tiling (later):** terrain brushes that pick edge and corner tiles (bitmask / Wang tiles) —
  the one major feature Galimore never had.
- **Undo/redo** through Bitmappy's command-pattern history (reuse, don't copy).
- **Playtest:** launch the map in a test scene with a placeholder player and the debug overlay on.
- **Controllers:** the multi-controller canvas mode Bitmappy already has, if cheap to reuse.

## Not in scope

Pixel editing (Bitmappy), building tilesets (sub-plan C), scripting.

## Testing

Editor operations as undoable commands with unit tests; load → edit → save round trips; a headless
scripted session that paints a small room and checks the saved TOML.

## Open questions

Separate app (`uv run mapsmith`) or a Bitmappy mode; how much of Bitmappy's editor scene to extract
into shared components first (palette, history, dialogs).
