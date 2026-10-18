# Level Tools A — Tilemap Format and Runtime

- **Date:** 2026-10-18 (revised the same day after the audit in the master plan)
- **Status:** Design brief
- **Master plan:** [Level Tools](2026-10-18-level-tools.md) (see "Audit of the borrowed ideas")
- **Roadmap:** `plans/engine-audit.md` #11; feeds #1 (solid collision) and uses #6 (world space)

## Goal

A tileset format and a map format in TOML, an engine loader, and rendering and collision support,
so a game can build a level from data instead of code. The format must express **today's games
first**: Brave Adventurer and Clockwork Keep levels are pixel-positioned objects (ground segments,
walls, platforms, elevators, spawns, enemies, pickups), so object layers are first-class and tile
layers are optional.

## Map format (sketch)

A map is an ordered list of layers. Each layer is a **tile layer** (grid) or an **object layer**
(named, typed objects at pixel positions). `z` orders layers relative to the actor layer (`z = 0`):
negative draws behind actors, positive in front.

```toml
[map]
name = "pharaoh_path_screen_4"
width = 800                 # pixels; tile layers derive their cell counts from tile size
height = 480
tilesets = { desert = "tiles/desert.toml" }
properties_schema = "maps/properties.toml"   # project-wide property names and types

# --- An object layer: what Brave Adventurer's ScreenData holds today ---
[[layer]]
name = "terrain"
kind = "objects"
z = 0

[[layer.object]]
type = "ground"
rect = [0, 400, 350, 80]
properties = { solid = true }

[[layer.object]]
type = "ground"
rect = [450, 400, 350, 80]
properties = { solid = true }

[[layer.object]]
type = "wall"
rect = [400, 352, 32, 48]
properties = { solid = true }

[[layer]]
name = "actors"
kind = "objects"
z = 0

[[layer.object]]
type = "enemy"
point = [600, 400]
properties = { species = "cobra", patrol = 80 }

[[layer.object]]
type = "pickup"
point = [400, 320]
properties = { item = "gold_scarab" }

[[layer.object]]
type = "spawn"
name = "from_left"          # named spawn points are exit targets
point = [16, 400]

[[layer.object]]
type = "exit"
rect = [796, 0, 4, 480]     # exits are regions (here the right edge)
properties = { to = "pharaoh_path_screen_5", spawn = "from_left", transition = "slide_left" }

# --- An optional tile layer (decoration or grid-based games) ---
[[layer]]
name = "backdrop"
kind = "tiles"
z = -1
tile_width = 32
tile_height = 32

[layer.legend]              # per-layer legend; "." = empty
"." = 0
"s" = { tileset = "desert", id = 1 }
"t" = { tileset = "desert", id = 2 }

[layer.grid]                # chunked rows keep wide maps readable; encoding = "csv" is the
rows = """                  # escape hatch when a layer needs more tiles than readable characters
sssssssssssssssssssssssss
....t.........t..........
"""

[layer.cell_properties]     # per-cell overrides on a tile layer (property paint)
legend = { "#" = { solid = true }, "~" = { water = true } }
grid = """
.........................
"""
```

### Properties

- Open, typed vocabulary declared in a project schema (name, type, default, description), so typos
  are lint errors. A small common core ships with the engine: `solid`, `one_way`, `hazard`,
  `climbable`, `water`. Games add their own (`species`, `patrol`, `item`…).
- Where they live: tile defaults (in the tileset) < cell overrides (tile layer) < object properties.

### Collision rules

- Object rects are used exactly as authored.
- A tile's collision shape is its **full cell**, unless the tile's sprite defines an explicit
  hitbox. It never uses the visible-pixel fallback (a grass tile with a transparent top row is still
  solid at the cell top).
- Solid cells and rects are merged into as few rectangles as possible and registered in
  `CollisionManager` layers named by property; this hands off to the solid-collision design (#1).

## Tileset format (sketch)

```toml
[tileset]
name = "desert"
tile_width = 32
tile_height = 32

[[tile]]
id = 1                      # explicit and permanent
sprite = "sprites/sand.toml"
name = "sand"
properties = { solid = true }

[[tile]]
id = 2
sprite = "sprites/torch.toml"   # an animated sprite animates in the map
name = "torch"

[[tile]]
id = 3
retired = true              # tombstone: ID 3 can never be reused
```

## Runtime

- `glitchygames/tilemaps/`: `Tileset`, `Tilemap`, `TileLayer`, `ObjectLayer` loaders with clear
  errors (unknown tile ID, retired ID used, ragged rows, legend character missing, unknown property
  or wrong type, exit to a missing spawn).
- **Objects become game entities through a registry:** a game maps object `type`s to factories
  (`"enemy" → make_enemy(properties)`), so the format stays game-neutral.
- Rendering: one pre-rendered surface per static tile layer (redrawn only when a tile changes);
  animated tiles per frame; drawn through `Camera2D` / the engine world space (#6).
- Exits: `tilemap.exit_at(rect)` returns the target map, spawn and transition, for use with
  `transition_to`.
- Debug overlay: a tilemap panel (or the existing `debug_draw` hook) showing collision rects,
  property cells, exits and spawn points.
- **Tiled JSON import** (`.tmj`): map Tiled tile and object layers onto this format, so existing
  Tiled maps work and can be compared against.

## Migration path

1. Convert one Brave Adventurer screen and one Clockwork Keep floor to object-layer maps; prove the
   game plays identically (same collision rects, same spawns) with tests that compare against the
   current `ScreenData` / `FloorData`.
2. Add tile layers for decoration.
3. Import one Galimore map (`house.map`) as the tile-layer integration fixture.

## Testing

Round-trip load → save → load; every error case; rendering a known map pixel-exact; tile and object
collision rects (including the full-cell rule for tiles with transparent edges); merged rectangles;
an animated tile advancing; exits resolving to spawns; the migration equivalence tests above.

## Open questions

Chunking for very large maps; per-layer parallax (Brave Adventurer already has camera-driven
parallax layers); whether moving platforms and elevators are objects with behaviours or plain
objects the game animates.
