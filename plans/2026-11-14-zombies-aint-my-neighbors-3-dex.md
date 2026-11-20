# Zombies Ain't My Neighbors, Feature 3: Dex, the First Kid on the Shared Rig — Plan

**Status (2026-11-14):** BUILT. The owner approved Dex ("Yes, dex looks good"); all four kids are
now written. Theo's back view read as a black hat (the hair ramp shaded into the outline); hair
is now plain with a sheen (grey on dark hair, white on light) and strands on dark hair. Rebuilt at 32x48 in SNES-era
detail after the owner's review of the first 16x24 pass ("they look atari 2600 - I want SNES");
the style was approved on a sample ("Much better"), then the rig was rewritten to it. The owner signed off the character BOM (draft 2.1) and
chose this feature next ("Ok, Let's go", to Claude's suggestion: the first playable stage's
characters, starting with one kid checked by eye before the other three are redrawn on the rig).

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md).
**Spec:** [the character BOM](2026-11-14-zombies-aint-my-neighbors-2-character-bom.md), sections 1
to 3: Dex's 82 frames, their names, timings, loops, transitions, hitbox and palette.

## Goal

Dex's sprite file, `zombies_aint_my_neighbors/sprites/dex.toml`, holding every kid animation the
BOM lists, made by a rig the other three kids will reuse; checked by the engine's sprite-file
checks, by a test that compares it with the BOM, and by eye on a contact sheet before the owner
sees it.

## Decisions (Claude's calls; the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| How the art is made | A rig in the game package (`zombies_aint_my_neighbors/art/`): each frame is composed from body parts (legs, torso, arms, head, hair, headset, clothes) placed by a pose table, painted with a kid's palette, and written as sprite TOML. The TOML is the asset; the rig only writes it | The BOM's shared rig made real: the other kids change the head, clothes and palette, never the poses, so they cannot drift from Dex. A frame typed by hand 82 times would drift |
| Where the rig lives | Inside the import package (`art/`), so it is linted, type-checked, tested and covered by the existing configuration; it is never imported by the game at run time | No new tool configuration; the game's runtime stays the same |
| Regenerating | `uv run python -m zombies_aint_my_neighbors.art.build` rewrites the sprite files; a test fails when a committed file differs from what the rig writes | The TOML in the repository always matches the rig |
| Checking by eye | `uv run python -m zombies_aint_my_neighbors.art.contact_sheet` renders every frame of a sprite at 4x, labelled, to a PNG | Claude looks at it before the owner does |
| Hand points | Generated with the poses, written to `zombies_aint_my_neighbors/art/hand_points.py` data used by the game later | BOM section 1: hand points live in game code, never in the TOML |

## Tasks

1. **The rig and its palette model** (`art/rig.py`, `art/palettes.py`): parts, poses per
   animation frame, a kid's palette (12 colours at most, the shared outline, the player colour on
   the clothes), compositing into a 16x24 character grid with magenta for transparency. Tests:
   every frame is 16x24; only palette characters appear; the outline colour is shared; the poses
   table has exactly the BOM's frame count per animation.
2. **Dex's file** (`art/build.py` writes `sprites/dex.toml`): every BOM namespace for facings
   down, up and left, the intervals, loop flags, `[[transition]]`s where a Then names a namespace
   in the same file, `frame_anchor = "bottom"`, the hitbox `offset_x=3, offset_y=6, width=10,
   height=18`, tags. Tests: the engine's `sprite_files` checks; a BOM-conformance test (every
   namespace, frame count, interval and loop as the BOM says; no right-facing namespaces); the
   committed file equals what the rig writes; the sprite loads through `SpriteFactory`.
3. **Package data**: the sprites ship inside the package; the member's `_package_data` and
   `_wheel` tests (game_packages.md); the wheel test's member data table
   (`tests/test_engine_wheel.py`, a shared file: noted when changed).
4. **The contact sheet and an eye check**: render Dex, look at every animation, fix what reads
   badly, and show the owner the sheet.

## Not in this feature

The other three kids (they follow once the owner approves Dex), hand-point use by weapons,
mirroring and white copies at load time (the game's sprite loader, with the first gameplay
feature), and any monster or neighbor.

## What was built (2026-11-14)

- `art/palettes.py`: four looks on 15-colour ramps (Dex built; Marisol, Theo and June drawn by
  the rig and checked by the shared-rig test, not written to files until Dex is approved).
- `art/poses.py`: the BOM's 12 kid animations, 82 frames of poses.
- `art/rig.py`: 32x48 shaded volumes (ellipse heads, rounded torsos, capsule limbs, lit from the
  top left), each kid's head and clothes details in three facings, auto-outline, knockout,
  loading-in and sparkle frames.
- `art/hand_points.py`: computed from the same poses (never in the TOML).
- `art/build.py` and `art/contact_sheet.py`: `python -m zombies_aint_my_neighbors.art.build`
  writes `sprites/dex.toml` (82 frames, 15 transitions); `...art.contact_sheet --kid dex
  --output sheet.png` renders it.
- Tests (`test_zombies_aint_my_neighbors_art.py`, `_package_data.py`): BOM conformance (names,
  frames, timings, loops, transitions, hitbox, anchor, no right-facing namespaces), 32x48 and
  the palette budget for all four kids, the shared rig (identical silhouettes from the shoulders
  down: it caught Marisol's knee patches and June's stripe overrunning), hand points, the
  committed file equals the rig's output, the engine's sprite-file checks and round trips, the
  sprite loads through `SpriteFactory`, and the wheel carries the file.

Deferred: the wheel test's member-data entry (`tests/test_engine_wheel.py`, a shared file) waits
until the game reads the kids at run time.
