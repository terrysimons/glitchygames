# Level Tools D — Bitmappy Updates

- **Date:** 2026-10-18
- **Status:** Design brief (a list of independent features; each can be its own small branch)
- **Master plan:** [Level Tools](2026-10-18-level-tools.md)
- **Ancestors:** Galimore Galibmap (2000) and GEDIT (1999)

## How this list was made

Every Galibmap/GEDIT feature was checked against the Bitmappy code on 2026-10-18. Bitmappy already
covers: eyedropper (right-click samples the canvas, Shift+right-click the screen —
`bitmappy/editor.py`), RGB sliders and a colour well (`bitmappy/slider_manager.py`), film-strip
frame copy and drag-reorder with undo (`bitmappy/frame_operations.py`, `history/commands.py`),
flood fill (`bitmappy/animated_canvas.py`), any canvas size, and PNG drag-and-drop (instead of
Galibmap's Photoshop RAW import). Not worth porting: Galibmap's hardware-info screen, file-type
detection by size, grey placeholder frames.

## Features Bitmappy lacks (with adjustments for this engine)

| # | Feature (ancestor) | Adjustment for GlitchyGames | Notes |
|---|---|---|---|
| D1 | **Visual hitbox editor** (implied by GATTRIB) | Draw and drag the sprite-level and per-frame hitbox rectangles on the canvas; show the effective hitbox (explicit → sprite default → visible-pixel fallback) and the `frame_anchor` reference point. | Highest value: hitboxes now drive collisions, terrain resolution and frame anchoring, and today they can only be edited as TOML text. |
| D2 | **Mirror / flip** (GEDIT) | Flip a frame or a whole animation horizontally or vertically, and **"Create mirrored animation"** (e.g. `right` from `left`), mirroring per-frame hitboxes too. Offer "use `hitbox_flip_x` at runtime instead" so a game can flip one stored animation rather than store both. | The ghosty sprite stores `right` as an exact mirror of `left`. |
| D3 | **Rotate** (GEDIT) | 90° / 180° / 270° for a frame or animation; for non-square canvases, either rotate the whole sprite (swapping width and height for every frame) or refuse. Rotate hitboxes with the pixels. | Wall corners, pipes, arrows. |
| D4 | **Replace colour** (Galibmap R) | Replace every pixel of one colour (including alpha) with another, scoped to frame / animation / whole sprite, as one undoable command; also "merge colours" to shrink the palette. | Palette swaps and enemy variants; flood fill only changes connected pixels. |
| D5 | **More colour wells with swap** (Galibmap's three wells, C cycles) | A primary/secondary pair with a swap key (X in most editors), plus a small recent-colours row. Check how this fits the multi-controller mode, where each controller may already carry its own colour. | Quick shading. |
| D6 | **Directional sprite templates** (Galibmap's 9-frame plan: front / away / side × still / walk, side mirrored) | "New character" creates animations named like ghosty (`front`, `back`, `left`, `right`, or `walk_down` etc.) with a chosen frame count, `frame_anchor = "bottom"` for walkers, and the mirrored side generated via D2 or set to runtime flip. | One click to lay out a walking character. |
| D7 | **Tile mode** (Galibmap object mode: fixed 32×32) | Open or create a tile from a tileset (sub-plan C): canvas size locked to the tileset's tile size, with a neighbour preview (the tile repeated 3×3) to check seams. | Easier after sub-plans A and C. |
| D8 | **Frame alignment command** (from this branch's frame-anchoring work; recorded as item 38 in `plans/future-features.md`) | Permanently re-align an animation's frames to one of the nine `FrameAnchor` points, rewriting pixels and per-frame hitboxes in a fixed canvas; refuse shifts that would push pixels off the canvas; preview; one undo step; clear `frame_anchor` afterwards. | Fixes top-aligned art (like the Papyrus player) once instead of at runtime. |
| D9 | **Sprite metadata panel** (Galibmap's object attributes, narrowed) | Edit art-intrinsic data only: name, description, frame timing per animation and per frame, `frame_anchor`, hitboxes (D1). Game-use data (solid, item, damage) belongs in tilesets (sub-plan C), not in the sprite. | Keeps one source of truth per kind of data. |
| D10 | **Transparent key handling** | TOML sprites keep magenta as an *opaque* pixel unless a game converts it (Papyrus does), so the engine's visible-pixel hitbox default does nothing for them (final-review finding M2 on `feature/debug-overlay`). Decide whether the loader should convert the magenta key to alpha for all TOML sprites; Bitmappy then previews exactly what games draw. | Engine-level decision with a Bitmappy-visible effect. GEDIT allowed any colour as the key; keep magenta. |
| D11 | **Fit canvas to sprite / trim canvas to content** (new, 2026-10-18; replaces the unreachable panned-viewport save, which cropped content) | **Grow:** measure the union of every frame's visible pixels across all animations, plus explicit hitboxes; grow each axis independently, never below the current size, rounded by a setting: **power of two** (default; content 10×10 on an 8×8 canvas → 16×16), **multiple of 8 / tile size** (keeps 32×48 characters at 32×48), or exact. Move **all frames by one shared offset**, never each frame separately (separate centring would make the animation jitter): centred by default, or placed by `frame_anchor` (a `BOTTOM` walker keeps its feet on the bottom row and grows upward). Shift per-frame and sprite-level hitboxes by the same offset; the anchor reference updates itself. One undoable command. **Trim:** the same in reverse — shrink to the union of all frames with the same rounding and shared offset (e.g. after AI generation leaves wide margins). **Triggers:** an explicit "Fit canvas to sprite" / "Trim canvas to content" command, plus an offer on save when content extends past the canvas (instead of losing it). Live growing while panning is deferred until the explicit version has been used. **Refused in tile mode (D7)** with a message, since tiles are locked to the tileset size. | Makes panning safe: content moved past the edge is never lost. A game that assumes a fixed sprite size in code is a reason to confirm a grow rather than do it silently. |

## Fixed on `feature/debug-overlay` (not part of this plan)

Saving reset frame timings and loop flags (BUGS.md #34), converted the visible-pixel fallback into
explicit hitboxes (#35), blanked static sprites with RGBA colours (#36, `toadstool.toml`), and
dropped the single-frame description (#39), the `[[transition]]` sections (#44) and, in Bitmappy's
single-frame save, the name, frame anchor and sprite hitbox (#43). Still open and related: #45
(renaming an animation drops its timing and loop flag).

## Suggested order

D1 (hitbox editor) → D2 + D3 (mirror and rotate, sharing transform code) → D4 + D5 (colour tools)
→ D10 (decide the key) → D11 (fit/trim canvas; shares the shared-offset code with D8) → D6
(templates, uses D2) → D8 (alignment) → D9 (metadata panel) → D7 (tile mode, after sub-plans A
and C).

## Testing

Each operation as an undoable command with unit tests (pixels and hitboxes before and after, undo
restores exactly); a load → edit → save → reload round trip for each; headless scripted editor
sessions for D1 and D6.
