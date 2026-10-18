# Galimore (1998–2001): what it is and how its tools work

A survey of the Galimore project (1998–2001), the author's earlier game and its tools, made on
2026-10-18 to inform GlitchyGames' level tools (`plans/2026-10-18-level-tools.md`).

Conventions: `SRC/` = the original files (`galimore_files/`, kept outside this repository);
`X/` = where the survey extracted each archive (one directory per archive). **[read]** = read
directly in a file; **[inferred]** = concluded from sizes, layouts or context. `R/` = PNG renders
the survey decoded from the original data with a small read-only decoder, used to confirm the
binary layouts below (the decoder and renders are not in this repository). Nothing from the
archives was executed.

## TL;DR
- **Not a Mac game.** Galimore is a top-down **tile RPG** ("similar to Final Fantasy 3 (English) or
  Zelda", `Galimore Clean Up/Old Galimore Folder/Galimore Archive/public_html copy/index.html`)
  [read] for **MS-DOS**, developed on an iMac (Photoshop 5.02 for art, Virtual PC for code: "Yeah,
  I'm using a Mac to write a PC game", `public_html copy/development.html`) [read]. Hence the
  resource forks, MacBinary `.bin`, CR line endings and `ƒ` folder names.
- **Two engine generations:**
  1. **1999, Borland C++ 16-bit DOS**: BGI `SVGA256.BGI`, 256 colours, XMS. A playable
     `GALIMORE.EXE` plus tools GEDIT, GMAP, GATTRIB, MAKEDAT, GTORAW/RAWTOG
     (`X/CU_galisource072399/`) [read].
  2. **Aug 1999 – Aug 2000, DJGPP (gcc 2.8.1) + Allegro 3.9.32 WIP**, 640×480 at 16/15-bit colour.
     Only the toolchain exists: **Galibmap** (bitmap/sprite editor), **Mapedit** (map editor),
     **Galimake** (data packer) and a fire-effect demo. The new game was "Not yet started, but should
     use most of the mapeditor engine" (`development.html`) [read].
- **Successor:** in Aug 2000 the code was relicensed (LGPL) as **"RPG Tools" / "Phosphor"**, a
  SourceForge map editor (`Galimore/Old Galimore Folder/RPG Tools Code/`) [read]; only headers and
  a Makefile exist (no rendering code; graphics were Allegro 2D, with no OpenGL anywhere).
- **Formats:** every file is a raw `fwrite` dump of a C++ object: no header, no version,
  little-endian, compiler-specific padding. **File type is detected purely by size** (2332 / 49152 /
  3072 / 4608 bytes). All are fully decoded in §2.

---

## 1. Inventory

### 1.1 Top-level items
| Item | Date | What it is |
|---|---|---|
| `Galimore.zip` (50.8 MB, 882 entries) | 2001-04-16 | Master backup of `Galimore/`: `bitmap.zip`, `mapedit.zip`, `Galimore Archive (08-00).zip`, `Old Galimore Folder/`, `Programming Archive/`. `Galimore/` is the same tree unpacked (880 vs 882 files; the gap is MacBinary/`Icon\r`/`ƒ` artefacts) [read]. |
| `Galimore/` | 2000–2001 | The unpacked master. Newest code: `Old Galimore Folder/Galimore Source as of 7_31_00/` (to 2000-08-01) and `Old Galimore Folder/RPG Tools/` (same tree with LGPL headers; `g_map.h` 2000-08-03) [read]. |
| `Galimore Clean Up/` | 2011-06 | Reorganised copy with several archives unpacked; adds `mapedit (Binary).zip` and `bitmap (Binary).zip` [read]. |

### 1.2 Archives (checked with md5)
| Archive | Date | Contents and notes |
|---|---|---|
| `Galimore Archive (08-00).zip` (both copies) and `Galimore Archive July 12.zip` | 2000-07-12/13 | **Byte-identical** (17,773,685 B); "08-00" is a copy/rename. June 2000 source snapshots, specs, sprites. |
| `Galimore Source 7:12:00.zip` | 2000-07-12 | 79 files: flat source, `.bg/.fg/.raw` tiles, `bg/fg/get.dat`, `house/map/test.map`, RHIDE `.gpr/.gdt`, `.o`. Identical to the unpacked "as of 7_12_00" folder. |
| `Programming Archive/codebackup.zip` (both identical) | zipped 2000-09-21, contents **2000-06-04/05** | `WINDOWS/Desktop/Complete/` (89 files, early-June source + data with `mapedit.exe`, `galibmap.exe`, `galimake.exe`) and a second desktop folder (11 files, a copy of the "GUI Shell" template). **Older** than the July trees despite the name. |
| `mapedit (Binary).zip` = `Galimore.zip/Galimore/mapedit.zip` | 2000-09-05 | Identical. `mapedit.exe` (DJGPP COFF; "Allegro 3.9.32 (WIP), djgpp", gcc 2.8.1), `bg.dat` (25 tiles), `fg.dat` (29), `get.dat` (2), `house/map/test.map`. |
| `bitmap (Binary).zip` = `Galimore.zip/Galimore/bitmap.zip` | 2000-06-15 | Identical. `galibmap.exe` and `pockets.spr` (49,152 B, the hero sprite). |
| `060400`, `060500`, `060600`, `061300`, `061500`, `6-29-00` `.zip` | June 2000 | Daily snapshots (48 → 164 files); copies elsewhere identical. `6-29-00` first has `house.map`, 29 fg / 25 bg tiles, `flame.gdt`. |
| `Galimore Archive May 2000.zip` | 2000-05-31 | `complete Folder/` (48 source files), `FF3 Tiles/` (10 reference tiles), `Galimore Specs/`, nested `gali.zip`, `gbe_4_17_00.zip`, `gme_4_17_00.zip` (**not extracted**). |
| `COMPLETE.ZIP` | 2000-07-12 | Same sources with DOS 8.3 names (zipped inside DOS/Virtual PC) [inferred]. |
| `galisource072399.zip` | 1999-07-23 | **1999 Borland/BGI generation**: `GALIMORE.CPP`; GEDIT/GMAP/GATTRIB/MAKEDAT/GTORAW/RAWTOG/PATCH `.CPP` + `.EXE`; 70 bitmaps; `.DAT` packs; `.SPR` sprites; maps. |
| `public_html copy/public_release/galimore07xx99.zip`, `pics.zip` | July 1999 | Public 1999 builds (`GALIMORE.EXE`, GEDIT/GMAP/GATTRIB, `.DAT`, `SVGA256.BGI`, `HGXMOUSE.EXE`); `072699` ships `GALIMORE.CPP`. |
| `public_html copy/betas/gali.zip` | 2000 | Beta `mapedit.exe` + `galibmap.exe`. |
| `flame.zip`, `FIRE.ZIP`, `galimake.zip` | 2000-06/07 | `flame.exe`, `FIRE.CPP`, `galimake.exe`. |
| `102599.zip` = `102599 (src).zip` | 1999-10-25 | Single-file-era `galibmap.cpp`, `gcommon.h`, `button.h`, `osinfo.h`. |

**Source chronology:** 1999-07 BGI (`galisource072399`) → 1999-10 `102599` → 2000-04 `gbe/gme_4_17_00`
→ 2000-05-31 May archive → 2000-06-04/05 `codebackup` → June daily zips → 2000-07-12 `Source
7:12:00` / `COMPLETE.ZIP` / `Archive July 12` (= `08-00`) → **2000-07-31/08-01 `Galimore Source as of
7_31_00` (newest Galimore code)** → 2000-08-03 `RPG Tools/` (LGPL) → 2000-08-07 `RPG Tools Code/`
(Phosphor) → 2000-09-05 `mapedit (Binary)` built → 2001-04-16 `Galimore.zip`.

**7_12 → 7_31:** flat directory split into `src/ include/ bg/ fg/ get/ raw/ Backup/`; "cross-platform"
`exists`/`file_size` in `g_io.cpp` (later commented out); a `GALIMAKE_STUB` hack in `gmore_raw.cpp`;
small fixes in galibmap, g_data and mapedit.

### 1.3 File counts (2,301 originals)
Art: 845 `.raw`, 203 `.fg`, 192 `.bg`, 46 `.gif`, 26 `.psp`, 19 `.psd`, 14 `.get`, 3 `.spr`, 4 `.big`.
Code: 297 `.h`, 293 `.cpp`, 75 `.o`, 25 `.gpr` + 25 `.gdt` (RHIDE), 14 `.exe`. Other: 34 `.zip`,
11 `.map`, 10 `.dat`, 19 `.html`, 8 `.log`, ~21 extension-less Mac sound files. `.raw` sizes:
675 × 3072 (32×32 RGB), 44 × 4608 (32×48 RGB), 118 × 768 (16×16 RGB), 4 × 6144, 4 × 4170.

### 1.4 Not extracted / unreadable / skipped
- Zip members inside `ƒ` folders failed ("Illegal byte sequence"); their unpacked copies were read.
- `060400.zip` member `test<non-ASCII>` (a 49,152 B sprite).
- Nested `gbe_4_17_00.zip`, `gme_4_17_00.zip`, `gali.zip` (May 2000 archive).
- No `unar`/`lsar`; no StuffIt/BinHex archives found in scope.
- **Sounds:** data forks are 0 bytes; audio is only in resource forks (`sfil`, System 7 sound).
- **ClarisWorks design docs** read via `strings` only (fragmentary).
- `.psd`/`.psp`/`.big` identified, not viewed.
- **Skipped as personal:** a personal page in `public_html copy/` and an e-mail contacts file in
  `RPG Tools Code/`.

---

## 2. Tools and file formats
All written with `ofstream::write((char*)&obj, sizeof(obj))`, little-endian x86.

### 2.1 Galibmap: bitmap and sprite editor (2000)
Sources `src/galibmap.cpp`, `src/bmap_gui.cpp`, `src/gmore_raw.cpp`, `src/g_object.cpp`,
`src/g_sprite.cpp`; binary `X/bitmap_Binary/galibmap.exe`.
- Space toggles object mode (8 frames of 32×32) and sprite mode (16 frames of 32×48).
- 6× zoomed canvas: left-drag paints, right-drag eyedropper; drag frames in the strip to copy or
  reorder.
- R/G/B sliders, three colour wells (C cycles, R replaces colour 2 with colour 1); New / Save / Load
  / Quit; keys 1–8, N, L, S, Esc.
- Load branches purely on `file_size`: 2332 → object, 49152 → sprite, 3072 → raw tile, 4608 → raw
  sprite frame (the file browser filters by the same sizes).

**GALIMORE_OBJECT (tile/object), 2332 bytes** (`.bg`, `.fg`, `.get`):
| Offset | Size | Field |
|---|---|---|
| 0 | 2048 | `INT16 array[32][32]`, **`[x][y]`** (offset (x·32+y)·2), **RGB565**; `0xF81F` = transparent |
| 2048 | 21 | objectName |
| 2069 | 1 | objectType |
| 2070 | 1 | objectState |
| 2071 | 1 | objectSpecial |
| 2072 | 2 | objectIsUsableBy (UINT16) |
| 2074 | 1 | objectWeight |
| 2075 | 256 | objectDescription |
| 2331 | 1 | pad |

The attribute block is all zeros in every shipped `.dat` (never authored).

**GALIMORE_SPRITE, 49,152 bytes** (`.spr`): 16 × `short array[32][48]`, `[x][y]` RGB565. Frame plan
(`spriteguide.html`): front / away / side × still / walk-R / walk-L, side mirrored → 9 used.
`pockets.spr` uses 6 (rest grey).

**RAW, 3072 / 4608 bytes** (`.raw`): headerless 8-bit RGB, **row-major**, 32×32 or 32×48 (Photoshop
Raw export). Pipeline: Photoshop → `.raw` → Galibmap → `.bg/.fg/.get/.spr`.

### 2.2 Galimake: data packer
`.dat` = 2332-byte records back to back (58,300 = 25×2332, 67,628 = 29×2332, 4,664 = 2×2332).
**Stable tile IDs:** maps store 1-based indices; on update Galimake loads the existing `.dat`,
**zeros (doesn't delete) records whose pixels no longer match a file**, refreshes matches, and puts
new tiles in the first blank slot, so map indices never shift.

### 2.3 Mapedit: map editor
Sources `src/mapedit.cpp`, `src/mapeditor_gui.cpp`, `src/g_map.cpp`, `include/g_map.h`.
- 14×14 map view with scroll bars; 4×6 tile palette; layer tabs **Fgnd / Bgnd / Obj / Spr / Mask**;
  floor radios 1F / 2F with show-layer checkboxes; "Make a Mask" and "Eraser" (tile 0).
- Brush sizes 1–4; s / l save / load; Esc quits.
- Mask tab: drag to stamp, right-click to pick up; magenta = no mask, purple = current, black = other.
- **Mask bits:** 0 LAYER_SWITCH, 1 UNPASSABLE_GOOD, 2 UNPASSABLE_BAD, 3 UNPASSABLE_NEUTRAL, 4 DEEP,
  5 BRIDGE, 6 CHASM, 7 PUSHABLE, 8 TRANSPARENT. An older plan (`g_mask.h`, Dec 1999) added exits,
  burnable/bombable/freezable, hot/cold, anti-magic, death, door, soil, farmed, layer 2; "Mask Cases"
  planned a replacement tile in the upper 16 bits (e.g. burnt version) — never implemented.

**GALIMORE_MAP, 114,692 bytes** (arrays `[floor][x][y]`; verified by decoding `house.map`):
| Offset | Size | Field |
|---|---|---|
| 0 | 1 | landscape (always 0) |
| 1 | 8192 | `UINT8 fgLayer[2][64][64]` (N → record N-1 of `fg.dat`; 0 = empty) |
| 8193 | 8192 | `UINT8 bgLayer` → `bg.dat` |
| 16385 | 1 | pad |
| 16386 | 16384 | `UINT16 objectLayer` → `get.dat` |
| 32770 | 16384 | `UINT16 spriteLayer` (unimplemented) |
| 49154 | 2 | pad |
| 49156 | 65536 | `UINT64 maskLayer` |

64×64 cells per floor, 2 floors. Samples: `house.map` (cottage on grass, 14 fg tiles, 1 object, 40
fully-impassable mask cells), `map.map` (lattice test), `test.map` (18 cells of tile 1).

### 2.4 The 1999 tools
GEDIT (32×32, 256 colours, rotate/mirror/replace/transparent colour, 8-frame sprites); GMAP (15×15
maps, layer toggles, exits); GATTRIB (attributes); GTORAW / RAWTOG (bitmap ↔ RGB raw, palette as a
`switch`). The two DOCs are swapped (`GMAP.DOC` documents GEDIT).
- **Bitmap, 1312 B:** bitmapSize, transparentImage, transparencyColor (default 15); `byte
  array[32][32]` palette indices `[x][y]`; attribs (name[21], 3 type bytes, misc, weight,
  description[256]). `BKG.DAT` 19,680 = 15×1312.
- **Sprite, 9262 B:** 8 frames (DOWN1/2, UP1/2, LEFT1/2, RIGHT1/2) + speed, dimensions, direction,
  X, Y + temp array + `struct time`.
- **Map:** 1458 B = `unsigned char Map[6][15][15]` + 6 exits (old: 2808 B with `int`). Exit = name[13]
  + pad + int X, Y. Layers: background, wall, object, scenery, door.

---

## 3. Assets
| Asset | Where | Format |
|---|---|---|
| 2000 tile art | `7_31_00/raw/`, `Galimore Archive/Galimore Tiles/`, `Galimore Specs/Galimore Tiles/` | 32×32 / 16×16 RGB raw |
| 2000 game tiles | `7_31_00/bg` (25), `fg` (29), `get` (2); `X/mapedit_Binary/*.dat` | 2332 B objects (`R/bg.png`, `R/fg.png`, `R/get.png`) |
| Maps | `X/mapedit_Binary/{house,map,test}.map` | 114,692 B (`R/house_crop.png`, `R/map_crop.png`) |
| Sprites | `pockets.spr`, `Sprite Testing/pockets_*.raw`, `Galimore Sprites/*` | `.spr`, raw, `.psd`, `.gif` (`R/pockets.png`) |
| Objects / icons | `Galimore Objects/*`, `The 5 Points/*` | `.psd` / `.psp` |
| World design | `Continent*.psd`, `Experiment Town.psd`, `House Example.jpg` | Photoshop |
| 1999 art | `X/CU_galisource072399/` (70 bitmaps; sprites JABBA/MONK/MONST/PIMP/DOUG/MAN) | 1312 B bitmaps, 9262 B sprites |
| Sound | `Sound Effects/Stephen King/` (21) | Mac resource forks only |

---

## 4. Code quality and notable points
**Good ideas:** stable tile IDs (blank instead of delete); size-based type sniffing; Allegro driver
trimming; reusable ID-dispatched widget toolkit with a "GUI Shell" starter template;
per-function debug gating; Photoshop RAW interop; two-floor maps with a 64-bit per-cell property mask
and layer-switch bit; palette-gradient fire for animated tiles; the editor doubles as the renderer.

**Bugs spotted (reported, not changed):**
1. `g_map.cpp` `saveMap()`/`loadMap()`: `char *fileName; strcpy(fileName, …)` (uninitialized pointer).
2. `g_map.cpp` `drawATile()`: uninitialized `theTileVector`, no `default:` case.
3. `mapeditor_gui.cpp`: `visibleLayers` bit layouts disagree, and init uses `&&` for `&`.
4. "Transparent" mask checkbox has no handler.
5. `GALIMORE_OBJECT::getBitmap()` has no `return`.
6. `convertTo15()` is identical to `convertTo16()`.
7. Sprite-frame copy constructor copies only 32×32 of 32×48; `displayFrame()` size mismatch.
8. Attribute copy/assignment skip `objectWeight`.
9. `~GALIMORE_BITMAP_OBJECT` destroys bitmaps shared by vector copies.
10. `g_mask.h` constants are `unsigned short` but shift up to bit 25 (bits ≥ 16 are zero).
11. `loadDataFile` dedups by pixels, so identical tiles would collapse [inferred risk].
12. `do{}while(infile)` processes the failed final read once more.
13. `.dat` order depends on directory order; memory-dump formats are compiler/endian-specific.

**Unfinished:** no 2000-era game runtime; sprite layer; object attributes; mask replacement tiles;
Linux port; script editor, character generation, NPC AI, OpenPlay networking.

**RPG Tools / Phosphor (Aug 2000):** `rpg_map.h` (map class renamed `C_RPGMap`), `rpg_raw.h` (LGPL),
gcc Makefile, a CodeWarrior project (the only real classic-Mac toolchain artefact), CVS at
`cvs.rpgtools.sourceforge.net`, naming style in `Text Docs/CODING_STYLE.txt` (`C_` classes, `S_`
structs, `g` globals, `k`/`gk` constants).

---

## 5. Relevance to GlitchyGames
Roadmap **#11 "Level/room data format (and tilemaps)"** is open; each game rolls its own
`ScreenData`/`FloorData`/`LevelManager` (`plans/engine-audit.md`).

### 5.1 Worth porting
1. **Map model for #11:** Galimore's ordered layers (bg → fg → objects → actors), per-cell
   properties kept separate from the art, and named exits with entry points. The GlitchyGames
   design built from these ideas, adjusted for today's games and constraints (object layers, a
   typed property vocabulary, exit regions with named spawn points), is
   `plans/2026-10-18-level-tools-a-tilemap-format.md`.
2. **Stable tile IDs:** explicit IDs or tombstones, never list position.
3. **Collision on the map cell, separate from the art.**
4. **Editor features:** Mapedit's brush sizes, property-paint mode with pick-up/stamp, layer and
   floor visibility, tileset palette, eraser = 0; Galibmap's colour wells, frame drag-reorder, and
   the 9-frame walk-cycle convention.
5. **Animated tiles** via animation frames, or a procedural fire buffer.

### 5.2 Converting Galimore data
The survey's read-only decoder (not in this repository) decodes everything below to PNG; sub-plan E
(`plans/2026-10-18-level-tools-e-galimore-import.md`) plans a reviewed converter.
- **Tiles:** `<1024H`, transpose from `[x][y]`, RGB565 → RGB888, `0xF81F` → magenta; write TOML
  `pixels` + `[colors]` (10–60 colours per tile); keep the 1-based `.dat` index as the tile ID.
- **Sprites:** 16 × 32×48 frames (`<1536H`, `[x][y]`); drop all-grey frames; `walk_down` (0–2),
  `walk_up` (3–5), `walk_side` (6–8, mirrored).
- **Raw:** RGB888 row-major → PNG for Bitmappy.
- **Maps:** offsets in §2.3; layers per floor; mask bits → named properties.
- **1999 data:** 1312 B indexed bitmaps (palette from GTORAW or `GALIMORE PALLETE.GIF`; honour
  `transparencyColor`), 9262 B 8-frame sprites, 1458 / 2808 B maps with exits — the best test case
  for a room/exit design.
- **Caveats:** tiles may be RGB555 if saved in 15-bit mode; attribute blocks are empty; sounds need
  resource-fork extraction first (e.g. `DeRez`).
