# Zombies Ain't My Neighbors, Feature 4: The Kids Walk the Neighborhood — Plan

**Status (2026-11-14):** BUILT, uncommitted. The owner approved the four kids' sprites and said
"proceed" to Claude's proposal: the kids walking around the neighborhood.

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md).
**Spec:** the master plan (decisions 4, 5, 11, 16 and 17) and the character BOM's sections 1 to 3.

## Goal

After the title, each joined player walks their own kid around a yard larger than the screen,
with their own keyboard or gamepad, the kids animating (idle and walk, four facings) under one
camera that keeps the whole group on screen.

## Decisions (Claude's calls; the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| Flow | A joined player's start on the title shows the FEATURE PRESENTATION card for 2.0 s, then the neighborhood; start on the card skips straight to it; the card no longer returns to the title (its only way back is the last player unplugging) | A TV title card fits the concept; the card was a placeholder "until gameplay exists" |
| The gameplay scene | `NeighborhoodScene` (`neighborhood.py`), a `RosterScene`, built from the roster; built from options alone (as a recording's first scene is) it has the keyboard as P1 | Goldens build the first scene from options only (engine `GameEngine`, `replay_arguments` applies to later scenes) |
| Kids | `Kid`, an `AnimatedSprite` world sprite (`kid.py`) loaded from the kid's TOML. Its own `dt_tick` advances the animation (and `update()` does nothing), as Papyrus's player does, so it never advances twice | The pose rule (CLAUDE.md, World Space) |
| Animation choice | Idle when still, walk when moving, in the facing nearest the movement (the horizontal one when both are equal); an animation is only started when its name changes, since `play()` resets the frame timer | The engine's `play` gotcha |
| Mirroring | Right uses the left animation, its frames flipped once each and cached by (sprite, animation, frame) in a cache the scene owns and hands to its kids; `hitbox_flip_x` set when facing right | BOM section 1; a module-level cache would trip the process-state guard |
| White hit copies | Not yet: nothing hits a kid in this feature | They come with damage (BOM section 1 says when they are made, not that they exist before a hit can) |
| Movement | 120 px a second (two and a half kid heights), from each player's own device: the keyboard player by WASD or the arrows (scancodes, the same place on every layout); a pad by its left stick (deadzone from the engine's `axis_deadzone`, 0.15 by default) or its d-pad, read on the controller layer when the pad has one, else the joystick layer (axes 0 and 1, hat 0) | Every input mode works, including the joystick mode scripted sessions force |
| Diagonal speed | Normalised, so diagonals are no faster | Fair movement |
| Camera | `Camera2D` with no smoothing, aimed by `camera_target()` at the midpoint of the joined kids' bounding box, bounded to the yard | A bounding-box midpoint keeps a spread group visible, where a centroid does not |
| Co-op screen limit | A kid cannot move so that the group's span exceeds the screen less a 24 px margin on each side, nor leave the yard | Arcade co-op: nobody walks off screen |
| The yard | 1600x960 (two screens by two), a mown checkerboard lawn (48 px squares, two tones) drawn by a camera background layer; the edge is a dark hedge-coloured border. First drawn as vertical stripes; the owner found up and down movement invisible on them (2026-11-14), so checkers | No tiles until the props BOM; checkers show movement both ways |
| Depth | Kids are drawn in order of their feet (lower is in front), by sprite layer, each frame | A top-down view needs it |
| Unplugging | A pad unplugged in the neighborhood removes its kid and frees its slot; an emptied roster goes back to the title | Matches the title and the card |
| Pause | P, or start (Enter, a pad's START), pauses; the shared pause screen resumes with Space | Mr. Muncher's convention; the browser's Esc and Space stay the engine's |
| Goldens | Two: the title's (`golden.jsonl.gz`, as now) and the neighborhood's (`golden-neighborhood.jsonl.gz`), recorded with the neighborhood as its first scene and keyboard P1 walking a square, pausing, resuming and quitting. `main()` starts a replay on the scene its recording names (Brave Adventurer's launcher pattern) | The golden rules (`test_golden_replays.py`) want the recording's game to be the gameplay scene |

## Tasks

1. **`Kid` and the mirror cache** (`kid.py`): loading, facing, idle/walk choice, the mirrored
   image and `hitbox_flip_x`, `dt_tick` advancing the animation. Tests: a kid moving right shows
   the left frame mirrored (pixels), its hitbox flips; an unchanged animation is not restarted
   (the walk cycle advances across ticks); the cache flips each frame once.
2. **Player input** (`controls.py`): a direction per device from the input snapshot and the
   device registry, keyboard and pad, both pad layers, deadzone, normalised diagonals. Tests,
   with stand-in pads: stick, d-pad, hat, keyboard, deadzone, joystick-mode fallback.
3. **`NeighborhoodScene`**: kids for the roster, movement at 120 px/s, the yard bounds, the
   co-op limit, the camera target, depth order, unplugging, pause, the yard background. Tests:
   each behaviour above, the group always on screen (an invariant over many random walks),
   the background never black.
4. **The card leads to the neighborhood**; the title's flow tests updated.
5. **The second golden**: `main()` routing replays by header; the recording scripts, the
   controls tables (polled input, hand-listed controls), the workspace expectations and the
   recording counts (shared files: named in the report). Check: both goldens replay with
   `--verify`.

## Not in this feature

Monsters, neighbors, weapons, hits and white copies, joining mid-game, tiles and the house, and
gamepads in the browser (Game TODOs).

## Rulings made while building (2026-11-14)

- **The card gets a back control** (Backspace, a pad's BACK) returning to the title with everyone
  joined: the title golden must end on the title and press both Enter keys, and the card no
  longer returns on start; back is also useful (more players can join).
- **Pause in the neighborhood is a roster-screen control**: `NeighborhoodScene` is a `RosterScene`,
  so P pauses and start (Enter, a pad's START) pauses through `_press_start`.
- **`main` moved to `launcher.py`**, which starts a replay on its recording's scene.
- **A test assumption fixed**: `test_the_games_of_a_member_with_several_name_their_goldens_apart`
  hard-coded Brave Adventurer's folder; it is now a parameter.
- **The two-player case of the on-screen invariant** did not catch a planted removal of the limit
  (a keyboard and one random pad rarely spread far in 40 bursts); the three- and four-player
  cases do.
- **Diagonal facings added** (owner, 2026-11-14: "I want a diagonal pose"): idle and walk in
  down-left and up-left, drawn as the front and back views turned a quarter; down-right and
  up-right mirror them. `Kid` faces the nearest of eight 45-degree sectors. The goldens were not
  re-recorded: a replay compares sprite rects, visibility and draw order, not pixels, and the
  diagonal frames are the same size. On the way, grey hair strands were limited to near-black
  hair (on Dex's brown they read as stripes).
